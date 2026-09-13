"""
config/settings.py — les réglages du gateway, en couches et groupés.

La configuration n'est JAMAIS construite comme effet de bord d'un import : les points d'entrée
(create_app, worker Celery, CLI, tests) appellent explicitement `GatewaySettings()` ou
`get_settings()`. Construire les réglages lit l'environnement et le fichier des fournisseurs ;
aucun accès Redis ni réseau.

Sources, de la plus forte à la plus faible (cf. `config/sources.py`) : arguments du
constructeur, environnement `LLM_GATEWAY_*` (`__` sépare les niveaux :
`LLM_GATEWAY_BATCHING__DELAY_SECONDS`), anciens noms non préfixés (dépréciés), fichier YAML
`LLM_GATEWAY_CONFIG`, profil `LLM_GATEWAY_PROFILE`, défauts ci-dessous.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from llm_gateway.config.providers import (
    DEFAULT_EXAMPLE_FILE,
    InferenceOverrides,
    ProviderEntry,
    ProvidersFile,
    load_providers_file,
)
from llm_gateway.core.quota import DEFAUT_FUSEAU_QUOTA
from llm_gateway.config.sources import ENV_PREFIX, LegacyEnvSource, yaml_sources
from llm_gateway.telemetry.logger import get_logger

logger = get_logger(__name__)

# Instances nommées <modèle>_key<N> : leur clé est nominative (pas de repli adapter).
_INSTANCE_KEY_SUFFIX = re.compile(r"_key\d+$")


# ---------------------------------------------------------------------------
# Un fournisseur résolu : l'entrée du fichier + la clé + les valeurs calculées
# ---------------------------------------------------------------------------

class ProviderConfig(BaseModel):
    """Configuration effective d'une instance de fournisseur, telle que le gateway l'utilise."""

    model_config = ConfigDict(extra="forbid")

    api_key: SecretStr = SecretStr("")
    rpm_limit: int
    tpm_limit: int | None = None
    rpd_limit: int | None = None
    tpd_limit: int | None = None
    quota_reset_tz: str = DEFAUT_FUSEAU_QUOTA   # fuseau du reset journalier (cf. core.quota)
    max_tokens_per_request: int | None = None
    max_output_tokens: int | None = None
    # Plafond de réflexion du modèle servi (cf. `ProviderEntry.thinking_budget_max` pour le
    # pourquoi). Lu par l'adapter Google, qui refuse un budget au-dessus.
    thinking_budget_max: int | None = None
    # Niveaux de réflexion acceptés par le modèle servi (`minimal`, `low`, `medium`, `high`).
    # Relevés dans la documentation du fournisseur : ils varient d'un modèle à l'autre, et
    # demander un niveau absent rend 400. Déclarés → le formulaire n'offre que ceux-là et un
    # niveau inconnu est refusé d'avance ; absents → aucun niveau n'est proposé.
    thinking_levels: list[str] | None = None
    base_url: str
    default_model: str
    weight: float = 1.0
    batch_max_agents: int = 1            # calculé : min(tpm/tokens_par_agent, capacité requête, rpm, plafond)
    tpm_estimate_per_request: int | None = None  # calculé : réservation TPM d'une requête pleine
    concurrency_limit: int = 2
    # Réglage d'APPELANT, recopié tel quel du fichier des fournisseurs : le gateway ne le lit
    # pas, il le publie pour que le client sache combien de temps attendre une tâche servie
    # par cette instance (cf. `sdk.client.execute(wait_timeout=…)`).
    wait_timeout: float | None = None
    disable_timeout: int = 180
    adapter: str = ""
    structured_output: Literal["json_schema", "json_object", "none"] | None = None
    schema_in_system: bool | None = None
    inference: InferenceOverrides | None = None

    def __repr__(self) -> str:
        return (
            f"ProviderConfig(rpm_limit={self.rpm_limit}, model='{self.default_model}', "
            f"base_url='{self.base_url}', weight={self.weight}, "
            f"api_key_length={len(self.api_key.get_secret_value())})"
        )


# ---------------------------------------------------------------------------
# Les groupes de réglages
# ---------------------------------------------------------------------------

class RedisSettings(BaseModel):
    url: str = "redis://localhost:6379/0"


class ExecutorSettings(BaseModel):
    kind: Literal["celery"] = "celery"   # « inprocess » viendra avec le port d'exécution
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"


class InferenceSettings(BaseModel):
    """Défauts globaux d'inférence ; surchargés par provider (`inference:` du fichier) puis par requête."""

    temperature: float = 0.7
    top_p: float | None = None
    max_tokens: int = 4096   # budget de sortie PAR TÂCHE ; le lot multiplie par son nombre d'agents
    # Profondeur de réflexion par défaut. `None` : rien n'est demandé, chaque fournisseur
    # applique la sienne — c'est le comportement qui prévalait avant le 2026-09-10, conservé
    # comme défaut pour ne pas déplacer toutes les mesures existantes d'un coup.
    thinking_budget: int | None = None
    # Niveau de réflexion par défaut. `None` : rien n'est envoyé, le modèle applique le sien
    # (`high` pour Flash et Pro, `minimal` pour Flash-Lite d'après la doc du 2026-09-10).
    thinking_level: str | None = None


