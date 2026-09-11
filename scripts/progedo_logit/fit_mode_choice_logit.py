"""fit_mode_choice_logit.py — Estimation du second oracle : logit multinomial.

Estime le **logit multinomial** annoncé par l'article (contribution C1, niveau 3 de
l'ablation, `exp_03a_multinomial_logit`) sur les mêmes microdonnées d'enquête que le booster
LightGBM, et le sérialise en `mnl_model.json`.

**Pourquoi un second oracle, et pas seulement le booster.** La littérature comparative ne
donne pas le même vainqueur selon la famille d'indicateurs : les arbres à gradient boosté
devancent le logit sur l'exactitude *désagrégée* (2,2 à 5,6 points sur trois jeux réels), et
le logit reprend l'avantage sur les **parts modales agrégées** et les indicateurs
comportementaux (Martín-Baos et al. 2023 ; réserve « behaviorally unreasonable » de Zhao et
al. 2020 sur les élasticités des modèles à arbres). Notre hypothèse H0 se joue sur une L1 de
parts modales : le plafond de référence peut donc être le logit, et l'affirmer sans l'avoir
estimé n'était pas vérifiable.

**Parité stricte — voie 1, tranchée le 2026-09-10.** Les 21 variables du `feature_spec.json`,
ni une de plus. Il n'existe dans ce contrat **aucune variable de niveau de service par mode**
(temps ou coût de chaque alternative) : ce modèle est donc une régression logistique
multinomiale sur caractéristiques individuelles, de motif et de géographie — **pas** un
modèle d'utilité aléatoire au sens de McFadden. Conséquence à déclarer et non à contourner :
ni valeur du temps, ni disposition à payer ne sont calculables ici. La voie 2 (utilités par
alternative alimentées par `mode_skims.parquet`) romprait la parité d'information avec le
booster et avec l'agent, et fait l'objet d'un ticket distinct.

**Ce qui rend la parité vraie par construction**, plutôt que promise :

1. le **même jeu** (`progedo_mode_choice_v2.parquet`) et la **même colonne `split`**, étanche
   au ménage — jamais un redécoupage local, qui mélangerait les déplacements d'un foyer
   entre les deux côtés (piège d'échantillonnage documenté par Hillel 2021) ;
2. le **même `sample_weight`** (redressement d'enquête COEP) à l'estimation et dans toutes
   les métriques ;
3. le **même encodage** — `encode_features` du script du booster, importée telle quelle ;
4. les **mêmes métriques**, produites par `mode_choice_eval.evaluate_proba`, module partagé
   par les deux oracles.

**Le réglage ne lit jamais le test.** La force de régularisation est choisie en validation
croisée **groupée par ménage à l'intérieur du train**, comme les hyperparamètres du booster
(`make policy-tune`). Choisir sur le test reviendrait à le sélectionner, et le chiffre publié
ne serait plus un chiffre de généralisation.

Usage :
    python -m scripts.progedo_logit.fit_mode_choice_logit [--out-dir DIR] [--C 1.0]

N'exige **pas** les données PROGEDO brutes (accès restreint lil-1750) : le parquet et le
spec sont versionnés dans le dépôt.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.model_selection import GroupKFold

from scripts.progedo_logit.fit_mode_choice_policy import (
    check_spec,
    encode_features,
    feature_names,
    find_project_root,
)
from scripts.progedo_logit.mode_choice_eval import (
    evaluate_proba,
    format_shares,
)
from scripts.progedo_logit.mode_choice_logit import (
    LOGIT_FORMAT,
    LOGIT_FORMAT_VERSION,
    MISSING_CATEGORY,
    LogitPredictor,
    design_columns,
    design_matrix,
)

# --- Réglages d'estimation --------------------------------------------------
# `lbfgs` sur la vraisemblance multinomiale : c'est l'estimateur du logit multinomial, pas
# une pile de logits binaires. Le plafond d'itérations est franchement au-dessus de la
# convergence observée (~150 tours) — une estimation qui l'atteint n'a pas convergé, et le
# script le dit au lieu de publier des coefficients tronqués.
SOLVER = "lbfgs"
MAX_ITER = 2000
TOLERANCE = 1e-6

# Grille de régularisation. Un logit de référence se veut au plus proche du non pénalisé,
# mais la matrice de dessin porte des modalités rares (`purpose = education`,
# `socioprofessional_class = Farmer`) dont les coefficients divergent sans un minimum de
# ridge. La validation croisée tranche, et la grille est publiée avec son score.
C_GRID = (0.01, 0.1, 1.0, 10.0, 100.0)
CV_FOLDS = 5


# ---------------------------------------------------------------------------
# Matrice de dessin
# ---------------------------------------------------------------------------

def missing_columns(encoded: pd.DataFrame, spec: dict) -> list[str]:
    """Variables portant au moins un manquant sur les lignes fournies.

    Calculé sur le **train seul** : une indicatrice de manquant créée d'après le test
    ferait entrer une information du test dans la structure du modèle. Une variable pleine
    dans le train et trouée dans le test verra donc ses manquants imputés sans indicatrice
    — le fait est compté à la prédiction (`feature_missing` du parquet) plutôt que corrigé
    en douce.
    """
    return [name for name in feature_names(spec) if bool(encoded[name].isna().any())]


def standardization(encoded: pd.DataFrame, spec: dict, weights: np.ndarray) -> dict:
    """Moyenne et écart-type **pondérés** des numériques, sur les non-manquants du train.

    Pondérés parce que tout le reste l'est : centrer sur la moyenne non redressée
    reviendrait à définir le point de référence des coefficients sur une population qui
    n'est pas celle que le modèle doit reproduire.
    """
    stats: dict = {}
    for feature in spec["features"]:
        if feature["kind"] != "numeric":
            continue
        name = feature["name"]
        values = encoded[name].to_numpy(dtype="float64")
        present = ~np.isnan(values)
        w = weights[present]
        v = values[present]
        mean = float(np.average(v, weights=w))
        variance = float(np.average((v - mean) ** 2, weights=w))
        std = float(np.sqrt(variance)) or 1.0
        stats[name] = {"mean": mean, "std": std, "n_present": int(present.sum())}
    return stats


def missing_category_support(encoded_train: pd.DataFrame, spec: dict) -> dict:
    """Effectif d'entraînement de chaque modalité `__missing__`, par catégorielle.

    **Ce que ce compteur empêche de croire.** La matrice de dessin porte toujours une
    colonne `<var>=__missing__`, mais son coefficient n'est estimé que si le train contient
    de telles lignes. À zéro ligne, la colonne est constante et la régularisation laisse son
    coefficient à zéro : une valeur absente à la prédiction se comporte alors comme la
    **modalité de référence**, ce qui est une hypothèse et non une mesure. Mesuré sur le run
    épinglé, `socioprofessional_class` est absente de 498 décisions parce que la population
    synthétique porte des modalités que le spec d'enquête ne connaît pas — le fait doit être
    lisible dans l'artefact, pas déduit après coup.
    """
    out = {}
    for feature in spec["features"]:
        if feature["kind"] != "categorical":
            continue
        n = int(encoded_train[feature["name"]].isna().sum())
        out[feature["name"]] = {
            "n_train": n,
            "identifie": n > 0,
            "sinon": ("coefficient nul : une valeur absente se comporte comme la "
                      f"modalité de référence « {feature['categories'][0]} »"),
        }
    return out


def build_contract(spec: dict, encoded_train: pd.DataFrame,
                   weights_train: np.ndarray) -> dict:
    """Bloc `logit` de l'artefact, hors coefficients : tout ce qui construit `Z`."""
    indicators = missing_columns(encoded_train, spec)
    return {
        "missing_category_support": missing_category_support(encoded_train, spec),
        "design_columns": design_columns(spec, indicators),
        "missing_indicators": indicators,
        "standardization": standardization(encoded_train, spec, weights_train),
        "reference_category": {
            f["name"]: f["categories"][0]
            for f in spec["features"] if f["kind"] == "categorical"
        },
        "missing_rule": {
            "categorical": f"modalité {MISSING_CATEGORY} (jamais la modalité modale)",
            "bool": "0, plus l'indicatrice <nom>__missing à 1",
            "numeric": ("moyenne pondérée du train, soit 0 après centrage, plus "
                        "l'indicatrice <nom>__missing à 1"),
            "note": ("les indicatrices distinguent « absent » de « moyen » ; sans elles "
                     "l'imputation affirmerait une valeur que la donnée ne porte pas"),
        },
        "link": "softmax(Z·coef^T + intercept), classes dans l'ordre du spec",
    }


