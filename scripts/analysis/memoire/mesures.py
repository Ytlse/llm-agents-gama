"""Mesures dérivées du run : redondance, contamination, décisivité, rappels.

Aucune mesure ne rend ici un « bon » score par défaut. Dans ce dépôt, l'absence
de mesure produit volontiers zéro, et zéro se lit comme la perfection : chaque
fonction rend donc explicitement le **nombre d'observations** qui la fonde, pour
que le rapport puisse écrire « aucune donnée » plutôt que « 0 % ».
"""
from __future__ import annotations

import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from . import sources
from .sources import BlocPrompt, BlocReflexion, EntreeLTM, Journal, Option, Run, Trajet

# ── Concepts : confiance, thèmes, redondance ─────────────────────────────────

def confiance(observations: int, contre_exemples: int) -> float:
    """Règle de succession de Laplace, comme `llm/concepts.py`.

    Réécrite ici plutôt qu'importée : le rapport doit tourner sur un run archivé
    sans charger le service. Un concept jamais observé vaut 0,50 — ni cru, ni écarté.
    """
    obs = max(0, int(observations or 0))
    contre = max(0, int(contre_exemples or 0))
    return (obs + 1) / (obs + contre + 2)


_MOTS_VIDES = {
    "the", "a", "an", "and", "or", "to", "of", "for", "is", "are", "was", "were",
    "be", "been", "it", "its", "this", "that", "these", "those", "in", "on", "at",
    "by", "with", "as", "from", "my", "me", "i", "but", "not", "no", "so", "than",
    "then", "when", "which", "while", "very", "more", "most", "much", "can", "will",
    "would", "should", "could", "have", "has", "had", "do", "does", "did", "get",
    "gets", "getting", "there", "their", "they", "he", "she", "we", "you", "always",
}


def _sac_de_mots(enonce: str) -> frozenset[str]:
    mots = re.findall(r"[a-zà-öø-ÿ']+", (enonce or "").lower())
    return frozenset(m for m in mots if len(m) > 2 and m not in _MOTS_VIDES)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class Theme:
    """Un thème et ses reformulations. Le libellé est le premier énoncé rencontré."""
    libelle: str
    concepts: list[EntreeLTM] = field(default_factory=list)

    @property
    def observations(self) -> int:
        return sum(c.observations for c in self.concepts)

    @property
    def contre_exemples(self) -> int:
        return sum(c.contre_exemples for c in self.concepts)

    @property
    def rappels(self) -> int:
        return sum(c.rappels for c in self.concepts)


SEUIL_THEME = 0.5


def concepts(entrees: Iterable[EntreeLTM]) -> list[EntreeLTM]:
    return sorted((e for e in entrees if e.memory_type == "concept"),
                  key=lambda e: (e.timestamp, e.doc_id))


def themes(liste: Sequence[EntreeLTM]) -> list[Theme]:
    """Regroupe les reformulations d'un même thème.

    Agglomération gloutonne sur le recouvrement de vocabulaire (Jaccard ≥ 0,5),
    dans l'ordre chronologique : un concept rejoint le **premier** thème existant
    qu'il recouvre, sinon il en ouvre un. L'ordre étant fixé par l'horodatage puis
    le `doc_id`, le regroupement est reproductible.
    """
    groupes: list[tuple[frozenset[str], Theme]] = []
    for concept in liste:
        sac = _sac_de_mots(concept.enonce)
        rejoint = None
        for reference, theme in groupes:
            if _jaccard(sac, reference) >= SEUIL_THEME:
                rejoint = theme
                break
        if rejoint is None:
            theme = Theme(libelle=concept.enonce or "(énoncé vide)")
            groupes.append((sac, theme))
            rejoint = theme
        rejoint.concepts.append(concept)
    return [theme for _, theme in groupes]


def taux_redondance(liste: Sequence[EntreeLTM]) -> float | None:
    """Part des concepts qui reformulent un thème déjà présent. ``None`` si aucun concept."""
    if not liste:
        return None
    return 1.0 - len(themes(liste)) / len(liste)


