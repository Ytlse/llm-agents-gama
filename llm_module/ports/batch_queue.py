"""
ports/batch_queue.py — Contrat des files de micro-batching.

Les tâches sont regroupées par batch_key (cf. core.batching.compute_batch_key)
et triées par priority_score (min departure_time). Le flag « scheduled »
garantit qu'exactement un dispatch différé est armé par cycle de batch.
"""

from __future__ import annotations
from typing import Protocol

from llm_module.core.models import Task


class BatchQueue(Protocol):
    # ── Côté API (async) ─────────────────────────────────────────────────
    async def add(self, batch_key: str, task_id: str, score: float) -> int:
        """Ajoute une tâche à la file et retourne la taille courante."""
        ...

    async def try_mark_scheduled(self, batch_key: str, ttl: int) -> bool:
        """Pose le flag « dispatch différé planifié » (SETNX). True si posé
        par cet appel — l'appelant doit alors planifier le dispatch."""
        ...

    # ── Côté worker (sync) ───────────────────────────────────────────────
    def clear_scheduled(self, batch_key: str) -> None:
        """Libère le flag de dispatch — appelé juste avant le pop."""
        ...

    def pop(self, batch_key: str, max_agents: int) -> list[Task]:
        """Dépile les tâches les plus urgentes jusqu'à la limite d'agents."""
        ...

    def requeue(self, batch_key: str, tasks: list[Task]) -> None:
        """Replace les tâches (retry) avec leur score d'origine."""
        ...

    def size(self, batch_key: str) -> int: ...

    def depths(self) -> dict[str, int]:
        """Profondeur de toutes les files non vides (monitoring)."""
        ...
