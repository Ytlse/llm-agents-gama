"""
core/models.py — Modèles de données Pydantic partagés entre tous les modules.

Domaine pur : aucun I/O, aucun import redis/celery/httpx/fastapi.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Énumérations
# ---------------------------------------------------------------------------

class TaskStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    SUCCESS   = "success"
    FAILED    = "failed"


# ---------------------------------------------------------------------------
# Requête entrante (client → API Gateway)
# ---------------------------------------------------------------------------

class AgentItem(BaseModel):
    """Un item d'un lot : un identifiant, et tout ce que la catégorie voudra y lire.

    Le gateway ne connaît que ``agent_id`` (démultiplexage des réponses). Les autres champs
    sont conservés tels quels (``extra="allow"``) et validés par le modèle d'item de la
    catégorie (cf. ``ports.category.CategorySpec.item_model``) au moment du rendu.
    """
    model_config = ConfigDict(extra="allow")

    agent_id: str

    @field_validator("agent_id", mode="before")
    @classmethod
    def _agent_id_as_str(cls, v: Any) -> Any:
        return str(v) if isinstance(v, int) else v


class LLMRequest(BaseModel):
    """Corps de la requête POST /tasks."""
    category: str = Field(..., description="Catégorie de la requête (selection itinéraire, ...)")
    agents: list[AgentItem] = Field(..., min_length=1, description="Items du lot (un persona, un document…), chacun avec son agent_id")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Paramètres additionnels pour le prompt")
    # Optionnel : forcer un fournisseur spécifique (contourne le load balancer)
    force_provider: str | None = None
    # Optionnel : TPM minimum requis — le load balancer exclut les providers en dessous de ce seuil
    min_tpm_required: int | None = None
    context: str | None = Field(default=None, description="Contexte global de la ville (ex: trafic, météo)")


# ---------------------------------------------------------------------------
# Tâche interne (API → Broker → Worker)
# ---------------------------------------------------------------------------

_FALLBACK_PRIORITY_SCORE: float = 9_999_999_999.0


class Task(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus = TaskStatus.PENDING
    request: LLMRequest
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    result: list[AgentResponse] | None = None
    error: str | None = None
    # Unix timestamp of earliest agent departure — lower score = higher priority
    priority_score: float = _FALLBACK_PRIORITY_SCORE

    # Métriques de télémétrie (remplies par le Worker)
    provider_used: str | None = None
    latency_ms: float | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    # Pipeline timing segments measured inside the worker (P4_4, P5_1, P5_3, P5_4, P5_5)
    timing_p5: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Sortie structurée (LLM → Worker)
# ---------------------------------------------------------------------------

class OptionProbability(BaseModel):
    """Probabilité, pour une option de trajet, que le persona la retienne.

    Le LLM note **toutes** les options proposées (somme = 100) au lieu d'en choisir
    une : c'est un tirage aléatoire dans cette distribution qui produit la décision
    (cf. mobility_llm.mode_choice). `probability` est accepté en % comme en
    fraction — la normalisation aval rend l'échelle indifférente.
    """
    model_config = ConfigDict(extra="allow")

    index: int | None = None
    mode: str | None = None
    probability: float | None = None
    # Justification PAR OPTION (2026-08-26). Portée auparavant par `AgentResponse.reason`,
    # une seule phrase pour tout le persona : elle ne disait pas pourquoi telle option
    # perdait contre telle autre. `extra="allow"` la tolérait déjà — on la déclare pour
    # que le contrat soit dans le modèle et non seulement dans le prompt.
    reason: str | None = None

    @field_validator("probability", mode="before")
    @classmethod
    def coerce_probability(cls, v: Any) -> Any:
        """Tolère « 40 % » ou « 0,4 » : certains modèles habillent leurs nombres."""
        if isinstance(v, str):
            cleaned = v.strip().replace("%", "").replace(",", ".")
            try:
                return float(cleaned)
            except ValueError:
                return None
        return v


class AgentResponse(BaseModel):
    """Un élément du tableau JSON retourné par le LLM."""
    model_config = ConfigDict(extra="allow")

    agent_id: str | int
    # Distribution sur les options proposées — format courant pour la catégorie
    # itinary_multi_agent.
    probabilities: list[OptionProbability] | None = None
    # `chosen_index`/`mode` : ancien format (le LLM choisissait une option). Conservés
    # pour rester capable de relire une réponse ou un cache produits avant la bascule.
    chosen_index: int | None = None
    mode: str | None = None
    reason: str | None = None
    summary: str | None = None

    @field_validator("agent_id")
    @classmethod
    def cast_agent_id_to_str(cls, v: Any) -> str:
        return str(v)


class LLMOutput(BaseModel):
    """Enveloppe validée à la réception de la réponse LLM."""
    agents: list[AgentResponse]


# ---------------------------------------------------------------------------
# Réponse API (Worker → client via polling)
# ---------------------------------------------------------------------------

class TaskStatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    result: list[AgentResponse] | None = None
    error: str | None = None
    # Métriques exposées au client (utile pour debug / monitoring)
    provider_used: str | None = None
    latency_ms: float | None = None
    timing_p5: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Interface commune entre modules (adapters ↔ load_balancer ↔ worker)
# ---------------------------------------------------------------------------

class InternalMessage(BaseModel):
    """Format normalisé transmis aux adapters."""
    role: str   # "system" | "user" | "assistant"
    content: str | None = None
    trajectories: list[dict[str, Any]] = []
    history: list[str] = []


class InternalRequest(BaseModel):
    """Ce que le Worker passe à l'Adapter sélectionné."""
    provider: str
    model: str | None = None          # Si None, utilise le default du provider
    messages: list[InternalMessage]
    response_schema: dict[str, Any]      # JSON Schema injecté pour Structured Output
    temperature: float = 0.7
    max_tokens: int = 8192
