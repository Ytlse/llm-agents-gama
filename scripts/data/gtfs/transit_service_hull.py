"""Enveloppe de desserte TC — `TOULOUSE_TRANSIT_SERVICE_WKT` de `llm-agents/geography.py` (ticket 031, T4).

Enveloppe concave des arrêts GTFS que le graphe OTP dessert **dans le polygone des 453 communes** :
tous les arrêts Tisséo, et les arrêts TER situés dans le polygone (le feed TER couvre toute
l'Occitanie ; un arrêt hors du polygone est atteignable en train mais son voisinage n'est pas dans
le graphe de rue d'OTP, construit sur l'extrait OSM du polygone).

Sert à la visualisation (`vizpop.py`) et à la documentation ; le runtime ne filtre pas dessus.

    llm-agents/.venv/bin/python scripts/data/gtfs/transit_service_hull.py [--ratio 0.3] [--json sortie.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "llm-agents")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

GTFS_DIR = REPO_ROOT / "data" / "gtfs"
FEEDS = {"tisseo": GTFS_DIR / "tisseo_gtfs" / "stops.txt", "ter": GTFS_DIR / "ter_gtfs" / "stops.txt"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ratio", type=float, default=0.3,
                        help="ratio de shapely.concave_hull (0 = très concave, 1 = enveloppe convexe)")
    parser.add_argument("--json", type=Path, default=None, help="écrit le WKT et les comptes dans ce fichier")
    args = parser.parse_args(argv)

    import pandas as pd
    from shapely import MultiPoint, concave_hull, contains_xy, prepare, set_precision
    from inputs.population.perimeter import PopulationPerimeter

    perimeter = PopulationPerimeter.load()
    prepare(perimeter.polygon)
    counts, pts = {}, []
    for name, path in FEEDS.items():
        df = pd.read_csv(path, usecols=["stop_lat", "stop_lon"]).dropna()
        inside = contains_xy(perimeter.polygon, df["stop_lon"].to_numpy(), df["stop_lat"].to_numpy())
        kept = df[inside] if name == "ter" else df
        counts[name] = {"arrets": int(len(df)), "dans_le_polygone": int(inside.sum()), "retenus": int(len(kept))}
        pts.extend(zip(kept["stop_lon"].tolist(), kept["stop_lat"].tolist()))
    hull = concave_hull(MultiPoint(pts), ratio=args.ratio)
    hull = set_precision(hull, 1e-5)
    wkt = hull.wkt
    out = {"ratio": args.ratio, "arrets": counts, "n_points": len(pts), "n_sommets": len(hull.exterior.coords),
           "aire_km2": round(hull.area * 111.32 * 111.32 * 0.72, 1), "bounds": list(hull.bounds), "wkt": wkt}
    print(json.dumps({k: v for k, v in out.items() if k != "wkt"}, ensure_ascii=False, indent=1))
    print(wkt)
    if args.json:
        args.json.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
