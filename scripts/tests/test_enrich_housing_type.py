"""Pose du trait « type de logement » sur une population synthétique (action A2).

C'est l'étape qui crée le trait : sans elle, `traits_json` ne le porte pas et la
colonne du journal reste vide. Ce qui est vérifié ici :

- le trait est posé sous le nom que le journal relit, avec le libellé de la référence ;
- **hors couche de zones fines, rien n'est posé** — et un trait hérité d'un
  enrichissement antérieur est retiré plutôt que laissé à traîner ;
- l'enrichissement est **idempotent et déterministe** : rejouer ne change rien, et un
  domicile partagé donne un seul logement ;
- **la taille du ménage est celle que le persona déclare** (ticket 019), pas le nombre
  de membres présents dans le fichier — les grappes d'adresse sont partielles, et
  compter les présents mettrait des familles dans des lois de personne seule ;
- **un persona sans taille ne reçoit rien** : pas de repli sur la loi de zone seule,
  qui est précisément le mécanisme aplati que le ticket 019 remplace ;
- **la recette du ticket 019 est exécutable** : `--check` sort en échec si le gradient
  de taille est faux, si son signe est inversé, ou si le trait manque en masse ;
- **sans les ressources d'accès restreint, la commande refuse de tourner** au lieu
  d'imputer à l'aveugle — et elle dit laquelle manque.

Hors ligne, sans les données PROGEDO : le résolveur de zones est remplacé par un
doublon qui rattache selon la latitude.
"""

from __future__ import annotations

import json

import pytest

from llm_module.core.housing_type import (
    MIN_RESOURCE_VERSION,
    MODALITY_KEYS,
    SIZE_MAX,
    SIZE_TRAIT_KEY,
    TRAIT_KEY,
    HousingTypeTable,
)
from scripts.data.population import enrich_housing_type as enrich_module

_URBAIN = (0.0, 0.0, 0.0, 1.0, 0.0)      # grand collectif certain
_RURAL = (1.0, 0.0, 0.0, 0.0, 0.0)       # individuel isolé certain

# Leviers neutres : les lois de test sont déjà déterministes, et ce fichier vérifie la
# pose du trait, pas l'arithmétique du raking (elle est verrouillée dans
# `llm_module/tests/test_housing_type.py`).
_NEUTRE = {size: (1.0,) * 5 for size in range(1, SIZE_MAX + 1)}

# Cibles de recette, comme la ressource réelle les publie.
_CIBLES = {"delivered": {"by_size": [
    {"size": 1, "individuel_isole_observed_pct": 15.7},
    {"size": 2, "individuel_isole_observed_pct": 46.4},
    {"size": 3, "individuel_isole_observed_pct": 45.5},
    {"size": 4, "individuel_isole_observed_pct": 53.9},
]}}


class _Zone:
    def __init__(self, zf: str):
        self.zf = zf


class _FakeResolver:
    """Rattache au nord (lat ≥ 43.6) à la zone urbaine, au sud à la rurale, et
    laisse hors couche tout ce qui est au-delà de 44."""

    def resolve_many(self, lats, lons):
        out = []
        for lat in lats:
            if lat is None or lat > 44.0:
                out.append(None)
            elif lat >= 43.6:
                out.append(_Zone("100100000"))
            else:
                out.append(_Zone("200200000"))
        return out


@pytest.fixture
def table() -> HousingTypeTable:
    return HousingTypeTable(zones={"100100000": _URBAIN, "200200000": _RURAL},
                            sectors={}, global_shares=_URBAIN,
                            size_leverage=dict(_NEUTRE), meta={},
                            validation=_CIBLES)


def _person(lat, lon=1.44, size=2, **traits) -> dict:
    home = {"lat": lat, "lon": lon} if lat is not None else {}
    identity_traits = {"age": 30, **traits}
    if size is not None:
        identity_traits.setdefault(SIZE_TRAIT_KEY, size)
    return {"person_id": f"{lat}", "identity": {"traits_json": identity_traits,
                                                "home": home}}


def _traits(population):
    return [p["identity"]["traits_json"].get(TRAIT_KEY) for p in population]


