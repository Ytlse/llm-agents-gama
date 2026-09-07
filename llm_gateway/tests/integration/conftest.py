"""Un gateway complet en mémoire : ports InMemory*, registre `echo`, aucun Redis, aucun réseau."""
from __future__ import annotations

import pytest

from llm_gateway.api.deps import GatewayDeps
from llm_gateway.balancer.router import LoadBalancer
from llm_gateway.config import Settings
from llm_gateway.testing import (
    InMemoryBatchQueue,
    InMemoryMetricsSink,
    InMemoryRateLimiter,
    InMemoryTaskStore,
    build_registry,
)
from llm_gateway.worker.runtime import WorkerRuntime


@pytest.fixture
def settings(monkeypatch, tmp_path) -> Settings:
    monkeypatch.setenv("APP_WORKDIR", str(tmp_path))   # journaux d'échanges dans un dossier jetable
    return Settings()


@pytest.fixture
def memory_deps(settings) -> GatewayDeps:
    store = InMemoryTaskStore()
    limiter = InMemoryRateLimiter(settings.providers)
    return GatewayDeps(
        settings=settings,
        store=store,
        queue=InMemoryBatchQueue(store),
        limiter=limiter,
        metrics=InMemoryMetricsSink(),
        balancer=LoadBalancer(settings.providers, limiter),
        registry=build_registry(),
    )


@pytest.fixture
def memory_runtime(memory_deps) -> WorkerRuntime:
    d = memory_deps
    return WorkerRuntime(
        settings=d.settings, store=d.store, queue=d.queue, limiter=d.limiter,
        metrics=d.metrics, balancer=d.balancer, registry=d.registry,
    )
