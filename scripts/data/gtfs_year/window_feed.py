"""
Extrait une fenêtre de quelques semaines d'un feed annuel.

POURQUOI
--------
OTP consomme sans difficulté un feed couvrant l'année entière. La chaîne GAMA,
non : le calendrier des services y est encodé en masque binaire 64 bits —
`assert len(all_dates) <= 64` dans `llm-agents/inputs/gtfs/gama.py`, décodé côté
modèle par `PublicTransport.gaml` (`trip_calendar_map` et `BITWISE_BIT_VAL`).
Au-delà de 64 dates, l'export échoue ; et `build_trips` balaie tous les trips
pour chacun d'eux, ce qui rend un feed annuel impraticable de toute façon
(28 Mo de `trip_info.json` pour 58 jours et 39 000 trips).

La fenêtre est donc ce que voient GAMA et le runtime, le feed annuel ce que voit
OTP. Elle doit contenir la date de simulation : hors calendrier,
`is_trip_available_today` se contente d'un avertissement et ne planifie plus
aucune course.

USAGE
-----
    make gtfs-window START=2026-03-16 DAYS=64
    python -m scripts.data.gtfs_year.window_feed --source data/gtfs_year/tisseo_2026 \\
        --debut 20260316 --jours 64 --sortie data/gtfs_year/fenetre_gama

La fenêtre s'écrit HORS de `data/gtfs/` : l'installer dans le feed en service est
une étape de publication, décrite dans `docs/arch/gtfs-annee.md`, pas le défaut.

CODES DE SORTIE
---------------
    0  fenêtre extraite
    1  source introuvable
    2  fenêtre vide, ou plus longue que ce que le masque binaire supporte
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.data.gtfs_year import gtfs_io  # noqa: E402
from scripts.data.gtfs_year.gtfs_io import Export  # noqa: E402

LIMITE_MASQUE = 64

CODE_RESSOURCE = 1
CODE_REFUS = 2


def fenetrer(
    source: Path, debut: str, jours: int, sortie: Path, journal=print
) -> int:
    """Copie dans `sortie` la part du feed `source` active sur la fenêtre."""
    if not source.exists():
        journal(f"[ALARME] source introuvable : {source}")
        return CODE_RESSOURCE
    if jours > LIMITE_MASQUE:
        journal(
            f"[ALARME] fenêtre de {jours} jours : le masque binaire du modèle GAMA "
            f"n'en supporte que {LIMITE_MASQUE}"
        )
        return CODE_REFUS

    premier = dt.date(int(debut[:4]), int(debut[4:6]), int(debut[6:8]))
    fenetre = {
        (premier + dt.timedelta(days=i)).strftime("%Y%m%d") for i in range(jours)
    }
    entree = Export(chemin=source, etiquette=source.name, empreinte="")
    sortie.mkdir(parents=True, exist_ok=True)

    calendrier = [
        ligne for ligne in gtfs_io.lire(entree, "calendar_dates.txt")
        if ligne["date"] in fenetre
    ]
    services = {ligne["service_id"] for ligne in calendrier}
    if not services:
        journal(f"[ALARME] aucune date du feed dans la fenêtre {debut} +{jours} j")
        return CODE_REFUS

    trips = [
        ligne for ligne in gtfs_io.lire(entree, "trips.txt")
        if ligne["service_id"] in services
    ]
    trips_retenus = {ligne["trip_id"] for ligne in trips}
    routes_retenues = {ligne["route_id"] for ligne in trips}
    shapes_retenues = {ligne.get("shape_id", "") for ligne in trips} - {""}

    horaires = [
        ligne for ligne in gtfs_io.lire(entree, "stop_times.txt")
        if ligne["trip_id"] in trips_retenus
    ]
    arrets_retenus = {ligne["stop_id"] for ligne in horaires}

    tables = [
        ("calendar_dates.txt", calendrier, lambda l: (l["service_id"], l["date"])),
        ("trips.txt", trips, lambda l: (l["route_id"], l["service_id"], l["trip_id"])),
        ("stop_times.txt", horaires, lambda l: (l["trip_id"], int(l["stop_sequence"]))),
    ]
    for nom, lignes, tri in tables:
        colonnes = gtfs_io.entetes(entree, nom)
        gtfs_io.ecrire_table(sortie / nom, colonnes, lignes, tri=tri)

    filtres = [
        ("routes.txt", lambda l: l["route_id"] in routes_retenues, lambda l: l["route_id"]),
        ("shapes.txt", lambda l: l["shape_id"] in shapes_retenues,
         lambda l: (l["shape_id"], int(l["shape_pt_sequence"]))),
        ("agency.txt", lambda l: True, lambda l: l.get("agency_id", "")),
        ("calendar.txt", lambda l: False, None),
        ("feed_info.txt", lambda l: True, None),
    ]
    for nom, garder, tri in filtres:
        colonnes = gtfs_io.entetes(entree, nom)
        if not colonnes:
            continue
        gtfs_io.ecrire_table(
            sortie / nom, colonnes, [l for l in gtfs_io.lire(entree, nom) if garder(l)], tri=tri
        )

    # Les arrêts embarquent leurs stations parentes, sans quoi OTP signale des
    # références pendantes à chaque construction de graphe.
    tous_arrets = {l["stop_id"]: l for l in gtfs_io.lire(entree, "stops.txt")}
    retenus = set(arrets_retenus)
    for _ in range(4):
        parents = {
            tous_arrets[s].get("parent_station", "")
            for s in retenus
            if s in tous_arrets and tous_arrets[s].get("parent_station")
        } - {""}
        if not parents - retenus:
            break
        retenus |= parents
    gtfs_io.ecrire_table(
        sortie / "stops.txt",
        gtfs_io.entetes(entree, "stops.txt"),
        [l for sid, l in tous_arrets.items() if sid in retenus],
        tri=lambda l: l["stop_id"],
    )
    colonnes_transferts = gtfs_io.entetes(entree, "transfers.txt")
    if colonnes_transferts:
        gtfs_io.ecrire_table(
            sortie / "transfers.txt",
            colonnes_transferts,
            [
                l for l in gtfs_io.lire(entree, "transfers.txt")
                if l.get("from_stop_id") in retenus and l.get("to_stop_id") in retenus
            ],
            tri=lambda l: (l.get("from_stop_id", ""), l.get("to_stop_id", "")),
        )

    dates = sorted({l["date"] for l in calendrier})
    journal(
        f"    fenêtre {dates[0]} → {dates[-1]} ({len(dates)} date(s) servies sur {jours} demandées) : "
        f"{len(trips):,} trips, {len(horaires):,} horaires, {len(services):,} services, "
        f"{len(retenus):,} arrêts → {sortie}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parseur.add_argument("--source", type=Path, required=True, help="feed annuel (répertoire ou zip)")
    parseur.add_argument("--debut", required=True, help="premier jour de la fenêtre, AAAAMMJJ")
    parseur.add_argument("--jours", type=int, default=LIMITE_MASQUE)
    parseur.add_argument("--sortie", type=Path, required=True)
    parseur.add_argument("--zip", action="store_true", help="archiver la fenêtre à côté du répertoire")
    args = parseur.parse_args(argv)

    debut = args.debut.replace("-", "")
    code = fenetrer(args.source, debut, args.jours, args.sortie, print)
    if code == 0 and args.zip:
        archive = gtfs_io.zipper(args.sortie, args.sortie.with_suffix(".zip"))
        print(f"    archive : {archive} ({archive.stat().st_size / 1_048_576:.1f} Mo)")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
