"""adapters — traducteurs vers les API des fournisseurs LLM (registre + cache d'instances)."""

from llm_gateway.adapters.base import (
    BaseAdapter,
    ProviderClientError,
    ProviderError,
    ProviderParseError,
    ProviderServerError,
    close_all_adapters,
    get_adapter,
    register_adapter,
)

__all__ = [
    "BaseAdapter",
    "ProviderClientError",
    "ProviderError",
    "ProviderParseError",
    "ProviderServerError",
    "close_all_adapters",
    "get_adapter",
    "register_adapter",
]
