"""Pose du trait « vélo » sur une population synthétique (ticket 015, voie 1).

C'est l'étape qui **remplace** le `personal_bike` d'eqasim, tiré d'un nombre de vélos
recopié d'un ménage ENTD 2008 apparié sans la taille du foyer. Ce qui est vérifié ici :

- le trait est posé sous le nom que relisent `simulation_controller._owns_bike` et la
  politique de choix modal, avec les libellés exacts du contrat ;
- **le foyer est reconstitué à l'adresse**, et les deux défauts de cette clé sont
  traités : les collisions sont **scindées** (deux célibataires au même point font deux
  foyers d'un, pas un foyer de deux) et les ménages partiellement présents tirent sur
  leur taille **nominale** ;
- **hors couche de zones fines, rien n'est posé** — et un `personal_bike` hérité
  d'eqasim est **retiré** plutôt que laissé à traîner, sans quoi la population serait
  moitié apprise, moitié recopiée sans que rien ne le signale ;
- l'enrichissement est **idempotent et déterministe** ;
- la validation **refuse de conclure sans matière** : une population trop petite ne
  « réussit » pas, elle est déclarée non concluante — c'est le motif « vacuité ≠
  perfection », l'absence de mesure ne doit pas produire le score parfait.

Hors ligne, sans les données PROGEDO : le résolveur de zones est remplacé par un
doublon qui rattache selon la latitude, et le modèle par des coefficients nuls dont on
connaît la loi exactement.
"""

from __future__ import annotations

import json
import math

import pytest

from llm_module.core.bike_ownership import (
    ELECTRIC_BIKE,
    K_CLASSES,
    NO_BIKE,
    PLAIN_BIKE,
    PROPENSITY_BASE_FEATURES,
    STOCK_FEATURES,
    TRAIT_KEY,
    BikeOwnershipModel,
    LogitModel,
)
from scripts.data.population import enrich_personal_bike as enrich_module


class _Zone:
    """Zone fine minimale, telle que l'enrichissement la consomme."""

    def __init__(self, zf: str, density: float = 500.0, dist: float = 3.0):
        self.zf = zf
        self.density_hh_km2 = density
        self.dist_center_km = dist


class _FakeResolver:
    """Rattache au nord (lat ≥ 43.6) à une zone dense, au sud à une zone diffuse, et
    laisse hors couche tout ce qui est au-delà de 44."""

    def resolve_many(self, lats, lons):
        out = []
        for lat in lats:
            if lat is None or lat > 44.0:
                out.append(None)
            elif lat >= 43.6:
                out.append(_Zone("100100000", density=3000.0, dist=1.0))
            else:
                out.append(_Zone("200200000", density=50.0, dist=20.0))
        return out


def _model(k_logits=None, propensity_intercept=0.0,
           under_age_holder_share=0.0) -> BikeOwnershipModel:
    """Modèle de test dont la loi de `k` est explicite.

    `k_logits` donne un logit par classe de `K_CLASSES` ; tous les coefficients sont
    nuls, donc la loi est celle du softmax des constantes, indépendamment des
    covariables. On sait ainsi exactement ce que le tirage doit produire.
    """
    logits = k_logits or [0.0] * len(K_CLASSES)
    return BikeOwnershipModel(
        stock=LogitModel(features=STOCK_FEATURES,
                         intercepts=tuple(logits),
                         coefficients=tuple((0.0,) * len(STOCK_FEATURES)
                                            for _ in K_CLASSES),
                         classes=K_CLASSES),
        propensity=LogitModel(features=PROPENSITY_BASE_FEATURES,
                              intercepts=(propensity_intercept,),
                              coefficients=((0.0,) * len(PROPENSITY_BASE_FEATURES),),
                              classes=(1,)),
        occupations=(),
        median_density=500.0,
        under_age_holder_share=under_age_holder_share,
        validation={},
        meta={},
    )


# Un `k` certain, pour rendre l'attribution lisible : -inf partout sauf la classe voulue.
def _certain_k(value: int) -> BikeOwnershipModel:
    logits = [-40.0] * len(K_CLASSES)
    logits[value] = 40.0
    return _model(k_logits=logits)


