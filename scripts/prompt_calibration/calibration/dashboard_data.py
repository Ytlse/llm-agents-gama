"""Accès en lecture au store pour le dashboard — phase 2 du ticket 004.

Fonctions **pures** (SQL + pandas, aucun réseau, aucune dépendance Streamlit) :
elles prennent un :class:`RunStore` ouvert en lecture et renvoient des
DataFrames / dicts prêts à afficher. Le rendu Streamlit vit dans
``dashboard.py`` ; la logique de requête est isolée ici pour être **testable**
sans lancer Streamlit (discipline de test du package).

Le dashboard est un **lecteur pur** du store (aucune écriture) : il tourne dans
un process séparé de la boucle, la lecture concurrente est garantie par le
journal WAL (ticket 004 §1).
"""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Optional

import pandas as pd

from .evaluation import decisions_to_df
from .metrics import MODES, L1Composite, normalized_global_gaps, worst_strata_modes
from .store import RunStore

# Dimensions du score sérialisées dans ``scores_json`` (clés par alias).
SCORE_DIMS = ["composite", "global", "absent_penalty", "age", "occupation",
              "genre", "motif", "distance", "length_penalty"]

# Sous-ensemble « gardé » (le veto collatéral et la vue distribution s'y réfèrent).
GUARDED_DIMS = ["age", "occupation", "genre", "motif", "distance"]

# Dimension de score → (colonne du df de décisions, clé de cerema_values.yaml).
# Même mapping que ``L1Composite.compute`` (source de vérité du scoring).
DIM_COLUMNS = {
    "age": ("age_cat", "Age"),
    "occupation": ("occupation", "occupation"),
    "genre": ("genre", "genre"),
    "motif": ("motif", "motif_deplacement"),
    "distance": ("dist_cat", "distance"),
}


def _scores_from_json(raw: Optional[str]) -> dict:
    return json.loads(raw) if raw else {}


# ── Vue Timeline ─────────────────────────────────────────────────────────────

def timeline_df(store: RunStore) -> pd.DataFrame:
    """Toutes les mutations depuis l'origine, avec score composite et par dimension.

    Jointure ``mutations × evals(train)`` sur ``node_to`` : chaque mutation porte
    le score du nœud qu'elle a produit (NULL si invalide/rejetée avant éval).
    Ajoute ``best_so_far`` : min cumulé du composite par branche (courbe du
    meilleur score), en ignorant les mutations vétoées et non évaluées.
    """
    rows = store.conn.execute(
        "SELECT m.id AS id, m.branch AS branch, m.iteration AS iteration, "
        "  m.operator AS operator, m.target_block AS target_block, "
        "  m.new_content AS new_content, m.verdict AS verdict, "
        "  m.reject_cause AS reject_cause, m.rationale AS rationale, "
        "  m.node_to AS node_to, e.scores_json AS scores_json, "
        "  m.mutation_prompt_text AS mutation_prompt_text "
        "FROM mutations m "
        "LEFT JOIN evals e ON e.node_hash=m.node_to AND e.dataset='train' "
        "ORDER BY m.branch, m.iteration, m.id").fetchall()

    records = []
    for r in rows:
        rec = {k: r[k] for k in (
            "id", "branch", "iteration", "operator", "target_block", "new_content",
            "verdict", "reject_cause", "rationale", "node_to", "mutation_prompt_text")}
        scores = _scores_from_json(r["scores_json"])
        for dim in SCORE_DIMS:
            rec[dim] = scores.get(dim)
        records.append(rec)

    df = pd.DataFrame(records, columns=(
        ["id", "branch", "iteration", "operator", "target_block", "new_content",
         "verdict", "reject_cause", "rationale", "node_to", "mutation_prompt_text"]
        + SCORE_DIMS + ["best_so_far"]))
    if df.empty:
        return df

    # Meilleur score cumulé par branche : min courant du composite retenu.
    df["best_so_far"] = pd.NA
    for branch, grp in df.groupby("branch", sort=False):
        best = None
        for idx in grp.index:
            comp = df.at[idx, "composite"]
            vetoed = df.at[idx, "verdict"] == "vetoed"
            if comp is not None and not pd.isna(comp) and not vetoed:
                best = comp if best is None else min(best, comp)
            df.at[idx, "best_so_far"] = pd.NA if best is None else best
    return df


