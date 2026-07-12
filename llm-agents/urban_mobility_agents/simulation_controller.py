"""
Ce module définit la boucle de simulation principale (SimulationLoopV1) pour le scénario.

Son rôle est d'orchestrer le déroulement de la simulation au fil du temps. Il gère :
- La synchronisation de l'état du monde et des agents.
- Le déclenchement des actions des agents (planification des déplacements).
- Le traitement des observations de l'environnement.
- L'orchestration des cycles de réflexion (mémoire à court et long terme) des agents.

Modèle de planification :
- Chemin rapide O(1) : à chaque arrivée, l'agent déclenche directement sa propre planification
  via _try_schedule_person → _plan_one (sous sémaphore de concurrence).
- Chemin de fallback O(N) : un Worker scanne toute la population toutes les 30 s pour
  rattraper les agents dont l'observation d'arrivée aurait été manquée.
- Deux points de push WebSocket vers GAMA :
    Point 1 : fin de calcul (l'agent est IDLE au moment où le trajet est prêt)
    Point 2 : réception d'un feedback d'arrivée (le trajet suivant est déjà Planned)
"""

import asyncio
import contextlib
import heapq
import math
import time
from dataclasses import dataclass
from typing import Callable, Coroutine, Optional, Tuple
import datetime

from loguru import logger

from backpressure import ThroughputEwma

from helper import humanize_duration, humanize_time, to_timestamp_based_on_day, humanize_date, to_24h_timestamp_full, shift_weekend_departure_to_monday, format_sim_timing
from models import Activity, BBox, Location, Person, PersonMove, TravelPlan
from urban_mobility_agents.core.scenario import Action, BaseScenario, Observation
from urban_mobility_agents.utils.history_log import HistoryStreamLog
from urban_mobility_agents.agents.llm_agent import Context, LlmAgent
from text_helper import env_ob_to_text, parse_ob
from trip_helper.base import TripHelper
from utils import random_uuid
from world.population import WorldPopulation
from world.world_data import WorldModel
from settings import settings

from prometheus_client import Counter, Gauge, Histogram
from llm_module.telemetry.alarms import fire_alarme
from urban_mobility_agents.utils.move_logger import GamaArrivalsLogger, MoveLogger
from urban_mobility_agents.utils.weather_loader import get_weather
from urban_mobility_agents.utils.pipeline_logger import PipelineLogger

history_logger = HistoryStreamLog.get_instance()


def _format_cache_hit_rates() -> str:
    """Ligne de log unifiée du taux de cache des trois sources de routage/décision.

    OTP, OSMnx et LLM sont des caches process-wide indépendants. Pour chacun on affiche
    hits/lookups (%) ; 'off' quand la source n'a reçu aucune requête (cache désactivé ou
    non encore sollicité)."""
    from trip_helper.cached_triphelper import get_otp_cache_stats
    from trip_helper.osmnx_direct import get_osmnx_cache_stats
    try:
        from llm.cache import get_llm_cache_stats, get_llm_miss_breakdown
        llm_stats = get_llm_cache_stats()
        llm_misses = get_llm_miss_breakdown()
    except Exception:
        llm_stats = (0, 0)
        llm_misses = {}

    # OTP : 'off' ambigu → préciser pourquoi le compteur est à 0.
    otp_hits, otp_total = get_otp_cache_stats()
    if otp_total == 0:
        if not settings.gtfs.otp_cache_enabled:
            otp_str = "OTP off (désactivé)"
        else:
            otp_str = "OTP off (aucune requête)"
    else:
        otp_str = f"OTP {100 * otp_hits // otp_total}% ({otp_hits}/{otp_total})"

    def _fmt(name: str, stats: tuple[int, int]) -> str:
        hits, total = stats
        if total == 0:
            return f"{name} off"
        return f"{name} {100 * hits // total}% ({hits}/{total})"

    llm_str = _fmt("LLM", llm_stats)
    if llm_misses:
        _breakdown = ", ".join(f"{r}={n}" for r, n in sorted(llm_misses.items(), key=lambda kv: -kv[1]))
        llm_str += f" [miss: {_breakdown}]"

    return " · ".join([
        otp_str,
        _fmt("OSMnx", get_osmnx_cache_stats()),
        llm_str,
    ])

PROCESS_PERSON_CALLS = Counter('gama_process_person_calls_total', 'Total calls to process_person')
# Toutes décisions confondues (LLM, cache sémantique, mono-choix, fallback) : compté au
# push du trajet vers GAMA — contrairement aux llm_mode_by_* de la gateway qui ne voient
# que les décisions passées par un appel LLM réel.
TRIP_MODE_BY_PURPOSE = Counter(
    'trip_mode_by_purpose_total',
    'Trajets poussés vers GAMA par mode principal et motif d\'activité',
    ['mode', 'purpose'],
)
EVALUATE_PLAN_CALLS = Counter('gama_evaluate_plan_calls_total', 'Total calls to evaluate_and_choose_travel_plan')
ACTIONS_CREATED = Counter('gama_actions_created_total', 'Total actions created')
PLANNING_LATE = Counter('controller_planning_late_total', 'Agents dont la date de départ était déjà passée lors de la planification')
LOST_ARRIVALS_RECOVERED = Counter('controller_lost_arrivals_recovered_total', 'Agents récupérés par le watchdog d\'arrivée (move poussé jamais suivi d\'observation d\'arrivée)')
ITINERARY_100_COMPLETION = Gauge('agent_itinerary_100_completion_seconds', 'Durée réelle (secondes) pour traiter 100 itinéraires réussis consécutifs')
BOOTSTRAP_DURATION = Gauge('agent_bootstrap_duration_seconds', 'Durée réelle (secondes) du bootstrap_all_agents (calcul initial des itinéraires au /init)')

# Détail temps réel de l'avancement de la phase 4 (bootstrap itinéraires), pour le cockpit.
BOOTSTRAP_ACTIVE        = Gauge('agent_bootstrap_active', 'Bootstrap en cours (1) ou terminé/inactif (0)')
BOOTSTRAP_TOTAL         = Gauge('agent_bootstrap_total', 'Nombre d\'agents éligibles à planifier au bootstrap')
BOOTSTRAP_COMPLETED     = Gauge('agent_bootstrap_completed', 'Agents dont le premier itinéraire est calculé (vague 1)')
BOOTSTRAP_PROGRESS      = Gauge('agent_bootstrap_progress_ratio', 'Progression de la vague 1 du bootstrap (0..1 = completed/total)')
BOOTSTRAP_CACHE_HITS    = Gauge('agent_bootstrap_cache_hits', 'Premiers itinéraires servis depuis le cache LLM pendant le bootstrap')
BOOTSTRAP_CACHE_MISSES  = Gauge('agent_bootstrap_cache_misses', 'Premiers itinéraires calculés via LLM (cache miss) pendant le bootstrap')
BOOTSTRAP_WAVE          = Gauge('agent_bootstrap_wave', 'Vague d\'anticipation courante (1 = premier itinéraire, ≥2 = act[N+k] pré-calculés)')
BOOTSTRAP_FUTURE_MOVES  = Gauge('agent_bootstrap_future_moves', 'Trajets futurs (act[N+k]) pré-cachés cumulés pendant le bootstrap')
# Détail par vague (1 = premiers itinéraires, ≥2 = anticipation act[N+k]).
# status : planned = candidats de la vague, done = traités (succès ou non),
#          ok = itinéraires obtenus, cache_hit/cache_miss = cache LLM (agents LLM seulement).
BOOTSTRAP_WAVE_MOVES    = Gauge('agent_bootstrap_wave_moves', 'Trajets par vague du bootstrap', ['wave', 'status'])
_WAVE_COUNTED_STATUSES  = ("done", "ok", "cache_hit", "cache_miss")


def _wave_metrics(wave: int, planned: int) -> dict:
    """Initialise et retourne les compteurs par statut d'une vague de bootstrap."""
    BOOTSTRAP_WAVE_MOVES.labels(wave=str(wave), status="planned").set(planned)
    counters = {s: BOOTSTRAP_WAVE_MOVES.labels(wave=str(wave), status=s) for s in _WAVE_COUNTED_STATUSES}
    for c in counters.values():
        c.set(0)
    return counters

# Issue de la décision de mobilité par activité planifiée. outcome ∈
#   llm           : plan choisi par le LLM
#   llm_fallback  : LLM sans réponse (saturation/timeout) → index par défaut (activité dégradée)
#   single        : un seul itinéraire → sélection automatique
#   no_solution   : aucun mode de transport ne relie l'OD
#   no_move       : déjà à destination (pas de déplacement)
# phase ∈ {bootstrap, live} : le bootstrap pré-calcule les itinéraires au /init (l'agent
# n'a encore rien « raté » — il partira quand même sur le fallback). Le cockpit ne compte
# comme « activités ratées faute de LLM » que la phase live (cf. panneaux ③).
# Permet de suivre en temps réel les activités « ratées faute de réponse LLM » (llm_fallback).
ACTIVITY_DECISIONS = Counter(
    'agent_activity_decisions_total',
    'Décisions de mobilité par activité planifiée, ventilées par issue (outcome) et phase',
    ['outcome', 'phase'],
)
# selection_method (texte du move-log) → outcome (label métrique, faible cardinalité)
_SELECTION_OUTCOME = {
    "LLM": "llm",
    "LLM Error (Default index)": "llm_fallback",
    "Un seul itinéraire disponible": "single",
    "Pas de solution de déplacement": "no_solution",
    "Pas de déplacement (même localisation)": "no_move",
}

# Métriques goulots d'étranglement
AGENT_SCHEDULING_LAG = Histogram(
    'agent_scheduling_lag_seconds',
    'δ entre scheduled_start_time et envoi de l\'action à GAMA (positif = en retard)',
    buckets=[10, 60, 300, 1800, float('inf')],
)
CONTROLLER_SCHEDULING_IN_PROGRESS = Gauge(
    'controller_scheduling_in_progress',
    'Nombre d\'agents en attente de décision LLM (scheduling_in_progress=True)',
)
AGENT_LATE_DEPARTURE = Histogram(
    'agent_late_departure_seconds',
    'Retard des agents (sim_time - scheduled_start_time) lors du skip d\'activité',
    buckets=[60, 300, 1800, 7200, float('inf')],
)