class BatchingSettings(BaseModel):
    """Micro-batching. Les valeurs sont celles mesurées sur les runs de juillet 2026 : à recalibrer
    sur d'autres prompts ou d'autres fournisseurs (cf. guide des quotas)."""

    max_agents: int = 5           # repli si aucun provider n'est configuré
    # Fenêtre d'accumulation : une requête sous le seuil attend ce délai pour être fusionnée.
    # Calée sur l'inter-arrivée mesurée des prompts (run 2026-07-10 : p50 = 1,4 s).
    delay_seconds: float = 3.0
    # Taille de file déclenchant un dispatch immédiat (cf. get_dispatch_threshold).
    target_agents: int = 10
    assumed_prompt_tokens: int = 2200   # tokens_in max par agent (historique +10 % de marge)
    assumed_output_tokens: int = 800    # tokens_out estimés par agent (réservation TPM glissante)
    # tokens ≈ caractères / ratio ; mesuré p50 = 3,24, p10 = 3,05 sur prompts FR + JSON.
    token_chars_ratio: float = 3.0
    max_batch_agents: int = 20          # plafond absolu du calcul de batch_max_agents
    min_output_tokens: int = 512        # budget de sortie minimal acceptable par requête
    max_output_tokens: int = 16384      # plafond du max_tokens envoyé (limite gpt-4o-mini)


class RoutingSettings(BaseModel):
    """Comment le balancer répartit les requêtes entre fournisseurs.

    `swrr` étale la charge sur tous les fournisseurs en rotation (débit maximal).
    `cascade` les épuise dans l'ordre : le premier tant qu'il accepte, le suivant seulement
    quand il refuse — quota du jour atteint, cooldown, ou débit par minute saturé. C'est ce
    qu'on veut quand deux clés servent le même modèle et qu'on préfère consommer la première
    en entier avant de toucher à la seconde (demande du 2026-09-07).
    """

    policy: Literal["swrr", "cascade"] = "swrr"


class ResilienceSettings(BaseModel):
    max_retries: int = 50
    backoff_base_seconds: float = 1.0
    # Cooldown court du provider fautif lors d'une bascule (parse error, 4xx non récupérable).
    provider_switch_cooldown_seconds: int = 30
    # Au-delà, le provider est désactivé pour `disable_timeout` secondes.
    disable_after_consecutive_errors: int = 30
    # Saturation : un lot attend `provider_wait_seconds` un créneau (sondé toutes les
    # `saturation_poll_seconds`), puis `saturation_retries` réessais espacés de
    # `saturation_retry_seconds`. Ensuite, si les fournisseurs éligibles sont seulement
    # OCCUPÉS (fenêtre RPM/TPM pleine, lissage, concurrence), le lot continue d'attendre jusqu'à
    # `max_retries` ; il n'est abandonné que s'ils sont réellement indisponibles (cooldown,
    # désactivation, quota du jour) ou si `abandon_when_busy` est vrai.
    provider_wait_seconds: float = 8.0
    saturation_poll_seconds: float = 2.0
    saturation_retries: int = 2
    saturation_retry_seconds: float = 12.0
    abandon_when_busy: bool = False