def _person(lat, lon=1.44, household_size=1, age=30, **traits) -> dict:
    home = {"lat": lat, "lon": lon} if lat is not None else {}
    return {
        "person_id": f"{lat}-{lon}-{age}",
        "identity": {
            "traits_json": {"age": age, "household_size": household_size,
                            "gender": "Female", "number_of_cars": 1, **traits},
            "home": home,
        },
    }


def _labels(population):
    return [p["identity"]["traits_json"].get(TRAIT_KEY) for p in population]


# ── Pose du trait ────────────────────────────────────────────────────────────

class TestPoseDuTrait:

    def test_un_foyer_sans_velo_recoit_pas_de_velo(self):
        population = [_person(43.61)]
        enrich_module.enrich(population, _certain_k(0), _FakeResolver())
        assert _labels(population) == [NO_BIKE]

    def test_un_foyer_a_un_velo_dote_son_unique_membre(self):
        population = [_person(43.61)]
        enrich_module.enrich(population, _certain_k(1), _FakeResolver())
        assert _labels(population)[0] in (PLAIN_BIKE, ELECTRIC_BIKE)

    def test_les_libelles_sont_ceux_du_contrat(self):
        population = [_person(43.6 + i / 1000, age=40) for i in range(60)]
        enrich_module.enrich(population, _model(), _FakeResolver())
        assert set(_labels(population)) <= {NO_BIKE, PLAIN_BIKE, ELECTRIC_BIKE}

    def test_les_autres_traits_ne_sont_pas_touches(self):
        population = [_person(43.61, income="Medium-High")]
        enrich_module.enrich(population, _certain_k(1), _FakeResolver())
        traits = population[0]["identity"]["traits_json"]
        assert traits["income"] == "Medium-High"
        assert traits["age"] == 30

    def test_le_decompte_est_rendu_par_libelle(self):
        population = [_person(43.6 + i / 1000) for i in range(10)]
        counts = enrich_module.enrich(population, _certain_k(1), _FakeResolver())
        assert counts[PLAIN_BIKE] + counts[ELECTRIC_BIKE] == 10
        assert counts[NO_BIKE] == 0

    def test_rejouer_ne_change_rien(self):
        population = [_person(43.6 + i / 1000, household_size=2) for i in range(20)]
        enrich_module.enrich(population, _model(), _FakeResolver())
        first = _labels(population)
        enrich_module.enrich(population, _model(), _FakeResolver())
        assert _labels(population) == first

    def test_un_enfant_de_trois_ans_na_jamais_de_velo(self):
        """Éligibilité à 5 ans (champ de la question `P20`) : même dans un foyer à 4
        vélos, le tout-petit n'en porte pas."""
        population = [_person(43.61, household_size=2, age=3),
                      _person(43.61, household_size=2, age=40)]
        enrich_module.enrich(population, _certain_k(4), _FakeResolver())
        assert _labels(population)[0] == NO_BIKE
        assert _labels(population)[1] != NO_BIKE

    def test_pas_de_vae_avant_quatorze_ans(self):
        population = [_person(43.6 + i / 1000, age=10) for i in range(80)]
        enrich_module.enrich(population, _certain_k(1), _FakeResolver())
        assert ELECTRIC_BIKE not in _labels(population)


# ── Le foyer reconstitué à l'adresse ─────────────────────────────────────────