# Ponctualité des départs (dashboard 07 · Métier Mobilité). Un départ est « à l'heure »
# si l'action part vers GAMA au plus LATE_DEPARTURE_TOLERANCE_S après l'heure prévue
# (même lag que AGENT_SCHEDULING_LAG). Phase live uniquement : le bootstrap pré-calcule
# au /init et ne mesure pas un vrai départ.
LATE_DEPARTURE_TOLERANCE_S = 60
DEPARTURE_PUNCTUALITY = Counter(
    'agent_departures_punctuality_total',
    'Départs poussés vers GAMA (phase live) par ponctualité : on_time (lag ≤ 60 s) ou late',
    ['status'],
)
DEPARTURE_DELAY = Histogram(
    'agent_departure_delay_seconds',
    'Retard (s) des seuls départs en retard (lag > 60 s) — sum/count = retard moyen',
    buckets=[120, 300, 900, 1800, 3600, float('inf')],
)
DEPARTURE_DELAY_MAX = Gauge(
    'agent_departure_delay_max_seconds',
    'Retard maximal (s) observé sur un départ depuis le démarrage du contrôleur',
)
for _status in ('on_time', 'late'):
    DEPARTURE_PUNCTUALITY.labels(status=_status)


_POPULATION_CHECKPOINT_HOUR = 2 * 3600  # 2:00 AM simulation time


