"""Tests de l'anticipation de la chaîne de la journée (ticket 014).

Le choix modal reste trajet par trajet, mais le bloc persona du prompt est
enrichi de trois éléments : la météo des tranches restantes de la journée
(tous les agents), l'agenda glissant des trajets restants et la position des
véhicules personnels (agents qui ont quelque chose à chaîner). La signature
déterministe de ces textes entre dans la clé du cache de décisions.

Comme `test_vehicle_chain.py`, ces tests importent les fonctions réelles du
contrôleur — le conftest de ce dossier met le dépôt et `llm-agents/` sur le path.

Lancement : cd llm-agents && .venv/bin/python -m pytest tests/test_agenda_anticipation.py
"""

from datetime import datetime

import pytest

from helper import humanize_time, to_timestamp_based_on_day
from llm.cache import LlmSemanticCache
from models import (
    Activity,
    Location,
    Person,
    PersonalIdentity,
    PersonState,
    Transit,
    TransitLocation,
    TravelPlan,
)
from urban_mobility_agents import simulation_controller as sc
from urban_mobility_agents.simulation_controller import (
    _agenda_lines,
    _build_anticipation,
    _chain_stake_modes,
)

HOME = Location(lat=43.6000, lon=1.4400)
WORK = Location(lat=43.6100, lon=1.4500)
GYM = Location(lat=43.6200, lon=1.4600)

# 08:00 UTC un lundi : les heures d'agenda sont résolues via
# to_timestamp_based_on_day (plancher de jour UTC), donc on raisonne en UTC.
DEPARTURE = 1773648000  # 2026-03-16 08:00:00 UTC


def _person(**traits) -> Person:
    """Adulte titulaire du permis, vivant seul, voiture + vélo au domicile."""
    base = {"personal_bike": "vélo normal", "number_of_cars": 1,
            "has_driving_license": True, "age": 40, "household_size": 1}
    base.update(traits)
    return Person(
        person_id="p1",
        identity=PersonalIdentity(name="Test", traits_json=base, home=HOME),
        state=PersonState(),
    )


def _act(id: str, start_24h: float, purpose: str, location) -> Activity:
    return Activity(id=id, scheduled_start_time=start_24h, start_time=start_24h,
                    end_time=start_24h + 3600, purpose=purpose, location=location)


def _day(person: Person, *acts: Activity) -> Person:
    person.identity.activities = list(acts)
    return person


def _no_weather(monkeypatch):
    """Neutralise la météo : les tests d'agenda ne dépendent pas du CSV météo."""
    monkeypatch.setattr(sc, "get_weather", lambda ts: None)
    monkeypatch.setattr(sc, "day_weather_outlook", lambda ts: None)


# ── Qui a quelque chose à chaîner ─────────────────────────────────────────────

class TestChainStake:
    def test_conducteur_avec_velo(self):
        assert _chain_stake_modes(_person()) == ["car", "bike"]

    def test_passager_garde_son_velo(self):
        """La voiture d'un passager n'est pas positionnelle — son vélo, si."""
        child = _person(age=12, has_driving_license=False, household_size=4,
                        number_of_cars=3)
        assert _chain_stake_modes(child) == ["bike"]

    def test_rien_a_chainer(self):
        p = _person(personal_bike="Pas de vélo", number_of_cars=0)
        assert _chain_stake_modes(p) == []

    def test_sans_permis_pas_de_voiture(self):
        p = _person(has_driving_license=False)
        assert _chain_stake_modes(p) == ["bike"]


# ── Agenda glissant ───────────────────────────────────────────────────────────

class TestAgendaLines:
    def _acts(self):
        # Heures 24h dans le jour UTC du départ (08:00 = 28800 s).
        return (
            _act("a1", 8 * 3600, "work", WORK),
            _act("a2", 12 * 3600, "leisure", GYM),
            _act("a3", 18 * 3600, "home", HOME),
        )

    def test_trajets_restants_seulement(self, monkeypatch):
        _no_weather(monkeypatch)
        person = _day(_person(), *self._acts())
        lines = _agenda_lines(person, person.identity.activities[0], DEPARTURE)
        assert len(lines) == 2
        assert "leisure" in lines[0] and "home" in lines[1]

    def test_heures_et_distances(self, monkeypatch):
        _no_weather(monkeypatch)
        person = _day(_person(), *self._acts())
        lines = _agenda_lines(person, person.identity.activities[0], DEPARTURE)
        expected_time = humanize_time(to_timestamp_based_on_day(12 * 3600, DEPARTURE))
        assert lines[0].startswith(f"{expected_time} → leisure")
        assert "km" in lines[0]  # ≈ vol d'oiseau × 1,3 depuis l'étape précédente

    def test_dernier_trajet_agenda_vide(self, monkeypatch):
        _no_weather(monkeypatch)
        person = _day(_person(), *self._acts())
        assert _agenda_lines(person, person.identity.activities[2], DEPARTURE) == []

    def test_bouclage_j_plus_1_exclu(self, monkeypatch):
        """Une activité dont l'heure 24h est déjà passée appartient au lendemain."""
        _no_weather(monkeypatch)
        person = _day(_person(),
                      _act("a1", 8 * 3600, "work", WORK),
                      _act("a2", 6 * 3600, "home", HOME))  # 06:00 < 08:00 ⇒ J+1
        assert _agenda_lines(person, person.identity.activities[0], DEPARTURE) == []

    def test_activite_inconnue_agenda_vide(self, monkeypatch):
        _no_weather(monkeypatch)
        person = _day(_person(), *self._acts())
        orphan = _act("zz", 9 * 3600, "other", GYM)
        assert _agenda_lines(person, orphan, DEPARTURE) == []

    def test_meteo_differente_annotee(self, monkeypatch):
        monkeypatch.setattr(sc, "day_weather_outlook", lambda ts: None)
        monkeypatch.setattr(sc, "get_weather", lambda ts: (
            {"weather_label": "Pluie", "temperature": 10.0, "weather_code": 61, "precip_mm": 4.0}
            if ts > DEPARTURE else
            {"weather_label": "Ensoleillé", "temperature": 12.0, "weather_code": 0, "precip_mm": 0.0}
        ))
        person = _day(_person(), *self._acts())
        lines = _agenda_lines(person, person.identity.activities[0], DEPARTURE)
        assert all("pluie prévu" in line for line in lines)


