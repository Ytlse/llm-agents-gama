"""Tests de la finalisation & publication (phase 7)."""

from datetime import datetime, timezone

from calibration.evaluation import Evaluator
from calibration.metrics import L1Composite
from calibration.models import RunConfig, Scores
from calibration.publish import (build_comparison, campaign_report, finalize,
                                 publish_key, publish_prompt)
from calibration.store import RunStore
from .test_metrics import CEREMA


def _rec(aid):
    section = (f"--- agent_id={aid} | Destination : work | Départ : 08:00 ---\n"
               "Persona. Options : foot.")
    return {"agent_id": str(aid), "section": section, "context": "Météo : sec.",
            "age": 30, "age_cat": "20-24", "occupation": "actif_temps_plein",
            "genre": "Homme", "motif": "travail", "dist_cat": "1-2km"}


class _DetCall:
    def __init__(self):
        self.calls = 0

    def __call__(self, entry):
        self.calls += 1
        prompt = entry["messages"][0]["content"]
        modes = ["foot", "car", "bicycle", "foot,bus,foot"]
        pick = modes[len(prompt.split()) % len(modes)]
        return [{"agent_id": aid, "mode": pick} for aid in entry["meta"]]


SEED = [
    {"name": "intro_s1", "mutable": True, "content": "Prompt initial court."},
    {"name": "json_schema", "mutable": False, "content": '{"type":"object"}'},
]
ALT = [
    {"name": "intro_s1", "mutable": True,
     "content": "Autre prompt beaucoup plus long avec davantage de mots ici presents voila."},
    {"name": "json_schema", "mutable": False, "content": '{"type":"object"}'},
]


# ── Helpers purs ─────────────────────────────────────────────────────────────

def test_publish_key_format():
    when = datetime(2026, 7, 15, 12, 34, tzinfo=timezone.utc)
    assert publish_key("calibrated", when) == "calibrated_20260715_1234"


def test_publish_prompt_adds_key_without_touching_existing(tmp_path):
    import yaml
    p = tmp_path / "prompts.yaml"
    p.write_text(yaml.safe_dump(
        {"active": "expert", "prompts": {"expert": {"content": "old"}}},
        allow_unicode=True), encoding="utf-8")

    key = publish_prompt(p, "nouveau prompt calibré", prefix="calibrated",
                         key="calibrated_20260715_1200", activate=True)
    d = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert key == "calibrated_20260715_1200"
    assert d["prompts"][key]["content"] == "nouveau prompt calibré"
    assert d["prompts"]["expert"]["content"] == "old"      # entrée existante intacte
    assert d["active"] == key                               # activation demandée


def test_publish_prompt_dry_default_no_activate(tmp_path):
    import yaml
    p = tmp_path / "prompts.yaml"
    p.write_text(yaml.safe_dump({"active": "expert", "prompts": {"expert": {"content": "x"}}},
                                allow_unicode=True), encoding="utf-8")
    publish_prompt(p, "texte", key="k1")                   # activate=False par défaut
    d = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert d["active"] == "expert"                          # inchangé
    assert d["prompts"]["k1"]["content"] == "texte"


def test_build_comparison_deltas_and_words():
    before = {"train": Scores(composite=10.0), "test": Scores(composite=12.0, age=5.0)}
    after = {"train": Scores(composite=6.0), "test": Scores(composite=7.0, age=2.0)}
    cmp = build_comparison(SEED, ALT, before, after)
    by_ds = {r["dataset"]: r for r in cmp["by_dataset"]}
    assert by_ds["train"]["delta"] == -4.0
    assert by_ds["test"]["delta"] == -5.0
    assert cmp["test_dims"]["age"]["delta"] == -3.0
    assert cmp["words_after"] > cmp["words_before"]         # ALT plus long que SEED


# ── Store + finalize ─────────────────────────────────────────────────────────

def _engine(tmp_path, call):
    config = RunConfig(store_path=tmp_path / "f.db", eval_rpm=100000, eval_samples=1,
                       eval_batch_max=10, eval_workers=1)
    store = RunStore(config.store_path)
    records = [_rec(i) for i in range(6)]
    meta = {r["agent_id"]: r for r in records}
    ev = Evaluator(config, store, L1Composite(0.0), CEREMA, meta, call)
    return config, store, ev, records


def test_campaign_report_counts(tmp_path):
    _, store, ev, records = _engine(tmp_path, _DetCall())
    seed = store.get_or_create_node(SEED, branch="main", iteration=0)
    ev.evaluate(seed, SEED, "train", records)
    store.save_run_state("main", {"iteration": 3, "accepted": 2, "best_score": 5.0,
                                  "best_node": seed})
    rep = campaign_report(store)
    assert rep["branches"] == ["main"]
    assert rep["total_accepted"] == 2
    assert rep["eval_counts"]["train"] == 1
    assert rep["n_evals"] == 1


def test_finalize_runs_single_test_eval_and_reports(tmp_path):
    call = _DetCall()
    config, store, ev, records = _engine(tmp_path, call)
    seed = store.get_or_create_node(SEED, branch="main", iteration=0)
    alt = store.get_or_create_node(ALT, branch="main", parent=seed, iteration=1)
    ev.evaluate(seed, SEED, "train", records)
    ev.evaluate(alt, ALT, "train", records)
    calls_before = call.calls

    test = [_rec(i) for i in range(3)]
    result = finalize(store, ev, config, SEED, test)
    assert result is not None
    # Le meilleur nœud = plus faible composite train, toutes branches confondues.
    assert result["best_hash"] == store.best_overall("train")["hash"]
    # Le test a bien été évalué pour le meilleur ET le seed (base de comparaison).
    assert "test" in result["best_scores"] and "test" in result["seed_scores"]
    assert call.calls > calls_before
    ds = {r["dataset"] for r in result["comparison"]["by_dataset"]}
    assert "train" in ds and "test" in ds
    store.close()


def test_finalize_is_idempotent_no_extra_llm(tmp_path):
    call = _DetCall()
    config, store, ev, records = _engine(tmp_path, call)
    seed = store.get_or_create_node(SEED, branch="main", iteration=0)
    ev.evaluate(seed, SEED, "train", records)
    test = [_rec(i) for i in range(3)]
    finalize(store, ev, config, SEED, test)
    calls_after_first = call.calls
    finalize(store, ev, config, SEED, test)     # rejeu → tout en cache
    assert call.calls == calls_after_first
    store.close()


def test_finalize_empty_store_returns_none(tmp_path):
    config, store, ev, _ = _engine(tmp_path, _DetCall())
    assert finalize(store, ev, config, SEED, []) is None
    store.close()
