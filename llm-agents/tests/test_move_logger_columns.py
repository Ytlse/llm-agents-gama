"""Alignement en-têtes / valeurs du move-log, et ventilation des probabilités par mode.

Une ligne de `moves.csv` est construite comme une liste positionnelle : un décalage
entre `CSV_HEADERS` et la ligne écrite décale silencieusement TOUTES les colonnes
suivantes, et les analyses lisent alors la mauvaise donnée sans rien signaler.
"""

import asyncio

import pytest

from models import Location, PersonalIdentity, Person
from urban_mobility_agents.utils.move_logger import (
    CSV_HEADERS,
    MODE_PROBABILITY_HEADERS,
    MoveLogger,
    _mode_probability_cells,
)

DISTRIBUTION = {"walking": 0.0, "cycling": 0.1, "car": 0.6,
                "public_transport": 0.3, "train": 0.0, "motorbike": 0.0}


class TestModeProbabilityCells:

    def test_une_cellule_par_mode_dans_l_ordre_des_entetes(self):
        cells = _mode_probability_cells(DISTRIBUTION)
        assert len(cells) == len(MODE_PROBABILITY_HEADERS)
        assert dict(zip(MODE_PROBABILITY_HEADERS, cells)) == {
            "P(Marche) %": 0.0,
            "P(Vélo) %": 10.0,
            "P(Voiture Privée) %": 60.0,
            "P(Transports_collectifs) %": 30.0,
            "P(Train) %": 0.0,
            "P(Deux-roues motorisé) %": 0.0,
            "P(Autres modes) %": 0.0,
        }

    def test_somme_a_cent(self):
        assert sum(_mode_probability_cells(DISTRIBUTION)) == pytest.approx(100.0)

    def test_absence_de_repartition_laisse_les_cellules_vides(self):
        """Vide ≠ 0 : « pas de décision probabiliste » vs « mode explicitement écarté »."""
        assert _mode_probability_cells(None) == [""] * len(MODE_PROBABILITY_HEADERS)
        assert _mode_probability_cells({}) == [""] * len(MODE_PROBABILITY_HEADERS)


def _person() -> Person:
    return Person(
        person_id="42",
        identity=PersonalIdentity(
            name="Test Persona",
            traits_json={"age": 30, "gender": "Female", "main_occupation": "actif"},
            home=Location(lat=43.6047, lon=1.4442),
        ),
    )


class TestRowAlignment:

    def _row(self, monkeypatch, **kwargs) -> list:
        captured = {}
        logger = MoveLogger()
        monkeypatch.setattr(logger, "_write_row", lambda row: captured.setdefault("row", row))
        asyncio.run(logger.log_move(
            person=_person(), plan=None, purpose="work", selection_method="LLM",
            provider_model="p/m", faster_itinerary=None, reasoning="parce que", **kwargs))
        return captured["row"]

    def test_ligne_alignee_sur_les_entetes(self, monkeypatch):
        assert len(self._row(monkeypatch, mode_probabilities=DISTRIBUTION)) == len(CSV_HEADERS)

    def test_ligne_alignee_sans_repartition(self, monkeypatch):
        assert len(self._row(monkeypatch)) == len(CSV_HEADERS)

    def test_probabilites_ecrites_sous_les_bonnes_colonnes(self, monkeypatch):
        row = dict(zip(CSV_HEADERS, self._row(monkeypatch, mode_probabilities=DISTRIBUTION)))
        assert row["P(Voiture Privée) %"] == 60.0
        assert row["P(Marche) %"] == 0.0
        # Les colonnes voisines n'ont pas glissé.
        assert row["ID Personne"] == "42"
        assert row["Méthode de sélection"] == "LLM"