class ApiSettings(BaseModel):
    cors_origins: list[str] = Field(default_factory=list)   # vide = pas de middleware CORS
    max_request_bytes: int = 2_000_000
    auth_tokens: list[SecretStr] = Field(default_factory=list)   # ticket 036 : non appliqué encore


class TelemetrySettings(BaseModel):
    log_level: str = "INFO"
    log_format: Literal["text", "json"] = "text"
    service_name: str | None = None      # ajoute un sink fichier <workdir>/<service>.log
    workdir: Path = Path(".")
    # Journal des échanges (prompts et réponses complets : données personnelles potentielles).
    # DÉSACTIVÉ par défaut ; la simulation l'active dans son compose.
    exchanges_enabled: bool = False
    exchanges_file: Path | None = None    # défaut : <workdir>/llm_exchanges.jsonl
    exchanges_max_bytes: int = 200_000_000  # rotation en .1 au-delà ; 0 = jamais
    redactor: str | None = None           # chemin pointé d'un rédacteur (telemetry.exchanges)


# ---------------------------------------------------------------------------
# Les réglages du gateway
# ---------------------------------------------------------------------------

class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX, env_nested_delimiter="__", extra="ignore", case_sensitive=False,
    )

    redis: RedisSettings = Field(default_factory=RedisSettings)
    executor: ExecutorSettings = Field(default_factory=ExecutorSettings)
    inference: InferenceSettings = Field(default_factory=InferenceSettings)
    batching: BatchingSettings = Field(default_factory=BatchingSettings)
    resilience: ResilienceSettings = Field(default_factory=ResilienceSettings)
    routing: RoutingSettings = Field(default_factory=RoutingSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)
    telemetry: TelemetrySettings = Field(default_factory=TelemetrySettings)

    # Fichier des fournisseurs (configuration de déploiement). None = exemple livré + avertissement.
    providers_file: Path | None = None
    # Où vivent les limites apprises (max_output_tokens révélés par HTTP 400).
    learned_limits: Literal["redis", "file", "none"] = "redis"
    learned_limits_file: Path | None = None   # défaut : <telemetry.workdir>/learned_limits.json

    # Clés d'API : LLM_GATEWAY_PROVIDER_KEYS__<nom> ou PROVIDER_KEYS__<nom>.
    provider_keys: dict[str, SecretStr] = Field(default_factory=dict)

    # Construits après validation — pas lus depuis l'environnement.
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    declared_providers: list[str] = Field(default_factory=list)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings, env_settings, LegacyEnvSource(settings_cls), *yaml_sources(settings_cls))

    # ── Construction des fournisseurs ────────────────────────────────────────

    def resolved_providers_file(self) -> Path:
        return Path(self.providers_file) if self.providers_file else DEFAULT_EXAMPLE_FILE

    @model_validator(mode="after")
    def build_providers(self) -> GatewaySettings:
        if self.providers:   # déjà construits (copie, tests) : ne pas relire le fichier
            return self
        path = self.resolved_providers_file()
        if self.providers_file is None:
            logger.warning(
                f"Aucun fichier des fournisseurs désigné ({ENV_PREFIX}PROVIDERS_FILE) : exemple livré "
                f"chargé ({path.name}). Sans clé d'API, aucun fournisseur ne sera actif."
            )
        declared = load_providers_file(path)
        self.declared_providers = sorted(declared.providers)
        self.providers = {
            name: self._resolve(name, entry) for name, entry in declared.providers.items()
        }
        return self

    def _resolve_key(self, name: str, adapter_name: str) -> SecretStr:
        """Clé d'API d'une instance : PROVIDER_KEYS__<instance>, sinon celle de l'adapter.

        Le repli sur l'adapter est REFUSÉ pour une instance suffixée `_key<N>` : son nom
        annonce une clé nominative, et replier ferait taper la clé d'un autre projet sans
        rien dire — c'est l'incident `google2_36`, où la convention de nommage a fait
        partir les appels sur la mauvaise clé. Sans clé propre, l'instance ressort avec
        une clé vide et `filter_providers_without_api_key` l'écarte de la rotation.

        Une variable présente mais VIDE (`PROVIDER_KEYS__x=""`, cf. `make run NO_GOOGLE=1`)
        est un blanchiment volontaire : pas de repli, pas d'alarme.
        """
        propre = self.provider_keys.get(name)
        if propre is not None:
            return propre
        if _INSTANCE_KEY_SUFFIX.search(name):
            if self.provider_keys.get(adapter_name):
                # Config incohérente : avant la garde, cette instance fonctionnait « par
                # accident » sur la clé de l'adapter. Elle est désormais écartée — le dire
                # fort, sinon la disparition d'une instance ne se lit nulle part.
                logger.error(
                    f"[ALARME] Instance '{name}' sans PROVIDER_KEYS__{name}, alors que la clé de "
                    f"l'adapter '{adapter_name}' existe : instance EXCLUE, aucun repli (le nom "
                    f"annonce une clé nominative). Déclarez PROVIDER_KEYS__{name} pour la servir."
                )
            else:
                logger.warning(
                    f"Instance '{name}' sans PROVIDER_KEYS__{name} : exclue de la rotation."
                )
            return SecretStr("")
        return self.provider_keys.get(adapter_name, SecretStr(""))

    def _resolve(self, name: str, entry: ProviderEntry) -> ProviderConfig:
        b = self.batching
        adapter_name = entry.adapter or name
        key = self._resolve_key(name, adapter_name)
        # Coût tokens (in+out) d'un agent dans un lot — dimensionne batch_max_agents.
        tokens_per_agent = b.assumed_prompt_tokens + b.assumed_output_tokens
        tpm_bound = int(entry.tpm_limit / tokens_per_agent) if entry.tpm_limit else entry.rpm_limit
        req_bound = int(entry.max_tokens_per_request / tokens_per_agent) if entry.max_tokens_per_request else b.max_batch_agents
        batch_max = max(1, min(tpm_bound, req_bound, entry.rpm_limit, b.max_batch_agents))
        if entry.batch_max_agents is not None:
            logger.warning(
                f"Provider '{name}' : batch_max_agents={entry.batch_max_agents} écrit dans le fichier "
                f"est ignoré, le gateway le calcule ({batch_max})."
            )
        tpm_estimate = batch_max * tokens_per_agent if entry.tpm_limit else None
        logger.info(
            f"Provider '{name}' — batch_max_agents={batch_max} tpm_estimate_per_request={tpm_estimate} "
            f"(tpm={entry.tpm_limit}, rpm={entry.rpm_limit}, cap={b.max_batch_agents})"
        )
        data = entry.model_dump(exclude={"batch_max_agents"})
        return ProviderConfig(
            api_key=key, batch_max_agents=batch_max, tpm_estimate_per_request=tpm_estimate, **data,
        )

    # ── Lecture des capacités ───────────────────────────────────────────────

    def get_batch_max_agents(self, force_provider: str | None = None) -> int:
        """Limite de lot du worker : celle du provider forcé, sinon le min des providers (conservateur)."""
        if force_provider:
            cfg = self.providers.get(force_provider)
            if cfg:
                return cfg.batch_max_agents
        if self.providers:
            return min(p.batch_max_agents for p in self.providers.values())
        return self.batching.max_agents

    def get_dispatch_threshold(self, force_provider: str | None = None) -> int:
        """Taille de file déclenchant un dispatch immédiat côté API.

        Provider forcé : sa capacité. Sinon la cible de lot, bornée par le plus gros provider —
        surtout PAS le min des providers, qui vaut 1 à cause des petits TPM et rendrait la fenêtre
        d'accumulation inopérante.
        """
        if force_provider:
            cfg = self.providers.get(force_provider)
            if cfg:
                return cfg.batch_max_agents
        if self.providers:
            return min(self.batching.target_agents, max(p.batch_max_agents for p in self.providers.values()))
        return self.batching.target_agents

    # ── Alias à plat (compatibilité une version ; préférer les groupes) ─────

    @property
    def redis_url(self) -> str: return self.redis.url
    @property
    def celery_broker_url(self) -> str: return self.executor.celery_broker_url
    @property
    def celery_result_backend(self) -> str: return self.executor.celery_result_backend
    @property
    def max_retries(self) -> int: return self.resilience.max_retries
    @property
    def backoff_base_seconds(self) -> float: return self.resilience.backoff_base_seconds
    @property
    def provider_switch_cooldown_seconds(self) -> int: return self.resilience.provider_switch_cooldown_seconds
    @property
    def batch_max_agents(self) -> int: return self.batching.max_agents
    @property
    def batch_delay_seconds(self) -> float: return self.batching.delay_seconds
    @property
    def batch_target_agents(self) -> int: return self.batching.target_agents
    @property
    def assumed_prompt_tokens(self) -> int: return self.batching.assumed_prompt_tokens
    @property
    def assumed_output_tokens(self) -> int: return self.batching.assumed_output_tokens
    @property
    def token_chars_ratio(self) -> float: return self.batching.token_chars_ratio
    @property
    def max_batch_agents(self) -> int: return self.batching.max_batch_agents
    @property
    def min_output_tokens(self) -> int: return self.batching.min_output_tokens
    @property
    def max_output_tokens(self) -> int: return self.batching.max_output_tokens


