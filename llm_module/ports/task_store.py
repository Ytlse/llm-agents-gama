"""
ports/task_store.py — Contrat de persistance des tâches (statut, résultat, pub/sub).
"""

from __future__ import annotations
from typing import Optional, Protocol

from llm_module.core.models import Task


class TaskStore(Protocol):
    """Variante async — utilisée par l'API FastAPI."""

    async def save(self, task: Task) -> None: ...

    async def get(self, task_id: str) -> Optional[Task]: ...

    async def wait_done(self, task_id: str, timeout: float) -> Optional[Task]:
        """Bloque jusqu'à l'état terminal de la tâche (pub/sub) ou le timeout.
        Retourne le dernier état connu de la tâche, None si elle n'existe pas."""
        ...


class SyncTaskStore(Protocol):
    """Variante sync — utilisée par le worker Celery."""

    def save_sync(self, task: Task) -> None: ...

    def get_sync(self, task_id: str) -> Optional[Task]: ...

    def publish_done_sync(self, task: Task) -> None:
        """Notifie les long-polls que la tâche a atteint un état terminal."""
        ...
