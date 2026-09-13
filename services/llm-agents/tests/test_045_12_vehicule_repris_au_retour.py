"""Ticket 045 — un véhicule laissé quelque part se reprend quand on y revient.

Question posée le 2026-09-11 : *« et si l'agent retourne à la position du véhicule, peut-il
l'utiliser à nouveau ? »* La réponse est **oui**, et ce fichier la fixe, parce qu'aucun test
ne la tenait.

La règle est **positionnelle, pas un verrou à usage unique** : un mode véhiculé est proposable
si et seulement si le véhicule est garé **là où le trajet commence**. Rien n'est consommé, rien
n'est marqué « déjà utilisé ». Un agent qui part au bureau en voiture, en repart autrement, puis
revient au bureau, retrouve sa voiture.

Sans ce comportement, la contrainte de chaîne deviendrait une interdiction définitive : le
premier trajet non véhiculé priverait l'agent de son véhicule pour toute la journée. Ce serait
aussi faux que le défaut qu'elle corrige — le « vélo fantôme » qui suivait l'agent partout.

**Le cas se présente vraiment.** Sur la cohorte v5, 177 des 894 personnes mobiles reviennent au
moins une fois sur un lieu hors domicile dans leur journée, pour 190 retours au total.

**Ce que la règle ne fait PAS**, et c'est délibéré : elle compare des points, pas des
voisinages. La tolérance est de 10⁻⁶ degré, soit environ 11 cm — de quoi absorber les arrondis
de sérialisation, rien de plus. Deux activités distantes de 200 m sont deux lieux, et la voiture
de l'une ne sert pas à l'autre. Sur la v5, 746 paires d'activités d'une même personne sont à
moins de 500 m sans être au même point ; 3 seulement sont à moins de 50 m. La marche d'approche
n'est pas modélisée, et ce test le déclare plutôt que de le laisser découvrir.
"""

from __future__ import annotations

import pytest

from models import Location
from urban_mobility_agents.vehicle_chain import (
    MOTIF_VEHICULE_AILLEURS,
    _park_vehicles,
    _vehicle_unavailable_reason,
)

HOME = {"lon": 1.44, "lat": 43.60, "public_transport": True, "zone": "centre"}
BUREAU = {"lon": 1.45, "lat": 43.61, "public_transport": True, "zone": "nord"}
SPORT = {"lon": 1.46, "lat": 43.62, "public_transport": False, "zone": "est"}


def _lieu(d: dict) -> Location:
    return Location(lon=d["lon"], lat=d["lat"], public_transport=d["public_transport"], zone=d["zone"])


def _acte(i: int, purpose: str, loc: dict) -> dict:
    return {
        "id": str(i),
        "scheduled_start_time": 3600.0 * (i + 7),
        "start_time": 3600.0 * (i + 7),
        "end_time": 3600.0 * (i + 8),
        "purpose": purpose,
        "location": loc,
    }


@pytest.fixture
def agent():
    """Une personne motorisée, avec permis, dont la journée repasse par le bureau."""
    from inputs.population.eqasim_loader import EqasimJSONPopulationLoader

    traits = {
        "age": 35,
        "gender": "Female",
        "main_occupation": "actif",
        "household_size": 1,
        "number_of_cars": 1,
        "has_driving_license": True,
        "personal_bike": "vélo normal",
        "residence_zone": "Toulouse",
    }
    brut = [
        {
            "person_id": "p",
            "identity": {
                "traits_json": traits,
                "home": HOME,
                "activities": [
                    _acte(0, "home", HOME),
                    _acte(1, "work", BUREAU),
                    _acte(2, "leisure", SPORT),
                    _acte(3, "work", BUREAU),
                ],
            },
            "state": {"last_activity_index": 0},
            "is_llm_based": True,
        }
    ]
    return EqasimJSONPopulationLoader().load_population_from_data(brut, max_size=1, bbox=None)[0]


