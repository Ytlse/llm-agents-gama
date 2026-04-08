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
from llm_module.broker.redis_broker import (
    get_task_sync,
    save_task_sync,
    mark_cooldown,
    pop_tasks_from_batch_sync,
    requeue_tasks_sync,
    _batch_queue_key,
    get_sync_redis,
)
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
    name="process_batch_task",
    bind=True,
    max_retries=settings.max_retries,
)
def process_batch_task(self, batch_key: str) -> None:
    """
    Point d'entrée Celery pour le traitement par lot (micro-batching).
    `bind=True` pour accéder à `self.retry()`.
    """
    tasks = pop_tasks_from_batch_sync(batch_key, settings.batch_max_agents)
    if not tasks:
        return

    # Marquer comme en cours
    for task in tasks:
        task.status = TaskStatus.RUNNING
        task.updated_at = datetime.utcnow()
        save_task_sync(task)

    batch_id = f"batch_{tasks[0].task_id[:8]}_{len(tasks)}"

    try:
        _execute_batch(tasks, batch_id)

    except ProviderServerError as e:
        # Erreur 5xx → exclusion temporaire, backoff exponentiel et retry
        mark_cooldown(e.provider, timeout=60)
        delay = min(settings.backoff_base_seconds * (2 ** self.request.retries), 30.0)
        logger.warning(
            "Erreur serveur provider, retry planifié",
            task_id=batch_id,
            provider=e.provider,
            http_status=e.status_code,
            retry_in=delay,
            attempt=self.request.retries + 1,
        )
        if self.request.retries < self.max_retries:
            requeue_tasks_sync(batch_key, [t.task_id for t in tasks])
            raise self.retry(exc=e, countdown=delay)
        else:
            for t in tasks:
                _fail_task(t, f"Max retries dépassé suite à une erreur 5xx sur {e.provider}")

    except ProviderClientError as e:
        if e.status_code == 429:
            # Rate limit (Too Many Requests) → exclusion temporaire et retry
            mark_cooldown(e.provider, timeout=60)
            delay = min(settings.backoff_base_seconds * (2 ** self.request.retries), 30.0)
            logger.warning(
                "Rate limit (429) atteint, provider en cooldown, retry planifié",
                task_id=batch_id,
                provider=e.provider,
                retry_in=delay,
                attempt=self.request.retries + 1,
            )
            if self.request.retries < self.max_retries:
                requeue_tasks_sync(batch_key, [t.task_id for t in tasks])
                raise self.retry(exc=e, countdown=delay)
            else:
                for t in tasks:
                    _fail_task(t, f"Max retries dépassé suite aux Rate Limits sur {e.provider}")
        else:
            # Autre erreur 4xx → échec définitif, pas de retry
            for t in tasks:
                _fail_task(t, str(e))

    except RuntimeError as e:
        if "Tous les fournisseurs" in str(e) or "indisponible" in str(e):
            # Tous les LLM sont bloqués : on attend 15s par retry
            delay = 15.0
            logger.warning(
                "Fournisseurs saturés ou en cooldown, retry planifié",
                task_id=batch_id,
                retry_in=delay,
                attempt=self.request.retries + 1,
            )
            if self.request.retries < self.max_retries:
                requeue_tasks_sync(batch_key, [t.task_id for t in tasks])
                raise self.retry(exc=e, countdown=delay)
            else:
                for t in tasks:
                    _fail_task(t, "Max retries dépassé : Tous les fournisseurs indisponibles.")
        else:
            logger.exception("RuntimeError inattendue dans le worker", task_id=batch_id)
            for t in tasks:
                _fail_task(t, f"RuntimeError interne : {str(e)}")

    except ProviderParseError as e:
        logger.exception("Erreur de parsing de la réponse du provider", task_id=batch_id)
        for t in tasks:
            _fail_task(t, f"Erreur de parsing [{e.provider}]: {str(e.raw)}")

    except Exception as e:
        # Cas générique — on logue avec stacktrace complète via logger.exception
        logger.exception("Exception inattendue dans le worker", task_id=batch_id, error=str(e))
        for t in tasks:
            _fail_task(t, f"Exception interne : {str(e)}")

    else:
        # Succès complet : relancer un worker s'il reste des éléments dans cette file
        r = get_sync_redis()
        if r.llen(_batch_queue_key(batch_key)) > 0:
            process_batch_task.delay(batch_key)


# ---------------------------------------------------------------------------
# Logique métier
# ---------------------------------------------------------------------------

def _execute_batch(tasks: list[Task], batch_id: str) -> None:
    base_req = tasks[0].request
    merged_agents = []
    for t in tasks:
        merged_agents.extend(t.request.agents)

    # 1. Sélection du provider
    provider_name = load_balancer.select_provider(force=base_req.force_provider)

    # 2. Construction du prompt
    messages = prompt_manager.render(
        category=base_req.category,
        agents=merged_agents,
        parameters=base_req.parameters,
    )
    schema = prompt_manager.get_output_schema(base_req.category)

    # 3. Assemblage de la requête interne
    internal_req = InternalRequest(
        provider=provider_name,
        messages=messages,
        response_schema=schema,
        temperature=base_req.parameters.get("temperature", 0.7),
        max_tokens=base_req.parameters.get("max_tokens", 4096),
    )

    # 4. Enregistrement du call RPM (avant l'appel, pour le circuit breaker)
    load_balancer.record_call(provider_name)

    # 5. Appel LLM via l'adapter approprié
    adapter = get_adapter(provider_name)
    start_ts = time.monotonic()

    llm_output, tokens_in, tokens_out = adapter.call(internal_req)

    logger.debug("LLM output reçu", agents_count=len(llm_output.agents))

    latency_ms = (time.monotonic() - start_ts) * 1000

    # 6. Télémétrie
    log_llm_call(
        task_id=batch_id,
        provider=provider_name,
        status="success",
        latency_ms=latency_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        http_status=200,
    )

    # 7. Démultiplexage et Persistance des résultats
    results_by_agent = {}
    for a in llm_output.agents:
        aid = a.get("agent_id") if isinstance(a, dict) else getattr(a, "agent_id", None)
        if aid:
            results_by_agent[aid] = a

    for t in tasks:
        t_agent_ids = [a.agent_id for a in t.request.agents]
        t_results = [results_by_agent[aid] for aid in t_agent_ids if aid in results_by_agent]

        t.status        = TaskStatus.SUCCESS
        t.result        = t_results
        t.provider_used = provider_name
        t.latency_ms    = latency_ms
        t.tokens_in     = tokens_in // len(tasks)   # Approximation du coût par tâche
        t.tokens_out    = tokens_out // len(tasks)
        t.updated_at    = datetime.utcnow()
        save_task_sync(t)

    logger.info(
        "Batch terminé avec succès",
        task_id=batch_id,
        tasks_merged=len(tasks),
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
