"""export_housing_type.py — Loi du type de logement par zone fine et taille de ménage.

La référence EMC² ventile les parts modales par **type d'habitat**, mais la chaîne de
génération de population ne produit pas ce trait : ni eqasim, ni les tables INSEE
mobilisées par le notebook (zonage AAV, grille de densité) ne portent l'information.
La seule source qui la porte pour le périmètre toulousain est l'enquête elle-même,
variable `M1` du fichier ménages (« Type d'habitat »), dont les modalités sont
exactement celles de la ventilation publiée.

Ce script en extrait la loi nécessaire pour imputer le trait à la génération de
population (action A2, révisée par le **ticket 019**) :

- **loi conditionnelle à la zone fine**, pondérée par les coefficients de redressement
  des **ménages** (`COE0`) : un ménage occupe un logement et tire une fois. Avant le
  ticket 019 la pondération était celle des personnes (`COEP`), ce qui compensait
  *par coïncidence* l'absence de la taille du ménage dans le conditionnement — il ne
  faut donc jamais changer la pondération sans le levier de taille, cf. `_internal_check`
  qui publie les deux mesures côte à côte ;
- **levier de taille de ménage** au niveau du périmètre, `P(M1 | taille) / P(M1)` pour
  les classes 1, 2, 3, 4 et plus. Le module l'applique à la loi de zone puis
  renormalise (transfert de rapport de cotes). Servir la loi brute
  `P(M1 | zone, taille)` était exclu : les 2 145 cellules (zone, taille) comptent
  **3 ménages en médiane** et 18 seulement atteignent 30 observations ;
- **lissage hiérarchique** zone → secteur de tirage → ensemble du périmètre. Une zone
  fine compte 12 ménages enquêtés en médiane, un secteur en compte 122 : servir la loi
  brute d'une zone à 2 répondants ferait passer du bruit d'échantillonnage pour de la
  géographie. Le poids du repli, `PRIOR_WEIGHT`, est fixé à l'effectif médian d'une
  zone — au médian, la zone et son secteur pèsent donc autant l'un que l'autre ;
- **aucun seuil ne masque rien** : l'effectif enquêté de chaque zone (en ménages et en
  personnes) est écrit dans la ressource à côté de sa loi lissée, et toute cellule
  (taille × modalité) sous `THIN_CELL` observations est signalée, pas lissée en silence.

Le script publie enfin le **test interne EMC²** exigé par le ticket 019 comme critère
exécutable : chaque ménage enquêté reçoit la loi de sa zone corrigée du levier de sa
taille, et on compare à son `M1` réel. C'est cette mesure — erreur absolue moyenne sur
les 20 cellules (5 modalités × 4 tailles) — qui dit si le mécanisme vaut mieux que le
précédent, et elle est écrite dans la ressource pour être relisible sans les données.

Ce que le script écrit dans `llm_module/data/zf_housing_type.json` : les modalités, la
loi d'ensemble, la loi par secteur, la loi par zone, les leviers de taille et leurs
effectifs, le bloc de validation, et un bloc `meta` de provenance. **Aucune
microdonnée** — uniquement des lois agrégées, comme la couche de zones fines exportée
par `export_zone_layer.py`, et de même statut : hors dépôt, régénérable, jamais
committée.

Usage :
    python -m scripts.progedo_logit.export_housing_type [--out DIR]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from llm_module.core.housing_type import (
    DEFAULT_RESOURCE,
    MODALITY_KEYS,
    SECTOR_PREFIX_LEN,
    SIZE_MAX,
    rake,
)
from scripts.progedo_logit.build_mode_choice_dataset import find_project_root, load_raw

# Recodage `M1` (fichier ménages) → clés de `cerema_values.yaml`. Les libellés de
# l'enquête sont : 1 Individuel isolé, 2 Individuel accolé, 3 Petit collectif
# (R+1 à R+3), 4 Grand collectif (R+4 et plus), 5 Autres.
HOUSING = {
    "1": "individuel_isole",
    "2": "individuel_accole",
    "3": "petit_habitat_collectif",
    "4": "grand_habitat_collectif",
    "5": "autres",
}

# Poids du repli, en **ménages** enquêtés. Fixé à l'effectif médian d'une zone fine :
# une zone médiane pèse alors autant que son secteur, une zone bien enquêtée domine son
# secteur, une zone à 2 répondants s'y efface. L'unité a suivi la pondération (ticket
# 019) : 18 personnes en médiane, mais 12 ménages.
PRIOR_WEIGHT = 12.0

# Poids du repli d'avant le ticket 019, en personnes enquêtées (médiane 18). Conservé
# pour rejouer le mécanisme précédent dans le test interne, et pour rien d'autre.
PREVIOUS_PRIOR = 18.0

# Seuil de signalement d'une cellule (taille × modalité) du bloc de leviers. Le ticket
# 019 l'exige : « toute cellule sous 30 observations pondérées est signalée, pas lissée
# en silence ». Le compte comparé au seuil est celui des **ménages enquêtés** : les
# poids `COE0` sont des coefficients d'extrapolation à la population (un ménage en pèse
# ~60), un seuil de 30 posé sur leur somme ne se déclencherait jamais.
THIN_CELL = 30

# Erreur absolue moyenne maximale du test interne EMC², en points, sur les 20 cellules
# (5 modalités × 4 tailles). Critère d'acceptation du ticket 019 ; le mécanisme
# antérieur valait 3,00 pt, le mécanisme livré 0,75.
MAX_MEAN_ABS_ERROR_PT = 1.0


def load_survey(progedo_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Les deux tables du test : les **ménages** enquêtés, et les **personnes**.

    Les ménages portent le type d'habitat, le poids `COE0`, la taille du foyer et sa
    classe de levier : c'est eux qui construisent la loi servie. Clé ménage = (zone
    fine, échantillon) — `ECH` seul n'est pas unique d'une zone à l'autre, même règle
    que `build_household`. La taille est **reconstituée depuis le fichier personnes**
    (`M4`/`M5` sont entièrement vides dans le fichier standard).

    Les personnes portent le type d'habitat de leur ménage et le poids `COEP` : c'est la
    table exacte que le mécanisme d'avant le ticket 019 utilisait, et elle ne sert plus
    qu'à le rejouer dans le test interne — plus une chose comparée de mémoire.
    """
    pers, men, _ = load_raw(progedo_dir)

    sizes = pers.groupby(["ZFP", "ECH"]).size().rename("size")
    key = pd.MultiIndex.from_arrays([men["ZFM"], men["ECH"]])

    households = pd.DataFrame({
        "ZF": men["ZFM"],
        "housing": men["M1"].map(HOUSING),
        "weight": pd.to_numeric(men["COE0"], errors="coerce"),
        "size": key.map(sizes),
    })
    n0 = len(households)
    households = households.dropna(subset=["ZF", "housing", "weight", "size"])
    households = households[households["weight"] > 0]
    households["bucket"] = np.minimum(households["size"].astype(int), SIZE_MAX)
    print(f"Ménages : {n0} au départ → {len(households)} avec type d'habitat, taille "
          f"et pondération")
    print("  par taille : " + " / ".join(
        f"{size}{'+' if size == SIZE_MAX else ''} : "
        f"{int((households['bucket'] == size).sum())}"
        for size in range(1, SIZE_MAX + 1)))

    housing_of = (men.assign(housing=men["M1"].map(HOUSING))
                  .drop_duplicates(["ZFM", "ECH"])
                  .set_index(["ZFM", "ECH"])["housing"])
    persons = pd.DataFrame({
        "ZF": pers["ZFP"],
        "housing": pd.MultiIndex.from_arrays([pers["ZFP"], pers["ECH"]]).map(housing_of),
        "weight": pd.to_numeric(pers["COEP"], errors="coerce"),
    })
    persons = persons.dropna(subset=["ZF", "housing", "weight"])
    persons = persons[persons["weight"] > 0]
    print(f"Personnes : {len(persons)} avec type d'habitat et pondération (elles ne "
          f"servent qu'à rejouer le mécanisme d'avant le ticket 019)")
    return households.reset_index(drop=True), persons.reset_index(drop=True)


