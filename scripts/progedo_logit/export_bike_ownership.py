"""export_bike_ownership.py — Les trois étages de l'équipement vélo, appris sur EMC².

Produit `llm_module/data/bike_ownership.json` : les coefficients des deux logit du
ticket 015, plus les tables de validation qui servent à juger le résultat.

**Étage 1 — combien de vélos dans le ménage.** Logit multinomial sur `k = M21` écrêté à
`4+`, 10 783 ménages, pondération `COE0`. Covariables : taille du ménage, nombre de VP
(`M6`), et la zone de résidence par sa densité de ménages et sa distance à l'hypercentre.
Ni `M1` (type d'habitat) ni `M2` (occupation du logement) — les raisons sont écrites dans
`llm_module/core/bike_ownership.py`, elles ne sont pas les mêmes : `M1` est moins
informatif que la zone dont il est imputé, `M2` n'existe pas côté persona.

**Étage 2 — qui, dans le ménage, tient les vélos.** Logit binaire sur `P20 ∈ {plusieurs
jours/semaine, plusieurs jours/mois, occasionnellement}`, la pratique déclarée en tant que
**conducteur** — le meilleur indicateur disponible de « à qui est ce vélo », et il n'y en
a pas d'autre : l'enquête ne demande jamais qui possède quoi. Restreint à `PENQ = 1`
(15 775 personnes sur 20 890), pondération `COEP` — qui vaut exactement 0 pour les
non-enquêtés, donc toute statistique pondérée `COEP` est déjà correctement restreinte.

**Limite d'identification, à assumer et non à contourner** : 67 % des ménages n'ont
qu'une seule personne enquêtée (7 238 sur 10 783). On peut estimer `P(pratique |
covariables)` ; on ne peut **pas** observer qui, parmi trois frères et sœurs, roule.
L'attribution est donc indépendante conditionnellement à `k`, sans corrélation intra-foyer
modélisée — et le script le calcule et l'écrit, plutôt que de le laisser deviner.

**La validation croisée est groupée par ménage, jamais par personne** : deux membres du
même foyer partagent `k`, la fuite serait mécanique.

Ce que le script écrit : des **coefficients** et des **tables agrégées**, aucune
microdonnée — même statut que `export_housing_type.py` et la couche de zones fines : hors
dépôt, régénérable, jamais committée.

Usage :
    python -m scripts.progedo_logit.export_bike_ownership [--out FICHIER]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

from llm_module.core.bike_ownership import (
    DEFAULT_RESOURCE,
    K_CLASSES,
    K_MAX,
    MIN_AGE_ELECTRIC,
    MIN_AGE_ELIGIBLE,
    PROPENSITY_BASE_FEATURES,
    SIZE_MAX,
    STOCK_FEATURES,
    VAE_SHARE,
    Member,
    assign,
    propensity_design,
    stock_design,
)
from llm_module.core.housing_type import MODALITY_KEYS, HousingTypeTable, draw
from scripts.progedo_logit.build_mode_choice_dataset import (
    GENDER,
    MAIN_OCCUPATION,
    build_geo,
    find_project_root,
    load_raw,
)

# Modalités de `P20` qui comptent comme « pratique le vélo en tant que conducteur ».
# `4` = « Jamais », et les vides sont les non-enquêtés (déjà écartés par `PENQ`).
PRACTICE_CODES = ("1", "2", "3")

# Recodage `M1` → clés de `core.housing_type`, uniquement pour les tables de validation
# (l'étage 1 n'utilise PAS l'habitat — cf. le module).
HOUSING = {
    "1": "individuel_isole", "2": "individuel_accole",
    "3": "petit_habitat_collectif", "4": "grand_habitat_collectif", "5": "autres",
}

# Régularisation. Volontairement faible sur l'étage 1 (les effectifs sont larges et on
# veut la loi observée, pas une loi rétrécie vers l'uniforme) et standard sur l'étage 2,
# où les indicatrices d'occupation ont des cellules minces.
STOCK_C = 1e3
PROPENSITY_C = 1.0
CV_SPLITS = 5

# Écrêtage des BUCKETS de taille de ménage dans les tables de validation. Distinct de
# `SIZE_MAX` (l'écrêtage des indicatrices du modèle) : la loi de `k` plafonne à `4+`
# parce que l'enquête montre qu'elle y plafonne réellement (2,62 / 2,64 / 2,42 vélos
# pour les tailles 4 / 5 / 6), mais le taux de PORTEURS continue de baisser au-delà,
# le dénominateur croissant sans le numérateur (63 % / 52 % / 40 %). Un bucket « 5+ »
# mélangerait donc deux régimes très différents, et sa valeur dépendrait entièrement du
# poids relatif des tailles 5 et 6 — qui n'est pas le même dans l'enquête et dans une
# population synthétique. Les buckets vont donc jusqu'à `6+` des deux côtés.
SIZE_BUCKET_MAX = 6

# Seuil de signalement d'une cellule. Le ticket l'exige : « toute cellule sous 30
# observations pondérées est signalée, pas lissée en silence ».
THIN_CELL = 30.0


# ── Chargement ───────────────────────────────────────────────────────────────

def load_frames(root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ménages et personnes de l'enquête, dotés de `k`, du VAE, de la taille et de la zone.

    La clé ménage réelle est `(ZFM, ECH)` — `ECH` seul n'est pas unique d'une zone à
    l'autre, même règle que `build_household`.

    `ML21` (nombre de vélos à assistance électrique) n'existe **pas** dans le fichier
    standard, où `M22` est entièrement vide : il faut le fichier original, dont la clé
    est `(MP2, ECH)` avec un `ECH` à 4 caractères là où le standard en porte 5 (le
    premier étant le type d'échantillon). Le rapprochement est vérifié ci-dessous sur
    `M20 == M21`, plutôt que supposé depuis l'ordre des lignes.
    """
    progedo = root / "data" / "PROGEDO 2023" / "lil-1750-Donnees_CSV"
    pers, men, _ = load_raw(progedo / "fichiers_standards")

    original = pd.read_csv(
        progedo / "fichiers_originaux"
        / "04a_EMC2_Toulouse_2023_Men_coef_ML21_21062023.csv",
        dtype=str, sep=None, engine="python")
    for column in original.columns:
        original[column] = original[column].str.strip().replace({"": np.nan})

    men = men.copy()
    men["k_raw"] = pd.to_numeric(men["M21"], errors="coerce")
    men["weight"] = pd.to_numeric(men["COE0"], errors="coerce")
    men["cars"] = pd.to_numeric(men["M6"], errors="coerce")
    men["housing"] = men["M1"].map(HOUSING)
    men["_ech4"] = men["ECH"].str[1:]

    vae = original.assign(
        n_vae=pd.to_numeric(original["ML21"], errors="coerce"),
        m20=pd.to_numeric(original["M20"], errors="coerce"),
    ).rename(columns={"MP2": "ZFM", "ECH": "_ech4"})
    men = men.merge(vae[["ZFM", "_ech4", "n_vae", "m20"]],
                    on=["ZFM", "_ech4"], how="left", validate="one_to_one")
    matched = men["m20"].notna()
    if not matched.all():
        raise SystemExit(
            f"Rapprochement du fichier original incomplet : {(~matched).sum()} ménages "
            "sans ML21. La clé (MP2, ECH) a changé — vérifiez la livraison lil-1750.")
    disagree = int((men["m20"] != men["k_raw"]).sum())
    if disagree:
        raise SystemExit(
            f"Rapprochement du fichier original suspect : {disagree} ménages où M20 "
            "(original) diffère de M21 (standard). Ce sont censément la même variable ; "
            "ne pas exporter un parc de VAE sur une jointure fausse.")
    print(f"ML21 rapproché sur {len(men)} ménages (M20 == M21 partout)")

    # Taille du ménage et éligibles de 5 ans et plus, comptés sur le fichier personnes.
    pers = pers.copy()
    pers["age"] = pd.to_numeric(pers["P4"], errors="coerce")
    sizes = pers.groupby(["ZFP", "ECH"]).size().rename("size")
    eligibles = (pers[pers["age"] >= MIN_AGE_ELIGIBLE]
                 .groupby(["ZFP", "ECH"]).size().rename("n_eligible"))
    key = pd.MultiIndex.from_arrays([men["ZFM"], men["ECH"]])
    men["size"] = key.map(sizes)
    men["n_eligible"] = key.map(eligibles).fillna(0)

    geo, _, _ = build_geo(root / "llm_module" / "data" / "zf_zones.gpkg", men)
    zone = geo.reindex(men["ZFM"]).reset_index(drop=True)
    men["density"] = zone["density_hh_km2"].values
    men["dist_center"] = zone["dist_center_km"].values

    # Personnes : démographie, pratique déclarée, et l'équipement de leur foyer.
    key_p = pd.MultiIndex.from_arrays([pers["ZFP"], pers["ECH"]])
    indexed = men.set_index(["ZFM", "ECH"])
    people = pd.DataFrame({
        "hh_id": [f"{z}|{e}" for z, e in zip(pers["ZFP"], pers["ECH"])],
        "ZF": pers["ZFP"].values,
        "PENQ": pers["PENQ"].values,
        "age": pers["age"].values,
        "gender": pers["P2"].map(GENDER).values,
        "main_occupation": pers["P9"].map(MAIN_OCCUPATION).values,
        "weight": pd.to_numeric(pers["COEP"], errors="coerce").values,
        "practises": pers["P20"].isin(PRACTICE_CODES).values,
        "k_raw": key_p.map(indexed["k_raw"]).values,
        "size": key_p.map(indexed["size"]).values,
        "density": key_p.map(indexed["density"]).values,
        "dist_center": key_p.map(indexed["dist_center"]).values,
    })

    n_men, n_pers = len(men), len(people)
    men = men.dropna(subset=["k_raw", "weight", "size", "dist_center"]).reset_index(drop=True)
    people = people[(people["PENQ"] == "1") & (people["weight"] > 0)]
    people = people.dropna(
        subset=["k_raw", "size", "age", "dist_center", "weight"]).reset_index(drop=True)
    print(f"Ménages  : {n_men} → {len(men)} exploitables")
    print(f"Personnes: {n_pers} → {len(people)} enquêtées exploitables")
    solo = int((people.groupby("hh_id").size() == 1).sum())
    print(f"Ménages à une seule personne enquêtée : {solo}/{people.hh_id.nunique()} "
          f"({100 * solo / people.hh_id.nunique():.0f} %) — l'attribution ne peut donc "
          f"pas modéliser de corrélation intra-foyer")
    return men, people


