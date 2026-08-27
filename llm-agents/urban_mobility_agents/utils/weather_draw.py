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
from functools import lru_cache
from typing import Optional, Sequence
from zoneinfo import ZoneInfo

# Même fuseau que `weather_loader.get_weather` : un décalage figé (`.astimezone()`
# sur un datetime naïf) reste correct pour la date d'origine mais se trompe d'une
# heure si la date tirée franchit la bascule heure d'été/hiver — la fenêtre de
# tirage (20/09 → 18/02) la traverse justement.
_TZ = ZoneInfo("Europe/Paris")

# Année de référence pour l'arithmétique des jours : bissextile, afin que le
# 29 février soit tirable quand la fenêtre le contient.
_ANNEE_PIVOT = 2024


def _jour_de_lannee(jour: dt.date) -> tuple[int, int]:
    return jour.month, jour.day


@lru_cache(maxsize=8)
def jours_eligibles(
    debut: str,
    fin: str,
    jours_semaine: Optional[tuple[int, ...]] = None,
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
    empreinte = hashlib.sha256(f"{graine}|{person_id}".encode("utf-8")).digest()
    return int.from_bytes(empreinte[:8], "big") % cardinal


def date_meteo(
    person_id: str,
    graine: int,
    jours: Sequence[tuple[int, int]],
) -> tuple[int, int]:
    """Le (mois, jour) attribué à cet agent."""
    return tuple(jours[indice_agent(graine, person_id, len(jours))])


def timestamp_meteo(
    timestamp_simule: int,
    person_id: str,
    graine: int,
    jours: Sequence[tuple[int, int]],
) -> int:
    """Timestamp à passer à `get_weather` : la date de l'agent, l'heure du départ.

    L'heure, la minute et la seconde de la journée simulée sont conservées : le
    bulletin est lu par créneaux de 3 h, et un départ à 08:00 doit continuer de
    lire le relevé de 06 h quelle que soit la date tirée. L'année utilisée est un
    pivot arbitraire, puisque `get_weather` n'en tient pas compte.
    """
    mois, jour = date_meteo(person_id, graine, jours)
    # `tz=_TZ` (Europe/Paris, un vrai fuseau à bascule) et non `.astimezone()` (offset
    # figé à la date d'origine) : `.timestamp()` recalcule l'offset UTC pour la date
    # SUBSTITUÉE, donc reste juste même quand le tirage franchit la bascule heure
    # d'été/hiver — comme le fait déjà `weather_loader.get_weather`.
    reference = dt.datetime.fromtimestamp(timestamp_simule, tz=_TZ)
    substitue = reference.replace(year=_ANNEE_PIVOT, month=mois, day=jour)
    return int(substitue.timestamp())
