"""Tests du persona mobilité (ex-AgentSpec de llm_module.core.models)."""

import pytest
from pydantic import ValidationError

from mobility_llm.persona import AgentSpec, departure_priority


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




class TestDeparturePriority:
    def test_min_des_departs(self):
        items = [AgentSpec(agent_id="a", perception="p", departure_timestamp=200.0),
                 AgentSpec(agent_id="b", perception="p", departure_timestamp=100.0)]
        assert departure_priority(items) == 100.0

    def test_aucun_depart_rend_none(self):
        assert departure_priority([AgentSpec(agent_id="a", perception="p")]) is None
