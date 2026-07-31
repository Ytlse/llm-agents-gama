"""
FastAPI application for LLM-GAMA integration.

This module provides the HTTP API and WebSocket communication layer between
the GAMA simulation and external LLM (Large Language Model) systems. It handles
world initialization, synchronization, and real-time observation/action exchange.
"""

import asyncio
import csv
import json
import math
import os
import re
import subprocess
import sys
import orjson
import time
from datetime import datetime
from pathlib import Path
import httpx
import numpy as np
import uvicorn
from loguru import logger
from backpressure import compute_backpressure_interval, update_drain_mode, edf_feasibility, time_ewma
from helper import setup_logging, humanize_date, to_timestamp_based_on_day, format_sim_timing
from models import Location
from gama_models import GamaPersonData, MessageResponse, MessageType, WorldInitRequest, WorldInitResponse, WorldSyncRequest
from urban_mobility_agents.core.scenario import BaseScenario, Observation
from handle.websocket import WebSocketClient
from llm_module.telemetry.alarms import fire_alarme
from settings import settings, FactorySettings
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import ORJSONResponse
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST, REGISTRY
from urban_mobility_agents.factory.factory import init_static_data, init_dynamic_scenario
from urban_mobility_agents.utils.pipeline_logger import PipelineLogger
from utils import create_background_task
from geography import TOULOUSE_OSM_ROUTES_30K_BBOX
from population_utils import fix_activities, merge_consecutive_activities, ajuster_planning

# Compteurs des endpoints du contrôleur
SYNC_REQUESTS = Counter('controller_sync_requests_total', 'Total requêtes /sync reçues de GAMA')
INIT_REQUESTS = Counter('controller_init_requests_total', 'Total requêtes /init reçues de GAMA')

# Métriques de la simulation
SIM_AGENTS_TOTAL  = Gauge('gama_sim_agents_total', 'Nombre total d\'agents dans la simulation (défini au /init)')
SIM_STEP_INTERVAL = Gauge('gama_sim_step_interval_seconds', 'Durée réelle entre deux pas de temps GAMA consécutifs (secondes)')
SIM_LOGICAL_TIME  = Gauge('gama_sim_logical_time_seconds', 'Horodatage logique courant de la simulation (timestamp Unix GAMA)')
SIM_REAL_ELAPSED  = Gauge('gama_sim_real_elapsed_seconds', 'Temps réel écoulé depuis le dernier /init (secondes)')
SIM_STEP_COUNT             = Gauge('gama_sim_step_count', 'Numéro du pas de temps courant depuis le /init')
SIM_STEP_LOGICAL_DURATION  = Gauge('gama_sim_step_logical_duration_seconds', 'Durée logique GAMA d\'un pas de temps (écart entre deux timestamps consécutifs en secondes de temps simulé)')
AGENT_STATES               = Gauge('gama_agent_states', 'Nombre d\'agents par état (inactive/ready/active)', ['state'])
SIM_WALL_CLOCK_RATIO       = Gauge('sim_wall_clock_ratio', 'Ratio temps simulé / temps réel entre deux /sync (accélération effective)')

# Cockpit — pilotage temps réel de la simulation
CTRL_BACKPRESSURE_INTERVAL = Gauge('controller_backpressure_interval_seconds', 'Frein backpressure appliqué à la dernière réponse /sync (secondes)')
CTRL_BACKLOG_FILL_RATIO    = Gauge('controller_backlog_fill_ratio', 'Remplissage de la pile : activités à calculer / population (1.0 = pile pleine)')
CTRL_DRAIN_MODE            = Gauge('controller_drain_mode_active', 'Mode drainage actif (1=/sync retenu jusqu\'au vidage de la pile, 0=nominal)')
CTRL_AGENTS_STUCK          = Gauge('controller_agents_stuck', 'Agents sans planification réussie depuis plus que le seuil (heures de simulation)')
CTRL_INIT_STAGE            = Gauge('controller_init_stage', 'Étape courante de l\'init /init: 0=idle,1=prépa population,2=population prête,3=scénario,4=bootstrap itinéraires,5=prêt')
CTRL_INIT_PROGRESS         = Gauge('controller_init_progress_ratio', 'Progression globale de l\'init (0..1 = étape/5)')

# Ticket 003 — ordonnancement EDF et contre-pression prédictive
CTRL_THROUGHPUT            = Gauge('controller_throughput_tasks_per_min', 'Débit de complétion D (EWMA) × 60 — tâches OTP+LLM drainées par minute')
CTRL_T_ESTIMATE           = Gauge('controller_t_estimate_seconds', 'Pire T_k du dernier test de faisabilité EDF (temps réel pour résoudre toute la file)')
CTRL_MIN_SLACK            = Gauge('controller_min_slack_sim_seconds', 'Échéance la plus proche en file − temps sim courant (secondes de temps SIMULÉ)')
CTRL_PREDICTIVE_HOLD      = Gauge('controller_predictive_hold_seconds', 'Rétention prédictive appliquée à la dernière réponse /sync (secondes)')
CTRL_EDF_QUEUE_DEPTH      = Gauge('controller_edf_queue_depth', 'Profondeur de la file EDF (tâches en attente, hors tâches en cours d\'exécution)')
CTRL_SYNC_DURATION        = Histogram(
    'controller_sync_duration_seconds',
    'Durée de traitement d\'une requête /sync (battement de cœur GAMA↔controller)',
    buckets=[0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10],
)
CTRL_DEADLINE_MISSES      = Counter('controller_deadline_misses_total', 'Arrivées planifiées après l\'heure de départ prévue (expected_arrive_at < timestamp) — expose _late_count')

_last_sync_wall_time: float          = 0.0
_last_sync_response_wall_time: float = 0.0   # timestamp of the last /sync response sent
_sim_init_wall_time: float           = 0.0
_sim_step_count: int                 = 0
_last_logical_time: int              = 0
_last_backpressure_in_progress: int  = 0     # in_progress_count used for the previous sync's sleep
_last_backpressure_min_interval: float = 0.0 # min_interval computed for the previous sync's sleep
_backlog_alarm_active: bool          = False # évite de répéter l'alarme backlog à chaque sync (front montant)
_drain_mode_active: bool             = False # mode drainage : /sync retenu tant que la pile n'est pas vidée sous le seuil de relâchement

# Ticket 003 — état du contrôle prédictif (module-level, réinitialisé au /init)
_sim_ratio_ewma: float | None        = None  # R lissé : secondes simulées / seconde réelle (EWMA du SIM_WALL_CLOCK_RATIO)
_sim_ratio_ewma_time: float | None   = None  # instant (wall) du dernier échantillon de R
_throttle_active: bool               = False # régime dégradé notifié à GAMA (topic system/throttle)
_throttle_last_notify_at: float      = 0.0   # dernier envoi (wall) — rafraîchissement périodique sans spam

# eqasim service URL — set via EQASIM_SERVICE_URL env var (default: http://eqasim:8003)
_EQASIM_SERVICE_URL = os.environ.get("EQASIM_SERVICE_URL", "http://eqasim:8003")


