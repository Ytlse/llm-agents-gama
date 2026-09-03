"""build_osmnx_perimeter_graph.py — Les trois graphes OSMnx du polygone des 453 communes.

    llm-agents/.venv/bin/python -m scripts.data.population.build_osmnx_perimeter_graph
    llm-agents/.venv/bin/python -m scripts.data.population.build_osmnx_perimeter_graph --force --trace docs/traces/<date>_graphe_perimetre
    make osmnx-perimeter-graph

POURQUOI (ticket 031, § 1.4 ; rapport de périmètre, action O1). Le graphe de routage de la
production est un disque de 30 km autour de Toulouse téléchargé par Overpass
(`ox.graph_from_address("Toulouse, France", dist=30000)`, clé `ecb40f20a303`). Le périmètre
d'étude est le polygone des 453 communes de l'EMC² 2023 : 5 428 km², jusqu'à 62 km du Capitole.
98 des 154 agents de 3ᵉ couronne de la population scellée v3 habitent hors du disque ; leurs
trajets se rabattent sur un même nœud de graphe et reçoivent une vitesse de repli — ce ne sont
pas des itinéraires. Un polygone de 5 428 km² dépasse ce qu'Overpass sert raisonnablement
(> 100 requêtes au découpage par défaut) : les graphes se construisent ici depuis les pbf OSM
régionaux déjà présents dans le fork eqasim (`osmium extract --polygon`, puis
`graph_from_xml`), sans téléchargement.

CE QUE LE SCRIPT GARANTIT.
  * **Mêmes réseaux que la production.** Les filtres `walk` / `bike` / `drive` sont ceux
    d'OSMnx lui-même (`osmnx._overpass._get_network_filter`), lus à l'exécution et transcrits
    en prédicats Python — pas une recopie qui divergerait à la prochaine version. Marche
    bidirectionnelle comme chez OSMnx (`settings.bidirectional_network_types`).
  * **Mêmes vitesses que la production.** `speed_kph` par type de voie vient de
    `trip_helper.osmnx_direct._SPEEDS` / `_FALLBACKS` (config/osmnx.yaml), et
    `ox.add_edge_travel_times` pose les temps de parcours — le code de `_GraphStore._build_sync`
    à l'identique.
  * **Une clé de cache distincte.** `graphs_<clé>.pkl` / `boundary_<clé>.pkl` dans
    `data/cache/osmnx/`, clé = md5(`PERIMETER_GRAPH_LABEL`)[:12] — le label dit le périmètre, la
    version de la table des communes et la date des pbf. Le disque de 30 km reste intact.
  * **Les zones de congestion sont posées sur les nœuds** (`zone` : `city` = commune de Toulouse,
    `agglo` = couronnes Toulouse + 1ʳᵉ + 2ᵉ hors Toulouse, `outside` = le reste ; ticket 031,
    décision 4) : `_route_sync` congestionne chaque arête selon la zone de son nœud d'origine.
    `boundary_<clé>.pkl` est la commune de Toulouse, copiée depuis le cache du disque de 30 km
    (aucun géocodage réseau). `--zones-only` (re)pose les zones sur un pickle existant.
  * **Un journal qui se relit.** Durées de chaque étape, nœuds et arêtes par mode, taille du
    pickle, mémoire de pointe, écrits sur stderr et, avec `--trace`, dans un dossier horodaté
    (`mesures.json`, `README.md`). Un fichier `graphs_<clé>.meta.json` porte la provenance à
    côté du pickle.

CE QUE LE SCRIPT NE FAIT PAS. Il ne touche ni au runtime (`osmnx_server.py`, `osmnx_direct.py`,
`geography.py` : partie 2 du ticket) ni au cache SQLite d'itinéraires. Il ne télécharge rien.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import pickle
import re
import resource
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
LLMAGENTS_PATH = REPO_ROOT / "llm-agents"
for _p in (str(REPO_ROOT), str(LLMAGENTS_PATH)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

logger = logging.getLogger("osmnx.perimetre")

# ── Identité du graphe ────────────────────────────────────────────────────────
# Le label dit ce que le graphe couvre et d'où il vient ; la clé en dérive. Changer les pbf
# (millésime), la table des communes (version `cc1`) ou le périmètre change la clé — et donc
# le cache — au lieu de resservir un vieux graphe sous un nom neuf.
# Définies dans `llm-agents/geography.py` depuis la partie 2 du ticket 031 : le runtime
# (`osmnx_server`, `osmnx_direct`) sert ce graphe-là, une seule définition de la clé.
from geography import PERIMETER_CACHE_KEY, PERIMETER_GRAPH_LABEL  # noqa: E402
from geography import PRODUCTION_CACHE_KEY_30KM as PRODUCTION_CACHE_KEY  # noqa: E402  (disque de 30 km : frontière réutilisée)

COURONNE_GEOJSON = REPO_ROOT / "llm_module" / "data" / "couronne_perimetre.geojson"
COMMUNE_TABLE = REPO_ROOT / "llm_module" / "data" / "commune_couronne.json"
OSM_PBF_SOURCES = [
    REPO_ROOT / "eqasim-toulouse" / "data" / "osm_toulouse" / "midi-pyrenees-220101.osm.pbf",
    REPO_ROOT / "eqasim-toulouse" / "data" / "osm_toulouse" / "languedoc-roussillon-220101.osm.pbf",
]
OSMNX_CACHE_DIR = REPO_ROOT / "data" / "cache" / "osmnx"
WORK_DIR = OSMNX_CACHE_DIR / "perimetre_453"      # extraits intermédiaires (pbf, xml)
OSMIUM = shutil.which("osmium") or "/opt/homebrew/bin/osmium"

OSMNX_MODES = ("walk", "bike", "drive")


# ── Filtres réseau OSMnx → prédicats Python ───────────────────────────────────

_FILTER_RE = re.compile(r'\["([^"]+)"(?:(!~|~|!=|=)"([^"]*)")?\]')


def parse_overpass_filter(way_filter: str) -> list[tuple[str, Optional[str], Optional[str]]]:
    """`["highway"]["area"!~"yes"]…` → [("highway", None, None), ("area", "!~", "yes"), …].

    Refuse une chaîne qu'il ne sait pas lire entièrement : un filtre partiellement compris
    laisserait passer des voies que la production exclut, sans le dire.
    """
    clauses = _FILTER_RE.findall(way_filter)
    rebuilt = "".join(f'["{k}"]' if not op else f'["{k}"{op}"{v}"]' for k, op, v in clauses)
    if rebuilt != way_filter:
        raise ValueError(f"filtre Overpass non entièrement analysé :\n  {way_filter}\n  {rebuilt}")
    return [(k, op or None, v if op else None) for k, op, v in clauses]


def way_predicate(way_filter: str) -> Callable[[dict], bool]:
    """Prédicat « cette voie passe le filtre Overpass » sur le dict de tags d'un way.

    Sémantique Overpass : `["k"]` → la clé existe ; `["k"!~"re"]` → la clé est absente ou sa
    valeur ne contient pas le motif (`re.search`, non ancré, comme Overpass) ; `["k"~"re"]` →
    présente et le motif s'y trouve ; `["k"="v"]` / `["k"!="v"]` → égalité stricte.
    """
    clauses = parse_overpass_filter(way_filter)
    compiled = [(k, op, re.compile(v) if op in ("~", "!~") else v) for k, op, v in clauses]

    def _ok(tags: dict) -> bool:
        for k, op, v in compiled:
            val = tags.get(k)
            if op is None:
                if val is None:
                    return False
            elif op == "!~":
                if val is not None and v.search(str(val)):
                    return False
            elif op == "~":
                if val is None or not v.search(str(val)):
                    return False
            elif op == "=":
                if val is None or str(val) != v:
                    return False
            elif op == "!=":
                if val is not None and str(val) == v:
                    return False
        return True

    return _ok


def network_filters() -> dict[str, str]:
    """Les filtres Overpass d'OSMnx pour les trois modes, lus dans la version installée."""
    from osmnx._overpass import _get_network_filter
    return {mode: _get_network_filter(mode) for mode in OSMNX_MODES}


