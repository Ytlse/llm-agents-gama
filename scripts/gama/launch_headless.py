"""Launcher headless : charge et joue l'expériment GAMA via le protocole GAMA Server.

Lancé par `make run OFFLINE=1` À L'INTÉRIEUR du conteneur controller (la lib
`websockets` y est installée et le service `gama` y est résolvable) :

    docker compose exec -T controller python /app/scripts/gama/launch_headless.py

Séquence :
  1. connexion à ws://gama:6868 (avec retries : GAMA Server met ~10-20 s à démarrer)
  2. `load` du modèle avec injection des paramètres réseau (http_url/http_port
     → http://controller:8002, déclarés comme parameters de l'expériment `e`)
  3. `play`, puis relais de la console GAMA sur stdout

IMPORTANT : le process doit rester vivant pendant toute la simulation — GAMA
Server tue les expériences dont le client WebSocket s'est déconnecté. L'arrêt
propre du run passe par `make down` (ou l'arrêt du service gama).
"""

import asyncio
import json
import os
import sys

import websockets

GAMA_SERVER_URL = os.environ.get("GAMA_SERVER_URL", "ws://gama:6868")
MODEL_PATH = os.environ.get("GAMA_MODEL_PATH", "/GAMA/CityTransport/models/City.gaml")
EXPERIMENT = os.environ.get("GAMA_EXPERIMENT", "e")
CONTROLLER_HTTP_URL = os.environ.get("GAMA_HTTP_URL", "http://controller")
CONTROLLER_HTTP_PORT = int(os.environ.get("GAMA_HTTP_PORT", "8002"))
CONNECT_TIMEOUT_S = int(os.environ.get("GAMA_CONNECT_TIMEOUT_S", "180"))

# Types de messages du protocole GAMA Server signalant un échec de commande.
ERROR_TYPES = {
    "MalformedRequest",
    "UnableToExecuteRequest",
    "GamaServerError",
    "SimulationError",
    "SimulationErrorDialog",
    "RuntimeError",
}

# Heartbeats de statut (un par top d'horloge) : jamais relayés dans le log,
# même si un futur `load` réactive "status".
NOISE_TYPES = {"SimulationStatusInform", "SimulationStatus"}


def log(msg: str) -> None:
    print(msg, flush=True)


async def connect_with_retries() -> websockets.WebSocketClientProtocol:
    """GAMA Server n'est prêt que quelques secondes après le départ du conteneur."""
    elapsed = 0
    while True:
        try:
            ws = await websockets.connect(GAMA_SERVER_URL, max_size=10**7)
            log(f"✅ Connecté à GAMA Server ({GAMA_SERVER_URL})")
            return ws
        except Exception as exc:
            if elapsed >= CONNECT_TIMEOUT_S:
                log(f"[ALARME] GAMA Server injoignable après {CONNECT_TIMEOUT_S}s : {exc}")
                raise
            log(f"⏳ GAMA Server pas encore prêt ({exc}), retry dans 5s...")
            await asyncio.sleep(5)
            elapsed += 5


async def recv_json(ws) -> dict:
    raw = await ws.recv()
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return {"type": "Raw", "content": raw}


async def wait_command_result(ws) -> dict:
    """Consomme les messages jusqu'au résultat de la dernière commande envoyée."""
    while True:
        msg = await recv_json(ws)
        mtype = msg.get("type")
        if mtype == "CommandExecutedSuccessfully":
            return msg
        if mtype in ERROR_TYPES:
            log(f"[ALARME] GAMA Server a rejeté la commande : {json.dumps(msg, ensure_ascii=False)}")
            raise RuntimeError(f"GAMA Server error: {mtype}")
        # Messages intermédiaires (console…) : on relaie et on continue.
        if mtype not in NOISE_TYPES:
            log(f"[gama] {json.dumps(msg, ensure_ascii=False)}")


async def main() -> None:
    ws = await connect_with_retries()

    greeting = await recv_json(ws)
    log(f"[gama] {json.dumps(greeting, ensure_ascii=False)}")

    load_cmd = {
        "type": "load",
        "model": MODEL_PATH,
        "experiment": EXPERIMENT,
        "console": True,
        # status: GAMA émet un SimulationStatusInform par top d'horloge — pur
        # heartbeat qui noie le log, on ne s'y abonne pas.
        "status": False,
        "dialog": True,
        "parameters": [
            {"type": "string", "name": "http_url", "value": CONTROLLER_HTTP_URL},
            {"type": "int", "name": "http_port", "value": CONTROLLER_HTTP_PORT},
        ],
    }
    log(f"📦 load {MODEL_PATH} (expériment '{EXPERIMENT}', controller={CONTROLLER_HTTP_URL}:{CONTROLLER_HTTP_PORT})")
    await ws.send(json.dumps(load_cmd))
    result = await wait_command_result(ws)
    exp_id = result.get("content")
    log(f"✅ Expériment chargé (exp_id={exp_id})")

    await ws.send(json.dumps({"type": "play", "exp_id": exp_id, "sync": False}))
    await wait_command_result(ws)
    log("▶️  Simulation lancée — la connexion reste ouverte (l'arrêt passe par `make down`)")

    # Relais de la console GAMA jusqu'à la fin du run. Une erreur de simulation
    # est signalée mais n'interrompt pas le relais : le modèle fait `pause` de
    # lui-même à simulation_max_days et le controller termine ses écritures.
    while True:
        msg = await recv_json(ws)
        mtype = msg.get("type")
        if mtype in NOISE_TYPES:
            continue
        prefix = "[ALARME] " if mtype in ERROR_TYPES else ""
        log(f"{prefix}[gama] {json.dumps(msg, ensure_ascii=False)}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("Arrêt du launcher (KeyboardInterrupt)")
    except websockets.exceptions.ConnectionClosed as exc:
        log(f"[ALARME] Connexion GAMA Server fermée : {exc} — l'expériment associé est arrêté par GAMA")
        sys.exit(1)
    except Exception as exc:
        log(f"[ALARME] Launcher headless en échec : {exc}")
        sys.exit(1)
