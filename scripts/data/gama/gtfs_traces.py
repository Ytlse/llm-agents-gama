"""Tracés d'un réseau GTFS qui ne publie pas de `shapes.txt` — le TER SNCF.

POURQUOI CE MODULE EXISTE
-------------------------
`routes.shp` (la géométrie que GAMA dessine ET le long de laquelle roulent ses
`public_vehicle`) et `trip_info.json` (les courses) sont produits par deux
recettes. Elles doivent nommer les tracés **exactement** de la même façon :
`PublicTransport.gaml` fait `route first_with (each.shape_id = shape_id)` à la
création de chaque véhicule, et un `shape_id` de course absent de la couche rend
un `route` nil — donc un véhicule sans géométrie, sans couleur et sans distances.
Ce module est l'endroit unique où ces `shape_id` sont fabriqués, pour que les
deux recettes ne puissent pas diverger en silence. C'est le décalage qui a duré
cinq mois (couches à trois réseaux, courses à un seul).

UN TRACÉ PAR SUITE D'ARRÊTS DISTINCTE, PAS UN PAR (LIGNE, SENS)
---------------------------------------------------------------
Un GTFS normal publie un `shape_id` par **motif de desserte** : Tisséo en
publie 395 pour 124 lignes. Le TER, lui, ne publie aucune géométrie (son
`shapes.txt` n'a qu'un en-tête) et laisse `trips.shape_id` vide.

La reconstruction par (ligne, sens) — un tracé, celui de la course la plus
desservie — suffit à l'affichage mais **fabrique du mouvement** dès qu'on
l'utilise pour faire rouler des véhicules. `build_trips`
(`llm-agents/inputs/gtfs/gama.py`) force le dernier segment d'une course jusqu'au
dernier point du tracé :

    shape_segments[-1] = len(shape_dist_traveled_list) - 1

Une course Toulouse → Tarbes posée sur le tracé Toulouse → Pau roulerait donc
jusqu'à Pau, dans le temps de trajet de Tarbes. Mesuré sur l'export en service :
sur 1 137 courses TER, 168 (14,8 %) ne sont même pas une sous-suite du tracé de
leur couple (ligne, sens), et 6 n'ont aucun `direction_id` — elles étaient
**silencieusement absentes** de la couche, leur `shape_id` valant `NaN`.

D'où la règle retenue : **une suite d'arrêts distincte = un tracé**, comme le
fait un GTFS qui publie ses géométries. Chaque course roule alors exactement sur
la polyligne de ses propres arrêts, le forçage du dernier segment est un
no-op, et aucune course n'est écartée.

Le `shape_id` est `<route_id>:<sens>:<empreinte>` où l'empreinte est celle de la
suite d'arrêts : elle ne bouge pas quand l'opérateur publie de nouvelles courses,
là où une numérotation par rang décalerait tous les identifiants suivants.

CE QUE CE MODULE NE FAIT PAS
----------------------------
Il ne connaît ni géométrie ni projection : il rend des **suites de `stop_id`**.
La polyligne (pour `routes.shp`) et les distances cumulées (pour
`trip_info.json`) sont calculées par les appelants, à partir des coordonnées du
feed. Ainsi les deux recettes partent des mêmes arrêts dans le même ordre.
"""

from __future__ import annotations

import collections
import hashlib

# `direction_id` absent : le TER en publie 6 courses. Un marqueur explicite vaut
# mieux qu'un repli sur "0", qui les mélangerait à un sens réel, et mieux que le
# `NaN` qui les faisait disparaître.
SENS_ABSENT = "-"

LONGUEUR_EMPREINTE = 8


def empreinte_suite(suite: list[str]) -> str:
    """Empreinte stable d'une suite d'arrêts — l'identité du motif de desserte."""
    brut = "".join(suite).encode("utf-8")
    return hashlib.sha1(brut).hexdigest()[:LONGUEUR_EMPREINTE]


def sens_normalise(direction_id) -> str:
    """`direction_id` en une chaîne, `SENS_ABSENT` quand il n'y en a pas.

    Le même champ arrive ici en `""` (lecteur csv), en `None` ou en `float('nan')`
    (pandas, `dtype=str`, cellule vide). Les confondre avec un sens réel — ou les
    laisser devenir la chaîne `"nan"` — est exactement ce qui a fait disparaître
    6 courses TER de la couche.
    """
    if direction_id is None:
        return SENS_ABSENT
    if isinstance(direction_id, float) and direction_id != direction_id:  # NaN
        return SENS_ABSENT
    texte = str(direction_id).strip()
    return SENS_ABSENT if texte in ("", "nan", "NaN", "None") else texte


