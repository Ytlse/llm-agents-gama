"""Ticket 047 — une offre à mode unique n'est pas une décision : la mesure est systématique.

Le ticket 045 (bloc D, R10-R12) avait déjà fait publier les deux lectures des PARTS MODALES
par `synthese.json`. Il restait la grandeur qui décide du classement des bras : le
**composite**. Il comptait les décisions à itinéraire unique sans le dire, et le compte
n'accompagnait ni le chiffre ni le tableau qui compare les bras.

Ce que ces tests verrouillent, c'est que la mesure se fait **toute seule** : aucune option,
aucune commande à penser. Rien ici ne tranche la convention — le composite principal continue
de compter ces lignes, la seconde lecture les retire, et les deux sont publiés côte à côte.

Pourquoi la mesure est obligatoire et non facultative, en chiffres du 2026-09-12 (16
exécutions du 11/09, même population, même jeu) : retirer les décisions à itinéraire unique
déplace le composite EMD de **−3,75** (`durmin`) à **+12,22** (`alea`), et **change le
classement** — `lgbm` (4,50) est premier toutes décisions comprises, mais passe à 10,46 et
derrière `klr` (9,95) hors itinéraire unique. Chaîne coupée, le même écart plafonne à 0,32 :
ces lignes viennent de la chaîne des véhicules, donc des choix antérieurs du bras lui-même.
"""

import json
import shutil
from pathlib import Path

import pytest
from experiences import formule as F
from experiences import score as S

REPO = Path(__file__).resolve().parents[3]


