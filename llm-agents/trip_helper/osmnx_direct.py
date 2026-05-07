"""
OSMnx direct route planner (foot, bicycle, car).

Optimised for high-frequency async use:
  - Graphs loaded once into a process-wide singleton (disk cache survives restarts).
  - CPU-bound routing dispatched to per-mode ProcessPoolExecutors (bypasses GIL).
  - Each worker process loads only its mode's graph once, then reuses it.
  - OTP-compatible timestamps (Unix seconds) and leg structure.
"""

import asyncio
import hashlib
import math
import multiprocessing as _mp
import os
import pickle
import sys as _sys
import time as _time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Optional

import geopandas as gpd
import osmnx as ox
import pandas as pd
import yaml
from loguru import logger
from prometheus_client import Counter, Histogram
from shapely.geometry import Point

from models import Location, Transit, TransitLocation, TravelPlan
from geography import TOULOUSE_CENTER_DIST_M
from settings import settings
from utils import random_uuid

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "osmnx.yaml"
with _CONFIG_PATH.open() as _f:
    _cfg = yaml.safe_load(_f)

# ── Prometheus ────────────────────────────────────────────────────────────────

OSMNX_OK  = Counter(
    "osmnx_requests_ok_total",
    "OSMnx routing successes",
    ["mode"],
)
OSMNX_ERR = Counter(
    "osmnx_requests_err_total",
    "OSMnx routing failures",
    ["mode", "reason"],
)
OSMNX_LAT = Histogram(
    "osmnx_request_duration_seconds",
    "OSMnx routing latency",
    ["mode"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5],
)

# ── Route markers (make each direct mode's get_code() unique) ─────────────────

DIRECT_ROUTE_MARKER = {
    "foot":     "__DIRECT_FOOT__",
    "bicycle":  "__DIRECT_BICYCLE__",
    "car":      "__DIRECT_CAR__",
}

# ── OSMnx network_type mapping ────────────────────────────────────────────────

_OSMNX_MODES = ("walk", "bike", "drive")
_MODE_TO_OSMNX = {"foot": "walk", "bicycle": "bike", "car": "drive"}

# ── Routing config (loaded from config/osmnx.yaml) ───────────────────────────

_SPEEDS    = _cfg["speeds"]
_FALLBACKS = _cfg["fallbacks"]
_PENALTIES = _cfg["penalties"]
_PARK_BASE = _cfg["park_base"]

# ── Congestion tables (TomTom Toulouse, loaded from config/osmnx.yaml) ────────

_DAYS  = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_HOURS = [f"{h:02d}:00" for h in range(24)]

_cong     = _cfg["congestion"]
_CITY_DF  = pd.DataFrame(_cong["city_raw"],  index=_HOURS, columns=_DAYS)
_METRO_DF = pd.DataFrame(_cong["metro_raw"], index=_HOURS, columns=_DAYS)
_CITY_FF  = float(_cong["city_free_flow_kmh"])
_METRO_FF = float(_cong["metro_free_flow_kmh"])

# ── Distance cutoffs ──────────────────────────────────────────────────────────
# Skip routing entirely when straight-line distance exceeds these thresholds.

_MAX_FOOT_M = 15_000   # 15 km
_MAX_BIKE_M = 30_000   # 30 km

# ── Executor pools ────────────────────────────────────────────────────────────
# Graph building is I/O-bound (OSM download) → ThreadPoolExecutor.
# Routing (NetworkX Dijkstra) is pure-Python CPU-bound → ProcessPoolExecutor
# per mode so each worker process loads only its own graph and bypasses the GIL.
#
# spawn is used on macOS/Windows (fork unsafe with asyncio threads);
# fork is used on Linux (faster startup, COW memory sharing).

_WORKERS_PER_MODE = 4

_IO_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="osmnx-io")

_mp_context = _mp.get_context("fork" if _sys.platform.startswith("linux") else "spawn")

_MODE_POOLS: dict[str, ProcessPoolExecutor] = {
    mode: ProcessPoolExecutor(max_workers=_WORKERS_PER_MODE, mp_context=_mp_context)
    for mode in _OSMNX_MODES
}

# ── Graph singleton ───────────────────────────────────────────────────────────