# ── Vue DAG (lignée) ─────────────────────────────────────────────────────────

def lineage_df(store: RunStore) -> pd.DataFrame:
    """Nœuds du DAG d'optimisation (seed + nœuds de mutation), un par itération.

    Filtre ``iteration IS NOT NULL`` : écarte les nœuds d'ablation (créés sans
    itération) qui ne sont pas sur le chemin de la campagne. Chaque nœud porte
    son composite train, son parent et son ``parent2`` (merge, phase 6).
    """
    rows = store.conn.execute(
        "SELECT n.hash AS hash, n.branch AS branch, n.iteration AS iteration, "
        "  n.parent AS parent, n.parent2 AS parent2, "
        "  (SELECT json_extract(e.scores_json,'$.composite') FROM evals e "
        "   WHERE e.node_hash=n.hash AND e.dataset='train' LIMIT 1) AS composite "
        "FROM nodes n WHERE n.iteration IS NOT NULL "
        "ORDER BY n.branch, n.iteration").fetchall()
    return pd.DataFrame(
        [{k: r[k] for k in ("hash", "branch", "iteration", "parent", "parent2",
                            "composite")} for r in rows],
        columns=["hash", "branch", "iteration", "parent", "parent2", "composite"])


def lineage_edges(nodes: pd.DataFrame) -> list[tuple[str, str, bool]]:
    """Arêtes ``(parent_hash, child_hash, is_merge)`` internes au DAG affiché.

    Seules les arêtes dont les deux extrémités sont dans ``nodes`` sont gardées
    (un parent d'ablation hors périmètre ne produit pas d'arête fantôme).
    """
    present = set(nodes["hash"])
    edges: list[tuple[str, str, bool]] = []
    for _, n in nodes.iterrows():
        if n["parent"] and n["parent"] in present:
            edges.append((n["parent"], n["hash"], False))
        if n["parent2"] and n["parent2"] in present:
            edges.append((n["parent2"], n["hash"], True))
    return edges


# ── Détail d'un nœud ─────────────────────────────────────────────────────────

def node_detail(store: RunStore, node_hash: str,
                compare_to_hash: Optional[str] = None) -> Optional[dict]:
    """Prompt complet, blocs, scores tous jeux, ablation et diff vs autre nœud."""
    node = store.node(node_hash)
    if node is None:
        return None
    blocks = json.loads(node["blocks_json"])
    # Un nœud peut porter plusieurs évals d'un même jeu (params_key différents,
    # ex. import legacy) : on préfère la plus récente **avec décisions brutes**
    # (les évals sans décisions sont des artefacts partiels).
    scores_by_dataset: dict[str, dict] = {}
    for row in store.conn.execute(
            "SELECT dataset, scores_json FROM evals WHERE node_hash=? "
            "ORDER BY (decisions='[]') ASC, id DESC", (node_hash,)).fetchall():
        scores_by_dataset.setdefault(row["dataset"], _scores_from_json(row["scores_json"]))
    ablations = [
        {"bloc": a["block_name"], "method": a["method"], "value": a["value"],
         "diag": a["diag"], "scores_json": a["scores_json"]}
        for a in store.ablations(node_hash)
    ]
    # Si compare_to_hash est fourni, il prime sur le parent par défaut.
    # S'il est vide (""), on ne fait pas de diff.
    comparison_hash = compare_to_hash if compare_to_hash is not None else node["parent"]
    diff_target_node = store.node(comparison_hash) if comparison_hash else None
    diff = ""
    if diff_target_node is not None:
        fromfile_label = "parent" if comparison_hash == node["parent"] else "node"
        diff = "\n".join(difflib.unified_diff(
            diff_target_node["prompt_text"].splitlines(), node["prompt_text"].splitlines(),
            fromfile=f"{fromfile_label} {diff_target_node['hash']}", tofile=f"node {node_hash}",
            lineterm=""))
    return {
        "hash": node_hash,
        "branch": node["branch"],
        "iteration": node["iteration"],
        "parent": node["parent"],
        "parent2": node["parent2"],
        "prompt_text": node["prompt_text"],
        "blocks": blocks,
        "scores_by_dataset": scores_by_dataset,
        "ablations": ablations,
        "diff": diff,
    }


