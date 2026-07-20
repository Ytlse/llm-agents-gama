"""CLI de calibration — phase 1 du ticket 004.

Commandes :
- ``calibrate run``      : lance (ou reprend) une campagne sur une branche ;
- ``calibrate resume``   : alias explicite de ``run`` (reprise depuis le store) ;
- ``calibrate status``   : état d'une branche (meilleur nœud, itération, #évals) ;
- ``calibrate export``   : export lisible du store (CSV + timeline Markdown) ;
- ``calibrate import``   : import one-shot des artefacts de l'ancienne version ;
- ``calibrate backtest`` : recalcule des losses sur l'historique stocké (phase 3) ;
- ``calibrate finalize`` : éval test unique + bilan avant/après + publication (phase 7) ;
- ``calibrate dashboard``: dashboard Streamlit (lecteur pur du store, phase 2).

Toute la configuration passe par ``RunConfig`` (YAML via ``--config``) — plus
aucun global mutable. Le notebook n'est plus qu'un client de ce package.

Usage (venv du projet) :
    ../../llm-agents/.venv/bin/python -m calibration.cli run --config run.yaml
    ../../llm-agents/.venv/bin/python -m calibration.cli status
    ../../llm-agents/.venv/bin/python -m calibration.cli export --out export/
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .blocks import decompose_prompt
from .evaluation import Evaluator, make_provider_call
from .export import export_all
from .loop import CalibrationLoop
from .metrics import get_metric
from .models import RunConfig
from .mutation import MutationGenerator
from .store import RunStore


# ── Chargement des ressources ────────────────────────────────────────────────

def _load_yaml(path: Path):
    import yaml
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def load_records(config: RunConfig, split: str, optional: bool = False) -> list[dict]:
    """Charge les records d'un jeu gelé (``{dataset_dir}/{version}/{split}.jsonl``).

    ``optional=True`` (jeu ``screen`` — phase 4, absent des anciennes versions) →
    renvoie une liste vide au lieu de lever si le fichier n'existe pas.
    """
    path = config.dataset_dir / config.dataset_version / f"{split}.jsonl"
    if not path.exists():
        if optional:
            return []
        raise FileNotFoundError(
            f"Jeu gelé introuvable : {path}. Générer d'abord les jeux :\n"
            f"  python -m calibration.datasets <experiment> "
            f"{config.dataset_dir} {config.dataset_version}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def seed_blocks_from_prompts(config: RunConfig) -> list[dict]:
    prompts = _load_yaml(config.prompts_path)
    entry = prompts["prompts"].get(config.seed_prompt)
    if entry is None:
        raise KeyError(f"Prompt seed {config.seed_prompt!r} absent de {config.prompts_path}")
    return decompose_prompt(entry["content"])


def metadata_by_id(records: list[dict]) -> dict[str, dict]:
    cols = ("age", "age_cat", "occupation", "genre", "motif", "dist_cat")
    return {str(r["agent_id"]): {c: r.get(c) for c in cols} for r in records}


def build_engine(config: RunConfig, with_mutator: bool = True):
    """Assemble store + évaluateur + mutateur + ressources depuis la config.

    ``with_mutator=False`` (finalisation phase 7 : pas de mutation) évite d'exiger
    une clé d'API pour le modèle de mutation → ``mutator`` renvoyé vaut ``None``.
    """
    cerema = _load_yaml(config.cerema_path)
    schema = json.loads(Path(config.schemas_path).read_text(encoding="utf-8"))[config.category]
    seed_blocks = seed_blocks_from_prompts(config)

    train = load_records(config, "train")
    val = load_records(config, "val")
    screen = load_records(config, config.screen_dataset, optional=True)
    if not screen:
        # Repli silencieux coûteux : sans jeu de screening, Shapley et le screening
        # tournent sur le train COMPLET (~5-6× plus de requêtes par coalition).
        print(f"⚠ [ALARME] jeu '{config.screen_dataset}' absent de "
              f"{config.dataset_dir}/{config.dataset_version} — évals Shapley et "
              f"screening sur le train complet ({len(train)} records au lieu de ~20 %). "
              f"Générer le jeu (filtre in_screen sur train.jsonl) pour diviser le coût.")
    meta = metadata_by_id(train + val)

    store = RunStore(config.store_path)
    metric = get_metric(config.loss, config)

    # Capacité de batch réelle du provider si non fixée dans la config.
    if not config.eval_batch_max:
        try:
            from llm_module.tasks.llm_config import get_batch_max_agents
            config.eval_batch_max = get_batch_max_agents(config.eval_provider)
        except Exception:  # noqa: BLE001 — repli : un lot = tout le jeu
            config.eval_batch_max = 0

    call_fn = make_provider_call(config, schema)
    evaluator = Evaluator(config, store, metric, cerema, meta, call_fn)

    mutator = None
    if with_mutator:
        # La clé API Google pour le modèle de mutation, alignée sur la convention du projet.
        api_key = (os.environ.get("PROVIDER_KEYS__google")
                   or os.environ.get("GEMINI_API_KEY")
                   or os.environ.get("GOOGLE_API_KEY", ""))
        if not api_key:
            raise ValueError("Clé d'API Google manquante : définissez PROVIDER_KEYS__google "
                             "dans votre environnement ou fichier .env. GEMINI_API_KEY ou "
                             "GOOGLE_API_KEY sont aussi acceptés pour le modèle de mutation.")
        mutator = MutationGenerator.default(config, cerema, api_key)

    return store, evaluator, mutator, cerema, seed_blocks, train, val, screen


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    except Exception:  # noqa: BLE001
        pass


# ── Commandes ────────────────────────────────────────────────────────────────

def cmd_run(config: RunConfig, args) -> int:
    _load_dotenv()
    if getattr(args, "islands", 0):
        config.n_islands = args.islands
    store, evaluator, mutator, cerema, seed_blocks, train, val, screen = build_engine(config)
    iterations = args.iterations or config.max_iterations

    if config.n_islands > 1:
        # Îlots parallèles (phase 6, D7) : k branches dans le même store, migration
        # en anneau, merge optionnel. Le call_fn est indépendant de la branche → il
        # est partagé par tous les îlots.
        from .islands import IslandRunner
        runner = IslandRunner(config, store, evaluator.metric, cerema,
                              evaluator.metadata_by_id, lambda cfg: evaluator.call_fn,
                              mutator, train, val, screen_records=screen)
        summary = runner.run(seed_blocks, max_iterations=iterations)
        best = summary.get("best")
        if best:
            print(f"\n✅ Îlots terminés — meilleur composite={best['composite']:.2f} "
                  f"(îlot {best['branch']}, nœud {best['hash']})")
    else:
        loop = CalibrationLoop(config, store, evaluator, mutator, cerema, train, val,
                               screen_records=screen)
        loop.run(seed_blocks, max_iterations=iterations)
    store.close()
    return 0


def cmd_status(config: RunConfig, args) -> int:
    store = RunStore(config.store_path)
    best = store.best(config.branch)
    print(f"Branche         : {config.branch}")
    print(f"Store           : {config.store_path}")
    print(f"Nœuds (branche) : {store.node_count(config.branch)}")
    print(f"Mutations       : {len(store.mutations(config.branch))}")
    state = store.resume_state(config.branch)
    if state:
        print(f"Itération       : {state['iteration']}")
        print(f"Acceptées       : {state['accepted']}")
        print(f"Meilleur score  : {state['best_score']:.2f} (nœud {state['best_node']})")
    if best:
        print(f"Best (SQL)      : composite={best['composite']:.2f} @ iter {best['iteration']}")
    store.close()
    return 0


def cmd_export(config: RunConfig, args) -> int:
    store = RunStore(config.store_path)
    out = export_all(store, args.out)
    print(f"Export → {out} (nodes.csv, mutations.csv, history.md)")
    store.close()
    return 0


def cmd_import(config: RunConfig, args) -> int:
    from .importer import import_legacy
    store = RunStore(config.store_path)
    seed_blocks = seed_blocks_from_prompts(config)
    summary = import_legacy(store, args.legacy_dir, seed_blocks, branch=config.branch)
    print(f"Import terminé : {summary}")
    store.close()
    return 0


def cmd_backtest(config: RunConfig, args) -> int:
    """Recalcule plusieurs losses sur l'historique stocké (zéro appel LLM, phase 3)."""
    from .backtest import backtest_metrics, compare_summary

    loss_names = [n.strip() for n in args.metrics.split(",") if n.strip()]
    store = RunStore(config.store_path)
    train = load_records(config, "train")
    meta = metadata_by_id(train)
    cerema = _load_yaml(config.cerema_path)
    metrics = {name: get_metric(name, config) for name in loss_names}

    df = backtest_metrics(store, meta, cerema, metrics, branch=config.branch,
                          dataset=args.dataset)
    store.close()
    if df.empty:
        print("Aucun nœud évalué à backtester (store vide ou branche inconnue).")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    summary = compare_summary(df, loss_names)
    print(f"Backtest ({summary['n_nodes']} nœuds, dataset={args.dataset}) → {args.out}")
    for name, stats in summary["losses"].items():
        print(f"  {name:14s} : final={stats['final']:.2f} "
              f"best={stats['best']:.2f} @ iter {stats['best_iteration']}")
    if "rank_correlation" in summary:
        print(f"  Corrélation de rang (Spearman) : {summary['rank_correlation']:.3f}")
    return 0


