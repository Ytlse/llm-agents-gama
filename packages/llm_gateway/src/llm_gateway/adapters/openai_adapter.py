"""adapters/openai_adapter.py — OpenAI : sortie structurée native (`response_format: json_schema`)."""
from __future__ import annotations

from llm_gateway.adapters.base import register_adapter
from llm_gateway.adapters.openai_compatible import OpenAICompatibleAdapter


@register_adapter
class OpenAIAdapter(OpenAICompatibleAdapter):
    provider_name = "openai"
    structured_output = "json_schema"
    schema_in_system = False


__all__ = ["OpenAIAdapter"]
