"""congestion_zones.py — La zone de congestion de chaque nœud du graphe OSMnx (ticket 031, décision 4).

Trois zones, posées sur les NŒUDS du graphe (attribut ``zone``) ; une arête prend la zone de
son nœud d'origine :

- ``city`` — la commune de Toulouse (la frontière géocodée ``boundary`` du graphe) : profil de
  congestion TomTom « ville » (``city_raw`` de ``config/osmnx.yaml``) ;
- ``agglo`` — l'agglomération hors Toulouse : union des couronnes ``Toulouse``, ``1ere couronne``
  et ``2eme couronne`` de l'enquête EMC² (``llm_module/data/couronne_perimetre.geojson``), moins
  la ville : profil « agglomération » (``metro_raw``) ;
- ``outside`` — le reste du polygone des 453 communes (la 3ᵉ couronne) et au-delà : facteur 1,0.

POURQUOI. Jusqu'au 2026-09-03, un trajet dont un bout touchait Toulouse recevait le facteur
« ville » sur toute sa longueur, et tout autre trajet le facteur « agglomération » — y compris un
village → village de 3ᵉ couronne, à 1,84 un lundi à 8 h. Avec le graphe du polygone des 453
communes, la moitié des kilomètres routés sont ruraux : la durée congestionnée devient la somme
des temps libres des arêtes, chacun multiplié par le facteur de SA zone à l'heure de départ.

Les zones se calculent une fois : à la construction du graphe du polygone
(`build_osmnx_perimeter_graph.py`) et, pour le graphe historique de 30 km, paresseusement au
premier chargement (`_GraphStore`, `route_worker`), puis mises en cache dans le pickle. Un graphe
sans zones et sans géométrie d'agglomération disponible est une erreur explicite, pas un repli.
"""

from __future__ import annotations

import logging
import os
from collections import Counter
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

ZONE_CITY, ZONE_AGGLO, ZONE_OUTSIDE = "city", "agglo", "outside"
ZONES = (ZONE_CITY, ZONE_AGGLO, ZONE_OUTSIDE)
NODE_ZONE_KEY = "zone"
AGGLO_COURONNES = ("Toulouse", "1ere couronne", "2eme couronne")

# Où trouver la géométrie des couronnes selon l'endroit où le code tourne : dépôt (notebook,
# tests), controller Docker (`/opt/llm_module`), réplicas osmnx (`/app/llm_module/data`).
GEOJSON_CANDIDATES = (
    os.environ.get("AGGLO_GEOJSON", ""),
    str(Path(__file__).resolve().parents[2] / "llm_module" / "data" / "couronne_perimetre.geojson"),
    "/opt/llm_module/data/couronne_perimetre.geojson",
    "/app/llm_module/data/couronne_perimetre.geojson",
)


class ZoneError(RuntimeError):
    """Géométrie absente ou nœud sans zone : on refuse de deviner un facteur de congestion."""


def geojson_path(explicit: Optional[str] = None) -> Path:
    for cand in (explicit, *GEOJSON_CANDIDATES):
        if cand and Path(cand).exists():
            return Path(cand)
    raise ZoneError(
        "géométrie des couronnes introuvable (couronne_perimetre.geojson) : cherché "
        + ", ".join(c for c in (explicit, *GEOJSON_CANDIDATES) if c)
        + ". Sans elle, les zones de congestion du graphe ne se calculent pas ; montez "
          "llm_module/data ou posez AGGLO_GEOJSON.")


def agglo_polygon(explicit: Optional[str] = None):
    """Union des couronnes Toulouse + 1ʳᵉ + 2ᵉ (WGS84) — l'agglomération au sens de l'enquête."""
    import geopandas as gpd

    path = geojson_path(explicit)
    g = gpd.read_file(path)
    if g.crs is None or g.crs.to_epsg() != 4326:
        g = g.to_crs(4326)
    sel = g[g["couronne"].isin(AGGLO_COURONNES)]
    if len(sel) != len(AGGLO_COURONNES):
        raise ZoneError(f"{path} : couronnes attendues {AGGLO_COURONNES}, trouvées {sorted(sel['couronne'])}")
    return sel.union_all() if hasattr(sel, "union_all") else sel.unary_union


def assign_node_zones(G, city_geom, agglo_geom) -> Counter:
    """Pose ``zone`` sur chaque nœud de ``G`` (coordonnées ``x`` = lon, ``y`` = lat). Rend les effectifs."""
    import numpy as np
    from shapely import contains_xy, prepare

    nodes = list(G.nodes)
    if not nodes:
        return Counter()
    xs = np.fromiter((G.nodes[n]["x"] for n in nodes), dtype=float, count=len(nodes))
    ys = np.fromiter((G.nodes[n]["y"] for n in nodes), dtype=float, count=len(nodes))
    prepare(city_geom)
    prepare(agglo_geom)
    in_city = contains_xy(city_geom, xs, ys)
    in_agglo = contains_xy(agglo_geom, xs, ys)
    counts: Counter = Counter()
    for n, c, a in zip(nodes, in_city, in_agglo):
        zone = ZONE_CITY if c else ZONE_AGGLO if a else ZONE_OUTSIDE
        G.nodes[n][NODE_ZONE_KEY] = zone
        counts[zone] += 1
    return counts


def has_zones(G) -> bool:
    return all(NODE_ZONE_KEY in data for _, data in G.nodes(data=True))


def ensure_zones(graphs: dict, boundary, geojson: Optional[str] = None,
                 log: Optional[logging.Logger] = None) -> Optional[dict]:
    """Calcule les zones des graphes qui n'en ont pas. Rend ``{mode: effectifs}`` ou ``None`` si rien à faire.

    ``boundary`` : GeoDataFrame de la commune de Toulouse (``boundary_<clé>.pkl``)."""
    log = log or logger
    missing = [mode for mode, G in graphs.items() if not has_zones(G)]
    if not missing:
        return None
    city = boundary.geometry.iloc[0]
    agglo = agglo_polygon(geojson)
    counts = {}
    for mode in missing:
        counts[mode] = assign_node_zones(graphs[mode], city, agglo)
        log.info("zones de congestion posées sur le graphe %s : %s", mode, dict(counts[mode]))
    return counts
