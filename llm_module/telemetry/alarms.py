"""Shim de compatibilité — `llm_module.telemetry.alarms` a déménagé dans `llm_gateway.telemetry.alarms`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `llm_gateway.telemetry.alarms`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.telemetry.alarms est déprécié : importez llm_gateway.telemetry.alarms (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from llm_gateway.telemetry.alarms import *  # noqa: E402,F401,F403
