"""Shim de compatibilité — `llm_module.core.bike_ownership` a déménagé dans `mobility_core.bike_ownership`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `mobility_core.bike_ownership`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.core.bike_ownership est déprécié : importez mobility_core.bike_ownership (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from mobility_core.bike_ownership import *  # noqa: E402,F401,F403
