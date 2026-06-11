"""
tests/test_adapter_base.py — Tests unitaires pour adapters/base.py.

Couvre :
  - BaseAdapter._parse_output : JSON valide, Markdown wrappé, fallback list, erreurs
  - BaseAdapter._raise_for_status : succès, 4xx, 5xx, 429 avec header ratelimit
  - extract_error_type : formats OpenAI/Groq et fallback
  - ProviderParseError, ProviderServerError, ProviderClientError : attributs

Aucun appel HTTP réel — les réponses HTTP sont mockées avec unittest.mock.
"""

import json
from unittest.mock import MagicMock

import pytest

from llm_module.adapters.base import (
    BaseAdapter,
    ProviderClientError,
    ProviderParseError,
    ProviderServerError,
    extract_error_type,
    register_adapter,
)
from llm_module.settings.models import InternalRequest, InternalMessage


# ---------------------------------------------------------------------------
# Adapteur minimal pour tester les méthodes concrètes de BaseAdapter
# ---------------------------------------------------------------------------

class _StubAdapter(BaseAdapter):
    provider_name = "stub"

    def call(self, request):
        raise NotImplementedError

_StubAdapter = register_adapter(_StubAdapter)


@pytest.fixture
def adapter():
    inst = _StubAdapter()
    inst._instance_name = "stub"
    return inst


# ---------------------------------------------------------------------------
# _parse_output — JSON valide
# ---------------------------------------------------------------------------

class TestParseOutputValid:
    def test_simple_agents_list(self, adapter):
        raw = json.dumps({"agents": [{"agent_id": "a1", "chosen_index": 0, "mode": "bus", "reason": "fast"}]})
        out = adapter._parse_output(raw)
        assert len(out.agents) == 1
        assert out.agents[0].agent_id == "a1"
        assert out.agents[0].chosen_index == 0

    def test_agent_id_as_integer_cast_to_str(self, adapter):
        raw = json.dumps({"agents": [{"agent_id": 42}]})
        out = adapter._parse_output(raw)
        assert out.agents[0].agent_id == "42"

    def test_multiple_agents(self, adapter):
        raw = json.dumps({
            "agents": [
                {"agent_id": "a1", "summary": "story one"},
                {"agent_id": "a2", "summary": "story two"},
            ]
        })
        out = adapter._parse_output(raw)
        assert len(out.agents) == 2

    def test_markdown_json_fenced_block(self, adapter):
        raw = '```json\n{"agents": [{"agent_id": "a1"}]}\n```'
        out = adapter._parse_output(raw)
        assert out.agents[0].agent_id == "a1"

    def test_markdown_fenced_no_language(self, adapter):
        raw = '```\n{"agents": [{"agent_id": "a1"}]}\n```'
        out = adapter._parse_output(raw)
        assert out.agents[0].agent_id == "a1"

    def test_fallback_list_key_when_no_agents_key(self, adapter):
        # Si "agents" est absent mais qu'il y a une autre clé de liste, on l'utilise
        raw = json.dumps({"results": [{"agent_id": "a1"}]})
        out = adapter._parse_output(raw)
        assert out.agents[0].agent_id == "a1"

    def test_json_embedded_in_text(self, adapter):
        # Texte parasite autour d'un JSON valide
        raw = 'Voici la réponse : {"agents": [{"agent_id": "a1"}]} fin.'
        out = adapter._parse_output(raw)
        assert out.agents[0].agent_id == "a1"


# ---------------------------------------------------------------------------
# _parse_output — Erreurs attendues
# ---------------------------------------------------------------------------

class TestParseOutputErrors:
    def test_invalid_json_raises_parse_error(self, adapter):
        with pytest.raises(ProviderParseError, match="JSONDecodeError"):
            adapter._parse_output("not json at all")

    def test_missing_agents_key_and_no_list_raises(self, adapter):
        raw = json.dumps({"foo": "bar", "baz": 42})
        with pytest.raises(ProviderParseError, match="agents.*absent"):
            adapter._parse_output(raw)

    def test_agents_not_a_list_raises(self, adapter):
        raw = json.dumps({"agents": "not a list"})
        with pytest.raises(ProviderParseError, match="TypeError"):
            adapter._parse_output(raw)

    def test_repetition_loop_raises(self, adapter):
        # 20 mots identiques consécutifs → boucle de répétition
        repeated = " ".join(["token"] * 25)
        raw = f'{{"agents": [{{"agent_id": "a1"}}], "junk": "{repeated}"}}'
        with pytest.raises(ProviderParseError, match="[Rr]epetition"):
            adapter._parse_output(raw)

    def test_parse_error_has_provider_and_raw(self, adapter):
        try:
            adapter._parse_output("{}")
        except ProviderParseError as e:
            assert e.provider == "stub"
            assert isinstance(e.raw, str)


