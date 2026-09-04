"""L'horloge de la simulation : un horodatage GAMA est une heure MURALE locale.

`GAMA/CityTransport/models/Settings.gaml` démarre la journée simulée sur
`date([2026,3,16,5,0,0]) // Lundi 5h` et publie son horloge ainsi :

    date UTC_START_DATE  <- date([1970,1,1,0,0,0]);
    int  CURRENT_TIMESTAMP -> int(current_date - UTC_START_DATE);

C'est la différence de deux dates **naïves**. L'entier qui en sort n'est donc pas
un instant : c'est l'heure **murale** de la simulation, encodée comme si elle
était UTC. Pour lundi 16 mars 2026 5 h, il vaut **1773637200** (relevé dans la
colonne « Temps simulé » de `experiments/archive/2026-09-04_01_09/moves.csv`).

Le lire avec `datetime.fromtimestamp(ts)` — sans fuseau — le fait passer par le
fuseau du **processus**. Dans le conteneur `controller` (`TZ=Europe/Paris`), 5 h
murales devenaient **6 h**, et le fuseau du processus décidait donc de l'heure à
laquelle les agents voyaient le réseau. Mesuré sur les 2 580 points de la
population scellée v4 (`docs/traces/2026-09-04_13-15_fuseau_otp/`) : **235**
points sans itinéraire TC à l'heure demandée, **605** à l'heure que le modèle
croyait demander. Le biais n'est même pas constant — une heure en mars, **deux**
pour une journée simulée en été.

Ce module est le SEUL endroit qui traduit cet entier :

    wall_clock(ts)          -> datetime naïf portant les champs muraux de GAMA
    to_network_datetime(ts) -> le même instant, CONSCIENT du fuseau du réseau
    network_iso(ts)         -> sa forme ISO-8601 (ce qu'OTP attend en `dateTime`)
    gama_timestamp(dt)      -> l'inverse : d'un instant (ou d'une heure murale)
                               vers l'horodatage GAMA

⚠ Le fuseau est celui du **réseau simulé**, pas celui du processus : un conteneur
mal configuré ne doit pas déplacer les itinéraires. Il est lu dans les feeds GTFS
en service (`agency.txt`, colonne `agency_timezone`) — la même source qu'OTP
utilise pour interpréter ses horaires — et se surcharge par
`settings.gtfs.network_timezone`. Aucun repli codé en dur : sans source lisible,
la conversion REFUSE au lieu de rendre une heure plausible.
"""

from __future__ import annotations

import calendar
import csv
import io
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from loguru import logger

from settings import settings

__all__ = [
    "NetworkTimezoneError",
    "gama_timestamp",
    "network_iso",
    "network_timezone",
    "network_timezone_name",
    "reset_cache",
    "to_network_datetime",
    "wall_clock",
]


class NetworkTimezoneError(RuntimeError):
    """Le fuseau du réseau simulé n'a pas de source lisible.

    Volontairement fatal : deviner « Europe/Paris » ferait d'une donnée absente un
    résultat plausible, et c'est exactement le défaut que ce module corrige.
    """


# Fuseau résolu une fois (la lecture ouvre des fichiers), avec la trace de sa source.
_tz: Optional[ZoneInfo] = None
_tz_source: str = ""
# Anomalies de changement d'heure déjà signalées : (date murale, nature) — l'alarme
# se lève sur front montant, une journée simulée compte des milliers de trajets.
_dst_alarmed: set[tuple[str, str]] = set()


def reset_cache() -> None:
    """Oublie le fuseau résolu (tests : la configuration ou les feeds changent)."""
    global _tz, _tz_source
    _tz = None
    _tz_source = ""
    _dst_alarmed.clear()


# ── Le fuseau du réseau simulé ────────────────────────────────────────────────