# ── Assemblage du contexte d'anticipation ─────────────────────────────────────

class TestBuildAnticipation:
    def _acts(self):
        return (_act("a1", 8 * 3600, "work", WORK),
                _act("a2", 18 * 3600, "home", HOME))

    def test_agenda_pour_un_conducteur(self, monkeypatch):
        _no_weather(monkeypatch)
        person = _day(_person(), *self._acts())
        antic = _build_anticipation(person, person.identity.activities[0], DEPARTURE)
        assert antic["trace"] == "agenda"
        assert antic["agenda"] and antic["signature"]
        # Plus AUCUNE mention de position de véhicule dans le contexte (le
        # libellé « avec vous » gonflait la part vélo — cf. arbitrage EMC²).
        assert "vehicles" not in antic
        assert "véhicule" not in antic["signature"].lower()

    def test_meteo_seule_pour_un_non_motorise(self, monkeypatch):
        monkeypatch.setattr(sc, "get_weather", lambda ts: None)
        monkeypatch.setattr(sc, "day_weather_outlook", lambda ts: "soirée 13°C, Pluie")
        person = _day(_person(personal_bike="Pas de vélo", number_of_cars=0), *self._acts())
        antic = _build_anticipation(person, person.identity.activities[0], DEPARTURE)
        assert antic["trace"] == "meteo"
        assert antic["agenda"] == []
        assert antic["outlook"] == "soirée 13°C, Pluie"

    def test_rien_a_montrer_rend_none(self, monkeypatch):
        _no_weather(monkeypatch)
        person = _day(_person(personal_bike="Pas de vélo", number_of_cars=0), *self._acts())
        assert _build_anticipation(person, person.identity.activities[0], DEPARTURE) is None

    def test_dernier_trajet_sans_meteo_rend_none(self, monkeypatch):
        """Dernier trajet de la journée : plus d'agenda, plus de ligne véhicules
        (supprimée) — sans météo restante, il n'y a plus rien à montrer."""
        _no_weather(monkeypatch)
        person = _day(_person(), *self._acts())
        assert _build_anticipation(person, person.identity.activities[1], DEPARTURE) is None

    def test_signatures_distinctes_par_agenda(self, monkeypatch):
        """Deux agendas restants différents ⇒ deux signatures distinctes."""
        _no_weather(monkeypatch)
        person = _day(_person(), *self._acts())
        sig_debut = _build_anticipation(person, person.identity.activities[0], DEPARTURE)["signature"]
        person.identity.activities = [self._acts()[0],
                                      _act("a3", 12 * 3600, "shop", GYM),
                                      self._acts()[1]]
        sig_avec_course = _build_anticipation(person, person.identity.activities[0], DEPARTURE)["signature"]
        assert sig_debut != sig_avec_course


# ── La signature entre dans la clé du cache ───────────────────────────────────

def _plan(mode: str) -> TravelPlan:
    loc = TransitLocation(stop="", lat=HOME.lat, lon=HOME.lon)
    leg = Transit(start_time=0, end_time=600, duration=600, distance=1000.0,
                  mode=mode, transit_route=f"__DIRECT_{mode}",
                  start_location=loc, end_location=loc)
    return TravelPlan(id="p", start_location=HOME, end_location=WORK,
                      start_time=0, end_time=600, legs=[leg])


class TestCacheKey:
    def test_extra_key_change_le_hash(self):
        options = [_plan("car"), _plan("bicycle")]
        base = LlmSemanticCache._make_state_hash(options)
        assert LlmSemanticCache._make_state_hash(options, None, "agenda A") != base
        assert LlmSemanticCache._make_state_hash(options, None, "agenda A") != \
            LlmSemanticCache._make_state_hash(options, None, "agenda B")

    def test_extra_key_vide_hash_inchange(self):
        """Anticipation désactivée ⇒ clé identique à l'existant (cache rétrocompatible)."""
        options = [_plan("car")]
        assert LlmSemanticCache._make_state_hash(options) == \
            LlmSemanticCache._make_state_hash(options, None, "")
