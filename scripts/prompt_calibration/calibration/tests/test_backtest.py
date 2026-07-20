"""Test du backtest rétroactif (phase 3) : recalcul de losses sur le store, zéro LLM."""

from calibration.backtest import backtest_metrics, compare_summary
from calibration.metrics import EMDJSDComposite, L1Composite
from calibration.models import EvalResult, Scores
from calibration.store import RunStore
from .test_metrics import CEREMA


def _blocks(text):
    return [{"name": "intro_s1", "mutable": True, "content": text},
            {"name": "json_schema", "mutable": False, "content": "{}"}]


def _seed_store(path):
    store = RunStore(path)
    meta = {str(i): {"age_cat": "20-24", "occupation": "actif_temps_plein",
                     "genre": "Homme", "motif": "travail", "dist_cat": "1-2km"}
            for i in range(20)}
    # Deux itérations avec des décisions différentes (donc des scores différents).
    for it, mode in ((1, "foot"), (2, "car")):
        blocks = _blocks(f"prompt v{it}")
        node = store.get_or_create_node(blocks, branch="main", iteration=it)
        decisions = [(str(i), mode) for i in range(20)]
        store.record_eval(EvalResult(node_hash=node, dataset="train",
                                     decisions=decisions, scores=Scores()),
                          params_key="k")
    return store, meta


def test_backtest_recomputes_both_losses(tmp_path):
    store, meta = _seed_store(tmp_path / "c.db")
    metrics = {"l1_composite": L1Composite(0.0), "emd_jsd": EMDJSDComposite(0.0)}
    df = backtest_metrics(store, meta, CEREMA, metrics, branch="main", dataset="train")
    store.close()

    assert list(df["iteration"]) == [1, 2]
    assert {"l1_composite", "emd_jsd", "node"} <= set(df.columns)
    # Les deux itérations ont des décisions différentes → composites distincts.
    assert df["l1_composite"].iloc[0] != df["l1_composite"].iloc[1]

    summary = compare_summary(df, ["l1_composite", "emd_jsd"])
    assert summary["n_nodes"] == 2
    assert "l1_composite" in summary["losses"]
    assert summary["losses"]["l1_composite"]["best_iteration"] in (1, 2)


def test_backtest_empty_store(tmp_path):
    store = RunStore(tmp_path / "empty.db")
    df = backtest_metrics(store, {}, CEREMA, {"l1_composite": L1Composite(0.0)})
    store.close()
    assert df.empty
