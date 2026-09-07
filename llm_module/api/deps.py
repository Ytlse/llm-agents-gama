"""Shim de compatibilité — `llm_module.api.deps` a déménagé dans `llm_gateway.api.deps`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `llm_gateway.api.deps`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.api.deps est déprécié : importez llm_gateway.api.deps (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from llm_gateway.api.deps import *  # noqa: E402,F401,F403
