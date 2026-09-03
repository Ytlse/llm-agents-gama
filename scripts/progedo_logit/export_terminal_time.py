"""export_terminal_time.py — Le temps terminal d'un trajet voiture, mesuré sur EMC².

`llm-agents/config/terminal_time.yaml` applique 2 à 10 minutes d'accès et de
stationnement par trajet voiture, sourcées sur la littérature (tables COMPASS, Shoup,
Cerema). L'enquête que le projet prend pour cible en mesure **11 à 14 fois moins**, et
elle le mesure directement : le fichier trajets porte `T2` (marche à pied au départ),
`T6` (marche à pied à l'arrivée) et `T11` (durée de recherche du stationnement).

Ce script en extrait la **loi empirique**, par couronne et par bout de trajet.

## Pourquoi une loi et pas une moyenne

La moyenne d'enquête est **inférieure à la minute** (0,36 min d'accès à Toulouse). Or le
rendu des options impose des multiples de 60 s — c'est structurel, l'invariant « total
affiché = somme des sous-étapes » en dépend. Servir la moyenne obligerait donc à afficher
0 minute partout, ce qui effacerait une queue bien réelle : 2 à 4 % des trajets ont
vraiment 5 minutes ou plus. La loi garde les deux, la moyenne **et** la queue.

Et ce n'est **pas une cloche**. La distribution est massée à zéro (87 à 96 % selon la
couronne) et étirée à droite. Une gaussienne produirait des valeurs négatives et
détruirait la masse à zéro ; c'est l'histogramme observé qui est servi, pas une forme
paramétrique choisie pour sa commodité.

## Ce que le contrôle de validité a établi

Le doute légitime était que la marche vers la voiture soit codée comme un **trajet à pied
distinct**, auquel cas `T2`/`T6` vaudraient 0 par construction et la comparaison serait
vide. Vérifié : sur les 24 481 déplacements comportant un trajet voiture, **aucun** ne
porte de trajet à pied. La marche terminale ne peut donc être que dans `T2`/`T6`. Et
l'instrument fonctionne — sur les trajets en transports collectifs, de structure
identique, `T2 + T6` donne 6 minutes en médiane. L'enquête sait enregistrer un temps
terminal ; elle en enregistre ~0,6 min pour la voiture.

## Ce que ce script n'est pas

Ce n'est **pas** l'ajustement que la décision T2 du ticket 013 interdit. T2 interdit de
régler ce paramètre *sur un score de calibration*. Ici il est **re-sourcé sur la mesure
d'enquête**, ce qui est précisément ce que son propre `provenance: sourced` réclame. La
distinction est vérifiable : aucune valeur ci-dessous n'a été choisie en regardant une
part modale.

Usage :
    python -m scripts.progedo_logit.export_terminal_time [--out FICHIER]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.progedo_logit.build_mode_choice_dataset import find_project_root

DEFAULT_RESOURCE = (Path(__file__).resolve().parents[2] / "llm_module" / "data"
                    / "terminal_time_emc2.json")

# `T3` du fichier trajets : mode utilisé. 21 = conducteur de véhicule particulier.
# On ne retient que le conducteur : le passager ne cherche pas de place.
CAR_DRIVER = "21"

# Modes de comparaison, pour publier le contrôle de validité dans la ressource.
TRANSIT = ("31", "32", "33")
BIKE = ("11", "17")

# Couronnes, dans l'ordre de lecture d'EMC². Ce sont les modalités de
# `population_reference.COURONNES`, et depuis le ticket 028 les strates sont posées par la
# TABLE de l'enquête (zone fine → secteur de tirage → couronne), plus par la distance à
# l'hypercentre : le temps terminal et la résidence parlent enfin du même découpage.
CROWNS = ("Toulouse", "1ere couronne", "2eme couronne", "3eme couronne")

# Écrêtage de la queue, en minutes. Au-delà de 20 min l'enquête ne porte plus que
# quelques trajets (et deux valeurs à 207 min, manifestement des saisies aberrantes) :
# les garder ferait porter la moyenne par le bruit.
MAX_MINUTES = 20

# Effectif minimal d'une cellule (couronne × bout) pour publier sa loi. En dessous, la
# ressource sert la loi d'ensemble plutôt qu'un histogramme sur quelques dizaines de
# trajets — et elle le dit, plutôt que de le lisser en silence.
MIN_CELL = 200


def crown_of_zone():
    """Zone fine → couronne, par la TABLE de l'enquête (ticket 028).

    Avant : le centroïde de chaque zone fine était classé par sa distance à l'hypercentre
    (`geo_reference.residence_zone`, 8 / 20 / 40 km). Ce n'est pas la définition de
    l'enquête, qui découpe par liste de communes, et le ticket 020 a mesuré l'écart :
    24,4 % des domiciles changent de couronne entre les deux. Les lois de temps terminal
    étaient donc stratifiées sur un découpage que ni les cibles ni le journal n'utilisent.

    `CouronneTable.couronne_of_zf` rattache une zone fine par son secteur de tirage — les
    trois premiers chiffres du code — et c'est le secteur qui porte la couronne dans
    l'enquête. Mesuré identique à 100 % au classement géométrique (ticket 021, lot 0). Un
    code inconnu de la table rend `None` : la ligne sort des strates et reste dans la loi
    d'ensemble, comme avant — on ne devine pas une couronne.
    """
    from llm_module.core.residence_zone import CouronneTable

    return CouronneTable.load().couronne_of_zf


def load_legs(root: Path) -> pd.DataFrame:
    """Trajets de l'enquête, dotés de leurs deux temps terminaux et de leurs couronnes."""
    path = (root / "data" / "PROGEDO 2023" / "lil-1750-Donnees_CSV"
            / "fichiers_standards" / "Toulouse_2023_std_traj.csv")
    legs = pd.read_csv(path, dtype=str)
    for column in legs.columns:
        legs[column] = legs[column].str.strip().replace({"": np.nan})
    for column in ("T2", "T6", "T11"):
        legs[column] = pd.to_numeric(legs[column], errors="coerce").fillna(0.0)

    crown_of = crown_of_zone()
    # `access` = marche au départ ; `egress` = marche à l'arrivée + recherche de place.
    # La recherche est comptée à l'arrivée parce que c'est là qu'on cherche.
    legs["access"] = legs["T2"].clip(0, MAX_MINUTES).round().astype(int)
    legs["egress"] = (legs["T6"] + legs["T11"]).clip(0, MAX_MINUTES).round().astype(int)
    # `T4`/`T5` : zones fines de départ et d'arrivée **du mode mécanisé**. L'accès dépend
    # de l'origine (où le véhicule est garé), l'égression de la destination (où il faut
    # trouver une place) — même convention que le fichier de config.
    legs["access_crown"] = legs["T4"].map(crown_of)
    legs["egress_crown"] = legs["T5"].map(crown_of)
    car = legs["T3"] == CAR_DRIVER
    # Compteur des trajets sans couronne : ils restent dans la loi d'ensemble, jamais
    # dans une strate. Un chiffre élevé signalerait une table périmée, pas un cas normal.
    unmapped = int((legs.loc[car, "access_crown"].isna()
                    | legs.loc[car, "egress_crown"].isna()).sum())
    print(f"Trajets : {len(legs)} au total, {int(car.sum())} en conducteur de VP, "
          f"dont {unmapped} sans couronne à un bout ({100.0 * unmapped / max(int(car.sum()), 1):.1f} %)")
    return legs


