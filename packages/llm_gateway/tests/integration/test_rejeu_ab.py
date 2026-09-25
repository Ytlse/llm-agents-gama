"""Rejeu à prompt exact : le bras témoin reçoit les réponses du bras traité tant que ses prompts
sont les mêmes, sans appel au fournisseur.

Le 2026-09-25, les deux bras de l'A/B a09 V2 divergeaient dès le premier soir : gemini-3.5
répondait autrement à des prompts identiques. Ces tests vérifient qu'un prompt déjà servi dans
un espace se ressert à l'identique, et que tout ce qui n'est pas ce prompt-là part au fournisseur.
"""
from __future__ import annotations

import json

import httpx
import pytest

import llm_gateway.worker.task_worker as tw
from llm_gateway.api.app import create_app
from llm_gateway.config import Settings
from llm_gateway.core.models import AgentItem, LLMRequest, Task, TaskStatus
from llm_gateway.core.rejeu_ab import cle_rejeu, espace_valide
from llm_gateway.testing import FakeAdapter

ESPACE = "exp_mem_presse_a13_test"


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        telemetry={"workdir": str(tmp_path), "exchanges_enabled": True},
        learned_limits="none",
        rejeu={"dir": str(tmp_path / "rejeu_ab")},
    )


class _Dispatch:
    def __init__(self):
        self.appels = 0

    def delay(self, *_a):
        self.appels += 1

    def apply_async(self, **_k):
        self.appels += 1


@pytest.fixture
def dispatch(monkeypatch) -> _Dispatch:
    stub = _Dispatch()
    monkeypatch.setattr(tw, "process_batch_task", stub)
    return stub


@pytest.fixture
def fake_adapter(monkeypatch) -> FakeAdapter:
    fake = FakeAdapter()
    monkeypatch.setattr(tw, "get_adapter", lambda name: fake)
    return fake


@pytest.fixture
async def client(memory_deps, dispatch):
    app = create_app(memory_deps.settings, deps=memory_deps)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://gw") as c:
        yield c


def _requete(aid: str, texte: str, origine: str, espace: str | None = ESPACE, **parametres) -> dict:
    return {
        "category": "echo",
        "agents": [{"agent_id": aid, "texte": texte}],
        "parameters": parametres,
        "instances_admises": ["fake"],
        "origine": origine,
        **({"espace_rejeu": espace} if espace else {}),
    }


def _bras_traite(memory_runtime, *couples):
    """Le traité : un lot fusionné, servi par le fournisseur, consigné tâche par tâche."""
    tasks = [Task(request=LLMRequest(**_requete(a, t, f"{ESPACE}_treated"))) for a, t in couples]
    for t in tasks:
        memory_runtime.store.save_sync(t)
    tw._execute_batch(memory_runtime, tasks, "batch_traite", "fake")
    return tasks


async def test_le_temoin_recoit_la_reponse_du_traite_sans_appel(
    client, memory_runtime, fake_adapter, dispatch, memory_deps, tmp_path
):
    _bras_traite(memory_runtime, ("a1", "matin"), ("a2", "soir"))
    assert len(fake_adapter.calls) == 1
    assert memory_runtime.metrics.get("rejeu_ab_consigne_total:echo") == 2, "une par tâche, pas par lot"

    r = await client.post("/tasks", json=_requete("a1", "matin", f"{ESPACE}_control"))
    assert r.status_code == 202
    corps = r.json()
    assert corps["status"] == TaskStatus.SUCCESS, "servie avant même d'entrer en file"
    assert dispatch.appels == 0, "ni lot, ni créneau, ni appel"
    assert len(fake_adapter.calls) == 1

    rendu = (await client.get(f"/tasks/{corps['task_id']}/wait", params={"timeout": 1})).json()
    assert rendu["rejeu"] == ESPACE
    assert rendu["provider_used"] == "fake", "le fournisseur d'origine : le client refuse les substitutions"
    assert [a["agent_id"] for a in rendu["result"]] == ["a1"]
    assert memory_deps.metrics.get("rejeu_ab_servi_total:echo") == 1

    journal = (tmp_path / "llm_exchanges.jsonl").read_text(encoding="utf-8")
    assert '"provider": "rejeu_ab:fake"' in journal, "le journal consigne aussi la réponse resservie"
    assert f'"origine": "{ESPACE}_control"' in journal