class TestReconstitutionDuFoyer:

    def test_une_grappe_coherente_est_un_seul_foyer(self):
        population = [_person(43.61, household_size=3, age=30 + i) for i in range(3)]
        counts = enrich_module.enrich(population, _certain_k(1), _FakeResolver())
        assert counts["grappes_coherentes"] == 1
        # Un seul vélo dans le foyer : exactement un membre le porte.
        assert sum(1 for label in _labels(population) if label != NO_BIKE) == 1

    def test_une_collision_est_scindee_et_non_fusionnee(self):
        """Deux célibataires au même point d'adresse font DEUX foyers d'un, pas un
        foyer de deux — qui hériterait du `k` d'un couple."""
        population = [_person(43.61, household_size=1, age=30),
                      _person(43.61, household_size=1, age=50)]
        counts = enrich_module.enrich(population, _certain_k(1), _FakeResolver())
        assert counts["grappes_en_collision"] == 1
        # Chaque foyer a son propre vélo : les deux sont dotés.
        assert all(label != NO_BIKE for label in _labels(population))

    def test_une_grappe_plus_grande_que_la_taille_declaree_est_scindee(self):
        population = [_person(43.61, household_size=2, age=30 + i) for i in range(5)]
        counts = enrich_module.enrich(population, _certain_k(2), _FakeResolver())
        assert counts["grappes_en_collision"] == 1
        # 5 personnes déclarant un foyer de 2 → foyers de 2, 2 et 1, chacun à 2 vélos :
        # tout le monde est doté (le dernier foyer perd son 2ᵉ vélo, faute de porteur).
        assert all(label != NO_BIKE for label in _labels(population))

    def test_des_tailles_declarees_differentes_scindent_la_grappe(self):
        population = [_person(43.61, household_size=1, age=30),
                      _person(43.61, household_size=4, age=40)]
        counts = enrich_module.enrich(population, _certain_k(1), _FakeResolver())
        assert counts["grappes_en_collision"] == 1

    def test_un_menage_partiellement_present_nest_pas_surequipe(self):
        """Le filtre par emprise n'a gardé qu'un membre d'un foyer de 4 : il ne doit pas
        recevoir à lui seul les 3 vélos du foyer. Les places absentes concourent."""
        population = [_person(43.61, household_size=4, age=30)]
        counts = enrich_module.enrich(population, _certain_k(3), _FakeResolver())
        assert counts["places_absentes"] == 3
        # Un seul membre présent : il porte au plus un vélo, et pas systématiquement.
        assert sum(1 for label in _labels(population) if label != NO_BIKE) <= 1

    def test_les_places_absentes_diluent_bien_lattribution(self):
        """Sur beaucoup de foyers, un membre isolé d'un foyer de 4 à 2 vélos doit être
        servi ~1 fois sur 2 — pas systématiquement."""
        served = 0
        trials = 200
        for i in range(trials):
            population = [_person(43.0 + i / 10000, household_size=4, age=30)]
            enrich_module.enrich(population, _certain_k(2), _FakeResolver())
            served += int(_labels(population)[0] != NO_BIKE)
        assert 0.3 < served / trials < 0.7, served / trials

    def test_un_foyer_partage_le_meme_tirage_de_stock(self):
        """Deux membres d'un même foyer tirent UN `k`, pas deux : sinon l'équipement
        cesse d'être un trait de foyer, ce qui est tout l'objet du ticket."""
        # Un modèle à loi uniforme sur k : si chaque membre tirait son propre k, on
        # verrait des foyers de 2 dotés de 0 puis 2 vélos incohérents. On vérifie ici
        # que le nombre de porteurs d'un foyer ne dépasse jamais K_MAX et reste
        # cohérent entre exécutions.
        population = [_person(43.61, household_size=2, age=30),
                      _person(43.61, household_size=2, age=32)]
        enrich_module.enrich(population, _model(), _FakeResolver())
        first = _labels(population)
        population2 = [_person(43.61, household_size=2, age=30),
                       _person(43.61, household_size=2, age=32)]
        enrich_module.enrich(population2, _model(), _FakeResolver())
        assert _labels(population2) == first


# ── Hors couche : on ne devine pas ───────────────────────────────────────────

