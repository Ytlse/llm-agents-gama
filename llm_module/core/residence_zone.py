"""Shim de compatibilité — `llm_module.core.residence_zone` a déménagé dans `mobility_core.residence_zone`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `mobility_core.residence_zone`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.core.residence_zone est déprécié : importez mobility_core.residence_zone (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from mobility_core.residence_zone import *  # noqa: E402,F401,F403
