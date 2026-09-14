"""Gravité d'un souvenir — ticket 071, lot 1.

Un souvenir n'est plus seulement daté, il est **qualifié**. Sa gravité décide de sa durée de
vie et, au lot 2, de son poids au rappel.

Deux sources, à deux endroits, jamais concurrentes :

- les **entrées brutes** de mémoire courte reçoivent une gravité DÉTERMINISTE, calculée depuis
  ce que la simulation mesure — elle ne coûte rien et elle est objective ;
- les **concepts** reçoivent un niveau nommé JUGÉ par le modèle, demandé à l'intérieur de la
  réflexion qui a déjà lieu, donc sans appel supplémentaire.

Et une règle de sécurité qui les arbitre : le fait mesuré l'emporte toujours sur le jugement.

Ce module est PUR : il ne lit que la configuration, jamais l'horloge, jamais le disque, jamais
le réseau. C'est ce qui le rend testable sans simulateur ni modèle.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from loguru import logger

from settings import settings

# ── Les cinq échelons ────────────────────────────────────────────────────────────
# Ancrés par une CONSÉQUENCE OBSERVABLE et non par une intensité ressentie. C'est un
# raffinement de Park et al. (2023), qui demandent un entier de 1 à 10 en n'ancrant que les
# deux extrémités. L'argument est la comparabilité : il faut pouvoir peser un choc du jour 2
# contre un trajet ordinaire du jour 5, donc une valeur ABSOLUE et non un rang.
# Les ancres textuelles vivent dans le gabarit de `stm_reflection` ; ici, leurs valeurs.
NIVEAUX: dict[str, float] = {
    "anodin": 0.10,
    "notable": 0.30,
    "genant": 0.50,
    "grave": 0.75,
    "marquant": 1.00,
}

# Le dispositif s'adresse au modèle en ANGLAIS (ticket 074) : le gabarit demande donc les
# échelons sous leur libellé anglais. Le vocabulaire canonique de la spécification reste le
# français — c'est la langue dans laquelle l'échelle a été définie et discutée — et ces alias
# ramènent l'un à l'autre. Les deux sont acceptés en entrée : un modèle qui répondrait dans
# l'autre langue est compris plutôt que rejeté.
ALIAS_NIVEAUX: dict[str, str] = {
    "negligible": "anodin",
    "noticeable": "notable",
    "inconvenient": "genant",
    "serious": "grave",
    "memorable": "marquant",
}

# Ancres textuelles, telles qu'elles sont posées dans le gabarit de réflexion. Chaque échelon
# est ancré par une CONSÉQUENCE OBSERVABLE, et non par une intensité ressentie : c'est ce qui
# rend la valeur comparable d'un agent et d'un jour à l'autre, là où un rang ne l'est pas.
ANCRES: dict[str, str] = {
    "anodin": "Everything went as I had planned.",
    "notable": "A noticeable deviation, with no consequence for the rest of my day.",
    "genant": "It cost me time, or forced me to shift a schedule.",
    "grave": "It made me miss something, or put me in difficulty.",
    "marquant": "I will remember this in a month; it changes how I travel.",
}

# ── Poids de la gravité déterministe ─────────────────────────────────────────────
POIDS_RETARD = 0.50
POIDS_CORRESPONDANCE_RATEE = 0.20
POIDS_INCIDENT_RESEAU = 0.20
POIDS_MODE_CONTRAINT = 0.10

# ⚠ Composantes SANS SOURCE aujourd'hui. `experiences/experience.py` déclare un format
# d'événement `incident`, mais refuse l'exécution : GAMA ne les joue pas encore. La chaîne est
# posée de bout en bout — paramètre, détail, compteur, journal — pour qu'il n'y ait qu'une
# source à brancher le jour venu, et non une formule à rouvrir.
#
# ⚠⚠ Une composante sans observable contribue ZÉRO, et zéro est exactement la valeur d'un
# trajet parfait. Sans déclaration explicite, la gravité serait sous-estimée sans qu'aucun
# symptôme n'apparaisse. D'où `journal_des_composantes()`, appelé au démarrage.
# Les trois autres composantes ne sont PAS repondérées pour compenser : repondérer changerait
# l'échelle de gravité en silence.
COMPOSANTES_INACTIVES: tuple[str, ...] = ("incident_reseau",)

# Valeurs de la « contrainte de chaîne » qui constituent un CHANGEMENT DE MODE CONTRAINT.
# `retour_force` : l'agent rentre avec ce qu'il a pris, ses options sont restreintes au mode
# du véhicule garé. `sortie_bloquee` : il ne peut pas partir dans le mode qu'il aurait choisi.
# `passager` en est volontairement EXCLU : être passager d'un autre membre du ménage est un
# arrangement, pas une dégradation subie — le compter dégraderait la mesure.
CONTRAINTES_MODE_FORCE: tuple[str, ...] = ("retour_force", "sortie_bloquee")


@dataclass(frozen=True)
class DetailGravite:
    """Contribution de chaque composante, pour que l'instrumentation dise laquelle a joué."""

    retard: float = 0.0
    correspondance_ratee: float = 0.0
    incident_reseau: float = 0.0
    mode_contraint: float = 0.0

    def total(self) -> float:
        return self.retard + self.correspondance_ratee + self.incident_reseau + self.mode_contraint

    def composantes_actives(self) -> tuple[str, ...]:
        """Celles qui ont réellement contribué sur CETTE entrée."""
        return tuple(
            nom
            for nom in ("retard", "correspondance_ratee", "incident_reseau", "mode_contraint")
            if getattr(self, nom) > 0.0
        )