class _GraphStore:
    """Process-wide singleton: load walk/bike/drive graphs + city boundary once."""

    _graphs:   Optional[dict]             = None
    _boundary: Optional[gpd.GeoDataFrame] = None
    _lock:     Optional[asyncio.Lock]     = None

    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock

    @classmethod
    def _cache_dir(cls) -> Path:
        path = Path(getattr(settings.gtfs, "osmnx_cache_dir", "/app/osmnx_cache"))
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def _build_sync(cls, city: str, dist: int) -> tuple[dict, gpd.GeoDataFrame]:
        """Download or restore graphs and boundary from disk cache."""
        key     = hashlib.md5(f"{city}_{dist}".encode()).hexdigest()[:12]
        g_path  = cls._cache_dir() / f"graphs_{key}.pkl"
        b_path  = cls._cache_dir() / f"boundary_{key}.pkl"

        graphs = None
        if g_path.exists():
            logger.info(f"OSMnx: loading graphs from {g_path.name}")
            with g_path.open("rb") as f:
                graphs = pickle.load(f)
            if not all(G.number_of_edges() > 0 for G in graphs.values()):
                logger.warning("OSMnx: cached graphs are empty, clearing cache and re-downloading…")
                g_path.unlink(missing_ok=True)
                graphs = None

        if graphs is None:
            logger.info(f"OSMnx: downloading graphs for {city!r} (r={dist} m) …")
            graphs = {}
            for osmnx_mode in _OSMNX_MODES:
                G = ox.graph_from_address(city, dist=dist, network_type=osmnx_mode)
                for _, _, _, data in G.edges(keys=True, data=True):
                    hwy = data.get("highway")
                    if isinstance(hwy, list):
                        hwy = hwy[0]
                    data["speed_kph"] = _SPEEDS[osmnx_mode].get(hwy, _FALLBACKS[osmnx_mode])
                graphs[osmnx_mode] = ox.add_edge_travel_times(G)
            with g_path.open("wb") as f:
                pickle.dump(graphs, f)
            logger.info(f"OSMnx: graphs saved to {g_path.name}")

        if b_path.exists():
            logger.info(f"OSMnx: loading boundary from {b_path.name}")
            with b_path.open("rb") as f:
                boundary = pickle.load(f)
        else:
            logger.info(f"OSMnx: downloading boundary for {city!r} …")
            boundary = ox.geocode_to_gdf(city).to_crs("EPSG:4326")
            with b_path.open("wb") as f:
                pickle.dump(boundary, f)
            logger.info(f"OSMnx: boundary saved to {b_path.name}")

        return graphs, boundary

    @classmethod
    async def get(cls, city: str = "Toulouse, France", dist: int = TOULOUSE_CENTER_DIST_M) -> tuple[dict, gpd.GeoDataFrame]:
        # Return cached graphs and boundary if exist
        if cls._graphs is not None:
            return cls._graphs, cls._boundary
        
        # Else build them in a thread to avoid blocking the event loop, with a lock to prevent concurrent builds
        async with cls._get_lock():
            if cls._graphs is not None:
                return cls._graphs, cls._boundary
            loop = asyncio.get_running_loop()
            cls._graphs, cls._boundary = await loop.run_in_executor(
                _IO_EXECUTOR, cls._build_sync, city, dist
            )
            logger.info("OSMnx: graphs ready.")
        return cls._graphs, cls._boundary


# ── Internal helpers ──────────────────────────────────────────────────────────

def _crow_flies_m(origin: Location, destination: Location) -> float:
    dlat = (destination.lat - origin.lat) * 111_320
    dlon = (destination.lon - origin.lon) * 111_320 * math.cos(math.radians(origin.lat))
    return math.hypot(dlat, dlon)


def _in_city(lon: float, lat: float, boundary: gpd.GeoDataFrame) -> bool:
    # Check whether the given point is inside the provided city boundary polygon.
    return boundary.geometry.iloc[0].contains(Point(lon, lat))


def _congestion_factor(dt: datetime, in_city: bool) -> float:
    # Compute a congestion multiplier based on time of day and whether the route is inside city limits.
    hour = f"{dt.hour:02d}:00"
    day  = dt.strftime("%a")
    if in_city:
        return _CITY_FF  / float(_CITY_DF.loc[hour, day])
    return _METRO_FF / float(_METRO_DF.loc[hour, day])


def _infra_penalty(G, route_nodes: list, osmnx_mode: str) -> float:
    # Penalize routes that traverse infrastructure types considered slower or less desirable.
    counts = {k: 0 for k in _PENALTIES[osmnx_mode]}
    for n in route_nodes[1:-1]:
        tag = G.nodes[n].get("highway")
        if tag in counts:
            counts[tag] += 1
    return sum(counts[k] * _PENALTIES[osmnx_mode][k] for k in counts)


# ── Worker-process state (populated lazily on first task, None in main process) ─

_worker_graph:    object                    = None
_worker_boundary: Optional[gpd.GeoDataFrame] = None


