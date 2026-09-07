"""Shim de compatibilité — `llm_module.core.mode_choice` a déménagé dans `mobility_llm.mode_choice`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `mobility_llm.mode_choice`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.core.mode_choice est déprécié : importez mobility_llm.mode_choice (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from mobility_llm.mode_choice import *  # noqa: E402,F401,F403
from mobility_llm.mode_choice import _MODE_KEYWORDS  # noqa: E402,F401
