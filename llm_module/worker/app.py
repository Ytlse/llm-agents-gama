"""Shim de compatibilité — `llm_module.worker.app` a déménagé dans `llm_gateway.worker.app`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `llm_gateway.worker.app`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.worker.app est déprécié : importez llm_gateway.worker.app (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from llm_gateway.worker.app import *  # noqa: E402,F401,F403