def _shares(frame: pd.DataFrame) -> np.ndarray:
    """Parts pondérées dans l'ordre de `MODALITY_KEYS`, sommant à 1."""
    mass = frame.groupby("housing")["weight"].sum()
    vector = np.array([float(mass.get(key, 0.0)) for key in MODALITY_KEYS])
    total = vector.sum()
    return vector / total if total > 0 else vector


def _smooth(observed: np.ndarray, n: float, prior: np.ndarray,
            prior_weight: float | None = None) -> np.ndarray:
    """Loi observée tirée vers son repli, à proportion de l'effectif enquêté.

    `prior_weight` n'est explicité que par la variante de comparaison en pondération
    personnes (`_person_weighted`), dont l'effectif est en personnes et non en ménages.
    """
    weight = PRIOR_WEIGHT if prior_weight is None else prior_weight
    return (n * observed + weight * prior) / (n + weight)


def build_geography(households: pd.DataFrame,
                    persons_per_zone: pd.Series) -> tuple[dict, dict, np.ndarray]:
    """Lois lissées par zone et par secteur, plus la loi d'ensemble du périmètre."""
    households = households.assign(sector=households["ZF"].str[:SECTOR_PREFIX_LEN])
    overall = _shares(households)

    sectors: dict[str, dict] = {}
    for sector, frame in households.groupby("sector"):
        sectors[str(sector)] = {
            "n": int(len(frame)),
            "shares": [round(float(v), 6)
                       for v in _smooth(_shares(frame), len(frame), overall)],
        }

    zones: dict[str, dict] = {}
    for zf, frame in households.groupby("ZF"):
        sector = str(zf)[:SECTOR_PREFIX_LEN]
        prior = np.array(sectors[sector]["shares"]) if sector in sectors else overall
        zones[str(zf)] = {
            "n": int(len(frame)),
            "n_persons": int(persons_per_zone.get(str(zf), 0)),
            "shares": [round(float(v), 6)
                       for v in _smooth(_shares(frame), len(frame), prior)],
        }
    return zones, sectors, overall


