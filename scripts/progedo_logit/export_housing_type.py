"""export_housing_type.py — Loi du type de logement par zone fine (action A2).

La référence EMC² ventile les parts modales par **type d'habitat**, mais la chaîne de
génération de population ne produit pas ce trait : ni eqasim, ni les tables INSEE
mobilisées par le notebook (zonage AAV, grille de densité) ne portent l'information.
La seule source qui la porte pour le périmètre toulousain est l'enquête elle-même,
variable `M1` du fichier ménages (« Type d'habitat »), dont les modalités sont
exactement celles de la ventilation publiée.

Ce script en extrait une **loi conditionnelle à la zone fine**, seule ressource
nécessaire pour imputer le trait à la génération de population :

- pondération par les coefficients de redressement des **personnes** (`COEP`), et non
  des ménages : c'est une personne qu'on dote d'un logement, et les ménages en
  individuel sont plus grands (34,7 % des ménages en individuel isolé, 41,7 % des
  personnes) ;
- lissage hiérarchique zone → secteur de tirage → ensemble du périmètre. Une zone
  fine compte 18 personnes enquêtées en médiane, un secteur en compte 174 :
  servir la loi brute d'une zone à 3 répondants ferait passer du bruit
  d'échantillonnage pour de la géographie. Le poids du repli, `PRIOR_WEIGHT`, est
  fixé à l'effectif médian d'une zone — au médian, la zone et son secteur pèsent
  donc autant l'un que l'autre ;
- aucun seuil ne masque rien : l'effectif enquêté de chaque zone est écrit dans la
  ressource, à côté de sa loi lissée.

Ce que le script écrit dans `llm_module/data/zf_housing_type.json` : les modalités,
la loi d'ensemble, la loi par secteur, la loi par zone, et un bloc `meta` de
provenance. **Aucune microdonnée** — uniquement des lois agrégées, comme la couche de
zones fines exportée par `export_zone_layer.py`, et de même statut : hors dépôt,
régénérable, jamais committée.

Usage :
    python -m scripts.progedo_logit.export_housing_type [--out DIR]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from llm_module.core.housing_type import (
    DEFAULT_RESOURCE,
    MODALITY_KEYS,
    SECTOR_PREFIX_LEN,
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

# Poids du repli, en personnes enquêtées. Fixé à l'effectif médian d'une zone fine :
# une zone médiane pèse alors autant que son secteur, une zone bien enquêtée domine
# son secteur, une zone à 2 répondants s'y efface.
PRIOR_WEIGHT = 18.0


def load_persons_with_housing(progedo_dir: Path) -> pd.DataFrame:
    """Personnes enquêtées, dotées du type d'habitat de leur ménage et de leur poids.

    Clé ménage = (zone fine, échantillon) : `ECH` seul n'est pas unique d'une zone à
    l'autre — même règle que `build_household`.
    """
    pers, men, _ = load_raw(progedo_dir)

    housing = men.assign(housing=men["M1"].map(HOUSING))
    housing = housing.drop_duplicates(["ZFM", "ECH"]).set_index(["ZFM", "ECH"])["housing"]

    out = pd.DataFrame({
        "ZF": pers["ZFP"],
        "housing": pd.MultiIndex.from_arrays([pers["ZFP"], pers["ECH"]]).map(housing),
        "weight": pd.to_numeric(pers["COEP"], errors="coerce"),
    })
    n0 = len(out)
    out = out.dropna(subset=["ZF", "housing", "weight"])
    out = out[out["weight"] > 0]
    print(f"Personnes : {n0} au départ → {len(out)} avec type d'habitat et pondération")
    return out


def _shares(frame: pd.DataFrame) -> np.ndarray:
    """Parts pondérées dans l'ordre de `MODALITY_KEYS`, sommant à 1."""
    mass = frame.groupby("housing")["weight"].sum()
    vector = np.array([float(mass.get(key, 0.0)) for key in MODALITY_KEYS])
    total = vector.sum()
    return vector / total if total > 0 else vector


def _smooth(observed: np.ndarray, n: float, prior: np.ndarray) -> np.ndarray:
    """Loi observée tirée vers son repli, à proportion de l'effectif enquêté."""
    return (n * observed + PRIOR_WEIGHT * prior) / (n + PRIOR_WEIGHT)


def build_table(persons: pd.DataFrame) -> dict:
    """Lois lissées par zone et par secteur, plus la loi d'ensemble."""
    persons = persons.assign(sector=persons["ZF"].str[:SECTOR_PREFIX_LEN])
    overall = _shares(persons)

    sectors: dict[str, dict] = {}
    for sector, frame in persons.groupby("sector"):
        sectors[str(sector)] = {
            "n": int(len(frame)),
            "shares": [round(float(v), 6)
                       for v in _smooth(_shares(frame), len(frame), overall)],
        }

    zones: dict[str, dict] = {}
    for zf, frame in persons.groupby("ZF"):
        sector = str(zf)[:SECTOR_PREFIX_LEN]
        prior = np.array(sectors[sector]["shares"]) if sector in sectors else overall
        zones[str(zf)] = {
            "n": int(len(frame)),
            "shares": [round(float(v), 6)
                       for v in _smooth(_shares(frame), len(frame), prior)],
        }

    counts = np.array([len(f) for _, f in persons.groupby("ZF")])
    return {
        "version": 1,
        "trait": "housing_type",
        "modalities": list(MODALITY_KEYS),
        "global": [round(float(v), 6) for v in overall],
        "sectors": sectors,
        "zones": zones,
        "meta": {
            "source": "EMC² Toulouse 2023 (ProGEDO lil-1750), fichiers standards "
                      "ménages (M1 « Type d'habitat ») et personnes (COEP)",
            "weighting": "COEP — coefficient de redressement de la personne enquêtée",
            "smoothing": f"zone → secteur de tirage ({SECTOR_PREFIX_LEN} premiers "
                         f"caractères du code ZF) → périmètre, poids du repli "
                         f"{PRIOR_WEIGHT} personnes",
            "n_persons": int(len(persons)),
            "n_zones": len(zones),
            "n_sectors": len(sectors),
            "median_persons_per_zone": float(np.median(counts)) if counts.size else 0.0,
            "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None,
                        help=f"Fichier de sortie (défaut : {DEFAULT_RESOURCE})")
    args = parser.parse_args()

    root = find_project_root()
    progedo_dir = (root / "data" / "PROGEDO 2023" / "lil-1750-Donnees_CSV"
                   / "fichiers_standards")

    persons = load_persons_with_housing(progedo_dir)
    table = build_table(persons)

    out = args.out or DEFAULT_RESOURCE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(table, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\nLoi d'ensemble (personnes, pondérée) :")
    for key, share in zip(MODALITY_KEYS, table["global"]):
        print(f"  {key:26s} {100 * share:5.2f} %")
    print(f"\n{table['meta']['n_zones']} zones, {table['meta']['n_sectors']} secteurs, "
          f"médiane {table['meta']['median_persons_per_zone']:.0f} personnes/zone")
    print(f"→ {out}")


if __name__ == "__main__":
    main()