def _agency_timezones() -> dict[str, str]:
    """`{nom du feed: agency_timezone}` pour les feeds GTFS en service.

    On énumère les feeds comme OTP le fait (`trip_helper.otp.feeds_en_service` :
    un répertoire ou un zip portant `stops.txt` au premier niveau du répertoire de
    build), et non le seul feed primaire — Tisséo, liO et le TER annuel roulent
    dans le même graphe depuis le 2026-09-04.
    """
    from trip_helper.otp import feeds_en_service  # import tardif : évite le cycle

    trouves: dict[str, str] = {}
    for feed in feeds_en_service(settings.gtfs.gtfs_file):
        feed = Path(feed)
        try:
            if feed.is_dir():
                agence = feed / "agency.txt"
                if not agence.exists():
                    continue
                flux = open(agence, encoding="utf-8-sig", newline="")
            else:
                archive = zipfile.ZipFile(feed)
                if "agency.txt" not in archive.namelist():
                    continue
                flux = io.TextIOWrapper(archive.open("agency.txt"), encoding="utf-8-sig", newline="")
            with flux:
                for ligne in csv.DictReader(flux):
                    valeur = (ligne.get("agency_timezone") or "").strip()
                    if valeur:
                        trouves[feed.name] = valeur
                        break
        except (OSError, zipfile.BadZipFile, csv.Error) as exc:
            logger.warning(f"[horloge] agency.txt illisible dans {feed.name} : {exc}")
    return trouves


def network_timezone_name() -> str:
    """Nom IANA du fuseau du réseau simulé, et d'où il vient.

    Ordre : le réglage explicite `gtfs.network_timezone`, puis l'`agency_timezone`
    des feeds en service. Deux feeds qui ne s'accordent pas, ou aucun feed lisible,
    lèvent `NetworkTimezoneError` : l'heure des itinéraires ne se devine pas.
    """
    global _tz_source

    surcharge = getattr(settings.gtfs, "network_timezone", None)
    if surcharge:
        _tz_source = f"réglage gtfs.network_timezone={surcharge}"
        return surcharge

    par_feed = _agency_timezones()
    distincts = sorted(set(par_feed.values()))
    if not distincts:
        logger.error(
            "[ALARME] [horloge] fuseau du réseau introuvable : aucun agency.txt lisible "
            f"à côté de {settings.gtfs.gtfs_file}. Les itinéraires ne peuvent pas être "
            "demandés à une heure inconnue — montez les feeds GTFS dans le service, ou "
            "posez explicitement `gtfs.network_timezone`.")
        raise NetworkTimezoneError(
            f"aucun agency_timezone lisible à côté de {settings.gtfs.gtfs_file} "
            "(réglez gtfs.network_timezone)")
    if len(distincts) > 1:
        logger.error(
            "[ALARME] [horloge] les feeds GTFS en service ne déclarent pas le même "
            f"fuseau : {par_feed}. En choisir un au hasard décalerait les horaires d'un "
            "réseau entier — posez explicitement `gtfs.network_timezone`.")
        raise NetworkTimezoneError(
            f"agency_timezone contradictoires entre feeds : {par_feed} "
            "(réglez gtfs.network_timezone)")

    _tz_source = ("agency.txt de " + ", ".join(f"{nom}={tz}" for nom, tz in sorted(par_feed.items())))
    return distincts[0]


def network_timezone() -> ZoneInfo:
    """Fuseau du réseau simulé (résolu une fois, journalisé avec sa source).

    Le succès se journalise, pas seulement l'échec : sans cette ligne, « l'horloge
    lit le fuseau du réseau » ne se distingue pas de « le module n'a jamais servi ».
    """
    global _tz
    if _tz is not None:
        return _tz
    nom = network_timezone_name()
    try:
        _tz = ZoneInfo(nom)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        logger.error(
            f"[ALARME] [horloge] fuseau « {nom} » inconnu de la base IANA ({exc}) — "
            f"source : {_tz_source}. Aucune heure n'est devinée à sa place.")
        raise NetworkTimezoneError(f"fuseau inconnu : {nom}") from exc
    logger.info(
        f"[horloge] fuseau du réseau simulé : {nom} (source : {_tz_source}) — "
        f"fuseau du processus : {os.environ.get('TZ', '(non posé)')}, qui n'entre "
        "dans aucune conversion")
    return _tz


# ── Les conversions ──────────────────────────────────────────────────────────