def build_size_leverage(households: pd.DataFrame, overall: np.ndarray) -> dict:
    """Leviers `P(M1 | taille) / P(M1)`, avec les effectifs de chaque cellule.

    Le levier est estimé **au périmètre**, pas par zone : c'est l'hypothèse de
    transfert du ticket 019, et elle est ce qui rend la loi servable — la cellule
    (zone, taille) compte 3 ménages en médiane.

    Une modalité de masse nulle au périmètre reçoit un levier de 1 (neutre) plutôt
    qu'une division par zéro : elle est de toute façon absente de toutes les lois.
    """
    out: dict[str, dict] = {}
    for bucket in range(1, SIZE_MAX + 1):
        frame = households[households["bucket"] == bucket]
        shares = _shares(frame)
        leverage = np.divide(shares, overall, out=np.ones_like(shares),
                            where=overall > 0)
        cells = frame.groupby("housing").agg(n=("weight", "size"),
                                            weighted_n=("weight", "sum"))
        out[str(bucket)] = {
            "n": int(len(frame)),
            "weighted_n": round(float(frame["weight"].sum()), 1),
            "shares": [round(float(v), 6) for v in shares],
            "leverage": [round(float(v), 6) for v in leverage],
            "cells": [
                {
                    "modality": key,
                    "n": int(cells["n"].get(key, 0)),
                    "weighted_n": round(float(cells["weighted_n"].get(key, 0.0)), 1),
                    "thin": bool(int(cells["n"].get(key, 0)) < THIN_CELL),
                }
                for key in MODALITY_KEYS
            ],
        }
    return out


def _law_of(zf: str, zones: dict, sectors: dict, overall: np.ndarray) -> np.ndarray:
    """Loi géographique servie pour une zone — même repli que `HousingTypeTable`."""
    node = zones.get(str(zf))
    if node is not None:
        return np.array(node["shares"], dtype=float)
    sector = sectors.get(str(zf)[:SECTOR_PREFIX_LEN])
    if sector is not None:
        return np.array(sector["shares"], dtype=float)
    return overall


def _imputed_by_size(households: pd.DataFrame, zones: dict, sectors: dict,
                     overall: np.ndarray,
                     leverage: dict[int, np.ndarray] | None) -> dict[int, np.ndarray]:
    """Loi imputée moyenne par classe de taille, pondérée `COE0`.

    On compare des **lois**, pas des tirages : le tirage par hachage reproduit la loi
    à l'aléa d'échantillonnage près (vérifié dans `test_housing_type.py`), et mesurer
    sur la loi évite de faire dépendre un critère d'acceptation d'un jeu de graines.
    """
    out: dict[int, np.ndarray] = {}
    for bucket, frame in households.groupby("bucket"):
        tilt = None if leverage is None else leverage[int(bucket)]
        weights = frame["weight"].to_numpy(dtype=float)
        laws = np.array([rake(_law_of(zf, zones, sectors, overall), tilt)
                         for zf in frame["ZF"]], dtype=float)
        out[int(bucket)] = (laws * weights[:, None]).sum(axis=0) / weights.sum()
    return out


