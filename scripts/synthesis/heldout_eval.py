"""Évalue la lignée épinglée sur un jeu gelé JAMAIS VU par la boucle (action A4).

    python -m scripts.synthesis.heldout_eval [--dataset test] [--dry-run] [--provider …]

**Le problème.** Toute la calibration a été optimisée *et* mesurée sur ``train``
(et sur son sous-échantillon ``screen``). Le store ne portait aucune évaluation
sur ``test`` : le chiffre qui dit ce que vaut le prompt **hors de ce sur quoi il
a été optimisé** n'existait pas. Un composite d'entraînement n'est pas un
résultat publiable — il ne distingue pas un prompt qui a compris la population
d'un prompt qui a mémorisé 298 personas.

**Ce que fait ce script.** Il rejoue les nœuds de la lignée épinglée dans
``sources.yaml`` sur le jeu demandé (``test`` par défaut), sous le régime
d'évaluation de ``run.yaml``, et écrit les résultats **dans le store**, à
l'endroit exact où ``calibrate reeval`` les écrit. La page les lit ensuite par
``frames.read_store_history``, qui accepte déjà ``train``/``val``/``test`` : rien
à recopier dans un fichier intermédiaire.

**Ce qu'il ne fait pas.** Aucun découpage de lots ni aucune boucle de rattrapage
maison : l'``Evaluator`` du moteur s'en charge, avec les défenses de l'action A10
(comparaison personas envoyés / décisions rendues, re-tir du lot incomplet par
moitiés, refus de mettre en cache une éval sous le plancher de couverture). A3 a
mesuré 29 lots amputés sur 128 en produisant sa mesure : un lotissement réécrit
pour l'occasion scorerait sur une sous-population sans que rien ne le signale.

**Ce qu'il refuse de faire.** Comparer le composite ``train`` au composite
``test`` tels quels. Les deux jeux n'ont pas le même effectif — 298 personnes
contre 66 — et les divergences par strate (JSD, EMD) sont biaisées vers le haut
quand les effectifs sont petits : A3 a mesuré +5,02 points de composite pour la
seule réduction de 881 personnes à 81, à décisions inchangées. Le témoin qui
neutralise cet effet est calculé par la page (``build.build_size_control``), sans
un seul appel LLM, en rééchantillonnant les décisions ``train`` déjà stockées à
l'effectif du ``test``. Ce script en rappelle l'existence dans son résumé, pour
qu'on ne publie pas l'écart brut.

Reprise : les évals sont adressées par contenu dans le store. Un rejeu interrompu
par le quota reprend là où il s'est arrêté — la granularité est le **nœud**, donc
un nœud terminé est acquis ; un nœud interrompu ne laisse rien.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .sources import REPO_ROOT, import_calibration, load_manifest

# Jeu par défaut. `test` est le seul jeu que la boucle n'a jamais vu : `val` sert
# à l'arrêt anticipé (elle a donc influencé la sélection des prompts), `screen`
# est un sous-ensemble strict du `train`.
DEFAULT_DATASET = "test"

# Lots de 8 personas — même raison que pour l'action A3 : à 15 (capacité déduite
# du provider), le modèle rend un JSON valide mais amputé de personas. Le
# découpage n'entre pas dans ``eval_params_key`` : il change le nombre d'appels,
# pas la mesure.
DEFAULT_BATCH = 8

# Nœuds mesurés par défaut : les deux extrémités de la lignée. C'est le couple que
# la page oppose partout ailleurs (matrice de synthèse, jeu commun), et le seul
# dont le coût tient à coup sûr dans un reliquat de quota. ``--all`` mesure la
# chaîne entière quand le seau le permet.
NODE_CHOICES = ("ends", "all")


def select_nodes(chain: list[str], which: str) -> list[dict]:
    """Nœuds à mesurer dans la chaîne seed → feuille, avec leur rôle.

    Séparée du CLI pour être testable sans store ni provider. Une chaîne d'un
    seul nœud n'a pas d'extrémités à opposer : c'est une erreur, pas une mesure
    dégradée.
    """
    if len(chain) < 2:
        raise ValueError(f"La lignée n'a que {len(chain)} nœud(s) : "
                         f"pas de graine à opposer à la feuille.")
    if which == "ends":
        picked = [(0, chain[0]), (len(chain) - 1, chain[-1])]
    elif which == "all":
        picked = list(enumerate(chain))
    else:
        raise ValueError(f"Sélection inconnue : {which!r} "
                         f"(attendu : {', '.join(NODE_CHOICES)})")
    out = []
    for rank, node_hash in picked:
        if rank == 0:
            role, label = "seed", "Graine"
        elif rank == len(chain) - 1:
            role, label = "leaf", "Meilleur prompt"
        else:
            role, label = "step", f"Étape {rank}"
        out.append({"role": role, "label": label, "node": node_hash,
                    "short": node_hash[:8], "rank": rank,
                    "n_nodes_in_lineage": len(chain)})
    return out


def dataset_profile(dataset_dir: Path, splits=("train", "val", "test", "screen")) -> dict:
    """Ce que sont vraiment les jeux gelés : effectifs, recouvrement, contenu.

    Trois faits sont établis **sur pièces** plutôt que supposés, parce qu'ils
    changent le sens du mot « généralisation » :

    - ``agents_shared_with_train`` : si le test partageait ses personnes avec le
      train, la généralisation porterait sur des *trajets* et non sur des
      *individus* — affirmation beaucoup plus faible ;
    - ``n_agents`` : c'est l'effectif, donc le facteur qui biaise les divergences
      par strate vers le haut. Un écart de niveau entre deux jeux d'effectifs
      différents ne prouve rien tant qu'il n'est pas neutralisé ;
    - ``with_memory`` : la part de records portant la section ``**Historique :**``.
      ``calibration.datasets`` la retire de ``val`` et ``test`` (la mémoire
      STM/LTM du run source n'est pas reproductible) et la garde dans le
      ``train``. Les deux jeux ne présentent donc pas la même *forme* d'entrée au
      modèle, et le lecteur doit le savoir avant d'attribuer un écart au prompt.
    """
    profile: dict[str, dict] = {}
    agents_by_split: dict[str, set] = {}
    for split in splits:
        path = Path(dataset_dir) / f"{split}.jsonl"
        if not path.exists():
            continue
        records = [json.loads(line)
                   for line in path.read_text(encoding="utf-8").splitlines()
                   if line.strip()]
        agents = {str(r["agent_id"]) for r in records}
        agents_by_split[split] = agents
        with_memory = sum(1 for r in records
                          if "**Historique" in (r.get("section") or ""))
        profile[split] = {
            "n_records": len(records),
            "n_agents": len(agents),
            "with_memory": with_memory,
            "memory_share": with_memory / len(records) if records else None,
        }
    train_agents = agents_by_split.get("train", set())
    for split, entry in profile.items():
        shared = len(agents_by_split[split] & train_agents) if split != "train" else None
        entry["agents_shared_with_train"] = shared
    return profile


def split_rule(dataset_dir: Path) -> Optional[str]:
    """Règle de découpage déclarée par le manifeste des jeux gelés."""
    path = Path(dataset_dir) / "manifest.yaml"
    if not path.exists():
        return None
    import yaml
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("split_rule")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", help="manifeste de sources (défaut : sources.yaml)")
    parser.add_argument("--run-config", default="run.yaml",
                        help="config du moteur de calibration (défaut : run.yaml)")
    parser.add_argument("--dataset", default=DEFAULT_DATASET,
                        help=f"jeu gelé à mesurer (défaut : {DEFAULT_DATASET})")
    parser.add_argument("--nodes", default="ends", choices=NODE_CHOICES,
                        help="ends : graine et feuille (défaut) ; all : toute la lignée")
    parser.add_argument("--batch", type=int, default=DEFAULT_BATCH,
                        help=f"personas par requête (défaut : {DEFAULT_BATCH})")
    parser.add_argument("--workers", type=int, default=0,
                        help="requêtes en vol (défaut : eval_workers de la config)")
    parser.add_argument("--provider", default=None,
                        help="surcharge eval_provider (ex. google2 : seconde clé, "
                             "seau de quota distinct — clé de cache distincte, "
                             "réservé aux mesures)")
    parser.add_argument("--dry-run", action="store_true",
                        help="affiche le plan et le coût exact, sans aucun appel LLM")
    args = parser.parse_args(argv)

    manifest = load_manifest(args.config)
    repo = manifest.get("arms.calibration.repo", "prompt_calibration")
    calibration, engine_error = import_calibration(repo)
    if calibration is None:
        print(f"[erreur] {engine_error}", file=sys.stderr)
        return 2

    pinned = manifest.get("arms.calibration.lineage") or {}
    leaf = pinned.get("leaf")
    if not leaf:
        print("[erreur] Aucune feuille de lignée épinglée "
              "(arms.calibration.lineage.leaf).", file=sys.stderr)
        return 2

    dataset_dir = manifest.path_of("arms.calibration.datasets")
    if dataset_dir and dataset_dir.exists():
        rule = split_rule(dataset_dir)
        profile = dataset_profile(dataset_dir)
        print(f"Jeux gelés : {dataset_dir.relative_to(REPO_ROOT)}")
        if rule:
            print(f"Règle de découpage : {rule}")
        for split, entry in profile.items():
            shared = entry["agents_shared_with_train"]
            shared_txt = ("—" if shared is None
                          else f"{shared} personne(s) en commun avec le train")
            memory = entry["memory_share"]
            memory_txt = ("historique absent" if not memory
                          else f"historique sur {memory:.0%} des records")
            print(f"  {split:<6} {entry['n_records']:>4} décisions, "
                  f"{entry['n_agents']:>3} personnes — {shared_txt}, {memory_txt}")

    engine_root = REPO_ROOT / repo
    cwd = Path.cwd()
    os.chdir(engine_root)
    try:
        from calibration.cli import (_fmt_local, _load_dotenv, _resume_after,
                                     build_engine, load_records)
        from calibration.evaluation import (EvaluationAborted, InsufficientCoverage,
                                            batches_from_records)
        from calibration.models import RunConfig
        from calibration.reeval import lineage_chain, resolve_node
        from calibration.store import RunStore

        _load_dotenv()
        config = RunConfig.from_yaml(Path(args.run_config))
        if args.provider:
            print(f"\n  🔑 éval : provider {args.provider} (au lieu de "
                  f"{config.eval_provider}) — seau de quota distinct, clé de cache "
                  f"distincte. Acceptable pour une MESURE (même modèle interrogé).")
            config.eval_provider = args.provider
        config.eval_batch_max = args.batch
        if args.workers:
            config.eval_workers = args.workers

        # Garde de quota : un cooldown actif signifie que le seau est éteint. On ne
        # le contourne pas — on le signale et on s'arrête.
        guard = RunStore(config.store_path)
        cooldown = guard.get_cooldown()
        guard.close()
        remaining = ((cooldown["resume_after"] - datetime.now(timezone.utc)).total_seconds()
                     if cooldown else 0.0)
        if remaining > 0 and not args.dry_run:
            print(f"⏸️  Cooldown quota actif encore {remaining / 3600:.1f} h "
                  f"({cooldown['reason']}) — rien à faire.")
            return 0

        store, evaluator, _mut, _cerema, _seed, _train, _val, _screen = build_engine(
            config, with_mutator=False)
        try:
            chain = lineage_chain(store, resolve_node(store, leaf))
            plan = select_nodes(chain, args.nodes)
            records = load_records(config, args.dataset)
            params_key = config.eval_params_key()
            n_batches = len(batches_from_records(
                records, config.eval_batch_max,
                prod_option_handling=config.prod_option_handling))
            for entry in plan:
                entry["cached"] = store.cached_eval(
                    entry["node"], args.dataset, params_key) is not None
            to_pay = [p for p in plan if not p["cached"]]

            print()
            print(f"Lignée     : {chain[0][:8]} → {chain[-1][:8]} ({len(chain)} nœuds) — "
                  f"{len(plan)} mesuré(s) ({args.nodes})")
            print(f"Jeu        : {args.dataset} ({len(records)} décisions, "
                  f"{len({r['agent_id'] for r in records})} personnes)")
            print(f"Clé d'éval : {params_key}")
            print(f"À payer    : {len(to_pay)}/{len(plan)} éval(s) × {n_batches} lot(s) "
                  f"= {len(to_pay) * n_batches} appel(s) LLM avant re-tirs "
                  f"(+~16 % mesurés par A10 → ≈ {round(len(to_pay) * n_batches * 1.16)}), "
                  f"lots de {config.eval_batch_max} personas, {config.eval_rpm} req/min "
                  f"→ ≳ {len(to_pay) * n_batches / max(1, config.eval_rpm):.0f} min")
            for entry in plan:
                print(f"  {'cache' if entry['cached'] else 'à payer':>7}  "
                      f"{entry['short']} — {entry['label']}")

            if args.dry_run:
                print("\n--dry-run : aucun appel LLM émis.")
                return 0

            paid = 0
            for i, entry in enumerate(plan, 1):
                if entry["cached"]:
                    print(f"  [{i}/{len(plan)}] {entry['short']} — cache")
                    continue
                blocks = store.node_blocks(entry["node"])
                if blocks is None:
                    print(f"  [{i}/{len(plan)}] {entry['short']} — blocs introuvables, "
                          f"ignoré")
                    continue
                try:
                    result, _df = evaluator.evaluate(
                        entry["node"], blocks, args.dataset, records,
                        desc=f"{args.dataset} {entry['short']}")
                except EvaluationAborted as exc:
                    # Même conduite que `calibrate reeval` : on PERSISTE la date de
                    # reprise plutôt que de laisser la commande suivante marteler une
                    # API épuisée. Le seau journalier du free tier Google se
                    # réinitialise à minuit **Pacific**, pas à minuit UTC.
                    resume, reason = _resume_after(config, exc)
                    guard = RunStore(config.store_path)
                    guard.set_cooldown(resume, reason)
                    guard.close()
                    print(f"\n⏸️  {exc}\n   Reprise autorisée {_fmt_local(resume)} "
                          f"({reason}).\n   Relancer la même commande après le reset : "
                          f"les nœuds déjà payés sont servis par le cache.")
                    return 2
                except InsufficientCoverage as exc:
                    # Refus AVANT écriture : mieux vaut un nœud manquant qu'un
                    # composite calculé sur une sous-population.
                    print(f"  🚨 [ALARME] [{i}/{len(plan)}] {entry['short']} — {exc}")
                    continue
                paid += 1
                print(f"  [{i}/{len(plan)}] {entry['short']} — composite moteur "
                      f"{result.scores.composite:.2f}")
        finally:
            store.close()
    finally:
        os.chdir(cwd)

    print(f"\nÉcrit dans le store : {paid} éval(s) sur « {args.dataset} ».")
    print("⚠ Ne pas publier l'écart train → test brut : les deux jeux n'ont pas le "
          "même effectif, et les divergences par strate sont biaisées vers le haut "
          "à petits effectifs. Le témoin est calculé par la page.")
    print("Régénérer la page : make synthesis")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
