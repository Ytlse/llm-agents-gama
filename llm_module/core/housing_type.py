"""Shim de compatibilité — `llm_module.core.housing_type` a déménagé dans `mobility_core.housing_type`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `mobility_core.housing_type`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.core.housing_type est déprécié : importez mobility_core.housing_type (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from mobility_core.housing_type import *  # noqa: E402,F401,F403
