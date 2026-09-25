"""Le souvenir d'un événement est-il SERVI aux décisions qui suivent ? — analyse du 2026-09-25.

CE QUI NE MARCHAIT PAS
----------------------
`evenement_par_jour.csv` répondait par deux colonnes, `souvenir_choc_servi` et
`decisions_avec_souvenir_choc`, et elles valaient 0 sur le bras traité `2026-09-24_17_50` alors
que six prompts de décision portaient l'article a09 : 286923 le 27 mars à 12 h 40, 14 h 21 et
17 h 36, 286920 les 30 et 31 mars à 5 h 57, 286921 le 30 mars à 13 h 38. Trois raisons, qui
s'additionnaient :

1. **Le lien cherché était littéral.** Les soixante premiers caractères du texte injecté, dans la
   mémoire longue. La consolidation REFORMULE : « Toulouse closed its parks and gardens from
   6 p.m. due to a yellow storm warning » ne contient pas le début de l'article.
2. **« Servi » se lisait dans `trace_rappel`**, qui compte ce que la recherche a remonté et non
   ce que le prompt contient : quand le noyau est présent, seules les deux ou trois épisodiques
   les plus récentes sont gardées, et le noyau lui-même (« Ce que je sais », « Ce qui a changé
   récemment ») n'y figure pas.
3. **Le jour même seulement.** Un article lu au réveil pèse, s'il pèse, les jours suivants.

CE QUE CE MODULE MESURE À LA PLACE
----------------------------------
Il lit la section `**History:**` de chaque prompt de décision — ce que le modèle a lu, ni plus
ni moins — et y cherche l'événement de deux façons :

- **texte** : l'article lui-même, espaces normalisés (l'entrée `[ PRESSE ]` de la mémoire, la
  ligne garantie du ticket 111, ou ce qu'un membre du foyer en a dit mot pour mot) ;
- **mots** : une reformulation — au moins `MOTS_MIN` racines distinctes (cinq caractères) parmi
  les mots distinctifs de l'article (`llm.evenements.temoin.mots_distinctifs`, le détecteur que
  la consolidation utilise déjà), **privés de tout mot que le foyer avait écrit en mémoire avant
  la lecture**. Sans ce filtre, « weather » ou « warning » suffiraient à faire d'une journée de
  pluie un souvenir de l'article. Mesuré le 2026-09-25 : 7 documents dérivés sur le bras
  traité, 0 sur 51 au témoin `2026-09-24_23_06`.

Le suivi couvre **tout le foyer** du lecteur, du jour de la lecture (J0) à la fin du run : le
lecteur (`expose`) et ses co-résidents, informés par le relais du ticket 111 ou non.

Il dit aussi PAR OÙ le souvenir est entré : « Ce que je sais » (un concept), « Ce qui a changé
récemment » (un choc, ou la ligne GARANTIE du ticket 111 — cinq jours de trajet, qui n'est donc
pas un souvenir spontané) ou les épisodiques rappelées. C'est ce qui sépare « le mécanisme a
servi l'article » de « l'agent s'en est souvenu ».

⚠ **Une décision tirée du cache n'a pas de prompt.** Elle ne se compte ni avec ni sans
souvenir : `decisions_sans_prompt` la montre, pour qu'un jour sans prompt ne se lise pas comme
un jour sans souvenir.

⚠ **Continuité.** Rien ici ne dépend de l'état final de la mémoire, sauf le vocabulaire d'avant
J0, figé dès J0 : une ligne d'un jour passé ne bouge pas quand le run avance. Le relevé des
documents dérivés (`souvenirs_derives.csv`), lui, est une PHOTOGRAPHIE de la mémoire longue au
moment du calcul — un concept fusionné plus tard en disparaît. Il n'entre donc pas dans la
vérification de continuité.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from scripts.analysis.memoire.sources import BlocPrompt, blocs_itineraires, lire_echanges, lire_ltm
from scripts.analysis.mesures import calendrier

RACINE = Path(__file__).resolve().parents[3]
if str(RACINE / "services" / "llm-agents") not in sys.path:
    sys.path.insert(0, str(RACINE / "services" / "llm-agents"))

from llm.evenements import temoin  # noqa: E402  (après l'ajout au chemin)

# Racines distinctes exigées pour reconnaître une reformulation. ⚠ PLUS que le témoin de la
# consolidation (`temoin_souvenir_mots_min`, 2), et c'est mesuré : le témoin compare le texte
# injecté à ce que la consolidation écrit JUSTE après ; ici on balaie toute la mémoire servie
# des jours suivants, et deux mots rares s'y rencontrent par hasard. Sur le bras traité du
# 2026-09-24_17_50, le seuil 2 prenait pour un souvenir de l'article « a quick shopping trip »
# à Compans (la station de métro, homonyme du jardin Compans-Caffarelli) qui « remained »
# pluvieux ; tous les vrais souvenirs y portent 3 racines ou plus.
MOTS_MIN = 3
LONGUEUR_RACINE = 5
# La mention de traduction exigée par le contrat du texte n'est pas l'article.
MOTS_DE_LA_MENTION = frozenset({"translated", "french"})
# Les noms de jours et de mois ne distinguent rien : le gabarit préfixe CHAQUE épisodique
# rappelée de sa date (« [Thursday, March 26] »), et l'article a09 dit « this Thursday ». Sans
# ce filtre, toute réflexion d'un jeudi portait déjà une racine de l'article.
CALENDRIER = frozenset({
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "june", "july", "august", "september",
    "october", "november", "december",
})
_MENTION = re.compile(r"^\s*\((?:translated|traduit)[^)]*\)\s*", re.IGNORECASE)
LONGUEUR_EXTRAIT = 60

SECTIONS = {
    "Mes habitudes": "habitudes",
    "Ce que je sais": "connaissances",
    "Ce qui a changé récemment": "changements",
}
VOIES = ("connaissances", "changements", "rappel")


@dataclass(frozen=True)
class Signature:
    """Ce qui reconnaît un événement dans un texte : un extrait littéral et des mots."""

    evenement_id: str
    extrait: str
    mots: tuple[str, ...]

    def reconnait(self, texte: str) -> str | None:
        """`"texte"`, `"mots"` ou `None`."""
        normal = _normaliser(texte)
        if self.extrait and self.extrait in normal:
            return "texte"
        if len(racines(temoin.mots_retrouves(self.mots, [texte]))) >= MOTS_MIN:
            return "mots"
        return None


def racines(mots: Sequence[str]) -> set[str]:
    """Cinq caractères, sans le pluriel : « park » et « parks » sont UN mot de l'article."""
    return {m[:LONGUEUR_RACINE].removesuffix("s") for m in mots}