def shape_id_synthetique(route_id: str, direction_id, suite: list[str]) -> str:
    """Le `shape_id` que porteront la couche ET les courses pour ce motif."""
    return f"{route_id}:{sens_normalise(direction_id)}:{empreinte_suite(suite)}"


def traces_par_suite_d_arrets(
    trips: list[dict], suites_par_course: dict[str, list[str]], journal=print
) -> tuple[dict[str, list[str]], dict[str, str], dict]:
    """Fabrique un tracé par suite d'arrêts distincte.

    Args:
        trips: lignes de `trips.txt` (dicts avec `route_id`, `trip_id`, `direction_id`)
        suites_par_course: `trip_id` → suite de `stop_id` ordonnée par `stop_sequence`
        journal: où écrire le compte rendu

    Returns:
        (traces, course_vers_trace, mesures) où
          * `traces` : `shape_id` → suite de `stop_id` (la polyligne à construire)
          * `course_vers_trace` : `trip_id` → `shape_id`
          * `mesures` : compteurs, dont les courses écartées et pourquoi
    """
    traces: dict[str, list[str]] = {}
    course_vers_trace: dict[str, str] = {}
    ecartees: collections.Counter = collections.Counter()
    sans_sens = 0

    for ligne in trips:
        trip_id = ligne["trip_id"]
        suite = suites_par_course.get(trip_id, [])
        # Une polyligne demande deux points ; un arrêt répété ferait un segment nul,
        # et `build_trips` chercherait un vertex strictement plus loin qu'il n'existe.
        if len(suite) < 2:
            ecartees["moins_de_deux_arrets"] += 1
            continue
        if len(set(suite)) != len(suite):
            ecartees["arret_repete"] += 1
            continue
        direction = ligne.get("direction_id")
        if sens_normalise(direction) == SENS_ABSENT:
            sans_sens += 1
        shape_id = shape_id_synthetique(ligne["route_id"], direction, suite)
        connue = traces.get(shape_id)
        if connue is not None and connue != suite:
            # Collision d'empreinte : impossible en pratique (sha1 tronqué sur des
            # suites d'arrêts d'une même ligne), mais un tracé écrasé ferait rouler
            # une course sur la géométrie d'une autre. On le dit plutôt que d'arbitrer.
            journal(
                f"[ALARME] collision d'empreinte sur {shape_id} : deux suites d'arrêts "
                f"différentes ({len(connue)} et {len(suite)} arrêts) — course {trip_id} écartée"
            )
            ecartees["collision_empreinte"] += 1
            continue
        traces[shape_id] = suite
        course_vers_trace[trip_id] = shape_id

    mesures = {
        "courses": len(trips),
        "courses_tracees": len(course_vers_trace),
        "traces": len(traces),
        "courses_sans_direction_id": sans_sens,
        "courses_ecartees": dict(ecartees),
    }
    total_ecartees = sum(ecartees.values())
    if total_ecartees:
        journal(
            f"[ALARME] {total_ecartees} course(s) sans tracé reconstructible : {dict(ecartees)} "
            f"— elles n'auront aucun véhicule dans GAMA"
        )
    journal(
        f"    tracés reconstruits depuis les arrêts : {len(traces)} motif(s) de desserte "
        f"pour {len(course_vers_trace)}/{len(trips)} course(s)"
        + (f", dont {sans_sens} sans direction_id" if sans_sens else "")
    )
    return traces, course_vers_trace, mesures


def suites_depuis_stop_times(lignes_stop_times) -> dict[str, list[str]]:
    """`trip_id` → suite de `stop_id`, ordonnée par `stop_sequence`.

    `lignes_stop_times` est n'importe quel itérable de dicts portant `trip_id`,
    `stop_id` et `stop_sequence` — le lecteur csv d'un feed comme un DataFrame
    converti en enregistrements.
    """
    par_course: dict[str, list[tuple[int, str]]] = collections.defaultdict(list)
    for ligne in lignes_stop_times:
        par_course[ligne["trip_id"]].append((int(ligne["stop_sequence"]), ligne["stop_id"]))
    return {tid: [s for _, s in sorted(v)] for tid, v in par_course.items()}
