"""persona.py — l'item des catégories mobilité : un persona et son contexte de décision.

C'était ``AgentSpec`` dans ``llm_module.core.models``. Le gateway ne connaît plus que
:class:`llm_gateway.core.models.AgentItem` (un ``agent_id`` et des champs libres) ; c'est ce
module qui dit ce qu'un persona doit porter pour que les templates mobilité le rendent.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentSpec(BaseModel):
    """Un persona dans un lot de décision (itinéraire, perception, réflexion).

    ``extra="ignore"`` : un champ inconnu est perdu en silence, comme avant le découpage.
    Déclarer le champ ici est la seule façon de le faire voyager jusqu'au template.
    """

    model_config = ConfigDict(extra="ignore")

    agent_id: str
    perception: str
    destination: str | None = None
    destination_zone: str | None = None
    departure_time: str | None = None
    departure_timestamp: float | None = None  # Unix, sert de score de priorité du lot
    current_time: str | None = None
    context: str | None = None
    history: list[str] = Field(default_factory=list)
    trajectories: list[dict[str, Any]] = Field(default_factory=list)
    goal: str | None = None
    constraints: str | None = None
    feeling: str | None = None
    # Mode interrogé par l'enquête du soir (ticket 095, lot B). UN prompt par mode, le mode
    # nommé et les autres jamais cités ; absent, c'est le prompt des PRIORITÉS, qui ne nomme
    # aucun mode. Déclaré ici parce que `extra="ignore"` jette en silence tout champ inconnu :
    # sans cette ligne, le gabarit recevrait un mode vide et poserait les six questions dans le
    # vide, sans qu'aucune erreur ne le dise.
    mode_interroge: str | None = None
    # Le texte de l'événement jugé (ticket 100, lot 3) — l'article lu ou le choc subi. MÊME
    # LEÇON que `mode_interroge` ci-dessus, et elle a été repayée le 2026-09-22 : sans cette
    # ligne, `extra="ignore"` jetait le texte en silence et le gabarit demandait à l'agent de
    # juger une page blanche. Le modèle répondait `negligible` — ce qui était la bonne réponse
    # à la question qu'on lui posait vraiment. Quinze appels sur quinze, sans une erreur.
    evenement: str | None = None
    # Ticket 111 — le relais au foyer. Même leçon, déclarée d'avance cette fois : l'article lu
    # et la fiche de chaque autre membre du foyer. Sans ces deux lignes, le lecteur recevrait
    # une page blanche et un foyer vide, et répondrait qu'il n'a rien à dire à personne.
    article: str | None = None
    membres: list[dict[str, Any]] = Field(default_factory=list)
    # Anticipation de la chaîne de la journée (ticket 014).
    day_outlook: str | None = None            # météo des tranches restantes du jour
    agenda: list[str] = Field(default_factory=list)  # trajets restants (agenda glissant)


def departure_priority(items: Sequence[BaseModel]) -> float | None:
    """Score de priorité d'un lot = plus petit ``departure_timestamp`` ; None si aucun."""
    stamps = [
        ts for ts in (getattr(a, "departure_timestamp", None) for a in items) if ts is not None
    ]
    return min(stamps) if stamps else None


__all__ = ["AgentSpec", "departure_priority"]
