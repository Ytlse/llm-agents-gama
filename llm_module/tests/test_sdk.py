"""
tests/test_sdk.py — Tests du SDK client typé (LLMGatewayClient / TaskResult).

Le gateway est simulé par un httpx.MockTransport : aucun serveur requis.
"""

import asyncio
import json

import httpx

from llm_module.core.models import TaskStatus
from llm_module.sdk import LLMGatewayClient, TaskResult, TaskTiming


def _gateway_mock(wait_response: dict, status_code: int = 200):
    """Transport qui répond au POST /tasks puis au GET /tasks/{id}/wait."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/tasks" and request.method == "POST":
            return httpx.Response(202, json={"task_id": "t-123", "status": "pending"})
        if request.url.path == "/tasks/t-123/wait":
            return httpx.Response(status_code, json=wait_response)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def _execute(client: LLMGatewayClient) -> TaskResult:
    async def run():
        try:
            return await client.execute({"category": "itinary_multi_agent", "agents": [{"agent_id": "a", "perception": "p"}]})
        finally:
            await client.aclose()
    return asyncio.run(run())


class TestExecute:
    def test_success_result_is_typed(self, tmp_path):
        transport = _gateway_mock({
            "task_id": "t-123",
            "status": "success",
            "created_at": "2026-07-07T10:00:00Z",
            "updated_at": "2026-07-07T10:00:01Z",
            "result": [{"agent_id": "a", "chosen_index": 2, "mode": "bus", "reason": "rapide"}],
            "provider_used": "groq_llama4",
            "timing_p5": {"P5_4_ms": 850.0},
        })
        client = LLMGatewayClient(transport=transport, dialogue_log_file=str(tmp_path / "dlg.log"))
        result = _execute(client)

        assert result.ok is True
        assert result.status is TaskStatus.SUCCESS
        assert result.task_id == "t-123"
        assert result.provider_used == "groq_llama4"
        assert result.agents[0].chosen_index == 2
        assert result.agents[0].mode == "bus"
        assert result.timing.timing_p5 == {"P5_4_ms": 850.0}
        assert result.timing.post_ms >= 0
        assert result.timing.wait_ms >= 0

    def test_extra_fields_accessible(self, tmp_path):
        # Les catégories de réflexion renvoient des champs hors schéma (extra=allow)
        transport = _gateway_mock({
            "status": "success",
            "created_at": "2026-07-07T10:00:00Z",
            "updated_at": "2026-07-07T10:00:01Z",
            "result": [{"agent_id": "a", "reflection": "bonne journée", "concepts": [["c1"]]}],
        })
        client = LLMGatewayClient(transport=transport, dialogue_log_file=str(tmp_path / "dlg.log"))
        result = _execute(client)
        assert getattr(result.agents[0], "reflection") == "bonne journée"
        assert getattr(result.agents[0], "concepts") == [["c1"]]

    def test_failed_task(self, tmp_path):
        transport = _gateway_mock({
            "status": "failed",
            "created_at": "2026-07-07T10:00:00Z",
            "updated_at": "2026-07-07T10:00:01Z",
            "result": None,
            "error": "Max retries dépassé",
        })
        client = LLMGatewayClient(transport=transport, dialogue_log_file=str(tmp_path / "dlg.log"))
        result = _execute(client)
        assert result.ok is False
        assert result.status is TaskStatus.FAILED
        assert "Max retries" in result.error

    def test_non_terminal_status_maps_to_failed_timeout(self, tmp_path):
        # Budget /wait épuisé : le gateway renvoie l'état courant (pending)
        transport = _gateway_mock({
            "status": "pending",
            "created_at": "2026-07-07T10:00:00Z",
            "updated_at": "2026-07-07T10:00:00Z",
        })
        client = LLMGatewayClient(transport=transport, dialogue_log_file=str(tmp_path / "dlg.log"))
        result = _execute(client)
        assert result.ok is False
        assert result.error == "Timeout expiré"

    def test_gateway_5xx_on_wait(self, tmp_path):
        transport = _gateway_mock({}, status_code=503)
        client = LLMGatewayClient(transport=transport, dialogue_log_file=str(tmp_path / "dlg.log"))
        result = _execute(client)
        assert result.ok is False
        assert "Gateway error 503" in result.error

    def test_dialogue_log_written(self, tmp_path):
        log_file = tmp_path / "dlg.log"
        transport = _gateway_mock({
            "status": "success",
            "created_at": "2026-07-07T10:00:00Z",
            "updated_at": "2026-07-07T10:00:01Z",
            "result": [{"agent_id": "a", "mode": "bus"}],
        })
        client = LLMGatewayClient(transport=transport, dialogue_log_file=str(log_file))
        _execute(client)
        content = log_file.read_text(encoding="utf-8")
        assert "REQUEST (Payload)" in content
        assert "bus" in content


class TestTaskResultModel:
    def test_ok_requires_success_and_agents(self):
        assert TaskResult(status=TaskStatus.SUCCESS).ok is False
        assert TaskResult(status=TaskStatus.FAILED).ok is False

    def test_default_timing(self):
        t = TaskTiming()
        assert t.post_ms == 0.0 and t.wait_ms == 0.0 and t.timing_p5 is None


class TestBackpressure:
    def test_alarm_arms_and_success_disarms(self):
        client = LLMGatewayClient(backpressure_max_inflight=20)
        # Sous le seuil d'alarme : rien d'armé
        for _ in range(client._FAILURE_ALARM_THRESHOLD - 1):
            client._observe(TaskResult(status=TaskStatus.FAILED, error="boom"),
                            {"category": "c"}, "c", 0.0, 0.0)
        assert client._backpressure_active is False
        # Au seuil : backpressure armée
        client._observe(TaskResult(status=TaskStatus.FAILED, error="boom"),
                        {"category": "c"}, "c", 0.0, 0.0)
        assert client._backpressure_active is True
        # Une réponse réussie désarme
        client._observe(TaskResult(status=TaskStatus.SUCCESS, agents=[]),
                        {"category": "c"}, "c", 0.0, 0.0)
        # agents=[] → not ok ; forçons un vrai succès
        from llm_module.core.models import AgentResponse
        client._observe(TaskResult(status=TaskStatus.SUCCESS, agents=[AgentResponse(agent_id="a")]),
                        {"category": "c"}, "c", 0.0, 0.0)
        assert client._backpressure_active is False

    def test_drain_waits_until_below_threshold(self):
        async def run():
            client = LLMGatewayClient(backpressure_max_inflight=20, backpressure_release_ratio=0.2)  # seuil=4
            client._backpressure_active = True
            client._inflight = 20
            released = {"done": False}

            async def waiter():
                await client._await_backpressure_drain()
                released["done"] = True

            t = asyncio.create_task(waiter())
            await asyncio.sleep(0.6)
            assert released["done"] is False  # pile pleine → toujours suspendu
            client._inflight = 4               # draine sous le seuil
            await asyncio.sleep(0.7)
            assert released["done"] is True
            assert client._backpressure_active is False
            await t

        asyncio.run(run())


class TestCircuitBreaker:
    """Disjoncteur : après N échecs consécutifs, les soumissions sont SUSPENDUES
    (aucune décision dégradée — on attend le rétablissement) ; l'un des appelants
    suspendus devient périodiquement la sonde qui referme le circuit au premier succès."""

    @staticmethod
    def _failing_transport(counter: dict):
        def handler(request: httpx.Request) -> httpx.Response:
            counter["requests"] += 1
            if request.url.path == "/tasks" and request.method == "POST":
                return httpx.Response(202, json={"task_id": "t-123", "status": "pending"})
            return httpx.Response(200, json={"status": "failed", "error": "Providers saturés"})
        return httpx.MockTransport(handler)

    @staticmethod
    def _success_transport(counter: dict):
        def handler(request: httpx.Request) -> httpx.Response:
            counter["requests"] += 1
            if request.url.path == "/tasks" and request.method == "POST":
                return httpx.Response(202, json={"task_id": "t-123", "status": "pending"})
            return httpx.Response(200, json={
                "status": "success",
                "result": [{"agent_id": "a", "chosen_index": 0}],
            })
        return httpx.MockTransport(handler)

    def test_opens_after_threshold_and_suspends_submissions(self, tmp_path):
        async def run():
            counter = {"requests": 0}
            client = LLMGatewayClient(
                transport=self._failing_transport(counter),
                dialogue_log_file=None,
                circuit_failure_threshold=3,
                circuit_probe_interval=3600.0,
            )
            for _ in range(3):
                result = await client.execute({"category": "c", "agents": []})
                assert result.ok is False
            assert client.circuit_open is True
            requests_before = counter["requests"]

            # Circuit ouvert, sonde pas encore due : la soumission est SUSPENDUE
            # (elle attend le rétablissement) — aucune requête HTTP, aucun échec rendu.
            waiter = asyncio.create_task(client.execute({"category": "c", "agents": []}))
            await asyncio.sleep(0.5)
            assert waiter.done() is False
            assert counter["requests"] == requests_before
            assert client._circuit_waiters == 1

            # Rétablissement (comme si la sonde d'un autre appel avait réussi) :
            # la soumission suspendue repart sur le chemin nominal.
            client._transport = self._success_transport(counter)
            await client.aclose()  # force la reconstruction du client HTTP
            client._circuit_open_since = None
            result = await waiter
            assert result.ok is True
            assert client._circuit_waiters == 0
            await client.aclose()

        asyncio.run(run())

    def test_probe_closes_circuit_on_success(self, tmp_path):
        async def run():
            counter = {"requests": 0}
            client = LLMGatewayClient(
                transport=self._failing_transport(counter),
                dialogue_log_file=None,
                circuit_failure_threshold=2,
                circuit_probe_interval=0.0,  # sonde immédiatement autorisée
            )
            for _ in range(2):
                await client.execute({"category": "c", "agents": []})
            assert client.circuit_open is True

            # Le gateway est rétabli : l'appel suivant devient la sonde, traverse,
            # obtient sa VRAIE décision LLM et referme le circuit.
            await client.aclose()  # force la reconstruction du client HTTP au prochain appel
            client._transport = self._success_transport(counter)
            result = await client.execute({"category": "c", "agents": []})
            assert result.ok is True
            assert client.circuit_open is False
            await client.aclose()

        asyncio.run(run())

    def test_failed_probe_keeps_circuit_open_and_reschedules(self):
        async def run():
            counter = {"requests": 0}
            client = LLMGatewayClient(
                transport=self._failing_transport(counter),
                dialogue_log_file=None,
                circuit_failure_threshold=2,
                circuit_probe_interval=3600.0,
            )
            for _ in range(2):
                await client.execute({"category": "c", "agents": []})
            assert client.circuit_open is True

            # Sonde forcée (comme si l'intervalle était écoulé) : elle échoue →
            # le circuit reste ouvert et la prochaine sonde est repoussée. L'appel
            # sondeur rend son échec (il sera re-suspendu à sa prochaine soumission).
            client._circuit_next_probe_at = 0.0
            requests_before = counter["requests"]
            result = await client.execute({"category": "c", "agents": []})
            assert result.ok is False
            assert counter["requests"] > requests_before  # la sonde a bien traversé
            assert client.circuit_open is True
            import time as _time
            assert client._circuit_next_probe_at > _time.monotonic()
            await client.aclose()

        asyncio.run(run())

    def test_network_error_counts_as_failure(self):
        # Gateway injoignable (ConnectError) : sans comptage, ni l'alarme ni le
        # disjoncteur ne se déclenchaient sur une coupure franche.
        async def run():
            def handler(request: httpx.Request) -> httpx.Response:
                raise httpx.ConnectError("connection refused")

            client = LLMGatewayClient(
                transport=httpx.MockTransport(handler),
                dialogue_log_file=None,
                circuit_failure_threshold=2,
                circuit_probe_interval=3600.0,
            )
            for _ in range(2):
                result = await client.execute({"category": "c", "agents": []})
                assert result.ok is False
                assert "injoignable" in result.error
            assert client.circuit_open is True
            await client.aclose()

        asyncio.run(run())

    def test_disabled_when_threshold_zero(self):
        async def run():
            counter = {"requests": 0}
            client = LLMGatewayClient(
                transport=self._failing_transport(counter),
                dialogue_log_file=None,
                circuit_failure_threshold=0,
            )
            for _ in range(15):
                await client.execute({"category": "c", "agents": []})
            assert client.circuit_open is False
            await client.aclose()

        asyncio.run(run())