class _PlanVoiture:
    """Le minimum qu'attend `_park_vehicles` : un trajet dont le mode est la voiture."""

    legs = [type("Leg", (), {"mode": "car", "is_transfer": False})()]


def test_la_voiture_part_du_domicile(agent):
    assert _vehicle_unavailable_reason(agent, "car", _lieu(HOME)) is None


def test_la_voiture_reste_ou_on_la_gare(agent):
    _park_vehicles(agent, _PlanVoiture(), _lieu(HOME), _lieu(BUREAU))
    assert _vehicle_unavailable_reason(agent, "car", _lieu(BUREAU)) is None
    assert _vehicle_unavailable_reason(agent, "car", _lieu(HOME)) == MOTIF_VEHICULE_AILLEURS


def test_ailleurs_la_voiture_nest_pas_proposable(agent):
    """Le défaut que la chaîne corrige : le véhicule fantôme qui suivait l'agent."""
    _park_vehicles(agent, _PlanVoiture(), _lieu(HOME), _lieu(BUREAU))
    assert _vehicle_unavailable_reason(agent, "car", _lieu(SPORT)) == MOTIF_VEHICULE_AILLEURS


def test_revenir_sur_le_lieu_de_stationnement_rend_la_voiture(agent):
    """LE point de la question : la contrainte n'est pas un verrou à usage unique."""
    _park_vehicles(agent, _PlanVoiture(), _lieu(HOME), _lieu(BUREAU))
    assert _vehicle_unavailable_reason(agent, "car", _lieu(SPORT)) == MOTIF_VEHICULE_AILLEURS
    # L'agent revient au bureau, par n'importe quel mode : sa voiture l'y attend toujours.
    assert _vehicle_unavailable_reason(agent, "car", _lieu(BUREAU)) is None


def test_la_reprise_ne_depend_pas_du_mode_par_lequel_on_revient(agent):
    """On peut revenir à pied, en bus ou en vélo : c'est la POSITION qui décide."""
    _park_vehicles(agent, _PlanVoiture(), _lieu(HOME), _lieu(BUREAU))
    velo = type("Plan", (), {"legs": [type("Leg", (), {"mode": "bicycle", "is_transfer": False})()]})()
    _park_vehicles(agent, velo, _lieu(BUREAU), _lieu(SPORT))  # on repart à vélo
    _park_vehicles(agent, velo, _lieu(SPORT), _lieu(BUREAU))  # on revient à vélo
    assert _vehicle_unavailable_reason(agent, "car", _lieu(BUREAU)) is None


def test_deux_lieux_proches_restent_deux_lieux(agent):
    """La règle compare des POINTS, pas des voisinages : la marche d'approche n'existe pas.

    Déclaré plutôt que découvert. Sur la cohorte v5, 746 paires d'activités d'une même
    personne sont à moins de 500 m sans être au même point.
    """
    _park_vehicles(agent, _PlanVoiture(), _lieu(HOME), _lieu(BUREAU))
    # ~200 m au nord du bureau : un autre lieu, donc pas de voiture.
    voisin = Location(lon=BUREAU["lon"], lat=BUREAU["lat"] + 0.0018, public_transport=True, zone="nord")
    assert _vehicle_unavailable_reason(agent, "car", voisin) == MOTIF_VEHICULE_AILLEURS


def test_un_arrondi_de_serialisation_ne_perd_pas_le_vehicule(agent):
    """La tolérance de 10⁻⁶ degré absorbe les arrondis, et rien d'autre (~11 cm)."""
    _park_vehicles(agent, _PlanVoiture(), _lieu(HOME), _lieu(BUREAU))
    arrondi = Location(
        lon=BUREAU["lon"] + 1e-9, lat=BUREAU["lat"] - 1e-9, public_transport=True, zone="nord"
    )
    assert _vehicle_unavailable_reason(agent, "car", arrondi) is None
