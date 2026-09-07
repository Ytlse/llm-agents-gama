"""L'API composée sur des ports en mémoire : validation par la catégorie, 422, 202, /health."""
from __future__ import annotations

import httpx
import pytest

from llm_gateway.api.app import create_app
from llm_gateway.core.models import _FALLBACK_PRIORITY_SCORE, TaskStatus


class _DispatchStub:
    """Remplace la tâche Celery : on note les dispatchs, on ne parle à aucun broker."""

    def __init__(self) -> None:
        self.delay_calls: list[tuple] = []
        self.apply_async_calls: list[dict] = []

    def delay(self, *args):
        self.delay_calls.append(args)

    def apply_async(self, **kwargs):
        self.apply_async_calls.append(kwargs)


@pytest.fixture
def dispatch(monkeypatch) -> _DispatchStub:
    import llm_gateway.worker.task_worker as tw
    stub = _DispatchStub()
    monkeypatch.setattr(tw, "process_batch_task", stub)
    return stub


@pytest.fixture
async def client(memory_deps, dispatch):
    app = create_app(memory_deps.settings, deps=memory_deps)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://gateway") as c:
        yield c


async def test_health_repond_avec_les_providers(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "providers" in r.json()


async def test_categorie_inconnue_est_refusee_en_422(client):
    r = await client.post("/tasks", json={"category": "inconnue", "agents": [{"agent_id": "a1"}]})
    assert r.status_code == 422
    assert "inconnue" in r.json()["detail"] and "echo" in r.json()["detail"]


async def test_item_sans_agent_id_est_refuse_en_422(client):
    r = await client.post("/tasks", json={"category": "echo", "agents": [{"texte": "x"}]})
    assert r.status_code == 422


async def test_tache_acceptee_stockee_et_dispatch_planifie(client, memory_deps, dispatch):
    r = await client.post("/tasks", json={"category": "echo", "agents": [{"agent_id": "a1", "texte": "bonjour"}]})
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == TaskStatus.PENDING
    task = await memory_deps.store.get(body["task_id"])
    assert task is not None
    assert task.request.agents[0].model_dump()["texte"] == "bonjour", "les champs libres voyagent"
    assert task.priority_score == _FALLBACK_PRIORITY_SCORE, "echo ne définit pas de priorité"
    assert dispatch.delay_calls or dispatch.apply_async_calls, "un dispatch a été planifié"

    r2 = await client.get(f"/tasks/{body['task_id']}")
    assert r2.status_code == 200 and r2.json()["status"] == "pending"


async def test_tache_inconnue_404(client):
    r = await client.get("/tasks/nope")
    assert r.status_code == 404