def _route_sync_process(
    cache_dir:    str,
    cache_key:    str,
    origin:       Location,
    destination:  Location,
    osmnx_mode:   str,
    congestion_dt: datetime,
) -> Optional[dict]:
    """Entry point for ProcessPoolExecutor workers. Loads its graph once, then routes."""
    global _worker_graph, _worker_boundary
    if _worker_graph is None:
        g_path = Path(cache_dir) / f"graphs_{cache_key}.pkl"
        b_path = Path(cache_dir) / f"boundary_{cache_key}.pkl"
        with g_path.open("rb") as fh:
            _worker_graph = pickle.load(fh)[osmnx_mode]
        with b_path.open("rb") as fh:
            _worker_boundary = pickle.load(fh)
    return _route_sync(_worker_graph, _worker_boundary, origin, destination, osmnx_mode, congestion_dt)


def _route_sync(
    G:            object,
    boundary:     gpd.GeoDataFrame,
    origin:       Location,
    destination:  Location,
    osmnx_mode:   str,
    congestion_dt: datetime,
) -> Optional[dict]:
    """Pure-sync OSMnx routing. Returns {duration_s, distance_m} or None."""
    # Find the nearest nodes on the graph to the origin and destination coordinates.
    orig = ox.distance.nearest_nodes(G, origin.lon, origin.lat)
    dest = ox.distance.nearest_nodes(G, destination.lon, destination.lat)

    # Both points map to the same graph node: distance is too short for OSMnx routing.
    # Fall back to Euclidean distance + walking speed regardless of mode.
    if orig == dest:
        dlat = (destination.lat - origin.lat) * 111_320
        dlon = (destination.lon - origin.lon) * 111_320 * math.cos(math.radians(origin.lat))
        dist_m = math.hypot(dlat, dlon)
        walk_ms = _FALLBACKS["walk"] * 1000 / 3600  # 5 km/h → m/s
        return {"duration_s": max(1, int(dist_m / walk_ms)), "distance_m": dist_m}

    # Compute the fastest route using edge travel times as weights.
    route = ox.routing.shortest_path(G, orig, dest, weight="travel_time")
    if route is None or len(route) < 2:
        return None

    # Convert the route to a GeoDataFrame to aggregate per-edge metrics.
    gdf = ox.routing.route_to_gdf(G, route)

    # Total geometric distance in meters and base travel time in seconds.
    dist_m = float(gdf["length"].sum())
    free_s = float(gdf["travel_time"].sum())

    # Add penalties for infrastructure types that are slower or less desirable.
    infra_s = _infra_penalty(G, route, osmnx_mode)

    # Parking or retrieval time is applied for drive/bike legs only.
    park_s = 0.0
    if osmnx_mode in ("drive", "bike"):
        park_s = _PARK_BASE[osmnx_mode] * 2  # park at destination and retrieve vehicle/bike

    # Congestion only affects driving mode and is based on whether the trip is inside city limits.
    cong = 1.0
    if osmnx_mode == "drive":
        dest_city = _in_city(destination.lon, destination.lat, boundary)
        orig_city = _in_city(origin.lon, origin.lat, boundary)
        cong = _congestion_factor(congestion_dt, orig_city or dest_city)

    # Round up to at least one second and apply all modifiers.
    return {
        "duration_s": max(1, int(free_s * cong + infra_s + park_s)),
        "distance_m": dist_m,
    }


# ── Public API ────────────────────────────────────────────────────────────────

async def get_direct_plan(
    origin:        Location,
    destination:   Location,
    trip_mode:     str,      # "foot" | "bicycle" | "car"
    departure_time: int,     # Unix timestamp in seconds
    congestion_dt:  datetime, # Real calendar date+time for congestion lookup
    city: str = "Toulouse, France",
    dist: int = TOULOUSE_CENTER_DIST_M,
) -> Optional[TravelPlan]:
    """Async OSMnx direct route. Returns a one-leg TravelPlan or None on failure."""
    # Fast reject: skip routing when the straight-line distance exceeds the mode's threshold.
    straight_m = _crow_flies_m(origin, destination)
    if trip_mode == "foot" and straight_m > _MAX_FOOT_M:
        return None
    if trip_mode == "bicycle" and straight_m > _MAX_BIKE_M:
        return None

    osmnx_mode = _MODE_TO_OSMNX[trip_mode]
    t0 = _time.monotonic()

    try:
        # Ensure graphs are on disk before workers try to load them.
        await _GraphStore.get(city, dist)
        cache_dir = str(_GraphStore._cache_dir())
        cache_key = hashlib.md5(f"{city}_{dist}".encode()).hexdigest()[:12]

        loop   = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            _MODE_POOLS[osmnx_mode],
            _route_sync_process,
            cache_dir, cache_key, origin, destination, osmnx_mode, congestion_dt,
        )
    except Exception as exc:
        OSMNX_ERR.labels(mode=trip_mode, reason=type(exc).__name__).inc()
        logger.error(f"OSMnx {trip_mode} routing error: {exc}")
        return None

    if result is None:
        OSMNX_ERR.labels(mode=trip_mode, reason="no_route").inc()
        return None

    OSMNX_OK.labels(mode=trip_mode).inc()
    OSMNX_LAT.labels(mode=trip_mode).observe(_time.monotonic() - t0)

    duration_s = result["duration_s"]
    distance_m = result["distance_m"]
    start_s    = departure_time
    end_s      = departure_time + duration_s

    loc_start = TransitLocation(stop="", lat=origin.lat,      lon=origin.lon)
    loc_end   = TransitLocation(stop="", lat=destination.lat, lon=destination.lon)

    logger.info(f"OSMnx success {trip_mode} route: {origin} → {destination}  ({duration_s}s, {distance_m:.1f}m)")

    leg = Transit(
        start_time=start_s,
        end_time=end_s,
        duration=duration_s,
        distance=distance_m,
        mode=trip_mode,
        start_location=loc_start,
        end_location=loc_end,
        is_transfer=False,
        transit_route=DIRECT_ROUTE_MARKER[trip_mode],
    )
    return TravelPlan(
        id=random_uuid(),
        start_location=origin,
        end_location=destination,
        start_time=start_s,
        end_time=end_s,
        duration=duration_s,
        distance=distance_m,
        legs=[leg],
    )


