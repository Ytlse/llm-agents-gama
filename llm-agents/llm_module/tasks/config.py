"""
config.py — Configuration centralisée via pydantic-settings.
Toutes les valeurs sensibles (clés API) viennent de variables d'environnement
ou d'un fichier .env à la racine.
"""

from __future__ import annotations
from typing import Dict
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderConfig(BaseModel):
    """Paramètres d'un fournisseur LLM."""
    api_key: str
    rpm_limit: int       # Requêtes par minute autorisées
    base_url: str
    default_model: str
    weight: float = 1.0  # Poids pour le Weighted Round-Robin (normalisé en runtime)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_nested_delimiter="__")

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Seuil circuit-breaker (% du quota RPM avant exclusion temporaire)
    circuit_breaker_threshold: float = 0.95

    # Retry backoff
    max_retries: int = 4
    backoff_base_seconds: float = 1.0

    # Fournisseurs (clés via env : PROVIDERS__openai__api_key=sk-...)
    providers: Dict[str, ProviderConfig] = {
        "openai": ProviderConfig(
            api_key="",
            rpm_limit=60,
            base_url="https://api.openai.com/v1",
            default_model="gpt-4o-mini",
            weight=1.0,
        ),
        "mistral": ProviderConfig(
            api_key="",
            rpm_limit=100,
            base_url="https://api.mistral.ai/v1",
            default_model="mistral-small-latest",
            weight=2.0,  # Plus de quota → plus de poids
        ),
        "google": ProviderConfig(
            api_key="",
            rpm_limit=50,
            base_url="https://generativelanguage.googleapis.com/v1beta",
            default_model="gemini-1.5-flash",
            weight=1.0,
        ),
    }


# Instance singleton importée partout
settings = Settings()