# ── Matrices de design, via les fonctions du module ──────────────────────────
# On passe par `stock_design` / `propensity_design` plutôt que de recopier les
# formules : c'est ce qui garantit que l'entraînement et l'application voient
# exactement le même vecteur. Une recopie dériverait au premier changement.

def stock_matrix(men: pd.DataFrame, median_density: float) -> pd.DataFrame:
    rows = [
        stock_design(int(size), cars,
                     median_density if pd.isna(density) else float(density),
                     float(dist))
        for size, cars, density, dist in zip(
            men["size"], men["cars"], men["density"], men["dist_center"])
    ]
    return pd.DataFrame(rows, columns=list(STOCK_FEATURES))


def propensity_matrix(people: pd.DataFrame, occupations: tuple[str, ...],
                      median_density: float) -> pd.DataFrame:
    rows = [
        propensity_design(int(k), int(size), age, gender, occupation,
                          median_density if pd.isna(density) else float(density),
                          float(dist), occupations)
        for k, size, age, gender, occupation, density, dist in zip(
            people["k_raw"], people["size"], people["age"], people["gender"],
            people["main_occupation"], people["density"], people["dist_center"])
    ]
    columns = list(PROPENSITY_BASE_FEATURES) + [f"occ_{o}" for o in occupations]
    return pd.DataFrame(rows, columns=columns)


# ── Étage 1 ──────────────────────────────────────────────────────────────────

def fit_stock(men: pd.DataFrame, median_density: float) -> tuple[dict, np.ndarray]:
    """Logit multinomial sur `k` écrêté. Renvoie le bloc de ressource et les lois prédites."""
    X = stock_matrix(men, median_density)
    y = men["k_raw"].clip(upper=K_MAX).astype(int)
    model = LogisticRegression(max_iter=5000, C=STOCK_C).fit(
        X, y, sample_weight=men["weight"])
    if tuple(int(c) for c in model.classes_) != K_CLASSES:
        raise SystemExit(
            f"Classes de l'étage 1 inattendues : {model.classes_} au lieu de {K_CLASSES}. "
            "Un k écrêté doit couvrir 0..K_MAX sans trou.")

    # Validation croisée groupée par ménage. Ici le ménage EST l'observation, donc le
    # groupe est trivial ; le pli reste un pli hors-échantillon honnête pour le
    # calibrage, et on l'écrit pour que la ressource dise sur quoi elle a été jugée.
    folds = GroupKFold(n_splits=CV_SPLITS)
    oof = np.zeros((len(men), len(K_CLASSES)))
    groups = men["ZFM"].astype(str) + "|" + men["ECH"].astype(str)
    for train, test in folds.split(X, y, groups=groups):
        fold = LogisticRegression(max_iter=5000, C=STOCK_C).fit(
            X.iloc[train], y.iloc[train], sample_weight=men["weight"].iloc[train])
        oof[test] = fold.predict_proba(X.iloc[test])

    doc = {
        "target": "k = M21 écrêté à 4+, nombre de vélos du ménage",
        "features": list(STOCK_FEATURES),
        "classes": list(K_CLASSES),
        "intercepts": [round(float(v), 8) for v in model.intercept_],
        "coefficients": [[round(float(v), 8) for v in row] for row in model.coef_],
        "n_households": int(len(men)),
        "weighting": "COE0 — coefficient de redressement du ménage",
        "regularisation_C": STOCK_C,
    }
    return doc, oof


