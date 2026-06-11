"""
tests/test_prompt_manager.py — Tests unitaires pour prompts/manager.py.

Couvre : PromptManager._split_sections, get_output_schema, render.
Pas besoin de Redis ni de LLM — teste uniquement la logique de templating.
"""

import pytest

from llm_module.prompts.manager import PromptManager, _SECTION_SYSTEM, _SECTION_USER
from llm_module.settings.models import AgentSpec, InternalMessage


# Fixture : instance isolée (on évite le singleton pour les tests)
@pytest.fixture
def manager():
    return PromptManager()


# ---------------------------------------------------------------------------
# get_output_schema
# ---------------------------------------------------------------------------

class TestGetOutputSchema:
    KNOWN_CATEGORIES = [
        "itinary_multi_agent",
        "perception_filter",
        "stm_reflection",
        "ltm_self_reflection",
    ]

    def test_known_categories_return_dicts(self, manager):
        for cat in self.KNOWN_CATEGORIES:
            schema = manager.get_output_schema(cat)
            assert isinstance(schema, dict)
            assert "type" in schema

    def test_unknown_category_raises(self, manager):
        with pytest.raises(ValueError, match="Schéma inconnu"):
            manager.get_output_schema("non_existent_category")


# ---------------------------------------------------------------------------
# _split_sections
# ---------------------------------------------------------------------------

class TestSplitSections:
    def test_no_markers_returns_single_user_message(self, manager):
        text = "Hello world, this is the prompt."
        messages = manager._split_sections(text)
        assert len(messages) == 1
        assert messages[0].role == "user"
        assert messages[0].content == text

    def test_system_marker_only(self, manager):
        text = f"{_SECTION_SYSTEM}\nThis is the system instruction."
        messages = manager._split_sections(text)
        assert len(messages) == 1
        assert messages[0].role == "system"
        assert "system instruction" in messages[0].content

    def test_user_marker_only(self, manager):
        text = f"{_SECTION_USER}\nThis is the user message."
        messages = manager._split_sections(text)
        assert len(messages) == 1
        assert messages[0].role == "user"

    def test_system_then_user(self, manager):
        text = (
            f"{_SECTION_SYSTEM}\nSystem part.\n"
            f"{_SECTION_USER}\nUser part."
        )
        messages = manager._split_sections(text)
        assert len(messages) == 2
        assert messages[0].role == "system"
        assert messages[1].role == "user"
        assert "System part" in messages[0].content
        assert "User part" in messages[1].content

    def test_empty_section_is_skipped(self, manager):
        # Section USER sans contenu → ne doit pas générer de message vide
        text = f"{_SECTION_SYSTEM}\nSystem content.\n{_SECTION_USER}\n   "
        messages = manager._split_sections(text)
        assert len(messages) == 1
        assert messages[0].role == "system"

    def test_no_empty_content_in_result(self, manager):
        text = f"{_SECTION_SYSTEM}\nHello.\n{_SECTION_USER}\nWorld."
        messages = manager._split_sections(text)
        for m in messages:
            assert m.content
            assert m.content.strip()

    def test_returns_internal_message_objects(self, manager):
        text = f"{_SECTION_USER}\nSome content."
        messages = manager._split_sections(text)
        assert all(isinstance(m, InternalMessage) for m in messages)


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------

class TestRender:
    def _make_agent(self, agent_id="ag1"):
        return AgentSpec(agent_id=agent_id, perception="Test perception")

    def test_render_perception_filter_returns_messages(self, manager):
        agents = [self._make_agent("a1"), self._make_agent("a2")]
        messages = manager.render("perception_filter", agents, {})
        assert len(messages) >= 1
        # Au moins un message doit contenir les agent_ids
        all_content = " ".join(m.content for m in messages if m.content)
        assert "a1" in all_content or "a2" in all_content

    def test_render_itinary_multi_agent_has_system_message(self, manager):
        agent = AgentSpec(
            agent_id="a1",
            perception="38y, engineer",
            trajectories=[{"mode": "bus", "total_distance_m": 5000}],
        )
        messages = manager.render("itinary_multi_agent", [agent], {})
        roles = [m.role for m in messages]
        assert "system" in roles

    def test_render_unknown_category_raises(self, manager):
        with pytest.raises(ValueError, match="Erreur de template"):
            manager.render("unknown_category", [self._make_agent()], {})

    def test_render_includes_schema_in_output(self, manager):
        agent = self._make_agent()
        messages = manager.render("perception_filter", [agent], {})
        all_content = " ".join(m.content for m in messages if m.content)
        # Le schéma JSON est injecté dans le template → "agents" doit apparaître
        assert "agents" in all_content

    def test_render_context_injected_when_provided(self, manager):
        agent = AgentSpec(
            agent_id="a1",
            perception="student",
            trajectories=[{"mode": "bus", "total_distance_m": 2000}],
        )
        messages = manager.render(
            "itinary_multi_agent",
            [agent],
            {"context": "heavy_rain_today"},
        )
        all_content = " ".join(m.content for m in messages if m.content)
        assert "heavy_rain_today" in all_content
