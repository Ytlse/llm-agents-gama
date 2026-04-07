"""
adapters/google_adapter.py — Traducteur pour l'API Google Gemini.

Format cible (API REST Gemini) :
  POST /v1beta/models/{model}:generateContent
  {
    "contents": [{"role": "user", "parts": [{"text": "..."}]}],
    "generationConfig": {
      "responseMimeType": "application/json",
      "responseSchema": {...}
    }
  }

Différences notables vs OpenAI :
  - "system" → systemInstruction séparé (pas dans contents)
  - "assistant" → "model" dans le rôle Gemini
  - Structured Output via generationConfig.responseSchema
  - Usage dans usageMetadata (et non usage)
"""

from __future__ import annotations
import json
from typing import Any, Dict, List, Tuple

import httpx

from llm_module.adapters.base import (
    BaseAdapter,
    ProviderClientError,
    ProviderParseError,
    ProviderServerError,
    register_adapter,
)
from llm_module.settings.models import AgentResponse, InternalRequest, LLMOutput

from llm_module.telemetry.logger import get_logger
logger = get_logger(__name__)

@register_adapter
class GoogleAdapter(BaseAdapter):
    provider_name = "google"

    # Mapping des rôles OpenAI → rôles Gemini
    ROLE_MAP = {
        "user":      "user",
        "assistant": "model",
        # "system" est traité séparément (systemInstruction)
    }

    def call(self, request: InternalRequest) -> Tuple[LLMOutput, int, int]:
        api_key = self._get_api_key()
        model   = self._resolve_model(request)

        system_instruction, contents = self._convert_messages(request)

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
                "responseMimeType": "application/json",
                "responseSchema": self._clean_schema(request.response_schema),
            },
        }

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        from llm_module.tasks.config import settings
        base_url = settings.providers[self.provider_name].base_url
        url = f"{base_url}/models/{model}:generateContent?key={api_key.get_secret_value()}"

        logger.info("Request Payload:")
        logger.info(json.dumps(payload, indent=2))

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                url,
                headers={"Content-Type": "application/json"},
                json=payload,
            )

        self._raise_for_status(response)

        data = response.json()
        raw_content = data["candidates"][0]["content"]["parts"][0]["text"]

        usage = data.get("usageMetadata", {})
        tokens_in  = usage.get("promptTokenCount", 0)
        tokens_out = usage.get("candidatesTokenCount", 0)

        return self._parse_output(raw_content), tokens_in, tokens_out

    def _convert_messages(
        self, request: InternalRequest
    ) -> Tuple[str, List[Dict]]:
        """
        Sépare le message 'system' (→ systemInstruction) des autres messages
        et convertit les rôles au format Gemini.
        """
        system_text = ""
        contents = []

        for msg in request.messages:
            if msg.role == "system":
                system_text += msg.content + "\n"
                continue
            gemini_role = self.ROLE_MAP.get(msg.role, "user")
            contents.append({
                "role": gemini_role,
                "parts": [{"text": msg.content}],
            })

        return system_text.strip(), contents

    def _clean_schema(self, schema: dict) -> dict:
        """Supprime récursivement les champs non supportés par Gemini."""
        UNSUPPORTED = {"additionalProperties", "$defs", "$schema", "title"}
        if isinstance(schema, dict):
            return {
                k: self._clean_schema(v)
                for k, v in schema.items()
                if k not in UNSUPPORTED
            }
        if isinstance(schema, list):
            return [self._clean_schema(i) for i in schema]
        return schema

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