# ── Parts modales ─────────────────────────────────────────────────────────────

def parts_modales(trajets: Sequence[Trajet]) -> dict[str, float]:
    total = sum(1 for t in trajets if t.mode)
    if not total:
        return {}
    compte: dict[str, int] = {}
    for trajet in trajets:
        if trajet.mode:
            compte[trajet.mode] = compte.get(trajet.mode, 0) + 1
    return {mode: 100.0 * n / total for mode, n in sorted(compte.items())}


# ── Appariement des itinéraires proposés ─────────────────────────────────────

@dataclass
class Appariement:
    """Résultat de l'appariement trajet ↔ bloc de prompt."""
    par_trajet: dict[str, BlocPrompt | None] = field(default_factory=dict)
    apparies: int = 0
    non_apparies: int = 0

    @property
    def total(self) -> int:
        return self.apparies + self.non_apparies

    @property
    def taux(self) -> float | None:
        return 100.0 * self.apparies / self.total if self.total else None


def apparier(trajets: Sequence[Trajet], blocs: Sequence[BlocPrompt]) -> Appariement:
    """Apparie chaque trajet à un bloc de prompt par ``(agent, jour, motif)``.

    Les options proposées ne vivent que dans le texte des prompts, et rien ne
    porte l'identifiant du trajet dans le prompt. On apparie donc par heure de
    départ la plus proche, une option par trajet au plus, en commençant par les
    couples les plus proches — l'ordre glouton est stable puisque les clés de tri
    sont totales. Quand aucun bloc ne reste, le trajet est déclaré **non apparié** :
    sa colonne sera grise, jamais vide en silence (contrat F3).
    """
    index: dict[tuple[str, str, str], list[BlocPrompt]] = {}
    for bloc in blocs:
        index.setdefault((bloc.agent, bloc.jour, bloc.motif), []).append(bloc)

    resultat = Appariement()
    par_cle: dict[tuple[str, str, str], list[Trajet]] = {}
    for trajet in trajets:
        par_cle.setdefault((trajet.person_id, trajet.jour, trajet.motif), []).append(trajet)

    for cle in sorted(par_cle):
        lot = sorted(par_cle[cle], key=lambda t: (t.depart_minutes or 0, t.trajet_id))
        disponibles = list(index.get(cle, []))
        couples = sorted(
            ((abs((t.depart_minutes or 0) - (b.depart_minutes or 0)), i, j)
             for i, t in enumerate(lot) for j, b in enumerate(disponibles)),
        )
        pris_t: set[int] = set()
        pris_b: set[int] = set()
        for _, i, j in couples:
            if i in pris_t or j in pris_b:
                continue
            pris_t.add(i)
            pris_b.add(j)
            resultat.par_trajet[lot[i].trajet_id] = disponibles[j]
            resultat.apparies += 1
        for i, trajet in enumerate(lot):
            if i not in pris_t:
                resultat.par_trajet[trajet.trajet_id] = None
                resultat.non_apparies += 1
    return resultat


@dataclass
class LigneItineraire:
    """Une ligne du tableau des itinéraires : un itinéraire distinct."""
    identite: tuple[str, tuple[str, ...]]
    mode_brut: str
    mode: str | None
    description: str
    etapes: tuple[str, ...]
    cases: dict[str, str] = field(default_factory=dict)   # jour → « retenu » | « propose »

    @property
    def retenus(self) -> int:
        return sum(1 for v in self.cases.values() if v == "retenu")

    @property
    def proposes(self) -> int:
        return len(self.cases)


@dataclass
class TableauItineraires:
    motif: str
    lignes: list[LigneItineraire] = field(default_factory=list)
    jours_gris: list[str] = field(default_factory=list)
    jours_actifs: list[str] = field(default_factory=list)
    trajets_non_apparies: int = 0
    trajets: int = 0


