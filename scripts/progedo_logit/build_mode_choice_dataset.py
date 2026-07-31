"""build_mode_choice_dataset.py — Jeu d'entraînement de la politique de choix modal.

Construit, depuis l'enquête EMC² Toulouse 2023 (ProGEDO / lil-1750), le dataset qui
servira à entraîner la politique statistique servie en simulation (ticket 005, phase 1).

Ce script **remplace** `prepare_progedo_logit.ipynb` pour tout usage d'entraînement.
Trois différences de fond avec le notebook :

1. **La distance.** Le notebook exporte `distance_km = D12/1000`. Cette variable est
   contaminée : pour la marche, D11 vaut exactement `durée déclarée × 58 m/min` et D12
   est la distance sur le réseau *du mode utilisé* — connaître la distance, c'est déjà
   connaître le mode (PR-AUC 0.985 contre 0.804 avec une distance mode-neutre, cf.
   `explore_progedo_walk_shapley.ipynb` §7). Et au moment de la décision en simulation,
   il n'existe pas de « distance du trajet » : il existe k options OTP ayant chacune la
   sienne. On utilise donc `od_km`, distance entre centroïdes de zones fines, mode-neutre
   et calculable des deux côtés.

2. **La pondération.** L'objectif est de reproduire des *parts modales* : un entraînement
   non pondéré les biaise. `COEP` (coefficient de redressement de la personne enquêtée)
   est exporté comme `sample_weight`.

3. **Le contrat de features.** Une variable n'entre dans le dataset que si elle est
   calculable à l'instant de la décision en simulation, depuis le persona
   (`traits_json`), le contexte de l'activité, ou la géométrie. `feature_spec.json`
   fige la liste, les types et les modalités : il est relu à l'entraînement et au
   runtime, et toute divergence lève une erreur au lieu de produire silencieusement des
   prédictions fausses.

**Domaine de validité** : l'enquête ne porte que sur des jours ouvrés (`JOUR ∈ 1..5`).
La politique entraînée ici est un modèle *de semaine* ; l'appliquer au samedi ou au
dimanche est une extrapolation hors domaine. C'est déclaré dans `feature_spec.json`
(`domain.weekday_only`) pour que le runtime puisse s'en défendre.

Usage :
    python scripts/progedo_logit/build_mode_choice_dataset.py [--out-dir DIR]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

# --- Version du contrat de features -----------------------------------------
# À incrémenter à chaque changement de la liste, de l'ordre ou du typage des
# features. Le runtime refuse de charger un modèle dont la version diffère.
SPEC_VERSION = 1

TEST_SIZE = 0.25
SPLIT_SEED = 0


# ---------------------------------------------------------------------------
# Dictionnaires de recodage (ProGEDO → espace de valeurs du projet)
# ---------------------------------------------------------------------------
# Les libellés viennent de `lil-1750-Documentation/LABELS/`. Les valeurs cibles
# sont celles observées dans `traits_json` de `data/population/*.json` : c'est ce
# qui rend l'enquête et la population synthétique comparables.

GENDER = {"1": "Male", "2": "Female"}

MAIN_OCCUPATION = {
    "1": "Travail à plein temps",
    "2": "Travail à temps partiel",
    "3": "Étudiant",  # alternance / stage
    "4": "Étudiant",
    "5": "Scolaire (jusqu'au Bac)",
    "6": "Chômeur/recherche d'emploi",
    "7": "Retraité",
    "8": "Personne au foyer",
    "9": "Autre",
}
EMPLOYED_CODES = {"1", "2"}
STUDIES_CODES = {"3", "4", "5"}

SOCIOPRO = {
    "01": "Farmer",
    "02": "Craftsperson or Shop Owner",
    "03": "Executive or Higher Intellectual Professional",
    "04": "Intermediate Professional",
    "05": "Employee",
    "06": "Manual Worker",
    "07": "Student",
    "08": "Other Inactive",
    "09": "Other Inactive",
}

# MODP → cible {car, bike, walk, transit}.
# Micro-mobilité active (roller/trottinette/fauteuil) rattachée à walk ; deux-roues
# motorisés, taxi/VTC et fourgon à car ; avion/fluvial/engins agricoles hors champ.
#
# Limite structurelle assumée : `train` et `motorbike`, qui existent côté simulation
# dans CANONICAL_MODES, sont ici fusionnés dans transit et car. La politique ne pourra
# jamais les distinguer (cf. ticket 005 §4).
MODE_GROUP = {
    "01": "walk", "93": "walk", "94": "walk", "96": "walk", "97": "walk",
    "10": "bike", "11": "bike", "12": "bike", "17": "bike", "18": "bike",
    "21": "car", "22": "car", "61": "car", "62": "car", "81": "car", "82": "car",
    "13": "car", "14": "car", "15": "car", "16": "car", "19": "car", "20": "car",
    "31": "transit", "32": "transit", "33": "transit", "34": "transit",
    "37": "transit", "38": "transit", "39": "transit",
    "41": "transit", "42": "transit", "43": "transit",
    "51": "transit", "52": "transit", "53": "transit", "54": "transit",
    "71": "transit",
}

TARGET_CLASSES = ["bike", "car", "transit", "walk"]


def purpose_from_code(code: str) -> str:
    """Motif ProGEDO (D5A destination / D2A origine) → purpose du projet."""
    if code in ("01", "02"):
        return "home"
    if code in ("11", "12", "13", "14", "81"):
        return "work"
    if code in ("21", "22", "23", "24", "25", "26", "27", "28", "29", "96", "97"):
        return "education"
    if code in ("30", "31", "32", "33", "34", "35", "82", "98"):
        return "shop"
    if code in ("51", "52", "53", "54"):
        return "leisure"
    return "other"


# ---------------------------------------------------------------------------
# Définition des features — le contrat
# ---------------------------------------------------------------------------
# `source` documente d'où la valeur viendra en simulation. C'est le critère
# d'admission : sans source runtime, la variable est exclue quel que soit son
# pouvoir prédictif.

FEATURE_SPEC: list[dict] = [
    # --- persona (traits_json) ---
    {"name": "age", "kind": "numeric", "source": "persona"},
    {"name": "gender", "kind": "categorical", "source": "persona"},
    {"name": "household_size", "kind": "numeric", "source": "persona"},
    {"name": "has_driving_license", "kind": "bool", "source": "persona"},
    {"name": "has_pt_subscription", "kind": "bool", "source": "persona"},
    {"name": "number_of_cars", "kind": "numeric", "source": "persona"},
    {"name": "car_availability", "kind": "categorical", "source": "persona"},
    {"name": "has_bike", "kind": "bool", "source": "persona"},
    {"name": "socioprofessional_class", "kind": "categorical", "source": "persona"},
    {"name": "main_occupation", "kind": "categorical", "source": "persona"},
    {"name": "employed", "kind": "bool", "source": "persona"},
    {"name": "studies", "kind": "bool", "source": "persona"},
    # --- contexte de l'activité ---
    {"name": "purpose", "kind": "categorical", "source": "context"},
    {"name": "purpose_origin", "kind": "categorical", "source": "context"},
    {"name": "departure_hour", "kind": "numeric", "source": "context"},
    # --- géométrie ---
    {"name": "od_km", "kind": "numeric", "source": "geo"},
    {"name": "same_zone", "kind": "bool", "source": "geo"},
    {"name": "dist_center_orig_km", "kind": "numeric", "source": "geo"},
    {"name": "dist_center_dest_km", "kind": "numeric", "source": "geo"},
    {"name": "density_orig", "kind": "numeric", "source": "geo"},
    {"name": "density_dest", "kind": "numeric", "source": "geo"},
]

FEATURES = [f["name"] for f in FEATURE_SPEC]

# Variables conservées dans le parquet pour diagnostic mais **interdites au modèle**.
DIAGNOSTIC_ONLY = ["distance_km", "crow_km", "duration_min"]

# Traçabilité (hors modèle).
KEYS = ["ZF", "ECH", "PER", "NDEP", "hh_id"]

# Features sans lesquelles une ligne n'est pas exploitable.
CRITICAL = [
    "age", "gender", "has_pt_subscription", "socioprofessional_class",
    "main_occupation", "car_availability", "number_of_cars", "od_km",
]


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def find_project_root() -> Path:
    root = Path(__file__).resolve()
    while not (root / "data" / "PROGEDO 2023").exists() and root != root.parent:
        root = root.parent
    if not (root / "data" / "PROGEDO 2023").exists():
        raise SystemExit("Racine du projet introuvable (dossier 'data/PROGEDO 2023').")
    return root


def load_raw(progedo_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Charge les trois fichiers standards, tout en str.

    Les codes ProGEDO ont des zéros de tête significatifs ('01' ≠ '1') et des cellules
    vides qui portent du sens (non-enquêté) : un parsing numérique automatique les
    détruirait. Le recodage est explicite plus bas.
    """
    frames = []
    for name in ("pers", "men", "depl"):
        df = pd.read_csv(progedo_dir / f"Toulouse_2023_std_{name}.csv", dtype=str)
        for c in df.columns:
            df[c] = df[c].str.strip().replace({"": np.nan})
        frames.append(df)
    pers, men, depl = frames
    print(f"pers: {pers.shape} | men: {men.shape} | depl: {depl.shape}")
    return pers, men, depl


