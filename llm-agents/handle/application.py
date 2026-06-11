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
import orjson
import time
from datetime import datetime
from pathlib import Path
import httpx
import numpy as np
import uvicorn
from loguru import logger
from helper import setup_logging, humanize_date, to_timestamp_based_on_day
from models import Location
from gama_models import GamaPersonData, MessageResponse, MessageType, WorldInitRequest, WorldInitResponse, WorldSyncRequest
from urban_mobility_agents.core.scenario import BaseScenario, Observation
from handle.websocket import WebSocketClient
from settings import settings, FactorySettings
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import ORJSONResponse
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST, REGISTRY
from urban_mobility_agents.factory.factory import init_static_data, init_dynamic_scenario
from urban_mobility_agents.utils.pipeline_logger import PipelineLogger
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
_last_sync_wall_time: float          = 0.0
_last_sync_response_wall_time: float = 0.0   # timestamp of the last /sync response sent
_sim_init_wall_time: float           = 0.0
_sim_step_count: int                 = 0
_last_logical_time: int              = 0
_last_backpressure_in_progress: int  = 0     # in_progress_count used for the previous sync's sleep
_last_backpressure_min_interval: float = 0.0 # min_interval computed for the previous sync's sleep

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
            logger.warning(f"[trace][app._init_osmnx_cache] calling init_otp_persistent_cache({otp_cache_dir})")
            init_otp_persistent_cache(otp_cache_dir)
        else:
            logger.warning("[trace][app._init_osmnx_cache] OTP cache init SKIPPED (condition false)")

    def _is_eqasim_format(data: list) -> bool:
        # Eqasim identity has no "name" key; Pydantic PersonalIdentity dump does
        return bool(data) and "name" not in data[0].get("identity", {})

    data = None
    if os.path.exists(workdir_path):
        with open(workdir_path, encoding="utf-8") as f:
            data = json.load(f)
        if not _is_eqasim_format(data):
            logger.info(f"[population] File in old Pydantic format — regenerating: {workdir_path}")
            data = None
        else:
            logger.info(f"[population] File exists — reusing: {workdir_path}")
            _init_osmnx_cache()
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
            raw_data = _random.sample(raw_data, population_size)
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
            logger.warning("[population] ajuster_planning: %s", exc)
    if sched_errors:
        logger.warning("[population] Step 5: %d person(s) with unresolved schedule conflicts", sched_errors)
    else:
        logger.info("[population] Step 5: all schedules adjusted successfully")

    tmp_path = workdir_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.rename(tmp_path, workdir_path)
    logger.info(f"[population] Population written to {workdir_path} ({len(data)} agents)")

    _init_osmnx_cache()
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

    def __init__(self):
        self.client = None
        self.scenario = None
        self._worker_task: asyncio.Task | None = None
        # Initialize WebSocket client for GAMA communication
        self.websocket_client = WebSocketClient(settings.server.gama_ws_url)
        self.websocket_client.on_message = self.handle_message

    def set_scenario(self, scenario: BaseScenario):
        """Set the active simulation scenario, inject push_fn and start the Worker."""
        # Cancel the previous Worker if still running (e.g. successive /test/init calls)
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()

        self.scenario = scenario

        # Injecter la fonction de push WebSocket direct dans le scénario
        async def _direct_push(action):
            await self.websocket_client.send_json({
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

    async def publish_loop(self):
        """
        Main publishing loop that sends action messages to GAMA via WebSocket.

        Continuously checks for new messages from the scenario and publishes them
        to the GAMA simulation. Handles connection failures and retries.

        `pending` is declared outside the try/except so that any unexpected
        exception (e.g. model_dump failure) never causes message loss: the
        unsent items remain in the buffer and are retried on the next iteration.
        """
        pending: list = []
        while True:
            try:
                # Only fetch new messages when the pending buffer is empty.
                if not pending and self.scenario and await self.scenario.has_messages():
                    pending = await self.scenario.pop_all_messages()

                sent = 0
                while pending:
                    message = pending[0]
                    payload = message.model_dump()
                    success = await self.websocket_client.send_json({
                        "topic": self.action_topic,
                        "payload": payload,
                    })
                    if not success:
                        # WebSocket not ready — keep in buffer, retry next tick
                        logger.warning(
                            f"WebSocket not connected, will retry {len(pending)} pending message(s)"
                        )
                        break
                    pending.pop(0)
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
                await asyncio.sleep(self.reconnect_interval)

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

@app.on_event("startup")
async def startup_event():
    """
    FastAPI startup event handler.

    Initializes WebSocket connection and starts background tasks for
    real-time communication with GAMA simulation.
    """
    await loop_container.greeting()
    asyncio.create_task(loop_container.websocket_client.run_with_reconnect())
    asyncio.create_task(loop_container.publish_loop())

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

    logger.info(f"INITIALISATION 2/{_N_STEPS} Population prête — {population_json_path}")
    await loop_container.send_log(f"[2/{_N_STEPS}] Population prête.")

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

    logger.info(f"INITIALISATION 4/{_N_STEPS} Pré-calcul du premier itinéraire pour chaque agent (bootstrap)")
    await loop_container.send_log(f"[4/{_N_STEPS}] Pré-calcul des premiers itinéraires...")

    if request.timestamp > 0:
        await scenario.bootstrap_all_agents(timestamp=request.timestamp)

    people = scenario.population.get_people_list()
    SIM_AGENTS_TOTAL.set(len(people))
    global _sim_init_wall_time, _sim_step_count, _last_logical_time
    _sim_init_wall_time = time.time()
    _sim_step_count = 0
    _last_logical_time = request.timestamp if request.timestamp > 0 else 0
    SIM_STEP_COUNT.set(0)
    SIM_REAL_ELAPSED.set(0)
    if request.timestamp > 0:
        SIM_LOGICAL_TIME.set(request.timestamp)
    for _state in ('inactive', 'ready', 'active'):
        AGENT_STATES.labels(state=_state).set(0)
    AGENT_STATES.labels(state='inactive').set(len(people))

    _init_duration = time.time() - _t_init_start
    from urban_mobility_agents.simulation_controller import _format_cache_hit_rates
    _cache_str = _format_cache_hit_rates()
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
    """
    Synchronize the world state with idle population data.

    Reads the raw body to remain compatible with GAMA's Java HTTP client,
    which sends h2c upgrade headers that prevent uvicorn/h11 from reading
    the body. hypercorn handles h2c natively, so the body is always available.
    """
    global _last_sync_wall_time, _last_sync_response_wall_time, _sim_step_count, _last_logical_time, _last_backpressure_in_progress, _last_backpressure_min_interval
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
            _agent_state_log.record(_sim_step_count, request.timestamp, inactive, ready, active)
        except Exception:
            pass
        in_progress_before_sync = loop_container.scenario.activities_to_compute_count
        await loop_container.scenario.sync(request.timestamp, _t_sync=now, _t_parse=_t_parse_end)
        try:
            SIM_LOGICAL_TIME.set(request.timestamp)
            if _last_logical_time > 0 and request.timestamp > _last_logical_time:
                sim_delta = request.timestamp - _last_logical_time
                SIM_STEP_LOGICAL_DURATION.set(sim_delta)
                if real_delta > 0:
                    SIM_WALL_CLOCK_RATIO.set(sim_delta / real_delta)
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
        _scale = settings.world.min_internal_coeff_scale
        _k     = settings.world.min_internal_coeff_k
        _cap   = settings.world.min_internal_coeff_cap
        dynamic_scale = _scale * (settings.data.population_size / 100.0)
        min_interval = min(_cap, (in_progress_count / dynamic_scale) ** _k)
        logger.info(f"Activités à calculer: {in_progress_count} — applying min_interval={min_interval:.2f}s")
        if min_interval > 0 and _last_sync_response_wall_time > 0:
            remaining = min_interval - (time.time() - _last_sync_response_wall_time)
            if remaining > 0:
                await asyncio.sleep(remaining)
        _last_backpressure_in_progress = in_progress_count
        _last_backpressure_min_interval = min_interval
        _last_sync_response_wall_time = time.time()
        return MessageResponse(data="synchronized", success=True)
    else:
        logger.debug("[/sync] Scenario not ready yet — init still in progress, skipping")
        return MessageResponse(data="not_ready", success=True)


if __name__ == "__main__":
    """
    Main entry point for running the FastAPI application.

    Starts the server on host 0.0.0.0 and port 8000.
    This provides the HTTP API for LLM-GAMA integration.
    """
    uvicorn.run(app, host="0.0.0.0", port=8000)