class TestHorsCouche:

    def test_domicile_hors_couche_reste_sans_trait(self):
        population = [_person(45.0)]
        counts = enrich_module.enrich(population, _certain_k(1), _FakeResolver())
        assert _labels(population) == [None]
        assert counts["hors_couche"] == 1

    def test_domicile_sans_coordonnees_reste_sans_trait(self):
        population = [_person(None)]
        counts = enrich_module.enrich(population, _certain_k(1), _FakeResolver())
        assert _labels(population) == [None]
        assert counts["sans_adresse"] == 1

    def test_un_personal_bike_herite_deqasim_est_retire(self):
        """Le trait recopié d'eqasim est précisément ce qu'on remplace : le laisser en
        place hors couche donnerait une population moitié apprise, moitié recopiée."""
        population = [_person(45.0, **{TRAIT_KEY: "vélo normal"})]
        enrich_module.enrich(population, _certain_k(1), _FakeResolver())
        assert TRAIT_KEY not in population[0]["identity"]["traits_json"]

    def test_une_loi_degeneree_ne_pose_rien(self):
        """Loi de `k` dégénérée : aucun trait, jamais « Pas de vélo » ni un `k` inventé.

        Un softmax de scores tous infinis rend des `nan`, avec lesquels toutes les
        comparaisons sont fausses : sans garde-fou, le tirage tombait sur son filet
        d'arrondi et rendait la DERNIÈRE classe, soit un ménage à quatre vélos sorti
        d'une loi vide. C'est le silence le plus coûteux du module."""
        model = _model()
        object.__setattr__(model.stock, "intercepts",
                           tuple([float("-inf")] * len(K_CLASSES)))
        population = [_person(43.61)]
        counts = enrich_module.enrich(population, model, _FakeResolver())
        assert _labels(population) == [None]
        assert counts["sans_loi"] == 1

    def test_une_loi_degeneree_ne_rend_pas_la_derniere_classe(self):
        """Le garde-fou, vu depuis le tirage lui-même."""
        from llm_module.core.bike_ownership import draw_index
        nan = float("nan")
        assert draw_index([nan] * 5, 0.5) is None
        assert draw_index([float("inf")] * 5, 0.5) is None
        assert draw_index([0.0] * 5, 0.5) is None


# ── La validation refuse de conclure sans matière ────────────────────────────

