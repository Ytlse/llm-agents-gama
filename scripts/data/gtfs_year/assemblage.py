"""
Assemblage du feed annuel : des journées choisies au jeu GTFS écrit sur disque.

L'unité atomique n'est pas le trip mais **l'offre d'une journée telle qu'un seul
export la décrit**. Une journée n'est donc jamais recomposée à partir de
plusieurs exports, ce qui élimine par construction le cas « la journée donneuse
référence un arrêt ou une géométrie absents ».

Trois règles gouvernent l'identité des objets :

  * Le `trip_id` de l'opérateur n'est pas stable sur l'année — l'indice de
    Jaccard entre les trips d'un mardi de mars et ceux d'un mardi de septembre
    vaut 0.00, les deux exports utilisant des espaces de noms disjoints.
    L'identité retenue est donc celle du CONTENU : ligne, sens, girouette,
    géométrie et suite d'arrêts horodatés.

  * `(trip, horaires, géométrie)` est indissociable. Le `shape_dist_traveled`
    des horaires est calibré sur SA géométrie. Dédupliquer les points de
    géométrie sur `(shape_id, shape_pt_sequence)` mélange deux tracés et produit
    une chimère : c'est ce qui est arrivé à la shape 14846 du feed en service,
    dont les 524 points proviennent de deux exports différents.

  * Les arrêts, lignes et correspondances sont de l'infrastructure, pas de
    l'offre : le dernier export publié fait foi, et tout écart notable est
    signalé plutôt qu'arbitré en silence.

Le calendrier de sortie est reconstruit par ENSEMBLES DE DATES : les trips qui
roulent exactement les mêmes jours partagent un `service_id` synthétique. Cela
rend la sur-offre structurellement impossible, garde `calendar.txt` vide et
`exception_type=1` — les deux conditions posées par
`llm-agents/inputs/gtfs/reader.py` — et compresse le calendrier d'un facteur dix
par rapport à un service par trip.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from . import gtfs_io
from .donneurs import EXTRAPOLE, REEL, Provenance
from .gtfs_io import Export
from .offre import IndexExport

COLONNES_TRIPS = [
    "route_id",
    "service_id",
    "trip_id",
    "trip_headsign",
    "direction_id",
    "block_id",
    "shape_id",
    "wheelchair_accessible",
    "bikes_allowed",
]
COLONNES_CALENDAR = ["service_id", "date", "exception_type"]
COLONNES_CALENDAR_HEBDO = [
    "service_id",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "start_date",
    "end_date",
]
COLONNES_FEED_INFO = [
    "feed_id",
    "feed_publisher_name",
    "feed_publisher_url",
    "feed_lang",
    "feed_start_date",
    "feed_end_date",
    "feed_version",
]

# Champs d'un horaire qui définissent le service rendu. `trip_id` en est exclu :
# c'est justement ce qu'on cherche à réconcilier entre exports.
CHAMPS_HORAIRE_IDENTITE = (
    "stop_sequence",
    "stop_id",
    "arrival_time",
    "departure_time",
    "pickup_type",
    "drop_off_type",
    "stop_headsign",
    "shape_dist_traveled",
)


@dataclass
class Statistiques:
    trips_ecrits: int = 0
    horaires_ecrits: int = 0
    services: int = 0
    lignes_calendrier: int = 0
    trips_fusionnes: int = 0
    trips_forkes: int = 0
    collisions_meme_jour: int = 0
    shapes_dupliquees: int = 0
    arrets_deplaces: list[tuple[str, float]] = field(default_factory=list)
    lignes_redefinies: int = 0
    orphelins: dict[str, int] = field(default_factory=dict)


def _hacher(*morceaux: str) -> str:
    digest = hashlib.sha256()
    for morceau in morceaux:
        digest.update(morceau.encode("utf-8"))
        digest.update(b"\x1f")
    return digest.hexdigest()


def _cle_horaires(horaires: list[dict[str, str]]) -> str:
    return _hacher(
        *[
            "|".join(h.get(champ, "") for champ in CHAMPS_HORAIRE_IDENTITE)
            for h in horaires
        ]
    )


def cle_contenu(meta: dict[str, str], horaires: list[dict[str, str]], hash_shape: str) -> str:
    """Identité d'un trip par ce qu'il fait, indépendamment de son `trip_id`.

    C'est la brique de l'empreinte d'offre utilisée par la validation : deux
    feeds servent la même journée si et seulement si leurs multiensembles de
    clés de contenu coïncident.
    """
    return _hacher(
        meta.get("route_id", ""),
        meta.get("direction_id", ""),
        meta.get("trip_headsign", ""),
        hash_shape,
        _cle_horaires(horaires),
    )


def hash_geometrie(points: list[dict[str, str]]) -> str:
    """Empreinte d'un tracé, sur ses points canonisés et ordonnés."""
    return _hacher(
        *[
            f"{p['shape_pt_lat']}|{p['shape_pt_lon']}|{p.get('shape_dist_traveled', '')}"
            for p in points
        ]
    )


