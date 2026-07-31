"""export_zone_layer.py — Ressource de zones fines embarquée pour le runtime.

Les quatre variables géographiques du modèle de choix modal (`od_km`, `density_*`,
`dist_center_*`) pèsent lourd dans ses importances, et toutes dérivent d'un même
préalable : savoir dans **quelle zone fine** tombe un point. À l'entraînement cette
information est donnée par l'enquête (`D3`/`D7`) ; en simulation il n'y a que des
coordonnées. Il faut donc rejouer la jointure spatiale au runtime — d'où cette
ressource (ticket 005 §2.1, action A7).

Ce que le script écrit dans `llm_module/data/` :

- `zf_zones.gpkg` — les 785 polygones de zones fines, avec par zone le centroïde
  Lambert 93, la surface, la densité de ménages et la distance à l'hypercentre ;
- `zf_zones.meta.json` — provenance (couche source et son empreinte) et la
  référence géographique, recopiée telle quelle depuis `build_geo`.

**Les valeurs ne sont pas recalculées ici.** Le script importe `build_geo` du
constructeur du jeu d'entraînement : densité, distance au centre et centroïdes sont
donc identiques par construction à celles vues à l'entraînement. Toute autre
approche (réimplémenter la densité, relire le shapefile à sa façon) créerait deux
définitions concurrentes de la même variable — exactement le défaut que
`feature_spec.json` existe pour empêcher.

Pourquoi une ressource dérivée plutôt que le shapefile source : `data/PROGEDO 2023`
contient les microdonnées d'accès restreint (lil-1750), n'est pas versionné et n'est
pas monté dans le conteneur `controller`. La couche exportée ici ne porte que des
agrégats à la zone, et vit sous `llm_module/`, déjà monté partout où le résolveur
tourne.

Usage :
    python -m scripts.progedo_logit.export_zone_layer [--out-dir DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd

from scripts.progedo_logit.build_mode_choice_dataset import (
    build_geo,
    find_project_root,
    load_raw,
)

# Nom de couche attendu par le résolveur (llm_module/core/zone_resolver.py).
LAYER_NAME = "zf"

# Colonnes de la ressource. `ZF` est la clé, les cinq suivantes sont tout ce dont
# le résolveur a besoin pour produire les six features géographiques du spec.
COLUMNS = ["ZF", "XL93", "YL93", "SURF_M2", "density_hh_km2", "dist_center_km"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_layer(sig_zf: Path, men) -> tuple[gpd.GeoDataFrame, dict]:
    """Couche polygonale enrichie des attributs de `build_geo`.

    La géométrie vient du shapefile, les attributs de `build_geo` : on rejoint les
    deux sur `ZF` plutôt que de recalculer, pour que la ressource et le jeu
    d'entraînement ne puissent pas diverger.
    """
    geo, xys, ref = build_geo(sig_zf, men)

    layer = gpd.read_file(sig_zf)[["ZF", "geometry"]].copy()
    layer["ZF"] = layer["ZF"].astype(str).str.strip()

    attrs = xys.join(geo)
    out = layer.merge(attrs, left_on="ZF", right_index=True, how="left")

    missing = out["XL93"].isna().sum()
    if missing:
        raise SystemExit(
            f"{missing} zones sans centroïde après jointure : la clé ZF ne correspond pas "
            "entre le shapefile et build_geo."
        )
    if len(out) != ref["n_zones"]:
        raise SystemExit(
            f"{len(out)} polygones pour {ref['n_zones']} zones attendues : la couche a changé."
        )

    # La densité est légitimement absente pour les zones sans ménage enquêté. On ne
    # l'impute pas : le booster route les valeurs manquantes nativement, et un 0
    # signifierait « zone déserte », ce qui est faux.
    n_no_density = int(out["density_hh_km2"].isna().sum())
    print(f"Zones sans ménage enquêté (densité manquante, non imputée) : {n_no_density}")

    return out[COLUMNS + ["geometry"]], ref


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="Répertoire de sortie (défaut : llm_module/data/)")
    args = parser.parse_args()

    root = find_project_root()
    progedo_dir = root / "data" / "PROGEDO 2023" / "lil-1750-Donnees_CSV" / "fichiers_standards"
    sig_zf = (root / "data" / "PROGEDO 2023" / "lil-1750-Documentation" / "SIG"
              / "EMC2_Toulouse_2023_ZF_26052023.shp")
    out_dir = args.out_dir or (root / "llm_module" / "data")
    out_dir.mkdir(parents=True, exist_ok=True)

    _, men, _ = load_raw(progedo_dir)
    layer, ref = build_layer(sig_zf, men)

    gpkg_path = out_dir / "zf_zones.gpkg"
    meta_path = out_dir / "zf_zones.meta.json"

    # Réécriture complète : sans suppression préalable, pyogrio ajoute une seconde
    # couche du même nom au lieu de remplacer la première.
    gpkg_path.unlink(missing_ok=True)
    layer.to_file(gpkg_path, layer=LAYER_NAME, driver="GPKG")

    meta = {
        "layer": LAYER_NAME,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": {
            "shapefile": sig_zf.name,
            "sha256": sha256(sig_zf),
            "survey": "EMC² Toulouse 2023 (ProGEDO / lil-1750)",
        },
        # Recopiée depuis build_geo, et donc comparable à l'identique avec le bloc
        # `geo_reference` de feature_spec.json : le résolveur refuse de servir une
        # couche et un modèle qui ne parlent pas du même hypercentre (cf. A9).
        "geo_reference": ref,
        "columns": COLUMNS,
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")

    print(f"\nÉcrits :\n - {gpkg_path} ({len(layer)} zones, couche '{LAYER_NAME}')"
          f"\n - {meta_path}")


if __name__ == "__main__":
    main()
