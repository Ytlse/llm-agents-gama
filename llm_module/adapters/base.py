"""
adapters/base.py — Interface commune (Adapter Pattern).

Tous les adapters fournisseur implémentent cette classe abstraite.
Le Worker ne connaît que BaseAdapter — il reste découplé des SDKs tiers.
"""

from __future__ import annotations
import json
import re
import threading
from abc import ABC, abstractmethod
from typing import Tuple

try:
    import demjson3 as _demjson
except ImportError:
    _demjson = None

import httpx
from pydantic import ValidationError

from llm_module.config import get_settings
from llm_module.core.models import AgentResponse, InternalRequest, LLMOutput
from llm_module.telemetry.logger import get_logger

_base_logger = get_logger(__name__)


class BaseAdapter(ABC):
    """
    Contrat que chaque traducteur fournisseur doit respecter.

    Méthode principale : call()
      - Prend un InternalRequest (format normalisé interne)
      - Retourne (LLMOutput, tokens_in, tokens_out)
      - Lève une exception en cas d'erreur récupérable (5xx) ou fatale (4xx)
    """

    provider_name: str  # Doit être défini dans chaque sous-classe (nom de la classe d'adapter)

    # Timeout des appels LLM — surchargeable par adapter (Google : 240s).
    request_timeout: float = 120.0

    def __init__(self):
        # Par défaut, l'instance name = le nom de la classe d'adapter.
        # get_adapter() le remplace par le nom de l'instance configurée (ex: "groq_1").
        self._instance_name: str = self.provider_name
        self._client: httpx.Client | None = None
        self._client_lock = threading.Lock()

    def _http(self) -> httpx.Client:
        """Client httpx partagé de l'instance (keep-alive entre appels).

        httpx.Client est thread-safe : les workers Celery (-P threads) peuvent
        l'utiliser concurremment. Évite le handshake TCP/TLS à chaque appel
        (~100-300 ms gagnées par appel LLM).
        """
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    self._client = httpx.Client(timeout=self.request_timeout)
        return self._client

    def close(self) -> None:
        """Libère le client httpx partagé (port LLMAdapter)."""
        with self._client_lock:
            if self._client is not None:
                self._client.close()
                self._client = None

    @abstractmethod
    def call(self, request: InternalRequest) -> Tuple[LLMOutput, int, int]:
        """
        Exécute l'appel HTTP au fournisseur LLM.

        Returns:
            Tuple[LLMOutput, tokens_in, tokens_out]

        Raises:
            ProviderServerError  : erreur 5xx → éligible au retry backoff
            ProviderClientError  : erreur 4xx → non retryable (mauvaise requête)
            ProviderParseError   : réponse JSON invalide ou schema non respecté
        """
        ...

    def ping(self) -> bool:
        """
        Health check minimal : envoie "Hello" sans JSON schema et vérifie que
        le provider répond avec un HTTP < 400.

        Doit être surchargé dans chaque adapter concret.
        Par défaut, retourne True (fail-open) pour ne pas bloquer les adapters
        qui n'ont pas encore implémenté la méthode.
        """
        _base_logger.warning(
            f"ping() non implémenté pour cet adapter — provider inclus par défaut | "
            f"provider={self._instance_name}"
        )
        return True

    def _resolve_model(self, request: InternalRequest) -> str:
        """Retourne le modèle spécifié ou le défaut du provider."""
        if request.model:
            return request.model
        return get_settings().providers[self._instance_name].default_model

    def _get_api_key(self):
        return get_settings().providers[self._instance_name].api_key

    def _get_base_url(self) -> str:
        return get_settings().providers[self._instance_name].base_url

    def _raise_for_status(self, response: "httpx.Response") -> None:
        """Lève une ProviderError si le status HTTP indique une erreur.

        Capture le délai de retry sur les 429 — header x-ratelimit-reset
        (Groq/OpenAI) ou, à défaut, corps JSON (Google Gemini) — et l'attache
        à l'exception pour qu'il apparaisse dans llm_errors.jsonl.
        """
        if response.status_code < 400:
            return
        # Ordre de priorité : retry-after (standard HTTP, exact) puis reset-tokens
        # (les 429 Groq portent sur les limites TPM/TPD, pas sur les requêtes),
        # puis les variantes requests/génériques.
        ratelimit_reset = (
            response.headers.get("retry-after")
            or response.headers.get("x-ratelimit-reset-tokens")
            or response.headers.get("x-ratelimit-reset-requests")
            or response.headers.get("x-ratelimit-reset")
        )
        # Repli : certains providers (Google Gemini) mettent le délai de retry
        # dans le corps JSON plutôt que dans un header.
        if not ratelimit_reset and response.status_code == 429:
            ratelimit_reset = extract_retry_delay_from_body(response.text)
        error_type = extract_error_type(response.text, response.status_code)
        if response.status_code >= 500:
            raise ProviderServerError(
                self._instance_name, response.status_code, response.text,
                error_type=error_type,
                ratelimit_reset=ratelimit_reset,
            )
        raise ProviderClientError(
            self._instance_name, response.status_code, response.text,
            error_type=error_type,
            ratelimit_reset=ratelimit_reset,
        )

    def _check_openai_finish_reason(self, data: dict) -> None:
        """Détecte une sortie tronquée à max_tokens (format OpenAI /chat/completions).

        finish_reason == "length" signifie que la génération a été coupée avant la
        fin → le JSON est incomplet et json.loads échouerait avec un message
        trompeur (Expecting ',' delimiter...). On lève à la place une erreur typée
        max_tokens_truncation, éligible au retry (même pattern que google_adapter
        avec finishReason == MAX_TOKENS).
        """
        choices = data.get("choices") or [{}]
        finish_reason = choices[0].get("finish_reason")
        if finish_reason == "length":
            _base_logger.warning(
                f"Réponse tronquée (finish_reason=length) | provider={self._instance_name} "
                f"completion_tokens={data.get('usage', {}).get('completion_tokens')}"
            )
            raise ProviderServerError(
                self._instance_name, 503,
                "Output truncated at max_tokens limit (finish_reason=length)",
                error_type="max_tokens_truncation",
            )

    def _parse_output(self, raw: str) -> LLMOutput:
        provider = self._instance_name

        # Nettoyage défensif : suppression des balises Markdown (ex: ```json ... ```)
        raw_clean = raw.strip()
        if raw_clean.startswith('```json'):
            raw_clean = raw_clean[7:]
        if raw_clean.startswith('```'):
            raw_clean = raw_clean[3:]
        if raw_clean.endswith('```'):
            raw_clean = raw_clean[:-3]
            
        raw_clean = raw_clean.strip()

        # Utilise un regex pour extraire le dictionnaire principal (ignore le texte parasite autour)
        match = re.search(r'\{.*\}', raw_clean, re.DOTALL)
        if match:
            raw_clean = match.group(0)

        _base_logger.debug(
            f"_parse_output start | provider={provider} raw_len={len(raw_clean)} "
            f"raw_preview={raw_clean[:300]!r}"
        )

        # Guard: detect repetition loops (same token repeated > 15 times consecutively)
        words = raw_clean.split()
        if len(words) > 20:
            max_consecutive = 1
            consecutive = 1
            for i in range(1, len(words)):
                if words[i] == words[i - 1]:
                    consecutive += 1
                    max_consecutive = max(max_consecutive, consecutive)
                else:
                    consecutive = 1
            if max_consecutive > 15:
                raise ProviderParseError(
                    provider, raw,
                    f"Repetition loop detected ({max_consecutive} consecutive identical tokens)"
                )

        # Step 1 — JSON decode (with demjson3 fallback for malformed output)
        try:
            data = json.loads(raw_clean)
        except json.JSONDecodeError as e:
            if _demjson is not None:
                try:
                    data = _demjson.decode(raw_clean)
                    _base_logger.warning(
                        f"_parse_output: json.loads failed, repaired with demjson3 | "
                        f"provider={provider} original_error={e}"
                    )
                except Exception:
                    _base_logger.warning(
                        f"_parse_output FAILED at json.loads and demjson3 | provider={provider} "
                        f"error={e} raw_preview={raw_clean[:500]!r}"
                    )
                    raise ProviderParseError(provider, raw, f"JSONDecodeError: {e}")
            else:
                _base_logger.warning(
                    f"_parse_output FAILED at json.loads | provider={provider} "
                    f"error={e} raw_preview={raw_clean[:500]!r}"
                )
                raise ProviderParseError(provider, raw, f"JSONDecodeError: {e}")

        # Step 2 — extract "agents" list
        agents_raw = None
        if "agents" in data:
            agents_raw = data["agents"]
        else:
            # Fallback : on cherche la première clé qui contient une liste
            for k, v in data.items():
                if isinstance(v, list):
                    agents_raw = v
                    break
                    
        if agents_raw is None:
            _base_logger.warning(
                f"_parse_output FAILED: missing 'agents' key (et aucune liste alternative trouvée) | provider={provider} "
                f"top_level_keys={list(data.keys())} raw_preview={raw[:500]!r}"
            )
            raise ProviderParseError(
                provider, raw,
                f"KeyError: 'agents' absent, clés présentes: {list(data.keys())}"
            )
        if not isinstance(agents_raw, list):
            _base_logger.warning(
                f"_parse_output FAILED: 'agents' is not a list | provider={provider} "
                f"type={type(agents_raw).__name__} value={agents_raw!r}"
            )
            raise ProviderParseError(
                provider, raw,
                f"TypeError: 'agents' est de type {type(agents_raw).__name__}, attendu list"
            )

        # Step 3 — build AgentResponse objects
        agents = []
        for idx, item in enumerate(agents_raw):
            if not isinstance(item, dict):
                _base_logger.warning(
                    f"_parse_output: skipping non-dict item at agents[{idx}] | provider={provider} "
                    f"type={type(item).__name__} value={item!r}"
                )
                continue
            try:
                agents.append(AgentResponse(**item))
            except (TypeError, ValidationError) as e:
                _base_logger.warning(
                    f"_parse_output FAILED at AgentResponse construction | provider={provider} "
                    f"index={idx} item={item!r} error={type(e).__name__}: {e}"
                )
                raise ProviderParseError(
                    provider, raw,
                    f"{type(e).__name__} on agents[{idx}]={item!r}: {e}"
                )

        return LLMOutput(agents=agents)


