"""Tests du micro-batching et de l'évaluateur (cache store) — phase 1."""

import pytest

from calibration.evaluation import (Evaluator, batches_from_records,
                                    decisions_to_df, persona_agent_id)
from calibration.metrics import L1Composite
from calibration.models import RunConfig
from calibration.store import RunStore
from .test_metrics import CEREMA


def _rec(agent_id, dest="work", motif="travail"):
    section = (f"--- agent_id={agent_id} | Destination : {dest} | Départ : 08:00 ---\n"
               "Persona bla. Options : foot.")
    return {"agent_id": str(agent_id), "section": section, "context": "Météo : pluie.",
            "age": 30, "age_cat": "30-34", "occupation": "actif_temps_plein",
            "genre": "Homme", "motif": motif, "dist_cat": "1-2km"}


def test_persona_agent_id_both_formats():
    assert persona_agent_id("--- agent_id=503036 | Destination : work ---") == "503036"
    assert persona_agent_id("--- PERSONA 42 | Destination : shop ---") == "42"


def test_batches_respect_cap_and_unique_agent():
    records = [_rec(i) for i in range(5)]
    batches = batches_from_records(records, cap=2)
    assert all(len(b["meta"]) <= 2 for b in batches)
    # tous les agents présents une fois
    seen = [aid for b in batches for aid in b["meta"]]
    assert sorted(seen) == [str(i) for i in range(5)]


def test_recurring_agent_split_across_batches():
    # Même agent_id deux fois → jamais dans le même lot.
    records = [_rec(7, motif="travail"), _rec(7, motif="achats")]
    batches = batches_from_records(records, cap=10)
    assert len(batches) == 2


def test_weather_injected_into_section():
    batches = batches_from_records([_rec(1)], cap=1)
    content = batches[0]["messages"][1]["content"]
    assert "Météo : pluie." in content


def test_decisions_to_df_joins_metadata():
    meta = {"1": {"age_cat": "30-34", "genre": "Homme"}}
    df = decisions_to_df([("1", "car")], meta)
    assert df.iloc[0]["mode_cat"] == "voiture"
    assert df.iloc[0]["genre"] == "Homme"


class _FakeCall:
    """call_fn déterministe : renvoie un mode par agent, compte les appels."""

    def __init__(self):
        self.calls = 0

    def __call__(self, entry):
        self.calls += 1
        out = []
        for i, aid in enumerate(entry["meta"]):
            out.append({"agent_id": aid, "mode": "car" if i % 2 else "foot"})
        return out


@pytest.fixture
def evaluator(tmp_path):
    config = RunConfig(store_path=tmp_path / "c.db", eval_rpm=100000,
                       eval_samples=1, eval_batch_max=10, eval_workers=1)
    store = RunStore(config.store_path)
    records = [_rec(i) for i in range(6)]
    meta = {r["agent_id"]: r for r in records}
    call = _FakeCall()
    ev = Evaluator(config, store, L1Composite(0.0), CEREMA, meta, call)
    return ev, store, records, call


def test_evaluate_caches_and_records(evaluator):
    ev, store, records, call = evaluator
    blocks = [{"name": "intro_s1", "mutable": True, "content": "Un prompt."}]
    h = store.get_or_create_node(blocks, branch="main")

    result, df = ev.evaluate(h, blocks, "train", records)
    assert not df.empty and len(result.decisions) == len(records)
    first_calls = call.calls
    assert first_calls > 0

    # Deuxième éval du même nœud → cache hit, zéro nouvel appel provider.
    result2, df2 = ev.evaluate(h, blocks, "train", records)
    assert call.calls == first_calls
    assert result2.scores.composite == result.scores.composite
    assert len(df2) == len(df)
