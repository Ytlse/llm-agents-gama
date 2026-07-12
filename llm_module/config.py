"""
config.py — Configuration du gateway (pydantic-settings).

La configuration n'est JAMAIS construite comme effet de bord d'un import de
module métier : les entrypoints (create_app, worker Celery, tests) appellent
explicitement Settings() ou get_settings(). Construire Settings lit
providers.yaml et l'environnement — aucun accès Redis/réseau.
"""

from __future__ import annotations
import os
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

import yaml
from pydantic import BaseModel, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from llm_module.telemetry.logger import get_logger

logger = get_logger(__name__)

_PROVIDERS_YAML = Path(__file__).parent / "config" / "providers.yaml"


def load_provider_defaults() -> Dict[str, dict]:
    """Charge la liste des providers depuis providers.yaml."""
    with open(_PROVIDERS_YAML, "r") as f:
        data = yaml.safe_load(f)
    return data.get("providers", {})


class ProviderConfig(BaseModel):
    api_key:                  SecretStr    = SecretStr("")
    rpm_limit:                int
    tpm_limit:                Optional[int] = None
    rpd_limit:                Optional[int] = None  # quota requêtes/jour (free tier) — appliqué : provider écarté jusqu'à minuit UTC une fois atteint
    tpd_limit:                Optional[int] = None  # quota tokens/jour (free tier) — appliqué (comptage a posteriori des tokens réellement consommés)
    max_tokens_per_request:   Optional[int] = None  # capacité max d'une requête unique (tokens) ; exclu si < batch_max_agents * assumed_prompt_tokens + min_output_tokens
    max_output_tokens:        Optional[int] = None  # plafond de complétion du modèle (param max_tokens) ; None = pas de limite connue (fallback settings.max_output_tokens) ; appris automatiquement sur HTTP 400 et persisté dans providers.yaml
    base_url:                 str
    default_model:            str
    weight:                   float        = 1.0
    batch_max_agents:         int          = 1   # calculé par Settings.build_providers — ne pas définir manuellement
    tpm_estimate_per_request: Optional[int] = None  # tokens (in+out) estimés d'une requête pleine ; calculé par Settings.build_providers — sert de garde-fou TPM glissant côté rate-limiter (None si tpm_limit absent)
    concurrency_limit:        int          = 2   # nb workers Celery simultanés autorisés pour ce provider
    disable_timeout:          int          = 180
    adapter:                  str          = ""

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
    max_retries:                int   = 50
    backoff_base_seconds:       float = 1.0
    # Cooldown court appliqué au provider fautif lors d'un basculement (parse error ou
    # 4xx non récupérable) : force la rotation à choisir un AUTRE modèle au réessai.
    provider_switch_cooldown_seconds: int = 30
    batch_max_agents:           int   = 5     # fallback si aucun provider configuré
    # Fenêtre d'accumulation du micro-batching : une requête qui n'atteint pas le
    # seuil de dispatch attend ce délai pour être fusionnée avec les suivantes.
    # Calé sur l'inter-arrivée mesurée des prompts (run 2026-07-10 : p50 = 1,4s,
    # p90 du débit = 40 prompts/min) — 1s ne captait quasiment rien.
    batch_delay_seconds:        float = 3.0
    # Seuil de dispatch immédiat (cf. get_dispatch_threshold) : taille de file à
    # partir de laquelle on n'attend plus batch_delay_seconds. Découplé du min
    # des providers, qui vaut 1 à cause des petits TPM Groq et court-circuitait
    # toute accumulation (ratio agents/prompt ≈ 1 hors backlog).
    batch_target_agents:        int   = 10
    assumed_prompt_tokens:      int   = 2200  # tokens_in max par agent (historique +10% de marge)
    assumed_output_tokens:      int   = 800   # tokens_out estimés par agent — sert (avec assumed_prompt_tokens) à dimensionner la réservation TPM glissante
    # Estimation tokens_in depuis la taille du prompt rendu : tokens ≈ chars / ratio.
    # Mesuré sur le run 2026-07-10 (427 échanges, prompts FR + JSON) : p50 = 3,24,
    # p10 = 3,05 → 3,0 laisse ~8 % de marge. Sert à recaler la réservation TPM
    # glissante sur la taille réelle de chaque requête (cf. worker/task_worker.py).
    token_chars_ratio:          float = 3.0
    max_batch_agents:           int   = 20    # plafond absolu du calcul automatique de batch_max_agents
    min_output_tokens:          int   = 512   # budget output minimal acceptable par requête
    max_output_tokens:          int   = 16384 # plafond du max_tokens envoyé au provider (16 384 = limite de complétion gpt-4o-mini, le plus contraint des providers configurés)

    # Les api_key viennent de l'env : PROVIDER_KEYS__groq=gsk-...
    provider_keys: Dict[str, SecretStr] = {}

    # Construit après validation — pas lu depuis l'env
    providers: Dict[str, ProviderConfig] = {}

    @model_validator(mode="after")
    def build_providers(self) -> "Settings":
        defaults = load_provider_defaults()
        # Coût tokens (in+out) d'un agent dans un batch — dimensionne batch_max_agents.
        # Mesuré sur le run 2026-07-10 : 1 282 in + 320 out ≈ 1 600/agent (p90 ≈ 2 400) ;
        # assumed_prompt_tokens + assumed_output_tokens = 3 000 garde ~25 % de marge.
        # (Historique : un 4096 codé en dur donnait 6 296/agent et écrasait à 1 le
        # batch_max_agents des providers à petit TPM.)
        tokens_per_agent = self.assumed_prompt_tokens + self.assumed_output_tokens
        result = {}
        for name, entry in defaults.items():
            adapter_name = entry.get("adapter", name)
            key = self.provider_keys.get(name) or self.provider_keys.get(adapter_name, SecretStr(""))
            tpm = entry.get("tpm_limit")
            rpm = entry.get("rpm_limit", 1)
            tpm_bound = int(tpm / tokens_per_agent) if tpm else rpm
            # Capacité par requête unique (HTTP 413 au-delà) : borne le batch au même
            # titre que le TPM — un batch qui ne tient pas dans une requête ne part jamais.
            req_cap = entry.get("max_tokens_per_request")
            req_bound = int(req_cap / tokens_per_agent) if req_cap else self.max_batch_agents
            entry["batch_max_agents"] = max(1, min(tpm_bound, req_bound, rpm, self.max_batch_agents))
            # Estimation de la consommation tokens (in+out) d'une requête pleine —
            # garde-fou TPM glissant appliqué par le rate-limiter (None si pas de tpm_limit).
            if tpm:
                entry["tpm_estimate_per_request"] = entry["batch_max_agents"] * (
                    self.assumed_prompt_tokens + self.assumed_output_tokens
                )
            logger.info(
                f"Provider '{name}' — batch_max_agents={entry['batch_max_agents']} "
                f"tpm_estimate_per_request={entry.get('tpm_estimate_per_request')} "
                f"(tpm={tpm}, rpm={rpm}, cap={self.max_batch_agents})"
            )
            result[name] = ProviderConfig(api_key=key, **entry)
        self.providers = result
        return self

    def get_batch_max_agents(self, force_provider: Optional[str] = None) -> int:
        """
        Limite de batch liée à la capacité du provider.
        - Provider forcé : limite exacte de ce provider.
        - Provider dynamique : minimum des providers disponibles (approche conservative,
          car on ne connaît pas encore le provider qui sera sélectionné).
        - Aucun provider configuré : fallback sur batch_max_agents.
        """
        if force_provider:
            provider_cfg = self.providers.get(force_provider)
            if provider_cfg:
                return provider_cfg.batch_max_agents

        if self.providers:
            return min(p.batch_max_agents for p in self.providers.values())

        return self.batch_max_agents

    def get_dispatch_threshold(self, force_provider: Optional[str] = None) -> int:
        """
        Taille de file (en tâches) déclenchant un dispatch immédiat côté API.
        En dessous, le dispatch est différé de batch_delay_seconds pour laisser
        le micro-batching accumuler des tâches compatibles.

        - Provider forcé : sa capacité exacte (attendre au-delà ne sert à rien).
        - Provider dynamique : batch_target_agents, borné par la capacité du plus
          gros provider. Surtout PAS le min des providers (contrairement à
          get_batch_max_agents, utilisé par le worker au pop) : les providers à
          petit TPM ont batch_max_agents = 1, le seuil serait toujours atteint et
          la fenêtre d'accumulation ne jouerait jamais.
        """
        if force_provider:
            provider_cfg = self.providers.get(force_provider)
            if provider_cfg:
                return provider_cfg.batch_max_agents

        if self.providers:
            return min(self.batch_target_agents, max(p.batch_max_agents for p in self.providers.values()))

        return self.batch_target_agents