# ---------------------------------------------------------------------------
# Estimation
# ---------------------------------------------------------------------------

def normalized_weights(w: np.ndarray) -> np.ndarray:
    """Poids d'enquête ramenés à une moyenne de 1, **pour l'estimation seulement**.

    Le redressement COEP vaut 85,5 en moyenne sur ce jeu (min 9,4, max 503,6). Passé tel
    quel à un estimateur pénalisé, il multiplie la vraisemblance par ~85 sans toucher à la
    pénalité : `C` ne veut alors plus rien dire, et l'optimiseur n'atteint pas sa tolérance
    dans le plafond d'itérations — mesuré, l'estimation butait sur les 2 000 tours. La
    normalisation ne change **ni** les poids relatifs entre observations **ni** les
    métriques, qui restent calculées avec le COEP brut ; elle rend seulement l'échelle de
    la régularisation lisible.
    """
    return w * (len(w) / w.sum())


def fit_logit(Z: np.ndarray, y: np.ndarray, w: np.ndarray, C: float) -> LogisticRegression:
    """Ajuste le logit multinomial pondéré. `Z` est déjà centrée-réduite et dilatée."""
    model = LogisticRegression(
        C=C, solver=SOLVER, max_iter=MAX_ITER, tol=TOLERANCE, fit_intercept=True)
    model.fit(Z, y, sample_weight=normalized_weights(w))
    return model


