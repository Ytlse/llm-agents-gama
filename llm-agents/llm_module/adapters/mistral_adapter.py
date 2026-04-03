"""
adapters/mistral_adapter.py — Traducteur pour l'API Mistral AI.

Format cible :
  POST /v1/chat/completions  (compatible OpenAI)
  Structured Output via response_format + json_object (Mistral ≥ mistral-small-3).

Note : Mistral utilise le même format /chat/completions qu'OpenAI mais
son endpoint Structured Output passe par "response_format": {"type": "json_object"}
combiné à des instructions dans le system prompt.
Pour les modèles récents, Mistral supporte aussi json_schema comme OpenAI.
"""

from __future__ import annotations
import json
from typing import Tuple

import httpx

from llm_module.adapters.base import (
    BaseAdapter,
    ProviderClientError,
    ProviderParseError,
    ProviderServerError,
    register_adapter,
)
from llm_module.models import AgentResponse, InternalRequest, LLMOutput


@register_adapter
class MistralAdapter(BaseAdapter):
    provider_name = "mistral"

    def call(self, request: InternalRequest) -> Tuple[LLMOutput, int, int]:
        api_key = self._get_api_key()
        model   = self._resolve_model(request)

        # Injection du schéma JSON dans le system prompt (fallback compatible)
        messages = self._inject_schema_in_system(request)

        payload = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "response_format": {"type": "json_object"},
        }

        from llm_module.config import settings
        base_url = settings.providers[self.provider_name].base_url

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        self._raise_for_status(response)

        data = response.json()
        raw_content = data["choices"][0]["message"]["content"]
        tokens_in   = data.get("usage", {}).get("prompt_tokens", 0)
        tokens_out  = data.get("usage", {}).get("completion_tokens", 0)

        return self._parse_output(raw_content), tokens_in, tokens_out

    def _inject_schema_in_system(self, request: InternalRequest) -> list[dict]:
        """
        Ajoute les instructions de format JSON dans le message system existant.
        Si aucun message system n'existe, en crée un.
        """
        schema_instruction = (
            f"\nTu dois répondre UNIQUEMENT en JSON valide, sans markdown, "
            f"en respectant ce schéma : {json.dumps(request.response_schema, ensure_ascii=False)}"
        )

        messages = [{"role": m.role, "content": m.content} for m in request.messages]

        for msg in messages:
            if msg["role"] == "system":
                msg["content"] += schema_instruction
                return messages

        # Pas de message system → on en insère un au début
        messages.insert(0, {"role": "system", "content": schema_instruction.strip()})
        return messages

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code >= 500:
            raise ProviderServerError(self.provider_name, response.status_code, response.text)
        if response.status_code >= 400:
            raise ProviderClientError(self.provider_name, response.status_code, response.text)

    def _parse_output(self, raw: str) -> LLMOutput:
        try:
            data = json.loads(raw)
            agents = [AgentResponse(**item) for item in data["agents"]]
            return LLMOutput(agents=agents)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise ProviderParseError(self.provider_name, raw, str(e))
