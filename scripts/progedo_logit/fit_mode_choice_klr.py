"""fit_mode_choice_klr.py — Estimation de la troisième famille : logistique à noyau (KLR).

Estime une **régression logistique à noyau RBF approchée par Nyström** sur les mêmes
microdonnées d'enquête que le booster LightGBM et le logit multinomial, et la sérialise en
`klr_model.json` (format `klr_mode_choice_policy` v1).

**Pourquoi une troisième famille.** Le dépôt tenait les deux extrêmes d'un même axe — un
booster exact et non lisse (0,785 d'exactitude test, élasticités erratiques par
construction), un logit lisse et moins exact (0,766) — et rien entre les deux. C'est
exactement le compromis que Martín-Baos et al. (2023) étudient, et leur conclusion désigne
la KLR comme le meilleur équilibre entre exactitude prédictive et plausibilité
comportementale. Double usage, le second valant peut-être davantage : un troisième chiffre
au niveau 3 de l'ablation, et un **second arbitre** pour le bloc C du score à deux oracles —
un arbitre unique ne se réfute pas.

La cible déclarée est d'entrer **entre** les deux sur l'exactitude en restant lisse en
élasticités. Espérer dépasser le booster serait contredit par Wang et al. (2024), qui
concluent sur des centaines de modèles que le contexte des données pèse davantage que la
famille retenue.

**Ce qui rend la parité vraie par construction** (règles K1 à K3), plutôt que promise :

1. le **même jeu** et la **même colonne `split`**, étanche au ménage ;
2. le **même `sample_weight`** (COEP) à l'estimation et dans toutes les métriques ;
3. le **même `encode_features`**, et surtout la **même matrice de dessin** que le logit,
   construite par la même fonction (`design_matrix_from_contract`) : un noyau RBF n'a de
   sens que sur des variables centrées-réduites, et refaire l'encodage introduirait un
   décalage que rien ne signalerait ;
4. les **mêmes métriques**, produites par `mode_choice_eval.evaluate_proba`.

**Le réglage ne lit jamais le test** (K5). `γ`, `λ` et `m` sont choisis en validation croisée
5 plis groupée par ménage **dans le train**, et les points d'appui sont tirés dans la partie
d'ajustement **de chaque pli** : un appui tiré une fois pour toutes sur le train entier
pourrait tomber dans le pli de validation, qui entrerait alors dans la structure du modèle.

**Le banc écarte la dérive avant de classer** (K6). Ce sont les probabilités, pas
l'exactitude, qui produisent les parts modales : une configuration qui gagne sur la
log-vraisemblance en déplaçant les parts est un mauvais modèle pour ce dépôt. Toute
configuration dont la L1 des parts hors-échantillon dépasse `référence + 0,005` est donc
écartée du classement et comptée. La référence est la **L1 hors-échantillon du logit sur les
mêmes plis** : mesurée plutôt que choisie, extérieure à la famille, et cohérente avec ce
qu'on attend d'une KLR — tenir l'agrégé comme le logit (0,0006 mesuré le 2026-09-11, contre
0,0117 pour le booster).

Usage :
    python -m scripts.progedo_logit.fit_mode_choice_klr [--out-dir DIR]
    python -m scripts.progedo_logit.fit_mode_choice_klr --gamma 0.04 --C 1 --m 1000

N'exige **pas** les données PROGEDO brutes (accès restreint lil-1750) : le parquet et le spec
sont dans le dépôt. L'artefact, lui, porte `m` lignes réelles d'enquête comme points d'appui
et reste gitignoré, comme les deux autres.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.model_selection import GroupKFold

from scripts.progedo_logit.fit_mode_choice_logit import (
    build_contract,
    fit_logit,
    normalized_weights,
)
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
from scripts.progedo_logit.mode_choice_klr import (
    EIGENVALUE_FLOOR,
    KLR_FORMAT,
    KLR_FORMAT_VERSION,
    KLRPredictor,
    nystrom_basis,
    rbf_kernel,
)
from scripts.progedo_logit.mode_choice_logit import design_matrix_from_contract

# --- Réglages d'estimation --------------------------------------------------
# Même estimateur que le logit, sur la carte de Nyström au lieu de la matrice de dessin :
# la KLR *est* un logit multinomial, dans un espace de variables que le noyau fabrique.
SOLVER = "lbfgs"
MAX_ITER = 2000
TOLERANCE = 1e-6

#: Graine unique du script. Le tirage des appuis en dépend, donc l'artefact aussi : deux
#: exécutions du même jour produisent le même modèle, et le SHA de l'artefact reste un
#: identifiant de version (R12 de la plateforme d'expériences).
SEED = 20260911

#: Grille de `γ`, en multiples de l'heuristique médiane (voir `median_sq_distance`). Ancrer
#: sur une grandeur mesurée plutôt que sur des valeurs absolues rend la grille lisible : le
#: multiplicateur 1 est « la largeur de noyau que la géométrie du jeu suggère ».
GAMMA_MULTIPLIERS = (0.25, 0.5, 1.0, 2.0, 4.0)

#: Grille du ridge, exprimée en `C = 1/λ` comme chez scikit-learn et comme pour le logit.
C_GRID = (0.1, 1.0, 10.0, 100.0)

#: Grille du nombre de points d'appui. Le ticket borne 500 à 2 000 : en dessous
#: l'approximation ne décrit plus l'espace, au-dessus la mémoire de `n × m` décide.
M_GRID = (500, 1000, 2000)

#: `m` de l'étage A. La grille (γ, C) se balaie au `m` le moins cher, puis seul `m` varie
#: sur le couple retenu : un balayage complet des trois axes coûterait 300 ajustements pour
#: une information que les deux étages donnent en 110.
STAGE_A_M = 500

CV_FOLDS = 5

#: Tolérance de calibration, reprise telle quelle du banc du booster : une configuration
#: qui dégrade la L1 des parts modales au-delà de ce seuil est écartée quel que soit son
#: gain sur le critère primaire.
L1_TOLERANCE = 0.005

#: En dessous de ce nombre de configurations éligibles, le banc le **dit** : un plafond qui
#: ne laisse presque rien ne sélectionne plus, il subit. Vacuité ≠ perfection.
MIN_ELIGIBLE = 3

#: Plafond mémoire de la carte de Nyström, en gibioctets. `n × m × 8` octets, et
#: scikit-learn en garde une copie : le refus arrive **avant** l'allocation, avec la valeur
#: de `m` à réduire, plutôt qu'un `MemoryError` nu au milieu d'un banc de 20 minutes.
MEMORY_LIMIT_GB = 3.0

#: Nombre de paires tirées pour l'heuristique médiane. 1 000 × 1 000 suffit à stabiliser une
#: médiane et coûte 8 Mo.
MEDIAN_SAMPLE = 1000


# ---------------------------------------------------------------------------
# Géométrie du noyau
# ---------------------------------------------------------------------------

def median_sq_distance(Z: np.ndarray, rng: np.random.Generator,
                       sample: int = MEDIAN_SAMPLE) -> float:
    """Médiane des `‖z − z′‖²` sur un sous-échantillon de paires — l'heuristique médiane.

    C'est l'ancrage classique de la largeur d'un noyau RBF : `γ = 1/médiane` place
    l'exponentielle à `e^{-1}` pour deux points « typiquement éloignés ». Sans ancrage, une
    grille de `γ` en valeurs absolues n'aurait pas de sens d'un jeu à l'autre — elle dépend
    du nombre de colonnes de dessin et de leur centrage-réduction.
    """
    n = len(Z)
    size = min(sample, n // 2)
    picks = rng.choice(n, size=2 * size, replace=False)
    left, right = Z[picks[:size]], Z[picks[size:]]
    a2 = np.einsum("ij,ij->i", left, left)[:, None]
    b2 = np.einsum("ij,ij->i", right, right)[None, :]
    d2 = np.maximum(a2 + b2 - 2.0 * (left @ right.T), 0.0)
    return float(np.median(d2))


def draw_landmarks(households: np.ndarray, m: int,
                   rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Indices de `m` points d'appui, **un par ménage**, et les ménages tirés (K4).

    Tirer `m` trajets au hasard concentrerait les appuis sur les gros foyers — jusqu'à 38
    déplacements pour un seul ménage du train — et l'espace des variables serait décrit là
    où quelques ménages habitent. On tire donc `m` ménages distincts, puis un trajet dans
    chacun.
    """
    unique = np.unique(households)
    if m > len(unique):
        raise ValueError(
            f"{m} points d'appui demandés pour {len(unique)} ménages disponibles : "
            "un appui par ménage est la règle K4, réduisez m.")
    chosen = rng.permutation(unique)[:m]
    indices = np.array([rng.choice(np.flatnonzero(households == hh)) for hh in chosen])
    return indices, chosen


