"""
export_commune_couronne.py — La donnée manquante du ticket 020 : quelle commune est
dans quelle couronne, et où s'arrête le périmètre d'enquête.

CE QUE ÇA PRODUIT. Trois ressources, dans `llm_module/data/` :

1. `commune_couronne.json` — les 453 communes du périmètre EMC² 2023 avec leur code
   INSEE et leur couronne (`Toulouse` / `1ere couronne` / `2eme couronne` /
   `3eme couronne`). C'est le référentiel de l'enquête, pas une reconstitution.
2. `couronne_perimetre.geojson` — la géométrie des quatre couronnes, en WGS84,
   permettant de classer un domicile par **appartenance** et non par distance.
3. `zf_couronne.json` — les 785 zones fines avec leur secteur de tirage, leur couronne,
   leur code INSEE et leur commune (ticket 021). C'est la ressource que lit
   `llm_module.core.residence_zone` : elle rend la couronne d'un domicile SANS géométrie
   au runtime, puisque `zone_resolver` en donne déjà la zone fine. Le grain est la zone
   fine et non le secteur, parce qu'une table `secteur → couronne` de 88 lignes ne
   porterait pas la commune — et la commune est ce qui rend le classement auditable.

POURQUOI. `geo_reference.residence_zone` classait un domicile par sa **distance à
l'hypercentre** (moins de 8 km = Toulouse, 20 = 1ʳᵉ couronne, 40 = 2ᵉ), avec le
commentaire « ce sont les modalités de `lieu_residence` de la référence EMC² ». Ce
n'en sont pas : l'enquête découpe par LISTE DE COMMUNES. Une couronne administrative
n'est pas un anneau métrique, et le ticket 020 a mesuré la conséquence sur
`toulouse_population_1000.json` : **24,4 % des agents changent de couronne**, dont 66
que le disque de 8 km baptise « Toulouse » alors qu'ils habitent Blagnac, Balma,
Colomiers ou Ramonville — comparés à une cible voiture de 31 % au lieu de 64 %.

SOURCE. Couche SIG de l'enquête, `data/PROGEDO 2023/lil-1750-Documentation/SIG/` :

- `EMC2_Toulouse_2023_DTIR_17072023.shp` — les 88 secteurs de tirage, portant le champ
  `NOM_D2` qui EST le découpage en couronnes de l'enquête ;
- `EMC2_Toulouse_2023_ZF_26052023.shp` — les 785 zones fines, portant `COM` et `INSEE`.

Le rattachement zone fine → secteur passe par le code : les trois premiers chiffres du
code `ZF` sont le `NUM_DTIR`. Vérifié à 100 % sur les 785 zones ; l'export échoue si un
seul code ne se rattache pas, plutôt que de laisser une zone sans couronne.

⚠ LA COUCHE SIG FAIT FOI, ET ELLE CONTREDIT LA PUBLICATION SUR UNE COMMUNE. Elle donne
1 / 69 / 108 / 275, la publication CEREMA annonce 1 / 68 / 109 / 275. Le total, 453, est
le même. On retient la couche : c'est elle qui définit les secteurs sur lesquels les
poids de redressement ont été calculés, donc elle qui définit les cibles.
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
SIG_DIR = REPO_ROOT / "data" / "PROGEDO 2023" / "lil-1750-Documentation" / "SIG"
DTIR_SHP = SIG_DIR / "EMC2_Toulouse_2023_DTIR_17072023.shp"
ZF_SHP = SIG_DIR / "EMC2_Toulouse_2023_ZF_26052023.shp"

OUT_DIR = REPO_ROOT / "llm_module" / "data"
OUT_TABLE = OUT_DIR / "commune_couronne.json"
OUT_GEOJSON = OUT_DIR / "couronne_perimetre.geojson"
OUT_ZF_TABLE = OUT_DIR / "zf_couronne.json"

# Ordre et libellés attendus — ceux de `cerema_values.yaml` / `COURONNES`.
COURONNES = ("Toulouse", "1ere couronne", "2eme couronne", "3eme couronne")


def build() -> dict:
    for path in (DTIR_SHP, ZF_SHP):
        if not path.exists():
            raise SystemExit(
                f"Couche SIG absente : {path}\n"
                "Les données PROGEDO sont d'accès restreint (lil-1750) ; cet export "
                "les exige. La ressource produite est, elle, versionnée.")

    dtir = gpd.read_file(DTIR_SHP)
    zf = gpd.read_file(ZF_SHP)

    inconnues = set(dtir["NOM_D2"].unique()) - set(COURONNES)
    if inconnues:
        raise SystemExit(
            f"Modalités de couronne inattendues dans NOM_D2 : {sorted(inconnues)}. "
            "Elles doivent être exactement celles de cerema_values.yaml.")

    zf = zf.assign(num_dtir=zf["ZF"].astype(str).str[:3])
    orphelines = ~zf["num_dtir"].isin(dtir["NUM_DTIR"].astype(str))
    if orphelines.any():
        raise SystemExit(
            f"{int(orphelines.sum())} zone(s) fine(s) sans secteur de tirage : "
            f"{zf.loc[orphelines, 'ZF'].tolist()[:10]}. Le rattachement par préfixe "
            "de code ne tient plus — il faut passer par une jointure spatiale.")

    # L'absence d'orpheline dit que chaque zone trouve un secteur ; elle ne dit pas que
    # chaque secteur est atteint. Un secteur sans zone fine signifierait que la couche ZF
    # et la couche DTIR ne décrivent pas le même périmètre — et la table publiée le
    # tairait. Contrôle ajouté au ticket 021, lot 1.
    sans_zone = sorted(set(dtir["NUM_DTIR"].astype(str)) - set(zf["num_dtir"]))
    if sans_zone:
        raise SystemExit(
            f"{len(sans_zone)} secteur(s) de tirage sans aucune zone fine : {sans_zone}. "
            "Les deux couches ne décrivent pas le même périmètre.")

    joined = zf.merge(dtir[["NUM_DTIR", "NOM_D2"]], left_on="num_dtir",
                      right_on="NUM_DTIR", how="left")

    # Une commune à cheval sur deux couronnes rendrait la table ambiguë : on refuse
    # plutôt que de trancher par un `mode()` silencieux.
    a_cheval = joined.groupby("INSEE")["NOM_D2"].nunique()
    if (a_cheval > 1).any():
        coupables = a_cheval[a_cheval > 1].index.tolist()
        raise SystemExit(
            f"Communes rattachées à plusieurs couronnes : {coupables}. "
            "La table commune → couronne n'est pas une fonction ; arbitrage manuel requis.")

    table = (joined.groupby("INSEE")
             .agg(commune=("COM", "first"), couronne=("NOM_D2", "first"))
             .reset_index()
             .sort_values("INSEE"))

    counts = table["couronne"].value_counts().to_dict()
    payload = {
        "version": "cc1",
        "source": {
            "survey": "EMC² Toulouse 2023 (ProGEDO / lil-1750)",
            "dtir_layer": DTIR_SHP.name,
            "zf_layer": ZF_SHP.name,
            "field": "NOM_D2",
        },
        "note": ("Découpage par liste de communes, tel que défini par la couche SIG de "
                 "l'enquête. La publication CEREMA annonce 68 et 109 communes pour les "
                 "1ʳᵉ et 2ᵉ couronnes ; la couche en donne 69 et 108, pour le même total "
                 "de 453. La couche fait foi : c'est sur ses secteurs que les poids de "
                 "redressement ont été calculés."),
        "counts": {z: int(counts.get(z, 0)) for z in COURONNES},
        "n_communes": int(len(table)),
        "communes": [
            {"insee": r.INSEE, "commune": r.commune, "couronne": r.couronne}
            for r in table.itertuples()
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_TABLE.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                         encoding="utf-8")

    # Table au grain ZONE FINE (ticket 021). Le runtime résout un domicile en zone fine
    # puis lit cette ligne : aucune jointure spatiale, et la commune vient avec.
    zones_table = (joined[["ZF", "num_dtir", "NOM_D2", "INSEE", "COM"]]
                   .rename(columns={"ZF": "zf", "num_dtir": "secteur",
                                    "NOM_D2": "couronne", "INSEE": "insee",
                                    "COM": "commune"})
                   .astype({"zf": str, "secteur": str, "insee": str})
                   .sort_values("zf"))
    zf_counts = zones_table["couronne"].value_counts().to_dict()
    zf_payload = {
        "version": "zc1",
        "source": payload["source"],
        "note": ("Les 785 zones fines de l'enquête avec leur secteur de tirage, leur "
                 "couronne, leur code INSEE et leur commune. Le rattachement zone → "
                 "secteur passe par les TROIS PREMIERS CHIFFRES du code ZF ; mesuré "
                 "identique à 100 % au classement par appartenance géométrique, sur les "
                 "785 zones comme sur 1 021 domiciles (ticket 021, lot 0, trace "
                 "docs/traces/2026-08-24_couronne_equivalences/). Hors de cette couche, "
                 "la couronne ne se devine pas : c'est `hors périmètre`."),
        "n_zones": int(len(zones_table)),
        "n_secteurs": int(zones_table["secteur"].nunique()),
        "counts": {z: int(zf_counts.get(z, 0)) for z in COURONNES},
        "secteurs": [
            {"secteur": s, "couronne": c}
            for s, c in sorted(zones_table.drop_duplicates("secteur")
                               .set_index("secteur")["couronne"].items())
        ],
        "zones": [
            {"zf": r.zf, "secteur": r.secteur, "couronne": r.couronne,
             "insee": r.insee, "commune": r.commune}
            for r in zones_table.itertuples()
        ],
    }
    OUT_ZF_TABLE.write_text(json.dumps(zf_payload, ensure_ascii=False, indent=1),
                            encoding="utf-8")

    # Géométrie des couronnes : dissolution des secteurs par NOM_D2, reprojetée en
    # WGS84 parce que c'est le repère des domiciles de la population synthétique.
    zones = (dtir[["NOM_D2", "geometry"]].dissolve(by="NOM_D2").reset_index()
             .to_crs(4326))
    zones = zones.rename(columns={"NOM_D2": "couronne"})
    zones["couronne"] = pd.Categorical(zones["couronne"], categories=COURONNES,
                                       ordered=True)
    zones = zones.sort_values("couronne")
    zones.to_file(OUT_GEOJSON, driver="GeoJSON")

    payload["zf_table"] = {k: v for k, v in zf_payload.items() if k != "zones"}
    return payload


def main() -> None:
    payload = build()
    print(f"→ {OUT_TABLE.relative_to(REPO_ROOT)}  ({payload['n_communes']} communes)")
    print(f"→ {OUT_GEOJSON.relative_to(REPO_ROOT)}")
    zf_table = payload["zf_table"]
    print(f"→ {OUT_ZF_TABLE.relative_to(REPO_ROOT)}  "
          f"({zf_table['n_zones']} zones fines, {zf_table['n_secteurs']} secteurs)")
    for zone, n in payload["counts"].items():
        print(f"   {zone:16s} {n:4d} communes")
    print("\nCadrage attendu (population_emc2_2023.yaml) : 1 / 69 / 108 / 275 = 453")


if __name__ == "__main__":
    main()
