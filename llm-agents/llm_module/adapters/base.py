"""
adapters/base.py — Interface commune (Adapter Pattern).

Tous les adapters fournisseur implémentent cette classe abstraite.
Le Worker ne connaît que BaseAdapter — il reste découplé des SDKs tiers.
"""

from __future__ import annotations
import json
from abc import ABC, abstractmethod
from typing import Tuple

from llm_module.settings.models import InternalRequest, LLMOutput


class BaseAdapter(ABC):
    """
    Contrat que chaque traducteur fournisseur doit respecter.

    Méthode principale : call()
      - Prend un InternalRequest (format normalisé interne)
      - Retourne (LLMOutput, tokens_in, tokens_out)
      - Lève une exception en cas d'erreur récupérable (5xx) ou fatale (4xx)
    """

    provider_name: str  # Doit être défini dans chaque sous-classe

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

    def _resolve_model(self, request: InternalRequest) -> str:
        """Retourne le modèle spécifié ou le défaut du provider."""
        from llm_module.tasks.config import settings
        if request.model:
            return request.model
        return settings.providers[self.provider_name].default_model

    def _get_api_key(self) -> str:
        from llm_module.tasks.config import settings
        return settings.providers[self.provider_name].api_key


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

    Raises:
        KeyError si le fournisseur n'est pas enregistré.
    """
    if provider_name not in _REGISTRY:
        # Chargement tardif des adapters connus pour éviter les imports circulaires.
        # Chaque import est protégé individuellement : un adapter manquant (ex: groq)
        # ne bloque pas les autres.
        _load_adapters()

    if provider_name not in _REGISTRY:
        raise KeyError(
            f"Adapter inconnu pour le fournisseur '{provider_name}'. "
            f"Adapters disponibles : {list(_REGISTRY.keys())}"
        )

    cls = _REGISTRY[provider_name]
    return cls()


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