def histogram(values: pd.Series) -> dict:
    """Loi en minutes entières : `{minutes: probabilité}`, plus ses moments."""
    counts = values.value_counts().sort_index()
    total = int(counts.sum())
    return {
        "n": total,
        "mean_min": round(float(values.mean()), 4),
        "median_min": float(values.median()),
        "p90_min": float(values.quantile(0.90)),
        # Les clés sont des chaînes : c'est du JSON, et un entier y devient une chaîne
        # de toute façon. Le consommateur reconvertit.
        "pmf": {str(int(k)): round(int(v) / total, 6) for k, v in counts.items()},
    }


def validity_check(legs: pd.DataFrame) -> dict:
    """Le contrôle qui autorise la comparaison, publié avec la loi.

    Si la marche vers la voiture était un trajet à pied distinct, `T2`/`T6` vaudraient 0
    par construction et la loi mesurerait le vide. On vérifie donc que les déplacements
    comportant une jambe voiture n'ont **pas** de jambe à pied, et qu'un mode dont on
    sait la marche terminale réelle (les transports collectifs) la fait bien apparaître.
    """
    key = ["ZFT", "ECH", "PER", "NDEP"]
    grouped = legs.assign(
        _car=legs["T3"] == CAR_DRIVER,
        _foot=legs["T3"] == "01",
        _transit=legs["T3"].isin(TRANSIT),
    ).groupby(key)[["_car", "_foot", "_transit"]].sum()
    with_car = grouped[grouped["_car"] > 0]

    def terminal(codes) -> pd.Series:
        frame = legs[legs["T3"].isin(codes)]
        return frame["access"] + frame["egress"]

    return {
        "question": "La marche vers la voiture est-elle codée comme un trajet à pied "
                    "distinct ? Si oui, T2/T6 vaudraient 0 par construction.",
        "trips_with_car_leg": int(len(with_car)),
        "of_which_no_foot_leg_pct": round(float(100 * (with_car["_foot"] == 0).mean()), 1),
        "verdict": "La marche terminale ne peut être que dans T2/T6 : aucun déplacement "
                   "voiture ne porte de jambe à pied.",
        "instrument_works": {
            "note": "Contrôle positif — un mode dont la marche terminale est réelle doit "
                    "l'afficher. Les TC, de structure identique (aucune jambe à pied), "
                    "la portent bien.",
            "transit_terminal_median_min": float(terminal(TRANSIT).median()),
            "transit_terminal_mean_min": round(float(terminal(TRANSIT).mean()), 2),
            "car_terminal_median_min": float(terminal([CAR_DRIVER]).median()),
            "car_terminal_mean_min": round(float(terminal([CAR_DRIVER]).mean()), 2),
            "bike_terminal_mean_min": round(float(terminal(BIKE).mean()), 2),
        },
    }


