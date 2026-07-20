"""Tests de la couche de lecture du dashboard (pure, sans Streamlit) — phase 2."""

import pytest

from calibration import dashboard_data as dd
from calibration.models import EvalResult, Scores
from calibration.store import RunStore

SEED = [{"name": "intro_s1", "mutable": True, "content": "Prends le vélo."}]
MUT = [{"name": "intro_s1", "mutable": True, "content": "Prends le bus plutôt."}]


@pytest.fixture
def store(tmp_path):
    s = RunStore(tmp_path / "c.db")
    yield s
    s.close()


def _eval(store, node_hash, dataset, composite, decisions=None, **dims):
    scores = {"composite": composite, **dims}
    store.record_eval(EvalResult(node_hash=node_hash, dataset=dataset,
                                 decisions=decisions or [], scores=Scores.model_validate(scores)),
                      params_key="pk")


def _campaign(store):
    """Seed (iter 0) + deux mutations (accepted meilleure, puis rejected pire)."""
    seed = store.get_or_create_node(SEED, branch="main", iteration=0)
    _eval(store, seed, "train", 10.0, age=2.0)

    n1 = store.get_or_create_node(MUT, branch="main", parent=seed, iteration=1)
    _eval(store, n1, "train", 6.0, age=1.0,
          decisions=[("1", "bus"), ("2", "voiture")])
    mid1 = store.record_mutation(branch="main", iteration=1, node_from=seed, node_to=n1,
                                 operator="modify", target_block="intro_s1",
                                 new_content="bus", rationale="cap TC", verdict="proposed")
    store.update_mutation(mid1, verdict="accepted", node_to=n1)

    n2 = store.get_or_create_node(
        [{"name": "intro_s1", "mutable": True, "content": "Marche toujours."}],
        branch="main", parent=n1, iteration=2)
    _eval(store, n2, "train", 8.0, age=3.0)
    mid2 = store.record_mutation(branch="main", iteration=2, node_from=n1, node_to=n2,
                                 operator="modify", target_block="intro_s1",
                                 new_content="marche", rationale="test", verdict="proposed")
    store.update_mutation(mid2, verdict="rejected_score", node_to=n2)
    return seed, n1, n2


def test_timeline_empty(store):
    assert dd.timeline_df(store).empty


def test_timeline_scores_and_best_curve(store):
    _campaign(store)
    df = dd.timeline_df(store).sort_values("iteration").reset_index(drop=True)
    assert list(df["iteration"]) == [1, 2]
    assert df.loc[0, "composite"] == 6.0 and df.loc[0, "age"] == 1.0
    # best_so_far = min cumulé : reste à 6.0 après une mutation pire (8.0).
    assert df.loc[0, "best_so_far"] == 6.0
    assert df.loc[1, "best_so_far"] == 6.0


def test_best_curve_ignores_vetoed(store):
    seed = store.get_or_create_node(SEED, branch="main", iteration=0)
    n1 = store.get_or_create_node(MUT, branch="main", parent=seed, iteration=1)
    _eval(store, n1, "train", 2.0)  # meilleur composite mais…
    mid = store.record_mutation(branch="main", iteration=1, node_from=seed, node_to=n1,
                                operator="modify", target_block="intro_s1",
                                new_content="x", rationale="", verdict="proposed")
    store.update_mutation(mid, verdict="vetoed", node_to=n1, reject_cause="motif +20")
    df = dd.timeline_df(store)
    # Vétoé → ne compte pas dans le meilleur score.
    assert df.loc[0, "best_so_far"] is None or df["best_so_far"].isna().all()


def test_lineage_filters_ablation_nodes(store):
    seed, n1, n2 = _campaign(store)
    # Nœud d'ablation : créé sans itération → hors DAG affiché.
    abl = store.get_or_create_node(
        [{"name": "other", "mutable": True, "content": "ablated variant."}],
        branch="main")
    nodes = dd.lineage_df(store)
    assert set(nodes["hash"]) == {seed, n1, n2}
    assert abl not in set(nodes["hash"])


def test_lineage_edges_internal_only(store):
    seed, n1, n2 = _campaign(store)
    nodes = dd.lineage_df(store)
    edges = dd.lineage_edges(nodes)
    assert (seed, n1, False) in edges
    assert (n1, n2, False) in edges
    assert all(not is_merge for _, _, is_merge in edges)


def test_node_detail_diff_and_scores(store):
    seed, n1, _ = _campaign(store)
    detail = dd.node_detail(store, n1)
    assert detail["parent"] == seed
    assert "train" in detail["scores_by_dataset"]
    assert detail["scores_by_dataset"]["train"]["composite"] == 6.0
    assert "bus" in detail["prompt_text"]
    assert detail["diff"]  # non vide : diff vs parent


def test_node_detail_missing(store):
    assert dd.node_detail(store, "deadbeef") is None


