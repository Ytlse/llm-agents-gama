"""Mémoire noyau — ticket 071, lot 4.

Les dix souvenirs bruts servis au modèle sont remplacés par un **bloc permanent structuré**,
complété de deux ou trois entrées épisodiques rappelées pour la décision en cours. C'est le
*working context* de MemGPT (Packer et al., 2023, § 2.1) : un bloc toujours présent dans le
contexte principal, le reste étant paginé à la demande.

**Les trois blocs sont CALCULÉS, aucun n'est écrit par le modèle.** La spécification ne
calculait que les habitudes et confiait les connaissances au modèle ; depuis le lot 3, un
concept porte son compteur d'observations, sa confiance et son état de service, si bien que le
bloc se calcule exactement. L'argument du garde-fou vaut pour les trois : un texte réécrit
périodiquement par un modèle dérive et invente, un bloc calculé reste vérifiable contre sa
source. Le lot 4 ne touche donc pas au schéma de l'auto-réflexion, et ne coûte aucune inférence.

**Le bloc ne porte aucune métadonnée sur lui-même** : ni date de mise à jour, ni nombre de jours
de vécu. Ces informations ne changent aucune décision, coûtent des jetons, et rompent la fiction
que les gabarits maintiennent — une personne ne pense pas « mon résumé d'habitudes date de trois
jours ». L'ancienneté utile est déjà portée, énoncé par énoncé, par les compteurs d'observations.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from settings import settings

# Une occurrence n'est pas une habitude. En dessous, la ligne n'est pas écrite : dire « vélo,
# 1 fois sur 1 » donnerait à un aléa l'autorité d'une routine.
OCCURRENCES_MIN_HABITUDE = 3
# Au-delà, le bloc coûte des jetons sans rien apprendre au modèle.
HABITUDES_MAX = 4
CONNAISSANCES_MAX = 6
CHANGEMENTS_MAX = 3
# Fenêtre du bloc « ce qui a changé récemment », en jours simulés.
FENETRE_CHANGEMENTS_JOURS = 14

_LIBELLE_MODE = {
    "walking": "à pied",
    "cycling": "à vélo",
    "car": "en voiture",
    "public_transport": "en transport en commun",
    "train": "en train",
    "motorbike": "en deux-roues",
}
_LIBELLE_CRENEAU = {
    "matin": "le matin",
    "midi": "en milieu de journée",
    "soir": "le soir",
    "nuit": "la nuit",
}


# ── Journal des trajets ──────────────────────────────────────────────────────────


def cle_journal(motif: str | None, creneau: str | None) -> str:
    """Clé du journal : le couple motif-créneau, sérialisable en JSON."""
    return f"{motif or '?'}|{creneau or '?'}"


def noter_trajet(
    journal: dict,
    motif: str | None,
    creneau: str | None,
    mode: str | None,
    retard_s: float = 0.0,
) -> dict:
    """Enregistre un trajet dans le journal d'un agent.

    ⚠ Ce journal n'existait pas. `MoveLogger` écrit dans `moves.csv` et rien d'autre, et
    `PersonState` ne garde aucun historique : relire un CSV à chaque décision est exclu, c'est
    le chemin critique. Il est donc tenu en mémoire et **persisté avec les métadonnées de
    l'agent**, ce qui réutilise l'écriture différée déjà en place. Sans persistance, un run
    repris repartirait sans habitudes et le bloc mentirait par omission le premier jour.
    """
    if not mode:
        # Un trajet dont le mode n'a pas été résolu ne compte pas — mais il ne fait pas non
        # plus dériver le dénominateur : on ne l'enregistre pas du tout.
        return journal
    clef = cle_journal(motif, creneau)
    entree = journal.setdefault(clef, {"modes": {}, "retards": 0, "total": 0})
    entree["modes"][mode] = entree["modes"].get(mode, 0) + 1
    entree["total"] += 1
    if retard_s >= 600:  # dix minutes
        entree["retards"] += 1
    return journal


def bloc_habitudes(journal: dict) -> list[str]:
    """« Mes habitudes », calculé depuis le journal des trajets. Jamais écrit par le modèle."""
    lignes = []
    for clef, entree in sorted(
        journal.items(), key=lambda kv: kv[1].get("total", 0), reverse=True
    ):
        total = int(entree.get("total", 0))
        if total < OCCURRENCES_MIN_HABITUDE:
            continue
        modes = entree.get("modes") or {}
        if not modes:
            continue
        mode, n = max(modes.items(), key=lambda kv: kv[1])
        motif, creneau = clef.split("|", 1)
        libelle = (
            f"{motif} {_LIBELLE_CRENEAU.get(creneau, creneau)} : "
            f"{_LIBELLE_MODE.get(mode, mode)}, {n} fois sur {total}"
        )
        retards = int(entree.get("retards", 0))
        if retards:
            libelle += f". {retards} retard(s) de plus de 10 min"
        lignes.append(libelle)
        if len(lignes) >= HABITUDES_MAX:
            break
    return lignes


# ── Ce que je sais ───────────────────────────────────────────────────────────────


def _enonce(entree) -> str:
    """Texte lisible d'un concept, quel que soit le format sous lequel il a été écrit."""
    contenu = entree.content or ""
    if contenu.startswith("["):
        try:
            cinq = json.loads(contenu)
            return str(cinq[0]) if cinq else contenu
        except (ValueError, IndexError):
            return contenu
    return contenu


