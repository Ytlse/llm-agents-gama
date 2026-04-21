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
import json
import hashlib
import os
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi.middleware.cors import CORSMiddleware

from llm_module.broker.redis_broker import (
    get_task_async, save_task_async, add_task_to_batch_async,
    scan_worker_metrics, get_worker_metric, WORKER_METRIC_PREFIX,
    get_sync_redis, is_provider_disabled, is_in_cooldown, DISABLED_KEY_PREFIX,
)
from llm_module.load_balancer.router import load_balancer
from llm_module.settings.models import LLMRequest, Task, TaskStatus, TaskStatusResponse
from llm_module.tasks.config import settings, get_batch_max_agents, _load_provider_defaults
from llm_module.telemetry.logger import get_logger
from llm_module.worker.task_worker import process_batch_task
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST, REGISTRY
from prometheus_client.metrics_core import CounterMetricFamily, GaugeMetricFamily


logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — warm-up connexion Celery au démarrage
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm up the Celery broker connection before the first request arrives."""
    try:
        from llm_module.worker.task_worker import celery_app
        conn = celery_app.connection()
        conn.ensure_connection(max_retries=5)
        conn.release()
        logger.info("Celery broker connection warmed up.")
    except Exception as e:
        logger.warning(f"Celery broker warm-up failed (non-fatal): {e}")
    yield


# ---------------------------------------------------------------------------
# Métriques API-side
# ---------------------------------------------------------------------------

# Agents reçus depuis GAMA (avant mini-batching)
AGENTS_RECEIVED = Counter(
    'gama_agents_received_total',
    'Total agents reçus depuis GAMA (avant mini-batching)',
    ['category'],
)

# ---------------------------------------------------------------------------
# Collecteur custom : métriques du Worker (stockées dans Redis)
# Le worker Celery n'expose pas de /metrics → on lit ses compteurs Redis ici.
# ---------------------------------------------------------------------------

class WorkerMetricsCollector:
    """
    Collecteur Prometheus qui lit les compteurs persistants du Worker depuis Redis.
    Expose :
      - llm_provider_calls_ok_total   {provider}  : appels LLM réussis par provider
      - llm_provider_calls_err_total  {provider}  : appels LLM échoués par provider
      - llm_prompts_sent_total        {category}  : prompts LLM envoyés par catégorie
      - llm_agents_batched_total      {category}  : agents batchés par catégorie
    """

    def collect(self):
        try:
            yield from self._collect()
        except Exception as exc:
            logger.error(f"WorkerMetricsCollector.collect() failed: {exc}")

    def _collect(self):
        r = get_sync_redis()

        # ── Appels LLM par provider ──────────────────────────────────────────
        # On scanne Redis directement pour ne pas dépendre de settings.providers
        # (un provider peut avoir des métriques en Redis sans clé API configurée).
        ok_fam  = CounterMetricFamily('llm_provider_calls_ok_total',  'Appels LLM réussis par provider',  labels=['provider'])
        err_fam = CounterMetricFamily('llm_provider_calls_err_total', 'Appels LLM échoués par provider',  labels=['provider'])
        ok_prefix  = f"{WORKER_METRIC_PREFIX}llm_calls_ok_total:"
        err_prefix_calls = f"{WORKER_METRIC_PREFIX}llm_calls_err_total:"
        seen_call_providers: set[str] = set()
        for key in r.scan_iter(f"{ok_prefix}*"):
            provider = key.removeprefix(ok_prefix)
            seen_call_providers.add(provider)
            val = r.get(key)
            ok_fam.add_metric([provider], int(val) if val else 0)
        for key in r.scan_iter(f"{err_prefix_calls}*"):
            provider = key.removeprefix(err_prefix_calls)
            seen_call_providers.add(provider)
        for provider in seen_call_providers:
            val = r.get(f"{err_prefix_calls}{provider}")
            err_fam.add_metric([provider], int(val) if val else 0)
        # Fallback : providers configurés mais sans appels encore (valeur 0)
        for provider in settings.providers:
            if provider not in seen_call_providers:
                ok_fam.add_metric([provider], 0)
                err_fam.add_metric([provider], 0)
        yield ok_fam
        yield err_fam

        # ── Prompts envoyés vs agents batchés (ratio mini-batch) ─────────────
        prompts_fam = CounterMetricFamily('llm_prompts_sent_total',   'Prompts LLM envoyés par catégorie', labels=['category'])
        batched_fam = CounterMetricFamily('llm_agents_batched_total', 'Agents batchés par catégorie',      labels=['category'])
        prefix = f"{WORKER_METRIC_PREFIX}prompts_sent_total:"
        for key in scan_worker_metrics("prompts_sent_total:*"):
            category = key.removeprefix(prefix)
            prompts_fam.add_metric([category], get_worker_metric(f"prompts_sent_total:{category}"))
            batched_fam.add_metric([category], get_worker_metric(f"agents_batched_total:{category}"))
        yield prompts_fam
        yield batched_fam

        # ── Tokens consommés par provider ─────────────────────────────────────
        tok_in_fam  = CounterMetricFamily('llm_tokens_in_total',  'Tokens en entrée (prompt) consommés par provider', labels=['provider'])
        tok_out_fam = CounterMetricFamily('llm_tokens_out_total', 'Tokens en sortie (completion) consommés par provider', labels=['provider'])
        tok_prefix_in  = f"{WORKER_METRIC_PREFIX}tokens_in_total:"
        tok_prefix_out = f"{WORKER_METRIC_PREFIX}tokens_out_total:"
        seen_providers = set()
        for key in r.scan_iter(f"{tok_prefix_in}*"):
            provider_label = key.removeprefix(tok_prefix_in)
            seen_providers.add(provider_label)
            val_in  = r.get(key)
            val_out = r.get(f"{tok_prefix_out}{provider_label}")
            tok_in_fam.add_metric([provider_label],  int(val_in)  if val_in  else 0)
            tok_out_fam.add_metric([provider_label], int(val_out) if val_out else 0)
        yield tok_in_fam
        yield tok_out_fam

        # ── Erreurs par provider ET type d'erreur ────────────────────────────
        err_type_fam = CounterMetricFamily(
            'llm_provider_errors_by_type_total',
            'Erreurs LLM par provider et type (rate_limit, tpm_exceeded, quota_exceeded, …)',
            labels=['provider', 'error_type'],
        )
        err_prefix = f"{WORKER_METRIC_PREFIX}llm_errors_by_type:"
        for key in r.scan_iter(f"{err_prefix}*"):
            suffix = key.removeprefix(err_prefix)
            parts  = suffix.split(":", 1)
            if len(parts) == 2:
                provider_label, error_type_label = parts
                val = r.get(key)
                err_type_fam.add_metric([provider_label, error_type_label], int(val) if val else 0)
        yield err_type_fam

        # ── Mode de transport choisi ──────────────────────────────────────────
        mode_fam = CounterMetricFamily(
            'llm_transport_mode_chosen_total',
            'Modes de transport principaux choisis par le LLM',
            labels=['mode'],
        )
        mode_prefix = f"{WORKER_METRIC_PREFIX}transport_mode_chosen:"
        for key in r.scan_iter(f"{mode_prefix}*"):
            mode_label = key.removeprefix(mode_prefix)
            val = r.get(key)
            mode_fam.add_metric([mode_label], int(val) if val else 0)
        yield mode_fam

        # ── Tranches de distance ──────────────────────────────────────────────
        dist_fam = CounterMetricFamily(
            'llm_trip_distance_bracket_total',
            'Nombre de trajets par tranche de distance',
            labels=['bracket'],
        )
        dist_prefix = f"{WORKER_METRIC_PREFIX}trip_distance_bracket:"
        for key in r.scan_iter(f"{dist_prefix}*"):
            bracket_label = key.removeprefix(dist_prefix)
            val = r.get(key)
            dist_fam.add_metric([bracket_label], int(val) if val else 0)
        yield dist_fam

        # ── Mode par tranche de distance ──────────────────────────────────────
        mode_dist_fam = CounterMetricFamily(
            'llm_mode_by_distance_total',
            'Modes de transport par tranche de distance',
            labels=['mode', 'bracket'],
        )
        md_prefix = f"{WORKER_METRIC_PREFIX}mode_by_distance:"
        for key in r.scan_iter(f"{md_prefix}*"):
            suffix = key.removeprefix(md_prefix)
            parts  = suffix.split(":", 1)
            if len(parts) == 2:
                mode_label, bracket_label = parts
                val = r.get(key)
                mode_dist_fam.add_metric([mode_label, bracket_label], int(val) if val else 0)
        yield mode_dist_fam

        # ── Mode par provider ─────────────────────────────────────────────────
        mode_prov_fam = CounterMetricFamily(
            'llm_mode_by_provider_total',
            'Modes de transport choisis par provider LLM',
            labels=['mode', 'provider'],
        )
        mp_prefix = f"{WORKER_METRIC_PREFIX}mode_by_provider:"
        for key in r.scan_iter(f"{mp_prefix}*"):
            suffix = key.removeprefix(mp_prefix)
            parts  = suffix.split(":", 1)
            if len(parts) == 2:
                mode_label, provider_label = parts
                val = r.get(key)
                mode_prov_fam.add_metric([mode_label, provider_label], int(val) if val else 0)
        yield mode_prov_fam

        # ── Indice de trajectoire choisi ──────────────────────────────────────
        idx_fam = CounterMetricFamily(
            'llm_chosen_index_total',
            'Distribution des indices de trajectoire choisis par le LLM (0 = premier choix proposé)',
            labels=['index'],
        )
        idx_prefix = f"{WORKER_METRIC_PREFIX}chosen_index:"
        for key in r.scan_iter(f"{idx_prefix}*"):
            idx_label = key.removeprefix(idx_prefix)
            val = r.get(key)
            idx_fam.add_metric([idx_label], int(val) if val else 0)
        yield idx_fam

        # ── État des providers ─────────────────────────────────────────────────
        # 0=sans_cle_api, 1=desactive_temporairement (disable_provider TTL), 2=cooldown, 3=actif
        state_fam = GaugeMetricFamily(
            'llm_provider_state',
            'État du provider: 0=sans_cle_api, 1=desactive_tmp, 2=cooldown, 3=actif',
            labels=['provider'],
        )
        all_providers = _load_provider_defaults()
        for provider in all_providers:
            if provider not in settings.providers:
                state_fam.add_metric([provider], 0)
            elif is_provider_disabled(provider):
                state_fam.add_metric([provider], 1)
            elif is_in_cooldown(provider):
                state_fam.add_metric([provider], 2)
            else:
                state_fam.add_metric([provider], 3)
        yield state_fam

        # ── TTL restant désactivation temporaire (via disable_provider) ────────
        # Expose le nombre de secondes avant réactivation automatique.
        disable_ttl_fam = GaugeMetricFamily(
            'llm_provider_disable_ttl_seconds',
            'Secondes avant réactivation automatique du provider (0 si actif)',
            labels=['provider'],
        )
        for provider in settings.providers:
            ttl = r.ttl(f"{DISABLED_KEY_PREFIX}{provider}")
            disable_ttl_fam.add_metric([provider], ttl if ttl > 0 else 0)
        yield disable_ttl_fam

        # ── Info statique providers (modèle, adapter) ──────────────────────────
        info_fam = GaugeMetricFamily(
            'llm_provider_info',
            'Informations statiques du provider (modèle, adapter)',
            labels=['provider', 'model', 'adapter'],
        )
        for provider, cfg in settings.providers.items():
            adapter = cfg.adapter or provider
            info_fam.add_metric([provider, cfg.default_model, adapter], 1)
        yield info_fam


REGISTRY.register(WorkerMetricsCollector())

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="LLM Unified Communication Module",
    description="Gateway asynchrone multi-fournisseur LLM avec load balancing RPM.",
    version="1.0.0",
    lifespan=lifespan,
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
    summary="Créer une tâche LLM batchée",
    description=(
        "Soumet une requête LLM en file d'attente pour traitement asynchrone par Celery. "
        "Les requêtes similaires (même catégorie, mêmes paramètres) sont automatiquement regroupées en lots (batchs) "
        "pour optimiser les appels aux LLMs.\n\n"
        "Retourne immédiatement un `task_id` unique à utiliser pour interroger le statut via `GET /tasks/{task_id}`."
    ),
    response_description="Le task_id généré et le statut initial de la tâche.",
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

    AGENTS_RECEIVED.labels(category=request.category).inc(len(request.agents))
    await save_task_async(task)

    # Création d'une clé de batch basée sur le contexte et les paramètres globaux.
    # Cela garantit qu'on ne merge que des tâches parfaitement compatibles !
    params_str = json.dumps(request.parameters, sort_keys=True)
    hash_str = hashlib.md5(f"{request.category}:{params_str}:{request.force_provider}".encode()).hexdigest()
    batch_key = f"{request.category}:{hash_str}"

    # Ajout à la file d'attente du batch
    queue_size = await add_task_to_batch_async(batch_key, task.task_id)
    
    # Si c'est le 1er élément du lot, on accorde un court délai (1s) pour en accumuler d'autres.
    batch_limit = get_batch_max_agents(request.force_provider)
    if queue_size == 1:
        process_batch_task.apply_async(args=[batch_key, request.force_provider], countdown=settings.batch_delay_seconds)
    elif queue_size >= batch_limit:
        process_batch_task.delay(batch_key, request.force_provider)  # Optimisation: on traite immédiatement si on est plein

    logger.info(f"Tâche créée et enqueued | task_id={task.task_id} category={request.category}")

    return {
        "task_id": task.task_id,
        "status": task.status,
        "provider_used": task.provider_used,
        "message": f"Tâche acceptée. Pollez GET /tasks/{task.task_id} pour le résultat.",
    }


@app.get(
    "/tasks/{task_id}",
    response_model=TaskStatusResponse,
    summary="Récupérer le statut et le résultat d'une tâche",
    description=(
        "Permet de faire du polling pour vérifier l'état d'une tâche précédemment soumise. "
        "Si la tâche est terminée (`status == 'success'`), le champ `result` contiendra la réponse du modèle LLM."
    ),
    response_description="L'état actuel de la tâche avec ses résultats éventuels.",
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
    summary="Vérifier la santé du service et les quotas RPM",
    description="Retourne l'état de fonctionnement de l'API Gateway ainsi que l'état courant des compteurs de requêtes par minute (RPM) pour chaque fournisseur LLM (OpenAI, vLLM, etc.).",
    response_description="Dictionnaire contenant le statut global et les métriques des fournisseurs.",
)
async def health() -> dict:
    """Retourne l'état du service et les compteurs RPM de chaque provider."""
    return {
        "status": "ok",
        "providers": load_balancer.get_status(),
    }

@app.get(
    "/metrics",
    summary="Exporter les métriques Prometheus",
    description="Expose les métriques internes de l'application (nombre de requêtes, temps de traitement, succès/échecs) au format lisible par un serveur Prometheus.",
    response_description="Texte brut au format Prometheus.",
)
async def metrics():
    """Prometheus metrics endpoint."""
    
    logger.info("Call to /metrics received.")
    
    content = generate_latest(REGISTRY)
        
    return Response(content=content, media_type=CONTENT_TYPE_LATEST)



# ---------------------------------------------------------------------------
# Lancement en développement
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("llm_module.main:app", host="0.0.0.0", port=8000, reload=True)