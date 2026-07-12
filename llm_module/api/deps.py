"""
api/deps.py — Composition des dépendances du gateway (injection explicite).

build_deps() est le SEUL endroit où l'API construit ses connexions Redis et
assemble les implémentations concrètes derrière les ports. Les routes lisent
le conteneur via request.app.state.deps.
"""

from __future__ import annotations
from dataclasses import dataclass

from llm_module.config import Settings
from llm_module.infra.redis import (
    RedisBatchQueue,
    RedisMetricsSink,
    RedisRateLimiter,
    RedisTaskStore,
    create_async_redis,
    create_sync_redis,
)
from llm_module.load_balancer.router import LoadBalancer


@dataclass
class GatewayDeps:
    settings: Settings
    store: RedisTaskStore
    queue: RedisBatchQueue
    limiter: RedisRateLimiter
    metrics: RedisMetricsSink
    balancer: LoadBalancer


def build_deps(settings: Settings) -> GatewayDeps:
    sync_client = create_sync_redis(settings.redis_url)
    async_client = create_async_redis(settings.redis_url)

    store = RedisTaskStore(sync_client=sync_client, async_client=async_client)
    queue = RedisBatchQueue(task_store=store, sync_client=sync_client, async_client=async_client)
    limiter = RedisRateLimiter(sync_client, settings.providers)
    metrics = RedisMetricsSink(sync_client)
    balancer = LoadBalancer(settings.providers, limiter)

    return GatewayDeps(
        settings=settings,
        store=store,
        queue=queue,
        limiter=limiter,
        metrics=metrics,
        balancer=balancer,
    )
