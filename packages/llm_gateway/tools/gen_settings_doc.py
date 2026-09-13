"""Génère docs/reference/reglages.md depuis les modèles pydantic des réglages.

Usage : ../llm-agents/.venv/bin/python tools/gen_settings_doc.py
La table est la source de vérité de la référence : ne pas l'éditer à la main.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, get_args, get_origin

from pydantic import BaseModel
from pydantic_core import PydanticUndefined

from llm_gateway.config.providers import InferenceOverrides, ProviderEntry
from llm_gateway.config.settings import (
    ApiSettings,
    BatchingSettings,
    ExecutorSettings,
    GatewaySettings,
    InferenceSettings,
    ProviderConfig,
    RedisSettings,
    ResilienceSettings,
    TelemetrySettings,
)
from llm_gateway.config.sources import ENV_PREFIX, LEGACY_ENV, new_env_name

OUT = Path(__file__).resolve().parents[1] / "docs" / "reference" / "reglages.md"

GROUPS: list[tuple[str, type[BaseModel], str]] = [
    ("redis", RedisSettings, "Connexion Redis : store des tâches, files de lot, rate-limiter, compteurs, limites apprises."),
    ("executor", ExecutorSettings, "Exécution des lots. `celery` aujourd'hui ; un exécuteur in-process est prévu."),
    ("inference", InferenceSettings, "Défauts d'inférence ; surchargés par provider (`inference:` du fichier) puis par requête."),
    ("batching", BatchingSettings, "Micro-batching : valeurs mesurées sur les runs de juillet 2026, à recalibrer ailleurs."),
    ("resilience", ResilienceSettings, "Réessais, bascule de fournisseur, désactivation après erreurs consécutives."),
    ("api", ApiSettings, "Couche HTTP : CORS, taille de requête, jetons (ticket 036, non appliqués)."),
    ("telemetry", TelemetrySettings, "Logs, dossier du run, journal des échanges."),
]

LEGACY_BY_PATH = {path: old for old, path in LEGACY_ENV.items()}


def _type_name(annotation: Any) -> str:
    origin = get_origin(annotation)
    if origin is None:
        return getattr(annotation, "__name__", str(annotation)).replace("typing.", "")
    args = ", ".join(_type_name(a) for a in get_args(annotation))
    if str(origin).endswith("UnionType") or origin is type(int | None):
        return " | ".join(_type_name(a) for a in get_args(annotation))
    return f"{getattr(origin, '__name__', str(origin))}[{args}]"


def _default(field: Any) -> str:
    if field.default_factory is not None:
        value = field.default_factory()
        return f"`{value!r}`" if value not in ({}, []) else "`vide`"
    if field.default is PydanticUndefined:
        return "**obligatoire**"
    v = field.default
    return f"`{v.get_secret_value()!r}`" if hasattr(v, "get_secret_value") else f"`{v!r}`"


def _rows(model: type[BaseModel], group: str | None) -> list[str]:
    rows = []
    for name, field in model.model_fields.items():
        env = new_env_name((group, name)) if group else f"{ENV_PREFIX}{name.upper()}"
        legacy = LEGACY_BY_PATH.get((group, name)) if group else None
        env_cell = f"`{env}`" + (f" (ex-`{legacy}`)" if legacy else "")
        desc = (field.description or "").replace("|", "\\|")
        rows.append(f"| `{name}` | `{_type_name(field.annotation)}` | {_default(field)} | {env_cell} | {desc} |")
    return rows


def main() -> int:
    lines = [
        "# Réglages",
        "",
        "> Page **générée** par `tools/gen_settings_doc.py` depuis les modèles pydantic ; la relancer après",
        "> tout changement de `config/settings.py` ou `config/providers.py`.",
        "",
        "Les réglages sont **groupés** et viennent de six sources, de la plus forte à la plus faible :",
        "arguments du constructeur, environnement `LLM_GATEWAY_*` (`__` sépare les niveaux :",
        "`LLM_GATEWAY_BATCHING__DELAY_SECONDS`), anciens noms non préfixés (dépréciés, une version, un",
        "avertissement par variable trouvée), fichier YAML désigné par `LLM_GATEWAY_CONFIG`, profil désigné par",
        "`LLM_GATEWAY_PROFILE` (`free-tier`, `paid`), défauts du code. Les clés d'API se lisent sous",
        "`LLM_GATEWAY_PROVIDER_KEYS__<nom>` **ou** `PROVIDER_KEYS__<nom>` (nom canonique partagé avec le compose,",
        "`make providers` et prompt_calibration, sans avertissement).",
        "",
        "## Champs de premier niveau",
        "",
        "| Champ | Type | Défaut | Variable | Sens |",
        "|---|---|---|---|---|",
    ]
    top = {
        "providers_file": "fichier des fournisseurs (configuration de déploiement). `None` = exemple livré chargé avec un avertissement.",
        "learned_limits": "où vivent les limites apprises (`max_output_tokens` révélé par HTTP 400) : `redis`, `file`, `none`.",
        "learned_limits_file": "chemin du fichier JSON quand `learned_limits=file` ; défaut `<telemetry.workdir>/learned_limits.json`.",
        "provider_keys": "clés d'API par instance ou par adapter ; résolution `provider_keys[instance] or provider_keys[adapter]`.",
        "providers": "**construit** après validation : instances résolues (`ProviderConfig`), pas lu de l'environnement.",
        "declared_providers": "**construit** : noms déclarés dans le fichier, avec ou sans clé.",
    }
    for name, desc in top.items():
        field = GatewaySettings.model_fields[name]
        env = f"`{ENV_PREFIX}{name.upper()}`" if name in ("providers_file", "learned_limits", "learned_limits_file") else (
            f"`{ENV_PREFIX}PROVIDER_KEYS__<nom>` ou `PROVIDER_KEYS__<nom>`" if name == "provider_keys" else "—")
        lines.append(f"| `{name}` | `{_type_name(field.annotation)}` | {_default(field)} | {env} | {desc} |")
    for group, model, intro in GROUPS:
        lines += ["", f"## `{group}`", "", intro, "", "| Champ | Type | Défaut | Variable | Sens |", "|---|---|---|---|---|"]
        lines += _rows(model, group)
    lines += [
        "", "## Fichier des fournisseurs", "",
        "Un objet `providers:` dont chaque entrée suit `ProviderEntry`. Toute clé inconnue fait échouer le",
        "chargement en nommant le fournisseur et la clé. Schéma JSON : `llm-gateway config schema providers`.",
        "", "| Champ | Type | Défaut | Sens |", "|---|---|---|---|",
    ]
    entry_desc = {
        "rpm_limit": "requêtes/minute, fenêtre glissante 60 s, lissage `60 / rpm` entre deux requêtes",
        "base_url": "racine de l'API du fournisseur", "default_model": "modèle envoyé si la requête n'en impose pas",
        "tpm_limit": "tokens/minute réservés dans la même fenêtre ; borne `batch_max_agents`",
        "rpd_limit": "requêtes/jour (UTC) ; atteint → écarté jusqu'à minuit UTC",
        "tpd_limit": "tokens/jour (UTC), comptés a posteriori ; même mise à l'écart",
        "max_tokens_per_request": "capacité d'une requête unique (HTTP 413 au-delà) ; borne le lot et le budget de sortie",
        "max_output_tokens": "plafond de complétion ; appris sur HTTP 400 et retenu par le store de limites apprises",
        "weight": "poids SWRR : `min(rpm_limit, tpm_limit / 3000) / 15`", "concurrency_limit": "workers simultanés autorisés sur l'instance",
        "disable_timeout": "durée (s) de mise à l'écart après `disable_after_consecutive_errors` erreurs",
        "adapter": "nom de l'adapter (openai_compatible, openai, mistral, google, groq, cerebras, ou un entry point `llm_gateway.adapters`) ; défaut = nom de l'entrée",
        "structured_output": "sortie structurée du traducteur OpenAI-compatible : `json_schema`, `json_object`, `none` ; None = défaut de l'adapter",
        "schema_in_system": "recopier le schéma JSON dans le message system ; None = défaut de l'adapter",
        "inference": "surcharges `temperature`, `top_p`, `max_tokens` pour cette instance",
        "batch_max_agents": "toléré pour les anciens fichiers, **ignoré** avec un avertissement : le gateway le calcule",
    }
    for name, field in ProviderEntry.model_fields.items():
        lines.append(f"| `{name}` | `{_type_name(field.annotation)}` | {_default(field)} | {entry_desc.get(name, '')} |")
    lines += ["", "### `inference` (surcharges par fournisseur)", "", "| Champ | Type | Défaut |", "|---|---|---|"]
    for name, field in InferenceOverrides.model_fields.items():
        lines.append(f"| `{name}` | `{_type_name(field.annotation)}` | {_default(field)} |")
    lines += [
        "", "## `ProviderConfig` (instance résolue)", "",
        "Ce que le gateway manipule : l'entrée du fichier, la clé injectée et deux valeurs calculées.",
        "`batch_max_agents = max(1, min(tpm_limit / (assumed_prompt_tokens + assumed_output_tokens),",
        "max_tokens_per_request / idem, rpm_limit, batching.max_batch_agents))` ;",
        "`tpm_estimate_per_request = batch_max_agents × (assumed_prompt_tokens + assumed_output_tokens)` si `tpm_limit`.",
        "", "| Champ | Type | Défaut |", "|---|---|---|",
    ]
    for name, field in ProviderConfig.model_fields.items():
        lines.append(f"| `{name}` | `{_type_name(field.annotation)}` | {_default(field)} |")
    lines += [
        "", "## Anciens noms encore lus (dépréciés)", "",
        "| Ancien nom | Nouveau nom |", "|---|---|",
    ]
    for old, path in LEGACY_ENV.items():
        lines.append(f"| `{old}` | `{new_env_name(path)}` |")
    lines += ["", "`PROVIDER_KEYS__<nom>` n'est pas déprécié : c'est le nom canonique des clés d'API.", ""]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{OUT.relative_to(Path.cwd())} : {len(lines)} lignes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
