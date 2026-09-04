"""Produit `GAMA/CityTransport/includes/trip_info.json` — les courses que GAMA fait rouler.

    llm-agents/.venv/bin/python scripts/data/gama/export_trip_info.py
    make gama-trip-info                     # les couches PUIS les courses

POURQUOI UNE RECETTE
--------------------
`trip_info.json` n'en avait aucune. Il était produit à la main par le bloc
`__main__` de `llm-agents/inputs/gtfs/gama.py`, qui lit en dur
`../data/gtfs/tisseo_gtfs/` et écrit dans `../data/exports/gtfs/`. Résultat
mesuré le 2026-09-04 : le fichier en service datait du **27 mai**, portait
**39 343 courses du seul Tisséo et aucune en `route_type=2`**, alors que
`routes.shp` traçait 34 lignes de TER et `stops.shp` 68 gares. GAMA dessinait
donc un réseau ferré où **aucun train ne roulerait** — et une ligne visible et
morte se lit comme une ligne sans passage, pas comme une donnée manquante.

CE QUE LA RECETTE GARANTIT
--------------------------
1. **Les trois réseaux.** Tisséo, TER et liO, lus aux mêmes emplacements que
   `export_gtfs_layers.py` (`FEEDS_DEFAUT`) — donc les mêmes lignes dans les
   couches et dans les courses.
2. **La date simulée est dans le calendrier.** Elle est lue dans
   `Settings.gaml` (`starting_date`), pas postulée. Hors calendrier,
   `is_trip_available_today` se contente d'un `warn` et ne planifie plus
   **aucune** course : la simulation tourne, le réseau est vide, et rien ne le
   dit. La recette échoue plutôt que de livrer ce fichier-là.
3. **La fenêtre tient dans le masque binaire.** Le calendrier de GAMA est un
   masque 64 bits (`assert len(all_dates) <= 64` dans `gama.py`, décodé par
   `PublicTransport.gaml` via `trip_calendar_map` et `BITWISE_BIT_VAL`). La
   recette refuse une fenêtre plus large, et vérifie l'étendue **réelle** des
   dates du feed fusionné, pas seulement le nombre de jours demandé.
4. **Chaque course a son tracé dans `routes.shp`.** `PublicTransport.gaml` fait
   `route r <- route first_with (each.shape_id = shape_id)` à la création du
   véhicule, puis lit `r.route_id`, `r.color` et `r.shape.points`. Un `shape_id`
   absent de la couche rend `r` nil : véhicule sans géométrie. Les courses sont
   donc restreintes aux `shape_id` de la couche, et le nombre de points de
   chaque tracé est **recoupé** entre la couche et le feed — les
   `shape_segments` sont des indices dans `r.shape.points`.
5. **Aucun type de ligne tracé sans course.** Le contrôle final est celui que le
   garde-fou de `PublicTransport.gaml` fait au chargement : les `route_type` de
   `routes.shp` doivent tous porter des courses. La recette sort en erreur si ce
   n'est pas le cas, pour que le défaut se voie ici et non cinq mois plus tard.

LES DEUX POINTS DÉLICATS
------------------------
**`service_id` est préfixé par réseau, et lui seul.** Les feeds annuels TER et
liO numérotent leurs services `SVC_0001`… : **224 identifiants collisionnent**
entre les deux. Fusionnés tels quels, les cars liO liraient le calendrier des
trains. Le préfixe est sans danger parce que `service_id` n'est une clé de
jointure avec rien : GAMA ne le lit que dans `trip_calendar_map`, `routes.shp`
le porte sans que le modèle le lise, et OTP ne l'expose pas. `shape_id`,
`route_id`, `trip_id` et `stop_id`, eux, **ne sont jamais renommés** : ce sont
les clés de jointure avec les itinéraires rendus par OTP (mesuré : aucune
collision entre les trois réseaux).

**Le TER ne publie pas de géométrie.** Son `shapes.txt` n'a qu'un en-tête et ses
`trips.shape_id` sont vides. Les tracés sont reconstruits par
[`gtfs_traces.py`](gtfs_traces.py) — **un par suite d'arrêts distincte**, comme
un GTFS qui publie ses shapes — et ce module est partagé avec
`export_gtfs_layers.py` pour que les deux fichiers portent les mêmes
identifiants.

CODES DE SORTIE
---------------
    0  fichier écrit, tous les contrôles tenus
    1  ressource absente (feed, couche, Settings.gaml)
    2  invariant démenti — le fichier n'est PAS écrit
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.data.gama import gtfs_traces  # noqa: E402
from scripts.data.gama.export_gtfs_layers import FEEDS_DEFAUT, _a_des_geometries  # noqa: E402

INCLUDES = REPO_ROOT / "GAMA" / "CityTransport" / "includes"
SETTINGS_GAML = REPO_ROOT / "GAMA" / "CityTransport" / "models" / "Settings.gaml"

# Le masque binaire du calendrier côté modèle : 64 bits, un par date.
LIMITE_MASQUE = 64

CODE_RESSOURCE = 1
CODE_REFUS = 2

# Tables que le lecteur `llm-agents/inputs/gtfs/reader.py` exige.
COLONNES_MINIMALES = {
    "routes.txt": ["route_id", "route_short_name", "route_long_name", "route_type"],
    "trips.txt": ["route_id", "service_id", "trip_id", "direction_id", "shape_id"],
    "stop_times.txt": ["trip_id", "stop_sequence", "stop_id", "arrival_time",
                       "departure_time", "shape_dist_traveled"],
    "stops.txt": ["stop_id", "stop_name", "stop_lat", "stop_lon", "location_type"],
    "shapes.txt": ["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence",
                   "shape_dist_traveled"],
    "calendar_dates.txt": ["service_id", "date", "exception_type"],
}


# ── Lectures ──────────────────────────────────────────────────────────────────

def _court(chemin: Path) -> str:
    """Chemin relatif au dépôt quand c'est possible, absolu sinon (essais hors dépôt)."""
    try:
        return str(chemin.relative_to(REPO_ROOT))
    except ValueError:
        return str(chemin)


