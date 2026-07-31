"""Pose du trait « type de logement » sur une population synthétique (action A2).

C'est l'étape qui crée le trait : sans elle, `traits_json` ne le porte pas et la
colonne du journal reste vide. Ce qui est vérifié ici :

- le trait est posé sous le nom que le journal relit, avec le libellé de la référence ;
- **hors couche de zones fines, rien n'est posé** — et un trait hérité d'un
  enrichissement antérieur est retiré plutôt que laissé à traîner ;
- l'enrichissement est **idempotent et déterministe** : rejouer ne change rien, et un
  domicile partagé donne un seul logement ;
- **sans les ressources d'accès restreint, la commande refuse de tourner** au lieu
  d'imputer à l'aveugle — et elle dit laquelle manque.

Hors ligne, sans les données PROGEDO : le résolveur de zones est remplacé par un
doublon qui rattache selon la latitude.
"""

from __future__ import annotations

import json

import pytest

from llm_module.core.housing_type import MODALITY_KEYS, TRAIT_KEY, HousingTypeTable
from scripts.data.population import enrich_housing_type as enrich_module

_URBAIN = (0.0, 0.0, 0.0, 1.0, 0.0)      # grand collectif certain
_RURAL = (1.0, 0.0, 0.0, 0.0, 0.0)       # individuel isolé certain


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
                            sectors={}, global_shares=_URBAIN, meta={})


def _person(lat, lon=1.44, **traits) -> dict:
    home = {"lat": lat, "lon": lon} if lat is not None else {}
    return {"person_id": f"{lat}", "identity": {"traits_json": {"age": 30, **traits},
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
        vide = HousingTypeTable(zones={}, sectors={}, global_shares=(), meta={})
        population = [_person(43.61)]
        counts = enrich_module.enrich(population, vide, _FakeResolver())
        assert _traits(population) == [None]
        assert counts["sans_loi"] == 1


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
            "modalities": list(MODALITY_KEYS), "global": list(table.global_shares),
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
