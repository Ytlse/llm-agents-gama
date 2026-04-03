"""
broker/redis_broker.py — Connexion Redis et helpers pour la persistance des tâches.

Redis remplit ici deux rôles distincts :
  1. Broker de messages pour Celery (file d'attente des tâches) → DB 1
  2. Stockage du statut/résultat des tâches (polling client)    → DB 0
  3. Compteurs RPM pour le load balancer                        → DB 0 (préfixe rpm:)
"""

from __future__ import annotations
import json
from typing import Optional

import redis.asyncio as aioredis
import redis as sync_redis

from llm_module.settings.models import Task, TaskStatus
from llm_module.tasks.config import settings


# ---------------------------------------------------------------------------
# Pool de connexions
# ---------------------------------------------------------------------------

# Pool async (utilisé par FastAPI)
_async_pool: Optional[aioredis.Redis] = None

# Pool sync (utilisé par le Worker Celery qui tourne en contexte synchrone)
_sync_pool: Optional[sync_redis.Redis] = None


def get_async_redis() -> aioredis.Redis:
    global _async_pool
    if _async_pool is None:
        _async_pool = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _async_pool


def get_sync_redis() -> sync_redis.Redis:
    global _sync_pool
    if _sync_pool is None:
        _sync_pool = sync_redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _sync_pool


# ---------------------------------------------------------------------------
# Clés Redis
# ---------------------------------------------------------------------------

TASK_KEY_PREFIX = "task:"
RPM_KEY_PREFIX  = "rpm:"


def _task_key(task_id: str) -> str:
    return f"{TASK_KEY_PREFIX}{task_id}"


def _rpm_key(provider: str) -> str:
    """
    Clé Redis pour le compteur RPM d'un fournisseur.
    On utilise un TTL de 60 s — Redis réinitialise automatiquement le compteur.
    """
    return f"{RPM_KEY_PREFIX}{provider}"


# ---------------------------------------------------------------------------
# CRUD tâches (async — utilisé par l'API Gateway)
# ---------------------------------------------------------------------------

async def save_task_async(task: Task) -> None:
    r = get_async_redis()
    await r.set(_task_key(task.task_id), task.model_dump_json(), ex=3600)


async def get_task_async(task_id: str) -> Optional[Task]:
    r = get_async_redis()
    raw = await r.get(_task_key(task_id))
    if raw is None:
        return None
    return Task.model_validate_json(raw)


# ---------------------------------------------------------------------------
# CRUD tâches (sync — utilisé par le Worker Celery)
# ---------------------------------------------------------------------------

def save_task_sync(task: Task) -> None:
    r = get_sync_redis()
    r.set(_task_key(task.task_id), task.model_dump_json(), ex=3600)


def get_task_sync(task_id: str) -> Optional[Task]:
    r = get_sync_redis()
    raw = r.get(_task_key(task_id))
    if raw is None:
        return None
    return Task.model_validate_json(raw)


# ---------------------------------------------------------------------------
# Compteurs RPM (sync — utilisé par le load balancer depuis le Worker)
# ---------------------------------------------------------------------------

def increment_rpm(provider: str) -> int:
    """
    Incrémente le compteur RPM d'un fournisseur.
    Le TTL de 60 s garantit la réinitialisation automatique toutes les minutes.
    Retourne la valeur courante après incrément.
    """
    r = get_sync_redis()
    key = _rpm_key(provider)
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, 60)
    results = pipe.execute()
    return int(results[0])


def get_rpm(provider: str) -> int:
    """Retourne le compteur RPM actuel d'un fournisseur (0 si inexistant)."""
    r = get_sync_redis()
    val = r.get(_rpm_key(provider))
    return int(val) if val else 0
