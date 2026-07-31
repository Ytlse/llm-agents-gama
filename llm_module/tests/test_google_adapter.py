"""
tests/test_google_adapter.py — Instrumentation de l'adaptateur Google Gemini.

Couvre les trois grandeurs de diagnostic relevées sur chaque appel — tokens de
complétion, ``finishReason``, tokens de « pensée » — et le comportement qu'elles
commandent :
  - une complétion normale rend (LLMOutput, tokens_in, tokens_out) ;
  - les tokens de raisonnement sont COMPTÉS dans tokens_out (facturés et décomptés
    du plafond maxOutputTokens : les ignorer sous-estimait la consommation et
    masquait la cause d'une troncature) ;
  - une troncature MAX_TOKENS lève une ProviderServerError 503 dont le message
    porte les chiffres, et déclenche une ERREUR `[ALARME]` sur FRONT MONTANT
    (une seule par épisode, réarmée par le premier succès) ;
  - une réponse bloquée ou sans candidat reste une erreur client, chiffres à l'appui.

Aucun appel HTTP réel : le client httpx de l'adaptateur est remplacé par un double.
"""

import json
from unittest.mock import MagicMock

import httpx
import pytest

from llm_module.adapters.base import ProviderClientError, ProviderServerError
from llm_module.adapters.google_adapter import GoogleAdapter
from llm_module.settings.models import InternalRequest, InternalMessage


PAYLOAD = {"agents": [{"agent_id": "1", "chosen_index": 0, "mode": "foot",
                       "reason": "proche"}]}


def _response(*, finish="STOP", usage=None, text=None, with_content=True):
    """Réponse Gemini minimale, telle que la renvoie generateContent."""
    candidate = {"finishReason": finish}
    if with_content:
        body = text if text is not None else json.dumps(PAYLOAD)
        candidate["content"] = {"parts": [{"text": body}]}
    data = {"candidates": [candidate],
            "usageMetadata": usage if usage is not None
            else {"promptTokenCount": 100, "candidatesTokenCount": 42}}
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = data
    return resp


@pytest.fixture
def adapter(monkeypatch):
    inst = GoogleAdapter()
    inst._instance_name = "google_test"
    monkeypatch.setattr(inst, "_get_api_key", lambda: MagicMock(
        get_secret_value=lambda: "clef"))
    monkeypatch.setattr(inst, "_get_base_url", lambda: "https://example.invalid/v1beta")
    monkeypatch.setattr(inst, "_resolve_model", lambda _r: "gemini-test")
    return inst


def _wire(adapter, monkeypatch, response):
    client = MagicMock()
    client.post.return_value = response
    monkeypatch.setattr(adapter, "_http", lambda: client)
    return client


def _request(max_tokens=4096):
    return InternalRequest(
        provider="google_test",
        messages=[InternalMessage(role="system", content="Consigne."),
                  InternalMessage(role="user", content="--- agent_id=1 | … ---")],
        response_schema={"type": "object"},
        temperature=0.0,
        max_tokens=max_tokens,
    )


class TestCompletionNominale:

    def test_rend_output_et_compteurs(self, adapter, monkeypatch):
        _wire(adapter, monkeypatch, _response(
            usage={"promptTokenCount": 8154, "candidatesTokenCount": 2737}))
        out, tokens_in, tokens_out = adapter.call(_request())
        assert tokens_in == 8154
        assert tokens_out == 2737
        assert out.agents[0].agent_id == "1"

    def test_tokens_de_pensee_comptes_dans_la_sortie(self, adapter, monkeypatch):
        """Les tokens de raisonnement sont facturés ET décomptés du plafond."""
        _wire(adapter, monkeypatch, _response(
            usage={"promptTokenCount": 100, "candidatesTokenCount": 200,
                   "thoughtsTokenCount": 1500}))
        _out, tokens_in, tokens_out = adapter.call(_request())
        assert tokens_in == 100
        assert tokens_out == 1700  # 200 + 1500, et non 200

    def test_usage_absent_ne_casse_pas_l_appel(self, adapter, monkeypatch):
        _wire(adapter, monkeypatch, _response(usage={}))
        _out, tokens_in, tokens_out = adapter.call(_request())
        assert (tokens_in, tokens_out) == (0, 0)