@dataclass(frozen=True)
class Suivi:
    """Un membre d'un foyer exposé, suivi à partir du jour de la lecture."""

    evenement_id: str
    person_id: str
    household_id: str | None
    role: str          # « expose » | « co_resident »
    informe: bool      # ticket 111 : une ligne `origine: entendu` le concerne
    j0: str
    # L'instant de la première lecture dans le foyer : le vocabulaire « d'avant » s'arrête là.
    # ⚠ Pas la journée : un article lu à 00 h 00 est, à la frontière de 3 h, dans la journée de
    # la veille — et son entrée `[ PRESSE ]` aurait versé tous ses mots dans le vocabulaire
    # antérieur, vidant la signature.
    instant: str
    signature: Signature


@dataclass(frozen=True)
class LigneSouvenir:
    jour_simule: int
    date_simulee: str
    person_id: str
    evenement_id: str
    role: str
    informe: bool
    jours_depuis_j0: int
    decisions: int
    prompts: int
    decisions_sans_prompt: int
    prompts_avec_souvenir: int
    souvenir_texte: int
    souvenir_mots: int
    via_connaissances: int
    via_changements: int
    via_rappel: int


@dataclass(frozen=True)
class SouvenirDerive:
    evenement_id: str
    person_id: str
    role: str
    doc_id: str
    type_souvenir: str
    ecrit_le: str
    appariement: str
    mots_retrouves: str
    enonce: str


