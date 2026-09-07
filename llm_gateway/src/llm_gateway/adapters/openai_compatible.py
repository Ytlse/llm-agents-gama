"""
adapters/openai_compatible.py — un seul traducteur pour toute API « /chat/completions ».

OpenAI, Groq, Cerebras, Mistral, mais aussi Ollama, vLLM, OpenRouter, LM Studio… parlent le
même dialecte : `POST {base_url}/chat/completions`, `choices[0].message.content`, `usage`.
Ce qui varie tient en deux réglages, portés par la sous-classe **ou** par l'instance dans le
fichier des fournisseurs (`structured_output`, `schema_in_system`) :

- `structured_output` : `json_schema` (sortie structurée native, OpenAI), `json_object`
  (le modèle promet du JSON, le schéma voyage dans le prompt), `none` (rien) ;
- `schema_in_system` : recopier le schéma JSON dans le message system, pour les modèles qui
  ne le reçoivent pas autrement (Mistral, Cerebras).

Un fournisseur compatible s'ajoute donc **par configuration seule** :

    mon_ollama:
      adapter: openai_compatible
      structured_output: json_object
      base_url: http://ollama:11434/v1
      default_model: qwen3:8b
      rpm_limit: 60
"""
from __future__ import annotations

import json
from typing import Any, Literal

from llm_gateway.adapters.base import BaseAdapter, register_adapter
from llm_gateway.core.models import InternalRequest, LLMOutput

StructuredOutput = Literal["json_schema", "json_object", "none"]


@register_adapter
class OpenAICompatibleAdapter(BaseAdapter):
    provider_name = "openai_compatible"

    # Défauts de la classe ; l'instance du fichier des fournisseurs peut les surcharger.
    structured_output: StructuredOutput = "json_object"
    schema_in_system: bool = False
    auth_header: str = "Authorization"
    auth_scheme: str = "Bearer"

    # ── Réglages effectifs (instance > classe) ───────────────────────────────

    def _instance_config(self) -> Any:
        from llm_gateway.config import get_settings

        return get_settings().providers.get(self._instance_name)

    def _structured_output(self) -> StructuredOutput:
        cfg = self._instance_config()
        value = getattr(cfg, "structured_output", None) if cfg is not None else None
        return value or self.structured_output

    def _schema_in_system(self) -> bool:
        cfg = self._instance_config()
        value = getattr(cfg, "schema_in_system", None) if cfg is not None else None
        return self.schema_in_system if value is None else bool(value)

    # ── Construction de la requête ──────────────────────────────────────────

    def _messages(self, request: InternalRequest) -> list[dict[str, Any]]:
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        if not self._schema_in_system():
            return messages
        instruction = (
            "\nTu dois répondre UNIQUEMENT en JSON valide, sans markdown, en respectant ce "
            f"schéma : {json.dumps(request.response_schema, ensure_ascii=False)}"
        )
        for msg in messages:
            if msg["role"] == "system":
                msg["content"] = (msg["content"] or "") + instruction
                return messages
        messages.insert(0, {"role": "system", "content": instruction.strip()})
        return messages

    def _response_format(self, request: InternalRequest) -> dict[str, Any] | None:
        mode = self._structured_output()
        if mode == "json_schema":
            return {
                "type": "json_schema",
                "json_schema": {"name": "agents_output", "strict": True, "schema": request.response_schema},
            }
        if mode == "json_object":
            return {"type": "json_object"}
        return None

    def build_payload(self, request: InternalRequest) -> dict[str, Any]:
        """Le corps envoyé au fournisseur ; exposé pour les tests et les adapters dérivés."""
        payload: dict[str, Any] = {
            "model": self._resolve_model(request),
            "messages": self._messages(request),
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        response_format = self._response_format(request)
        if response_format is not None:
            payload["response_format"] = response_format
        return payload

    def _headers(self) -> dict[str, str]:
        key = self._get_api_key().get_secret_value()
        value = f"{self.auth_scheme} {key}".strip() if self.auth_scheme else key
        return {self.auth_header: value, "Content-Type": "application/json"}

    # ── Appel ───────────────────────────────────────────────────────────────

    def call(self, request: InternalRequest) -> tuple[LLMOutput, int, int]:
        response = self._post(
            f"{self._get_base_url()}/chat/completions",
            headers=self._headers(),
            json=self.build_payload(request),
        )
        self._raise_for_status(response)
        data = response.json()
        self._check_openai_finish_reason(data)
        raw_content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {}) or {}
        tokens_in = usage.get("prompt_tokens", 0)
        tokens_out = usage.get("completion_tokens", 0)
        return self._parse_output(raw_content), tokens_in, tokens_out


__all__ = ["OpenAICompatibleAdapter", "StructuredOutput"]
