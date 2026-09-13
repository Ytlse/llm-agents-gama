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

Une queue peut aussi être tronquée **par ligne** sans que l'offre globale
s'effondre : l'export liO décrit tout le réseau jusqu'au changement de service
du 13/12/2026, puis ne prolonge que les lignes déjà renseignées. Treize lignes
`.liO 31` — dix dans le périmètre d'étude, toutes des rabattements sur gare —
s'arrêtent le 11 ou le 12/12/2026 et ne reviennent jamais sur les trente-sept
semaines suivantes, pendant que le nombre de lignes actives reste à 94 % de son
maximum. Aucun seuil global ne peut le voir : d'où `_falaise_lignes`.

Les deux formes de calendrier GTFS sont lues. Tisséo et le TER n'emploient que
`calendar_dates.txt`, une ligne par date de service ; liO publie un
`calendar.txt` hebdomadaire que `calendar_dates.txt` corrige ensuite dans les
deux sens (ajout `exception_type=1`, retrait `exception_type=2`). Le calendrier
est déplié en dates explicites à l'indexation ; le feed produit, lui, reste
toujours en dates explicites avec un `calendar.txt` vide (invariant V1).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from . import gtfs_io
from .calendar_fr import JOURS, to_date
from .gtfs_io import Export

# Colonnes de `calendar.txt`, dans l'ordre de `date.weekday()` (0 = lundi).
COLONNES_JOURS_GTFS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
_UN_JOUR = dt.timedelta(days=1)


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

    # Les deux façons dont un GTFS déclare quand un service roule. Tisséo et le
    # TER n'utilisent que `calendar_dates.txt` (une ligne par date) ; liO publie
    # un `calendar.txt` hebdomadaire (457 services sur 396 jours) que
    # `calendar_dates.txt` corrige ensuite dans les deux sens — 3 408 ajouts et
    # 2 925 retraits. Ignorer les retraits ferait rouler des cars les jours où
    # l'opérateur dit qu'ils ne roulent pas : le calendrier est déplié ici, et
    # le feed produit reste, lui, en dates explicites (invariant V1).
    dates_par_service: dict[str, set[str]] = {}
    calendrier_hebdo = list(gtfs_io.lire(export, "calendar.txt"))
    jours_deplies = 0
    for ligne in calendrier_hebdo:
        service_id = ligne["service_id"]
        debut, fin = ligne.get("start_date", ""), ligne.get("end_date", "")
        if not debut or not fin:
            journal(f"[ALARME] {export.etiquette} : service {service_id} sans bornes de validité")
            continue
        jour_courant, dernier = to_date(debut), to_date(fin)
        if jour_courant > dernier:
            journal(
                f"[ALARME] {export.etiquette} : service {service_id} borné à l'envers "
                f"({debut} → {fin}) — ignoré"
            )
            continue
        actives = dates_par_service.setdefault(service_id, set())
        while jour_courant <= dernier:
            if ligne.get(COLONNES_JOURS_GTFS[jour_courant.weekday()]) == "1":
                actives.add(f"{jour_courant:%Y%m%d}")
                jours_deplies += 1
            jour_courant += _UN_JOUR

    ajouts = retraits = retraits_sans_effet = 0
    for ligne in gtfs_io.lire(export, "calendar_dates.txt"):
        service_id, date = ligne["service_id"], ligne["date"]
        exception = ligne.get("exception_type")
        if exception == "1":
            dates_par_service.setdefault(service_id, set()).add(date)
            ajouts += 1
        elif exception == "2":
            actives = dates_par_service.get(service_id)
            if actives and date in actives:
                actives.discard(date)
                retraits += 1
            else:
                retraits_sans_effet += 1
        else:
            journal(
                f"[ALARME] {export.etiquette} : exception_type {exception!r} inconnu "
                f"(service {service_id}, {date}) — ligne ignorée"
            )

    lignes_par_date: dict[str, set[str]] = {}
    for service_id, dates_actives in dates_par_service.items():
        trips_du_service = trips_par_service.get(service_id, ())
        routes_du_service = lignes_par_service.get(service_id, ())
        for date in dates_actives:
            index.trips_par_date.setdefault(date, []).extend(trips_du_service)
            lignes_par_date.setdefault(date, set()).update(routes_du_service)

    if calendrier_hebdo:
        journal(
            f"    {export.etiquette} : calendar.txt déplié — {len(calendrier_hebdo)} service(s) "
            f"hebdomadaire(s), {jours_deplies:,} (service, date) produits"
        )
    if ajouts or retraits or retraits_sans_effet:
        journal(
            f"    {export.etiquette} : calendar_dates — {ajouts:,} ajout(s), {retraits:,} retrait(s), "
            f"{retraits_sans_effet:,} retrait(s) sans effet"
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


def _falaise_lignes(
    index: IndexExport, dates: list[str], config: dict, journal=print
) -> int | None:
    """Première date à partir de laquelle l'export décrit un réseau amputé.

    La règle 1 « historique » cherche un effondrement **global** du nombre de
    lignes actives. Elle est aveugle à la troncature *par ligne*, celle d'un
    export qui décrit le réseau entier jusqu'au prochain changement de service
    puis ne prolonge que les lignes déjà renseignées. Mesuré sur liO
    (2026-08-01 → 2027-08-31) : **treize lignes `.liO 31` cessent le 11 ou le
    12/12/2026** — dont dix desservent le périmètre d'étude, toutes des
    rabattements sur gare (Muret, Carbonne, Noé, Villefranche,
    Castelnau-d'Estrétefonds, Boussens) — et ne reprennent jamais sur les
    trente-sept semaines restantes. Leur `calendar.txt` s'arrête là (services
    du 06 au 12/12) quand celui des lignes voisines court jusqu'au 31/08/2027 :
    c'est l'horizon de l'export, pas une décision d'exploitation. L'offre
    globale, elle, ne bougeait presque pas (4 303 → 4 165 courses le lundi,
    260 lignes actives sur 276) : aucun seuil global ne pouvait le voir.

    Ce qui sépare une falaise d'une fin de saison n'est pas la forme de la
    perte, c'est **ce que l'export fait ensuite**. Les cinquante-deux lignes
    scolaires qui s'arrêtent le 30/06/2027 ne reprennent pas non plus, mais
    l'export s'achève neuf semaines plus tard, en pleines vacances d'été :
    leur absence est expliquée. Les treize du 11/12, elles, manquent à
    trente-sept semaines dont six mois de période scolaire. D'où la condition
    `falaise_jours_apres_min` : une saison dure au plus dix semaines, donc si
    l'export couvre encore treize semaines après la perte, la saison ne
    l'explique plus. Cette condition met aussi les exports glissants de Tisséo
    (35 jours) hors d'atteinte du contrôle par construction.

    Renvoie l'indice de la première date à écarter, ou `None`.
    """
    part_min = float(config.get("falaise_lignes_part_min", 0.04))
    plancher_lignes = int(config.get("falaise_lignes_min", 5))
    jours_apres_min = int(config.get("falaise_jours_apres_min", 91))
    fenetre_jours = int(config.get("falaise_fenetre_jours", 7))
    if part_min <= 0 or jours_apres_min <= 0:
        return None

    # Dernier jour de service de chaque ligne, dans les dates de l'export.
    derniere_par_ligne: dict[str, str] = {}
    for date in dates:
        for trip_id in index.trips_par_date.get(date, ()):
            ligne = index.trips.get(trip_id, {}).get("route_id", "")
            if ligne:
                derniere_par_ligne[ligne] = date
    if not derniere_par_ligne:
        return None

    # Les lignes qui s'arrêtent le dernier jour de l'export ne prouvent rien :
    # c'est l'export qui s'arrête, pas elles.
    fins: dict[str, int] = {}
    for ligne, fin in derniere_par_ligne.items():
        if fin != dates[-1]:
            fins[fin] = fins.get(fin, 0) + 1

    actives_max = max(index.lignes_par_date.values(), default=0)
    seuil = max(plancher_lignes, part_min * actives_max)

    for position, date in enumerate(dates):
        if len(dates) - 1 - position < jours_apres_min:
            break
        fenetre = dates[max(0, position - fenetre_jours + 1) : position + 1]
        perdues = {d: fins.get(d, 0) for d in fenetre if fins.get(d)}
        if sum(perdues.values()) < seuil:
            continue
        # La dernière journée d'une ligne perdue est encore complète ; c'est le
        # lendemain qui manque. On coupe donc juste après la plus PRÉCOCE des
        # pertes de la fenêtre.
        derniere_complete = min(perdues)
        indice = dates.index(derniere_complete) + 1
        journal(
            f"    {index.export.etiquette} : falaise de lignes le {derniere_complete} — "
            f"{sum(perdues.values())} ligne(s) cessent définitivement de rouler "
            f"(seuil {seuil:.1f} sur {actives_max} lignes actives au maximum) alors que "
            f"l'export couvre encore {len(dates) - 1 - position} jour(s) : "
            f"queue tronquée par ligne, pas fin de saison"
        )
        journal(
            f"[ALARME] {index.export.etiquette} : l'export cesse de décrire "
            f"{sum(perdues.values())} ligne(s) au {derniere_complete} et couvre pourtant "
            f"{len(dates) - 1 - position} jour(s) de plus — {len(dates) - indice} date(s) "
            f"écartée(s) ; un export publié après ce changement de service les rendrait réelles"
        )
        return indice
    return None


def fenetre_fiable(index: IndexExport, config: dict, journal=print) -> list[str]:
    """Dates de l'export à considérer comme complètes.

    Deux formes de troncature, et la coupe retient la plus précoce des deux.

    **Effondrement global** — deux seuils, et la coupe porte sur le plus long
    suffixe qui les enfreint :

      - relatif au type de jour : sous `ratio_lignes_min` fois le maximum de
        lignes atteint par ce type de jour dans l'export ;
      - absolu : sous `ratio_plancher_lignes` fois le maximum de l'export, tous
        types de jour confondus — le filet quand un type de jour n'apparaît
        jamais complet.

    **Falaise de lignes** — des lignes entières cessent d'être décrites alors
    que l'export couvre encore des mois : voir `_falaise_lignes`.

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

    # Seconde forme de troncature : la falaise de lignes. L'effondrement global
    # ci-dessus ne voit rien quand l'export décrit tout le réseau jusqu'au
    # prochain changement de service, puis ne prolonge que les lignes déjà
    # renseignées : le nombre de lignes actives reste haut (liO garde 94 % des
    # siennes au 14/12/2026) mais des lignes entières disparaissent pour
    # toujours. Voir `_falaise_lignes`.
    debut_falaise = _falaise_lignes(index, dates, config, journal)
    if debut_falaise is not None:
        debut_queue = min(debut_queue, debut_falaise)

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
