"""Car scolaire synthétique — fabrique d'option (ticket 030).

Une fonction, pas une classe : l'option est purement synthétique (aucun appel OTP
ni OSMnx), elle n'a pas besoin de l'interface :class:`TripHelper`. Elle produit un
:class:`TravelPlan` à une jambe, présenté au modèle comme les autres options.

Choix de modélisation (cf. ticket 030, décisions du 2026-09-03) :

- **Éligibilité** = âge 5-17 (règlement liO) + domicile hors ressort Tisséo (là où
  la Région propose le service, proxy ``home.public_transport is False``) + trajet
  lié à l'activité ``education``. Ni sectorisation ni seuil de distance.
- **Mode / rendu GAMA** : la jambe porte ``mode="school_bus"`` (lu par toutes les
  tables de métriques → compté en TC) et ``transit_route="__DIRECT_CAR__"`` (GAMA
  l'interpole point-à-point comme une voiture, sans édition GAMA — lot GAMA hors
  périmètre, l'agent s'affiche en rouge). Les arrêts portent des **noms non vides**
  pour que ``get_code()`` diffère de celui d'une vraie voiture (anti-collision de
  déduplication).
- **Durée / horaire / coût** : paramètres exogènes figés de ``config/school_bus.yaml``.

Module pur : lecture du YAML au premier appel, pas d'état mutable, pas de réseau.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml
from loguru import logger
from prometheus_client import Counter

from helper import to_timestamp_based_on_day
from models import Activity, Location, Person, Transit, TransitLocation, TravelPlan
from utils import random_uuid

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "school_bus.yaml"

# GAMA interpole une jambe dont ``transit_route`` vaut ce marqueur exactement comme
# une voiture (point-à-point, sans véhicule GTFS). On le réutilise pour NE PAS avoir
# à toucher GAMA (lot GAMA hors périmètre). Contrepartie : rendu rouge.
SCHOOL_BUS_ROUTE_MARKER = "__DIRECT_CAR__"

SCHOOL_BUS_OPTIONS = Counter(
    "school_bus_options_total",
    "Options car scolaire synthétiques produites (ticket 030)",
    ["direction"],  # 'outbound' | 'return'
)


@dataclass(frozen=True)
class _SchoolBusConfig:
    age_min: int
    age_max: int
    access_minutes: float
    detour_factor: float
    in_vehicle_speed_kmh: float
    ramassage_minutes: float
    schedule_margin_minutes: float


_CONFIG: Optional[_SchoolBusConfig] = None


def _config() -> _SchoolBusConfig:
    global _CONFIG
    if _CONFIG is None:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        _CONFIG = _SchoolBusConfig(
            age_min=int(raw["age_min"]),
            age_max=int(raw["age_max"]),
            access_minutes=float(raw["access_minutes"]),
            detour_factor=float(raw["detour_factor"]),
            in_vehicle_speed_kmh=float(raw["in_vehicle_speed_kmh"]),
            ramassage_minutes=float(raw["ramassage_minutes"]),
            schedule_margin_minutes=float(raw["schedule_margin_minutes"]),
        )
    return _CONFIG


def _age_of(traits: Optional[dict]) -> Optional[int]:
    if not traits:
        return None
    try:
        return int(traits.get("age"))
    except (TypeError, ValueError):
        return None


def _haversine_km(a: Location, b: Location) -> float:
    """Distance à vol d'oiseau en km entre deux points (lat/lon en degrés)."""
    r = 6371.0088
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dphi = math.radians(b.lat - a.lat)
    dlmb = math.radians(b.lon - a.lon)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _same_loc(a: Optional[Location], b: Optional[Location], tol: float = 1e-6) -> bool:
    return (
        a is not None and b is not None
        and abs(a.lat - b.lat) <= tol and abs(a.lon - b.lon) <= tol
    )


