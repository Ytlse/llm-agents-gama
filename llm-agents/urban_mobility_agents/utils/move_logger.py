import asyncio
import csv
import itertools
import math
from pathlib import Path
from typing import Optional

from models import Person, TravelPlan
from settings import settings

_TOULOUSE_CENTER_LAT = 43.6047
_TOULOUSE_CENTER_LON = 1.4442

_TRANSIT_MODES = {"bus", "metro", "tram", "cableway", "rail", "ferry", "subway", "gondola", "funicular"}
_CAR_MODES = {"car", "__car__"}
_BIKE_MODES = {"bicycle", "bike"}
_WALK_MODES = {"foot", "walk"}

_PURPOSE_FR = {
    "work": "Travail",
    "education": "Etude",
    "shop": "Achats",
    "shopping": "Achats",
    "escort": "Accompagnement",
    "accompany": "Accompagnement",
}

CSV_HEADERS = [
    "Référence",
    "Trajet",
    "Mode de transport",
    "Lieu de résidence",
    "Genre",
    "Âge",
    "Occupation principale",
    "Type de logement",
    "Motifs de déplacement",
    "Distance parcourue",
    "Méthode de sélection",
    "Fournisseur & Modèle",
    "Température",
    "Mémoire à court terme",
    "Mémoire à long terme",
    "Filtre de perception",
    "Traits de personnalité",
]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _residence_zone(home_lat: Optional[float], home_lon: Optional[float]) -> str:
    if home_lat is None or home_lon is None:
        return ""
    d = _haversine_km(_TOULOUSE_CENTER_LAT, _TOULOUSE_CENTER_LON, home_lat, home_lon)
    if d < 8:
        return "Toulouse"
    elif d < 20:
        return "1ere couronne"
    elif d < 40:
        return "2eme couronne"
    return "3eme couronne"


def _plan_transport_mode(plan: Optional[TravelPlan]) -> str:
    if plan is None:
        return ""
    non_transfer = [leg for leg in (plan.legs or []) if not leg.is_transfer]
    if not non_transfer:
        return "Marche"
    modes = {(leg.mode or "").lower() for leg in non_transfer}
    if modes & _CAR_MODES:
        return "Voiture Privée"
    if modes & _TRANSIT_MODES:
        return "Transports en commun"
    if modes & _BIKE_MODES:
        return "Vélo"
    if modes <= _WALK_MODES:
        return "Marche"
    return "Autres modes"


def _plan_distance_km(plan: Optional[TravelPlan]) -> str:
    if plan is None:
        return ""
    if plan.distance is not None:
        return str(round(plan.distance / 1000, 2))
    total = sum(leg.get_distance() for leg in (plan.legs or []))
    return str(round(total / 1000, 2))


class MoveLogger:
    _instance: Optional["MoveLogger"] = None

    def __init__(self):
        self._path: Optional[Path] = None
        self._lock = asyncio.Lock()
        self._counter = itertools.count(1)
        self._initialized = False

    @classmethod
    def get_instance(cls) -> "MoveLogger":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _resolve_path(self) -> Path:
        return Path(settings.app.log_file).parent / "moves.csv"

    def _ensure_header(self):
        if self._initialized:
            return
        path = self._resolve_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with open(path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(CSV_HEADERS)
        self._path = path
        self._initialized = True

    async def log_move(
        self,
        person: Person,
        plan: Optional[TravelPlan],
        purpose: Optional[str],
        selection_method: str,
        provider_model: str,
    ):
        async with self._lock:
            self._ensure_header()
            trip_id = next(self._counter)
            traits = person.identity.traits_json
            home = person.identity.home

            gender_raw = traits.get("gender", "")
            gender = "Homme" if gender_raw == "Male" else "Femme" if gender_raw == "Female" else gender_raw

            purpose_fr = _PURPOSE_FR.get((purpose or "").lower(), purpose or "")

            row = [
                settings.workdir.name,
                trip_id,
                _plan_transport_mode(plan),
                _residence_zone(home.lat if home else None, home.lon if home else None),
                gender,
                traits.get("age_bracket", ""),
                traits.get("main_occupation", ""),
                "",  # Type de logement — not available in traits_json
                purpose_fr,
                _plan_distance_km(plan),
                selection_method,
                provider_model,
                settings.agent.llm_params.get("temperature", ""),
                True,
                settings.agent.long_term_memory_enabled,
                settings.agent.long_term_memory_filter_by_datetime,
                "personality" in traits,
            ]

            with open(self._path, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(row)
