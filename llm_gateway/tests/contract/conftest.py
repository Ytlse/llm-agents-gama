"""Une même suite, plusieurs implémentations : les fixtures paramètrent le « backend ».

- ``memory``    : les implémentations InMemory* (toujours) ;
- ``fakeredis`` : les implémentations Redis* sur fakeredis (scripts Lua via lupa) ;
- ``redis``     : les implémentations Redis* sur un vrai serveur, si LLM_GATEWAY_TEST_REDIS_URL
                  est défini (la CI démarre un service Redis pour cela).

Chaque test de contrat n'utilise que les méthodes des ports (``llm_gateway.ports``).
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

import pytest
from pydantic import SecretStr

from llm_gateway.config import ProviderConfig
from llm_gateway.infra.memory import (
    InMemoryBatchQueue,
    InMemoryLearnedLimits,
    InMemoryMetricsSink,
    InMemoryRateLimiter,
    InMemoryTaskStore,
)

REDIS_URL = os.getenv("LLM_GATEWAY_TEST_REDIS_URL")

BACKENDS = ["memory", "fakeredis"] + (["redis"] if REDIS_URL else [])


def providers_fixture() -> dict[str, ProviderConfig]:
    return {
        "p1": ProviderConfig(
            api_key=SecretStr("k"), rpm_limit=2, base_url="http://x", default_model="m",
            concurrency_limit=5, disable_timeout=30,
        ),
        "p2": ProviderConfig(
            api_key=SecretStr("k"), rpm_limit=100, tpm_limit=10_000, base_url="http://y",
            default_model="m", concurrency_limit=5,
        ),
        # rpm énorme : le lissage (60 s / rpm) ne bloque pas des réservations rapprochées,
        # et le quota journalier (rpd_limit=3) est la seule borne testée.
        "p3": ProviderConfig(
            api_key=SecretStr("k"), rpm_limit=1_000_000, base_url="http://z", default_model="m",
            concurrency_limit=5, rpd_limit=3,
        ),
        # Fournisseur dont la journée de quota se termine en heure du Pacifique, comme le
        # free tier Gemini : sert à vérifier que le retrait vise SON reset, pas minuit UTC.
        "p_pacifique": ProviderConfig(
            api_key=SecretStr("k"), rpm_limit=1_000_000, base_url="http://pac",
            default_model="m", concurrency_limit=5, rpd_limit=500,
            quota_reset_tz="America/Los_Angeles",
        ),
    }


@dataclass
class Ports:
    backend: str
    store: object
    queue: object
    limiter: object
    metrics: object
    learned: object


def _redis_ports(backend: str, sync_client, async_client) -> Ports:
    from llm_gateway.infra.redis import (
        RedisBatchQueue,
        RedisLearnedLimits,
        RedisMetricsSink,
        RedisRateLimiter,
        RedisTaskStore,
    )
    store = RedisTaskStore(sync_client=sync_client, async_client=async_client)
    queue = RedisBatchQueue(task_store=store, sync_client=sync_client, async_client=async_client)
    limiter = RedisRateLimiter(sync_client, providers_fixture())
    metrics = RedisMetricsSink(sync_client)
    return Ports(backend, store, queue, limiter, metrics, RedisLearnedLimits(sync_client))


@pytest.fixture(params=BACKENDS)
def ports(request) -> Ports:
    backend = request.param
    if backend == "memory":
        store = InMemoryTaskStore()
        return Ports(
            backend, store, InMemoryBatchQueue(store),
            InMemoryRateLimiter(providers_fixture()), InMemoryMetricsSink(), InMemoryLearnedLimits(),
        )
    if backend == "fakeredis":
        fakeredis = pytest.importorskip("fakeredis")
        pytest.importorskip("lupa", reason="les scripts Lua du rate limiter exigent fakeredis[lua]")
        server = fakeredis.FakeServer()
        sync_client = fakeredis.FakeRedis(server=server, decode_responses=True)
        async_client = fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
        return _redis_ports(backend, sync_client, async_client)
    # vrai Redis : base dédiée, vidée avant chaque test
    import redis as sync_redis
    import redis.asyncio as aioredis
    sync_client = sync_redis.from_url(REDIS_URL, decode_responses=True)
    sync_client.flushdb()
    async_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis_ports(backend, sync_client, async_client)


@pytest.fixture
def unique_key() -> str:
    return f"cat:{uuid.uuid4().hex[:8]}"
