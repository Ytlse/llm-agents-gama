"""Tests du trait « vélo » (core/bike_ownership.py, ticket 015).

Le trait est **appris puis tiré** : aucun contrôle en aval ne peut distinguer, en
regardant une ligne, une attribution correcte d'une attribution biaisée. Ce qui est
verrouillé ici, ce sont donc les propriétés que le mécanisme doit avoir en masse, et
les frontières qu'il ne doit jamais franchir :

- **le stock fixe le niveau, la propension ne fixe que l'ordre** — `assign` attribue
  exactement `min(k, éligibles)` vélos, jamais plus parce qu'un membre est très
  cycliste, jamais moins parce qu'aucun ne l'est. C'est l'inversion que le ticket
  interdit, et c'est la propriété la plus facile à casser par accident ;
- **la propension biaise dans le bon sens** — un membre plus cycliste est servi plus
  souvent, sinon l'étage 2 ne sert à rien ;
- **il n'y a aucun ordre déterministe** — pas de « toujours l'aîné », pas d'artefact de
  tri sur les ex æquo : à propensions égales, les membres doivent être servis à peu près
  autant les uns que les autres ;
- **le tirage est déterministe** — pas d'un RNG, pas de `hash()` (randomisé par
  processus) : deux exécutions, deux machines, deux moments donnent le même parc ;
- **les vélos dormants existent** — un ménage bien doté sert des membres de faible
  propension, et c'est voulu : un vélo au garage est un vélo ;
- **rien n'est deviné** — loi vide, ressource absente ou features divergentes lèvent au
  lieu de produire « Pas de vélo », qui est une valeur plausible et donc indétectable ;
- **le VAE est une part de parc, pas de porteurs** — et le filtre d'âge est renormalisé,
  sinon la cible est manquée par le bas.

Hors ligne, sans les données PROGEDO. Les tests de parité avec la vraie ressource se
sautent d'eux-mêmes quand elle n'a pas été exportée.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from llm_module.core.bike_ownership import (
    DEFAULT_RESOURCE,
    ELECTRIC_BIKE,
    K_CLASSES,
    K_MAX,
    LABELS,
    MIN_AGE_ELECTRIC,
    MIN_AGE_ELIGIBLE,
    NO_BIKE,
    PLAIN_BIKE,
    PROPENSITY_BASE_FEATURES,
    RESOURCE_VERSION,
    STOCK_FEATURES,
    TRAIT_KEY,
    VAE_SHARE,
    BikeOwnershipModel,
    LogitModel,
    Member,
    address_key,
    assign,
    bike_label,
    draw_index,
    electric_probability,
    propensity_design,
    stock_design,
    uniform,
)


def _members(propensities, eligible=None, present=None) -> list[Member]:
    return [
        Member(index=i,
               propensity=p,
               eligible=True if eligible is None else eligible[i],
               present=True if present is None else present[i])
        for i, p in enumerate(propensities)
    ]


# ── Étage 2 : l'attribution, le cœur du ticket ───────────────────────────────

class TestAttribution:
    """« `k` décide combien, la propension décide seulement qui. »"""

    @pytest.mark.parametrize("k", [0, 1, 2, 3, 4])
    def test_le_nombre_attribue_est_exactement_k(self, k):
        members = _members([0.9, 0.5, 0.2, 0.05])
        assert len(assign(members, k, "foyer")) == k

    def test_une_propension_ecrasante_ne_cree_pas_de_velo(self):
        """Le membre le plus cycliste du monde ne fait pas apparaître un 2ᵉ vélo."""
        members = _members([0.999999, 0.000001, 0.000001])
        assert len(assign(members, 1, "foyer")) == 1

    def test_des_propensions_nulles_nempechent_pas_de_servir(self):
        """`k` fixe le niveau : si le foyer a 2 vélos, 2 membres les tiennent, même si
        aucun ne roule. Ce sont les vélos dormants, et il est juste de les représenter."""
        members = _members([0.0, 0.0, 0.0])
        assert len(assign(members, 2, "foyer")) == 2

    def test_le_surplus_de_velos_nest_porte_par_personne(self):
        """`k > éligibles` : un vélo sans titulaire n'apparaît pas dans le JSON."""
        members = _members([0.5, 0.5])
        assert len(assign(members, 4, "foyer")) == 2

    def test_les_ineligibles_ne_recoivent_jamais_de_velo(self):
        """Champ de la question `P20` : interdit d'attribuer le vélo du foyer à un
        enfant de trois ans, même quand le foyer en a plus que de membres éligibles."""
        members = _members([0.9, 0.9, 0.9], eligible=[True, False, False])
        assert assign(members, 3, "foyer") == {0}

    def test_aucun_velo_si_personne_nest_eligible(self):
        members = _members([0.9, 0.9], eligible=[False, False])
        assert assign(members, 2, "foyer") == set()

    def test_la_propension_biaise_le_service(self):
        """Sur beaucoup de foyers à 1 vélo, le membre cycliste doit être servi
        nettement plus souvent — sinon l'étage 2 ne sert à rien."""
        served = Counter()
        for foyer in range(2000):
            members = _members([0.8, 0.1])
            for index in assign(members, 1, f"foyer-{foyer}"):
                served[index] += 1
        assert served[0] > served[1] * 2

    def test_a_propension_egale_aucun_ordre_deterministe(self):
        """Pas de « toujours l'aîné » : à propensions égales, les deux membres doivent
        être servis à peu près autant. Un tri stable sur l'index donnerait 2000/0."""
        served = Counter()
        for foyer in range(2000):
            members = _members([0.4, 0.4])
            for index in assign(members, 1, f"foyer-{foyer}"):
                served[index] += 1
        assert 800 < served[0] < 1200
        assert served[0] + served[1] == 2000

    def test_les_places_absentes_peuvent_emporter_un_velo(self):
        """Un ménage nominal de 4 dont un seul membre est présent ne doit pas recevoir
        les 3 vélos du foyer : les places absentes concourent au tirage."""
        present_only = _members([0.5])
        assert len(assign(present_only, 3, "foyer")) == 1

        with_absent = [Member(index=0, propensity=0.5, eligible=True, present=True)] + [
            Member(index=-1 - j, propensity=0.5, eligible=True, present=False)
            for j in range(3)
        ]
        chosen = assign(with_absent, 3, "foyer")
        assert len(chosen) == 3
        # Le membre présent n'est pas servi systématiquement : il concourt avec les
        # trois absents pour 3 places sur 4.
        served = sum(1 for f in range(400)
                     if 0 in assign(
                         [Member(index=0, propensity=0.5, eligible=True)] +
                         [Member(index=-1 - j, propensity=0.5, eligible=True)
                          for j in range(3)], 3, f"foyer-{f}"))
        assert 250 < served < 390

    def test_le_tirage_est_deterministe(self):
        members = _members([0.6, 0.3, 0.1])
        assert assign(members, 2, "foyer-x") == assign(members, 2, "foyer-x")

    def test_deux_foyers_ne_tirent_pas_la_meme_chose(self):
        """La clé de ménage entre dans le hachage : sinon tous les foyers du fichier
        servent le même rang de membre."""
        members = _members([0.5, 0.5, 0.5])
        results = {frozenset(assign(members, 1, f"foyer-{i}")) for i in range(50)}
        assert len(results) > 1


