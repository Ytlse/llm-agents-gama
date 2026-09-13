"""
infra/redis/connection.py — Fabriques de clients Redis.

Les clients sont créés explicitement par la composition (create_app, worker
runtime) et injectés dans les implémentations infra — jamais construits comme
effet de bord d'un import.
"""

from __future__ import annotations

import redis as sync_redis
import redis.asyncio as aioredis


def create_sync_redis(redis_url: str) -> sync_redis.Redis:
    return sync_redis.from_url(redis_url, encoding="utf-8", decode_responses=True)


def create_async_redis(redis_url: str) -> aioredis.Redis:
    return aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