def select_C(Z: np.ndarray, y: np.ndarray, w: np.ndarray, groups: np.ndarray,
             classes: list[str], grid=C_GRID, folds: int = CV_FOLDS) -> dict:
    """Choisit `C` par validation croisée groupée par ménage, **dans le train**.

    Le critère est la log-vraisemblance négative pondérée : c'est la grandeur dont dépendent
    les probabilités, donc les parts modales. L'exactitude n'y sert pas d'arbitre — un
    modèle qui gagne un point d'exactitude en écrasant le vélo dégrade les parts.
    """
    splitter = GroupKFold(n_splits=folds)
    labels = list(range(len(classes)))
    scores: list[dict] = []
    for C in grid:
        losses, sizes = [], []
        for fit_idx, valid_idx in splitter.split(Z, y, groups=groups):
            model = fit_logit(Z[fit_idx], y[fit_idx], w[fit_idx], C)
            proba = model.predict_proba(Z[valid_idx])
            losses.append(float(log_loss(y[valid_idx], proba, labels=labels,
                                         sample_weight=w[valid_idx])))
            sizes.append(int(len(valid_idx)))
        scores.append({
            "C": C,
            "cv_log_loss_weighted": float(np.mean(losses)),
            "per_fold": losses,
            "fold_sizes": sizes,
        })
        print(f"  C = {C:<8g} log-loss CV = {scores[-1]['cv_log_loss_weighted']:.5f}")
    best = min(scores, key=lambda s: s["cv_log_loss_weighted"])
    return {
        "grid": [s["C"] for s in scores],
        "folds": folds,
        "grouped_by": "hh_id",
        "scored_on": "train uniquement — le split test n'est jamais lu pour régler",
        "criterion": "log_loss_weighted",
        "results": scores,
        "C": best["C"],
        "cv_log_loss_weighted": best["cv_log_loss_weighted"],
    }


# ---------------------------------------------------------------------------
# Sérialisation
# ---------------------------------------------------------------------------