def gravite_deterministe(
    retard_s: float = 0.0,
    correspondance_ratee: bool = False,
    incident_reseau: bool = False,
    mode_contraint: bool = False,
) -> tuple[float, DetailGravite]:
    """Gravité d'une entrée brute, depuis ce que la simulation mesure. Bornée sur [0, 1].

    Apport propre au dispositif : ni Park et al. ni Vu et al. ne disposent d'un simulateur qui
    mesure le retard subi, et Park et al. (2023, § 4.1) notent qu'« il existe beaucoup
    d'implémentations possibles d'un score d'importance ».

    Une arrivée EN AVANCE n'est pas un bonus : un retard négatif vaut zéro, jamais une gravité
    négative qui viendrait compenser un incident réel dans la même entrée.
    """
    retard_ref = float(settings.agent.memoire__retard_ref_s)
    if retard_ref > 0:
        part_retard = POIDS_RETARD * min(max(float(retard_s), 0.0) / retard_ref, 1.0)
    else:
        # Un `RETARD_REF` nul ou négatif rendrait la composante indéfinie. On ne devine pas :
        # elle vaut zéro ET on le dit, sans quoi le retard cesserait de compter en silence.
        logger.error(
            f"[ALARME] memoire__retard_ref_s = {retard_ref} : la composante de retard de la "
            f"gravité est INACTIVE — toute gravité de retard vaudra zéro"
        )
        part_retard = 0.0

    detail = DetailGravite(
        retard=part_retard,
        correspondance_ratee=POIDS_CORRESPONDANCE_RATEE * bool(correspondance_ratee),
        incident_reseau=POIDS_INCIDENT_RESEAU * bool(incident_reseau),
        mode_contraint=POIDS_MODE_CONTRAINT * bool(mode_contraint),
    )
    return borne_0_1(detail.total()), detail