def bloc_connaissances(entrees) -> list[str]:
    """« Ce que je sais », calculé depuis les CONCEPTS et leurs compteurs.

    Un concept mis hors service n'y figure pas : on ne sert pas au modèle ce que l'agent ne
    croit plus. Les plus confiants d'abord.
    """
    concepts = [
        e for e in entrees
        if not e.est_episodique and e.est_servi and not e.depasse_le
    ]
    concepts.sort(
        key=lambda e: (e.confiance, e.observations, e.horodatage_de_reference),
        reverse=True,
    )
    return [
        f"{_enonce(e)}  ({e.observations} obs.)"
        for e in concepts[:CONNAISSANCES_MAX]
    ]


# ── Ce qui a changé récemment ────────────────────────────────────────────────────


def bloc_changements(entrees, maintenant: datetime | None) -> list[str]:
    """« Ce qui a changé récemment » : les chocs, et les croyances mises à l'écart.

    La mise à l'écart d'un concept est l'observable que l'expérience d'hystérésis cherche.
    C'est ici qu'elle devient lisible dans le prompt lui-même, et non plus seulement dans les
    statistiques de sortie.
    """
    if maintenant is None:
        return []
    depuis = maintenant - timedelta(days=FENETRE_CHANGEMENTS_JOURS)
    seuil_choc = float(settings.agent.memoire__importance_choc)
    lignes: list[tuple[datetime, str]] = []

    for e in entrees:
        if e.est_episodique:
            if float(e.importance or 0.0) >= seuil_choc and e.timestamp >= depuis:
                lignes.append((e.timestamp, _enonce(e)))
            continue
        if e.depasse_le:
            try:
                quand = datetime.fromisoformat(e.depasse_le)
            except (TypeError, ValueError):
                continue
            if quand >= depuis:
                lignes.append(
                    (quand, f"Je ne crois plus que : {_enonce(e)}")
                )

    lignes.sort(key=lambda kv: kv[0], reverse=True)
    return [texte for _, texte in lignes[:CHANGEMENTS_MAX]]


# ── Le bloc complet ──────────────────────────────────────────────────────────────


def memoire_noyau(journal: dict, entrees, maintenant: datetime | None) -> list[str]:
    """Le bloc permanent, en lignes prêtes pour le gabarit.

    Un bloc vide est ABSENT et non présent avec un titre : un titre sans contenu dit au modèle
    qu'il devrait y avoir quelque chose, et l'invite à le combler.
    """
    sections = (
        ("Mes habitudes", bloc_habitudes(journal or {})),
        ("Ce que je sais", bloc_connaissances(entrees or [])),
        ("Ce qui a changé récemment", bloc_changements(entrees or [], maintenant)),
    )
    sortie: list[str] = []
    for titre, lignes in sections:
        if not lignes:
            continue
        sortie.append(titre)
        sortie.extend(f"- {ligne}" for ligne in lignes)
    return sortie