def build_artefact(model: LogisticRegression, spec: dict, spec_path: Path,
                   dataset_path: Path, contract: dict, training: dict,
                   metrics: dict) -> dict:
    """Artefact autoportant : de quoi prédire sans scikit-learn ni parquet."""
    return {
        "format": LOGIT_FORMAT,
        "format_version": LOGIT_FORMAT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": spec.get("source"),
        # Le consommateur compare cette version à celle du spec qu'il lit : un modèle
        # estimé sous un autre contrat de variables doit être refusé, pas réinterprété.
        "spec_version": spec["spec_version"],
        "spec_file": spec_path.name,
        "dataset_file": dataset_path.name,
        "target": {"name": spec["target"]["name"], "classes": spec["target"]["classes"]},
        "features": [
            {"name": f["name"], "kind": f["kind"], "source": f["source"],
             **({"categories": f["categories"]} if f["kind"] == "categorical" else {})}
            for f in spec["features"]
        ],
        # Encodage d'entrée : celui du booster, à l'identique. La dilatation en
        # indicatrices propre au logit est décrite dans le bloc `logit`.
        "encoding": {
            "shared_with": "fit_mode_choice_policy.encode_features",
            "missing": "NaN en entrée, traité par logit.missing_rule",
            "unknown_category": f"NaN à l'encodage, puis modalité {MISSING_CATEGORY}",
        },
        "geo_reference": spec.get("geo_reference"),
        "domain": spec.get("domain"),
        "notes": spec.get("notes"),
        "training": training,
        "metrics": metrics,
        "logit": {
            **contract,
            "estimator": {
                "library": "scikit-learn",
                "class": "LogisticRegression",
                "solver": SOLVER,
                "multinomial": True,
                "max_iter": MAX_ITER,
                "tol": TOLERANCE,
            },
            "coef": [[float(v) for v in row] for row in model.coef_],
            "intercept": [float(v) for v in model.intercept_],
        },
    }


