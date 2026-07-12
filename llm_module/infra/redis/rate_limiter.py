"""
infra/redis/rate_limiter.py — RedisRateLimiter : quotas RPM, circuit breaker, concurrence.

Implémente le port RateLimiter. La réservation d'un slot RPM combine, en une
seule opération atomique côté Redis (script Lua) :
  1. la vérification de l'intervalle minimum depuis la dernière requête
     (lissage : min_interval = ttl / limit — évite les rafales en début de fenêtre)
  2. la réservation du slot (INCR + vérification de limite, rollback DECR sinon)
  3. la mise à jour du timestamp de dernière requête
"""

from __future__ import annotations
import time
from datetime import datetime, timezone
from typing import Dict

import redis as sync_redis

from llm_module.config import ProviderConfig
from llm_module.telemetry.logger import get_logger

logger = get_logger(__name__)

RPM_KEY_PREFIX          = "rpm:"
TPM_KEY_PREFIX          = "tpm:"              # tokens/minute estimés (fenêtre glissante 60s)
COOLDOWN_KEY_PREFIX     = "cooldown:"
CONS_ERR_KEY_PREFIX     = "cons_err:"
DISABLED_KEY_PREFIX     = "disabled:"
ACTIVE_WORKER_PREFIX    = "active_workers:"
LAST_REQUEST_KEY_PREFIX = "last_req:"
RPD_KEY_PREFIX          = "rpd:"              # compteur requêtes/jour (UTC)
TPD_KEY_PREFIX          = "tpd:"              # compteur tokens/jour (UTC)
QUOTA_EXHAUSTED_PREFIX  = "quota_exhausted:"  # provider écarté jusqu'à minuit UTC

RPM_WINDOW_SECONDS = 60
DAILY_KEY_TTL_SECONDS = 90000  # ~25 h : couvre le jour + marge, purge automatique


def _utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _seconds_until_utc_midnight() -> int:
    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elapsed = (now - midnight).total_seconds()
    return max(1, int(86400 - elapsed))

# Réservation atomique RPM + TPM (fenêtre glissante 60s) avec lissage temporel.
# Ordre : lissage → réservation TPM (tokens estimés) → réservation RPM. Toute
# étape qui échoue annule les réservations déjà posées (rollback DECRBY/DECR) pour
# ne jamais laisser fuir un slot.
# Valeurs de retour :
#   -1 : trop tôt — min_interval non respecté (lissage)
#    0 : quota RPM ou TPM atteint (rollback)
#   >0 : slot réservé avec succès (valeur du compteur RPM)
_TRY_RESERVE_RPM_SMOOTHED_SCRIPT = r"""
local rpm_key      = KEYS[1]
local last_req_key = KEYS[2]
local tpm_key      = KEYS[3]
local limit        = tonumber(ARGV[1])
local ttl          = tonumber(ARGV[2])
local now          = tonumber(ARGV[3])
local min_interval = tonumber(ARGV[4])
local tpm_limit    = tonumber(ARGV[5])
local est_tokens   = tonumber(ARGV[6])

if min_interval > 0 then
    local last = redis.call('GET', last_req_key)
    if last then
        local elapsed = now - tonumber(last)
        if elapsed < min_interval then
            return -1
        end
    end
end

-- Garde-fou TPM : réserve les tokens estimés dans la fenêtre glissante 60s.
-- Ignoré si le provider n'a pas de tpm_limit (tpm_limit <= 0).
local tpm_reserved = false
if tpm_limit > 0 and est_tokens > 0 then
    local tcount = redis.call('INCRBY', tpm_key, est_tokens)
    if redis.call('TTL', tpm_key) == -1 then
        redis.call('EXPIRE', tpm_key, ttl)
    end
    if tcount > tpm_limit then
        redis.call('DECRBY', tpm_key, est_tokens)
        return 0
    end
    tpm_reserved = true
end

local count = redis.call('INCR', rpm_key)
if redis.call('TTL', rpm_key) == -1 then
    redis.call('EXPIRE', rpm_key, ttl)
end
if count > limit then
    redis.call('DECR', rpm_key)
    if tpm_reserved then
        redis.call('DECRBY', tpm_key, est_tokens)
    end
    return 0
end

redis.call('SET', last_req_key, tostring(now), 'EX', ttl)
return count
"""


def _rpm_key(provider: str) -> str:
    return f"{RPM_KEY_PREFIX}{provider}"


def _tpm_key(provider: str) -> str:
    return f"{TPM_KEY_PREFIX}{provider}"


def _last_req_key(provider: str) -> str:
    return f"{LAST_REQUEST_KEY_PREFIX}{provider}"


