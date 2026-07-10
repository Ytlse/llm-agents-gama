"""
core/batching.py — Logique pure de regroupement des requêtes en batchs.

La clé de batch garantit qu'on ne merge que des tâches parfaitement
compatibles : même catégorie, mêmes paramètres, même provider forcé,
même contrainte TPM.
"""

from __future__ import annotations
import hashlib
import json

from llm_module.core.models import _FALLBACK_PRIORITY_SCORE, AgentSpec, LLMRequest


def compute_batch_key(request: LLMRequest) -> str:
    """Clé de batch : MD5(catégorie + paramètres + provider forcé + min_tpm)."""
    params_str = json.dumps(request.parameters, sort_keys=True)
    hash_str = hashlib.md5(
        f"{request.category}:{params_str}:{request.force_provider}:{request.min_tpm_required}".encode()
    ).hexdigest()
    return f"{request.category}:{hash_str}"


def compute_priority_score(agents: list[AgentSpec]) -> float:
    """Score de priorité = min(departure_timestamp) — plus bas = plus urgent."""
    scores = [a.departure_timestamp for a in agents if a.departure_timestamp is not None]
    return min(scores) if scores else _FALLBACK_PRIORITY_SCORE