# ---------------------------------------------------------------------------
# Exceptions spécifiques aux adapters
# ---------------------------------------------------------------------------

class ProviderError(Exception):
    """Base."""
    def __init__(self, provider: str, status_code: int, message: str, error_type: str = "unknown", ratelimit_reset: str | None = None):
        self.provider = provider
        self.status_code = status_code
        self.error_type = error_type
        self.ratelimit_reset = ratelimit_reset
        super().__init__(f"[{provider}] HTTP {status_code}: {message}")


class ProviderServerError(ProviderError):
    """Erreur 5xx — éligible au retry avec backoff exponentiel."""
    pass


class ProviderClientError(ProviderError):
    """Erreur 4xx — ne pas retenter (auth invalide, quota dépassé, etc.)."""
    pass


class ProviderParseError(Exception):
    """La réponse du LLM ne respecte pas le schéma JSON attendu."""

    def __init__(self, provider: str, raw: str, detail: str):
        self.provider = provider
        self.raw = raw
        # Clé de métrique : les 10 premiers mots du détail de parsing
        self.error_type = _truncate_to_words(f"parse error {detail}", 10)
        super().__init__(f"[{provider}] Parse error: {detail}")


# ---------------------------------------------------------------------------
# Extraction du message d'erreur brut depuis le corps de réponse
# ---------------------------------------------------------------------------

