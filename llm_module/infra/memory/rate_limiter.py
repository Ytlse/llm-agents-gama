"""
infra/memory/rate_limiter.py — InMemoryRateLimiter : port RateLimiter en pur
Python, pour les tests. Fenêtre RPM de 60s, lissage et circuit breaker inclus.
"""

from __future__ import annotations
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict

from llm_module.config import ProviderConfig

RPM_WINDOW_SECONDS = 60


def _utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _seconds_until_utc_midnight() -> int:
    now = datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int(86400 - (now - midnight).total_seconds()))


class InMemoryRateLimiter:
    def __init__(self, providers: Dict[str, ProviderConfig]) -> None:
        self._providers = providers
        self._rpm: dict[str, int] = defaultdict(int)
        self._tpm: dict[str, int] = defaultdict(int)
        self._window_start: dict[str, float] = {}
        self._last_req: dict[str, float] = {}
        self._cooldown_until: dict[str, float] = {}
        self._disabled_until: dict[str, float] = {}
        self._consecutive_errors: dict[str, int] = defaultdict(int)
        self._active: dict[str, int] = defaultdict(int)
        # Quotas journaliers (clé = provider|jour UTC) et flag d'épuisement.
        self._daily_req: dict[tuple[str, str], int] = defaultdict(int)
        self._daily_tok: dict[tuple[str, str], int] = defaultdict(int)
        self._quota_exhausted_until: dict[str, float] = {}

    # ── Réservation RPM ──────────────────────────────────────────────────

    def _maybe_reset_window(self, provider: str) -> None:
        start = self._window_start.get(provider)
        if start is None or time.time() - start >= RPM_WINDOW_SECONDS:
            self._window_start[provider] = time.time()
            self._rpm[provider] = 0
            self._tpm[provider] = 0

    def try_reserve(self, provider: str, est_tokens: int | None = None) -> bool:
        cfg = self._providers.get(provider)
        if cfg is None:
            return False
        if self.is_disabled(provider) or self.is_in_cooldown(provider):
            return False
        if self.active_workers(provider) >= cfg.concurrency_limit:
            return False

        if self._daily_quota_exhausted(provider, cfg):
            return False

        self._maybe_reset_window(provider)
        if self._rpm[provider] >= cfg.rpm_limit:
            return False

        min_interval = RPM_WINDOW_SECONDS / cfg.rpm_limit if cfg.rpm_limit > 0 else 0.0
        last = self._last_req.get(provider)
        if min_interval > 0 and last is not None and time.time() - last < min_interval:
            return False

        # Garde-fou TPM glissant (mêmes règles que le limiter Redis).
        if est_tokens is None:
            est_tokens = cfg.tpm_estimate_per_request or 0
        if cfg.tpm_limit and est_tokens and self._tpm[provider] + est_tokens > cfg.tpm_limit:
            return False

        self._rpm[provider] += 1
        self._tpm[provider] += est_tokens
        self._last_req[provider] = time.time()
        self._daily_req[(provider, _utc_day())] += 1
        return True

    # ── Quotas journaliers (RPD / TPD) ──────────────────────────────────

    def _daily_quota_exhausted(self, provider: str, cfg: ProviderConfig) -> bool:
        if cfg.rpd_limit is None and cfg.tpd_limit is None:
            return False
        if time.time() < self._quota_exhausted_until.get(provider, 0.0):
            return True
        if cfg.rpd_limit is not None and self.daily_requests(provider) >= cfg.rpd_limit:
            self._quota_exhausted_until[provider] = time.time() + _seconds_until_utc_midnight()
            return True
        if cfg.tpd_limit is not None and self.daily_tokens(provider) >= cfg.tpd_limit:
            self._quota_exhausted_until[provider] = time.time() + _seconds_until_utc_midnight()
            return True
        return False

    def record_tokens(self, provider: str, tokens: int) -> None:
        if tokens > 0:
            self._daily_tok[(provider, _utc_day())] += tokens

    def daily_requests(self, provider: str) -> int:
        return self._daily_req[(provider, _utc_day())]

    def daily_tokens(self, provider: str) -> int:
        return self._daily_tok[(provider, _utc_day())]

    def is_quota_exhausted(self, provider: str) -> bool:
        return time.time() < self._quota_exhausted_until.get(provider, 0.0)

    def release_slot(self, provider: str, est_tokens: int | None = None) -> None:
        if self._rpm[provider] > 0:
            self._rpm[provider] -= 1
        if est_tokens is None:
            cfg = self._providers.get(provider)
            est_tokens = cfg.tpm_estimate_per_request if cfg else None
        if est_tokens:
            self._tpm[provider] = max(0, self._tpm[provider] - est_tokens)

    def adjust_tokens(self, provider: str, delta: int) -> None:
        cfg = self._providers.get(provider)
        if cfg is None or not cfg.tpm_limit or delta == 0:
            return
        self._tpm[provider] = max(0, self._tpm[provider] + delta)

    def current_rpm(self, provider: str) -> int:
        self._maybe_reset_window(provider)
        return self._rpm[provider]

    def current_tpm(self, provider: str) -> int:
        self._maybe_reset_window(provider)
        return self._tpm[provider]

    def reset_windows(self) -> None:
        self._rpm.clear()
        self._tpm.clear()
        self._window_start.clear()
        self._last_req.clear()

    # ── Circuit breaker ──────────────────────────────────────────────────

    def cooldown(self, provider: str, seconds: int) -> None:
        self._cooldown_until[provider] = time.time() + seconds

    def is_in_cooldown(self, provider: str) -> bool:
        return time.time() < self._cooldown_until.get(provider, 0.0)

    def cooldown_ttl(self, provider: str) -> int:
        remaining = self._cooldown_until.get(provider, 0.0) - time.time()
        return int(remaining) if remaining > 0 else 0

    def disable(self, provider: str, seconds: int) -> None:
        self._disabled_until[provider] = time.time() + seconds
        self._consecutive_errors[provider] = 0

    def is_disabled(self, provider: str) -> bool:
        return time.time() < self._disabled_until.get(provider, 0.0)

    def disabled_ttl(self, provider: str) -> int:
        remaining = self._disabled_until.get(provider, 0.0) - time.time()
        return int(remaining) if remaining > 0 else 0

    def record_failure(self, provider: str) -> int:
        self._consecutive_errors[provider] += 1
        return self._consecutive_errors[provider]

    def record_success(self, provider: str) -> None:
        self._consecutive_errors[provider] = 0

    # ── Concurrence ──────────────────────────────────────────────────────

    def incr_active(self, provider: str) -> int:
        self._active[provider] += 1
        return self._active[provider]

    def decr_active(self, provider: str) -> int:
        self._active[provider] = max(0, self._active[provider] - 1)
        return self._active[provider]

    def active_workers(self, provider: str) -> int:
        return self._active[provider]
