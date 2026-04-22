"""
adapters/groq_adapter.py — Traducteur pour l'API Groq.

Format cible (API REST Groq — compatible OpenAI) :
  POST /openai/v1/chat/completions
  {
    "model": "llama3-8b-8192",
    "messages": [{"role": "user", "content": "..."}],
    "temperature": 0.7,
    "max_tokens": 1024,
    "response_format": {"type": "json_object"}
  }

Différences notables vs Google :
  - API compatible OpenAI : rôles identiques (system, user, assistant)
  - Structured Output via response_format (json_object uniquement, pas de schema)
  - Usage dans .usage (prompt_tokens / completion_tokens)
  - Auth : Bearer token dans le header Authorization
"""

from __future__ import annotations
import json
from typing import Any, Dict, List, Tuple

import httpx

from llm_module.adapters.base import (
    BaseAdapter,
    ProviderClientError,
    ProviderServerError,
    extract_error_type,
    register_adapter,
)
from llm_module.settings.models import InternalRequest, LLMOutput

from llm_module.telemetry.logger import get_logger
logger = get_logger(__name__)

@register_adapter
class GroqAdapter(BaseAdapter):
    provider_name = "groq" 

    def call(self, request: InternalRequest) -> Tuple[LLMOutput, int, int]:
        api_key = self._get_api_key()
        model   = self._resolve_model(request)

        base_url = self._get_base_url()
        url = f"{base_url}/chat/completions"

        payload: Dict[str, Any] = {
            "model": model,
            "messages": self._convert_messages(request),
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "response_format": {"type": "json_object"},
        }

        logger.info("Request Payload:")
        logger.info(json.dumps(payload, indent=2))

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key.get_secret_value()}",
                },
                json=payload,
            )

        self._raise_for_status(response)

        data = response.json()
        raw_content = data["choices"][0]["message"]["content"]

        usage      = data.get("usage", {})
        tokens_in  = usage.get("prompt_tokens", 0)
        tokens_out = usage.get("completion_tokens", 0)

        return self._parse_output(raw_content), tokens_in, tokens_out

    def _convert_messages(self, request: InternalRequest) -> List[Dict]:
        """
        Groq / OpenAI acceptent les rôles system, user, assistant tels quels.
        Pas de transformation nécessaire.
        """
        return [
            {"role": msg.role, "content": msg.content}
            for msg in request.messages
        ]

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

