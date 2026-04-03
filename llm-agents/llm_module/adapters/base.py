"""
adapters/base.py — Interface commune (Adapter Pattern).

Tous les adapters fournisseur implémentent cette classe abstraite.
Le Worker ne connaît que BaseAdapter — il reste découplé des SDKs tiers.
"""

from __future__ import annotations
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
        from llm_module.config import settings
        if request.model:
            return request.model
        return settings.providers[self.provider_name].default_model

    def _get_api_key(self) -> str:
        from llm_module.config import settings
        return settings.providers[self.provider_name].api_key


# ---------------------------------------------------------------------------
# Exceptions spécifiques aux adapters
# ---------------------------------------------------------------------------

class ProviderError(Exception):
    """Base."""
    def __init__(self, provider: str, status_code: int, message: str):
        self.provider = provider
        self.status_code = status_code
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
        super().__init__(f"[{provider}] Parse error: {detail}")


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
        # Charger tous les adapters connus (import tardif pour éviter les circulaires)
        from llm_module.adapters import openai_adapter, google_adapter, mistral_adapter  # noqa
    cls = _REGISTRY[provider_name]
    return cls()
