"""Shim de compatibilité — `llm_module.config` a déménagé dans `llm_gateway.config`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `llm_gateway.config`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.config est déprécié : importez llm_gateway.config (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from llm_gateway.config import *  # noqa: E402,F401,F403
