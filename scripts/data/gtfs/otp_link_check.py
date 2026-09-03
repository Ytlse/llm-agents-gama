"""Contrôle de rattachement OTP d'une population : zéro « Couldn't link » attendu (ticket 031, critère 2).

Pour chaque domicile et chaque lieu d'activité distinct d'un fichier de population, interroge OTP
(Transmodel v3) pour un trajet en transports collectifs vers un point de référence (le Capitole)
à une heure donnée, et compte les `routingErrors` par code — `LOCATION_NOT_FOUND` est le
« Couldn't link » d'OTP 2 (point trop loin de toute rue du graphe), `OUTSIDE_BOUNDS` un point hors
de l'emprise du graphe, `NO_STOPS_IN_RANGE` un point sans arrêt accessible (pas un défaut de graphe :
la 3ᵉ couronne rurale n'a pas de TC). Les instances sont interrogées en tournante.

    llm-agents/.venv/bin/python scripts/data/gtfs/otp_link_check.py \
        --population data/population/population_1000_AAMAS_v4/population.json \
        --json docs/traces/<trace>/otp_link_check.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import Counter
from pathlib import Path

DEFAULT_ENDPOINTS = ["http://localhost:8080/otp/transmodel/v3",
                     "http://localhost:8081/otp/transmodel/v3",
                     "http://localhost:8082/otp/transmodel/v3"]
CAPITOLE = (43.6045, 1.4440)
QUERY = """
query ($from: Location!, $to: Location!, $dateTime: DateTime) {
  trip(from: $from, to: $to, dateTime: $dateTime, numTripPatterns: 1,
       modes: {accessMode: foot, egressMode: foot, transportModes: [{transportMode: bus}, {transportMode: metro},
               {transportMode: tram}, {transportMode: rail}, {transportMode: cableway}]}) {
    tripPatterns { duration }
    routingErrors { code description inputField }
  }
}
"""


def _points(pop: list) -> tuple[list, list]:
    homes, acts, seen = [], [], set()
    for e in pop:
        ident = e.get("identity") or {}
        h = ident.get("home") or {}
        if h.get("lat") is not None:
            homes.append((e["person_id"], "home", float(h["lat"]), float(h["lon"])))
        for a in ident.get("activities") or []:
            if a.get("purpose") == "home":
                continue
            loc = a.get("location") or {}
            if loc.get("lat") is None:
                continue
            key = (round(float(loc["lat"]), 5), round(float(loc["lon"]), 5))
            if key in seen:
                continue
            seen.add(key)
            acts.append((e["person_id"], a.get("purpose", "?"), float(loc["lat"]), float(loc["lon"])))
    return homes, acts


async def _query(session, url, lat, lon, date_time):
    variables = {"from": {"coordinates": {"latitude": lat, "longitude": lon}},
                 "to": {"coordinates": {"latitude": CAPITOLE[0], "longitude": CAPITOLE[1]}},
                 "dateTime": date_time}
    async with session.post(url, json={"query": QUERY, "variables": variables}) as resp:
        body = await resp.json()
    trip = (body.get("data") or {}).get("trip") or {}
    errors = [e.get("code") for e in trip.get("routingErrors") or []]
    if "errors" in body and not trip:
        errors = ["GRAPHQL_ERROR:" + str(body["errors"])[:80]]
    return len(trip.get("tripPatterns") or []), errors


async def run(points, endpoints, date_time, concurrency) -> dict:
    import aiohttp

    sem = asyncio.Semaphore(concurrency)
    codes, per_kind, no_pattern, link_failures = Counter(), Counter(), Counter(), []
    t0 = time.monotonic()
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as session:
        async def one(i, pt):
            pid, kind, lat, lon = pt
            async with sem:
                try:
                    n, errs = await _query(session, endpoints[i % len(endpoints)], lat, lon, date_time)
                except Exception as exc:  # réseau, timeout
                    n, errs = -1, [f"EXC:{type(exc).__name__}"]
            per_kind[kind] += 1
            if n == 0:
                no_pattern[kind] += 1
            for c in errs:
                codes[c] += 1
                if c in ("LOCATION_NOT_FOUND", "OUTSIDE_BOUNDS") or c.startswith("EXC") or c.startswith("GRAPHQL"):
                    link_failures.append({"person_id": pid, "kind": kind, "lat": lat, "lon": lon, "code": c})
        await asyncio.gather(*(one(i, pt) for i, pt in enumerate(points)))
    return {"points": len(points), "par_type": dict(per_kind), "sans_itineraire": dict(no_pattern),
            "routing_errors": dict(codes), "echecs_de_rattachement": link_failures,
            "n_echecs_de_rattachement": len(link_failures), "duree_s": round(time.monotonic() - t0, 1)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--population", type=Path, required=True)
    parser.add_argument("--endpoints", default=",".join(DEFAULT_ENDPOINTS))
    parser.add_argument("--date-time", default="2026-03-16T08:00:00+01:00", help="lundi 16 mars 2026, 8 h")
    parser.add_argument("--concurrency", type=int, default=9)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)

    pop = json.loads(args.population.read_text(encoding="utf-8"))
    homes, acts = _points(pop)
    print(f"{len(pop)} personas : {len(homes)} domiciles, {len(acts)} lieux d'activité distincts → OTP {args.date_time}",
          file=sys.stderr)
    result = asyncio.run(run(homes + acts, args.endpoints.split(","), args.date_time, args.concurrency))
    result.update({"population": str(args.population), "date_time": args.date_time, "reference": CAPITOLE})
    print(json.dumps({k: v for k, v in result.items() if k != "echecs_de_rattachement"}, ensure_ascii=False, indent=1))
    if result["echecs_de_rattachement"]:
        print(f"[ALARME] {result['n_echecs_de_rattachement']} point(s) non rattaché(s) au graphe OTP "
              f"(LOCATION_NOT_FOUND / OUTSIDE_BOUNDS)", file=sys.stderr)
        for f in result["echecs_de_rattachement"][:10]:
            print("  ", f, file=sys.stderr)
    if args.json:
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if result["echecs_de_rattachement"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
