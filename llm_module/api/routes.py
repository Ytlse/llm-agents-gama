"""Shim de compatibilité — `llm_module.api.routes` a déménagé dans `llm_gateway.api.routes`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `llm_gateway.api.routes`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.api.routes est déprécié : importez llm_gateway.api.routes (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from llm_gateway.api.routes import *  # noqa: E402,F401,F403