async def test_un_prompt_qui_change_part_au_fournisseur(client, memory_runtime, fake_adapter, dispatch, memory_deps):
    _bras_traite(memory_runtime, ("a1", "matin"))
    r = await client.post("/tasks", json=_requete("a1", "matin — j'ai lu dans le journal", f"{ESPACE}_control"))
    assert r.json()["status"] == TaskStatus.PENDING
    assert dispatch.appels == 1
    assert memory_deps.metrics.get("rejeu_ab_absent_total:echo") == 1


async def test_un_parametre_qui_change_part_au_fournisseur(client, memory_runtime, fake_adapter, dispatch):
    _bras_traite(memory_runtime, ("a1", "matin"))
    r = await client.post("/tasks", json=_requete("a1", "matin", f"{ESPACE}_control", temperature=0.7))
    assert r.json()["status"] == TaskStatus.PENDING


async def test_un_autre_espace_ne_voit_rien(client, memory_runtime, fake_adapter, dispatch):
    _bras_traite(memory_runtime, ("a1", "matin"))
    r = await client.post("/tasks", json=_requete("a1", "matin", "autre_control", espace="autre_exp"))
    assert r.json()["status"] == TaskStatus.PENDING


async def test_sans_espace_rien_ne_change(client, memory_runtime, fake_adapter, dispatch, memory_deps):
    _bras_traite(memory_runtime, ("a1", "matin"))
    r = await client.post("/tasks", json=_requete("a1", "matin", "x", espace=None))
    assert r.json()["status"] == TaskStatus.PENDING
    assert memory_deps.metrics.get("rejeu_ab_absent_total:echo") == 0, "aucune recherche n'a eu lieu"


async def test_un_espace_hors_charset_est_refuse(client, dispatch):
    assert espace_valide("../../etc") is None
    assert espace_valide("exp.a_b-1") == "exp.a_b-1"
    r = await client.post("/tasks", json=_requete("a1", "matin", "x", espace="../../etc"))
    assert r.json()["status"] == TaskStatus.PENDING


def test_l_origine_n_entre_pas_dans_la_cle():
    """Elle nomme le bras, qui diffère par construction : si elle entrait, rien ne se resservirait."""
    traite = LLMRequest(**_requete("a1", "matin", f"{ESPACE}_treated"))
    temoin = LLMRequest(**_requete("a1", "matin", f"{ESPACE}_control"))
    messages = [{"role": "user", "content": "matin"}]
    assert cle_rejeu(traite, messages) == cle_rejeu(temoin, messages)
    autre = LLMRequest(**{**_requete("a1", "matin", "x"), "instances_admises": ["autre"]})
    assert cle_rejeu(autre, messages) != cle_rejeu(traite, messages), "le modèle, lui, compte"


def test_une_reponse_incomplete_n_est_pas_consignee(memory_runtime, monkeypatch, tmp_path):
    """Resservir une réponse où un agent manque la rendrait définitive."""
    fake = FakeAdapter(responder=lambda aid: {"agent_id": "inconnu", "summary": "s"})
    monkeypatch.setattr(tw, "get_adapter", lambda name: fake)
    _bras_traite(memory_runtime, ("a1", "matin"))
    assert not list((tmp_path / "rejeu_ab").rglob("*.json"))


def test_la_premiere_reponse_consignee_fait_foi(memory_runtime, monkeypatch, tmp_path):
    reponses = iter(["premiere", "seconde"])
    fake = FakeAdapter(responder=lambda aid: {"agent_id": aid, "summary": next(reponses)})
    monkeypatch.setattr(tw, "get_adapter", lambda name: fake)
    _bras_traite(memory_runtime, ("a1", "matin"))
    _bras_traite(memory_runtime, ("a1", "matin"))
    (fichier,) = (tmp_path / "rejeu_ab" / ESPACE).glob("*.json")
    assert json.loads(fichier.read_text())["agents"][0]["summary"] == "premiere"
