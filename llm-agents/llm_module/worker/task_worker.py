"""
worker/task_worker.py — Worker Celery avec retry et backoff exponentiel.

Le Worker est le cœur du traitement :
  1. Récupère la tâche depuis Redis
  2. Construit le prompt via le PromptManager
  3. Sélectionne le provider via le LoadBalancer
  4. Exécute l'appel LLM via l'Adapter approprié
  5. Valide la sortie structurée
  6. Persiste le résultat en Redis

Retry avec backoff exponentiel sur les erreurs 5xx :
  tentative 1 → attente 1s
  tentative 2 → attente 2s
  tentative 3 → attente 4s
  tentative 4 → attente 8s  (max_retries=4 dans config)
"""

from __future__ import annotations
import time
from datetime import datetime

from celery import Celery
from celery.utils.log import get_task_logger

from llm_module.tasks.config import settings
from llm_module.settings.models import InternalRequest, Task, TaskStatus
from llm_module.adapters.base import (
    ProviderClientError,
    ProviderParseError,
    ProviderServerError,
    get_adapter,
)
from llm_module.broker.redis_broker import get_task_sync, save_task_sync
from llm_module.load_balancer.router import load_balancer
from llm_module.prompts.manager import prompt_manager
from llm_module.telemetry.logger import get_logger, log_llm_call

logger = get_logger(__name__)
task_logger = get_task_logger(__name__)

# ---------------------------------------------------------------------------
# Application Celery
# ---------------------------------------------------------------------------

celery_app = Celery(
    "llm_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_prefetch_multiplier=1,   # Un seul message à la fois par Worker (appels LLM longs)
    task_acks_late=True,            # Acquitter APRÈS traitement (évite la perte en cas de crash)
)


# ---------------------------------------------------------------------------
# Tâche principale
# ---------------------------------------------------------------------------

@celery_app.task(
    name="process_llm_task",
    bind=True,
    max_retries=settings.max_retries,
)
def process_llm_task(self, task_id: str) -> None:
    """
    Point d'entrée Celery.
    `bind=True` pour accéder à `self.retry()`.
    """
    task = get_task_sync(task_id)
    if task is None:
        logger.error("Tâche introuvable dans Redis", task_id=task_id)
        return

    # Marquer comme en cours
    task.status = TaskStatus.RUNNING
    task.updated_at = datetime.utcnow()
    save_task_sync(task)

    try:
        _execute_task(task)
    except ProviderServerError as e:
        # Erreur 5xx → backoff exponentiel et retry
        delay = settings.backoff_base_seconds * (2 ** self.request.retries)
        logger.warning(
            "Erreur serveur provider, retry planifié",
            task_id=task_id,
            provider=e.provider,
            http_status=e.status_code,
            retry_in=delay,
            attempt=self.request.retries + 1,
        )
        raise self.retry(exc=e, countdown=delay)

    except (ProviderClientError, ProviderParseError) as e:
        # Erreur 4xx ou parse → échec définitif, pas de retry
        _fail_task(task, str(e))

    except Exception as e:
        # Erreur inattendue → log et échec
        logger.exception("Erreur inattendue dans le worker", task_id=task_id)
        _fail_task(task, f"Erreur interne : {str(e)}")


# ---------------------------------------------------------------------------
# Logique métier
# ---------------------------------------------------------------------------

def _execute_task(task: Task) -> None:
    req = task.request

    # 1. Sélection du provider
    provider_name = load_balancer.select_provider(force=req.force_provider)

    # 2. Construction du prompt
    messages = prompt_manager.render(
        category=req.category,
        agents=req.agents,
        parameters=req.parameters,
    )
    schema = prompt_manager.get_output_schema()

    # 3. Assemblage de la requête interne
    internal_req = InternalRequest(
        provider=provider_name,
        messages=messages,
        response_schema=schema,
        temperature=req.parameters.get("temperature", 0.7),
        max_tokens=req.parameters.get("max_tokens", 4096),
    )

    # 4. Enregistrement du call RPM (avant l'appel, pour le circuit breaker)
    load_balancer.record_call(provider_name)

    # 5. Appel LLM via l'adapter approprié
    adapter = get_adapter(provider_name)
    start_ts = time.monotonic()

    llm_output, tokens_in, tokens_out = adapter.call(internal_req)

    latency_ms = (time.monotonic() - start_ts) * 1000

    # 6. Télémétrie
    log_llm_call(
        task_id=task.task_id,
        provider=provider_name,
        status="success",
        latency_ms=latency_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        http_status=200,
    )

    # 7. Persistance du résultat
    task.status       = TaskStatus.SUCCESS
    task.result       = llm_output.agents
    task.provider_used = provider_name
    task.latency_ms   = latency_ms
    task.tokens_in    = tokens_in
    task.tokens_out   = tokens_out
    task.updated_at   = datetime.utcnow()
    save_task_sync(task)

    logger.info(
        "Tâche terminée avec succès",
        task_id=task.task_id,
        provider=provider_name,
        latency_ms=round(latency_ms, 2),
        agents_count=len(llm_output.agents),
    )


def _fail_task(task: Task, error_msg: str) -> None:
    task.status     = TaskStatus.FAILED
    task.error      = error_msg
    task.updated_at = datetime.utcnow()
    save_task_sync(task)
    logger.error("Tâche échouée", task_id=task.task_id, error=error_msg)