def _print_finalize_report(result: dict) -> None:
    """Affiche le bilan de finalisation (rapport + comparaison avant/après)."""
    rep, cmp = result["report"], result["comparison"]
    print(f"\n{'═'*64}\n  BILAN DE CAMPAGNE\n{'═'*64}")
    print(f"Meilleur prompt : nœud {result['best_hash']} (branche {result['best_branch']})")
    print(f"Branches        : {', '.join(rep['branches'])}")
    print(f"Acceptées (tot) : {rep['total_accepted']}")
    print(f"Évals LLM       : {rep['n_evals']} "
          f"({', '.join(f'{k}={v}' for k, v in rep['eval_counts'].items())})")
    if rep["duration_s"] is not None:
        print(f"Durée (approx.) : {rep['duration_s'] / 60:.1f} min")
    print(f"Nb de mots      : {cmp['words_before']} → {cmp['words_after']} "
          f"({cmp['words_after'] - cmp['words_before']:+d})")

    print("\nComposite avant/après (↓ = mieux) :")
    for row in cmp["by_dataset"]:
        b = f"{row['before']:.2f}" if row["before"] is not None else "—"
        a = f"{row['after']:.2f}" if row["after"] is not None else "—"
        d = f" (Δ={row['delta']:+.2f})" if "delta" in row else ""
        marker = " ← publiable" if row["dataset"] == "test" else ""
        print(f"  {row['dataset']:6s} : {b:>7s} → {a:>7s}{d}{marker}")

    if cmp["test_dims"]:
        print("\nDétail test par dimension (avant → après) :")
        for dim, v in cmp["test_dims"].items():
            if v["before"] is None or v["after"] is None:
                continue
            print(f"  {dim:14s} : {v['before']:6.2f} → {v['after']:6.2f} "
                  f"(Δ={v['delta']:+.2f})")


