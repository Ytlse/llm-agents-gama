"""
api/deps.py — Composition des dépendances du gateway (injection explicite).

build_deps() est le SEUL endroit où l'API construit ses connexions Redis et
assemble les implémentations concrètes derrière les ports. Le registre des
catégories (bundles découverts par entry point) y est injecté, ou passé par le test. Les routes lisent
le conteneur via request.app.state.deps.
"""

from __future__ import annotations

from dataclasses import dataclass

from llm_gateway.balancer.router import LoadBalancer
from llm_gateway.config import Settings, apply_learned_limits
from llm_gateway.config.learned_store import build_learned_store
from llm_gateway.infra.redis import (
    RedisBatchQueue,
    RedisMetricsSink,
    RedisRateLimiter,
    RedisTaskStore,
    create_async_redis,
    create_sync_redis,
)
from llm_gateway.ports.learned_limits import LearnedLimits
from llm_gateway.prompts.registry import CategoryRegistry, get_registry


@dataclass
class GatewayDeps:
    settings: Settings
    store: RedisTaskStore
    queue: RedisBatchQueue
    limiter: RedisRateLimiter
    metrics: RedisMetricsSink
    balancer: LoadBalancer
    registry: CategoryRegistry
    learned: LearnedLimits


def build_deps(settings: Settings, registry: CategoryRegistry | None = None) -> GatewayDeps:
    sync_client = create_sync_redis(settings.redis.url)
    async_client = create_async_redis(settings.redis.url)
    learned = build_learned_store(settings, sync_client)
    apply_learned_limits(settings, learned)

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
        registry=registry if registry is not None else get_registry(),
        learned=learned,
    )