def construire(
    sortie: Path,
    plan: dict[str, Provenance],
    index_par_export: dict[str, IndexExport],
    config: dict,
    identite_feed: dict[str, str],
    journal=print,
) -> Statistiques:
    """Écrit le feed annuel dans `sortie` et renvoie ses compteurs."""
    stats = Statistiques()
    sortie.mkdir(parents=True, exist_ok=True)
    dec_coord = int(config["canonicalisation"]["decimales_coordonnees"])
    dec_dist = int(config["canonicalisation"]["decimales_distance"])
    deplacement_max = float(config["controles"]["deplacement_arret_max_m"])

    # Journées à charger, groupées par export : (étiquette → dates sources).
    journees: dict[str, set[str]] = {}
    for provenance in plan.values():
        if provenance.mode in (REEL, EXTRAPOLE) and provenance.export:
            journees.setdefault(provenance.export, set()).add(provenance.date_source)

    # Ordre de traitement : le plus ancien export d'abord, pour que le `trip_id`
    # conservé soit le plus stable dans l'historique du dépôt.
    ordre = sorted(journees, key=lambda e: (index_par_export[e].export.date_min, e))

    contenu_vers_trip: dict[str, str] = {}
    trip_pris: dict[str, str] = {}
    journee_canon: dict[tuple[str, str], list[str]] = {}
    shapes_vues: dict[str, dict[str, str]] = {}  # shape_id → {hash: shape_id_final}
    trips_sortie: dict[str, dict[str, str]] = {}
    stops_references: set[str] = set()
    routes_referencees: set[str] = set()

    colonnes_horaires = ["trip_id", *CHAMPS_HORAIRE_IDENTITE, "timepoint"]
    colonnes_shapes = [
        "shape_id",
        "shape_pt_lat",
        "shape_pt_lon",
        "shape_pt_sequence",
        "shape_dist_traveled",
    ]
    ecrivain_horaires = gtfs_io.EcrivainCSV(sortie / "stop_times.txt", colonnes_horaires)
    ecrivain_shapes = gtfs_io.EcrivainCSV(sortie / "shapes.txt", colonnes_shapes)

    for etiquette in ordre:
        index = index_par_export[etiquette]
        export = index.export
        dates_sources = journees[etiquette]
        trips_voulus: set[str] = set()
        for date in dates_sources:
            trips_voulus.update(index.trips_par_date.get(date, ()))
        journal(
            f"    {etiquette} : {len(dates_sources)} journée(s) retenue(s), "
            f"{len(trips_voulus):,} trip(s) à charger"
        )

        # ── Géométries nécessaires ────────────────────────────────────────────
        shapes_voulues = {
            index.trips[t].get("shape_id", "") for t in trips_voulus
        } - {""}
        points_par_shape: dict[str, list[dict[str, str]]] = {}
        for ligne in gtfs_io.lire(export, "shapes.txt"):
            if ligne["shape_id"] in shapes_voulues:
                points_par_shape.setdefault(ligne["shape_id"], []).append(
                    gtfs_io.canoniser_point_shape(ligne, dec_coord, dec_dist)
                )
        for points in points_par_shape.values():
            points.sort(key=lambda p: int(p["shape_pt_sequence"]))

        hash_par_shape = {
            shape_id: hash_geometrie(points)
            for shape_id, points in points_par_shape.items()
        }

        # ── Horaires nécessaires ──────────────────────────────────────────────
        horaires_par_trip: dict[str, list[dict[str, str]]] = {}
        for ligne in gtfs_io.lire(export, "stop_times.txt"):
            trip_id = ligne["trip_id"]
            if trip_id in trips_voulus:
                horaires_par_trip.setdefault(trip_id, []).append(
                    gtfs_io.canoniser_horaire(ligne, dec_dist)
                )
        for horaires in horaires_par_trip.values():
            horaires.sort(key=lambda h: int(h["stop_sequence"]))

        # ── Identité par contenu ──────────────────────────────────────────────
        trip_local_vers_canon: dict[str, str] = {}
        for trip_id in sorted(trips_voulus):
            meta = index.trips[trip_id]
            horaires = horaires_par_trip.get(trip_id)
            if not horaires:
                journal(f"[ALARME] {etiquette} : trip {trip_id} sans horaire, écarté")
                continue
            shape_id = meta.get("shape_id", "")
            hash_shape = hash_par_shape.get(shape_id, "")

            cle = cle_contenu(meta, horaires, hash_shape)
            deja = contenu_vers_trip.get(cle)
            if deja is not None:
                trip_local_vers_canon[trip_id] = deja
                stats.trips_fusionnes += 1
                continue

            # Le contenu est nouveau. On garde le trip_id de l'opérateur, sauf
            # s'il désigne déjà un autre contenu — un fork réel, qui doit rester
            # visible plutôt que d'être arbitré.
            trip_final = trip_id
            if trip_id in trip_pris:
                trip_final = f"{trip_id}__{etiquette}"
                stats.trips_forkes += 1
                journal(
                    f"    fork : trip {trip_id} a un contenu différent dans {etiquette}, "
                    f"conservé sous {trip_final}"
                )
            trip_pris[trip_final] = cle
            contenu_vers_trip[cle] = trip_final
            trip_local_vers_canon[trip_id] = trip_final

            # Géométrie : première variante sous son identifiant d'origine, les
            # suivantes dupliquées. Jamais de fusion point par point.
            shape_final = ""
            if shape_id:
                variantes = shapes_vues.setdefault(shape_id, {})
                shape_final = variantes.get(hash_shape, "")
                if not shape_final:
                    shape_final = shape_id if not variantes else f"{shape_id}__{etiquette}"
                    if variantes:
                        stats.shapes_dupliquees += 1
                        journal(
                            f"    géométrie : shape {shape_id} diverge dans {etiquette} "
                            f"({len(points_par_shape.get(shape_id, []))} points), "
                            f"conservée sous {shape_final}"
                        )
                    variantes[hash_shape] = shape_final
                    for point in points_par_shape.get(shape_id, ()):
                        ecrivain_shapes.ecrire({**point, "shape_id": shape_final})

            sortie_trip = {c: meta.get(c, "") for c in COLONNES_TRIPS}
            sortie_trip["trip_id"] = trip_final
            sortie_trip["shape_id"] = shape_final
            sortie_trip["service_id"] = ""  # attribué à la fin
            trips_sortie[trip_final] = sortie_trip
            routes_referencees.add(meta.get("route_id", ""))

            for horaire in horaires:
                ecrivain_horaires.ecrire({**horaire, "trip_id": trip_final})
                stops_references.add(horaire["stop_id"])
            stats.horaires_ecrits += len(horaires)

        for date in dates_sources:
            mappes = [
                trip_local_vers_canon[t]
                for t in index.trips_par_date.get(date, ())
                if t in trip_local_vers_canon
            ]
            distincts = sorted(set(mappes))
            # Deux courses de contenu identique le MÊME jour existent en théorie
            # (deux véhicules sur un même horaire, pour la capacité). Les
            # confondre retirerait une course de l'offre de cette journée. Ce cas
            # ne se produit sur aucun des exports 2026, mais il ne doit pas
            # passer en silence s'il apparaît : V2 le bloquerait de toute façon,
            # autant le nommer ici.
            if len(distincts) != len(mappes):
                stats.collisions_meme_jour += len(mappes) - len(distincts)
                journal(
                    f"[ALARME] {etiquette} {date} : {len(mappes) - len(distincts)} course(s) de "
                    f"contenu identique le même jour — l'offre de cette journée serait amputée"
                )
            journee_canon[(etiquette, date)] = distincts

    ecrivain_horaires.fermer()
    ecrivain_shapes.fermer()
    stats.trips_ecrits = len(trips_sortie)

    # ── Calendrier par ensembles de dates ────────────────────────────────────
    dates_par_trip: dict[str, list[str]] = {}
    for date in sorted(plan):
        provenance = plan[date]
        if provenance.mode not in (REEL, EXTRAPOLE):
            continue
        for trip_final in journee_canon.get((provenance.export, provenance.date_source), ()):
            dates_par_trip.setdefault(trip_final, []).append(date)

    ensembles: dict[tuple[str, ...], list[str]] = {}
    for trip_final, dates in dates_par_trip.items():
        ensembles.setdefault(tuple(dates), []).append(trip_final)

    # Services numérotés par cardinalité décroissante : SVC_0001 est le service
    # le plus fréquent, ce qui rend le calendrier lisible à l'œil nu.
    ordre_services = sorted(ensembles.items(), key=lambda kv: (-len(kv[0]), kv[0]))
    calendrier: list[dict[str, str]] = []
    for rang, (dates, trips) in enumerate(ordre_services, start=1):
        service_id = f"SVC_{rang:04d}"
        for trip_final in trips:
            trips_sortie[trip_final]["service_id"] = service_id
        for date in dates:
            calendrier.append(
                {"service_id": service_id, "date": date, "exception_type": "1"}
            )
    stats.services = len(ordre_services)
    stats.lignes_calendrier = len(calendrier)

    sans_service = [t for t, l in trips_sortie.items() if not l["service_id"]]
    if sans_service:
        journal(
            f"[ALARME] {len(sans_service)} trip(s) écrit(s) sans aucune date active — "
            f"ils sont retirés de trips.txt, mais leurs horaires et géométries sont "
            f"déjà écrits : la fermeture référentielle les signalera en orphelins"
        )
        for trip_final in sans_service:
            del trips_sortie[trip_final]
        stats.trips_ecrits = len(trips_sortie)

    gtfs_io.ecrire_table(
        sortie / "trips.txt",
        COLONNES_TRIPS,
        trips_sortie.values(),
        tri=lambda l: (l["route_id"], l["service_id"], l["trip_id"]),
    )
    gtfs_io.ecrire_table(
        sortie / "calendar_dates.txt",
        COLONNES_CALENDAR,
        calendrier,
        tri=lambda l: (l["service_id"], l["date"]),
    )
    # calendar.txt vide : le lecteur du dépôt l'exige, et tout le calendrier est
    # déjà porté par calendar_dates.txt.
    gtfs_io.ecrire_table(sortie / "calendar.txt", COLONNES_CALENDAR_HEBDO, [])

    # ── Infrastructure : le dernier export publié fait foi ───────────────────
    _ecrire_infrastructure(
        sortie,
        ordre,
        index_par_export,
        stops_references,
        routes_referencees,
        dec_coord,
        deplacement_max,
        stats,
        journal,
    )

    _ecrire_feed_info(sortie, plan, identite_feed)

    stats.orphelins = _verifier_fermeture(sortie, journal)
    return stats


