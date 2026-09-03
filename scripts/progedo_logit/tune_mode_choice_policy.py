"""tune_mode_choice_policy.py — Réglage des hyperparamètres du booster de choix modal.

`fit_mode_choice_policy.py` entraîne avec des réglages posés à la main et assumés
« volontairement sobres » : ils n'ont jamais été cherchés. Ce script les cherche, avec
une contrainte qui structure tout le reste — **la décision E7 tient**. On n'utilise ni
`is_unbalance` ni `class_weight` : repondérer les classes remonte le rappel vélo et
détruit la calibration, or ce sont les probabilités, pas les étiquettes dures, qui
produisent des parts modales.

**Ce qu'on peut faire à la place pour les modes sous-représentés.** Le vélo pèse
1 581 lignes d'entraînement sur 39 203 (4,3 % en masse pondérée). Sa masse de
probabilité est déjà juste ; ce qui lui manque, c'est du **pouvoir discriminant** —
séparer les 4 % de déplacements à vélo du reste. Cela se gagne sur la capacité du
modèle (`num_leaves`, `min_data_in_leaf`, nombre de tours) et sur le traitement des
catégorielles rares (`cat_smooth`, `min_data_per_group`), pas sur la repondération.
La différence est vérifiable : un gain de discrimination fait monter la PR-AUC vélo
**sans** dégrader la L1 des parts modales ; une repondération fait l'inverse.

**Trois garde-fous méthodologiques.**

1. **Le split test n'est jamais lu.** Toute la sélection se fait en validation croisée
   *à l'intérieur* du train. Un hyperparamètre choisi sur le test transforme le chiffre
   de généralisation en chiffre d'entraînement, silencieusement.
2. **Les plis sont par ménage** (`hh_id`), comme le split principal : les déplacements
   d'un même foyer partagent son équipement automobile. Des plis par déplacement
   donneraient une CV optimiste.
3. **L'arrêt anticipé est interne au pli.** Dans chaque pli, une part de validation est
   redécoupée par ménage dans les 4/5 d'entraînement. Arrêter sur le pli tenu à l'écart
   reviendrait à le choisir, et les prédictions hors-échantillon ne seraient plus
   hors-échantillon.

**Critères de sélection** (tous pondérés par le redressement `COEP`) :

- `logloss` — critère primaire, celui que E7 désigne ;
- `nll_bike` — log-vraisemblance négative *sur les seules lignes vélo*, c'est-à-dire
  « quelle probabilité le modèle accorde-t-il au vélo quand le vélo a été choisi ». Le
  critère minoritaire honnête : il ne récompense pas le fait de crier vélo partout,
  puisque `logloss` global le pénaliserait ;
- `ap_bike` / `ap_transit` — PR-AUC un-contre-tous, mesure de discrimination
  indépendante de tout seuil (le rappel argmax, lui, s'effondre mécaniquement sur une
  classe à 4 %) ;
- `l1_mass` — écart absolu total entre parts modales prédites (en masse) et observées.
  **Garde-fou de calibration** : une configuration qui dégrade la L1 au-delà de la
  tolérance est écartée quel que soit son gain sur le vélo.

Usage :
    python -m scripts.progedo_logit.tune_mode_choice_policy [--trials N] [--folds K]

Écrit `mode_choice_tuning.json` : toutes les configurations essayées avec leurs
métriques, triées. Ce fichier est la trace de l'expérience — il ne modifie aucun
modèle. Reporter le gagnant dans `PARAMS` de `fit_mode_choice_policy.py` reste un geste
humain, suivi d'un `make policy`.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, log_loss, roc_auc_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit

from scripts.progedo_logit.fit_mode_choice_policy import (
    EARLY_STOPPING_ROUNDS,
    MAX_ROUNDS,
    PARAMS,
    SEED,
    VALID_FRACTION,
    categorical_indices,
    check_spec,
    encode_features,
    feature_names,
    find_project_root,
)

# Tolérance de calibration : une configuration qui dégrade la L1 des parts modales de
# plus de ce montant (en points de probabilité cumulés sur les 4 classes) est écartée,
# même si elle gagne sur le vélo. C'est le mur qui empêche la recherche de redécouvrir
# la repondération de classes par une porte dérobée.
L1_TOLERANCE = 0.005

# Espace de recherche. Chaque axe est là pour une raison liée aux classes rares :
#   num_leaves / min_data_in_leaf : la capacité à isoler une poche de 4 % ;
#   learning_rate + tours          : un pas plus court laisse le temps de la modéliser ;
#   cat_smooth / min_data_per_group: le lissage des modalités rares (`purpose`,
#                                    `socioprofessional_class`) vers la moyenne globale ;
#   path_smoothing                 : régularise les feuilles peu peuplées, exactement
#                                    celles où vivent les modes minoritaires ;
#   objective multiclassova        : un-contre-tous, chaque classe a son propre budget
#                                    d'arbres au lieu de partager un softmax.
SEARCH_SPACE = {
    "objective": ["multiclass", "multiclass", "multiclass", "multiclassova"],
    "learning_rate": [0.02, 0.03, 0.05, 0.08],
    "num_leaves": [15, 31, 63, 127],
    "min_data_in_leaf": [10, 20, 30, 50, 80],
    "feature_fraction": [0.6, 0.7, 0.8, 0.9, 1.0],
    "bagging_fraction": [0.7, 0.8, 0.9, 1.0],
    "lambda_l1": [0.0, 0.5, 2.0],
    "lambda_l2": [0.0, 1.0, 5.0, 20.0],
    "cat_smooth": [1.0, 10.0, 50.0],
    "min_data_per_group": [20, 50, 100],
    "max_cat_threshold": [16, 32],
    "path_smoothing": [0.0, 1.0, 10.0],
}

# Espace de raffinement (`--refine`). La première passe a fait ressortir un signal net :
# toutes les configurations des trois podiums se tiennent à `num_leaves = 15`, la borne
# **basse** de la grille. Un optimum sur un bord de grille n'est pas un optimum : il dit
# seulement que la recherche s'est arrêtée trop tôt. Cet espace descend plus bas en
# capacité et resserre le pas, parce que c'est exactement ce dont une classe à 4 % a
# besoin — moins de feuilles, donc des feuilles plus peuplées, donc des probabilités
# vélo estimées sur assez de monde pour valoir quelque chose.
REFINE_SPACE = {
    "objective": ["multiclass"],
    "learning_rate": [0.015, 0.02, 0.03, 0.05],
    "num_leaves": [7, 10, 12, 15, 20, 24],
    "min_data_in_leaf": [5, 10, 20, 30, 50],
    "feature_fraction": [0.5, 0.6, 0.7, 0.8],
    "bagging_fraction": [0.8, 0.9, 1.0],
    "lambda_l1": [0.0, 0.5, 2.0],
    "lambda_l2": [2.0, 5.0, 10.0, 20.0],
    "cat_smooth": [10.0, 25.0, 50.0, 100.0],
    "min_data_per_group": [30, 50, 100],
    "max_cat_threshold": [16, 32],
    "path_smoothing": [0.0, 1.0, 5.0, 10.0],
}

FIXED = {
    "metric": "multi_logloss",
    "verbosity": -1,
    "num_threads": 4,
    "deterministic": True,
    "force_row_wise": True,
    "seed": SEED,
    "data_random_seed": SEED,
    "feature_fraction_seed": SEED,
    "bagging_seed": SEED,
}


# ---------------------------------------------------------------------------
# Métriques
# ---------------------------------------------------------------------------

def per_class_metrics(y: np.ndarray, proba: np.ndarray, w: np.ndarray,
                      classes: list[str]) -> dict:
    """Discrimination et calibration classe par classe, toutes pondérées.

    `nll` est la log-vraisemblance négative restreinte aux lignes de la classe : elle
    répond à « quand ce mode a été choisi, quelle masse le modèle lui accordait-il ».
    `ap` (PR-AUC un-contre-tous) est la mesure de discrimination qui reste lisible sur
    une classe à 4 %, là où le rappel argmax ne mesure plus que la prévalence.
    """
    eps = 1e-15
    out = {}
    for k, name in enumerate(classes):
        mask = y == k
        target = mask.astype(int)
        out[name] = {
            "support_share": float(w[mask].sum() / w.sum()),
            "nll": float(-(w[mask] * np.log(np.clip(proba[mask, k], eps, 1))).sum()
                         / w[mask].sum()),
            "ap": float(average_precision_score(target, proba[:, k], sample_weight=w)),
            "auc": float(roc_auc_score(target, proba[:, k], sample_weight=w)),
            # Calibration de la classe : masse prédite / masse observée. 1.0 = juste.
            "mass_ratio": float((w * proba[:, k]).sum() / w[mask].sum()),
        }
    return out


def expected_calibration_error(y: np.ndarray, proba: np.ndarray, w: np.ndarray,
                               bins: int = 15) -> float:
    """ECE sur la confiance (probabilité max), pondérée COEP."""
    conf = proba.max(axis=1)
    correct = (proba.argmax(axis=1) == y).astype(float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    idx = np.clip(np.digitize(conf, edges[1:-1]), 0, bins - 1)
    total = w.sum()
    ece = 0.0
    for b in range(bins):
        m = idx == b
        if not m.any():
            continue
        wb = w[m].sum()
        ece += wb / total * abs(
            (w[m] * correct[m]).sum() / wb - (w[m] * conf[m]).sum() / wb)
    return float(ece)


def score_oof(y: np.ndarray, proba: np.ndarray, w: np.ndarray,
              classes: list[str]) -> dict:
    """Tableau de bord complet d'un jeu de prédictions hors-échantillon."""
    k = len(classes)
    observed = np.array([w[y == c].sum() / w.sum() for c in range(k)])
    mass = (proba * w[:, None]).sum(axis=0) / w.sum()
    hard = proba.argmax(axis=1)
    argmax_share = np.array([w[hard == c].sum() / w.sum() for c in range(k)])
    per_class = per_class_metrics(y, proba, w, classes)
    return {
        "logloss": float(log_loss(y, proba, labels=list(range(k)), sample_weight=w)),
        "accuracy": float((w * (hard == y)).sum() / w.sum()),
        "ece": expected_calibration_error(y, proba, w),
        "l1_mass": float(np.abs(mass - observed).sum()),
        "l1_argmax": float(np.abs(argmax_share - observed).sum()),
        "mode_shares": {"observed": observed.tolist(),
                        "predicted_mass": mass.tolist(),
                        "predicted_argmax": argmax_share.tolist()},
        "per_class": per_class,
        # Raccourcis pour le tri et l'affichage.
        "nll_bike": per_class["bike"]["nll"],
        "ap_bike": per_class["bike"]["ap"],
        "ap_transit": per_class["transit"]["ap"],
        # Moyenne non pondérée des NLL par classe : traite les 4 modes à égalité,
        # contrairement au log-loss global que la voiture domine à 57 %.
        "macro_nll": float(np.mean([per_class[c]["nll"] for c in classes])),
    }