class TestPoseDuTrait:

    def test_le_trait_porte_le_libelle_de_la_reference(self, table):
        population = [_person(43.61), _person(43.50)]
        enrich_module.enrich(population, table, _FakeResolver())
        assert _traits(population) == ["Grand habitat collectif", "Individuel isolé"]

    def test_le_decompte_est_rendu_par_modalite(self, table):
        counts = enrich_module.enrich([_person(43.61), _person(43.62), _person(43.50)],
                                      table, _FakeResolver())
        assert counts["grand_habitat_collectif"] == 2
        assert counts["individuel_isole"] == 1

    def test_les_autres_traits_ne_sont_pas_touches(self, table):
        population = [_person(43.61, gender="Female")]
        enrich_module.enrich(population, table, _FakeResolver())
        assert population[0]["identity"]["traits_json"]["gender"] == "Female"
        assert population[0]["identity"]["traits_json"]["age"] == 30

    def test_meme_domicile_meme_logement(self, table):
        """Deux personas d'un même foyer ne peuvent pas habiter deux logements."""
        population = [_person(43.61), _person(43.61)]
        enrich_module.enrich(population, table, _FakeResolver())
        assert len(set(_traits(population))) == 1

    def test_rejouer_ne_change_rien(self, table):
        population = [_person(43.61), _person(43.50)]
        enrich_module.enrich(population, table, _FakeResolver())
        first = _traits(population)
        enrich_module.enrich(population, table, _FakeResolver())
        assert _traits(population) == first


class TestHorsCouche:

    def test_domicile_hors_couche_reste_sans_trait(self, table):
        population = [_person(45.0)]
        counts = enrich_module.enrich(population, table, _FakeResolver())
        assert _traits(population) == [None]
        assert counts["hors_couche"] == 1

    def test_domicile_sans_coordonnees_reste_sans_trait(self, table):
        population = [_person(None)]
        counts = enrich_module.enrich(population, table, _FakeResolver())
        assert _traits(population) == [None]
        assert counts["hors_couche"] == 1

    def test_un_trait_herite_est_retire(self, table):
        """Une population enrichie sous une autre couche ne doit pas garder un trait
        que la couche courante ne sait plus justifier."""
        population = [_person(45.0, **{TRAIT_KEY: "Individuel isolé"})]
        enrich_module.enrich(population, table, _FakeResolver())
        assert TRAIT_KEY not in population[0]["identity"]["traits_json"]

    def test_zone_sans_loi_ne_produit_pas_de_modalite(self):
        vide = HousingTypeTable(zones={}, sectors={}, global_shares=(),
                                size_leverage=dict(_NEUTRE), meta={})
        population = [_person(43.61)]
        counts = enrich_module.enrich(population, vide, _FakeResolver())
        assert _traits(population) == [None]
        assert counts["sans_loi"] == 1


class TestTailleDuMenage:
    """Le conditionnement du ticket 019, du côté de la population."""

    def test_la_taille_nominale_est_celle_qui_sert(self, table):
        """Un foyer de quatre dont un seul membre est dans le fichier tire dans la loi
        des ménages de quatre. Compter les présents en ferait une personne seule."""
        laws = {}
        for size in (1, 4):
            population = [_person(43.61, size=size)]
            enrich_module.enrich(population, table, _FakeResolver())
            laws[size] = population[0]["identity"]["traits_json"].get(TRAIT_KEY)
        # Les leviers de test sont neutres : ce qui est vérifié ici, c'est que la taille
        # déclarée est LUE et acceptée, pas qu'elle change le tirage.
        assert all(value is not None for value in laws.values())

    def test_persona_sans_taille_ne_recoit_rien(self, table):
        population = [_person(43.61, size=None)]
        counts = enrich_module.enrich(population, table, _FakeResolver())
        assert _traits(population) == [None]
        assert counts["sans_taille"] == 1

    def test_un_trait_herite_est_retire_faute_de_taille(self, table):
        """Le cas de la ré-imputation : le trait v1 posé sans la taille doit partir."""
        population = [_person(43.61, size=None, **{TRAIT_KEY: "Individuel isolé"})]
        enrich_module.enrich(population, table, _FakeResolver())
        assert TRAIT_KEY not in population[0]["identity"]["traits_json"]

    def test_taille_absurde_ne_produit_pas_de_modalite(self, table):
        population = [_person(43.61, size=0), _person(43.62, size="deux")]
        counts = enrich_module.enrich(population, table, _FakeResolver())
        assert _traits(population) == [None, None]
        assert counts["sans_taille"] == 2

    def test_le_niveau_de_repli_est_compte(self, table):
        """« Le compte par niveau de repli est publié à chaque enrichissement. »"""
        counts = enrich_module.enrich([_person(43.61), _person(43.50)],
                                      table, _FakeResolver())
        assert counts["repli_zone"] == 2
        assert not counts["repli_secteur"] and not counts["repli_perimetre"]

    def test_une_zone_inconnue_est_comptee_au_perimetre(self, table):
        class _Ailleurs:
            def resolve_many(self, lats, lons):
                return [_Zone("999999999")] * len(lats)

        counts = enrich_module.enrich([_person(43.61)], table, _Ailleurs())
        assert counts["repli_perimetre"] == 1


