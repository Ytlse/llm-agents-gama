"""Passerelle entre les réponses probabilistes du LLM et les analyses de ces notebooks.

Ces notebooks ont été écrits quand le prompt demandait au modèle de **choisir** un
itinéraire (`chosen_index`). Le prompt demande désormais une **probabilité par option**
(cf. `docs/arch/llm-inference.md`), et `chosen_index` n'est plus renseigné.

`decision_index()` restitue l'ancienne grandeur — l'option que le modèle privilégie,
c'est-à-dire la plus probable — pour que les analyses existantes continuent de mesurer
ce qu'elles mesuraient. **Attention** : ce n'est pas ce que fait la simulation, qui
*tire au sort* dans la distribution (`llm_module.core.mode_choice.draw_index`).

⚠ Ce que la bascule change pour ces notebooks, et qui mérite une reformulation :

- **Variabilité d'un modèle** (notebook 1) — mesurer la dispersion de `chosen_index`
  sur N appels répétés estimait l'hésitation du modèle *par échantillonnage*. Cette
  hésitation est maintenant lisible **directement** dans la distribution d'un seul
  appel : `entropy_of()` la donne sans répéter les requêtes. Les deux ne sont pas
  interchangeables — la première mesure l'instabilité du décodage, la seconde la
  confiance déclarée — mais la seconde est gratuite et bien moins bruitée.
- **Entropie inter-appels** (notebook 2) — même remarque : une entropie calculée sur
  des argmax répétés perd toute l'information intermédiaire.
- **Influence de la température** (notebook 3) — la température agit désormais sur des
  probabilités *déclarées*, pas sur un choix. Un modèle peut être très stable en argmax
  tout en déplaçant nettement sa distribution : comparer `entropy_of()` par température
  est plus informatif que comparer des taux d'accord.
"""

from __future__ import annotations

import sys
from math import log2
from pathlib import Path
from typing import Any, Optional

# llm_module vit à la racine du dépôt : scripts/models_influence/ → ../../
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from llm_module.core.mode_choice import (  # noqa: E402
    argmax_index,
    canonical_mode,
    draw_index,
    mode_distribution,
    normalize_option_probabilities,
)


def weights_of(agent: Any) -> list[float]:
    """Distribution normalisée (somme = 1) d'une réponse, indexée par position."""
    entries = getattr(agent, "probabilities", None)
    if not entries:
        return []
    positional = [{"index": i, "probability": getattr(e, "probability", None)}
                  for i, e in enumerate(entries)]
    return normalize_option_probabilities(positional, len(positional),
                                          context=f"agent={getattr(agent, 'agent_id', '?')}")


def decision_index(agent: Any) -> Optional[int]:
    """Option privilégiée par le modèle — équivalent de l'ancien `chosen_index`.

    Repli sur `chosen_index` si la réponse suit encore l'ancien format.
    """
    weights = weights_of(agent)
    if weights:
        return argmax_index(weights)
    return getattr(agent, "chosen_index", None)


def drawn_index(agent: Any, *seed_parts: Any) -> Optional[int]:
    """Option **tirée au sort**, comme le fait la simulation (graine reproductible)."""
    weights = weights_of(agent)
    if not weights:
        return getattr(agent, "chosen_index", None)
    return draw_index(weights, *seed_parts)


def mode_of(agent: Any) -> Optional[str]:
    """Mode de l'option privilégiée (étiquette telle que recopiée par le modèle)."""
    entries = getattr(agent, "probabilities", None)
    idx = decision_index(agent)
    if entries and idx is not None and 0 <= idx < len(entries):
        return getattr(entries[idx], "mode", None)
    return getattr(agent, "mode", None)


def probabilities_of(agent: Any) -> dict[int, float]:
    """`{index: probabilité}` en %, pour stocker la réponse complète dans un DataFrame."""
    return {i: round(w * 100, 2) for i, w in enumerate(weights_of(agent))}


def distribution_of(agent: Any) -> dict[str, float]:
    """Répartition par mode canonique (modes proposés mais écartés compris, à 0)."""
    entries = getattr(agent, "probabilities", None)
    weights = weights_of(agent)
    if not weights:
        return {}
    modes = [getattr(e, "mode", None) for e in entries]
    return mode_distribution(weights, modes)


def entropy_of(agent: Any, normalized: bool = True) -> Optional[float]:
    """Entropie de la distribution — l'hésitation du modèle, en un seul appel.

    0 = certitude absolue ; 1 (si `normalized`) = indécision totale entre les options.
    C'est la grandeur qui remplace avantageusement une dispersion mesurée sur N appels.
    """
    weights = [w for w in weights_of(agent) if w > 0]
    if len(weights) < 2:
        return 0.0 if weights else None
    h = -sum(w * log2(w) for w in weights)
    return h / log2(len(weights_of(agent))) if normalized else h


def canonical_mode_of(agent: Any) -> Optional[str]:
    """Mode canonique de l'option privilégiée (`walking`, `car`, …)."""
    raw = mode_of(agent)
    return canonical_mode(raw) if raw else None
