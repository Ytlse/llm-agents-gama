"""export_equipment_propensity.py — Lot 1 des tickets 016 et 017, en une passe.

Deux traits du persona sont aujourd'hui **recopiés** du donneur ENTD 2008 apparié à la
personne (`eqasim-toulouse/synthesis/population/enriched.py`), et tous deux sont faux de
la même façon : le total tient à peu près, la répartition est retournée, et la cause est
la même — `matching_attributes` utilise une classe d'âge `[14, 29, 44, 59, 74]` qui
couvre 15 à 29 ans d'un seul bloc, là où l'enquête voit la propension s'effondrer d'un
facteur 2 à l'intérieur de cette classe.

| Trait | Écart mesuré (ticket) |
|---|---|
| `has_pt_subscription` | étudiants **−38,9 pt**, retraités **+12,0 pt**, ensemble −3,9 |
| `has_driving_license` | 18-24 ans **+27,3 pt**, ensemble +5,6 |

Les deux tickets écrivent que « les lots 1 et 2 sont communs : même fichier source, même
restriction `PENQ = 1`, même pondération `COEP`, même cause, même patron de correction.
Les traiter ensemble divise le coût par deux ; les traiter séparément fait écrire deux
fois le même chargeur. » Ce script est cette mise en commun : un chargeur, deux cibles,
deux ressources.

## Ce qu'il écrit

`llm_module/data/pt_subscription.json` et `llm_module/data/driving_license.json` :
coefficients du logit, vocabulaire d'occupation, médiane de densité du périmètre, tables
de recette hors-échantillon, bloc de provenance. **Aucune microdonnée** — c'est ce qui
permet de committer les ressources alors que leur source est d'accès restreint
(ProGEDO/ADISP `lil-1750`).

## Deux décisions de méthode, écrites plutôt que subies

**1. La validation croisée est groupée par ménage, jamais par personne.** Deux membres
d'un même foyer partagent la motorisation, la zone et le contexte : un découpage par
personne mettrait le même ménage des deux côtés et surestimerait la généralisation.
67 % des ménages n'ont qu'une personne enquêtée, ce qui borne d'emblée ce qu'on peut
apprendre de la corrélation intra-foyer — le ticket 016 demande de le publier, pas de le
taire.

**2. Les paliers tarifaires sont ajustés puis arbitrés, pas décrétés.** La règle Tisséo
« moins de 26 ans » et l'ouverture senior (65 ans, ou 62 pour les retraités) disent
*où* placer une rupture dans la courbe d'âge ; elles ne disent pas qu'elle vaut la peine.
Le script ajuste chaque trait **avec et sans** ces paliers et publie les deux AUC
hors-échantillon. La règle de décision est écrite ici, avant de voir le résultat :

    les paliers sont retenus si l'AUC hors-échantillon groupée par ménage gagne
    au moins KNOT_MIN_GAIN ; sinon ils sont retirés et le retrait est imprimé.

C'est la seule façon d'empêcher une covariable « à saveur métier » de rester parce
qu'elle a l'air pertinente.

Usage :
    llm-agents/.venv/bin/python -m scripts.progedo_logit.export_equipment_propensity
    llm-agents/.venv/bin/python -m scripts.progedo_logit.export_equipment_propensity --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

from llm_module.core.equipment_propensity import (
    DRIVING_LICENSE,
    FEATURE_BASE,
    FEATURE_KNOTS,
    PT_SUBSCRIPTION,
    RESOURCE_DIR,
    TraitSpec,
    design_vector,
    write_resource,
)
from scripts.progedo_logit.build_mode_choice_dataset import (
    GENDER,
    MAIN_OCCUPATION,
    build_geo,
    find_project_root,
    load_raw,
)

# Régularisation. Faible pénalisation : on veut la loi de l'enquête, pas un modèle
# parcimonieux — l'objectif est de reproduire des strates publiées, et un `C` serré
# écraserait justement les modalités peu peuplées que le ticket demande de tenir.
PROPENSITY_C = 1e3
CV_SPLITS = 5

# Gain minimal d'AUC hors-échantillon pour retenir les paliers tarifaires. Fixé avant
# de voir le résultat (cf. l'en-tête). 0,002 est l'ordre du bruit de la CV sur ~15 000
# personnes : en dessous, on ne distingue pas un gain d'un artefact de découpage.
KNOT_MIN_GAIN = 0.002

# Une cellule sous ce nombre d'observations pondérées ne tranche rien : elle est
# signalée dans les tables, pas lissée en silence.
THIN_CELL = 30.0

# Cibles opposables, recalculées sur `lil-1750` par les tickets 016 et 017. Elles ne
# sont PAS recalculées ici : le script mesure ce que sa loi reproduit, et la
# confrontation à ces valeurs est ce qui dit si le lot 1 tient.
AGE_BANDS_PT = ((5, 18, "5-17"), (18, 25, "18-24"), (25, 35, "25-34"),
                (35, 50, "35-49"), (50, 65, "50-64"), (65, 200, "65+"))
AGE_BANDS_LICENSE = ((18, 25, "18-24"), (25, 35, "25-34"), (35, 50, "35-49"),
                     (50, 65, "50-64"), (65, 75, "65-74"), (75, 200, "75+"))

TARGETS_PT = {
    "overall": 25.8,
    "occupation": {"Étudiant": 74.3, "Scolaire (jusqu'au Bac)": 33.3,
                   "Chômeur/recherche d'emploi": 28.8, "Personne au foyer": 24.0,
                   "Travail à temps partiel": 21.5, "Retraité": 17.7,
                   "Travail à plein temps": 14.8},
    "age": {"5-17": 32.9, "18-24": 63.3, "25-34": 22.7, "35-49": 15.2,
            "50-64": 14.8, "65+": 18.9},
    "cars": {"0": 61.8, "1": 25.5, "2+": 16.1},
    "gender": {"Female": 28.0, "Male": 23.6},
}

TARGETS_LICENSE = {
    "overall": 85.9,
    "occupation": {"Travail à plein temps": 94.8, "Retraité": 92.6,
                   "Travail à temps partiel": 86.5,
                   "Chômeur/recherche d'emploi": 69.4, "Personne au foyer": 63.9,
                   "Étudiant": 59.2},
    "age": {"18-24": 58.1, "25-34": 84.3, "35-49": 91.8, "50-64": 94.3,
            "65-74": 93.8, "75+": 88.9},
    "gender": {"Male": 88.6, "Female": 83.4},
}


# ── Chargement — un seul, pour les deux traits ────────────────────────────────

def load_people(root: Path) -> pd.DataFrame:
    """Personnes enquêtées, dotées des deux cibles et des covariables communes.

    Restriction `PENQ = 1` et pondération `COEP` : `COEP` est nulle pour les
    non-enquêtés, donc toute statistique pondérée est déjà correctement restreinte —
    mais on filtre explicitement plutôt que de s'appuyer sur cette coïncidence.

    La clé ménage réelle est `(ZF, ECH)` : `ECH` seul n'est pas unique d'une zone à
    l'autre. Même règle que `build_household` et `export_bike_ownership`.
    """
    progedo = root / "data" / "PROGEDO 2023" / "lil-1750-Donnees_CSV"
    pers, men, _ = load_raw(progedo / "fichiers_standards")

    men = men.copy()
    men["cars"] = pd.to_numeric(men["M6"], errors="coerce")
    geo, _, _ = build_geo(root / "llm_module" / "data" / "zf_zones.gpkg", men)
    zone = geo.reindex(men["ZFM"]).reset_index(drop=True)
    men["density"] = zone["density_hh_km2"].values
    men["dist_center"] = zone["dist_center_km"].values
    indexed = men.set_index(["ZFM", "ECH"])

    pers = pers.copy()
    key = pd.MultiIndex.from_arrays([pers["ZFP"], pers["ECH"]])
    people = pd.DataFrame({
        "hh_id": [f"{z}|{e}" for z, e in zip(pers["ZFP"], pers["ECH"])],
        "PENQ": pers["PENQ"].values,
        "age": pd.to_numeric(pers["P4"], errors="coerce").values,
        "gender": pers["P2"].map(GENDER).values,
        "main_occupation": pers["P9"].map(MAIN_OCCUPATION).values,
        "weight": pd.to_numeric(pers["COEP"], errors="coerce").values,
        # Les deux cibles, recodées ici et nulle part ailleurs.
        #
        # `P7 == 3` = « conduite accompagnée et leçons de conduite » : 266 personnes,
        # âge médian 18 ans, dont 155 majeures. Elles ne sont PAS titulaires — le
        # `.eq("1")` le dit, mais c'est écrit pour que personne ne le relise comme un
        # oubli.
        "has_pt_subscription": pers["P12"].eq("6").values,
        "has_driving_license": pers["P7"].eq("1").values,
        "cars": key.map(indexed["cars"]).values,
        "density": key.map(indexed["density"]).values,
        "dist_center": key.map(indexed["dist_center"]).values,
    })

    before = len(people)
    people = people[(people["PENQ"] == "1") & (people["weight"] > 0)]
    people = people.dropna(
        subset=["age", "gender", "main_occupation", "cars", "dist_center", "weight"]
    ).reset_index(drop=True)
    print(f"Personnes : {before} → {len(people)} enquêtées exploitables")
    solo = int((people.groupby("hh_id").size() == 1).sum())
    n_hh = people.hh_id.nunique()
    print(f"Ménages à une seule personne enquêtée : {solo}/{n_hh} "
          f"({100 * solo / n_hh:.0f} %) — borne d'identification : la corrélation "
          f"intra-foyer résiduelle ne sera pas reproduite, seulement mesurée")
    return people


# ── Ajustement ───────────────────────────────────────────────────────────────

def matrix(people: pd.DataFrame, occupations: tuple[str, ...],
           features: tuple[str, ...], median_density: float) -> pd.DataFrame:
    """Matrice de design, construite par la fonction **du module**.

    Jamais une recopie de la formule : c'est ce qui garantit que l'entraînement et
    l'application voient exactement le même vecteur. Une recopie dériverait au premier
    changement de recodage.
    """
    rows = [
        design_vector(age, gender, occupation, cars, density, dist,
                      occupations, features, median_density)
        for age, gender, occupation, cars, density, dist in zip(
            people["age"], people["gender"], people["main_occupation"],
            people["cars"], people["density"], people["dist_center"])
    ]
    return pd.DataFrame(rows, columns=list(features))


def fit(people: pd.DataFrame, target: str, occupations: tuple[str, ...],
        features: tuple[str, ...], median_density: float) -> tuple[LogisticRegression,
                                                                   np.ndarray, float]:
    """Logit pondéré + prédiction hors-échantillon groupée par ménage."""
    X = matrix(people, occupations, features, median_density)
    y = people[target].astype(int)
    weight = people["weight"]
    model = LogisticRegression(max_iter=5000, C=PROPENSITY_C).fit(
        X, y, sample_weight=weight)

    oof = np.zeros(len(people))
    for train, test in GroupKFold(n_splits=CV_SPLITS).split(
            X, y, groups=people["hh_id"]):
        fold = LogisticRegression(max_iter=5000, C=PROPENSITY_C).fit(
            X.iloc[train], y.iloc[train], sample_weight=weight.iloc[train])
        oof[test] = fold.predict_proba(X.iloc[test])[:, 1]
    auc_out = float(roc_auc_score(y, oof, sample_weight=weight))
    return model, oof, auc_out


def fit_with_knot_arbitration(people: pd.DataFrame, spec: TraitSpec,
                              occupations: tuple[str, ...],
                              median_density: float) -> dict:
    """Ajuste sans puis avec les paliers tarifaires, et tranche selon la règle écrite."""
    base = tuple(FEATURE_BASE) + tuple(f"occ_{o}" for o in occupations)
    with_knots = tuple(FEATURE_BASE) + tuple(FEATURE_KNOTS) + tuple(
        f"occ_{o}" for o in occupations)

    print(f"\n── {spec.key} " + "─" * max(0, 56 - len(spec.key)))
    _, oof_base, auc_base = fit(people, spec.key, occupations, base, median_density)
    model_k, oof_k, auc_k = fit(people, spec.key, occupations, with_knots,
                                median_density)
    gain = auc_k - auc_base
    keep = gain >= KNOT_MIN_GAIN
    print(f"AUC hors-échantillon (CV groupée ménage) : sans paliers {auc_base:.4f} | "
          f"avec paliers {auc_k:.4f} | gain {gain:+.4f}")
    print(f"Règle (gain ≥ {KNOT_MIN_GAIN}) → paliers tarifaires "
          f"{'RETENUS' if keep else 'RETIRÉS'}"
          + ("" if keep else " — la rupture d'âge est déjà portée par les termes "
                             "continus et les occupations"))

    features = with_knots if keep else base
    if keep:
        model, oof, auc = model_k, oof_k, auc_k
    else:
        model, oof, auc = fit(people, spec.key, occupations, features, median_density)
    auc_in = float(roc_auc_score(
        people[spec.key].astype(int),
        model.predict_proba(matrix(people, occupations, features,
                                   median_density))[:, 1],
        sample_weight=people["weight"]))
    print(f"AUC en place {auc_in:.4f} | hors-échantillon {auc:.4f}")
    return {
        "law": {
            "features": list(features),
            "occupations": list(occupations),
            "intercept": round(float(model.intercept_[0]), 8),
            "coefficients": [round(float(v), 8) for v in model.coef_[0]],
            "median_density": round(median_density, 6),
        },
        "fit": {
            "n_persons": int(len(people)),
            "restriction": "PENQ = 1 (personnes enquêtées)",
            "weighting": "COEP — coefficient de redressement de la personne enquêtée",
            "regularisation_C": PROPENSITY_C,
            "cv": f"GroupKFold({CV_SPLITS}) groupée par ménage — un découpage par "
                  f"personne mettrait le même foyer des deux côtés",
            "auc_in_sample": round(auc_in, 4),
            "auc_out_of_sample_grouped_by_household": round(auc, 4),
            "knots_offered": list(FEATURE_KNOTS),
            "knots_retained": keep,
            "knot_auc_gain": round(float(gain), 5),
            "knot_min_gain_rule": KNOT_MIN_GAIN,
        },
        "oof": oof,
    }


# ── Recette ──────────────────────────────────────────────────────────────────

def _band(age: float, bands) -> str:
    for low, high, label in bands:
        if low <= age < high:
            return label
    return "hors bandes"


def _cars_class(cars: float) -> str:
    return "0" if cars <= 0 else ("1" if cars < 2 else "2+")


def stratum_table(people: pd.DataFrame, target: str, oof: np.ndarray,
                  keys: pd.Series, order, targets: dict) -> list[dict]:
    """Observé / prédit hors-échantillon / cible, par strate, avec effectifs.

    L'écart affiché est **prédit − observé** : c'est ce que la loi rate sur l'enquête
    elle-même, hors échantillon. La colonne cible dit en plus si l'observé du script
    coïncide avec la valeur publiée par le ticket — s'il ne coïncide pas, ce n'est pas
    la loi qui est en cause mais la définition de la strate, et il faut le voir.
    """
    weight = people["weight"].values
    y = people[target].astype(float).values
    rows = []
    for label in order:
        mask = (keys == label).values
        w = weight[mask]
        if w.sum() <= 0:
            continue
        observed = 100.0 * float((w * y[mask]).sum() / w.sum())
        predicted = 100.0 * float((w * oof[mask]).sum() / w.sum())
        rows.append({
            "stratum": label,
            "n_persons": int(mask.sum()),
            "n_weighted": round(float(w.sum()), 1),
            "observed_pct": round(observed, 2),
            "predicted_oof_pct": round(predicted, 2),
            "gap_pt": round(predicted - observed, 2),
            "ticket_target_pct": targets.get(label),
            "thin_cell": bool(w.sum() < THIN_CELL),
        })
    return rows


def validation(people: pd.DataFrame, spec: TraitSpec, oof: np.ndarray,
               bands, targets: dict) -> dict:
    """Les tables de recette des tickets, mesurées hors échantillon."""
    scope = people if spec.key == "has_pt_subscription" else people[people.age >= 18]
    idx = scope.index
    sub_oof = oof[idx]
    weight = scope["weight"].values
    y = scope[spec.key].astype(float).values
    overall_obs = 100.0 * float((weight * y).sum() / weight.sum())
    overall_pred = 100.0 * float((weight * sub_oof).sum() / weight.sum())

    out = {
        "scope": ("5 ans et plus" if spec.key == "has_pt_subscription"
                  else "18 ans et plus"),
        "overall": {
            "observed_pct": round(overall_obs, 2),
            "predicted_oof_pct": round(overall_pred, 2),
            "gap_pt": round(overall_pred - overall_obs, 2),
            "ticket_target_pct": targets["overall"],
        },
        "by_occupation": stratum_table(
            scope, spec.key, sub_oof, scope["main_occupation"],
            list(targets["occupation"]), targets["occupation"]),
        "by_age": stratum_table(
            scope, spec.key, sub_oof,
            scope["age"].map(lambda a: _band(a, bands)),
            list(targets["age"]), targets["age"]),
        "by_gender": stratum_table(
            scope, spec.key, sub_oof, scope["gender"],
            list(targets["gender"]), targets["gender"]),
    }
    if "cars" in targets:
        out["by_household_cars"] = stratum_table(
            scope, spec.key, sub_oof, scope["cars"].map(_cars_class),
            list(targets["cars"]), targets["cars"])
    # Corrélation intra-foyer : critère de VALIDATION, pas d'identité (ticket 016).
    # Si la loi reste à son niveau d'indépendance, la covariable de motorisation ne
    # fait pas son travail, et il faut le dire plutôt que de la croire utile.
    multi = scope.groupby("hh_id").filter(lambda g: len(g) >= 2)
    if len(multi):
        obs_all = multi.groupby("hh_id")[spec.key].all()
        out["intra_household"] = {
            "households_with_2plus_respondents": int(obs_all.size),
            "all_equipped_pct_observed": round(100.0 * float(obs_all.mean()), 2),
            "note": "à comparer au niveau d'indépendance ; un modèle qui y reste "
                    "signale que la motorisation ne porte pas la corrélation",
        }
    return out


def report(spec: TraitSpec, block: dict) -> None:
    v = block["validation"]
    print(f"\nRecette — {spec.key} ({v['scope']})")
    o = v["overall"]
    print(f"  ensemble : observé {o['observed_pct']:.1f} % | prédit hors-éch. "
          f"{o['predicted_oof_pct']:.1f} % | écart {o['gap_pt']:+.1f} | "
          f"cible ticket {o['ticket_target_pct']}")
    for name, key in (("occupation", "by_occupation"), ("âge", "by_age"),
                      ("genre", "by_gender"), ("motorisation", "by_household_cars")):
        if key not in v:
            continue
        print(f"  par {name} :")
        for row in v[key]:
            flag = "  ⚠ cellule mince" if row["thin_cell"] else ""
            target = row["ticket_target_pct"]
            target_txt = f"cible {target:5.1f}" if target is not None else "cible   —  "
            print(f"    {row['stratum']:28s} n={row['n_persons']:5d} "
                  f"obs {row['observed_pct']:5.1f} % | préd {row['predicted_oof_pct']:5.1f} % "
                  f"| écart {row['gap_pt']:+5.1f} | {target_txt}{flag}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="ajuste et affiche la recette, sans écrire les ressources")
    args = parser.parse_args(argv)

    root = find_project_root()
    progedo = root / "data" / "PROGEDO 2023"
    if not progedo.is_dir():
        print(f"[erreur] Données PROGEDO absentes : {progedo} "
              f"(accès restreint lil-1750)", file=sys.stderr)
        return 1

    people = load_people(root)
    occupations = tuple(sorted(set(MAIN_OCCUPATION.values())))
    median_density = float(people["density"].median())
    print(f"Vocabulaire d'occupation ({len(occupations)}) : {', '.join(occupations)}")
    print(f"Densité médiane du périmètre : {median_density:.1f} ménages/km²")

    written = []
    for spec, bands, targets in ((PT_SUBSCRIPTION, AGE_BANDS_PT, TARGETS_PT),
                                 (DRIVING_LICENSE, AGE_BANDS_LICENSE,
                                  TARGETS_LICENSE)):
        block = fit_with_knot_arbitration(people, spec, occupations, median_density)
        block["validation"] = validation(people, spec, block.pop("oof"), bands,
                                         targets)
        report(spec, block)
        if not args.dry_run:
            path = RESOURCE_DIR / spec.resource
            write_resource(path, spec, block["law"],
                           {**block["validation"], "fit": block["fit"]},
                           {"source": "EMC² Toulouse 2023 — ProGEDO/ADISP lil-1750, "
                                      "fichier standard `pers`",
                            "tickets": ["016", "017"]})
            written.append(path)

    if args.dry_run:
        print("\n--dry-run : aucune ressource écrite.")
    else:
        for path in written:
            print(f"\nÉcrit : {path.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
