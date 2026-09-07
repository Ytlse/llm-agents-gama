"""
telemetry/logger.py — Logging unifié via loguru.

La configuration du handler est un geste explicite des entrypoints
(create_app, worker Celery) via configure_logging() — plus jamais un effet
de bord d'import de ce module.

log_llm_exchange() écrit un JSONL dans le fichier désigné par la variable
d'environnement LLM_EXCHANGES_FILE, ou à défaut APP_WORKDIR/llm_exchanges.jsonl :
  - time, task_id, provider, tokens_in, tokens_out, messages (input), response (output)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

_configured = False


def configure_logging(telemetry: Any = None, level: str | None = None) -> None:
    """
    Remplace le handler loguru par défaut (DEBUG) par un handler au niveau demandé.
    Idempotent — appelé par les points d'entrée (create_app, worker, CLI), jamais par un import.

    `telemetry` : les réglages `GatewaySettings.telemetry` (log_level, log_format, service_name,
    workdir). Sans réglages, repli sur les anciennes variables d'environnement (LOG_LEVEL,
    SERVICE_NAME, APP_WORKDIR), dépréciées. Si un nom de service est connu, un sink fichier
    `<workdir>/<service>.log` centralise les logs du conteneur dans le dossier du run.
    """
    global _configured
    if _configured:
        return
    _configured = True
    lvl = level or _attr(telemetry, "log_level") or os.environ.get("LOG_LEVEL", "INFO")
    logger.remove()
    if _attr(telemetry, "log_format") == "json":
        logger.add(sys.stderr, level=lvl, serialize=True)
    else:
        logger.add(
            sys.stderr,
            level=lvl,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        )
    _add_service_file_sink(lvl, telemetry)


def _attr(telemetry: Any, name: str) -> Any:
    """Lecture tolérante d'un réglage de télémétrie (objet ou None)."""
    return getattr(telemetry, name, None) if telemetry is not None else None


def _add_service_file_sink(level: str, telemetry: Any = None) -> None:
    """Sink fichier par service dans le workdir, activé si un nom de service est défini.

    Format identique aux logs du controller (`app.log`) pour que la même regex
    d'agrégation fonctionne. Tolérant : toute erreur (workdir absent, droits) est
    silencieuse — le logging console reste opérationnel.
    """
    service = _attr(telemetry, "service_name") or os.environ.get("SERVICE_NAME")
    if not service:
        return
    try:
        workdir = _workdir(telemetry)
        if not workdir.exists():
            return
        logger.add(
            str(workdir / f"{service}.log"),
            level=level,
            rotation="10 MB",
            retention="7 days",
            enqueue=True,  # écritures thread/process-safe (worker multi-threads)
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name} - {message}",
        )
    except OSError:
        pass


def get_logger(name: str):
    """Retourne le logger loguru. Le paramètre name est conservé pour compatibilité API."""
    return logger


# ---------------------------------------------------------------------------
# Helper pour loguer les métriques d'un appel LLM complété
# ---------------------------------------------------------------------------

def log_llm_call(
    task_id: str,
    provider: str,
    status: str,        # "success" | "failed"
    latency_ms: float,
    tokens_in: int,
    tokens_out: int,
    http_status: int,
    error: str | None = None,
) -> None:
    msg = (
        f"llm_call_completed | task_id={task_id} provider={provider} status={status} "
        f"latency_ms={latency_ms:.1f} tokens_in={tokens_in} tokens_out={tokens_out} "
        f"http_status={http_status}"
    )
    if error:
        msg += f" error={error}"

    if status == "success":
        logger.info(msg)
    else:
        logger.error(msg)


# ---------------------------------------------------------------------------
# Log des échanges LLM (prompt envoyé + réponse + tokens)
# ---------------------------------------------------------------------------

def _workdir(telemetry: Any = None) -> Path:
    """Dossier du run : `telemetry.workdir`, sinon APP_WORKDIR (déprécié), sinon le répertoire courant."""
    configured = _attr(telemetry, "workdir")
    if configured is not None:
        return Path(configured)
    return Path(os.environ.get("APP_WORKDIR", "."))


def log_llm_error(
    task_id: str,
    provider: str,
    error_type: str,
    error_message: str,
    http_status: int | None = None,
    ratelimit_reset: str | None = None,
    telemetry: Any = None,
) -> None:
    """
    Enregistre une erreur LLM dans <workdir>/llm_errors.jsonl.
    """
    log_file = _workdir(telemetry) / "llm_errors.jsonl"

    entry = {
        "time": datetime.now(UTC).isoformat(),
        "task_id": task_id,
        "provider": provider,
        "error_type": error_type,
        "error_message": error_message,
        "http_status": http_status,
    }
    if ratelimit_reset is not None:
        entry["ratelimit_reset"] = ratelimit_reset

    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except OSError as e:
        logger.warning(f"Impossible d'écrire dans {log_file}: {e}")


def log_llm_exchange(
    task_id: str,
    provider: str,
    messages: list[dict],
    response: Any,
    tokens_in: int,
    tokens_out: int,
    category: str = "",
    sim_ts: float | None = None,
    telemetry: Any = None,
) -> None:
    """
    Enregistre un échange complet avec le LLM dans un fichier JSONL.
    Chemin : `telemetry.exchanges_file`, sinon LLM_EXCHANGES_FILE (env, déprécié), sinon
    <workdir>/llm_exchanges.jsonl.

    sim_ts : timestamp Unix *simulé* (heure du monde GAMA) de la décision, pour pouvoir
    ventiler la consommation par jour de simulation (l'horloge murale `time` ne le permet pas).
    """
    configured = _attr(telemetry, "exchanges_file")
    override = os.environ.get("LLM_EXCHANGES_FILE")
    if configured is not None:
        log_file = Path(configured)
    elif override:
        log_file = Path(override)
    else:
        log_file = _workdir(telemetry) / "llm_exchanges.jsonl"

    entry = {
        "time": datetime.now(UTC).isoformat(),
        "sim_ts": sim_ts,
        # `tz=timezone.utc` sur un horodatage de l'horloge de GAMA rend le jour MURAL de
        # la simulation, indépendamment du `TZ` du processus (c'est la définition de
        # `llm-agents/sim_clock.py:wall_clock`, que ce paquet — séparé — n'importe pas).
        "sim_day": datetime.fromtimestamp(sim_ts, tz=UTC).strftime("%Y-%m-%d") if sim_ts else None,
        "task_id": task_id,
        "provider": provider,
        "category": category,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "messages": messages,
        "response": response,
    }

    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str, indent=2) + "\n")
    except OSError as e:
        logger.warning(f"Impossible d'écrire dans {log_file}: {e}")