def tableaux_itineraires(trajets: Sequence[Trajet],
                         appariement: Appariement) -> list[TableauItineraires]:
    """Un tableau par motif : lignes = itinéraires distincts, colonnes = jours.

    L'option **retenue** se déduit du mode choisi : l'index effectivement tiré
    n'est journalisé nulle part dans ce run (c'est précisément ce que réclame le
    lot E.2). Quand plusieurs options partagent le mode retenu, la plus courte —
    à mode égal, le plus petit index — porte la marque, et le rapport le déclare.
    """
    par_motif: dict[str, list[Trajet]] = {}
    for trajet in trajets:
        par_motif.setdefault(trajet.motif, []).append(trajet)

    tableaux: list[TableauItineraires] = []
    for motif in sorted(par_motif):
        tableau = TableauItineraires(motif=motif)
        lignes: dict[tuple[str, tuple[str, ...]], LigneItineraire] = {}
        for trajet in sorted(par_motif[motif], key=lambda t: (t.jour, t.depart, t.trajet_id)):
            tableau.trajets += 1
            if trajet.jour not in tableau.jours_actifs:
                tableau.jours_actifs.append(trajet.jour)
            bloc = appariement.par_trajet.get(trajet.trajet_id)
            if bloc is None:
                tableau.trajets_non_apparies += 1
                if trajet.jour not in tableau.jours_gris:
                    tableau.jours_gris.append(trajet.jour)
                continue
            retenue = _option_retenue(bloc.options, trajet.mode)
            for option in bloc.options:
                ligne = lignes.get(option.identite)
                if ligne is None:
                    ligne = LigneItineraire(
                        identite=option.identite, mode_brut=option.mode_brut,
                        mode=option.mode, description=option.description,
                        etapes=option.etapes)
                    lignes[option.identite] = ligne
                etat = "retenu" if (retenue is not None
                                    and option.identite == retenue.identite) else "propose"
                if ligne.cases.get(trajet.jour) != "retenu":
                    ligne.cases[trajet.jour] = etat
        tableau.lignes = sorted(
            lignes.values(),
            key=lambda l: (-l.retenus, -l.proposes, l.mode_brut, l.etapes))
        tableaux.append(tableau)
    return tableaux


def _option_retenue(options: Sequence[Option], mode: str | None) -> Option | None:
    if not mode:
        return None
    candidates = [o for o in options if o.mode == mode]
    if not candidates:
        return None
    return min(candidates, key=lambda o: (len(o.etapes), o.index))


# ── Décisivité et entropie, par semaine ──────────────────────────────────────

@dataclass
class Semaine:
    libelle: str
    debut: str
    fin: str
    decisivite: float | None
    entropie: float | None
    n: int