def memory_guard(n_rows: int, m: int, limit_gb: float = MEMORY_LIMIT_GB) -> float:
    """Refuse une carte de Nyström trop grande **avant** de l'allouer. Rend la taille en Go.

    Deux fois `n × m × 8` octets : la carte, plus la copie que scikit-learn fait en
    validant ses entrées. À `m = 2 000` sur 39 203 lignes, cela fait 1,25 Gio.
    """
    gib = 2.0 * n_rows * m * 8 / 2**30
    if gib > limit_gb:
        raise SystemExit(
            f"[ALARME] Carte de Nyström de {gib:.2f} Gio pour n={n_rows}, m={m} — au-delà du "
            f"plafond de {limit_gb:.2f} Gio. Réduisez m (--m-grid) ou relevez "
            "--memory-limit-gb en connaissance de cause.")
    return gib


# ---------------------------------------------------------------------------
# Ajustement
# ---------------------------------------------------------------------------

def nystrom_map(landmarks: np.ndarray, gamma: float) -> tuple[np.ndarray, dict]:
    """Base de projection `W` et son diagnostic, depuis les appuis et `γ` seuls.

    Ne dépend que des appuis : c'est ce qui permet de la construire une fois par pli et d'y
    ajuster tous les ridges de la grille.
    """
    return nystrom_basis(rbf_kernel(landmarks, landmarks, gamma), EIGENVALUE_FLOOR)


