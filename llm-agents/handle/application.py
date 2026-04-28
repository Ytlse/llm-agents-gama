"""
FastAPI application for LLM-GAMA integration.

This module provides the HTTP API and WebSocket communication layer between
the GAMA simulation and external LLM (Large Language Model) systems. It handles
world initialization, synchronization, and real-time observation/action exchange.
"""

import asyncio
import json
import os
import orjson
import time
from datetime import datetime
import httpx
import uvicorn
from loguru import logger
from helper import setup_logging, humanize_date
from gama_models import GamaPersonData, MessageResponse, MessageType, WorldInitRequest, WorldInitResponse, WorldSyncRequest
from urban_mobility_agents.core.scenario import BaseScenario, Observation
from handle.websocket import WebSocketClient
from settings import settings
import traceback
from fastapi import FastAPI, Request, Response
from fastapi.responses import ORJSONResponse
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST, REGISTRY
from urban_mobility_agents.factory.factory import init_static_data, init_dynamic_scenario

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
_last_sync_wall_time: float  = 0.0
_sim_init_wall_time: float   = 0.0
_sim_step_count: int         = 0
_last_logical_time: int      = 0

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
    from fastapi import HTTPException
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
        # Initialize WebSocket client for GAMA communication
        self.websocket_client = WebSocketClient(settings.server.gama_ws_url)
        self.websocket_client.on_message = self.handle_message

    def set_scenario(self, scenario: BaseScenario):
        """Set the active simulation scenario."""
        self.scenario = scenario

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

                if sent > 0:
                    logger.info(f"WebSocket loop sent {sent} message(s) to {self.action_topic}")
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
            traceback.print_exc()
            logger.error(f"Error handling message: {e}")

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
            traceback.print_exc()
            logger.error(f"Error processing observation: {e}")

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

    logger.info(f"[/init] Publishing world data — bootstrap at {humanize_date(request.timestamp)}")

    await loop_container.send_log(f"Création de la population (taille demandée : {request.population_size or 'défaut'})...")

    min_lon, min_lat, max_lon, max_lat = static_data.gtfs_data.get_bounding_box()
    buffer = 0.05
    gtfs_bbox = (min_lon - buffer, min_lat - buffer, max_lon + buffer, max_lat + buffer)
    await _trigger_eqasim_generation(request.population_size or settings.data.population_size, bbox=gtfs_bbox)

    scenario = init_dynamic_scenario(
        static_data,
        population_size=request.population_size,
        part_of_llm_agents=request.part_of_llm_based_agents,
        long_term_memory_enabled=request.long_term_memory_enabled,
        long_term_self_reflect_enabled=request.long_term_self_reflect_enabled,
    )
    loop_container.set_scenario(scenario)

    await loop_container.send_log("Pré-calcul du premier itinéraire pour chaque agent via OTP...")

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

    await loop_container.send_log("Initialisation terminée ! Envoi des agents à GAMA.")

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
        await loop_container.scenario.reflect_all(request.timestamp)
        return MessageResponse(
            data="reflected",
            success=True,
        )
    else:
        return MessageResponse(
            success=False,
            error="Scenario not set"
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
    """
    Synchronize the world state with idle population data.

    Reads the raw body to remain compatible with GAMA's Java HTTP client,
    which sends h2c upgrade headers that prevent uvicorn/h11 from reading
    the body. hypercorn handles h2c natively, so the body is always available.
    """
    global _last_sync_wall_time, _sim_step_count, _last_logical_time
    now = time.time()
    if _last_sync_wall_time > 0:
        SIM_STEP_INTERVAL.set(now - _last_sync_wall_time)
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

    logger.info(f"Synchronizing world at timestamp: {request.timestamp} ({humanize_date(request.timestamp)})")

    if loop_container.scenario:
        await loop_container.scenario.sync(request.timestamp, idle_people=request.idle_people)
        try:
            people = loop_container.scenario.population.get_people_list()
            inactive = sum(1 for p in people if p.state.last_location is None)
            ready    = sum(1 for p in people if p.state.last_location is not None
                          and p.state.heading_to is None and not p.state.scheduling_in_progress)
            active   = sum(1 for p in people if p.state.scheduling_in_progress or p.state.heading_to is not None)
            AGENT_STATES.labels(state='inactive').set(inactive)
            AGENT_STATES.labels(state='ready').set(ready)
            AGENT_STATES.labels(state='active').set(active)
            SIM_LOGICAL_TIME.set(request.timestamp)
            if _last_logical_time > 0 and request.timestamp > _last_logical_time:
                SIM_STEP_LOGICAL_DURATION.set(request.timestamp - _last_logical_time)
        except Exception:
            pass
        _last_logical_time = request.timestamp
        return MessageResponse(data="synchronized", success=True)
    else:
        return MessageResponse(success=False, error="Scenario not set")


if __name__ == "__main__":
    """
    Main entry point for running the FastAPI application.

    Starts the server on host 0.0.0.0 and port 8000.
    This provides the HTTP API for LLM-GAMA integration.
    """
    uvicorn.run(app, host="0.0.0.0", port=8000)
