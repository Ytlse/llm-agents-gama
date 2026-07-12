"""
ports/rate_limiter.py — Contrat quotas RPM, circuit breaker et concurrence.

Regroupe tout l'état « santé provider » partagé entre workers :
  - fenêtre RPM glissante avec lissage temporel (min_interval = ttl / limit)
  - cooldown (429 / 5xx) et désactivation temporaire (erreurs consécutives)
  - compteur de workers actifs (limite de concurrence par provider)
"""

from __future__ import annotations
from typing import Optional, Protocol


class RateLimiter(Protocol):
    # ── Réservation RPM ──────────────────────────────────────────────────
    def try_reserve(self, provider: str, est_tokens: Optional[int] = None) -> bool:
        """Réserve atomiquement un slot RPM (vérifie désactivation, cooldown,
        concurrence, quota + lissage). True si le slot est acquis.
        `est_tokens` surcharge l'estimation TPM statique (tpm_estimate_per_request)
        quand la taille réelle de la requête est connue."""
        ...

    def release_slot(self, provider: str, est_tokens: Optional[int] = None) -> None:
        """Restitue les slots RPM + TPM réservés quand l'appel LLM échoue.
        `est_tokens` doit valoir le montant effectivement réservé (après un
        éventuel adjust_tokens) ; défaut = estimation statique."""
        ...

    def adjust_tokens(self, provider: str, delta: int) -> None:
        """Corrige la réservation TPM de la fenêtre glissante courante :
        delta > 0 quand la requête réelle dépasse l'estimation posée à la
        réservation, delta < 0 quand elle est plus petite (libère du headroom).
        Sans effet si le provider n'a pas de tpm_limit."""
        ...

    def current_rpm(self, provider: str) -> int: ...

    def current_tpm(self, provider: str) -> int:
        """Tokens estimés réservés dans la fenêtre glissante 60s (0 si pas de tpm_limit)."""
        ...

    def reset_windows(self) -> None:
        """Remet à zéro les fenêtres RPM + TPM de tous les providers (démarrage API)."""
        ...

    # ── Quotas journaliers (RPD / TPD) ──────────────────────────────────
    def record_tokens(self, provider: str, tokens: int) -> None:
        """Comptabilise les tokens consommés pour l'application du quota tpd_limit
        (fenêtre journalière UTC). Appelé après chaque appel LLM réussi."""
        ...

    def is_quota_exhausted(self, provider: str) -> bool:
        """True si le provider a épuisé son quota journalier (RPD/TPD) et reste
        écarté jusqu'à minuit UTC."""
        ...

    def daily_requests(self, provider: str) -> int: ...

    def daily_tokens(self, provider: str) -> int: ...

    # ── Circuit breaker ──────────────────────────────────────────────────
    def cooldown(self, provider: str, seconds: int) -> None: ...

    def is_in_cooldown(self, provider: str) -> bool: ...

    def cooldown_ttl(self, provider: str) -> int:
        """Secondes avant fin du cooldown (0 si pas en cooldown)."""
        ...

    def disable(self, provider: str, seconds: int) -> None: ...

    def is_disabled(self, provider: str) -> bool: ...

    def disabled_ttl(self, provider: str) -> int:
        """Secondes avant réactivation automatique (0 si actif)."""
        ...

    def record_failure(self, provider: str) -> int:
        """Incrémente les erreurs consécutives ; retourne la nouvelle valeur."""
        ...

    def record_success(self, provider: str) -> None:
        """Remet à zéro le compteur d'erreurs consécutives."""
        ...

    # ── Concurrence ──────────────────────────────────────────────────────
    def incr_active(self, provider: str) -> int: ...

    def decr_active(self, provider: str) -> int: ...

    def active_workers(self, provider: str) -> int: ...
