"""Ticket 109 — un rendu de l'onglet 🧠 sous test n'écrit jamais dans les vraies données."""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.dashboard import memoire as ONGLET

VRAI_DOSSIER = REPO_ROOT / "data" / "experiences_memoire"
VRAI_FORMULAIRE = REPO_ROOT / "experiments" / ".dashboard" / "formulaire_memoire.yaml"


def _st_tout_clique() -> MagicMock:
    """Un `st` MagicMock : chaque `st.button` renvoie un mock vrai, donc chaque action part."""
    st = MagicMock()
    st.columns.side_effect = lambda spec, **_: [
        MagicMock() for _ in range(spec if isinstance(spec, int) else len(spec))
    ]
    st.session_state = {}
    return st


def _empreinte(chemin: Path):
    return chemin.stat().st_mtime_ns if chemin.exists() else None


def test_rendu_mocke_ecrit_sous_tmp_et_pas_dans_data(_isoler_donnees_memoire):
    avant = set(VRAI_DOSSIER.iterdir()) if VRAI_DOSSIER.exists() else set()
    formulaire_avant = _empreinte(VRAI_FORMULAIRE)

    # Le dossier est créé avant le YAML, qui échoue sur les valeurs MagicMock : c'est
    # ainsi qu'un dossier vide `exp_mem_…_magicmock-…` restait dans `data/`.
    with contextlib.suppress(Exception):
        ONGLET.render(_st_tout_clique(), pd)

    apres = set(VRAI_DOSSIER.iterdir()) if VRAI_DOSSIER.exists() else set()
    assert apres == avant, f"dossiers créés dans les vraies données : {apres - avant}"
    assert _empreinte(VRAI_FORMULAIRE) == formulaire_avant
    # Le bouton « Enregistrer » est bien passé : l'écriture a eu lieu, mais sous tmp.
    assert any(_isoler_donnees_memoire.iterdir())