# ── Signature d'un événement ──────────────────────────────────────────────────────────


def _normaliser(texte: str) -> str:
    return re.sub(r"\s+", " ", texte or "").strip().lower()


def _sans_mention(texte: str) -> str:
    return _MENTION.sub("", texte or "", count=1)


def _vocabulaire(textes: Sequence[str]) -> set[str]:
    return {m.lower() for t in textes for m in temoin._MOT.findall(t or "")}


def signature(evenement_id: str, texte: str, vocabulaire_anterieur: set[str]) -> Signature:
    """Extrait et mots distinctifs de l'article, privés du vocabulaire que le foyer avait déjà."""
    corps = _sans_mention(texte)
    mots = tuple(
        m for m in temoin.mots_distinctifs(corps)
        if m not in MOTS_DE_LA_MENTION and m not in CALENDRIER
        and m not in vocabulaire_anterieur
    )
    return Signature(evenement_id, _normaliser(corps)[:LONGUEUR_EXTRAIT], mots)


# ── Qui suivre, à partir de quand ─────────────────────────────────────────────────────


def suivis(chemin_run: Path, evenements: Sequence[dict],
           journee_de: Any) -> list[Suivi]:
    """Les membres des foyers exposés, avec J0 et la signature de l'événement pour ce foyer.

    `journee_de(evenement)` rend la journée simulée d'une exposition (celle d'`evenement_par_jour`).
    """
    menages = calendrier.menages(chemin_run)
    informes = {
        (str(e.get("evenement_id") or e.get("choc_id") or ""), str(e.get("person_id")))
        for e in evenements if e.get("origine") == "entendu"
    }
    # (événement, foyer) → J0, lecteurs et texte. Un agent hors de toute population connue
    # forme son propre foyer : on le suit seul plutôt que de ne pas le suivre.
    foyers: dict[tuple[str, str], dict[str, Any]] = {}
    for e in evenements:
        if e.get("origine") == "entendu":
            continue
        agent = str(e.get("person_id") or "")
        identifiant = str(e.get("evenement_id") or e.get("choc_id") or "")
        journee = journee_de(e)
        texte = str(e.get("vecu") or "").strip()
        if not (agent and identifiant and journee and texte):
            continue
        foyer = menages.get(agent) or f"seul:{agent}"
        instant = _instant(e.get("horodatage_simule"))
        courant = foyers.setdefault((identifiant, foyer), {"j0": journee, "lecteurs": set(),
                                                           "texte": texte, "instant": instant})
        courant["j0"] = min(courant["j0"], journee)
        courant["instant"] = min(courant["instant"], instant)
        courant["lecteurs"].add(agent)
    if not foyers:
        return []

    entrees, _ = lire_ltm(chemin_run)
    resultat: list[Suivi] = []
    for (identifiant, foyer), info in sorted(foyers.items()):
        membres = (
            sorted(p for p, h in menages.items() if h == foyer)
            if not foyer.startswith("seul:") else [foyer.split(":", 1)[1]]
        )
        anterieur = _vocabulaire([
            x.contenu for p in membres for x in entrees.get(p, [])
            if _instant(x.timestamp) and _instant(x.timestamp) < info["instant"]
        ])
        sig = signature(identifiant, info["texte"], anterieur)
        for p in membres:
            resultat.append(Suivi(
                evenement_id=identifiant, person_id=p,
                household_id=None if foyer.startswith("seul:") else foyer,
                role="expose" if p in info["lecteurs"] else "co_resident",
                informe=(identifiant, p) in informes, j0=info["j0"],
                instant=info["instant"], signature=sig,
            ))
    return resultat


