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

import threading
import time
from typing import Any, Dict, List, Tuple

import httpx

from llm_module.adapters.base import (
    BaseAdapter,
    ProviderClientError,
    ProviderServerError,
    extract_error_type,
    register_adapter,
)
from llm_module.core.models import InternalRequest, LLMOutput
from llm_module.telemetry.logger import get_logger

_logger = get_logger(__name__)

# Seuil de troncatures MAX_TOKENS consécutives au-delà duquel on passe du WARNING
# à une ERREUR `[ALARME]`. Déclenchement sur FRONT MONTANT (une seule alarme par
# épisode, réarmée par le premier succès) : une troncature isolée est un aléa, une
# série signale un plafond `max_tokens` sous-dimensionné ou une boucle de répétition
# — et sans ce signal, le retry de l'appelant la rejoue en silence jusqu'à épuisement.
_MAX_TOKENS_ALARM_THRESHOLD = 3


@register_adapter
class GoogleAdapter(BaseAdapter):
    provider_name = "google"

    # Plafond de patience d'UN appel. Mesuré le 2026-07-31 sur
    # gemini-3.1-flash-lite-preview, lots de 15 personas du jeu `train` avec
    # distribution complète par persona : 3,6 à 8,8 s par appel, 2 742 tokens de
    # complétion au pire. La marge est donc de deux ordres de grandeur — ce n'est
    # PAS ce timeout qui bloquait la ré-évaluation pondérée (cf. docs/changelog.md
    # du 2026-07-31). Ne pas le rallonger sans une mesure qui le justifie : un appel
    # réellement bloqué doit finir par rendre la main.
    request_timeout = 240.0

    # Mapping des rôles OpenAI → rôles Gemini
    ROLE_MAP = {
        "user":      "user",
        "assistant": "model",
        # "system" est traité séparément (systemInstruction)
    }

    def __init__(self):
        super().__init__()
        # Troncatures MAX_TOKENS consécutives, par instance d'adaptateur (les
        # adapters sont partagés entre threads : un verrou suffit, la granularité
        # n'a pas besoin d'être exacte).
        self._trunc_streak = 0
        self._trunc_lock = threading.Lock()

    def _note_truncation(self, model: str, detail: str) -> None:
        """Compte une troncature et lève l'`[ALARME]` sur le front montant."""
        with self._trunc_lock:
            self._trunc_streak += 1
            streak = self._trunc_streak
        if streak == _MAX_TOKENS_ALARM_THRESHOLD:
            _logger.error(
                f"[ALARME] {streak} troncatures MAX_TOKENS consécutives | "
                f"provider={self._instance_name} model={model} — le plafond "
                f"max_tokens est sous-dimensionné ou le modèle boucle ; les retries "
                f"vont rejouer la même troncature. {detail}"
            )

    def _note_completion(self) -> None:
        """Réarme le front montant : une complétion propre clôt l'épisode."""
        with self._trunc_lock:
            self._trunc_streak = 0

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
        # Clé API en header x-goog-api-key (jamais en query string : les URLs
        # finissent dans les logs et les traces d'erreur).
        url = f"{base_url}/models/{model}:generateContent"

        started = time.monotonic()
        try:
            response = self._http().post(
                url,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": api_key.get_secret_value(),
                },
                json=payload,
            )
            self._raise_for_status(response)
        except httpx.TimeoutException as exc:
            elapsed = time.monotonic() - started
            # Le timeout est le SEUL cas où l'on ne saura jamais ni le finishReason ni
            # les tokens produits : on trace au moins le budget demandé et le temps
            # réellement attendu, pour distinguer « génération trop longue » de
            # « plafond trop court ».
            _logger.warning(
                f"Timeout de l'API Google après {elapsed:.1f}s "
                f"(limite {self.request_timeout:.0f}s) | provider={self._instance_name} "
                f"model={model} max_tokens_demandes={request.max_tokens} error={exc}"
            )
            # 504 correspond à Gateway Timeout, éligible au mécanisme de Retry de votre worker
            # _instance_name (ex: "google_gemma42") et non provider_name ("google") :
            # le cooldown est indexé sur le nom d'instance configuré dans providers.yaml.
            raise ProviderServerError(self._instance_name, 504, f"Request timeout: {exc}", error_type="timeout")

        elapsed = time.monotonic() - started
        data = response.json()

        # ── Les trois grandeurs de diagnostic ────────────────────────────────
        # Sans elles, un lot qui « n'avance plus » est indiscernable d'un lot lent,
        # tronqué, ou d'un modèle qui rend une réponse incomplète mais valide. Elles
        # sont donc relevées AVANT toute levée d'exception, et rappelées dans le
        # message de chaque erreur.
        usage = data.get("usageMetadata", {})
        tokens_in = usage.get("promptTokenCount", 0)
        completion_tokens = usage.get("candidatesTokenCount", 0)
        # Les tokens de « pensée » des modèles à raisonnement sont facturés ET
        # décomptés du plafond maxOutputTokens : les ignorer sous-estimait à la fois
        # la consommation et la cause d'une troncature.
        thoughts_tokens = usage.get("thoughtsTokenCount", 0) or 0
        tokens_out = completion_tokens + thoughts_tokens

        candidates = data.get("candidates", [])
        if not candidates:
            raise ProviderClientError(
                self._instance_name, 400,
                f"Aucun candidat retourné après {elapsed:.1f}s "
                f"(tokens in={tokens_in} out={tokens_out}). Data: {data}")

        candidate = candidates[0]
        finish_reason = candidate.get("finishReason", "STOP")

        if "content" not in candidate or "parts" not in candidate["content"]:
            raise ProviderClientError(
                self._instance_name, 400,
                f"Réponse bloquée ou vide après {elapsed:.1f}s. "
                f"Raison: {finish_reason} (tokens in={tokens_in} "
                f"completion={completion_tokens} thoughts={thoughts_tokens})")

        raw_content = candidate["content"]["parts"][0]["text"]

        _logger.debug(
            f"Appel Google | provider={self._instance_name} model={model} "
            f"latence={elapsed:.1f}s finishReason={finish_reason} "
            f"tokens_in={tokens_in} completion={completion_tokens} "
            f"thoughts={thoughts_tokens} plafond={request.max_tokens}"
        )

        if finish_reason == "MAX_TOKENS":
            detail = (f"latence={elapsed:.1f}s completion={completion_tokens} "
                      f"thoughts={thoughts_tokens} plafond={request.max_tokens}")
            _logger.warning(
                f"Réponse tronquée (MAX_TOKENS) — plafond atteint ou boucle de "
                f"répétition | provider={self._instance_name} model={model} {detail} "
                f"raw_preview={raw_content[:200]!r}"
            )
            self._note_truncation(model, detail)
            raise ProviderServerError(
                self._instance_name, 503,
                f"Output truncated at MAX_TOKENS limit ({detail}) — "
                f"possible repetition loop",
                error_type="max_tokens_truncation",
            )

        self._note_completion()
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
        from llm_module.config import get_settings
        try:
            model = get_settings().providers[self._instance_name].default_model
            api_key = self._get_api_key().get_secret_value()
            url = f"{self._get_base_url()}/models/{model}:generateContent"
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "x-goog-api-key": api_key,
                    },
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