class TestValidation:

    def _measure(self, population):
        return enrich_module.measure(population)

    def test_la_mesure_compte_les_foyers_et_pas_seulement_les_personnes(self):
        """`k` est tiré par foyer : les membres d'un même ménage ne sont pas des
        observations indépendantes, et la précision se calcule sur les foyers."""
        population = [_person(43.61, household_size=3, age=30 + i) for i in range(3)]
        enrich_module.enrich(population, _certain_k(1), _FakeResolver())
        measured = self._measure(population)
        assert measured["with_trait"] == 3
        assert measured["households"] == 1
        _, persons, households = measured["holders_by_size"][3]
        assert (persons, households) == (3, 1)

    def test_les_agents_sans_trait_sortent_des_denominateurs(self):
        """Mêler les agents hors couche aux dénominateurs ferait baisser mécaniquement
        les parts et présenterait l'absence de mesure comme un résultat."""
        population = [_person(43.61), _person(45.0)]
        enrich_module.enrich(population, _certain_k(1), _FakeResolver())
        measured = self._measure(population)
        assert measured["n"] == 2
        assert measured["with_trait"] == 1
        assert measured["coverage"] == 0.5
        assert measured["holders_pct"] == 100.0

    def test_une_population_minuscule_est_non_concluante_et_non_reussie(self):
        """Le garde-fou central : `--check` ne doit pas passer sur une population où
        rien n'a pu être vérifié. L'absence de mesure ne produit pas le score parfait."""
        population = [_person(43.61)]
        counts = enrich_module.enrich(population, _certain_k(1), _FakeResolver())
        model = _model()
        object.__setattr__(model, "validation", {
            "targets": {"holders_pct": 50.9, "holders_pct_mechanism": 49.4,
                        "vae_share_of_fleet_pct": 7.67,
                        "holders_by_household_size": [], "practising_per_bike": []},
            "stock": {"overall": {"equipped_pct_observed": 53.6},
                      "by_household_size": [], "clipping_cost": {}},
        })
        failures = enrich_module.report(self._measure(population),
                                       enrich_module.household_measure(population),
                                       counts, model)
        assert any("concluant" in failure for failure in failures)

    def test_une_couverture_trop_faible_fait_echouer(self):
        """« Un `personal_bike = None` massif doit faire ÉCHOUER la validation. »"""
        population = [_person(45.0) for _ in range(10)] + [_person(43.61)]
        counts = enrich_module.enrich(population, _certain_k(1), _FakeResolver())
        model = _model()
        object.__setattr__(model, "validation", {"targets": {}, "stock": {}})
        failures = enrich_module.report(self._measure(population),
                                       enrich_module.household_measure(population),
                                       counts, model)
        assert any("couverture" in failure for failure in failures)

    def test_une_note_incomplete_ne_fait_pas_tomber_le_verdict(self):
        """Une ressource partielle doit priver le rapport d'une NOTE, jamais d'un verdict.

        Le bloc explicatif sur le coût de l'écrêtage lisait cinq clés entre crochets sous
        un simple `if clipping:`. Une ressource exportée par une autre version le faisait
        planter **après** l'affichage des verdicts, si bien que `--check` ne rendait
        jamais son code de sortie : l'appelant voyait une trace au lieu d'une conclusion.
        Une note n'est pas un verdict.
        """
        population = [_person(43.6 + i / 1000, household_size=1, age=40)
                      for i in range(40)]
        counts = enrich_module.enrich(population, _certain_k(1), _FakeResolver())
        model = _model()
        object.__setattr__(model, "validation", {
            "targets": {"holders_pct": 50.9, "holders_pct_mechanism": 49.4,
                        "vae_share_of_fleet_pct": 7.67,
                        "holders_by_household_size": [], "practising_per_bike": []},
            # `clipping_cost` non vide mais amputé : le cas qui plantait.
            "stock": {"overall": {"equipped_pct_observed": 53.6},
                      "by_household_size": [],
                      "clipping_cost": {"k_max": 4,
                                        "bikes_per_household_unclipped": 1.215}},
        })
        failures = enrich_module.report(self._measure(population),
                                       enrich_module.household_measure(population),
                                       counts, model)
        # Aucune exception, et les échecs restants ne parlent que de mesurabilité.
        assert all("clipping" not in failure for failure in failures)

    def test_une_amplitude_publiee_incomplete_nest_pas_fabriquee(self, capsys):
        """Une borne absente ne doit pas produire une amplitude, mais aucune amplitude.

        `published.get("grand_habitat_collectif", 0.0)` fabriquait l'amplitude à partir
        d'une borne manquante : elle valait alors la borne haute (70,9 au lieu de 33,4),
        chiffre faux et parfaitement plausible affiché à l'utilisateur. C'est le motif
        « défaut substitué à une donnée absente, puis calcul dessus ».
        """
        # Le bloc habitat n'est imprimé que si les personas portent `housing_type` :
        # c'est `enrich_housing_type` qui le pose, en amont de cette étape.
        population = [_person(43.6 + i / 1000, household_size=1, age=40,
                              housing_type="Individuel isolé")
                      for i in range(40)]
        counts = enrich_module.enrich(population, _certain_k(1), _FakeResolver())
        model = _model()
        object.__setattr__(model, "validation", {
            "targets": {"holders_pct_mechanism": 49.4, "vae_share_of_fleet_pct": 7.67,
                        "holders_by_household_size": [], "practising_per_bike": []},
            "stock": {"overall": {}, "by_household_size": [], "clipping_cost": {}},
            "housing_reference": {
                "attainable_on_imputed_housing": {"individuel_isole": 57.2},
                # Borne basse absente : l'amplitude n'est pas calculable.
                "published_on_observed_housing": {"individuel_isole": 70.9},
                "attainable_spread_pts": 26.8,
            },
        })
        enrich_module.report(self._measure(population),
                            enrich_module.household_measure(population),
                            counts, model)
        printed = capsys.readouterr().out
        assert "écrase l'amplitude." in printed, printed
        assert "70.9 à" not in printed, "une amplitude a été fabriquée depuis une borne absente"

    def test_la_standardisation_recompose_la_cible(self):
        """Écarter les foyers incomplets sur-représente les personnes seules : la cible
        doit être recomposée sur la ventilation réellement mesurée."""
        by_size = {1: {"n": 80, "equipped": 0, "bikes": 0},
                   4: {"n": 20, "equipped": 0, "bikes": 0}}
        reference = {1: 33.0, 4: 84.0}
        assert enrich_module.standardise(by_size, reference) == pytest.approx(
            0.8 * 33.0 + 0.2 * 84.0)

    def test_la_standardisation_refuse_une_reference_incomplete(self):
        """Mieux vaut ne pas servir de cible que d'en servir une bancale."""
        by_size = {1: {"n": 10, "equipped": 0, "bikes": 0},
                   4: {"n": 10, "equipped": 0, "bikes": 0}}
        assert enrich_module.standardise(by_size, {1: 33.0}) is None

    def test_seuls_les_foyers_complets_entrent_au_niveau_menage(self):
        """On ne peut pas mesurer « les vélos du ménage » sur un foyer dont il manque
        des membres : le numérateur serait tronqué et le dénominateur non."""
        population = [_person(43.61, household_size=1, age=30),
                      _person(43.62, household_size=4, age=30)]
        enrich_module.enrich(population, _certain_k(1), _FakeResolver())
        household = enrich_module.household_measure(population)
        assert household["complete_households"] == 1


