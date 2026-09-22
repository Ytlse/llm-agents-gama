"""Ticket 059, lot 3 — le dépouillement de l'étage 1.

Contrat : `specs/ticket_059/tests.md`, règles S1 à S5. Deux gardes y sont vérifiées plus que le
reste, parce que ce sont elles qui mentent quand elles manquent :

- **la vacuité** — un mode absent rend « non concluant », jamais 0,0 ;
- **le bruit** — un écart plus petit que le plancher du décideur n'est pas un effet.

Tout est PUR : aucun modèle, aucun appel réseau, aucun corpus requis.

Lancement :
    services/llm-agents/.venv/bin/python -m pytest scripts/tests/test_059_scoring.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from scripts.analysis.presse.grille import charger_grille  # noqa: E402
from scripts.analysis.presse.scoring import (  # noqa: E402
    EFFECTIF_MIN_PAR_MODE,
    NON_CONCLUANT,
    intervalle_groupe_par_evenement,
    accord_de_signe,
    ecart_apparie,
    kappa_pondere,
    signes_observes,
)

GRILLE = RACINE / "docs" / "paper" / "sources" / "actualites" / "grille_signes.yaml"


def _decisions(n: int, mode: str, part: float) -> dict[str, str]:
    """n déplacements dont `part` portent `mode`, les autres un mode neutre."""
    combien = round(n * part)
    return {f"d{i}": (mode if i < combien else "autre") for i in range(n)}


# ── L'écart apparié ─────────────────────────────────────────────────────────────────────


def test_S1_l_ecart_se_calcule_sur_l_intersection_des_deux_conditions():
    """Un déplacement qu'une seule condition porte est écarté, jamais complété par un défaut."""
    ref = _decisions(60, "tc", 0.5)
    con = dict(list(_decisions(60, "tc", 0.5).items())[:40])
    e = ecart_apparie(ref, con, article="a13", mode="tc")
    assert e.n_apparies == 40


def test_S4_un_effectif_trop_faible_rend_non_concluant_et_pas_zero():
    """Dans ce dépôt, l'absence de mesure produit le score parfait. Ce test l'interdit ici."""
    petit = _decisions(EFFECTIF_MIN_PAR_MODE - 1, "tc", 0.5)
    e = ecart_apparie(petit, petit, article="a13", mode="tc")
    assert e.verdict == NON_CONCLUANT
    assert e.ecart is None, "un écart non mesurable ne vaut pas 0,0"


def test_l_ecart_a_le_signe_et_l_amplitude_attendus():
    ref = _decisions(100, "tc", 0.80)
    con = _decisions(100, "tc", 0.55)
    e = ecart_apparie(ref, con, article="a13", mode="tc")
    assert e.ecart == pytest.approx(-0.25)


# ── Le plancher de bruit ────────────────────────────────────────────────────────────────


def test_S_un_ecart_dans_le_bruit_compte_pour_zero():
    """Appeler '+' un écart plus petit que le bruit reviendrait à scorer du hasard."""
    ref, con = _decisions(100, "tc", 0.50), _decisions(100, "tc", 0.52)
    e = ecart_apparie(ref, con, article="a13", mode="tc")
    assert signes_observes([e], plancher_de_bruit=0.032)[("a13", "tc")] == "0"
    assert signes_observes([e], plancher_de_bruit=0.005)[("a13", "tc")] == "+"


def test_S_le_plancher_de_bruit_n_a_pas_de_valeur_par_defaut():
    """Un défaut se ferait oublier — et le plancher mesuré au 095 n'est pas nul."""
    import inspect

    params = inspect.signature(signes_observes).parameters
    assert params["plancher_de_bruit"].default is inspect.Parameter.empty


def test_S_un_ecart_non_lisible_donne_un_signe_absent_et_non_zero():
    petit = _decisions(5, "tc", 0.5)
    e = ecart_apparie(petit, petit, article="a13", mode="tc")
    assert signes_observes([e], plancher_de_bruit=0.032)[("a13", "tc")] is None


# ── Le taux d'accord de signe ───────────────────────────────────────────────────────────


def test_S3_le_binomial_est_RETIRE_et_lincertitude_se_groupe_par_evenement():
    """Le chapitre posait la barre à quinze concordances sur vingt. Elle est retirée.

    Le binomial supposait vingt tirages indépendants. Ils ne le sont pas : les parts modales
    d'un même événement somment à un, donc un seul comportement produit mécaniquement
    plusieurs concordances. L'incertitude passe par un rééchantillonnage GROUPÉ par événement.
    """
    grille = charger_grille(GRILLE)
    parfait = {(c.article, c.mode): c.signe for c in grille.cellules}
    a = accord_de_signe(grille, parfait)
    assert a.p_binomial is None, "le champ reste, vide, pour que les rapports se relisent"
    assert a.intervalle is not None
    assert a.intervalle == (1.0, 1.0), "un accord parfait sur tous les articles reste parfait"