def test_distribution_view(store):
    seed, n1, _ = _campaign(store)
    cerema = {"parts_modales_2023": {"global": {
        "marche": 0.25, "voiture": 0.5, "velo": 0.05, "transports_collectifs": 0.2}}}
    meta = {"1": {"age_cat": "25-29"}, "2": {"age_cat": "25-29"}}
    view = dd.distribution_view(store, n1, cerema, meta)
    assert view is not None
    assert view["n_decisions"] == 2
    modes = {b["mode"]: b for b in view["global_bars"]}
    # 1 TC + 1 voiture sur 2 décisions → 50 % chacun.
    assert modes["transports_collectifs"]["actual"] == 50.0
    assert modes["voiture"]["actual"] == 50.0


def test_distribution_view_no_decisions(store):
    seed = store.get_or_create_node(SEED, branch="main", iteration=0)
    _eval(store, seed, "train", 10.0)  # éval sans décisions brutes
    assert dd.distribution_view(store, seed, {"parts_modales_2023": {"global": {}}}, {}) is None


# ── Carte d'ablation avec détail par dimension ───────────────────────────────

def test_ablation_table_shapley(store):
    import json
    seed, n1, _ = _campaign(store)
    # Shapley : le détail pondéré (pts de composite) est déjà persisté tel quel.
    store.record_ablation(n1, "intro_s1", "shapley", 2.5,
                          scores_json=json.dumps({"global": 1.5, "age": 1.0}), diag="")

    detail = dd.node_detail(store, n1)
    adf = dd.ablation_table(detail).set_index("method")
    # Relu depuis le store, pas recalculé.
    assert adf.loc["shapley", "global"] == pytest.approx(1.5)
    assert adf.loc["shapley", "age"] == pytest.approx(1.0)
    assert list(adf.columns[:2]) == ["bloc", "value"]


def test_node_detail_prefers_eval_with_decisions(store):
    # Une éval train plus récente mais SANS décisions (artefact partiel, ex. import
    # legacy) ne doit masquer ni les scores ni les décisions de l'éval complète.
    _, n1, _ = _campaign(store)
    store.record_eval(EvalResult(node_hash=n1, dataset="train", decisions=[],
                                 scores=Scores.model_validate({"composite": 99.0})),
                      params_key="pk-legacy")
    det = dd.node_detail(store, n1)
    assert det["scores_by_dataset"]["train"]["composite"] == 6.0
    meta = {"1": {"age_cat": "20-24"}, "2": {"age_cat": "65+"}}
    view = dd.comparison_view(store, [n1], CEREMA_CMP, meta, "global")
    assert view["missing"] == []


def test_ablation_table_without_persisted_detail(store):
    # Ligne Shapley sans détail par dimension persisté (scores_json vide) : les
    # colonnes de dimension sont None, pas d'erreur.
    node = store.get_or_create_node(SEED, branch="b2", iteration=0)
    store.record_ablation(node, "intro_s1", "shapley", 1.0, scores_json="{}", diag="")
    adf = dd.ablation_table(dd.node_detail(store, node))
    assert adf.loc[0, "age"] is None


# ── Vue Comparaison (prompts vs EMC²) ────────────────────────────────────────

CEREMA_CMP = {"parts_modales_2023": {
    "global": {"marche": 25, "voiture": 50, "velo": 5,
               "transports_collectifs": 20, "autres_modes": 3},
    "Age": {"20-24": {"marche": 30, "voiture": 40, "velo": 10,
                      "transports_collectifs": 20},
            "65+": {"marche": 40, "voiture": 50, "velo": 0,
                    "transports_collectifs": 10}},
}}


def test_comparison_view_global(store):
    seed, n1, _ = _campaign(store)   # n1 : décisions [("1","bus"), ("2","voiture")]
    meta = {"1": {"age_cat": "20-24"}, "2": {"age_cat": "65+"}}
    view = dd.comparison_view(store, [seed, n1], CEREMA_CMP, meta, "global")
    # Le seed n'a pas de décisions stockées → signalé, pas planté.
    assert view["missing"] == [seed]
    assert len(view["categories"]) == 1
    bars = {b["mode"]: b for b in view["categories"][0]["bars"]}
    assert bars["voiture"]["values"][n1] == pytest.approx(50.0)
    assert bars["transports_collectifs"]["values"][n1] == pytest.approx(50.0)
    # Cible renormalisée sans autres_modes : voiture 50/100 → 50 %.
    assert bars["voiture"]["target"] == pytest.approx(50.0)


