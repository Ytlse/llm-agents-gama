"""
worker/runtime.py — Composition des dépendances côté worker Celery.

Le worker est synchrone : il ne construit que le client Redis sync. Les
dépendances sont assemblées au premier appel de get_worker_runtime() (dans la
tâche Celery), jamais à l'import du module — un worker peut donc être importé
sans Redis disponible.
"""

from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache

from llm_module.config import Settings, get_settings
from llm_module.infra.redis import (
    RedisBatchQueue,
    RedisMetricsSink,
    RedisRateLimiter,
    RedisTaskStore,
    create_sync_redis,
)
from llm_module.load_balancer.router import LoadBalancer


@dataclass
class WorkerRuntime:
    settings: Settings
    store: RedisTaskStore
    queue: RedisBatchQueue
    limiter: RedisRateLimiter
    metrics: RedisMetricsSink
    balancer: LoadBalancer


def build_worker_runtime(settings: Settings) -> WorkerRuntime:
    sync_client = create_sync_redis(settings.redis_url)
    store = RedisTaskStore(sync_client=sync_client)
    queue = RedisBatchQueue(task_store=store, sync_client=sync_client)
    limiter = RedisRateLimiter(sync_client, settings.providers)
    metrics = RedisMetricsSink(sync_client)
    balancer = LoadBalancer(settings.providers, limiter)
    return WorkerRuntime(
        settings=settings,
        store=store,
        queue=queue,
        limiter=limiter,
        metrics=metrics,
        balancer=balancer,
    )


@lru_cache(maxsize=1)
def get_worker_runtime() -> WorkerRuntime:
    return build_worker_runtime(get_settings())