# ── Étage 3 : le type de vélo ────────────────────────────────────────────────

class TestTypeDeVelo:

    def test_pas_de_vae_sous_lage_minimum(self):
        for age in (0, 5, MIN_AGE_ELECTRIC - 1):
            labels = {bike_label(f"foyer-{i}", 0, age) for i in range(200)}
            assert labels == {PLAIN_BIKE}

    def test_le_vae_existe_au_dela_de_lage_minimum(self):
        labels = {bike_label(f"foyer-{i}", 0, MIN_AGE_ELECTRIC) for i in range(500)}
        assert labels == {PLAIN_BIKE, ELECTRIC_BIKE}

    def test_la_part_de_vae_est_celle_du_parc(self):
        """7,7 % du parc — et non 14,8 %, qui est la part des *ménages équipés* ayant un
        VAE et que l'ancienne imputation appliquait (1,7× trop de VAE)."""
        electric = sum(bike_label(f"foyer-{i}", 0, 40) == ELECTRIC_BIKE
                       for i in range(20000))
        assert abs(electric / 20000 - VAE_SHARE) < 0.01

    def test_le_filtre_dage_est_renormalise(self):
        """Appliquer `VAE_SHARE` aux seuls éligibles ferait sortir le parc SOUS la
        cible, à proportion des vélos tenus par des enfants."""
        assert electric_probability(0.0) == pytest.approx(VAE_SHARE)
        assert electric_probability(0.2) == pytest.approx(VAE_SHARE / 0.8)
        # Un parc dont 20 % des porteurs sont trop jeunes atteint bien la cible.
        p = electric_probability(0.2)
        assert pytest.approx(0.8 * p, abs=1e-9) == VAE_SHARE

    def test_la_renormalisation_est_bornee(self):
        """Au-delà de 50 % de porteurs inéligibles, on ne multiplie pas indéfiniment."""
        assert electric_probability(0.99) == pytest.approx(VAE_SHARE / 0.5)
        assert electric_probability(-1.0) == pytest.approx(VAE_SHARE)

    def test_le_type_est_decorrele_du_rang_dattribution(self):
        """Sel distinct de celui de l'attribution : sinon les VAE iraient
        systématiquement aux hautes propensions."""
        keys = [uniform(f"bike-holder:foyer:{i}") for i in range(200)]
        kinds = [uniform(f"bike-kind:foyer:{i}") for i in range(200)]
        assert keys != kinds


