"""Configuration pytest partagée.

Ajoute au sys.path :
- la **racine du dépôt**, pour les tests qui importent la chaîne complète du
  contrôleur (laquelle importe `llm_module`, packagé à la racine) — comme en
  Docker où `llm_module` est installé sur le path ;
- le dossier **`llm-agents/`** lui-même, où vivent les modules top-level
  `backpressure`, `settings`, `world`, etc. Sans lui, `pytest` lancé depuis la
  racine du dépôt échoue à la collecte (`ModuleNotFoundError: backpressure` /
  `settings`) et interrompt tout le run ; avec lui, les tests se collectent quel
  que soit le répertoire d'invocation.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LLM_AGENTS = Path(__file__).resolve().parents[1]
for _p in (_REPO_ROOT, _LLM_AGENTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
