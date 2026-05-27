"""
adapters/cerebras_adapter.py — Adaptateur pour l'API Cerebras.
"""

from __future__ import annotations
import json
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
from llm_module.telemetry.logger import get_logger

logger = get_logger(__name__)

@register_adapter
class CerebrasAdapter(BaseAdapter):
    provider_name = "cerebras"

    def call(self, request: InternalRequest) -> Tuple[LLMOutput, int, int]:
        api_key = self._get_api_key()
        model   = self._resolve_model(request)

        # Injection du schéma JSON strict dans le message system
        messages = self._inject_schema_in_system(request)

        payload = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": False,
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
        
        usage      = data.get("usage", {})
        tokens_in  = usage.get("prompt_tokens", 0)
        tokens_out = usage.get("completion_tokens", 0)

        return self._parse_output(raw_content), tokens_in, tokens_out

    def _inject_schema_in_system(self, request: InternalRequest) -> list[dict]:
        schema_instruction = (
            f"\nTu dois répondre UNIQUEMENT en JSON valide, sans markdown, "
            f"en respectant ce schéma : {json.dumps(request.response_schema, ensure_ascii=False)}"
        )

        messages = [{"role": m.role, "content": m.content} for m in request.messages]

        for msg in messages:
            if msg["role"] == "system":
                msg["content"] += schema_instruction
                return messages

        messages.insert(0, {"role": "system", "content": schema_instruction.strip()})
        return messages

    def ping(self) -> bool:
        from llm_module.tasks.llm_config import settings
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