# ---------------------------------------------------------------------------
# Validation croisée groupée
# ---------------------------------------------------------------------------

def cross_val_oof(params: dict, X: pd.DataFrame, y: np.ndarray, w: np.ndarray,
                  groups: np.ndarray, spec: dict, folds: int,
                  max_rounds: int = MAX_ROUNDS,
                  ) -> tuple[np.ndarray, list[int], float]:
    """Prédictions hors-échantillon sur tout le train, par plis de ménages.

    Chaque pli refait un arrêt anticipé *dans* ses 4/5, sur une part de validation
    elle-même détourée par ménage. Le pli tenu à l'écart n'intervient qu'à la
    prédiction : c'est ce qui rend les probabilités agrégées réellement
    hors-échantillon.
    """
    cat = categorical_indices(spec)
    n_classes = len(spec["target"]["classes"])
    oof = np.zeros((len(y), n_classes))
    iterations: list[int] = []
    started = time.perf_counter()

    full = dict(FIXED)
    full.update(params)
    full["num_class"] = n_classes

    for fit_idx, held_idx in GroupKFold(n_splits=folds).split(X, y, groups=groups):
        inner, valid = next(
            GroupShuffleSplit(n_splits=1, test_size=VALID_FRACTION,
                              random_state=SEED).split(fit_idx, groups=groups[fit_idx]))
        inner_idx, valid_idx = fit_idx[inner], fit_idx[valid]

        fit_set = lgb.Dataset(X.iloc[inner_idx], label=y[inner_idx],
                              weight=w[inner_idx], categorical_feature=cat,
                              free_raw_data=False)
        valid_set = lgb.Dataset(X.iloc[valid_idx], label=y[valid_idx],
                                weight=w[valid_idx], categorical_feature=cat,
                                reference=fit_set, free_raw_data=False)
        booster = lgb.train(
            full, fit_set, num_boost_round=max_rounds, valid_sets=[valid_set],
            callbacks=[lgb.early_stopping(EARLY_STOPPING_ROUNDS, verbose=False)])
        iterations.append(int(booster.best_iteration))
        oof[held_idx] = booster.predict(X.iloc[held_idx],
                                        num_iteration=booster.best_iteration)

    # `multiclassova` produit des sigmoïdes un-contre-tous dont la somme ne vaut pas 1.
    # On renormalise ici plutôt que de laisser chaque métrique le faire dans son coin :
    # les parts modales en masse de probabilité n'auraient aucun sens autrement.
    oof /= oof.sum(axis=1, keepdims=True)
    return oof, iterations, time.perf_counter() - started