def features(Z: np.ndarray, landmarks: np.ndarray, gamma: float,
             basis: np.ndarray) -> np.ndarray:
    """Carte de Nyström `Φ = K(Z, L)·W`, l'espace dans lequel le logit est ajusté."""
    return rbf_kernel(Z, landmarks, gamma) @ basis


def fit_klr(Phi: np.ndarray, y: np.ndarray, w: np.ndarray, C: float) -> LogisticRegression:
    """Ajuste le logit multinomial pondéré sur la carte de Nyström.

    Les poids sont normalisés à une moyenne de 1 par la **même** fonction que le logit : le
    redressement COEP vaut 85,5 en moyenne, et passé tel quel il multiplie la vraisemblance
    par ~85 sans toucher à la pénalité — `C` ne voudrait plus rien dire.
    """
    model = LogisticRegression(
        C=C, solver=SOLVER, max_iter=MAX_ITER, tol=TOLERANCE, fit_intercept=True)
    model.fit(Phi, y, sample_weight=normalized_weights(w))
    return model


def dual_coefficients(basis: np.ndarray, model: LogisticRegression) -> np.ndarray:
    """`B = W·βᵀ`, de forme `m × classes` — ce que l'artefact transporte (K7).

    Replier `W` dans les coefficients rend l'artefact 20 fois plus petit et la prédiction
    indépendante de la décomposition propre. L'égalité `Φβᵀ = K·B` est exacte ; elle est
    vérifiée à 1e-9 avant écriture, et mesurée à 3e-14.
    """
    return basis @ model.coef_.T


# ---------------------------------------------------------------------------
# Banc : validation croisée groupée par ménage, dans le train
# ---------------------------------------------------------------------------

def l1_mass(proba: np.ndarray, y: np.ndarray, w: np.ndarray, n_classes: int) -> float:
    """L1 entre parts modales prédites (en masse de probabilité) et observées, pondérée."""
    observed = np.array([w[y == k].sum() / w.sum() for k in range(n_classes)])
    mass = (proba * w[:, None]).sum(axis=0) / w.sum()
    return float(np.abs(mass - observed).sum())


def score_oof(proba: np.ndarray, y: np.ndarray, w: np.ndarray, n_classes: int) -> dict:
    """Les deux grandeurs du banc : critère primaire et garde-fou de calibration."""
    return {
        "cv_log_loss_weighted": float(log_loss(
            y, proba, labels=list(range(n_classes)), sample_weight=w)),
        "l1_mass_oof": l1_mass(proba, y, w, n_classes),
    }


def logit_reference(Z: np.ndarray, y: np.ndarray, w: np.ndarray, folds: list,
                    n_classes: int, C: float) -> dict:
    """Référence du plafond de calibration : le **logit sur les mêmes plis** (K6).

    Le banc du booster se compare à sa propre configuration sortante ; la KLR n'en a pas,
    étant une famille neuve. La référence est donc extérieure et mesurée : la L1
    hors-échantillon du logit, sur la même matrice de dessin, les mêmes plis, les mêmes
    poids. Elle dit ce qu'on demande à la KLR — tenir l'agrégé comme le logit.
    """
    oof = np.zeros((len(y), n_classes))
    for fit_idx, valid_idx in folds:
        model = fit_logit(Z[fit_idx], y[fit_idx], w[fit_idx], C)
        oof[valid_idx] = model.predict_proba(Z[valid_idx])
    scores = score_oof(oof, y, w, n_classes)
    return {"family": "logit multinomial", "C": C,
            "measured_on": "mêmes plis, même matrice de dessin, mêmes poids", **scores}


def cross_val_klr(Z: np.ndarray, y: np.ndarray, w: np.ndarray, households: np.ndarray,
                  folds: list, n_classes: int, gamma: float, m: int,
                  c_values: tuple[float, ...],
                  seed: int) -> tuple[dict[float, np.ndarray], dict[float, int]]:
    """Prédictions hors-échantillon pour un `(γ, m)` et **chaque** `C`, en un seul passage.

    La carte de Nyström d'un pli ne dépend pas de `C` : la construire une fois et y ajuster
    les quatre ridges économise quatre cinquièmes du travail de noyau. Les appuis sont tirés
    **dans la partie d'ajustement du pli** (K5), avec une graine dérivée du pli — donc
    reproductible, et jamais la même que celle du modèle final.

    Rend aussi, par `C`, le **nombre de plis qui ont atteint le plafond d'itérations**. Un
    pli non convergé ne rend pas la solution du ridge demandé : son score n'est pas celui de
    la configuration, et laisser une telle ligne concourir reviendrait à classer un modèle
    qu'on n'a pas estimé. L'appelant l'écarte, il ne le corrige pas.
    """
    oof = {C: np.zeros((len(y), n_classes)) for C in c_values}
    capped = {C: 0 for C in c_values}
    for fold, (fit_idx, valid_idx) in enumerate(folds):
        rng = np.random.default_rng(seed + 1000 * fold)
        local = draw_landmarks(households[fit_idx], m, rng)[0]
        landmarks = Z[fit_idx][local]
        basis, _ = nystrom_map(landmarks, gamma)
        Phi_fit = features(Z[fit_idx], landmarks, gamma, basis)
        Phi_valid = features(Z[valid_idx], landmarks, gamma, basis)
        for C in c_values:
            model = fit_klr(Phi_fit, y[fit_idx], w[fit_idx], C)
            if int(np.max(np.atleast_1d(model.n_iter_))) >= MAX_ITER:
                capped[C] += 1
            oof[C][valid_idx] = model.predict_proba(Phi_valid)
    return oof, capped