def borne_0_1(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def ecart_de_rang(n_niveau: int, rang: int) -> float:
    """Départage à l'intérieur d'un même niveau : +1 au premier, -1 au dernier, 0 au milieu.

    Le rang ne sert QU'À CELA. Demander au modèle de classer ses concepts entre eux produit un
    ordre fiable, mais relatif au lot : sur une journée entièrement banale, le moins banal
    décrocherait la note maximale. L'ordre n'écarte donc les concepts que de ±0,05.

    ⚠ Corrigé le 2026-09-14 (ticket 071, specs/ticket_071/tests_lot1.md § 9) : la formule
    d'origine, `2 × (n - rang) / max(n - 1, 1) - 1`, valait **-1** pour un concept SEUL dans son
    niveau, qu'elle pénalisait donc de 0,05 — alors que c'est le cas le plus courant et qu'il n'y
    a rien à départager quand il n'y a qu'un candidat.
    """
    if n_niveau <= 1:
        return 0.0
    rang = max(1, min(int(rang), int(n_niveau)))
    return 2.0 * (n_niveau - rang) / (n_niveau - 1) - 1.0


def gravite_jugee(niveau: str | None, n_niveau: int = 1, rang: int = 1) -> float | None:
    """Gravité d'un concept d'après le niveau nommé rendu par le modèle, ou `None`.

    `None` quand le modèle répond hors grille ou ne répond pas : le concept retombe alors sur la
    seule gravité déterministe de son groupe (cf. `gravite_concept`). Une réponse hors grille ne
    doit pas faire perdre la réflexion entière, mais elle doit laisser une TRACE — c'est ce qui
    permettra de voir, sur un run, qu'un modèle ne respecte pas l'échelle.

    ⚠ Bornée sur [0, 1] après départage : sans cette borne, un `marquant` premier de trois
    valait 1,05 et sa durée de vie passait de 19,60 à 20,44 jours.
    """
    if niveau is None or not str(niveau).strip():
        logger.warning(
            "[gravite] niveau de gravité ABSENT dans la réponse du modèle — le concept retombe "
            "sur la gravité déterministe de son groupe"
        )
        return None
    clef = str(niveau).strip().lower()
    clef = ALIAS_NIVEAUX.get(clef, clef)
    if clef not in NIVEAUX:
        logger.warning(
            f"[gravite] niveau de gravité INCONNU « {niveau} » — hors des cinq échelons "
            f"{sorted(ALIAS_NIVEAUX)} ; le concept retombe sur la gravité déterministe "
            f"de son groupe"
        )
        return None
    return borne_0_1(NIVEAUX[clef] + 0.05 * ecart_de_rang(n_niveau, rang))


def gravite_concept(i_llm: float | None, i_det_groupe: float = 0.0) -> float:
    """Règle de sécurité, NON NÉGOCIABLE : `I = max(I_llm, max(I_det du groupe consommé))`.

    Un modèle qui sous-estime un incident de quarante-cinq minutes ne peut pas le dégrader : le
    fait mesuré l'emporte toujours sur le jugement.

    ⚠ La protection est ASYMÉTRIQUE, et c'est assumé : elle ne joue que vers le bas. Un modèle
    qui SURESTIME n'est borné par rien d'autre que le plafond de 1,0. Un plafond symétrique
    n'est pas spécifié et n'est pas appliqué ici.
    """
    plancher = borne_0_1(i_det_groupe)
    if i_llm is None:
        return plancher
    return max(borne_0_1(i_llm), plancher)


# ── Durée de vie ─────────────────────────────────────────────────────────────────


def force_initiale(importance: float) -> float:
    """Constante de temps de l'oubli, en jours, fixée à l'écriture selon la gravité.

    `force = min(S0 × (1 + k × I), FORCE_MAX)`. La forme `exp(-Δt / force)` et la force qui
    croît au rappel viennent de MemoryBank (Zhong et al., 2024), qui reprend la courbe d'oubli
    d'Ebbinghaus (1885). La modulation par la gravité ne vient PAS d'ACT-R, dont l'activation de
    base n'encode que récence et fréquence : elle s'appuie sur la mémoire émotionnelle
    (McGaugh, 2004).

    Le plafond s'applique DÈS L'ÉCRITURE et pas seulement au renforcement : au point de
    sensibilité publié (`S0 = 8,3` j, Park et al.), un souvenir `marquant` partirait sinon à
    58 jours.
    """
    s0 = float(settings.agent.long_term_retrieval__force_base_jours)
    k = float(settings.agent.memoire__force_k_importance)
    plafond = float(settings.agent.memoire__force_max_jours)
    return min(s0 * (1.0 + k * borne_0_1(importance)), plafond)


def force_apres_rappel(force: float | None) -> float:
    """`force ← min(force + δ, FORCE_MAX)`. ADDITIF, et c'est un choix.

    Un facteur multiplicatif (× 1,15) saturait au plafond en dix-sept rappels tout ce qui est
    rappelé souvent. Chaque rappel ajoute un jour : un trajet banal atteint le plafond en
    vingt-huit rappels, un souvenir `marquant` en onze. C'est aussi plus proche de
    l'apprentissage de base d'ACT-R, où la fréquence a des rendements décroissants.
    """
    delta = float(settings.agent.memoire__force_delta_rappel_jours)
    plafond = float(settings.agent.memoire__force_max_jours)
    depart = float(settings.agent.long_term_retrieval__force_base_jours) if force is None else float(force)
    return min(depart + delta, plafond)


def poids_temporel(delta_jours: float, force: float | None) -> float:
    """`exp(-Δt / force)`, où Δt se compte depuis le DERNIER RAPPEL et non depuis l'écriture.

    Comme chez Park et al. (2023, § 4.1), dont la récence décroît « depuis le dernier rappel du
    souvenir », et chez MemoryBank. Une `force` absente — entrée écrite avant ce lot — retombe
    sur la constante de temps par défaut plutôt que de valoir zéro.
    """
    f = float(settings.agent.long_term_retrieval__force_base_jours) if force is None else float(force)
    if f <= 0:
        return 0.0
    return math.exp(-max(0.0, float(delta_jours)) / f)


def est_purgeable(delta_jours: float, force: float | None) -> bool:
    """Une entrée ÉPISODIQUE se purge quand son poids passe sous le seuil, soit ~4,6 × force.

    Treize jours pour un trajet banal jamais rappelé, quatre-vingt-onze pour un `marquant` :
    donc jamais dans un run. Remplace les seuils par type du nettoyage en service, qui
    emportaient un souvenir marquant de trente et un jours avec les trajets ordinaires.

    Les CONCEPTS ne passent jamais par ici : ils ne s'oublient pas à l'horloge (lot 3).
    """
    return poids_temporel(delta_jours, force) < float(settings.agent.memoire__purge_seuil_poids)


# ── Déclaration de ce qui est actif ──────────────────────────────────────────────


def journal_des_composantes() -> str:
    """Ligne de démarrage nommant les composantes de `I_det` actives et inactives.

    Un dispositif muet ne permet pas de distinguer « la composante vaut zéro parce que le trajet
    s'est bien passé » de « la composante vaut zéro parce que rien ne l'alimente ».
    """
    toutes = {
        "retard": POIDS_RETARD,
        "correspondance_ratee": POIDS_CORRESPONDANCE_RATEE,
        "incident_reseau": POIDS_INCIDENT_RESEAU,
        "mode_contraint": POIDS_MODE_CONTRAINT,
    }
    actives = [f"{n} ({p:.2f})" for n, p in toutes.items() if n not in COMPOSANTES_INACTIVES]
    inactives = [f"{n} ({p:.2f})" for n, p in toutes.items() if n in COMPOSANTES_INACTIVES]
    ligne = (
        f"[gravite] composantes de la gravité déterministe — ACTIVES : {', '.join(actives)}"
        f" | INACTIVES (aucune source, contribuent 0) : {', '.join(inactives) or 'aucune'}"
        f" | RETARD_REF = {settings.agent.memoire__retard_ref_s} s"
        f" | seuil de choc = {settings.agent.memoire__importance_choc}"
    )
    logger.info(ligne)
    if inactives:
        logger.warning(
            f"[gravite] {len(inactives)} composante(s) de gravité sans source : la gravité est "
            f"MINORÉE tant que GAMA ne les produit pas. Les autres ne sont pas repondérées."
        )
    return ligne
