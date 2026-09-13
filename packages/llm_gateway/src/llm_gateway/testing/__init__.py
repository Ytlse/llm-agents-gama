"""testing — ce qu'un consommateur ou un test a besoin de brancher sans Redis ni réseau.

* les implémentations mémoire des ports (réexportées d'``infra.memory``) ;
* :func:`echo_bundle` : un bundle d'une catégorie ``echo`` qui renvoie chaque item, pour
  tester le gateway sans aucun métier ;
* :class:`FakeAdapter` : un adapter LLM déterministe qui répond au schéma demandé ;
* :func:`build_registry` : un registre construit à la main, sans entry point.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from llm_gateway.adapters.base import BaseAdapter
from llm_gateway.core.models import AgentResponse, InternalRequest, LLMOutput
from llm_gateway.infra.memory import (
    FileLearnedLimits,
    InMemoryBatchQueue,
    InMemoryLearnedLimits,
    InMemoryMetricsSink,
    InMemoryRateLimiter,
    InMemoryTaskStore,
)
from llm_gateway.ports.category import CategoryBundle, CategorySpec
from llm_gateway.prompts.registry import CategoryRegistry

_HERE = Path(__file__).resolve().parent
ECHO_TEMPLATES_DIR = _HERE / "templates"
ECHO_SCHEMAS_FILE = _HERE / "echo_schemas.json"


def echo_bundle() -> CategoryBundle:
    """Un bundle minimal : la catégorie ``echo`` demande au modèle de répéter chaque item."""
    return CategoryBundle(
        name="echo",
        templates_dir=ECHO_TEMPLATES_DIR,
        schemas_file=ECHO_SCHEMAS_FILE,
        categories={"echo": CategorySpec(name="echo")},
    )


def build_registry(*bundles: CategoryBundle) -> CategoryRegistry:
    """Registre construit sans entry point ; par défaut le seul bundle ``echo``."""
    return CategoryRegistry(bundles or (echo_bundle(),))


class FakeAdapter(BaseAdapter):
    """Adapter sans réseau : rend une réponse valide pour chaque ``agent_id`` du prompt.

    ``responder`` permet à un test de fabriquer la réponse (``dict`` par agent) ; par défaut
    chaque agent reçoit ``{"agent_id": …, "summary": "echo"}``. Les compteurs de tokens sont
    la longueur des messages, pour que les métriques bougent.
    """

    provider_name = "fake"

    def __init__(self, responder: Callable[[str], dict[str, Any]] | None = None) -> None:
        super().__init__()
        self._responder = responder or (lambda aid: {"agent_id": aid, "summary": "echo"})
        self.calls: list[InternalRequest] = []

    def call(self, request: InternalRequest) -> tuple[LLMOutput, int, int]:
        self.calls.append(request)
        text = "\n".join(m.content or "" for m in request.messages)
        agent_ids = _agent_ids_in(text)
        agents = [AgentResponse.model_validate(self._responder(aid)) for aid in agent_ids]
        tokens_in = max(1, len(text) // 4)
        return LLMOutput(agents=agents), tokens_in, max(1, 8 * len(agents))

    def close(self) -> None:  # pas de client HTTP à fermer
        return None


_AGENT_ID_RE = re.compile(r"agent_id=([^\s|,;]+)")


def _agent_ids_in(text: str) -> list[str]:
    """Les ``agent_id=…`` écrits dans le prompt (template echo en tête de bloc, mobilité dans
    l'en-tête de chaque persona), dans l'ordre, sans doublon."""
    seen: dict[str, None] = {}
    for m in _AGENT_ID_RE.finditer(text):
        seen.setdefault(m.group(1).strip(), None)
    return list(seen)


def load_echo_schema() -> dict[str, Any]:
    return json.loads(ECHO_SCHEMAS_FILE.read_text(encoding="utf-8"))["echo"]


__all__ = [
    "ECHO_SCHEMAS_FILE",
    "ECHO_TEMPLATES_DIR",
    "FakeAdapter",
    "FileLearnedLimits",
    "InMemoryBatchQueue",
    "InMemoryLearnedLimits",
    "InMemoryMetricsSink",
    "InMemoryRateLimiter",
    "InMemoryTaskStore",
    "build_registry",
    "echo_bundle",
    "load_echo_schema",
]
