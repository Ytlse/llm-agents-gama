"""
broker/redis_broker.py — Connexion Redis et helpers pour la persistance des tâches.

Redis remplit ici deux rôles distincts :
  1. Broker de messages pour Celery (file d'attente des tâches) → DB 1 (via celery_broker_url)
  2. Stockage du statut/résultat des tâches (polling client)    → DB 0 (via redis_url)
  3. Compteurs RPM pour le load balancer                        → DB 0 (préfixe rpm:)

Note : les numéros de DB effectifs dépendent des variables d'environnement redis_url
et celery_broker_url.
"""

from __future__ import annotations
import json
from typing import Optional

import redis.asyncio as aioredis
import redis as sync_redis

from llm_module.settings.models import Task, TaskStatus
from llm_module.tasks.config import settings


# ---------------------------------------------------------------------------
# Pool de connexions
# ---------------------------------------------------------------------------

# Pool async (utilisé par FastAPI)
_async_pool: Optional[aioredis.Redis] = None

# Pool sync (utilisé par le Worker Celery qui tourne en contexte synchrone)
_sync_pool: Optional[sync_redis.Redis] = None


def get_async_redis() -> aioredis.Redis:
    global _async_pool
    if _async_pool is None:
        _async_pool = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _async_pool


def get_sync_redis() -> sync_redis.Redis:
    global _sync_pool
    if _sync_pool is None:
        _sync_pool = sync_redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _sync_pool


# ---------------------------------------------------------------------------
# Clés Redis
# ---------------------------------------------------------------------------

TASK_KEY_PREFIX        = "task:"
RPM_KEY_PREFIX         = "rpm:"
COOLDOWN_KEY_PREFIX    = "cooldown:"
BATCH_QUEUE_PREFIX     = "batch:"
CONS_ERR_KEY_PREFIX    = "cons_err:"
DISABLED_KEY_PREFIX    = "disabled:"
ACTIVE_WORKER_PREFIX   = "active_workers:"


def _task_key(task_id: str) -> str:
    return f"{TASK_KEY_PREFIX}{task_id}"


def _rpm_key(provider: str) -> str:
    """
    Clé Redis pour le compteur RPM d'un fournisseur.
    TTL de 60 s — Redis réinitialise automatiquement le compteur toutes les minutes.
    """
    return f"{RPM_KEY_PREFIX}{provider}"


def _cooldown_key(provider: str) -> str:
    return f"{COOLDOWN_KEY_PREFIX}{provider}"


def _batch_queue_key(batch_key: str) -> str:
    return f"{BATCH_QUEUE_PREFIX}{batch_key}"


# ---------------------------------------------------------------------------
# CRUD tâches (async — utilisé par l'API Gateway)
# ---------------------------------------------------------------------------

async def save_task_async(task: Task) -> None:
    r = get_async_redis()
    await r.set(_task_key(task.task_id), task.model_dump_json(), ex=3600)


async def get_task_async(task_id: str) -> Optional[Task]:
    r = get_async_redis()
    raw = await r.get(_task_key(task_id))
    if raw is None:
        return None
    return Task.model_validate_json(raw)


# ---------------------------------------------------------------------------
# CRUD tâches (sync — utilisé par le Worker Celery)
# ---------------------------------------------------------------------------

def save_task_sync(task: Task) -> None:
    r = get_sync_redis()
    r.set(_task_key(task.task_id), task.model_dump_json(), ex=3600)


def get_task_sync(task_id: str) -> Optional[Task]:
    r = get_sync_redis()
    raw = r.get(_task_key(task_id))
    if raw is None:
        return None
    return Task.model_validate_json(raw)


# ---------------------------------------------------------------------------
# Compteurs RPM (sync — utilisé par le load balancer depuis le Worker)
# ---------------------------------------------------------------------------

def increment_rpm(provider: str) -> int:
    """
    Incrémente le compteur RPM d'un fournisseur.
    Le TTL de 60 s garantit la réinitialisation automatique toutes les minutes.
    Retourne la valeur courante après incrément.
    """
    r = get_sync_redis()
    key = _rpm_key(provider)
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.ttl(key)
    results = pipe.execute()
    count = int(results[0])
    ttl = results[1]
    if ttl == -1:  # Clé sans TTL : première incrémentation ou TTL perdu
        r.expire(key, 60)
    return count


