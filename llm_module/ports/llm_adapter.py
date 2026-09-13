"""Shim de compatibilité — `llm_module.ports.llm_adapter` a déménagé dans `llm_gateway.ports.llm_adapter`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `llm_gateway.ports.llm_adapter`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.ports.llm_adapter est déprécié : importez llm_gateway.ports.llm_adapter (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from llm_gateway.ports.llm_adapter import *  # noqa: E402,F401,F403