def run_bench(Z: np.ndarray, y: np.ndarray, w: np.ndarray, households: np.ndarray,
              folds: list, n_classes: int, gamma_base: float, gamma_multipliers: tuple,
              c_grid: tuple, stage_a_m: int, seed: int, memory_limit: float) -> dict:
    """Étage A du banc : la grille (γ, C) au `m` le moins cher.

    Rend les configurations mesurées, chacune avec ses deux métriques, son compte de plis
    non convergés et sa durée. Le garde-fou (`apply_guard`) et le classement (`best_of`)
    sont appliqués par l'appelant : le banc **mesure**, il ne décide pas.
    """
    results: list[dict] = []

    def measure(gamma_mult: float, m: int, c_values: tuple) -> None:
        gamma = gamma_mult * gamma_base
        memory_guard(len(y), m, memory_limit)
        start = time.perf_counter()
        oof, capped = cross_val_klr(Z, y, w, households, folds, n_classes, gamma, m,
                                    c_values, seed)
        elapsed = time.perf_counter() - start
        for C in c_values:
            scores = score_oof(oof[C], y, w, n_classes)
            results.append({"gamma_multiplier": gamma_mult, "gamma": gamma, "C": C, "m": m,
                            **scores, "n_folds_not_converged": capped[C],
                            "seconds": round(elapsed / len(c_values), 1)})
            print(f"  γ×{gamma_mult:<5g} C={C:<7g} m={m:<5d} "
                  f"log-loss CV = {scores['cv_log_loss_weighted']:.5f} "
                  f"L1 = {scores['l1_mass_oof']:.4f}"
                  + (f" [{capped[C]} pli(s) NON CONVERGÉ(S)]" if capped[C] else "")
                  + f" ({elapsed / len(c_values):.0f} s)", flush=True)

    print(f"\nÉtage A — grille (γ, C) à m = {stage_a_m}, "
          f"{len(gamma_multipliers) * len(c_grid)} configurations :")
    stage_a_start = time.perf_counter()
    for multiplier in gamma_multipliers:
        measure(multiplier, stage_a_m, c_grid)
    print(f"Étage A terminé en {time.perf_counter() - stage_a_start:.0f} s")

    return {"results": results}


def apply_guard(results: list[dict], reference_l1: float,
                tolerance: float = L1_TOLERANCE) -> tuple[list[dict], list[dict], float]:
    """Sépare les configurations éligibles de celles qu'on écarte, **avec leur raison**.

    Deux motifs d'écart, et aucun n'est un ajustement du score :

    - **dérive des parts modales** (K6), au-delà de `référence + tolérance` ;
    - **pli non convergé** : le ridge demandé n'a pas été estimé, donc la ligne ne mesure
      pas la configuration qu'elle nomme. La rattraper en relevant le plafond
      d'itérations serait un autre banc, pas une correction de celui-ci.
    """
    ceiling = reference_l1 + tolerance
    eligible, rejected = [], []
    for result in results:
        if result.get("n_folds_not_converged"):
            reason = (f"{result['n_folds_not_converged']} pli(s) au plafond de "
                      f"{MAX_ITER} itérations")
        elif result["l1_mass_oof"] > ceiling:
            reason = (f"dérive des parts modales : L1 {result['l1_mass_oof']:.4f} > "
                      f"{ceiling:.4f}")
        else:
            eligible.append(result)
            continue
        rejected.append({**result, "ecartee_pour": reason})
    return eligible, rejected, ceiling


