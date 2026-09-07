"""adapters/mistral_adapter.py — Mistral : dialecte OpenAI, `json_object`, schéma recopié en system.

Les modèles récents acceptent aussi `json_schema` : `structured_output: json_schema` sur
l'instance suffit à basculer, sans code.
"""
from __future__ import annotations

from llm_gateway.adapters.base import register_adapter
from llm_gateway.adapters.openai_compatible import OpenAICompatibleAdapter


@register_adapter
class MistralAdapter(OpenAICompatibleAdapter):
    provider_name = "mistral"
    structured_output = "json_object"
    schema_in_system = True


__all__ = ["MistralAdapter"]
