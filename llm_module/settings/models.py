"""Shim de compatibilité — `llm_module.settings.models` a déménagé dans `llm_gateway.core.models`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `llm_gateway.core.models`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.settings.models est déprécié : importez llm_gateway.core.models (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from llm_gateway.core.models import *  # noqa: E402,F401,F403
from llm_gateway.core.models import _FALLBACK_PRIORITY_SCORE  # noqa: E402,F401
from mobility_llm.persona import AgentSpec  # noqa: E402,F401