def ablation_table(detail: dict, weights: Optional[dict] = None) -> pd.DataFrame:
    """Carte d'ablation d'un nœud avec **détail par dimension** (pts de composite).

    Prend la sortie de :func:`node_detail` et ajoute, pour chaque ligne d'ablation,
    la contribution pondérée de chaque dimension au Δ du bloc (``w_d × φ_d``,
    sommant à ``value``). Pour les lignes ``shapley``, le détail est **déjà
    persisté** dans ``scores_json`` (écrit par ``loop.run_shapley``).

    Colonnes : ``bloc``, ``method``, ``value``, une par dimension, ``diag``.
    """
    from .mutation import detail_from_stored
    weights = weights or L1Composite.WEIGHTS
    dims = [d for d, w in weights.items() if w > 0]
    rows = []
    for a in detail.get("ablations", []):
        stored = _scores_from_json(a.get("scores_json"))
        contrib = detail_from_stored(stored, weights) if a["method"] == "shapley" else {}
        rows.append({"bloc": a["bloc"], "method": a["method"], "value": a["value"],
                     **{d: contrib.get(d) for d in dims}, "diag": a["diag"]})
    return pd.DataFrame(rows, columns=["bloc", "method", "value", *dims, "diag"])


# ── Vue Distribution ─────────────────────────────────────────────────────────

def _train_decisions(store: RunStore, node_hash: str) -> Optional[list[tuple]]:
    # Priorité à l'éval la plus récente avec décisions non vides (cf. node_detail).
    row = store.conn.execute(
        "SELECT decisions FROM evals WHERE node_hash=? AND dataset='train' "
        "ORDER BY (decisions='[]') ASC, id DESC LIMIT 1", (node_hash,)).fetchone()
    if row is None:
        return None
    return [tuple(d) for d in json.loads(row["decisions"])]


def distribution_view(store: RunStore, node_hash: str, cerema: dict,
                      metadata_by_id: dict[str, dict]) -> Optional[dict]:
    """Distribution modale actuelle vs EMC² pour un nœud (global + pires strates).

    Reconstruit le df de scoring depuis les **décisions brutes** stockées (aucun
    réappel LLM) et applique les mêmes helpers que la loss (`normalized_global_gaps`,
    `worst_strata_modes`).
    """
    decisions = _train_decisions(store, node_hash)
    if not decisions:
        return None
    df = decisions_to_df(decisions, metadata_by_id)
    if df.empty or "mode_cat" not in df.columns:
        return None

    counts = df["mode_cat"].value_counts()
    gaps = normalized_global_gaps(counts, cerema)
    total = int(counts.sum()) or 1
    ref = {k: v for k, v in cerema["parts_modales_2023"]["global"].items()
           if k in MODES}
    ref_sum = sum(ref.values()) or 1
    global_bars = [
        {"mode": m,
         "actual": counts.get(m, 0) / total * 100,
         "target": ref.get(m, 0) * 100.0 / ref_sum,
         "gap": gaps[m]}
        for m in MODES
    ]
    return {
        "n_decisions": int(counts.sum()),
        "global_bars": global_bars,
        "worst_strata": worst_strata_modes(df, cerema),
    }


# ── Vue Comparaison (prompts vs vérité terrain EMC²) ─────────────────────────

def _ref_shares(ref_by_mode: dict) -> dict[str, float]:
    """Parts EMC² d'une strate, restreintes aux MODES et renormalisées en %."""
    ref = {m: ref_by_mode.get(m, 0) for m in MODES}
    total = sum(ref.values()) or 1
    return {m: v * 100.0 / total for m, v in ref.items()}


def _mode_shares(df: pd.DataFrame) -> Optional[dict[str, float]]:
    counts = df["mode_cat"].value_counts()
    counts = counts[counts.index.isin(MODES)]
    total = int(counts.sum())
    if total == 0:
        return None
    return {m: counts.get(m, 0) / total * 100.0 for m in MODES}