def semaines(trajets: Sequence[Trajet], jours: Sequence[str]) -> list[Semaine]:
    """Découpe le run en semaines de sept jours à partir du premier jour observé.

    * **décisivité** : probabilité du mode dominant, moyenne des décisions ;
    * **entropie** : entropie de Shannon de la distribution, en bits.

    Les trajets sans distribution (itinéraire unique, erreur LLM) ne comptent pas :
    leur inclure un 100 % implicite gonflerait la décisivité d'une décision qui
    n'en est pas une.
    """
    if not jours:
        return []
    premier = _date(jours[0])
    dernier = _date(jours[-1])
    if premier is None or dernier is None:
        return []
    paquets: dict[int, list[Trajet]] = {}
    for trajet in trajets:
        jour = _date(trajet.jour)
        if jour is None:
            continue
        paquets.setdefault((jour - premier).days // 7, []).append(trajet)

    resultat: list[Semaine] = []
    nb = (dernier - premier).days // 7 + 1
    for index in range(nb):
        debut = premier + timedelta(days=7 * index)
        fin = min(dernier, debut + timedelta(days=6))
        lot = [t for t in paquets.get(index, []) if t.probabilites]
        if lot:
            decisivite = sum(max(t.probabilites.values()) for t in lot) / len(lot) / 100.0
            entropie = sum(_entropie(t.probabilites) for t in lot) / len(lot)
        else:
            decisivite = entropie = None
        resultat.append(Semaine(
            libelle=f"S{index + 1}", debut=debut.isoformat(), fin=fin.isoformat(),
            decisivite=decisivite, entropie=entropie, n=len(lot)))
    return resultat


def _entropie(probabilites: dict[str, float]) -> float:
    total = sum(probabilites.values())
    if total <= 0:
        return 0.0
    somme = 0.0
    for valeur in probabilites.values():
        part = valeur / total
        if part > 0:
            somme -= part * math.log2(part)
    return somme


def _date(jour: str) -> date | None:
    try:
        return date.fromisoformat(jour)
    except (TypeError, ValueError):
        return None


# ── Contamination des observations ───────────────────────────────────────────

@dataclass
class Contamination:
    marches_fantomes: int = 0
    marches_examinees: int = 0
    marches_sans_arrivee: int = 0
    tc_total: int = 0
    tc_anonymes: int = 0
    voiture_en_tc: int = 0
    par_agent: dict[str, dict[str, int]] = field(default_factory=dict)


_WALK_VIDE = "[ WALK ] Walked to ''"
_TC = "[ PUBLIC TRANSPORT ]"
_TC_ANONYME = "Unknown Unknown"


def contamination(run: Run) -> Contamination:
    """Deux observations fausses, comptées sur les fichiers du run.

    1. **Marches fantômes** (lot B1) : une marche de distance nulle dont la durée,
       arrondie à la minute comme le fait le gabarit, égale exactement le retard au
       départ du trajet qui la contient. C'est l'attente avant départ journalisée
       comme un déplacement à pied.
    2. **Voiture journalisée en transport collectif** (lot B2) : un événement
       « Trip by Unknown Unknown » alors que la décision du même trajet est la
       voiture.
    """
    mesure = Contamination()
    par_agent: dict[str, list[dict[str, Any]]] = {}
    for arrivee in run.arrivees:
        par_agent.setdefault(arrivee["person_id"], []).append(arrivee)

    modes_par_trajet = {t.trajet_id: t.mode for t in run.trajets}
    fenetres: dict[str, list[tuple[int, int, str]]] = {}
    for arrivee in run.arrivees:
        fenetres.setdefault(arrivee["person_id"], []).append(
            (arrivee["started_at"], arrivee["arrive_at"], arrivee["move_id"]))

    for evenement in run.evenements:
        message = str(evenement.get("message") or "")
        agent = str(evenement.get("person_id") or "")
        compteurs = mesure.par_agent.setdefault(
            agent, {"marches_fantomes": 0, "voiture_en_tc": 0, "tc_anonymes": 0})
        horodatage = int(evenement.get("timestamp") or 0)

        if message.startswith(_WALK_VIDE):
            mesure.marches_examinees += 1
            arrivee = _arrivee_contenante(par_agent.get(agent, []), horodatage)
            if arrivee is None:
                mesure.marches_sans_arrivee += 1
                continue
            duree = sources.duree_en_secondes(message)
            retard = abs(int(arrivee["departure_delay_s"]))
            if duree and duree > 0 and retard - (retard % 60) == duree:
                mesure.marches_fantomes += 1
                compteurs["marches_fantomes"] += 1
            continue

        if message.startswith(_TC):
            mesure.tc_total += 1
            if _TC_ANONYME in message:
                mesure.tc_anonymes += 1
                compteurs["tc_anonymes"] += 1
                arrivee = _arrivee_contenante(par_agent.get(agent, []), horodatage)
                if arrivee is not None and modes_par_trajet.get(arrivee["move_id"]) == "car":
                    mesure.voiture_en_tc += 1
                    compteurs["voiture_en_tc"] += 1
    return mesure


def _arrivee_contenante(arrivees: Sequence[dict[str, Any]],
                        horodatage: int) -> dict[str, Any] | None:
    """Le trajet qui contient cet instant ; à défaut, aucun.

    Les événements de mémoire portent l'heure murale simulée : l'événement de
    marche tombe entre le départ et l'arrivée du trajet qu'il décrit.
    """
    candidats = [a for a in arrivees if a["started_at"] <= horodatage <= a["arrive_at"]]
    if not candidats:
        return None
    return max(candidats, key=lambda a: (a["started_at"], a["move_id"]))


# ── Croyances servies à la réflexion ─────────────────────────────────────────

@dataclass
class Croyances:
    blocs: int = 0
    vides: int = 0
    par_agent: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def taux_vide(self) -> float | None:
        return 100.0 * self.vides / self.blocs if self.blocs else None


def croyances(blocs: Sequence[BlocReflexion]) -> Croyances:
    """Part des blocs de réflexion arrivés avec un ``known_beliefs`` vide.

    Un bloc vide, c'est un modèle à qui l'on ne donne rien à confirmer ni à
    contredire : la redondance qui suit n'est pas de son fait.
    """
    mesure = Croyances()
    brut: dict[str, list[int]] = {}
    for bloc in blocs:
        mesure.blocs += 1
        vide = 1 if bloc.nb_croyances == 0 else 0
        mesure.vides += vide
        compteurs = brut.setdefault(bloc.agent, [0, 0])
        compteurs[0] += 1
        compteurs[1] += vide
    mesure.par_agent = {agent: (total, vides) for agent, (total, vides) in sorted(brut.items())}
    return mesure


# ── Concentration des rappels ────────────────────────────────────────────────

@dataclass
class Rappels:
    servis: int = 0
    evenements: int = 0
    top: list[tuple[str, int]] = field(default_factory=list)

    @property
    def concentration(self) -> float | None:
        """Part du total occupée par les dix souvenirs les plus servis."""
        if not self.servis:
            return None
        return 100.0 * sum(n for _, n in self.top[:10]) / self.servis


def rappels(journal: Journal | None) -> Rappels:
    mesure = Rappels()
    if journal is None:
        return mesure
    compte: dict[str, int] = {}
    for _, incipits in journal.rappels:
        mesure.evenements += 1
        for incipit in incipits:
            mesure.servis += 1
            compte[incipit] = compte.get(incipit, 0) + 1
    mesure.top = sorted(compte.items(), key=lambda item: (-item[1], item[0]))
    return mesure


# ── Raisons citant l'expérience ──────────────────────────────────────────────

_MARQUEURS_EXPERIENCE = (
    "yesterday", "last time", "previous", "past experience", "usual", "usually",
    "habit", "learned", "remember", "again", "as always", "recent", "history",
    "experience", "before",
)


def part_raisons_experience(trajets: Sequence[Trajet]) -> tuple[float | None, int]:
    """Part des raisonnements qui invoquent explicitement le passé de l'agent."""
    avec_raison = [t for t in trajets if t.raisonnement]
    if not avec_raison:
        return None, 0
    cites = sum(1 for t in avec_raison
                if any(m in t.raisonnement.lower() for m in _MARQUEURS_EXPERIENCE))
    return 100.0 * cites / len(avec_raison), len(avec_raison)


# ── Frise des modes ──────────────────────────────────────────────────────────

def frise(trajets: Sequence[Trajet], jours: Sequence[str]) -> list[tuple[str, dict[str, list[str]]]]:
    """Par motif, et par jour, la suite des modes retenus (plusieurs trajets possibles)."""
    par_motif: dict[str, dict[str, list[str]]] = {}
    for trajet in sorted(trajets, key=lambda t: (t.motif, t.jour, t.depart, t.trajet_id)):
        jours_du_motif = par_motif.setdefault(trajet.motif, {})
        jours_du_motif.setdefault(trajet.jour, []).append(trajet.mode or "autres")
    ordre = sorted(par_motif, key=lambda m: (-sum(len(v) for v in par_motif[m].values()), m))
    return [(motif, par_motif[motif]) for motif in ordre]
