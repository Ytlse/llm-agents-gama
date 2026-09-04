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
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
COURONNES_GEOJSON = REPO_ROOT / "llm_module" / "data" / "couronne_perimetre.geojson"

DEFAULT_ENDPOINTS = ["http://localhost:8080/otp/transmodel/v3",
                     "http://localhost:8081/otp/transmodel/v3",
                     "http://localhost:8082/otp/transmodel/v3"]
CAPITOLE = (43.6045, 1.4440)
# Les modes demandés sont ceux du runtime (`llm-agents/trip_helper/otp.py`) : un mode
# absent d'ici mesurerait une offre que les agents ne voient pas, et réciproquement.
# `legs { mode authority }` sert à compter les itinéraires qui proposent un TRAIN —
# le seul chiffre qui dise si l'ajout du mode `rail` change quelque chose.
QUERY = """
query ($from: Location!, $to: Location!, $dateTime: DateTime, $numTripPatterns: Int) {
  trip(from: $from, to: $to, dateTime: $dateTime, numTripPatterns: $numTripPatterns,
       modes: {accessMode: foot, egressMode: foot, transportModes: [{transportMode: bus}, {transportMode: metro},
               {transportMode: tram}, {transportMode: rail}, {transportMode: cableway}]}) {
    tripPatterns { duration legs { mode authority { id name } } }
    routingErrors { code description inputField }
  }
}
"""
# Modes de jambe qui comptent comme du train (transmodel v3).
MODES_TRAIN = {"rail"}


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


def classer_par_couronne(points: list, geojson: Path = COURONNES_GEOJSON) -> dict:
    """point → couronne de résidence (Toulouse, 1ᵉ, 2ᵉ, 3ᵉ, ou « hors périmètre »).

    Le manque de desserte n'est pas réparti au hasard : c'est la question posée
    par le rapport de périmètre (« sans liO, les couronnes externes n'ont qu'un
    dixième de leur offre TC »). Un total agrégé ne permet pas d'y répondre.
    """
    from shapely import contains_xy, prepare
    from shapely.geometry import shape

    if not geojson.exists():
        return {}
    couronnes = []
    for feature in json.loads(geojson.read_text(encoding="utf-8"))["features"]:
        polygone = shape(feature["geometry"])
        prepare(polygone)
        couronnes.append((feature["properties"].get("couronne", "?"), polygone))
    classement = {}
    for index, (_pid, _kind, lat, lon) in enumerate(points):
        nom = "hors perimetre"
        for libelle, polygone in couronnes:
            if contains_xy(polygone, lon, lat):
                nom = libelle
                break
        classement[index] = nom
    return classement


async def _query(session, url, lat, lon, date_time, num_trip_patterns=1):
    variables = {"from": {"coordinates": {"latitude": lat, "longitude": lon}},
                 "to": {"coordinates": {"latitude": CAPITOLE[0], "longitude": CAPITOLE[1]}},
                 "dateTime": date_time, "numTripPatterns": num_trip_patterns}
    async with session.post(url, json={"query": QUERY, "variables": variables}) as resp:
        body = await resp.json()
    trip = (body.get("data") or {}).get("trip") or {}
    errors = [e.get("code") for e in trip.get("routingErrors") or []]
    if "errors" in body and not trip:
        errors = ["GRAPHQL_ERROR:" + str(body["errors"])[:80]]
    motifs = trip.get("tripPatterns") or []
    # Modes de jambe rencontrés, et itinéraires portant au moins un train.
    modes, avec_train, autorites_train = Counter(), 0, Counter()
    for motif in motifs:
        modes_motif = {(leg.get("mode") or "").lower() for leg in motif.get("legs") or []}
        modes.update(modes_motif)
        if modes_motif & MODES_TRAIN:
            avec_train += 1
            for leg in motif.get("legs") or []:
                if (leg.get("mode") or "").lower() in MODES_TRAIN:
                    autorites_train[((leg.get("authority") or {}).get("name") or "?")] += 1
    return len(motifs), errors, modes, avec_train, autorites_train