# ── Déterminisme et clés ─────────────────────────────────────────────────────

class TestDeterminisme:

    def test_la_clé_dadresse_est_stable_et_arrondie(self):
        assert address_key(43.6047, 1.4442) == address_key(43.60470004, 1.44420004)
        assert address_key(43.6047, 1.4442) != address_key(43.6048, 1.4442)

    def test_luniforme_est_dans_lintervalle_et_reproductible(self):
        for key in ("a", "foyer:12", "43.6,1.4"):
            value = uniform(key)
            assert 0.0 <= value < 1.0
            assert value == uniform(key)

    def test_luniforme_ne_depend_pas_du_hash_de_python(self):
        """Valeur gelée : si elle bouge, tout le parc a bougé, et ça doit être un acte
        délibéré (changement de `DRAW_SALT`), pas un effet de bord."""
        assert uniform("foyer-temoin") == pytest.approx(0.2768345234349732, abs=1e-12)


# ── Tirages et lois ──────────────────────────────────────────────────────────

class TestTirage:

    def test_une_loi_vide_ne_rend_rien(self):
        """Tirer depuis rien rendrait 0 — « pas de vélo » — donc indétectable."""
        assert draw_index([], 0.5) is None
        assert draw_index([0.0, 0.0, 0.0], 0.5) is None

    def test_le_tirage_suit_la_loi(self):
        law = [0.5, 0.3, 0.2]
        counts = Counter(draw_index(law, i / 10000) for i in range(10000))
        assert abs(counts[0] / 10000 - 0.5) < 0.01
        assert abs(counts[1] / 10000 - 0.3) < 0.01
        assert abs(counts[2] / 10000 - 0.2) < 0.01

    def test_le_tirage_ne_sort_jamais_de_lintervalle(self):
        assert draw_index([0.5, 0.5], 0.0) == 0
        assert draw_index([0.5, 0.5], 0.999999) == 1


# ── Vecteurs de design : le contrat entraînement / application ───────────────

class TestDesign:

    def test_les_features_du_stock_sont_celles_du_contrat(self):
        design = stock_design(2, 1, 500.0, 3.0)
        assert set(design) == set(STOCK_FEATURES)

    def test_les_features_de_propension_sont_celles_du_contrat(self):
        design = propensity_design(2, 3, 40, "Female", "Retraité", 500.0, 3.0,
                                   ("Retraité", "Étudiant"))
        assert set(design) == set(PROPENSITY_BASE_FEATURES) | {
            "occ_Retraité", "occ_Étudiant"}

    def test_la_taille_est_ecretee(self):
        assert stock_design(4, 0, 1.0, 1.0) == stock_design(9, 0, 1.0, 1.0)

    def test_le_stock_est_ecrete_dans_la_propension(self):
        assert (propensity_design(4, 2, 30, "Male", None, 1.0, 1.0, ())
                == propensity_design(9, 2, 30, "Male", None, 1.0, 1.0, ()))

    def test_une_taille_absurde_ne_leve_pas(self):
        """Une population mal formée ne doit pas faire tomber l'enrichissement : la
        taille est bornée par le bas, pas rejetée."""
        assert stock_design(0, None, None, 0.0)["size2"] == 0.0

    def test_un_age_absent_neutralise_les_termes_dage(self):
        design = propensity_design(1, 1, None, None, None, 1.0, 1.0, ())
        assert design["age"] == 0.0 and design["age2"] == 0.0

    def test_le_genre_est_lu_au_libelle_du_persona(self):
        assert propensity_design(1, 1, 30, "Female", None, 1.0, 1.0, ())["female"] == 1.0
        assert propensity_design(1, 1, 30, "Male", None, 1.0, 1.0, ())["female"] == 0.0
        assert propensity_design(1, 1, 30, None, None, 1.0, 1.0, ())["female"] == 0.0


