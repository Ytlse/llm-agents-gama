"""
load_balancer/router.py — Routeur intelligent multi-fournisseur.

Implémente :
  - Weighted Round-Robin : répartition proportionnelle aux quotas RPM
  - Circuit Breaker      : exclusion temporaire si > 95 % du quota atteint
  - Suivi RPM via Redis  : compteurs partagés entre tous les Workers

"""

from __future__ import annotations
import threading
from typing import Dict, List, Optional

from llm_module.tasks.config import settings
from llm_module.broker.redis_broker import get_rpm, increment_rpm, is_in_cooldown, is_provider_disabled
from llm_module.telemetry.logger import get_logger

logger = get_logger(__name__)


class LoadBalancer:
    """
    Sélectionne le fournisseur optimal pour chaque requête.

    Algorithme Weighted Round-Robin :
    ─────────────────────────────────
    On construit une séquence « pondérée » à partir des poids normalisés.
    Ex : mistral(w=2), openai(w=1), google(w=1) → séquence [mistral, mistral, openai, google]
    On parcourt cette séquence de façon circulaire (modulo).

    Le Circuit Breaker court-circuite la rotation : si le compteur Redis
    d'un fournisseur dépasse 95 % de son quota RPM, il est ignoré pour
    ce tour de sélection.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cursor: int = 0
        self._sequence: List[str] = self._build_sequence()

    # ------------------------------------------------------------------
    # Construction de la séquence pondérée
    # ------------------------------------------------------------------

    def _build_sequence(self) -> List[str]:
        """
        Construit la liste de rotation pondérée une seule fois au démarrage.
        
        Utilise l'algorithme Smooth Weighted Round-Robin (SWRR, type NGINX) 
        pour garantir un entrelacement et éviter les micro-rafales 
        sur un même fournisseur.
        """
        total_weight = sum(p.weight for p in settings.providers.values())
        if total_weight == 0:
            return []

        # Initialisation des états pour l'algorithme SWRR
        peers = []
        for name, cfg in settings.providers.items():
            effective_weight = max(1, round((cfg.weight / total_weight) * 100))
            peers.append({"name": name, "weight": effective_weight, "current_weight": 0})

        total_slots = sum(p["weight"] for p in peers)
        sequence: List[str] = []

        # Génération de la séquence entrelacée
        for _ in range(total_slots):
            for p in peers:
                p["current_weight"] += p["weight"]
            best = max(peers, key=lambda x: x["current_weight"])
            best["current_weight"] -= total_slots
            sequence.append(best["name"])

        logger.debug(f"Séquence WRR construite | sequence={sequence}")
        return sequence

    def rebuild_sequence(self) -> None:
        with self._lock:
            self._sequence = self._build_sequence()
            self._cursor = 0

    # ------------------------------------------------------------------
    # Sélection du fournisseur
    # ------------------------------------------------------------------

    def select_provider(self, force: Optional[str] = None) -> str:
        """
        Retourne le nom du fournisseur à utiliser.

        Args:
            force: Si fourni, bypasse la rotation et utilise ce fournisseur
                   (après vérification du circuit breaker).

        Raises:
            RuntimeError: Si tous les fournisseurs sont saturés.
        """
        if force:
            if self._is_available(force):
                return force
            raise RuntimeError(
                f"Fournisseur forcé '{force}' indisponible (quota atteint)."
            )

        # Rotation normale.
        # Le lock ne protège que la lecture/écriture du curseur entier.
        # _is_available() fait des appels Redis HORS du lock (voir docstring module).
        seq_len = len(self._sequence)
        for _ in range(seq_len):
            with self._lock:
                candidate = self._sequence[self._cursor % seq_len]
                self._cursor += 1

            if self._is_available(candidate):
                logger.debug(f"\n[Provider sélectionné] | provider={candidate} cursor={self._cursor}\n")
                return candidate

        raise RuntimeError(
            "Tous les fournisseurs LLM ont atteint leur quota RPM. "
            "Réessayez dans quelques secondes."
        )

    def _is_available(self, provider: str) -> bool:
        """
        Vérifie si le fournisseur est sous le seuil du circuit breaker.
        Retourne False si inconnu dans la config (sécurité défensive).
        """
        cfg = settings.providers.get(provider)
        if cfg is None:
            logger.warning(f"Provider inconnu dans la config | provider={provider}")
            return False

        if is_provider_disabled(provider):
            return False

        if is_in_cooldown(provider):
            #logger.debug(f"Provider en cooldown (ignoré) | provider={provider}")
            return False

        current_rpm = get_rpm(provider)
        threshold = cfg.rpm_limit * settings.circuit_breaker_threshold

        if current_rpm >= threshold:
            logger.warning(
                f"Circuit breaker déclenché | provider={provider} "
                f"current_rpm={current_rpm} threshold={threshold:.1f} rpm_limit={cfg.rpm_limit}"
            )
            return False
        return True

    def record_call(self, provider: str) -> int:
        """
        Enregistre un appel effectué vers un fournisseur.
        À appeler APRÈS la sélection, juste avant l'appel HTTP.
        Retourne le compteur RPM mis à jour.
        """
        count = increment_rpm(provider)
        logger.debug(f"RPM incrémenté | provider={provider} rpm_count={count}")
        return count

    def get_status(self) -> Dict[str, Dict]:
        """Snapshot des compteurs RPM pour monitoring / debug."""
        status = {}
        for name, cfg in settings.providers.items():
            current = get_rpm(name)
            status[name] = {
                "current_rpm":  current,
                "rpm_limit":    cfg.rpm_limit,
                "usage_pct":    round(current / cfg.rpm_limit * 100, 1) if cfg.rpm_limit else 0,
                "cooldown":     is_in_cooldown(name),
                "available":    self._is_available(name),
            }
        return status


# Instance singleton
load_balancer = LoadBalancer()