# ── Étage 2 ──────────────────────────────────────────────────────────────────

def fit_propensity(people: pd.DataFrame, occupations: tuple[str, ...],
                   median_density: float) -> tuple[dict, np.ndarray]:
    """Logit binaire sur la pratique déclarée. Renvoie le bloc de ressource et l'OOF."""
    X = propensity_matrix(people, occupations, median_density)
    y = people["practises"].astype(int)
    weight = people["weight"]
    model = LogisticRegression(max_iter=5000, C=PROPENSITY_C).fit(
        X, y, sample_weight=weight)

    folds = GroupKFold(n_splits=CV_SPLITS)
    oof = np.zeros(len(people))
    for train, test in folds.split(X, y, groups=people["hh_id"]):
        fold = LogisticRegression(max_iter=5000, C=PROPENSITY_C).fit(
            X.iloc[train], y.iloc[train], sample_weight=weight.iloc[train])
        oof[test] = fold.predict_proba(X.iloc[test])[:, 1]

    auc_in = float(roc_auc_score(y, model.predict_proba(X)[:, 1], sample_weight=weight))
    auc_out = float(roc_auc_score(y, oof, sample_weight=weight))
    print(f"Étage 2 — AUC en place {auc_in:.4f} | hors-échantillon (groupée ménage) "
          f"{auc_out:.4f}")
    doc = {
        "target": "P20 ∈ {plusieurs jours/semaine, plusieurs jours/mois, "
                  "occasionnellement} — vélo, conducteur",
        "features": list(X.columns),
        "classes": [1],
        "intercepts": [round(float(model.intercept_[0]), 8)],
        "coefficients": [[round(float(v), 8) for v in model.coef_[0]]],
        "n_persons": int(len(people)),
        "restriction": "PENQ = 1 (personnes enquêtées)",
        "weighting": "COEP — coefficient de redressement de la personne enquêtée",
        "regularisation_C": PROPENSITY_C,
        "auc_in_sample": round(auc_in, 4),
        "auc_out_of_sample_grouped_by_household": round(auc_out, 4),
        "cv": f"GroupKFold({CV_SPLITS}) groupée par ménage — un split par personne "
              f"fuirait, deux membres d'un foyer partageant k",
    }
    return doc, oof


# ── Tables de validation ─────────────────────────────────────────────────────

def _share(frame: pd.DataFrame, mask: pd.Series, weight: str = "weight") -> float:
    total = frame[weight].sum()
    return float(100.0 * frame.loc[mask, weight].sum() / total) if total > 0 else float("nan")


