"""Ticket 092, lot A — la restriction d'instances est une propriété du CLIENT.

Le ticket 084 posait `instances_admises` sur le seul payload de décision. Les deux autres
appels du run (réflexion STM, auto-réflexion LTM) partaient sans restriction et étaient donc
servis en cascade — mesuré le 2026-09-16 : les décisions sur gemini 3.1, la consolidation
mémoire sur mistral. Pour une expérience dont l'objet EST la mémoire, l'objet mesuré était
fabriqué par un modèle non déclaré, sans qu'aucune ligne ne le signale.

Contrat : `specs/ticket_092/tests.md`.
"""

import asyncio

import httpx

from llm_gateway.sdk import LLMGatewayClient

ADMISES = ["google_gemini31_key1", "google_gemini31_key2"]


def _transport_qui_retient(vus: list[dict]) -> httpx.MockTransport:
    """Répond au cycle soumission/attente en retenant chaque payload soumis."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/tasks" and request.method == "POST":
            vus.append(httpx.Response(200, content=request.content).json())
            return httpx.Response(202, json={"task_id": "t-1", "status": "pending"})
        if request.url.path == "/tasks/t-1/wait":
            return httpx.Response(200, json={
                "task_id": "t-1",
                "status": "success",
                "created_at": "2026-09-16T10:00:00Z",
                "updated_at": "2026-09-16T10:00:01Z",
                "result": [{"agent_id": "a", "chosen_index": 0, "mode": "car", "reason": "r"}],
                "provider_used": "google_gemini31_key1",
            })
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def _payload(category: str) -> dict:
    return {
        "category": category,
        "agents": [{"agent_id": "899549", "perception": "p"}],
    }


def _soumettre(client: LLMGatewayClient, payload: dict) -> None:
    async def run():
        try:
            await client.execute(payload)
        finally:
            await client.aclose()

    asyncio.run(run())


def _soumis(payload: dict, *, admises=ADMISES) -> dict:
    vus: list[dict] = []
    client = LLMGatewayClient(transport=_transport_qui_retient(vus), instances_admises=admises)
    _soumettre(client, payload)
    assert vus, "aucun payload n'a été soumis"
    return vus[0]


class TestLaRestrictionCouvreLesTroisAppels:
    def test_A1_decision(self):
        assert _soumis(_payload("itinary_multi_agent"))["instances_admises"] == ADMISES

    def test_A2_reflexion_stm(self):
        """Le cas mesuré en production : c'est CELUI-CI qui partait chez mistral."""
        assert _soumis(_payload("stm_reflection"))["instances_admises"] == ADMISES

    def test_A3_auto_reflexion_ltm(self):
        assert _soumis(_payload("ltm_self_reflection"))["instances_admises"] == ADMISES


class TestCeQuiNeDoitPasChanger:
    def test_A4_un_payload_qui_porte_sa_restriction_n_est_pas_ecrase(self):
        """L'appelant qui sait ce qu'il veut reste maître : le client ne fait que combler."""
        propre = ["google_gemini35_key1"]
        soumis = _soumis({**_payload("itinary_multi_agent"), "instances_admises": propre})
        assert soumis["instances_admises"] == propre

    def test_A5_sans_restriction_aucune_cle_ajoutee(self):
        """Comportement rigoureusement identique à avant le ticket : la clé n'existe pas."""
        assert "instances_admises" not in _soumis(_payload("itinary_multi_agent"), admises=None)

    def test_A6_liste_vide_vaut_aucune_restriction(self):
        assert "instances_admises" not in _soumis(_payload("itinary_multi_agent"), admises=[])


class TestTracabilite:
    def test_A7_la_restriction_est_annoncee_au_demarrage(self):
        """Une restriction qui ne se voit pas dans le journal ne se vérifie pas après coup."""
        from loguru import logger

        lignes: list[str] = []
        puits = logger.add(lambda m: lignes.append(str(m)), level="INFO")
        try:
            LLMGatewayClient(instances_admises=ADMISES)
        finally:
            logger.remove(puits)
        trace = "\n".join(lignes)
        assert "google_gemini31_key1" in trace and "google_gemini31_key2" in trace