def comparison_view(store: RunStore, node_hashes: list[str], cerema: dict,
                    metadata_by_id: dict[str, dict],
                    dimension: str = "global") -> dict:
    """Parts modales de plusieurs prompts vs la référence EMC², par strate.

    Pour chaque nœud, le df est reconstruit depuis les **décisions brutes**
    ``train`` stockées (zéro réappel LLM). ``dimension`` = ``global`` (une seule
    strate) ou une clé de :data:`DIM_COLUMNS` ; les catégories affichées sont
    celles de la référence EMC² (ordre du YAML). Structure renvoyée :

    ``{"dimension", "modes", "missing": [hash sans décisions], "categories":
    [{"cat", "n": {hash: effectif}, "bars": [{"mode", "target",
    "values": {hash: part % ou None}}]}]}``
    """
    parts = cerema["parts_modales_2023"]
    dfs: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    for h in node_hashes:
        decisions = _train_decisions(store, h)
        df = decisions_to_df(decisions, metadata_by_id) if decisions else pd.DataFrame()
        if df.empty or "mode_cat" not in df.columns:
            missing.append(h)
        else:
            dfs[h] = df

    if dimension == "global":
        cat_refs = {"global": parts["global"]}
        subset = {"global": {h: df for h, df in dfs.items()}}
    else:
        col, ref_key = DIM_COLUMNS[dimension]
        cat_refs = parts[ref_key]
        subset = {cat: {h: (df[df[col] == cat] if col in df.columns
                            else df.iloc[0:0])
                        for h, df in dfs.items()}
                  for cat in cat_refs}

    categories = []
    for cat, ref_by_mode in cat_refs.items():
        target = _ref_shares(ref_by_mode)
        shares = {h: _mode_shares(d) for h, d in subset[cat].items()}
        categories.append({
            "cat": cat,
            "n": {h: int(d["mode_cat"].isin(MODES).sum())
                  for h, d in subset[cat].items()},
            "bars": [{"mode": m, "target": target[m],
                      "values": {h: (s[m] if s else None)
                                 for h, s in shares.items()}}
                     for m in MODES],
        })
    return {"dimension": dimension, "modes": list(MODES),
            "missing": missing, "categories": categories}


# ── Vue Run (état de campagne) ───────────────────────────────────────────────

def run_status(store: RunStore, branch: str) -> dict:
    """État agrégé d'une branche : itération, acceptées, best, val, volumétrie.

    Lit ``run_state`` (snapshot de la boucle) et complète par des comptages réels
    du store (nœuds, mutations, évals par jeu). Le hit-rate de cache instrumenté
    n'est pas persisté par la boucle (il vit dans les logs de run) : la vue
    montre les volumes d'éval effectivement stockés, pas un taux estimé.
    """
    state = store.resume_state(branch) or {}
    eval_counts = {
        row["dataset"]: row["n"]
        for row in store.conn.execute(
            "SELECT dataset, COUNT(*) AS n FROM evals GROUP BY dataset").fetchall()
    }
    return {
        "branch": branch,
        "iteration": state.get("iteration"),
        "accepted": state.get("accepted"),
        "best_score": state.get("best_score"),
        "best_node": state.get("best_node"),
        "val_best": state.get("val_best"),
        "val_no_improve": state.get("val_no_improve"),
        "n_nodes": store.node_count(branch),
        "n_mutations": len(store.mutations(branch)),
        "eval_counts": eval_counts,
    }


def branches(store: RunStore) -> list[str]:
    rows = store.conn.execute(
        "SELECT DISTINCT branch FROM nodes ORDER BY branch").fetchall()
    return [r["branch"] for r in rows]


# ── Vue Pareto (phase 6, DC) ─────────────────────────────────────────────────