# ── Le logit servi ───────────────────────────────────────────────────────────

class TestLogit:

    def test_un_logit_binaire_rend_une_probabilite(self):
        model = LogitModel(features=("x",), intercepts=(0.0,),
                           coefficients=((0.0,),), classes=(1,))
        assert model.probability({"x": 0.0}) == pytest.approx(0.5)
        assert model.probability({"x": 100.0}) == pytest.approx(0.5)

    def test_un_logit_binaire_ne_deborde_pas(self):
        model = LogitModel(features=("x",), intercepts=(0.0,),
                           coefficients=((1.0,),), classes=(1,))
        assert model.probability({"x": -10000.0}) == pytest.approx(0.0)
        assert model.probability({"x": 10000.0}) == pytest.approx(1.0)

    def test_un_multinomial_somme_a_un(self):
        model = LogitModel(features=("x",), intercepts=(0.0, 1.0, -1.0),
                           coefficients=((0.5,), (0.0,), (-0.5,)), classes=(0, 1, 2))
        probabilities = model.probabilities({"x": 2.0})
        assert sum(probabilities) == pytest.approx(1.0)
        assert all(p >= 0 for p in probabilities)

    def test_un_multinomial_ne_deborde_pas(self):
        model = LogitModel(features=("x",), intercepts=(0.0, 0.0),
                           coefficients=((1.0,), (-1.0,)), classes=(0, 1))
        probabilities = model.probabilities({"x": 5000.0})
        assert sum(probabilities) == pytest.approx(1.0)

    def test_une_feature_absente_vaut_zero(self):
        """Sens d'une indicatrice non activée — et le seul cas où cela se produit."""
        model = LogitModel(features=("a", "b"), intercepts=(0.0,),
                           coefficients=((1.0, 1.0),), classes=(1,))
        assert model.probability({"a": 1.0}) == model.probability({"a": 1.0, "b": 0.0})

    def test_des_coefficients_mal_dimensionnes_levent(self):
        with pytest.raises(ValueError):
            LogitModel(features=("a", "b"), intercepts=(0.0,),
                       coefficients=((1.0,),), classes=(1,))
        with pytest.raises(ValueError):
            LogitModel(features=("a",), intercepts=(0.0, 0.0),
                       coefficients=((1.0,),), classes=(1,))

    def test_probability_refuse_un_multinomial(self):
        model = LogitModel(features=("x",), intercepts=(0.0, 0.0),
                           coefficients=((1.0,), (0.0,)), classes=(0, 1))
        with pytest.raises(ValueError):
            model.probability({"x": 1.0})


# ── Chargement : aucun repli silencieux ──────────────────────────────────────

def _minimal_doc(**overrides) -> dict:
    doc = {
        "version": 1,
        "stock": {
            "features": list(STOCK_FEATURES),
            "classes": list(K_CLASSES),
            "intercepts": [0.0] * len(K_CLASSES),
            "coefficients": [[0.0] * len(STOCK_FEATURES) for _ in K_CLASSES],
        },
        "propensity": {
            "features": list(PROPENSITY_BASE_FEATURES),
            "classes": [1],
            "intercepts": [0.0],
            "coefficients": [[0.0] * len(PROPENSITY_BASE_FEATURES)],
        },
        "occupations": [],
        "median_density": 500.0,
        "under_age_holder_share": 0.16,
    }
    doc.update(overrides)
    return doc


