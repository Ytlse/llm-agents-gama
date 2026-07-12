"""
ports/llm_adapter.py — Contrat des adapters LLM.

BaseAdapter (llm_module.adapters.base) fournit l'implémentation de référence ;
ce protocol formalise le cycle de vie attendu par le worker, notamment close()
pour libérer le client httpx partagé (keep-alive).
"""

from __future__ import annotations
from typing import Protocol, Tuple

from llm_module.core.models import InternalRequest, LLMOutput


class LLMAdapter(Protocol):
    def call(self, request: InternalRequest) -> Tuple[LLMOutput, int, int]:
        """Exécute l'appel LLM. Retourne (sortie, tokens_in, tokens_out)."""
        ...

    def close(self) -> None:
        """Libère les ressources (client httpx partagé)."""
        ...
