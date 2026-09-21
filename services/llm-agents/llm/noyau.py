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
import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from loguru import logger
from llm.gravite import force_initiale
from settings import settings

# Une occurrence n'est pas une habitude. En dessous, la ligne n'est pas écrite : dire « vélo,
# 1 fois sur 1 » donnerait à un aléa l'autorité d'une routine.
OCCURRENCES_MIN_HABITUDE = 3
# Au-delà, le bloc coûte des jetons sans rien apprendre au modèle.
HABITUDES_MAX = 4
CONNAISSANCES_MAX = 6

# La fenêtre du bloc « ce qui a changé récemment » et son plafond de lignes sont des RÉGLAGES
# (`memoire__fenetre_changements_jours`, `memoire__changements_max`) et non des constantes :
# c'est la fenêtre qui décide combien de temps un choc pèse sur les décisions, et elle était
# écrite en dur. Cf. ticket 077, lot I.

# Fenêtre des CROYANCES MISES À L'ÉCART, inchangée depuis le lot 4 du 071 et volontairement
# laissée en constante : le bras d'ablation ne fait varier que la fenêtre des souvenirs de choc.
FENETRE_CROYANCES_ECARTEES_JOURS = 14

# Souvenirs de choc dont la sortie de fenêtre a déjà été annoncée : (agent, instant du souvenir).
# Front montant — sans lui, la ligne se répéterait à chaque décision et noierait ce qu'elle dit.
_SORTIES_ANNONCEES: set[tuple[str, str]] = set()
_FENETRE_NEGATIVE_DITE = False

# ── Les deux modes de service du bloc de changements (ticket 095, lot A) ─────────
MODE_DERIVEE = "derivee"
MODE_FIXE = "fixe"
_MODES = (MODE_DERIVEE, MODE_FIXE)

# Réglages hors domaine déjà signalés. Une alarme qui se répète à chaque décision cesse d'en
# être une ; une alarme muette laisse un repli passer pour un réglage accepté.
_REGLAGES_FAUTIFS_DITS: set[str] = set()


def reinitialiser() -> None:
    """Oublie ce qui a déjà été annoncé. Réservé aux tests."""
    global _FENETRE_NEGATIVE_DITE
    _SORTIES_ANNONCEES.clear()
    _REGLAGES_FAUTIFS_DITS.clear()
    _FENETRE_NEGATIVE_DITE = False


def _alarmer_une_fois(cle: str, message: str) -> None:
    """Signale un réglage hors domaine UNE fois, en ERROR : c'est une mesure qui dérive."""
    if cle in _REGLAGES_FAUTIFS_DITS:
        return
    _REGLAGES_FAUTIFS_DITS.add(cle)
    logger.error(message)


def _fenetre_jours() -> int:
    """La fenêtre en vigueur, lue à CHAQUE appel.

    Figée à l'import, une surcharge d'environnement — donc le bras d'ablation — ne servirait
    à rien.
    """
    global _FENETRE_NEGATIVE_DITE
    brut = int(settings.agent.memoire__fenetre_changements_jours)
    if brut < 0:
        if not _FENETRE_NEGATIVE_DITE:
            _FENETRE_NEGATIVE_DITE = True
            logger.warning(
                f"[noyau] fenêtre « ce qui a changé récemment » négative ({brut} j) — ramenée "
                f"à 0, donc aucun souvenir de choc dans le bloc. Si c'est l'ablation qui est "
                f"voulue, déclarer 0 ; une valeur négative ne doit pas se lire comme un réglage "
                f"accepté."
            )
        return 0
    return brut

def _mode_fenetre() -> str:
    """`derivee` ou `fixe`, lu à CHAQUE appel. Un mode inconnu ne s'interprète pas."""
    brut = str(getattr(settings.agent, "memoire__mode_fenetre_changements", MODE_DERIVEE)).strip()
    if brut in _MODES:
        return brut
    _alarmer_une_fois(
        f"mode:{brut}",
        f"[ALARME] [noyau] mode de fenêtre « ce qui a changé récemment » inconnu ({brut!r}) — "
        f"repli sur {MODE_DERIVEE!r}. Modes admis : {list(_MODES)}. Un bras lancé sous ce "
        f"réglage ne mesure PAS ce qu'il déclare mesurer.",
    )
    return MODE_DERIVEE