async def warmup(city: str = "Toulouse, France", dist: int = TOULOUSE_CENTER_DIST_M) -> None:
    """Pre-load OSMnx graphs at application startup to avoid cold-start latency."""
    await _GraphStore.get(city, dist)


if __name__ == "__main__":
    import sys
    import tempfile
    import time as _ttime

    city = "Toulouse, France"
    # Smaller radius by default so the test completes quickly.
    # Pass a custom dist as first arg: python osmnx_direct.py 30000
    dist = int(sys.argv[1]) if len(sys.argv) > 1 else 30_000

    print(f"=== OSMnx save/reload test — {city}, dist={dist} m ===\n")

    # ── Step 1: build (forced, no cache) ──────────────────────────────────────
    print("[1/3] Building graphs from OSMnx (no cache)…")
    t_build_start = _ttime.monotonic()
    graphs_orig: dict = {}
    for mode in _OSMNX_MODES:
        print(f"      {mode}…", end=" ", flush=True)
        t0 = _ttime.monotonic()
        G = ox.graph_from_address(city, dist=dist, network_type=mode)
        for _, _, _, data in G.edges(keys=True, data=True):
            hwy = data.get("highway")
            if isinstance(hwy, list):
                hwy = hwy[0]
            data["speed_kph"] = _SPEEDS[mode].get(hwy, _FALLBACKS[mode])
        graphs_orig[mode] = ox.add_edge_travel_times(G)
        n, e = graphs_orig[mode].number_of_nodes(), graphs_orig[mode].number_of_edges()
        print(f"nodes={n}, edges={e}  ({_ttime.monotonic() - t0:.1f}s)")
        if e == 0:
            print(f"      ERROR: downloaded graph for {mode!r} has no edges!", file=sys.stderr)
            sys.exit(1)
    t_build = _ttime.monotonic() - t_build_start
    print(f"      → build total: {t_build:.1f}s")

    # ── Step 2: pickle save ────────────────────────────────────────────────────
    with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as tmp:
        pkl_path = Path(tmp.name)

    print(f"\n[2/3] Saving to {pkl_path}…")
    t0 = _ttime.monotonic()
    with pkl_path.open("wb") as f:
        pickle.dump(graphs_orig, f)
    size_mb = pkl_path.stat().st_size / 1_048_576
    print(f"      Written {size_mb:.1f} MB in {_ttime.monotonic() - t0:.2f}s")

    # ── Step 3: reload and validate ───────────────────────────────────────────
    print(f"\n[3/3] Reloading from {pkl_path}…")
    t0 = _ttime.monotonic()
    with pkl_path.open("rb") as f:
        graphs_loaded = pickle.load(f)
    t_load = _ttime.monotonic() - t0
    print(f"      Loaded in {t_load:.2f}s")

    ok = True
    for mode in _OSMNX_MODES:
        orig_e  = graphs_orig[mode].number_of_edges()
        load_e  = graphs_loaded[mode].number_of_edges()
        status  = "OK" if orig_e == load_e and load_e > 0 else "FAIL"
        print(f"      {mode}: before={orig_e} edges, after={load_e} edges  [{status}]")
        if status == "FAIL":
            ok = False

    pkl_path.unlink(missing_ok=True)

    print()
    if ok:
        print(f"All graphs survived the save/reload cycle correctly. (build {t_build:.1f}s, reload {t_load:.2f}s)")
    else:
        print("ERROR: edge count mismatch after reload — pickle corruption detected.", file=sys.stderr)
        sys.exit(1)
