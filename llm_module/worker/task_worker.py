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
  tentative 4 → attente 8s  (max_retries=settings.max_retries dans config)
"""

from __future__ import annotations
import time
from datetime import datetime

from celery import Celery

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
    increment_worker_metric,
    increment_worker_error_by_type,
    increment_consecutive_errors,
    reset_consecutive_errors,
    disable_provider,
    decrement_rpm,
    increment_active_worker,
    decrement_active_worker,
)
from llm_module.load_balancer.router import load_balancer
from llm_module.prompts.manager import prompt_manager
from llm_module.telemetry.logger import get_logger, log_llm_call, log_llm_exchange, log_llm_error

logger = get_logger(__name__)

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
def process_batch_task(self, batch_key: str, force_provider: str | None = None) -> None:
    """
    Point d'entrée Celery pour le traitement par lot (micro-batching).
    `bind=True` pour accéder à `self.retry()`.
    """
    # Sélectionner le provider en premier pour utiliser sa limite de batch.
    # Si tous les providers sont saturés, RuntimeError est levée ici, avant
    # de dépiler les tâches (elles restent en file pour le prochain retry).
    try:
        provider_name = load_balancer.select_provider(force=force_provider)
    except RuntimeError as e:
        delay = 5.0
        # logger.warning(
        #     f"Fournisseurs saturés ou en cooldown, retry planifié | "
        #     f"task_id={batch_key} retry_in={delay:.1f}s attempt={self.request.retries + 1}"
        # )
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=delay)
        else:
            tasks = pop_tasks_from_batch_sync(batch_key, 100)
            for t in tasks:
                _fail_task(t, "Max retries dépassé : Tous les fournisseurs sont saturés ou en cooldown.")
        return

    # ------------------------------------------------------------------
    # Début du tracking d'occupation du provider
    # ------------------------------------------------------------------
    increment_active_worker(provider_name)
    try:
        batch_limit = settings.providers[provider_name].batch_max_agents
    
        r = get_sync_redis()
        queue_depth_before = r.llen(_batch_queue_key(batch_key))
        tasks = pop_tasks_from_batch_sync(batch_key, batch_limit)
        if not tasks:
            return
    
        queue_depth_after = r.llen(_batch_queue_key(batch_key))
        agents_count = sum(len(t.request.agents) for t in tasks)
        logger.info(
            f"[worker] Batch démarré | batch_key={batch_key} tasks={len(tasks)} "
            f"agents={agents_count} provider={provider_name} batch_limit={batch_limit} "
            f"queue_before={queue_depth_before} queue_after={queue_depth_after}"
        )
    
        # Marquer comme en cours
        for task in tasks:
            task.status = TaskStatus.RUNNING
            task.updated_at = datetime.utcnow()
            save_task_sync(task)
    
        batch_id = f"batch_{tasks[0].task_id[:8]}_{len(tasks)}"
    
        try:
            _execute_batch(tasks, batch_id, provider_name)
    
        except ProviderServerError as e:
            # Erreur 5xx → exclusion temporaire, backoff exponentiel et retry
            mark_cooldown(e.provider, timeout=60)
            delay = min(settings.backoff_base_seconds * (2 ** self.request.retries), 30.0)
            logger.warning(
                f"Erreur serveur provider, retry planifié | task_id={batch_id} "
                f"provider={e.provider} http_status={e.status_code} "
                f"retry_in={delay:.1f}s attempt={self.request.retries + 1}"
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
                    f"Rate limit (429) atteint, provider en cooldown, retry planifié | "
                    f"task_id={batch_id} provider={e.provider} "
                    f"retry_in={delay:.1f}s attempt={self.request.retries + 1}"
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
                # Tous les LLM sont bloqués : on attend 5s par retry
                delay = 5.0
                logger.warning(
                    f"Fournisseurs saturés ou en cooldown, retry planifié | "
                    f"task_id={batch_id} retry_in={delay:.1f}s attempt={self.request.retries + 1}"
                )
                if self.request.retries < self.max_retries:
                    requeue_tasks_sync(batch_key, [t.task_id for t in tasks])
                    raise self.retry(exc=e, countdown=delay)
                else:
                    for t in tasks:
                        _fail_task(t, "Max retries dépassé : Tous les fournisseurs indisponibles.")
            else:
                logger.exception(f"RuntimeError inattendue dans le worker | task_id={batch_id}")
                for t in tasks:
                    _fail_task(t, f"RuntimeError interne : {str(e)}")
    
        except ProviderParseError as e:
            logger.exception(
                f"Erreur de parsing de la réponse du provider | task_id={batch_id} "
                f"detail={str(e)} raw_preview={str(e.raw)[:300]!r}"
            )
            for t in tasks:
                _fail_task(t, f"{str(e)}\nRaw LLM response:\n{e.raw}")
    
        except Exception as e:
            # Cas générique — on logue avec stacktrace complète via logger.exception
            logger.exception(f"Exception inattendue dans le worker | task_id={batch_id} error={e}")
            for t in tasks:
                _fail_task(t, f"Exception interne : {str(e)}")
    
        else:
            # Succès complet : relancer un worker s'il reste des éléments dans cette file
            r = get_sync_redis()
            if r.llen(_batch_queue_key(batch_key)) > 0:
                process_batch_task.delay(batch_key, force_provider)
    finally:
        # Quoi qu'il arrive (succès, échec, retry, timeout...), on libère le slot !
        decrement_active_worker(provider_name)


# ---------------------------------------------------------------------------
# Logique métier
# ---------------------------------------------------------------------------

def _execute_batch(tasks: list[Task], batch_id: str, provider_name: str) -> None:
    base_req = tasks[0].request
    merged_agents = []
    for t in tasks:
        merged_agents.extend(t.request.agents)

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

    # 4. Appel LLM via l'adapter approprié
    adapter = get_adapter(provider_name)
    start_ts = time.monotonic()

    try:
        llm_output, tokens_in, tokens_out = adapter.call(internal_req)
    except Exception as exc:
        decrement_rpm(provider_name)
        logger.error(f"Error with provider | task_id={batch_id} provider={provider_name}")
        increment_worker_metric(f"llm_calls_err_total:{provider_name}")
        error_type = getattr(exc, "error_type", "unknown")
        http_status = getattr(exc, "status_code", None)
        log_llm_error(
            task_id=batch_id,
            provider=provider_name,
            error_type=error_type,
            error_message=str(exc),
            http_status=http_status,
        )
        increment_worker_error_by_type(provider_name, error_type)
        consecutive = increment_consecutive_errors(provider_name)
        if consecutive >= 30:
            cfg = settings.providers.get(provider_name)
            timeout = cfg.disable_timeout if cfg else 180
            disable_provider(provider_name, timeout=timeout)
            logger.error(
                f"Provider désactivé pendant {timeout}s après {consecutive} erreurs consécutives | "
                f"provider={provider_name}"
            )
        raise

    reset_consecutive_errors(provider_name)

    # ── Métriques métier : mode de transport et tranche de distance ──────────
    agent_specs_by_id = {a.agent_id: a for a in merged_agents}
    for agent_resp in llm_output.agents:
        primary_mode = _extract_primary_mode(agent_resp.mode or "unknown")
        increment_worker_metric(f"transport_mode_chosen:{primary_mode}")
        increment_worker_metric(f"mode_by_provider:{primary_mode}:{provider_name}")

        spec = agent_specs_by_id.get(agent_resp.agent_id)
        if spec and agent_resp.chosen_index is not None and spec.trajectories:
            idx = agent_resp.chosen_index
            if 0 <= idx < len(spec.trajectories):
                dist_m = float(spec.trajectories[idx].get("total_distance_m") or 0)
                bracket = _get_distance_bracket(dist_m)
                increment_worker_metric(f"trip_distance_bracket:{bracket}")
                increment_worker_metric(f"mode_by_distance:{primary_mode}:{bracket}")
                increment_worker_metric(f"chosen_index:{idx}")

    #logger.debug(f"LLM output reçu | agents_count={len(llm_output.agents)}")

    latency_ms = (time.monotonic() - start_ts) * 1000

    # Métriques: appel réussi + batching (agents reçus → 1 prompt envoyé)
    increment_worker_metric(f"llm_calls_ok_total:{provider_name}")
    increment_worker_metric(f"prompts_sent_total:{base_req.category}")
    increment_worker_metric(f"agents_batched_total:{base_req.category}", amount=len(merged_agents))

    # Métriques tokens
    increment_worker_metric(f"tokens_in_total:{provider_name}", amount=tokens_in)
    increment_worker_metric(f"tokens_out_total:{provider_name}", amount=tokens_out)
    increment_worker_metric("tokens_in_total:__all__", amount=tokens_in)
    increment_worker_metric("tokens_out_total:__all__", amount=tokens_out)

    # 6. Log de l'échange LLM (prompt + réponse + tokens) dans workdir/llm_exchanges.jsonl
    log_llm_exchange(
        task_id=batch_id,
        provider=provider_name,
        messages=[{"role": m.role, "content": m.content} for m in messages],
        response=[a.model_dump() if hasattr(a, "model_dump") else a for a in llm_output.agents],
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )

    # 7. Télémétrie métriques
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

    n = len(tasks)
    base_in,  rem_in  = divmod(tokens_in,  n)
    base_out, rem_out = divmod(tokens_out, n)

    for i, t in enumerate(tasks):
        t_agent_ids = [a.agent_id for a in t.request.agents]
        t_results = [results_by_agent[aid] for aid in t_agent_ids if aid in results_by_agent]

        t.status        = TaskStatus.SUCCESS
        t.result        = t_results
        t.provider_used = provider_name
        t.latency_ms    = latency_ms
        t.tokens_in     = base_in  + (rem_in  if i == n - 1 else 0)
        t.tokens_out    = base_out + (rem_out if i == n - 1 else 0)
        t.updated_at    = datetime.utcnow()
        save_task_sync(t)

    logger.info(
        f"Batch terminé avec succès | task_id={batch_id} tasks_merged={len(tasks)} "
        f"provider={provider_name} latency_ms={latency_ms:.1f} agents_count={len(llm_output.agents)}"
    )


def _fail_task(task: Task, error_msg: str) -> None:
    task.status     = TaskStatus.FAILED
    task.error      = error_msg
    task.updated_at = datetime.utcnow()
    save_task_sync(task)
    logger.error(f"Tâche échouée | task_id={task.task_id} error={error_msg}")


# ---------------------------------------------------------------------------
# Helpers métriques métier
# ---------------------------------------------------------------------------

def _extract_primary_mode(mode: str) -> str:
    """
    Réduit une chaîne de modes composée ("foot,bus,foot") au mode principal.
    Priorité : metro > tram > bus > car > cycling > walking > other
    """
    if not mode or mode == "unknown":
        return "unknown"
    parts = {m.strip().lower() for m in mode.split(",")}
    if "metro" in parts or "subway" in parts:
        return "metro"
    if "tram" in parts or "tramway" in parts:
        return "tram"
    if "bus" in parts:
        return "bus"
    if "car" in parts or "driving" in parts:
        return "car"
    if "bicycle" in parts or "bike" in parts or "cycling" in parts:
        return "cycling"
    if parts <= {"foot", "walk", "walking"}:
        return "walking"
    return "other"


def _get_distance_bracket(distance_m: float) -> str:
    """Classe une distance en mètres dans une tranche prédéfinie."""
    if distance_m < 1_000:
        return "0-1km"
    if distance_m < 3_000:
        return "1-3km"
    if distance_m < 5_000:
        return "3-5km"
    if distance_m < 15_000:
        return "5-15km"
    return ">15km"