def _ecrire_infrastructure(
    sortie: Path,
    ordre: list[str],
    index_par_export: dict[str, IndexExport],
    stops_references: set[str],
    routes_referencees: set[str],
    dec_coord: int,
    deplacement_max: float,
    stats: Statistiques,
    journal,
) -> None:
    """Arrêts, lignes, agences, correspondances : dernière version publiée.

    Les arrêts ne sont jamais suffixés : dédoubler un `stop_id` créerait deux
    quais distincts dans OTP et dégraderait les correspondances. Un arrêt qui
    bouge notablement est signalé, pas arbitré en silence.
    """
    arrets: dict[str, dict[str, str]] = {}
    lignes: dict[str, dict[str, str]] = {}
    agences: dict[str, dict[str, str]] = {}
    correspondances: dict[tuple[str, str], dict[str, str]] = {}
    colonnes = {"stops": [], "routes": [], "agency": [], "transfers": []}

    for etiquette in ordre:  # du plus ancien au plus récent : le dernier écrase
        export = index_par_export[etiquette].export
        for nom, cible in (("stops.txt", "stops"), ("routes.txt", "routes"),
                           ("agency.txt", "agency"), ("transfers.txt", "transfers")):
            for entete in gtfs_io.entetes(export, nom):
                if entete not in colonnes[cible]:
                    colonnes[cible].append(entete)

        for ligne in gtfs_io.lire(export, "stops.txt"):
            canonique = gtfs_io.canoniser_arret(ligne, dec_coord)
            stop_id = canonique["stop_id"]
            precedent = arrets.get(stop_id)
            if precedent is not None:
                ecart = gtfs_io.distance_m(
                    precedent.get("stop_lat", ""), precedent.get("stop_lon", ""),
                    canonique.get("stop_lat", ""), canonique.get("stop_lon", ""),
                )
                if ecart > deplacement_max:
                    stats.arrets_deplaces.append((stop_id, ecart))
            arrets[stop_id] = canonique

        for ligne in gtfs_io.lire(export, "routes.txt"):
            route_id = ligne["route_id"]
            if route_id in lignes and lignes[route_id] != ligne:
                stats.lignes_redefinies += 1
            lignes[route_id] = ligne

        for ligne in gtfs_io.lire(export, "agency.txt"):
            agences[ligne.get("agency_id", "")] = ligne

        for ligne in gtfs_io.lire(export, "transfers.txt"):
            correspondances[(ligne.get("from_stop_id", ""), ligne.get("to_stop_id", ""))] = ligne

    if stats.arrets_deplaces:
        pires = sorted(stats.arrets_deplaces, key=lambda x: -x[1])[:5]
        journal(
            f"[ALARME] {len(stats.arrets_deplaces)} arrêt(s) déplacé(s) de plus de "
            f"{deplacement_max:.0f} m entre exports — les pires : "
            + ", ".join(f"{s} ({d:.0f} m)" for s, d in pires)
        )
    if stats.lignes_redefinies:
        journal(f"    infrastructure : {stats.lignes_redefinies} redéfinition(s) de ligne, dernière version retenue")

    # Fermeture sur les stations parentes : un quai retenu dont la station a été
    # écartée laisserait une référence pendante que OTP signale à chaque build.
    retenus = set(stops_references)
    for _ in range(4):  # les hiérarchies GTFS sont peu profondes
        parents = {
            arrets[s].get("parent_station", "")
            for s in retenus
            if s in arrets and arrets[s].get("parent_station")
        } - {""}
        nouveaux = parents - retenus
        if not nouveaux:
            break
        retenus |= nouveaux

    gtfs_io.ecrire_table(
        sortie / "stops.txt",
        colonnes["stops"],
        [a for sid, a in arrets.items() if sid in retenus],
        tri=lambda l: l["stop_id"],
    )
    gtfs_io.ecrire_table(
        sortie / "routes.txt",
        colonnes["routes"],
        [l for rid, l in lignes.items() if rid in routes_referencees],
        tri=lambda l: l["route_id"],
    )
    gtfs_io.ecrire_table(
        sortie / "agency.txt", colonnes["agency"], list(agences.values()),
        tri=lambda l: l.get("agency_id", ""),
    )
    gtfs_io.ecrire_table(
        sortie / "transfers.txt",
        colonnes["transfers"],
        [
            t for (source, cible), t in correspondances.items()
            if source in retenus and cible in retenus
        ],
        tri=lambda l: (l.get("from_stop_id", ""), l.get("to_stop_id", "")),
    )