# Nom historique, conservé pour les imports existants.
Settings = GatewaySettings


# ---------------------------------------------------------------------------
# Filtrage, exposition masquée, accès partagé
# ---------------------------------------------------------------------------

def filter_providers_without_api_key(settings: GatewaySettings) -> dict[str, ProviderConfig]:
    valid: dict[str, ProviderConfig] = {}
    b = settings.batching
    for name, provider in settings.providers.items():
        if not provider.api_key.get_secret_value():
            logger.warning(f"Fournisseur '{name}' exclu : clé API manquante.")
            continue
        if provider.max_tokens_per_request is not None:
            min_needed = provider.batch_max_agents * b.assumed_prompt_tokens + b.min_output_tokens
            if provider.max_tokens_per_request < min_needed:
                logger.warning(
                    f"Fournisseur '{name}' exclu : capacité insuffisante "
                    f"(max_tokens_per_request={provider.max_tokens_per_request} < "
                    f"batch_max_agents={provider.batch_max_agents} × assumed_prompt_tokens={b.assumed_prompt_tokens} "
                    f"+ min_output_tokens={b.min_output_tokens} = {min_needed})."
                )
                continue
        valid[name] = provider
        logger.info(f"Fournisseur '{name}' inclus : {provider}")
    return valid


def redacted_dump(settings: GatewaySettings) -> dict[str, Any]:
    """La configuration effective, secrets masqués : ce que `/config` et `config show` publient."""
    data = settings.model_dump(mode="json")
    data["provider_keys"] = {k: "***" for k in settings.provider_keys}
    data["api"]["auth_tokens"] = ["***" for _ in settings.api.auth_tokens]
    for name, cfg in data.get("providers", {}).items():
        cfg["api_key"] = "***" if settings.providers[name].api_key.get_secret_value() else ""
    data["providers_file"] = str(settings.resolved_providers_file())
    return data