def grid_edges(best: dict, gamma_multipliers: tuple, c_grid: tuple,
               m_grid: tuple) -> list[str]:
    """Axes sur lesquels la valeur retenue est au **bord** de la grille explorée.

    Un optimum au bord ne dit pas « c'est l'optimum », il dit « l'optimum est peut-être
    dehors ». Le banc du booster publie la même information (« aucun bord de grille
    touché ») : sans elle, une grille trop étroite se lit comme un résultat.
    """
    edges = []
    if best["gamma_multiplier"] in (min(gamma_multipliers), max(gamma_multipliers)):
        edges.append(f"γ×{best['gamma_multiplier']:g} (grille "
                     f"{min(gamma_multipliers):g}..{max(gamma_multipliers):g})")
    if best["C"] in (min(c_grid), max(c_grid)):
        edges.append(f"C={best['C']:g} (grille {min(c_grid):g}..{max(c_grid):g})")
    if len(m_grid) > 1 and best["m"] in (min(m_grid), max(m_grid)):
        edges.append(f"m={best['m']} (grille {min(m_grid)}..{max(m_grid)})")
    return edges


def best_of(results: list[dict]) -> dict:
    """Meilleure configuration au critère primaire : la log-vraisemblance négative CV.

    L'exactitude n'y sert pas d'arbitre — un modèle qui gagne un point d'exactitude en
    écrasant le vélo (4 % des déplacements) dégrade les parts modales, qui sont ce que le
    pipeline consomme.
    """
    return min(results, key=lambda r: r["cv_log_loss_weighted"])


# ---------------------------------------------------------------------------
# Diagnostic de lissage
# ---------------------------------------------------------------------------

def profile_by_decile(proba: np.ndarray, values: np.ndarray, w: np.ndarray,
                      classes: list[str], bins: int = 10) -> list[dict]:
    """Parts modales prédites par décile d'une variable continue — lecture d'élasticité.

    La cible du ticket n'est pas seulement d'entrer entre les deux familles sur l'exactitude,
    c'est de **rester lisse**. Un profil de parts le long des déciles de `od_km` se lit d'un
    coup d'œil : une famille lisse y dessine des courbes monotones, un booster y dessine des
    marches. Publié en diagnostic, comme les importances par gain du booster et les plus
    gros coefficients du logit.
    """
    finite = np.isfinite(values)
    edges = np.quantile(values[finite], np.linspace(0, 1, bins + 1))
    out: list[dict] = []
    for i in range(bins):
        low, high = edges[i], edges[i + 1]
        mask = finite & (values >= low) & ((values <= high) if i == bins - 1
                                          else (values < high))
        if not mask.any():
            continue
        weights = w[mask]
        mass = (proba[mask] * weights[:, None]).sum(axis=0) / weights.sum()
        out.append({"decile": i + 1, "od_km_min": float(low), "od_km_max": float(high),
                    "n": int(mask.sum()),
                    "shares": {c: float(v) for c, v in zip(classes, mass)}})
    return out


# ---------------------------------------------------------------------------
# Sérialisation
# ---------------------------------------------------------------------------

