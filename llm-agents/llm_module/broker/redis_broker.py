"""
broker/redis_broker.py — Connexion Redis et helpers pour la persistance des tâches.

Redis remplit ici deux rôles distincts :
  1. Broker de messages pour Celery (file d'attente des tâches) → DB 1 (via celery_broker_url)
  2. Stockage du statut/résultat des tâches (polling client)    → DB 0 (via redis_url)
  3. Compteurs RPM pour le load balancer                        → DB 0 (préfixe rpm:)

Note : les numéros de DB effectifs dépendent des variables d'environnement redis_url
et celery_broker_url.
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

TASK_KEY_PREFIX     = "task:"
RPM_KEY_PREFIX      = "rpm:"
COOLDOWN_KEY_PREFIX = "cooldown:"
BATCH_QUEUE_PREFIX  = "batch:"


def _task_key(task_id: str) -> str:
    return f"{TASK_KEY_PREFIX}{task_id}"


def _rpm_key(provider: str) -> str:
    """
    Clé Redis pour le compteur RPM d'un fournisseur.
    TTL de 60 s — Redis réinitialise automatiquement le compteur toutes les minutes.
    """
    return f"{RPM_KEY_PREFIX}{provider}"


def _cooldown_key(provider: str) -> str:
    return f"{COOLDOWN_KEY_PREFIX}{provider}"


def _batch_queue_key(batch_key: str) -> str:
    return f"{BATCH_QUEUE_PREFIX}{batch_key}"


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
    count = pipe.incr(key)
    if count == 1:
        r.expire(key, 60)
    results = pipe.execute()
    return int(results[0])


def get_rpm(provider: str) -> int:
    """Retourne le compteur RPM actuel d'un fournisseur (0 si inexistant)."""
    r = get_sync_redis()
    val = r.get(_rpm_key(provider))
    return int(val) if val else 0


# ---------------------------------------------------------------------------
# Cooldown (sync — utilisé pour exclure temporairement un fournisseur)
# ---------------------------------------------------------------------------

def mark_cooldown(provider: str, timeout: int = 60) -> None:
    """Place un fournisseur en quarantaine pour une durée donnée."""
    r = get_sync_redis()
    r.set(_cooldown_key(provider), "1", ex=timeout)


def is_in_cooldown(provider: str) -> bool:
    """Vérifie si un fournisseur est actuellement en quarantaine."""
    r = get_sync_redis()
    return r.exists(_cooldown_key(provider)) > 0


# ---------------------------------------------------------------------------
# Micro-Batching (sync / async)
# ---------------------------------------------------------------------------

async def add_task_to_batch_async(batch_key: str, task_id: str) -> int:
    """Ajoute une tâche au bout de la file de batch et retourne la taille de la file."""
    r = get_async_redis()
    key = _batch_queue_key(batch_key)
    await r.rpush(key, task_id)
    await r.expire(key, 3600)
    return await r.llen(key)


def pop_tasks_from_batch_sync(batch_key: str, max_agents: int) -> list[Task]:
    """Dépile les tâches de la file de batch jusqu'à atteindre la limite d'agents."""
    r = get_sync_redis()
    key = _batch_queue_key(batch_key)
    selected_tasks = []
    current_agents_count = 0

    while True:
        task_id = r.lpop(key)
        if not task_id:
            break

        task = get_task_sync(task_id)
        if not task:
            continue

        agents_in_task = len(task.request.agents)
        if current_agents_count + agents_in_task > max_agents and current_agents_count > 0:
            # Dépasse la limite et on a déjà des tâches : on remet la tâche en tête de file
            r.lpush(key, task_id)
            break

        selected_tasks.append(task)
        current_agents_count += agents_in_task

    return selected_tasks


def requeue_tasks_sync(batch_key: str, task_ids: list[str]) -> None:
    """En cas d'erreur de réseau (retry), replace les tâches en tête de file."""
    if not task_ids:
        return
    r = get_sync_redis()
    r.lpush(_batch_queue_key(batch_key), *task_ids)
