"""
core/batching.py — Logique pure de regroupement des requêtes en batchs.

La clé de batch garantit qu'on ne merge que des tâches parfaitement
compatibles : même catégorie, mêmes paramètres, même provider forcé,
même contrainte TPM.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable

from llm_gateway.core.models import _FALLBACK_PRIORITY_SCORE, LLMRequest


def compute_batch_key(request: LLMRequest) -> str:
    """Clé de batch : MD5(catégorie + paramètres + provider forcé + min_tpm + instances admises).

    ⚠ **Toute contrainte de routage doit entrer ici** (ticket 084). Un lot est servi par UNE
    instance : deux requêtes aux restrictions différentes fusionnées dans le même lot feraient
    servir l'une par un fournisseur qu'elle excluait, sans qu'aucune trace ne le dise. C'est la
    seule garde contre ce mélange, et elle est silencieuse quand on l'oublie.

    Les instances admises entrent TRIÉES et dédupliquées : c'est un ensemble, pas une séquence,
    et deux déclarations du même ensemble dans un ordre différent doivent partager leur lot.
    """
    params_str = json.dumps(request.parameters, sort_keys=True)
    admises = (
        ",".join(sorted(set(request.instances_admises)))
        if request.instances_admises
        else None
    )
    hash_str = hashlib.md5(
        f"{request.category}:{params_str}:{request.force_provider}:"
        f"{request.min_tpm_required}:{admises}".encode()
    ).hexdigest()
    return f"{request.category}:{hash_str}"


def compute_priority_score(scores: Iterable[float | None]) -> float:
    """Score de priorité d'un lot = plus petit score fourni — plus bas = plus urgent.

    Les scores viennent de la catégorie (``CategorySpec.priority``) ; le gateway ne sait pas
    ce qu'ils mesurent (un horodatage de départ pour la mobilité). Aucun score → repli.
    """
    known = [s for s in scores if s is not None]
    return float(min(known)) if known else _FALLBACK_PRIORITY_SCORE