def _next_checkpoint_ts(after_ts: int, hour_24h: int = _POPULATION_CHECKPOINT_HOUR) -> int:
    """Return the absolute timestamp of the next 2 AM occurrence after after_ts."""
    day_start = (after_ts // 86400) * 86400
    candidate = day_start + hour_24h
    if candidate <= after_ts:
        candidate += 86400
    return candidate


def _estimate_fallback_duration(origin, destination) -> int:
    """Estimate travel time in seconds from crow-flies distance at 30 km/h with 1.3 detour factor."""
    if origin is None or destination is None:
        return 30 * 60
    lat1, lon1 = math.radians(origin.lat), math.radians(origin.lon)
    lat2, lon2 = math.radians(destination.lat), math.radians(destination.lon)
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    distance_m = 2 * 6_371_000 * math.asin(math.sqrt(a))
    road_distance_m = distance_m * 1.3
    speed_ms = 30_000 / 3600  # 30 km/h
    return max(5 * 60, int(road_distance_m / speed_ms))


def _record_trip_mode(move: PersonMove, activity: Optional[Activity]) -> None:
    """Alimente trip_mode_by_purpose_total pour un trajet effectivement poussé vers GAMA."""
    if move.plan is None:
        return
    purpose = ((activity.purpose if activity else None) or move.purpose or "unknown").lower()
    TRIP_MODE_BY_PURPOSE.labels(mode=_primary_mode(move.plan), purpose=purpose).inc()


def _primary_mode(plan: TravelPlan) -> str:
    modes = {(leg.mode or "").lower() for leg in plan.legs if not leg.is_transfer}
    if modes & {"car"}:
        return "car"
    if modes & {"bicycle", "bike"}:
        return "bike"
    if not modes - {"foot", "walk", ""}:
        return "walk"
    return "transit"


def _select_candidates(itineraries: list[TravelPlan], max_n: int) -> list[TravelPlan]:
    """Cap to max_n itineraries, keeping the fastest plan per mode group first."""
    by_duration = sorted(itineraries, key=lambda p: p.duration or float("inf"))
    seen, priority, rest = set(), [], []
    for plan in by_duration:
        mode = _primary_mode(plan)
        if mode not in seen:
            seen.add(mode)
            priority.append(plan)
        else:
            rest.append(plan)
    selected = priority[:max_n]
    for plan in rest:
        if len(selected) >= max_n:
            break
        selected.append(plan)
    return selected


@dataclass
class _EdfJob:
    """Tâche de planification en file EDF (Earliest Deadline First).

    deadline_sim : échéance en temps SIMULÉ (heure de départ du trajet). Plus elle
                   est proche, plus la tâche est prioritaire. Sentinelle 0 pour un
                   push (déjà calculé, il ne reste qu'à envoyer → toujours prioritaire).
    kind         : "plan" | "refill" | "push" (métriques + snapshot de faisabilité).
    make_coro    : fabrique la coroutine à exécuter (paresseuse : rien n'est créé si
                   la file est vidée avant consommation → pas de "coroutine never awaited").
    person_id    : pour les logs.
    """
    deadline_sim: float
    kind: str
    make_coro: Callable[[], Coroutine]
    person_id: str


class SimulationLoopV1(BaseScenario):
    MAX_ADJUST_START_TIME = 15*60  # 15 minutes

    # Intervalle du scan de fallback (secondes). Ce scan rattrape les agents
    # dont l'observation d'arrivée aurait été manquée. Le chemin normal est
    # O(1) : chaque agent se programme lui-même à son arrivée.
    _WORKER_SCAN_INTERVAL = 30.0

    def __init__(self,
                 world_model: "WorldModel",
                 trip_helper: "TripHelper" = None,
                 agent: Optional["LlmAgent"] = None):
        self.MAX_ADJUST_START_TIME = settings.agent.max_reschedule_amount or self.MAX_ADJUST_START_TIME
        self._messages = []
        self._late_count = 0
        self._max_departure_delay_s = 0.0  # pire retard observé, alimente DEPARTURE_DELAY_MAX
        self._itinerary_success_count = 0
        self._itinerary_window_start = time.monotonic()
        # True pendant bootstrap_all_agents : distingue les décisions de pré-calcul (/init)
        # des décisions live (simulation en marche) pour la métrique ACTIVITY_DECISIONS.
        self._in_bootstrap = False
        self.model = world_model
        self.trip_helper = trip_helper
        self.agent = agent
        self.next_self_reflection_at = None
        self._stm_reflecting: set[str] = set()  # person_ids with an in-flight STM reflection task
        # Échéance EDF (temps SIM) de la réflexion STM en attente, par person_id.
        # Posée au premier déclenchement et CONSERVÉE entre les retentatives : un
        # échec gateway laisse les entrées STM en place, le sync suivant re-soumet
        # avec la deadline d'origine → la priorité EDF monte à chaque retry.
        self._stm_reflect_due: dict[str, float] = {}
        self._stm_overdue_alarm_on = False  # front montant de l'alarme réflexions en retard

        # Worker
        # _worker_sem  : limite la concurrence LLM+OTP (initialisé dans start_worker)
        # _worker_in_progress : activités dont le calcul est en cours (sous sémaphore ou en vol)
        # _current_sim_timestamp : dernier timestamp connu de la simulation
        self._worker_sem: Optional[asyncio.Semaphore] = None
        self._worker_loop_task: Optional[asyncio.Task] = None
        # Tâches fire-and-forget du scénario (planification, refill, réflexions…) :
        # annulées en bloc par stop_worker() pour qu'un scénario remplacé ne pousse
        # plus d'actions périmées vers la nouvelle simulation.
        self._inflight_tasks: set[asyncio.Task] = set()
        # --- Dispatcher EDF (ticket 003) ---
        # File de priorité (min-heap) triée par (deadline_sim, seq) : les tâches de
        # planification sont servies par échéance croissante, pas dans l'ordre d'arrivée.
        # Consommée par worker_concurrency tâches (_edf_consumer) qui REMPLACENT le
        # sémaphore comme limite de concurrence. Le sémaphore reste utilisé par le
        # bootstrap (hors dispatcher). Initialisés dans start_worker().
        self._edf_heap: list[tuple[float, int, _EdfJob]] = []
        self._edf_seq: int = 0
        self._edf_event: Optional[asyncio.Event] = None
        self._edf_consumers: list[asyncio.Task] = []
        # EWMA du débit de complétion (tâches/s) : mesuré à la fin de _plan_one /
        # _precompute_one (le pipeline complet OTP+LLM est l'unité qui draine la file).
        self._throughput: Optional[ThroughputEwma] = None
        self._worker_in_progress: int = 0
        self._current_sim_timestamp: int = 0
        self._push_fn: Optional[Callable[[Action], Coroutine]] = None
        self._next_population_checkpoint_at: Optional[int] = None
        # Suivi temporel : heure réelle franchie à chaque tranche de 24h de temps simulé
        self._sim_start_ts: Optional[int] = None       # premier timestamp simulé observé
        self._sim_real_start: Optional[float] = None   # heure réelle (monotonic) correspondante
        self._next_day_log_at: Optional[int] = None     # prochaine borne 24h à logger

        if settings.agent.reschedule_activity__version == 2:
            self.reschedule_amount_function = self.reschedule_amount_v2
            logger.info("Using reschedule activity function version v2")
        else:
            self.reschedule_amount_function = self.reschedule_amount
            logger.info("Using reschedule activity function version v1")

    # -------------------------------------------------------------------------
    # BaseScenario — interface publique Worker
    # -------------------------------------------------------------------------

    def set_push_fn(self, fn: Callable[[Action], Coroutine]) -> None:
        """Inject the coroutine used for direct WebSocket push to GAMA."""
        self._push_fn = fn

    @property
    def worker_in_progress_count(self) -> int:
        """Activités dont le calcul est en cours ou en file d'attente du sémaphore."""
        return self._worker_in_progress

    @property
    def late_since_last_sync(self) -> int:
        """Nombre d'arrivées planifiées en retard (expected_arrive_at < timestamp)
        accumulées depuis le dernier /sync (remis à 0 par sync()). Lu par le contrôleur
        avant sync() pour alimenter le compteur controller_deadline_misses_total."""
        return self._late_count

    @property
    def activities_to_compute_count(self) -> int:
        """Activités à calculer : en vol + agents Idle sans plan (comptage en direct).

        Le comptage Idle-sans-plan est en direct et non un snapshot du dernier sync :
        le mode drainage du /sync ré-échantillonne cette jauge chaque seconde pendant
        qu'il retient la réponse, et doit voir la pile baisser au fil des push pour
        rendre la main à GAMA dès le seuil de relâchement atteint.
        """
        idle_unplanned = sum(
            1 for p in self.population.get_people_list()
            if p.state.heading_to is None
            and not p.state.scheduling_in_progress
            and p.state.next_planned_move is None
        )
        return self._worker_in_progress + idle_unplanned

    def count_stuck_agents(self, current_ts: int, threshold_seconds: float) -> int:
        """Nombre d'agents sans planification réussie depuis plus de `threshold_seconds`
        de temps simulé.

        Choke point unique (appelé à chaque /sync) : un agent est "sain" s'il a un plan
        courant, des plans pré-calculés en réserve, ou un calcul en vol — dans ce cas on
        rafraîchit son horodatage de dernière réussite. Sinon, on le compte comme bloqué
        dès que l'écart au dernier plan réussi dépasse le seuil. Les agents jamais encore
        planifiés sont amorcés à `current_ts` (pas bloqués tant que le seuil n'est pas
        écoulé depuis leur première observation)."""
        stuck = 0
        for person in self.population.get_people_list():
            st = person.state
            healthy = (
                st.next_planned_move is not None
                or len(st.precomputed_moves) > 0
                or st.scheduling_in_progress
            )
            if healthy:
                st.last_successful_plan_sim_ts = current_ts
            elif st.last_successful_plan_sim_ts is None:
                st.last_successful_plan_sim_ts = current_ts
            elif current_ts - st.last_successful_plan_sim_ts > threshold_seconds:
                stuck += 1
        return stuck

    async def start_worker(self) -> None:
        """Start the fallback Worker (periodic scan), the EDF dispatcher and the semaphore."""
        concurrency = settings.world.worker_concurrency
        # Le sémaphore reste la limite de concurrence du BOOTSTRAP (hors dispatcher,
        # awaité par /init). En régime permanent, la limite est le nombre de consommateurs EDF.
        self._worker_sem = asyncio.Semaphore(concurrency)
        self._throughput = ThroughputEwma(
            tau_s=settings.world.throughput_ewma_tau_s,
            floor_per_s=settings.world.throughput_floor_per_s,
        )
        # Dispatcher EDF : file + N consommateurs. false = spawn direct FIFO historique.
        self._edf_heap = []
        self._edf_seq = 0
        self._edf_event = asyncio.Event()
        self._edf_consumers = []
        if settings.world.edf_enabled:
            self._edf_consumers = [
                asyncio.create_task(self._edf_consumer(i)) for i in range(concurrency)
            ]
        # La task est conservée pour pouvoir être annulée via stop_worker() lors
        # d'un remplacement de scénario (/init ou /test/init successifs).
        self._worker_loop_task = asyncio.create_task(self._worker_loop())
        logger.info(
            f"[worker] Worker started "
            f"(concurrency={concurrency}, edf={settings.world.edf_enabled}, "
            f"fallback_scan_interval={self._WORKER_SCAN_INTERVAL}s)"
        )

    def stop_worker(self) -> None:
        """Cancel the fallback Worker loop, EDF consumers and all in-flight tasks.

        Sans l'annulation des tâches en vol, les planifications LLM/OTP de l'ancien
        scénario continueraient après un stop GAMA et pousseraient leurs actions à la
        simulation suivante (mêmes person_ids → trajets périmés injectés). La file EDF
        est vidée au même moment pour ne pas exécuter des tâches périmées."""
        if self._worker_loop_task is not None and not self._worker_loop_task.done():
            self._worker_loop_task.cancel()
            logger.info("[worker] Worker loop cancelled (scenario replaced)")
        self._worker_loop_task = None
        # Annuler les consommateurs EDF et vider la file (jobs périmés jamais exécutés).
        for consumer in self._edf_consumers:
            if not consumer.done():
                consumer.cancel()
        _queued = len(self._edf_heap)
        self._edf_consumers = []
        self._edf_heap = []
        if _queued:
            logger.info(f"[edf] {_queued} queued job(s) discarded (scenario replaced)")
        # Les jobs "reflect" en file sont détruits sans exécuter leur finally :
        # purger l'état de suivi pour que le prochain scénario reparte propre.
        self._stm_reflecting.clear()
        self._stm_reflect_due.clear()
        cancelled = 0
        for task in list(self._inflight_tasks):
            if not task.done():
                task.cancel()
                cancelled += 1
        self._inflight_tasks.clear()
        if cancelled:
            logger.info(f"[worker] {cancelled} in-flight task(s) cancelled (scenario replaced)")

    def _spawn(self, coro) -> asyncio.Task:
        """Lance une tâche fire-and-forget rattachée au scénario (annulable via stop_worker)."""
        task = asyncio.create_task(coro)
        self._inflight_tasks.add(task)
        task.add_done_callback(self._inflight_tasks.discard)
        return task

    # -------------------------------------------------------------------------
    # Dispatcher EDF (Earliest Deadline First)
    # -------------------------------------------------------------------------

    def _dispatch(self, deadline_sim: float, kind: str, make_coro: Callable[[], Coroutine], person_id: str) -> None:
        """Route une tâche de planification : file EDF si activée, sinon spawn direct FIFO.

        Les invariants (scheduling_in_progress / precompute_in_progress / _worker_in_progress)
        sont posés par l'APPELANT avant l'appel — une tâche en file compte comme « en vol ».
        """
        if settings.world.edf_enabled and self._edf_event is not None:
            self._edf_seq += 1
            job = _EdfJob(deadline_sim=float(deadline_sim), kind=kind, make_coro=make_coro, person_id=person_id)
            heapq.heappush(self._edf_heap, (job.deadline_sim, self._edf_seq, job))
            self._edf_event.set()
        else:
            # Comportement historique : fire-and-forget, la concurrence est bornée par
            # le sémaphore acquis dans la coroutine (_worker_concurrency_guard).
            self._spawn(make_coro())

    async def _edf_consumer(self, idx: int) -> None:
        """Consommateur EDF : dépile la tâche la plus urgente et l'exécute.

        Les N consommateurs constituent la limite de concurrence (ils remplacent le
        sémaphore). Motif de réveil sûr : on vide le heap, on clear l'event, on
        re-teste le heap avant de dormir (évite le réveil perdu si un job arrive juste
        après le clear — set() est collant, wait() rend la main immédiatement).
        """
        assert self._edf_event is not None
        while True:
            try:
                while self._edf_heap:
                    _, _, job = heapq.heappop(self._edf_heap)
                    try:
                        await job.make_coro()
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        logger.error(f"[edf] job {job.kind} for {job.person_id} failed: {e}")
                self._edf_event.clear()
                if self._edf_heap:
                    continue
                await self._edf_event.wait()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[edf] consumer {idx} unexpected error: {e}")

    def _worker_concurrency_guard(self):
        """Contexte de concurrence pour _plan_one / _precompute_one.

        Sous EDF, la concurrence est déjà bornée par le nombre de consommateurs →
        aucun sémaphore (sinon double limitation). Sinon (spawn direct FIFO), le
        sémaphore borne la concurrence comme historiquement.
        """
        if settings.world.edf_enabled and self._edf_consumers:
            return contextlib.nullcontext()
        return self._worker_sem

    def _mark_completion(self) -> None:
        """Enregistre la complétion d'une tâche du pipeline (débit D de la file EDF)."""
        if self._throughput is not None:
            self._throughput.mark_completion(time.monotonic())

    def throughput_per_s(self) -> float:
        """Débit de complétion courant (tâches/s, EWMA) — >= plancher, jamais 0."""
        if self._throughput is None:
            return settings.world.throughput_floor_per_s
        return self._throughput.rate(time.monotonic())

    @property
    def edf_queue_depth(self) -> int:
        """Nombre de tâches en attente dans la file EDF (hors tâches en cours d'exécution)."""
        return len(self._edf_heap)

    def edf_snapshot_deadlines(self) -> list[float]:
        """Snapshot trié des échéances (temps SIM) des tâches plan/refill/reflect en file.

        Exclut les push (sentinelle 0 : déjà calculés, drainés en ms — les inclure
        fausserait le test de faisabilité en simulant une échéance déjà expirée).
        Les réflexions STM (kind "reflect", échéance +12h sim) sont incluses : c'est
        la contre-pression prédictive qui garantit leur échéance en retenant le /sync
        si le débit courant ne permet plus de les servir à temps.
        """
        return sorted(
            job.deadline_sim for _, _, job in self._edf_heap if job.kind in ("plan", "refill", "reflect")
        )

    # -------------------------------------------------------------------------
    # Worker — boucle principale et scan proactif
    # -------------------------------------------------------------------------

    async def _worker_loop(self) -> None:
        """Scan de fallback : rattrape les agents Idle dont l'observation a été manquée.

        Le chemin normal est O(1) via _try_schedule_person déclenché à chaque arrivée.
        Ce scan O(N) ne tourne que toutes les _WORKER_SCAN_INTERVAL secondes.
        """
        while True:
            try:
                await asyncio.sleep(self._WORKER_SCAN_INTERVAL)
                await self._scan_and_plan_all_idle()
            except Exception as e:
                logger.error(f"[worker] Unexpected scan error: {e}")

    # -------------------------------------------------------------------------
    # MODÈLE D'HORIZON (pré-planification glissante)
    # -------------------------------------------------------------------------
    # Chaque agent possède une liste cyclique de `nb` activités par jour
    # (person.identity.activities). Une activité n'est PAS liée à un jour
    # calendaire : start_time/end_time sont des offsets 24h ; le jour réel est
    # déduit du timestamp de fin de l'activité précédente.
    #
    # Invariant visé, en permanence, pour chaque agent :
    #   - 1 activité EN COURS (l'agent y est, ou est en trajet vers elle) ;
    #   - ~(nb-1) activités suivantes déjà PLANIFIÉES (trajets pré-calculés dans
    #     person.state.precomputed_moves) ou EN COURS de planification (tâche de
    #     refill en vol). Autrement dit, toute la journée de l'agent est tenue
    #     d'avance — ce n'est pas un horizon à 1 cran.
    #
    # Deux phases alimentent cet horizon :
    #   1. BOOTSTRAP (_bootstrap_all_agents, vers L992) : précalcule tout le
    #      cycle journalier par vagues act[N+1], act[N+2], … et s'arrête au tour
    #      complet (next_act == act_N). En sortie, precomputed_moves contient
    #      ~(nb-1) trajets, et precomputed_horizon_{act,ts} pointe sur le dernier.
    #   2. RÉGIME PERMANENT (horizon glissant) : à chaque trajet consommé
    #      (popleft sur precomputed_moves), _refill_precomputed_queue recalcule
    #      EXACTEMENT un trajet au-delà de l'horizon courant. On dépile 1, on
    #      réempile 1 → la profondeur ~(nb-1) reste constante.
    #
    # Base temporelle du chaînage : chaque maillon part de l'ARRIVÉE du maillon
    # précédent (move.expected_arrive_at), ce qui propage correctement tout
    # décalage de jour (cf. report week-end → lundi dans _compute_move_for_activity).
    # _try_schedule_next_after est un chemin de SECOURS (file vide) qui, lui,
    # part de _current_sim_timestamp.
    # -------------------------------------------------------------------------

    def _try_schedule_next_after(self, person: Person, just_started_activity: Activity, timestamp: int) -> bool:
        """Pré-planifie act[N+1] en utilisant act[N].location comme origin. Non-bloquant.

        Appelé après chaque dispatch (bootstrap ou push) pour garantir que l'agent
        a toujours son prochain trajet prêt avant d'arriver à destination.
        """
        if person.state.scheduling_in_progress or person.state.next_planned_move is not None:
            return False

        activities = person.identity.activities
        if not activities or just_started_activity.location is None:
            return False

        try:
            curr_idx = activities.index(just_started_activity)
        except ValueError:
            return False

        next_idx = (curr_idx + 1) % len(activities)
        next_act = activities[next_idx]

        if next_act.location is None:
            return False

        # Build the full Unix timestamp for when just_started_activity ENDS.
        # Activity.start_time and .end_time are 24h offsets (seconds within a day).
        # If end_time < start_time the activity ends the next calendar day.
        # Using timestamp directly would give the wrong day when, e.g., act[N]=15h46
        # ends at 14h06 next day: to_timestamp_based_on_day(14h06, 5am_sim_start)
        # returns same-day 14h06 (still in the future at 5am) instead of next-day 14h06.
        act_start_ts = to_timestamp_based_on_day(int(just_started_activity.start_time), timestamp)
        if act_start_ts < timestamp:
            act_start_ts += 86400
        act_end_ts = to_timestamp_based_on_day(int(just_started_activity.end_time), act_start_ts)
        if act_end_ts < act_start_ts:
            act_end_ts += 86400

        _, _time24h = to_24h_timestamp_full(timestamp)
        person.state.scheduling_in_progress = True
        person.state.scheduling_started_at = _time24h
        self._worker_in_progress += 1
        CONTROLLER_SCHEDULING_IN_PROGRESS.set(self._worker_in_progress)
        # Deadline EDF = base de départ du trajet (fin de l'activité en cours) : cette
        # pré-planification act[N+1] est légitimement dépriorisée face à un départ imminent.
        self._dispatch(
            deadline_sim=act_end_ts, kind="plan", person_id=person.person_id,
            make_coro=lambda: self._plan_one(
                person, next_act, act_end_ts,
                from_location_override=just_started_activity.location,
            ),
        )
        return True

    def _refill_precomputed_queue(self, person: Person) -> None:
        """Déclenche le calcul de la prochaine activité au-delà de l'horizon courant.

        Appelé après chaque popleft() sur precomputed_moves pour maintenir la queue
        en horizon glissant 24h. Non-bloquant : lance _precompute_one comme tâche asyncio.
        """
        if person.state.precompute_in_progress:
            return
        horizon_act = person.state.precomputed_horizon_act
        horizon_ts = person.state.precomputed_horizon_ts
        if horizon_act is None or horizon_ts is None:
            return
        activities = person.identity.activities
        if not activities or len(activities) <= 1:
            return
        try:
            curr_idx = next(i for i, a in enumerate(activities) if a.id == horizon_act.id)
        except StopIteration:
            return
        next_idx = (curr_idx + 1) % len(activities)
        next_act = activities[next_idx]
        if next_act.location is None or horizon_act.location is None:
            return
        person.state.precompute_in_progress = True
        # Base de départ du trajet de refill = fin de l'activité d'horizon. Remontée ici
        # (et non calculée dans _precompute_one) pour servir de deadline EDF : un refill
        # lointain (J+1) est naturellement dépriorisé face à une replanification urgente.
        from_act_end_ts = to_timestamp_based_on_day(int(horizon_act.end_time), horizon_ts)
        if from_act_end_ts < horizon_ts:
            from_act_end_ts += 86400
        self._dispatch(
            deadline_sim=from_act_end_ts, kind="refill", person_id=person.person_id,
            make_coro=lambda: self._precompute_one(person, horizon_act, from_act_end_ts, next_act),
        )

    async def _precompute_one(self, person: Person, from_act: Activity, from_act_end_ts: int, to_act: Activity) -> None:
        """Calcule un move de refill (concurrence bornée) et l'appende à precomputed_moves."""
        try:
            async with self._worker_concurrency_guard():
                move, _ = await self._compute_move_for_activity(
                    person, to_act, from_act_end_ts,
                    from_location_override=from_act.location,
                )
            if move:
                person.state.precomputed_moves.append(move)
                person.state.precomputed_horizon_act = to_act
                person.state.precomputed_horizon_ts = move.expected_arrive_at
            else:
                logger.debug(f"[refill] No move for {person.person_id}/{to_act.purpose}")
        except Exception as e:
            logger.debug(f"[refill] Error for {person.person_id}/{to_act.purpose}: {e}")
        finally:
            person.state.precompute_in_progress = False
            self._mark_completion()

    def _try_schedule_person(self, person: Person, timestamp: int) -> bool:
        """Tente de planifier un agent de façon atomique (pas d'await).

        Vérifie les conditions d'éligibilité, réserve le slot (scheduling_in_progress)
        et lance _plan_one comme tâche asyncio. Retourne True si une tâche a été lancée.
        Appelé O(1) à chaque arrivée depuis handle_observation et sync.
        """
        if (
            person.state.heading_to is not None
            or person.state.scheduling_in_progress
            or person.state.next_planned_move is not None
        ):
            return False

        sched = self.population.get_person_default_scheduler(person)
        next_act = sched.next_upcoming_activity(timestamp)
        if next_act is None:
            return False

        _loc = person.state.last_location
        if (
            _loc is not None and next_act.location is not None
            and _loc.lat == next_act.location.lat
            and _loc.lon == next_act.location.lon
        ):
            return False

        _, _time24h = to_24h_timestamp_full(timestamp)
        person.state.scheduling_in_progress = True
        person.state.scheduling_started_at = _time24h
        self._worker_in_progress += 1
        CONTROLLER_SCHEDULING_IN_PROGRESS.set(self._worker_in_progress)
        # Deadline EDF = timestamp courant (le départ est dû maintenant → urgent).
        self._dispatch(
            deadline_sim=timestamp, kind="plan", person_id=person.person_id,
            make_coro=lambda: self._plan_one(person, next_act, timestamp),
        )
        return True

    async def _scan_and_plan_all_idle(self) -> None:
        """Scan de sécurité (toutes les 30s) : détecte les états anormaux et les corrige.

        État nominal : tout agent en déplacement a son act[N+1] dans next_planned_move.
        État anormal :
          - Agent Idle sans next_planned_move ni scheduling_in_progress → WARNING + planifie
          - Agent en déplacement sans next_planned_move ni scheduling_in_progress → WARNING + pré-planifie N+1
        """
        timestamp = self._current_sim_timestamp
        if timestamp == 0 or self._worker_sem is None:
            return

        _, _time24h = to_24h_timestamp_full(timestamp)
        all_people = self.population.get_people_list()

        idle_fallback: list[tuple[Person, Activity]] = []
        idle_precomputed: list[Person] = []
        moving_fallback_count = 0
        _watchdog_s = int(settings.world.arrival_watchdog_hours * 3600)

        for person in all_people:
            is_idle = person.state.heading_to is None
            has_plan = person.state.next_planned_move is not None
            in_progress = person.state.scheduling_in_progress

            # Watchdog arrivées perdues : l'agent est "en déplacement" côté Python mais
            # l'échéance d'arrivée du move poussé est dépassée depuis plus que la marge.
            # L'observation d'arrivée ne viendra jamais (move perdu dans une coupure
            # WebSocket, jamais reçu par GAMA) : sans reprise forcée, l'agent resterait
            # inactif pour toujours, invisible de la pile et du drainage.
            if (
                not is_idle
                and _watchdog_s > 0
                and person.state.heading_expected_arrive_at is not None
                and timestamp > person.state.heading_expected_arrive_at + _watchdog_s
            ):
                _overdue = timestamp - person.state.heading_expected_arrive_at
                fire_alarme("arrivee_perdue")
                logger.error(
                    f"[ALARME] Arrivée perdue — person={person.person_id} "
                    f"heading_to={person.state.heading_to} arrivée attendue à "
                    f"{humanize_date(person.state.heading_expected_arrive_at)} "
                    f"(dépassée de {humanize_duration(_overdue)}) : move jamais reçu par "
                    f"GAMA ? Reprise forcée du cycle de l'agent."
                )
                LOST_ARRIVALS_RECOVERED.inc()
                self.population.get_person_default_scheduler(person).finish_activity()
                person.state.heading_expected_arrive_at = None
                # L'agent est maintenant Idle : les branches ci-dessous le remettent dans
                # le circuit (re-push du plan en main ou replanification).
                is_idle = True

            if is_idle and has_plan and not in_progress:
                # Push précédemment échoué (rollback WebSocket) : l'agent est Idle avec
                # un plan jamais envoyé — hors de ce cas, l'état Idle+Planned n'existe
                # que de façon transitoire à l'intérieur d'une même coroutine.
                logger.warning(
                    f"[worker] ANOMALIE push — person={person.person_id} "
                    f"Idle avec plan non envoyé → nouvelle tentative d'envoi"
                )
                idle_precomputed.append(person)

            elif is_idle and not has_plan and not in_progress:
                # Consommer d'abord la queue pré-calculée (évite un recalcul inutile)
                if person.state.precomputed_moves:
                    person.state.next_planned_move = person.state.precomputed_moves.popleft()
                    self._refill_precomputed_queue(person)
                    idle_precomputed.append(person)
                    continue

                # Cas anormal : agent Idle sans aucun plan
                sched = self.population.get_person_default_scheduler(person)
                next_act = sched.next_upcoming_activity(timestamp)
                if next_act is None:
                    continue
                _loc = person.state.last_location
                if (
                    _loc is not None and next_act.location is not None
                    and _loc.lat == next_act.location.lat
                    and _loc.lon == next_act.location.lon
                ):
                    continue
                logger.warning(
                    f"[worker] ANOMALIE idle — person={person.person_id} "
                    f"Idle sans plan → planification de secours pour {next_act.purpose}"
                )
                person.state.scheduling_in_progress = True
                person.state.scheduling_started_at = _time24h
                self._worker_in_progress += 1
                idle_fallback.append((person, next_act))

            elif not is_idle and not has_plan and not in_progress:
                # Cas anormal : agent en déplacement sans act[N+1] pré-planifié
                current_act = person.state.cache_current_activity
                if current_act is not None:
                    logger.warning(
                        f"[worker] ANOMALIE moving — person={person.person_id} "
                        f"en route vers {person.state.heading_to} sans act[N+1] → pré-planification"
                    )
                    self._try_schedule_next_after(person, current_act, timestamp)
                    moving_fallback_count += 1

            # Détection refill silencieusement échoué : horizon défini, queue vide, pas de tâche en vol.
            if (person.state.precomputed_horizon_act is not None
                    and not person.state.precomputed_moves
                    and not person.state.precompute_in_progress):
                logger.warning(
                    f"[worker] ANOMALIE refill — person={person.person_id} "
                    f"horizon défini mais queue vide → refill forcé"
                )
                self._refill_precomputed_queue(person)

        for person in idle_precomputed:
            # Push d'un move déjà calculé : deadline 0 = toujours prioritaire.
            self._dispatch(
                deadline_sim=0.0, kind="push", person_id=person.person_id,
                make_coro=lambda _p=person: self._push_planned_move(_p),
            )

        if not idle_fallback and moving_fallback_count == 0:
            return

        if idle_fallback:
            CONTROLLER_SCHEDULING_IN_PROGRESS.set(self._worker_in_progress)
            for person, activity in idle_fallback:
                # Planification de secours : deadline = timestamp (départ dû maintenant).
                self._dispatch(
                    deadline_sim=timestamp, kind="plan", person_id=person.person_id,
                    make_coro=lambda _p=person, _a=activity: self._plan_one(_p, _a, timestamp),
                )

    async def _plan_one(self, person: Person, activity: Activity, timestamp: int, from_location_override: Optional[Location] = None) -> None:
        """Calcule le trajet d'un agent (concurrence bornée par EDF ou par le sémaphore)."""
        async with self._worker_concurrency_guard():
            try:
                await self._compute_and_store_planned(person, activity, timestamp, from_location_override=from_location_override)
            except Exception as e:
                logger.error(f"[worker] Error for {person.person_id}: {e}")
                person.state.scheduling_in_progress = False
                person.state.scheduling_started_at = None
            finally:
                self._worker_in_progress -= 1
                CONTROLLER_SCHEDULING_IN_PROGRESS.set(self._worker_in_progress)
                self._mark_completion()

    async def _compute_and_store_planned(self, person: Person, activity: Activity, timestamp: int, from_location_override: Optional[Location] = None) -> None:
        """Calcule le trajet, le stocke comme Planned, puis push si l'agent est IDLE (Point 1)."""
        _pl = PipelineLogger.get()
        _pipeline_rec = _pl.begin(person.person_id, timestamp) if (_pl is not None and person.is_llm_based) else None
        _dispatched_act: Optional[Activity] = None
        try:
            PROCESS_PERSON_CALLS.inc()
            move, _ = await self._compute_move_for_activity(person, activity, timestamp, from_location_override=from_location_override, _pipeline_rec=_pipeline_rec)

            if move:
                if move.expected_arrive_at < timestamp:
                    _, _time24h = to_24h_timestamp_full(timestamp)
                    _late_s = timestamp - move.expected_arrive_at
                    self._late_count += 1
                    PLANNING_LATE.inc()
                    AGENT_LATE_DEPARTURE.observe(_late_s)
                    logger.warning(
                        f"[worker] LATE — person={person.person_id} activity={activity.purpose} "
                        f"scheduled={humanize_time(activity.start_time)} "
                        f"sim_time={humanize_time(_time24h)} late={humanize_duration(_late_s)}"
                    )

                self._itinerary_success_count += 1
                if self._itinerary_success_count >= 100:
                    ITINERARY_100_COMPLETION.set(time.monotonic() - self._itinerary_window_start)
                    self._itinerary_success_count = 0
                    self._itinerary_window_start = time.monotonic()

                _, _send_time24h = to_24h_timestamp_full(timestamp)
                _target_24h = (activity.scheduled_start_time or activity.start_time) % 86400
                # Delta normalisé dans [-43200, +43200] : gère le wrap minuit (un envoi à
                # 00:05 pour une cible 23:55 vaut +600 s, pas -85 800 s).
                _lag_s = ((_send_time24h - _target_24h + 43200) % 86400) - 43200
                AGENT_SCHEDULING_LAG.observe(_lag_s)
                if not self._in_bootstrap:
                    if _lag_s > LATE_DEPARTURE_TOLERANCE_S:
                        DEPARTURE_PUNCTUALITY.labels(status='late').inc()
                        DEPARTURE_DELAY.observe(_lag_s)
                        if _lag_s > self._max_departure_delay_s:
                            self._max_departure_delay_s = float(_lag_s)
                            DEPARTURE_DELAY_MAX.set(_lag_s)
                    else:
                        DEPARTURE_PUNCTUALITY.labels(status='on_time').inc()

                # Stocker comme Planned
                person.state.next_planned_move = move

                # Point 1 : l'agent est IDLE → push immédiat
                pushed = await self._push_planned_move(person)
                if pushed:
                    _dispatched_act = move.for_activity
            else:
                logger.warning(f"[worker] No move computed for {person.person_id}")
        finally:
            person.state.scheduling_in_progress = False
            person.state.scheduling_started_at = None

        # Planifier act[N+1] APRÈS le finally pour que scheduling_in_progress=False soit visible.
        # À l'intérieur du try, scheduling_in_progress=True bloque _try_schedule_next_after ;
        # la même logique s'applique ici que dans _bootstrap_one (ligne ~754).
        if _dispatched_act is not None and person.state.heading_to is not None:
            self._try_schedule_next_after(person, _dispatched_act, self._current_sim_timestamp)

    # -------------------------------------------------------------------------
    # Push WebSocket direct (idempotent)
    # -------------------------------------------------------------------------

    async def _push_planned_move(self, person: Person) -> bool:
        """Push the pre-computed planned move to GAMA if agent is IDLE.

        Idempotent: only executes when heading_to is None AND next_planned_move is set.
        Since asyncio is single-threaded, the check+set below is atomic w.r.t. other
        coroutines: no two concurrent calls can both pass the guard.
        """
        move = person.state.next_planned_move
        if move is None or person.state.heading_to is not None:
            return False

        # Réservation atomique avant tout await
        person.state.next_planned_move = None
        activity = move.for_activity
        if activity:
            self.population.get_person_default_scheduler(person).start_on_activity(activity=activity)

        if self._push_fn:
            action = Action(
                person_id=person.person_id,
                action=move.model_dump(exclude_none=False)
            )
            ACTIONS_CREATED.inc()
            _record_trip_mode(move, activity)
            _pl = PipelineLogger.get()
            if _pl is not None and person.is_llm_based:
                _pl.mark_enqueued(person.person_id)
            # send_message avale les exceptions d'envoi et retourne False (socket morte,
            # reconnexion en cours, "not connected") : le retour doit être vérifié au
            # même titre qu'une exception, sinon le push perdu passe pour un succès et
            # l'agent devient un zombie (GAMA n'a jamais reçu le trajet, Python attend
            # une arrivée qui ne viendra jamais — cf. run 2026-07-08, coupures WS 1006).
            delivered = False
            try:
                delivered = (await self._push_fn(action)) is not False
            except Exception as e:
                logger.error(f"[push] WebSocket send failed for {person.person_id}: {e}")
            if not delivered:
                logger.error(
                    f"[push] Envoi non délivré pour {person.person_id} "
                    f"(WebSocket indisponible) — rollback, le scan retentera le push"
                )
                # Rollback complet : agent remis en IDLE et move restauré tel quel —
                # le trajet déjà calculé (LLM + OTP) n'est pas perdu, le scan de fallback
                # retentera simplement le push (état Idle + plan présent).
                person.state.heading_to = None
                person.state.cache_current_activity = None
                person.state.next_planned_move = move
                return False
            logger.info(
                f"[push] {person.person_id} → {activity.purpose if activity else '?'}"
            )
            if _pl is not None and person.is_llm_based:
                _pl.complete(person.person_id)

        # Armement du watchdog d'arrivée : si le temps sim dépasse cette échéance
        # d'une marge, l'arrivée est considérée perdue et le scan force la reprise.
        person.state.heading_expected_arrive_at = move.expected_arrive_at

        # Charger le prochain move depuis la queue pré-calculée si disponible et déclencher
        # le refill horizon glissant ; sinon calcul réactif à la volée.
        if activity is not None:
            if person.state.precomputed_moves:
                person.state.next_planned_move = person.state.precomputed_moves.popleft()
                self._refill_precomputed_queue(person)
            else:
                self._try_schedule_next_after(person, activity, self._current_sim_timestamp)

        return True

    # -------------------------------------------------------------------------
    # BaseScenario interface
    # -------------------------------------------------------------------------

    @property
    def population(self) -> "WorldPopulation":
        return self.model.population

    @property
    def world_bbox(self) -> BBox:
        return self.model.bbox

    async def _write_population_checkpoint(self, checkpoint_ts: int) -> None:
        date_str = datetime.datetime.fromtimestamp(checkpoint_ts).strftime("%Y-%m-%d")
        fname = f"population_{settings.data.population_size}_checkpoint_{date_str}.json"
        path = str(settings.workdir / fname)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.population.dump_population_snapshot, path)

    async def sync(self, timestamp: int, _t_sync: float | None = None, _t_parse: float | None = None):
        _sync_start = time.monotonic()
        all_people = self.population.get_people_list()
        currently_idle = [p for p in all_people if p.state.heading_to is None]
        currently_moving = [p for p in all_people if p.state.heading_to is not None]
        n_planned = sum(1 for p in all_people if p.state.next_planned_move is not None)
        n_sched_in_progress = sum(1 for p in all_people if p.state.scheduling_in_progress)
        n_unscheduled_idle = sum(
            1 for p in currently_idle
            if not p.state.scheduling_in_progress and p.state.next_planned_move is None
        )
        logger.info(
            f"[sync] START sim_time={humanize_date(timestamp)} "
            f"total_people={len(all_people)} idle={len(currently_idle)} moving={len(currently_moving)} "
            f"planned={n_planned} sched_in_progress={n_sched_in_progress} unscheduled_idle={n_unscheduled_idle} "
            f"late_since_last_sync={self._late_count}"
        )
        logger.info(f"[cache] {_format_cache_hit_rates()}")
        self._late_count = 0

        # Avancer le timestamp de référence du Worker
        self._current_sim_timestamp = timestamp

        # Suivi temporel : heure réelle à chaque tranche de 24h de temps simulé écoulé.
        # Ancré sur le premier timestamp observé (et non sur le calendrier) pour mesurer
        # le débit réel de la simu (combien de temps réel = 24h simulées).
        if self._sim_start_ts is None:
            self._sim_start_ts = timestamp
            self._sim_real_start = time.monotonic()
            self._next_day_log_at = timestamp + 86400
        elif timestamp >= self._next_day_log_at:
            sim_day = (timestamp - self._sim_start_ts) // 86400 + 1
            real_elapsed = int(time.monotonic() - self._sim_real_start)
            logger.info(format_sim_timing(
                "SIM_DAY",
                sim_day=sim_day,
                sim_time=humanize_date(timestamp),
                real_elapsed=humanize_duration(real_elapsed),
            ))
            self._next_day_log_at += 86400

        # Population checkpoint — une fois par jour de simulation à 2h du matin
        if self._next_population_checkpoint_at is None:
            self._next_population_checkpoint_at = _next_checkpoint_ts(timestamp)
        elif timestamp >= self._next_population_checkpoint_at:
            self._spawn(self._write_population_checkpoint(self._next_population_checkpoint_at))
            self._next_population_checkpoint_at += 86400

        # --- Phase 2 : réflexion STM déclenchée par volume d'entrées ---
        # Chaque réflexion part en file EDF (kind "reflect") avec une échéance sim de
        # +stm_reflection_deadline_sim_s : servie quand il y a du mou, priorisée à
        # l'approche de l'échéance, comptée par la contre-pression prédictive. En cas
        # d'échec gateway, les entrées STM restent en place → re-soumission au sync
        # suivant avec la deadline d'ORIGINE (_stm_reflect_due), jamais repoussée.
        if settings.agent.long_term_memory_enabled and settings.agent.stm_reflection_min_entries > 0:
            people_to_reflect = [
                p for p in all_people
                if p.is_llm_based
                and p.person_id not in self._stm_reflecting
                and len(self.agent.get_short_term_memory(p.person_id).recent_entries) >= settings.agent.stm_reflection_min_entries
            ]
            if people_to_reflect:
                logger.info(f"[timestamp: {humanize_date(timestamp)}] STM reflection for {len(people_to_reflect)} agents (>= {settings.agent.stm_reflection_min_entries} entries)")
                _default_due = timestamp + settings.agent.stm_reflection_deadline_sim_s
                for _p in people_to_reflect:
                    self._stm_reflecting.add(_p.person_id)
                    _due = self._stm_reflect_due.setdefault(_p.person_id, _default_due)

                    def _make_reflect_coro(_person=_p, _ts=timestamp):
                        async def _reflect_one():
                            try:
                                await self.agent.trigger_short_term_reflection_for_all_people(timestamp=_ts, people=[_person])
                                _mem = self.agent.get_short_term_memory(_person.person_id)
                                if len(_mem.recent_entries) < settings.agent.stm_reflection_min_entries:
                                    # Lot consommé → réflexion aboutie, l'échéance est levée.
                                    self._stm_reflect_due.pop(_person.person_id, None)
                            finally:
                                self._stm_reflecting.discard(_person.person_id)
                        return _reflect_one()

                    self._dispatch(_due, "reflect", _make_reflect_coro, _p.person_id)

            # Alarme (front montant) : réflexions toujours pendantes au-delà de leur
            # échéance simulée — la garantie « réflexion < 12h sim » n'est plus tenue.
            _overdue = sum(1 for _d in self._stm_reflect_due.values() if timestamp > _d)
            if _overdue and not self._stm_overdue_alarm_on:
                logger.error(
                    f"[ALARME] {_overdue} réflexion(s) STM au-delà de l'échéance de "
                    f"{settings.agent.stm_reflection_deadline_sim_s / 3600:.0f}h simulées — "
                    f"file EDF surchargée ou providers saturés (voir make capacity)"
                )
                self._stm_overdue_alarm_on = True
            elif _overdue == 0:
                self._stm_overdue_alarm_on = False

        if settings.agent.long_term_self_reflect_enabled:
            if not self.next_self_reflection_at:
                self.next_self_reflection_at = timestamp + settings.agent.long_term_self_reflect_interval_days*24*3600
            elif timestamp >= self.next_self_reflection_at:
                logger.info(f"[timestamp: {humanize_date(timestamp)}] Self reflecting the state of the world")
                _duration_days = settings.agent.long_term_self_reflect_window_days
                from_date = datetime.datetime.fromtimestamp(timestamp) - datetime.timedelta(days=_duration_days)
                from_date = from_date.replace(hour=0, minute=0, second=0, microsecond=0)
                self.next_self_reflection_at = timestamp + settings.agent.long_term_self_reflect_interval_days*24*3600
                self._spawn(self.agent.trigger_long_term_reflection_for_all_people(timestamp=timestamp, from_date=from_date, people=self.population.get_people_list()))

        _sync_duration = time.monotonic() - _sync_start
        logger.info(
            f"[sync] END sim_time={humanize_date(timestamp)} "
            f"state_update_duration={_sync_duration:.3f}s worker_backlog={self.worker_in_progress_count}"
        )

    async def trigger_short_term_reflection_for_all(self, timestamp: int):
        people = [p for p in self.population.get_people_list() if p.is_llm_based]

        sem = asyncio.Semaphore(100)

        async def reflect_person(person):
            async with sem:
                await self.agent.trigger_short_term_reflection_for_all_people(timestamp=timestamp, people=[person])

        tasks = [reflect_person(person) for person in people]
        await asyncio.gather(*tasks)

    async def trigger_long_term_reflection_for_all(self, timestamp: int):
        people = self.population.get_people_list()

        sem = asyncio.Semaphore(50)

        async def self_reflect_person(person):
            async with sem:
                await self.agent.reflect_on_long_term_memory(timestamp=timestamp, people=[person])

        tasks = [self_reflect_person(person) for person in people]
        await asyncio.gather(*tasks)

    async def handle_observation(self, observation: Observation):
        """Handle observation data.

        Pour une arrivée : finish_activity, push si Planned (Point 2), et réveille
        le Worker pour qu'il planifie immédiatement l'activité suivante.
        """
        person = self.population.get_person(observation.person_id)
        if not person:
            logger.warning(f"[timestamp: {humanize_date(observation.timestamp)}] Person {observation.person_id} not found in population")
            return
        person.state.last_location = observation.location
        on_purpose = person.state.heading_to

        ob_text = env_ob_to_text(
            code=observation.env_ob_code,
            ob=observation.data,
            purpose=on_purpose,
            weather=get_weather(observation.timestamp),
        )

        if observation.env_ob_code in ("arrival", "tc_timeout"):
            _started_at = observation.data.get("started_at")
            _schedule_at = observation.data.get("schedule_at")
            _timed_out = observation.env_ob_code == "tc_timeout"
            await GamaArrivalsLogger.get_instance().log_arrival(
                move_id=str(observation.data.get("moving_id", "")),
                person_id=observation.person_id,
                arrive_at=int(observation.data.get("arrive_at", observation.timestamp)),
                expected_arrive_at=int(observation.data.get("expected_arrive_at", observation.timestamp)),
                started_at=int(_started_at) if _started_at is not None else None,
                schedule_at=int(_schedule_at) if _schedule_at is not None else None,
                timed_out=_timed_out,
            )
            if observation.env_ob_code == "arrival" and person.state.cache_current_activity:
                activity = person.state.cache_current_activity
                ob = parse_ob(code=observation.env_ob_code, ob=observation.data)
                if settings.agent.reschedule_activity_departure_time:
                    duration = self.reschedule_amount_function(arrival_late_seconds=ob.late)
                    self.population.get_person_default_scheduler(person).reschedule_activity(activity, duration)
                    _context = Context(
                        person=person,
                        activity_id=observation.activity_id,
                        timestamp=observation.timestamp,
                        data={
                            "location": observation.location.model_dump(exclude_none=True),
                            "heading_to": person.state.heading_to,
                            "data": observation.data,
                        }
                    )
                    self.agent.add_short_term_memory(
                        context=_context,
                        msg=f"Because you arrived late, you adjusted your target arrival time for {activity.purpose}. You will now aim to arrive at {humanize_time(activity.scheduled_start_time)}, which is {humanize_duration(activity.start_time - activity.scheduled_start_time)} earlier than originally planned.",
                        timestamp=observation.timestamp
                    )

            # Transition ACTIVE → IDLE
            self.population.get_person_default_scheduler(person).finish_activity()
            person.state.heading_expected_arrive_at = None  # désarme le watchdog d'arrivée

            # Mettre à jour le timestamp de référence
            self._current_sim_timestamp = max(self._current_sim_timestamp, observation.timestamp)

            # Point 2 : si le trajet suivant est déjà Planned, push immédiat
            pushed = await self._push_planned_move(person)

            # Chemin rapide O(1) : planifier directement cet agent sans scan global
            if not pushed:
                self._try_schedule_person(person, self._current_sim_timestamp)

        _context = Context(
            person=person,
            activity_id=observation.activity_id,
            timestamp=observation.timestamp,
            data={
                "location": observation.location.model_dump(exclude_none=True),
                "heading_to": person.state.heading_to,
                "data": observation.data,
            }
        )
        self.agent.add_short_term_memory(
            context=_context,
            msg=ob_text,
            timestamp=observation.timestamp
        )

    def reschedule_amount(self, arrival_late_seconds: int) -> int:
        if arrival_late_seconds <= 0:
            return 0
        amount = min(int(abs(arrival_late_seconds) * settings.agent.reschedule_transition_ratio), self.MAX_ADJUST_START_TIME)
        amount = amount if arrival_late_seconds > 0 else -amount
        return amount

    def reschedule_amount_v2(self, arrival_late_seconds: int) -> int:
        if arrival_late_seconds <= 0:
            return 0
        k = settings.agent.reschedule_activity_v2__k or 0.02
        arrival_late_minutes = arrival_late_seconds / 60.0
        amount = min(k * arrival_late_minutes * arrival_late_minutes * 60, self.MAX_ADJUST_START_TIME)
        amount = int(amount) if arrival_late_seconds > 0 else -int(amount)
        return amount

    async def has_messages(self) -> bool:
        return len(self._messages) > 0

    async def pop_all_messages(self) -> list[Action]:
        messages = self._messages.copy()
        self._messages.clear()
        return messages

    async def bootstrap_all_agents(self, timestamp: int):
        """Pre-compute the first upcoming itinerary for every agent.

        Called from /init so GAMA's reflex init blocks on the HTTP response until
        every OTP query is done. Affiche une barre de progression rich dans la console.
        Les trajets sont stockés dans _messages (publish_loop les envoie après /init).
        """
        import sys
        from rich.console import Console as RichConsole
        from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn, MofNCompleteColumn, SpinnerColumn

        # Initialiser le timestamp de référence du Worker dès le bootstrap
        self._current_sim_timestamp = timestamp

        # Marque la phase bootstrap : ACTIVITY_DECISIONS tag phase=bootstrap, cockpit ③
        # n'y compte aucune activité ratée. Réinitialise les jauges d'avancement (cockpit ①).
        self._in_bootstrap = True
        BOOTSTRAP_ACTIVE.set(1)
        BOOTSTRAP_COMPLETED.set(0)
        BOOTSTRAP_PROGRESS.set(0)
        BOOTSTRAP_CACHE_HITS.set(0)
        BOOTSTRAP_CACHE_MISSES.set(0)
        BOOTSTRAP_WAVE.set(1)
        BOOTSTRAP_FUTURE_MOVES.set(0)
        BOOTSTRAP_WAVE_MOVES.clear()  # purge les vagues d'un éventuel /init précédent

        all_people = self.population.get_people_list()
        _, _time24h = to_24h_timestamp_full(timestamp)

        eligible: list[tuple[Person, Activity]] = []
        for person in all_people:
            if person.state.heading_to is not None or person.state.scheduling_in_progress:
                continue
            sched = self.population.get_person_default_scheduler(person)
            next_act = sched.next_upcoming_activity(timestamp)
            if next_act is None:
                continue
            person.state.scheduling_in_progress = True
            person.state.scheduling_started_at = _time24h
            eligible.append((person, next_act))

        total = len(eligible)
        BOOTSTRAP_TOTAL.set(total)
        _w1 = _wave_metrics(1, total)
        logger.info(
            f"[bootstrap] sim_time={humanize_date(timestamp)} "
            f"computing itineraries for {total}/{len(all_people)} agents — GAMA blocked"
        )
        _bootstrap_start = time.monotonic()

        # Console dédiée sur stderr, force_terminal=True pour affichage dans VSCode
        # même quand stdout est capturé par uvicorn/hypercorn.
        # Loguru écrit sur stdout → pas d'interférence.
        _rich_console = RichConsole(
            stderr=True,
            force_terminal=True,
            highlight=False,
        )
        _rich_console.print(
            f"\n[bold cyan]Bootstrap :[/bold cyan] calcul de {total} itinéraires initiaux…\n"
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan][bootstrap][/bold cyan]"),
            BarColumn(bar_width=40),
            MofNCompleteColumn(),
            TextColumn("agents planifiés"),
            TimeElapsedColumn(),
            console=_rich_console,
            refresh_per_second=4,
            transient=False,
        ) as progress:
            task_id = progress.add_task("bootstrap", total=total)
            _cache_stats = {"hits": 0, "misses": 0, "done": 0}

            # Lissage de la rafale : borne les pipelines OTP+LLM en vol (cf.
            # settings.world.bootstrap_concurrency) pour ne pas saturer les quotas
            # provider au /init. Les tâches sont toutes créées d'un coup mais
            # n'entrent dans le calcul que par vagues au fil des libérations.
            _boot_sem = asyncio.Semaphore(max(1, settings.world.bootstrap_concurrency))

            async def _bootstrap_one(person: Person, act: Activity):
                _dispatched_act = None
                try:
                    _pl = PipelineLogger.get()
                    _pipeline_rec = _pl.begin(person.person_id, timestamp) if (_pl is not None and person.is_llm_based) else None
                    PROCESS_PERSON_CALLS.inc()
                    async with _boot_sem:
                        move, _reason = await self._compute_move_for_activity(person, act, timestamp, _pipeline_rec=_pipeline_rec)
                    if "cache sémantique" in (_reason or ""):
                        _cache_stats["hits"] += 1
                        BOOTSTRAP_CACHE_HITS.set(_cache_stats["hits"])
                        _w1["cache_hit"].inc()
                        logger.info(f"[bootstrap] cache hit — {person.person_id} / {act.purpose}")
                    elif person.is_llm_based:
                        _cache_stats["misses"] += 1
                        BOOTSTRAP_CACHE_MISSES.set(_cache_stats["misses"])
                        _w1["cache_miss"].inc()
                        logger.info(f"[bootstrap] cache miss — {person.person_id} / {act.purpose}")
                    if move:
                        _w1["ok"].inc()
                        self._itinerary_success_count += 1
                        if self._itinerary_success_count >= 100:
                            ITINERARY_100_COMPLETION.set(time.monotonic() - self._itinerary_window_start)
                            self._itinerary_success_count = 0
                            self._itinerary_window_start = time.monotonic()
                        ACTIONS_CREATED.inc()
                        _record_trip_mode(move, act)
                        # Chemin bootstrap : push via _messages (publish_loop après /init)
                        self._messages.append(Action(
                            person_id=person.person_id,
                            action=move.model_dump(exclude_none=False)
                        ))
                        self.population.get_person_default_scheduler(person).start_on_activity(activity=act)
                        if _pl is not None and person.is_llm_based:
                            _pl.mark_enqueued(person.person_id)
                        _dispatched_act = act
                except Exception as _e:
                    logger.debug(f"[bootstrap] Error for {person.person_id}/{act.purpose}: {_e}")
                finally:
                    person.state.scheduling_in_progress = False
                    person.state.scheduling_started_at = None
                    progress.advance(task_id, 1)
                    _cache_stats["done"] += 1
                    BOOTSTRAP_COMPLETED.set(_cache_stats["done"])
                    _w1["done"].inc()
                    if total:
                        BOOTSTRAP_PROGRESS.set(_cache_stats["done"] / total)
                # Pré-planifier act[N+1] avec act[N].location comme origin dès la fin du bootstrap
                if _dispatched_act is not None:
                    self._try_schedule_next_after(person, _dispatched_act, timestamp)

            tasks = [asyncio.create_task(_bootstrap_one(person, act)) for person, act in eligible]
            completed = 0
            log_interval = max(1, total // 10)
            for coro in asyncio.as_completed(tasks):
                try:
                    await coro
                except Exception:
                    pass
                completed += 1
                if completed % log_interval == 0 or completed == total:
                    _llm_total = _cache_stats["hits"] + _cache_stats["misses"]
                    _hit_pct = int(100 * _cache_stats["hits"] / _llm_total) if _llm_total else 0
                    logger.info(
                        f"[bootstrap] progress {completed}/{total} ({100*completed//total}%) "
                        f"— cache hits: {_cache_stats['hits']}/{_llm_total} ({_hit_pct}%)"
                    )

        # Attendre que tous les act[N+1] lancés par _try_schedule_next_after soient calculés
        # avant de retourner, pour que GAMA démarre sans backpressure au premier /sync.
        if self._worker_in_progress > 0:
            logger.info(f"[bootstrap] waiting for {self._worker_in_progress} act[N+1] pre-planning tasks...")
            while self._worker_in_progress > 0:
                await asyncio.sleep(0.5)

        # Pré-calculer act[N+2], act[N+3], ... pour chaque agent et les stocker dans
        # precomputed_moves. Cela évite le pic de planification pendant les heures de pointe
        # du matin (100+ agents arrivant simultanément qui déclenchent tous un calcul OTP).
        # Track the full Unix arrival timestamp for the last planned activity per person.
        # This is needed so each wave can compute the correct calendar day for the
        # following activity: act[N+2] must depart AFTER act[N+1] ends, not on the
        # simulation start day.
        person_last_planned_act: dict[str, Activity] = {}
        person_last_planned_ts: dict[str, int] = {}
        for person, act_N in eligible:
            move = person.state.next_planned_move
            if move and move.for_activity:
                person_last_planned_act[person.person_id] = move.for_activity
                person_last_planned_ts[person.person_id] = move.expected_arrive_at

        async def _compute_future_wave_move(
            person: Person,
            from_act: Activity,
            from_arrive_ts: int,
            to_act: Activity,
            wm: dict,
        ) -> None:
            """Calcule un trajet de vague bootstrap sous le sémaphore de concurrence.

            `wm` : compteurs agent_bootstrap_wave_moves de la vague (cf. _wave_metrics).
            """
            try:
                # Compute when from_act ends: its end_time is a 24h offset, and may
                # be on the next calendar day relative to when the person arrives.
                from_act_end_ts = to_timestamp_based_on_day(int(from_act.end_time), from_arrive_ts)
                if from_act_end_ts < from_arrive_ts:
                    from_act_end_ts += 86400
                async with self._worker_sem:
                    move, _reason = await self._compute_move_for_activity(
                        person, to_act, from_act_end_ts,
                        from_location_override=from_act.location,
                    )
                if "cache sémantique" in (_reason or ""):
                    wm["cache_hit"].inc()
                elif person.is_llm_based:
                    wm["cache_miss"].inc()
                if move:
                    wm["ok"].inc()
                    person.state.precomputed_moves.append(move)
                    person_last_planned_act[person.person_id] = to_act
                    person_last_planned_ts[person.person_id] = move.expected_arrive_at
                else:
                    person_last_planned_act.pop(person.person_id, None)
                    person_last_planned_ts.pop(person.person_id, None)
            except Exception as _e:
                logger.debug(f"[bootstrap/wave] Error for {person.person_id}/{to_act.purpose}: {_e}")
                person_last_planned_act.pop(person.person_id, None)
                person_last_planned_ts.pop(person.person_id, None)
            finally:
                wm["done"].inc()

        wave = 2
        while person_last_planned_act:
            wave_batch: list[tuple[Person, Activity, int, Activity]] = []

            for person, act_N in eligible:
                pid = person.person_id
                last_act = person_last_planned_act.get(pid)
                last_ts = person_last_planned_ts.get(pid)
                if last_act is None or last_ts is None:
                    continue
                activities = person.identity.activities or []
                if len(activities) <= 1:
                    del person_last_planned_act[pid]
                    person_last_planned_ts.pop(pid, None)
                    continue
                curr_idx = next((i for i, a in enumerate(activities) if a.id == last_act.id), None)
                if curr_idx is None:
                    del person_last_planned_act[pid]
                    person_last_planned_ts.pop(pid, None)
                    continue
                next_idx = (curr_idx + 1) % len(activities)
                next_act = activities[next_idx]
                if next_act.id == act_N.id:
                    # Cycle complet : on a couvert toutes les activités de la journée
                    del person_last_planned_act[pid]
                    person_last_planned_ts.pop(pid, None)
                    continue
                wave_batch.append((person, last_act, last_ts, next_act))

            if not wave_batch:
                break

            logger.info(f"[bootstrap] pre-computing {len(wave_batch)} act[N+{wave}] itineraries (wave {wave})...")
            BOOTSTRAP_WAVE.set(wave)
            _wm = _wave_metrics(wave, len(wave_batch))

            wave_tasks = [
                asyncio.create_task(_compute_future_wave_move(p, fa, fa_ts, ta, _wm))
                for p, fa, fa_ts, ta in wave_batch
            ]
            for coro in asyncio.as_completed(wave_tasks):
                try:
                    await coro
                except Exception:
                    pass
                BOOTSTRAP_FUTURE_MOVES.set(sum(len(p.state.precomputed_moves) for p in all_people))

            wave += 1

        # Initialiser l'horizon glissant pour chaque agent à partir des résultats du bootstrap.
        # person_last_planned_act/ts contiennent la dernière activité calculée par les vagues.
        for person, act_N in eligible:
            pid = person.person_id
            last_act = person_last_planned_act.get(pid)
            last_ts = person_last_planned_ts.get(pid)
            if last_act is not None and last_ts is not None:
                person.state.precomputed_horizon_act = last_act
                person.state.precomputed_horizon_ts = last_ts

        n_precomputed = sum(len(p.state.precomputed_moves) for p in all_people)
        logger.info(f"[bootstrap] all activities pre-planning tasks done ({n_precomputed} future moves pre-cached across {wave - 2} additional wave(s))")

        _bootstrap_duration = time.monotonic() - _bootstrap_start
        BOOTSTRAP_DURATION.set(_bootstrap_duration)
        _planned = sum(1 for p in all_people if p.state.heading_to is not None)
        logger.info(f"[bootstrap] done — {total} itineraries computed in {_bootstrap_duration:.2f}s")
        logger.info(f"[cache] {_format_cache_hit_rates()}")
        _rich_console.print(
            f"\n[bold green]✓ Bootstrap terminé[/bold green] — "
            f"[cyan]{_planned}/{total}[/cyan] agents planifiés en "
            f"[yellow]{_bootstrap_duration:.1f}s[/yellow]\n"
        )
        # Fin de phase bootstrap : les décisions suivantes sont live (cockpit ③ compte à partir d'ici).
        self._in_bootstrap = False
        BOOTSTRAP_ACTIVE.set(0)

    # -------------------------------------------------------------------------
    # Trip computation (partagé bootstrap + Worker)
    # -------------------------------------------------------------------------

    async def _compute_move_for_activity(
        self,
        person: Person,
        next_activity: Activity,
        timestamp: int,
        from_location_override: Optional[Location] = None,
        _pipeline_rec=None,
    ) -> Tuple[Optional[PersonMove], Optional[str]]:
        from_location = from_location_override if from_location_override is not None else person.state.last_location

        # scheduled_start_time = departure time from the previous activity toward next_activity.
        # Use it as the trip departure; arrive_by=False (depart at this time).
        target_24h = next_activity.scheduled_start_time if next_activity.scheduled_start_time is not None else next_activity.end_time
        departure_time = to_timestamp_based_on_day(
            target_24h_timestamp=target_24h,
            based_on=timestamp,
        )
        planning_late_s = max(0, timestamp - departure_time)
        if departure_time < timestamp:
            departure_time += 86400  # activité du lendemain (bouclage J+1)
        # Aucun déplacement ne démarre le week-end : un départ samedi/dimanche est
        # reporté au lundi suivant à la même heure. L'itinéraire OTP, expected_arrive_at
        # et le schedule_at côté GAMA découlent tous de departure_time → tout est décalé.
        if settings.agent.no_weekend_departures:
            shifted = shift_weekend_departure_to_monday(departure_time)
            if shifted != departure_time:
                logger.info(
                    f"[weekend] Départ de {person.person_id} pour {next_activity.purpose} "
                    f"reporté de {humanize_date(departure_time)} à {humanize_date(shifted)} (lundi)"
                )
                departure_time = shifted
        include_car = (person.identity.traits_json.get("number_of_cars", 0) > 0)
        include_bike = (person.identity.traits_json.get("personal_bike", "vélo normal").lower() != "pas de vélo")

        same_location = (
            from_location is not None and next_activity.location is not None
            and from_location.lat == next_activity.location.lat
            and from_location.lon == next_activity.location.lon
        )
        if same_location:
            itineraries = []
        else:
            _timing_sink: dict | None = {} if _pipeline_rec is not None else None
            if _pipeline_rec is not None:
                _pipeline_rec.T_otp_start = time.time()
            itineraries = await self.trip_helper.get_itineraries(
                origin=from_location,
                destination=next_activity.location,
                departure_time=departure_time,
                include_car=include_car,
                include_bike=include_bike,
                arrive_by=False,
                _timing_sink=_timing_sink,
            )
            if _pipeline_rec is not None:
                _pipeline_rec.T_otp_end = time.time()
                if _timing_sink:
                    _pipeline_rec.T_transit_sem = _timing_sink.get("transit_sem_end")
                    _pipeline_rec.T_transit_end = _timing_sink.get("transit_end")
                    _pipeline_rec.T_osmnx_sem   = _timing_sink.get("osmnx_sem_end")
                    _pipeline_rec.T_osmnx_end   = _timing_sink.get("osmnx_end")

        if not include_bike:
            itineraries = [it for it in itineraries if _primary_mode(it) != "bike"]

        for itinerary in itineraries:
            itinerary.purpose = next_activity.purpose

        selection_method = "Undefined"
        provider_info = ""
        reasoning = ""
        faster_itinerary = None

        if not itineraries:
            estimated_duration = _estimate_fallback_duration(from_location, next_activity.location)
            if same_location:
                selection_method = "Pas de déplacement (même localisation)"
                logger.debug(
                    f"[timestamp: {humanize_date(timestamp)}] Already at destination for {next_activity.purpose} "
                    f"(lat={from_location.lat:.5f},lon={from_location.lon:.5f}) — using fallback duration"
                )
            else:
                selection_method = "Pas de solution de déplacement"
                bbox = self.world_bbox
                def _in_bbox(loc) -> bool:
                    return (loc is not None and
                            bbox.min_lat <= loc.lat <= bbox.max_lat and
                            bbox.min_lon <= loc.lon <= bbox.max_lon)
                origin_ok = _in_bbox(from_location)
                dest_ok = _in_bbox(next_activity.location)
                logger.warning(
                    f"[timestamp: {humanize_date(timestamp)}] Can't get to destination {next_activity.location} by any transport mode, "
                    f"estimated travel time: {humanize_duration(estimated_duration)} | "
                    f"origin_in_bbox={origin_ok} (lat={from_location.lat:.5f},lon={from_location.lon:.5f}) "
                    f"dest_in_bbox={dest_ok}"
                )
            plan = TravelPlan(
                id=random_uuid(),
                start_location=from_location,
                end_location=next_activity.location,
                start_time=departure_time * 1000,
                end_time=(departure_time + estimated_duration) * 1000,
                purpose=next_activity.purpose,
                legs=[],
            )
            plan_index = 0
            reasoning = "Can't find a suitable public transport plan, walk to the destination anyway"
        else:
            plan_index = 0
            reasoning = "Hard to choice, just pick the first one"

            for itinerary in itineraries:
                if faster_itinerary is None or itinerary.duration < faster_itinerary.duration:
                    faster_itinerary = itinerary

            itineraries = _select_candidates(itineraries, settings.gtfs.max_trip_candidates)

            if len(itineraries) == 1:
                reasoning = "Un seul itinéraire disponible, sélection automatique"
                selection_method = "Un seul itinéraire disponible"
            elif person.is_llm_based and self.agent:
                context = Context(
                    person=person,
                    timestamp=timestamp,
                    activity_id=next_activity.id,
                    data={"type": "travel_plan"},
                )
                EVALUATE_PLAN_CALLS.inc()
                plan_index, reasoning, provider_info = await self.agent.evaluate_and_choose_travel_plan(
                    context=context,
                    options=itineraries,
                    destination=next_activity.purpose,
                    departure_time=departure_time,
                )
                if isinstance(plan_index, int) and 0 <= plan_index < len(itineraries):
                    selection_method = "LLM"
                else:
                    plan_index = 0
                    provider_info = ""
                    selection_method = "LLM Error (Default index)"
                    logger.debug(f"[timestamp: {humanize_date(timestamp)}] No suitable plan found for person {person.person_id} to {next_activity.location}")

            plan: TravelPlan = itineraries[plan_index]
            plan.purpose = next_activity.purpose

        plan_duration_s = max(0, (plan.end_time - plan.start_time) // 1000) if plan is not None else 0
        prepare_before_seconds = max(plan_duration_s, settings.world.time_step)
        # expected_arrive_at = actual arrival time from OTP (departure + trip duration)
        expected_arrive_at = plan.end_time // 1000 if plan is not None else departure_time

        move = PersonMove(
            id=random_uuid(),
            person_id=person.person_id,
            current_time=timestamp,
            expected_arrive_at=expected_arrive_at,
            prepare_before_seconds=prepare_before_seconds,
            purpose=next_activity.purpose,
            target_location=next_activity.location,
            for_activity=next_activity,
            plan=plan,
        )

        if _pipeline_rec is not None:
            _pipeline_rec.plan_selected_index = plan_index
            _pipeline_rec.selection_method = selection_method

        # Issue de la décision → métrique temps réel (suivi des activités dégradées
        # faute de réponse LLM, cf. cockpit ③). Le bootstrap pré-calcule au /init : un
        # fallback n'y est PAS une activité ratée (l'agent partira quand même) → phase séparée.
        ACTIVITY_DECISIONS.labels(
            outcome=_SELECTION_OUTCOME.get(selection_method, "other"),
            phase="bootstrap" if self._in_bootstrap else "live",
        ).inc()

        _weather = get_weather(timestamp)
        await MoveLogger.get_instance().log_move(
            person=person,
            plan=plan,
            purpose=next_activity.purpose,
            selection_method=selection_method,
            provider_model=provider_info or "",
            faster_itinerary=faster_itinerary,
            reasoning=reasoning,
            weather_temp=_weather["temperature"] if _weather else None,
            weather_condition=_weather["weather_label"] if _weather else None,
            weather_precip_mm=_weather["precip_mm"] if _weather else None,
            late_s=planning_late_s,
            move_id=move.id,
            simulated_time=timestamp,
            start_time=plan.start_time if plan is not None else None,
            available_options=itineraries,
            activity_id=next_activity.id,
        )


        return move, reasoning
