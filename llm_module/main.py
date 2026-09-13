"""Shim de compatibilité — `llm_module.main` a déménagé dans `llm_gateway.main`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `llm_gateway.main`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.main est déprécié : importez llm_gateway.main (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from llm_gateway.main import *  # noqa: E402,F401,F403
from llm_gateway.main import app  # noqa: E402,F401
