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

from llm_gateway.balancer.router import LoadBalancer
from llm_gateway.config import Settings, apply_learned_limits, get_settings
from llm_gateway.config.learned_store import build_learned_store
from llm_gateway.infra.redis import (
    RedisBatchQueue,
    RedisMetricsSink,
    RedisRateLimiter,
    RedisTaskStore,
    create_sync_redis,
)
from llm_gateway.ports.learned_limits import LearnedLimits
from llm_gateway.prompts.registry import CategoryRegistry, get_registry


@dataclass
class WorkerRuntime:
    settings: Settings
    store: RedisTaskStore
    queue: RedisBatchQueue
    limiter: RedisRateLimiter
    metrics: RedisMetricsSink
    balancer: LoadBalancer
    registry: CategoryRegistry
    learned: LearnedLimits


def build_worker_runtime(settings: Settings, registry: CategoryRegistry | None = None) -> WorkerRuntime:
    sync_client = create_sync_redis(settings.redis.url)
    learned = build_learned_store(settings, sync_client)
    apply_learned_limits(settings, learned)
    store = RedisTaskStore(sync_client=sync_client)
    queue = RedisBatchQueue(task_store=store, sync_client=sync_client)
    limiter = RedisRateLimiter(sync_client, settings.providers)
    metrics = RedisMetricsSink(sync_client)
    balancer = LoadBalancer(settings.providers, limiter, policy=settings.routing.policy)
    return WorkerRuntime(
        settings=settings,
        store=store,
        queue=queue,
        limiter=limiter,
        metrics=metrics,
        balancer=balancer,
        registry=registry if registry is not None else get_registry(),
        learned=learned,
    )


@lru_cache(maxsize=1)
def get_worker_runtime() -> WorkerRuntime:
    return build_worker_runtime(get_settings())
