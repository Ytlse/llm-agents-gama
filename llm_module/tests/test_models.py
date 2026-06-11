"""
tests/test_models.py — Tests unitaires pour settings/models.py.

Couvre : AgentSpec, LLMRequest, Task, AgentResponse, LLMOutput, TaskStatus.
"""

import pytest
from pydantic import ValidationError

from llm_module.settings.models import (
    AgentResponse,
    AgentSpec,
    LLMOutput,
    LLMRequest,
    Task,
    TaskStatus,
    _FALLBACK_PRIORITY_SCORE,
)


# ---------------------------------------------------------------------------
# TaskStatus
# ---------------------------------------------------------------------------

class TestTaskStatus:
    def test_values(self):
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.SUCCESS == "success"
        assert TaskStatus.FAILED  == "failed"


# ---------------------------------------------------------------------------
# AgentSpec
# ---------------------------------------------------------------------------

class TestAgentSpec:
    def test_minimal_valid(self):
        a = AgentSpec(agent_id="ag1", perception="desc")
        assert a.agent_id == "ag1"
        assert a.history == []
        assert a.trajectories == []

    def test_full(self):
        a = AgentSpec(
            agent_id="ag2",
            perception="desc",
            destination="city center",
            departure_time="08:00",
            departure_timestamp=1_700_000_000.0,
            current_time="07:55",
            context="rush hour",
            history=["event1"],
            trajectories=[{"mode": "bus"}],
            goal="save time",
            constraints="no car",
            feeling="positive",
        )
        assert a.destination == "city center"
        assert a.departure_timestamp == 1_700_000_000.0
        assert len(a.history) == 1

    def test_missing_required_fields_raises(self):
        with pytest.raises(ValidationError):
            AgentSpec(agent_id="ag1")  # perception manquant

    def test_missing_agent_id_raises(self):
        with pytest.raises(ValidationError):
            AgentSpec(perception="desc")  # agent_id manquant


# ---------------------------------------------------------------------------
# LLMRequest
# ---------------------------------------------------------------------------

class TestLLMRequest:
    def _agent(self, agent_id="a1"):
        return {"agent_id": agent_id, "perception": "desc"}

    def test_minimal_valid(self):
        req = LLMRequest(category="itinary_multi_agent", agents=[self._agent()])
        assert req.category == "itinary_multi_agent"
        assert req.parameters == {}
        assert req.force_provider is None

    def test_empty_agents_raises(self):
        with pytest.raises(ValidationError):
            LLMRequest(category="itinary_multi_agent", agents=[])

    def test_multiple_agents(self):
        req = LLMRequest(
            category="perception_filter",
            agents=[self._agent("a1"), self._agent("a2")],
            force_provider="groq",
        )
        assert len(req.agents) == 2
        assert req.force_provider == "groq"

    def test_context_field(self):
        req = LLMRequest(
            category="itinary_multi_agent",
            agents=[self._agent()],
            context="traffic jam on highway",
        )
        assert req.context == "traffic jam on highway"


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

class TestTask:
    def _request(self):
        return LLMRequest(
            category="itinary_multi_agent",
            agents=[{"agent_id": "a1", "perception": "desc"}],
        )

    def test_default_status_is_pending(self):
        t = Task(request=self._request())
        assert t.status == TaskStatus.PENDING

    def test_task_id_is_uuid(self):
        t = Task(request=self._request())
        assert len(t.task_id) == 36
        assert t.task_id.count("-") == 4

    def test_two_tasks_have_different_ids(self):
        t1 = Task(request=self._request())
        t2 = Task(request=self._request())
        assert t1.task_id != t2.task_id

    def test_fallback_priority_score(self):
        t = Task(request=self._request())
        assert t.priority_score == _FALLBACK_PRIORITY_SCORE

    def test_priority_score_override(self):
        t = Task(request=self._request(), priority_score=1234.5)
        assert t.priority_score == 1234.5

    def test_result_and_error_none_by_default(self):
        t = Task(request=self._request())
        assert t.result is None
        assert t.error is None


# ---------------------------------------------------------------------------
# AgentResponse
# ---------------------------------------------------------------------------

class TestAgentResponse:
    def test_agent_id_cast_to_str(self):
        a = AgentResponse(agent_id=42)
        assert a.agent_id == "42"
        assert isinstance(a.agent_id, str)

    def test_string_agent_id_unchanged(self):
        a = AgentResponse(agent_id="ag_marc")
        assert a.agent_id == "ag_marc"

    def test_optional_fields_default_none(self):
        a = AgentResponse(agent_id="a1")
        assert a.chosen_index is None
        assert a.mode is None
        assert a.reason is None
        assert a.summary is None

    def test_full_itinary_response(self):
        a = AgentResponse(agent_id="a1", chosen_index=2, mode="bus", reason="cheaper")
        assert a.chosen_index == 2
        assert a.mode == "bus"

    def test_extra_fields_allowed(self):
        a = AgentResponse(agent_id="a1", reflection="some text")
        assert a.reflection == "some text"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# LLMOutput
# ---------------------------------------------------------------------------

class TestLLMOutput:
    def test_valid_agents_list(self):
        out = LLMOutput(agents=[AgentResponse(agent_id="a1")])
        assert len(out.agents) == 1

    def test_empty_agents_valid(self):
        out = LLMOutput(agents=[])
        assert out.agents == []
