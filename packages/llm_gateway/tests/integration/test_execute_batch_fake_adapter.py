"""Le chemin complet d'un lot dans le worker, sans Celery, sans Redis, sans réseau.

`_execute_batch` : validation des items par la catégorie, rendu du prompt, appel de l'adapter
(FakeAdapter), réalignement des agent_id, hook `observe`, démultiplexage, persistance.
"""
from __future__ import annotations

import pytest

import llm_gateway.worker.task_worker as tw
from llm_gateway.core.models import AgentItem, LLMRequest, Task, TaskStatus
from llm_gateway.testing import FakeAdapter


@pytest.fixture
def fake_adapter(monkeypatch) -> FakeAdapter:
    fake = FakeAdapter()
    monkeypatch.setattr(tw, "get_adapter", lambda name: fake)
    return fake


def _tasks(*agent_ids: str) -> list[Task]:
    return [
        Task(request=LLMRequest(category="echo", agents=[AgentItem(agent_id=aid, texte=f"item {aid}")]))
        for aid in agent_ids
    ]


def test_un_lot_de_deux_taches_est_demultiplexe(memory_runtime, fake_adapter):
    tasks = _tasks("a1", "a2")
    for t in tasks:
        memory_runtime.store.save_sync(t)

    tw._execute_batch(memory_runtime, tasks, "batch_test", "fake")

    for t in tasks:
        saved = memory_runtime.store.get_sync(t.task_id)
        assert saved.status == TaskStatus.SUCCESS
        assert [a.agent_id for a in saved.result] == [t.request.agents[0].agent_id]
        assert saved.provider_used == "fake"
        assert saved.timing_p5["provider"] == "fake"
    assert len(fake_adapter.calls) == 1, "deux tâches, un seul appel LLM : c'est le micro-batching"
    rendered = "\n".join(m.content or "" for m in fake_adapter.calls[0].messages)
    assert "item a1" in rendered and "item a2" in rendered, "le template a bien reçu les champs libres"

    m = memory_runtime.metrics
    assert m.get("llm_calls_ok_total:fake") == 1
    assert m.get("prompts_sent_total:echo") == 1
    assert m.get("agents_batched_total:echo") == 2


def test_agent_id_mal_forme_est_realigne(memory_runtime, monkeypatch):
    fake = FakeAdapter(responder=lambda aid: {"agent_id": f"PERSONA {aid[-1]}", "summary": "s"})
    monkeypatch.setattr(tw, "get_adapter", lambda name: fake)
    (t,) = _tasks("ag_7")
    memory_runtime.store.save_sync(t)

    tw._execute_batch(memory_runtime, [t], "batch_realign", "fake")

    saved = memory_runtime.store.get_sync(t.task_id)
    assert saved.status == TaskStatus.SUCCESS
    assert saved.result[0].agent_id == "ag_7", "réaligné sur sa partie numérique"


def test_hook_observe_en_erreur_ne_fait_pas_echouer_le_lot(memory_runtime, fake_adapter):
    handle = memory_runtime.registry.get("echo")
    boom = handle.spec.__class__(name="echo", observe=lambda ctx: 1 / 0)
    object.__setattr__(handle, "spec", boom)   # dataclass frozen : on force pour le test
    (t,) = _tasks("a1")
    memory_runtime.store.save_sync(t)

    tw._execute_batch(memory_runtime, [t], "batch_observe", "fake")

    assert memory_runtime.store.get_sync(t.task_id).status == TaskStatus.SUCCESS
