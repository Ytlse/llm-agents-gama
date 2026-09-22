"""Le garde-fou du jugement, sans un seul appel — ticket 095.

Le garde-fou décide si une campagne de cinquante jours part ou non. Sa logique de verdict doit
donc être exercée sans modèle : un garde-fou qu'on ne teste qu'en le lançant coûte trente appels
à chaque vérification, et on cesse de le vérifier.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

RACINE = Path(__file__).resolve().parents[2]
for chemin in (str(RACINE), str(RACINE / "services" / "llm-agents")):
    if chemin not in sys.path:
        sys.path.insert(0, chemin)

from scripts.experiment.banc_fonctionnel.garde_fou_jugement import (  # noqa: E402
    BRAS,
    charger_grille,
    verdict,
)

GRILLE = RACINE / "specs" / "ticket_095" / "grille_attendus.yaml"
SEUILS = {"part_hors_plage_max": 0.20, "echelons_distincts_min": 3}


def _bilan(**kw):
    base = {
        "appels": 32, "sans_reponse": 0,
        "part_hors_plage_aveugle": 0.0, "part_hors_plage_deja_vue": 0.0,
        "echelons_distincts": 3, "bras_dans_l_ordre_predit": True, "ordre_detail": [],
        "bras": {"c2_crevaison": "notable", "c6_voiture_suspecte": "genant",
                 "c3_panne_reseau": "grave"},
    }
    return base | kw


# ── La grille livrée ────────────────────────────────────────────────────────────────────────
def test_la_grille_du_depot_est_complete_et_lisible():
    grille, seuils, marche = charger_grille(GRILLE)
    assert len(grille) == 9, "cinq articles, les trois bras, et la sonde de l'orage"
    assert set(marche) <= set(grille), "les bras de la marche doivent être déclarés"
    assert len(marche) >= 3, "une marche de moins de trois bras ne se teste pas"
    assert "c5_orage_grele" in grille and "c5_orage_grele" not in marche, (
        "l'orage est mesuré mais ne fait pas partie de la marche ordonnée : il la traverse"
    )
    assert seuils["echelons_distincts_min"] >= 3


def test_chaque_plage_est_une_plage_d_echelons_connus():
    from llm.gravite import NIVEAUX

    grille, _, marche = charger_grille(GRILLE)
    for nom, e in grille.items():
        assert e["attendu"], nom
        assert set(e["attendu"]) <= set(NIVEAUX), f"{nom} : échelon inconnu"
        assert e["motif"].strip(), f"{nom} : une plage sans motif ne se relit pas"
        assert isinstance(e["deja_vu"], bool), f"{nom} : `deja_vu` doit être déclaré"


def test_la_marche_predit_une_progression_et_non_un_plateau():
    """Sans ordre prédit, le test ne pourrait rien réfuter : il constaterait ce qui sort.

    La marche n'a PAS à être strictement croissante : deux bras que l'auteur ne sait pas
    départager portent la même plage, et on ne demande pas à la mesure de trancher ce que
    personne n'a prédit. Ce qui est exigé, c'est qu'elle progresse d'un bout à l'autre et ne
    redescende jamais.
    """
    from llm.gravite import NIVEAUX

    rangs = {n: i for i, n in enumerate(NIVEAUX)}
    grille, _, marche = charger_grille(GRILLE)
    bornes = [
        (min(rangs[x] for x in grille[b]["attendu"]), max(rangs[x] for x in grille[b]["attendu"]))
        for b in marche
    ]
    for (b1, h1), (b2, h2) in zip(bornes, bornes[1:]):
        assert b2 >= b1 and h2 >= h1, "la marche ne doit jamais redescendre"
    assert bornes[0][1] < bornes[-1][1], "le dernier bras doit être prédit au-dessus du premier"


def test_au_moins_deux_bras_sont_des_predictions_aveugles():
    """Une grille entièrement écrite après coup ne garde rien — c'est le point faible connu."""
    grille, _, marche = charger_grille(GRILLE)
    aveugles = [b for b in marche if not grille[b]["deja_vu"]]
    assert len(aveugles) >= 2, f"seuls {aveugles} sont aveugles"


def test_une_marche_nommant_un_texte_absent_arrete_le_test(tmp_path):
    """L'ordre porterait sur un texte qu'on ne mesure pas."""
    p = tmp_path / "g.yaml"
    p.write_text(yaml.safe_dump({
        "a07_greve_eboueurs": {"attendu": ["anodin"]},
        "marche": ["a07_greve_eboueurs", "c9_inexistant"],
    }), "utf-8")
    with pytest.raises(SystemExit, match="ne déclare pas"):
        charger_grille(p)


def test_une_grille_incomplete_arrete_le_test(tmp_path):
    p = tmp_path / "g.yaml"
    p.write_text(yaml.safe_dump({"a07_greve_eboueurs": {"attendu": []}}), "utf-8")
    with pytest.raises(SystemExit, match="incomplète"):
        charger_grille(p)


# ── Le verdict ──────────────────────────────────────────────────────────────────────────────
def test_tout_au_vert_laisse_partir_la_campagne():
    ok, motifs = verdict(_bilan(), SEUILS)
    assert ok and not motifs


def test_une_seule_reponse_manquante_refuse():
    """Une exposition non jugée n'est pas une exposition anodine : elle n'a pas eu lieu."""
    ok, motifs = verdict(_bilan(sans_reponse=1), SEUILS)
    assert not ok and any("sans réponse" in m for m in motifs)


def test_un_seul_echelon_refuse_meme_si_tout_est_dans_la_plage():
    """Le cas du 2026-09-22 : des jugements défendables un par un, et rien à mesurer."""
    ok, motifs = verdict(_bilan(echelons_distincts=1), SEUILS)
    assert not ok and any("échelon" in m for m in motifs)


def test_des_bras_dans_le_desordre_refusent():
    ok, motifs = verdict(
        _bilan(bras_dans_l_ordre_predit=False,
               ordre_detail=["c3_panne_reseau (genant) est SOUS c6_voiture_suspecte (grave)"]),
        SEUILS)
    assert not ok and any("marche n'est pas tenue" in m for m in motifs)


def test_une_egalite_non_departagee_se_signale_sans_bloquer():
    """Deux bras portant la même plage attendue ne sont pas une réfutation de la marche."""
    ok, motifs = verdict(
        _bilan(ordre_detail=["c6 et c3 à égalité (grave) — NON départagés par la grille"]),
        SEUILS)
    assert ok, "une égalité que personne n'avait prédite ne bloque pas"
    assert any(m.startswith("⚠") for m in motifs)


def test_le_taux_aveugle_bloque_et_le_taux_deja_vu_ne_bloque_pas():
    """La distinction EST le test : mélanger les deux populations ne voudrait rien dire."""
    ok, _ = verdict(_bilan(part_hors_plage_aveugle=0.50), SEUILS)
    assert not ok

    ok, motifs = verdict(_bilan(part_hors_plage_deja_vue=0.90), SEUILS)
    assert ok, "une plage écrite après coup ne peut pas bloquer une campagne"
    assert any(m.startswith("⚠") for m in motifs), "elle doit tout de même se signaler"


def test_aucun_jugement_aveugle_ne_fabrique_pas_de_verdict():
    """Grille entièrement déjà vue : le taux aveugle est None et ne doit pas lever."""
    ok, _ = verdict(_bilan(part_hors_plage_aveugle=None), SEUILS)
    assert ok
