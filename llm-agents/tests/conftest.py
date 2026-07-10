"""Configuration pytest partagée.

Ajoute la racine du dépôt au sys.path pour que les tests qui importent la chaîne
complète du contrôleur (laquelle importe `llm_module`, packagé à la racine du dépôt)
fonctionnent sans avoir à exporter PYTHONPATH manuellement — comme en Docker où
`llm_module` est installé sur le path.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
