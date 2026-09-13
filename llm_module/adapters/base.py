"""Shim de compatibilité — `llm_module.adapters.base` a déménagé dans `llm_gateway.adapters.base`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `llm_gateway.adapters.base`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.adapters.base est déprécié : importez llm_gateway.adapters.base (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from llm_gateway.adapters.base import *  # noqa: E402,F401,F403
from llm_gateway.adapters.base import _REGISTRY, _INSTANCES, _load_adapters  # noqa: E402,F401
