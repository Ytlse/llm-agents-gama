from __future__ import annotations
from pathlib import Path
from typing import Dict, Optional
import yaml
from pydantic import BaseModel, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from llm_module.telemetry.logger import get_logger

logger = get_logger(__name__)

_PROVIDERS_YAML = Path(__file__).parent.parent / "config" / "providers.yaml"


def _load_provider_defaults() -> Dict[str, dict]:
    """Charge la liste des providers depuis providers.yaml."""
    with open(_PROVIDERS_YAML, "r") as f:
        data = yaml.safe_load(f)
    return data.get("providers", {})


class ProviderConfig(BaseModel):
    api_key:           SecretStr = SecretStr("")
    rpm_limit:         int
    base_url:          str
    default_model:     str
    weight:            float = 1.0
    batch_max_agents:  int   = 5
    concurrency_limit: int   = 2   # nb workers Celery simultanés autorisés pour ce provider
    disable_timeout:   int   = 180  # secondes de désactivation automatique après N erreurs consécutives
    adapter:           str   = ""   # nom de la classe d'adapter ; vide = utiliser le nom du provider

    def __repr__(self) -> str:
        return (
            f"ProviderConfig(rpm_limit={self.rpm_limit}, model='{self.default_model}', "
            f"base_url='{self.base_url}', weight={self.weight}, "
            f"api_key_length={len(self.api_key.get_secret_value())})"
        )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter='__')

    redis_url:                  str   = "redis://localhost:6379/0"
    celery_broker_url:          str   = "redis://localhost:6379/1"
    celery_result_backend:      str   = "redis://localhost:6379/2"
    circuit_breaker_threshold:  float = 0.95
    max_retries:                int   = 10
    backoff_base_seconds:       float = 1.0
    batch_max_agents:           int   = 5
    batch_delay_seconds:        float = 1.0

    # Les api_key viennent de l'env : PROVIDER_KEYS__groq=gsk-...
    provider_keys: Dict[str, SecretStr] = {}

    # Construit après validation — pas lu depuis l'env
    providers: Dict[str, ProviderConfig] = {}

    @model_validator(mode="after")
    def build_providers(self) -> "Settings":
        defaults = _load_provider_defaults()
        result = {}
        for name, entry in defaults.items():
            # L'api_key est lue via le nom de l'instance ou du provider de base (champ adapter)
            adapter_name = entry.get("adapter", name)
            key = self.provider_keys.get(name) or self.provider_keys.get(adapter_name, SecretStr(""))
            result[name] = ProviderConfig(api_key=key, **entry)
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
