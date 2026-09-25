"""Le souvenir injecté a-t-il atteint la mémoire longue ? — ticket 106.

POURQUOI CE CONTRÔLE EXISTE
---------------------------
Le 2026-09-23, la campagne `e_c3_attribution_861500_v4` a injecté une panne de métro dans la
mémoire courte de 861500 le 27 mars à 14:02, jugée `grave` (0,75, RETENU 0,75). La consolidation
du soir a écrit : *« Today went very smoothly overall, with all my trips adhering closely to
schedule »*, importance 0,10. Sur les 123 documents de mémoire longue du run, **aucun** ne parle
de métro, d'éclairage, d'annonce ni de rame. Le choc n'a jamais existé pour l'agent, et rien ne
l'a dit — le run a tourné 2 h 22 de plus.

Cause mécanique : le texte de l'événement est JOINT à l'observation d'arrivée (ticket 100), et
cette arrivée disait `On time.` — l'agent est arrivé 199 s en avance sur son horaire attendu,
parce que `retard_injecte_s` ne remonte qu'au `GamaArrivalsLogger`. La consolidation a résumé
une journée dont la ligne dominante était « tout s'est bien passé ».

CE QUE CE MODULE FAIT, ET CE QU'IL NE FAIT PAS
----------------------------------------------
Il **constate et alarme**. Il n'arrête rien. C'est délibéré, et la raison est mesurée : sur les
15 runs archivés portant une injection, **14 gardent le choc et 1 le perd** (7 %). Le défaut est
donc rare, alors que le témoin, lui, est heuristique — une paraphrase légitime (« the underground »
pour « metro ») produirait un faux positif. Arrêter un run sur ce témoin-là, c'est risquer de
tuer un bon run pour attraper un cas sur quinze. On apprend d'abord son taux de fausses alarmes
sur des runs réels ; brancher l'arrêt ensuite est une ligne à changer, pas un chantier.

C'est le geste du ticket 105 à un cran de moins, parce que la certitude n'est pas la même.

POURQUOI LES MOTS, ET PAS L'IMPORTANCE
--------------------------------------
Le témoin évident — « la consolidation a-t-elle produit une entrée d'importance comparable à
l'importance retenue ? » — a été mesuré et **rejeté** : le run `11_10`, qui garde parfaitement le
choc, plafonne à 0,10 en mémoire longue, plus bas que le run `13_54` qui le perd (0,15). Sur 13
runs lisibles, 7 ont une importance maximale inférieure à l'importance retenue. L'importance de
la mémoire courte ne se propage pas : la consolidation est une réflexion de synthèse, pas une
copie, et aucun identifiant ne relie l'entrée courte à la réflexion longue. Restent les mots.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Sequence

from loguru import logger

from llm.evenements.injection import PREFIXE_LU, PREFIXE_VECU

PREFIXES = (PREFIXE_VECU, PREFIXE_LU)

# Longueur minimale d'un mot retenu. En dessous, ce sont des articles, des prépositions et des
# nombres écrits en chiffres — aucun ne distingue un texte d'un autre.
LONGUEUR_MIN = 4

# ── La liste d'exclusion, et pourquoi chaque famille y est ───────────────────────────────
#
# Un mot BANAL DANS CE DOMAINE retrouvé dans une réflexion ne prouve rien : tous les agents de
# tous les runs écrivent « trip », « minutes », « late ». Le 2026-09-23, le run `09_31` a
# d'abord été compté comme AYANT PERDU son choc, puis comme l'ayant gardé : la première lecture
# faisait correspondre « incident » à la phrase *« without any unexpected incidents »*, qui dit
# exactement le contraire. Un témoin qui se déclenche sur la négation de ce qu'il cherche est
# pire qu'aucun témoin.
#
# La règle d'admission dans cette liste : le mot apparaîtrait-il dans la réflexion d'un jour
# ORDINAIRE ? Si oui, il sort.
BANALITES = frozenset(
    {
        # Vocabulaire quotidien de la mobilité — présent dans toute réflexion, choc ou non.
        "trip", "trips", "travel", "travelled", "travelling", "travels", "journey",
        "journeys", "route", "routes", "commute", "commuted", "commuting",
        "arrive", "arrived", "arrives", "arrival", "depart", "departed", "departure",
        "leave", "left", "went", "took", "taken", "take", "taking", "board", "boarded",
        "walk", "walked", "walking", "ride", "rode", "riding",
        # Le temps et le retard : toute réflexion en parle, y compris pour dire que tout
        # allait bien. « late », « delay » et « minutes » sont les trois faux amis du témoin.
        "time", "times", "late", "later", "delay", "delays", "delayed", "early",
        "minute", "minutes", "hour", "hours", "morning", "afternoon", "evening",
        "today", "day", "days", "week", "month", "schedule", "scheduled", "planned",
        # Les modes et les lieux : ils NOMMENT le trajet, ils ne qualifient pas l'incident.
        "line", "lines", "station", "stations", "stop", "stops", "stopped", "service",
        "services", "train", "trains", "metro", "bus", "buses", "tram", "car", "bike",
        "home", "work", "city", "centre", "center",
        # Les mots d'appréciation généraux. « incident » est ici POUR la raison ci-dessus.
        "incident", "incidents", "problem", "problems", "issue", "issues",
        "usual", "usually", "normal", "again", "than", "that", "this", "with", "from",
        "have", "were", "was", "been", "being", "which", "when", "what", "where",
        "very", "much", "more", "most", "some", "they", "them", "there", "their",
        "then", "over", "into", "also", "just", "made", "make", "about", "after",
        # « between » a été ajouté le 2026-09-23 en calibrant : c'est le SEUL mot que le run
        # v4 retrouvait dans une phrase sans rapport (« between errands »), et il suffisait à
        # le faire passer pour un run sain. Un mot de liaison n'est jamais distinctif.
        "between", "among", "along", "around", "through", "while", "during",
        "before", "could", "would", "should", "will", "able", "back", "down", "well",
        "good", "fine", "nice", "only", "other", "same", "each", "both",
    }
)

_MOT = re.compile(r"[a-zA-Z]+")


@dataclass
class Constat:
    """Ce qu'une consolidation a fait du souvenir injecté."""

    person_id: str
    sim_ts: int
    evenement_id: str
    mots_cherches: list[str] = field(default_factory=list)
    mots_retrouves: list[str] = field(default_factory=list)
    seuil: int = 2

    @property
    def retrouve(self) -> bool:
        return len(self.mots_retrouves) >= self.seuil

    @property
    def verdict(self) -> str:
        return "retrouvé" if self.retrouve else "PERDU"