class TestRecette:
    """`--check` : le gradient de taille, son signe, et la couverture du trait."""

    def _measured(self, spec: dict[int, tuple[int, int]]):
        """`spec` : taille → (nombre d'individuels isolés, nombre total)."""
        population, lat = [], 43.0
        for size, (isolated, total) in spec.items():
            for index in range(total):
                lat += 1e-4
                label = ("Individuel isolé" if index < isolated
                         else "Grand habitat collectif")
                population.append(_person(lat, size=size, **{TRAIT_KEY: label}))
        return population

    def test_le_gradient_conforme_ne_produit_aucun_echec(self, table, capsys):
        # 16 / 46 / 45 / 54 % sur 100 adresses par taille : les cibles de l'enquête.
        population = self._measured({1: (16, 100), 2: (46, 100),
                                     3: (45, 100), 4: (54, 100)})
        failures = enrich_module.check_size_gradient(
            enrich_module.measure_by_size(population), table)
        assert failures == []
        assert "ok" in capsys.readouterr().out

    def test_la_pente_inversee_echoue(self, table):
        """C'est le défaut exact d'avant le ticket 019 : 27 % → 36 % au lieu de
        16 % → 54 %. Le signe est un critère à part entière."""
        population = self._measured({1: (54, 100), 2: (46, 100),
                                     3: (45, 100), 4: (16, 100)})
        failures = enrich_module.check_size_gradient(
            enrich_module.measure_by_size(population), table)
        assert any("pente" in failure for failure in failures)

    def test_la_pente_n_est_pas_jugee_sur_une_cible_absente(self, capsys):
        """Un `targets.get(size, 0)` par défaut fabriquerait une pente attendue à partir
        d'une cible manquante, et jugerait la population contre du vide."""
        partiel = HousingTypeTable(
            zones={}, sectors={}, global_shares=_URBAIN,
            size_leverage=dict(_NEUTRE), meta={},
            validation={"delivered": {"by_size": [
                {"size": 1, "individuel_isole_observed_pct": 15.7}]}})
        population = self._measured({1: (16, 100), 4: (54, 100)})
        failures = enrich_module.check_size_gradient(
            enrich_module.measure_by_size(population), partiel)
        assert "non jugée" in capsys.readouterr().out
        assert not any("pente" in failure for failure in failures)

    def test_une_cellule_trop_mince_ne_tranche_pas(self, table, capsys):
        """Vacuité ≠ perfection : une cellule de 5 adresses ne « réussit » pas."""
        population = self._measured({1: (5, 5), 4: (0, 5)})
        enrich_module.check_size_gradient(
            enrich_module.measure_by_size(population), table)
        assert "NON CONCLUANT" in capsys.readouterr().out

    def test_l_effectif_utile_est_celui_des_adresses(self, table):
        """Six personas d'un même foyer partagent UN tirage : les compter six fois
        ferait croire la cellule six fois plus précise qu'elle n'est."""
        population = [_person(43.61, size=4, **{TRAIT_KEY: "Individuel isolé"})
                      for _ in range(6)]
        measured = enrich_module.measure_by_size(population)
        assert measured[4]["n"] == 6
        assert measured[4]["n_addresses"] == 1

    def test_sans_cibles_la_recette_ne_passe_pas_en_silence(self):
        """Une table sans bloc de validation : le critère est ABSENT, pas atteint."""
        sans_cibles = HousingTypeTable(zones={}, sectors={}, global_shares=_URBAIN,
                                       size_leverage=dict(_NEUTRE), meta={})
        failures = enrich_module.check_size_gradient({1: {
            "n": 100, "isolated_pct": 15.7, "n_addresses": 100}}, sans_cibles)
        assert failures and "ne peut pas être évalué" in failures[0]

    def test_un_none_massif_fait_echouer_la_couverture(self, table, capsys):
        """« Un None massif doit faire échouer la validation, pas la réussir. »"""
        population = [_person(45.0) for _ in range(10)] + [_person(43.61)]
        counts = enrich_module.enrich(population, table, _FakeResolver())
        failures = enrich_module.report(counts, table, population)
        assert any("couverture" in failure for failure in failures)


def _run(monkeypatch, *args) -> int:
    monkeypatch.setattr("sys.argv", ["enrich_housing_type", *args])
    return enrich_module.main()


