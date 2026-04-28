"""
load_balancer/router.py — Routeur intelligent multi-fournisseur.

Implémente :
  - Weighted Round-Robin   : répartition proportionnelle aux quotas RPM (SWRR NGINX)
  - Réservation atomique   : script Lua Redis garantit que INCR et vérification limite
                             sont indivisibles — aucun worker concurrent ne peut dépasser
                             le rpm_limit configuré
  - Circuit Breaker        : exclusion temporaire (cooldown) sur erreurs 5xx / 429
  - Désactivation temporaire : exclusion automatique après N erreurs consécutives,
                               réactivation après `disable_timeout` secondes (défaut 180s)

"""

from __future__ import annotations
import threading
from typing import Dict, List, Optional

from llm_module.tasks.config import settings
from llm_module.broker.redis_broker import (
    get_rpm, is_in_cooldown, is_provider_disabled, try_reserve_rpm_smoothed,
    reset_all_rpm_counters, get_active_workers,
)
from llm_module.telemetry.logger import get_logger

logger = get_logger(__name__)


class LoadBalancer:
    """
    Sélectionne le fournisseur optimal pour chaque requête et réserve atomiquement
    un slot RPM avant de retourner le nom du fournisseur.

    Algorithme Weighted Round-Robin :
    ─────────────────────────────────
    On construit une séquence « pondérée » à partir des poids normalisés.
    Ex : mistral(w=2), openai(w=1), google(w=1) → séquence [mistral, mistral, openai, google]
    On parcourt cette séquence de façon circulaire (modulo).

    Garantie quota RPM :
    ────────────────────
    La réservation d'un slot RPM utilise un script Lua Redis (atomique) : INCR + check
    en une seule opération. Si le compteur dépasse rpm_limit, il est décrémenté et le
    provider est ignoré. Aucun worker concurrent ne peut s'intercaler entre la vérification
    et l'incrément → le rpm_limit est respecté même sous forte concurrence.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cursor: int = 0
        reset_all_rpm_counters(list(settings.providers.keys()))
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
        active = {name: cfg for name, cfg in settings.providers.items()}


        if not active:
            logger.error("Aucun provider disponible après health checks — séquence vide.")
            return []

        total_weight = sum(p.weight for p in active.values())

        # Initialisation des états pour l'algorithme SWRR
        peers = []
        for name, cfg in active.items():
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
        Retourne le nom du fournisseur à utiliser et réserve atomiquement un slot RPM.

        La réservation (incrément Redis) est faite ici, via un script Lua atomique,
        pour garantir qu'aucun worker concurrent ne dépasse le quota entre la
        vérification et l'incrément.

        Args:
            force: Si fourni, bypasse la rotation et utilise ce fournisseur.

        Raises:
            RuntimeError: Si tous les fournisseurs sont saturés ou indisponibles.
        """
        if force:
            if self._try_reserve(force):
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

            if self._try_reserve(candidate):
                active = get_active_workers(candidate)
                logger.debug(f"\n[Provider sélectionné] | provider={candidate} cursor={self._cursor} active_tasks={active}\n")
                return candidate

        status_snapshot = {
            name: {
                "rpm": get_rpm(name),
                "limit": cfg.rpm_limit,
                "active_tasks": get_active_workers(name),
                "cooldown": is_in_cooldown(name),
                "disabled": is_provider_disabled(name),
            }
            for name, cfg in settings.providers.items()
        }
        raise RuntimeError(
            "Tous les fournisseurs LLM sont saturés ou ont atteint leur limite de concurrence. "
            "Réessayez dans quelques secondes."
        )

    def _try_reserve(self, provider: str) -> bool:
        """
        Vérifie les pré-conditions (désactivé, cooldown, quota dépassé) puis
        tente de réserver atomiquement un slot RPM via un script Lua Redis.

        La vérification rapide du RPM courant (get_rpm) sert d'optimisation pour
        éviter le round-trip Lua quand le quota est manifestement épuisé.
        La limite stricte est ensuite appliquée de façon atomique par try_reserve_rpm.

        Retourne False si inconnu dans la config (sécurité défensive).
        """
        cfg = settings.providers.get(provider)
        if cfg is None:
            logger.warning(f"Provider inconnu dans la config | provider={provider}")
            return False

        if is_provider_disabled(provider):
            return False

        if is_in_cooldown(provider):
            return False

        # Limite de concurrence : configurable par provider dans providers.yaml
        max_active = cfg.concurrency_limit
        active_count = get_active_workers(provider)
        if active_count >= max_active:
            # logger.debug(f"Limite de concurrence atteinte | provider={provider} active={active_count}/{max_active}")
            return False

        # Optimisation : évite le round-trip Lua si le quota est déjà dépassé.
        if get_rpm(provider) >= cfg.rpm_limit:
            logger.debug(
                f"Quota RPM atteint (fast-path) | provider={provider} "
                f"rpm_limit={cfg.rpm_limit}"
            )
            return False

        # Réservation atomique avec lissage temporel :
        # vérifie min_interval, INCR RPM et maj last_req en une seule opération Redis.
        result = try_reserve_rpm_smoothed(provider, cfg.rpm_limit)
        if result == -1:
            # logger.debug(
            #     f"Lissage RPM : intervalle minimum non écoulé | provider={provider} "
            #     f"min_interval={60 / cfg.rpm_limit:.2f}s"
            # )
            return False
        if result == 0:
            logger.warning(
                f"Quota RPM atteint (atomic) | provider={provider} rpm_limit={cfg.rpm_limit}"
            )
            return False
        return True

    def get_status(self) -> Dict[str, Dict]:
        """Snapshot des compteurs RPM pour monitoring / debug."""
        status = {}
        for name, cfg in settings.providers.items():
            current = get_rpm(name)
            available = (
                not is_provider_disabled(name)
                and not is_in_cooldown(name)
                and current < cfg.rpm_limit
                and get_active_workers(name) < cfg.concurrency_limit
            )
            status[name] = {
                "current_rpm":  current,
                "rpm_limit":    cfg.rpm_limit,
                "active_tasks": get_active_workers(name),
                "usage_pct":    round(current / cfg.rpm_limit * 100, 1) if cfg.rpm_limit else 0,
                "cooldown":     is_in_cooldown(name),
                "available":    available,
            }
        return status


# Instance singleton
load_balancer = LoadBalancer()
