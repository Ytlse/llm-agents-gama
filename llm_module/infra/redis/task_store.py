"""
infra/redis/task_store.py — RedisTaskStore : persistance statut/résultat + pub/sub.

Implémente les ports TaskStore (async, API) et SyncTaskStore (sync, worker).
Clés `task:{id}` (TTL 1h) ; notification de fin sur le canal `task_done:{id}`
(latence ~10ms vs polling).
"""

from __future__ import annotations
import asyncio
import time
from typing import Optional

import redis as sync_redis
import redis.asyncio as aioredis
import redis.exceptions as redis_exc

from llm_module.core.models import Task, TaskStatus

TASK_KEY_PREFIX = "task:"
TASK_DONE_CHANNEL_PREFIX = "task_done:"
TASK_TTL_SECONDS = 3600


def task_key(task_id: str) -> str:
    return f"{TASK_KEY_PREFIX}{task_id}"


def task_done_channel(task_id: str) -> str:
    return f"{TASK_DONE_CHANNEL_PREFIX}{task_id}"


class RedisTaskStore:
    def __init__(
        self,
        sync_client: Optional[sync_redis.Redis] = None,
        async_client: Optional[aioredis.Redis] = None,
    ) -> None:
        self._sync = sync_client
        self._async = async_client

    # ------------------------------------------------------------------
    # Async (API)
    # ------------------------------------------------------------------

    async def save(self, task: Task) -> None:
        await self._async.set(task_key(task.task_id), task.model_dump_json(), ex=TASK_TTL_SECONDS)

    async def get(self, task_id: str) -> Optional[Task]:
        raw = await self._async.get(task_key(task_id))
        if raw is None:
            return None
        return Task.model_validate_json(raw)

    async def wait_done(self, task_id: str, timeout: float) -> Optional[Task]:
        """
        Bloque jusqu'à l'état terminal (success/failed) via pub/sub, ou timeout.

        Se reconnecte automatiquement si la socket pubsub est interrompue avant
        la fin du budget de temps (évite les faux-timeouts sur coupure Redis).
        Retourne le dernier état connu, None si la tâche n'existe pas.
        """
        deadline = time.monotonic() + timeout
        channel = task_done_channel(task_id)

        task = await self.get(task_id)
        if task is None:
            return None
        if task.status in (TaskStatus.SUCCESS, TaskStatus.FAILED):
            return task

        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            pubsub = self._async.pubsub()
            await pubsub.subscribe(channel)
            try:
                # Re-check après subscribe : ferme la course entre la fin de
                # tâche et l'abonnement.
                task = await self.get(task_id) or task
                if task.status in (TaskStatus.SUCCESS, TaskStatus.FAILED):
                    break

                async def _recv() -> str:
                    async for msg in pubsub.listen():
                        if msg["type"] == "message":
                            return msg["data"]

                try:
                    raw = await asyncio.wait_for(_recv(), timeout=remaining)
                    task = Task.model_validate_json(raw)
                    break
                except asyncio.TimeoutError:
                    # Budget épuisé — on retourne le dernier état connu.
                    task = await self.get(task_id) or task
                    break
                except redis_exc.TimeoutError:
                    # Socket pubsub coupée avant la fin ; on retente s'il reste du temps.
                    task = await self.get(task_id) or task
                    if task.status in (TaskStatus.SUCCESS, TaskStatus.FAILED):
                        break
            finally:
                await pubsub.unsubscribe(channel)
                await pubsub.aclose()

        return task

    # ------------------------------------------------------------------
    # Sync (worker Celery)
    # ------------------------------------------------------------------

    def save_sync(self, task: Task) -> None:
        self._sync.set(task_key(task.task_id), task.model_dump_json(), ex=TASK_TTL_SECONDS)

    def get_sync(self, task_id: str) -> Optional[Task]:
        raw = self._sync.get(task_key(task_id))
        if raw is None:
            return None
        return Task.model_validate_json(raw)

    def publish_done_sync(self, task: Task) -> None:
        self._sync.publish(task_done_channel(task.task_id), task.model_dump_json())
