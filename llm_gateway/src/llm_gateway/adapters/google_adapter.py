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
from typing import Any

import httpx

from llm_gateway.adapters.base import (
    BaseAdapter,
    ProviderClientError,
    ProviderServerError,
    register_adapter,
)
from llm_gateway.config.settings import get_settings
from llm_gateway.core.models import InternalRequest, LLMOutput
from llm_gateway.telemetry.logger import get_logger

_logger = get_logger(__name__)

# Seuil de troncatures MAX_TOKENS consécutives au-delà duquel on passe du WARNING
# à une ERREUR `[ALARME]`. Déclenchement sur FRONT MONTANT (une seule alarme par
# épisode, réarmée par le premier succès) : une troncature isolée est un aléa, une
# Réserve de sortie quand la réflexion est laissée au modèle (`thinking_budget: -1`) : on ne
# sait pas combien de jetons de pensée il consommera, et ils sont pris sur le budget de sortie.
# Valeur reprise de `prompt_calibration` (`mutation_thinking_reserve`), éprouvée sur la
# campagne génétique.
RESERVE_REFLEXION = 2048

# série signale un plafond `max_tokens` sous-dimensionné ou une boucle de répétition
# — et sans ce signal, le retry de l'appelant la rejoue en silence jusqu'à épuisement.
_MAX_TOKENS_ALARM_THRESHOLD = 3


