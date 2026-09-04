import asyncio
import hashlib
import json
import os
import sqlite3
import time as _time
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
    def make_key(departure_time: int, origin: Location, destination: Location, include_car: bool, arrive_by: bool, include_bike: bool = True) -> str:
        # include_bike fait partie de la clé : sans lui, un résultat calculé pour un
        # agent sans vélo (aucune option vélo) serait resservi à un agent avec vélo.
        #
        # ⚠ La version des données d'itinéraire (`terminal_time.data_version()`) est
        # dans la clé, et c'est ici qu'elle compte le plus des trois caches : ce cache
        # ne mémorise pas des durées, il mémorise les **TravelPlan sérialisés**, options
        # voiture et vélo comprises. Sans version, un cache chaud resservirait des plans
        # à UNE SEULE jambe, portant l'ancien stationnement fondu dans la durée — c'est-
        # à-dire la totalité du défaut du ticket 013, ressuscitée après sa correction, et
        # sans qu'aucun log ne le signale. Bumper la version dans
        # config/terminal_time.yaml rend les anciennes lignes inatteignables sans les
        # détruire.
        #
        # NOTE fixed_day : la clé inclut la date absolue (YYYY-MM-DD) du departure_time
        # simulé, calculée AVANT le remapping fixed_day fait dans OTPTripHelper
        # (otp.py). Quand gtfs.fixed_day est actif, deux dates simulées différentes
        # produisent pourtant la même requête OTP (mêmes horaires GTFS), mais des clés
        # de cache différentes → le cache réchauffé au jour J est intégralement raté
        # au jour J+1.
        # TODO: quand fixed_day est actif, remplacer date_str par la date fixe (ou le
        # jour de semaine) pour partager le cache entre dates simulées, comme le fait
        # déjà OsmnxPersistentCache (clé weekday, pas date absolue).
        #
        # ⚠ L'INSTANT, décalage compris, et non plus une date et une heure nues
        # (2026-09-04). `datetime.fromtimestamp(departure_time)` lisait l'horloge
        # murale de GAMA dans le fuseau du PROCESSUS : 5 h murales devenaient 6 h, et
        # c'est à 6 h qu'OTP était interrogé. Ce cache ne mémorise pas des durées mais
        # des TravelPlan sérialisés, et `lookup` les décale de
        # `departure_time - stored_departure_time` : une entrée rangée sous l'étiquette
        # « 06:00 » alors qu'elle répondait à un départ de 5 h murales serait
        # resservie, puis décalée d'une heure de plus, à un départ de 6 h murales.
        # Aucune version ne protégeait de ça — `data_version()` ne bouge pas et
        # `routing_version` n'entre pas ici. Écrire l'instant complet
        # (`2026-03-16T05:00:00+01:00`) change la FORME de la clé : plus aucune entrée
        # de l'ancienne convention n'est atteignable, sans purge manuelle, et le
        # décalage porté par la clé distingue enfin l'heure d'hiver de l'heure d'été
        # — la même heure murale n'est pas le même instant selon la saison.
        from sim_clock import to_network_datetime
        from trip_helper.terminal_time import data_version

        dt = to_network_datetime(departure_time)
        bucket = dt.replace(minute=(dt.minute // 10) * 10, second=0, microsecond=0)
        raw = (f"{data_version()}|{bucket.isoformat()}|{origin.lat:.5f}|{origin.lon:.5f}"
               f"|{destination.lat:.5f}|{destination.lon:.5f}"
               f"|{int(include_car)}|{int(arrive_by)}|{int(include_bike)}")
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def make_blacklist_key(origin: Location, destination: Location) -> str:
        # PAS de version ici, et c'est délibéré : la liste noire dit « OTP ne relie pas
        # ces deux points », un fait de topologie du réseau qui ne dépend d'aucun temps
        # terminal. La versionner ferait re-interroger OTP pour rien sur les paires
        # connues comme non reliées — la moitié des avertissements « No usable
        # itinerary » d'un run.
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