def filter_providers_without_api_key(settings: Settings) -> Dict[str, ProviderConfig]:
    valid = {}
    for name, provider in settings.providers.items():
        if not provider.api_key.get_secret_value():
            logger.warning(f"Fournisseur '{name}' exclu : clé API manquante.")
            continue
        if provider.max_tokens_per_request is not None:
            min_needed = provider.batch_max_agents * settings.assumed_prompt_tokens + settings.min_output_tokens
            if provider.max_tokens_per_request < min_needed:
                logger.warning(
                    f"Fournisseur '{name}' exclu : capacité insuffisante "
                    f"(max_tokens_per_request={provider.max_tokens_per_request} < "
                    f"batch_max_agents={provider.batch_max_agents} × assumed_prompt_tokens={settings.assumed_prompt_tokens} "
                    f"+ min_output_tokens={settings.min_output_tokens} = {min_needed})."
                )
                continue
        valid[name] = provider
        logger.info(f"Fournisseur '{name}' inclus : {provider}")
    return valid


def learn_provider_max_output_tokens(provider_name: str, limit: int) -> bool:
    """Enregistre la limite de complétion réelle d'un provider apprise via une
    erreur HTTP 400 ("`max_tokens` must be less than or equal to N").

    Met à jour la config en mémoire du process courant (le prochain batch sera
    plafonné correctement) et persiste la valeur dans providers.yaml pour que
    les autres process / prochains démarrages en profitent.

    Returns:
        True si une nouvelle limite (plus stricte) a été apprise, False si la
        config connaissait déjà une limite ≤ (rien à corriger → l'appelant ne
        doit PAS retenter, sous peine de boucler sur la même 400).
    """
    if limit <= 0:
        return False
    settings = get_settings()
    cfg = settings.providers.get(provider_name)
    if cfg is None:
        logger.warning(
            f"Limite max_output_tokens apprise pour un provider inconnu | "
            f"provider={provider_name} limit={limit}"
        )
        return False
    if cfg.max_output_tokens is not None and cfg.max_output_tokens <= limit:
        return False
    logger.warning(
        f"Limite de complétion apprise depuis l'erreur provider — config ajustée | "
        f"provider={provider_name} max_output_tokens={cfg.max_output_tokens} -> {limit}"
    )
    cfg.max_output_tokens = limit
    _persist_provider_max_output_tokens(provider_name, limit)
    return True


