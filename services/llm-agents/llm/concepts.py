"""Consolidation des concepts — ticket 071, lot 3.

Un concept ne s'empile plus : il se **corrige**. Il se confirme, se précise ou se voit
contredire, avec un compteur derrière. C'est le principe d'extraction-puis-mise-à-jour de
Mem0 (Chhikara et al., 2025) et de l'évolution des notes d'A-MEM (Xu et al., 2025).

**Il n'y a pas de suppression**, et c'est une divergence assumée avec Mem0, dont le jeu
d'opérations comporte un `DELETE`. Un concept dépassé est marqué et daté, jamais supprimé : la
raison est scientifique et non technique, cette mise à l'écart datée **est** la trace lisible
d'un changement d'habitude, et c'est l'observable que l'expérience d'hystérésis cherche.

**Un concept ne s'oublie pas à l'horloge.** Qu'une ligne sature les jours de pluie entre 8 h et
8 h 30 ne devient pas faux parce que dix jours ont passé. C'est la séparation de Tulving (1972)
entre épisodique et sémantique, et l'architecture à deux systèmes de McClelland, McNaughton &
O'Reilly (1995).
"""

from __future__ import annotations

from loguru import logger

from settings import settings

# Les quatre opérations, dans le vocabulaire du modèle (anglais) et dans celui de la
# spécification (français). Correspondance avec Mem0 : `creer` = ADD, `preciser` = UPDATE,
# `confirmer` = NOOP plus un compteur, `contredire` remplace DELETE.
CREER = "creer"
CONFIRMER = "confirmer"
PRECISER = "preciser"
CONTREDIRE = "contredire"
OPERATIONS = (CREER, CONFIRMER, PRECISER, CONTREDIRE)

ALIAS_OPERATIONS: dict[str, str] = {
    "create": CREER,
    "confirm": CONFIRMER,
    "refine": PRECISER,
    "update": PRECISER,
    "contradict": CONTREDIRE,
}

# Nombre de concepts d'un même panier montrés au modèle. Le panier « sans mode » rassemblerait
# sinon tous les concepts généraux d'un motif, et le montrer entier gonflerait le prompt.
CONCEPTS_MONTRES_PAR_PANIER = 5


def normaliser_operation(valeur: str | None) -> str:
    """Opération demandée par le modèle, ramenée au vocabulaire interne.

    Une valeur inconnue ou absente retombe sur `creer` : c'est le repli le moins destructeur —
    on ajoute un concept plutôt que de toucher un existant sur la foi d'une réponse qu'on n'a
    pas comprise. Mais elle laisse une TRACE, sans quoi un modèle qui ne respecterait jamais le
    contrat passerait inaperçu.
    """
    if not valeur:
        return CREER
    clef = str(valeur).strip().lower()
    clef = ALIAS_OPERATIONS.get(clef, clef)
    if clef not in OPERATIONS:
        logger.warning(
            f"[concepts] opération INCONNUE « {valeur} » — hors de {OPERATIONS} ; "
            f"repli sur « {CREER} », rien n'est modifié dans l'existant"
        )
        return CREER
    return clef


def panier_de(axe_objet: str | None, axe_motif: str | None) -> tuple:
    """Clé du panier : le couple mode-motif.

    Le panier désigne un petit ENSEMBLE de candidats, jamais un emplacement unique. Une identité
    unique par couple condamnerait l'agent à une seule pensée par mode et par motif, chaque
    concept nouveau détruisant le précédent : un agent pendulaire à vélo perdrait « la piste du
    canal est protégée » en apprenant « l'abri à vélos sature à 8 h 30 ».
    """
    return (axe_objet, axe_motif)


def confiance(observations: int, contre_exemples: int) -> float:
    """Règle de succession de Laplace (1814), pour qu'une observation unique ne vaille pas
    certitude.

    Un concept jamais observé vaut 0,5 : ni cru, ni écarté.
    """
    obs = max(0, int(observations or 0))
    contre = max(0, int(contre_exemples or 0))
    return (obs + 1) / (obs + contre + 2)


def est_hors_service(observations: int, contre_exemples: int) -> bool:
    """Le concept cesse-t-il d'être servi au modèle ?

    Lecture exacte du seuil sous Laplace : le concept a été contredit **plus souvent** qu'il n'a
    été confirmé. Il n'est PAS supprimé pour autant — sa mise à l'écart datée est l'observable
    que l'expérience cherche.

    ⚠ C'est la troisième exception à la règle de non-exclusion du lot 2, avec l'identité de
    l'agent et la fenêtre d'âge. Elle est écrite comme une exception et non fondue dans la
    règle : la formulation « rien ne filtre » se transporte à l'article, elle y deviendrait
    fausse sans mention.
    """
    return confiance(observations, contre_exemples) < float(
        settings.agent.memoire__confiance_seuil_service
    )


def est_depasse(observations: int, contre_exemples: int) -> bool:
    """Le concept est-il dépassé ? DEUX conditions, pas une.

    Au moins trois contradictions **et** plus de contradictions que de confirmations. Ni trois
    contradictions contre vingt confirmations, ni une majorité de contradictions sur deux
    observations.
    """
    return int(contre_exemples or 0) >= int(
        settings.agent.memoire__contre_exemples_seuil
    ) and est_hors_service(observations, contre_exemples)