def _truncate_to_words(text: str, n: int = 10) -> str:
    """Retourne les n premiers mots de text, en minuscules, sans retours à la ligne."""
    cleaned = " ".join(text.split())          # normalise les espaces / \n
    words = cleaned.lower().split()
    return " ".join(words[:n])


def extract_error_type(response_text: str, status_code: int) -> str:
    """
    Retourne les 10 premiers mots du message d'erreur tel que renvoyé par le provider.

    Ce texte est utilisé directement comme clé de métrique : chaque message unique
    crée automatiquement son propre compteur dans Prometheus, sans catégorie prédéfinie.

    Exemples :
      "request too large for model llama3-8b-8192 in organization"
      "you exceeded your current quota please check your plan"
      "invalid api key provided"
      "http 500"  (si le corps n'est pas du JSON valide)
    """
    try:
        body = json.loads(response_text)
        err = body.get("error", {})

        # Format OpenAI / Groq / Mistral : {"error": {"message": "..."}}
        msg = (err.get("message") or "").strip()

        # Format Google : les détails sont parfois dans error.message aussi
        if not msg:
            msg = (body.get("message") or body.get("error_message") or "").strip()

        if msg:
            return _truncate_to_words(msg, 10)

    except (json.JSONDecodeError, AttributeError, TypeError):
        pass

    # Fallback : code HTTP uniquement
    return f"http {status_code}"


