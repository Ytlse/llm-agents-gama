"""
telemetry/logger.py — Logging structuré via structlog.

Chaque log contient automatiquement :
  - timestamp ISO8601
  - niveau
  - module source
  - tous les champs extra passés en kwargs

Format JSON en production, format coloré lisible en développement.
"""

from __future__ import annotations
import logging
import os
import sys
from pathlib import Path
from typing import Any

import structlog

# ---------------------------------------------------------------------------
# Configuration de structlog
# ---------------------------------------------------------------------------

_ENV = os.getenv("APP_ENV", "development")

def _configure_logging() -> None:
    """Configure structlog une seule fois au démarrage."""

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
    ]

    if _ENV == "production":
        # JSON pour collecteurs (Loki, CloudWatch, etc.)
        renderer = structlog.processors.JSONRenderer()
    else:
        # Lisible en dev
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [console_handler, file_handler]
    root.setLevel(logging.DEBUG if _ENV != "production" else logging.INFO)


_configure_logging()


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Retourne un logger structlog lié au module demandeur."""
    return structlog.get_logger(name)


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
    logger = get_logger("telemetry.llm_call")
    log_fn = logger.info if status == "success" else logger.error

    log_fn(
        "llm_call_completed",
        task_id=task_id,
        provider=provider,
        status=status,
        latency_ms=round(latency_ms, 2),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        http_status=http_status,
        error=error,
    )
