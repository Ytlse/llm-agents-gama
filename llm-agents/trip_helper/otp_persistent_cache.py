import asyncio
import hashlib
import json
import os
import sqlite3
import time as _time
from datetime import datetime
from typing import Optional

from models import Location, TravelPlan


class OtpPersistentCache:
    def __init__(self, cache_dir: str):
        os.makedirs(cache_dir, exist_ok=True)
        self.db_path = os.path.join(cache_dir, "otp_cache.db")
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS otp_cache (
                    key TEXT PRIMARY KEY,
                    plans_json TEXT NOT NULL,
                    departure_time INTEGER NOT NULL,
                    stored_at INTEGER NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS otp_blacklist (
                    key TEXT PRIMARY KEY,
                    stored_at INTEGER NOT NULL
                )
            """)
            conn.commit()

    @staticmethod
    def make_key(departure_time: int, origin: Location, destination: Location, include_car: bool, arrive_by: bool) -> str:
        dt = datetime.fromtimestamp(departure_time)
        date_str = dt.strftime('%Y-%m-%d')
        time_bucket = f"{dt.hour:02d}:{(dt.minute // 10) * 10:02d}"
        raw = f"{date_str}|{time_bucket}|{origin.lat:.5f}|{origin.lon:.5f}|{destination.lat:.5f}|{destination.lon:.5f}|{int(include_car)}|{int(arrive_by)}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def make_blacklist_key(origin: Location, destination: Location) -> str:
        raw = f"{origin.lat:.5f}|{origin.lon:.5f}|{destination.lat:.5f}|{destination.lon:.5f}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def lookup(self, key: str) -> Optional[tuple[list[TravelPlan], int]]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT plans_json, departure_time FROM otp_cache WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        plans = [TravelPlan.model_validate(p) for p in json.loads(row[0])]
        return plans, row[1]

    def store(self, key: str, itineraries: list[TravelPlan], departure_time: int):
        plans_json = json.dumps([p.model_dump() for p in itineraries])
        with self._get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO otp_cache (key, plans_json, departure_time, stored_at) VALUES (?, ?, ?, ?)",
                (key, plans_json, departure_time, int(_time.time()))
            )
            conn.commit()

    def is_blacklisted(self, bl_key: str) -> bool:
        with self._get_conn() as conn:
            row = conn.execute("SELECT 1 FROM otp_blacklist WHERE key = ?", (bl_key,)).fetchone()
        return row is not None

    def blacklist_add(self, bl_key: str):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO otp_blacklist (key, stored_at) VALUES (?, ?)",
                (bl_key, int(_time.time()))
            )
            conn.commit()

    async def lookup_async(self, key: str) -> Optional[tuple[list[TravelPlan], int]]:
        return await asyncio.to_thread(self.lookup, key)

    async def store_async(self, key: str, itineraries: list[TravelPlan], departure_time: int):
        await asyncio.to_thread(self.store, key, itineraries, departure_time)

    async def blacklist_add_async(self, bl_key: str):
        await asyncio.to_thread(self.blacklist_add, bl_key)

    async def is_blacklisted_async(self, bl_key: str) -> bool:
        return await asyncio.to_thread(self.is_blacklisted, bl_key)