def texte_injecte(contenus: Iterable[str]) -> str | None:
    """Le texte de l'événement parmi les entrées courtes que la consolidation consomme.

    Rend `None` — le cas de l'immense majorité des consolidations — quand aucune entrée ne porte
    un préfixe d'injection. L'ancrage est le PRÉFIXE et non le registre : l'entrée porte déjà le
    texte, et le faire redescendre du contrôleur ajouterait un chemin qui peut diverger.
    """
    for contenu in contenus:
        if not contenu:
            continue
        for prefixe in PREFIXES:
            position = contenu.find(prefixe)
            if position != -1:
                return contenu[position + len(prefixe) :].strip()
    return None


def mots_distinctifs(texte: str) -> list[str]:
    """Les mots de ce texte qui ne pourraient pas venir d'une journée ordinaire.

    L'ordre d'apparition est conservé : une alarme qui les nomme se relit dans l'ordre du texte
    injecté, ce qui permet de reconnaître la phrase d'un coup d'œil.
    """
    vus: list[str] = []
    connus: set[str] = set()
    for brut in _MOT.findall(texte or ""):
        mot = brut.lower()
        if len(mot) < LONGUEUR_MIN or mot in BANALITES or mot in connus:
            continue
        connus.add(mot)
        vus.append(mot)
    return vus


def mots_retrouves(mots: Sequence[str], textes: Iterable[str]) -> list[str]:
    """Ceux de `mots` qui figurent dans ce que la consolidation a écrit.

    La comparaison se fait sur des MOTS ENTIERS, jamais sur des sous-chaînes : « announce »
    dans « announcement » se reconnaît par la racine partagée ci-dessous, mais « rain » ne doit
    pas se reconnaître dans « train ». Une correspondance par sous-chaîne produisait exactement
    ce genre de faux positif silencieux.
    """
    presents: set[str] = set()
    for texte in textes:
        for brut in _MOT.findall(texte or ""):
            presents.add(brut.lower())
    trouves = []
    for mot in mots:
        if mot in presents:
            trouves.append(mot)
            continue
        # Tolérance de flexion : « announcement » couvre « announcements » et « announced ».
        # Cinq caractères de racine commune — assez pour ne pas confondre deux mots du corpus,
        # assez peu pour suivre un pluriel ou un participe.
        if len(mot) > 5 and any(_meme_racine(mot, p) for p in presents):
            trouves.append(mot)
    return trouves


def _meme_racine(mot: str, autre: str) -> bool:
    """Cinq caractères de racine commune, les deux mots faisant plus de cinq caractères."""
    return len(autre) > 5 and (mot[:5] == autre[:5])


