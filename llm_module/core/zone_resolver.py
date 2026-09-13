"""Shim de compatibilité — `llm_module.core.zone_resolver` a déménagé dans `mobility_core.zone_resolver`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `mobility_core.zone_resolver`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.core.zone_resolver est déprécié : importez mobility_core.zone_resolver (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from mobility_core.zone_resolver import *  # noqa: E402,F401,F403
