"""Shim de compatibilité — `llm_module.ports.batch_queue` a déménagé dans `llm_gateway.ports.batch_queue`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `llm_gateway.ports.batch_queue`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.ports.batch_queue est déprécié : importez llm_gateway.ports.batch_queue (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from llm_gateway.ports.batch_queue import *  # noqa: E402,F401,F403