# ---------------------------------------------------------------------------
# _raise_for_status
# ---------------------------------------------------------------------------

class TestRaiseForStatus:
    def _mock_response(self, status_code, text="", headers=None):
        resp = MagicMock()
        resp.status_code = status_code
        resp.text = text
        resp.headers = headers or {}
        return resp

    def test_2xx_does_not_raise(self, adapter):
        for code in (200, 201, 202, 204):
            adapter._raise_for_status(self._mock_response(code))  # no exception

    def test_5xx_raises_server_error(self, adapter):
        with pytest.raises(ProviderServerError) as exc_info:
            adapter._raise_for_status(self._mock_response(500, "Internal Server Error"))
        assert exc_info.value.status_code == 500
        assert exc_info.value.provider == "stub"

    def test_4xx_raises_client_error(self, adapter):
        with pytest.raises(ProviderClientError) as exc_info:
            adapter._raise_for_status(self._mock_response(401, "Unauthorized"))
        assert exc_info.value.status_code == 401

    def test_429_raises_client_error(self, adapter):
        with pytest.raises(ProviderClientError) as exc_info:
            adapter._raise_for_status(self._mock_response(429, "Too Many Requests"))
        assert exc_info.value.status_code == 429

    def test_429_captures_ratelimit_reset_header(self, adapter):
        headers = {"x-ratelimit-reset-requests": "45s"}
        with pytest.raises(ProviderClientError) as exc_info:
            adapter._raise_for_status(self._mock_response(429, "Too Many Requests", headers))
        assert exc_info.value.ratelimit_reset == "45s"

    def test_503_raises_server_error(self, adapter):
        with pytest.raises(ProviderServerError):
            adapter._raise_for_status(self._mock_response(503, "Service Unavailable"))


# ---------------------------------------------------------------------------
# extract_error_type
# ---------------------------------------------------------------------------

class TestExtractErrorType:
    def test_openai_groq_format(self):
        body = json.dumps({"error": {"message": "You exceeded your current quota, please check your plan"}})
        result = extract_error_type(body, 429)
        assert "quota" in result

    def test_google_format(self):
        body = json.dumps({"message": "Request rate limit exceeded"})
        result = extract_error_type(body, 429)
        assert "rate" in result.lower() or "request" in result.lower()

    def test_invalid_json_fallback(self):
        result = extract_error_type("not json", 500)
        assert result == "http 500"

    def test_empty_message_fallback(self):
        body = json.dumps({"error": {"message": ""}})
        result = extract_error_type(body, 503)
        assert result == "http 503"

    def test_truncated_to_10_words(self):
        long_msg = " ".join([f"word{i}" for i in range(20)])
        body = json.dumps({"error": {"message": long_msg}})
        result = extract_error_type(body, 400)
        assert len(result.split()) <= 10


# ---------------------------------------------------------------------------
# Exception attributes
# ---------------------------------------------------------------------------

class TestExceptionAttributes:
    def test_provider_server_error_attrs(self):
        e = ProviderServerError("groq", 500, "internal error", error_type="server_error")
        assert e.provider == "groq"
        assert e.status_code == 500
        assert e.error_type == "server_error"
        assert "groq" in str(e)

    def test_provider_client_error_attrs(self):
        e = ProviderClientError("openai", 401, "unauthorized", ratelimit_reset="60s")
        assert e.ratelimit_reset == "60s"

    def test_provider_parse_error_attrs(self):
        e = ProviderParseError("mistral", '{"bad": "json"}', "KeyError: agents absent")
        assert e.provider == "mistral"
        assert e.raw == '{"bad": "json"}'
        assert "mistral" in str(e)
