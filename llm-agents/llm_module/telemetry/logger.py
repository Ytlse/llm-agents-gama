"""
telemetry/logger.py — Logging unifié via loguru.

Chaque log contient automatiquement :
  - timestamp
  - niveau
  - module source (via {name} loguru)
  - message

log_llm_exchange() écrit un JSONL dans workdir/llm_exchanges.jsonl :
  - time, task_id, provider, tokens_in, tokens_out, messages (input), response (output)
"""

from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger


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
# Écrit dans workdir/llm_exchanges.jsonl
# ---------------------------------------------------------------------------

def log_llm_exchange(
    task_id: str,
    provider: str,
    messages: list[dict],
    response: Any,
    tokens_in: int,
    tokens_out: int,
) -> None:
    """
    Enregistre un échange complet avec le LLM dans un fichier JSONL.
    Le fichier est placé dans APP_WORKDIR (env var), ou dans le répertoire courant par défaut.
    """
    workdir = os.environ.get("APP_WORKDIR", ".")
    log_file = Path(workdir) / "llm_exchanges.jsonl"

    entry = {
        "time": datetime.now(timezone.utc).isoformat(),
        "task_id": task_id,
        "provider": provider,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "messages": messages,
        "response": response,
    }

    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except OSError as e:
        logger.warning(f"Impossible d'écrire dans {log_file}: {e}")
