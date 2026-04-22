"""
adapters/base.py — Interface commune (Adapter Pattern).

Tous les adapters fournisseur implémentent cette classe abstraite.
Le Worker ne connaît que BaseAdapter — il reste découplé des SDKs tiers.
"""

from __future__ import annotations
import json
import re
from abc import ABC, abstractmethod
from typing import Tuple

from pydantic import ValidationError

from llm_module.settings.models import AgentResponse, InternalRequest, LLMOutput
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

    def __init__(self):
        # Par défaut, l'instance name = le nom de la classe d'adapter.
        # get_adapter() le remplace par le nom de l'instance configurée (ex: "groq_1").
        self._instance_name: str = self.provider_name

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
        from llm_module.tasks.config import settings
        if request.model:
            return request.model
        return settings.providers[self._instance_name].default_model

    def _get_api_key(self) -> str:
        from llm_module.tasks.config import settings
        return settings.providers[self._instance_name].api_key

    def _get_base_url(self) -> str:
        from llm_module.tasks.config import settings
        return settings.providers[self._instance_name].base_url

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

        # Step 1 — JSON decode
        try:
            data = json.loads(raw_clean)
        except json.JSONDecodeError as e:
            _base_logger.warning(
                f"_parse_output FAILED at json.loads | provider={provider} "
                f"error={e} raw_preview={raw_clean[:500]!r}"
            )
            raise ProviderParseError(provider, raw, f"JSONDecodeError: {e}")

        # Step 2 — extract "agents" list
        if "agents" not in data:
            _base_logger.warning(
                f"_parse_output FAILED: missing 'agents' key | provider={provider} "
                f"top_level_keys={list(data.keys())} raw_preview={raw[:500]!r}"
            )
            raise ProviderParseError(
                provider, raw,
                f"KeyError: 'agents' absent, clés présentes: {list(data.keys())}"
            )
        agents_raw = data["agents"]
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
    def __init__(self, provider: str, status_code: int, message: str, error_type: str = "unknown"):
        self.provider = provider
        self.status_code = status_code
        self.error_type = error_type
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


# ---------------------------------------------------------------------------
# Registre des adapters (auto-découverte par nom de fournisseur)
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type[BaseAdapter]] = {}


def register_adapter(cls: type[BaseAdapter]) -> type[BaseAdapter]:
    """Décorateur d'enregistrement — utilisé dans chaque adapter concret."""
    _REGISTRY[cls.provider_name] = cls
    return cls


def get_adapter(provider_name: str) -> BaseAdapter:
    """
    Instancie et retourne l'adapter correspondant au fournisseur.

    Pour les providers multi-instances (ex: groq_1, groq_2), résout la classe
    via le champ `adapter` de ProviderConfig, puis attache l'instance name
    pour que _resolve_model/_get_api_key lisent la bonne config.

    Raises:
        KeyError si le fournisseur n'est pas enregistré.
    """
    from llm_module.tasks.config import settings

    # Résolution de la classe : champ `adapter` ou nom du provider directement
    cfg = settings.providers.get(provider_name)
    adapter_key = (cfg.adapter or provider_name) if cfg else provider_name

    if adapter_key not in _REGISTRY:
        _load_adapters()

    if adapter_key not in _REGISTRY:
        raise KeyError(
            f"Adapter inconnu pour le fournisseur '{provider_name}' (adapter='{adapter_key}'). "
            f"Adapters disponibles : {list(_REGISTRY.keys())}"
        )

    inst = _REGISTRY[adapter_key]()
    inst._instance_name = provider_name  # pointe vers la bonne entrée dans settings.providers
    return inst


def _load_adapters() -> None:
    """Tente de charger chaque adapter connu. Les imports manquants sont loggés, pas levés."""
    from llm_module.telemetry.logger import get_logger
    _logger = get_logger(__name__)

    _known_adapters = {
        "openai":   "llm_module.adapters.openai_adapter",
        "google":   "llm_module.adapters.google_adapter",
        "mistral":  "llm_module.adapters.mistral_adapter",
        "groq":     "llm_module.adapters.groq_adapter",
    }

    for name, module_path in _known_adapters.items():
        try:
            import importlib
            importlib.import_module(module_path)
        except ImportError as e:
            _logger.warning(f"Adapter non disponible (module manquant) | provider={name} reason={e}")
