"""
api/routes.py — Endpoints du gateway (couche transport uniquement).

Contrat HTTP inchangé (consommé par GAMA / le controller) :
  POST /tasks                  → crée une tâche, retourne le task_id immédiatement
  GET  /tasks/{task_id}        → polling : statut + résultat si disponible
  GET  /tasks/{task_id}/wait   → long-poll (Redis Pub/Sub)
  GET  /health                 → healthcheck (statut RPM des providers)
  GET  /metrics                → export Prometheus

Les dépendances (store, queue, balancer…) sont lues dans request.app.state.deps —
composées par create_app(), jamais importées comme singletons.
"""

from __future__ import annotations
import asyncio

from fastapi import APIRouter, HTTPException, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest

from llm_module.api.deps import GatewayDeps
from llm_module.api.metrics import AGENTS_RECEIVED
from llm_module.core.batching import compute_batch_key, compute_priority_score
from llm_module.core.models import LLMRequest, Task, TaskStatus, TaskStatusResponse
from llm_module.telemetry.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


def _deps(request: Request) -> GatewayDeps:
    return request.app.state.deps


def _to_response(task: Task) -> TaskStatusResponse:
    return TaskStatusResponse(
        task_id=task.task_id,
        status=task.status,
        created_at=task.created_at,
        updated_at=task.updated_at,
        result=task.result,
        error=task.error,
        provider_used=task.provider_used,
        latency_ms=task.latency_ms,
        timing_p5=task.timing_p5,
    )


@router.post(
    "/tasks",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Créer une tâche LLM batchée",
    description=(
        "Soumet une requête LLM en file d'attente pour traitement asynchrone par Celery. "
        "Les requêtes similaires (même catégorie, mêmes paramètres) sont automatiquement regroupées en lots (batchs) "
        "pour optimiser les appels aux LLMs.\n\n"
        "Retourne immédiatement un `task_id` unique à utiliser pour interroger le statut via `GET /tasks/{task_id}`."
    ),
    response_description="Le task_id généré et le statut initial de la tâche.",
)
async def create_task(payload: LLMRequest, request: Request) -> dict:
    """
    1. Valide la requête (Pydantic)
    2. Crée la tâche avec statut PENDING et la persiste
    3. L'ajoute à sa file de batch et planifie le dispatch Celery
    4. Retourne immédiatement
    """
    from llm_module.worker.task_worker import process_batch_task

    deps = _deps(request)
    priority_score = compute_priority_score(payload.agents)
    task = Task(request=payload, priority_score=priority_score)

    AGENTS_RECEIVED.labels(category=payload.category).inc(len(payload.agents))
    await deps.store.save(task)

    # Clé de batch basée sur le contexte et les paramètres globaux : on ne merge
    # que des tâches parfaitement compatibles.
    batch_key = compute_batch_key(payload)
    queue_size = await deps.queue.add(batch_key, task.task_id, priority_score)

    # Batch plein → dispatch immédiat. Sinon, on accorde un court délai pour
    # accumuler d'autres tâches ; le flag SETNX garantit qu'exactement un dispatch
    # différé est planifié par cycle de batch, quel que soit l'ordre d'arrivée
    # des requêtes concurrentes (queue_size seul ne suffit pas : deux requêtes
    # simultanées peuvent toutes deux observer queue_size == 2).
    settings = deps.settings
    batch_limit = settings.get_batch_max_agents(payload.force_provider)
    # Budget de sortie d'une tâche : le load balancer écarte les providers dont
    # le plafond de complétion (max_output_tokens) ne peut pas servir une seule tâche.
    min_output_required = payload.parameters.get("max_tokens")
    loop = asyncio.get_event_loop()
    if queue_size >= batch_limit:
        await loop.run_in_executor(
            None,
            lambda: process_batch_task.delay(batch_key, payload.force_provider, payload.min_tpm_required, min_output_required),
        )
    elif await deps.queue.try_mark_scheduled(batch_key, ttl=int(settings.batch_delay_seconds) + 30):
        await loop.run_in_executor(
            None,
            lambda: process_batch_task.apply_async(
                args=[batch_key, payload.force_provider, payload.min_tpm_required, min_output_required],
                countdown=settings.batch_delay_seconds,
            ),
        )

    logger.info(f"Tâche créée et enqueued | task_id={task.task_id} category={payload.category}")

    return {
        "task_id": task.task_id,
        "status": task.status,
        "provider_used": task.provider_used,
        "message": f"Tâche acceptée. Pollez GET /tasks/{task.task_id} pour le résultat.",
    }


