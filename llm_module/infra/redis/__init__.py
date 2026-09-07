"""Shim de compatibilité — `llm_module.infra.redis` a déménagé dans `llm_gateway.infra.redis`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `llm_gateway.infra.redis`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.infra.redis est déprécié : importez llm_gateway.infra.redis (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from llm_gateway.infra.redis import *  # noqa: E402,F401,F403