async def _trigger_eqasim_generation(population_size: int, bbox: tuple[float, float, float, float] | None = None) -> None:
    """Call the eqasim service to ensure the population JSON is ready.

    Blocks until generation completes (or returns immediately on cache hit).
    Timeout is 30 min to accommodate first-time synpp runs.
    Raises HTTPException on generation failure so /init surfaces the error
    to GAMA rather than crashing later on a missing population file.

    bbox: optional (min_lon, min_lat, max_lon, max_lat) in WGS84 — restricts
    synpp to the communes intersecting this zone so generated profiles stay
    within the simulation area.
    """
    url = f"{_EQASIM_SERVICE_URL}/generate"
    payload: dict = {"population_size": population_size}
    if bbox is not None:
        payload["bbox"] = list(bbox)
    logger.info(f"[eqasim] Triggering population generation via {url} (population_size={population_size}, bbox={bbox})")
    try:
        async with httpx.AsyncClient(timeout=1800.0) as client:
            resp = await client.post(url, json=payload)
            body = resp.json()
            if resp.status_code == 200 and body.get("status") == "ok":
                logger.info(f"[eqasim] Population ready — {body.get('file', '')}")
            else:
                exit_code = body.get("exit_code", "?")
                msg = f"[eqasim] Generation failed (exit_code={exit_code}). Check eqasim container logs (OOM if exit_code=137)."
                logger.error(msg)
                raise HTTPException(status_code=503, detail=msg)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(f"[eqasim] Could not reach eqasim service ({exc}); will attempt to load existing file")


def _find_population_json(population_size: int | None = None) -> str | None:
    """Return the path of the eqasim population JSON for the requested size.

    If population_size is given, looks for the exact file
    ``{prefix}population_{population_size}.json`` and returns None if absent.
    If population_size is None, falls back to the largest available file.
    """
    output_dir = settings.data.eqasim_output_dir
    prefix = settings.data.synthetic_file_prefix
    if population_size is not None:
        exact = os.path.join(output_dir, f"{prefix}population_{population_size}.json")
        return exact if os.path.exists(exact) else None
    pattern = re.compile(rf"^{re.escape(prefix)}population_(\d+)\.json$")
    candidates = [
        (int(m.group(1)), os.path.join(output_dir, name))
        for name in os.listdir(output_dir)
        if (m := pattern.match(name))
    ]
    return max(candidates)[1] if candidates else None


async def _prepare_population(
    population_size: int,
    stop_coords: np.ndarray,
    sim_base_timestamp: int,
    bbox,
) -> str | None:
    """Ensure workdir/population_{N}.json exists, contains exactly N enriched agents.

    The workdir file is written in eqasim format (not Pydantic) so that both the
    OSMnx route cache and world/population.py can consume it.  Writes are atomic
    (.tmp → rename) so a crash mid-write leaves no corrupted file.

    Idempotence: if workdir/population_{N}.json already exists in enriched eqasim
    format it is used as-is (no re-generation, no re-enrichment).
    """
    import random as _random
    from trip_helper.osmnx_direct import get_direct_plan, init_persistent_cache
    from population_utils import scheduling_mode as _sched_mode, _activity_index_pairs

    workdir_path = f"{settings.data.population_cache_prefix}{population_size}.json"

    def _init_osmnx_cache() -> None:
        population_name = f"{settings.data.synthetic_file_prefix}population_{population_size}"
        if settings.gtfs.osmnx_cache_enabled:
            cache_dir = os.path.join(settings.gtfs.osmnx_persistent_cache_dir, population_name)
            init_persistent_cache(cache_dir)
            
        if settings.gtfs.mode == "OTP" and settings.gtfs.otp_cache_enabled:
            from trip_helper.cached_triphelper import init_otp_persistent_cache
            otp_cache_dir = os.path.join(settings.gtfs.otp_persistent_cache_dir, population_name)
            init_otp_persistent_cache(otp_cache_dir)

    def _is_eqasim_format(data: list) -> bool:
        # Eqasim identity has no "name" key; Pydantic PersonalIdentity dump does
        return bool(data) and "name" not in data[0].get("identity", {})

    # Init caches before any routing: Pass 2 (regeneration path) must read/write
    # the persistent OSMnx cache, otherwise every regeneration recomputes all routes.
    _init_osmnx_cache()

    data = None
    if os.path.exists(workdir_path):
        with open(workdir_path, encoding="utf-8") as f:
            data = json.load(f)
        if not _is_eqasim_format(data):
            logger.info(f"[population] File in old Pydantic format — regenerating: {workdir_path}")
            data = None
        else:
            logger.info(f"[population] File exists — reusing: {workdir_path}")
            return workdir_path

    if data is None:
        # Ensure raw eqasim output exists for the exact requested size
        raw_json_path = _find_population_json(population_size)
        if not raw_json_path:
            # No bbox: let eqasim generate the full Toulouse area pool.
            # Bbox filtering is applied below in Python after loading the raw data.
            await _trigger_eqasim_generation(population_size)
            raw_json_path = _find_population_json(population_size)
            if not raw_json_path:
                logger.error("[population] No population file found after eqasim generation")
                return None

        with open(raw_json_path, encoding="utf-8") as f:
            raw_data = json.load(f)

        # Bbox filter then random sample to exactly population_size.
        # All locations (home + every activity) must be within the OSMnx graph area
        # so that routing never falls back to the "orig == dest" out-of-graph path.
        if bbox is not None:
            min_lon, min_lat, max_lon, max_lat = bbox
            def _all_locs_in_bbox(entry: dict) -> bool:
                identity = entry.get("identity", {})
                home = identity.get("home")
                if not home or home.get("lon") is None:
                    return False
                if not (min_lon <= home["lon"] <= max_lon and min_lat <= home["lat"] <= max_lat):
                    return False
                for act in identity.get("activities", []):
                    loc = act.get("location")
                    if loc and loc.get("lon") is not None:
                        if not (min_lon <= loc["lon"] <= max_lon and min_lat <= loc["lat"] <= max_lat):
                            return False
                return True
            before = len(raw_data)
            raw_data = [e for e in raw_data if _all_locs_in_bbox(e)]
            logger.info(
                f"[population] Bbox filter: {before} → {len(raw_data)} agents "
                f"(dropped {before - len(raw_data)} with home or activity outside OSMnx area)"
            )
        if population_size < len(raw_data):
            # Local seeded RNG (n'affecte pas l'état global de `random`) : le même
            # sous-ensemble d'agents est tiré à chaque run → trajets identiques → cache
            # OSMnx réutilisable au rejeu.
            _rng = _random.Random(settings.data.population_sample_seed)
            raw_data = _rng.sample(raw_data, population_size)
        data = raw_data
        logger.info(f"[population] Selected {len(data)} agents from eqasim output")

        # Step 2: fix activity sequences + merge consecutive same-purpose/same-location
        fix_count = 0
        for i, person in enumerate(data):
            data[i], fixes = fix_activities(person)
            if fixes:
                fix_count += 1
        n_merged = merge_consecutive_activities(data)
        logger.info(f"[population] Step 2: {fix_count} persons fixed, {n_merged} activities merged")

        # Pass 1: public_transport flag
        MAX_WALK_M = 1_500
        def _flag(lon: float, lat: float) -> bool:
            dlat = stop_coords[:, 0] - lat
            dlon = (stop_coords[:, 1] - lon) * math.cos(math.radians(lat))
            return float(np.hypot(dlat, dlon).min()) * 111_320 <= MAX_WALK_M

        pt_count = 0
        for entry in data:
            identity = entry.get("identity", {})
            home = identity.get("home")
            if home and home.get("lon") is not None:
                home["public_transport"] = _flag(home["lon"], home["lat"])
                pt_count += 1
            for act in identity.get("activities", []):
                loc = act.get("location")
                if loc and loc.get("lon") is not None:
                    loc["public_transport"] = _flag(loc["lon"], loc["lat"])
                    pt_count += 1
        logger.info(f"[population] {pt_count} locations flagged with public_transport")

    # Pass 2: compute scheduling-mode travel times (car for car owners, bicycle otherwise)
    # and adjust scheduled_start_time via ajuster_planning.
    # Always executed when generating a new file.
    # Build one scheduling-mode route per activity pair, then call ajuster_planning.
    tasks_meta: list[tuple] = []   # (person_index, prev_i, curr_i)
    coros = []
    for p_idx, entry in enumerate(data):
        activities = entry["identity"].get("activities", [])
        has_car    = entry["identity"].get("traits_json", {}).get("number_of_cars", 0) > 0
        mode       = _sched_mode(entry)

        for prev_i, curr_i, _ in _activity_index_pairs(activities, has_car):
            prev_act = activities[prev_i]
            curr_act = activities[curr_i]
            prev_loc = prev_act.get("location", {})
            curr_loc = curr_act.get("location", {})
            if not prev_loc or not curr_loc:
                continue
            if prev_loc.get("lon") is None or curr_loc.get("lon") is None:
                continue
            origin      = Location(lat=prev_loc["lat"], lon=prev_loc["lon"])
            destination = Location(lat=curr_loc["lat"], lon=curr_loc["lon"])
            origin_end  = prev_act.get("end_time") or 0
            departure_unix = to_timestamp_based_on_day(
                int(origin_end) if origin_end > 0 else int(curr_act.get("start_time", 0)),
                sim_base_timestamp,
            )
            congestion_dt = datetime.fromtimestamp(departure_unix)
            tasks_meta.append((p_idx, prev_i, curr_i))
            coros.append(get_direct_plan(
                origin=origin,
                destination=destination,
                trip_mode=mode,
                departure_time=departure_unix,
                congestion_dt=congestion_dt,
            ))

    logger.info(f"[population] Pass 2 OSMnx scheduling: {len(coros)} routes ({len(data)} agents)…")

    BATCH = 200
    results = []
    for i in range(0, len(coros), BATCH):
        batch_results = await asyncio.gather(*coros[i:i + BATCH], return_exceptions=True)
        results.extend(batch_results)
        logger.info(f"[population] Pass 2: {min(i + BATCH, len(coros))}/{len(coros)} routes calculées")

    # Build per-person travel_times dict from results
    person_travel_times: list[dict] = [{} for _ in data]
    osmnx_ok = 0
    for (p_idx, prev_i, curr_i), result in zip(tasks_meta, results):
        if isinstance(result, Exception) or result is None:
            continue
        person_travel_times[p_idx][(prev_i, curr_i)] = result.duration
        osmnx_ok += 1
    logger.info(f"[population] Pass 2: {osmnx_ok}/{len(tasks_meta)} scheduling routes computed")

    # Adjust schedules
    sched_errors = 0
    for p_idx, entry in enumerate(data):
        acts = entry.get("identity", {}).get("activities", [])
        try:
            entry["identity"]["activities"] = ajuster_planning(
                workdir_path,
                entry.get("person_id", "?"),
                acts,
                travel_times=person_travel_times[p_idx],
                raise_error=True,
            )
        except ValueError as exc:
            sched_errors += 1
            logger.warning(f"[population] ajuster_planning: {exc}")
    if sched_errors:
        logger.warning(f"[population] Step 5: {sched_errors} person(s) with unresolved schedule conflicts")
    else:
        logger.info("[population] Step 5: all schedules adjusted successfully")

    tmp_path = workdir_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.rename(tmp_path, workdir_path)
    logger.info(f"[population] Population written to {workdir_path} ({len(data)} agents)")

    return workdir_path