async def run(points, endpoints, date_time, concurrency, couronnes=None, num_trip_patterns=1) -> dict:
    import aiohttp

    couronnes = couronnes or {}
    sem = asyncio.Semaphore(concurrency)
    codes, per_kind, no_pattern, link_failures = Counter(), Counter(), Counter(), []
    modes_totaux, autorites_train = Counter(), Counter()
    itineraires, itineraires_train, points_avec_train = 0, 0, 0
    par_couronne = defaultdict(lambda: {"points": 0, "sans_itineraire": 0, "erreurs": Counter(),
                                        "points_avec_train": 0, "itineraires": 0, "itineraires_avec_train": 0})
    t0 = time.monotonic()
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as session:
        async def one(i, pt):
            nonlocal itineraires, itineraires_train, points_avec_train
            pid, kind, lat, lon = pt
            async with sem:
                try:
                    n, errs, modes, avec_train, autorites = await _query(
                        session, endpoints[i % len(endpoints)], lat, lon, date_time, num_trip_patterns)
                except Exception as exc:  # réseau, timeout
                    n, errs, modes, avec_train, autorites = -1, [f"EXC:{type(exc).__name__}"], Counter(), 0, Counter()
            per_kind[kind] += 1
            modes_totaux.update(modes)
            autorites_train.update(autorites)
            couronne = couronnes.get(i)
            if couronne:
                par_couronne[couronne]["points"] += 1
            if n > 0:
                itineraires += n
                if couronne:
                    par_couronne[couronne]["itineraires"] += n
            if avec_train:
                itineraires_train += avec_train
                points_avec_train += 1
                if couronne:
                    par_couronne[couronne]["itineraires_avec_train"] += avec_train
                    par_couronne[couronne]["points_avec_train"] += 1
            if n == 0:
                no_pattern[kind] += 1
                if couronne:
                    par_couronne[couronne]["sans_itineraire"] += 1
            for c in errs:
                codes[c] += 1
                if couronne:
                    par_couronne[couronne]["erreurs"][c] += 1
                if c in ("LOCATION_NOT_FOUND", "OUTSIDE_BOUNDS") or c.startswith("EXC") or c.startswith("GRAPHQL"):
                    link_failures.append({"person_id": pid, "kind": kind, "lat": lat, "lon": lon, "code": c})
        await asyncio.gather(*(one(i, pt) for i, pt in enumerate(points)))
    return {"points": len(points), "par_type": dict(per_kind), "sans_itineraire": dict(no_pattern),
            "routing_errors": dict(codes),
            "num_trip_patterns": num_trip_patterns,
            "itineraires_rendus": itineraires,
            "itineraires_avec_train": itineraires_train,
            "points_avec_au_moins_un_itineraire_train": points_avec_train,
            "modes_de_jambe": dict(modes_totaux.most_common()),
            "autorites_du_train": dict(autorites_train.most_common()),
            "par_couronne": {nom: {**valeurs, "erreurs": dict(valeurs["erreurs"])}
                             for nom, valeurs in sorted(par_couronne.items())},
            "echecs_de_rattachement": link_failures,
            "n_echecs_de_rattachement": len(link_failures), "duree_s": round(time.monotonic() - t0, 1)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--population", type=Path, required=True)
    parser.add_argument("--endpoints", default=",".join(DEFAULT_ENDPOINTS))
    parser.add_argument("--date-time", default="2026-03-16T08:00:00+01:00", help="lundi 16 mars 2026, 8 h")
    parser.add_argument("--concurrency", type=int, default=9)
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--sans-couronnes", action="store_true",
                        help="ne pas ventiler les résultats par couronne de résidence")
    parser.add_argument("--num-trip-patterns", type=int, default=1,
                        help="itinéraires demandés par point. 1 (défaut) = la mesure de "
                             "rattachement, comparable aux relevés antérieurs ; 6 = ce que "
                             "le runtime demande (settings.gtfs.max_trip_candidates), donc "
                             "ce que l'agent se voit réellement proposer")
    args = parser.parse_args(argv)

    pop = json.loads(args.population.read_text(encoding="utf-8"))
    homes, acts = _points(pop)
    points = homes + acts
    print(f"{len(pop)} personas : {len(homes)} domiciles, {len(acts)} lieux d'activité distincts → OTP {args.date_time}",
          file=sys.stderr)
    couronnes = {} if args.sans_couronnes else classer_par_couronne(points)
    result = asyncio.run(run(points, args.endpoints.split(","), args.date_time, args.concurrency,
                             couronnes, args.num_trip_patterns))
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