class TestTroncatureMaxTokens:

    def test_leve_une_erreur_serveur_avec_les_chiffres(self, adapter, monkeypatch):
        _wire(adapter, monkeypatch, _response(
            finish="MAX_TOKENS",
            usage={"promptTokenCount": 9685, "candidatesTokenCount": 4096}))
        with pytest.raises(ProviderServerError) as exc:
            adapter.call(_request(max_tokens=4096))
        assert exc.value.status_code == 503
        assert exc.value.error_type == "max_tokens_truncation"
        # Les chiffres qui permettent de trancher « plafond trop bas » vs « boucle ».
        assert "completion=4096" in str(exc.value)
        assert "plafond=4096" in str(exc.value)

    def test_alarme_sur_front_montant_uniquement(self, adapter, monkeypatch):
        """5 troncatures d'affilée → UNE seule alarme (front montant, pas de spam)."""
        import llm_module.adapters.google_adapter as mod

        alarms = []
        monkeypatch.setattr(mod._logger, "error", lambda m, *a, **k: alarms.append(m))
        monkeypatch.setattr(mod._logger, "warning", lambda *a, **k: None)
        _wire(adapter, monkeypatch, _response(finish="MAX_TOKENS"))

        for _ in range(5):
            with pytest.raises(ProviderServerError):
                adapter.call(_request())

        assert len(alarms) == 1, "l'alarme doit tirer une fois, pas à chaque troncature"
        assert "[ALARME]" in alarms[0]
        assert adapter._trunc_streak == 5

    def test_une_troncature_isolee_n_alarme_pas(self, adapter, monkeypatch):
        """Sous le seuil, c'est un aléa : WARNING, pas d'ERREUR."""
        import llm_module.adapters.google_adapter as mod

        alarms = []
        monkeypatch.setattr(mod._logger, "error", lambda m, *a, **k: alarms.append(m))
        monkeypatch.setattr(mod._logger, "warning", lambda *a, **k: None)
        _wire(adapter, monkeypatch, _response(finish="MAX_TOKENS"))

        with pytest.raises(ProviderServerError):
            adapter.call(_request())
        assert alarms == []

    def test_un_succes_rearme_le_front(self, adapter, monkeypatch):
        """Une complétion propre clôt l'épisode : la série suivante ré-alarme."""
        import llm_module.adapters.google_adapter as mod

        alarms = []
        monkeypatch.setattr(mod._logger, "error", lambda m, *a, **k: alarms.append(m))
        monkeypatch.setattr(mod._logger, "warning", lambda *a, **k: None)

        _wire(adapter, monkeypatch, _response(finish="MAX_TOKENS"))
        for _ in range(3):
            with pytest.raises(ProviderServerError):
                adapter.call(_request())
        assert len(alarms) == 1

        _wire(adapter, monkeypatch, _response())
        adapter.call(_request())
        assert adapter._trunc_streak == 0  # épisode clos

        _wire(adapter, monkeypatch, _response(finish="MAX_TOKENS"))
        for _ in range(3):
            with pytest.raises(ProviderServerError):
                adapter.call(_request())
        assert len(alarms) == 2  # nouvel épisode → nouvelle alarme


class TestReponsesDegradees:

    def test_aucun_candidat(self, adapter, monkeypatch):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.json.return_value = {"candidates": [], "usageMetadata": {}}
        _wire(adapter, monkeypatch, resp)
        with pytest.raises(ProviderClientError) as exc:
            adapter.call(_request())
        assert exc.value.status_code == 400

    def test_reponse_bloquee_expose_la_raison(self, adapter, monkeypatch):
        _wire(adapter, monkeypatch, _response(finish="SAFETY", with_content=False))
        with pytest.raises(ProviderClientError) as exc:
            adapter.call(_request())
        assert "SAFETY" in str(exc.value)

    def test_timeout_reste_un_504_retentable(self, adapter, monkeypatch):
        client = MagicMock()
        client.post.side_effect = httpx.ReadTimeout("trop long")
        monkeypatch.setattr(adapter, "_http", lambda: client)
        with pytest.raises(ProviderServerError) as exc:
            adapter.call(_request())
        assert exc.value.status_code == 504
        assert exc.value.error_type == "timeout"


class TestCompatibiliteAppelants:
    """L'adaptateur est partagé par toute la simulation : la forme de l'appel HTTP
    ne doit pas bouger."""

    def test_payload_inchange(self, adapter, monkeypatch):
        client = _wire(adapter, monkeypatch, _response())
        adapter.call(_request(max_tokens=2048))
        _args, kwargs = client.post.call_args
        payload = kwargs["json"]
        assert payload["generationConfig"]["maxOutputTokens"] == 2048
        assert payload["generationConfig"]["response_mime_type"] == "application/json"
        # Le message système part en systemInstruction, jamais dans contents.
        assert payload["systemInstruction"]["parts"][0]["text"] == "Consigne."
        assert [c["role"] for c in payload["contents"]] == ["user"]
        assert kwargs["headers"]["x-goog-api-key"] == "clef"
