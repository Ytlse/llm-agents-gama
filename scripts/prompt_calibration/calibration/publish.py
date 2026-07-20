"""Finalisation & publication d'une campagne — phase 7 du ticket 004.

La consolidation d'une campagne tient en trois gestes, tous outillés ici :

1. **Éval test unique** — le meilleur prompt (plus faible composite ``train``,
   toutes branches confondues) est évalué **une seule fois** sur le jeu ``test``
   gelé, jamais vu par la boucle → c'est le chiffre publiable. Le prompt seed est
   évalué sur le même jeu → base de comparaison **avant/après**.
2. **Rapport chiffré** — composite par jeu (train/val/test) du seed et du meilleur,
   nombre de mots, nombre d'évals LLM consommées, acceptées, durée approximative.
3. **Publication** — le prompt calibré est écrit dans ``prompts.yaml`` sous une clé
   ``{publish_prefix}_{horodatage}`` (convention historique), éventuellement activé.

Le calcul est **pur** partout où c'est possible (rapport, comparaison, écriture
YAML testable sur fichier temporaire) ; seule l'éval test passe par l'``Evaluator``
(donc par le cache du store — relancer la finalisation ne recompute rien).

L'écriture dans ``prompts.yaml`` (fichier de configuration **de production** : le
prompt calibré est envoyé à chaque décision d'itinéraire) est une action à effet
durable → la CLI la protège par un drapeau ``--write`` explicite (défaut : dry-run
qui montre le diff sans modifier le fichier).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .blocks import blocks_to_prompt, prompt_word_count
from .evaluation import Evaluator
from .models import RunConfig, Scores
from .store import RunStore

# Dimensions rapportées dans la comparaison avant/après (mêmes que le veto/Pareto).
_REPORT_DIMS = ["composite", "global", "age", "occupation", "genre", "motif", "distance"]


def campaign_report(store: RunStore) -> dict:
    """Statistiques finales d'une campagne (lecture pure du store).

    Agrège l'état de toutes les branches (itérations, acceptées, meilleur score),
    la volumétrie d'éval consommée (par jeu + total) et la durée approximative
    (premier→dernier horodatage d'éval).
    """
    branch_rows = store.conn.execute(
        "SELECT DISTINCT branch FROM nodes ORDER BY branch").fetchall()
    branches = [r["branch"] for r in branch_rows]

    per_branch = {}
    total_accepted = 0
    for br in branches:
        st = store.resume_state(br) or {}
        per_branch[br] = {
            "iteration": st.get("iteration"),
            "accepted": st.get("accepted"),
            "best_score": st.get("best_score"),
            "best_node": st.get("best_node"),
        }
        total_accepted += st.get("accepted") or 0

    eval_counts = {
        row["dataset"]: row["n"]
        for row in store.conn.execute(
            "SELECT dataset, COUNT(*) AS n FROM evals GROUP BY dataset").fetchall()
    }
    started, ended = store.eval_span()
    return {
        "branches": branches,
        "per_branch": per_branch,
        "total_accepted": total_accepted,
        "eval_counts": eval_counts,
        "n_evals": sum(eval_counts.values()),
        "started_at": started,
        "ended_at": ended,
        "duration_s": _duration_seconds(started, ended),
    }


def _duration_seconds(started: Optional[str], ended: Optional[str]) -> Optional[float]:
    if not started or not ended:
        return None
    try:
        a = datetime.fromisoformat(started)
        b = datetime.fromisoformat(ended)
        return max(0.0, (b - a).total_seconds())
    except ValueError:
        return None


def build_comparison(seed_blocks: list[dict], best_blocks: list[dict],
                     seed_scores: dict[str, Scores],
                     best_scores: dict[str, Scores]) -> dict:
    """Comparaison **avant/après** entre le prompt seed et le meilleur prompt.

    ``seed_scores`` / ``best_scores`` : ``dataset → Scores`` (train/val/test selon
    disponibilité). Renvoie, par jeu, le composite avant/après et son delta
    (négatif = amélioration), plus le nombre de mots avant/après.
    """
    datasets = ["train", "val", "test"]
    by_dataset = []
    for ds in datasets:
        sb, bb = seed_scores.get(ds), best_scores.get(ds)
        if sb is None and bb is None:
            continue
        row = {"dataset": ds,
               "before": sb.composite if sb else None,
               "after": bb.composite if bb else None}
        if sb is not None and bb is not None:
            row["delta"] = bb.composite - sb.composite
        by_dataset.append(row)

    # Détail par dimension sur le jeu test (le chiffre publiable) si disponible.
    dims = {}
    st, bt = seed_scores.get("test"), best_scores.get("test")
    if st is not None and bt is not None:
        sd, bd = st.model_dump(by_alias=True), bt.model_dump(by_alias=True)
        dims = {d: {"before": sd.get(d), "after": bd.get(d),
                    "delta": (bd.get(d, 0.0) - sd.get(d, 0.0))}
                for d in _REPORT_DIMS}

    return {
        "by_dataset": by_dataset,
        "test_dims": dims,
        "words_before": prompt_word_count(seed_blocks),
        "words_after": prompt_word_count(best_blocks),
    }


def finalize(store: RunStore, evaluator: Evaluator, config: RunConfig,
             seed_blocks: list[dict], test_records: list[dict]) -> Optional[dict]:
    """Évalue le meilleur prompt (+ le seed) sur ``test`` et produit le bilan complet.

    Le meilleur nœud = plus faible composite ``train`` toutes branches confondues.
    Les évals ``test`` passent par le cache : une finalisation rejouée ne rappelle
    pas le LLM. Renvoie ``None`` si aucun nœud n'a été évalué (store vide).
    """
    best = store.best_overall("train")
    if best is None:
        return None
    best_hash = best["hash"]
    best_blocks = store.node_blocks(best_hash)

    seed_hash = store.get_or_create_node(seed_blocks, branch=config.branch)

    # Éval test unique du meilleur ET du seed (base de comparaison publiable).
    if test_records:
        evaluator.evaluate(best_hash, best_blocks, config.test_dataset, test_records,
                           desc="test (best)")
        evaluator.evaluate(seed_hash, seed_blocks, config.test_dataset, test_records,
                           desc="test (seed)")

    best_scores = store.scores_by_dataset(best_hash)
    seed_scores = store.scores_by_dataset(seed_hash)

    return {
        "best_hash": best_hash,
        "best_branch": best["branch"],
        "best_prompt": blocks_to_prompt(best_blocks),
        "best_blocks": best_blocks,
        "report": campaign_report(store),
        "comparison": build_comparison(seed_blocks, best_blocks, seed_scores, best_scores),
        "best_scores": {k: v.model_dump(by_alias=True) for k, v in best_scores.items()},
        "seed_scores": {k: v.model_dump(by_alias=True) for k, v in seed_scores.items()},
    }


def publish_key(prefix: str, when: Optional[datetime] = None) -> str:
    """Clé de publication ``{prefix}_{YYYYMMDD_HHMM}`` (convention historique)."""
    when = when or datetime.now(timezone.utc)
    return f"{prefix}_{when:%Y%m%d_%H%M}"


def publish_prompt(prompts_path: str | Path, prompt_text: str, *,
                   prefix: str = "calibrated", key: Optional[str] = None,
                   activate: bool = False) -> str:
    """Écrit le prompt calibré dans ``prompts.yaml`` sous une nouvelle clé.

    Ne modifie **aucune** entrée existante (ajout seul) ; ``activate=True`` met à
    jour le champ ``active``. Préserve l'ordre et le style bloc pour rester lisible
    en diff git. Renvoie la clé écrite.
    """
    import yaml

    path = Path(prompts_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data.setdefault("prompts", {})
    key = key or publish_key(prefix)
    data["prompts"][key] = {"content": prompt_text}
    if activate:
        data["active"] = key
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100000,
                       default_flow_style=False),
        encoding="utf-8")
    return key