def cmd_finalize(config: RunConfig, args) -> int:
    """Finalise une campagne : éval test unique + bilan avant/après + publication (phase 7)."""
    _load_dotenv()
    from .publish import finalize, publish_prompt

    store, evaluator, _, cerema, seed_blocks, train, val, screen = build_engine(
        config, with_mutator=False)
    test = load_records(config, config.test_dataset, optional=True)
    if not test:
        print(f"⚠ Jeu de test absent ({config.dataset_dir}/{config.dataset_version}/"
              f"{config.test_dataset}.jsonl) : le composite test ne sera pas calculé.")
    result = finalize(store, evaluator, config, seed_blocks, test)
    if result is None:
        print("Aucun nœud évalué dans le store : lancer une campagne d'abord.")
        store.close()
        return 1

    _print_finalize_report(result)

    if args.write:
        key = publish_prompt(config.prompts_path, result["best_prompt"],
                             prefix=config.publish_prefix, activate=args.activate)
        print(f"\n✅ Prompt calibré publié dans {config.prompts_path} sous « {key} »"
              + (" (activé)" if args.activate else ""))
    else:
        print("\n(dry-run : le prompt n'a PAS été écrit — ajouter --write pour publier "
              "dans prompts.yaml, +--activate pour l'activer)")
    store.close()
    return 0