class RedisRateLimiter:
    def __init__(self, sync_client: sync_redis.Redis, providers: Dict[str, ProviderConfig]) -> None:
        self._r = sync_client
        self._providers = providers

    # ------------------------------------------------------------------
    # Réservation RPM
    # ------------------------------------------------------------------

    def try_reserve(self, provider: str, est_tokens: int | None = None) -> bool:
        """
        Vérifie les pré-conditions (désactivé, cooldown, concurrence, quota)
        puis réserve atomiquement un slot RPM (Lua, avec lissage temporel).
        `est_tokens` surcharge l'estimation TPM statique quand la taille réelle
        de la requête est connue.
        """
        cfg = self._providers.get(provider)
        if cfg is None:
            return False

        if self.is_disabled(provider):
            return False

        if self.is_in_cooldown(provider):
            return False

        if self.active_workers(provider) >= cfg.concurrency_limit:
            return False

        # Quota journalier (RPD/TPD) épuisé → provider écarté jusqu'à minuit UTC.
        if self._daily_quota_exhausted(provider, cfg):
            return False

        # Optimisation : évite le round-trip Lua si le quota est déjà dépassé.
        if self.current_rpm(provider) >= cfg.rpm_limit:
            return False

        now = time.time()
        limit = cfg.rpm_limit
        min_interval = RPM_WINDOW_SECONDS / limit if limit > 0 else 0.0
        # Garde-fou TPM : n'est armé que si le provider déclare un tpm_limit ET une
        # estimation (fournie par l'appelant, sinon statique calculée au build).
        # Sinon tpm_limit=0 → script ignore.
        tpm_limit = cfg.tpm_limit or 0
        if est_tokens is None:
            est_tokens = cfg.tpm_estimate_per_request or 0
        result = self._r.eval(
            _TRY_RESERVE_RPM_SMOOTHED_SCRIPT,
            3,
            _rpm_key(provider),
            _last_req_key(provider),
            _tpm_key(provider),
            limit,
            RPM_WINDOW_SECONDS,
            now,
            min_interval,
            tpm_limit,
            est_tokens,
        )
        reserved = int(result) > 0
        if reserved:
            self._incr_daily_requests(provider)
        return reserved

    # ------------------------------------------------------------------
    # Quotas journaliers (RPD / TPD)
    # ------------------------------------------------------------------

    def _daily_quota_exhausted(self, provider: str, cfg: ProviderConfig) -> bool:
        """True si le provider a atteint son quota journalier (requêtes ou tokens).
        Le premier dépassement pose un flag TTL jusqu'à minuit UTC : les appels
        suivants court-circuitent le comptage tant que le flag est présent."""
        if cfg.rpd_limit is None and cfg.tpd_limit is None:
            return False

        if self._r.exists(f"{QUOTA_EXHAUSTED_PREFIX}{provider}"):
            return True

        if cfg.rpd_limit is not None and self.daily_requests(provider) >= cfg.rpd_limit:
            self._mark_quota_exhausted(provider, "rpd", self.daily_requests(provider), cfg.rpd_limit)
            return True

        if cfg.tpd_limit is not None and self.daily_tokens(provider) >= cfg.tpd_limit:
            self._mark_quota_exhausted(provider, "tpd", self.daily_tokens(provider), cfg.tpd_limit)
            return True

        return False

    def _mark_quota_exhausted(self, provider: str, kind: str, used: int, limit: int) -> None:
        ttl = _seconds_until_utc_midnight()
        self._r.set(f"{QUOTA_EXHAUSTED_PREFIX}{provider}", kind, ex=ttl)
        logger.warning(
            f"Quota journalier {kind.upper()} épuisé — provider écarté jusqu'à minuit UTC "
            f"| provider={provider} used={used} limit={limit} reset_in={ttl}s"
        )

    def _incr_daily_requests(self, provider: str) -> None:
        key = f"{RPD_KEY_PREFIX}{provider}:{_utc_day()}"
        if self._r.incr(key) == 1:
            self._r.expire(key, DAILY_KEY_TTL_SECONDS)

    def record_tokens(self, provider: str, tokens: int) -> None:
        if tokens <= 0:
            return
        key = f"{TPD_KEY_PREFIX}{provider}:{_utc_day()}"
        if self._r.incrby(key, tokens) == tokens:
            self._r.expire(key, DAILY_KEY_TTL_SECONDS)

    def daily_requests(self, provider: str) -> int:
        val = self._r.get(f"{RPD_KEY_PREFIX}{provider}:{_utc_day()}")
        return int(val) if val else 0

    def daily_tokens(self, provider: str) -> int:
        val = self._r.get(f"{TPD_KEY_PREFIX}{provider}:{_utc_day()}")
        return int(val) if val else 0

    def is_quota_exhausted(self, provider: str) -> bool:
        return self._r.exists(f"{QUOTA_EXHAUSTED_PREFIX}{provider}") > 0

    def release_slot(self, provider: str, est_tokens: int | None = None) -> None:
        """Restitue les slots RPM + TPM réservés lorsque l'appel LLM échoue.
        Évite que les erreurs consomment du quota sans appel réussi.
        `est_tokens` doit valoir le montant effectivement réservé (après un
        éventuel adjust_tokens) ; défaut = estimation statique."""
        key = _rpm_key(provider)
        # On décrémente seulement si la clé existe (sinon DECR créerait -1)
        if self._r.exists(key):
            self._r.decr(key)
        # Restitution symétrique de la réservation TPM estimée (sinon la fenêtre
        # glissante enfle à chaque échec et sur-freine le provider).
        if est_tokens is None:
            cfg = self._providers.get(provider)
            est_tokens = cfg.tpm_estimate_per_request if cfg else None
        if est_tokens:
            self.adjust_tokens(provider, -est_tokens)

    def adjust_tokens(self, provider: str, delta: int) -> None:
        """Corrige la réservation TPM de la fenêtre glissante courante (delta
        signé). Clampe à 0 pour ne jamais laisser la fenêtre négative (la clé
        a pu expirer entre la réservation et l'ajustement)."""
        if delta == 0:
            return
        cfg = self._providers.get(provider)
        if cfg is None or not cfg.tpm_limit:
            return
        tpm_key = _tpm_key(provider)
        if delta < 0:
            if self._r.exists(tpm_key) and int(self._r.decrby(tpm_key, -delta)) < 0:
                self._r.set(tpm_key, 0, keepttl=True)
        else:
            if int(self._r.incrby(tpm_key, delta)) == delta:
                # Clé créée par cet INCRBY → poser le TTL de la fenêtre.
                self._r.expire(tpm_key, RPM_WINDOW_SECONDS)

    def current_rpm(self, provider: str) -> int:
        val = self._r.get(_rpm_key(provider))
        return int(val) if val else 0

    def current_tpm(self, provider: str) -> int:
        """Tokens estimés réservés dans la fenêtre glissante 60s (monitoring)."""
        val = self._r.get(_tpm_key(provider))
        return int(val) if val else 0

    def reset_windows(self) -> None:
        """Remise à zéro des fenêtres RPM + TPM — geste explicite du lifespan de l'API."""
        keys = [_rpm_key(name) for name in self._providers]
        keys += [_tpm_key(name) for name in self._providers]
        if keys:
            self._r.delete(*keys)

    # ------------------------------------------------------------------
    # Circuit breaker
    # ------------------------------------------------------------------

    def cooldown(self, provider: str, seconds: int) -> None:
        self._r.set(f"{COOLDOWN_KEY_PREFIX}{provider}", "1", ex=seconds)

    def is_in_cooldown(self, provider: str) -> bool:
        return self._r.exists(f"{COOLDOWN_KEY_PREFIX}{provider}") > 0

    def cooldown_ttl(self, provider: str) -> int:
        ttl = self._r.ttl(f"{COOLDOWN_KEY_PREFIX}{provider}")
        return ttl if ttl > 0 else 0

    def disable(self, provider: str, seconds: int) -> None:
        """Désactivation temporaire — à l'expiration du TTL, Redis supprime la
        clé et le provider redevient éligible."""
        self._r.set(f"{DISABLED_KEY_PREFIX}{provider}", "1", ex=seconds)
        self._r.delete(f"{CONS_ERR_KEY_PREFIX}{provider}")

    def is_disabled(self, provider: str) -> bool:
        return self._r.exists(f"{DISABLED_KEY_PREFIX}{provider}") > 0

    def disabled_ttl(self, provider: str) -> int:
        ttl = self._r.ttl(f"{DISABLED_KEY_PREFIX}{provider}")
        return ttl if ttl > 0 else 0

    def record_failure(self, provider: str) -> int:
        return int(self._r.incr(f"{CONS_ERR_KEY_PREFIX}{provider}"))

    def record_success(self, provider: str) -> None:
        self._r.delete(f"{CONS_ERR_KEY_PREFIX}{provider}")

    # ------------------------------------------------------------------
    # Concurrence (workers actifs par provider)
    # ------------------------------------------------------------------

    def incr_active(self, provider: str) -> int:
        key = f"{ACTIVE_WORKER_PREFIX}{provider}"
        val = self._r.incr(key)
        if val == 1:
            self._r.expire(key, 600)  # Sécurité : expire après 10 min si le worker plante
        return val

    def decr_active(self, provider: str) -> int:
        key = f"{ACTIVE_WORKER_PREFIX}{provider}"
        val = self._r.decr(key)
        if val < 0:
            self._r.set(key, 0)
            val = 0
        return val

    def active_workers(self, provider: str) -> int:
        val = self._r.get(f"{ACTIVE_WORKER_PREFIX}{provider}")
        return int(val) if val else 0