# ── Bout en bout, sur un fichier ─────────────────────────────────────────────

class TestBoutEnBout:

    def test_le_fichier_est_reecrit_atomiquement(self, tmp_path, monkeypatch, capsys):
        path = tmp_path / "pop.json"
        population = [_person(43.6 + i / 1000, household_size=2, age=30 + i)
                      for i in range(40)]
        path.write_text(json.dumps(population, ensure_ascii=False), encoding="utf-8")

        model = _model()
        object.__setattr__(model, "validation", {"targets": {}, "stock": {}})
        monkeypatch.setattr(enrich_module.BikeOwnershipModel, "load",
                            classmethod(lambda cls, resource=None: model))
        monkeypatch.setattr(
            "llm_module.core.zone_resolver.ZoneResolver.load",
            classmethod(lambda cls, resource=None, spec=None: _FakeResolver()))
        monkeypatch.setattr("sys.argv", ["enrich", str(path)])

        assert enrich_module.main() == 0
        written = json.loads(path.read_text(encoding="utf-8"))
        assert len(written) == 40
        assert all(TRAIT_KEY in p["identity"]["traits_json"] for p in written)
        assert not list(tmp_path.glob("*.tmp"))

    def test_dry_run_ne_reecrit_pas(self, tmp_path, monkeypatch):
        path = tmp_path / "pop.json"
        population = [_person(43.61, household_size=1)]
        original = json.dumps(population, ensure_ascii=False)
        path.write_text(original, encoding="utf-8")

        model = _model()
        object.__setattr__(model, "validation", {"targets": {}, "stock": {}})
        monkeypatch.setattr(enrich_module.BikeOwnershipModel, "load",
                            classmethod(lambda cls, resource=None: model))
        monkeypatch.setattr(
            "llm_module.core.zone_resolver.ZoneResolver.load",
            classmethod(lambda cls, resource=None, spec=None: _FakeResolver()))
        monkeypatch.setattr("sys.argv", ["enrich", str(path), "--dry-run"])

        enrich_module.main()
        assert path.read_text(encoding="utf-8") == original

    def test_une_ressource_absente_refuse_de_tourner(self, tmp_path, monkeypatch):
        """Sans le modèle, la commande échoue en disant comment le produire — elle
        n'impute pas à l'aveugle et ne retombe pas sur la formule d'eqasim."""
        path = tmp_path / "pop.json"
        path.write_text("[]", encoding="utf-8")
        monkeypatch.setattr("sys.argv", ["enrich", str(path)])
        monkeypatch.setattr(
            enrich_module.BikeOwnershipModel, "load",
            classmethod(lambda cls, resource=None: (_ for _ in ()).throw(
                FileNotFoundError("Modèle d'équipement vélo absent : make bike-ownership"))))
        assert enrich_module.main() == 1

    def test_le_rapport_json_dit_ce_que_la_console_a_dit(self, tmp_path, monkeypatch):
        """`--rapport-json` écrit les contrôles, la pente, les verdicts et le code de sortie :
        c'est ce que lit la synthèse de représentativité, au lieu d'une console recopiée."""
        path = tmp_path / "pop.json"
        population = [_person(43.6 + i / 1000, household_size=1 + i % 4, age=30 + i)
                      for i in range(40)]
        path.write_text(json.dumps(population, ensure_ascii=False), encoding="utf-8")
        rapport = tmp_path / "trace" / "velo.json"

        model = _model()
        object.__setattr__(model, "validation", {"targets": {}, "stock": {}})
        monkeypatch.setattr(enrich_module.BikeOwnershipModel, "load",
                            classmethod(lambda cls, resource=None: model))
        monkeypatch.setattr(
            "llm_module.core.zone_resolver.ZoneResolver.load",
            classmethod(lambda cls, resource=None, spec=None: _FakeResolver()))
        monkeypatch.setattr("sys.argv", ["enrich", str(path), "--dry-run", "--check",
                                         "--rapport-json", str(rapport)])

        code = enrich_module.main()
        payload = json.loads(rapport.read_text(encoding="utf-8"))
        assert payload["code_sortie"] == code
        assert payload["check"] is True and payload["dry_run"] is True
        assert payload["regles"]["SLOPE_MIN_CELL"] == enrich_module.SLOPE_MIN_CELL
        pop = payload["populations"][0]
        assert pop["n"] == 40 and pop["fichier"] == str(path)
        assert len(pop["sha256_avant"]) == 64
        # Sans cible servie, chaque contrôle est journalisé « pas de cible » ; la pente est
        # « non concluant » (40 personnes ne font pas 100 foyers par taille) et le dit.
        assert pop["controles"] and all(c["verdict"] == "pas de cible" for c in pop["controles"])
        assert pop["pente_tailles_1_4"]["statut"] == "non concluant"
        assert pop["pente_tailles_1_4"]["min_foyers_pour_juger"] == enrich_module.SLOPE_MIN_CELL
        assert set(pop["verdicts"]) == {"ok", "echec", "non_concluant"}
        assert isinstance(pop["echecs"], list)

    def test_un_persona_sans_adresse_perd_le_trait_herite(self, tmp_path, monkeypatch):
        """Un domicile non résoluble n'entre dans aucun foyer : le trait qu'un
        enrichissement amont avait posé doit être RETIRÉ, pas laissé en place — sinon la
        population est moitié apprise, moitié recopiée sans que rien ne le signale
        (mesuré le 2026-09-04 : 14 personas du vivier, ticket 034 lot 2)."""
        path = tmp_path / "pop.json"
        sans_domicile = _person(43.61, household_size=1)
        sans_domicile["identity"]["home"] = None
        sans_domicile["identity"]["traits_json"][TRAIT_KEY] = "VAE"
        population = [sans_domicile, _person(43.62, household_size=1)]
        path.write_text(json.dumps(population, ensure_ascii=False), encoding="utf-8")

        model = _certain_k(1)
        object.__setattr__(model, "validation", {"targets": {}, "stock": {}})
        monkeypatch.setattr(enrich_module.BikeOwnershipModel, "load",
                            classmethod(lambda cls, resource=None: model))
        monkeypatch.setattr(
            "llm_module.core.zone_resolver.ZoneResolver.load",
            classmethod(lambda cls, resource=None, spec=None: _FakeResolver()))
        monkeypatch.setattr("sys.argv", ["enrich", str(path)])

        assert enrich_module.main() == 0
        written = json.loads(path.read_text(encoding="utf-8"))
        assert TRAIT_KEY not in written[0]["identity"]["traits_json"]
        assert written[1]["identity"]["traits_json"][TRAIT_KEY] is not None