def _exec_reelle() -> Path | None:
    """Une exécution terminée du dépôt qui porte des choix forcés dans son périmètre scoré.

    Pointée en dur, la référence disparaîtrait avec l'expérience qui la porte. On exige des
    choix forcés : sur une exécution qui n'en a aucun, les deux lectures coïncident et tous
    les tests passeraient sans rien mesurer — la vacuité prise pour la réussite, motif
    récurrent de ce dépôt.
    """
    racine = REPO / "data" / "experiences"
    for exp in sorted(racine.iterdir()) if racine.is_dir() else []:
        executions = exp / "executions"
        for d in sorted(executions.iterdir()) if executions.is_dir() else []:
            if not (d / "moves.csv").exists() or not (d / "synthese.json").exists():
                continue
            try:
                synthese = json.loads((d / "synthese.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if (synthese.get("etat") or {}).get("etat") != "terminee":
                continue
            if ((synthese.get("choix_forces") or {}).get("n") or 0) > 0:
                return d
    return None


EXEC_REELLE = _exec_reelle()

pytestmark = pytest.mark.skipif(
    EXEC_REELLE is None,
    reason="aucune exécution terminée AVEC choix forcés dans data/experiences",
)


@pytest.fixture
def exec_tmp(tmp_path):
    dst = tmp_path / EXEC_REELLE.name
    shutil.copytree(EXEC_REELLE, dst)
    for f in ("scores.json", "synthese_scores.html"):
        (dst / f).unlink(missing_ok=True)
    return dst


@pytest.fixture(scope="module")
def registre():
    return F.charger()


@pytest.fixture(scope="module")
def scores(registre):
    """Un scoring, partagé : `calculer` lit moves.csv deux fois et score deux trames."""
    if EXEC_REELLE is None:
        pytest.skip("substrat absent")
    return S.calculer(EXEC_REELLE, registre.reference)


# ── La mesure est faite, sans qu'on la demande ───────────────────────────────


def test_le_scoring_publie_les_deux_lectures_sans_option(scores):
    """Aucun drapeau, aucun paramètre : un scoring ordinaire porte les deux composites."""
    comp = scores["composite"]
    for cle in ("emd_jsd", "l1", "emd_jsd_hors_choix_unique", "l1_hors_choix_unique"):
        assert comp.get(cle) is not None, f"lecture absente du scores.json : {cle}"


def test_la_seconde_lecture_egale_un_scoring_direct_sans_ces_lignes(scores, registre):
    """Elle n'est pas approchée depuis la première : c'est le MÊME Scorer sur la trame filtrée."""
    scorer, _ = S.scorer_pour(registre.reference)
    # Ticket 057 — par `lire_perimetre`, et non en re-spécifiant la coupe ici : c'est cette
    # duplication qui avait laissé le test reproduire un périmètre qui n'était plus celui du
    # scoreur, et passer pendant que les deux divergeaient.
    rows, _ = S.lire_perimetre(
        EXEC_REELLE, S.EXCLURE_METHODES + [S.METHODE_CHOIX_UNIQUE_MOVES]
    )
    attendu = S.frames.simulation_frames(rows)["attendu"]
    cerema = S.frames.load_cerema(
        S._resoudre_cerema(json.loads((EXEC_REELLE / "synthese.json").read_text()))
    )
    direct = scorer.score(attendu, cerema)["emd_jsd"]["composite"]
    assert abs(scores["composite"]["emd_jsd_hors_choix_unique"] - direct) < 1e-9


def test_le_composite_principal_compte_toujours_ces_lignes(scores):
    """La convention n'a pas changé : ce ticket mesure, il ne retire rien.

    `EXCLURE_METHODES` reste la liste des lignes SANS décision modale ; une offre à mode
    unique n'en fait pas partie — elle a produit un déplacement, et la journée l'a joué.
    """
    assert S.METHODE_CHOIX_UNIQUE_MOVES not in S.EXCLURE_METHODES
    forces = scores["choix_forces"]
    assert forces["n_scorees"] == forces["n_hors_choix_unique"] + forces["n"]


# ── Le compte voyage avec le chiffre, et nomme son périmètre ─────────────────


def test_le_compte_accompagne_le_composite(scores):
    forces = scores["choix_forces"]
    assert forces["n"] > 0
    assert forces["part"] == pytest.approx(forces["n"] / forces["n_scorees"])
    assert forces["perimetre"] and forces["lecture"]


def test_les_deux_perimetres_sont_nommes_et_distincts(scores):
    """Le piège que ce ticket ferme : un compte posé à côté d'un chiffre qu'il ne recouvre pas.

    `synthese.json` compte sur TOUTES les décisions archivées ; le composite ne porte que sur
    le premier jour simulé et la dernière tentative. Mesuré sur les 16 exécutions du 11/09,
    les deux comptes diffèrent de 14 à 19 lignes — jamais de zéro. Publier l'un pour l'autre
    donnerait une part de choix forcés fausse de plusieurs points (27,0 % contre 20,6 % sur
    `exp_lgbm`).
    """
    forces = scores["choix_forces"]
    assert forces["perimetre"] != forces["perimetre_execution"]
    assert forces["n_execution"] is not None, (
        "le compte de l'exécution doit être relayé"
    )
    # Relayé, pas recalculé : il vaut celui que `synthese.json` a écrit (R11 du ticket 045).
    synthese = json.loads((EXEC_REELLE / "synthese.json").read_text())
    assert forces["n_execution"] == synthese["choix_forces"]["n"]


# ── Rien ne se dégrade en silence ────────────────────────────────────────────


def test_un_rejeu_de_formule_recompose_LES_DEUX_composites(exec_tmp, registre):
    """Sinon la seconde lecture resterait figée sous l'ancienne formule.

    Deux chiffres côte à côte calculés sous deux pondérations : leur écart ne mesurerait
    plus les choix forcés mais le changement de formule, sans que rien ne le dise.
    """
    ref = S.calculer(exec_tmp, registre.reference)
    poids_alt = {**registre.reference.poids, "age": 0.9, "distance": 0.1}
    alt = F.Formule("alt", poids_alt, F.empreinte(poids_alt))
    rejoue, frais = S.rejouer(ref, alt), S.calculer(exec_tmp, alt)
    for cle in ("emd_jsd", "emd_jsd_hors_choix_unique", "l1", "l1_hors_choix_unique"):
        assert abs(rejoue["composite"][cle] - frais["composite"][cle]) < 1e-9, cle


def test_sans_decision_restante_la_seconde_lecture_est_non_mesuree_jamais_zero(
    exec_tmp, registre, monkeypatch
):
    """Vacuité ≠ perfection : ici 0.0 est le score PARFAIT, donc jamais une valeur de repli.

    On simule le cas limite — toutes les décisions scorées sont à itinéraire unique — en
    faisant rendre une trame vide à la seconde lecture.
    """
    vraie_lecture = S.frames.read_moves

    def lecture(path, exclure, **kw):
        if S.METHODE_CHOIX_UNIQUE_MOVES in exclure:
            return [], {}
        return vraie_lecture(path, exclure, **kw)

    monkeypatch.setattr(S.frames, "read_moves", lecture)
    contenu = S.calculer(exec_tmp, registre.reference)
    assert contenu["composite"]["emd_jsd_hors_choix_unique"] is None
    assert contenu["composite"]["l1_hors_choix_unique"] is None
    assert contenu["choix_forces"]["n_hors_choix_unique"] == 0


def test_l_ecart_entre_lectures_leve_une_alarme(exec_tmp, registre, caplog):
    """Un écart décisif ne se découvre pas en comparant deux colonnes à la main.

    Le seuil (1,0 point EMD) sépare les deux régimes mesurés le 2026-09-12 : chaîne coupée,
    l'écart plafonne à 0,32 ; chaîne active, il part de 2,62.
    """
    import logging

    from loguru import logger

    tampon: list[str] = []
    sink = logger.add(lambda m: tampon.append(m), level="ERROR")
    try:
        contenu = S.calculer(exec_tmp, registre.reference)
    finally:
        logger.remove(sink)
    comp = contenu["composite"]
    ecart = abs(comp["emd_jsd_hors_choix_unique"] - comp["emd_jsd"])
    attendue = ecart >= S.ECART_LECTURES_ALARME
    levee = any("[ALARME]" in m and "choix forcés" in m for m in tampon)
    assert levee is attendue, (
        f"écart {ecart:.2f} vs seuil {S.ECART_LECTURES_ALARME} — alarme levée : {levee}"
    )
    assert logging  # l'import reste explicite : caplog ne capte pas loguru


# ── Les surfaces de comparaison portent le compte ────────────────────────────


def test_le_registre_cli_porte_le_compte_et_la_seconde_lecture():
    """Le tableau où les bras se comparent, en console."""
    from experiences.registre import formater_table

    colonnes_par_defaut = formater_table([]).splitlines()[0]
    for colonne in ("choix_forces", "composite_emd_hors_forces"):
        assert colonne in colonnes_par_defaut, (
            f"« {colonne} » doit être affichée PAR DÉFAUT : une colonne qu'il faut "
            "demander est une colonne que personne ne demande"
        )


def test_le_tableau_de_bord_porte_le_compte_par_defaut():
    """Et celui où elles se comparent à l'écran — la surface que le ticket bloquait."""
    import sys

    sys.path.insert(0, str(REPO))
    from scripts.dashboard.experiences import (
        COLONNES_REGISTRE,
        COLONNES_REGISTRE_DEFAUT,
    )

    for colonne in ("choix_forces", "composite_emd_hors_forces"):
        assert colonne in COLONNES_REGISTRE_DEFAUT
    for colonne in ("part_forces", "choix_forces_score", "composite_l1_hors_forces"):
        assert colonne in COLONNES_REGISTRE, "au moins rappelable au sélecteur"
