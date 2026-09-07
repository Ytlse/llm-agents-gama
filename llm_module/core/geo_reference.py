"""Shim de compatibilité — `llm_module.core.geo_reference` a déménagé dans `mobility_core.geo_reference`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `mobility_core.geo_reference`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.core.geo_reference est déprécié : importez mobility_core.geo_reference (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from mobility_core.geo_reference import *  # noqa: E402,F401,F403
