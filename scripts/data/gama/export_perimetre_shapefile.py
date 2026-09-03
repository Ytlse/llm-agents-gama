"""Exporte le polygone du périmètre des 453 communes en shapefile WGS84 pour GAMA (ticket 031, G1).

    llm-agents/.venv/bin/python scripts/data/gama/export_perimetre_shapefile.py

Produit `GAMA/CityTransport/includes/perimetre_453.shp` (+ .shx/.dbf/.prj/.cpg), une seule entité :
le polygone dissous des quatre couronnes de `llm_module/data/couronne_perimetre.geojson` (EPSG:4326,
comme `routes.shp` et `stops.shp`). `Settings.gaml` en fait l'emprise du monde
(`geometry shape <- envelope(perimetre_shape_file)`) à la place de l'enveloppe des lignes Tisséo,
qui laissait 163 domiciles de la population dehors (rapport de périmètre du 2026-09-03).

Le dossier `includes/` n'est pas versionné : ce script est la recette. Les attributs portent la
provenance (label, version de la table des communes, date d'export).
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "llm-agents")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

INCLUDES = REPO_ROOT / "GAMA" / "CityTransport" / "includes"
OUT = INCLUDES / "perimetre_453.shp"


def main() -> int:
    import geopandas as gpd
    from inputs.population.perimeter import PERIMETER_LABEL, PopulationPerimeter

    perimeter = PopulationPerimeter.load()
    version = (perimeter.communes.meta or {}).get("version", "?")
    gdf = gpd.GeoDataFrame(
        {"label": [PERIMETER_LABEL], "communes": [len(perimeter.communes)], "table_v": [str(version)],
         "exporte_le": [date.today().isoformat()]},
        geometry=[perimeter.polygon], crs="EPSG:4326")
    INCLUDES.mkdir(parents=True, exist_ok=True)
    gdf.to_file(OUT)
    b = perimeter.bbox
    info = {"fichier": str(OUT), "crs": "EPSG:4326", "geom_type": perimeter.polygon.geom_type,
            "bounds": [b.min_lon, b.min_lat, b.max_lon, b.max_lat], "communes": len(perimeter.communes),
            "table_version": version, "date": date.today().isoformat()}
    print(json.dumps(info, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