def get_rpm(provider: str) -> int:
    """Retourne le compteur RPM actuel d'un fournisseur (0 si inexistant)."""
    r = get_sync_redis()
    val = r.get(_rpm_key(provider))
    return int(val) if val else 0


# Script Lua pour la réservation atomique d'un slot RPM.
# Garantit que l'incrément et la vérification de limite sont une opération indivisible,
# éliminant la race condition entre plusieurs workers Celery concurrents.
_TRY_RESERVE_RPM_SCRIPT = r"""
local key   = KEYS[1]
local limit = tonumber(ARGV[1])
local ttl   = tonumber(ARGV[2])
local count = redis.call('INCR', key)
if redis.call('TTL', key) == -1 then
    redis.call('EXPIRE', key, ttl)
end
if count > limit then
    redis.call('DECR', key)
    return 0
end
return count
"""


def try_reserve_rpm(provider: str, limit: int, ttl: int = 60) -> bool:
    """
    Tente de réserver atomiquement un slot RPM pour le fournisseur.

    Utilise un script Lua exécuté côté Redis pour garantir que le INCR et la
    vérification de la limite forment une opération atomique — aucun autre
    worker ne peut s'intercaler entre les deux.

    Retourne True si le slot a été réservé (compteur ≤ limit),
             False si la limite est déjà atteinte (rollback automatique).
    """
    r = get_sync_redis()
    result = r.eval(_TRY_RESERVE_RPM_SCRIPT, 1, _rpm_key(provider), limit, ttl)
    return int(result) > 0


# ---------------------------------------------------------------------------
# Cooldown (sync — utilisé pour exclure temporairement un fournisseur)
# ---------------------------------------------------------------------------

def mark_cooldown(provider: str, timeout: int = 60) -> None:
    """Place un fournisseur en quarantaine pour une durée donnée."""
    r = get_sync_redis()
    r.set(_cooldown_key(provider), "1", ex=timeout)


def is_in_cooldown(provider: str) -> bool:
    """Vérifie si un fournisseur est actuellement en quarantaine."""
    r = get_sync_redis()
    return r.exists(_cooldown_key(provider)) > 0


# ---------------------------------------------------------------------------
# Erreurs consécutives et désactivation permanente (sync)
# ---------------------------------------------------------------------------

def increment_consecutive_errors(provider: str) -> int:
    """Incrémente le compteur d'erreurs consécutives. Retourne la nouvelle valeur."""
    return int(get_sync_redis().incr(f"{CONS_ERR_KEY_PREFIX}{provider}"))


def reset_consecutive_errors(provider: str) -> None:
    """Remet le compteur à zéro (appel réussi)."""
    get_sync_redis().delete(f"{CONS_ERR_KEY_PREFIX}{provider}")


def get_consecutive_errors(provider: str) -> int:
    val = get_sync_redis().get(f"{CONS_ERR_KEY_PREFIX}{provider}")
    return int(val) if val else 0


def decrement_rpm(provider: str) -> None:
    """Restitue un slot RPM réservé lorsque l'appel LLM échoue côté serveur.
    Évite que les erreurs consomment du quota sans appel réussi."""
    r = get_sync_redis()
    key = _rpm_key(provider)
    # On décrémente seulement si la clé existe (sinon DECR créerait -1)
    if r.exists(key):
        r.decr(key)


def disable_provider(provider: str, timeout: int = 180) -> None:
    """Désactive temporairement un fournisseur pour `timeout` secondes.
    À l'expiration du TTL, Redis supprime la clé et le fournisseur redevient éligible."""
    r = get_sync_redis()
    r.set(f"{DISABLED_KEY_PREFIX}{provider}", "1", ex=timeout)
    r.delete(f"{CONS_ERR_KEY_PREFIX}{provider}")


def enable_provider(provider: str) -> None:
    """Réactive un fournisseur et remet à zéro son compteur d'erreurs et son RPM.
    Le compteur RPM est vidé pour éviter un burst immédiat si la clé est encore active."""
    r = get_sync_redis()
    r.delete(f"{DISABLED_KEY_PREFIX}{provider}")
    r.delete(f"{CONS_ERR_KEY_PREFIX}{provider}")
    r.delete(_rpm_key(provider))