def test_S3_lintervalle_reechantillonne_les_ARTICLES_et_non_les_cellules():
    """Quatre cellules d'un même article voyagent en bloc : c'est tout l'objet du groupement."""
    # Cinq articles, quatre cellules chacun. Un seul article discordant sur les quatre.
    concordances = [
        (f"a{i}", i != 0) for i in range(5) for _ in range(4)
    ]
    bas, haut = intervalle_groupe_par_evenement(concordances)
    # Taux observé : 16/20 = 0,80. Groupé par article, l'intervalle vaut [0,40 ; 1,00].
    assert (bas, haut) == (0.4, 1.0)

    # ⚠ LA COMPARAISON QUI JUSTIFIE TOUT : en rééchantillonnant les CELLULES comme si elles
    # étaient indépendantes — ce que le binomial supposait — le même jeu rend [0,60 ; 0,95].
    # L'intervalle se resserre de moitié sans qu'aucune donnée de plus ne soit entrée. Cette
    # précision-là est fabriquée par l'hypothèse, pas mesurée.
    import random as _r

    plats = [c for _a, c in concordances]
    alea = _r.Random(59)
    taux = sorted(
        sum(alea.choices(plats, k=len(plats))) / len(plats) for _ in range(2000)
    )
    faux_bas, faux_haut = round(taux[49], 2), round(taux[-50], 2)
    assert (faux_bas, faux_haut) == (0.6, 0.95)
    assert (haut - bas) > (faux_haut - faux_bas), (
        "grouper par événement doit ÉLARGIR l'intervalle : c'est la précision fabriquée par "
        "l'hypothèse d'indépendance qu'on rend"
    )


def test_S3_lintervalle_est_reproductible_et_refuse_un_seul_evenement():
    concordances = [("a1", True), ("a1", False), ("a2", True), ("a2", True)]
    assert intervalle_groupe_par_evenement(concordances) == intervalle_groupe_par_evenement(
        concordances
    ), "graine fixe : deux dépouillements du même résultat doivent coïncider"
    assert intervalle_groupe_par_evenement([("a1", True), ("a1", False)]) is None, (
        "un intervalle tiré sur un seul groupe ne rééchantillonne rien"
    )


def test_S3_l_accord_porte_sur_la_grille_gelee():
    grille = charger_grille(GRILLE)
    parfait = {(c.article, c.mode): c.signe for c in grille.cellules}
    a = accord_de_signe(grille, parfait)
    assert a.concordants == 20 and a.lisibles == 20 and a.non_lisibles == 0
    assert a.taux == 1.0


def test_S3_une_cellule_non_lisible_sort_du_denominateur():
    """La compter comme discordance ferait porter à l'effet la faute de l'échantillon."""
    grille = charger_grille(GRILLE)
    observes = {(c.article, c.mode): c.signe for c in grille.cellules}
    observes[("a09_vent_autan", "velo")] = None
    a = accord_de_signe(grille, observes)
    assert a.lisibles == 19 and a.non_lisibles == 1
    assert a.concordants == 19


def test_S3_predire_l_absence_d_effet_et_l_observer_est_une_concordance():
    grille = charger_grille(GRILLE)
    observes = {(c.article, c.mode): c.signe for c in grille.cellules}
    assert observes[("a18_la_machine", "marche")] == "0"
    assert accord_de_signe(grille, observes).concordants == 20


def test_S4_aucune_cellule_lisible_rend_non_concluant():
    grille = charger_grille(GRILLE)
    a = accord_de_signe(grille, {(c.article, c.mode): None for c in grille.cellules})
    assert a.verdict == NON_CONCLUANT
    assert a.taux is None, "un taux sur zéro cellule ne vaut pas 0,0"


# ── Le kappa pondéré ────────────────────────────────────────────────────────────────────


def test_le_kappa_vaut_un_sur_un_accord_parfait():
    grille = charger_grille(GRILLE)
    parfait = {(c.article, c.mode): c.intensite for c in grille.cellules}
    assert kappa_pondere(grille, parfait) == pytest.approx(1.0)


def test_le_kappa_rend_non_concluant_sous_dix_cellules():
    grille = charger_grille(GRILLE)
    observees: dict = {(c.article, c.mode): None for c in grille.cellules}
    for c in list(grille.cellules)[:8]:
        observees[(c.article, c.mode)] = c.intensite
    assert kappa_pondere(grille, observees) == NON_CONCLUANT


def test_le_kappa_rend_non_concluant_sur_une_serie_constante():
    """Un kappa sur une série constante vaut 0 par construction, et ce zéro ne dit rien."""
    grille = charger_grille(GRILLE)
    plat = {(c.article, c.mode): 2 for c in grille.cellules}
    assert kappa_pondere(grille, plat) == NON_CONCLUANT
