"""fit_mode_choice_policy.py — Entraînement de la politique de choix modal.

Entraîne le booster LightGBM multiclasse annoncé par le ticket 005 (phase 2) sur le
jeu préparé par `build_mode_choice_dataset.py`, et le sérialise en un artefact
autoportant : `mode_choice_policy.json`.

**Ce que « autoportant » veut dire ici.** Le consommateur du modèle (action A8, puis
l'évaluateur d'exécution de la phase 3b) ne doit rien avoir à deviner ni à relire :
l'artefact embarque l'ordre exact des variables, la table d'encodage de chaque
modalité catégorielle, l'ordre des classes de sortie, la version du contrat de
features, et le booster lui-même sous deux formes — le `dump_model()` JSON que
l'évaluateur pur Python traversera (décision E9 : le conteneur `controller` n'a pas
`libgomp1`, `import lightgbm` y échouerait) et le format texte natif de LightGBM,
qui permet de recharger le booster à l'identique là où la bibliothèque est présente.
Le parquet n'est nécessaire qu'ici.

**Trois garde-fous, avant toute chose.** Ils tiennent le modèle sur ses rails :

1. `distance_km`, `crow_km` et `duration_min` sont contaminées (ticket 005 §1 : pour
   la marche, la distance est une fonction affine de la durée déclarée) et le spec les
   liste en `diagnostic_only`. Le script vérifie explicitement qu'aucune n'entre dans
   la matrice d'entraînement. Une PR-AUC marche à 0.985 est le symptôme de la fuite,
   pas d'un bon modèle.
2. Le découpage train/test est **lu** dans la colonne `split` du parquet, jamais
   refait : il est étanche au ménage (`hh_id`), et un découpage local ré-tiré
   mélangerait les déplacements d'un même foyer entre les deux côtés.
3. `sample_weight` (le coefficient de redressement `COEP` de l'enquête) pondère
   l'entraînement **et** toutes les métriques. L'objectif est de reproduire des parts
   modales : non pondérées, elles ne sont pas représentatives.

L'arrêt anticipé se fait sur une part de validation redécoupée **dans le train** et
par ménage : utiliser le test pour arrêter reviendrait à le choisir, et le chiffre
rapporté ne serait plus un chiffre de généralisation.

Usage :
    python -m scripts.progedo_logit.fit_mode_choice_policy [--out-dir DIR]

N'exige **pas** les données PROGEDO brutes (accès restreint lil-1750) : le parquet et
le spec sont versionnés dans le dépôt.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, log_loss
from sklearn.model_selection import GroupShuffleSplit

# --- Version du format de l'artefact ----------------------------------------
# Décrit la *structure* de mode_choice_policy.json, indépendamment de
# `spec_version` qui décrit le contrat de features. Un consommateur doit refuser un
# format qu'il ne connaît pas plutôt que d'en interpréter les clés au hasard.
POLICY_FORMAT = "lightgbm_mode_choice_policy"
POLICY_FORMAT_VERSION = 1

# --- Réglages d'entraînement ------------------------------------------------
# Volontairement sobres : 21 features, ~21 k lignes d'entraînement, et un artefact
# qui doit rester diffable en git. `deterministic` + `force_row_wise` fixent l'ordre
# des réductions flottantes, sans quoi le multithread rend le résultat non
# reproductible d'une exécution à l'autre.
SEED = 0
VALID_FRACTION = 0.2          # part du train réservée à l'arrêt anticipé
# Le plafond doit rester franchement au-dessus de l'arrêt anticipé réel (~1 500 tours
# depuis le réglage du 2026-08-30). Une configuration qui *atteint* le plafond n'a pas
# convergé : son chiffre est tronqué, et rien dans le journal ne le dit si on ne le
# vérifie pas. `best_iteration` est reporté à la fin de l'entraînement, comparez-le.
MAX_ROUNDS = 4000
EARLY_STOPPING_ROUNDS = 50

PARAMS = {
    "objective": "multiclass",
    "metric": "multi_logloss",
    # Réglages issus du banc `tune_mode_choice_policy.py` (2026-08-30) : recherche
    # aléatoire puis raffinement, 96 configurations distinctes, validation croisée à 5 plis par
    # ménage **à l'intérieur du train**, le split test n'ayant jamais été lu.
    #
    # Le résultat tient en une phrase : le modèle précédent était en sur-capacité, et
    # c'est le vélo qui le payait. Passer de 31 à 5 feuilles, avec un pas trois fois
    # plus court et trois fois plus de tours, améliore *simultanément* le log-loss
    # global, la vraisemblance du vélo, sa PR-AUC, la calibration (ECE) et la L1 des
    # parts modales. Beaucoup d'arbres peu profonds valent mieux ici que peu d'arbres
    # profonds : une classe à 4,3 % ne peuple pas assez les feuilles d'un arbre à 31
    # feuilles pour que sa probabilité y soit estimée sur autre chose que du bruit.
    "learning_rate": 0.015,
    "num_leaves": 5,
    "min_data_in_leaf": 10,
    "feature_fraction": 0.5,
    "bagging_fraction": 0.9,
    "bagging_freq": 1,            # sans `freq`, `bagging_fraction` est ignoré en silence
    "lambda_l1": 0.5,
    "lambda_l2": 10.0,
    # Lissage des modalités rares vers la moyenne globale : `purpose = education` et
    # `socioprofessional_class = Farmer` n'ont pas assez d'observations vélo pour
    # mériter une branche à elles.
    "cat_smooth": 50.0,
    "min_data_per_group": 50,
    "max_cat_threshold": 16,
    "path_smoothing": 5.0,        # régularise les feuilles peu peuplées — les minoritaires
    # E7 : ni `is_unbalance` ni `class_weight`. Rééquilibrer les classes détruit la
    # calibration (précision vélo 0.14 dans le notebook d'origine), or ce sont les
    # probabilités, pas l'accuracy, qui servent à produire des parts modales. Le gain
    # sur les modes sous-représentés est allé chercher de la *capacité mieux placée*,
    # pas de la repondération — et le banc le vérifie : chaque configuration qui
    # dégradait la L1 des parts modales de plus de 0,005 y était écartée d'office.
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
# Chemins
# ---------------------------------------------------------------------------

def find_project_root() -> Path:
    """Racine du dépôt, repérée au spec plutôt qu'aux données brutes.

    `build_mode_choice_dataset.find_project_root` cherche `data/PROGEDO 2023/`, d'accès
    restreint. L'entraînement, lui, ne lit que des fichiers versionnés : il doit
    tourner sur un clone nu.
    """
    root = Path(__file__).resolve()
    marker = Path("scripts") / "progedo_logit" / "feature_spec.json"
    while not (root / marker).exists() and root != root.parent:
        root = root.parent
    if not (root / marker).exists():
        raise SystemExit(f"Racine du projet introuvable (repère : {marker}).")
    return root


# ---------------------------------------------------------------------------
# Contrat de features
# ---------------------------------------------------------------------------

def check_spec(spec: dict, df: pd.DataFrame) -> None:
    """Refuse d'entraîner sur un jeu qui ne correspond pas au contrat.

    Chaque contrôle correspond à une façon connue de produire un modèle faux sans
    qu'aucune exception ne soit levée.
    """
    names = feature_names(spec)
    diagnostic = set(spec.get("diagnostic_only") or [])

    leaked = sorted(diagnostic & set(names))
    if leaked:
        raise SystemExit(
            f"Variables `diagnostic_only` présentes dans les features : {leaked}. "
            "Elles sont contaminées (ticket 005 §1) et ne doivent jamais entrer dans "
            "le modèle."
        )

    missing = [n for n in names if n not in df.columns]
    if missing:
        raise SystemExit(f"Colonnes absentes du jeu de données : {missing}")

    for col in (spec["target"]["name"], spec["sample_weight"], "split", "hh_id"):
        if col not in df.columns:
            raise SystemExit(f"Colonne obligatoire absente du jeu de données : {col}")

    observed = set(df[spec["target"]["name"]].dropna().unique())
    declared = set(spec["target"]["classes"])
    if observed - declared:
        raise SystemExit(
            f"Modalités de la cible hors du spec : {sorted(observed - declared)}"
        )

    for feature in spec["features"]:
        if feature["kind"] != "categorical":
            continue
        seen = set(df[feature["name"]].dropna().astype(str).unique())
        unknown = sorted(seen - set(feature["categories"]))
        if unknown:
            raise SystemExit(
                f"Modalités hors spec pour {feature['name']} : {unknown}. "
                "Le spec fige la liste fermée : régénérez-le avec "
                "build_mode_choice_dataset.py."
            )


def feature_names(spec: dict) -> list[str]:
    """Ordre des colonnes de la matrice — c'est le spec qui l'impose, pas le parquet."""
    return [f["name"] for f in spec["features"]]


def categorical_encoding(spec: dict) -> dict[str, dict[str, int]]:
    """Modalité → code entier, dans l'ordre du spec.

    Figer les codes ici, et les republier dans l'artefact, est ce qui garantit qu'une
    catégorie sera encodée identiquement à l'entraînement et au runtime. Les déduire
    des valeurs présentes dans un lot de prédiction donnerait un encodage flottant
    d'un appel à l'autre.
    """
    return {
        f["name"]: {cat: i for i, cat in enumerate(f["categories"])}
        for f in spec["features"] if f["kind"] == "categorical"
    }


def encode_features(df: pd.DataFrame, spec: dict) -> pd.DataFrame:
    """Matrice numérique prête pour LightGBM, dans l'ordre du spec.

    - catégorielle → code entier du spec, `NaN` pour l'inconnu (jamais un code de
      repli : « modalité inattendue » n'est pas « modalité la plus fréquente ») ;
    - booléenne    → 0/1, `NaN` conservé quand la valeur manque ;
    - numérique    → flottant, `NaN` conservé.

    Les valeurs manquantes ne sont **pas** imputées : LightGBM les route nativement,
    et la densité est légitimement absente pour les 81 zones sans ménage enquêté (un
    0 y affirmerait « zone déserte », ce qui est faux).
    """
    encoding = categorical_encoding(spec)
    out = pd.DataFrame(index=df.index)
    for feature in spec["features"]:
        name, kind = feature["name"], feature["kind"]
        col = df[name]
        if kind == "categorical":
            out[name] = col.astype("object").map(encoding[name]).astype("float64")
        elif kind == "bool":
            # `astype(float)` direct échoue sur une colonne objet contenant des NaN.
            out[name] = pd.to_numeric(col.astype("object").map(
                {True: 1.0, False: 0.0, 1: 1.0, 0: 0.0}), errors="coerce")
        else:
            out[name] = pd.to_numeric(col, errors="coerce").astype("float64")
    return out[feature_names(spec)]


def categorical_indices(spec: dict) -> list[int]:
    """Positions des catégorielles — LightGBM les veut par index, pas par nom."""
    return [i for i, f in enumerate(spec["features"]) if f["kind"] == "categorical"]


# ---------------------------------------------------------------------------
# Entraînement
# ---------------------------------------------------------------------------

def split_valid(train: pd.DataFrame, fraction: float, seed: int) -> pd.Series:
    """Part de validation détourée **dans le train**, par ménage.

    Par ménage pour la même raison que le split principal : les déplacements d'un
    foyer partagent son équipement automobile. Dans le train, parce qu'arrêter sur le
    test revient à le sélectionner.
    """
    fit_idx, valid_idx = next(
        GroupShuffleSplit(n_splits=1, test_size=fraction, random_state=seed)
        .split(train, groups=train["hh_id"])
    )
    is_valid = pd.Series(False, index=train.index)
    is_valid.iloc[valid_idx] = True
    return is_valid


def train_booster(X: pd.DataFrame, y: np.ndarray, w: np.ndarray,
                  is_valid: np.ndarray, spec: dict,
                  params: Optional[dict] = None) -> tuple[lgb.Booster, dict]:
    """Ajuste le booster, arrêt anticipé sur la part de validation."""
    params = dict(params or PARAMS)
    params["num_class"] = len(spec["target"]["classes"])

    cat = categorical_indices(spec)
    fit_set = lgb.Dataset(X[~is_valid], label=y[~is_valid], weight=w[~is_valid],
                          categorical_feature=cat, free_raw_data=False)
    valid_set = lgb.Dataset(X[is_valid], label=y[is_valid], weight=w[is_valid],
                            categorical_feature=cat, reference=fit_set,
                            free_raw_data=False)

    history: dict = {}
    booster = lgb.train(
        params, fit_set, num_boost_round=MAX_ROUNDS, valid_sets=[valid_set],
        valid_names=["valid"],
        callbacks=[
            lgb.early_stopping(EARLY_STOPPING_ROUNDS, verbose=False),
            lgb.record_evaluation(history),
            lgb.log_evaluation(period=100),
        ],
    )
    training = {
        "params": {k: v for k, v in params.items() if k != "verbosity"},
        "max_rounds": MAX_ROUNDS,
        "early_stopping_rounds": EARLY_STOPPING_ROUNDS,
        "best_iteration": int(booster.best_iteration),
        "valid_multi_logloss": float(history["valid"]["multi_logloss"][booster.best_iteration - 1]),
        "n_fit": int((~is_valid).sum()),
        "n_valid": int(is_valid.sum()),
    }
    return booster, training


# ---------------------------------------------------------------------------
# Évaluation
# ---------------------------------------------------------------------------

def mode_shares(labels: np.ndarray, weights: np.ndarray, n_classes: int) -> list[float]:
    """Parts modales pondérées, depuis des étiquettes dures."""
    total = weights.sum()
    return [float(weights[labels == k].sum() / total) for k in range(n_classes)]


def evaluate(booster: lgb.Booster, X: pd.DataFrame, y: np.ndarray, w: np.ndarray,
             classes: list[str]) -> dict:
    """Métriques du split test — toutes pondérées par le redressement d'enquête.

    Les parts modales sont rapportées de **deux** façons, parce que les deux ont un
    usage : en masse de probabilité (ce que le pipeline consomme réellement, cf.
    ticket 005 §4) et en mode élu (ce que produirait un argmax). La seconde est
    systématiquement plus contrastée — un classifieur bien calibré exagère les parts
    quand on le durcit.
    """
    proba = booster.predict(X, num_iteration=booster.best_iteration)
    hard = proba.argmax(axis=1)
    k = len(classes)

    observed = mode_shares(y, w, k)
    predicted_hard = mode_shares(hard, w, k)
    predicted_mass = list((proba * w[:, None]).sum(axis=0) / w.sum())

    cm = confusion_matrix(y, hard, labels=list(range(k)), sample_weight=w)
    cm_counts = confusion_matrix(y, hard, labels=list(range(k)))

    # Rappel/précision par classe, pondérés. Le vélo (4 % des déplacements) est la
    # classe où la calibration se joue : c'est elle que toute repondération casse.
    per_class = {}
    for i, name in enumerate(classes):
        tp = cm[i, i]
        support = cm[i, :].sum()
        predicted = cm[:, i].sum()
        per_class[name] = {
            "support_share": float(support / cm.sum()),
            "recall": float(tp / support) if support else None,
            "precision": float(tp / predicted) if predicted else None,
        }

    return {
        "n_rows": int(len(y)),
        "log_loss_weighted": float(log_loss(y, proba, labels=list(range(k)), sample_weight=w)),
        "log_loss_unweighted": float(log_loss(y, proba, labels=list(range(k)))),
        "accuracy_weighted": float(accuracy_score(y, hard, sample_weight=w)),
        "accuracy_unweighted": float(accuracy_score(y, hard)),
        "classes": classes,
        "mode_shares": {
            "observed": observed,
            "predicted_probability_mass": predicted_mass,
            "predicted_argmax": predicted_hard,
            "l1_probability_mass": float(np.abs(np.array(predicted_mass) - np.array(observed)).sum()),
            "l1_argmax": float(np.abs(np.array(predicted_hard) - np.array(observed)).sum()),
        },
        "per_class": per_class,
        # Lignes = vrai, colonnes = prédit, dans l'ordre de `classes`.
        "confusion_matrix_weighted": [[float(v) for v in row] for row in cm],
        "confusion_matrix_counts": [[int(v) for v in row] for row in cm_counts],
    }


def importances(booster: lgb.Booster, names: list[str]) -> list[dict]:
    """Importances par gain, décroissantes — utilisées en diagnostic de fuite."""
    gains = booster.feature_importance(importance_type="gain")
    splits = booster.feature_importance(importance_type="split")
    total = float(gains.sum()) or 1.0
    rows = [{"name": n, "gain_share": float(g / total), "splits": int(s)}
            for n, g, s in zip(names, gains, splits)]
    return sorted(rows, key=lambda r: -r["gain_share"])


# ---------------------------------------------------------------------------
# Sérialisation
# ---------------------------------------------------------------------------

def build_policy(booster: lgb.Booster, spec: dict, spec_path: Path,
                 dataset_path: Path, training: dict, metrics: dict) -> dict:
    """Artefact autoportant : tout ce qu'il faut pour prédire, et rien du parquet."""
    return {
        "format": POLICY_FORMAT,
        "format_version": POLICY_FORMAT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": spec.get("source"),
        # Le runtime compare cette version à celle du spec qu'il lit : un modèle
        # entraîné sous un autre contrat de features doit être refusé, pas réinterprété.
        "spec_version": spec["spec_version"],
        "spec_file": spec_path.name,
        "dataset_file": dataset_path.name,
        "target": {"name": spec["target"]["name"], "classes": spec["target"]["classes"]},
        # Ordre exact des colonnes attendu par le booster.
        "features": [
            {"name": f["name"], "kind": f["kind"], "source": f["source"],
             **({"categories": f["categories"]} if f["kind"] == "categorical" else {})}
            for f in spec["features"]
        ],
        "encoding": {
            "categorical": categorical_encoding(spec),
            "bool": {"false": 0, "true": 1},
            "missing": "null / NaN, routé nativement par le booster — jamais imputé",
            "unknown_category": "null / NaN (aucun code de repli)",
        },
        # Recopiée pour que le consommateur puisse vérifier qu'il calcule od_km et
        # dist_center_* depuis la même référence (garde-fou de ZoneResolver.load).
        "geo_reference": spec.get("geo_reference"),
        "domain": spec.get("domain"),
        "notes": spec.get("notes"),
        "training": training,
        "metrics": metrics,
        "booster": {
            "library": "lightgbm",
            "version": lgb.__version__,
            "best_iteration": int(booster.best_iteration),
            # Deux formes, deux consommateurs (cf. docstring du module).
            "dump_model": booster.dump_model(num_iteration=booster.best_iteration),
            "model_text": booster.model_to_string(num_iteration=booster.best_iteration),
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def format_shares(classes: list[str], observed: list[float],
                  mass: list[float], hard: list[float]) -> str:
    lines = [f"  {'mode':10s} {'observé':>9s} {'masse p.':>9s} {'mode élu':>9s}"]
    for i, name in enumerate(classes):
        lines.append(f"  {name:10s} {observed[i]:8.1%} {mass[i]:8.1%} {hard[i]:8.1%}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=None,
                        help="Parquet d'entraînement (défaut : progedo_mode_choice_v2.parquet)")
    parser.add_argument("--spec", type=Path, default=None,
                        help="Contrat de features (défaut : feature_spec.json)")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="Répertoire de sortie (défaut : scripts/progedo_logit/)")
    args = parser.parse_args()

    root = find_project_root()
    here = root / "scripts" / "progedo_logit"
    dataset_path = args.dataset or (here / "progedo_mode_choice_v2.parquet")
    spec_path = args.spec or (here / "feature_spec.json")
    out_dir = args.out_dir or here
    out_dir.mkdir(parents=True, exist_ok=True)

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    df = pd.read_parquet(dataset_path)
    check_spec(spec, df)

    names = feature_names(spec)
    classes = spec["target"]["classes"]
    print(f"Jeu : {len(df)} lignes | spec v{spec['spec_version']} | "
          f"{len(names)} features | {len(classes)} classes")
    print(f"Exclues du modèle (diagnostic) : {spec.get('diagnostic_only')}")

    X = encode_features(df, spec)
    y = df[spec["target"]["name"]].map({c: i for i, c in enumerate(classes)}).to_numpy()
    w = df[spec["sample_weight"]].to_numpy(dtype=float)

    is_train = (df["split"] == "train").to_numpy()
    is_test = (df["split"] == "test").to_numpy()
    print(f"Split lu dans le parquet : train={is_train.sum()} test={is_test.sum()} "
          f"| ménages={df['hh_id'].nunique()}")

    train = df[is_train]
    is_valid_train = split_valid(train, VALID_FRACTION, SEED).to_numpy()

    booster, training = train_booster(
        X[is_train].reset_index(drop=True), y[is_train], w[is_train],
        is_valid_train, spec)
    print(f"\nArrêt anticipé à l'itération {training['best_iteration']} "
          f"(valid multi_logloss = {training['valid_multi_logloss']:.4f})")

    metrics = evaluate(booster, X[is_test].reset_index(drop=True),
                       y[is_test], w[is_test], classes)
    metrics["feature_importances"] = importances(booster, names)

    print(f"\nTest ({metrics['n_rows']} lignes, pondéré COEP) :"
          f"\n  log-loss  = {metrics['log_loss_weighted']:.4f}"
          f"\n  accuracy  = {metrics['accuracy_weighted']:.4f}")
    shares = metrics["mode_shares"]
    print("\nParts modales (test, pondérées) :")
    print(format_shares(classes, shares["observed"],
                        shares["predicted_probability_mass"], shares["predicted_argmax"]))
    print(f"  L1 masse de probabilité = {shares['l1_probability_mass']:.4f}"
          f" | L1 mode élu = {shares['l1_argmax']:.4f}")

    print("\nImportances (gain, top 8) :")
    for row in metrics["feature_importances"][:8]:
        print(f"  {row['name']:22s} {row['gain_share']:6.1%}")

    policy = build_policy(booster, spec, spec_path, dataset_path, training, metrics)
    policy_path = out_dir / "mode_choice_policy.json"
    policy_path.write_text(json.dumps(policy, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")

    # Métriques à part : l'artefact du modèle les embarque aussi, mais un fichier
    # dédié se lit et se diffe sans traverser plusieurs Mo de booster.
    report = {
        "generated_at": policy["generated_at"],
        "spec_version": spec["spec_version"],
        "dataset": dataset_path.name,
        "split": spec.get("split"),
        "training": training,
        "test": metrics,
    }
    metrics_path = out_dir / "mode_choice_policy_metrics.json"
    metrics_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")

    size_mb = policy_path.stat().st_size / 1e6
    print(f"\nÉcrits :\n - {policy_path} ({size_mb:.1f} Mo, format "
          f"{POLICY_FORMAT} v{POLICY_FORMAT_VERSION})\n - {metrics_path}")


if __name__ == "__main__":
    main()