def reset_all_rpm_counters(provider_names: list[str]) -> None:
    """Remet à zéro les compteurs RPM de tous les providers au démarrage."""
    r = get_sync_redis()
    keys = [_rpm_key(name) for name in provider_names]
    if keys:
        r.delete(*keys)


def is_provider_disabled(provider: str) -> bool:
    """Vérifie si un fournisseur a été désactivé suite à trop d'erreurs consécutives."""
    return get_sync_redis().exists(f"{DISABLED_KEY_PREFIX}{provider}") > 0



# ---------------------------------------------------------------------------
# Tracking des requêtes actives (Concurrency Limit)
# ---------------------------------------------------------------------------

def increment_active_worker(provider: str) -> int:
    """Incrémente le compteur de workers actifs pour un provider."""
    r = get_sync_redis()
    key = f"{ACTIVE_WORKER_PREFIX}{provider}"
    val = r.incr(key)
    if val == 1:
        r.expire(key, 600)  # Sécurité : expire après 10 minutes si le worker plante
    return val

def decrement_active_worker(provider: str) -> int:
    """Décrémente le compteur de workers actifs pour un provider."""
    r = get_sync_redis()
    key = f"{ACTIVE_WORKER_PREFIX}{provider}"
    val = r.decr(key)
    if val < 0:
        r.set(key, 0)
        val = 0
    return val

def get_active_workers(provider: str) -> int:
    """Retourne le nombre de workers actuellement occupés par ce provider."""
    val = get_sync_redis().get(f"{ACTIVE_WORKER_PREFIX}{provider}")
    return int(val) if val else 0


# ---------------------------------------------------------------------------
# Micro-Batching (sync / async)
# ---------------------------------------------------------------------------

async def add_task_to_batch_async(batch_key: str, task_id: str) -> int:
    """Ajoute une tâche au bout de la file de batch et retourne la taille de la file."""
    r = get_async_redis()
    key = _batch_queue_key(batch_key)
    await r.rpush(key, task_id)
    await r.expire(key, 3600)
    return await r.llen(key)


def pop_tasks_from_batch_sync(batch_key: str, max_agents: int) -> list[Task]:
    """Dépile les tâches de la file de batch jusqu'à atteindre la limite d'agents."""
    r = get_sync_redis()
    key = _batch_queue_key(batch_key)
    selected_tasks = []
    current_agents_count = 0

    while True:
        task_id = r.lpop(key)
        if not task_id:
            break

        task = get_task_sync(task_id)
        if not task:
            continue

        agents_in_task = len(task.request.agents)
        if current_agents_count + agents_in_task > max_agents and current_agents_count > 0:
            # Dépasse la limite et on a déjà des tâches : on remet la tâche en tête de file
            r.lpush(key, task_id)
            break

        selected_tasks.append(task)
        current_agents_count += agents_in_task

    return selected_tasks


def requeue_tasks_sync(batch_key: str, task_ids: list[str]) -> None:
    """En cas d'erreur de réseau (retry), replace les tâches en tête de file."""
    if not task_ids:
        return
    r = get_sync_redis()
    r.lpush(_batch_queue_key(batch_key), *task_ids)


# ---------------------------------------------------------------------------
# Métriques Worker (sync — compteurs Redis persistants sans TTL)
# Exposés via le collecteur custom dans l'API /metrics
# ---------------------------------------------------------------------------

WORKER_METRIC_PREFIX = "wmetrics:"


def increment_worker_metric(name: str, amount: int = 1) -> None:
    """Incrémente un compteur de métrique worker (persistant, sans TTL)."""
    get_sync_redis().incrby(f"{WORKER_METRIC_PREFIX}{name}", amount)


def scan_worker_metrics(pattern: str):
    """Retourne un itérateur sur les clés de métriques worker correspondant au pattern."""
    return get_sync_redis().scan_iter(f"{WORKER_METRIC_PREFIX}{pattern}")


def get_worker_metric(name: str) -> int:
    """Lit la valeur courante d'un compteur worker (0 si inexistant)."""
    val = get_sync_redis().get(f"{WORKER_METRIC_PREFIX}{name}")
    return int(val) if val else 0


def increment_worker_error_by_type(provider: str, error_type: str) -> None:
    """Incrémente le compteur d'erreurs par provider ET par type d'erreur."""
    get_sync_redis().incrby(
        f"{WORKER_METRIC_PREFIX}llm_errors_by_type:{provider}:{error_type}", 1
    )