def _seuil_service() -> float:
    """Le seuil de poids sous lequel un souvenir quitte le bloc. Domaine ouvert ]0, 1[."""
    defaut = 0.35
    brut = float(getattr(settings.agent, "memoire__seuil_service_changement", defaut))
    if 0.0 < brut < 1.0:
        return brut
    _alarmer_une_fois(
        f"seuil:{brut}",
        f"[ALARME] [noyau] seuil de service du bloc de changements hors de ]0, 1[ ({brut}) — "
        f"repli sur {defaut}. À 1 la durée serait nulle (une ablation que personne n'a "
        f"déclarée), à 0 elle serait infinie.",
    )
    return defaut


def _bornes_duree() -> tuple[float, float]:
    """Plancher et plafond de la durée servie, en jours, remis dans l'ordre s'il le faut."""
    plancher = float(getattr(settings.agent, "memoire__plancher_changement_jours", 2.0))
    plafond = float(getattr(settings.agent, "memoire__plafond_changement_jours", 30.0))
    if plancher > plafond:
        _alarmer_une_fois(
            f"bornes:{plancher}:{plafond}",
            f"[ALARME] [noyau] plancher de durée ({plancher} j) supérieur au plafond "
            f"({plafond} j) — les deux bornes sont échangées. Sans cet échange, aucun souvenir "
            f"de choc ne serait jamais servi.",
        )
        plancher, plafond = plafond, plancher
    return max(0.0, plancher), max(0.0, plafond)


@dataclass(frozen=True)
class DureeService:
    """Ce qu'il faut pour justifier une date de sortie, et pas seulement l'annoncer."""

    jours: float        # la durée SERVIE, bornes appliquées
    brute: float        # `force × ln(1/seuil)`, avant bornes
    force: float        # la constante de temps de l'oubli de ce souvenir, en jours
    gravite: float
    borne: str          # "plancher", "plafond", ou "" quand aucune borne n'a mordu


def duree_service_jours(entree) -> DureeService:
    """Combien de jours ce souvenir de choc reste servi dans « ce qui a changé récemment ».

    `poids(t) = exp(-t / force)` décroît ; le souvenir est servi tant que ce poids dépasse le
    seuil, soit `t ≤ force × ln(1 / seuil)`. La forme vient de MemoryBank (Zhong et al., 2024) —
    c'est la même que celle du rappel, et c'est le point : la durée d'un effet cesse d'être un
    entier posé à côté du modèle d'oubli pour en devenir une conséquence.

    La `force` est celle PORTÉE par l'entrée, qui a pu croître au rappel. Absente — entrée
    écrite avant le lot 1 du ticket 071 —, elle est recalculée depuis la gravité plutôt que
    traitée comme nulle : une force nulle rendrait une durée nulle, c'est-à-dire une ablation.
    """
    gravite = float(getattr(entree, "importance", 0.0) or 0.0)
    force = getattr(entree, "force", None)
    force = float(force) if force else force_initiale(gravite)
    brute = force * math.log(1.0 / _seuil_service())
    plancher, plafond = _bornes_duree()
    borne = ""
    jours = brute
    if jours > plafond:
        jours, borne = plafond, "plafond"
    elif jours < plancher:
        jours, borne = plancher, "plancher"
    return DureeService(
        jours=jours, brute=brute, force=force, gravite=gravite, borne=borne
    )


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


def _annoncer_sortie(
    person_id: str | None,
    dans: list,
    hors: list[tuple],
    mode: str,
    fenetre: int,
) -> None:
    """Le jour où un souvenir de choc quitte le bloc, et ce jour-là seulement.

    C'est l'événement qui, sur le run du 2026-09-19, coïncide au prompt près avec le retour de
    la voiture. Il était jusqu'ici invisible : il fallait relire le texte des prompts pour le
    reconstituer, et le rapport du run lui a attribué une autre cause.

    ⚠ La ligne porte désormais **ce qui a produit la durée** — gravité, force, durée calculée,
    et le nom de la borne quand une borne a mordu — et non plus la seule date. Une durée servie
    sans sa cause ne se vérifie pas après coup : c'est exactement ce qui a rendu indiscernables,
    pendant deux jours, la décroissance du souvenir et la coupure de fenêtre.
    """
    if not person_id or not hors:
        return
    for entree, duree in sorted(hors, key=lambda kv: kv[0].timestamp, reverse=True):
        cle = (str(person_id), entree.timestamp.isoformat())
        if cle in _SORTIES_ANNONCEES:
            continue
        _SORTIES_ANNONCEES.add(cle)
        if mode == MODE_FIXE:
            cause = f"fenêtre fixe de {fenetre} j"
        elif duree is None:
            cause = "durée indéterminée"
        else:
            cause = (
                f"durée {duree.jours:.2f} j dérivée d'une gravité de {duree.gravite:.2f} "
                f"(force {duree.force:.2f} j, durée calculée {duree.brute:.2f} j)"
            )
            if duree.borne:
                cause += f", ramenée par le {duree.borne}"
        reste = (
            "" if dans else " — plus aucun souvenir de choc ne pèse sur ses décisions"
        )
        logger.info(
            f"[noyau] {person_id} : le souvenir de choc du "
            f"{entree.timestamp:%Y-%m-%d} est sorti du bloc « ce qui a changé récemment » "
            f"({cause}){reste}."
        )