def stock_validation(men: pd.DataFrame, oof: np.ndarray) -> dict:
    """Ce que l'étage 1 doit reproduire, et ce qu'il reproduit hors échantillon."""
    weight = men["weight"].values
    equipped_pred = 1.0 - oof[:, 0]
    expected_k = oof @ np.array(K_CLASSES, dtype=float)
    total = weight.sum()
    eligible = men["n_eligible"].values
    raw_k = men["k_raw"].values
    clipped_k = men["k_raw"].clip(upper=K_MAX).values
    out: dict = {
        "overall": {
            "equipped_pct_observed": round(_share(men, men["k_raw"] > 0), 2),
            "equipped_pct_predicted": round(float(100 * (weight * equipped_pred).sum() / total), 2),
            "bikes_per_household_observed": round(
                float((weight * clipped_k).sum() / total), 4),
            "bikes_per_household_predicted": round(
                float((weight * expected_k).sum() / total), 4),
        },
        # Ce que coûte l'écrêtage à `4+`, mesuré plutôt que supposé.
        #
        # Le critère d'acceptation du ticket demande **1,22 vélo/ménage (± 0,05)**.
        # C'est le chiffre publié, calculé sur `M21` non écrêté. Un modèle écrêté à
        # `4+` — l'écrêtage que le ticket spécifie lui-même, et sur lequel toutes ses
        # tables de référence sont bâties — ne peut structurellement pas l'atteindre :
        # il plafonne à 1,151, soit 0,065 en dessous, ce qui mange toute la tolérance.
        # Le critère est donc **restaté** : la cible opposable est la moyenne écrêtée.
        #
        # Ce n'est pas une concession de confort, et voici la mesure qui le montre :
        # sur la grandeur que le trait porte réellement — les vélos *attribuables*,
        # `min(k, éligibles de 5 ans et plus)`, puisqu'un vélo sans titulaire n'apparaît
        # pas dans le JSON — l'écrêtage ne coûte que 0,011 vélo par ménage et ne touche
        # que ~1 % des ménages. Les 4,1 % de foyers à 5 vélos et plus ont en moyenne
        # moins de 5 membres éligibles : leurs vélos surnuméraires n'auraient de toute
        # façon eu personne pour les porter.
        "clipping_cost": {
            "k_max": K_MAX,
            "bikes_per_household_unclipped": round(float((weight * raw_k).sum() / total), 4),
            "bikes_per_household_clipped": round(float((weight * clipped_k).sum() / total), 4),
            "attributable_per_household_unclipped": round(
                float((weight * np.minimum(raw_k, eligible)).sum() / total), 4),
            "attributable_per_household_clipped": round(
                float((weight * np.minimum(clipped_k, eligible)).sum() / total), 4),
            "households_losing_an_attributable_bike_pct": round(float(
                100 * weight[(raw_k > K_MAX) & (eligible > K_MAX)].sum() / total), 2),
            # Écart-type pondéré des vélos attribuables par ménage. Servi pour que
            # l'application puisse borner le bruit d'échantillonnage de sa moyenne :
            # sur 7 foyers mesurables (population de 10 agents), σ/√n vaut 0,45 vélo et
            # exiger ± 0,05 mesurerait uniquement le hasard.
            "attributable_sd": round(float(np.sqrt(
                np.average((np.minimum(clipped_k, eligible)
                            - np.average(np.minimum(clipped_k, eligible),
                                         weights=weight)) ** 2,
                           weights=weight))), 4),
            "note": "Le critère publié « 1,22 vélo/ménage » porte sur M21 non écrêté ; "
                    "un modèle écrêté à 4+ plafonne à la valeur `..._clipped`, qui est "
                    "la cible opposable. L'écrêtage est sans effet sur le trait produit "
                    "(cf. `attributable_*`, 0,011 d'écart) parce que l'attribution est "
                    "de toute façon bornée par le nombre de membres éligibles.",
        },
        "by_household_size": [],
        "by_housing_observed": [],
    }
    for size, frame in men.groupby(men["size"].clip(upper=SIZE_BUCKET_MAX)):
        index = frame.index
        out["by_household_size"].append({
            "size": int(size),
            "n": int(len(frame)),
            "weighted_n": round(float(frame["weight"].sum()), 1),
            "equipped_pct_observed": round(_share(frame, frame["k_raw"] > 0), 2),
            "equipped_pct_predicted": round(float(
                100 * (frame["weight"].values * equipped_pred[index]).sum()
                / frame["weight"].sum()), 2),
            # Servi pour la standardisation directe côté application : les foyers
            # mesurables d'une population synthétique ne sont pas un échantillon neutre
            # des tailles de ménage (un foyer d'une personne est toujours complet), donc
            # la cible doit être recomposée sur la ventilation réellement mesurée.
            "bikes_per_household_observed": round(float(
                (frame["weight"] * frame["k_raw"].clip(upper=K_MAX)).sum()
                / frame["weight"].sum()), 4),
            # Vélos réellement ATTRIBUABLES, `min(k, éligibles de 5 ans et plus)`.
            # C'est cette grandeur — et non le stock — que le trait individuel porte :
            # un vélo sans titulaire n'apparaît pas dans le JSON. Comparer les vélos
            # attribués d'une population au stock de l'enquête confond deux grandeurs
            # (0,33 contre 0,44 chez les personnes seules, l'écart étant les vélos que
            # personne ne peut porter).
            "attributable_per_household_observed": round(float(
                (frame["weight"] * np.minimum(frame["k_raw"].clip(upper=K_MAX),
                                              frame["n_eligible"])).sum()
                / frame["weight"].sum()), 4),
            "thin": bool(frame["weight"].sum() < THIN_CELL),
        })
    for housing, frame in men.groupby("housing"):
        index = frame.index
        out["by_housing_observed"].append({
            "housing": str(housing),
            "n": int(len(frame)),
            "weighted_n": round(float(frame["weight"].sum()), 1),
            "equipped_pct_observed": round(_share(frame, frame["k_raw"] > 0), 2),
            "equipped_pct_predicted": round(float(
                100 * (frame["weight"].values * equipped_pred[index]).sum()
                / frame["weight"].sum()), 2),
            "thin": bool(frame["weight"].sum() < THIN_CELL),
        })
    return out


