"""adapters — traducteurs vers les API des fournisseurs LLM (registre, cache d'instances, entry points).

`OpenAICompatibleAdapter` couvre tout dialecte `/chat/completions` ; OpenAI, Groq, Cerebras et
Mistral en sont des réglages. Google a son propre traducteur. Un paquet tiers apporte le sien par
l'entry point `llm_gateway.adapters`.
"""

from llm_gateway.adapters.base import (
    ADAPTERS_ENTRY_POINT,
    BaseAdapter,
    ProviderClientError,
    ProviderError,
    ProviderParseError,
    ProviderServerError,
    close_all_adapters,
    get_adapter,
    register_adapter,
)
from llm_gateway.adapters.openai_compatible import OpenAICompatibleAdapter

__all__ = [
    "ADAPTERS_ENTRY_POINT",
    "BaseAdapter",
    "OpenAICompatibleAdapter",
    "ProviderClientError",
    "ProviderError",
    "ProviderParseError",
    "ProviderServerError",
    "close_all_adapters",
    "get_adapter",
    "register_adapter",
]
