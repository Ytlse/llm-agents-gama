"""Shim de compatibilité — `llm_module.prompts.manager` a déménagé dans `llm_gateway.prompts.engine`.

Ce module disparaîtra à la version majeure suivante de llm-gateway (2.0). Remplacez
l'import par `llm_gateway.prompts.engine`.
"""
import warnings as _warnings

_warnings.warn(
    "llm_module.prompts.manager est déprécié : importez llm_gateway.prompts.engine (retrait prévu en 2.0).",
    DeprecationWarning,
    stacklevel=2,
)

from llm_gateway.prompts.engine import *  # noqa: E402,F401,F403
from mobility_llm import prompt_manager as get_prompt_manager  # noqa: E402,F401


def __getattr__(name):
    if name == 'prompt_manager':
        return get_prompt_manager()
    raise AttributeError(name)
