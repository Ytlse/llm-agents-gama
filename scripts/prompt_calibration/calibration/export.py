"""Export lisible du store — phase 1.3 du ticket 004.

Le store SQLite reste la source de vérité (DAG, décisions brutes) ; l'export
répond au **besoin de lisibilité** derrière la demande de CSV (ticket §1) :
``nodes.csv``, ``mutations.csv`` et une timeline Markdown ``history.md``.
Le dashboard Streamlit (phase 2) est la vue lisible interactive.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .store import RunStore


def export_all(store: RunStore, out_dir: str | Path) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    _export_table(store, "nodes",
                  "SELECT hash, branch, iteration, parent, parent2, created_at FROM nodes "
                  "ORDER BY branch, iteration", out / "nodes.csv")
    _export_table(store, "mutations",
                  "SELECT id, branch, iteration, node_from, node_to, operator, target_block, "
                  "verdict, reject_cause, rationale FROM mutations ORDER BY id",
                  out / "mutations.csv")
    _export_history_md(store, out / "history.md")
    return out


def _export_table(store: RunStore, name: str, query: str, path: Path) -> None:
    rows = store.conn.execute(query).fetchall()
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if rows:
            writer.writerow(rows[0].keys())
            for r in rows:
                writer.writerow([r[k] for k in r.keys()])
        else:
            writer.writerow([])


def _export_history_md(store: RunStore, path: Path) -> None:
    """Timeline lisible : itération, opérateur, bloc, verdict, score, rationale."""
    lines = ["# Timeline des mutations\n",
             "| branche | itér | opérateur | bloc | verdict | composite | rationale |",
             "|---|---|---|---|---|---|---|"]
    query = (
        "SELECT m.branch AS branch, m.iteration AS iteration, m.operator AS operator, "
        "  m.target_block AS target_block, m.verdict AS verdict, m.rationale AS rationale, "
        "  json_extract(e.scores_json,'$.composite') AS composite "
        "FROM mutations m LEFT JOIN evals e "
        "  ON e.node_hash=m.node_to AND e.dataset='train' "
        "ORDER BY m.branch, m.iteration")
    for r in store.conn.execute(query).fetchall():
        comp = f"{r['composite']:.2f}" if r["composite"] is not None else "—"
        rationale = (r["rationale"] or "").replace("|", "\\|").replace("\n", " ")[:80]
        lines.append(f"| {r['branch']} | {r['iteration']} | {r['operator']} | "
                     f"{r['target_block']} | {r['verdict']} | {comp} | {rationale} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
