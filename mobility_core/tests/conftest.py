"""Racine du dépôt pour les fichiers de référence que le paquet ne recopie pas.

Les tests peuvent être lancés depuis `mobility_core/` ou depuis la racine : on désigne
explicitement la racine du dépôt au lieu de dépendre du répertoire courant.
"""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("MOBILITY_CORE_REPO_ROOT", str(REPO_ROOT))
