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


# ---------------------------------------------------------------------------
# Le champ qu'un gabarit lit doit exister sur le modèle d'item
# ---------------------------------------------------------------------------

def test_tout_champ_lu_par_un_gabarit_est_declare_sur_AgentSpec():
    """`extra="ignore"` jette en silence : un gabarit peut lire un champ qui n'arrive jamais.

    La panne a eu lieu deux fois. `mode_interroge` (ticket 095, lot B) posait six questions
    dans le vide. `evenement` (ticket 100, lot 3) demandait à l'agent de juger une page
    blanche : quinze appels sur quinze ont répondu `negligible`, sans une erreur nulle part,
    et le défaut s'est d'abord lu comme « le modèle n'utilise pas l'échelle ».

    Ce test regarde ce que les gabarits LISENT et le confronte à ce que le modèle DÉCLARE.
    Il ne peut pas prouver qu'un champ déclaré est rempli — mais il rend impossible la
    troisième occurrence de ce motif-là.
    """
    import re

    from mobility_llm.persona import AgentSpec
    from mobility_llm.prompts import CATEGORIES_DIR

    declares = set(AgentSpec.model_fields)
    manquants: dict[str, set[str]] = {}
    for gabarit in sorted(CATEGORIES_DIR.glob("*/template.md.j2")):
        lus = set(re.findall(r"\bagent\.([a-z_][a-z0-9_]*)", gabarit.read_text("utf-8")))
        if absents := lus - declares:
            manquants[gabarit.parent.name] = absents
    assert not manquants, (
        f"des gabarits lisent des champs qu'`AgentSpec` ne déclare pas : {manquants}. "
        f"`extra=\"ignore\"` les jettera en silence et le prompt partira amputé."
    )
