"""Shim de compatibilité — `llm_module.core.equipment_propensity` a déménagé dans `mobility_core.equipment_propensity`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `mobility_core.equipment_propensity`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.core.equipment_propensity est déprécié : importez mobility_core.equipment_propensity (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from mobility_core.equipment_propensity import *  # noqa: E402,F401,F403
