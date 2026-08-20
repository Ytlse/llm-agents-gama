import asyncio
import csv
import itertools
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from llm_module.core.geo_reference import residence_zone
from llm_module.core.housing_type import TRAIT_KEY as HOUSING_TRAIT_KEY, key_for
from models import Person, TravelPlan
from settings import settings

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

# Modes canoniques (llm_module.core.mode_choice) → libellés des colonnes, alignés sur
# le vocabulaire de « Mode de transport Choisi ». L'ordre fixe les colonnes du CSV.
_CANONICAL_FR = {
    "walking": "Marche",
    "cycling": "Vélo",
    "car": "Voiture Privée",
    "public_transport": "Transports_collectifs",
    "train": "Train",
    "motorbike": "Deux-roues motorisé",
    "other": "Autres modes",
}

# Une colonne par mode : la répartition estimée par le LLM avant tirage (somme = 100).
# Un mode non proposé vaut 0 (et non vide) — c'est ce qui distingue « était possible mais
# jugé nul » de « décision sans répartition » (mono-choix, erreur LLM, cache hérité), où
# toutes ces colonnes sont vides.
MODE_PROBABILITY_HEADERS = [f"P({label}) %" for label in _CANONICAL_FR.values()]

# Valeurs admises de « Contrainte de chaîne » (ticket 008, A4) — une seule par ligne :
#   ""              aucune contrainte, le jeu de choix est celui d'OTP ;
#   retour_force    verrou de retour appliqué, options restreintes au mode du véhicule garé ;
#   passager        trajet en voiture conduite par un tiers du foyer ;
#   sortie_bloquee  un mode véhiculé possédé a été écarté faute de véhicule sur place.
# La colonne **explique**, elle ne filtre pas : ces lignes restent dans le scoring, et
# la page de synthèse en affiche la répartition à côté des méthodes de sélection.
CHAIN_CONSTRAINTS = ("", "retour_force", "passager", "sortie_bloquee")

# Valeurs admises de « Anticipation » (ticket 014) — ce que le prompt de CE trajet
# contenait comme contexte d'anticipation :
#   ""        décision sans prompt (cache, mono-option) ou anticipation désactivée ;
#   agenda    bloc complet — agenda glissant + position des véhicules (+ météo du jour) ;
#   meteo     météo du jour seule (agent sans véhicule à chaîner).
# Indispensable pour segmenter l'A/B avant/après : les non-motorisés n'ont pas le bloc.
ANTICIPATION_VALUES = ("", "agenda", "meteo")

CSV_HEADERS = [
    "Référence",
    "Trajet",
    "ID Trajet",
    "Mode de transport Choisi",
    "Plus rapide",
    "Modes proposés au LLM",
    *MODE_PROBABILITY_HEADERS,
    "Lieu de résidence",
    "Genre",
    "Âge",
    "Occupation principale",
    "Type de logement",
    "Motifs de déplacement",
    "Distance parcourue",
    "Méthode de sélection",
    "Contrainte de chaîne",
    "Anticipation",
    "Fournisseur & Modèle",
    "Température",
    "Mémoire à court terme",
    "Mémoire à long terme",
    "Filtre de perception",
    "Traits de personnalité",
    "Météo Température (°C)",
    "Météo Condition",
    "Météo Précipitations (mm)",
    "Raisonnement",
    "Retard planification (s)",
    "Heure de calcul",
    "Temps simulé",
    "Heure de départ",
    "ID Personne",
    "ID Activité",
]


def _residence_zone(home_lat: Optional[float], home_lon: Optional[float]) -> str:
    """Couronne de résidence — délègue à la définition PARTAGÉE (ticket 013).

    Le classement vivait ici. Il est monté dans `llm_module.core.geo_reference`, qui
    porte déjà l'hypercentre et se déclare seul point de lecture, parce qu'un second
    consommateur est apparu : le temps terminal spatialisé des trajets véhiculés.
    Deux classements divergents feraient facturer un stationnement de centre-ville à
    un agent que cette colonne dit en 2ᵉ couronne.
    """
    return residence_zone(home_lat, home_lon)


def _housing_type(traits: dict) -> str:
    """Type de logement du persona, aux modalités de la référence EMC².

    Le trait est posé à la génération de population (`scripts/data/population/
    enrich_housing_type.py`) : il est **imputé** depuis la loi que l'enquête observe
    dans la zone fine du domicile, jamais tiré ici. Ce module ne fait que le recopier.

    Vide quand le persona n'en porte pas — population générée avant l'action A2, ou
    domicile hors de la couche de zones fines, où l'on ne devine pas. Vide n'est donc
    pas une modalité, exactement comme une cellule de probabilité vide n'est pas un 0.
    Une valeur hors référentiel est ramenée à vide plutôt que journalisée : la page de
    synthèse joint cette colonne sur les libellés EMC², une valeur exotique y
    disparaîtrait sans être comptée.
    """
    label = str(traits.get(HOUSING_TRAIT_KEY) or "").strip()
    return label if key_for(label) else ""


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