def _ecrire_feed_info(sortie: Path, plan: dict[str, Provenance], identite: dict[str, str]) -> None:
    dates = sorted(plan)
    gtfs_io.ecrire_table(
        sortie / "feed_info.txt",
        COLONNES_FEED_INFO,
        [
            {
                "feed_id": identite["feed_id"],
                "feed_publisher_name": identite["publisher"],
                "feed_publisher_url": identite["url"],
                "feed_lang": "fr",
                "feed_start_date": dates[0],
                "feed_end_date": dates[-1],
                "feed_version": identite["version"],
            }
        ],
    )


def _verifier_fermeture(sortie: Path, journal) -> dict[str, int]:
    """Vérifie que toute référence du feed écrit résout, dans les deux sens."""
    export = Export(chemin=sortie, etiquette=sortie.name, empreinte="")
    stops = {l["stop_id"] for l in gtfs_io.lire(export, "stops.txt")}
    routes = {l["route_id"] for l in gtfs_io.lire(export, "routes.txt")}
    shapes = {l["shape_id"] for l in gtfs_io.lire(export, "shapes.txt")}
    services = {l["service_id"] for l in gtfs_io.lire(export, "calendar_dates.txt")}

    trips = {}
    orphelins = {"route": 0, "shape": 0, "service": 0, "stop": 0, "trip": 0}
    for ligne in gtfs_io.lire(export, "trips.txt"):
        trips[ligne["trip_id"]] = ligne
        if ligne["route_id"] not in routes:
            orphelins["route"] += 1
        if ligne["shape_id"] and ligne["shape_id"] not in shapes:
            orphelins["shape"] += 1
        if ligne["service_id"] not in services:
            orphelins["service"] += 1
    for ligne in gtfs_io.lire(export, "stop_times.txt"):
        if ligne["trip_id"] not in trips:
            orphelins["trip"] += 1
        if ligne["stop_id"] not in stops:
            orphelins["stop"] += 1

    total = sum(orphelins.values())
    if total:
        journal(f"[ALARME] fermeture référentielle : {total} orphelin(s) — {orphelins}")
    else:
        journal("    fermeture référentielle : aucune référence orpheline")
    return orphelins
