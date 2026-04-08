"""
adapters/openai_adapter.py — Traducteur pour l'API OpenAI (et compatibles).

Format cible :
  POST /v1/chat/completions
  {
    "model": "...",
    "messages": [{"role": "...", "content": "..."}],
    "response_format": {"type": "json_schema", "json_schema": {...}}
  }

OpenAI supporte nativement le Structured Output via response_format.
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
from llm_module.settings.models import AgentResponse, InternalRequest, LLMOutput


@register_adapter
class OpenAIAdapter(BaseAdapter):
    provider_name = "openai"

    def call(self, request: InternalRequest) -> Tuple[LLMOutput, int, int]:
        api_key = self._get_api_key()
        model   = self._resolve_model(request)

        payload = {
            "model": model,
            "messages": [
                {"role": m.role, "content": m.content}
                for m in request.messages
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            # Structured Output OpenAI
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "agents_output",
                    "strict": True,
                    "schema": request.response_schema,
                },
            },
        }

        from llm_module.tasks.config import settings
        base_url = settings.providers[self.provider_name].base_url

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key.get_secret_value()}",
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

    # ------------------------------------------------------------------
    # Helpers privés
    # ------------------------------------------------------------------

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