def wall_clock(timestamp: int | float) -> datetime:
    """Horodatage GAMA → datetime NAÏF portant l'heure murale de la simulation.

    `wall_clock(1773637200)` vaut `datetime(2026, 3, 16, 5, 0)` quel que soit le
    `TZ` du processus. À utiliser partout où seuls les CHAMPS comptent (heure de
    la table de congestion, jour de la semaine, date du jour simulé).
    """
    return datetime.fromtimestamp(int(timestamp), tz=timezone.utc).replace(tzinfo=None)


def _signale_bascule(mur: datetime, tz: ZoneInfo) -> None:
    """Alarme (front montant) quand l'heure murale n'existe pas ou existe deux fois.

    L'horloge de GAMA est une horloge murale sans changement d'heure : sa journée
    du dernier dimanche de mars compte 24 heures murales là où la réalité n'en a
    que 23. L'heure manquante et l'heure doublée sont des faits, pas des détails de
    conversion : elles se disent, et la conversion continue sur `fold=0` — un choix
    annoncé plutôt qu'un instant plausible produit en silence.
    """
    debut = mur.replace(tzinfo=tz)
    if debut.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None) != mur:
        cle = (mur.strftime("%Y-%m-%d"), "inexistante")
        if cle not in _dst_alarmed:
            _dst_alarmed.add(cle)
            logger.error(
                f"[ALARME] [horloge] l'heure murale {mur.isoformat()} n'existe pas en "
                f"{tz.key} (passage à l'heure d'été) : la journée simulée compte une "
                "heure que le réseau n'a pas. Conversion poursuivie sur l'heure d'hiver "
                "(fold=0) ; les itinéraires de cette tranche sont à lire avec prudence.")
        return
    if debut.utcoffset() != mur.replace(tzinfo=tz, fold=1).utcoffset():
        cle = (mur.strftime("%Y-%m-%d"), "ambigue")
        if cle not in _dst_alarmed:
            _dst_alarmed.add(cle)
            logger.error(
                f"[ALARME] [horloge] l'heure murale {mur.isoformat()} existe DEUX fois en "
                f"{tz.key} (retour à l'heure d'hiver) : la première occurrence est "
                "retenue (fold=0). Les horaires GTFS de cette tranche sont ambigus.")


def to_network_datetime(timestamp: int | float) -> datetime:
    """Horodatage GAMA → instant CONSCIENT du fuseau, dans le fuseau du réseau.

    `to_network_datetime(1773637200)` vaut `2026-03-16T05:00:00+01:00`, et
    `to_network_datetime(1783918800)` (5 h murales le 13 juillet) vaut
    `2026-07-13T05:00:00+02:00` : l'écart à l'ancienne lecture vaut une heure en
    hiver et deux en été.
    """
    tz = network_timezone()
    mur = wall_clock(timestamp)
    _signale_bascule(mur, tz)
    return mur.replace(tzinfo=tz)


def network_iso(timestamp: int | float) -> str:
    """Horodatage GAMA → ISO-8601 avec décalage, tel qu'OTP l'attend en `dateTime`.

    OTP est correct : il traduit l'instant reçu dans le fuseau de son réseau. Lui
    envoyer `05:00+00:00` pour 5 h murales lui faisait planifier **6 h locales**.
    """
    return to_network_datetime(timestamp).isoformat()


def gama_timestamp(moment: datetime) -> int:
    """Inverse de :func:`to_network_datetime` : un instant → l'horodatage GAMA.

    Sert des deux côtés de la frontière :

    - les instants qu'OTP RENVOIE (`2026-03-16T05:12:00+01:00`) doivent revenir
      dans l'horloge de GAMA, sinon `start_in` — l'écart entre le départ demandé et
      le départ du plan — se trompe d'une heure et l'agent voit des options qui
      « partent dans le passé » ;
    - le remappage `gtfs.fixed_day`, qui reconstruit un horodatage à partir d'une
      date fixe et de l'heure murale demandée.

    Un datetime naïf est lu comme une heure MURALE du réseau (c'est la seule
    lecture cohérente pour un horaire de transport) ; un datetime conscient du
    fuseau est d'abord ramené dans celui du réseau.
    """
    if moment.tzinfo is not None:
        moment = moment.astimezone(network_timezone()).replace(tzinfo=None)
    return int(calendar.timegm(moment.timetuple()))
