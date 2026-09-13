"""Shim de compatibilité — `llm_module.core.selection` a déménagé dans `llm_gateway.core.selection`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `llm_gateway.core.selection`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.core.selection est déprécié : importez llm_gateway.core.selection (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from llm_gateway.core.selection import *  # noqa: E402,F401,F403
