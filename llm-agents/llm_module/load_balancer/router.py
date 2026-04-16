"""
load_balancer/router.py — Routeur intelligent multi-fournisseur.

Implémente :
  - Weighted Round-Robin   : répartition proportionnelle aux quotas RPM (SWRR NGINX)
  - Réservation atomique   : script Lua Redis garantit que INCR et vérification limite
                             sont indivisibles — aucun worker concurrent ne peut dépasser
                             le rpm_limit configuré
  - Circuit Breaker        : exclusion temporaire (cooldown) sur erreurs 5xx / 429
  - Désactivation durable  : exclusion permanente après N erreurs consécutives

"""

from __future__ import annotations
import threading
from typing import Dict, List, Optional

from llm_module.tasks.config import settings
from llm_module.broker.redis_broker import get_rpm, is_in_cooldown, is_provider_disabled, try_reserve_rpm
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
                logger.debug(f"\n[Provider sélectionné] | provider={candidate} cursor={self._cursor}\n")
                return candidate

        status_snapshot = {
            name: {
                "rpm": get_rpm(name),
                "limit": cfg.rpm_limit,
                "cooldown": is_in_cooldown(name),
                "disabled": is_provider_disabled(name),
            }
            for name, cfg in settings.providers.items()
        }
        logger.warning(
            f"[load_balancer] TOUS LES PROVIDERS SATURÉS | snapshot={status_snapshot}"
        )
        raise RuntimeError(
            "Tous les fournisseurs LLM ont atteint leur quota RPM. "
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

        # Optimisation : évite le round-trip Lua si le quota est déjà dépassé.
        if get_rpm(provider) >= cfg.rpm_limit:
            logger.warning(
                f"Quota RPM atteint (fast-path) | provider={provider} "
                f"rpm_limit={cfg.rpm_limit}"
            )
            return False

        # Réservation atomique : INCR + vérification limite en une seule opération Redis.
        reserved = try_reserve_rpm(provider, cfg.rpm_limit)
        if not reserved:
            logger.warning(
                f"Quota RPM atteint (atomic) | provider={provider} rpm_limit={cfg.rpm_limit}"
            )
        return reserved

    def get_status(self) -> Dict[str, Dict]:
        """Snapshot des compteurs RPM pour monitoring / debug."""
        status = {}
        for name, cfg in settings.providers.items():
            current = get_rpm(name)
            available = (
                not is_provider_disabled(name)
                and not is_in_cooldown(name)
                and current < cfg.rpm_limit
            )
            status[name] = {
                "current_rpm":  current,
                "rpm_limit":    cfg.rpm_limit,
                "usage_pct":    round(current / cfg.rpm_limit * 100, 1) if cfg.rpm_limit else 0,
                "cooldown":     is_in_cooldown(name),
                "available":    available,
            }
        return status


# Instance singleton
load_balancer = LoadBalancer()
