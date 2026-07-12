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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

_configured = False


def configure_logging(level: str | None = None) -> None:
    """
    Remplace le handler loguru par défaut (DEBUG) par un handler qui respecte
    LOG_LEVEL (défaut INFO). Idempotent — appelé par les entrypoints.

    Si la variable d'environnement SERVICE_NAME est définie, ajoute en plus un
    sink fichier `APP_WORKDIR/<SERVICE_NAME>.log` (format aligné sur app.log du
    controller) afin que les logs de chaque conteneur (api, worker, …) soient
    centralisés dans le dossier du run et agrégeables par les outils de debug.
    """
    global _configured
    if _configured:
        return
    _configured = True
    lvl = level or os.environ.get("LOG_LEVEL", "INFO")
    logger.remove()
    logger.add(
        sys.stderr,
        level=lvl,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    )
    _add_service_file_sink(lvl)


def _add_service_file_sink(level: str) -> None:
    """Sink fichier par service dans APP_WORKDIR, activé si SERVICE_NAME est défini.

    Format identique aux logs du controller (`app.log`) pour que la même regex
    d'agrégation fonctionne. Tolérant : toute erreur (workdir absent, droits) est
    silencieuse — le logging console reste opérationnel.
    """
    service = os.environ.get("SERVICE_NAME")
    if not service:
        return
    try:
        workdir = _workdir()
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

def _workdir() -> Path:
    return Path(os.environ.get("APP_WORKDIR", "."))


def log_llm_error(
    task_id: str,
    provider: str,
    error_type: str,
    error_message: str,
    http_status: int | None = None,
    ratelimit_reset: str | None = None,
) -> None:
    """
    Enregistre une erreur LLM dans APP_WORKDIR/llm_errors.jsonl.
    """
    log_file = _workdir() / "llm_errors.jsonl"

    entry = {
        "time": datetime.now(timezone.utc).isoformat(),
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
) -> None:
    """
    Enregistre un échange complet avec le LLM dans un fichier JSONL.
    Chemin : LLM_EXCHANGES_FILE (env), sinon APP_WORKDIR/llm_exchanges.jsonl.

    sim_ts : timestamp Unix *simulé* (heure du monde GAMA) de la décision, pour pouvoir
    ventiler la consommation par jour de simulation (l'horloge murale `time` ne le permet pas).
    """
    override = os.environ.get("LLM_EXCHANGES_FILE")
    log_file = Path(override) if override else _workdir() / "llm_exchanges.jsonl"

    entry = {
        "time": datetime.now(timezone.utc).isoformat(),
        "sim_ts": sim_ts,
        "sim_day": datetime.fromtimestamp(sim_ts, tz=timezone.utc).strftime("%Y-%m-%d") if sim_ts else None,
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
