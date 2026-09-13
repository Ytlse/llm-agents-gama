"""core/inference.py — la cascade des paramètres d'inférence, pure.

Trois niveaux, du plus fort au plus faible : la **requête** (`parameters` du payload), le
**fournisseur** (bloc `inference:` de son entrée dans le fichier des fournisseurs), les
**défauts globaux** (`GatewaySettings.inference`). Une valeur absente à un niveau descend au
suivant ; `top_p` et `thinking_budget` peuvent rester `None`, auquel cas les adapters ne les
envoient pas — pour `thinking_budget`, cela signifie « défaut du fournisseur », à distinguer de
`0` qui désactive la réflexion.

`max_tokens` est un budget **par tâche** : le worker le multiplie par le nombre d'agents du lot
et le borne ensuite par les plafonds du fournisseur.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol


class _InferenceLike(Protocol):
    temperature: float | None
    top_p: float | None
    max_tokens: int | None
    thinking_budget: int | None
    thinking_level: str | None


class ReglagesReflexionIncompatibles(ValueError):
    """`thinking_level` et `thinking_budget` demandés ensemble — l'API rend 400."""


@dataclass(frozen=True)
class InferenceParams:
    temperature: float
    top_p: float | None
    max_tokens: int
    # None = non demandé : le fournisseur applique son propre défaut de réflexion. Distinct de
    # 0, qui la désactive explicitement.
    thinking_budget: int | None = None
    # Niveau de réflexion (API courante) : `minimal` | `low` | `medium` | `high`.
    thinking_level: str | None = None


def _pick(name: str, request: Mapping[str, Any], provider: _InferenceLike | None, defaults: _InferenceLike) -> Any:
    value = request.get(name)
    if value is None and provider is not None:
        value = getattr(provider, name, None)
    if value is None:
        # `None` par défaut si l'objet de défauts ne déclare pas la clé : une clé ajoutée à la
        # cascade ne doit pas faire tomber la résolution sur une configuration plus ancienne
        # qui l'ignore. Vrai pour `thinking_budget`, et pour toute clé future.
        value = getattr(defaults, name, None)
    return value


def resolve_inference(
    request_parameters: Mapping[str, Any] | None,
    provider_overrides: _InferenceLike | None,
    defaults: _InferenceLike,
) -> InferenceParams:
    """Résout température, top_p et budget de sortie : requête > fournisseur > défauts.

    Les valeurs de la requête sont coercées (un client JSON peut envoyer `"0.7"`) ; une
    valeur illisible est ignorée et le niveau suivant s'applique, jamais une exception
    pour un paramètre d'inférence.
    """
    req = dict(request_parameters or {})
    for key, caster in (("temperature", float), ("top_p", float), ("max_tokens", int),
                        ("thinking_budget", int), ("thinking_level", str)):
        if key in req and req[key] is not None:
            try:
                req[key] = caster(req[key])
            except (TypeError, ValueError):
                req[key] = None
    temperature = _pick("temperature", req, provider_overrides, defaults)
    top_p = _pick("top_p", req, provider_overrides, defaults)
    max_tokens = _pick("max_tokens", req, provider_overrides, defaults)
    budget = _pick("thinking_budget", req, provider_overrides, defaults)
    niveau = _pick("thinking_level", req, provider_overrides, defaults)
    if niveau is not None and budget is not None:
        # Le fournisseur rend 400 si les deux sont présents. Refuser ici nomme le conflit et le
        # niveau où il se joue, au lieu d'un 400 opaque au milieu d'un run de trois heures.
        raise ReglagesReflexionIncompatibles(
            f"thinking_level={niveau!r} et thinking_budget={budget!r} demandés ensemble : "
            "l'API les refuse conjointement (400). Choisissez l'un — `thinking_level` est le "
            "réglage courant, `thinking_budget` n'est là que pour compatibilité ascendante."
        )
    return InferenceParams(
        temperature=float(temperature),
        top_p=None if top_p is None else float(top_p),
        max_tokens=int(max_tokens),
        thinking_budget=None if budget is None else int(budget),
        thinking_level=None if niveau is None else str(niveau),
    )


__all__ = ["InferenceParams", "ReglagesReflexionIncompatibles", "resolve_inference"]