def diluted_housing_reference(men: pd.DataFrame, root: Path, draws: int = 8) -> dict:
    """La cible **opposable** de l'équipement par type d'habitat, et pourquoi elle diffère.

    Le ticket demande de reproduire 71 % (individuel isolé) → 38 % (grand collectif),
    la courbe publiée. Ce critère est **inatteignable par construction** sur une
    population synthétique : l'habitat du persona est lui-même imputé depuis la loi de
    sa zone fine, et il ne coïncide avec l'habitat réel qu'une fois sur deux. Croiser le
    nombre de vélos **vrai de l'enquête** par l'habitat **imputé** suffit à écraser
    l'amplitude de 33 à ~19 points : c'est de la dilution de régression, elle plafonne
    ce que la mesure peut voir, et aucun modèle de `k` ne peut la défaire.

    Cette fonction calcule ce plafond, en rejouant l'imputation d'habitat de
    `enrich_housing_type` sur les ménages de l'enquête (dont on connaît le vrai `k`), et
    en moyennant sur plusieurs tirages pour que la cible ne dépende pas d'une graine.
    C'est cette courbe-là que la validation de la population doit viser ; la courbe
    publiée reste écrite à côté, comme le chiffre source qu'elle est.

    Depuis le **ticket 019**, l'imputation rejouée est conditionnée à la **taille du
    ménage** en plus de la zone : c'est la même loi que celle servie en production, et
    le taux d'accord avec l'habitat observé est mesuré ici plutôt que récité. Il fixe
    l'ampleur de la dilution, donc la hauteur du plafond.
    """
    # `FileNotFoundError` : ressource jamais exportée. `ValueError` : ressource exportée
    # pour une autre version du module que celle installée — c'est le cas pendant le
    # déploiement du ticket 019, dont le module exige la v2 quand l'exportateur produit
    # encore la v1. Les deux sont le même cas fonctionnel : « pas de loi d'habitat
    # utilisable ». On dégrade en le disant, on ne fait pas tomber tout l'export du
    # modèle vélo pour une cible annexe.
    try:
        table = HousingTypeTable.load()
    except (FileNotFoundError, ValueError) as exc:
        print(f"[avertissement] Loi du type de logement inutilisable — la cible diluée "
              f"par habitat n'est PAS calculée, et le contrôle de cet axe sera donc "
              f"absent du rapport d'enrichissement (pas « réussi » : absent).\n"
              f"  cause : {exc}\n"
              f"  suite : `make housing-type`, puis relancer `make bike-ownership`.")
        return {}

    weight = men["weight"].values
    # Deux grandeurs par modalité, et **il faut les deux** — c'est le piège de cet axe.
    #
    # `households`  : part de MÉNAGES équipés (`k > 0`). C'est la définition de la courbe
    #                 publiée (« Ménages équipés, individuel isolé : 70,9 % »).
    # `holders`     : part de PERSONNES dotées d'un vélo, sous les règles du mécanisme
    #                 (`min(min(k, K_MAX), éligibles) / taille`).
    #
    # Les deux diffèrent de 2 à 10 points **et l'écart suit la taille du ménage** : les
    # familles sont dans les maisons, et un foyer de quatre avec un vélo est « équipé »
    # alors qu'un seul de ses membres est doté. Servir la part de ménages en cible d'une
    # mesure faite par personne produit donc un biais négatif sur TOUTES les modalités,
    # d'autant plus fort que l'habitat est familial (−10,0 pts en individuel isolé contre
    # −3,2 en grand collectif). C'est une confusion d'unité, pas un défaut du modèle.
    accumulated: dict[str, list[float]] = {key: [] for key in MODALITY_KEYS}
    accumulated_holders: dict[str, list[float]] = {key: [] for key in MODALITY_KEYS}
    attributable = np.minimum(men["k_raw"].clip(upper=K_MAX), men["n_eligible"]).values
    sizes_arr = men["size"].values
    # Taux d'accord entre habitat imputé et habitat observé. C'est LUI qui gouverne la
    # dilution, et il change à chaque amélioration de l'imputation (47,6 % avec la loi
    # de zone seule, 50,2 % après le raking sur la taille du ticket 019). On le mesure
    # donc au lieu de le figer dans un commentaire qui se périmerait en silence.
    agreement: list[float] = []
    # La loi d'habitat est servie par (zone, **taille du ménage**) depuis le ticket 019 :
    # on impute donc ici avec la taille réelle de chaque ménage enquêté, exactement comme
    # `enrich_housing_type` le fera sur la population. Mesurer la dilution avec une autre
    # loi que celle réellement appliquée donnerait une cible fausse.
    sizes = men["size"].tolist()
    for seed in range(draws):
        # Tirage indépendant de celui de la production (sel distinct via l'offset) :
        # on cherche l'espérance du croisement, pas la réalisation d'un fichier donné.
        rng = np.random.default_rng(seed)
        uniforms = rng.random(len(men))
        imputed = [draw(table.shares_for(zf, size), u)
                   for zf, size, u in zip(men["ZFM"], sizes, uniforms)]
        series = pd.Series(imputed, index=men.index)
        agreement.append(float((series.values == men["housing"].values).mean()))
        for key in MODALITY_KEYS:
            mask = (series == key).values
            if not mask.any():
                continue
            accumulated[key].append(
                float(100 * weight[mask & (men["k_raw"].values > 0)].sum()
                      / weight[mask].sum()))
            denominator = float((weight[mask] * sizes_arr[mask]).sum())
            if denominator > 0:
                accumulated_holders[key].append(
                    float(100 * (weight[mask] * attributable[mask]).sum() / denominator))

    observed = {str(h): round(_share(f, f["k_raw"] > 0), 2)
                for h, f in men.groupby("housing")}
    return {
        "note": "Cible opposable à une population synthétique. L'habitat du persona "
                "étant lui-même IMPUTÉ, le croisement est dilué : même avec le k VRAI "
                "de l'enquête, l'amplitude tombe sous celle de la courbe publiée. "
                "Comparer la population à la courbe PUBLIÉE reviendrait à exiger du "
                "modèle qu'il sur-corrige pour compenser le bruit de l'axe de mesure. "
                "La dilution est RECALCULÉE à chaque export avec la loi d'habitat du "
                "moment : elle se resserre à mesure que cette imputation s'améliore "
                "(ticket 019).",
        "imputed_vs_observed_agreement_pct": (
            round(float(np.mean(agreement)) * 100, 1) if agreement else None),
        "draws": draws,
        "published_on_observed_housing": observed,
        # Part de MÉNAGES équipés, à comparer à la courbe publiée (même unité).
        "attainable_households_equipped_pct": {
            key: round(float(np.mean(values)), 2)
            for key, values in accumulated.items() if values
        },
        # Part de PERSONNES dotées : c'est CELLE-CI que le rapport d'enrichissement
        # oppose à la population, parce que le trait `personal_bike` est individuel.
        "attainable_on_imputed_housing": {
            key: round(float(np.mean(values)), 2)
            for key, values in accumulated_holders.items() if values
        },
        "unit": "attainable_on_imputed_housing = part de PERSONNES dotées d'un vélo "
                "(min(min(k, K_MAX), éligibles) / taille). La courbe publiée et "
                "`attainable_households_equipped_pct` sont, elles, des parts de "
                "MÉNAGES équipés : ne pas comparer les deux unités.",
        # Amplitude en part de MÉNAGES, donc directement comparable aux 33,4 pts publiés.
        "attainable_spread_pts": round(float(
            np.mean(accumulated["individuel_isole"])
            - np.mean(accumulated["grand_habitat_collectif"])), 2)
        if accumulated["individuel_isole"] and accumulated["grand_habitat_collectif"]
        else None,
    }


def practice_validation(people: pd.DataFrame, oof: np.ndarray) -> dict:
    """La table `P(pratique | k, taille)`, observée et prédite hors échantillon."""
    cells = []
    k = people["k_raw"].clip(upper=K_MAX)
    size = people["size"].clip(upper=SIZE_MAX)
    for stock in range(1, K_MAX + 1):
        for members in range(1, SIZE_MAX + 1):
            mask = (k == stock) & (size == members)
            frame = people[mask]
            if frame.empty:
                continue
            weight = frame["weight"]
            cells.append({
                "k": stock,
                "size": members,
                "n": int(len(frame)),
                "weighted_n": round(float(weight.sum()), 1),
                "practice_pct_observed": round(
                    float(100 * (weight * frame["practises"]).sum() / weight.sum()), 2),
                "practice_pct_predicted": round(
                    float(100 * (weight * oof[mask.values]).sum() / weight.sum()), 2),
                "thin": bool(weight.sum() < THIN_CELL),
            })
    overall = people["weight"]
    return {
        "overall_practice_pct_observed": round(
            float(100 * (overall * people["practises"]).sum() / overall.sum()), 2),
        "overall_practice_pct_predicted": round(
            float(100 * (overall * oof).sum() / overall.sum()), 2),
        "by_k_and_size": cells,
    }


