"""Configuration pytest partagée.

Ajoute au sys.path :
- la **racine du dépôt**, pour les tests qui importent la chaîne complète du
  contrôleur (laquelle importe `mobility_core`, packagé à la racine) — comme en
  Docker où `mobility_core` est installé sur le path ;
- le dossier **`services/llm-agents/`** lui-même, où vivent les modules top-level
  `backpressure`, `settings`, `world`, etc. Sans lui, `pytest` lancé depuis la
  racine du dépôt échoue à la collecte (`ModuleNotFoundError: backpressure` /
  `settings`) et interrompt tout le run ; avec lui, les tests se collectent quel
  que soit le répertoire d'invocation.
"""

import sys
from pathlib import Path

# Depuis le ticket 039 `llm-agents` vit sous `services/` : la racine est à TROIS crans,
# plus deux. On la cherche par son ancre plutôt que de la compter, pour que le prochain
# déplacement ne casse pas la collecte (même raison que `experiences.chemins`).
_REPO_ROOT = next(
    (a for a in Path(__file__).resolve().parents if (a / "scripts" / "synthesis").is_dir()),
    Path(__file__).resolve().parents[3],
)
_LLM_AGENTS = Path(__file__).resolve().parents[1]
for _p in (_REPO_ROOT, _LLM_AGENTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
