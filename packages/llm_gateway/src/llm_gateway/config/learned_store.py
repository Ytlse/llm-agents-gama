"""config/learned_store.py — quel store de limites apprises pour ces réglages."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from llm_gateway.config.settings import GatewaySettings
from llm_gateway.infra.memory.learned_limits import FileLearnedLimits, InMemoryLearnedLimits
from llm_gateway.ports.learned_limits import LearnedLimits


def build_learned_store(settings: GatewaySettings, sync_redis_client: Any = None) -> LearnedLimits:
    """Redis (partagé entre processus), fichier JSON (sans Redis) ou mémoire (rien n'est retenu)."""
    kind = settings.learned_limits
    if kind == "redis" and sync_redis_client is not None:
        from llm_gateway.infra.redis.learned_limits import RedisLearnedLimits

        return RedisLearnedLimits(sync_redis_client)
    if kind == "file" or (kind == "redis" and sync_redis_client is None):
        path = settings.learned_limits_file or Path(settings.telemetry.workdir) / "learned_limits.json"
        return FileLearnedLimits(path)
    return InMemoryLearnedLimits()


__all__ = ["build_learned_store"]
