import asyncio
import csv
import itertools
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from models import Person, TravelPlan
from settings import settings

_TOULOUSE_CENTER_LAT = 43.6047
_TOULOUSE_CENTER_LON = 1.4442

_BUS_MODES = {"bus", "metro", "subway","tram", "cableway", "gondola", "funicular"}
_RAIL_MODES = {"rail"}
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
    "ID Trajet",
    "Mode de transport Choisi",
    "Plus rapide",
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
    "Raisonnement",
    "Retard planification (s)",
    "Heure de calcul",
    "Temps simulé",
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
    if modes & _BUS_MODES:
        return "Transports_collectifs"
    if modes & _RAIL_MODES:
        return "Train"
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


class GamaArrivalsLogger:
    _instance: Optional["GamaArrivalsLogger"] = None

    _HEADERS = ["move_id", "person_id", "arrive_at", "expected_arrive_at", "delay_s"]

    def __init__(self):
        self._path: Optional[Path] = None
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> "GamaArrivalsLogger":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _ensure_header(self):
        path = Path(settings.app.log_file).parent / "gama_results" / "gama_arrivals.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        needs_header = not path.exists()
        self._path = path
        if needs_header:
            with open(path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(self._HEADERS)

    async def log_arrival(self, move_id: str, person_id: str, arrive_at: int, expected_arrive_at: int):
        async with self._lock:
            self._ensure_header()
            delay_s = arrive_at - expected_arrive_at
            with open(self._path, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([move_id, person_id, arrive_at, expected_arrive_at, delay_s])


class MoveLogger:
    _instance: Optional["MoveLogger"] = None

    def __init__(self):
        self._path: Optional[Path] = None
        self._lock = asyncio.Lock()
        self._counter = itertools.count(1)

    @classmethod
    def get_instance(cls) -> "MoveLogger":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _resolve_path(self) -> Path:
        return Path(settings.app.log_file).parent / "moves.csv"

    def _ensure_header(self):
        path = self._resolve_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        needs_header = not path.exists()
        self._path = path
        if needs_header:
            with open(path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(CSV_HEADERS)

    async def log_move(
        self,
        person: Person,
        plan: Optional[TravelPlan],
        purpose: Optional[str],
        selection_method: str,
        provider_model: str,
        faster_itinerary: Optional[TravelPlan],
        reasoning: str,
        late_s: int = 0,
        move_id: str = "",
        simulated_time: Optional[int] = None,
    ):
        async with self._lock:
            self._ensure_header()
            computed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            trip_id = next(self._counter)
            traits = person.identity.traits_json
            home = person.identity.home

            gender_raw = traits.get("gender", "")
            gender = "Homme" if gender_raw == "Male" else "Femme" if gender_raw == "Female" else gender_raw

            purpose_fr = _PURPOSE_FR.get((purpose or "").lower(), purpose or "")

            row = [
                settings.workdir.name,
                trip_id,
                move_id,
                _plan_transport_mode(plan),
                _plan_transport_mode(faster_itinerary),
                _residence_zone(home.lat if home else None, home.lon if home else None),
                gender,
                traits.get("age", ""),
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
                reasoning,
                late_s,
                computed_at,
                simulated_time if simulated_time is not None else "",
            ]

            with open(self._path, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(row)
