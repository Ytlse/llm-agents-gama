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
from typing import Tuple

import httpx

from llm_module.adapters.base import (
    BaseAdapter,
    ProviderClientError,
    ProviderServerError,
    extract_error_type,
    register_adapter,
)
from llm_module.settings.models import InternalRequest, LLMOutput


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

        base_url = self._get_base_url()

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

    def ping(self) -> bool:
        from llm_module.tasks.config import settings
        try:
            model = settings.providers[self._instance_name].default_model
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(
                    f"{self._get_base_url()}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._get_api_key().get_secret_value()}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": "Hello"}],
                        "max_tokens": 5,
                    },
                )
            return resp.status_code < 400
        except Exception:
            return False

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code >= 500:
            raise ProviderServerError(
                self.provider_name, response.status_code, response.text,
                error_type=extract_error_type(response.text, response.status_code),
            )
        if response.status_code >= 400:
            raise ProviderClientError(
                self.provider_name, response.status_code, response.text,
                error_type=extract_error_type(response.text, response.status_code),
            )