def holder_targets(men: pd.DataFrame, people: pd.DataFrame) -> dict:
    """Les cibles au niveau **personne** : porteurs, gradient de taille, pratiquants/vélo.

    « Personnes dotées d'un vélo » est calculé à l'identique de ce que produira le
    mécanisme — `min(k, taille)` vélos attribués par ménage, pondération `COE0` — pour
    que la comparaison porte sur la même grandeur.

    La part de personnes **vivant dans** un ménage équipé (63,2 % en `COEP`) est écrite
    à côté : c'est la définition sur laquelle la politique de choix modal a été
    entraînée, et l'écart avec ~51 % est précisément la contrainte du consommateur que
    le lot 3 doit résoudre.
    """
    weight, k, size = men["weight"], men["k_raw"], men["size"]
    eligible = men["n_eligible"]
    # Deux définitions, et il faut les deux.
    #
    # `holders_pct` est le chiffre PUBLIÉ du ticket (50,9 %) : `min(k, taille)` sur le
    # `k` brut, sans écrêtage ni condition d'âge.
    #
    # `holders_pct_mechanism` est la même grandeur calculée **sous les règles que le
    # mécanisme obéit réellement** : `k` écrêté à `K_MAX`, et attribution bornée par les
    # membres de 5 ans et plus (`min(k, éligibles)`), puisqu'un vélo sans titulaire
    # n'apparaît pas dans le JSON. C'est celle-là qui est opposable à une population : le
    # chiffre publié demanderait au mécanisme de produire des porteurs qu'il refuse
    # délibérément de produire — des enfants de trois ans à vélo.
    #
    # L'écart est négligeable en agrégat (~0,7 point) et considérable sur les grands
    # ménages, où les jeunes enfants sont nombreux et le stock dépasse l'écrêtage : à
    # taille 5, 59,7 % en publié contre ~52 % sous les règles du mécanisme.
    attributable = np.minimum(k.clip(upper=K_MAX), eligible)
    holders = (weight * np.minimum(k, size)).sum() / (weight * size).sum()
    holders_mech = (weight * attributable).sum() / (weight * size).sum()
    by_size = []
    for value, frame in men.groupby(size.clip(upper=SIZE_BUCKET_MAX)):
        w, kk, ss = frame["weight"], frame["k_raw"], frame["size"]
        att = np.minimum(kk.clip(upper=K_MAX), frame["n_eligible"])
        by_size.append({
            "size": int(value),
            "n": int(len(frame)),
            "weighted_n": round(float(w.sum()), 1),
            "holders_pct": round(float(100 * (w * np.minimum(kk, ss)).sum()
                                       / (w * ss).sum()), 2),
            "holders_pct_mechanism": round(float(100 * (w * att).sum()
                                                 / (w * ss).sum()), 2),
            "thin": bool(w.sum() < THIN_CELL),
        })

    # Pratiquants par ménage et par vélo, numérateur COEP sur enquêtés, dénominateur
    # COE0 sur ménages — deux pondérations, comme le veut le contrôle du ticket.
    practising = (people.assign(_p=people["weight"] * people["practises"])
                  .groupby("hh_id")["_p"].sum())
    eligible_5p = men["n_eligible"]
    hh_id = men["ZFM"].astype(str) + "|" + men["ECH"].astype(str)
    men_practising = hh_id.map(practising).fillna(0.0)
    per_bike = []
    for stock in range(1, K_MAX + 1):
        mask = k.clip(upper=K_MAX) == stock
        frame_weight = weight[mask]
        if frame_weight.sum() <= 0:
            continue
        per_bike.append({
            "k": stock,
            "n": int(mask.sum()),
            "persons_5plus_per_household": round(
                float((frame_weight * eligible_5p[mask]).sum() / frame_weight.sum()), 2),
            "practising_per_household": round(
                float(men_practising[mask].sum() / frame_weight.sum()), 2),
            "practising_per_bike": round(
                float(men_practising[mask].sum() / (frame_weight * stock).sum()), 2),
        })

    person_weight = people["weight"]
    return {
        "holders_pct": round(float(100 * holders), 2),
        "holders_definition": "Σ w·min(k, taille) / Σ w·taille, pondération COE0 — le "
                              "chiffre publié du ticket (50,9 %)",
        "holders_pct_mechanism": round(float(100 * holders_mech), 2),
        "holders_mechanism_definition": "Σ w·min(min(k, K_MAX), éligibles 5+) / Σ w·"
                                        "taille — la même grandeur sous les règles que "
                                        "le mécanisme obéit (écrêtage de k, pas de vélo "
                                        "sous 5 ans). C'est la cible OPPOSABLE.",
        "living_in_equipped_household_pct": round(float(
            100 * person_weight[people["k_raw"] > 0].sum() / person_weight.sum()), 2),
        "living_in_equipped_definition": "part de personnes dans un ménage à k > 0, "
                                         "pondération COEP — la définition sur laquelle "
                                         "la politique de choix modal a été entraînée "
                                         "(has_bike = M21 > 0)",
        "holders_by_household_size": by_size,
        "practising_per_bike": per_bike,
        "vae_share_of_fleet_pct": round(float(
            100 * (weight * men["n_vae"].fillna(0)).sum()
            / (weight * k).sum()), 2),
        "households_with_at_least_one_vae_pct": round(
            _share(men, men["n_vae"].fillna(0) > 0), 2),
    }


