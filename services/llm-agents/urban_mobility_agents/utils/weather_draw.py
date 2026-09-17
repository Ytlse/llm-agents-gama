"""
Une date météo par agent — l'instrument qui rend l'effet météo mesurable.

POURQUOI
--------
Le ticket 023 a mesuré le bulletin météo enrichi « à pleine masse » et conclu à
aucun effet, sa grille notant « aucune conclusion sur la pluie, le Δ change de
signe entre substrats ». La cause est instrumentale, pas substantielle : **sur
une seule journée simulée, les 1 000 agents partagent une seule météo.** Le
régresseur a une variance nulle — aucun effet n'est détectable, quelle que soit
la vérité.

Ce module tire, pour chaque agent, un jour de l'année dans une fenêtre déclarée,
et ne substitue que la DATE du bulletin : l'heure de la journée est conservée
parce que le bulletin se lit par créneaux de 3 h (`weather_loader._reading_bucket`).
Tout le reste de la simulation — horaires GTFS, véhicules, itinéraires, agendas —
reste sur la journée simulée. C'est un dispositif *ceteris paribus* : seule la
météo bouge.

CE QUE ÇA LIBÈRE
----------------
Sur les 365 jours de `data/weather/meteo_toulouse_12_mois.csv` : température du
matin de −4 à +23 °C (écart-type 5,1) et 155 jours précipitants, dont 16 au-delà
de 5 mm. Sur la seule fenêtre de collecte de l'enquête (`2022-09-20 → 2023-02-18`,
jours ouvrés) : 109 journées exploitables.

L'ANNÉE EST IGNORÉE, ET C'EST VOULU
-----------------------------------
`weather_loader.get_weather` indexe par (mois, jour) : seul le jour de l'année
compte. On apparie donc la SAISON visée à la météo dont on dispose, pas les
journées historiques que les enquêtés ont vécues — une distribution saisonnière
correcte, pas une reconstitution.

DÉTERMINISME
------------
Le tirage est une fonction pure de `(graine, person_id)`. Deux runs identiques
produisent exactement les mêmes météos, comme la graine du tirage de mode. Il
n'utilise ni `random` global ni horloge.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
from pathlib import Path
from collections.abc import Sequence
from functools import lru_cache

from loguru import logger

from sim_clock import gama_timestamp, wall_clock

# Année de référence pour l'arithmétique des jours : bissextile, afin que le
# 29 février soit tirable quand la fenêtre le contient.
_ANNEE_PIVOT = 2024


def _jour_de_lannee(jour: dt.date) -> tuple[int, int]:
    return jour.month, jour.day


@lru_cache(maxsize=8)
def jours_eligibles(
    debut: str,
    fin: str,
    jours_semaine: tuple[int, ...] | None = None,
) -> tuple[tuple[int, int], ...]:
    """Jours (mois, jour) de la fenêtre, éventuellement filtrés par jour de semaine.

    `debut` et `fin` sont des dates ISO inclusives ; la fenêtre peut chevaucher le
    Nouvel An (l'enquête EMC² court du 20 septembre au 18 février). Le filtre par
    jour de semaine s'applique aux dates RÉELLES de la fenêtre — c'est là qu'un
    « jour ouvré » a un sens —, et seul le couple (mois, jour) est conservé,
    puisque c'est ce que le chargeur météo indexe.
    """
    premier = dt.date.fromisoformat(debut)
    dernier = dt.date.fromisoformat(fin)
    if dernier < premier:
        raise ValueError(f"fenêtre météo vide : {debut} → {fin}")

    autorises = set(jours_semaine) if jours_semaine else None
    sortie: list[tuple[int, int]] = []
    vus: set[tuple[int, int]] = set()
    jour = premier
    while jour <= dernier:
        if autorises is None or jour.isoweekday() in autorises:
            cle = _jour_de_lannee(jour)
            if cle not in vus:
                vus.add(cle)
                sortie.append(cle)
        jour += dt.timedelta(days=1)
    if not sortie:
        raise ValueError(
            f"aucun jour éligible dans {debut} → {fin} avec les jours de semaine {jours_semaine}"
        )
    return tuple(sortie)


def indice_agent(graine: int, person_id: str, cardinal: int) -> int:
    """Indice déterministe dans `[0, cardinal)`, tiré de (graine, agent).

    Un hachage plutôt que `random.Random(...).randrange` : le résultat ne dépend
    ni de la version de Python ni de l'ordre des appels, donc une trace archivée
    reste rejouable.
    """
    if cardinal <= 0:
        raise ValueError("cardinal nul")
    empreinte = hashlib.sha256(f"{graine}|{person_id}".encode()).digest()
    return int.from_bytes(empreinte[:8], "big") % cardinal


def date_meteo(
    person_id: str,
    graine: int,
    jours: Sequence[tuple[int, int]],
) -> tuple[int, int]:
    """Le (mois, jour) de DÉPART attribué à cet agent."""
    return tuple(jours[indice_agent(graine, person_id, len(jours))])


# ── Progression : la date tirée est un DÉPART, pas une assignation (ticket 075) ──────────
#
# Le tirage seul suffisait tant qu'un run tenait en une journée simulée. Sur soixante jours, il
# faisait relire soixante fois le même bulletin au même agent : aucune persistance d'épisode
# pluvieux, aucune saison, et une mémoire épisodique qui se construit sur une météo immobile.
# La date tirée devient donc le PREMIER jour, avancé d'un jour calendaire par jour simulé.
#
# ⚠ L'arithmétique se fait sur une année NON bissextile, et ce n'est pas un détail : la source
# (`data/weather/meteo_toulouse_12_mois.csv`) porte 365 jours et **aucun 29 février**. Compter
# sur une année bissextile ferait tomber une journée sur 366 dans un trou — `get_weather`
# rendrait `None` et le bulletin disparaîtrait du prompt sans qu'aucune ligne ne le dise.
_ANNEE_ARITHMETIQUE = 2023

# Le 29 février n'est signalé qu'une fois : il peut sortir du tirage de départ (la fenêtre
# « année » est décrite sur 2024, bissextile), et l'alarme doit se voir sans noyer le journal.
_29_FEVRIER_SIGNALE = False


def avancer_date(mois: int, jour: int, jours_ecoules: int) -> tuple[int, int]:
    """Le (mois, jour) situé `jours_ecoules` jours après `(mois, jour)`.

    L'année est ignorée par le chargeur météo : le 31 décembre est donc suivi du 1ᵉʳ janvier,
    sans rupture ni fin de fenêtre. Un 29 février en entrée — possible quand la fenêtre de
    tirage est décrite sur une année bissextile — est ramené au 1ᵉʳ mars, parce que la source
    ne le porte pas.
    """
    global _29_FEVRIER_SIGNALE
    if (mois, jour) == (2, 29):
        if not _29_FEVRIER_SIGNALE:
            _29_FEVRIER_SIGNALE = True
            logger.info(
                "[météo] 29 février tiré comme jour de départ : ramené au 1ᵉʳ mars — la "
                "source météo porte 365 jours et ne contient pas cette date."
            )
        mois, jour = 3, 1
    # L'avancement se fait sur le RANG dans l'année, pas par addition de jours à une date :
    # additionner ferait sortir de l'année arithmétique dès que la somme dépasse le 31 décembre,
    # et la date d'arrivée retomberait dans l'année suivante — bissextile une fois sur quatre.
    # Défaut trouvé par le test A5bis : `31 décembre + 60 jours` rendait le 29 février, que la
    # source ne porte pas. Le rang, lui, boucle sur 365 par construction.
    rang = dt.date(_ANNEE_ARITHMETIQUE, mois, jour).timetuple().tm_yday
    rang = (rang - 1 + int(jours_ecoules)) % 365
    arrivee = dt.date(_ANNEE_ARITHMETIQUE, 1, 1) + dt.timedelta(days=rang)
    return arrivee.month, arrivee.day


@lru_cache(maxsize=4)
def dates_declarees(fichier: str) -> dict[str, tuple[int, int]]:
    """`person_id → (mois, jour)` du jour décrit, lu une fois et gardé.

    Le fichier vit à côté de la population et porte des dates `AAAA-MM-JJ`. Seuls le mois et
    le jour comptent : `weather_loader.get_weather` indexe par (mois, jour), et l'année de nos
    relevés n'est pas celle de l'enquête. On apparie donc le BON JOUR CALENDAIRE dans l'année
    dont on dispose, ce qui reste un appariement saisonnier, pas la météo vécue.
    """
    import json

    brut = json.loads(Path(fichier).read_text(encoding="utf-8"))
    table: dict[str, tuple[int, int]] = {}
    for person_id, texte in brut.items():
        try:
            date = dt.date.fromisoformat(str(texte))
        except ValueError:
            continue
        table[str(person_id)] = (date.month, date.day)
    logger.info(
        f"[météo] dates déclarées chargées : {len(table)} personne(s) depuis {fichier}"
    )
    if len(table) < len(brut):
        logger.warning(
            f"[météo] {len(brut) - len(table)} date(s) illisible(s) dans {fichier} : "
            "ces personnes retombent sur le tirage par graine"
        )
    return table


def date_declaree(person_id: object, fichier: object) -> tuple[int, int] | None:
    """Le (mois, jour) décrit par cette personne, si la table en porte un.

    Défensive par contrat : ce chemin d'accès ne doit JAMAIS faire tomber le dispositif « une
    météo par agent ». Un réglage absent, d'un type inattendu ou pointant sur un fichier
    illisible rend `None`, et le tirage par graine reprend — ce qui est le comportement
    d'avant le ticket 058, pas une dégradation silencieuse d'autre chose.
    """
    if not isinstance(fichier, (str, os.PathLike)) or not str(fichier).strip():
        return None
    chemin = Path(fichier)
    if not chemin.is_file():
        logger.warning(
            f"[météo] table de dates déclarées introuvable ({chemin}) : tirage par graine"
        )
        return None
    try:
        return dates_declarees(str(chemin)).get(str(person_id))
    except Exception as err:  # pragma: no cover — garde-fou
        logger.error(
            f"[ALARME] table de dates déclarées illisible ({chemin} : {err}) — tirage par "
            "graine ; les bulletins ne sont PAS ceux des jours d'enquête"
        )
        return None


def timestamp_meteo(
    timestamp_simule: int,
    person_id: str,
    graine: int,
    jours: Sequence[tuple[int, int]],
    jours_ecoules: int = 0,
    date_imposee: tuple[int, int] | None = None,
) -> int:
    """Timestamp à passer à `get_weather` : la date de l'agent, l'heure du départ.

    `jours_ecoules` est le nombre de jours simulés écoulés depuis le début du run. À zéro — un
    run d'une seule journée, ou le premier jour d'un run long — la date rendue est **exactement**
    celle du tirage : une expérience déjà mesurée et scellée rejoue la même météo qu'avant le
    ticket 075. Au-delà, l'agent avance d'un jour calendaire par jour simulé.

    L'heure, la minute et la seconde de la journée simulée sont conservées : le
    bulletin est lu par créneaux de 3 h, et un départ à 08:00 doit continuer de
    lire le relevé de 06 h quelle que soit la date tirée. L'année utilisée est un
    pivot arbitraire, puisque `get_weather` n'en tient pas compte.

    ⚠ **Tout se passe en heure MURALE** (`sim_clock`), et c'est ce qui rend la
    substitution exacte. La version d'avant le 2026-09-04 relisait l'horodatage de
    GAMA dans `Europe/Paris` puis reconstruisait un instant par `.timestamp()` :
    l'heure de lecture partait déjà décalée d'une heure (deux en été), et la
    question de la bascule heure d'été/hiver — que la fenêtre 20/09 → 18/02
    traverse — n'existait que parce qu'on passait par des instants. L'horloge de
    GAMA ignore les bascules : en champs muraux, la conservation de l'heure est
    exacte par construction, sur toute la fenêtre.
    """
    mois, jour = date_imposee or date_meteo(person_id, graine, jours)
    if jours_ecoules:
        mois, jour = avancer_date(mois, jour, jours_ecoules)
    reference = wall_clock(timestamp_simule)
    substitue = reference.replace(year=_ANNEE_PIVOT, month=mois, day=jour)
    return gama_timestamp(substitue)
