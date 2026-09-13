"""Corpus de sorties LLM (réelles ou reconstituées) contre le parseur tolérant `_parse_output`.

Ajouter un cas = ajouter une entrée dans tests/data/llm_outputs.json : `expect` est le nombre
d'agents attendus, ou "error" si la réponse doit être refusée (ProviderParseError).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from llm_gateway.adapters.base import ProviderParseError
from llm_gateway.testing import FakeAdapter

CORPUS = json.loads((Path(__file__).resolve().parents[1] / "data" / "llm_outputs.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CORPUS, ids=[c["name"] for c in CORPUS])
def test_corpus(case):
    adapter = FakeAdapter()
    if case["expect"] == "error":
        with pytest.raises(ProviderParseError):
            adapter._parse_output(case["raw"])
        return
    output = adapter._parse_output(case["raw"])
    assert len(output.agents) == case["expect"]
    assert all(isinstance(a.agent_id, str) for a in output.agents)