def _available_modes_summary(options: Optional[list]) -> str:
    if not options:
        return ""
    return " | ".join(_plan_transport_mode(opt) for opt in options)


def _mode_probability_cells(distribution: Optional[dict]) -> list:
    """Ventile la répartition par mode sur une colonne par mode (ordre `_CANONICAL_FR`).

    Sans répartition (mono-choix, erreur LLM, point de cache hérité), toutes les cellules
    sont vides — à distinguer d'un 0, qui signifie « le LLM a explicitement écarté ce mode ».
    """
    if not distribution:
        return [""] * len(_CANONICAL_FR)
    return [round(distribution.get(mode, 0.0) * 100, 1) for mode in _CANONICAL_FR]


def _plan_distance_km(plan: Optional[TravelPlan]) -> str:
    if plan is None:
        return ""
    if plan.distance is not None:
        return str(round(plan.distance / 1000, 2))
    total = sum(leg.get_distance() for leg in (plan.legs or []))
    return str(round(total / 1000, 2))


class GamaArrivalsLogger:
    _instance: Optional["GamaArrivalsLogger"] = None

    _HEADERS = ["move_id", "person_id", "arrive_at", "expected_arrive_at", "delay_s", "started_at", "schedule_at", "departure_delay_s", "timed_out"]

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

    def _write_arrival(self, move_id: str, person_id: str, arrive_at: int, expected_arrive_at: int,
                       started_at: Optional[int], schedule_at: Optional[int], timed_out: bool):
        self._ensure_header()
        delay_s = arrive_at - expected_arrive_at
        departure_delay_s = (started_at - schedule_at) if started_at is not None and schedule_at is not None else None
        with open(self._path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([move_id, person_id, arrive_at, expected_arrive_at, delay_s,
                                    started_at, schedule_at, departure_delay_s, timed_out])

    async def log_arrival(self, move_id: str, person_id: str, arrive_at: int, expected_arrive_at: int,
                          started_at: Optional[int] = None, schedule_at: Optional[int] = None,
                          timed_out: bool = False):
        # Écriture déportée hors de l'event loop (open/write bloquants) ; le lock asyncio
        # garantit l'ordre des lignes et l'unicité de l'écriture d'en-tête.
        async with self._lock:
            await asyncio.to_thread(self._write_arrival, move_id, person_id, arrive_at,
                                    expected_arrive_at, started_at, schedule_at, timed_out)


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
        chain_constraint: str = "",
        anticipation: str = "",
        weather_temp: Optional[float] = None,
        weather_condition: Optional[str] = None,
        weather_precip_mm: Optional[float] = None,
        late_s: int = 0,
        move_id: str = "",
        simulated_time: Optional[int] = None,
        start_time: Optional[int] = None,
        available_options: Optional[list] = None,
        activity_id: Optional[str] = None,
        mode_probabilities: Optional[dict] = None,
    ):
        async with self._lock:
            computed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            trip_id = next(self._counter)
            traits = person.identity.traits_json
            home = person.identity.home

            gender_raw = traits.get("gender", "")
            gender = "Homme" if gender_raw == "Male" else "Femme" if gender_raw == "Female" else gender_raw

            purpose_fr = _PURPOSE_FR.get((purpose or "").lower(), purpose or "")

            no_move = selection_method == "Pas de déplacement (même localisation)"
            row = [
                settings.workdir.name,
                trip_id,
                move_id,
                "Aucun" if no_move else _plan_transport_mode(plan),
                _plan_transport_mode(faster_itinerary),
                _available_modes_summary(available_options),
                *_mode_probability_cells(mode_probabilities),
                _residence_zone(home.lat if home else None, home.lon if home else None),
                gender,
                traits.get("age", ""),
                traits.get("main_occupation", ""),
                _housing_type(traits),
                purpose_fr,
                _plan_distance_km(plan),
                selection_method,
                chain_constraint if chain_constraint in CHAIN_CONSTRAINTS else "",
                anticipation if anticipation in ANTICIPATION_VALUES else "",
                provider_model,
                settings.agent.llm_params.get("temperature", ""),
                True,
                settings.agent.long_term_memory_enabled,
                settings.agent.long_term_memory_filter_by_datetime,
                "personality" in traits,
                weather_temp if weather_temp is not None else "",
                weather_condition if weather_condition is not None else "",
                weather_precip_mm if weather_precip_mm is not None else "",
                reasoning,
                late_s,
                computed_at,
                simulated_time if simulated_time is not None else "",
                datetime.fromtimestamp(start_time / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if start_time is not None else "",
                person.person_id,
                activity_id if activity_id is not None else "",
            ]

            # Écriture déportée hors de l'event loop (open/write bloquants)
            await asyncio.to_thread(self._write_row, row)

    def _write_row(self, row: list):
        self._ensure_header()
        with open(self._path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)