def build_geo(sig_zf: Path, men: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Couches géographiques par zone fine : densité, distance à l'hypercentre, centroïde.

    Renvoie (GEO, XYS, REF) — GEO porte les features dérivées, XYS les coordonnées
    Lambert 93 et la surface nécessaires au calcul de `od_km`, REF la référence
    géographique à publier dans le spec pour que le runtime calcule à l'identique.
    """
    # Le CRS est capturé avant le sous-ensemble de colonnes : sans la géométrie,
    # le GeoDataFrame retombe en DataFrame et perd `.crs`.
    layer = gpd.read_file(sig_zf)
    crs = layer.crs
    zf = layer[["ZF", "XL93", "YL93", "SURF_M2"]].copy()
    zf["ZF"] = zf["ZF"].astype(str).str.strip()

    # Densité de ménages estimée depuis les coefficients de redressement du ménage.
    weights = men.assign(COE0=pd.to_numeric(men["COE0"], errors="coerce")).groupby("ZFM")["COE0"].sum()
    zf["area_km2"] = zf["SURF_M2"] / 1e6
    zf["density_hh_km2"] = zf["ZF"].map(weights) / zf["area_km2"]

    # Hypercentre = centroïde des zones fines du secteur 01 (Capitole).
    core = zf[zf["ZF"].str.startswith("1011")]
    cx, cy = core["XL93"].mean(), core["YL93"].mean()
    zf["dist_center_km"] = np.hypot(zf["XL93"] - cx, zf["YL93"] - cy) / 1000

    # Publié dans le spec : le runtime doit utiliser CE centre, et non la constante
    # codée en dur dans `move_logger.py` (43.6047 / 1.4442), dont il est distant de
    # ~820 m. Deux définitions concurrentes du centre décaleraient dist_center_*.
    center_wgs84 = (
        gpd.GeoSeries(gpd.points_from_xy([cx], [cy]), crs=crs)
        .to_crs("EPSG:4326")
    )
    ref = {
        "crs": crs.to_string(),
        "zf_layer": sig_zf.name,
        "n_zones": int(len(zf)),
        "hypercenter": {
            "definition": "centroïde des zones fines du secteur 01 (Capitole)",
            "x_l93": round(float(cx), 1),
            "y_l93": round(float(cy), 1),
            "lat": round(float(center_wgs84.y.iloc[0]), 6),
            "lon": round(float(center_wgs84.x.iloc[0]), 6),
        },
        # Formule de od_km à répliquer exactement au runtime : une distance calculée
        # sur les coordonnées exactes plutôt que sur les centroïdes donne un facteur 2
        # sur les trajets intra-zone (cf. ticket 005 §2.1).
        "od_km": {
            "inter_zone": "distance entre centroïdes de zones fines (L93), en km",
            "intra_zone": "0.5 * sqrt(SURF_M2) / 1000",
        },
    }
    print(f"Hypercentre : L93 X={cx:.0f} Y={cy:.0f} "
          f"| WGS84 lat={ref['hypercenter']['lat']:.4f} lon={ref['hypercenter']['lon']:.4f}")

    geo = zf.set_index("ZF")[["density_hh_km2", "dist_center_km"]]
    xys = zf.set_index("ZF")[["XL93", "YL93", "SURF_M2"]]
    return geo, xys, ref


def build_household(men: pd.DataFrame) -> pd.DataFrame:
    """Équipement du foyer. Clé ménage réelle = (ZFM, ECH) — ECH seul n'est pas unique."""
    out = pd.DataFrame({
        "ZF": men["ZFM"],
        "ECH": men["ECH"],
        "number_of_cars": pd.to_numeric(men["M6"], errors="coerce"),
        "n_bikes": pd.to_numeric(men["M21"], errors="coerce"),
    })
    # M22 (vélos à assistance électrique) n'est pas renseigné dans ce jeu : impossible
    # de distinguer le VAE, `personal_bike` du persona se réduit donc à un booléen.
    out["has_bike"] = out["n_bikes"].fillna(0) > 0
    return out.drop_duplicates(["ZF", "ECH"]).drop(columns="n_bikes")


def build_person(pers: pd.DataFrame, household: pd.DataFrame) -> pd.DataFrame:
    """Démographie et équipement individuel. Clé personne = (ZFP, ECH, PER)."""
    hh_size = pers.groupby(["ZFP", "ECH"]).size().rename("household_size").reset_index()
    licensed = (
        pers.assign(_lic=(pers["P7"] == "1"))
        .groupby(["ZFP", "ECH"])["_lic"].sum()
        .rename("n_licensed").reset_index()
    )

    out = pd.DataFrame({
        "ZF": pers["ZFP"],
        "ECH": pers["ECH"],
        "PER": pers["PER"],
        "PENQ": pers["PENQ"],
        "age": pd.to_numeric(pers["P4"], errors="coerce"),
        "gender": pers["P2"].map(GENDER),
        "has_driving_license": pers["P7"] == "1",
        "has_pt_subscription": pers["P12"].map({"4": False, "6": True}),
        "socioprofessional_class": pers["PCSC"].map(SOCIOPRO),
        "main_occupation": pers["P9"].map(MAIN_OCCUPATION),
        "employed": pers["P9"].isin(EMPLOYED_CODES),
        "studies": pers["P9"].isin(STUDIES_CODES),
        # Coefficient de redressement de la personne enquêtée : c'est lui qui porte
        # la représentativité des déplacements (cf. ticket 005, E5).
        "sample_weight": pd.to_numeric(pers["COEP"], errors="coerce"),
    })

    for agg in (hh_size, licensed):
        out = out.merge(
            agg, left_on=["ZF", "ECH"], right_on=["ZFP", "ECH"], how="left"
        ).drop(columns="ZFP")
    out = out.merge(household, on=["ZF", "ECH"], how="left")

    def car_availability(row):
        """Offre de voitures rapportée aux conducteurs du foyer (sémantique du projet)."""
        cars = row["number_of_cars"]
        if pd.isna(cars):
            return np.nan
        if cars == 0:
            return "none"
        lic = row["n_licensed"]
        if pd.isna(lic) or lic == 0:
            return "all"  # voiture disponible, aucune contrainte de conducteur
        return "all" if cars >= lic else "some"

    out["car_availability"] = out.apply(car_availability, axis=1)
    return out.drop(columns="n_licensed")


def build_trips(depl: pd.DataFrame, geo: pd.DataFrame, xys: pd.DataFrame) -> pd.DataFrame:
    """Déplacements enrichis de la géométrie origine-destination."""
    out = pd.DataFrame({
        "ZF": depl["ZFD"],
        "ECH": depl["ECH"],
        "PER": depl["PER"],
        "NDEP": depl["NDEP"],
        "mode": depl["MODP"].map(MODE_GROUP),
        "purpose": depl["D5A"].map(purpose_from_code),
        "purpose_origin": depl["D2A"].map(purpose_from_code),
        "departure_hour": (pd.to_numeric(depl["D4"], errors="coerce") // 100) % 24,
        "ZF_orig": depl["D3"],
        "ZF_dest": depl["D7"],
        # Diagnostic uniquement — contaminées, jamais dans le modèle (ticket 005 §1).
        "distance_km": pd.to_numeric(depl["D12"], errors="coerce") / 1000,
        "crow_km": pd.to_numeric(depl["D11"], errors="coerce") / 1000,
        "duration_min": pd.to_numeric(depl["D9"], errors="coerce"),
    })

    for side in ("orig", "dest"):
        joined = geo.reindex(out[f"ZF_{side}"]).reset_index(drop=True)
        out[f"density_{side}"] = joined["density_hh_km2"].values
        out[f"dist_center_{side}_km"] = joined["dist_center_km"].values

    # Distance OD mode-neutre. Pour un déplacement intra-zone la distance entre
    # centroïdes vaut 0 : on la remplace par une longueur caractéristique de la zone
    # (0.5 × √surface). `same_zone` reste à côté pour que le modèle sache que la
    # valeur est imputée plutôt que mesurée.
    o = xys.reindex(out["ZF_orig"]).reset_index(drop=True)
    d = xys.reindex(out["ZF_dest"]).reset_index(drop=True)
    inter_km = np.hypot(o["XL93"].values - d["XL93"].values,
                        o["YL93"].values - d["YL93"].values) / 1000
    intra = (out["ZF_orig"].values == out["ZF_dest"].values)
    out["od_km"] = np.where(intra, 0.5 * np.sqrt(o["SURF_M2"].values) / 1000, inter_km)
    out["same_zone"] = intra
    return out


def assign_split(df: pd.DataFrame) -> pd.Series:
    """Split train/test **par ménage**.

    Un split par déplacement fuirait : les déplacements d'un même individu partagent
    ses caractéristiques, et ceux d'un même ménage son équipement automobile.
    """
    train_idx, test_idx = next(
        GroupShuffleSplit(n_splits=1, test_size=TEST_SIZE, random_state=SPLIT_SEED)
        .split(df, groups=df["hh_id"])
    )
    split = pd.Series("train", index=df.index, dtype="object")
    split.iloc[test_idx] = "test"
    return split


def build_feature_spec(clean: pd.DataFrame, geo_ref: dict) -> dict:
    """Sérialise le contrat de features, modalités catégorielles comprises.

    Le runtime relit ce fichier : figer les modalités ici, c'est garantir que
    l'encodage d'une catégorie sera identique à l'entraînement et en simulation.
    """
    features = []
    for spec in FEATURE_SPEC:
        entry = dict(spec)
        if spec["kind"] == "categorical":
            entry["categories"] = sorted(clean[spec["name"]].dropna().unique().tolist())
        features.append(entry)

    return {
        "spec_version": SPEC_VERSION,
        "source": "EMC² Toulouse 2023 (ProGEDO / lil-1750)",
        "target": {"name": "mode", "classes": TARGET_CLASSES},
        "sample_weight": "sample_weight",
        "features": features,
        # Référence géographique : le runtime doit reproduire ces définitions à
        # l'identique, sinon les features géo sont décalées (ticket 005 §2.1).
        "geo_reference": geo_ref,
        "diagnostic_only": DIAGNOSTIC_ONLY,
        "split": {"by": "hh_id", "test_size": TEST_SIZE, "seed": SPLIT_SEED},
        "domain": {
            # L'enquête ne couvre que les jours ouvrés (JOUR ∈ 1..5) : appliquer la
            # politique un samedi ou un dimanche est une extrapolation hors domaine.
            "weekday_only": True,
            "city": "Toulouse",
            # od_km n'est calculable que si les deux zones fines sont dans le
            # périmètre d'enquête.
            "requires_survey_perimeter": True,
        },
        "notes": [
            "distance_km/crow_km/duration_min sont contaminées : diagnostic uniquement.",
            "train et motorbike sont fusionnés dans transit et car : la politique ne "
            "peut pas les distinguer.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="Répertoire de sortie (défaut : scripts/progedo_logit/)")
    args = parser.parse_args()

    root = find_project_root()
    progedo_dir = root / "data" / "PROGEDO 2023" / "lil-1750-Donnees_CSV" / "fichiers_standards"
    sig_zf = (root / "data" / "PROGEDO 2023" / "lil-1750-Documentation" / "SIG"
              / "EMC2_Toulouse_2023_ZF_26052023.shp")
    out_dir = args.out_dir or (root / "scripts" / "progedo_logit")
    out_dir.mkdir(parents=True, exist_ok=True)

    pers, men, depl = load_raw(progedo_dir)
    geo, xys, geo_ref = build_geo(sig_zf, men)
    household = build_household(men)
    person = build_person(pers, household)
    trips = build_trips(depl, geo, xys)

    df = trips.merge(person, on=["ZF", "ECH", "PER"], how="left")
    n0 = len(df)

    # --- Filtres, tracés un par un : chacun coûte des lignes, on veut savoir combien.
    steps = []
    df = df[df["mode"].notna()]
    steps.append(("mode exploitable", len(df)))
    df = df[df["PENQ"] == "1"]
    steps.append(("personne enquêtée", len(df)))
    df = df.dropna(subset=CRITICAL)
    steps.append(("features critiques", len(df)))
    df = df[df["sample_weight"].notna()]
    steps.append(("pondération", len(df)))

    print(f"\nLignes : {n0} au départ")
    for label, n in steps:
        print(f"  après {label:22s} : {n}")

    df = df.reset_index(drop=True)
    df["hh_id"] = df["ZF"].astype(str) + "_" + df["ECH"].astype(str)
    df["split"] = assign_split(df)

    clean = df[KEYS + FEATURES + DIAGNOSTIC_ONLY + ["mode", "sample_weight", "split"]].copy()

    # Typage explicite : le parquet doit être relu sans ambiguïté.
    for spec in FEATURE_SPEC:
        col = spec["name"]
        if spec["kind"] == "bool":
            clean[col] = clean[col].astype(bool)
        elif spec["kind"] == "categorical":
            clean[col] = clean[col].astype("category")
    clean["age"] = clean["age"].astype(int)
    for col in ("household_size", "number_of_cars", "departure_hour"):
        clean[col] = clean[col].astype("Int64")

    # --- Contrôles ---------------------------------------------------------
    print("\nParts modales (brutes) :")
    print(clean["mode"].value_counts(normalize=True).round(4).to_string())
    weighted = (clean.groupby("mode", observed=True)["sample_weight"].sum()
                / clean["sample_weight"].sum())
    print("\nParts modales (pondérées COEP) :")
    print(weighted.round(4).to_string())

    missing = clean[FEATURES].isna().sum()
    missing = missing[missing > 0]
    if not missing.empty:
        print("\nValeurs manquantes restantes (LightGBM les gère nativement) :")
        print(missing.to_string())

    print(f"\nSplit : train={(clean['split'] == 'train').sum()} "
          f"test={(clean['split'] == 'test').sum()} "
          f"| ménages={clean['hh_id'].nunique()}")
    overlap = (set(clean.loc[clean['split'] == 'train', 'hh_id'])
               & set(clean.loc[clean['split'] == 'test', 'hh_id']))
    assert not overlap, f"Fuite : {len(overlap)} ménages dans les deux splits"

    # --- Écriture ----------------------------------------------------------
    parquet_path = out_dir / "progedo_mode_choice_v2.parquet"
    spec_path = out_dir / "feature_spec.json"
    clean.to_parquet(parquet_path, index=False)
    spec_path.write_text(
        json.dumps(build_feature_spec(clean, geo_ref), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"\nÉcrits :\n - {parquet_path} ({len(clean)} lignes, {clean.shape[1]} colonnes)"
          f"\n - {spec_path} (spec v{SPEC_VERSION}, {len(FEATURES)} features)")


if __name__ == "__main__":
    main()
