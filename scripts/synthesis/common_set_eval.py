"""Ré-évalue graine et meilleur prompt sur le jeu commun (action A3).

    python -m scripts.synthesis.common_set_eval [--dry-run] [--provider …]

**Le problème.** Le volet 2 de la page de synthèse est scoré sur les *personas
gelés* (``calibration_datasets/v1``), c'est-à-dire un sous-ensemble d'un run de
mars antérieur, tandis que le volet 1 est scoré sur le run épinglé dans
``sources.yaml``. Les deux colonnes ne portent donc pas sur la même population :
les comparer revient à comparer deux mesures faites sur deux substrats.

**Ce que fait ce script.** Il rejoue les deux extrémités de la lignée épinglée —
la graine et la feuille — sur un échantillon **du run épinglé**, sous le régime
d'évaluation épinglé, et écrit les décisions obtenues au format que la page
consomme (``arms.calibration.common_set_eval`` du manifeste).

**Ce qu'il ne fait pas.** Aucun découpage de lots ni aucune boucle de rattrapage
maison : l'``Evaluator`` du moteur de calibration s'en charge, avec les défenses
posées par l'action A10 (comparaison personas envoyés / décisions rendues, re-tir
du lot incomplet par moitiés, refus de mettre en cache une éval sous le plancher
de couverture). Ré-implémenter ce découpage réintroduirait exactement le défaut
que A10 vient de corriger — une mesure calculée sur une sous-population, sans que
rien ne le signale.

Reprise : les évals sont mises en cache dans le store, adressées par contenu. Un
rejeu interrompu par le quota reprend là où il s'est arrêté ; un rejeu déjà
complet ne coûte aucun appel.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .sources import REPO_ROOT, import_calibration, load_manifest

# ── Échantillon du jeu commun — règle GELÉE ──────────────────────────────────
#
# Même logique que les jeux gelés de ``calibration_datasets/v1`` (cf.
# ``calibration/datasets.py``) : affectation **par personne**, par un hash sha256
# stable de l'``agent_id`` — jamais ``hash()``, salé par interpréteur — puis
# rapport de couverture sur les strates Cerema. Toutes les décisions d'une
# personne retenue sont conservées, aucune n'est coupée en deux.
#
# Une seule chose change, et c'est délibéré : le hash est **namespacé**. Reprendre
# ``sha256(agent_id) % 100 < k`` tel quel choisirait un préfixe de l'intervalle
# train ([0, 70)) — l'échantillon serait alors composé à 100 % de personas du
# split sur lequel la calibration a été optimisée, ce qui flatterait la feuille.
# Le préfixe de namespace décorrèle le tirage du découpage train/val/test : la
# composition de l'échantillon reflète celle de la population (≈ 70/15/15).
SAMPLE_NAMESPACE = "common_set_v1"
SAMPLE_MODULUS = 1000

# Seuil gelé. Choisi par balayage croissant : c'est le plus petit seuil dont le
# rapport de couverture du moteur est **propre**, c'est-à-dire dont toutes les
# strates Cerema présentes dans le run atteignent ``COVERAGE_MIN_COUNT`` (5).
# En dessous (k=83, 424 décisions), la tranche d'âge 70-74 est vide : la dimension
# `age` du composite serait calculée sur un support amputé, donc non comparable au
# volet 1. Le seuil est FIGÉ ici plutôt que recalculé à chaque exécution — sans
# quoi la moindre donnée ajoutée changerait l'échantillon en silence.
SAMPLE_BUCKET_MAX = 99

# Nom de jeu sous lequel les évals sont mises en cache dans le store. Distinct de
# train/val/test à dessein : la page ne lit que ces trois-là pour la trajectoire
# des prompts (``frames.read_store_history``), donc ces évals ne peuvent pas se
# mêler aux courbes de la calibration.
DATASET_NAME = "common_set_v1"

# Lots de 8 personas. À 15 (capacité déduite du provider), le modèle rend un JSON
# valide mais amputé de personas — mesuré par A10 : 4 lots sur 12 incomplets.
# Ne change pas la mesure (le découpage n'entre pas dans ``eval_params_key``),
# seulement le nombre d'appels.
DEFAULT_BATCH = 8

SCHEMA = "calibration_on_common_set/v1"

# Colonnes écrites pour chaque décision : exactement la trame de scoring de la
# page (``frames.decisions_frame``), plus le mode brut rendu par le modèle.
COLUMNS = ["agent_id", "mode", "mode_cat", "weight",
           "genre", "age_cat", "occupation", "motif", "dist_cat"]


def sample_bucket(agent_id: str) -> int:
    """Bucket stable [0, ``SAMPLE_MODULUS``) d'une personne dans l'échantillon."""
    digest = hashlib.sha256(f"{SAMPLE_NAMESPACE}:{agent_id}".encode()).hexdigest()
    return int(digest, 16) % SAMPLE_MODULUS


def in_sample(agent_id: str) -> bool:
    return sample_bucket(agent_id) < SAMPLE_BUCKET_MAX


def sample_rule() -> str:
    return (f'sha256("{SAMPLE_NAMESPACE}:" + agent_id) % {SAMPLE_MODULUS} '
            f'< {SAMPLE_BUCKET_MAX}')


def build_sample(run_dir: Path) -> tuple[list[dict], dict]:
    """Décisions du run épinglé retenues dans l'échantillon, + descriptif.

    Les records sont construits par le moteur lui-même (``build_decision_records``),
    donc au format exact qu'attend l'évaluateur : le texte persona du run, son
    contexte météo, ses options d'itinéraire, et les traits joints depuis
    ``population_*.json``. Une section non rattachable est une anomalie, pas une
    ligne silencieusement perdue — on refuse alors de produire l'échantillon.
    """
    from calibration.datasets import coverage_report, split_of
    from calibration.evaluation import parse_option_modes
    from calibration.exchanges import itinerary_entries
    from calibration.metadata import build_decision_records, load_population

    exchanges = run_dir / "llm_exchanges.jsonl"
    candidates = sorted(p for p in run_dir.glob("population_*[0-9].json"))
    if not exchanges.exists() or not candidates:
        raise FileNotFoundError(
            f"Le run {run_dir} ne porte pas les deux sources nécessaires : "
            f"llm_exchanges.jsonl et population_*.json.")
    entries = itinerary_entries(exchanges)
    traits = load_population(candidates[0])
    records, anomalies = build_decision_records(entries, traits)
    if anomalies:
        causes = Counter(a["cause"] for a in anomalies)
        raise ValueError(f"{len(anomalies)} section(s) non rattachée(s) au run "
                         f"({dict(causes)}) — échantillon refusé.")

    kept = [r for r in records if in_sample(r["agent_id"])]
    for rec in kept:
        # Comme ``cli.load_records`` : les modes d'option sont extraits une fois du
        # texte gelé, et servent de référence pour associer un index tiré à un mode.
        rec["option_modes"] = parse_option_modes(rec.get("section", ""))
    unparsed = sum(1 for r in kept if not r["option_modes"])
    if unparsed:
        print(f"⚠ [ALARME] {unparsed}/{len(kept)} records sans liste d'options "
              f"exploitable — le mode retombera sur l'étiquette du LLM.")

    coverage, warnings = coverage_report({DATASET_NAME: kept})
    # Une strate vide dans le run entier ne peut pas être remplie par un
    # échantillonnage, quel qu'il soit : la distinguer évite de faire passer une
    # propriété du run pour un défaut du tirage. Le run épinglé ne contient aucun
    # trajet de plus de 50 km — le train gelé non plus.
    _cov_run, warnings_run = coverage_report({DATASET_NAME: records})
    empty_in_run = {w.rsplit(":", 1)[0] for w in warnings_run
                    if w.endswith("effectif 0 < 5")}
    warnings = [w + (" (strate vide dans le run entier)"
                     if w.rsplit(":", 1)[0] in empty_in_run else "")
                for w in warnings]
    agents = {r["agent_id"] for r in kept}
    info = {
        "run": str(run_dir.relative_to(REPO_ROOT)) if run_dir.is_relative_to(REPO_ROOT)
        else str(run_dir),
        "dataset": DATASET_NAME,
        "rule": sample_rule(),
        "namespace": SAMPLE_NAMESPACE,
        "modulus": SAMPLE_MODULUS,
        "bucket_max": SAMPLE_BUCKET_MAX,
        "n_records": len(kept),
        "n_agents": len(agents),
        "n_run_records": len(records),
        "n_run_agents": len({r["agent_id"] for r in records}),
        # Composition en splits gelés : dit quelle part de l'échantillon tombe
        # dans le train sur lequel la calibration a été optimisée. Ce n'est pas une
        # fuite (les trajets, les contextes et les dates viennent d'un autre run),
        # mais le lecteur doit pouvoir en juger.
        "splits": dict(Counter(split_of(a) for a in agents)),
        "coverage": coverage[DATASET_NAME],
        "coverage_warnings": warnings,
    }
    return kept, info


def resolve_prompts(store, leaf: str) -> list[dict]:
    """Graine et feuille de la lignée épinglée — les deux extrémités mesurées.

    La graine n'est pas codée en dur : elle est le premier nœud de la chaîne que
    la page elle-même affiche (``reeval.lineage_chain``, qui replie sur les arêtes
    de mutation, sans quoi la lignée perd sa graine).
    """
    from calibration.reeval import lineage_chain, resolve_node

    leaf_hash = resolve_node(store, leaf)
    chain = lineage_chain(store, leaf_hash)
    if len(chain) < 2:
        raise ValueError(f"La lignée de {leaf_hash[:8]} n'a qu'un nœud : "
                         f"pas de graine à comparer.")
    out = []
    for role, label, node_hash in (("seed", "Graine", chain[0]),
                                   ("leaf", "Meilleur prompt", chain[-1])):
        row = store.node(node_hash)
        out.append({"role": role, "label": label, "node": node_hash,
                    "short": node_hash[:8],
                    "branch": (row["branch"] if row is not None else "—"),
                    "n_nodes_in_lineage": len(chain)})
    return out


def _rows_from_frame(df) -> list[list]:
    """DataFrame de décisions → lignes compactes, dans l'ordre de ``COLUMNS``.

    Le df de l'évaluateur porte les métadonnées **par décision** (elles viennent du
    record du lot, pas d'un index par agent) : une personne qui fait trois trajets
    garde ses trois motifs et ses trois distances. Écrire ces lignes telles quelles
    évite l'approximation « un motif par agent » que subit tout recalcul fait
    depuis les seules décisions stockées.
    """
    rows = []
    for rec in df.to_dict("records"):
        row = []
        for col in COLUMNS:
            value = rec.get(col)
            if value is not None and hasattr(value, "item"):
                value = value.item()
            row.append(value)
        rows.append(row)
    return rows


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", help="manifeste de sources (défaut : sources.yaml)")
    parser.add_argument("--run-config", default="run.yaml",
                        help="config du moteur de calibration (défaut : run.yaml)")
    parser.add_argument("--out", help="fichier de sortie (défaut : celui du manifeste)")
    parser.add_argument("--batch", type=int, default=DEFAULT_BATCH,
                        help=f"personas par requête (défaut : {DEFAULT_BATCH})")
    parser.add_argument("--workers", type=int, default=0,
                        help="requêtes en vol (défaut : eval_workers de la config)")
    parser.add_argument("--provider", default=None,
                        help="surcharge eval_provider (ex. google2 : seconde clé, "
                             "seau de quota distinct — clé de cache distincte, "
                             "réservé aux mesures)")
    parser.add_argument("--dry-run", action="store_true",
                        help="affiche l'échantillon et le coût, sans aucun appel LLM")
    args = parser.parse_args(argv)

    manifest = load_manifest(args.config)
    repo = manifest.get("arms.calibration.repo", "prompt_calibration")
    calibration, engine_error = import_calibration(repo)
    if calibration is None:
        print(f"[erreur] {engine_error}", file=sys.stderr)
        return 2

    out_path = Path(args.out or manifest.get("arms.calibration.common_set_eval"))
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path
    run_dir = manifest.path_of("common_set.run")
    if run_dir is None or not run_dir.exists():
        print(f"[erreur] Run introuvable : {manifest.get('common_set.run')}",
              file=sys.stderr)
        return 2
    pinned = manifest.get("arms.calibration.lineage") or {}
    leaf = pinned.get("leaf")
    if not leaf:
        print("[erreur] Aucune feuille de lignée épinglée "
              "(arms.calibration.lineage.leaf).", file=sys.stderr)
        return 2

    print(f"Run épinglé : {run_dir.relative_to(REPO_ROOT)}")
    records, info = build_sample(run_dir)
    print(f"Échantillon : {info['n_records']} décisions, {info['n_agents']} personnes "
          f"(sur {info['n_run_records']} / {info['n_run_agents']} dans le run)")
    print(f"Règle gelée : {info['rule']}")
    print(f"Splits gelés des personnes retenues : {info['splits']}")
    if info["coverage_warnings"]:
        print(f"⚠ {len(info['coverage_warnings'])} strate(s) sous le seuil de 5 :")
        for w in info["coverage_warnings"]:
            print(f"  - {w}")
    else:
        print("Couverture : complète (toutes les strates Cerema ≥ 5)")

    # ── Moteur de calibration ────────────────────────────────────────────────
    # RunConfig porte des chemins relatifs à la racine du dépôt de calibration
    # (jeux gelés, store, ressources du dépôt voisin) : on s'y place, une fois les
    # chemins de sortie déjà résolus en absolu.
    engine_root = REPO_ROOT / repo
    cwd = Path.cwd()
    results: list[dict] = []
    os.chdir(engine_root)
    try:
        from calibration.cli import (_fmt_local, _load_dotenv, _resume_after,
                                     build_engine)
        from calibration.evaluation import (EvaluationAborted, InsufficientCoverage,
                                            batches_from_records, normalize_decisions)
        from calibration.models import RunConfig
        from calibration.store import RunStore

        _load_dotenv()
        config = RunConfig.from_yaml(Path(args.run_config))
        if args.provider:
            print(f"  🔑 éval : provider {args.provider} (au lieu de "
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
            prompts = resolve_prompts(store, leaf)
            params_key = config.eval_params_key()
            # Nombre d'appels EXACT (et non estimé) : c'est la fonction de lotissement
            # du moteur qui le donne, la même qui sera utilisée pour l'éval.
            n_batches = len(batches_from_records(
                records, config.eval_batch_max,
                prod_option_handling=config.prod_option_handling))
            to_pay = [p for p in prompts
                      if store.cached_eval(p["node"], DATASET_NAME, params_key) is None]
            print()
            print(f"Clé d'éval : {params_key}")
            print(f"Prompts    : " + ", ".join(
                f'{p["short"]} ({p["label"]}, branche {p["branch"]})' for p in prompts))
            print(f"À payer    : {len(to_pay)}/{len(prompts)} éval(s) × {n_batches} lot(s) "
                  f"= {len(to_pay) * n_batches} appel(s) LLM avant re-tirs "
                  f"(+~16 % mesurés par A10 → ≈ {round(len(to_pay) * n_batches * 1.16)}), "
                  f"lots de {config.eval_batch_max} personas, {config.eval_rpm} req/min "
                  f"→ ≳ {len(to_pay) * n_batches / max(1, config.eval_rpm):.0f} min")

            if args.dry_run:
                print("\n--dry-run : aucun appel LLM émis.")
                return 0

            results = []
            for i, prompt in enumerate(prompts, 1):
                blocks = store.node_blocks(prompt["node"])
                if blocks is None:
                    print(f"  [{i}/{len(prompts)}] {prompt['short']} — blocs "
                          f"introuvables, ignoré")
                    continue
                try:
                    result, df = evaluator.evaluate(
                        prompt["node"], blocks, DATASET_NAME, records,
                        desc=f"{DATASET_NAME} {prompt['short']}")
                except EvaluationAborted as exc:
                    # Même conduite que `calibrate reeval` : on PERSISTE la date de
                    # reprise dans le store plutôt que de laisser la commande
                    # suivante marteler une API épuisée. Le quota journalier du free
                    # tier Google se réinitialise à minuit **Pacific**, pas à minuit
                    # UTC — et le `retryDelay` renvoyé dans le 429 (une trentaine de
                    # secondes) ne dit pas du tout quand le seau se remplit.
                    resume, reason = _resume_after(config, exc)
                    guard = RunStore(config.store_path)
                    guard.set_cooldown(resume, reason)
                    guard.close()
                    print(f"\n⏸️  {exc}\n   Reprise autorisée {_fmt_local(resume)} "
                          f"({reason}).\n   Relancer la même commande après le reset : "
                          f"les évals déjà payées sont servies par le cache.")
                    break
                except InsufficientCoverage as exc:
                    # Refus AVANT écriture : mieux vaut un prompt manquant qu'un
                    # composite calculé sur une sous-population.
                    print(f"  🚨 [ALARME] [{i}/{len(prompts)}] {prompt['short']} — {exc}")
                    continue
                if df.empty:
                    print(f"  ⚠ [{i}/{len(prompts)}] {prompt['short']} — aucune décision")
                    continue
                covered = len({aid for aid, _m, _w
                               in normalize_decisions(result.decisions)})
                results.append({
                    "schema": SCHEMA,
                    "role": prompt["role"], "label": prompt["label"],
                    "node": prompt["node"], "short": prompt["short"],
                    "branch": prompt["branch"],
                    "regime": {
                        "model": config.eval_model,
                        "policy": "masse de probabilité",
                        "label": f"{config.eval_model} · masse de probabilité",
                        "params_key": params_key,
                        "provider": config.eval_provider,
                        "temperature": config.eval_temp,
                    },
                    "sample": info,
                    "n_decisions": len(result.decisions),
                    "n_agents_covered": covered,
                    "coverage": covered / max(1, info["n_agents"]),
                    "stored_composite": result.scores.composite,
                    "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "columns": COLUMNS,
                    "decisions": _rows_from_frame(df),
                })
                print(f"  [{i}/{len(prompts)}] {prompt['short']} — composite moteur "
                      f"{result.scores.composite:.2f} sur {covered}/{info['n_agents']} "
                      f"personnes")
        finally:
            store.close()
    finally:
        os.chdir(cwd)

    if not results:
        print("\nAucun résultat exploitable — fichier de sortie inchangé.")
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for entry in results:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    rel = out_path.relative_to(REPO_ROOT) if out_path.is_relative_to(REPO_ROOT) else out_path
    print(f"\nÉcrit : {rel} ({len(results)} prompt(s))")
    print("Régénérer la page : make synthesis")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
