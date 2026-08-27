"""
Indexation de l'offre d'un export et détection de sa fenêtre fiable.

Les exports Tisséo sont « glissants » : chacun couvre environ 35 jours, mais
n'est complet que sur les premières semaines. Au-delà, l'opérateur ne publie
plus que les lignes structurantes — le nombre de lignes actives s'effondre de
123 à 3 (métro A, B, TELEO), puis à 1. Reprendre ces journées telles quelles
ferait tourner la simulation sur un réseau réduit au métro, sans aucun signal
d'erreur.

La coupe se fait d'abord sur un ratio RELATIF au type de jour. Un seuil absolu
exigeant du genre « au moins 80 % du maximum » rejetterait le samedi 11/04/2026
(88 lignes) et le dimanche 12/04 (48 lignes), qui sont des journées parfaitement
normales : un dimanche a légitimement trois fois moins de lignes qu'un mardi.

Un plancher absolu très bas complète la règle, parce que la règle par type de
jour est aveugle quand un type de jour n'apparaît jamais complet dans l'export —
sa référence vaut alors le niveau de la queue elle-même.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import gtfs_io
from .calendar_fr import JOURS, to_date
from .gtfs_io import Export


@dataclass
class IndexExport:
    """Ce qu'un export dit de chaque journée qu'il couvre."""

    export: Export
    trips: dict[str, dict[str, str]] = field(default_factory=dict)
    trips_par_date: dict[str, list[str]] = field(default_factory=dict)
    lignes_par_date: dict[str, int] = field(default_factory=dict)
    agences: list[dict[str, str]] = field(default_factory=list)

    @property
    def dates(self) -> list[str]:
        return sorted(self.trips_par_date)

    def nb_trips(self, date: str) -> int:
        return len(self.trips_par_date.get(date, ()))


def indexer(export: Export, journal=print) -> IndexExport:
    """Construit l'index d'un export : quels trips roulent quel jour.

    Ne lit ni `stop_times.txt` ni `shapes.txt` — les deux fichiers lourds ne
    seront parcourus qu'une fois les journées réellement retenues connues.
    """
    index = IndexExport(export=export)
    index.agences = list(gtfs_io.lire(export, "agency.txt"))

    services_par_trip: dict[str, str] = {}
    trips_par_service: dict[str, list[str]] = {}
    lignes_par_service: dict[str, set[str]] = {}
    for ligne in gtfs_io.lire(export, "trips.txt"):
        trip_id = ligne["trip_id"]
        service_id = ligne["service_id"]
        index.trips[trip_id] = ligne
        services_par_trip[trip_id] = service_id
        trips_par_service.setdefault(service_id, []).append(trip_id)
        lignes_par_service.setdefault(service_id, set()).add(ligne["route_id"])

    exceptions_ignorees = 0
    lignes_par_date: dict[str, set[str]] = {}
    for ligne in gtfs_io.lire(export, "calendar_dates.txt"):
        if ligne.get("exception_type") != "1":
            exceptions_ignorees += 1
            continue
        date = ligne["date"]
        service_id = ligne["service_id"]
        index.trips_par_date.setdefault(date, []).extend(trips_par_service.get(service_id, ()))
        lignes_par_date.setdefault(date, set()).update(lignes_par_service.get(service_id, ()))

    calendrier_hebdo = list(gtfs_io.lire(export, "calendar.txt"))
    if calendrier_hebdo:
        raise ValueError(
            f"[ALARME] {export.etiquette} : calendar.txt non vide "
            f"({len(calendrier_hebdo)} services hebdomadaires). Ce pipeline ne "
            f"gère que les calendriers en dates explicites."
        )
    if exceptions_ignorees:
        journal(
            f"    {export.etiquette} : {exceptions_ignorees} ligne(s) de calendar_dates "
            f"en exception_type≠1 ignorée(s)"
        )

    for date in index.trips_par_date:
        index.trips_par_date[date].sort()
    index.lignes_par_date = {d: len(v) for d, v in lignes_par_date.items()}

    dates = index.dates
    if dates:
        export.date_min, export.date_max = dates[0], dates[-1]
    journal(
        f"    {export.etiquette} : {len(index.trips):,} trips, {len(dates)} dates "
        f"({export.date_min} → {export.date_max})"
    )
    return index


def fenetre_fiable(index: IndexExport, config: dict, journal=print) -> list[str]:
    """Dates de l'export à considérer comme complètes.

    Deux seuils, et la coupe porte sur le plus long suffixe qui les enfreint :

      - relatif au type de jour : sous `ratio_lignes_min` fois le maximum de
        lignes atteint par ce type de jour dans l'export ;
      - absolu : sous `ratio_plancher_lignes` fois le maximum de l'export, tous
        types de jour confondus — le filet quand un type de jour n'apparaît
        jamais complet.

    La troncature ne se rouvre jamais : tout ce qui suit son début est écarté.
    """
    ratio_min = float(config["ratio_lignes_min"])
    ratio_plancher = float(config["ratio_plancher_lignes"])
    jours_min = int(config["jours_min_par_export"])

    dates = index.dates
    if not dates:
        return []

    # Référence : le MAXIMUM de lignes actives observé pour ce type de jour sur
    # tout l'export. Prendre la médiane des premières semaines paraissait plus
    # robuste, mais un export livré tardivement — majoritairement composé de sa
    # propre queue tronquée — contaminerait sa propre référence : la médiane
    # tomberait au niveau de la queue, plus rien ne serait « sous le seuil », et
    # l'export passerait intact en injectant des journées réduites au métro.
    reference: dict[str, int] = {}
    for date in dates:
        type_jour = JOURS[to_date(date).weekday()]
        lignes = index.lignes_par_date.get(date, 0)
        if lignes > reference.get(type_jour, -1):
            reference[type_jour] = lignes

    # Second garde-fou, absolu celui-là : une fraction du maximum atteint par
    # l'export, tous types de jour confondus. La règle par type de jour est
    # aveugle quand un type n'apparaît JAMAIS complet dans l'export — sa
    # référence vaut alors le niveau de la queue elle-même, et rien n'est coupé.
    # Le plancher est très bas pour laisser passer les dimanches, qui roulent
    # légitimement à 39 % des lignes d'un mardi sur le réseau toulousain.
    plancher = ratio_plancher * max(index.lignes_par_date.values(), default=0)

    def sous_seuil(date: str) -> bool:
        lignes = index.lignes_par_date.get(date, 0)
        if lignes < plancher:
            return True
        type_jour = JOURS[to_date(date).weekday()]
        seuil = reference.get(type_jour)
        if seuil is None:
            return False
        return lignes < ratio_min * seuil

    # La troncature est un effondrement DURABLE qui court jusqu'à la fin de
    # l'export, pas un creux isolé. On cherche donc le plus long suffixe dont
    # toutes les journées sont sous le seuil. Couper au premier creux
    # rencontré rejetterait les jours fériés, qui roulent légitimement au
    # niveau d'un dimanche : le lundi de Pâques 06/04 (48 lignes contre 123
    # pour un lundi ordinaire) amputerait l'export de six journées valides.
    debut_queue = len(dates)
    for position in range(len(dates) - 1, -1, -1):
        if not sous_seuil(dates[position]):
            break
        debut_queue = position

    retenues = dates[:debut_queue]
    if debut_queue < len(dates):
        premiere = dates[debut_queue]
        type_jour = JOURS[to_date(premiere).weekday()]
        journal(
            f"    {index.export.etiquette} : queue tronquée à partir du {premiere} "
            f"({index.lignes_par_date.get(premiere, 0)} lignes actives contre "
            f"{reference.get(type_jour)} attendues pour un {type_jour}) — "
            f"{len(dates) - debut_queue} date(s) écartée(s)"
        )

    creux_isoles = [d for d in retenues if sous_seuil(d)]
    if creux_isoles:
        journal(
            f"    {index.export.etiquette} : {len(creux_isoles)} creux isolé(s) conservé(s) "
            f"(offre réduite mais suivie d'un retour à la normale, typiquement un férié) : "
            f"{', '.join(creux_isoles[:6])}{'…' if len(creux_isoles) > 6 else ''}"
        )

    if len(retenues) < jours_min:
        journal(
            f"[ALARME] {index.export.etiquette} : seulement {len(retenues)} date(s) fiable(s), "
            f"minimum attendu {jours_min} — export inutilisable"
        )
        return []

    index.export.fin_fiable = retenues[-1]
    index.export.jours_fiables = retenues
    return retenues
