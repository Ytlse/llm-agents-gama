"""config/learned.py — fusion des limites apprises dans les réglages, et apprentissage.

Le plafond de complétion d'un modèle n'est souvent connu qu'au premier HTTP 400. Le worker
l'apprend, le range dans le port `LearnedLimits`, et chaque processus (API, workers, à leur
démarrage) le fusionne par-dessus la configuration : une limite apprise ne peut que resserrer
celle du fichier, jamais l'élargir.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from llm_gateway.ports.learned_limits import LearnedLimits
from llm_gateway.telemetry.logger import get_logger

if TYPE_CHECKING:  # pragma: no cover
    from llm_gateway.config.settings import GatewaySettings

logger = get_logger(__name__)


def apply_learned_limits(settings: GatewaySettings, store: LearnedLimits) -> int:
    """Fusionne les limites apprises dans `settings.providers`. Rend le nombre de providers ajustés."""
    try:
        learned = store.all_max_output_tokens()
    except Exception as exc:  # store injoignable : on démarre avec la configuration seule
        logger.warning(f"Limites apprises illisibles au démarrage (ignorées) | error={exc!r}")
        return 0
    adjusted = 0
    for name, limit in learned.items():
        cfg = settings.providers.get(name)
        if cfg is None or limit <= 0:
            continue
        if cfg.max_output_tokens is None or limit < cfg.max_output_tokens:
            logger.info(
                f"Limite de complétion apprise appliquée | provider={name} "
                f"max_output_tokens={cfg.max_output_tokens} -> {limit}"
            )
            cfg.max_output_tokens = limit
            adjusted += 1
    return adjusted


def learn_provider_max_output_tokens(
    settings: GatewaySettings, store: LearnedLimits, provider_name: str, limit: int
) -> bool:
    """Enregistre la limite de complétion révélée par un HTTP 400 du fournisseur.

    Met à jour la configuration du processus courant et le store partagé. Rend False si la
    limite était déjà connue (égale ou plus stricte) ou si le provider est inconnu : l'appelant
    ne doit alors PAS retenter, sous peine de boucler sur la même 400.
    """
    if limit <= 0:
        return False
    cfg = settings.providers.get(provider_name)
    if cfg is None:
        logger.warning(
            f"Limite max_output_tokens apprise pour un provider inconnu | "
            f"provider={provider_name} limit={limit}"
        )
        return False
    if cfg.max_output_tokens is not None and cfg.max_output_tokens <= limit:
        return False
    logger.warning(
        f"Limite de complétion apprise depuis l'erreur provider — config ajustée | "
        f"provider={provider_name} max_output_tokens={cfg.max_output_tokens} -> {limit}"
    )
    cfg.max_output_tokens = limit
    try:
        store.set_max_output_tokens(provider_name, limit)
    except Exception as exc:
        logger.error(
            f"[ALARME] Impossible de mémoriser la limite apprise (les autres processus la "
            f"réapprendront) | provider={provider_name} limit={limit} error={exc!r}"
        )
    return True


__all__ = ["apply_learned_limits", "learn_provider_max_output_tokens"]
