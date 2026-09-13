"""Shim de compatibilité — `llm_module.api.app` a déménagé dans `llm_gateway.api.app`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `llm_gateway.api.app`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.api.app est déprécié : importez llm_gateway.api.app (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from llm_gateway.api.app import *  # noqa: E402,F401,F403
