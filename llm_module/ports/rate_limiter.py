"""Shim de compatibilité — `llm_module.ports.rate_limiter` a déménagé dans `llm_gateway.ports.rate_limiter`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `llm_gateway.ports.rate_limiter`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.ports.rate_limiter est déprécié : importez llm_gateway.ports.rate_limiter (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from llm_gateway.ports.rate_limiter import *  # noqa: E402,F401,F403
