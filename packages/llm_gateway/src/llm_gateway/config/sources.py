"""config/sources.py — d'où viennent les réglages, et dans quel ordre.

De la plus forte à la plus faible : arguments du constructeur, environnement préfixé
`LLM_GATEWAY_`, anciens noms non préfixés (une version, avec avertissement), fichier YAML désigné
par `LLM_GATEWAY_CONFIG`, profil désigné par `LLM_GATEWAY_PROFILE`, défauts du code.

`PROVIDER_KEYS__<nom>` reste un nom **canonique** pour les clés d'API (il est partagé avec
`make providers`, le compose et prompt_calibration) : accepté sans avertissement, au même titre
que `LLM_GATEWAY_PROVIDER_KEYS__<nom>`.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, YamlConfigSettingsSource

from llm_gateway.telemetry.logger import get_logger

logger = get_logger(__name__)

ENV_PREFIX = "LLM_GATEWAY_"
CONFIG_FILE_ENV = "LLM_GATEWAY_CONFIG"
PROFILE_ENV = "LLM_GATEWAY_PROFILE"
PROVIDER_KEYS_LEGACY_PREFIX = "PROVIDER_KEYS__"
PROFILES_DIR = Path(__file__).resolve().parent / "profiles"

# Ancien nom → chemin dans GatewaySettings. Lus pendant une version, puis retirés.
LEGACY_ENV: dict[str, tuple[str, ...]] = {
    "REDIS_URL": ("redis", "url"),
    "CELERY_BROKER_URL": ("executor", "celery_broker_url"),
    "CELERY_RESULT_BACKEND": ("executor", "celery_result_backend"),
    "LOG_LEVEL": ("telemetry", "log_level"),
    "SERVICE_NAME": ("telemetry", "service_name"),
    "APP_WORKDIR": ("telemetry", "workdir"),
    "LLM_EXCHANGES_FILE": ("telemetry", "exchanges_file"),
    "MAX_RETRIES": ("resilience", "max_retries"),
    "BACKOFF_BASE_SECONDS": ("resilience", "backoff_base_seconds"),
    "PROVIDER_SWITCH_COOLDOWN_SECONDS": ("resilience", "provider_switch_cooldown_seconds"),
    "BATCH_MAX_AGENTS": ("batching", "max_agents"),
    "BATCH_DELAY_SECONDS": ("batching", "delay_seconds"),
    "BATCH_TARGET_AGENTS": ("batching", "target_agents"),
    "ASSUMED_PROMPT_TOKENS": ("batching", "assumed_prompt_tokens"),
    "ASSUMED_OUTPUT_TOKENS": ("batching", "assumed_output_tokens"),
    "TOKEN_CHARS_RATIO": ("batching", "token_chars_ratio"),
    "MAX_BATCH_AGENTS": ("batching", "max_batch_agents"),
    "MIN_OUTPUT_TOKENS": ("batching", "min_output_tokens"),
    "MAX_OUTPUT_TOKENS": ("batching", "max_output_tokens"),
}


def new_env_name(path: tuple[str, ...]) -> str:
    return ENV_PREFIX + "__".join(p.upper() for p in path)


def _env_has(name: str) -> bool:
    upper = name.upper()
    return any(k.upper() == upper for k in os.environ)


def _set_path(target: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    node = target
    for part in path[:-1]:
        node = node.setdefault(part, {})
    node[path[-1]] = value


class LegacyEnvSource(PydanticBaseSettingsSource):
    """Anciens noms de variables : lus si le nouveau nom est absent, avec un avertissement chacun."""

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:  # pragma: no cover
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for old, path in LEGACY_ENV.items():
            value = os.environ.get(old)
            if value is None or _env_has(new_env_name(path)):
                continue
            _set_path(out, path, value)
            logger.warning(
                f"Variable d'environnement dépréciée {old} : utilisez {new_env_name(path)} "
                f"(les anciens noms disparaîtront à la version majeure suivante)."
            )
        # Clés d'API : alias canonique, sans avertissement.
        for name, value in os.environ.items():
            if not name.upper().startswith(PROVIDER_KEYS_LEGACY_PREFIX):
                continue
            provider = name[len(PROVIDER_KEYS_LEGACY_PREFIX):].lower()
            if not provider or _env_has(f"{ENV_PREFIX}PROVIDER_KEYS__{provider}"):
                continue
            out.setdefault("provider_keys", {})[provider] = value
        return out


def available_profiles() -> list[str]:
    return sorted(p.stem for p in PROFILES_DIR.glob("*.yaml"))


def yaml_sources(settings_cls: type[BaseSettings]) -> list[PydanticBaseSettingsSource]:
    """Fichier de configuration puis profil, dans cet ordre de priorité."""
    sources: list[PydanticBaseSettingsSource] = []
    config_path = os.environ.get(CONFIG_FILE_ENV)
    if config_path:
        path = Path(config_path)
        if not path.is_file():
            raise FileNotFoundError(f"{CONFIG_FILE_ENV}={config_path} : fichier introuvable")
        sources.append(YamlConfigSettingsSource(settings_cls, yaml_file=path))
    profile = os.environ.get(PROFILE_ENV)
    if profile:
        path = PROFILES_DIR / f"{profile}.yaml"
        if not path.is_file():
            raise FileNotFoundError(
                f"{PROFILE_ENV}={profile!r} : profil inconnu. Disponibles : {available_profiles()}"
            )
        sources.append(YamlConfigSettingsSource(settings_cls, yaml_file=path))
    return sources


__all__ = [
    "CONFIG_FILE_ENV",
    "ENV_PREFIX",
    "LEGACY_ENV",
    "PROFILE_ENV",
    "PROFILES_DIR",
    "LegacyEnvSource",
    "available_profiles",
    "new_env_name",
    "yaml_sources",
]
