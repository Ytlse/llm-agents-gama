"""Shim de compatibilité — `llm_module.core.mode_hierarchy` a déménagé dans `mobility_core.mode_hierarchy`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `mobility_core.mode_hierarchy`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.core.mode_hierarchy est déprécié : importez mobility_core.mode_hierarchy (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from mobility_core.mode_hierarchy import *  # noqa: E402,F401,F403
