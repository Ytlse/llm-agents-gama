"""
ports/task_store.py — Contrat de persistance des tâches (statut, résultat, pub/sub).
"""

from __future__ import annotations

from typing import Protocol

from llm_gateway.core.models import Task


class TaskStore(Protocol):
    """Variante async — utilisée par l'API FastAPI."""

    async def save(self, task: Task) -> None: ...

    async def get(self, task_id: str) -> Task | None: ...

    async def wait_done(self, task_id: str, timeout: float) -> Task | None:
        """Bloque jusqu'à l'état terminal de la tâche (pub/sub) ou le timeout.
        Retourne le dernier état connu de la tâche, None si elle n'existe pas."""
        ...


class SyncTaskStore(Protocol):
    """Variante sync — utilisée par le worker Celery."""

    def save_sync(self, task: Task) -> None: ...

    def get_sync(self, task_id: str) -> Task | None: ...

    def publish_done_sync(self, task: Task) -> None:
        """Notifie les long-polls que la tâche a atteint un état terminal."""
        ...