class TestCommande:

    def _population_file(self, tmp_path):
        path = tmp_path / "pop.json"
        path.write_text(json.dumps([_person(43.61)]), encoding="utf-8")
        return path

    def test_table_absente_refuse_de_tourner(self, tmp_path, monkeypatch, capsys):
        path = self._population_file(tmp_path)
        assert _run(monkeypatch, str(path), "--table",
                    str(tmp_path / "absente.json")) == 1
        assert "make housing-type" in capsys.readouterr().err
        # La population n'a pas été touchée.
        assert _traits(json.loads(path.read_text(encoding="utf-8"))) == [None]

    def test_couche_de_zones_absente_refuse_de_tourner(self, tmp_path, monkeypatch,
                                                       capsys, table):
        pytest.importorskip("geopandas", reason="le résolveur exige l'extra 'geo'")
        path = self._population_file(tmp_path)
        table_path = tmp_path / "table.json"
        table_path.write_text(json.dumps({
            "version": MIN_RESOURCE_VERSION,
            "modalities": list(MODALITY_KEYS), "global": list(table.global_shares),
            "size_leverage": {str(size): {"leverage": list(values)}
                              for size, values in _NEUTRE.items()},
            "sectors": {}, "zones": {},
        }), encoding="utf-8")
        assert _run(monkeypatch, str(path), "--table", str(table_path),
                    "--zones", str(tmp_path / "absente.gpkg")) == 1
        assert "make zones" in capsys.readouterr().err

    def _stub_ressources(self, monkeypatch, table):
        monkeypatch.setattr(HousingTypeTable, "load",
                            classmethod(lambda cls, p=None: table))
        monkeypatch.setattr(
            "llm_module.core.zone_resolver.ZoneResolver.load",
            classmethod(lambda cls, r=None, s=None: _FakeResolver()))

    def test_dry_run_rapporte_sans_reecrire(self, tmp_path, monkeypatch, table, capsys):
        path = self._population_file(tmp_path)
        self._stub_ressources(monkeypatch, table)
        assert _run(monkeypatch, str(path), "--dry-run") == 0
        assert "dry-run" in capsys.readouterr().out
        assert _traits(json.loads(path.read_text(encoding="utf-8"))) == [None]

    def test_ecriture_effective(self, tmp_path, monkeypatch, table):
        path = self._population_file(tmp_path)
        self._stub_ressources(monkeypatch, table)
        assert _run(monkeypatch, str(path)) == 0
        assert _traits(json.loads(path.read_text(encoding="utf-8"))) == [
            "Grand habitat collectif"]

    def test_population_introuvable_signalee(self, tmp_path, monkeypatch, table, capsys):
        self._stub_ressources(monkeypatch, table)
        assert _run(monkeypatch, str(tmp_path / "nulle-part.json")) == 1
        assert "introuvable" in capsys.readouterr().err

    def test_une_population_trop_petite_a_son_propre_code(self, tmp_path, monkeypatch,
                                                          table, capsys):
        """Un fichier d'un seul persona : la couverture tient, mais rien ne tranche.

        Ce n'est pas un échec de l'imputation — et ce n'est pas un succès non plus. Le
        code 3 dit exactement cela, et le notebook peut continuer sans faire semblant.
        """
        path = self._population_file(tmp_path)
        self._stub_ressources(monkeypatch, table)
        assert _run(monkeypatch, str(path), "--check") == enrich_module.EXIT_NOT_MEASURABLE
        out = capsys.readouterr().out
        assert "NON VALIDÉE" in out
        assert enrich_module.NOT_MEASURABLE in out

    def test_une_cible_dementie_a_le_code_d_echec(self, tmp_path, monkeypatch, table,
                                                  capsys):
        """La pente inversée, elle, met l'imputation en cause : code 2."""
        path = tmp_path / "pop.json"
        population = []
        lat = 43.0
        for size, isolated, total in ((1, 40, 40), (4, 0, 40)):
            for index in range(total):
                lat += 1e-4
                label = ("Individuel isolé" if index < isolated
                         else "Grand habitat collectif")
                population.append(_person(lat, size=size, **{TRAIT_KEY: label}))
        path.write_text(json.dumps(population), encoding="utf-8")

        # Le résolveur laisse tout hors couche : l'enrichissement ne réécrit rien, et
        # c'est bien le contrôle des traits DÉJÀ posés qu'on mesure ici.
        self._stub_ressources(monkeypatch, table)
        monkeypatch.setattr(enrich_module, "enrich", lambda pop, t, r: __import__(
            "collections").Counter({"individuel_isole": 40,
                                    "grand_habitat_collectif": 40,
                                    "repli_zone": 80}))
        assert _run(monkeypatch, str(path), "--check") == enrich_module.EXIT_TARGET_MISSED
        assert "pente" in capsys.readouterr().out

    def test_sans_check_l_ecart_est_signale_sans_bloquer(self, tmp_path, monkeypatch,
                                                         table, capsys):
        path = self._population_file(tmp_path)
        self._stub_ressources(monkeypatch, table)
        assert _run(monkeypatch, str(path)) == enrich_module.EXIT_OK
        assert "relancez avec --check" in capsys.readouterr().out