# Modes dont on sert une loi, avec les codes `T3` correspondants et la spatialisation.
# Le vélo n'est PAS spatialisé : 2 047 trajets seulement, donc des cellules par couronne
# trop minces. Inventer une variation de couronne serait de l'ajustement déguisé.
LAW_MODES = {
    "car": {"codes": (CAR_DRIVER,), "spatialise": True},
    "bicycle": {"codes": BIKE, "spatialise": False},
}


def build_ends(frame: pd.DataFrame, spatialise: bool) -> dict:
    """Lois `access`/`egress` d'un mode, par couronne si l'effectif le permet."""
    ends: dict[str, dict] = {}
    for end, crown_column in (("access", "access_crown"), ("egress", "egress_crown")):
        overall = histogram(frame[end])
        per_crown: dict[str, dict] = {}
        if spatialise:
            for crown in CROWNS:
                cell = frame[frame[crown_column] == crown]
                if len(cell) < MIN_CELL:
                    # Signalée, pas lissée en silence : le consommateur se rabattra sur
                    # la loi d'ensemble et saura pourquoi.
                    per_crown[crown] = {"n": int(len(cell)), "thin": True}
                    continue
                per_crown[crown] = {**histogram(cell[end]), "thin": False}
        ends[end] = {"overall": overall, "by_crown": per_crown}
    return ends