@router.get(
    "/tasks/{task_id}",
    response_model=TaskStatusResponse,
    summary="Récupérer le statut et le résultat d'une tâche",
    description=(
        "Permet de faire du polling pour vérifier l'état d'une tâche précédemment soumise. "
        "Si la tâche est terminée (`status == 'success'`), le champ `result` contiendra la réponse du modèle LLM."
    ),
    response_description="L'état actuel de la tâche avec ses résultats éventuels.",
)
async def get_task_status(task_id: str, request: Request) -> TaskStatusResponse:
    task = await _deps(request).store.get(task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tâche '{task_id}' introuvable ou expirée.",
        )

    return _to_response(task)


@router.get(
    "/tasks/{task_id}/wait",
    response_model=TaskStatusResponse,
    summary="Attendre la fin d'une tâche (long-poll Redis Pub/Sub)",
    description=(
        "Bloque jusqu'à ce que la tâche atteigne un état terminal (success/failed) "
        "ou que le timeout expire. Latence de notification ~10ms via Redis Pub/Sub. "
        "Se reconnecte automatiquement si la socket pubsub est interrompue avant la fin du timeout."
    ),
)
async def wait_for_task(task_id: str, request: Request, timeout: float = 120.0) -> TaskStatusResponse:
    timeout = min(max(timeout, 1.0), 300.0)
    task = await _deps(request).store.wait_done(task_id, timeout)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tâche '{task_id}' introuvable ou expirée.",
        )

    return _to_response(task)


@router.get(
    "/health",
    summary="Vérifier la santé du service et les quotas RPM",
    description="Retourne l'état de fonctionnement de l'API Gateway ainsi que l'état courant des compteurs de requêtes par minute (RPM) pour chaque fournisseur LLM.",
    response_description="Dictionnaire contenant le statut global et les métriques des fournisseurs.",
)
async def health(request: Request) -> dict:
    return {
        "status": "ok",
        "providers": _deps(request).balancer.get_status(),
    }


@router.get(
    "/errors/recent",
    summary="Dernières erreurs LLM remontées par les providers",
    description=(
        "Retourne les dernières erreurs LLM (message brut, provider, type, code HTTP) "
        "depuis le ring buffer Redis. Consommé par le panneau 'Dernières erreurs' du cockpit "
        "Grafana (datasource Infinity) — Prometheus ne stockant que du numérique."
    ),
    response_description="Liste JSON des erreurs, de la plus récente à la plus ancienne.",
)
async def recent_errors(request: Request, limit: int = 50) -> list[dict]:
    limit = min(max(limit, 1), 50)
    loop = asyncio.get_event_loop()
    metrics_sink = _deps(request).metrics
    return await loop.run_in_executor(None, metrics_sink.recent_errors, limit)


@router.get(
    "/metrics",
    summary="Exporter les métriques Prometheus",
    description="Expose les métriques internes de l'application au format lisible par un serveur Prometheus.",
    response_description="Texte brut au format Prometheus.",
)
async def metrics():
    loop = asyncio.get_event_loop()
    # generate_latest lit Redis de manière synchrone, on l'isole dans un thread
    content = await loop.run_in_executor(None, generate_latest, REGISTRY)
    return Response(content=content, media_type=CONTENT_TYPE_LATEST)