def _lire_csv(chemin: Path) -> list[dict]:
    with open(chemin, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def date_simulee_de_settings(chemin: Path = SETTINGS_GAML) -> date | None:
    """`starting_date <- date([2026,3,16,5,0,0]);` → 2026-03-16.

    La date est LUE là où le modèle la déclare, pas recopiée dans la recette :
    deux sources pour une même date finissent par diverger, et la conséquence
    d'une divergence est un réseau vide sans message d'erreur.
    """
    if not chemin.exists():
        return None
    motif = re.compile(
        r"^\s*date\s+starting_date\s*<-\s*date\(\s*\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)",
        re.MULTILINE,
    )
    trouve = motif.search(chemin.read_text(encoding="utf-8"))
    if not trouve:
        return None
    a, m, j = (int(g) for g in trouve.groups())
    return date(a, m, j)


def types_de_la_couche(chemin_routes: Path, journal=print) -> tuple[dict[str, int], dict[str, float]]:
    """`routes.shp` → (`shape_id` → nombre de points, `shape_id` → `route_type`)."""
    import geopandas as gpd

    couche = gpd.read_file(chemin_routes)
    points, types = {}, {}
    for _, entite in couche.iterrows():
        shape_id = str(entite["shape_id"])
        geom = entite.geometry
        if geom is None or geom.is_empty:
            journal(f"[ALARME] tracé {shape_id} sans géométrie dans {chemin_routes.name}")
            continue
        points[shape_id] = len(geom.coords)
        types[shape_id] = float(entite["route_type"])
    return points, types


# ── Géométrie ─────────────────────────────────────────────────────────────────

def _metres(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Distance haversine, en mètres.

    `build_trips` ne se sert de `shape_dist_traveled` que pour retrouver des
    INDICES de sommets ; seule la croissance stricte compte. On la calcule tout
    de même en mètres pour que le `shapes.txt` intermédiaire reste lisible et
    comparable à celui des réseaux qui en publient un.
    """
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _cumul(points: list[tuple[float, float]]) -> list[float]:
    cumule, total = [0.0], 0.0
    for (lo1, la1), (lo2, la2) in zip(points, points[1:]):
        total += _metres(lo1, la1, lo2, la2)
        cumule.append(round(total, 1))
    return cumule


# ── Le corps de la recette ────────────────────────────────────────────────────

def preparer_reseau(
    reseau: str,
    feed: Path,
    fenetre: set[str],
    shapes_de_la_couche: dict[str, int],
    journal=print,
) -> tuple[dict[str, list[dict]], dict]:
    """Extrait d'un feed la part active sur la fenêtre, prête à être fusionnée."""
    debut = time.monotonic()
    mesures: dict = {"feed": str(feed)}

    calendrier = [l for l in _lire_csv(feed / "calendar_dates.txt") if l["date"] in fenetre]
    exceptions = {l.get("exception_type", "1") for l in calendrier}
    if exceptions - {"1"}:
        journal(f"[ALARME] {reseau} : exception_type {sorted(exceptions - {'1'})} dans "
                f"calendar_dates.txt — le lecteur GAMA n'accepte que 1 (dates explicites)")
        return {}, {**mesures, "refus": "exception_type"}
    services = {l["service_id"] for l in calendrier}

    trips = [l for l in _lire_csv(feed / "trips.txt") if l["service_id"] in services]
    horaires_tous = _lire_csv(feed / "stop_times.txt")

    # ── Le tracé de chaque course ────────────────────────────────────────────
    if _a_des_geometries(feed):
        origine = "gtfs"
        for l in trips:
            l["shape_id"] = (l.get("shape_id") or "").strip()
        sans_trace = [l["trip_id"] for l in trips if not l["shape_id"]]
        if sans_trace:
            journal(f"[ALARME] {reseau} : {len(sans_trace)} course(s) sans shape_id dans un feed "
                    f"qui publie des géométries — aucun véhicule ne roulera pour elles")
        points_par_shape = None
    else:
        origine = "arrets"
        journal(f"    {reseau} : aucune géométrie publiée — tracés reconstruits depuis les arrêts")
        suites = gtfs_traces.suites_depuis_stop_times(horaires_tous)
        traces, course_vers_trace, m_traces = gtfs_traces.traces_par_suite_d_arrets(
            trips, suites, journal=journal)
        mesures["traces_reconstruites"] = m_traces
        coords = {l["stop_id"]: (float(l["stop_lon"]), float(l["stop_lat"]))
                  for l in _lire_csv(feed / "stops.txt")}
        points_par_shape = {}
        for shape_id, suite in traces.items():
            pts = [coords[s] for s in suite if s in coords]
            if len(pts) < 2:
                journal(f"[ALARME] {reseau} : tracé {shape_id} sans coordonnées "
                        f"({len(pts)} point(s) sur {len(suite)} arrêts) — écarté")
                continue
            points_par_shape[shape_id] = (suite, pts, _cumul(pts))
        for l in trips:
            shape_id = course_vers_trace.get(l["trip_id"], "")
            l["shape_id"] = shape_id if shape_id in points_par_shape else ""

    # ── Restriction aux tracés que porte la couche ────────────────────────────
    avant = len(trips)
    retenus = [l for l in trips if l["shape_id"] in shapes_de_la_couche]
    hors_couche = sorted({l["shape_id"] for l in trips if l["shape_id"] not in shapes_de_la_couche})
    journal(f"    {reseau} : {len(retenus)}/{avant} course(s) dont le tracé est dans routes.shp "
            f"({len(hors_couche)} tracé(s) hors couche — hors du périmètre, ou sans géométrie)")
    trips = retenus
    trips_retenus = {l["trip_id"] for l in trips}
    shapes_retenues = {l["shape_id"] for l in trips}
    routes_retenues = {l["route_id"] for l in trips}

    # ── Horaires ─────────────────────────────────────────────────────────────
    horaires = [l for l in horaires_tous if l["trip_id"] in trips_retenus]
    shape_par_trip = {l["trip_id"]: l["shape_id"] for l in trips}
    if origine == "arrets":
        # Les sommets du tracé SONT les arrêts : la distance au sommet fait foi.
        index_cumul = {sid: {s: c for s, c in zip(suite, cumule)}
                       for sid, (suite, _pts, cumule) in points_par_shape.items()}
        manquants = 0
        for l in horaires:
            table = index_cumul[shape_par_trip[l["trip_id"]]]
            valeur = table.get(l["stop_id"])
            if valeur is None:
                manquants += 1
                continue
            l["shape_dist_traveled"] = f"{valeur}"
        if manquants:
            journal(f"[ALARME] {reseau} : {manquants} horaire(s) dont l'arrêt n'est pas un sommet "
                    f"de son tracé — la course ne peut pas être placée")
            return {}, {**mesures, "refus": "arret_hors_trace"}
    vides = sum(1 for l in horaires if not str(l.get("shape_dist_traveled") or "").strip())
    if vides:
        journal(f"[ALARME] {reseau} : {vides} horaire(s) sans shape_dist_traveled — "
                f"`build_trips` ne peut pas découper le tracé")
        return {}, {**mesures, "refus": "shape_dist_traveled_absent"}

    # ── Géométries ───────────────────────────────────────────────────────────
    if origine == "arrets":
        shapes = []
        for shape_id in sorted(shapes_retenues):
            _suite, pts, cumule = points_par_shape[shape_id]
            for i, ((lon, lat), dist) in enumerate(zip(pts, cumule)):
                shapes.append({"shape_id": shape_id, "shape_pt_lat": f"{lat}",
                               "shape_pt_lon": f"{lon}", "shape_pt_sequence": str(i),
                               "shape_dist_traveled": f"{dist}"})
    else:
        shapes = [l for l in _lire_csv(feed / "shapes.txt") if l["shape_id"] in shapes_retenues]

    # Recoupement avec la couche : les `shape_segments` sont des indices dans
    # `r.shape.points`. Un tracé plus court dans la couche que dans le feed fait
    # sortir GAMA de la liste, un tracé plus long y laisse un moignon inatteignable.
    nb_points = {}
    for l in shapes:
        nb_points[l["shape_id"]] = nb_points.get(l["shape_id"], 0) + 1
    desaccords = {sid: (n, shapes_de_la_couche[sid])
                  for sid, n in nb_points.items() if n != shapes_de_la_couche[sid]}
    if desaccords:
        exemples = dict(list(desaccords.items())[:3])
        journal(f"[ALARME] {reseau} : {len(desaccords)} tracé(s) dont le nombre de points diffère "
                f"entre le feed et routes.shp — ex. (feed, couche) {exemples}")
        return {}, {**mesures, "refus": "points_desaccord", "desaccords": len(desaccords)}

    # ── Tables annexes ───────────────────────────────────────────────────────
    routes = [l for l in _lire_csv(feed / "routes.txt") if l["route_id"] in routes_retenues]
    arrets_retenus = {l["stop_id"] for l in horaires}
    stops = [l for l in _lire_csv(feed / "stops.txt") if l["stop_id"] in arrets_retenus]

    # ── Préfixe des service_id (et d'eux seuls) ──────────────────────────────
    services_utiles = {t["service_id"] for t in trips}
    calendrier = [dict(l, service_id=f"{reseau}:{l['service_id']}")
                  for l in calendrier if l["service_id"] in services_utiles]
    for l in trips:
        l["service_id"] = f"{reseau}:{l['service_id']}"

    type_par_route = {l["route_id"]: float(l["route_type"]) for l in routes}
    mesures.update({
        "origine_trace": origine,
        "courses_dans_la_fenetre": avant,
        "courses_retenues": len(trips),
        "traces_retenus": len(shapes_retenues),
        "traces_hors_couche": len(hors_couche),
        "lignes": len(routes),
        "arrets": len(stops),
        "services": len({l["service_id"] for l in calendrier}),
        "duree_s": round(time.monotonic() - debut, 1),
    })
    mesures["courses_par_type"] = _compte_par_type(trips, type_par_route)
    journal(f"    {reseau} : {len(trips):,} course(s), {len(shapes_retenues)} tracé(s), "
            f"{len(routes)} ligne(s), {mesures['services']} service(s) "
            f"en {mesures['duree_s']} s".replace(",", " "))
    return {"routes.txt": routes, "trips.txt": trips, "stop_times.txt": horaires,
            "stops.txt": stops, "shapes.txt": shapes, "calendar_dates.txt": calendrier}, mesures


def _compte_par_type(trips: list[dict], type_par_route: dict[str, float]) -> dict[str, int]:
    compte: dict[str, int] = {}
    for l in trips:
        cle = str(int(type_par_route[l["route_id"]]))
        compte[cle] = compte.get(cle, 0) + 1
    return dict(sorted(compte.items(), key=lambda kv: int(kv[0])))


def ecrire_feed(tables: dict[str, list[dict]], sortie: Path) -> None:
    """Écrit le feed fusionné, colonnes en union, `calendar.txt` vide."""
    sortie.mkdir(parents=True, exist_ok=True)
    for nom, lignes in tables.items():
        colonnes = list(COLONNES_MINIMALES.get(nom, []))
        for ligne in lignes:
            for cle in ligne:
                if cle not in colonnes:
                    colonnes.append(cle)
        with open(sortie / nom, "w", encoding="utf-8", newline="") as fh:
            ecrivain = csv.DictWriter(fh, fieldnames=colonnes, extrasaction="ignore")
            ecrivain.writeheader()
            for ligne in lignes:
                ecrivain.writerow({c: ligne.get(c, "") for c in colonnes})
    # Le lecteur GAMA exige un calendar.txt VIDE (il ne sait pas déplier des
    # services hebdomadaires) : `assert len(data.calendar) == 0` dans reader.py.
    (sortie / "calendar.txt").write_text(
        "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
        "start_date,end_date\n", encoding="utf-8")


def courses_du_jour(donnees: dict, jour: str) -> dict[str, int]:
    """Décode le masque binaire et compte les courses actives ce jour-là, par type.

    C'est le contrôle qui compte : `is_trip_available_today` fait exactement ce
    calcul côté modèle. Compter les courses du fichier sans décoder le calendrier
    dirait « 40 000 courses » d'un fichier qui n'en fait rouler aucune.
    """
    calendrier = donnees["calendar"]
    if jour not in calendrier["dates"]:
        return {}
    bit = 1 << calendrier["dates"].index(jour)
    masques = calendrier["data"]
    compte: dict[str, int] = {}
    for trip in donnees["trip_list"]:
        if masques.get(trip["service_id"], 0) & bit:
            cle = str(int(trip["route_type"]))
            compte[cle] = compte.get(cle, 0) + 1
    return dict(sorted(compte.items(), key=lambda kv: int(kv[0])))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--feed", action="append", metavar="NOM=CHEMIN",
                        help="réseau à inclure (défaut : tisseo, ter, lio — comme les couches)")
    parser.add_argument("--date-simulee", default=None,
                        help="AAAA-MM-JJ ; par défaut lue dans Settings.gaml (starting_date)")
    parser.add_argument("--debut", default=None,
                        help="premier jour de la fenêtre, AAAA-MM-JJ (défaut : la date simulée)")
    parser.add_argument("--jours", type=int, default=LIMITE_MASQUE)
    parser.add_argument("--routes", type=Path, default=INCLUDES / "routes.shp")
    parser.add_argument("--sortie", type=Path, default=INCLUDES / "trip_info.json")
    parser.add_argument("--feed-intermediaire", type=Path, default=None,
                        help="où garder le GTFS fusionné (défaut : temporaire, supprimé)")
    parser.add_argument("--json", type=Path, default=None, help="écrit les mesures dans ce fichier")
    args = parser.parse_args(argv)

    depart = time.monotonic()

    # ── La date simulée ──────────────────────────────────────────────────────
    if args.date_simulee:
        jour_simule = date.fromisoformat(args.date_simulee)
        source_date = "argument --date-simulee"
    else:
        jour_simule = date_simulee_de_settings()
        source_date = f"Settings.gaml ({_court(SETTINGS_GAML)})"
        if jour_simule is None:
            print("[ALARME] starting_date introuvable dans Settings.gaml — "
                  "passez --date-simulee AAAA-MM-JJ plutôt que de deviner", file=sys.stderr)
            return CODE_RESSOURCE
    debut = date.fromisoformat(args.debut) if args.debut else jour_simule
    print(f"date simulée : {jour_simule} (lue dans {source_date})")

    if args.jours > LIMITE_MASQUE:
        print(f"[ALARME] fenêtre de {args.jours} jours : le calendrier de GAMA est un masque "
              f"binaire de {LIMITE_MASQUE} bits (gama.py, PublicTransport.gaml)", file=sys.stderr)
        return CODE_REFUS
    if args.jours < 1:
        print(f"[ALARME] fenêtre de {args.jours} jour(s)", file=sys.stderr)
        return CODE_REFUS

    fenetre_dates = [debut + timedelta(days=i) for i in range(args.jours)]
    if jour_simule not in fenetre_dates:
        print(f"[ALARME] la date simulée {jour_simule} n'est PAS dans la fenêtre "
              f"{fenetre_dates[0]} → {fenetre_dates[-1]} : hors calendrier, GAMA ne planifierait "
              f"aucune course et ne le dirait qu'en `warn`", file=sys.stderr)
        return CODE_REFUS
    fenetre = {d.strftime("%Y%m%d") for d in fenetre_dates}
    jour_simule_txt = jour_simule.strftime("%Y%m%d")
    print(f"fenêtre : {fenetre_dates[0]} → {fenetre_dates[-1]} ({args.jours} jours)")

    # ── Les feeds ────────────────────────────────────────────────────────────
    demandes = FEEDS_DEFAUT if not args.feed else dict(f.split("=", 1) for f in args.feed)
    feeds: dict[str, Path] = {}
    for reseau, chemin in demandes.items():
        feed = Path(chemin) if Path(chemin).is_absolute() else REPO_ROOT / chemin
        if not (feed / "trips.txt").exists():
            print(f"[ALARME] feed {reseau} introuvable : {feed}", file=sys.stderr)
            return CODE_RESSOURCE
        feeds[reseau] = feed
    if not args.routes.exists():
        print(f"[ALARME] couche introuvable : {args.routes} — lancez d'abord "
              f"scripts/data/gama/export_gtfs_layers.py", file=sys.stderr)
        return CODE_RESSOURCE

    points_couche, types_couche = types_de_la_couche(args.routes)
    types_traces = sorted({int(t) for t in types_couche.values()})
    print(f"réseaux : {', '.join(feeds)}")
    print(f"couche {args.routes.name} : {len(points_couche)} tracé(s), "
          f"route_type {types_traces}")

    # ── Réseau par réseau ────────────────────────────────────────────────────
    fusion: dict[str, list[dict]] = {nom: [] for nom in COLONNES_MINIMALES}
    mesures_reseaux: dict[str, dict] = {}
    for reseau, feed in feeds.items():
        tables, mesures = preparer_reseau(reseau, feed, fenetre, points_couche)
        mesures_reseaux[reseau] = mesures
        if not tables:
            print(f"[ALARME] {reseau} : préparation refusée ({mesures.get('refus')}) — "
                  f"trip_info.json n'est pas écrit", file=sys.stderr)
            return CODE_REFUS
        for nom, lignes in tables.items():
            fusion[nom].extend(lignes)

    # ── Contrôles sur le feed fusionné ───────────────────────────────────────
    dates_servies = sorted({l["date"] for l in fusion["calendar_dates.txt"]})
    if not dates_servies:
        print("[ALARME] aucune date servie dans la fenêtre", file=sys.stderr)
        return CODE_REFUS
    premiere = datetime.strptime(dates_servies[0], "%Y%m%d").date()
    derniere = datetime.strptime(dates_servies[-1], "%Y%m%d").date()
    etendue = (derniere - premiere).days + 1
    print(f"calendrier fusionné : {dates_servies[0]} → {dates_servies[-1]} "
          f"({len(dates_servies)} date(s) servies, étendue {etendue} jours)")
    if etendue > LIMITE_MASQUE:
        print(f"[ALARME] étendue de {etendue} jours entre la première et la dernière date servie : "
              f"`build_calendar_binary_map` construit un bit PAR JOUR de l'intervalle, pas par "
              f"date servie — le masque de {LIMITE_MASQUE} bits déborde", file=sys.stderr)
        return CODE_REFUS
    if jour_simule_txt not in dates_servies:
        print(f"[ALARME] la date simulée {jour_simule} n'est servie par aucun réseau de la "
              f"fenêtre — aucune course ne serait planifiée", file=sys.stderr)
        return CODE_REFUS

    for reseau, mesures in mesures_reseaux.items():
        if not mesures.get("courses_retenues"):
            print(f"[ALARME] {reseau} : aucune course retenue — le réseau serait tracé et mort",
                  file=sys.stderr)
            return CODE_REFUS

    # ── Le fichier ───────────────────────────────────────────────────────────
    temporaire = args.feed_intermediaire
    ephemere = temporaire is None
    if ephemere:
        temporaire = args.sortie.parent / f".feed_fusionne_{datetime.now():%Y%m%d_%H%M%S}"
    ecrire_feed(fusion, temporaire)
    print(f"feed fusionné écrit : {temporaire}")

    try:
        sys.path.insert(0, str(REPO_ROOT / "llm-agents"))
        # Depuis le 2026-09-04, importer `settings` ne crée plus de répertoire de run
        # et ne déplace plus `experiments/current` : cela appartient à `claim_run()`,
        # que seul le processus propriétaire appelle. Un run en cours n'est pas touché.
        from inputs.gtfs.gama import GamaGTFS  # noqa: E402
        from inputs.gtfs.reader import GTFSData  # noqa: E402

        t0 = time.monotonic()
        print("lecture du feed fusionné …")
        gtfs = GTFSData.from_gtfs_files(str(temporaire))
        print(f"construction des courses ({len(fusion['trips.txt']):,} courses) …"
              .replace(",", " "))
        donnees = GamaGTFS(gtfs).build_data(use_cache=False)
        donnees["trip_list"] = [t.model_dump() for t in donnees["trip_list"]]
        duree_build = round(time.monotonic() - t0, 1)
        print(f"courses construites en {duree_build} s")
    finally:
        if ephemere and temporaire.exists():
            shutil.rmtree(temporaire)

    # ── Contrôles sur le fichier produit ─────────────────────────────────────
    types_courses = sorted({int(t["route_type"]) for t in donnees["trip_list"]})
    par_type: dict[str, int] = {}
    for t in donnees["trip_list"]:
        cle = str(int(t["route_type"]))
        par_type[cle] = par_type.get(cle, 0) + 1
    par_type = dict(sorted(par_type.items(), key=lambda kv: int(kv[0])))
    du_jour = courses_du_jour(donnees, jour_simule_txt)

    print(f"courses par route_type : {par_type}")
    print(f"courses actives le {jour_simule} (masque binaire décodé) : {du_jour}")

    manquants = [t for t in types_traces if t not in types_courses]
    if manquants:
        print(f"[ALARME] route_type tracé(s) dans {args.routes.name} mais ABSENT(s) des courses : "
              f"{manquants} — c'est exactement le défaut que cette recette corrige ; "
              f"trip_info.json n'est PAS écrit", file=sys.stderr)
        return CODE_REFUS
    muets = [t for t in types_traces if not du_jour.get(str(t))]
    if muets:
        print(f"[ALARME] route_type sans AUCUNE course active le {jour_simule} : {muets} — "
              f"la ligne serait visible et morte le jour simulé ; trip_info.json n'est PAS écrit",
              file=sys.stderr)
        return CODE_REFUS

    # ── Écriture, l'ancien fichier archivé et daté ───────────────────────────
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    archive = None
    if args.sortie.exists():
        horodatage = datetime.fromtimestamp(args.sortie.stat().st_mtime).strftime("%Y-%m-%d_%H-%M")
        dossier = args.sortie.parent / f"archives_{datetime.now():%Y-%m-%d_%H-%M}"
        dossier.mkdir(parents=True, exist_ok=True)
        archive = dossier / f"{args.sortie.stem}_{horodatage}{args.sortie.suffix}"
        shutil.move(str(args.sortie), str(archive))
        print(f"ancien fichier conservé : {_court(archive)}")

    with open(args.sortie, "w", encoding="utf-8") as fh:
        json.dump(donnees, fh)
    taille = args.sortie.stat().st_size
    duree = round(time.monotonic() - depart, 1)
    print(f"écrit : {args.sortie} — {taille:,} o ({taille / 1_048_576:.1f} Mo) "
          f"en {duree} s".replace(",", " "))

    resultat = {
        "date": datetime.now().isoformat(timespec="seconds"),
        "date_simulee": jour_simule.isoformat(),
        "fenetre": {"debut": fenetre_dates[0].isoformat(), "fin": fenetre_dates[-1].isoformat(),
                    "jours_demandes": args.jours, "dates_servies": len(dates_servies),
                    "etendue_jours": etendue},
        "reseaux": mesures_reseaux,
        "couche": {"fichier": str(args.routes), "traces": len(points_couche),
                   "route_types": types_traces},
        "trip_info": {"fichier": str(args.sortie), "octets": taille,
                      "courses": len(donnees["trip_list"]),
                      "courses_par_type": par_type,
                      "courses_actives_le_jour_simule": du_jour,
                      "dates_du_calendrier": len(donnees["calendar"]["dates"]),
                      "services": len(donnees["calendar"]["data"]),
                      "duree_construction_s": duree_build},
        "ancien_fichier": _court(archive) if archive else None,
        "duree_totale_s": duree,
    }
    print(json.dumps(resultat, ensure_ascii=False, indent=1))
    if args.json:
        args.json.write_text(json.dumps(resultat, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