def _instant(horodatage: Any) -> str:
    """« AAAA-MM-JJTHH:MM:SS », comparable comme une chaîne. Vide si illisible."""
    texte = str(horodatage or "").strip().replace(" ", "T")[:19]
    return texte if len(texte) >= 10 else ""


def _journee_ltm(horodatage: str) -> str:
    from scripts.analysis.mesures.calcul import journee_du_moment

    return journee_du_moment(horodatage) or ""


# ── Ce que les prompts contenaient ────────────────────────────────────────────────────


def elements_d_historique(historique: str) -> list[tuple[str, str]]:
    """(voie, texte) pour chaque élément de la section History, continuation comprise.

    Le gabarit rend chaque entrée « - <entrée> » ; les titres du noyau sont des entrées nues,
    leurs lignes des entrées « - - … ». Une entrée longue (l'article, sur plusieurs
    paragraphes) se prolonge sur les lignes qui ne commencent pas par « - ».
    """
    elements: list[list[str]] = []
    voie = "rappel"
    for ligne in (historique or "").splitlines():
        if ligne.startswith("- "):
            corps = ligne[2:]
            titre = SECTIONS.get(corps.strip())
            if titre:
                voie = titre
                continue
            if not corps.startswith("- "):
                # Une entrée de premier niveau hors noyau : une épisodique rappelée.
                voie = "rappel"
            elements.append([voie, corps])
        elif elements and ligne.strip():
            elements[-1][1] += "\n" + ligne
    return [(v, t) for v, t in elements]


def _journee_du_bloc(bloc: BlocPrompt) -> str | None:
    from scripts.analysis.mesures.calcul import journee_du_moment

    if not bloc.jour or bloc.depart_minutes is None:
        return None
    heures, minutes = divmod(bloc.depart_minutes, 60)
    return journee_du_moment(f"{bloc.jour} {heures:02d}:{minutes:02d}:00")


def _blocs_uniques(chemin_run: Path) -> list[BlocPrompt] | None:
    """Un bloc par décision. `None` quand le run n'a pas de journal d'échanges."""
    if not (chemin_run / "llm_exchanges.jsonl").is_file():
        return None
    uniques: dict[tuple, BlocPrompt] = {}
    for bloc in blocs_itineraires(lire_echanges(chemin_run)):
        # Le rejeu d'une reprise redemande la même décision : la dernière demande est celle
        # dont la réponse reste dans `moves.csv`.
        uniques[(bloc.agent, bloc.jour, bloc.depart_minutes, bloc.motif)] = bloc
    return list(uniques.values())


# ── Assemblage ────────────────────────────────────────────────────────────────────────


@dataclass
class Souvenirs:
    lignes: list[LigneSouvenir]
    derives: list[SouvenirDerive]
    # (journée, agent, événement) → appariement du jour, pour `evenement_par_jour.csv`.
    du_jour: dict[tuple[str, str, str], tuple[int, int, str]]
    journal_present: bool