def top_coefficients(artefact: dict, k: int = 8) -> list[dict]:
    """Coefficients de plus grande amplitude, par classe — lecture de premier niveau.

    Un coefficient de logit se lit sur l'échelle des log-odds, et les numériques sont
    centrées-réduites : « +0,8 » se lit « un écart-type de plus multiplie la cote de e^0,8 ».
    Publié en diagnostic, comme les importances par gain du booster.
    """
    logit = artefact["logit"]
    columns = logit["design_columns"]
    rows: list[dict] = []
    for class_index, name in enumerate(artefact["target"]["classes"]):
        coefficients = logit["coef"][class_index]
        ranked = sorted(zip(columns, coefficients), key=lambda p: -abs(p[1]))[:k]
        rows.append({"class": name,
                     "top": [{"column": c, "coef": float(v)} for c, v in ranked]})
    return rows


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", type=Path, default=None,
                        help="Parquet d'entraînement (défaut : progedo_mode_choice_v2.parquet)")
    parser.add_argument("--spec", type=Path, default=None,
                        help="Contrat de variables (défaut : feature_spec.json)")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="Répertoire de sortie (défaut : scripts/progedo_logit/)")
    parser.add_argument("--C", type=float, default=None,
                        help="Force de régularisation imposée (défaut : validation croisée)")
    args = parser.parse_args(argv)

    root = find_project_root()
    here = root / "scripts" / "progedo_logit"
    dataset_path = args.dataset or (here / "progedo_mode_choice_v2.parquet")
    spec_path = args.spec or (here / "feature_spec.json")
    out_dir = args.out_dir or here
    out_dir.mkdir(parents=True, exist_ok=True)

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    df = pd.read_parquet(dataset_path)
    check_spec(spec, df)          # même garde-fou de fuite que le booster

    names = feature_names(spec)
    classes = spec["target"]["classes"]
    print(f"Jeu : {len(df)} lignes | spec v{spec['spec_version']} | "
          f"{len(names)} variables | {len(classes)} classes")
    print(f"Exclues du modèle (diagnostic) : {spec.get('diagnostic_only')}")

    encoded = encode_features(df, spec)
    y = df[spec["target"]["name"]].map({c: i for i, c in enumerate(classes)}).to_numpy()
    w = df[spec["sample_weight"]].to_numpy(dtype=float)
    groups = df["hh_id"].to_numpy()

    is_train = (df["split"] == "train").to_numpy()
    is_test = (df["split"] == "test").to_numpy()
    print(f"Split lu dans le parquet : train={is_train.sum()} test={is_test.sum()} "
          f"| ménages={df['hh_id'].nunique()}")

    contract = build_contract(spec, encoded[is_train], w[is_train])
    print(f"Matrice de dessin : {len(contract['design_columns'])} colonnes "
          f"({len(contract['missing_indicators'])} indicatrices de manquant : "
          f"{contract['missing_indicators']})")

    # L'artefact partiel sert de contrat à `design_matrix` : la matrice d'estimation est
    # construite par le **même** code que celle de prédiction, jamais par un chemin parallèle.
    partial = {"features": spec["features"], "logit": contract}
    Z = design_matrix(encoded, partial)

    if args.C is not None:
        tuning = {"C": args.C, "imposed": True,
                  "scored_on": "aucun réglage — valeur imposée en ligne de commande"}
        print(f"\nRégularisation imposée : C = {args.C}")
    else:
        print(f"\nValidation croisée {CV_FOLDS} plis, groupée par ménage, dans le train :")
        tuning = select_C(Z[is_train], y[is_train], w[is_train], groups[is_train], classes)
        print(f"  retenu : C = {tuning['C']}")

    model = fit_logit(Z[is_train], y[is_train], w[is_train], tuning["C"])
    iterations = int(np.max(np.atleast_1d(model.n_iter_)))
    if iterations >= MAX_ITER:
        raise SystemExit(
            f"[ALARME] L'estimation a atteint le plafond de {MAX_ITER} itérations : les "
            "coefficients ne sont pas convergés et ne doivent pas être publiés.")

    training = {
        "estimator": "multinomial logistic regression (lbfgs, pondérée COEP)",
        "C": tuning["C"],
        "tuning": tuning,
        "n_iter": iterations,
        "n_fit": int(is_train.sum()),
        "n_test": int(is_test.sum()),
        "n_design_columns": int(Z.shape[1]),
        "sample_weight": spec["sample_weight"],
        "weight_normalization": ("poids ramenés à une moyenne de 1 pour l'estimation ; "
                                 "métriques calculées avec le COEP brut"),
        "split": spec.get("split"),
    }
    print(f"Convergence en {iterations} itérations (plafond {MAX_ITER})")

    proba_test = model.predict_proba(Z[is_test])
    metrics = evaluate_proba(proba_test, y[is_test], w[is_test], classes)

    print(f"\nTest ({metrics['n_rows']} lignes, pondéré COEP) :"
          f"\n  CEL (log-loss) = {metrics['cel_weighted']:.4f}"
          f"\n  GMPCA          = {metrics['gmpca_weighted']:.4f}"
          f"\n  accuracy       = {metrics['accuracy_weighted']:.4f}")
    shares = metrics["mode_shares"]
    print("\nParts modales (test, pondérées) :")
    print(format_shares(classes, shares["observed"],
                        shares["predicted_probability_mass"], shares["predicted_argmax"]))
    print(f"  L1 masse de probabilité = {shares['l1_probability_mass']:.4f}"
          f" | L1 mode élu = {shares['l1_argmax']:.4f}")

    artefact = build_artefact(model, spec, spec_path, dataset_path, contract,
                              training, metrics)
    artefact["metrics"]["top_coefficients"] = top_coefficients(artefact)

    # Vérification de l'autoportance, **avant** d'écrire : l'évaluateur pur numpy doit
    # reproduire les probabilités de scikit-learn. Un artefact qui ne se relit pas comme il
    # a été estimé est un artefact faux, et rien ne le dirait à la lecture.
    replayed = LogitPredictor(artefact).predict(encoded[is_test])
    gap = float(np.abs(replayed - proba_test).max())
    if gap > 1e-9:
        raise SystemExit(
            f"[ALARME] L'artefact ne reproduit pas l'estimation : écart max {gap:.2e} "
            "sur les probabilités du test. Artefact non écrit.")
    print(f"Autoportance vérifiée : écart max artefact / estimateur = {gap:.1e}")

    artefact_path = out_dir / "mnl_model.json"
    artefact_path.write_text(json.dumps(artefact, ensure_ascii=False, indent=1) + "\n",
                             encoding="utf-8")

    report = {
        "generated_at": artefact["generated_at"],
        "spec_version": spec["spec_version"],
        "dataset": dataset_path.name,
        "split": spec.get("split"),
        "training": training,
        "test": metrics,
    }
    metrics_path = out_dir / "mnl_model_metrics.json"
    metrics_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")

    size_kb = artefact_path.stat().st_size / 1e3
    print(f"\nÉcrits :\n - {artefact_path} ({size_kb:.0f} ko, format "
          f"{LOGIT_FORMAT} v{LOGIT_FORMAT_VERSION})\n - {metrics_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
