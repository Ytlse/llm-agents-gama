"""Garde-fous partagés par tous les tests de `scripts/tests`."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_CHEMIN_SERVICES = REPO_ROOT / "services" / "llm-agents"
if str(_CHEMIN_SERVICES) not in sys.path:
    sys.path.insert(0, str(_CHEMIN_SERVICES))

try:
    from experiences import memoire as _memoire
except Exception:  # noqa: BLE001 — module absent ou cassé : rien à isoler
    _memoire = None


@pytest.fixture(autouse=True)
def _isoler_donnees_memoire(tmp_path_factory, monkeypatch):
    """Détourne vers un dossier temporaire les écritures des expériences mémoire.

    L'onglet 🧠 (ticket 109) enregistre une expérience dès qu'un bouton est vrai. Rendu
    avec un `st` MagicMock, chaque `st.button` est vrai : sans ce détour, le test crée un
    dossier `exp_mem_…_magicmock-…` dans le vrai `data/experiences_memoire/` et réécrit
    `experiments/.dashboard/formulaire_memoire.yaml`.
    """
    if _memoire is None:
        yield None
        return
    racine = tmp_path_factory.mktemp("memoire_isolee")
    dossier = racine / "data" / "experiences_memoire"
    dossier.mkdir(parents=True)
    monkeypatch.setattr(_memoire, "DOSSIER_MEMOIRE", dossier)
    monkeypatch.setattr(_memoire, "ETAT_FORMULAIRE_MEMOIRE", racine / "formulaire_memoire.yaml")
    yield dossier
