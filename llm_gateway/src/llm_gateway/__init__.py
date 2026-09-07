"""llm_gateway — gateway asynchrone multi-fournisseur LLM.

Façade publique. Tout ce qui n'est pas listé dans ``__all__`` est interne et peut changer
sans préavis ; les chemins profonds restent importables mais ne sont pas un contrat.

Usage côté client ::

    from llm_gateway import LLMGatewayClient, LLMRequest

    client = LLMGatewayClient(base_url="http://localhost:8000")
    result = await client.execute(LLMRequest(category="...", agents=[...]))

Usage côté service : ``create_app`` (API FastAPI) et ``create_celery_app`` (worker). Les
catégories de prompts sont apportées par des bundles enregistrés sous l'entry point
``llm_gateway.categories`` (cf. :mod:`llm_gateway.ports.category`).
"""
from __future__ import annotations

__version__ = "1.2.0"

from typing import TYPE_CHECKING, Any  # noqa: E402

if TYPE_CHECKING:  # pragma: no cover - pour les IDE et mypy uniquement
    from llm_gateway.core.models import (  # noqa: F401
        AgentItem,
        AgentResponse,
        LLMOutput,
        LLMRequest,
        Task,
        TaskStatus,
        TaskStatusResponse,
    )
    from llm_gateway.ports.category import (  # noqa: F401
        CategoryBundle,
        CategorySpec,
        ObserveContext,
    )
    from llm_gateway.sdk import LLMGatewayClient, TaskResult, TaskTiming  # noqa: F401

# Chaque nom public → le module qui le porte. Résolu au premier accès (PEP 562) : importer
# `llm_gateway` ne charge ni httpx ni prometheus_client ni FastAPI ; un processus n'embarque
# que ce qu'il utilise (l'API n'a pas les métriques du client, le worker n'a pas FastAPI).
_LAZY: dict[str, str] = {
    "AgentItem": "llm_gateway.core.models",
    "AgentResponse": "llm_gateway.core.models",
    "LLMOutput": "llm_gateway.core.models",
    "LLMRequest": "llm_gateway.core.models",
    "Task": "llm_gateway.core.models",
    "TaskStatus": "llm_gateway.core.models",
    "TaskStatusResponse": "llm_gateway.core.models",
    "CategoryBundle": "llm_gateway.ports.category",
    "CategorySpec": "llm_gateway.ports.category",
    "ObserveContext": "llm_gateway.ports.category",
    "LLMGatewayClient": "llm_gateway.sdk",
    "TaskResult": "llm_gateway.sdk",
    "TaskTiming": "llm_gateway.sdk",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY.get(name)
    if module_name is None:
        raise AttributeError(f"module 'llm_gateway' has no attribute {name!r}")
    import importlib

    value = getattr(importlib.import_module(module_name), name)
    globals()[name] = value  # mis en cache : un seul import
    return value


def create_app(*args: Any, **kwargs: Any) -> Any:
    """Fabrique de l'application FastAPI (import paresseux : FastAPI n'est chargé qu'ici)."""
    from llm_gateway.api.app import create_app as _create_app

    return _create_app(*args, **kwargs)


def create_celery_app(*args: Any, **kwargs: Any) -> Any:
    """Fabrique de l'application Celery (import paresseux : Celery n'est chargé qu'ici)."""
    from llm_gateway.worker.app import create_celery_app as _create

    return _create(*args, **kwargs)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY))


__all__ = [
    "__version__",
    *sorted(_LAZY),
    "create_app",
    "create_celery_app",
]
