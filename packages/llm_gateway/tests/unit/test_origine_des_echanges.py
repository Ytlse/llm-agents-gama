"""L'origine d'une requête signe l'échange dans le journal du worker (2026-09-24).

Le journal des échanges est écrit par le WORKER, commun à tous les clients : un bras de 20
agents a lu dans son `llm_exchanges.jsonl` 97 échanges d'une population de 1 000 agents servie
pendant qu'il tournait. Chaque client signe désormais ses requêtes ; un lot n'en mélange
jamais deux.
"""

import asyncio
import json

import httpx

from llm_gateway.core.batching import compute_batch_key
from llm_gateway.core.models import LLMRequest
from llm_gateway.sdk import LLMGatewayClient
from llm_gateway.telemetry.exchanges import ExchangeRecord


def _requete(**extra) -> LLMRequest:
    return LLMRequest(category="itinary_multi_agent", agents=[{"agent_id": "a"}], **extra)


def test_deux_origines_ne_partagent_pas_un_lot():
    assert compute_batch_key(_requete(origine="run_a")) != compute_batch_key(_requete(origine="run_b"))
    assert compute_batch_key(_requete(origine="run_a")) == compute_batch_key(_requete(origine="run_a"))


def test_l_enregistrement_porte_son_origine():
    rec = ExchangeRecord(
        task_id="b", provider="p", category="c", tokens_in=1, tokens_out=1,
        messages=[], response=[], origine="2026-09-24_11_14",
    )
    assert rec.to_json_dict()["origine"] == "2026-09-24_11_14"
    sans = ExchangeRecord(task_id="b", provider="p", category="c", tokens_in=1, tokens_out=1,
                          messages=[], response=[])
    assert sans.to_json_dict()["origine"] is None


def _soumis(payload: dict, **client_kw) -> dict:
    vus: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/tasks" and request.method == "POST":
            vus.append(json.loads(request.content))
            return httpx.Response(202, json={"task_id": "t-1", "status": "pending"})
        if request.url.path == "/tasks/t-1/wait":
            return httpx.Response(200, json={
                "task_id": "t-1", "status": "success",
                "created_at": "2026-09-24T10:00:00Z", "updated_at": "2026-09-24T10:00:01Z",
                "result": [{"agent_id": "a", "chosen_index": 0, "mode": "car", "reason": "r"}],
                "provider_used": "p",
            })
        return httpx.Response(404)

    client = LLMGatewayClient(transport=httpx.MockTransport(handler), **client_kw)

    async def run():
        try:
            await client.execute(payload)
        finally:
            await client.aclose()

    asyncio.run(run())
    return vus[0]


def test_le_client_signe_chaque_appel():
    payload = {"category": "stm_reflection", "agents": [{"agent_id": "a"}]}
    assert _soumis(payload, origine="2026-09-24_11_14")["origine"] == "2026-09-24_11_14"


def test_un_client_sans_origine_ne_pose_rien():
    payload = {"category": "stm_reflection", "agents": [{"agent_id": "a"}]}
    assert "origine" not in _soumis(payload)