def test_comparison_view_by_dimension(store):
    _, n1, _ = _campaign(store)
    meta = {"1": {"age_cat": "20-24"}, "2": {"age_cat": "65+"}}
    view = dd.comparison_view(store, [n1], CEREMA_CMP, meta, "age")
    cats = {c["cat"]: c for c in view["categories"]}
    # Les catégories viennent de la référence EMC² (ordre du YAML).
    assert list(cats) == ["20-24", "65+"]
    # 20-24 : une seule décision (bus) → TC à 100 %.
    b2024 = {b["mode"]: b for b in cats["20-24"]["bars"]}
    assert b2024["transports_collectifs"]["values"][n1] == pytest.approx(100.0)
    assert cats["20-24"]["n"][n1] == 1
    # Cible 20-24 : marche 30 % (somme des MODES = 100).
    assert b2024["marche"]["target"] == pytest.approx(30.0)
    # 65+ : la décision voiture.
    b65 = {b["mode"]: b for b in cats["65+"]["bars"]}
    assert b65["voiture"]["values"][n1] == pytest.approx(100.0)


def test_run_status(store):
    _campaign(store)
    store.save_run_state("main", {"iteration": 2, "accepted": 1, "best_score": 6.0,
                                  "best_node": "x", "val_best": 7.0, "val_no_improve": 1})
    status = dd.run_status(store, "main")
    assert status["iteration"] == 2 and status["accepted"] == 1
    assert status["best_score"] == 6.0
    assert status["n_mutations"] == 2
    assert status["eval_counts"]["train"] == 3


def test_branches(store):
    _campaign(store)
    assert dd.branches(store) == ["main"]


# ── Vue Pareto & snippets (phase 6) ──────────────────────────────────────────

def test_pareto_view_front_and_dominated(store):
    flat = {d: 0.0 for d in ("global", "occupation", "genre", "distance")}
    a = store.get_or_create_node([{"name": "intro_s1", "mutable": True, "content": "A"}],
                                 branch="isl-0", iteration=0)
    b = store.get_or_create_node([{"name": "intro_s1", "mutable": True, "content": "B"}],
                                 branch="isl-1", iteration=0)
    c = store.get_or_create_node([{"name": "intro_s1", "mutable": True, "content": "C"}],
                                 branch="isl-0", iteration=1)
    _eval(store, a, "train", 5.0, age=1.0, motif=5.0, **flat)   # extrême age
    _eval(store, b, "train", 5.0, age=5.0, motif=1.0, **flat)   # extrême motif
    _eval(store, c, "train", 8.0, age=6.0, motif=6.0, **flat)   # dominé par A et B

    view = dd.pareto_view(store)
    assert view["n_total"] == 3
    assert view["n_front"] == 2
    assert {it["hash"] for it in view["front"]} == {a, b}
    on_front = {it["hash"]: it["on_front"] for it in view["items"]}
    assert on_front[a] and on_front[b] and not on_front[c]


def test_snippets_df(store):
    node = store.get_or_create_node(
        [{"name": "intro_s1", "mutable": True, "content": "x"}], branch="main")
    store.record_snippet(node_origin=node, branch="main", operator="insert",
                         block_name="inserted_1", content="Vélo malin.",
                         tag_mode="velo", gain=4.0)
    df = dd.snippets_df(store)
    assert len(df) == 1
    assert df.iloc[0]["tag_mode"] == "velo" and df.iloc[0]["gain"] == 4.0


# ── Actions Maintenance ──────────────────────────────────────────────────────

class _Cfg:
    """Config minimale pour les helpers d'action (attributs suffisants)."""
    def __init__(self, prompts_path, branch="main", seed_prompt="expert"):
        self.prompts_path = prompts_path
        self.branch = branch
        self.seed_prompt = seed_prompt


def _write_prompts(tmp_path):
    import yaml
    p = tmp_path / "prompts.yaml"
    p.write_text(yaml.safe_dump(
        {"prompts": {"expert": {"content": "Première phrase. Deuxième phrase."}}}),
        encoding="utf-8")
    return p


def test_seed_blocks_for(tmp_path):
    cfg = _Cfg(_write_prompts(tmp_path))
    blocks = dd.seed_blocks_for(cfg)
    assert blocks and all("content" in b and "name" in b for b in blocks)


def test_seed_blocks_for_missing_seed(tmp_path):
    cfg = _Cfg(_write_prompts(tmp_path), seed_prompt="absent")
    with pytest.raises(KeyError):
        dd.seed_blocks_for(cfg)


def test_export_readable(store, tmp_path):
    _campaign(store)
    out = dd.export_readable(store, tmp_path / "export")
    assert (out / "nodes.csv").exists()
    assert (out / "mutations.csv").exists()
    assert (out / "history.md").exists()


def test_import_legacy_run(store, tmp_path):
    cfg = _Cfg(_write_prompts(tmp_path))
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    # Un run legacy minimal : une mutation rejouable + son score.
    (legacy / "mutations.jsonl").write_text(
        '{"iteration": 1, "mutation": {"target_block": "intro_s1", '
        '"action": "modify", "new_content": "Nouvelle phrase.", "rationale": "x"}}\n',
        encoding="utf-8")
    (legacy / "calibration_history.csv").write_text(
        "iteration,composite\n0,10.0\n1,6.0\n", encoding="utf-8")
    summary = dd.import_legacy_run(store, cfg, legacy)
    assert summary["nodes"] >= 1 and summary["mutations"] == 1