def _persist_provider_max_output_tokens(provider_name: str, limit: int) -> None:
    """Écrit max_output_tokens dans providers.yaml (édition chirurgicale, ligne
    remplacée ou insérée sous le bloc du provider — les commentaires du fichier
    sont préservés). Écriture atomique via fichier temporaire + os.replace."""
    try:
        lines = _PROVIDERS_YAML.read_text().splitlines(keepends=True)

        start = next(
            (i for i, l in enumerate(lines)
             if re.match(rf"^  {re.escape(provider_name)}:\s*(#.*)?$", l)),
            None,
        )
        if start is None:
            logger.error(
                f"[ALARME] Provider introuvable dans providers.yaml — limite non persistée | "
                f"provider={provider_name} max_output_tokens={limit}"
            )
            return

        # Fin du bloc = prochaine ligne non vide/non commentaire indentée à 2 espaces max
        end = len(lines)
        for j in range(start + 1, len(lines)):
            if re.match(r"^(  )?\S", lines[j]):
                end = j
                break

        new_line = (
            f"    max_output_tokens:       {limit}  "
            f"# auto-ajusté le {date.today().isoformat()} (HTTP 400 du provider)\n"
        )
        for j in range(start + 1, end):
            if re.match(r"^\s*max_output_tokens\s*:", lines[j]):
                lines[j] = new_line
                break
        else:
            lines.insert(start + 1, new_line)

        tmp = _PROVIDERS_YAML.with_suffix(".yaml.tmp")
        tmp.write_text("".join(lines))
        os.replace(tmp, _PROVIDERS_YAML)
        logger.warning(
            f"providers.yaml mis à jour automatiquement | provider={provider_name} "
            f"max_output_tokens={limit}"
        )
    except OSError as e:
        logger.error(
            f"[ALARME] Impossible de persister max_output_tokens dans providers.yaml | "
            f"provider={provider_name} limit={limit} error={e}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Settings partagés du process — construits au premier appel, pas à l'import."""
    settings = Settings()
    settings.providers = filter_providers_without_api_key(settings)
    return settings
