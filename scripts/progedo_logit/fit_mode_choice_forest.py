"""fit_mode_choice_forest.py — Le témoin random forest : d'où vient l'avantage du booster ?

Le booster LightGBM devance le logit multinomial de 1,9 point d'exactitude et de 0,0017 de L1
sur les parts modales. **Cet avantage vient-il des arbres, ou du boosting ?** La phrase que
l'article s'apprête à écrire n'est pas réfutable tant que les deux causes la produisent
également :

- les **arbres** — non-linéarités et interactions qu'une forme linéaire en log-odds ne peut
  pas représenter ; le levier serait alors le contrat de variables ;
- le **boosting** — l'agrégation par descente de gradient, qui replace la capacité là où la
  vraisemblance manque ; une troisième famille d'arbres n'apporterait alors rien.

Un random forest sépare les deux : il est fait d'arbres comme le booster, mais agrégés par
**bagging**. Ce script l'ajuste à parité stricte et publie **où il se place entre les deux**.

**C'est un témoin, pas un candidat.** Personne ne propose de remplacer l'oracle par un RF.
Conséquence tranchée à l'ouverture (ticket 044) : *aucun modèle n'est sérialisé*, seulement
un fichier de mesures. Un RF autoportant, ce serait 400 à 1 200 arbres de plusieurs milliers
de nœuds — de l'ordre de 80 à 800 Mo de JSON illisible — là où le booster pèse déjà 18,9 Mo,
et sans un seul consommateur pour le relire. Rejouer le témoin demande de relancer
`make forest` : c'est déterministe (`random_state` fixé), hors ligne, et ça coûte des minutes.

**Les quatre conditions de la comparabilité**, vraies par construction et non promises :

1. le **même jeu** (`progedo_mode_choice_v2.parquet`) et la **même colonne `split`**, étanche
   au ménage, lue et jamais redécoupée ;
2. le **même `sample_weight`** (redressement COEP) à l'ajustement et dans toutes les
   métriques ;
3. le **même `encode_features`**, importé du script du booster ;
4. les **mêmes métriques**, produites par `mode_choice_eval.evaluate_proba`, module partagé
   par les trois modèles.

**Le piège de l'encodage, et pourquoi la voie principale n'est pas la voie littérale.** Les
arbres de scikit-learn n'ont **aucun support des catégorielles** : nourris des codes entiers
du spec, ils liraient `purpose`, `socioprofessional_class` et `main_occupation` comme des
**ordinales** sur un ordre arbitraire, là où LightGBM partitionne des ensembles de modalités.
Un RF en retrait ne dirait alors plus « c'est le boosting » — il dirait peut-être « c'est
l'encodage », et le témoin perdrait la seule propriété qui le rend utile. La voie principale
réutilise donc la **matrice de dessin déclarée du logit** (`mode_choice_logit.design_matrix` :
indicatrices par modalité, modalité `__missing__`, moyenne pondérée du train plus indicatrice
de manquant). Le centrage-réduction qu'elle applique est neutre pour un arbre — une
transformation monotone ne change aucune coupure.

La voie littérale n'est pas abandonnée pour autant : `--encodage natif` ajuste le **même** RF
sur les 21 colonnes brutes, `NaN` routés nativement par scikit-learn, et l'écart entre les
deux **chiffre le coût de l'encodage**. C'est ce qui rend le choix ci-dessus réfutable au lieu
d'être affirmé.

**Le réglage ne lit jamais le test**, et le verdict a son **seuil déclaré d'avance** : la part
de l'écart booster–logit comblée par le RF, `≥ 0,70` → les arbres, `≤ 0,30` → le boosting,
entre les deux → indécis et la phrase reste à écrire. Choisir le seuil après avoir vu le
chiffre reviendrait à choisir la conclusion.

Usage :
    python -m scripts.progedo_logit.fit_mode_choice_forest [--encodage les-deux] [--rapide]

N'exige **pas** les données PROGEDO brutes (accès restreint lil-1750) : le parquet et le spec
sont versionnés dans le dépôt.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import log_loss
from sklearn.model_selection import GroupKFold

from scripts.progedo_logit.fit_mode_choice_logit import build_contract
from scripts.progedo_logit.fit_mode_choice_policy import (
    check_spec,
    encode_features,
    feature_names,
    find_project_root,
)
from scripts.progedo_logit.mode_choice_eval import evaluate_proba, format_shares
from scripts.progedo_logit.mode_choice_logit import design_matrix

# --- Réglages ---------------------------------------------------------------
SEED = 0
CV_FOLDS = 5

#: Grille de réglage. Explicite plutôt qu'aléatoire : un témoin d'une heure n'a pas besoin du
#: banc à 96 configurations du booster, et une grille publiée se relit.
DEPTH_GRID = (None, 8, 14, 20)
LEAF_GRID = (1, 5, 20, 50)
FEATURES_GRID = ("sqrt", 0.3, 0.6)

#: Nombre d'arbres pendant la validation croisée, puis pour le contrôle de plateau. La
#: log-loss de validation d'un RF décroît de façon **monotone** en nombre d'arbres — le
#: bagging réduit la variance, il ne sur-ajuste pas en `n_estimators`. Régler la profondeur à
#: 200 arbres puis vérifier à 400 et 1 200 coûte six fois moins qu'une grille complète, et le
#: plateau se **montre** (les trois chiffres sont publiés) au lieu de s'affirmer.
N_ESTIMATORS_CV = 200
N_ESTIMATORS_PLATEAU = (400, 1200)

#: Seuils du verdict, fixés **avant** de lancer (règle R8). Ils n'ont aucune justification
#: statistique : c'est une convention de lecture, et elle est publiée comme telle.
SEUIL_ARBRES = 0.70
SEUIL_BOOSTING = 0.30

#: En deçà, l'écart booster–logit est trop petit pour qu'une part en soit lisible : le rapport
#: divergerait au lieu de mesurer. La comparaison vaut alors « non mesuré », jamais un chiffre.
ECART_MINIMAL = 1e-6

ENCODAGES = ("dessin", "natif")


# ---------------------------------------------------------------------------
# Matrice d'entrée
# ---------------------------------------------------------------------------

def build_matrix(encoded: pd.DataFrame, spec: dict, weights: np.ndarray,
                 is_train: np.ndarray, encodage: str) -> tuple[np.ndarray, dict]:
    """Matrice d'entrée du RF, et la description de la règle appliquée (règle R6).

    ``dessin`` : la matrice de dessin déclarée du logit — indicatrices par modalité, modalité
    `__missing__`, moyenne pondérée du train plus indicatrice de manquant. Le contrat est
    construit **sur le train seul** : une indicatrice déduite du test y ferait entrer une
    information du test.

    ``natif`` : les 21 colonnes de `encode_features`, codes entiers pour les catégorielles,
    `NaN` routés par scikit-learn. Voie de sensibilité : elle mesure ce que coûte de lire une
    nominale comme une ordinale.
    """
    if encodage == "dessin":
        contract = build_contract(spec, encoded[is_train], weights[is_train])
        partial = {"features": spec["features"], "logit": contract}
        matrix = design_matrix(encoded, partial)
        description = {
            "voie": "dessin",
            "colonnes": len(contract["design_columns"]),
            "noms_colonnes": contract["design_columns"],
            # Republié intégralement : c'est ce que l'artefact du témoin embarque pour que
            # `RFPredictor` reconstruise la MÊME matrice, sans relire ce script.
            "contrat": contract,
            "indicatrices_de_manquant": contract["missing_indicators"],
            "regle_des_manquants": contract["missing_rule"],
            "partage_avec": "mode_choice_logit.design_matrix (second oracle)",
            "pourquoi": ("les arbres de scikit-learn n'ont aucun support des catégorielles ; "
                         "les codes entiers du spec y seraient lus comme des ordinales"),
        }
        return matrix, description

    if encodage == "natif":
        matrix = encoded.to_numpy(dtype="float64")
        n_nan = int(np.isnan(matrix).sum())
        description = {
            "voie": "natif",
            "colonnes": matrix.shape[1],
            "noms_colonnes": feature_names(spec),
            "indicatrices_de_manquant": [],
            "regle_des_manquants": {
                "toutes": ("NaN laissés tels quels, routés par les arbres de scikit-learn "
                           "(support ajouté en 1.4, splitter « best », matrice dense)"),
                "note": ("les catégorielles sont lues comme des ORDINALES sur l'ordre du "
                         "spec — c'est le biais que cette voie sert à mesurer"),
            },
            "n_valeurs_manquantes": n_nan,
            "partage_avec": "fit_mode_choice_policy.encode_features (booster), tel quel",
            "pourquoi": "voie de sensibilité — elle chiffre le coût de l'encodage",
        }
        return matrix, description

    raise SystemExit(f"Encodage inconnu : {encodage!r} (attendu : {ENCODAGES})")


# ---------------------------------------------------------------------------
# Ajustement
# ---------------------------------------------------------------------------

def forest(n_estimators: int, max_depth, min_samples_leaf: int,
           max_features) -> RandomForestClassifier:
    """Le RF du témoin. `class_weight=None` n'est pas un défaut : c'est la règle R4.

    Comme pour le booster (décision E7), aucune repondération de classe. Rééquilibrer gonfle
    le rappel des minoritaires en détruisant la calibration — or ce sont les probabilités, pas
    l'exactitude, qui produisent les parts modales.
    """
    return RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        max_features=max_features,
        class_weight=None,
        bootstrap=True,
        random_state=SEED,
        n_jobs=-1,
    )


def proba_complete(model: RandomForestClassifier, matrix: np.ndarray,
                   n_classes: int) -> np.ndarray:
    """Probabilités sur **les quatre** classes, même si un pli n'en a pas vu une.

    `predict_proba` ne rend que les colonnes des classes vues à l'ajustement. Sur un pli
    pauvre en vélo (4 % des déplacements), une matrice à trois colonnes se mélangerait
    silencieusement aux autres et décalerait tout l'ordre des classes.
    """
    partial = model.predict_proba(matrix)
    full = np.zeros((len(matrix), n_classes), dtype="float64")
    for position, label in enumerate(model.classes_):
        full[:, int(label)] = partial[:, position]
    return full


def cv_log_loss(matrix: np.ndarray, y: np.ndarray, w: np.ndarray, groups: np.ndarray,
                n_classes: int, n_estimators: int, max_depth, min_samples_leaf: int,
                max_features, folds: int = CV_FOLDS) -> tuple[float, list[float]]:
    """Log-vraisemblance négative pondérée en validation croisée groupée par ménage.

    Groupée parce que les déplacements d'un foyer partagent son équipement automobile : des
    plis tirés au hasard mettraient le même ménage des deux côtés et flatteraient toutes les
    configurations de la même façon fausse (piège d'échantillonnage, Hillel 2021).
    """
    splitter = GroupKFold(n_splits=folds)
    labels = list(range(n_classes))
    losses: list[float] = []
    for fit_idx, valid_idx in splitter.split(matrix, y, groups=groups):
        model = forest(n_estimators, max_depth, min_samples_leaf, max_features)
        model.fit(matrix[fit_idx], y[fit_idx], sample_weight=w[fit_idx])
        proba = proba_complete(model, matrix[valid_idx], n_classes)
        losses.append(float(log_loss(y[valid_idx], proba, labels=labels,
                                     sample_weight=w[valid_idx])))
    return float(np.mean(losses)), losses


def grids(rapide: bool) -> tuple[tuple, tuple, tuple]:
    """Grille de réglage. `--rapide` la réduit pour une passe de fumée, jamais pour publier."""
    if rapide:
        return (None, 14), (5, 50), ("sqrt",)
    return DEPTH_GRID, LEAF_GRID, FEATURES_GRID


def select_params(matrix: np.ndarray, y: np.ndarray, w: np.ndarray, groups: np.ndarray,
                  n_classes: int, rapide: bool = False) -> dict:
    """Choisit la configuration en validation croisée, **dans le train** (règle R3).

    Le critère est la log-vraisemblance négative pondérée, pas l'exactitude : un modèle qui
    gagne un point d'exactitude en écrasant le vélo dégrade les parts modales, et ce sont les
    parts que l'article compare.
    """
    depth_grid, leaf_grid, features_grid = grids(rapide)
    combinations = list(itertools.product(depth_grid, leaf_grid, features_grid))
    results: list[dict] = []
    started = time.monotonic()
    print(f"  {len(combinations)} configurations × {CV_FOLDS} plis, "
          f"{N_ESTIMATORS_CV} arbres :")
    for index, (max_depth, min_samples_leaf, max_features) in enumerate(combinations, 1):
        step = time.monotonic()
        mean, per_fold = cv_log_loss(matrix, y, w, groups, n_classes, N_ESTIMATORS_CV,
                                     max_depth, min_samples_leaf, max_features)
        results.append({
            "max_depth": max_depth,
            "min_samples_leaf": min_samples_leaf,
            "max_features": max_features,
            "n_estimators": N_ESTIMATORS_CV,
            "cv_log_loss_weighted": mean,
            "per_fold": per_fold,
            "seconds": round(time.monotonic() - step, 1),
        })
        print(f"   [{index:>2}/{len(combinations)}] depth={str(max_depth):<4} "
              f"leaf={min_samples_leaf:<3} feat={str(max_features):<5} "
              f"log-loss = {mean:.5f}  ({results[-1]['seconds']:.0f} s)")
    best = min(results, key=lambda r: r["cv_log_loss_weighted"])

    # Une configuration retenue sur un bord de grille signale que l'optimum est peut-être
    # au-delà : le chiffre publié serait alors le meilleur de ce qu'on a regardé, pas le
    # meilleur du modèle. On le dit à la lecture plutôt que de le laisser deviner.
    edges = []
    # `max_depth = None` est le bord de capacité maximale, mais il n'a rien « au-delà » :
    # une profondeur illimitée ne peut pas être sous-explorée. Seule la borne finie compte.
    if best["max_depth"] is not None and best["max_depth"] == max(
            d for d in depth_grid if d is not None):
        edges.append("max_depth")
    if best["min_samples_leaf"] in (leaf_grid[0], leaf_grid[-1]):
        edges.append("min_samples_leaf")
    if len(features_grid) > 1 and best["max_features"] in (features_grid[0],
                                                           features_grid[-1]):
        edges.append("max_features")
    if edges:
        print(f"  [ALARME] Configuration retenue sur un bord de grille : {edges}. "
              "L'optimum peut être au-delà de ce qui a été exploré.")

    duration = round(time.monotonic() - started, 1)
    print(f"  Réglage terminé en {duration:.0f} s — retenu : depth={best['max_depth']} "
          f"leaf={best['min_samples_leaf']} feat={best['max_features']} "
          f"(log-loss CV {best['cv_log_loss_weighted']:.5f})")
    return {
        "grille": {"max_depth": list(depth_grid), "min_samples_leaf": list(leaf_grid),
                   "max_features": list(features_grid)},
        "folds": CV_FOLDS,
        "grouped_by": "hh_id",
        "scored_on": "train uniquement — le split test n'est jamais lu pour régler",
        "criterion": "log_loss_weighted",
        "n_estimators_cv": N_ESTIMATORS_CV,
        "results": results,
        "retenu": {k: best[k] for k in
                   ("max_depth", "min_samples_leaf", "max_features", "cv_log_loss_weighted")},
        "bords_de_grille": edges,
        "seconds": duration,
    }


def plateau(matrix: np.ndarray, y: np.ndarray, w: np.ndarray, groups: np.ndarray,
            n_classes: int, retenu: dict) -> dict:
    """Contrôle de plateau : la même configuration, à 200, 400 et 1 200 arbres.

    Publié parce qu'un réglage fait à 200 arbres ne vaut pour 1 200 que si la log-loss s'est
    resserrée. Si elle continue de descendre franchement, le témoin est sous-dimensionné et le
    lecteur doit le savoir.
    """
    points = [{"n_estimators": N_ESTIMATORS_CV,
               "cv_log_loss_weighted": retenu["cv_log_loss_weighted"]}]
    for n_estimators in N_ESTIMATORS_PLATEAU:
        mean, _ = cv_log_loss(matrix, y, w, groups, n_classes, n_estimators,
                              retenu["max_depth"], retenu["min_samples_leaf"],
                              retenu["max_features"])
        points.append({"n_estimators": n_estimators, "cv_log_loss_weighted": mean})
        print(f"   {n_estimators:>5} arbres : log-loss CV = {mean:.5f}")
    gains = [points[i - 1]["cv_log_loss_weighted"] - points[i]["cv_log_loss_weighted"]
             for i in range(1, len(points))]
    return {
        "points": points,
        "gains_successifs": gains,
        "n_estimators_retenu": points[-1]["n_estimators"],
        "lecture": ("le gain du dernier palier mesure ce qu'il resterait à prendre en "
                    "ajoutant des arbres"),
    }


# ---------------------------------------------------------------------------
# Le verdict
# ---------------------------------------------------------------------------

def part_de_l_ecart(rf: float, booster: float, logit: float) -> Optional[float]:
    """Part de l'écart booster–logit comblée par le RF : 0 = le logit, 1 = le booster.

    Le rapport est **insensible au sens** de la métrique : que « mieux » soit plus haut
    (exactitude) ou plus bas (L1), `(rf − logit) / (booster − logit)` vaut 0 au niveau du
    logit et 1 à celui du booster. Il peut sortir de [0, 1] — un RF meilleur que le booster
    donne plus de 1, un RF pire que le logit donne moins de 0 — et c'est une information, pas
    une anomalie à borner.
    """
    ecart = booster - logit
    if abs(ecart) < ECART_MINIMAL:
        return None
    return float((rf - logit) / ecart)


def verdict(parts: list[Optional[float]]) -> dict:
    """Le verdict, depuis les parts mesurées et les seuils déclarés d'avance (règle R8)."""
    mesurees = [p for p in parts if p is not None]
    if not mesurees:
        return {"conclusion": "non mesuré",
                "pourquoi": "aucun écart booster–logit exploitable",
                "seuils": {"arbres": SEUIL_ARBRES, "boosting": SEUIL_BOOSTING}}
    if min(mesurees) >= SEUIL_ARBRES:
        conclusion = "les arbres"
        lecture = ("le RF rejoint le booster : l'avantage tient aux arbres — non-linéarités "
                   "et interactions — et le levier est le contrat de variables")
    elif max(mesurees) <= SEUIL_BOOSTING:
        conclusion = "le boosting"
        lecture = ("le RF reste près du logit : l'avantage tient à l'agrégation par descente "
                   "de gradient, et une troisième famille d'arbres n'apporterait rien")
    else:
        conclusion = "indécis"
        lecture = ("le RF se place entre les deux seuils : la phrase de l'article reste à "
                   "écrire, et aucune des deux causes ne peut être affirmée seule")
    return {
        "conclusion": conclusion,
        "lecture": lecture,
        "seuils": {"arbres": SEUIL_ARBRES, "boosting": SEUIL_BOOSTING,
                   "declares": "avant le lancement (règle R8) — jamais ajustés après coup"},
    }


def lire_metriques(path: Path) -> Optional[dict]:
    """Bloc `test` d'un fichier de métriques d'oracle, ou `None` s'il n'a pas été produit."""
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("test")


def cel(metrics: dict) -> float:
    """CEL pondérée, sous l'un ou l'autre de ses deux noms.

    `mode_choice_eval` publie la **même grandeur en nats** sous `log_loss_weighted` (le nom
    historique du dépôt) et `cel_weighted` (celui de la littérature comparative dont le GMPCA
    dérive). Le fichier du booster date du 2026-08-30, avant que le second nom n'existe :
    le lire sous son nom d'alors n'est pas un repli, c'est le même nombre. Ce qui serait un
    repli — recalculer une CEL par un autre chemin, ou publier un zéro — n'est pas fait.
    """
    if "cel_weighted" in metrics:
        return float(metrics["cel_weighted"])
    return float(metrics["log_loss_weighted"])


def alias_manquant(path: Path, metrics: dict) -> Optional[str]:
    """Signale un fichier de référence antérieur aux alias CEL/GMPCA — lisible, pas muet."""
    if "cel_weighted" in metrics:
        return None
    return (f"{path.name} : produit avant les alias CEL/GMPCA (ticket 042) ; "
            "`log_loss_weighted` lu à leur place — même grandeur, mêmes nats")


def comparer(rf_metrics: dict, booster_path: Path, logit_path: Path) -> dict:
    """Situe le RF entre les deux oracles, en **recalculant** depuis leurs fichiers.

    Rien n'est recopié d'un tableau : les trois chiffres viennent des trois fichiers produits
    par le **même** module d'évaluation. Si l'un des deux manque, la comparaison vaut « non
    mesuré » et pas `0.0` — une absence de mesure qui sortirait un zéro se lirait « aucun
    écart », soit exactement l'inverse de ce qu'elle dit (règle R9).
    """
    booster = lire_metriques(booster_path)
    logit = lire_metriques(logit_path)
    manquants = [p.name for p, m in ((booster_path, booster), (logit_path, logit)) if m is None]
    if manquants:
        return {
            "statut": "non mesuré",
            "references_manquantes": manquants,
            "comment_les_produire": "make policy (booster) et make logit (second oracle)",
            "verdict": verdict([]),
        }

    axes = [
        ("accuracy_weighted", "exactitude pondérée", lambda m: m["accuracy_weighted"]),
        ("l1_probability_mass", "L1 masse de probabilité",
         lambda m: m["mode_shares"]["l1_probability_mass"]),
        ("cel_weighted", "CEL", cel),
        ("l1_argmax", "L1 mode élu", lambda m: m["mode_shares"]["l1_argmax"]),
        ("recall_bike", "rappel vélo", lambda m: m["per_class"]["bike"]["recall"]),
    ]
    lignes = {}
    for key, label, read in axes:
        valeurs = {"random_forest": read(rf_metrics), "lightgbm": read(booster),
                   "logit": read(logit)}
        lignes[key] = {
            "libelle": label,
            **valeurs,
            "part_de_l_ecart_comblee": part_de_l_ecart(
                valeurs["random_forest"], valeurs["lightgbm"], valeurs["logit"]),
        }

    # Le verdict ne porte que sur les deux axes de la question posée : l'exactitude
    # désagrégée et la L1 des parts agrégées. Les trois autres sont publiés en lecture.
    parts = [lignes["accuracy_weighted"]["part_de_l_ecart_comblee"],
             lignes["l1_probability_mass"]["part_de_l_ecart_comblee"]]
    notes = [n for n in (alias_manquant(booster_path, booster),
                         alias_manquant(logit_path, logit)) if n]
    return {
        "statut": "mesuré",
        "sur": {"split": "test scellé", "n_rows": rf_metrics["n_rows"],
                "pondere_par": "COEP"},
        "references": {"lightgbm": booster_path.name, "logit": logit_path.name},
        "compatibilite": notes,
        "axes": lignes,
        "axes_du_verdict": ["accuracy_weighted", "l1_probability_mass"],
        "formule": "(RF − logit) / (booster − logit) : 0 = le logit, 1 = le booster",
        "verdict": verdict(parts),
    }


# ---------------------------------------------------------------------------
# Une passe complète, pour un encodage
# ---------------------------------------------------------------------------

def passe(encodage: str, encoded: pd.DataFrame, spec: dict, y: np.ndarray, w: np.ndarray,
          groups: np.ndarray, is_train: np.ndarray, is_test: np.ndarray,
          classes: list[str], rapide: bool) -> dict:
    """Règle, ajuste et évalue le RF pour un encodage donné."""
    print(f"\n=== Encodage « {encodage} » " + "=" * 46)
    matrix, description = build_matrix(encoded, spec, w, is_train, encodage)
    print(f"Matrice : {matrix.shape[0]} lignes × {matrix.shape[1]} colonnes "
          f"({len(description['indicatrices_de_manquant'])} indicatrices de manquant)")

    print(f"\nValidation croisée {CV_FOLDS} plis, groupée par ménage, dans le train :")
    tuning = select_params(matrix[is_train], y[is_train], w[is_train], groups[is_train],
                           len(classes), rapide)
    retenu = tuning["retenu"]

    print("\nContrôle de plateau (même configuration, plus d'arbres) :")
    courbe = plateau(matrix[is_train], y[is_train], w[is_train], groups[is_train],
                     len(classes), retenu)
    n_estimators = courbe["n_estimators_retenu"]

    print(f"\nAjustement final : {n_estimators} arbres sur {int(is_train.sum())} lignes…")
    started = time.monotonic()
    model = forest(n_estimators, retenu["max_depth"], retenu["min_samples_leaf"],
                   retenu["max_features"])
    model.fit(matrix[is_train], y[is_train], sample_weight=w[is_train])
    seconds = round(time.monotonic() - started, 1)

    # R4 vérifiée sur l'estimateur ajusté, pas sur l'intention : une repondération de classe
    # introduite par mégarde doit arrêter le script, pas sortir dans un chiffre publié.
    if model.class_weight is not None:
        raise SystemExit("[ALARME] `class_weight` non nul : le rééquilibrage détruit la "
                         "calibration des probabilités (règle R4). Rien n'est écrit.")
    print(f"Ajusté en {seconds:.0f} s — {model.n_estimators} arbres, "
          f"profondeur max observée {max(e.get_depth() for e in model.estimators_)}")

    proba_test = proba_complete(model, matrix[is_test], len(classes))
    metrics = evaluate_proba(proba_test, y[is_test], w[is_test], classes)

    print(f"\nTest ({metrics['n_rows']} lignes, pondéré COEP) :"
          f"\n  CEL (log-loss) = {metrics['cel_weighted']:.4f}"
          f"\n  GMPCA          = {metrics['gmpca_weighted']:.4f}"
          f"\n  exactitude     = {metrics['accuracy_weighted']:.4f}"
          f"\n  rappel vélo    = {metrics['per_class']['bike']['recall']:.3f}")
    shares = metrics["mode_shares"]
    print("\nParts modales (test, pondérées) :")
    print(format_shares(classes, shares["observed"],
                        shares["predicted_probability_mass"], shares["predicted_argmax"]))
    print(f"  L1 masse de probabilité = {shares['l1_probability_mass']:.4f}"
          f" | L1 mode élu = {shares['l1_argmax']:.4f}")

    importances = sorted(
        ({"colonne": nom, "importance": float(v)} for nom, v in zip(
            description["noms_colonnes"], model.feature_importances_)),
        key=lambda r: -r["importance"])
    return {
        "encodage": description,
        "training": {
            "estimator": "RandomForestClassifier (scikit-learn, pondéré COEP)",
            "n_estimators": int(model.n_estimators),
            "max_depth": retenu["max_depth"],
            "min_samples_leaf": retenu["min_samples_leaf"],
            "max_features": retenu["max_features"],
            "class_weight": None,
            "bootstrap": True,
            "random_state": SEED,
            "n_fit": int(is_train.sum()),
            "n_test": int(is_test.sum()),
            "n_colonnes": int(matrix.shape[1]),
            "sample_weight": spec["sample_weight"],
            "fit_seconds": seconds,
            "tuning": tuning,
            "plateau": courbe,
        },
        "test": metrics,
        "importances": importances[:15],
    }


# ---------------------------------------------------------------------------
# Artefact de rejeu — des chiffres et un contrat, jamais un arbre
# ---------------------------------------------------------------------------

def build_artefact(passe_principale: dict, spec: dict, spec_path: Path,
                   dataset_path: Path, trainset_path: Path, genere_le: str) -> dict:
    """Artefact du témoin : de quoi **refaire** la forêt, pas de quoi la transporter.

    Aucun arbre n'y figure. Les 3 740 500 nœuds de la forêt retenue pèseraient ~150 Mo en
    JSON ou 165 Mo en `joblib` compressé ; `RFPredictor` les reconstruit en une dizaine de
    secondes depuis le parquet, à graine fixée, donc à l'identique. L'artefact fige les deux
    conditions de cette identité — empreinte du parquet, version de scikit-learn — et le
    prédicteur refuse de tourner si l'une diverge.
    """
    from sklearn import __version__ as sklearn_version

    from scripts.progedo_logit.mode_choice_rf import RF_FORMAT, RF_FORMAT_VERSION, sha256_fichier

    training = passe_principale["training"]
    return {
        "format": RF_FORMAT,
        "format_version": RF_FORMAT_VERSION,
        "generated_at": genere_le,
        "source": spec.get("source"),
        "spec_version": spec["spec_version"],
        "spec_file": spec_path.name,
        "dataset_file": dataset_path.name,
        # Provenance seulement : le parquet n'est pas versionné et, surtout, le conteneur
        # `controller` où tournent les expériences ne sait pas le lire (ni pyarrow ni
        # fastparquet). Le rejeu passe donc par la matrice ci-dessous, que numpy suffit à
        # relire, et dont l'empreinte atteste que la forêt réajustée est bien celle publiée.
        "dataset_sha256": sha256_fichier(dataset_path),
        "trainset_file": trainset_path.name,
        "trainset_sha256": sha256_fichier(trainset_path),
        "target": {"name": spec["target"]["name"], "classes": spec["target"]["classes"]},
        "features": [
            {"name": f["name"], "kind": f["kind"], "source": f["source"],
             **({"categories": f["categories"]} if f["kind"] == "categorical" else {})}
            for f in spec["features"]
        ],
        "encoding": {
            "shared_with": "fit_mode_choice_policy.encode_features",
            "missing": "NaN en entrée, traité par rf.contrat.missing_rule",
            "design": "dilatée par mode_choice_logit.design_matrix, comme le second oracle",
        },
        "geo_reference": spec.get("geo_reference"),
        "domain": spec.get("domain"),
        "notes": spec.get("notes"),
        "training": {k: v for k, v in training.items() if k not in ("tuning", "plateau")},
        "metrics": passe_principale["test"],
        "rf": {
            "estimator": {
                "library": "scikit-learn",
                "class": "RandomForestClassifier",
                "version": sklearn_version,
            },
            "hyperparameters": {
                "n_estimators": training["n_estimators"],
                "max_depth": training["max_depth"],
                "min_samples_leaf": training["min_samples_leaf"],
                "max_features": training["max_features"],
                "class_weight": None,
                "bootstrap": True,
                "random_state": SEED,
            },
            "ajustement": ("réajusté au chargement depuis le parquet (~10 s) — aucun arbre "
                           "n'est sérialisé ; graine fixée, donc forêt identique"),
            "pourquoi": ("1 200 arbres et 3 740 500 nœuds pèsent ~150 Mo en JSON et 165 Mo "
                         "en joblib compressé ; un pickle scikit-learn se périme en outre à "
                         "la version suivante de la bibliothèque"),
            "contrat": passe_principale["encodage"]["contrat"],
        },
    }


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
    parser.add_argument("--encodage", choices=("dessin", "natif", "les-deux"),
                        default="les-deux",
                        help="Voie principale seule, voie native seule, ou les deux (défaut)")
    parser.add_argument("--rapide", action="store_true",
                        help="Grille réduite — passe de fumée, jamais pour publier")
    parser.add_argument("--artefact", action="store_true",
                        help="Écrit aussi rf_mode_choice_policy.json — contrat de rejeu "
                             "sans arbres, pour la plateforme d'expériences")
    parser.add_argument("--artefact-seul", action="store_true",
                        help="Régénère l'artefact depuis rf_mode_choice_metrics.json, sans "
                             "rejouer le réglage (les mesures publiées sont inchangées)")
    args = parser.parse_args(argv)

    # Le réglage dure une vingtaine de minutes. Sans cette ligne, `make forest > journal.log`
    # n'écrit rien jusqu'à la fin : impossible de distinguer « ça avance » de « ça ne tourne
    # plus », alors que la progression par configuration est déjà imprimée.
    sys.stdout.reconfigure(line_buffering=True)

    root = find_project_root()
    here = root / "scripts" / "progedo_logit"
    dataset_path = args.dataset or (here / "progedo_mode_choice_v2.parquet")
    spec_path = args.spec or (here / "feature_spec.json")
    out_dir = args.out_dir or here
    out_dir.mkdir(parents=True, exist_ok=True)

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    df = pd.read_parquet(dataset_path)
    check_spec(spec, df)          # même garde-fou de fuite que les deux oracles

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
    if args.rapide:
        print("[ALARME] Grille réduite (--rapide) : passe de fumée, chiffres non publiables.")

    if args.artefact_seul:
        # Régénérer l'artefact ne doit pas coûter la grille : les mesures publiées sont
        # déjà écrites, et l'artefact n'en est qu'une mise en forme. Ce chemin ne RE-MESURE
        # rien — il refuse d'ailleurs de tourner si le fichier de mesures n'existe pas,
        # plutôt que d'inventer une passe.
        mesures_path = out_dir / "rf_mode_choice_metrics.json"
        if not mesures_path.exists():
            raise SystemExit(
                f"Mesures absentes : {mesures_path}. `--artefact-seul` met en forme une "
                "mesure existante, il n'en produit pas. Lancez `make forest` d'abord.")
        mesures = json.loads(mesures_path.read_text(encoding="utf-8"))
        principal = mesures["principal"]
        if "contrat" not in principal["encodage"]:
            raise SystemExit(
                "Le fichier de mesures est antérieur au contrat de rejeu (clé "
                "`encodage.contrat` absente). Relancez `make forest FOREST_ARGS=--artefact`.")
        matrix, _ = build_matrix(encoded, spec, w, is_train, "dessin")
        trainset_path = out_dir / "rf_mode_choice_trainset.npz"
        np.savez_compressed(trainset_path, X=matrix, y=y.astype("int8"), w=w,
                            is_train=is_train, is_test=is_test)
        artefact = build_artefact(principal, spec, spec_path, dataset_path, trainset_path,
                                  mesures["generated_at"])
        artefact_path = out_dir / "rf_mode_choice_policy.json"
        artefact_path.write_text(json.dumps(artefact, ensure_ascii=False, indent=1) + "\n",
                                 encoding="utf-8")
        print(f"Artefact régénéré depuis {mesures_path.name} (aucune re-mesure) :"
              f"\n - {artefact_path} ({artefact_path.stat().st_size / 1e3:.0f} ko)"
              f"\n - {trainset_path} ({trainset_path.stat().st_size / 1e6:.1f} Mo, "
              f"{matrix.shape[1]} colonnes)")
        return 0

    voies = ENCODAGES if args.encodage == "les-deux" else (args.encodage,)
    started = time.monotonic()
    passes = {voie: passe(voie, encoded, spec, y, w, groups, is_train, is_test,
                          classes, args.rapide) for voie in voies}
    duration = round(time.monotonic() - started, 1)

    principal = passes.get("dessin") or passes[voies[0]]
    comparaison = comparer(principal["test"],
                           here / "mode_choice_policy_metrics.json",
                           here / "mnl_model_metrics.json")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "temoin": {
            "question": ("l'avantage du booster sur le logit vient-il des ARBRES ou du "
                         "BOOSTING ?"),
            "ticket": "docs/tickets/ticket_044_temoin_random_forest.md",
            "spec": "specs/ticket_044/temoin_random_forest.md",
            "nature": ("témoin, pas candidat — aucun modèle n'est sérialisé, aucun "
                       "consommateur ; rejouer demande `make forest`"),
        },
        "spec_version": spec["spec_version"],
        "dataset": dataset_path.name,
        "split": spec.get("split"),
        "grille_reduite": bool(args.rapide),
        "seconds": duration,
        "principal": principal,
        "comparaison": comparaison,
    }
    if "natif" in passes and passes["natif"] is not principal:
        report["sensibilite_encodage"] = {
            **passes["natif"],
            "ecart_au_principal": {
                "accuracy_weighted": float(passes["natif"]["test"]["accuracy_weighted"]
                                           - principal["test"]["accuracy_weighted"]),
                "cel_weighted": float(passes["natif"]["test"]["cel_weighted"]
                                      - principal["test"]["cel_weighted"]),
                "l1_probability_mass": float(
                    passes["natif"]["test"]["mode_shares"]["l1_probability_mass"]
                    - principal["test"]["mode_shares"]["l1_probability_mass"]),
                "lecture": ("écart de la voie native à la voie principale : ce que coûte de "
                            "lire les catégorielles comme des ordinales"),
            },
        }

    print("\n" + "=" * 70)
    if comparaison["statut"] == "non mesuré":
        print(f"Comparaison : non mesuré — références absentes "
              f"({comparaison['references_manquantes']}). "
              f"{comparaison['comment_les_produire']}")
    else:
        print(f"{'axe':26s} {'RF':>9s} {'LightGBM':>9s} {'logit':>9s} {'part':>7s}")
        for key in comparaison["axes"]:
            row = comparaison["axes"][key]
            part = row["part_de_l_ecart_comblee"]
            part_txt = f"{part:7.2f}" if part is not None else "     n/m"
            print(f"{row['libelle']:26s} {row['random_forest']:9.4f} "
                  f"{row['lightgbm']:9.4f} {row['logit']:9.4f} {part_txt}")
        v = comparaison["verdict"]
        print(f"\nVerdict (seuils déclarés {SEUIL_BOOSTING} / {SEUIL_ARBRES}) : "
              f"**{v['conclusion']}**\n  {v['lecture']}")
    if "sensibilite_encodage" in report:
        ecart = report["sensibilite_encodage"]["ecart_au_principal"]
        print(f"\nCoût de l'encodage natif (ordinales) : "
              f"exactitude {ecart['accuracy_weighted']:+.4f}, "
              f"CEL {ecart['cel_weighted']:+.4f}, "
              f"L1 masse {ecart['l1_probability_mass']:+.4f}")

    if args.artefact:
        if "dessin" not in passes:
            raise SystemExit(
                "[ALARME] `--artefact` exige la voie principale (« dessin ») : le témoin ne "
                "publie pas un contrat de rejeu bâti sur la voie de sensibilité.")
        # La matrice de dessin part AVEC l'artefact : 1,4 Mo compressés (elle est surtout
        # faite de 0 et de 1), contre 165 Mo pour la forêt. C'est ce qui permet au rejeu de
        # n'exiger que numpy — le conteneur des expériences n'a pas de moteur parquet.
        matrix, _ = build_matrix(encoded, spec, w, is_train, "dessin")
        trainset_path = out_dir / "rf_mode_choice_trainset.npz"
        np.savez_compressed(trainset_path, X=matrix, y=y.astype("int8"), w=w,
                            is_train=is_train, is_test=is_test)
        print(f"\nMatrice d'entraînement écrite : {trainset_path} "
              f"({trainset_path.stat().st_size / 1e6:.1f} Mo, {matrix.shape[1]} colonnes)")
        artefact = build_artefact(passes["dessin"], spec, spec_path, dataset_path,
                                  trainset_path, report["generated_at"])
        artefact_path = out_dir / "rf_mode_choice_policy.json"
        artefact_path.write_text(json.dumps(artefact, ensure_ascii=False, indent=1) + "\n",
                                 encoding="utf-8")
        report["artefact"] = {
            "fichier": artefact_path.name,
            "matrice": trainset_path.name,
            "contient_des_arbres": False,
            "rejeu": ("RFPredictor réajuste la forêt depuis le parquet en ~10 s ; il refuse "
                      "si le SHA du parquet ou la version de scikit-learn diverge"),
        }
        print(f"\nArtefact de rejeu écrit : {artefact_path} "
              f"({artefact_path.stat().st_size / 1e3:.0f} ko, aucun arbre)")

    out_path = out_dir / "rf_mode_choice_metrics.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"\nÉcrit en {duration:.0f} s :\n - {out_path} "
          f"({out_path.stat().st_size / 1e3:.0f} ko — mesures seules, aucun modèle)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