def _variant(households: pd.DataFrame, zones: dict, sectors: dict,
             overall: np.ndarray, leverage: dict[int, np.ndarray] | None,
             label: str) -> dict:
    """Une variante du mécanisme, mesurée à l'intérieur d'EMC²."""
    imputed = _imputed_by_size(households, zones, sectors, overall, leverage)
    weights_by_size = households.groupby("bucket")["weight"].sum()
    total = float(weights_by_size.sum())

    cells, by_size = [], []
    for bucket in sorted(imputed):
        frame = households[households["bucket"] == bucket]
        observed = _shares(frame)
        for index, key in enumerate(MODALITY_KEYS):
            cells.append({
                "size": bucket,
                "modality": key,
                "observed_pct": round(float(100 * observed[index]), 2),
                "imputed_pct": round(float(100 * imputed[bucket][index]), 2),
                "abs_error_pt": round(
                    float(100 * abs(observed[index] - imputed[bucket][index])), 2),
            })
        by_size.append({
            "size": bucket,
            "n": int(len(frame)),
            "individuel_isole_observed_pct": round(float(100 * observed[0]), 2),
            "individuel_isole_imputed_pct": round(float(100 * imputed[bucket][0]), 2),
        })

    marginal = sum(float(weights_by_size[b]) * imputed[b] for b in imputed) / total
    return {
        "label": label,
        "mean_abs_error_pt": round(
            float(np.mean([cell["abs_error_pt"] for cell in cells])), 3),
        "by_size": by_size,
        "cells": cells,
        "overall_marginal_observed_pct": [
            round(float(100 * v), 2) for v in _shares(households)],
        "overall_marginal_imputed_pct": [round(float(100 * v), 2) for v in marginal],
    }


def internal_check(households: pd.DataFrame, persons: Optional[pd.DataFrame],
                   zones: dict, sectors: dict, overall: np.ndarray,
                   size_leverage: dict) -> dict:
    """Le test interne EMC² du ticket 019, et les deux mécanismes qu'il remplace.

    Trois variantes sont mesurées sur les mêmes ménages :

    1. **zone seule, pondération personnes** — le mécanisme d'avant le ticket 019 ;
    2. **zone seule, pondération ménages** — pour montrer que la pondération n'est PAS
       le sujet : seule, elle dégrade. Qui ne mesurerait que celle-là conclurait qu'il
       faut revenir à `COEP` ;
    3. **zone en pondération ménages + levier de taille** — le mécanisme livré.

    Le test est *en place* : les lois sont estimées sur les ménages qui servent aussi
    à les évaluer. Il ne mesure donc pas une capacité de généralisation mais la
    **fidélité du mécanisme** — un mécanisme qui ne sait pas reproduire le gradient de
    la population sur laquelle il est estimé ne le reproduira nulle part, et c'est
    exactement ce que faisait le précédent (3,00 pt en place).
    """
    leverage = {int(size): np.array(node["leverage"], dtype=float)
                for size, node in size_leverage.items()}

    # Variante 1 : la loi de zone telle qu'elle était pondérée avant le ticket 019.
    # Reconstruite ici plutôt que lue dans l'ancienne ressource, pour que la
    # comparaison porte sur le seul changement mesuré et pas sur un fichier daté.
    baselines = []
    if persons is not None and len(persons):
        before = _person_weighted(persons)
        baselines.append(_variant(households, *before, None,
                                  "zone seule, pondération personnes "
                                  "(avant ticket 019)"))
    households_only = _variant(households, zones, sectors, overall, None,
                               "zone seule, pondération ménages")
    raked = _variant(households, zones, sectors, overall, leverage,
                     "zone en pondération ménages + levier de taille (livré)")

    return {
        "note": "Chaque ménage enquêté reçoit la loi de sa zone (corrigée du levier de "
                "sa taille pour la variante livrée) ; on la compare à son M1 réel. "
                "Mesure EN PLACE, sans biais de périmètre : c'est la fidélité du "
                "mécanisme, pas sa généralisation.",
        "max_mean_abs_error_pt": MAX_MEAN_ABS_ERROR_PT,
        "passes": raked["mean_abs_error_pt"] <= MAX_MEAN_ABS_ERROR_PT,
        "delivered": raked,
        "baselines": baselines + [households_only],
    }