def build(legs: pd.DataFrame) -> dict:
    modes = {
        mode: {
            "spatialise": spec["spatialise"],
            "n_legs": int(legs["T3"].isin(spec["codes"]).sum()),
            "ends": build_ends(legs[legs["T3"].isin(spec["codes"])],
                               spec["spatialise"]),
        }
        for mode, spec in LAW_MODES.items()
    }
    return {
        "version": 2,
        "trait": "terminal_time",
        "unit": "minutes entières",
        "crowns": list(CROWNS),
        "modes": modes,
        # Conservé pour les lecteurs qui n'ont besoin que de la voiture.
        "ends": modes["car"]["ends"],
        "validity": validity_check(legs),
        "meta": {
            "source": "EMC² Toulouse 2023 (ProGEDO lil-1750), fichier trajets — T2 "
                      "(marche au départ), T6 (marche à l'arrivée), T11 (durée de "
                      "recherche du stationnement)",
            "scope": "conducteur de véhicule particulier (T3 = 21) ; le passager ne "
                     "cherche pas de place",
            "crown_definition": "llm_module.core.residence_zone.CouronneTable — zone "
                                "fine → secteur de tirage → couronne, la liste de "
                                "communes de l'enquête (ticket 028) ; même définition "
                                "que le trait `residence_zone` des personas",
            "clip_minutes": MAX_MINUTES,
            "min_cell": MIN_CELL,
            "not_a_calibration_fit": "Aucune valeur n'a été choisie en regardant une "
                                     "part modale. Le paramètre reste exogène (ticket "
                                     "013, décision T2) ; il est re-sourcé, pas ajusté.",
            "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    }


def report(doc: dict) -> None:
    validity = doc["validity"]
    print(f"\n── Contrôle de validité ────────────────────────────────────────────")
    print(f"  déplacements avec jambe voiture : {validity['trips_with_car_leg']}, "
          f"dont {validity['of_which_no_foot_leg_pct']} % sans aucune jambe à pied")
    works = validity["instrument_works"]
    print(f"  terminal médian — TC {works['transit_terminal_median_min']:.0f} min "
          f"(moyenne {works['transit_terminal_mean_min']:.2f}) contre voiture "
          f"{works['car_terminal_median_min']:.0f} min "
          f"(moyenne {works['car_terminal_mean_min']:.2f})")
    print(f"  → l'instrument enregistre bien un temps terminal ; la voiture en a peu.")

    # Valeurs actuellement appliquées, pour que l'écart soit lisible d'un coup d'œil.
    applied = {"access": {"Toulouse": 3, "1ere couronne": 2, "2eme couronne": 2,
                          "3eme couronne": 1},
               "egress": {"Toulouse": 7, "1ere couronne": 4, "2eme couronne": 3,
                          "3eme couronne": 1}}
    print(f"\n── vélo — loi d'ensemble (non spatialisée, 2 047 trajets) ─────────────")
    for end in ("access", "egress"):
        cell = doc["modes"]["bicycle"]["ends"][end]["overall"]
        print(f"  {end:8s} n={cell['n']:5d}  moyenne {cell['mean_min']:.2f} min "
              f"| tt2 appliquait 1 min")
    for end in ("access", "egress"):
        print(f"\n── {end} — loi d'enquête contre valeur appliquée ───────────────────")
        print(f"  {'couronne':16s} {'n':>6s} {'moyenne':>8s} {'appliqué':>9s} "
              f"{'facteur':>8s}   loi (minutes : part)")
        for crown in doc["crowns"]:
            cell = doc["ends"][end]["by_crown"].get(crown) or {}
            if cell.get("thin"):
                print(f"  {crown:16s} {cell.get('n', 0):6d}   cellule mince → loi d'ensemble")
                continue
            pmf = cell["pmf"]
            top = " ".join(f"{k}:{100 * v:.0f}%" for k, v in list(pmf.items())[:5])
            factor = applied[end][crown] / max(cell["mean_min"], 1e-9)
            print(f"  {crown:16s} {cell['n']:6d} {cell['mean_min']:8.2f} "
                  f"{applied[end][crown]:9d} {factor:7.0f}×   {top}")


def emit_yaml(doc: dict) -> str:
    """Bloc `modes:` de `terminal_time.yaml`, généré depuis la loi mesurée.

    Le bloc est **embarqué dans le YAML** plutôt que lu depuis la ressource JSON, et
    c'est une contrainte de déploiement, pas un choix : les réplicas `osmnx` ne montent
    que `config/` et n'ont pas `llm_module` sur leur path (cf. l'import paresseux de
    `osmnx_direct`). Une config qui dépendrait de `llm_module/data/` les tuerait au
    prochain `docker compose build`.

    Il est donc **généré**, pas recopié : `make terminal-time --emit-config` le réémet
    depuis l'enquête, ce qui évite qu'une centaine de nombres dérivent à la main.
    """
    # Libellés de rendu : repris à l'identique de tt2 — seules les DURÉES changent, et
    # les émettre ici garde le bloc autoportant (le validateur les exige).
    labels = {
        "car": {"access": "Rejoindre la voiture", "main": "Conduite",
                "egress": "Stationnement et marche jusqu'à '{destination}'",
                "egress_sans_destination": "Stationnement et marche jusqu'à la destination",
                "terminal": "d'accès et de stationnement"},
        "bicycle": {"access": "Déverrouiller le vélo", "main": "Trajet à vélo",
                    "egress": "Attacher le vélo à '{destination}'",
                    "egress_sans_destination": "Attacher le vélo à l'arrivée",
                    "terminal": "d'accès et d'attache"},
    }
    lines: list[str] = []
    for mode in ("car", "bicycle"):
        spec = doc["modes"][mode]
        lines.append(f"  {mode}:   # {spec['n_legs']} trajets enquêtés")
        for end in ("access", "egress"):
            node = spec["ends"][end]
            lines.append(f"    {end}_law:")
            for crown in list(doc["crowns"]) + ["default"]:
                cell = (node["by_crown"].get(crown) if crown != "default"
                        else node["overall"])
                thin = crown != "default" and (cell or {}).get("thin")
                if crown == "default" or thin or not cell:
                    cell = node["overall"]
                    note = "  # repli : cellule mince" if thin else ""
                else:
                    note = ""
                lines.append(f"      {crown}:{note}"
                             f"   # n={cell['n']}, moyenne {cell['mean_min']:.2f} min")
                for minutes, probability in sorted(cell["pmf"].items(),
                                                   key=lambda kv: int(kv[0])):
                    lines.append(f"        {minutes}: {probability}")
        # `spatialise` reste vrai pour la voiture : la loi EST par couronne. Le vélo
        # garde une loi d'ensemble, faute d'effet de couronne mesurable sur 2 047
        # trajets — l'inventer serait de l'ajustement déguisé.
        lines.append(f"    provenance: sourced")
        lines.append(f"    spatialise: {'true' if spec['spatialise'] else 'false'}")
        lines.append(f"    labels:")
        for key, value in labels[mode].items():
            lines.append(f"      {key}: \"{value}\"")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None,
                        help=f"Fichier de sortie (défaut : {DEFAULT_RESOURCE})")
    parser.add_argument("--emit-config", type=Path, default=None,
                        help="Écrit aussi le bloc `modes:` de terminal_time.yaml")
    args = parser.parse_args()

    root = find_project_root()
    legs = load_legs(root)
    doc = build(legs)
    report(doc)

    out = args.out or DEFAULT_RESOURCE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n→ {out}")
    if args.emit_config:
        args.emit_config.write_text(emit_yaml(doc), encoding="utf-8")
        print(f"→ {args.emit_config} (bloc `modes:` à insérer dans terminal_time.yaml)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