def cmd_dashboard(config: RunConfig, args) -> int:
    """Lance le dashboard Streamlit (lecteur pur du store, phase 2)."""
    import subprocess

    app = Path(__file__).with_name("dashboard.py")
    cmd = [sys.executable, "-m", "streamlit", "run", str(app)]
    if args.port:
        cmd += ["--server.port", str(args.port)]
    cmd += ["--"]
    if args.config:
        cmd += ["--config", str(args.config)]
    # Le store épinglé par la CLI prime (utile quand --config est omis).
    cmd += ["--store", str(config.store_path)]
    try:
        return subprocess.call(cmd)
    except FileNotFoundError:
        print("streamlit n'est pas installé : "
              "`../../llm-agents/.venv/bin/pip install streamlit`", file=sys.stderr)
        return 1


def _add_global_opts(parser: argparse.ArgumentParser, *, suppress: bool) -> None:
    """Ajoute ``--config`` / ``--branch``, acceptés avant OU après la sous-commande.

    Sur le parser principal : défauts normaux (``None``). Sur chaque sous-parser :
    ``default=SUPPRESS`` → si l'option n'est pas donnée après la sous-commande,
    elle n'écrase pas la valeur éventuellement lue avant.
    """
    kw = {"default": argparse.SUPPRESS} if suppress else {}
    parser.add_argument("--config", type=Path, help="YAML RunConfig (défauts sinon)", **kw)
    parser.add_argument("--branch", help="surcharge la branche de la config", **kw)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="calibrate", description=__doc__)
    _add_global_opts(p, suppress=False)
    sub = p.add_subparsers(dest="command", required=True)

    def _sub(name: str, **kw):
        s = sub.add_parser(name, **kw)
        _add_global_opts(s, suppress=True)
        return s

    r = _sub("run", help="lance/reprend une campagne")
    r.add_argument("--iterations", type=int, default=0)
    r.add_argument("--islands", type=int, default=0,
                   help="nombre d'îlots parallèles (phase 6 ; >1 → multi-branches)")
    r.set_defaults(func=cmd_run)

    rs = _sub("resume", help="reprend une campagne (= run)")
    rs.add_argument("--iterations", type=int, default=0)
    rs.add_argument("--islands", type=int, default=0,
                    help="nombre d'îlots parallèles (phase 6 ; >1 → multi-branches)")
    rs.set_defaults(func=cmd_run)

    _sub("status", help="état de la branche").set_defaults(func=cmd_status)

    e = _sub("export", help="export lisible du store")
    e.add_argument("--out", type=Path, default=Path("calibration_results/export"))
    e.set_defaults(func=cmd_export)

    im = _sub("import", help="import des artefacts de l'ancienne version")
    im.add_argument("legacy_dir", type=Path)
    im.set_defaults(func=cmd_import)

    bt = _sub("backtest", help="recalcule des losses sur l'historique (zéro LLM)")
    bt.add_argument("--metrics", default="l1_composite,emd_jsd",
                    help="losses à comparer, séparées par des virgules")
    bt.add_argument("--dataset", default="train")
    bt.add_argument("--out", type=Path, default=Path("calibration_results/backtest.csv"))
    bt.set_defaults(func=cmd_backtest)

    fin = _sub("finalize", help="éval test unique + bilan avant/après + publication (phase 7)")
    fin.add_argument("--write", action="store_true",
                     help="écrit le prompt calibré dans prompts.yaml (défaut : dry-run)")
    fin.add_argument("--activate", action="store_true",
                     help="avec --write : active le prompt publié (champ 'active')")
    fin.set_defaults(func=cmd_finalize)

    d = _sub("dashboard", help="dashboard Streamlit (lecteur du store)")
    d.add_argument("--port", type=int, default=0)
    d.set_defaults(func=cmd_dashboard)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    config = RunConfig.from_yaml(args.config) if args.config else RunConfig()
    if args.branch:
        config.branch = args.branch
    return args.func(config, args)


if __name__ == "__main__":
    raise SystemExit(main())
