"""Ticket 030 — car scolaire synthétique.

Deux familles de tests :

1. **« school_bus = TC partout »** — le mode ``school_bus`` doit compter en transport
   collectif dans les trois tables de métriques et le pont oracle, et ne JAMAIS
   déclencher la mention d'abonnement (le transport scolaire est gratuit). Ce test
   est écrit pour **échouer** contre le code d'avant le ticket 030 : ``canonical_mode``
   et ``move_logger._BUS_MODES`` ignorent ``school_bus``, et ``_pt_subscription_note``
   le déclenche à tort par la sous-chaîne « bus ».

2. **La fabrique d'options** (`build_school_bus_option`) — éligibilité, horaire, durée,
   et l'invariant anti-collision de déduplication (``get_code`` ≠ celui d'une voiture).

Lancement : cd llm-agents && .venv/bin/python -m pytest tests/test_school_bus.py
"""

from llm_module.core.mode_choice import canonical_mode
from urban_mobility_agents.utils.move_logger import _plan_transport_mode
from scripts.models_influence.prompt_calibration_lib import categorize_mode
from scripts.synthesis.model_on_common_set import CANONICAL_TO_CAT
from urban_mobility_agents.agents.llm_agent import _pt_subscription_note

from models import TransitLocation, Transit, TravelPlan


def _school_bus_plan() -> TravelPlan:
    """Un plan minimal à une jambe car scolaire, tel que le produit le Lot A."""
    start = TransitLocation(stop="Arrêt car scolaire", lat=43.2, lon=1.1)
    end = TransitLocation(stop="École", lat=43.25, lon=1.15)
    leg = Transit(
        start_time=0,
        end_time=1_800_000,
        start_location=start,
        end_location=end,
        is_transfer=False,
        transit_route="__DIRECT_CAR__",  # GAMA l'interpole comme une voiture
        shape_id=None,
        duration=1_800,
        distance=5_000.0,
        mode="school_bus",              # lu par toutes les tables de métriques
    )
    return TravelPlan(
        id="sb-test",
        start_location=start,
        end_location=end,
        start_time=0,
        end_time=1_800_000,
        legs=[leg],
    )


# ── 1. « school_bus = TC partout » ────────────────────────────────────────────

def test_canonical_mode_school_bus_is_public_transport():
    assert canonical_mode("school_bus") == "public_transport"


def test_move_logger_ranks_school_bus_as_transit():
    assert _plan_transport_mode(_school_bus_plan()) == "Transports_collectifs"


def test_categorize_mode_school_bus_is_transit():
    assert categorize_mode("school_bus") == "transports_collectifs"


def test_oracle_bridge_maps_school_bus_to_transit():
    # Le pont oracle passe par le mode canonique : school_bus → public_transport →
    # transports_collectifs.
    assert CANONICAL_TO_CAT[canonical_mode("school_bus")] == "transports_collectifs"


def test_school_bus_gets_no_subscription_note():
    # Gratuit : aucune mention d'abonnement, quel que soit l'abonnement du persona.
    assert _pt_subscription_note("school_bus", True) == ""
    assert _pt_subscription_note("school_bus", False) == ""


def test_real_bus_still_gets_subscription_note():
    # Contre-épreuve : un vrai bus garde la mention (la garde ne casse pas le cas normal).
    assert _pt_subscription_note("foot,bus,foot", True) != ""


# ── 2. La fabrique d'options ──────────────────────────────────────────────────

from trip_helper.school_bus import build_school_bus_option, SCHOOL_BUS_ROUTE_MARKER
from text_helper import env_ob_to_text
from models import Activity, Location, Person, PersonalIdentity

_HOME = Location(lon=1.10, lat=43.20, public_transport=False)   # hors Tisséo
_SCHOOL = Location(lon=1.15, lat=43.25, public_transport=False)
_TS = 3 * 86400 + 6 * 3600  # un jour, 6 h du matin (pas de bouclage J+1)


def _edu_activity() -> Activity:
    return Activity(id="edu", scheduled_start_time=8 * 3600, start_time=8 * 3600,
                    end_time=16 * 3600, purpose="education", location=_SCHOOL)


def _person(age=13, home=_HOME, activities=None) -> Person:
    return Person(
        person_id="p1",
        identity=PersonalIdentity(
            name="Test",
            traits_json={"age": age},
            home=home,
            activities=activities if activities is not None else [_edu_activity()],
        ),
    )


def test_outbound_option_is_built():
    plan = build_school_bus_option(_person(), _HOME, _edu_activity(), _TS, _TS)
    assert plan is not None
    assert len(plan.legs) == 1
    leg = plan.legs[0]
    assert leg.mode == "school_bus"
    assert leg.transit_route == SCHOOL_BUS_ROUTE_MARKER
    assert leg.is_transfer is False
    assert leg.duration and leg.duration > 0
    # Arrive 30 min avant le début de l'école (28800 s), au jour de _TS.
    assert plan.end_time // 1000 == 3 * 86400 + 8 * 3600 - 30 * 60


def test_return_option_is_built():
    home_activity = Activity(id="h", start_time=17 * 3600, end_time=23 * 3600,
                             purpose="home", location=_HOME)
    # Retour : on part de l'école vers le domicile.
    plan = build_school_bus_option(_person(), _SCHOOL, home_activity, _TS, _TS)
    assert plan is not None
    # Part 30 min après la fin de l'école (57600 s).
    assert plan.start_time // 1000 == 3 * 86400 + 16 * 3600 + 30 * 60


def test_not_eligible_when_adult():
    assert build_school_bus_option(_person(age=30), _HOME, _edu_activity(), _TS, _TS) is None


def test_not_eligible_when_home_served_by_tisseo():
    home = Location(lon=1.10, lat=43.20, public_transport=True)
    assert build_school_bus_option(_person(home=home), _HOME, _edu_activity(), _TS, _TS) is None


def test_not_eligible_when_trip_unrelated_to_school():
    shop = Activity(id="s", start_time=10 * 3600, end_time=11 * 3600,
                    purpose="shop", location=Location(lon=1.30, lat=43.30, public_transport=False))
    # Départ du domicile vers un commerce : ni origine ni destination = école.
    assert build_school_bus_option(_person(), _HOME, shop, _TS, _TS) is None


def test_get_code_distinct_from_car_no_dedup_collision():
    from models import Transit, TransitLocation, TravelPlan
    plan = build_school_bus_option(_person(), _HOME, _edu_activity(), _TS, _TS)
    # Une vraie jambe voiture directe a des arrêts vides → "__DIRECT_CAR__^^".
    car_leg = Transit(
        start_time=0, end_time=1000,
        start_location=TransitLocation(stop="", lat=43.20, lon=1.10),
        end_location=TransitLocation(stop="", lat=43.25, lon=1.15),
        is_transfer=False, transit_route="__DIRECT_CAR__", mode="car",
    )
    car_plan = TravelPlan(id="car", start_location=_HOME, end_location=_SCHOOL,
                          start_time=0, end_time=1000, legs=[car_leg])
    assert plan.get_code() != car_plan.get_code()


def test_rendering_shows_free_school_bus():
    plan = build_school_bus_option(_person(), _HOME, _edu_activity(), _TS, _TS)
    text = env_ob_to_text("travel_plan", plan.model_dump())
    assert "Car scolaire" in text
    assert "gratuit" in text.lower()