class TestChargement:

    def test_une_ressource_absente_leve(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="make bike-ownership"):
            BikeOwnershipModel.load(tmp_path / "absent.json")

    def test_une_ressource_minimale_se_charge(self, tmp_path):
        path = tmp_path / "bike.json"
        path.write_text(json.dumps(_minimal_doc()), encoding="utf-8")
        model = BikeOwnershipModel.load(path)
        assert model.stock.classes == K_CLASSES
        assert model.electric_p == pytest.approx(electric_probability(0.16))

    def test_des_features_de_stock_divergentes_levent(self, tmp_path):
        doc = _minimal_doc()
        doc["stock"]["features"] = ["autre_chose"] + list(STOCK_FEATURES[1:])
        path = tmp_path / "bike.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        with pytest.raises(ValueError, match="étage 1"):
            BikeOwnershipModel.load(path)

    def test_des_occupations_manquantes_levent(self, tmp_path):
        """La ressource déclare des occupations mais n'a pas les colonnes : des
        coefficients alignés sur les mauvaises colonnes ne lèvent pas d'erreur, ils
        produisent un parc faux."""
        doc = _minimal_doc(occupations=["Retraité"])
        path = tmp_path / "bike.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        with pytest.raises(ValueError, match="étage 2"):
            BikeOwnershipModel.load(path)

    def test_des_classes_de_k_divergentes_levent(self, tmp_path):
        doc = _minimal_doc()
        doc["stock"]["classes"] = [0, 1, 2]
        doc["stock"]["intercepts"] = [0.0] * 3
        doc["stock"]["coefficients"] = [[0.0] * len(STOCK_FEATURES) for _ in range(3)]
        path = tmp_path / "bike.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        with pytest.raises(ValueError, match="classes"):
            BikeOwnershipModel.load(path)

    def test_une_ressource_d_une_autre_version_est_refusee(self, tmp_path):
        """Même garde-fou que `residence_zone.RESOURCE_VERSION` : une ressource
        écrite pour un autre schéma ne doit pas se charger avec des coefficients
        mal alignés faute de contrôle de version."""
        doc = _minimal_doc(version=RESOURCE_VERSION + 1)
        path = tmp_path / "bike.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        with pytest.raises(ValueError, match="version"):
            BikeOwnershipModel.load(path)


class TestContratDeSortie:

    def test_les_trois_libelles_sont_ceux_du_persona(self):
        """`traits_json` porte ces chaînes exactes, et `simulation_controller._owns_bike`
        les relit : une divergence d'un caractère prive les agents de vélo en silence."""
        assert LABELS == ("Pas de vélo", "vélo normal", "VAE")
        assert TRAIT_KEY == "personal_bike"

    def test_seul_pas_de_velo_est_negatif(self):
        assert NO_BIKE.lower() == "pas de vélo"
        assert PLAIN_BIKE.lower() != "pas de vélo"
        assert ELECTRIC_BIKE.lower() != "pas de vélo"

    def test_les_bornes_dage_sont_celles_de_lenquete(self):
        assert MIN_AGE_ELIGIBLE == 5      # champ de la question P20
        assert MIN_AGE_ELECTRIC == 14     # garde-fou du ticket 008, A1.a
        assert K_MAX == 4


# ── Parité avec la vraie ressource (sautés si elle n'est pas exportée) ───────

@pytest.mark.skipif(not DEFAULT_RESOURCE.exists(),
                    reason="ressource non exportée (make bike-ownership)")
