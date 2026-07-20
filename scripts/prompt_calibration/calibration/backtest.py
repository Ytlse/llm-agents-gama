"""Backtest rétroactif d'une loss sur l'historique — phase 3 du ticket 004.

Le store conservant les **décisions brutes** de chaque éval, toute loss est
recalculable a posteriori sur tout l'historique d'une campagne **sans réappel
LLM**. On s'en sert avant de basculer de loss : comparer les trajectoires L1 vs
EMD/JSD sur les mêmes nœuds déjà évalués, pour vérifier que la nouvelle loss se
comporte comme attendu (ex. classe « moins grave » un décalage de strate
adjacent qu'un décalage distant).

Fonction **pure** (lecture store + pandas, aucun réseau) → testable.
"""

from __future__ import annotations

import json

import pandas as pd

from .evaluation import decisions_to_df
from .metrics import Metric
from .store import RunStore


def backtest_metrics(store: RunStore, metadata_by_id: dict[str, dict], cerema: dict,
                     metrics: dict[str, Metric], *, branch: str = "main",
                     dataset: str = "train") -> pd.DataFrame:
    """Recalcule le composite de chaque loss sur les nœuds déjà évalués d'une branche.

    Renvoie un DataFrame ``iteration × node × <loss1> × <loss2> …`` (une ligne par
    nœud candidat ayant une éval ``dataset``, trié par itération). Aucune éval LLM :
    les décisions brutes stockées suffisent.
    """
    sql = (
        "SELECT n.hash AS hash, n.iteration AS iteration, n.prompt_text AS prompt_text, "
        "  e.decisions AS decisions "
        "FROM nodes n JOIN evals e ON e.node_hash = n.hash "
        "WHERE n.branch = ? AND e.dataset = ? AND n.iteration IS NOT NULL "
        "ORDER BY n.iteration")
    rows = []
    for r in store.conn.execute(sql, (branch, dataset)).fetchall():
        decisions = [tuple(d) for d in json.loads(r["decisions"])]
        df = decisions_to_df(decisions, metadata_by_id)
        row = {"iteration": r["iteration"], "node": r["hash"]}
        for name, metric in metrics.items():
            row[name] = metric.compute(df, cerema, prompt_text=r["prompt_text"]).composite
        rows.append(row)
    return pd.DataFrame(rows)


def compare_summary(df: pd.DataFrame, loss_names: list[str]) -> dict:
    """Résumé lisible du backtest : valeurs finales, minima, corrélation de rang.

    La corrélation de Spearman entre losses dit si elles ordonnent les nœuds de la
    même façon ; une corrélation basse signale que la nouvelle loss change réellement
    les décisions d'acceptation (intérêt du backtest avant bascule).
    """
    present = [n for n in loss_names if n in df.columns]
    summary: dict = {"n_nodes": int(len(df)), "losses": {}}
    for name in present:
        col = df[name]
        summary["losses"][name] = {
            "final": float(col.iloc[-1]) if len(col) else None,
            "best": float(col.min()) if len(col) else None,
            "best_iteration": int(df.loc[col.idxmin(), "iteration"]) if len(col) else None,
        }
    if len(present) == 2 and len(df) >= 3:
        summary["rank_correlation"] = float(
            df[present[0]].corr(df[present[1]], method="spearman"))
    return summary
