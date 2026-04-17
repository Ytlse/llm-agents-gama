from __future__ import annotations
from typing import Dict, Optional
from pydantic import BaseModel, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from llm_module.telemetry.logger import get_logger

logger = get_logger(__name__)


_PROVIDER_DEFAULTS: Dict[str, dict] = {
    "openai": {
        "rpm_limit":        15,
        "base_url":         "https://api.openai.com/v1",
        "default_model":    "gpt-4o-mini",
        "weight":           1.0,
        "batch_max_agents": 10,
    },
    "mistral": {
        "rpm_limit":        100,
        "base_url":         "https://api.mistral.ai/v1",
        "default_model":    "mistral-small-latest",
        "weight":           2.0,
        "batch_max_agents": 10,
    },
    "google": {
        "rpm_limit":        15,
        "base_url":         "https://generativelanguage.googleapis.com/v1beta",
        "default_model":    "gemini-3.1-flash-lite-preview",
        "weight":           1.0,
        "batch_max_agents": 15,
    },
    "groq": {
        "rpm_limit":        30,
        "base_url":         "https://api.groq.com/openai/v1",
        "default_model":    "openai/gpt-oss-120b",
        "weight":           1.0,
        "batch_max_agents": 2,
    },
}


class ProviderConfig(BaseModel):
    api_key:          SecretStr = SecretStr("")
    rpm_limit:        int
    base_url:         str
    default_model:    str
    weight:           float = 1.0
    batch_max_agents: int   = 5

    def __repr__(self) -> str:
        return (
            f"ProviderConfig(rpm_limit={self.rpm_limit}, model='{self.default_model}', "
            f"base_url='{self.base_url}', weight={self.weight}, "
            f"api_key_length={len(self.api_key.get_secret_value())})"
        )


class Settings(BaseSettings):

    redis_url:                  str   = "redis://localhost:6379/0"
    celery_broker_url:          str   = "redis://localhost:6379/1"
    celery_result_backend:      str   = "redis://localhost:6379/2"
    circuit_breaker_threshold:  float = 0.95
    max_retries:                int   = 10
    backoff_base_seconds:       float = 1.0
    batch_max_agents:           int   = 5
    batch_delay_seconds:        float = 1.0

    # Les api_key viennent de l'env : PROVIDER_KEYS__openai=sk-...
    provider_keys: Dict[str, SecretStr] = {}

    # Construit après validation — pas lu depuis l'env
    providers: Dict[str, ProviderConfig] = {}

    @model_validator(mode="after")
    def build_providers(self) -> "Settings":
        result = {}
        for name, defaults in _PROVIDER_DEFAULTS.items():
            key = self.provider_keys.get(name, SecretStr(""))
            result[name] = ProviderConfig(api_key=key, **defaults)
        self.providers = result
        return self


def get_batch_max_agents(force_provider: Optional[str] = None) -> int:
    """
    Retourne la limite de batch liée à la capacité du provider.
    - Provider forcé : limite exacte de ce provider.
    - Provider dynamique : minimum des providers disponibles (approche conservative,
      car on ne connaît pas encore le provider qui sera sélectionné).
    - Aucun provider configuré : fallback sur settings.batch_max_agents.
    """
    if force_provider:
        provider_cfg = settings.providers.get(force_provider)
        if provider_cfg:
            return provider_cfg.batch_max_agents

    if settings.providers:
        return min(p.batch_max_agents for p in settings.providers.values())

    return settings.batch_max_agents


def filter_providers_without_api_key(settings: Settings) -> Dict[str, ProviderConfig]:
    valid = {}
    for name, provider in settings.providers.items():
        if provider.api_key.get_secret_value():
            valid[name] = provider
            logger.info(f"Fournisseur '{name}' inclus : {provider}")
        else:
            logger.warning(f"Fournisseur '{name}' exclu : clé API manquante.")
    return valid


settings = Settings()
settings.providers = filter_providers_without_api_key(settings)
