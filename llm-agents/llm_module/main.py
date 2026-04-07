"""
main.py — API Gateway FastAPI.

Endpoints :
  POST /tasks            → Crée une tâche, retourne le task_id immédiatement
  GET  /tasks/{task_id}  → Polling : retourne le statut et le résultat si disponible
  GET  /health           → Healthcheck (inclut le statut RPM des providers)

Le flux est 100% non-bloquant :
  - L'API ne fait QUE valider + enqueuer
  - Le Worker Celery traite en arrière-plan
  - Le client poll jusqu'à status == "success" | "failed"
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from llm_module.broker.redis_broker import get_task_async, save_task_async
from llm_module.load_balancer.router import load_balancer
from llm_module.settings.models import LLMRequest, Task, TaskStatus, TaskStatusResponse
from llm_module.telemetry.logger import get_logger
from llm_module.worker.task_worker import process_llm_task

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="LLM Unified Communication Module",
    description="Gateway asynchrone multi-fournisseur LLM avec load balancing RPM.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # À restreindre en production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post(
    "/tasks",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Créer une tâche LLM",
    description=(
        "Soumet une requête LLM en file d'attente. "
        "Retourne immédiatement un task_id. "
        "Utilisez GET /tasks/{task_id} pour récupérer le résultat."
    ),
)
async def create_task(request: LLMRequest) -> dict:
    """
    1. Valide la requête (Pydantic)
    2. Crée la tâche avec statut PENDING
    3. Persiste en Redis
    4. Enqueues le task_id dans Celery
    5. Retourne immédiatement
    """
    task = Task(request=request)

    await save_task_async(task)

    # Envoi à Celery — uniquement le task_id (pas toute la tâche)
    process_llm_task.delay(task.task_id)

    logger.info("Tâche créée et enqueued", task_id=task.task_id, category=request.category)

    return {
        "task_id": task.task_id,
        "status": task.status,
        "message": f"Tâche acceptée. Pollez GET /tasks/{task.task_id} pour le résultat.",
    }


@app.get(
    "/tasks/{task_id}",
    response_model=TaskStatusResponse,
    summary="Récupérer le statut d'une tâche",
)
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """
    Retourne le statut courant de la tâche.
    Si status == "success", le champ `result` contient les réponses des agents.
    """
    task = await get_task_async(task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tâche '{task_id}' introuvable ou expirée.",
        )

    return TaskStatusResponse(
        task_id=task.task_id,
        status=task.status,
        created_at=task.created_at,
        updated_at=task.updated_at,
        result=task.result,
        error=task.error,
        provider_used=task.provider_used,
        latency_ms=task.latency_ms,
    )


@app.get(
    "/health",
    summary="Healthcheck et statut RPM",
)
async def health() -> dict:
    """Retourne l'état du service et les compteurs RPM de chaque provider."""
    return {
        "status": "ok",
        "providers": load_balancer.get_status(),
    }


# ---------------------------------------------------------------------------
# Lancement en développement
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("llm_module.main:app", host="0.0.0.0", port=8000, reload=True)