def bloc_changements(
    entrees, maintenant: datetime | None, person_id: str | None = None
) -> list[str]:
    """« Ce qui a changé récemment » : les chocs, et les croyances mises à l'écart.

    La mise à l'écart d'un concept est l'observable que l'expérience d'hystérésis cherche.
    C'est ici qu'elle devient lisible dans le prompt lui-même, et non plus seulement dans les
    statistiques de sortie.

    ⚠ DEUX fenêtres, et c'est voulu. Celle des souvenirs de choc dépend du MODE déclaré — en
    `derivee`, elle se calcule souvenir par souvenir depuis la gravité ; en `fixe`, elle vaut
    `memoire__fenetre_changements_jours` pour tous. Celle des croyances mises à l'écart reste la
    constante historique : la faire bouger en même temps confondrait deux changements dans une
    seule mesure.

    ⚠ L'âge d'un souvenir se compte depuis `timestamp`, l'instant de l'ÉVÉNEMENT, et non depuis
    `dernier_rappel`. Ce bloc annonce l'ancienneté d'un CHANGEMENT, pas celle de sa dernière
    lecture : un choc relu hier n'est pas un choc d'hier. Le renforcement au rappel continue de
    jouer, mais par la `force`, donc sur la durée — pas en rajeunissant l'événement.

    `person_id` ne sert qu'au journal ; il est facultatif pour que les appels purs restent purs.
    """
    if maintenant is None:
        return []
    mode = _mode_fenetre()
    fenetre = _fenetre_jours()
    depuis_chocs = maintenant - timedelta(days=fenetre)
    depuis_croyances = maintenant - timedelta(days=FENETRE_CROYANCES_ECARTEES_JOURS)
    seuil_choc = float(settings.agent.memoire__importance_choc)
    lignes: list[tuple[datetime, str]] = []
    chocs_dans: list = []
    chocs_hors: list[tuple] = []

    for e in entrees:
        if e.est_episodique:
            if float(e.importance or 0.0) >= seuil_choc:
                duree = None
                if mode == MODE_FIXE:
                    # Fenêtre à 0 : ABLATION déclarée, aucun souvenir de choc ne passe — y
                    # compris celui de l'instant même, que `>= maintenant` laisserait entrer.
                    servi = fenetre > 0 and e.timestamp >= depuis_chocs
                else:
                    duree = duree_service_jours(e)
                    age_jours = (maintenant - e.timestamp).total_seconds() / 86400.0
                    servi = age_jours <= duree.jours
                if servi:
                    chocs_dans.append(e)
                    lignes.append((e.timestamp, _enonce(e)))
                else:
                    chocs_hors.append((e, duree))
            continue
        if e.depasse_le:
            try:
                quand = datetime.fromisoformat(e.depasse_le)
            except (TypeError, ValueError):
                continue
            if quand >= depuis_croyances:
                lignes.append(
                    (quand, f"Je ne crois plus que : {_enonce(e)}")
                )

    _annoncer_sortie(person_id, chocs_dans, chocs_hors, mode, fenetre)
    lignes.sort(key=lambda kv: kv[0], reverse=True)
    return [texte for _, texte in lignes[: int(settings.agent.memoire__changements_max)]]


# ── Le bloc complet ──────────────────────────────────────────────────────────────


def memoire_noyau(
    journal: dict, entrees, maintenant: datetime | None, person_id: str | None = None
) -> list[str]:
    """Le bloc permanent, en lignes prêtes pour le gabarit.

    Un bloc vide est ABSENT et non présent avec un titre : un titre sans contenu dit au modèle
    qu'il devrait y avoir quelque chose, et l'invite à le combler.
    """
    sections = (
        ("Mes habitudes", bloc_habitudes(journal or {})),
        ("Ce que je sais", bloc_connaissances(entrees or [])),
        ("Ce qui a changé récemment", bloc_changements(entrees or [], maintenant, person_id)),
    )
    sortie: list[str] = []
    for titre, lignes in sections:
        if not lignes:
            continue
        sortie.append(titre)
        sortie.extend(f"- {ligne}" for ligne in lignes)
    return sortie
