"""Shim de compatibilité — `llm_module.ports` a déménagé dans `llm_gateway.ports`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `llm_gateway.ports`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.ports est déprécié : importez llm_gateway.ports (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from llm_gateway.ports import *  # noqa: E402,F401,F403
