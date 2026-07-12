"""
infra/redis/batch_queue.py — RedisBatchQueue : files de micro-batching.

Sorted Set `batch:{batch_key}` trié par priority_score (min departure_time) ;
flag SETNX `batch_sched:{batch_key}` pour dédupliquer le dispatch différé.
"""

from __future__ import annotations
from typing import Optional

import redis as sync_redis
import redis.asyncio as aioredis

from llm_module.core.models import Task
from llm_module.infra.redis.task_store import RedisTaskStore

BATCH_QUEUE_PREFIX = "batch:"
BATCH_SCHED_PREFIX = "batch_sched:"
BATCH_QUEUE_TTL_SECONDS = 3600


def batch_queue_key(batch_key: str) -> str:
    return f"{BATCH_QUEUE_PREFIX}{batch_key}"


def _batch_sched_key(batch_key: str) -> str:
    return f"{BATCH_SCHED_PREFIX}{batch_key}"


class RedisBatchQueue:
    def __init__(
        self,
        task_store: RedisTaskStore,
        sync_client: Optional[sync_redis.Redis] = None,
        async_client: Optional[aioredis.Redis] = None,
    ) -> None:
        self._store = task_store
        self._sync = sync_client
        self._async = async_client

    # ------------------------------------------------------------------
    # Côté API (async)
    # ------------------------------------------------------------------

    async def add(self, batch_key: str, task_id: str, score: float) -> int:
        key = batch_queue_key(batch_key)
        await self._async.zadd(key, {task_id: score})
        await self._async.expire(key, BATCH_QUEUE_TTL_SECONDS)
        return await self._async.zcard(key)

    async def try_mark_scheduled(self, batch_key: str, ttl: int) -> bool:
        """Pose le flag « dispatch différé planifié » (SETNX).

        True si le flag vient d'être posé (l'appelant doit planifier le
        dispatch), False s'il existait déjà. Élimine la course où deux requêtes
        simultanées observent chacune queue_size > 1 et où aucune ne planifie
        le worker. Le TTL sert de filet de sécurité si le message Celery se perd.
        """
        return bool(await self._async.set(_batch_sched_key(batch_key), "1", nx=True, ex=ttl))

    # ------------------------------------------------------------------
    # Côté worker (sync)
    # ------------------------------------------------------------------

    def clear_scheduled(self, batch_key: str) -> None:
        """Libère le flag de dispatch — appelé juste avant de dépiler, pour que
        les tâches arrivant ensuite puissent replanifier un dispatch."""
        self._sync.delete(_batch_sched_key(batch_key))

    def pop(self, batch_key: str, max_agents: int) -> list[Task]:
        """Dépile les tâches les plus urgentes (score min) jusqu'à la limite d'agents."""
        key = batch_queue_key(batch_key)
        selected_tasks: list[Task] = []
        current_agents_count = 0

        while True:
            result = self._sync.zpopmin(key, count=1)
            if not result:
                break

            task_id = result[0][0]
            if isinstance(task_id, bytes):
                task_id = task_id.decode()

            task = self._store.get_sync(task_id)
            if not task:
                continue

            agents_in_task = len(task.request.agents)
            if current_agents_count + agents_in_task > max_agents and current_agents_count > 0:
                # Dépasse la limite : on remet la tâche avec son score d'origine
                self._sync.zadd(key, {task_id: task.priority_score})
                break

            selected_tasks.append(task)
            current_agents_count += agents_in_task

        return selected_tasks

    def requeue(self, batch_key: str, tasks: list[Task]) -> None:
        """En cas d'erreur (retry), replace les tâches avec leur score d'origine."""
        if not tasks:
            return
        mapping = {t.task_id: t.priority_score for t in tasks}
        self._sync.zadd(batch_queue_key(batch_key), mapping)

    def size(self, batch_key: str) -> int:
        return self._sync.zcard(batch_queue_key(batch_key))

    def depths(self) -> dict[str, int]:
        """Profondeur des files non vides — pour la gauge llm_task_queue_depth."""
        result: dict[str, int] = {}
        for key in self._sync.scan_iter(f"{BATCH_QUEUE_PREFIX}*"):
            name = key.decode() if isinstance(key, bytes) else key
            if name.startswith(BATCH_SCHED_PREFIX):
                continue
            depth = self._sync.zcard(name)
            if depth > 0:
                result[name] = depth
        return result
