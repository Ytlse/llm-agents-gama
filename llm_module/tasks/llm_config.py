"""
tasks/llm_config.py — Shim de compatibilité.

La configuration vit désormais dans llm_module.config (restructuration en
package, cf. docs/arch/llm-module-package-refactor.md). Ce module est conservé
pour les notebooks d'analyse (scripts/models_influence/*, scripts/analysis/*) ;
préférer `from llm_module.config import get_settings`.
"""

from __future__ import annotations
from typing import Optional

from llm_module.config import (  # noqa: F401
    ProviderConfig,
    Settings,
    filter_providers_without_api_key,
    get_settings,
    load_provider_defaults,
)

# Alias historiques
_load_provider_defaults = load_provider_defaults

settings = get_settings()


def get_batch_max_agents(force_provider: Optional[str] = None) -> int:
    return settings.get_batch_max_agents(force_provider)
