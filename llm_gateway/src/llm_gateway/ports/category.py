"""ports/category.py — le contrat entre le gateway et un « bundle » de catégories.

Le gateway ne connaît aucun métier. Ce qu'il sait faire : recevoir des lots d'items par
catégorie, rendre un prompt, appeler un fournisseur, valider la sortie contre un schéma,
démultiplexer par ``agent_id``. Tout ce qui est propre à un domaine (le modèle d'un item, la
priorité d'un lot, les métriques métier à tirer d'une réponse) est apporté par un bundle,
découvert par l'entry point ``llm_gateway.categories``::

    [project.entry-points."llm_gateway.categories"]
    mobility = "mobility_llm:bundle"

où ``bundle()`` rend un :class:`CategoryBundle`.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from llm_gateway.core.models import AgentItem, LLMOutput
from llm_gateway.ports.metrics import MetricsSink


@dataclass(frozen=True)
class ObserveContext:
    """Ce que le worker transmet au bundle une fois la réponse validée.

    ``items`` sont les items validés par :attr:`CategorySpec.item_model` (dans l'ordre du
    lot), ``output`` la réponse déjà réalignée sur les ``agent_id`` attendus. Le bundle ne
    modifie ni l'un ni l'autre : il observe et compte dans ``metrics``.
    """

    category: str
    provider: str
    items: Sequence[BaseModel]
    output: LLMOutput
    metrics: MetricsSink


@dataclass(frozen=True)
class CategorySpec:
    """Une catégorie de prompt : son modèle d'item et ses hooks facultatifs."""

    name: str
    # Modèle pydantic qui valide chaque item du payload. None = AgentItem générique.
    item_model: type[BaseModel] = AgentItem
    # Score de priorité d'un lot (plus bas = plus urgent). None = pas de priorité.
    priority: Callable[[Sequence[BaseModel]], float | None] | None = None
    # Métriques métier tirées d'une réponse réussie.
    observe: Callable[[ObserveContext], None] | None = None

    def validate_items(self, raw_items: Sequence[Any]) -> list[BaseModel]:
        """Valide les items du payload avec le modèle de la catégorie."""
        model = self.item_model
        out: list[BaseModel] = []
        for raw in raw_items:
            data = raw.model_dump() if isinstance(raw, BaseModel) else raw
            out.append(model.model_validate(data))
        return out


@dataclass(frozen=True)
class CategoryBundle:
    """Un jeu de catégories livré avec ses templates, schémas et variantes de prompt.

    ``templates_dir`` contient un ``<catégorie>.md.j2`` par catégorie, ``schemas_file`` un
    objet JSON ``{catégorie: schéma de sortie}``, ``prompts_file`` (facultatif) le fichier
    ``active:`` / ``prompts:`` des variantes de prompt système.
    """

    name: str
    templates_dir: Path
    schemas_file: Path
    categories: dict[str, CategorySpec] = field(default_factory=dict)
    prompts_file: Path | None = None

    def spec(self, category: str) -> CategorySpec:
        return self.categories[category]


__all__ = ["CategoryBundle", "CategorySpec", "ObserveContext"]