def mechanism_check(men: pd.DataFrame, people: pd.DataFrame,
                    occupations: tuple[str, ...], median_density: float,
                    propensity_doc: dict) -> dict:
    """Le mécanisme d'attribution rejoué **sur les ménages de l'enquête**.

    C'est le contrôle qui vaut : `k`, la taille et `P20` y sont tous connus, donc on
    peut vérifier que le tirage sans remise pondéré reproduit la table
    `P(pratique | k, taille)` — dont le module rappelle qu'elle n'est pas une identité
    du schéma d'Efraimidis–Spirakis mais un critère à vérifier après coup.

    Ce même rejeu produit l'indicateur `has_bike` **construit** que le lot 3 doit
    substituer à `M21 > 0` pour ré-entraîner la politique de choix modal : sans lui, la
    politique consomme « il y a un vélo dans le foyer » (63,2 % des personnes) là où le
    persona porte une attribution nominative (~51 %), et le coefficient appris
    s'applique à autre chose que ce qu'il mesure.
    """
    from llm_module.core.bike_ownership import LogitModel

    model = LogitModel.from_doc(propensity_doc)
    columns = list(propensity_doc["features"])
    rows = propensity_matrix(people, occupations, median_density)
    people = people.assign(_p=[model.probability(dict(zip(columns, row)))
                               for row in rows.to_numpy()])

    held: dict[int, bool] = {}
    for hh_id, frame in people.groupby("hh_id"):
        stock = int(frame["k_raw"].iloc[0])
        nominal = int(frame["size"].iloc[0])
        present = [Member(index=int(i), propensity=float(p),
                          eligible=bool(a >= MIN_AGE_ELIGIBLE))
                   for i, p, a in zip(frame.index, frame["_p"], frame["age"])]
        # Places absentes : le ménage nominal compte `size` personnes, l'enquête n'en
        # décrit qu'une partie (67 % des ménages n'ont qu'un enquêté). Sans elles, les
        # k vélos se concentreraient sur les seuls répondants et on les sur-équiperait —
        # exactement le biais des ménages partiellement présents côté population.
        mean_p = float(np.mean([m.propensity for m in present])) if present else 0.0
        absent = [Member(index=-1 - j, propensity=mean_p, eligible=True)
                  for j in range(max(0, nominal - len(frame)))]
        chosen = assign(present + absent, stock, hh_id)
        for member in present:
            held[member.index] = member.index in chosen

    people = people.assign(_held=[held.get(i, False) for i in people.index])
    weight = people["weight"]
    cells = []
    k = people["k_raw"].clip(upper=K_MAX)
    size = people["size"].clip(upper=SIZE_MAX)
    for stock in range(1, K_MAX + 1):
        for members in range(1, SIZE_MAX + 1):
            mask = (k == stock) & (size == members)
            frame = people[mask]
            if frame.empty:
                continue
            w = frame["weight"]
            cells.append({
                "k": stock, "size": members, "n": int(len(frame)),
                "practice_pct_observed": round(
                    float(100 * (w * frame["practises"]).sum() / w.sum()), 2),
                "held_pct_mechanism": round(
                    float(100 * (w * frame["_held"]).sum() / w.sum()), 2),
                "thin": bool(w.sum() < THIN_CELL),
            })
    held_pct = float(100 * (weight * people["_held"]).sum() / weight.sum())
    practice_pct = float(100 * (weight * people["practises"]).sum() / weight.sum())
    # Part des porteurs trop jeunes pour un VAE. C'est elle qui renormalise l'étage 3 :
    # sans elle, appliquer 7,67 % aux seuls 14 ans et plus fait sortir le parc sous la
    # cible, à proportion des vélos tenus par des enfants (cf. `electric_probability`).
    held_weight = (weight * people["_held"]).sum()
    under_age = float(
        (weight * (people["_held"] & (people["age"] < MIN_AGE_ELECTRIC))).sum()
        / held_weight) if held_weight > 0 else 0.0
    return {
        "note": "Attribution rejouée sur les ménages de l'enquête (k, taille et P20 "
                "connus). `held_pct_mechanism` est l'indicateur has_bike CONSTRUIT sur "
                "lequel la politique de choix modal doit être ré-entraînée, à la place "
                "de M21 > 0.",
        "constructed_has_bike_pct": round(held_pct, 2),
        "practice_pct": round(practice_pct, 2),
        # Deux grandeurs distinctes, à ne pas confondre — le ticket cite la seconde.
        #
        # `dormant_gross` : la part de la population qui tient un vélo SANS le
        # pratiquer. C'est la masse dormante au sens propre, celle qu'on représente
        # exprès parce qu'un vélo au garage est un vélo.
        #
        # `dormant_net` : l'écart porteurs − pratiquants. Il est plus petit, parce
        # qu'il y a AUSSI des pratiquants sans vélo attribué : les usagers du libre-
        # service (hors périmètre du ticket) et les 7,9 % de pratiquants vivant dans un
        # ménage à zéro vélo. Le flux joue donc dans les deux sens, et seul le net se
        # lit sur les deux totaux.
        "dormant_gross_pts": round(float(
            100 * (weight * (people["_held"] & ~people["practises"])).sum()
            / weight.sum()), 2),
        "dormant_net_pts": round(held_pct - practice_pct, 2),
        "practising_without_bike_pts": round(float(
            100 * (weight * (~people["_held"] & people["practises"])).sum()
            / weight.sum()), 2),
        "under_age_holder_share": round(under_age, 6),
        "by_k_and_size": cells,
    }


# ── Sortie ───────────────────────────────────────────────────────────────────

