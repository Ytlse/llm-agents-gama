"""
load_balancer/router.py — Routeur intelligent multi-fournisseur.

Implémente :
  - Weighted Round-Robin   : répartition proportionnelle aux quotas RPM (SWRR NGINX,
                             séquence pure construite par core.selection)
  - Réservation atomique   : déléguée au port RateLimiter (script Lua Redis) — aucun
                             worker concurrent ne peut dépasser le rpm_limit configuré
  - Circuit Breaker        : exclusion temporaire (cooldown) sur erreurs 5xx / 429
  - Désactivation temporaire : exclusion automatique après N erreurs consécutives,
                               réactivation après `disable_timeout` secondes (défaut 180s)

Le constructeur ne touche PAS à Redis : la remise à zéro des fenêtres RPM est un
geste explicite du lifespan de l'API (cf. api/app.py), plus jamais un effet de
bord d'import.
"""

from __future__ import annotations
import threading
from typing import Dict, List, Optional

from llm_module.config import ProviderConfig
from llm_module.core.selection import build_swrr_sequence
from llm_module.ports.rate_limiter import RateLimiter
from llm_module.telemetry.logger import get_logger

logger = get_logger(__name__)


class LoadBalancer:
    """
    Sélectionne le fournisseur optimal pour chaque requête et réserve atomiquement
    un slot RPM (via le RateLimiter injecté) avant de retourner son nom.
    """

    def __init__(self, providers: Dict[str, ProviderConfig], limiter: RateLimiter) -> None:
        self._providers = providers
        self._limiter = limiter
        self._lock = threading.Lock()
        self._cursor: int = 0
        self._sequence: List[str] = self._build_sequence()

    # ------------------------------------------------------------------
    # Construction de la séquence pondérée
    # ------------------------------------------------------------------

    def _build_sequence(self) -> List[str]:
        if not self._providers:
            logger.error("Aucun provider disponible — séquence SWRR vide.")
            return []
        sequence = build_swrr_sequence({name: cfg.weight for name, cfg in self._providers.items()})
        logger.debug(f"Séquence WRR construite | sequence={sequence}")
        return sequence

    def rebuild_sequence(self) -> None:
        with self._lock:
            self._sequence = self._build_sequence()
            self._cursor = 0

    # ------------------------------------------------------------------
    # Sélection du fournisseur
    # ------------------------------------------------------------------

    def select_provider(
        self,
        force: Optional[str] = None,
        min_tpm: Optional[int] = None,
        min_output: Optional[int] = None,
    ) -> str:
        """
        Retourne le nom du fournisseur à utiliser et réserve atomiquement un slot RPM.

        Args:
            force:      Si fourni, bypasse la rotation et utilise ce fournisseur.
            min_tpm:    Si fourni, exclut les providers dont tpm_limit < min_tpm
                        (les providers sans limite TPM, tpm_limit=None, restent éligibles).
            min_output: Si fourni, exclut les providers dont le plafond de complétion
                        max_output_tokens < min_output (budget de sortie d'une tâche).
                        Les providers sans limite connue (None) restent éligibles.

        Raises:
            RuntimeError: Si tous les fournisseurs sont saturés ou indisponibles.
        """
        if force:
            if self._try_reserve(force, min_tpm=min_tpm, min_output=min_output):
                return force
            raise RuntimeError(
                f"Fournisseur forcé '{force}' indisponible (quota atteint ou désactivé)."
            )

        # Rotation normale — le lock ne protège que la lecture/écriture du curseur.
        # _try_reserve() fait ses appels Redis HORS du lock.
        seq_len = len(self._sequence)
        for _ in range(seq_len):
            with self._lock:
                candidate = self._sequence[self._cursor % seq_len]
                self._cursor += 1

            if self._try_reserve(candidate, min_tpm=min_tpm, min_output=min_output):
                return candidate

        raise RuntimeError(
            "Tous les fournisseurs LLM sont saturés ou ont atteint leur limite de concurrence. "
            "Réessayez dans quelques secondes."
        )

    def _try_reserve(
        self,
        provider: str,
        min_tpm: Optional[int] = None,
        min_output: Optional[int] = None,
    ) -> bool:
        """
        Applique les contraintes de routage (provider connu, min_tpm, min_output)
        puis délègue la réservation atomique (désactivation, cooldown, concurrence,
        quota + lissage) au RateLimiter.
        """
        cfg = self._providers.get(provider)
        if cfg is None:
            logger.warning(f"Provider inconnu dans la config | provider={provider}")
            return False

        if min_tpm is not None and cfg.tpm_limit is not None and cfg.tpm_limit < min_tpm:
            return False

        if (
            min_output is not None
            and cfg.max_output_tokens is not None
            and cfg.max_output_tokens < min_output
        ):
            return False

        return self._limiter.try_reserve(provider)

    def get_status(self) -> Dict[str, Dict]:
        """Snapshot des compteurs RPM pour monitoring / debug (/health)."""
        status = {}
        for name, cfg in self._providers.items():
            current = self._limiter.current_rpm(name)
            quota_exhausted = self._limiter.is_quota_exhausted(name)
            available = (
                not self._limiter.is_disabled(name)
                and not self._limiter.is_in_cooldown(name)
                and not quota_exhausted
                and current < cfg.rpm_limit
                and self._limiter.active_workers(name) < cfg.concurrency_limit
            )
            status[name] = {
                "current_rpm":     current,
                "rpm_limit":       cfg.rpm_limit,
                "active_tasks":    self._limiter.active_workers(name),
                "usage_pct":       round(current / cfg.rpm_limit * 100, 1) if cfg.rpm_limit else 0,
                "cooldown":        self._limiter.is_in_cooldown(name),
                "daily_requests":  self._limiter.daily_requests(name),
                "rpd_limit":       cfg.rpd_limit,
                "daily_tokens":    self._limiter.daily_tokens(name),
                "tpd_limit":       cfg.tpd_limit,
                "quota_exhausted": quota_exhausted,
                "available":       available,
            }
        return status
