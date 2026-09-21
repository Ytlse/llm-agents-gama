"""Tests du support commun de l'entropie croisée (audit_unitaire_058.py).

Le défaut corrigé le 2026-09-21 : chaque décideur était noté sur les décisions où sa propre
distribution laissait une masse non nulle au mode déclaré, c'est-à-dire sur un ensemble qu'il
choisissait lui-même en tranchant plus ou moins dur. Ces tests fixent le comportement attendu
pour qu'il ne revienne pas.
"""

from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "scripts" / "progedo_logit"))

from audit_unitaire_058 import support_commun

# Quatre décisions, quatre classes (bike, car, transit, walk). Le mode déclaré est `car`,
# d'indice 1, partout sauf en d4 où il est `walk`, d'indice 3.
PRUDENT = {  # laisse toujours une masse au mode déclaré
    "d1": (1, [0.1, 0.6, 0.2, 0.1], 1.0),
    "d2": (1, [0.2, 0.5, 0.2, 0.1], 1.0),
    "d3": (1, [0.3, 0.4, 0.2, 0.1], 1.0),
    "d4": (3, [0.2, 0.3, 0.2, 0.3], 1.0),
}
TRANCHANT = {  # met zéro sur le mode déclaré en d3 et d4 : ses deux pires décisions
    "d1": (1, [0.0, 1.0, 0.0, 0.0], 1.0),
    "d2": (1, [0.1, 0.9, 0.0, 0.0], 1.0),
    "d3": (1, [1.0, 0.0, 0.0, 0.0], 1.0),
    "d4": (3, [0.0, 1.0, 0.0, 0.0], 1.0),
}
PARTIEL = {"d1": (1, [0.25, 0.25, 0.25, 0.25], 1.0)}  # ne couvre pas le support


def resultats_vides(*noms: str) -> dict[str, dict]:
    return {nom: {"etat_execution": "terminee"} for nom in noms}


def test_le_support_est_l_intersection_pas_le_sous_ensemble_de_chacun():
    """Les décisions que le tranchant met à zéro sortent pour TOUT LE MONDE, pas pour lui seul."""
    resultats = resultats_vides("prudent", "tranchant")
    support = support_commun({"prudent": PRUDENT, "tranchant": TRANCHANT}, resultats)

    assert support == {"d1", "d2"}
    assert resultats["prudent"]["support_commun_notes"] == 2
    assert resultats["tranchant"]["support_commun_notes"] == 2


def test_les_deux_decideurs_sont_notes_sur_le_meme_nombre_de_decisions():
    """Le défaut d'origine : 5 923 décisions contre 6 588, comparées comme si de rien n'était."""
    resultats = resultats_vides("prudent", "tranchant")
    support_commun({"prudent": PRUDENT, "tranchant": TRANCHANT}, resultats)

    assert (
        resultats["prudent"]["support_commun_notes"]
        == resultats["tranchant"]["support_commun_notes"]
    )
    assert resultats["prudent"]["cel_weighted_support_commun"] is not None
    assert resultats["tranchant"]["cel_weighted_support_commun"] is not None


def test_un_plancher_ne_definit_pas_le_support_mais_y_est_note():
    """`alea` laisserait des milliers de zéros : il raboterait l'intersection pour tout le monde."""
    notables = {"prudent": PRUDENT, "alea": TRANCHANT}
    resultats = resultats_vides("prudent", "alea")
    support = support_commun(notables, resultats)

    assert support == {"d1", "d2", "d3", "d4"}  # seul `prudent` définit
    assert resultats["alea"]["cel_weighted_support_commun"] is not None


def test_un_decideur_qui_ne_couvre_pas_le_support_ne_recoit_pas_de_valeur():
    """Le noter sur ce qu'il couvre le remettrait sur un troisième sous-ensemble.

    Un définisseur couvre toujours le support, l'intersection étant prise sur ses propres
    décisions. Seul un non-définisseur peut lui manquer : c'est le cas du hasard uniforme sur
    le jeu réel, à qui 74 décisions du support commun font défaut.
    """
    notables = {"prudent": PRUDENT, "tranchant": TRANCHANT, "alea": PARTIEL}
    resultats = resultats_vides("prudent", "tranchant", "alea")
    support = support_commun(notables, resultats)

    assert support == {"d1", "d2"}
    assert resultats["alea"]["cel_weighted_support_commun"] is None
    assert "support_commun_motif" in resultats["alea"]


def test_une_execution_non_terminee_ne_definit_pas_le_support():
    """Une exécution partielle ne couvre qu'un début d'échantillon : elle ne borne personne."""
    notables = {"prudent": PRUDENT, "tranchant": TRANCHANT}
    resultats = resultats_vides("prudent")
    resultats["tranchant"] = {"etat_execution": "en_cours"}
    support = support_commun(notables, resultats)

    assert support == {"d1", "d2", "d3", "d4"}
