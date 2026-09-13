"""config/providers.py — le fichier des fournisseurs, validé avant tout démarrage.

Le fichier (YAML) décrit les instances de fournisseurs : quotas, modèle, poids, capacité.
Il vit **hors du paquet** (configuration de déploiement, `LLM_GATEWAY_PROVIDERS_FILE`) ;
le paquet ne livre qu'un exemple, `providers.example.yaml`, chargé avec un avertissement quand
aucun fichier n'est désigné.

Une clé inconnue fait échouer le chargement en nommant le fournisseur et la clé : un
`tpm_limt` ignoré en silence faisait tourner un provider avec un autre réglage que celui écrit.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from llm_gateway.core.quota import DEFAUT_FUSEAU_QUOTA

DEFAULT_EXAMPLE_FILE = Path(__file__).resolve().parent / "providers.example.yaml"


class ProvidersConfigError(ValueError):
    """Fichier des fournisseurs absent, illisible ou invalide. Jamais un repli silencieux."""


class InferenceOverrides(BaseModel):
    """Surcharge par fournisseur des paramètres d'inférence (cascade : requête > provider > défaut)."""

    model_config = ConfigDict(extra="forbid")

    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    # Surcharge par fournisseur : utile pour éteindre la réflexion sur une instance qui la
    # facture ou la supporte mal, sans toucher aux autres.
    thinking_budget: int | None = None
    thinking_level: str | None = None


class ProviderEntry(BaseModel):
    """Une instance de fournisseur telle qu'écrite dans le fichier. Aucun champ calculé ici."""

    model_config = ConfigDict(extra="forbid")

    rpm_limit: int
    base_url: str
    default_model: str
    tpm_limit: int | None = None
    rpd_limit: int | None = None   # requêtes/jour : appliqué, provider écarté jusqu'au reset du quota
    # Fuseau du reset journalier du fournisseur. Gemini free tier compte sa journée en
    # heure du Pacifique : avec le défaut UTC, les compteurs se vidaient 7 h trop tôt et
    # une clé refusée passait pour disponible (incident du 2026-09-08).
    quota_reset_tz: str = DEFAUT_FUSEAU_QUOTA
    tpd_limit: int | None = None   # tokens/jour : appliqué, comptage a posteriori des tokens réels
    max_tokens_per_request: int | None = None  # capacité d'une requête unique (HTTP 413 au-delà)
    max_output_tokens: int | None = None       # plafond de complétion ; appris sur HTTP 400 (cf. learned)
    # Plafond de RÉFLEXION du modèle servi, en jetons de pensée. À relever dans la
    # documentation du fournisseur, jamais deviné : un budget au-dessus du plafond est raboté
    # SILENCIEUSEMENT côté fournisseur, et la réponse ne rapporte que les jetons de pensée
    # consommés — jamais le budget appliqué. Rien ne permettrait donc de rattraper l'écart
    # après coup, et l'empreinte de l'expérience porterait un budget qui n'a pas été appliqué.
    # Déclaré → « maximum » devient proposable au formulaire et un budget supérieur est refusé
    # d'avance. Absent → aucun maximum n'est proposé (on ne remplace pas une mesure par un
    # chiffre plausible).
    thinking_budget_max: int | None = None
    # Niveaux de réflexion acceptés par le modèle servi (`minimal`, `low`, `medium`, `high`).
    # Relevés dans la documentation du fournisseur : ils varient d'un modèle à l'autre, et
    # demander un niveau absent rend 400. Déclarés → le formulaire n'offre que ceux-là et un
    # niveau inconnu est refusé d'avance ; absents → aucun niveau n'est proposé.
    thinking_levels: list[str] | None = None
    weight: float = 1.0
    concurrency_limit: int = 2
    # Attente maximale du CLIENT pour une tâche servie par cette instance (secondes).
    # Réglage d'appelant, pas de routage : le gateway ne le lit pas, le SDK le reçoit par appel
    # (cf. `sdk.client.execute(wait_timeout=…)`). Un modèle local ne sert qu'un appel à la fois :
    # l'attente d'une tâche est celle de la FILE, pas de la génération. None = défaut du client.
    wait_timeout: float | None = None
    disable_timeout: int = 180
    adapter: str = ""
    # Sortie structurée de l'adapter OpenAI-compatible : json_schema (natif), json_object,
    # none ; et injection du schéma dans le message system. None = défauts de l'adapter.
    structured_output: Literal["json_schema", "json_object", "none"] | None = None
    schema_in_system: bool | None = None
    inference: InferenceOverrides | None = None
    # Toléré parce que d'anciens fichiers le portent ; recalculé par les réglages, jamais lu.
    batch_max_agents: int | None = None   # ignoré et signalé au chargement : le gateway le calcule


class ProvidersFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    providers: dict[str, ProviderEntry] = Field(default_factory=dict)


def _format_validation_error(path: Path, exc: ValidationError) -> str:
    lines = []
    for err in exc.errors():
        loc = [str(x) for x in err.get("loc", ())]
        provider = loc[1] if len(loc) > 1 and loc[0] == "providers" else None
        key = ".".join(loc[2:]) if len(loc) > 2 else ".".join(loc)
        where = f"provider {provider!r}, clé {key!r}" if provider else f"clé {key!r}"
        lines.append(f"  - {where} : {err.get('msg')}")
    return f"Fichier des fournisseurs invalide ({path}) :\n" + "\n".join(lines)


def load_providers_file(path: Path) -> ProvidersFile:
    """Charge et valide le fichier. Lève ProvidersConfigError, jamais autre chose."""
    path = Path(path)
    if not path.is_file():
        raise ProvidersConfigError(f"Fichier des fournisseurs introuvable : {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ProvidersConfigError(f"Fichier des fournisseurs illisible ({path}) : {exc}") from exc
    if not isinstance(data, dict):
        raise ProvidersConfigError(f"Fichier des fournisseurs ({path}) : un objet YAML est attendu")
    try:
        return ProvidersFile.model_validate(data)
    except ValidationError as exc:
        raise ProvidersConfigError(_format_validation_error(path, exc)) from exc


def providers_schema() -> dict[str, Any]:
    """JSON Schema du fichier des fournisseurs (validation dans l'éditeur, en CI)."""
    return ProvidersFile.model_json_schema()


def providers_schema_json() -> str:
    return json.dumps(providers_schema(), indent=2, ensure_ascii=False)


__all__ = [
    "DEFAULT_EXAMPLE_FILE",
    "InferenceOverrides",
    "ProviderEntry",
    "ProvidersConfigError",
    "ProvidersFile",
    "load_providers_file",
    "providers_schema",
    "providers_schema_json",
]