def build_school_bus_option(
    person: Person,
    from_location: Optional[Location],
    next_activity: Activity,
    timestamp: int,
    departure_time: int,
) -> Optional[TravelPlan]:
    """Produit l'option car scolaire pour ce trajet, ou ``None`` si non éligible.

    Éligible si : persona de 5-17 ans, domicile hors ressort Tisséo
    (``home.public_transport is False``), et trajet dont l'une des extrémités est
    l'activité ``education`` du persona (aller : destination = école ; retour :
    origine = école).
    """
    cfg = _config()
    dest = next_activity.location
    if from_location is None or dest is None:
        return None

    # 1. Âge (seul critère individuel retenu).
    age = _age_of(person.identity.traits_json)
    if age is None or not (cfg.age_min <= age <= cfg.age_max):
        return None

    # 2. Zone : domicile hors ressort Tisséo (proxy : aucun arrêt Tisséo à ≤ 1,5 km).
    home = person.identity.home
    if home is None or home.public_transport is not False:
        return None

    # 3. Activité d'études du persona (destination scolaire ou lieu d'études connu).
    edu = next(
        (a for a in (person.identity.activities or [])
         if (a.purpose or "").lower() == "education" and a.location is not None),
        None,
    )
    if edu is None:
        return None

    # 4. Direction : la destination est l'école (aller) ou l'origine l'est (retour).
    dest_is_school = (next_activity.purpose or "").lower() == "education"
    origin_is_school = _same_loc(from_location, edu.location)
    if not (dest_is_school or origin_is_school):
        return None

    # 5. Distance à vol d'oiseau (pas de graphe : zéro impact OSMnx).
    d_km = _haversine_km(from_location, dest)

    # 6. Durée : accès + (distance × détour / vitesse) + ramassage.
    dur_s = int(round(
        cfg.access_minutes * 60
        + (d_km * cfg.detour_factor / cfg.in_vehicle_speed_kmh) * 3600
        + cfg.ramassage_minutes * 60
    ))

    # 7. Horaire, calé sur l'activité scolaire avec la marge.
    margin_s = int(cfg.schedule_margin_minutes * 60)
    if dest_is_school:
        school_24h = next_activity.scheduled_start_time
        if school_24h is None:
            school_24h = next_activity.start_time
        school_abs = to_timestamp_based_on_day(int(school_24h), timestamp)
        end_abs = school_abs - margin_s          # arrive 30 min avant le début
        start_abs = end_abs - dur_s
        direction = "outbound"
    else:  # retour : part 30 min après la fin de l'école
        school_abs = to_timestamp_based_on_day(int(edu.end_time), timestamp)
        start_abs = school_abs + margin_s
        end_abs = start_abs + dur_s
        direction = "return"

    # Bouclage J+1, comme le calcul de departure_time du contrôleur.
    if start_abs < timestamp:
        start_abs += 86400
        end_abs += 86400

    # 8. Plan à une jambe. Arrêts nommés → get_code() distinct d'une voiture.
    school_stop = "École"
    home_stop = "Arrêt car scolaire"
    if dest_is_school:
        leg_start = TransitLocation(stop=home_stop, lat=from_location.lat, lon=from_location.lon)
        leg_end = TransitLocation(stop=school_stop, lat=dest.lat, lon=dest.lon)
    else:
        leg_start = TransitLocation(stop=school_stop, lat=from_location.lat, lon=from_location.lon)
        leg_end = TransitLocation(stop=home_stop, lat=dest.lat, lon=dest.lon)

    leg = Transit(
        start_time=int(start_abs) * 1000,
        end_time=int(end_abs) * 1000,
        start_location=leg_start,
        end_location=leg_end,
        is_transfer=False,
        transit_route=SCHOOL_BUS_ROUTE_MARKER,
        shape_id=None,
        duration=dur_s,
        distance=d_km * 1000.0,
        mode="school_bus",
    )
    plan = TravelPlan(
        id=random_uuid(),
        start_location=from_location,
        end_location=dest,
        start_time=int(start_abs) * 1000,
        end_time=int(end_abs) * 1000,
        start_in=int(start_abs - departure_time),
        duration=dur_s,
        distance=d_km * 1000.0,
        legs=[leg],
    )
    SCHOOL_BUS_OPTIONS.labels(direction=direction).inc()
    logger.debug(
        f"[school_bus] option {direction} pour {person.person_id} "
        f"(âge {age}, {d_km:.1f} km, {dur_s // 60} min)"
    )
    return plan
