"""ports/learned_limits.py — ce que le gateway apprend des fournisseurs et doit retenir.

Aujourd'hui une seule chose : le plafond de complétion réel (`max_output_tokens`) qu'un
fournisseur révèle par un HTTP 400 « max_tokens must be ≤ N ». Avant le ticket 037, cette
valeur était réécrite dans le YAML du paquet installé ; elle vit désormais derrière ce port
(Redis en production, fichier ou mémoire sans Redis).
"""
from __future__ import annotations

from typing import Protocol


class LearnedLimits(Protocol):
    def get_max_output_tokens(self, provider: str) -> int | None: ...

    def set_max_output_tokens(self, provider: str, limit: int) -> None: ...

    def all_max_output_tokens(self) -> dict[str, int]:
        """Toutes les limites apprises, {provider: limite}."""
        ...


__all__ = ["LearnedLimits"]