# Set working directory from environment if specified
workdir = os.environ.get("APP_WORKDIR", "")
if workdir:
    settings.update_workdir(workdir)

# Initialize logging
setup_logging(settings)

# Create FastAPI application instance
# ORJSONResponse est la classe de réponse par défaut : elle calcule Content-Length
# et sérialise le body avec le MÊME sérialiseur (orjson), évitant la désynchronisation
# qui causait "fixed content-length: X, bytes received: Y" côté Java.
app = FastAPI(default_response_class=ORJSONResponse)



class LoopContainer:
    """
    Container for managing WebSocket communication and message loops.

    This class handles the bidirectional communication between the FastAPI server
    and the GAMA simulation via WebSocket. It manages observation publishing and
    action message handling.
    """
    action_topic = "action/data"
    system_greeting_topic = "system/greeting"
    observation_topic = "observation/data"
    system_log_topic = "system/log"
    system_throttle_topic = "system/throttle"

    def __init__(self):
        self.client = None
        self.scenario = None
        self._worker_task: asyncio.Task | None = None
        # Buffer de retry du publish_loop : attribut d'instance (et non variable locale)
        # pour pouvoir être purgé au remplacement de scénario — sinon les actions de
        # l'ancienne simulation restées en attente (socket morte au stop GAMA) seraient
        # rejouées vers la nouvelle simulation à la reconnexion.
        self._pending: list = []
        # Initialize WebSocket client for GAMA communication
        self.websocket_client = WebSocketClient(settings.server.gama_ws_url)
        self.websocket_client.on_message = self.handle_message

    def set_scenario(self, scenario: BaseScenario):
        """Set the active simulation scenario, inject push_fn and start the Worker."""
        # Cancel the previous Worker if still running (e.g. successive /test/init calls).
        # stop_worker() annule la vraie boucle _worker_loop du scénario précédent ;
        # _worker_task (le wrapper start_worker) est lui déjà terminé à ce stade.
        if self.scenario is not None:
            try:
                self.scenario.stop_worker()
            except Exception as e:
                logger.warning(f"Failed to stop previous scenario worker: {e}")
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()

        # Purger les actions de l'ancien scénario encore en attente d'envoi :
        # les person_ids étant identiques d'un run à l'autre (même population, même
        # seed), ces trajets périmés seraient injectés dans la nouvelle simulation.
        if self._pending:
            logger.warning(
                f"[set_scenario] {len(self._pending)} pending action(s) from previous "
                f"scenario discarded (would have been replayed to the new simulation)"
            )
            self._pending.clear()

        self.scenario = scenario

        # Injecter la fonction de push WebSocket direct dans le scénario.
        # Le booléen de send_json est propagé : send_message avale les exceptions
        # d'envoi et retourne False (socket morte, reconnexion en cours) — sans ce
        # retour, _push_planned_move croyait le push délivré et l'agent devenait
        # un zombie (GAMA sans trajet, Python en attente d'une arrivée impossible).
        async def _direct_push(action) -> bool:
            return await self.websocket_client.send_json({
                "topic": self.action_topic,
                "payload": action.model_dump(),
            })

        scenario.set_push_fn(_direct_push)
        self._worker_task = asyncio.create_task(scenario.start_worker())

    async def greeting(self):
        """Send a greeting message to the WebSocket server"""
        await self.websocket_client.connect()

        greeting_message = {
            "topic": self.system_greeting_topic,
            "payload": {
                "type": "greeting",
                "message": "Hello from FastAPI + WebSocket client!"
            }
        }
        success = await self.websocket_client.send_json(greeting_message)
        if not success:
            logger.error("Failed to send greeting message")

    async def send_log(self, message: str):
        """Envoie un message de progression à GAMA via WebSocket"""
        if self.websocket_client:
            await self.websocket_client.send_json({
                "topic": self.system_log_topic,
                "payload": {
                    "message": message
                }
            })

    async def send_throttle(self, payload: dict):
        """Notifie GAMA du régime de contre-pression (topic system/throttle, ticket 003).

        Même canal que send_log : le champ `message` reste autoporteur (un GAMA qui ne
        gère pas le topic peut le traiter comme un log). Les autres champs (débits,
        backlog) alimentent l'UI / les globales de l'expérience."""
        if self.websocket_client:
            await self.websocket_client.send_json({
                "topic": self.system_throttle_topic,
                "payload": payload,
            })

    async def publish_loop(self):
        """
        Main publishing loop that sends action messages to GAMA via WebSocket.

        Continuously checks for new messages from the scenario and publishes them
        to the GAMA simulation. Handles connection failures and retries.

        `self._pending` survit aux exceptions inattendues (e.g. model_dump) — les
        messages non envoyés restent en buffer et sont retentés à l'itération
        suivante ; le buffer est purgé par set_scenario au changement de scénario.
        """
        while True:
            try:
                # Only fetch new messages when the pending buffer is empty.
                if not self._pending and self.scenario and await self.scenario.has_messages():
                    self._pending = await self.scenario.pop_all_messages()

                sent = 0
                while self._pending:
                    message = self._pending[0]
                    payload = message.model_dump()
                    success = await self.websocket_client.send_json({
                        "topic": self.action_topic,
                        "payload": payload,
                    })
                    if not success:
                        # WebSocket not ready — keep in buffer, retry next tick
                        logger.warning(
                            f"WebSocket not connected, will retry {len(self._pending)} pending message(s)"
                        )
                        break
                    # set_scenario peut avoir purgé le buffer pendant l'await du send
                    if self._pending:
                        self._pending.pop(0)
                    sent += 1
                    _pl = PipelineLogger.get()
                    if _pl is not None:
                        _person_id = payload.get("person_id")
                        if _person_id:
                            _pl.complete(_person_id)

                if sent > 0:
                    logger.info(f"WebSocket loop sent {sent} message(s) to {self.action_topic}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"WebSocket publish loop error: {e}")

            await asyncio.sleep(1)  # Adjust sleep time as needed

    async def handle_message(self, text: str):
        """Handle received Websocket message"""
        try:
            #logger.debug(f"Received: {self.observation_topic} -> {text}")
            await self.process_observation(self.observation_topic, text)

        except Exception as e:
            logger.exception(f"Error handling message: {e}")

    async def process_observation(self, topic: str, payload: str):
        """
        Process observation data received from GAMA simulation.

        Parses the observation payload and forwards it to the scenario for processing.
        Observations contain agent state information for LLM decision making.
        """
        try:
            data = json.loads(payload)
            assert data["topic"] == self.observation_topic, "Invalid topic in observation data"
            observation = Observation(**data["payload"])
            await self.scenario.handle_observation(observation)
        except Exception as e:
            logger.exception(f"Error processing observation: {e}")

class _AgentStateLog:
    """Append-only CSV recording agent state counts per simulation step."""

    _HEADERS = ["step", "sim_timestamp", "sim_time", "inactive", "ready", "active", "total"]

    def __init__(self):
        self._path: Path | None = None
        self._initialized = False

    def _ensure_file(self) -> Path:
        if self._path is None:
            self._path = settings.workdir / "gama_results" / "agent_states.csv"
            self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._initialized:
            self._initialized = True
            if not self._path.exists():
                with open(self._path, "w", newline="", encoding="utf-8") as f:
                    csv.writer(f).writerow(self._HEADERS)
        return self._path

    def record(self, step: int, sim_timestamp: int, inactive: int, ready: int, active: int):
        path = self._ensure_file()
        sim_time = datetime.fromtimestamp(sim_timestamp).strftime("%H:%M:%S") if sim_timestamp > 0 else ""
        with open(path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([step, sim_timestamp, sim_time, inactive, ready, active, inactive + ready + active])


_agent_state_log = _AgentStateLog()

# Global loop container instance
loop_container = LoopContainer()
# Initialisation des données statiques (chargement GTFS, OTP...) au démarrage du serveur
static_data = init_static_data()
print("===> Données statiques initialisées. En attente de la requête /init de GAMA...")

EVENT_LOOP_LAG = Gauge('controller_event_loop_lag_seconds', 'Retard maximal observé de l\'event loop asyncio sur la dernière fenêtre (stall = la loop n\'a pas repris la main à temps)')


async def _event_loop_lag_monitor(tick: float = 1.0, alarm_threshold: float = 5.0) -> None:
    """Mesure les blocages de l'event loop (dérive d'un sleep périodique).

    Un stall > alarm_threshold est tracé en ERROR avec [ALARME] : c'est lui qui
    fait expirer le keepalive WebSocket (coupure 1006 → push perdus) quand il
    dépasse le ping_timeout. La trace donne l'instant de reprise — le coupable
    est l'opération qui vient de rendre la main juste avant.
    """
    loop = asyncio.get_running_loop()
    while True:
        t0 = loop.time()
        await asyncio.sleep(tick)
        lag = loop.time() - t0 - tick
        EVENT_LOOP_LAG.set(max(0.0, lag))
        if lag > alarm_threshold:
            fire_alarme("event_loop")
            logger.error(
                f"[ALARME] Event loop bloquée pendant ~{lag:.1f}s — opération synchrone "
                f"dans la boucle asyncio (calcul CPU, I/O bloquante ?). Au-delà du "
                f"ping_timeout WebSocket, ces stalls provoquent les coupures 1006."
            )


@app.on_event("startup")
async def startup_event():
    """
    FastAPI startup event handler.

    Initializes WebSocket connection and starts background tasks for
    real-time communication with GAMA simulation.
    """
    await loop_container.greeting()
    create_background_task(loop_container.websocket_client.run_with_reconnect())
    create_background_task(loop_container.publish_loop())
    create_background_task(_event_loop_lag_monitor())

@app.on_event("shutdown")
async def shutdown_event():
    """FastAPI shutdown event handler - closes WebSocket connections."""
    await loop_container.websocket_client.stop()
    _pl = PipelineLogger.get()
    if _pl is not None:
        _pl.close()

@app.get(
    "/",
    summary="Vérifier le statut du contrôleur",
    description="Vérifie si l'API du contrôleur de simulation (FastAPI) est bien démarrée et en attente de la connexion WebSocket avec GAMA.",
    tags=["Système"]
)
async def root():
    """Root endpoint - returns service status."""
    return {"status": "FastAPI + Websocket running"}

@app.get(
    "/metrics",
    summary="Exporter les métriques Prometheus",
    description="Expose les compteurs d'événements de la simulation GAMA (appels, synchronisations) au format Prometheus.",
    tags=["Système"]
)
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)

@app.post(
    "/init",
    summary="Initialiser la population du monde",
    description=(
        "Génère et renvoie la liste complète de la population synthétique (avec les coordonnées des domiciles et les caractéristiques des agents) "
        "pour peupler la carte GAMA au lancement de la simulation. "
        "Bloque jusqu'à ce que tous les premiers itinéraires soient calculés (bootstrap), "
        "de sorte que GAMA ne commence pas à avancer avant que chaque agent ait son premier trajet en file."
    ),
    tags=["Simulation"]
)
async def init(request: WorldInitRequest):
    """
    Initialize the simulation world and pre-compute all first itineraries.

    GAMA's reflex init blocks on this HTTP call, so the simulation cannot
    advance until bootstrap_all_agents completes and every agent has a move queued.
    """
    INIT_REQUESTS.inc()
    _N_STEPS = 5
    _t_init_start = time.time()

    def _init_stage(step: int) -> None:
        CTRL_INIT_STAGE.set(step)
        CTRL_INIT_PROGRESS.set(step / _N_STEPS)

    _init_stage(1)

    logger.info(format_sim_timing("SIM_START", sim_time=humanize_date(request.timestamp)))
    logger.info(f"INITIALISATION 1/{_N_STEPS} Préparation de la population — sim_time={humanize_date(request.timestamp)}")
    await loop_container.send_log(f"[1/{_N_STEPS}] Préparation de la population (génération + enrichissement)...")

    effective_population_size = request.population_size or settings.data.population_size
    stops_df = static_data.gtfs_data.stops[['stop_lat', 'stop_lon']].dropna()
    stop_coords = stops_df.values.astype(float)
    population_json_path = await _prepare_population(
        population_size=effective_population_size,
        stop_coords=stop_coords,
        sim_base_timestamp=request.timestamp,
        bbox=TOULOUSE_OSM_ROUTES_30K_BBOX,
    )
    if population_json_path is None:
        raise RuntimeError(
            f"[population] Impossible de préparer la population ({effective_population_size} agents) — "
            "vérifier les logs eqasim et le répertoire eqasim-output."
        )

    _init_stage(2)
    logger.info(f"INITIALISATION 2/{_N_STEPS} Population prête — {population_json_path}")
    await loop_container.send_log(f"[2/{_N_STEPS}] Population prête.")

    _init_stage(3)
    logger.info(f"INITIALISATION 3/{_N_STEPS} Initialisation du scénario et chargement des agents")
    await loop_container.send_log(f"[3/{_N_STEPS}] Initialisation du scénario...")

    scenario = init_dynamic_scenario(
        static_data,
        sim_base_timestamp=request.timestamp,
        population_size=request.population_size,
        part_of_llm_agents=request.part_of_llm_based_agents if request.part_of_llm_based_agents is not None else 1.0,
        long_term_memory_enabled=request.long_term_memory_enabled,
        long_term_self_reflect_enabled=request.long_term_self_reflect_enabled,
    )
    loop_container.set_scenario(scenario)

    if settings.app.pipeline_log_enabled:
        from pathlib import Path
        PipelineLogger.init(Path(settings.app.pipeline_log_file))
        logger.info(f"Pipeline timing log enabled → {settings.app.pipeline_log_file}")

    _init_stage(4)
    logger.info(f"INITIALISATION 4/{_N_STEPS} Pré-calcul du premier itinéraire pour chaque agent (bootstrap)")
    await loop_container.send_log(f"[4/{_N_STEPS}] Pré-calcul des premiers itinéraires...")

    if request.timestamp > 0:
        await scenario.bootstrap_all_agents(timestamp=request.timestamp)

    people = scenario.population.get_people_list()
    SIM_AGENTS_TOTAL.set(len(people))
    global _sim_init_wall_time, _sim_step_count, _last_logical_time
    global _sim_ratio_ewma, _sim_ratio_ewma_time, _throttle_active, _throttle_last_notify_at
    _sim_init_wall_time = time.time()
    _sim_step_count = 0
    _last_logical_time = request.timestamp if request.timestamp > 0 else 0
    # Réinitialiser l'état du contrôle prédictif (ticket 003) pour un run propre.
    _sim_ratio_ewma = None
    _sim_ratio_ewma_time = None
    _throttle_active = False
    _throttle_last_notify_at = 0.0
    SIM_STEP_COUNT.set(0)
    SIM_REAL_ELAPSED.set(0)
    if request.timestamp > 0:
        SIM_LOGICAL_TIME.set(request.timestamp)
    for _state in ('inactive', 'ready', 'active'):
        AGENT_STATES.labels(state=_state).set(0)
    AGENT_STATES.labels(state='inactive').set(len(people))

    _init_stage(5)
    _init_duration = time.time() - _t_init_start
    from urban_mobility_agents.simulation_controller import _format_cache_hit_rates
    _cache_str = _format_cache_hit_rates()
    logger.info(format_sim_timing("INIT_DONE", agents=len(people), init_duration_s=f"{_init_duration:.0f}"))
    logger.info(f"INITIALISATION 5/{_N_STEPS} Démarrage de la simulation — {len(people)} agents envoyés à GAMA (init={_init_duration:.0f}s)")
    await loop_container.send_log(
        f"[5/{_N_STEPS}] Démarrage de la simulation — {len(people)} agents | init: {_init_duration:.0f}s | caches: {_cache_str}"
    )

    person_response = [
        GamaPersonData(
            **person.model_dump(),
            location=scenario.population.get_person_home_location(person.person_id),
            name=person.identity.name,
        )
        for person in people
    ]
    return MessageResponse(
        message_type=MessageType.AG_WORLD_INIT,
        data=WorldInitResponse(
            people=person_response,
            num_people=len(people),
            # TODO: remove this
            timestamp=0,
        )
    )

@app.post(
    "/test/init",
    summary="[TEST] Initialiser le scénario sans GAMA",
    description=(
        "Initialise le scénario directement depuis le fichier de population, sans connexion WebSocket GAMA. "
        "Réservé aux tests de charge et de performance. Ne lance pas le bootstrap des itinéraires."
    ),
    tags=["Test"],
)
async def test_init(population_size: int = None, timestamp: int = 1_775_800_000):
    """Initialize the scenario from the population file without a GAMA WebSocket connection."""
    if population_size is None:
        # Fallback to the largest available file; do NOT use settings (can default to 1)
        largest = _find_population_json(population_size=None)
        if largest is None:
            raise HTTPException(status_code=404, detail="No population file found. Pass population_size explicitly.")
        m = re.search(r"population_(\d+)\.json$", largest)
        effective_size = int(m.group(1)) if m else settings.data.population_size
    else:
        effective_size = population_size

    stops_df = static_data.gtfs_data.stops[['stop_lat', 'stop_lon']].dropna()
    stop_coords = stops_df.values.astype(float)

    population_json_path = await _prepare_population(
        population_size=effective_size,
        stop_coords=stop_coords,
        sim_base_timestamp=timestamp,
        bbox=TOULOUSE_OSM_ROUTES_30K_BBOX,
    )
    if population_json_path is None:
        return MessageResponse(success=False, error="Population preparation failed")

    scenario = init_dynamic_scenario(
        static_data,
        sim_base_timestamp=timestamp,
        population_size=effective_size,
        long_term_memory_enabled=False,
        long_term_self_reflect_enabled=False,
    )
    loop_container.set_scenario(scenario)

    people = scenario.population.get_people_list()
    logger.info(f"[test/init] Scénario initialisé — {len(people)} agents, timestamp={timestamp}")
    return MessageResponse(success=True, data={"num_people": len(people), "population_file": str(population_json_path)})


@app.get(
    "/test/queue_depth",
    summary="[TEST] Nombre d'agents en cours de scheduling",
    tags=["Test"],
)
async def queue_depth():
    """Return the number of agents currently waiting for an LLM/OTP response."""
    if not loop_container.scenario:
        return {"scheduling_in_progress": 0, "total_agents": 0}
    people = loop_container.scenario.population.get_people_list()
    in_progress = sum(1 for p in people if p.state.scheduling_in_progress)
    return {"scheduling_in_progress": in_progress, "total_agents": len(people)}


@app.post(
    "/reflect",
    summary="Déclencher la réflexion forcée des agents",
    description=(
        "Force tous les agents de la simulation à mettre à jour leur état cognitif (réflexion sur leur mémoire) "
        "pour correspondre au timestamp fourni. Utilisé principalement pour le débogage ou la synchronisation manuelle."
    ),
    tags=["Simulation"]
)
async def reflect(request: WorldSyncRequest):
    """
    Reflect the current world state at a specific timestamp.

    Forces all agents to update their state to match the simulation time.
    Used for synchronization and debugging.
    """
    logger.info(f"Reflecting world at timestamp: {request.timestamp}")

    if loop_container.scenario:
        await loop_container.scenario.trigger_short_term_reflection_for_all(request.timestamp)
        return MessageResponse(
            data="reflected",
            success=True,
        )
    else:
        logger.debug("[/reflect] Scenario not ready yet — init still in progress, skipping")
        return MessageResponse(data="not_ready", success=True)


# Digest de capacité poussé à GAMA (topic system/log) tous les N /sync : signaux
# « live » cheaply available en-process (cache LLM, débit, backlog, activité agents).
_DIGEST_EVERY_N_SYNC = 10


def _build_capacity_digest(
    step: int, inactive: int, ready: int, active: int,
    in_progress: int, throughput_per_s: float,
) -> str:
    """Ligne synthétique de capacité (≈ pendant live de scripts/debug/llm_capacity.py)."""
    total = inactive + ready + active
    d_min = throughput_per_s * 60.0
    try:
        from llm.cache import get_llm_cache_stats
        hits, lookups = get_llm_cache_stats()
        cache_str = f"{100 * hits // lookups}% ({hits}/{lookups})" if lookups else "off"
    except Exception:
        cache_str = "n/a"
    fill = in_progress / max(1, total) if total else 0.0
    return (
        f"📊 [cycle {step}] cache LLM {cache_str} · débit {d_min:.0f} req/min · "
        f"backlog {in_progress} ({fill:.0%}) · agents {active} actifs / "
        f"{inactive} inactifs / {total} total"
    )


@app.post(
    "/sync",
    summary="Synchroniser l'état du monde",
    description=(
        "Met à jour l'état du scénario côté Python avec les données de la population inactive (`idle_people`) envoyées par GAMA. "
        "Le contrôleur lit le corps de la requête en texte brut pour contourner les éventuels problèmes de header HTTP/2 (h2c)."
    ),
    tags=["Simulation"]
)
async def sync(raw: Request):
    """Point d'entrée /sync : mesure la durée totale de traitement puis délègue."""
    with CTRL_SYNC_DURATION.time():
        return await _sync_impl(raw)


async def _sync_impl(raw: Request):
    """
    Synchronize the world state with idle population data.

    Reads the raw body to remain compatible with GAMA's Java HTTP client,
    which sends h2c upgrade headers that prevent uvicorn/h11 from reading
    the body. hypercorn handles h2c natively, so the body is always available.
    """
    global _last_sync_wall_time, _last_sync_response_wall_time, _sim_step_count, _last_logical_time, _last_backpressure_in_progress, _last_backpressure_min_interval, _backlog_alarm_active, _drain_mode_active
    global _sim_ratio_ewma, _sim_ratio_ewma_time, _throttle_active, _throttle_last_notify_at
    now = time.time()
    real_delta = now - _last_sync_wall_time if _last_sync_wall_time > 0 else 0.0
    if real_delta > 0:
        SIM_STEP_INTERVAL.set(real_delta)
    _last_sync_wall_time = now
    _sim_step_count += 1
    SIM_STEP_COUNT.set(_sim_step_count)
    if _sim_init_wall_time > 0:
        SIM_REAL_ELAPSED.set(now - _sim_init_wall_time)

    SYNC_REQUESTS.inc()
    body = await raw.body()

    if not body:
        logger.warning("[/sync] Empty body received — sync skipped (unknown timestamp)")
        return MessageResponse(data="skipped (empty body)", success=True)

    try:
        data = orjson.loads(body)
        request = WorldSyncRequest(**data)
    except Exception as e:
        logger.error(f"[/sync] JSON parsing error: {e}")
        return ORJSONResponse(status_code=422, content={"detail": str(e)})
    _t_parse_end = time.time()

    logger.info(f"Synchronizing world at timestamp: {request.timestamp} ({humanize_date(request.timestamp)})")

    if loop_container.scenario:
        try:
            ready    = request.ready_count
            active   = request.active_count
            inactive = request.inactive_count
            AGENT_STATES.labels(state='inactive').set(inactive)
            AGENT_STATES.labels(state='ready').set(ready)
            AGENT_STATES.labels(state='active').set(active)
            # Écriture CSV déportée hors de l'event loop (open/write bloquants)
            await asyncio.to_thread(_agent_state_log.record, _sim_step_count, request.timestamp, inactive, ready, active)
        except Exception:
            pass
        in_progress_before_sync = loop_container.scenario.activities_to_compute_count
        # Deadline misses (ticket 003) : _late_count est remis à 0 par sync() → le lire avant.
        try:
            CTRL_DEADLINE_MISSES.inc(loop_container.scenario.late_since_last_sync)
        except Exception:
            pass
        await loop_container.scenario.sync(request.timestamp, _t_sync=now, _t_parse=_t_parse_end)
        try:
            SIM_LOGICAL_TIME.set(request.timestamp)
            if _last_logical_time > 0 and request.timestamp > _last_logical_time:
                sim_delta = request.timestamp - _last_logical_time
                SIM_STEP_LOGICAL_DURATION.set(sim_delta)
                if real_delta > 0:
                    _ratio = sim_delta / real_delta
                    SIM_WALL_CLOCK_RATIO.set(_ratio)
                    # R : rythme sim/réel lissé (EWMA temporel), utilisé par le test de
                    # faisabilité EDF. Le SIM_WALL_CLOCK_RATIO brut est bruité d'un /sync
                    # à l'autre (frein variable) ; le lissage stabilise le slack estimé.
                    _sim_ratio_ewma = time_ewma(
                        _sim_ratio_ewma, _sim_ratio_ewma_time, _ratio, now,
                        tau_s=settings.world.throughput_ewma_tau_s,
                    )
                    _sim_ratio_ewma_time = now
        except Exception:
            pass
        _last_logical_time = request.timestamp
        in_progress_count = loop_container.scenario.activities_to_compute_count
        if real_delta > 5.0:
            await loop_container.send_log(
                f"[⚠ sync lent] {real_delta:.1f}s depuis le dernier sync — "
                f"tâches utilisées pour le sleep précédent : {_last_backpressure_in_progress} "
                f"(sleep calculé : {_last_backpressure_min_interval:.2f}s)"
            )
        _k   = settings.world.min_internal_coeff_k
        _cap = settings.world.min_internal_coeff_cap
        min_interval = compute_backpressure_interval(
            in_progress_count, settings.data.population_size, k=_k, cap=_cap
        )
        logger.info(f"Activités à calculer: {in_progress_count} — applying min_interval={min_interval:.2f}s")

        # Digest de capacité poussé à GAMA tous les _DIGEST_EVERY_N_SYNC cycles.
        # Toute erreur est avalée : le digest ne doit jamais faire échouer un /sync.
        if _sim_step_count % _DIGEST_EVERY_N_SYNC == 0:
            try:
                await loop_container.send_log(_build_capacity_digest(
                    step=_sim_step_count,
                    inactive=request.inactive_count,
                    ready=request.ready_count,
                    active=request.active_count,
                    in_progress=in_progress_count,
                    throughput_per_s=loop_container.scenario.throughput_per_s(),
                ))
            except Exception as e:
                logger.debug(f"[digest] non envoyé: {e}")

        # Alarme backlog : alignée sur les seuils du mode drainage (front montant à
        # drain_trigger_ratio, réarmée quand le backlog repasse sous drain_release_ratio) —
        # au-delà du seuil, le pipeline LLM ne suit plus la cadence de la simulation.
        _backlog_ratio = in_progress_count / max(1, settings.data.population_size)
        CTRL_BACKLOG_FILL_RATIO.set(_backlog_ratio)
        if _backlog_ratio >= settings.world.drain_trigger_ratio > 0 and not _backlog_alarm_active:
            _backlog_alarm_active = True
            fire_alarme("backlog")
            _alarm_msg = (
                f"[ALARME] Backlog critique : {in_progress_count} activités en attente "
                f"({_backlog_ratio:.0%} de la population) — le pipeline LLM ne draine plus. "
                f"Backpressure actuel min_interval={min_interval:.2f}s "
                f"(coeffs k={_k} cap={_cap}). "
                f"Vérifier les rate limits providers (make error) et le taux de hit du cache LLM."
            )
            logger.error(_alarm_msg)
            await loop_container.send_log(f"⛔ {_alarm_msg}")
        elif _backlog_ratio < settings.world.drain_release_ratio and _backlog_alarm_active:
            _backlog_alarm_active = False
            logger.info(
                f"[ALARME levée] Backlog résorbé : {in_progress_count} activités en attente "
                f"({_backlog_ratio:.0%} de la population)"
            )
        # Mode drainage (hystérésis, en plus du frein progressif) : dès que la pile
        # atteint drain_trigger_ratio, la réponse /sync est retenue jusqu'au cap
        # (limite dure : le read timeout HTTP du client GAMA, une réponse ne peut
        # pas être retenue plus longtemps) et la pile est ré-échantillonnée à
        # intervalle court pour rendre la main dès qu'elle est vidée sous
        # drain_release_ratio. Tant que ce seuil n'est pas atteint, chaque /sync
        # suivant est retenu à son tour : GAMA est bridé à ~1 step par cap.
        _was_draining = _drain_mode_active
        _drain_mode_active = update_drain_mode(
            _drain_mode_active, _backlog_ratio,
            settings.world.drain_trigger_ratio, settings.world.drain_release_ratio,
        )
        if _drain_mode_active and not _was_draining:
            logger.warning(
                f"[drain] Pile à {_backlog_ratio:.0%} (≥ {settings.world.drain_trigger_ratio:.0%}) : "
                f"les réponses /sync sont retenues jusqu'à {_cap:.0f}s tant que la pile "
                f"n'est pas redescendue sous {settings.world.drain_release_ratio:.0%}"
            )
        # --- Observation prédictive (ticket 003) : calculée à chaque /sync, même quand
        # le contrôle prédictif est désactivé (phase d'observation pour calibrer tau/marge). ---
        _D = loop_container.scenario.throughput_per_s()            # débit de complétion (tâches/s, EWMA)
        _R = _sim_ratio_ewma if _sim_ratio_ewma is not None else 0.0  # rythme sim/réel lissé
        _deadlines = loop_container.scenario.edf_snapshot_deadlines()
        _feas = edf_feasibility(
            _deadlines, request.timestamp, _D, _R, settings.world.predictive_margin
        )
        CTRL_THROUGHPUT.set(_D * 60.0)
        CTRL_T_ESTIMATE.set(_feas.t_estimate_s)
        CTRL_MIN_SLACK.set(_feas.min_slack_sim_s)
        CTRL_EDF_QUEUE_DEPTH.set(loop_container.scenario.edf_queue_depth)

        _predictive_hold_s = 0.0
        if _drain_mode_active:
            # Filet de sécurité ultime (surcharge permanente > 100 % d'utilisation) :
            # gel par ratio à hystérésis, inchangé. Prioritaire sur le prédictif.
            _drain_start = time.time()
            _live_ratio = _backlog_ratio
            while _drain_mode_active and (time.time() - _drain_start) < _cap:
                await asyncio.sleep(settings.world.drain_poll_interval)
                _live_count = loop_container.scenario.activities_to_compute_count
                _live_ratio = _live_count / max(1, settings.data.population_size)
                _drain_mode_active = update_drain_mode(
                    True, _live_ratio,
                    settings.world.drain_trigger_ratio, settings.world.drain_release_ratio,
                )
            if _drain_mode_active:
                logger.warning(
                    f"[drain] Cap {_cap:.0f}s atteint, pile encore à {_live_ratio:.0%} — "
                    f"GAMA sera retenu à nouveau au prochain /sync"
                )
            else:
                logger.info(
                    f"[drain] Pile redescendue à {_live_ratio:.0%} (< {settings.world.drain_release_ratio:.0%}) — "
                    f"main rendue à GAMA après {time.time() - _drain_start:.1f}s"
                )
            min_interval = _cap
        elif settings.world.predictive_backpressure_enabled and settings.world.edf_enabled:
            # Rétention prédictive : le /sync n'est retenu que si le test de faisabilité
            # EDF annonce une échéance menacée. Nécessite le dispatcher EDF (le test lit
            # un snapshot du heap) : sans EDF, on retombe sur le frein progressif ci-dessous.
            # Sinon → réponse immédiate (le frein progressif cap·ratio^k est court-circuité).
            # Retenir le /sync gèle le temps simulé (donc les deadlines) : ce qui débloque
            # la file, c'est le drainage par les consommateurs (T_k = k/D baisse) — pas
            # l'avancée du temps.
            # R est figé à l'entrée : pendant la rétention le rythme mesuré s'effondre
            # (aucun /sync servi), il ne doit pas rétroagir sur la condition de sortie.
            _R_frozen = _R
            _live_feas = _feas
            if _feas.hold and _R_frozen > 0:
                _hold_start = time.time()
                while _live_feas.hold and (time.time() - _hold_start) < _cap:
                    await asyncio.sleep(settings.world.drain_poll_interval)
                    _live_D = loop_container.scenario.throughput_per_s()
                    _live_deadlines = loop_container.scenario.edf_snapshot_deadlines()
                    _live_feas = edf_feasibility(
                        _live_deadlines, request.timestamp, _live_D, _R_frozen,
                        settings.world.predictive_margin,
                    )
                _predictive_hold_s = time.time() - _hold_start
                logger.info(
                    f"[predictive] /sync retenu {_predictive_hold_s:.1f}s "
                    f"(D={_D*60:.1f}/min, R×{_R_frozen:.1f}, file={len(_deadlines)}, "
                    f"T≈{_feas.t_estimate_s:.0f}s, slack_min={_feas.min_slack_sim_s:.0f}s sim) — "
                    f"{'relâché' if not _live_feas.hold else 'cap atteint'}"
                )
            min_interval = _predictive_hold_s
        elif min_interval > 0 and _last_sync_response_wall_time > 0:
            remaining = min_interval - (time.time() - _last_sync_response_wall_time)
            if remaining > 0:
                await asyncio.sleep(remaining)
        CTRL_PREDICTIVE_HOLD.set(_predictive_hold_s)

        # --- Notification GAMA (topic system/throttle, hystérésis, ticket 003) ---
        _now_wall = time.time()
        _backlog_now = loop_container.scenario.activities_to_compute_count
        if _predictive_hold_s >= settings.world.throttle_notify_threshold_s:
            _need_notify = (
                not _throttle_active
                or (_now_wall - _throttle_last_notify_at) >= settings.world.throttle_notify_refresh_s
            )
            if _need_notify:
                _msg = (
                    f"⏳ Simulation bridée : débit LLM {_D*60:.1f}/min, vitesse sim ×{_R:.1f}, "
                    f"{_backlog_now} tâches en file (T≈{_feas.t_estimate_s/60:.1f}min)"
                )
                await loop_container.send_throttle({
                    "active": True,
                    "llm_rate_per_min": round(_D * 60.0, 1),
                    "sim_ratio": round(_R, 1),
                    "backlog": _backlog_now,
                    "t_estimate_s": round(_feas.t_estimate_s, 1),
                    "min_slack_sim_s": round(_feas.min_slack_sim_s, 1),
                    "message": _msg,
                })
                _throttle_active = True
                _throttle_last_notify_at = _now_wall
        elif _throttle_active:
            # Front descendant : premier /sync servi sans rétention → levée.
            await loop_container.send_throttle({
                "active": False,
                "llm_rate_per_min": round(_D * 60.0, 1),
                "sim_ratio": round(_R, 1),
                "backlog": _backlog_now,
                "t_estimate_s": round(_feas.t_estimate_s, 1),
                "min_slack_sim_s": round(_feas.min_slack_sim_s, 1),
                "message": "✅ Simulation rétablie : plus de bridage prédictif.",
            })
            _throttle_active = False

        _last_backpressure_in_progress = in_progress_count
        _last_backpressure_min_interval = min_interval
        _last_sync_response_wall_time = time.time()
        CTRL_BACKPRESSURE_INTERVAL.set(min_interval)
        CTRL_DRAIN_MODE.set(1 if _drain_mode_active else 0)
        try:
            _stuck_threshold_s = settings.world.stuck_agent_threshold_hours * 3600
            CTRL_AGENTS_STUCK.set(
                loop_container.scenario.count_stuck_agents(request.timestamp, _stuck_threshold_s)
            )
        except Exception:
            pass
        return MessageResponse(data="synchronized", success=True)
    else:
        logger.debug("[/sync] Scenario not ready yet — init still in progress, skipping")
        return MessageResponse(data="not_ready", success=True)


# ── Calibration du prompt (déclenchée depuis l'IHM GAMA) ─────────────────────
# Chemin du dépôt autonome prompt_calibration monté dans le conteneur (voir
# docker-compose, volume ./prompt_calibration:/app/prompt_calibration). La
# calibration lit ses chemins relativement à ce dossier (jeux gelés, store) et
# via config/gama_container.yaml pour prompts.yaml / cerema_values.yaml.
CALIBRATION_DIR = Path("/app/prompt_calibration")

# Handle du sous-processus de calibration en cours (un seul à la fois), et
# verrou pour rendre atomique la séquence vérification-puis-lancement (sans
# lui, deux requêtes /calibrate concurrentes peuvent toutes deux passer le
# check "déjà en cours" et lancer chacune leur campagne sur le même store).
_calibration_proc: subprocess.Popen | None = None
_calibration_lock = asyncio.Lock()


@app.post(
    "/calibrate",
    summary="Lancer la calibration du prompt",
    description=(
        "Démarre une campagne de calibration du prompt système `itinary_multi_agent` "
        "en tâche de fond, avec un nombre de cycles (itérations de la boucle) paramétrable. "
        "L'appel est non bloquant : GAMA reçoit immédiatement l'accusé de démarrage, la "
        "calibration se poursuit dans le conteneur `controller`. Un seul run à la fois."
    ),
    tags=["Calibration"],
)
async def calibrate(raw: Request):
    """Lance `python -m calibration.cli run --iterations N` en sous-processus détaché."""
    global _calibration_proc

    # Corps lu en brut (client HTTP GAMA / h2c), tolérant au corps vide.
    body = await raw.body()
    iterations = 20
    if body:
        try:
            payload = orjson.loads(body)
            iterations = int(payload.get("iterations", iterations))
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "message_type": "calibration_error",
                    "error": f"Corps de requête invalide : {exc}"}

    if iterations < 1:
        return {"success": False, "message_type": "calibration_error",
                "error": "Le nombre de cycles doit être >= 1"}

    if not CALIBRATION_DIR.exists():
        msg = (f"Package de calibration introuvable ({CALIBRATION_DIR}). "
               f"Vérifier le montage ./prompt_calibration:/app/prompt_calibration "
               f"dans docker-compose.yml.")
        logger.error(f"[ALARME] /calibrate : {msg}")
        return {"success": False, "message_type": "calibration_error", "error": msg}

    async with _calibration_lock:
        if _calibration_proc is not None and _calibration_proc.poll() is None:
            logger.warning("[/calibrate] Une calibration est déjà en cours — requête ignorée")
            return {"success": False, "message_type": "calibration_busy",
                    "error": "Une calibration est déjà en cours.",
                    "data": {"pid": _calibration_proc.pid}}

        log_dir = Path("/app/experiments/current")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "calibration.log"
        cmd = [sys.executable, "-m", "calibration.cli", "run", "--iterations", str(iterations)]
        # Config adaptée à la disposition du conteneur (llm_module sous /opt, etc.).
        container_config = CALIBRATION_DIR / "config" / "gama_container.yaml"
        if container_config.exists():
            cmd[3:3] = ["--config", str(container_config)]

        log_file = open(log_path, "a", encoding="utf-8")
        try:
            log_file.write(
                f"\n{'='*70}\n[{datetime.now().isoformat()}] "
                f"Calibration lancée depuis GAMA — {iterations} cycle(s)\n{'='*70}\n")
            log_file.flush()
            _calibration_proc = subprocess.Popen(
                cmd, cwd=str(CALIBRATION_DIR),
                stdout=log_file, stderr=subprocess.STDOUT,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(f"[ALARME] /calibrate : échec du lancement du sous-processus : {exc}")
            return {"success": False, "message_type": "calibration_error", "error": str(exc)}
        finally:
            # Le sous-processus reçoit sa propre copie du descriptor au fork ;
            # le parent doit fermer la sienne pour ne pas la garder ouverte
            # pendant toute la durée de vie (potentiellement longue) du run.
            log_file.close()

    logger.info(f"[/calibrate] Calibration démarrée (pid={_calibration_proc.pid}, "
                f"cycles={iterations}) — journal : {log_path}")
    return {
        "success": True,
        "message_type": "calibration_started",
        "data": {"pid": _calibration_proc.pid, "iterations": iterations,
                 "log": str(log_path)},
    }


if __name__ == "__main__":
    """
    Main entry point for running the FastAPI application.

    Starts the server on host 0.0.0.0 and port 8000.
    This provides the HTTP API for LLM-GAMA integration.
    """
    uvicorn.run(app, host="0.0.0.0", port=8000)