def report(doc: dict) -> None:
    stock = doc["validation"]["stock"]
    print("\n── Étage 1 : combien de vélos dans le ménage "
          "(hors-échantillon) ────────────")
    over = stock["overall"]
    print(f"  ménages équipés  observé {over['equipped_pct_observed']:5.1f} %  "
          f"prédit {over['equipped_pct_predicted']:5.1f} %")
    print(f"  vélos par ménage observé {over['bikes_per_household_observed']:5.2f}    "
          f"prédit {over['bikes_per_household_predicted']:5.2f}")
    clip = stock["clipping_cost"]
    print(f"  [écrêtage {clip['k_max']}+] stock publié "
          f"{clip['bikes_per_household_unclipped']:.3f} → cible opposable "
          f"{clip['bikes_per_household_clipped']:.3f} ; mais vélos ATTRIBUABLES "
          f"{clip['attributable_per_household_unclipped']:.3f} → "
          f"{clip['attributable_per_household_clipped']:.3f} "
          f"({clip['households_losing_an_attributable_bike_pct']:.2f} % des ménages "
          f"perdent un vélo portable)")
    print(f"  {'taille':>8} {'observé':>9} {'prédit':>9} {'écart':>7}   n")
    for row in stock["by_household_size"]:
        print(f"  {row['size']:>8} {row['equipped_pct_observed']:8.1f}% "
              f"{row['equipped_pct_predicted']:8.1f}% "
              f"{row['equipped_pct_predicted'] - row['equipped_pct_observed']:+7.1f}"
              f"   {row['n']}{'  [cellule mince]' if row['thin'] else ''}")
    print(f"  {'habitat (observé, hors modèle)':>30} {'observé':>9} {'prédit':>9}")
    for row in stock["by_housing_observed"]:
        print(f"  {row['housing']:>30} {row['equipped_pct_observed']:8.1f}% "
              f"{row['equipped_pct_predicted']:8.1f}%"
              f"{'  [cellule mince]' if row['thin'] else ''}")

    diluted = doc["validation"].get("housing_reference") or {}
    if diluted.get("attainable_on_imputed_housing"):
        print("\n── Habitat : la cible opposable, et pourquoi elle n'est pas la publiée ──")
        print(f"  {'modalité':>30} {'publiée':>9} {'ménages':>10} {'personnes':>11}")
        print(f"  {'(unité)':>30} {'ménages':>9} {'ménages':>10} {'personnes':>11}")
        households = diluted.get("attainable_households_equipped_pct") or {}
        for key, value in diluted["attainable_on_imputed_housing"].items():
            published = diluted["published_on_observed_housing"].get(key)
            shown = f"{published:8.1f}%" if published is not None else f"{'—':>9}"
            hh = households.get(key)
            hh_shown = f"{hh:9.1f}%" if hh is not None else f"{'—':>10}"
            print(f"  {key:>30} {shown} {hh_shown} {value:10.1f}%")
        print("  La colonne « personnes » est la cible opposée à la population : le trait\n"
              "  `personal_bike` est individuel. L'écart entre les deux dernières colonnes\n"
              "  suit la taille du ménage — un foyer de quatre à un vélo est « équipé »,\n"
              "  mais un seul de ses membres est doté.")
        published = diluted["published_on_observed_housing"]
        published_spread = (published["individuel_isole"]
                            - published["grand_habitat_collectif"])
        accord = diluted.get("imputed_vs_observed_agreement_pct")
        print(f"  amplitude atteignable isolé − grand collectif : "
              f"{diluted['attainable_spread_pts']:.1f} pts, contre "
              f"{published_spread:.1f} pts publiés")
        print(f"  L'écart EST la dilution de l'habitat imputé"
              + (f" (accord imputé/observé : {accord:.1f} %)" if accord else "")
              + " : il se resorbe\n  à mesure que cette imputation gagne en précision "
                "(ticket 019). Rien à corriger côté vélo.")

    practice = doc["validation"]["practice"]
    print("\n── Étage 2 : P(pratique | k, taille) — observé / prédit "
          "hors-échantillon ──")
    print(f"  pratiquants  observé {practice['overall_practice_pct_observed']:5.2f} %  "
          f"prédit {practice['overall_practice_pct_predicted']:5.2f} %")
    for stock_value in range(1, K_MAX + 1):
        cells = [c for c in practice["by_k_and_size"] if c["k"] == stock_value]
        line = "  ".join(
            f"{c['practice_pct_observed']:5.1f}/{c['practice_pct_predicted']:5.1f}"
            f"{'!' if c['thin'] else ' '}(n={c['n']:4d})" for c in cells)
        print(f"  k={stock_value}  {line}")

    mech = doc["validation"]["mechanism"]
    print("\n── Attribution rejouée sur l'enquête ───────────────────────────────────")
    print(f"  has_bike construit : {mech['constructed_has_bike_pct']:5.2f} %   "
          f"pratiquants : {mech['practice_pct']:5.2f} %")
    print(f"  vélos dormants : {mech['dormant_gross_pts']:5.2f} pts en brut "
          f"(tiennent un vélo sans le pratiquer), {mech['dormant_net_pts']:5.2f} pts en "
          f"net — l'écart\n    est comblé par les "
          f"{mech['practising_without_bike_pts']:.2f} pts qui pratiquent SANS vélo "
          f"attribué (libre-service,\n    ménages à zéro vélo) : le flux joue dans les "
          f"deux sens. Le ticket cite le net.")
    print("  (c'est `constructed_has_bike_pct` que la politique de choix modal doit "
          "apprendre,\n   et non les "
          f"{doc['validation']['targets']['living_in_equipped_household_pct']:.1f} % de "
          "personnes vivant dans un ménage équipé)")

    targets = doc["validation"]["targets"]
    print("\n── Cibles au niveau personne (critères d'acceptation) ──────────────────")
    print(f"  personnes dotées d'un vélo : {targets['holders_pct']:.2f} %")
    print("  gradient de taille : " + " / ".join(
        f"{row['holders_pct']:.1f}" for row in targets["holders_by_household_size"]))
    print("  pratiquants par vélo : " + " / ".join(
        f"{row['practising_per_bike']:.2f}" for row in targets["practising_per_bike"]))
    print(f"  part de VAE dans le parc : {targets['vae_share_of_fleet_pct']:.2f} % "
          f"(constante du module : {100 * VAE_SHARE:.2f} %)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None,
                        help=f"Fichier de sortie (défaut : {DEFAULT_RESOURCE})")
    args = parser.parse_args()

    root = find_project_root()
    men, people = load_frames(root)

    # Médiane de la densité, servie dans la ressource : c'est ce que le module
    # substituera aux 81 zones fines sans ménage enquêté. Pas zéro, qui décrirait un
    # désert là où l'information est simplement absente.
    median_density = float(men["density"].median())
    occupations = tuple(sorted(set(MAIN_OCCUPATION.values())))

    stock_doc, stock_oof = fit_stock(men, median_density)
    propensity_doc, propensity_oof = fit_propensity(people, occupations, median_density)
    # Le rejeu de l'attribution sert deux fois : il valide le mécanisme ET il mesure la
    # part de porteurs trop jeunes pour un VAE, qui renormalise l'étage 3.
    mechanism = mechanism_check(men, people, occupations, median_density, propensity_doc)

    doc = {
        "version": 1,
        "trait": "personal_bike",
        "stock": stock_doc,
        "propensity": propensity_doc,
        "occupations": list(occupations),
        "median_density": round(median_density, 6),
        "vae_share_of_fleet": VAE_SHARE,
        "under_age_holder_share": mechanism["under_age_holder_share"],
        "validation": {
            "stock": stock_validation(men, stock_oof),
            "housing_reference": diluted_housing_reference(men, root),
            "practice": practice_validation(people, propensity_oof),
            "mechanism": mechanism,
            "targets": holder_targets(men, people),
            "thin_cell_weighted_n": THIN_CELL,
        },
        "meta": {
            "source": "EMC² Toulouse 2023 (ProGEDO lil-1750) — fichiers standards "
                      "ménages (M21, M1, M6, COE0) et personnes (P20, P4, P2, P9, "
                      "COEP), fichier original (ML21, vélos à assistance électrique, "
                      "absent du standard où M22 est vide)",
            "stage1_covariates": "taille du ménage, nombre de VP (M6), densité de "
                                 "ménages et distance à l'hypercentre de la zone fine. "
                                 "NI l'habitat (M1) — moins informatif que la zone dont "
                                 "il est imputé côté persona — NI l'occupation du "
                                 "logement (M2), que le persona ne porte pas.",
            "stage2_covariates": "k, taille du ménage, âge, genre, occupation, densité "
                                 "et distance au centre. AUCUNE distance de "
                                 "déplacement : un stock doit être invariant au trajet.",
            "eligibility": f"membres de {MIN_AGE_ELIGIBLE} ans et plus (champ de la "
                           f"question P20) ; VAE à partir de {14} ans",
            "out_of_scope": "vélo en libre-service (MODP ∈ {10, 18}, 7 % des trajets "
                            "vélo) ; stationnement (M23, P18A manquant à 65 %) ; "
                            "week-end — P20 ne porte que du lundi au vendredi, un "
                            "cycliste de loisir dominical est vu « Jamais » et "
                            "l'attribution le sous-estime sans qu'on puisse mesurer de "
                            "combien",
            "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    }

    report(doc)
    out = args.out or DEFAULT_RESOURCE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n→ {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
