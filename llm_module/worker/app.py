"""
worker/app.py — Fabrique de l'application Celery.

create_celery_app(config) construit l'app explicitement à partir des Settings.
L'instance module-level reste dans worker/task_worker.py (exigence du CLI
Celery : `-A llm_module.worker.task_worker.celery_app`).
"""

from __future__ import annotations

from celery import Celery
from celery.signals import worker_shutdown

from llm_module.config import Settings
from llm_module.telemetry.logger import configure_logging


@worker_shutdown.connect
def _close_shared_http_clients(**_kwargs) -> None:
    """Libère les clients httpx partagés des adapters à l'arrêt du worker."""
    from llm_module.adapters.base import close_all_adapters
    close_all_adapters()


def create_celery_app(settings: Settings) -> Celery:
    configure_logging()
    app = Celery(
        "llm_worker",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_track_started=True,
        worker_prefetch_multiplier=1,   # Un seul message à la fois par Worker (appels LLM longs)
        task_acks_late=True,            # Acquitter APRÈS traitement (évite la perte en cas de crash)
    )
    return app