def pareto_view(store: RunStore, dims: Optional[list[str]] = None,
                dataset: str = "train") -> dict:
    """Front de Pareto (nœuds non dominés) + points dominés, toutes branches.

    Le calcul de dominance est **pur** (``pareto.pareto_front``) sur les losses par
    dimension reconstruites des évals stockées. Sert la vue « Pareto » du dashboard
    (compromis complémentaires) et documente d'où partent les îlots / merges.
    """
    from . import pareto
    dims = dims or pareto.DEFAULT_DIMS
    items = store.pareto_candidates(dataset)
    front = pareto.pareto_front(items, dims)
    front_hashes = {it["hash"] for it in front}
    for it in items:
        it["on_front"] = it["hash"] in front_hashes
    return {"dims": dims, "items": items, "front": front,
            "n_front": len(front), "n_total": len(items)}


# ── Vue bibliothèque de snippets (phase 6.4, DL) ─────────────────────────────

def snippets_df(store: RunStore) -> pd.DataFrame:
    """Bibliothèque d'arguments comportementaux capitalisés (triés par gain)."""
    rows = store.conn.execute(
        "SELECT id, branch, operator, block_name, content, tag_mode, tag_strata, "
        "gain, node_origin FROM snippets ORDER BY gain DESC").fetchall()
    return pd.DataFrame(
        [{k: r[k] for k in ("id", "branch", "operator", "block_name", "content",
                            "tag_mode", "tag_strata", "gain", "node_origin")}
         for r in rows],
        columns=["id", "branch", "operator", "block_name", "content", "tag_mode",
                 "tag_strata", "gain", "node_origin"])


# ── Contexte partagé (cerema + métadonnées des jeux gelés) ───────────────────

def _load_yaml(path: str | Path):
    import yaml
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def load_context(config) -> tuple[dict, dict[str, dict]]:
    """Charge (cerema, metadata_by_id) pour la vue distribution.

    ``metadata_by_id`` est reconstruit depuis les jeux gelés (train+val) : la
    jointure ``agent_id → traits`` est la même que celle du moteur.
    """
    cerema = _load_yaml(config.cerema_path)
    cols = ("age", "age_cat", "occupation", "genre", "motif", "dist_cat")
    meta: dict[str, dict] = {}
    for split in ("train", "val"):
        path = config.dataset_dir / config.dataset_version / f"{split}.jsonl"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            meta[str(r["agent_id"])] = {c: r.get(c) for c in cols}
    return cerema, meta


# ── Actions Maintenance (seules écritures : import) ──────────────────────────
#
# Ces helpers alimentent la vue « Maintenance » du dashboard (exécuter les
# commandes CLI depuis l'UI). ``export_readable`` et ``seed_blocks_for`` sont en
# lecture seule ; ``import_legacy_run`` **écrit** dans le store (seule exception
# au principe de lecteur pur, protégée côté UI par une confirmation).

def seed_blocks_for(config) -> list[dict]:
    """Blocs du prompt seed (``config.seed_prompt``) décomposés depuis prompts.yaml.

    Lève ``KeyError`` si le seed est absent — même contrat que
    ``cli.seed_blocks_from_prompts``, mais sans dépendre d'un ``RunConfig`` complet
    (le dashboard passe une config légère).
    """
    from .blocks import decompose_prompt
    prompts = _load_yaml(config.prompts_path)
    entry = prompts["prompts"].get(config.seed_prompt)
    if entry is None:
        raise KeyError(
            f"Prompt seed {config.seed_prompt!r} absent de {config.prompts_path}")
    return decompose_prompt(entry["content"])


def export_readable(store: RunStore, out_dir: str | Path) -> Path:
    """Export lisible du store (``nodes.csv`` / ``mutations.csv`` / ``history.md``).

    Enveloppe ``export.export_all`` — lecture seule. Renvoie le répertoire produit.
    """
    from .export import export_all
    return export_all(store, out_dir)


def import_legacy_run(store: RunStore, config, legacy_dir: str | Path) -> dict:
    """Rejoue un run de l'ancienne version dans le store (**écrit**).

    Reconstruit les blocs seed depuis la config puis délègue à
    ``importer.import_legacy``. Renvoie le résumé ``{nodes, mutations, evals}``.
    """
    from .importer import import_legacy
    seed_blocks = seed_blocks_for(config)
    return import_legacy(store, legacy_dir, seed_blocks,
                         branch=getattr(config, "branch", "main"))