def load_provider_defaults(path: Path | None = None) -> dict[str, dict]:
    """Les entrées BRUTES du fichier des fournisseurs (avec ou sans clé) — compatibilité.

    Consommé par prompt_calibration pour connaître les instances déclarées. Sans chemin, celui des
    réglages courants.
    """
    target = Path(path) if path else get_settings().resolved_providers_file()
    declared: ProvidersFile = load_providers_file(target)
    return {name: entry.model_dump(exclude_none=True) for name, entry in declared.providers.items()}


@lru_cache(maxsize=1)
def get_settings() -> GatewaySettings:
    """Réglages partagés du processus — construits au premier appel, pas à l'import.

    Les fournisseurs sans clé (ou sans capacité) sont retirés ici ; `declared_providers` garde la
    liste complète du fichier.
    """
    settings = GatewaySettings()
    settings.providers = filter_providers_without_api_key(settings)
    return settings


__all__ = [
    "ApiSettings",
    "BatchingSettings",
    "ExecutorSettings",
    "GatewaySettings",
    "InferenceSettings",
    "ProviderConfig",
    "RedisSettings",
    "ResilienceSettings",
    "Settings",
    "TelemetrySettings",
    "filter_providers_without_api_key",
    "get_settings",
    "load_provider_defaults",
    "redacted_dump",
]
