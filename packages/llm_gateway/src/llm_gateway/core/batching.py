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
    """Clé de batch : MD5(catégorie + paramètres + provider forcé + min_tpm)."""
    params_str = json.dumps(request.parameters, sort_keys=True)
    hash_str = hashlib.md5(
        f"{request.category}:{params_str}:{request.force_provider}:{request.min_tpm_required}".encode()
    ).hexdigest()
    return f"{request.category}:{hash_str}"


def compute_priority_score(scores: Iterable[float | None]) -> float:
    """Score de priorité d'un lot = plus petit score fourni — plus bas = plus urgent.

    Les scores viennent de la catégorie (``CategorySpec.priority``) ; le gateway ne sait pas
    ce qu'ils mesurent (un horodatage de départ pour la mobilité). Aucun score → repli.
    """
    known = [s for s in scores if s is not None]
    return float(min(known)) if known else _FALLBACK_PRIORITY_SCORE
