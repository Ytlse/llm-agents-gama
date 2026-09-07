"""
infra/redis/metrics.py — RedisMetricsSink : compteurs worker persistants.

Migration perf (CR §2.2) : les compteurs vivent dans UN hash Redis (`wmetrics`,
HINCRBY) au lieu de N clés string. Le scrape Prometheus fait un seul HGETALL
au lieu de dizaines de SCAN+GET.
"""

from __future__ import annotations

import json

import redis as sync_redis

WORKER_METRICS_HASH_KEY = "wmetrics"

# Ring buffer des dernières erreurs LLM (texte) — Prometheus ne stocke que du
# numérique, donc les messages bruts vivent dans une liste Redis plafonnée,
# relue par l'endpoint /errors/recent (cf. api/routes.py).
RECENT_ERRORS_KEY = "llm:recent_errors"
RECENT_ERRORS_MAX = 50


class RedisMetricsSink:
    def __init__(self, sync_client: sync_redis.Redis) -> None:
        self._r = sync_client

    def incr(self, name: str, amount: int = 1) -> None:
        self._r.hincrby(WORKER_METRICS_HASH_KEY, name, amount)

    def get(self, name: str) -> int:
        val = self._r.hget(WORKER_METRICS_HASH_KEY, name)
        return int(val) if val else 0

    def items(self) -> dict[str, int]:
        raw = self._r.hgetall(WORKER_METRICS_HASH_KEY)
        return {
            (k.decode() if isinstance(k, bytes) else k): int(v)
            for k, v in raw.items()
        }

    # ------------------------------------------------------------------
    # Ring buffer des dernières erreurs LLM (texte)
    # ------------------------------------------------------------------

    def push_error(self, entry: dict) -> None:
        """Empile une erreur LLM en tête de liste et tronque à RECENT_ERRORS_MAX."""
        self._r.lpush(RECENT_ERRORS_KEY, json.dumps(entry, ensure_ascii=False, default=str))
        self._r.ltrim(RECENT_ERRORS_KEY, 0, RECENT_ERRORS_MAX - 1)

    def recent_errors(self, n: int = RECENT_ERRORS_MAX) -> list[dict]:
        """Retourne les n dernières erreurs LLM, de la plus récente à la plus ancienne."""
        raw = self._r.lrange(RECENT_ERRORS_KEY, 0, max(0, n - 1))
        out: list[dict] = []
        for item in raw:
            s = item.decode() if isinstance(item, bytes) else item
            try:
                out.append(json.loads(s))
            except (ValueError, TypeError):
                continue
        return out