def _person_weighted(persons: pd.DataFrame) -> tuple[dict, dict, np.ndarray]:
    """Les lois de zone telles que le mécanisme d'avant le ticket 019 les construisait.

    Rejeu **exact** : une ligne par personne enquêtée, pondération `COEP`, effectif de
    lissage en personnes, poids du repli à 18. Reconstruit ici plutôt que relu dans
    l'ancienne ressource, pour que la comparaison porte sur le mécanisme et pas sur un
    fichier daté — mais c'est bien la même table et le même code de lissage.
    """
    overall = _shares(persons)
    sectors: dict[str, dict] = {}
    for sector, frame in persons.groupby(persons["ZF"].str[:SECTOR_PREFIX_LEN]):
        sectors[str(sector)] = {
            "n": int(len(frame)),
            "shares": list(_smooth(_shares(frame), len(frame), overall, PREVIOUS_PRIOR)),
        }
    zones: dict[str, dict] = {}
    for zf, frame in persons.groupby("ZF"):
        prior = np.array(sectors[str(zf)[:SECTOR_PREFIX_LEN]]["shares"])
        zones[str(zf)] = {
            "n": int(len(frame)),
            "shares": list(_smooth(_shares(frame), len(frame), prior, PREVIOUS_PRIOR)),
        }
    return zones, sectors, overall


