"""Importer `settings` lit la configuration ; ouvrir un run est un acte explicite.

Jusqu'au 2026-09-04, l'import de `settings` créait un répertoire de run et faisait pointer
`experiments/current` dessus. Un script d'analyse lancé pendant un run faisait donc basculer le
lien vers un répertoire vide, et le journal des échanges avec le modèle — qui résout le lien à
chaque écriture — se mettait à écrire à côté du run. Quatre occurrences en une nuit, la première
ayant détourné 1 037 échanges. Ces tests tiennent la frontière.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import settings as settings_module  # noqa: E402
from settings import FactorySettings  # noqa: E402


@pytest.fixture
def experiences(tmp_path, monkeypatch):
    """Un dossier d'expériences neuf, avec un `current` qui pointe sur un run existant."""
    exp = tmp_path / "experiments"
    (exp / "archive" / "run_en_cours").mkdir(parents=True)
    lien = exp / "current"
    lien.symlink_to(Path("archive") / "run_en_cours")
    monkeypatch.setenv("APP_EXPERIMENTS_DIR", str(exp))
    # Les garde-fous de test neutralisent justement ce qu'on veut observer : on les lève,
    # et on travaille dans un dossier temporaire pour que rien de réel ne bouge.
    monkeypatch.setattr(settings_module, "_run_artifacts_disabled", lambda: False)
    monkeypatch.setattr(FactorySettings, "_instance", None, raising=False)
    yield exp, lien
    FactorySettings._instance = None


def test_un_import_ne_cree_rien_et_ne_deplace_pas_le_lien(experiences):
    exp, lien = experiences
    avant = sorted(p.name for p in (exp / "archive").iterdir())

    s = FactorySettings.force_reload()

    assert not s.workdir.exists(), "un import ne doit créer aucun répertoire de run"
    assert sorted(p.name for p in (exp / "archive").iterdir()) == avant
    assert os.readlink(lien) == str(Path("archive") / "run_en_cours")


def test_claim_run_ouvre_le_run_et_deplace_le_lien(experiences):
    exp, lien = experiences
    s = FactorySettings.force_reload()
    assert not s.workdir.exists()

    FactorySettings.claim_run()

    assert s.workdir.is_dir(), "claim_run doit créer le répertoire du run"
    assert (s.workdir / "static_config.yaml").exists(), "la configuration doit y être figée"
    assert os.readlink(lien) == str(Path("archive") / s.workdir.name)


def test_claim_run_est_idempotente(experiences):
    exp, lien = experiences
    s = FactorySettings.force_reload()
    FactorySettings.claim_run()
    cible = os.readlink(lien)

    FactorySettings.claim_run()

    assert os.readlink(lien) == cible
    assert s.workdir.is_dir()


def test_sous_test_claim_run_ne_touche_a_rien(tmp_path, monkeypatch):
    """Le garde-fou existant reste opposable : une suite de tests qui appelle claim_run()
    — par mégarde ou par un import transitif — ne vole pas la sortie d'un run en cours."""
    exp = tmp_path / "experiments"
    (exp / "archive" / "run_en_cours").mkdir(parents=True)
    lien = exp / "current"
    lien.symlink_to(Path("archive") / "run_en_cours")
    monkeypatch.setenv("APP_EXPERIMENTS_DIR", str(exp))
    monkeypatch.setenv("APP_NO_RUN_ARTIFACTS", "1")
    FactorySettings._instance = None

    FactorySettings.claim_run()

    assert os.readlink(lien) == str(Path("archive") / "run_en_cours")
    FactorySettings._instance = None
