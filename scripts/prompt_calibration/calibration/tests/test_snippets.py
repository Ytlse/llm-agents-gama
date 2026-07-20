"""Tests de la bibliothèque d'arguments comportementaux (phase 6.4, DL)."""

import pandas as pd

from calibration.evaluation import Evaluator
from calibration.loop import CalibrationLoop
from calibration.metrics import L1Composite
from calibration.models import RunConfig
from calibration.mutation import format_snippets_for_mutation
from calibration.store import RunStore
from .test_metrics import CEREMA


def _node(store, text):
    return store.get_or_create_node(
        [{"name": "intro_s1", "mutable": True, "content": text}], branch="main")


def _store(tmp_path):
    return RunStore(tmp_path / "s.db")


def test_store_record_and_top_snippets(tmp_path):
    store = _store(tmp_path)
    n1, n2 = _node(store, "un"), _node(store, "deux")
    store.record_snippet(node_origin=n1, branch="main", operator="insert",
                         block_name="inserted_1", content="Pense au vélo par beau temps.",
                         tag_mode="velo", gain=5.0)
    store.record_snippet(node_origin=n2, branch="main", operator="modify",
                         block_name="intro_s1", content="Le bus est pratique.",
                         tag_mode="transports_collectifs", gain=2.0)
    # Tri par gain décroissant.
    top = store.top_snippets(limit=5)
    assert [r["gain"] for r in top] == [5.0, 2.0]
    # Filtre par mode ciblé.
    velo = store.top_snippets(limit=5, tag_mode="velo")
    assert len(velo) == 1 and velo[0]["block_name"] == "inserted_1"
    store.close()


def test_format_snippets_for_mutation():
    assert format_snippets_for_mutation(None) == ""
    txt = format_snippets_for_mutation([
        {"content": "Argument vélo.", "tag_mode": "velo", "gain": 4.0}])
    assert "velo" in txt and "Argument vélo" in txt


def _min_loop(tmp_path, records):
    config = RunConfig(store_path=tmp_path / "l.db", eval_rpm=100000, eval_samples=1,
                       eval_batch_max=10, eval_workers=1, snippet_min_gain=2.0)
    store = RunStore(config.store_path)
    meta = {r["agent_id"]: r for r in records}
    ev = Evaluator(config, store, L1Composite(0.0), CEREMA, meta, lambda e: [])
    loop = CalibrationLoop(config, store, ev, object(), CEREMA, records, [])
    return loop, store


def _rec(aid):
    return {"agent_id": str(aid), "age": 30, "age_cat": "20-24",
            "occupation": "actif_temps_plein", "genre": "Homme",
            "motif": "travail", "dist_cat": "1-2km"}


def _df_all_car():
    # Distribution 100 % voiture → le vélo est le mode le plus sous-représenté.
    return pd.DataFrame([{"agent_id": str(i), "mode_cat": "voiture"} for i in range(10)])


def test_capture_snippet_on_significant_gain(tmp_path):
    loop, store = _min_loop(tmp_path, [_rec(i) for i in range(4)])
    node = _node(store, "un prompt")
    mutation = {"target_block": "intro_s1", "action": "insert",
                "new_content": "Le vélo est agréable en ville.", "rationale": "r"}
    # delta = -3 → gain 3 ≥ seuil 2 → capitalisé.
    loop._capture_snippet(mutation, node, _df_all_car(), delta=-3.0)
    snips = store.top_snippets(limit=5)
    assert len(snips) == 1
    assert snips[0]["content"] == "Le vélo est agréable en ville."
    # df 100 % voiture → marche est le mode le plus sous-représenté vs EMC² → taggé.
    assert snips[0]["tag_mode"] == "marche"
    store.close()


def test_no_capture_below_threshold_or_wrong_operator(tmp_path):
    loop, store = _min_loop(tmp_path, [_rec(i) for i in range(4)])
    node = _node(store, "un prompt")
    # Gain insuffisant.
    loop._capture_snippet({"target_block": "b", "action": "insert",
                           "new_content": "x"}, node, _df_all_car(), delta=-1.0)
    # Opérateur sans contenu réutilisable (delete).
    loop._capture_snippet({"target_block": "b", "action": "delete",
                           "new_content": ""}, node, _df_all_car(), delta=-5.0)
    assert store.top_snippets(limit=5) == []
    store.close()


def test_top_snippets_feeds_mutator_context(tmp_path):
    loop, store = _min_loop(tmp_path, [_rec(i) for i in range(4)])
    node = _node(store, "un prompt")
    store.record_snippet(node_origin=node, branch="main", operator="insert",
                         block_name="inserted_1", content="Vélo malin.",
                         tag_mode="velo", gain=9.0)
    fed = loop._top_snippets(_df_all_car())
    assert fed and fed[0]["content"] == "Vélo malin."
    store.close()
