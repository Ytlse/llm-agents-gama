"""Exporte les couches GAMA des lignes et des arrêts TC (ticket 031, G2).

    llm-agents/.venv/bin/python scripts/data/gama/export_gtfs_layers.py

Produit `GAMA/CityTransport/includes/routes.shp` et `stops.shp` à partir de **plusieurs** feeds
GTFS — Tisséo, TER et liO — là où ces couches ne portaient que Tisséo. Les couches précédentes
sont déplacées à côté, horodatées, jamais supprimées.

Ce que GAMA lit, et qui fixe le schéma (`PublicTransport.gaml`) :
`routes.shp` → `color`, `route_type`, `shape_id`, `route_id` ; `stops.shp` → `stop_name`,
`stop_id`, `route_type`. Le `shape_id` sert de jointure avec les itinéraires rendus par OTP
(`Inhabitant.gaml` : `shape_id_list contains each.shape_id`) : **les identifiants ne sont donc
jamais préfixés ni renommés**, et une collision entre deux réseaux lève une `[ALARME]` au lieu
d'être arbitrée en silence.

Le dossier `includes/` n'est pas versionné : ce script est la recette. Il ne dépend pas de
`llm-agents/settings.py` — l'importer depuis un script de l'hôte re-pointe `experiments/current`
et détourne les traces d'un run en cours (ticket 031, question ouverte n° 12).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

INCLUDES = REPO_ROOT / "GAMA" / "CityTransport" / "includes"
PERIMETRE = REPO_ROOT / "llm_module" / "data" / "couronne_perimetre.geojson"

# Les trois réseaux du périmètre. Tisséo et le TER dans leur export en service ;
# liO dans son feed annuel, le seul qui couvre la date simulée (l'export de
# l'opérateur commence au 1er août 2026).
FEEDS_DEFAUT = {
    "tisseo": "data/gtfs/tisseo_gtfs",
    "ter": "data/gtfs/ter_gtfs",
    "lio": "data/gtfs_year/lio_2026",
}

COLONNES_ROUTES = ["shape_id", "route_id", "service_id", "trip_id", "agency_id", "short_name",
                   "long_name", "color", "text_color", "route_type", "reseau", "trace"]
COLONNES_STOPS = ["stop_id", "stop_name", "location_t", "wheelchair", "route_type", "reseau"]


def _couleur(valeur) -> str:
    """`route_color` GTFS (six hexa, sans dièse) en une valeur lisible par GAMA."""
    texte = "" if valeur is None else str(valeur).strip()
    if texte in ("", "nan", "None"):
        return "#000000"
    return texte if texte.startswith("#") else f"#{texte}"


def _lire(feed: Path, nom: str, **kwargs):
    import pandas as pd

    chemin = feed / nom
    if not chemin.exists():
        raise FileNotFoundError(f"{chemin} absent — feed incomplet")
    return pd.read_csv(chemin, dtype=str, **kwargs)


def couches(feeds: dict[str, Path], journal=print):
    """Construit les deux GeoDataFrames, réseau par réseau."""
    import geopandas as gpd
    import pandas as pd
    from shapely.geometry import LineString

    routes_out, stops_out, comptes = [], [], {}
    for reseau, feed in feeds.items():
        trips = _lire(feed, "trips.txt")
        routes = _lire(feed, "routes.txt")
        stops = _lire(feed, "stops.txt")
        stop_times = _lire(feed, "stop_times.txt", usecols=["trip_id", "stop_id", "stop_sequence"])

        # ── Lignes : une entité par tracé ─────────────────────────────────────
        # Le feed TER ne publie aucun `shapes.txt`. Plutôt que de laisser ses
        # lignes hors de la couche, leur tracé est la polyligne de leurs arrêts
        # desservis — une approximation du corridor, marquée `trace=arrets`,
        # bonne pour l'affichage et pour la mesure de couverture du monde, et
        # qui n'entre dans aucun calcul de temps de parcours.
        if (feed / "shapes.txt").exists():
            origine_trace = "gtfs"
            shapes = _lire(feed, "shapes.txt")
            shapes["shape_pt_sequence"] = shapes["shape_pt_sequence"].astype(int)
            shapes = shapes.sort_values(["shape_id", "shape_pt_sequence"])
            geometries = shapes.groupby("shape_id").apply(
                lambda l: LineString(zip(l["shape_pt_lon"].astype(float), l["shape_pt_lat"].astype(float))),
                include_groups=False,
            )
            trips_traces = trips.copy()
        else:
            origine_trace = "arrets"
            journal(f"    {reseau} : aucun shapes.txt — tracés reconstruits depuis la suite des arrêts")
            trips_traces = trips.copy()
            # Un tracé par (ligne, sens) : la course la plus desservie fait foi.
            trips_traces["shape_id"] = (trips_traces["route_id"].astype(str) + ":"
                                        + trips_traces.get("direction_id", "0").astype(str))
            coords = stops.set_index("stop_id")[["stop_lon", "stop_lat"]].astype(float)
            horaires = stop_times.merge(trips_traces[["trip_id", "shape_id"]], on="trip_id", how="inner")
            horaires["stop_sequence"] = horaires["stop_sequence"].astype(int)
            plus_longue = (horaires.groupby(["shape_id", "trip_id"]).size().reset_index(name="n")
                           .sort_values(["shape_id", "n"], ascending=[True, False])
                           .groupby("shape_id").first().reset_index())
            retenues = horaires.merge(plus_longue[["shape_id", "trip_id"]], on=["shape_id", "trip_id"])
            lignes = {}
            for shape_id, groupe in retenues.sort_values("stop_sequence").groupby("shape_id"):
                points = [(coords.at[s, "stop_lon"], coords.at[s, "stop_lat"])
                          for s in groupe["stop_id"] if s in coords.index]
                if len(points) >= 2:
                    lignes[shape_id] = LineString(points)
            geometries = pd.Series(lignes)
            if geometries.empty:
                journal(f"[ALARME] {reseau} : aucun tracé reconstructible depuis les arrêts")
        table = pd.DataFrame({"shape_id": list(geometries.index), "geometry": list(geometries.values)})
        premier_trip = (trips_traces[["route_id", "service_id", "trip_id", "shape_id"]]
                        .groupby("shape_id").agg(lambda x: x.iloc[0]).reset_index())
        table = table.merge(premier_trip, on="shape_id", how="left").merge(routes, on="route_id", how="left")
        table = table.rename(columns={"route_short_name": "short_name", "route_long_name": "long_name",
                                      "route_color": "color", "route_text_color": "text_color"})
        for colonne in COLONNES_ROUTES:
            if colonne not in table.columns:
                table[colonne] = ""
        table["color"] = table["color"].apply(_couleur)
        table["text_color"] = table["text_color"].apply(_couleur)
        table["reseau"] = reseau
        table["trace"] = origine_trace
        routes_out.append(gpd.GeoDataFrame(table[COLONNES_ROUTES + ["geometry"]], crs="EPSG:4326"))

        # ── Arrêts : ceux qu'une course dessert, avec le type de leur ligne ────
        type_par_trip = trips[["route_id", "trip_id"]].merge(
            routes[["route_id", "route_type"]], on="route_id", how="left")
        type_par_arret = (stop_times.merge(type_par_trip[["trip_id", "route_type"]], on="trip_id", how="left")
                          .dropna(subset=["route_type"]))
        type_par_arret["route_type"] = type_par_arret["route_type"].astype(int)
        type_par_arret = type_par_arret.groupby("stop_id").agg({"route_type": "min"}).reset_index()
        table_arrets = stops.rename(columns={"location_type": "location_t",
                                             "wheelchair_boarding": "wheelchair"})
        for colonne in ("location_t", "wheelchair"):
            if colonne not in table_arrets.columns:
                table_arrets[colonne] = ""
        table_arrets = table_arrets[["stop_id", "stop_name", "location_t", "wheelchair",
                                     "stop_lon", "stop_lat"]].merge(type_par_arret, on="stop_id", how="inner")
        table_arrets["reseau"] = reseau
        stops_out.append(gpd.GeoDataFrame(
            table_arrets[COLONNES_STOPS],
            geometry=gpd.points_from_xy(table_arrets["stop_lon"].astype(float),
                                        table_arrets["stop_lat"].astype(float), z=0),
            crs="EPSG:4326"))
        comptes[reseau] = {"lignes_gtfs": int(len(routes)), "traces": int(len(table)),
                           "origine_trace": origine_trace,
                           "arrets_desservis": int(len(table_arrets)), "feed": str(feed)}
        journal(f"    {reseau} : {len(routes)} ligne(s), {len(table)} tracé(s), "
                f"{len(table_arrets)} arrêt(s) desservi(s)")

    couche_routes = pd.concat(routes_out, ignore_index=True)
    couche_stops = pd.concat(stops_out, ignore_index=True)

    # Les identifiants sont des clés de jointure avec OTP : une collision entre
    # réseaux ferait monter un agent dans le véhicule d'un autre.
    for nom, couche, cle in (("shape_id", couche_routes, "shape_id"), ("stop_id", couche_stops, "stop_id")):
        doublons = couche[couche.duplicated(cle, keep=False)]
        if len(doublons):
            reseaux = sorted(set(doublons["reseau"]))
            journal(f"[ALARME] {len(doublons)} {nom} partagés entre réseaux {reseaux} — "
                    f"la jointure GAMA/OTP est ambiguë sur ces entités")
            comptes.setdefault("collisions", {})[nom] = int(len(doublons))
    return couche_routes, couche_stops, comptes


def restreindre(couche_routes, couche_stops, journal=print):
    """Ne garde que ce qui touche le périmètre des 453 communes.

    liO couvre toute l'Occitanie : 2 634 tracés, de Perpignan à Millau. Les
    verser tels quels dans un monde GAMA de 86 × 93 km y ferait entrer des
    géométries dix fois plus larges que lui. Les tracés retenus ne sont pas
    découpés — une ligne qui sort du périmètre le fait entière, sinon son
    véhicule sauterait d'un bout à l'autre du monde.
    """
    import geopandas as gpd

    polygone = gpd.read_file(PERIMETRE).union_all()
    routes_gardees = couche_routes[couche_routes.intersects(polygone)].reset_index(drop=True)
    stops_gardes = couche_stops[couche_stops.within(polygone)].reset_index(drop=True)
    journal(f"    périmètre : {len(routes_gardees)} / {len(couche_routes)} tracé(s) et "
            f"{len(stops_gardes)} / {len(couche_stops)} arrêt(s) touchent les 453 communes")
    return routes_gardees, stops_gardes


def couverture(couche_routes, couche_stops, journal=print) -> dict:
    """Ce que le réseau TC dessert vraiment du monde GAMA.

    Trois mesures, parce que la première ne suffit pas :
      * l'enveloppe — le test que fait `Settings.gaml` au chargement. Il devient
        vrai dès qu'un réseau régional entre dans la couche, et ne dit alors plus
        rien de la desserte : une enveloppe qui couvre le monde n'y met pas un
        arrêt.
      * les mailles de 5 km du monde qui portent au moins un arrêt ;
      * les communes du périmètre qui portent au moins un arrêt — le chiffre qui
        dit combien d'habitants peuvent voir un transport collectif.
    """
    import geopandas as gpd
    from shapely.geometry import box

    perimetre = gpd.read_file(PERIMETRE)
    monde = box(*perimetre.total_bounds)
    lignes = box(*couche_routes.total_bounds)
    part_enveloppe = lignes.intersection(monde).area / monde.area

    # Mailles de 5 km, en degrés à la latitude du périmètre (1° lat = 111,2 km,
    # 1° lon = 111,32 × cos(43,5°) = 80,7 km). Seules comptent au dénominateur
    # les mailles dont le centre tombe dans le périmètre : les coins du
    # rectangle englobant ne sont pas du territoire d'étude.
    from shapely import contains_xy, prepare

    polygone = perimetre.union_all()
    prepare(polygone)
    lon_min, lat_min, lon_max, lat_max = perimetre.total_bounds
    pas_lat, pas_lon = 5.0 / 111.2, 5.0 / 80.7
    n_lat = max(1, int((lat_max - lat_min) / pas_lat) + 1)
    n_lon = max(1, int((lon_max - lon_min) / pas_lon) + 1)
    dans_le_perimetre = {
        (i, j) for i in range(n_lat) for j in range(n_lon)
        if contains_xy(polygone, lon_min + (j + 0.5) * pas_lon, lat_min + (i + 0.5) * pas_lat)
    }
    mailles = {(int((y - lat_min) / pas_lat), int((x - lon_min) / pas_lon))
               for x, y in zip(couche_stops.geometry.x, couche_stops.geometry.y)
               if lon_min <= x <= lon_max and lat_min <= y <= lat_max} & dans_le_perimetre
    part_mailles = len(mailles) / max(1, len(dans_le_perimetre))

    mesure = {"monde_bounds": [round(v, 4) for v in perimetre.total_bounds],
              "lignes_bounds": [round(v, 4) for v in couche_routes.total_bounds],
              "part_enveloppe": round(part_enveloppe, 4),
              "mailles_5km": {"dans_le_perimetre": len(dans_le_perimetre), "avec_arret": len(mailles),
                              "part": round(part_mailles, 4)}}

    zones = REPO_ROOT / "llm_module" / "data" / "zf_zones.gpkg"
    if zones.exists():
        zf = gpd.read_file(zones).to_crs("EPSG:4326")
        avec = gpd.sjoin(zf[["geometry"]], couche_stops[["geometry"]], predicate="contains", how="inner")
        servies = int(avec.index.nunique())
        mesure["zones_fines"] = {"total": int(len(zf)), "avec_arret": servies,
                                 "part": round(servies / max(1, len(zf)), 4)}
        journal(f"    couverture : {servies} / {len(zf)} zones fines de l'enquête portent au moins un arrêt")
    journal(f"    couverture : enveloppe {part_enveloppe:.0%} du monde ; "
            f"{len(mailles)} / {len(dans_le_perimetre)} mailles de 5 km du périmètre portent un arrêt "
            f"({part_mailles:.0%})")
    return mesure


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--feed", action="append", metavar="NOM=CHEMIN",
                        help="réseau à inclure (défaut : tisseo, ter, lio)")
    parser.add_argument("--sortie", type=Path, default=INCLUDES)
    parser.add_argument("--tout", action="store_true",
                        help="ne pas restreindre au périmètre des 453 communes")
    parser.add_argument("--json", type=Path, default=None, help="écrit les mesures dans ce fichier")
    args = parser.parse_args(argv)

    demandes = FEEDS_DEFAUT if not args.feed else dict(f.split("=", 1) for f in args.feed)
    feeds = {}
    for reseau, chemin in demandes.items():
        feed = Path(chemin) if Path(chemin).is_absolute() else REPO_ROOT / chemin
        if not (feed / "trips.txt").exists():
            print(f"[ALARME] feed {reseau} introuvable : {feed}", file=sys.stderr)
            return 1
        feeds[reseau] = feed

    print(f"réseaux : {', '.join(feeds)}")
    couche_routes, couche_stops, comptes = couches(feeds)
    comptes["avant_restriction"] = {"traces": int(len(couche_routes)), "arrets": int(len(couche_stops))}
    if not args.tout:
        couche_routes, couche_stops = restreindre(couche_routes, couche_stops)
    mesure = couverture(couche_routes, couche_stops)

    args.sortie.mkdir(parents=True, exist_ok=True)
    horodatage = datetime.now().strftime("%Y-%m-%d_%H-%M")
    archive = args.sortie / f"archives_{horodatage}"
    deplaces = []
    for base in ("routes", "stops"):
        for existant in sorted(args.sortie.glob(f"{base}.*")):
            archive.mkdir(parents=True, exist_ok=True)
            shutil.move(str(existant), str(archive / existant.name))
            deplaces.append(existant.name)
    if deplaces:
        print(f"    couches précédentes conservées dans {archive.name} : {len(deplaces)} fichier(s)")

    couche_routes.to_file(args.sortie / "routes.shp")
    couche_stops.to_file(args.sortie / "stops.shp")

    resultat = {"date": datetime.now().isoformat(timespec="seconds"), "reseaux": comptes,
                "routes_shp": {"entites": int(len(couche_routes))},
                "stops_shp": {"entites": int(len(couche_stops))},
                "couverture": mesure,
                "anciennes_couches": {"dossier": archive.name if deplaces else None,
                                      "fichiers": deplaces}}
    print(json.dumps(resultat, ensure_ascii=False, indent=1))
    if args.json:
        args.json.write_text(json.dumps(resultat, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
