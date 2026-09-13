"""Shim de compatibilité — `llm_module.telemetry.logger` a déménagé dans `llm_gateway.telemetry.logger`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `llm_gateway.telemetry.logger`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.telemetry.logger est déprécié : importez llm_gateway.telemetry.logger (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from llm_gateway.telemetry.logger import *  # noqa: E402,F401,F403
