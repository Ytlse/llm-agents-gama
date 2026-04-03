"""
models.py — Modèles de données Pydantic partagés entre tous les modules.
Séparer les modèles du reste évite les imports circulaires.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


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

class AgentSpec(BaseModel):
    """Décrit un agent individuel inclus dans le prompt batch."""
    agent_id: str
    role: str
    context: Optional[str] = None


class LLMRequest(BaseModel):
    """Corps de la requête POST /tasks."""
    category: str = Field(..., description="Catégorie de la requête (selection itinéraire, ...)")
    agents: List[AgentSpec] = Field(..., min_length=1, description="Liste des agents à simuler")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Paramètres additionnels pour le prompt")
    # Optionnel : forcer un fournisseur spécifique (contourne le load balancer)
    force_provider: Optional[str] = None


# ---------------------------------------------------------------------------
# Tâche interne (API → Broker → Worker)
# ---------------------------------------------------------------------------

class Task(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus = TaskStatus.PENDING
    request: LLMRequest
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    result: Optional[List[AgentResponse]] = None
    error: Optional[str] = None

    # Métriques de télémétrie (remplies par le Worker)
    provider_used: Optional[str] = None
    latency_ms: Optional[float] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None


# ---------------------------------------------------------------------------
# Sortie structurée (LLM → Worker)
# ---------------------------------------------------------------------------

class AgentResponse(BaseModel):
    """Un élément du tableau JSON retourné par le LLM."""
    agent_id: str
    reponse: str


class LLMOutput(BaseModel):
    """Enveloppe validée à la réception de la réponse LLM."""
    agents: List[AgentResponse]


# ---------------------------------------------------------------------------
# Réponse API (Worker → client via polling)
# ---------------------------------------------------------------------------

class TaskStatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    result: Optional[List[AgentResponse]] = None
    error: Optional[str] = None
    # Métriques exposées au client (utile pour debug / monitoring)
    provider_used: Optional[str] = None
    latency_ms: Optional[float] = None


# ---------------------------------------------------------------------------
# Interface commune entre modules (adapters ↔ load_balancer ↔ worker)
# ---------------------------------------------------------------------------

class InternalMessage(BaseModel):
    """Format normalisé transmis aux adapters."""
    role: str   # "system" | "user" | "assistant"
    content: str


class InternalRequest(BaseModel):
    """Ce que le Worker passe à l'Adapter sélectionné."""
    provider: str
    model: Optional[str] = None          # Si None, utilise le default du provider
    messages: List[InternalMessage]
    response_schema: Dict[str, Any]      # JSON Schema injecté pour Structured Output
    temperature: float = 0.7
    max_tokens: int = 4096