def extract_retry_delay_from_body(response_text: str) -> str | None:
    """Extrait le délai de retry du corps d'une réponse 429.

    Utilisé en repli quand le provider ne renvoie pas le délai dans un header
    (cas Google Gemini, qui le place dans le JSON). Cherche, dans l'ordre :
      1. Le champ structuré google.rpc.RetryInfo : error.details[].retryDelay
      2. Le texte du message : "Please retry in 11.103190523s." (Gemini) ou
         "Please try again in 16m7.68s" / "in 140ms" (Groq)

    Retourne la chaîne de durée telle quelle (ex: "16m7.68s", parsable par
    _parse_ratelimit_reset_seconds), ou None si rien n'est trouvé.
    """
    if not response_text:
        return None

    # 1. Champ structuré google.rpc.RetryInfo
    try:
        data = json.loads(response_text)
        for detail in data.get("error", {}).get("details", []):
            retry_delay = detail.get("retryDelay")
            if retry_delay:
                return str(retry_delay)  # ex: "11s"
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass

    # 2. Repli sur le texte du message — couvre "retry in" (Gemini) et
    #    "try again in" (Groq), formats composés h/m/s/ms inclus.
    m = re.search(r"(?:re)?try(?: again)? in ((?:\d+(?:\.\d+)?(?:h|ms|m|s))+)", response_text)
    if m:
        return m.group(1)

    return None


# ---------------------------------------------------------------------------
# Registre des adapters (auto-découverte par nom de fournisseur)
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type[BaseAdapter]] = {}

# Instances mises en cache par nom de provider : le client httpx partagé
# (keep-alive) survit d'un appel à l'autre au lieu d'être recréé à chaque batch.
_INSTANCES: dict[str, BaseAdapter] = {}
_INSTANCES_LOCK = threading.Lock()


def register_adapter(cls: type[BaseAdapter]) -> type[BaseAdapter]:
    """Décorateur d'enregistrement — utilisé dans chaque adapter concret."""
    _REGISTRY[cls.provider_name] = cls
    return cls


def get_adapter(provider_name: str) -> BaseAdapter:
    """
    Retourne l'adapter (mis en cache) correspondant au fournisseur.

    Pour les providers multi-instances (ex: groq_1, groq_2), résout la classe
    via le champ `adapter` de ProviderConfig, puis attache l'instance name
    pour que _resolve_model/_get_api_key lisent la bonne config.

    Raises:
        KeyError si le fournisseur n'est pas enregistré.
    """
    inst = _INSTANCES.get(provider_name)
    if inst is not None:
        return inst

    # Résolution de la classe : champ `adapter` ou nom du provider directement
    cfg = get_settings().providers.get(provider_name)
    adapter_key = (cfg.adapter or provider_name) if cfg else provider_name

    if adapter_key not in _REGISTRY:
        _load_adapters()

    if adapter_key not in _REGISTRY:
        raise KeyError(
            f"Adapter inconnu pour le fournisseur '{provider_name}' (adapter='{adapter_key}'). "
            f"Adapters disponibles : {list(_REGISTRY.keys())}"
        )

    with _INSTANCES_LOCK:
        inst = _INSTANCES.get(provider_name)
        if inst is None:
            inst = _REGISTRY[adapter_key]()
            inst._instance_name = provider_name  # pointe vers la bonne entrée dans settings.providers
            _INSTANCES[provider_name] = inst
    return inst


def close_all_adapters() -> None:
    """Ferme les clients httpx partagés de toutes les instances (arrêt du worker)."""
    with _INSTANCES_LOCK:
        for inst in _INSTANCES.values():
            inst.close()
        _INSTANCES.clear()


def _load_adapters() -> None:
    """Tente de charger chaque adapter connu. Les imports manquants sont loggés, pas levés."""
    from llm_module.telemetry.logger import get_logger
    _logger = get_logger(__name__)

    _known_adapters = {
        "openai":   "llm_module.adapters.openai_adapter",
        "google":   "llm_module.adapters.google_adapter",
        "mistral":  "llm_module.adapters.mistral_adapter",
        "groq":     "llm_module.adapters.groq_adapter",
        "cerebras": "llm_module.adapters.cerebras_adapter",
    }

    for name, module_path in _known_adapters.items():
        try:
            import importlib
            importlib.import_module(module_path)
        except ImportError as e:
            _logger.warning(f"Adapter non disponible (module manquant) | provider={name} reason={e}")