# ---------------------------------------------------------------------------
# Recherche
# ---------------------------------------------------------------------------

def sample_config(rng: np.random.Generator, space: dict) -> dict:
    """Un tirage dans l'espace de recherche, normalisé pour LightGBM."""
    cfg = {k: v[int(rng.integers(len(v)))] for k, v in space.items()}
    # `bagging_fraction` sans `bagging_freq` est ignoré silencieusement — le piège
    # classique : on croit régulariser, il ne se passe rien.
    cfg["bagging_freq"] = 0 if cfg["bagging_fraction"] >= 1.0 else 1
    # Types natifs : `json.dumps` refuse les entiers numpy.
    return {k: (int(v) if isinstance(v, (int, np.integer)) and not isinstance(v, bool)
                else float(v) if isinstance(v, (float, np.floating)) else v)
            for k, v in cfg.items()}


def baseline_config() -> dict:
    """Les réglages actuellement en production, évalués sur le même banc."""
    return {k: v for k, v in PARAMS.items()
            if k not in FIXED and k not in ("num_class",)}


def describe(cfg: dict) -> str:
    keys = ["objective", "learning_rate", "num_leaves", "min_data_in_leaf",
            "feature_fraction", "bagging_fraction", "lambda_l1", "lambda_l2",
            "cat_smooth", "min_data_per_group", "path_smoothing"]
    return " ".join(f"{k.split('_')[0][:4]}{'_'.join(k.split('_')[1:])[:3]}={cfg[k]}"
                    for k in keys if k in cfg)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=48,
                        help="Configurations tirées au sort (hors référence)")
    parser.add_argument("--folds", type=int, default=5, help="Plis de la CV groupée")
    parser.add_argument("--max-rounds", type=int, default=MAX_ROUNDS,
                        help="Plafond de tours. À surveiller : une configuration qui "
                             "l'atteint n'a pas convergé, son chiffre est tronqué et "
                             "non comparable aux autres.")
    parser.add_argument("--refine", action="store_true",
                        help="Tirer dans REFINE_SPACE (voisinage du gagnant de la "
                             "première passe) plutôt que dans SEARCH_SPACE")
    parser.add_argument("--seed-configs", type=Path, default=None,
                        help="JSON {nom: params} évalués en plus du tirage — sert à "
                             "rejouer les gagnants d'une passe précédente sur le "
                             "même banc")
    parser.add_argument("--dataset", type=Path, default=None)
    parser.add_argument("--spec", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    root = find_project_root()
    here = root / "scripts" / "progedo_logit"
    dataset_path = args.dataset or (here / "progedo_mode_choice_v2.parquet")
    spec_path = args.spec or (here / "feature_spec.json")
    out_path = args.out or (here / "mode_choice_tuning.json")

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    df = pd.read_parquet(dataset_path)
    check_spec(spec, df)

    classes = spec["target"]["classes"]
    is_train = (df["split"] == "train").to_numpy()
    train = df[is_train].reset_index(drop=True)

    X = encode_features(train, spec)
    y = train[spec["target"]["name"]].map({c: i for i, c in enumerate(classes)}).to_numpy()
    w = train[spec["sample_weight"]].to_numpy(dtype=float)
    groups = train["hh_id"].to_numpy()

    print(f"Banc de réglage — {len(train)} lignes de train, {len(np.unique(groups))} "
          f"ménages, {args.folds} plis groupés. Le split test n'est pas lu.")
    print(f"Support pondéré : " + "  ".join(
        f"{c}={w[y == i].sum() / w.sum():.1%}" for i, c in enumerate(classes)))

    space = REFINE_SPACE if args.refine else SEARCH_SPACE
    print(f"Espace : {'REFINE_SPACE' if args.refine else 'SEARCH_SPACE'}")
    rng = np.random.default_rng(SEED + (1 if args.refine else 0))
    configs = [("référence", baseline_config())]
    seen = {json.dumps(configs[0][1], sort_keys=True)}
    if args.seed_configs:
        for name, cfg in json.loads(args.seed_configs.read_text()).items():
            cfg.setdefault("bagging_freq", 0 if cfg.get("bagging_fraction", 1.0) >= 1.0 else 1)
            configs.append((name, cfg))
            seen.add(json.dumps(cfg, sort_keys=True))
    n_target = args.trials + len(configs)
    while len(configs) < n_target:
        cfg = sample_config(rng, space)
        key = json.dumps(cfg, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        configs.append((f"t{len(configs):03d}", cfg))

    results = []
    for name, cfg in configs:
        oof, iterations, elapsed = cross_val_oof(
            cfg, X, y, w, groups, spec, args.folds, args.max_rounds)
        metrics = score_oof(y, oof, w, classes)
        capped = max(iterations) >= args.max_rounds
        results.append({"name": name, "params": cfg, "metrics": metrics,
                        "best_iterations": iterations, "hit_round_cap": capped,
                        "seconds": round(elapsed, 1)})
        print(f"  {name:10s}{' [PLAFOND]' if capped else ''} "
              f"logloss={metrics['logloss']:.4f} "
              f"nll_bike={metrics['nll_bike']:.4f} ap_bike={metrics['ap_bike']:.4f} "
              f"l1={metrics['l1_mass']:.4f} ece={metrics['ece']:.4f} "
              f"iters~{int(np.median(iterations))} ({elapsed:.0f}s)")

    baseline = results[0]
    l1_ceiling = baseline["metrics"]["l1_mass"] + L1_TOLERANCE
    eligible = [r for r in results if r["metrics"]["l1_mass"] <= l1_ceiling]
    rejected = [r["name"] for r in results if r not in eligible]

    by_logloss = sorted(eligible, key=lambda r: r["metrics"]["logloss"])
    by_bike = sorted(eligible, key=lambda r: r["metrics"]["nll_bike"])
    by_macro = sorted(eligible, key=lambda r: r["metrics"]["macro_nll"])

    print(f"\n{len(eligible)}/{len(results)} configurations passent le garde-fou de "
          f"calibration (L1 ≤ {l1_ceiling:.4f}).")
    if rejected:
        print(f"Écartées pour dérive des parts modales : {', '.join(rejected)}")

    def podium(title: str, ranked: list[dict], key: str) -> None:
        print(f"\n{title}")
        for r in ranked[:5]:
            m = r["metrics"]
            print(f"  {r['name']:10s} {key}={m[key]:.4f}  logloss={m['logloss']:.4f}  "
                  f"nll_bike={m['nll_bike']:.4f}  ap_bike={m['ap_bike']:.4f}  "
                  f"l1={m['l1_mass']:.4f}\n             {describe(r['params'])}")

    podium("Meilleures sur le log-loss global (critère E7) :", by_logloss, "logloss")
    podium("Meilleures sur le vélo (NLL des lignes vélo) :", by_bike, "nll_bike")
    podium("Meilleures sur la moyenne macro des 4 classes :", by_macro, "macro_nll")

    b = baseline["metrics"]
    print("\nRéférence actuelle, par classe (CV hors-échantillon) :")
    for c in classes:
        p = b["per_class"][c]
        print(f"  {c:9s} support={p['support_share']:6.1%}  nll={p['nll']:.4f}  "
              f"ap={p['ap']:.4f}  auc={p['auc']:.4f}  masse/observé={p['mass_ratio']:.3f}")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "spec_version": spec["spec_version"],
        "dataset": dataset_path.name,
        "protocol": {
            "folds": args.folds,
            "grouped_by": "hh_id",
            "early_stopping": "interne au pli, part de validation par ménage",
            "test_split_used": False,
            "l1_tolerance": L1_TOLERANCE,
            "seed": SEED,
            "max_rounds": args.max_rounds,
        },
        "n_train_rows": int(len(train)),
        "baseline": baseline,
        "l1_ceiling": l1_ceiling,
        "rejected_for_calibration": rejected,
        "best_by_logloss": by_logloss[0]["name"] if by_logloss else None,
        "best_by_nll_bike": by_bike[0]["name"] if by_bike else None,
        "best_by_macro_nll": by_macro[0]["name"] if by_macro else None,
        "trials": sorted(results, key=lambda r: r["metrics"]["logloss"]),
    }
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
    print(f"\nÉcrit : {out_path}")


if __name__ == "__main__":
    main()
