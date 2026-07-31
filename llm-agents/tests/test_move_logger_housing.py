"""Écriture de la colonne « Type de logement » du journal (action A2).

La colonne était écrite vide, ce qui laissait à zéro tout un axe de la référence
EMC². Elle porte désormais le trait imputé à la génération de population — et le
journal ne fait que le recopier : il ne tire rien, il ne devine rien.

Trois frontières sont vérifiées ici, parce qu'aucune ne lève d'exception quand elle
est franchie :

- le libellé écrit est **exactement** celui de la référence, seule clé de jointure de
  la page de synthèse ;
- un persona sans trait laisse la cellule **vide** — « non renseigné » n'est pas une
  modalité, comme une cellule de probabilité vide n'est pas un 0 ;
- une valeur hors référentiel est ramenée à vide plutôt que journalisée telle quelle,
  faute de quoi elle disparaîtrait de la page sans y être comptée.
"""

import asyncio

import pytest

from llm_module.core.housing_type import LABEL_BY_KEY, REFERENCE_KEYS, TRAIT_KEY
from models import Location, PersonalIdentity, Person
from urban_mobility_agents.utils.move_logger import CSV_HEADERS, MoveLogger, _housing_type


def _person(**traits) -> Person:
    return Person(
        person_id="42",
        identity=PersonalIdentity(
            name="Test Persona",
            traits_json={"age": 30, "gender": "Female", **traits},
            home=Location(lat=43.6047, lon=1.4442),
        ),
    )


def _row(monkeypatch, person: Person) -> dict:
    captured = {}
    logger = MoveLogger()
    monkeypatch.setattr(logger, "_write_row", lambda row: captured.setdefault("row", row))
    asyncio.run(logger.log_move(
        person=person, plan=None, purpose="work", selection_method="LLM",
        provider_model="p/m", faster_itinerary=None, reasoning="parce que"))
    return dict(zip(CSV_HEADERS, captured["row"]))


class TestValeurEcrite:

    @pytest.mark.parametrize("key", REFERENCE_KEYS)
    def test_chaque_modalite_de_reference_est_journalisee_telle_quelle(self, monkeypatch, key):
        label = LABEL_BY_KEY[key]
        row = _row(monkeypatch, _person(**{TRAIT_KEY: label}))
        assert row["Type de logement"] == label

    def test_autres_est_journalise_aussi(self, monkeypatch):
        """L'enquête connaît cette modalité ; c'est la page qui la comptera hors
        référentiel, pas le journal qui l'effacera."""
        row = _row(monkeypatch, _person(**{TRAIT_KEY: "Autres"}))
        assert row["Type de logement"] == "Autres"

    def test_la_colonne_ne_deborde_pas_sur_ses_voisines(self, monkeypatch):
        row = _row(monkeypatch, _person(**{TRAIT_KEY: "Grand habitat collectif"}))
        assert row["Occupation principale"] == ""
        assert row["Motifs de déplacement"] == "Travail"


class TestAbsenceEtValeursHorsReferentiel:

    def test_persona_sans_trait_laisse_la_cellule_vide(self, monkeypatch):
        """Population générée avant l'action A2, ou domicile hors couche de zones."""
        assert _row(monkeypatch, _person())["Type de logement"] == ""

    def test_valeur_hors_referentiel_ramenee_a_vide(self):
        assert _housing_type({TRAIT_KEY: "Maison de ville"}) == ""
        assert _housing_type({TRAIT_KEY: "individuel_isole"}) == ""

    def test_valeur_vide_ou_absente(self):
        assert _housing_type({}) == ""
        assert _housing_type({TRAIT_KEY: None}) == ""
        assert _housing_type({TRAIT_KEY: "   "}) == ""

    def test_espaces_autour_du_libelle_tolérés(self):
        assert _housing_type({TRAIT_KEY: " Individuel isolé "}) == "Individuel isolé"
