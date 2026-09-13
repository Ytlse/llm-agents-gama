"""Shim de compatibilité — `llm_module.infra.memory` a déménagé dans `llm_gateway.infra.memory`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `llm_gateway.infra.memory`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.infra.memory est déprécié : importez llm_gateway.infra.memory (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from llm_gateway.infra.memory import *  # noqa: E402,F401,F403