# ── Étapes ────────────────────────────────────────────────────────────────────

def _run(cmd: list[str], label: str) -> float:
    t0 = time.monotonic()
    logger.info("%s — début : %s", label, " ".join(str(c) for c in cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    dt = time.monotonic() - t0
    if proc.returncode != 0:
        logger.error("[ALARME] %s a échoué (code %d) après %.1fs : %s", label, proc.returncode, dt,
                     (proc.stderr or proc.stdout).strip()[-800:])
        raise RuntimeError(f"{label} : code {proc.returncode}")
    logger.info("%s — fin en %.1fs", label, dt)
    return dt


def _mb(path: Path) -> float:
    return path.stat().st_size / 1_048_576 if path.exists() else 0.0


def perimeter_polygon(geojson: Path, out: Path) -> dict:
    """Union des quatre couronnes → un GeoJSON à une seule géométrie, pour `osmium extract -p`."""
    import geopandas as gpd

    g = gpd.read_file(geojson)
    if g.crs is None or g.crs.to_epsg() != 4326:
        g = g.to_crs(4326)
    union = g.union_all() if hasattr(g, "union_all") else g.unary_union
    area_km2 = gpd.GeoSeries([union], crs=4326).to_crs(2154).area.iloc[0] / 1e6
    out.parent.mkdir(parents=True, exist_ok=True)
    gpd.GeoDataFrame({"name": ["perimetre_453_communes"]}, geometry=[union], crs=4326).to_file(
        out, driver="GeoJSON")
    bounds = [round(b, 5) for b in union.bounds]
    logger.info("polygone du périmètre : %s, %.0f km², emprise %s", union.geom_type, area_km2, bounds)
    return {"geom_type": union.geom_type, "area_km2": round(area_km2, 1), "bounds_wgs84": bounds,
            "n_couronnes": int(len(g))}


def extract_highways_xml(polygon: Path, sources: list[Path], work: Path, force: bool) -> tuple[Path, dict]:
    """pbf régionaux → extrait par polygone → fusion → voies `highway` en XML `.osm`."""
    work.mkdir(parents=True, exist_ok=True)
    xml_path = work / "perimetre_453_highway.osm"
    journal: dict = {"etapes_s": {}, "tailles_mo": {}}
    if xml_path.exists() and not force:
        logger.info("extrait XML déjà présent (%.0f Mo) : %s — --force pour le refaire", _mb(xml_path), xml_path)
        journal["reutilise"] = True
        journal["tailles_mo"]["highway.osm"] = round(_mb(xml_path), 1)
        return xml_path, journal
    missing = [str(p) for p in sources if not p.exists()]
    if missing:
        raise FileNotFoundError(f"pbf OSM absents : {missing}")
    extracts = []
    for src in sources:
        dst = work / f"ext_{src.stem}.pbf"
        journal["etapes_s"][f"extract {src.name}"] = round(
            _run([OSMIUM, "extract", "-p", str(polygon), "-s", "smart", "--overwrite", "-o", str(dst), str(src)],
                 f"osmium extract {src.name}"), 1)
        journal["tailles_mo"][dst.name] = round(_mb(dst), 1)
        extracts.append(dst)
    merged = work / "perimetre_453.osm.pbf"
    journal["etapes_s"]["merge"] = round(
        _run([OSMIUM, "merge", "--overwrite", "-o", str(merged), *map(str, extracts)], "osmium merge"), 1)
    journal["tailles_mo"][merged.name] = round(_mb(merged), 1)
    journal["etapes_s"]["tags-filter highway → xml"] = round(
        _run([OSMIUM, "tags-filter", "--overwrite", "-o", str(xml_path), str(merged), "w/highway"],
             "osmium tags-filter w/highway"), 1)
    journal["tailles_mo"]["highway.osm"] = round(_mb(xml_path), 1)
    return xml_path, journal


def build_graphs(xml_path: Path, speeds: dict, fallbacks: dict) -> tuple[dict, dict]:
    """Un graphe par mode, aux filtres et vitesses de la production."""
    import osmnx as ox
    from osmnx import settings as ox_settings
    from osmnx._osm_xml import _overpass_json_from_xml
    from osmnx.graph import _create_graph

    t0 = time.monotonic()
    response = _overpass_json_from_xml(xml_path, "utf-8")
    elements = response["elements"]
    nodes = [e for e in elements if e["type"] == "node"]
    ways = [e for e in elements if e["type"] == "way"]
    node_by_id = {n["id"]: n for n in nodes}
    journal: dict = {"xml_lecture_s": round(time.monotonic() - t0, 1),
                     "noeuds_xml": len(nodes), "voies_highway_xml": len(ways), "modes": {}}
    logger.info("XML lu en %.1fs : %d nœuds, %d voies highway", journal["xml_lecture_s"], len(nodes), len(ways))

    filters = network_filters()
    graphs: dict = {}
    for mode in OSMNX_MODES:
        t1 = time.monotonic()
        keep = way_predicate(filters[mode])
        mode_ways = [w for w in ways if keep(w.get("tags", {}))]
        needed = {nid for w in mode_ways for nid in w["nodes"]}
        mode_nodes = [node_by_id[nid] for nid in needed if nid in node_by_id]
        bidirectional = mode in ox_settings.bidirectional_network_types
        G = _create_graph([{"elements": mode_nodes + mode_ways}], bidirectional)
        n_raw, e_raw = G.number_of_nodes(), G.number_of_edges()
        G = ox.truncate.largest_component(G, strongly=False)
        G = ox.simplification.simplify_graph(G)
        # Vitesses de la production, à l'identique de `_GraphStore._build_sync`.
        n_fallback = 0
        for _, _, _, data in G.edges(keys=True, data=True):
            hwy = data.get("highway")
            if isinstance(hwy, list):
                hwy = hwy[0]
            if hwy in speeds[mode]:
                data["speed_kph"] = speeds[mode][hwy]
            else:
                data["speed_kph"] = fallbacks[mode]
                n_fallback += 1
        G = ox.add_edge_travel_times(G)
        graphs[mode] = G
        journal["modes"][mode] = {
            "filtre_overpass": filters[mode], "bidirectionnel": bidirectional,
            "voies_retenues": len(mode_ways), "noeuds_bruts": n_raw, "aretes_brutes": e_raw,
            "noeuds": G.number_of_nodes(), "aretes": G.number_of_edges(),
            "aretes_vitesse_repli": n_fallback,
            "part_aretes_vitesse_repli_pct": round(100.0 * n_fallback / max(G.number_of_edges(), 1), 1),
            "duree_s": round(time.monotonic() - t1, 1),
        }
        logger.info("graphe %-5s : %d voies → %d nœuds / %d arêtes (simplifié ; brut %d / %d), "
                    "%d arêtes en vitesse de repli (%.1f %%), %.1fs", mode, len(mode_ways),
                    G.number_of_nodes(), G.number_of_edges(), n_raw, e_raw, n_fallback,
                    journal["modes"][mode]["part_aretes_vitesse_repli_pct"], time.monotonic() - t1)
    journal["construction_s"] = round(time.monotonic() - t0, 1)
    return graphs, journal


def respeed_graphs(graphs: dict, speeds: dict, fallbacks: dict) -> dict:
    """Repose `speed_kph` et `travel_time` de chaque arête depuis la config courante ; journal par mode.

    Sert quand `config/osmnx.yaml` change (ticket 031 partie 2, action O3 : vitesses vélo pour
    `track`, `service`, `trunk`, `*_link`…) : le pickle porte les vitesses de sa construction, la
    config seule ne suffit pas. Ne reconstruit rien d'autre — nœuds, arêtes, zones restent.
    """
    import osmnx as ox
    from collections import Counter

    journal: dict = {}
    for mode, G in graphs.items():
        t1 = time.monotonic()
        n_fallback = n_changed = 0
        en_repli: Counter = Counter()
        for _, _, _, data in G.edges(keys=True, data=True):
            hwy = data.get("highway")
            if isinstance(hwy, list):
                hwy = hwy[0]
            new = speeds[mode].get(hwy)
            if new is None:
                new = fallbacks[mode]
                n_fallback += 1
                en_repli[str(hwy)] += 1
            if data.get("speed_kph") != new:
                n_changed += 1
            data["speed_kph"] = new
        ox.add_edge_travel_times(G)
        journal[mode] = {
            "aretes": G.number_of_edges(), "aretes_modifiees": n_changed,
            "aretes_vitesse_repli": n_fallback,
            "part_aretes_vitesse_repli_pct": round(100.0 * n_fallback / max(G.number_of_edges(), 1), 1),
            "types_en_repli": dict(en_repli.most_common(10)), "duree_s": round(time.monotonic() - t1, 1),
        }
        logger.info("vitesses reposées sur %-5s : %d arêtes modifiées / %d, %d en repli (%.1f %%) : %s — %.1fs",
                    mode, n_changed, G.number_of_edges(), n_fallback,
                    journal[mode]["part_aretes_vitesse_repli_pct"], dict(en_repli.most_common(6)),
                    time.monotonic() - t1)
    return journal


def city_geometry(cache_dir: Path):
    """La commune de Toulouse (frontière géocodée du graphe de production)."""
    b_path = cache_dir / f"boundary_{PRODUCTION_CACHE_KEY}.pkl"
    if not b_path.exists():
        raise FileNotFoundError(f"frontière de Toulouse absente : {b_path}")
    with b_path.open("rb") as fh:
        return pickle.load(fh).geometry.iloc[0]


def assign_zones(graphs: dict, cache_dir: Path) -> dict:
    """Zones de congestion des nœuds (ticket 031, décision 4) : ville / agglomération / extérieur."""
    from trip_helper.congestion_zones import agglo_polygon, assign_node_zones

    city = city_geometry(cache_dir)
    agglo = agglo_polygon()
    journal = {}
    for mode, G in graphs.items():
        t0 = time.monotonic()
        counts = assign_node_zones(G, city, agglo)
        journal[mode] = {**dict(counts), "duree_s": round(time.monotonic() - t0, 1)}
        logger.info("zones de congestion %-5s : %s (%.1fs)", mode, dict(counts), time.monotonic() - t0)
    return journal


def production_speeds() -> tuple[dict, dict]:
    """`_SPEEDS` / `_FALLBACKS` de la production — importés, jamais recopiés."""
    from trip_helper.osmnx_direct import _FALLBACKS, _SPEEDS
    return _SPEEDS, _FALLBACKS


def write_cache(graphs: dict, cache_dir: Path, key: str, force: bool) -> dict:
    cache_dir.mkdir(parents=True, exist_ok=True)
    g_path = cache_dir / f"graphs_{key}.pkl"
    b_path = cache_dir / f"boundary_{key}.pkl"
    prod_boundary = cache_dir / f"boundary_{PRODUCTION_CACHE_KEY}.pkl"
    if g_path.exists() and not force:
        raise FileExistsError(f"{g_path} existe déjà — --force pour le réécrire")
    t0 = time.monotonic()
    with g_path.open("wb") as fh:
        pickle.dump(graphs, fh)
    pickle_s = time.monotonic() - t0
    if not b_path.exists() or force:
        if not prod_boundary.exists():
            raise FileNotFoundError(
                f"frontière de Toulouse absente : {prod_boundary}. Elle vient du cache du graphe de "
                "production (géocodage Nominatim de « Toulouse, France ») ; rien n'est téléchargé ici.")
        shutil.copy2(prod_boundary, b_path)
    logger.info("pickle écrit : %s (%.0f Mo, %.1fs) ; frontière : %s", g_path.name, _mb(g_path), pickle_s, b_path.name)
    return {"graphs_pkl": str(g_path), "graphs_pkl_mo": round(_mb(g_path), 1), "pickle_s": round(pickle_s, 1),
            "boundary_pkl": str(b_path), "boundary_source": str(prod_boundary)}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def write_trace(mesures: dict, trace_dir: Path) -> None:
    trace_dir.mkdir(parents=True, exist_ok=True)
    (trace_dir / "mesures.json").write_text(json.dumps(mesures, ensure_ascii=False, indent=1), encoding="utf-8")
    modes = mesures["graphes"]["modes"]
    lines = [f"# Graphes OSMnx du polygone des 453 communes — {mesures['date']}", "",
             f"Produit par `scripts/data/population/build_osmnx_perimeter_graph.py` (ticket 031 § 1.4, action O1).",
             f"Clé de cache `{mesures['cache_key']}` (label `{mesures['label']}`), pickle "
             f"{mesures['cache']['graphs_pkl_mo']} Mo, polygone {mesures['polygone']['area_km2']} km².", "",
             "| Mode | Voies retenues | Nœuds | Arêtes | Arêtes en vitesse de repli | Durée |",
             "|---|---:|---:|---:|---:|---:|"]
    for mode, m in modes.items():
        lines.append(f"| {mode} | {m['voies_retenues']} | {m['noeuds']} | {m['aretes']} | "
                     f"{m['aretes_vitesse_repli']} ({m['part_aretes_vitesse_repli_pct']} %) | {m['duree_s']} s |")
    lines += ["", f"Mémoire de pointe du processus de construction : {mesures['ram_pointe_mo']} Mo ; "
              f"durée totale {mesures['duree_totale_s']} s.", "",
              "Les filtres réseau sont ceux d'OSMnx " + mesures["osmnx_version"] + " (voir `mesures.json`).", ""]
    (trace_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
    logger.info("trace archivée → %s", trace_dir)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="refaire l'extrait et réécrire le pickle")
    parser.add_argument("--zones-only", action="store_true",
                        help="ne (re)poser que les zones de congestion sur le pickle existant, sans reconstruire")
    parser.add_argument("--respeed", action="store_true",
                        help="reposer les vitesses de config/osmnx.yaml (speed_kph, travel_time) sur le pickle "
                             "existant, sans reconstruire — après toute modification de `speeds`")
    parser.add_argument("--trace", type=Path, default=None, help="dossier de trace horodaté (docs/traces/…)")
    parser.add_argument("--cache-dir", type=Path, default=OSMNX_CACHE_DIR)
    parser.add_argument("--work-dir", type=Path, default=WORK_DIR)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s — %(message)s")

    import osmnx as ox
    t0 = time.monotonic()
    logger.info("graphe du périmètre — début : label %s, clé %s, osmnx %s", PERIMETER_GRAPH_LABEL,
                PERIMETER_CACHE_KEY, ox.__version__)
    if not Path(OSMIUM).exists():
        logger.error("[ALARME] osmium introuvable (%s) — `brew install osmium-tool`", OSMIUM)
        return 2
    g_path = args.cache_dir / f"graphs_{PERIMETER_CACHE_KEY}.pkl"
    if args.zones_only:
        if not g_path.exists():
            logger.error("[ALARME] --zones-only : pas de pickle %s", g_path)
            return 2
        with g_path.open("rb") as fh:
            graphs = pickle.load(fh)
        zones = assign_zones(graphs, args.cache_dir)
        with g_path.open("wb") as fh:
            pickle.dump(graphs, fh)
        meta_path = args.cache_dir / f"graphs_{PERIMETER_CACHE_KEY}.meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        meta.setdefault("graphes", {})["zones_congestion"] = zones
        meta["zones_posees_le"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        logger.info("zones posées et pickle réécrit (%.0f Mo) en %.1fs", _mb(g_path), time.monotonic() - t0)
        return 0
    if args.respeed:
        if not g_path.exists():
            logger.error("[ALARME] --respeed : pas de pickle %s", g_path)
            return 2
        with g_path.open("rb") as fh:
            graphs = pickle.load(fh)
        speeds, fallbacks = production_speeds()
        journal = respeed_graphs(graphs, speeds, fallbacks)
        tmp = g_path.with_suffix(".pkl.tmp")
        with tmp.open("wb") as fh:
            pickle.dump(graphs, fh)
        tmp.replace(g_path)
        meta_path = args.cache_dir / f"graphs_{PERIMETER_CACHE_KEY}.meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        for mode, j in journal.items():
            meta.setdefault("graphes", {}).setdefault("modes", {}).setdefault(mode, {}).update(
                {"aretes_vitesse_repli": j["aretes_vitesse_repli"],
                 "part_aretes_vitesse_repli_pct": j["part_aretes_vitesse_repli_pct"]})
        meta["vitesses"] = {"source": "trip_helper.osmnx_direct._SPEEDS / _FALLBACKS (config/osmnx.yaml)",
                            "speeds_kph": speeds, "fallbacks_kph": fallbacks, "reposees_le":
                            datetime.now(timezone.utc).isoformat(timespec="seconds"), "journal": journal}
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        ram_mo = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1_048_576 if sys.platform == "darwin" else 1024)
        logger.info("vitesses reposées et pickle réécrit (%.0f Mo) en %.1fs ; RAM de pointe %d Mo",
                    _mb(g_path), time.monotonic() - t0, round(ram_mo))
        if args.trace:
            args.trace.mkdir(parents=True, exist_ok=True)
            (args.trace / "respeed.json").write_text(json.dumps(
                {"date": meta["vitesses"]["reposees_le"], "cache_key": PERIMETER_CACHE_KEY, "journal": journal,
                 "speeds_kph": speeds, "fallbacks_kph": fallbacks, "duree_s": round(time.monotonic() - t0, 1),
                 "ram_pointe_mo": round(ram_mo)}, ensure_ascii=False, indent=1), encoding="utf-8")
        return 0
    if g_path.exists() and not args.force:
        logger.info("graphes déjà en cache : %s (%.0f Mo) — --force pour reconstruire", g_path, _mb(g_path))
        return 0

    polygon_path = args.work_dir / "perimetre_453_communes.geojson"
    poly = perimeter_polygon(COURONNE_GEOJSON, polygon_path)
    xml_path, extract_journal = extract_highways_xml(polygon_path, OSM_PBF_SOURCES, args.work_dir, args.force)
    speeds, fallbacks = production_speeds()
    graphs, build_journal = build_graphs(xml_path, speeds, fallbacks)
    build_journal["zones_congestion"] = assign_zones(graphs, args.cache_dir)
    cache_journal = write_cache(graphs, args.cache_dir, PERIMETER_CACHE_KEY, args.force)

    ram_mo = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1_048_576 if sys.platform == "darwin" else 1024)
    mesures = {
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "label": PERIMETER_GRAPH_LABEL, "cache_key": PERIMETER_CACHE_KEY, "osmnx_version": ox.__version__,
        "polygone": {**poly, "source": str(COURONNE_GEOJSON), "communes": str(COMMUNE_TABLE)},
        "sources_pbf": [{"fichier": str(p), "mo": round(_mb(p), 1)} for p in OSM_PBF_SOURCES],
        "extraction": extract_journal, "graphes": build_journal, "cache": cache_journal,
        "vitesses": {"source": "trip_helper.osmnx_direct._SPEEDS / _FALLBACKS (config/osmnx.yaml)",
                     "fallbacks_kph": fallbacks},
        "ram_pointe_mo": round(ram_mo), "duree_totale_s": round(time.monotonic() - t0, 1),
    }
    (args.cache_dir / f"graphs_{PERIMETER_CACHE_KEY}.meta.json").write_text(
        json.dumps(mesures, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.trace:
        write_trace(mesures, args.trace)
    logger.info("graphe du périmètre — fin en %.1fs : %s ; RAM de pointe %d Mo", mesures["duree_totale_s"],
                ", ".join(f"{m} {j['noeuds']} nœuds / {j['aretes']} arêtes" for m, j in build_journal["modes"].items()),
                round(ram_mo))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