class TestRessourceReelle:

    @pytest.fixture(scope="class")
    def model(self) -> BikeOwnershipModel:
        return BikeOwnershipModel.load()

    def test_elle_se_charge_et_expose_les_deux_etages(self, model):
        assert model.stock.classes == K_CLASSES
        assert len(model.propensity.coefficients) == 1

    def test_la_loi_de_k_somme_a_un(self, model):
        for size in (1, 2, 3, 4, 6):
            probabilities = model.stock_probabilities(size, 1, 500.0, 3.0)
            assert sum(probabilities) == pytest.approx(1.0)

    def test_lequipement_croit_avec_la_taille_du_menage(self, model):
        """Le gradient que le ticket existe pour redresser : il était INVERSÉ."""
        equipped = [1.0 - model.stock_probabilities(size, 1, 500.0, 5.0)[0]
                    for size in (1, 2, 3, 4)]
        assert equipped == sorted(equipped), equipped

    def test_la_propension_est_une_probabilite(self, model):
        for age in (6, 20, 45, 80):
            p = model.propensity_of(2, 3, age, "Female", "Retraité", 500.0, 3.0)
            assert 0.0 <= p <= 1.0

    def test_la_densite_manquante_ne_casse_rien(self, model):
        """81 zones fines sur 785 n'ont pas de densité : la médiane du périmètre est
        substituée, pas zéro, qui décrirait un désert."""
        with_none = model.stock_probabilities(2, 1, None, 3.0)
        with_median = model.stock_probabilities(2, 1, model.median_density, 3.0)
        assert with_none == pytest.approx(with_median)

    def test_la_ressource_publie_ses_cibles_et_ses_effectifs(self, model):
        """« Effectifs de cellule publiés avec chaque table » — critère du ticket."""
        targets = model.validation["targets"]
        assert 45.0 < targets["holders_pct"] < 56.0
        assert 7.0 < targets["vae_share_of_fleet_pct"] < 8.5
        for row in targets["holders_by_household_size"]:
            assert {"size", "n", "weighted_n", "thin"} <= set(row)
        for cell in model.validation["practice"]["by_k_and_size"]:
            assert {"k", "size", "n", "weighted_n", "thin"} <= set(cell)

    def test_le_gradient_publie_est_croissant_sur_les_tailles_1_a_4(self, model):
        curve = {row["size"]: row["holders_pct"]
                 for row in model.validation["targets"]["holders_by_household_size"]}
        ordered = [curve[size] for size in (1, 2, 3, 4)]
        assert ordered == sorted(ordered), ordered

    def test_la_cible_habitat_est_en_part_de_personnes_pas_de_menages(self, model):
        """L'unité de la cible habitat, et c'est un piège qui a mordu.

        `personal_bike` est un trait **individuel** : la cible opposée à la population
        doit être une part de PERSONNES dotées. La courbe publiée, elle, est une part de
        MÉNAGES équipés (« Ménages équipés, individuel isolé : 70,9 % »). Confondre les
        deux produit un biais négatif sur TOUTES les modalités, d'autant plus fort que
        l'habitat est familial — un foyer de quatre à un vélo est « équipé » mais un seul
        de ses membres est doté. Le symptôme trompe : il ressemble à un défaut
        d'imputation alors que c'est une erreur d'unité.
        """
        reference = model.validation.get("housing_reference") or {}
        if not reference.get("attainable_on_imputed_housing"):
            pytest.skip("table du type de logement absente à l'export")
        holders = reference["attainable_on_imputed_housing"]
        households = reference.get("attainable_households_equipped_pct")
        assert households, "la ressource doit servir les DEUX unités"
        # Dans les habitats familiaux, la part de personnes est nettement sous la part de
        # ménages. C'est ce qui distingue les deux unités ; si l'égalité s'installait,
        # c'est que l'une des deux a été recalculée avec la formule de l'autre.
        assert holders["individuel_isole"] < households["individuel_isole"] - 3.0
        # L'écart doit être plus grand en individuel (grands ménages) qu'en collectif.
        gap_house = households["individuel_isole"] - holders["individuel_isole"]
        gap_flat = (households["grand_habitat_collectif"]
                    - holders["grand_habitat_collectif"])
        assert gap_house > gap_flat, (gap_house, gap_flat)
        assert reference.get("unit"), "l'unité servie doit être documentée dans la ressource"

    def test_la_cible_habitat_diluee_est_publiee_et_plus_plate_que_la_publiee(self, model):
        """Le critère « 71 % → 38 % » est inatteignable par construction : l'habitat du
        persona est lui-même imputé. La ressource doit servir la cible atteignable."""
        reference = model.validation.get("housing_reference") or {}
        if not reference.get("attainable_on_imputed_housing"):
            pytest.skip("table du type de logement absente à l'export")
        # `attainable_spread_pts` est une amplitude en part de MÉNAGES, donc comparable
        # à la courbe publiée qui l'est aussi.
        attainable = reference["attainable_households_equipped_pct"]
        published = reference["published_on_observed_housing"]
        published_spread = (published["individuel_isole"]
                            - published["grand_habitat_collectif"])
        assert reference["attainable_spread_pts"] < published_spread
        assert attainable["individuel_isole"] > attainable["grand_habitat_collectif"]
