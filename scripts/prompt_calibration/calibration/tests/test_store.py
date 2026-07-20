"""Tests du store SQLite (nœuds, évals, cache, mutations, reprise) — phase 1.2."""

import pytest

from calibration.models import EvalResult, Scores
from calibration.store import RunStore


@pytest.fixture
def store(tmp_path):
    s = RunStore(tmp_path / "c.db")
    yield s
    s.close()


BLOCKS = [{"name": "intro_s1", "mutable": True, "content": "Bonjour le monde."}]


def test_node_dedup_content_addressed(store):
    h1 = store.get_or_create_node(BLOCKS, branch="main", iteration=0)
    h2 = store.get_or_create_node(BLOCKS, branch="main", iteration=5)
    assert h1 == h2
    assert store.node_count() == 1


def test_eval_cache_roundtrip(store):
    h = store.get_or_create_node(BLOCKS, branch="main")
    res = EvalResult(node_hash=h, dataset="train",
                     decisions=[("1", "marche"), ("2", "car")],
                     scores=Scores.model_validate({"global": 3.0, "composite": 7.0}))
    store.record_eval(res, params_key="pk")
    got = store.cached_eval(h, "train", "pk")
    assert got is not None
    assert got.decisions == [("1", "marche"), ("2", "car")]
    assert got.scores.composite == 7.0
    # Params différents → cache miss (ne resserre pas une éval d'autres paramètres).
    assert store.cached_eval(h, "train", "other") is None


def test_mutation_verdict_update_and_replay(store):
    h = store.get_or_create_node(BLOCKS, branch="main")
    mid = store.record_mutation(branch="main", iteration=1, node_from=h, node_to=None,
                                operator="modify", target_block="intro_s1",
                                new_content="Salut.", rationale="test", verdict="proposed")
    replay = store.replayable_mutation("main", 1)
    assert replay["target_block"] == "intro_s1" and replay["action"] == "modify"
    store.update_mutation(mid, verdict="accepted", node_to=h)
    row = store.mutation_row_at("main", 1)
    assert row["verdict"] == "accepted" and row["node_to"] == h


def test_best_returns_lowest_composite(store):
    h1 = store.get_or_create_node(BLOCKS, branch="main", iteration=0)
    h2 = store.get_or_create_node(
        [{"name": "intro_s1", "mutable": True, "content": "Autre prompt ici."}],
        branch="main", iteration=1)
    store.record_eval(EvalResult(node_hash=h1, dataset="train", decisions=[],
                                 scores=Scores.model_validate({"composite": 9.0})), "pk")
    store.record_eval(EvalResult(node_hash=h2, dataset="train", decisions=[],
                                 scores=Scores.model_validate({"composite": 4.0})), "pk")
    best = store.best("main")
    assert best["hash"] == h2 and best["composite"] == 4.0


def test_resume_state_roundtrip(store):
    assert store.resume_state("main") is None
    store.save_run_state("main", {"iteration": 3, "accepted": 2})
    assert store.resume_state("main") == {"iteration": 3, "accepted": 2}


def test_lineage_ordered_seed_to_node(store):
    h0 = store.get_or_create_node(BLOCKS, branch="main", iteration=0)
    h1 = store.get_or_create_node(
        [{"name": "intro_s1", "mutable": True, "content": "Deuxième version ok."}],
        branch="main", parent=h0, iteration=1)
    chain = store.lineage(h1)
    assert [n["hash"] for n in chain] == [h0, h1]


def test_ablation_recorded(store):
    h = store.get_or_create_node(BLOCKS, branch="main")
    store.record_ablation(h, "intro_s1", "shapley", 4.2, diag="dim age -1.0")
    rows = store.ablations(h)
    assert len(rows) == 1 and rows[0]["value"] == 4.2
