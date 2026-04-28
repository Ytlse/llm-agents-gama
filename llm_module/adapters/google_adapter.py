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

_logger = get_logger(__name__)


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
                "temperature":      request.temperature,
                "maxOutputTokens":  request.max_tokens,
                "response_mime_type": "application/json",
                "response_json_schema":   self._clean_schema(request.response_schema),
            },
        }

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        base_url = self._get_base_url()
        url = f"{base_url}/models/{model}:generateContent?key={api_key.get_secret_value()}"

        try:
            with httpx.Client(timeout=240.0) as client:
                response = client.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                )
            self._raise_for_status(response)
        except httpx.TimeoutException as exc:
            _logger.warning(f"Timeout de l'API Google | model={model} error={exc}")
            # 504 correspond à Gateway Timeout, éligible au mécanisme de Retry de votre worker
            raise ProviderServerError(self.provider_name, 504, f"Request timeout: {exc}", error_type="timeout")

        data = response.json()
        
        candidates = data.get("candidates", [])
        if not candidates:
            raise ProviderClientError(self.provider_name, 400, f"Aucun candidat retourné. Data: {data}")
            
        candidate = candidates[0]
        if "content" not in candidate or "parts" not in candidate["content"]:
            finish_reason = candidate.get("finishReason", "UNKNOWN")
            raise ProviderClientError(self.provider_name, 400, f"Réponse bloquée ou vide. Raison: {finish_reason}")

        raw_content = candidate["content"]["parts"][0]["text"]

        usage      = data.get("usageMetadata", {})
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
                "role":  gemini_role,
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

    def ping(self) -> bool:
        from llm_module.tasks.config import settings
        try:
            model = settings.providers[self._instance_name].default_model
            api_key = self._get_api_key().get_secret_value()
            url = f"{self._get_base_url()}/models/{model}:generateContent?key={api_key}"
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json={
                        "contents": [{"parts": [{"text": "Hello"}]}],
                        "generationConfig": {"maxOutputTokens": 5},
                    },
                )
            ok = resp.status_code < 400
            return ok
        except Exception as exc:
            _logger.warning(f"ping EXCEPTION | provider={self._instance_name} error={exc}")
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
