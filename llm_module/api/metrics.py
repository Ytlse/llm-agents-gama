"""Shim de compatibilité — `llm_module.api.metrics` a déménagé dans `llm_gateway.api.metrics`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `llm_gateway.api.metrics`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.api.metrics est déprécié : importez llm_gateway.api.metrics (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from llm_gateway.api.metrics import *  # noqa: E402,F401,F403