def build_artefact(spec: dict, spec_path: Path, dataset_path: Path, contract: dict,
                   kernel: dict, nystrom: dict, landmarks: np.ndarray,
                   dual_coef: np.ndarray, intercept: np.ndarray, training: dict,
                   metrics: dict) -> dict:
    """Artefact autoportant : de quoi prédire sans scikit-learn ni parquet (K7)."""
    return {
        "format": KLR_FORMAT,
        "format_version": KLR_FORMAT_VERSION,
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
        "encoding": {
            "shared_with": "fit_mode_choice_policy.encode_features",
            "design_shared_with": "mode_choice_logit.design_matrix_from_contract",
            "missing": "NaN en entrée, traité par klr.design.missing_rule",
        },
        "geo_reference": spec.get("geo_reference"),
        "domain": spec.get("domain"),
        "notes": spec.get("notes"),
        "training": training,
        "metrics": metrics,
        "klr": {
            # Contrat de matrice : celui du logit, à l'identique. La clé est `design` et
            # non `logit` — c'est le même contrat, ce n'est pas la même famille.
            "design": contract,
            "kernel": kernel,
            "nystrom": nystrom,
            "landmarks": [[float(v) for v in row] for row in landmarks],
            "dual_coef": [[float(v) for v in row] for row in dual_coef],
            "intercept": [float(v) for v in intercept],
            "link": ("softmax(K(Z,L)·dual_coef + intercept), K = exp(−γ‖z−l‖²), "
                     "classes dans l'ordre du spec"),
            "landmark_privacy": ("les appuis sont m lignes réelles d'enquête "
                                 "(centrées-réduites) : artefact gitignoré, source PROGEDO "
                                 "d'accès restreint lil-1750"),
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
    parser.add_argument("--gamma", type=float, default=None,
                        help="γ imposé (défaut : choisi en validation croisée)")
    parser.add_argument("--C", type=float, default=None,
                        help="C = 1/λ imposé (défaut : validation croisée)")
    parser.add_argument("--m", type=int, default=None,
                        help="Nombre de points d'appui imposé (défaut : validation croisée)")
    parser.add_argument("--m-grid", type=int, nargs="+", default=list(M_GRID),
                        help=f"Grille de m pour l'étage B (défaut : {list(M_GRID)})")
    parser.add_argument("--gamma-multipliers", type=float, nargs="+",
                        default=list(GAMMA_MULTIPLIERS),
                        help=("Grille de γ en multiples de l'heuristique médiane (défaut : "
                              f"{list(GAMMA_MULTIPLIERS)}) — à élargir quand le banc "
                              "signale un bord de grille touché"))
    parser.add_argument("--folds", type=int, default=CV_FOLDS,
                        help=f"Plis de la validation croisée (défaut : {CV_FOLDS})")
    parser.add_argument("--memory-limit-gb", type=float, default=MEMORY_LIMIT_GB,
                        help=f"Plafond de la carte de Nyström (défaut : {MEMORY_LIMIT_GB} Gio)")
    args = parser.parse_args(argv)

    started = time.perf_counter()
    root = find_project_root()
    here = root / "scripts" / "progedo_logit"
    dataset_path = args.dataset or (here / "progedo_mode_choice_v2.parquet")
    spec_path = args.spec or (here / "feature_spec.json")
    out_dir = args.out_dir or here
    out_dir.mkdir(parents=True, exist_ok=True)

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    df = pd.read_parquet(dataset_path)
    check_spec(spec, df)          # même garde-fou de fuite que les deux autres familles

    names = feature_names(spec)
    classes = spec["target"]["classes"]
    print(f"Jeu : {len(df)} lignes | spec v{spec['spec_version']} | "
          f"{len(names)} variables | {len(classes)} classes")

    encoded = encode_features(df, spec)
    y = df[spec["target"]["name"]].map({c: i for i, c in enumerate(classes)}).to_numpy()
    w = df[spec["sample_weight"]].to_numpy(dtype=float)
    households = df["hh_id"].to_numpy()

    is_train = (df["split"] == "train").to_numpy()
    is_test = (df["split"] == "test").to_numpy()
    print(f"Split lu dans le parquet : train={is_train.sum()} test={is_test.sum()} "
          f"| ménages={df['hh_id'].nunique()}")

    # Contrat de dessin : construit sur le train seul, par le code du logit.
    contract = build_contract(spec, encoded[is_train], w[is_train])
    Z = design_matrix_from_contract(encoded, spec["features"], contract)
    print(f"Matrice de dessin (partagée avec le logit) : {Z.shape[1]} colonnes "
          f"({len(contract['missing_indicators'])} indicatrices de manquant)")

    Ztr, ytr, wtr, hhtr = Z[is_train], y[is_train], w[is_train], households[is_train]
    rng = np.random.default_rng(SEED)
    gamma_base = 1.0 / median_sq_distance(Ztr, rng)
    print(f"Heuristique médiane : ‖z−z′‖² médian = {1.0 / gamma_base:.3f} "
          f"→ γ_med = {gamma_base:.5f}")

    imposed = all(v is not None for v in (args.gamma, args.C, args.m))
    if imposed:
        tuning = {"gamma": args.gamma, "C": args.C, "m": args.m, "imposed": True,
                  "scored_on": "aucun réglage — valeurs imposées en ligne de commande",
                  "gamma_median_heuristic": gamma_base}
        print(f"\nRéglage imposé : γ = {args.gamma}, C = {args.C}, m = {args.m}")
    else:
        if any(v is not None for v in (args.gamma, args.C, args.m)):
            raise SystemExit(
                "--gamma, --C et --m s'imposent ensemble ou pas du tout : un réglage "
                "partiellement imposé rendrait la trace du banc illisible.")
        folds = list(GroupKFold(n_splits=args.folds).split(Ztr, ytr, groups=hhtr))
        print(f"\nValidation croisée {args.folds} plis, groupée par ménage, DANS le train "
              f"(plis de {[len(v) for _, v in folds]} lignes)")

        print("\nRéférence du plafond de calibration — le logit sur les mêmes plis :")
        t0 = time.perf_counter()
        reference = logit_reference(Ztr, ytr, wtr, folds, len(classes), C=1.0)
        print(f"  log-loss CV = {reference['cv_log_loss_weighted']:.5f} | "
              f"L1 hors-échantillon = {reference['l1_mass_oof']:.4f} "
              f"({time.perf_counter() - t0:.0f} s)")
        ceiling_value = reference["l1_mass_oof"] + L1_TOLERANCE
        print(f"  plafond = {reference['l1_mass_oof']:.4f} + {L1_TOLERANCE} "
              f"= {ceiling_value:.4f} : au-delà, une configuration est écartée du classement")

        bench = run_bench(Ztr, ytr, wtr, hhtr, folds, len(classes), gamma_base,
                          tuple(args.gamma_multipliers), C_GRID, STAGE_A_M, SEED,
                          args.memory_limit_gb)
        results = bench["results"]

        eligible, rejected, ceiling = apply_guard(results, reference["l1_mass_oof"])
        print(f"\n{len(eligible)}/{len(results)} configurations passent le garde-fou de "
              f"calibration (L1 ≤ {ceiling:.4f}).")
        for r in rejected:
            print(f"  écartée : γ×{r['gamma_multiplier']:g} C={r['C']:g} m={r['m']} — "
                  f"{r['ecartee_pour']}")
        if not eligible:
            raise SystemExit(
                "[ALARME] Aucune configuration ne passe le garde-fou de calibration : le "
                "banc ne sélectionne pas, il subirait. Rien n'est publié. Élargissez la "
                "grille ou revoyez la référence du plafond (K6).")
        if len(eligible) < MIN_ELIGIBLE:
            print(f"⚠ [ALARME] Seulement {len(eligible)} configuration(s) éligible(s) sur "
                  f"{len(results)} : le plafond de calibration décide plus que le critère "
                  "primaire. Le triplet retenu est publié avec cette réserve.")

        stage_a_best = best_of(eligible)
        print(f"\nÉtage A retenu : γ×{stage_a_best['gamma_multiplier']:g} "
              f"(γ = {stage_a_best['gamma']:.5f}), C = {stage_a_best['C']:g}")

        extra_m = [m for m in args.m_grid if m != STAGE_A_M]
        if extra_m:
            print(f"\nÉtage B — nombre de points d'appui, sur le couple retenu : {extra_m}")
            stage_b_start = time.perf_counter()
            for m in extra_m:
                memory_guard(len(ytr), m, args.memory_limit_gb)
                t0 = time.perf_counter()
                oof, capped = cross_val_klr(Ztr, ytr, wtr, hhtr, folds, len(classes),
                                            stage_a_best["gamma"], m,
                                            (stage_a_best["C"],), SEED)
                scores = score_oof(oof[stage_a_best["C"]], ytr, wtr, len(classes))
                elapsed = time.perf_counter() - t0
                results.append({"gamma_multiplier": stage_a_best["gamma_multiplier"],
                                "gamma": stage_a_best["gamma"], "C": stage_a_best["C"],
                                "m": m, **scores,
                                "n_folds_not_converged": capped[stage_a_best["C"]],
                                "seconds": round(elapsed, 1)})
                print(f"  m={m:<5d} log-loss CV = {scores['cv_log_loss_weighted']:.5f} "
                      f"L1 = {scores['l1_mass_oof']:.4f}"
                      + (f" [{capped[stage_a_best['C']]} pli(s) NON CONVERGÉ(S)]"
                         if capped[stage_a_best["C"]] else "")
                      + f" ({elapsed:.0f} s)", flush=True)
            print(f"Étage B terminé en {time.perf_counter() - stage_b_start:.0f} s")

        eligible, rejected, ceiling = apply_guard(results, reference["l1_mass_oof"])
        best = best_of(eligible)
        edges = grid_edges(best, tuple(args.gamma_multipliers), C_GRID,
                           tuple(args.m_grid))
        tuning = {
            "grid": {"gamma_multipliers": list(args.gamma_multipliers),
                     "gamma_median_heuristic": gamma_base,
                     "C": list(C_GRID), "m": list(args.m_grid), "stage_a_m": STAGE_A_M},
            "folds": args.folds,
            "grouped_by": "hh_id",
            "scored_on": "train uniquement — le split test n'est jamais lu pour régler",
            "criterion": "cv_log_loss_weighted, sous garde-fou de calibration",
            "calibration_guard": {
                "tolerance": L1_TOLERANCE,
                "reference": reference,
                "ceiling": ceiling,
                "n_eligible": len(eligible),
                "n_rejected": len(rejected),
                "rejected": [{k: r[k] for k in ("gamma", "C", "m", "l1_mass_oof",
                                                "n_folds_not_converged", "ecartee_pour")}
                             for r in rejected],
                "note": ("ce sont les probabilités, pas l'exactitude, qui produisent les "
                         "parts modales : une configuration qui dérive est écartée avant "
                         "tout classement, comme une configuration dont un pli n'a pas "
                         "convergé"),
            },
            "landmark_draw": ("un trajet tiré par ménage, m ménages distincts, appuis tirés "
                              "dans la partie d'ajustement de CHAQUE pli"),
            "results": results,
            "gamma": best["gamma"],
            "gamma_multiplier": best["gamma_multiplier"],
            "C": best["C"],
            "m": best["m"],
            "cv_log_loss_weighted": best["cv_log_loss_weighted"],
            "l1_mass_oof": best["l1_mass_oof"],
            "grid_edges_touched": edges,
        }
        if edges:
            print("⚠ Bord de grille touché : " + " ; ".join(edges)
                  + " — l'optimum est peut-être hors de la grille explorée. "
                    "Élargir : --gamma-multipliers / --m-grid.")
        print(f"\nRetenu : γ = {best['gamma']:.5f} (×{best['gamma_multiplier']:g}), "
              f"C = {best['C']:g}, m = {best['m']} — log-loss CV "
              f"{best['cv_log_loss_weighted']:.5f}, L1 {best['l1_mass_oof']:.4f}")

    # ── Modèle final : appuis tirés sur le train entier ──────────────────────
    gamma, C, m = tuning["gamma"], tuning["C"], tuning["m"]
    size_gib = memory_guard(int(is_train.sum()), m, args.memory_limit_gb)
    print(f"\nAjustement final (carte de Nyström {int(is_train.sum())} × {m}, "
          f"{size_gib:.2f} Gio avec la copie de scikit-learn) :")
    t0 = time.perf_counter()
    final_rng = np.random.default_rng(SEED)
    local_idx, landmark_households = draw_landmarks(hhtr, m, final_rng)
    landmarks = Ztr[local_idx]
    basis, nystrom = nystrom_map(landmarks, gamma)
    if nystrom["dropped_eigencomponents"]:
        print(f"⚠ {nystrom['dropped_eigencomponents']} composante(s) propre(s) sous le "
              f"plancher écartée(s) : rang effectif {nystrom['rank']}/{m}")
    Phi_train = features(Ztr, landmarks, gamma, basis)
    model = fit_klr(Phi_train, ytr, wtr, C)
    iterations = int(np.max(np.atleast_1d(model.n_iter_)))
    if iterations >= MAX_ITER:
        raise SystemExit(
            f"[ALARME] L'ajustement a atteint le plafond de {MAX_ITER} itérations : les "
            "coefficients ne sont pas convergés et ne doivent pas être publiés.")
    print(f"Convergence en {iterations} itérations (plafond {MAX_ITER}), "
          f"{time.perf_counter() - t0:.0f} s")

    dual = dual_coefficients(basis, model)
    nystrom = {**nystrom, "landmark_draw": tuning.get("landmark_draw", "un trajet par ménage"),
               "landmark_households": [str(h) for h in landmark_households],
               "seed": SEED}
    kernel = {"type": "rbf", "gamma": float(gamma),
              "gamma_median_heuristic": float(gamma_base),
              "median_sq_distance": float(1.0 / gamma_base),
              "heuristic": f"médiane des ‖z−z′‖² sur {MEDIAN_SAMPLE}² paires du train"}

    training = {
        "estimator": ("kernel logistic regression (RBF + Nyström, lbfgs multinomial, "
                      "pondérée COEP)"),
        "gamma": float(gamma), "C": float(C), "m": int(m),
        "rank": nystrom["rank"],
        "tuning": tuning,
        "n_iter": iterations,
        "n_fit": int(is_train.sum()),
        "n_test": int(is_test.sum()),
        "n_design_columns": int(Z.shape[1]),
        "sample_weight": spec["sample_weight"],
        "weight_normalization": ("poids ramenés à une moyenne de 1 pour l'estimation ; "
                                 "métriques calculées avec le COEP brut"),
        "split": spec.get("split"),
        "seed": SEED,
    }

    # ── Métriques du test scellé, par le module partagé ─────────────────────
    proba_test = model.predict_proba(features(Z[is_test], landmarks, gamma, basis))
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

    artefact = build_artefact(spec, spec_path, dataset_path, contract, kernel, nystrom,
                              landmarks, dual, model.intercept_, training, metrics)

    # ── Autoportance, AVANT d'écrire ────────────────────────────────────────
    # L'évaluateur pur numpy doit reproduire scikit-learn : c'est la vérification qui rend
    # le repliement `B = W·βᵀ` digne de confiance. Un artefact qui ne se relit pas comme il
    # a été estimé est un artefact faux, et rien ne le dirait à la lecture.
    replayed = KLRPredictor(artefact).predict(encoded[is_test])
    gap = float(np.abs(replayed - proba_test).max())
    if gap > 1e-9:
        raise SystemExit(
            f"[ALARME] L'artefact ne reproduit pas l'estimation : écart max {gap:.2e} sur "
            "les probabilités du test. Artefact non écrit.")
    print(f"Autoportance vérifiée : écart max artefact / estimateur = {gap:.1e}")

    artefact["metrics"]["mode_profile_by_od_decile"] = profile_by_decile(
        proba_test, df.loc[is_test, "od_km"].to_numpy(dtype="float64"),
        w[is_test], classes)

    artefact_path = out_dir / "klr_model.json"
    artefact_path.write_text(json.dumps(artefact, ensure_ascii=False, indent=1) + "\n",
                             encoding="utf-8")

    report = {
        "generated_at": artefact["generated_at"],
        "spec_version": spec["spec_version"],
        "dataset": dataset_path.name,
        "split": spec.get("split"),
        "training": training,
        "kernel": kernel,
        "nystrom": {k: v for k, v in nystrom.items() if k != "landmark_households"},
        "test": artefact["metrics"],
    }
    metrics_path = out_dir / "klr_model_metrics.json"
    metrics_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")

    size_kb = artefact_path.stat().st_size / 1e3
    print(f"\nÉcrits :\n - {artefact_path} ({size_kb:.0f} ko, format "
          f"{KLR_FORMAT} v{KLR_FORMAT_VERSION})\n - {metrics_path}")
    print(f"Terminé en {time.perf_counter() - started:.0f} s — "
          f"γ = {gamma:.5f}, C = {C:g}, m = {m}, rang {nystrom['rank']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
