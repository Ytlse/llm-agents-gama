"""Import one-shot des artefacts de l'ancienne version vers le store — phase 1.2.

Reconstruit le DAG d'un run historique en **rejouant** les mutations
(``mutations.jsonl``) sur le prompt seed, en attachant les verdicts et scores
composites lus de ``calibration_history.csv``.

Limite assumée : les **décisions brutes** de l'ancien run ne sont pas
récupérables (l'ancien cache d'éval — ``eval_cache/*.csv`` — est adressé par un
hash de contenu incompatible, et ne conserve pas le lien nœud ↔ décisions du
nouveau schéma). Les évals importées ne portent donc que les scores agrégés
disponibles ; une réévaluation ultérieure d'un nœud le complètera (cache miss →
recalcul, puis décisions brutes disponibles). L'objectif de l'import est la
**continuité de l'historique** (timeline, DAG, dashboard), pas le recalcul
rétroactif de la loss sur l'ancien run.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import EvalResult, Scores
from .mutation import apply_mutation
from .store import RunStore

_SCORE_COLS = ["composite", "global", "absent_penalty", "age", "occupation",
               "genre", "motif", "distance", "length_penalty"]


def _load_history(path: Path) -> dict[int, dict]:
    hist: dict[int, dict] = {}
    if not path.exists():
        return hist
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                it = int(row["iteration"])
            except (KeyError, ValueError):
                continue
            scores = {c: float(row[c]) for c in _SCORE_COLS if row.get(c) not in (None, "")}
            hist[it] = {"scores": scores, "best_score": row.get("best_score")}
    return hist


def _load_mutations(path: Path) -> dict[int, dict]:
    cache: dict[int, dict] = {}
    if not path.exists():
        return cache
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        cache[int(rec["iteration"])] = rec["mutation"]
    return cache


def import_legacy(store: RunStore, legacy_dir: str | Path, seed_blocks: list[dict],
                  branch: str = "main") -> dict:
    """Importe un run historique. Renvoie un résumé ``{nodes, mutations, evals}``."""
    legacy = Path(legacy_dir)
    mutations = _load_mutations(legacy / "mutations.jsonl")
    history = _load_history(legacy / "calibration_history.csv")

    seed_hash = store.get_or_create_node(seed_blocks, branch=branch, iteration=0)
    n_eval = 0
    if 0 in history and history[0]["scores"]:
        _record_synthetic_eval(store, seed_hash, history[0]["scores"])
        n_eval += 1

    blocks = seed_blocks
    node_from = seed_hash
    n_mut = 0
    for it in sorted(mutations):
        mutation = mutations[it]
        mutated = apply_mutation(blocks, mutation)
        if mutated is None:
            store.record_mutation(
                branch=branch, iteration=it, node_from=node_from, node_to=None,
                operator=mutation.get("action", "modify"),
                target_block=mutation.get("target_block", ""),
                new_content=mutation.get("new_content", ""),
                rationale=mutation.get("rationale", ""), verdict="invalid")
            n_mut += 1
            continue
        node_to = store.get_or_create_node(mutated, branch=branch, parent=node_from,
                                           iteration=it)
        scores = history.get(it, {}).get("scores") or {}
        if scores:
            _record_synthetic_eval(store, node_to, scores)
            n_eval += 1
        # Verdict inconnu précisément dans l'ancien format → 'imported'.
        store.record_mutation(
            branch=branch, iteration=it, node_from=node_from, node_to=node_to,
            operator=mutation.get("action", "modify"),
            target_block=mutation.get("target_block", ""),
            new_content=mutation.get("new_content", ""),
            rationale=mutation.get("rationale", ""), verdict="imported")
        n_mut += 1
        # L'ancien run muta toujours depuis le meilleur ; on suit la chaîne linéaire.
        blocks, node_from = mutated, node_to

    return {"nodes": store.node_count(branch), "mutations": n_mut, "evals": n_eval}


def _record_synthetic_eval(store: RunStore, node_hash: str, scores: dict) -> None:
    """Éval sans décisions brutes (scores agrégés hérités de l'ancien historique)."""
    result = EvalResult(node_hash=node_hash, dataset="train", decisions=[],
                        scores=Scores.model_validate(scores), eval_model="legacy_import")
    # params_key dédié : ne collisionne pas avec une éval réelle (qui la recalculera).
    store.record_eval(result, params_key="legacy_import")