def build_table(households: pd.DataFrame,
                persons: Optional[pd.DataFrame] = None) -> dict:
    """La ressource complète : géographie, leviers de taille, validation, provenance.

    `persons` ne sert qu'au rejeu du mécanisme d'avant le ticket 019 dans le bloc de
    validation, et à publier l'effectif en personnes de chaque zone. Sans elle, la
    ressource est complète mais le point de comparaison manque.
    """
    per_zone = (persons.groupby("ZF").size() if persons is not None and len(persons)
                else pd.Series(dtype=int))
    zones, sectors, overall = build_geography(households, per_zone)
    size_leverage = build_size_leverage(households, overall)
    validation = internal_check(households, persons, zones, sectors,
                                overall, size_leverage)

    counts = households.groupby("ZF").size()
    cells = households.groupby(["ZF", "bucket"]).size()
    return {
        "version": 2,
        "trait": "housing_type",
        "modalities": list(MODALITY_KEYS),
        "sizes": list(range(1, SIZE_MAX + 1)),
        "global": [round(float(v), 6) for v in overall],
        "size_leverage": size_leverage,
        "sectors": sectors,
        "zones": zones,
        "validation": validation,
        "meta": {
            "source": "EMC² Toulouse 2023 (ProGEDO lil-1750), fichiers standards "
                      "ménages (M1 « Type d'habitat », COE0) et personnes (taille du "
                      "ménage reconstituée)",
            "weighting": "COE0 — coefficient de redressement du ménage enquêté. Un "
                         "ménage occupe un logement et tire une fois ; la marginale "
                         "personnes se reconstitue par le conditionnement sur la taille",
            "conditioning": "zone fine × taille du ménage (1, 2, 3, 4+), la taille "
                            f"entrant par un levier P(M1|taille)/P(M1) estimé au "
                            f"périmètre puis renormalisé (ticket 019)",
            "smoothing": f"zone → secteur de tirage ({SECTOR_PREFIX_LEN} premiers "
                         f"caractères du code ZF) → périmètre, poids du repli "
                         f"{PRIOR_WEIGHT} ménages",
            "thin_cell_threshold": THIN_CELL,
            "n_households": int(len(households)),
            "n_zones": len(zones),
            "n_sectors": len(sectors),
            "median_households_per_zone": float(np.median(counts)) if len(counts) else 0.0,
            "zones_under_5_households": int((counts < 5).sum()),
            "n_zone_size_cells": int(len(cells)),
            "median_households_per_zone_size_cell": (
                float(np.median(cells)) if len(cells) else 0.0),
            "zone_size_cells_over_30": int((cells >= 30).sum()),
            "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    }


def report(table: dict) -> None:
    """Ce que le lecteur doit voir sans ouvrir le JSON."""
    print("\nLoi d'ensemble (ménages, pondérée COE0) :")
    for key, share in zip(MODALITY_KEYS, table["global"]):
        print(f"  {key:26s} {100 * share:5.2f} %")

    print("\nLeviers de taille P(M1|taille)/P(M1) — 1 = neutre :")
    header = "  " + " ".join(f"{key[:12]:>13s}" for key in MODALITY_KEYS)
    print(f"  {'taille':>6s} {'n':>6s}" + header)
    for size in table["sizes"]:
        node = table["size_leverage"][str(size)]
        line = " ".join(f"{value:13.3f}" for value in node["leverage"])
        print(f"  {size:>6d} {node['n']:>6d}   {line}")
    thin = [(size, cell["modality"], cell["n"])
            for size in table["sizes"]
            for cell in table["size_leverage"][str(size)]["cells"] if cell["thin"]]
    if thin:
        print(f"  cellules sous {THIN_CELL} ménages enquêtés (signalées, pas lissées) :")
        for size, modality, n in thin:
            print(f"    taille {size} × {modality:26s} n = {n}")
    else:
        print(f"  aucune cellule sous {THIN_CELL} ménages enquêtés")

    print("\nTest interne EMC² — part d'individuel isolé par taille de ménage :")
    delivered = table["validation"]["delivered"]
    print(f"  {'taille':>6s} {'observé':>9s} {'imputé':>9s} {'écart':>7s}")
    for row in delivered["by_size"]:
        observed = row["individuel_isole_observed_pct"]
        imputed = row["individuel_isole_imputed_pct"]
        print(f"  {row['size']:>6d} {observed:8.1f}% {imputed:8.1f}% "
              f"{imputed - observed:+7.1f}")
    print("\n  erreur absolue moyenne sur les 20 cellules (5 modalités × 4 tailles) :")
    for variant in table["validation"]["baselines"]:
        print(f"    {variant['mean_abs_error_pt']:5.2f} pt   {variant['label']}")
    print(f"    {delivered['mean_abs_error_pt']:5.2f} pt   {delivered['label']}")
    verdict = "TENU" if table["validation"]["passes"] else "NON TENU"
    print(f"  critère du ticket 019 (≤ {MAX_MEAN_ABS_ERROR_PT} pt) : {verdict}")

    print("\n  marginale d'ensemble — la géographie ne doit pas bouger :")
    print("    observée : " + " / ".join(
        f"{v:.1f}" for v in delivered["overall_marginal_observed_pct"]))
    print("    imputée  : " + " / ".join(
        f"{v:.1f}" for v in delivered["overall_marginal_imputed_pct"]))

    meta = table["meta"]
    print(f"\n{meta['n_zones']} zones, {meta['n_sectors']} secteurs, médiane "
          f"{meta['median_households_per_zone']:.0f} ménages/zone, "
          f"{meta['zones_under_5_households']} zones sous 5 ménages (elles s'effacent "
          f"derrière leur secteur)")
    print(f"{meta['n_zone_size_cells']} cellules (zone, taille), médiane "
          f"{meta['median_households_per_zone_size_cell']:.0f} ménages, "
          f"{meta['zone_size_cells_over_30']} à 30 ménages ou plus — c'est pourquoi la "
          f"taille entre par un levier de périmètre et non par un croisement brut")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None,
                        help=f"Fichier de sortie (défaut : {DEFAULT_RESOURCE})")
    args = parser.parse_args()

    root = find_project_root()
    progedo_dir = (root / "data" / "PROGEDO 2023" / "lil-1750-Donnees_CSV"
                   / "fichiers_standards")

    households, persons = load_survey(progedo_dir)
    table = build_table(households, persons)

    out = args.out or DEFAULT_RESOURCE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(table, ensure_ascii=False, indent=1), encoding="utf-8")

    report(table)
    print(f"→ {out}")
    if not table["validation"]["passes"]:
        print("\n[ALARME] Test interne EMC² au-dessus du seuil du ticket 019 : la loi "
              "est écrite, mais elle ne tient pas le critère de recette.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