def _evenement_declare() -> str:
    """L'identifiant de l'événement déclaré par le run, ou `""` si rien n'est déclaré.

    L'appelant est la consolidation du soir, qui ne sait pas quel événement a été joint à une
    arrivée du matin : l'identifiant ne vit que dans le registre, et le texte de l'entrée
    courte ne le porte pas. Un run ne déclare qu'UN événement (`evenement.yaml`, clé
    `evenement`), éventuellement sur plusieurs jours — la lecture est donc exacte tant que
    cette forme tient. Le jour où un run en déclarera deux, il faudra que le site d'appel
    passe `evenement_id` explicitement, et ce repli deviendra faux.

    Ne lève jamais : sans identifiant, la trace reste lisible, elle nomme juste moins.
    """
    try:
        from llm import evenements as evenements_module

        registre = evenements_module.registre()
        if registre is None:
            return ""
        return str(registre.evenement.evenement_id or "")
    except Exception:  # pragma: no cover - le témoin ne casse jamais son appelant
        return ""


def controler(
    *,
    person_id: str,
    sim_ts: int,
    contenus_courts: Iterable[str],
    textes_longs: Iterable[str],
    seuil: int,
    evenement_id: str = "",
) -> Constat | None:
    """Le contrôle complet. Rend `None` quand cette consolidation ne suit aucune injection.

    Ne lève JAMAIS : un témoin qui ferait tomber une consolidation coûterait plus cher que le
    défaut qu'il surveille.
    """
    try:
        from urban_mobility_agents.utils.reprise import gel_actif

        if gel_actif():
            # Un rejeu ne décide rien et n'écrit rien : la consolidation qu'il traverse a déjà
            # été contrôlée au premier passage. La contrôler deux fois doublerait la trace et
            # fausserait le taux de fausses alarmes qu'on cherche justement à mesurer.
            return None
        texte = texte_injecte(contenus_courts)
        if texte is None:
            return None
        mots = mots_distinctifs(texte)
        if not mots:
            # Un texte sans aucun mot distinctif ne se cherche pas. Ce n'est pas un échec du
            # souvenir, c'est un texte que ce témoin ne sait pas suivre — et le dire évite de
            # compter une alarme qui n'en est pas une.
            logger.warning(
                f"[temoin] aucun mot distinctif dans le texte injecté à {person_id} — "
                f"le témoin ne peut rien conclure sur cette consolidation."
            )
            return None
        constat = Constat(
            person_id=str(person_id),
            sim_ts=int(sim_ts),
            evenement_id=str(evenement_id or _evenement_declare()),
            mots_cherches=mots,
            mots_retrouves=mots_retrouves(mots, textes_longs),
            seuil=int(seuil),
        )
        _journaliser(constat)
        _tracer(constat)
        return constat
    except Exception as err:  # noqa: BLE001 — jamais vers l'appelant
        logger.warning(f"[temoin] contrôle impossible pour {person_id} ({err})")
        return None


def _journaliser(constat: Constat) -> None:
    """Le succès se dit AUSSI : un témoin muet ne distingue pas « ça marche » de « ça ne tourne plus »."""
    cherches = ", ".join(constat.mots_cherches[:8])
    retrouves = ", ".join(constat.mots_retrouves) or "aucun"
    if constat.retrouve:
        logger.info(
            f"[temoin] souvenir injecté RETROUVÉ en mémoire longue | "
            f"agent={constat.person_id} evenement={constat.evenement_id or '?'} "
            f"mots={retrouves} (seuil {constat.seuil})"
        )
        return
    logger.error(
        f"[ALARME] [temoin] le souvenir injecté n'a PAS atteint la mémoire longue | "
        f"agent={constat.person_id} evenement={constat.evenement_id or '?'} "
        f"retrouvés={retrouves} sur seuil={constat.seuil} | cherchés={cherches} — "
        f"la consolidation qui suit l'injection n'en garde pas la trace : les jours suivants "
        f"ne mesurent PAS l'effet d'un souvenir, et ce bras est inexploitable tel quel."
    )


def _tracer(constat: Constat) -> None:
    """Une ligne JSONL par contrôle, lue par `make report`.

    Écrit à part du journal applicatif parce qu'un taux de fausses alarmes se compte sur des
    runs, pas sur un `grep` — et c'est précisément ce que ce témoin doit apprendre avant qu'on
    envisage de lui faire arrêter quoi que ce soit.
    """
    try:
        from settings import _run_artifacts_disabled, settings

        if _run_artifacts_disabled():
            return
        entree = {
            "sim_ts": constat.sim_ts,
            "sim_day": datetime.fromtimestamp(constat.sim_ts, tz=timezone.utc).strftime(
                "%Y-%m-%d"
            ),
            "person_id": constat.person_id,
            "evenement_id": constat.evenement_id,
            "retrouve": constat.retrouve,
            "seuil": constat.seuil,
            "mots_cherches": constat.mots_cherches,
            "mots_retrouves": constat.mots_retrouves,
        }
        with open(settings.app.temoin_souvenir_file, "a", encoding="utf-8") as flux:
            flux.write(json.dumps(entree, ensure_ascii=False, default=str) + "\n")
    except Exception as err:  # noqa: BLE001
        logger.warning(f"[temoin] trace non écrite pour {constat.person_id} ({err})")
