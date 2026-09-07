"""Shim de compatibilité — `llm_module.load_balancer.router` a déménagé dans `llm_gateway.balancer.router`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `llm_gateway.balancer.router`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.load_balancer.router est déprécié : importez llm_gateway.balancer.router (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from llm_gateway.balancer.router import *  # noqa: E402,F401,F403