@register_adapter
class GoogleAdapter(BaseAdapter):
    provider_name = "google"

    # Seul adapter qui sache transmettre la profondeur de réflexion (`generationConfig
    # .thinkingConfig`). Ailleurs, le réglage est signalé comme non appliqué.
    applique_reflexion = True

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

    def call(self, request: InternalRequest) -> tuple[LLMOutput, int, int]:
        api_key = self._get_api_key()
        model   = self._resolve_model(request)

        system_instruction, contents = self._convert_messages(request)

        # Profondeur de réflexion (2026-09-10) : jusqu'ici AUCUN thinkingConfig n'était envoyé,
        # donc tous les Gemini tournaient avec leur réflexion par défaut, non pilotée — alors
        # que `thoughtsTokenCount` était déjà lu et compté. `None` conserve ce comportement.
        budget = request.thinking_budget
        niveau = request.thinking_level
        self._refuser_reflexion_hors_plafond(budget)
        self._refuser_niveau_non_supporte(niveau)
        plafond = request.max_tokens
        if niveau is not None and niveau != "minimal":
            # Un niveau ne dit pas combien de jetons la pensée prendra, et elle est prélevée
            # sur le budget de sortie : on réserve le forfait, comme pour un budget dynamique.
            plafond = request.max_tokens + RESERVE_REFLEXION
        if budget is not None and budget != 0:
            # La pensée consomme le budget de SORTIE : sans réserve, un budget de réflexion
            # généreux fait tronquer la réponse (MAX_TOKENS) et l'appel est perdu.
            plafond = request.max_tokens + (budget if budget > 0 else RESERVE_REFLEXION)
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature":      request.temperature,
                "maxOutputTokens":  plafond,
                **({"topP": request.top_p} if request.top_p is not None else {}),
                # `thinking_level` en snake_case : c'est la forme donnée par la
                # documentation, et le reste du corps mélange déjà les deux conventions
                # (`response_mime_type` fonctionne à côté de `maxOutputTokens`).
                **({"thinking_level": niveau} if niveau is not None else {}),
                **({"thinkingConfig": {"thinkingBudget": budget, "includeThoughts": False}}
                   if budget is not None else {}),
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
            # _instance_name (ex: "google_gemma42_key1") et non provider_name ("google") :
            # le cooldown est indexé sur le nom d'instance configuré dans providers.yaml.
            raise ProviderServerError(self._instance_name, 504, f"Request timeout: {exc}", error_type="timeout") from exc

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

        self._refuser_substitution_de_modele(model, data)
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
            if request.thinking_budget is not None and thoughts_tokens and not completion_tokens:
                # La pensée a mangé toute la réponse : dire lequel des deux réglages baisser,
                # plutôt que laisser conclure à une boucle de répétition.
                detail += (f" · réflexion demandée={request.thinking_budget} — la pensée a "
                           f"consommé le budget sans laisser de réponse : baisser "
                           f"thinking_budget ou relever max_tokens")
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

    def _refuser_reflexion_hors_plafond(self, budget: int | None) -> None:
        """Refuse un budget de réflexion supérieur au plafond DÉCLARÉ de l'instance.

        Le fournisseur, lui, raboterait sans le dire, et la réponse ne rapporte que les jetons
        de pensée consommés — jamais le budget appliqué. L'expérience scellerait alors dans son
        empreinte un budget qui n'a pas eu lieu. Mieux vaut refuser l'appel.

        Sans `thinking_budget_max` déclaré, aucun contrôle : on ne substitue pas un chiffre
        plausible à une mesure absente.
        """
        if budget is None or budget <= 0:
            return
        cfg = get_settings().providers.get(self._instance_name)
        plafond = getattr(cfg, "thinking_budget_max", None) if cfg else None
        if plafond and budget > int(plafond):
            raise ProviderClientError(
                self._instance_name, 400,
                f"budget de réflexion {budget} au-delà du plafond déclaré {plafond} pour "
                f"{getattr(cfg, 'default_model', '?')!r} : le fournisseur le raboterait sans le "
                f"dire et "
                f"l'empreinte de l'expérience porterait un budget non appliqué. Abaissez "
                f"thinking_budget, ou corrigez thinking_budget_max dans providers.yaml.",
            )

    def _refuser_substitution_de_modele(self, demande: str, data: dict) -> None:
        """Refuse une réponse rendue par un AUTRE modèle que celui demandé.

        Google renvoie `modelVersion`. La comparaison est un PRÉFIXE, pas une égalité : l'API
        répond couramment avec un identifiant versionné (`gemini-3.5-flash-001` pour
        `gemini-3.5-flash`), qui est bien le modèle demandé. En revanche un alias retiré servi
        par son successeur ne commence pas par l'identifiant demandé — cas de
        `gemini-3.1-flash-lite-preview`, arrêté le 2026-05-25, dont deux exécutions de
        septembre portent pourtant le nom dans leur empreinte scellée sans qu'aucune erreur
        n'ait été levée.

        Sans `modelVersion` dans la réponse, aucun contrôle : on ne refuse pas sur un champ
        absent.
        """
        servi = str(data.get("modelVersion") or "").strip()
        if not servi or not demande:
            return
        if servi == demande or servi.startswith(f"{demande}-"):
            return
        raise ProviderClientError(
            self._instance_name, 502,
            f"substitution de modèle : {demande!r} demandé, {servi!r} servi. La mesure "
            f"porterait un nom de modèle faux dans son empreinte scellée. Corrigez "
            f"`default_model` de cette instance — un alias retiré est servi par son "
            f"successeur sans que rien ne le signale.",
        )

    def _refuser_niveau_non_supporte(self, niveau: str | None) -> None:
        """Refuse un niveau de réflexion que le modèle n'accepte pas.

        Les niveaux varient d'un modèle à l'autre : `minimal` existe sur gemini-3.6-flash et
        3.5-flash-lite, pas sur 3.7 ni 3.8 — le demander y rend 400. Le contrôle ne s'exerce
        que si `thinking_levels` est déclaré pour l'instance : sans déclaration, on laisse
        passer plutôt que de bloquer sur une liste devinée.
        """
        if niveau is None:
            return
        cfg = get_settings().providers.get(self._instance_name)
        connus = getattr(cfg, "thinking_levels", None) if cfg else None
        if connus and niveau not in connus:
            raise ProviderClientError(
                self._instance_name, 400,
                f"niveau de réflexion {niveau!r} non accepté par "
                f"{getattr(cfg, 'default_model', '?')!r} : niveaux déclarés "
                f"{', '.join(connus)}. Corrigez `thinking_level`, ou `thinking_levels` dans "
                f"providers.yaml si la liste est fausse.",
            )

    def _convert_messages(
        self, request: InternalRequest
    ) -> tuple[str, list[dict]]:
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
