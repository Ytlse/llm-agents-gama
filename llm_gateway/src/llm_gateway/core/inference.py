"""core/inference.py — la cascade des paramètres d'inférence, pure.

Trois niveaux, du plus fort au plus faible : la **requête** (`parameters` du payload), le
**fournisseur** (bloc `inference:` de son entrée dans le fichier des fournisseurs), les
**défauts globaux** (`GatewaySettings.inference`). Une valeur absente à un niveau descend au
suivant ; `top_p` peut rester `None`, auquel cas les adapters ne l'envoient pas.

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


@dataclass(frozen=True)
class InferenceParams:
    temperature: float
    top_p: float | None
    max_tokens: int


def _pick(name: str, request: Mapping[str, Any], provider: _InferenceLike | None, defaults: _InferenceLike) -> Any:
    value = request.get(name)
    if value is None and provider is not None:
        value = getattr(provider, name, None)
    if value is None:
        value = getattr(defaults, name)
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
    for key, caster in (("temperature", float), ("top_p", float), ("max_tokens", int)):
        if key in req and req[key] is not None:
            try:
                req[key] = caster(req[key])
            except (TypeError, ValueError):
                req[key] = None
    temperature = _pick("temperature", req, provider_overrides, defaults)
    top_p = _pick("top_p", req, provider_overrides, defaults)
    max_tokens = _pick("max_tokens", req, provider_overrides, defaults)
    return InferenceParams(
        temperature=float(temperature),
        top_p=None if top_p is None else float(top_p),
        max_tokens=int(max_tokens),
    )


__all__ = ["InferenceParams", "resolve_inference"]
