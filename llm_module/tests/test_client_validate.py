"""
tests/test_client_validate.py — Tests unitaires pour LLMClient.validate_format.

Couvre toutes les catégories métier et les cas limites (résultats vides, champs manquants).
Aucun appel HTTP — teste uniquement la logique de validation locale.
"""

import pytest

from llm_module.client import LLMClient


@pytest.fixture
def client():
    return LLMClient()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _response(agents, status="success"):
    return {"status": status, "result": agents}


# ---------------------------------------------------------------------------
# itinary_multi_agent
# ---------------------------------------------------------------------------

class TestValidateItinaryMultiAgent:
    CATEGORY = "itinary_multi_agent"

    def test_valid_full(self, client):
        data = _response([
            {"agent_id": "a1", "chosen_index": 0, "mode": "bus", "reason": "fast"},
        ])
        assert client.validate_format(data, self.CATEGORY) is True

    def test_multiple_valid_agents(self, client):
        data = _response([
            {"agent_id": "a1", "chosen_index": 0, "mode": "car",  "reason": "convenient"},
            {"agent_id": "a2", "chosen_index": 1, "mode": "train", "reason": "eco"},
        ])
        assert client.validate_format(data, self.CATEGORY) is True

    def test_missing_chosen_index(self, client):
        data = _response([{"agent_id": "a1", "mode": "bus", "reason": "fast"}])
        assert client.validate_format(data, self.CATEGORY) is False

    def test_none_chosen_index(self, client):
        data = _response([{"agent_id": "a1", "chosen_index": None, "mode": "bus", "reason": "fast"}])
        assert client.validate_format(data, self.CATEGORY) is False

    def test_missing_mode(self, client):
        data = _response([{"agent_id": "a1", "chosen_index": 0, "reason": "fast"}])
        assert client.validate_format(data, self.CATEGORY) is False

    def test_empty_mode(self, client):
        data = _response([{"agent_id": "a1", "chosen_index": 0, "mode": "", "reason": "fast"}])
        assert client.validate_format(data, self.CATEGORY) is False

    def test_missing_reason(self, client):
        data = _response([{"agent_id": "a1", "chosen_index": 0, "mode": "bus"}])
        assert client.validate_format(data, self.CATEGORY) is False

    def test_chosen_index_zero_is_valid(self, client):
        # 0 est un index valide (falsy en Python, mais truthy check ne doit pas exclure 0)
        data = _response([{"agent_id": "a1", "chosen_index": 0, "mode": "bus", "reason": "ok"}])
        assert client.validate_format(data, self.CATEGORY) is True


# ---------------------------------------------------------------------------
# perception_filter
# ---------------------------------------------------------------------------

class TestValidatePerceptionFilter:
    CATEGORY = "perception_filter"

    def test_valid_summary(self, client):
        data = _response([{"agent_id": "a1", "summary": "A very detailed story about the commute."}])
        assert client.validate_format(data, self.CATEGORY) is True

    def test_summary_too_short(self, client):
        data = _response([{"agent_id": "a1", "summary": "Short"}])
        assert client.validate_format(data, self.CATEGORY) is False

    def test_summary_exactly_10_chars(self, client):
        data = _response([{"agent_id": "a1", "summary": "1234567890"}])
        assert client.validate_format(data, self.CATEGORY) is True

    def test_missing_summary(self, client):
        data = _response([{"agent_id": "a1"}])
        assert client.validate_format(data, self.CATEGORY) is False

    def test_empty_summary(self, client):
        data = _response([{"agent_id": "a1", "summary": ""}])
        assert client.validate_format(data, self.CATEGORY) is False

    def test_multiple_agents_all_valid(self, client):
        data = _response([
            {"agent_id": "a1", "summary": "Long enough story for agent one."},
            {"agent_id": "a2", "summary": "Long enough story for agent two."},
        ])
        assert client.validate_format(data, self.CATEGORY) is True

    def test_one_invalid_agent_fails_whole_response(self, client):
        data = _response([
            {"agent_id": "a1", "summary": "Long enough story for agent one."},
            {"agent_id": "a2", "summary": "Tiny"},
        ])
        assert client.validate_format(data, self.CATEGORY) is False


# ---------------------------------------------------------------------------
# stm_reflection
# ---------------------------------------------------------------------------

class TestValidateStmReflection:
    CATEGORY = "stm_reflection"

    def test_valid_reflection(self, client):
        data = _response([{"agent_id": "a1", "reflection": "Detailed reflection about the day..."}])
        assert client.validate_format(data, self.CATEGORY) is True

    def test_missing_reflection(self, client):
        data = _response([{"agent_id": "a1"}])
        assert client.validate_format(data, self.CATEGORY) is False

    def test_empty_reflection(self, client):
        data = _response([{"agent_id": "a1", "reflection": ""}])
        assert client.validate_format(data, self.CATEGORY) is False


# ---------------------------------------------------------------------------
# ltm_self_reflection
# ---------------------------------------------------------------------------

class TestValidateLtmSelfReflection:
    CATEGORY = "ltm_self_reflection"

    def test_valid_reflection(self, client):
        data = _response([{"agent_id": "a1", "reflection": "Long-term pattern analysis."}])
        assert client.validate_format(data, self.CATEGORY) is True

    def test_missing_reflection(self, client):
        data = _response([{"agent_id": "a1"}])
        assert client.validate_format(data, self.CATEGORY) is False


# ---------------------------------------------------------------------------
# Cas communs à toutes catégories
# ---------------------------------------------------------------------------

class TestValidateCommon:
    def test_empty_result_list(self, client):
        data = {"status": "success", "result": []}
        assert client.validate_format(data, "itinary_multi_agent") is False

    def test_missing_result_key(self, client):
        data = {"status": "success"}
        assert client.validate_format(data, "itinary_multi_agent") is False

    def test_result_is_none(self, client):
        data = {"status": "success", "result": None}
        assert client.validate_format(data, "itinary_multi_agent") is False

    def test_unknown_category_does_not_raise(self, client):
        # Catégorie inconnue : aucun champ n'est vérifié → valide tant que result non vide
        data = _response([{"agent_id": "a1", "anything": "value"}])
        assert client.validate_format(data, "unknown_category") is True
