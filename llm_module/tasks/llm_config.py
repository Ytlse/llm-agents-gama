"""Shim de compatibilité — `llm_module.tasks.llm_config` a déménagé dans `llm_gateway.config`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `llm_gateway.config`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.tasks.llm_config est déprécié : importez llm_gateway.config (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from llm_gateway.config import *  # noqa: E402,F401,F403
from llm_gateway.config import get_settings as _gs  # noqa: E402

_load_provider_defaults = load_provider_defaults  # noqa: F405
settings = _gs()


def get_batch_max_agents(force_provider=None):
    return settings.get_batch_max_agents(force_provider)