def mesurer(chemin_run: Path, evenements: Sequence[dict], journees: Sequence[Any],
            decisions_par_jour: dict[tuple[str, str], int], journee_de: Any) -> Souvenirs:
    chemin_run = Path(chemin_run)
    liste = suivis(chemin_run, evenements, journee_de)
    blocs = _blocs_uniques(chemin_run)
    if not liste:
        return Souvenirs([], [], {}, blocs is not None)

    par_agent_jour: dict[tuple[str, str], list[BlocPrompt]] = {}
    for bloc in blocs or []:
        journee = _journee_du_bloc(bloc)
        if journee:
            par_agent_jour.setdefault((bloc.agent, journee), []).append(bloc)

    index = {j.date: j.index for j in journees}
    lignes: list[LigneSouvenir] = []
    du_jour: dict[tuple[str, str, str], tuple[int, int, str]] = {}
    for suivi in liste:
        j0_index = _rang(suivi.j0, journees)
        for journee in journees:
            if journee.date < suivi.j0:
                continue
            prompts = par_agent_jour.get((suivi.person_id, journee.date), [])
            voies: Counter = Counter()
            avec = texte = mots = 0
            for bloc in prompts:
                trouve: dict[str, str] = {}
                for voie, contenu in elements_d_historique(bloc.historique):
                    appariement = suivi.signature.reconnait(contenu)
                    if appariement and (voie not in trouve or appariement == "texte"):
                        trouve[voie] = appariement
                if not trouve:
                    continue
                avec += 1
                texte += "texte" in trouve.values()
                mots += "texte" not in trouve.values()
                for voie in trouve:
                    voies[voie] += 1
            decisions = decisions_par_jour.get((journee.date, suivi.person_id), 0)
            lignes.append(LigneSouvenir(
                jour_simule=journee.index, date_simulee=journee.date,
                person_id=suivi.person_id, evenement_id=suivi.evenement_id,
                role=suivi.role, informe=suivi.informe,
                jours_depuis_j0=journee.index - j0_index if j0_index is not None else None,
                decisions=decisions, prompts=len(prompts),
                decisions_sans_prompt=max(0, decisions - len(prompts)),
                prompts_avec_souvenir=avec, souvenir_texte=texte, souvenir_mots=mots,
                via_connaissances=voies["connaissances"], via_changements=voies["changements"],
                via_rappel=voies["rappel"],
            ))
            du_jour[(journee.date, suivi.person_id, suivi.evenement_id)] = (
                len(prompts), avec, "texte" if texte else ("mots" if mots else ""))
        # Le jour de la lecture peut n'avoir aucun trajet : il n'a pas de journée vécue, mais
        # son appariement reste demandé par `evenement_par_jour.csv`.
        if suivi.j0 not in index:
            prompts = par_agent_jour.get((suivi.person_id, suivi.j0), [])
            du_jour.setdefault((suivi.j0, suivi.person_id, suivi.evenement_id),
                               (len(prompts), 0, ""))

    return Souvenirs(
        lignes=sorted(lignes, key=lambda l: (l.jour_simule, l.evenement_id,
                                             _cle(l.person_id))),
        derives=_derives(chemin_run, liste),
        du_jour=du_jour,
        journal_present=blocs is not None,
    )


def _rang(date_iso: str, journees: Sequence[Any]) -> int | None:
    from scripts.analysis.mesures.calcul import _indice_calendaire

    return _indice_calendaire(date_iso, journees)


def _derives(chemin_run: Path, liste: Sequence[Suivi]) -> list[SouvenirDerive]:
    """Les documents de la mémoire longue qui portent l'événement — photographie, pour l'audit."""
    entrees, _ = lire_ltm(chemin_run)
    derives = []
    for suivi in liste:
        for x in entrees.get(suivi.person_id, []):
            if not _instant(x.timestamp) or _instant(x.timestamp) < suivi.instant:
                continue
            appariement = suivi.signature.reconnait(x.contenu)
            if not appariement:
                continue
            derives.append(SouvenirDerive(
                evenement_id=suivi.evenement_id, person_id=suivi.person_id, role=suivi.role,
                doc_id=x.doc_id, type_souvenir=x.memory_type,
                ecrit_le=_instant(x.timestamp), appariement=appariement,
                mots_retrouves=" ".join(temoin.mots_retrouves(suivi.signature.mots, [x.contenu])),
                enonce=_normaliser(x.enonce or x.contenu)[:160],
            ))
    return sorted(derives, key=lambda d: (d.evenement_id, _cle(d.person_id), d.ecrit_le,
                                          d.doc_id))


def _cle(person_id: str) -> tuple[int, int, str]:
    return (0, int(person_id), "") if person_id.isdigit() else (1, 0, person_id)
