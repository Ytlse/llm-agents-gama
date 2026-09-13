"""Ticket 035 — scoring automatique à la clôture d'une exécution (R21, R23).

Voir `specs/scoring_composite_experiences.md`. Substrat : une vraie exécution terminée du
dépôt, copiée en tmp pour que les écritures ne polluent pas `data/`.

Le contrat tenu ici est celui du fail-open : le scoring de clôture est un rendu, jamais
une raison de faire échouer une exécution qui a produit toutes ses décisions.
"""

import json
import shutil
from pathlib import Path

import pytest
from experiences import score as S
from loguru import logger

from tests.test_035_08_score import EXEC_REELLE

pytestmark = pytest.mark.skipif(
    EXEC_REELLE is None,
    reason="aucune exécution terminée dans data/experiences (substrat absent)",
)


@pytest.fixture
def exec_tmp(tmp_path):
    dst = tmp_path / EXEC_REELLE.name
    shutil.copytree(EXEC_REELLE, dst)
    for f in ("scores.json", "synthese_scores.html"):
        (dst / f).unlink(missing_ok=True)
    return dst


def test_R23_execution_terminee_scoree_a_la_cloture(exec_tmp):
    # Sans qu'on le demande : plus de `score --toutes` à lancer à la main pour voir un composite.
    chemin = S.scorer_a_la_cloture(exec_tmp)
    assert chemin is not None and chemin.exists()
    contenu = json.loads(chemin.read_text(encoding="utf-8"))
    assert contenu["composite"]["emd_jsd"] is not None
    assert (exec_tmp / "synthese_scores.html").exists(), "la page de détail doit suivre"


@pytest.mark.parametrize("etat", ["arretee", "en_pause", "en_cours", "epuisee"])
def test_R21_seule_une_execution_terminee_est_scoree(exec_tmp, etat):
    # Tranché : une exécution arrêtée n'est PAS prise en compte, même largement remplie.
    synthese = json.loads((exec_tmp / "synthese.json").read_text(encoding="utf-8"))
    synthese["etat"]["etat"] = etat
    (exec_tmp / "synthese.json").write_text(
        json.dumps(synthese, ensure_ascii=False), encoding="utf-8"
    )
    assert S.scorer_a_la_cloture(exec_tmp) is None
    assert not (exec_tmp / "scores.json").exists()


def test_R23_fail_open_moteur_absent(exec_tmp, monkeypatch):
    # Moteur de loss indisponible : pas d'exception, pas de scores.json, une ALARME lisible.
    monkeypatch.setattr(
        S.sources, "import_calibration", lambda *a, **k: (None, "moteur absent (test)")
    )
    messages = []
    sink = logger.add(lambda m: messages.append(str(m)), level="ERROR")
    try:
        assert S.scorer_a_la_cloture(exec_tmp) is None  # ne lève pas
    finally:
        logger.remove(sink)
    assert not (exec_tmp / "scores.json").exists()
    assert any("[ALARME]" in m and exec_tmp.name in m for m in messages), messages


def test_R23_fail_open_erreur_inattendue(exec_tmp, monkeypatch):
    # Toute panne, pas seulement le moteur manquant : l'exécution reste terminée.
    def boum(*a, **k):
        raise RuntimeError("disque plein")

    monkeypatch.setattr(S, "score_execution", boum)
    messages = []
    sink = logger.add(lambda m: messages.append(str(m)), level="ERROR")
    try:
        assert S.scorer_a_la_cloture(exec_tmp) is None
    finally:
        logger.remove(sink)
    etat = json.loads((exec_tmp / "synthese.json").read_text(encoding="utf-8"))["etat"]
    assert etat["etat"] == "terminee", "le scoring ne change jamais l'état de l'exécution"
    assert any("[ALARME]" in m and "disque plein" in m for m in messages), messages
