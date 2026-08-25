"""export_car_availability.py — La disponibilité de la voiture du ménage, mesurée sur EMC².

`car_availability` (`all` / `some` / `none`) est dérivée, pas observée : elle compare le
nombre de voitures du ménage à son nombre de titulaires du permis majeurs
(`eqasim-toulouse/synthesis/population/enriched.py`). La population synthétique voit donc
**trop de partage** dès que le nombre de permis est surestimé — ce que mesure le
[ticket 017](../../docs/tickets/ticket_017_permis_progedo.md).

Ce script publie la distribution de référence, recalculée depuis les microdonnées, avec les
contrôles qui la rendent opposable. Il ne corrige rien : il fournit la cible du
[ticket 018](../../docs/tickets/ticket_018_partage_voiture_foyer.md).

## La règle de dérivation est recopiée d'eqasim, pas réinventée

    all   si voitures >= permis du ménage (majeurs seulement)
    some  si voitures <  permis
    none  si voitures == 0                (prime sur les deux précédentes)

La restriction aux majeurs vient de l'action A1.a du ticket 008 : un permis hérité d'un
donneur adulte par un enfant faisait basculer des ménages de `all` vers `some`, la voiture y
devenant « à partager » alors que le conducteur supplémentaire a neuf ans. Mesurer la cible
avec une autre règle que celle du simulateur produirait un écart qui ne serait pas un biais
mais une différence de définition — le motif exact que les tickets 015 à 019 corrigent.

## Les deux contrôles de validité

**Positif** — la même lecture du fichier ménages doit reproduire la motorisation publiée par
l'enquête : 1,25 voiture par ménage, et 19 / 45 / 35 % de ménages à zéro / une / deux
voitures et plus. Si ce contrôle échoue, la pondération ou le filtrage sont faux et la
distribution dérivée ne vaut rien. Le script **échoue** plutôt que de publier.

**Négatif** — `P7` doit être renseignée pour les personnes à qui la question est posée. Une
variable vide produirait zéro titulaire par ménage, donc `all` partout : un résultat
parfait et faux, exactement la vacuité que le projet traque. Le script publie le taux de
non-réponse et la répartition des modalités.

⚠ `P7 == 3` (« conduite accompagnée et leçons de conduite ») n'est **pas** un titulaire.
La confondre avec un `oui` gonflerait le nombre de permis et donc le partage — c'est
précisément le biais qu'on mesure.

## Deux pondérations, parce qu'elles ne disent pas la même chose

- **ménages** (`COE0`) : la structure du parc. C'est la lecture qui se compare à la
  motorisation publiée.
- **personnes** (`COE1`) : ce que vit un individu tiré au hasard, donc la lecture opposable
  à une population synthétique d'agents. C'est celle que cite le ticket 018.

Usage :
    python -m scripts.progedo_logit.export_car_availability [--out FICHIER]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "PROGEDO 2023" / "lil-1750-Donnees_CSV" / "fichiers_standards"
OUT = ROOT / "llm_module" / "data" / "car_availability_emc2.json"

LEVELS = ("all", "some", "none")

# Motorisation publiée par l'enquête (cf. scripts/data/population/population_emc2_2023.yaml).
# Sert de contrôle POSITIF : la lecture doit la reproduire, sinon elle est fausse.
PUBLISHED = {"cars_per_household": 1.25, "zero": 19.0, "one": 45.0, "two_plus": 35.0}
TOLERANCE_PT = 1.0
TOLERANCE_CARS = 0.03


def load(root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ménages et personnes du fichier standard. Clé ménage réelle : `(ZFM, ECH)`.

    `ECH` seul n'est pas unique d'une zone à l'autre — même remarque que
    `export_bike_ownership`, et s'en écarter mélangerait des ménages de zones différentes.
    """
    men = pd.read_csv(root / "Toulouse_2023_std_men.csv", dtype=str, sep=None,
                      engine="python")
    pers = pd.read_csv(root / "Toulouse_2023_std_pers.csv", dtype=str, sep=None,
                       engine="python")
    men["weight"] = pd.to_numeric(men["COE0"], errors="coerce")
    men["cars"] = pd.to_numeric(men["M6"], errors="coerce")
    pers["weight"] = pd.to_numeric(pers["COE1"], errors="coerce")
    pers["age"] = pd.to_numeric(pers["P4"], errors="coerce")
    return men, pers


def negative_control(pers: pd.DataFrame) -> dict:
    """`P7` est-elle vivante ? Une variable morte donnerait `all` partout."""
    codes = pers["P7"].fillna("").str.strip()
    total = len(pers)
    adults = pers["age"] >= 18
    blank_adults = int((codes.eq("") & adults).sum())
    return {
        "modalities": {("(vide)" if k == "" else k): int(v)
                       for k, v in codes.value_counts().items()},
        "labels": {"1": "Oui", "2": "Non",
                   "3": "Conduite accompagnée et leçons (PAS un titulaire)"},
        "blank_share_pct": round(100 * float(codes.eq("").sum()) / total, 2),
        "blank_adults": blank_adults,
        "blank_adults_share_pct": round(100 * blank_adults / int(adults.sum()), 2),
        "verdict": ("variable vivante" if codes.eq("1").sum() > 0.3 * total
                    else "SUSPECTE — trop peu de titulaires, vérifier le codage"),
    }


def positive_control(men: pd.DataFrame) -> dict:
    """La lecture reproduit-elle la motorisation publiée ?"""
    frame = men.dropna(subset=["weight", "cars"])
    total = float(frame["weight"].sum())
    measured = {
        "cars_per_household": float((frame["cars"] * frame["weight"]).sum() / total),
        "zero": 100 * float(frame.loc[frame["cars"] == 0, "weight"].sum()) / total,
        "one": 100 * float(frame.loc[frame["cars"] == 1, "weight"].sum()) / total,
        "two_plus": 100 * float(frame.loc[frame["cars"] >= 2, "weight"].sum()) / total,
    }
    deltas = {k: measured[k] - PUBLISHED[k] for k in PUBLISHED}
    ok = (abs(deltas["cars_per_household"]) <= TOLERANCE_CARS
          and all(abs(deltas[k]) <= TOLERANCE_PT for k in ("zero", "one", "two_plus")))
    return {"measured": {k: round(v, 3) for k, v in measured.items()},
            "published": PUBLISHED,
            "delta": {k: round(v, 3) for k, v in deltas.items()},
            "tolerance_pt": TOLERANCE_PT, "tolerance_cars": TOLERANCE_CARS,
            "passed": bool(ok)}


def derive(men: pd.DataFrame, pers: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ajoute `car_availability` aux ménages, et la reporte sur les personnes."""
    pers = pers.copy()
    # P7 == "1" seulement : la conduite accompagnée (3) n'est pas un titulaire.
    pers["licensed_adult"] = (pers["P7"].fillna("").str.strip() == "1") & (pers["age"] >= 18)
    licenses = (pers.groupby(["ZFP", "ECH"])["licensed_adult"].sum()
                .rename("licenses").reset_index().rename(columns={"ZFP": "ZFM"}))
    hh = men.merge(licenses, on=["ZFM", "ECH"], how="left", validate="one_to_one")
    hh["licenses"] = hh["licenses"].fillna(0)
    hh = hh.dropna(subset=["weight", "cars"])

    level = np.where(hh["cars"] >= hh["licenses"], "all", "some")
    hh["car_availability"] = np.where(hh["cars"] == 0, "none", level)

    people = pers.merge(
        hh[["ZFM", "ECH", "car_availability"]].rename(columns={"ZFM": "ZFP"}),
        on=["ZFP", "ECH"], how="inner", validate="many_to_one").dropna(subset=["weight"])
    return hh, people


def distribution(frame: pd.DataFrame) -> dict:
    total = float(frame["weight"].sum())
    return {lvl: round(100 * float(frame.loc[frame["car_availability"] == lvl,
                                             "weight"].sum()) / total, 2)
            for lvl in LEVELS}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--root", type=Path, default=DATA)
    args = parser.parse_args()

    if not args.root.is_dir():
        print(f"[ERREUR] microdonnées absentes : {args.root}")
        return 1

    men, pers = load(args.root)
    negative = negative_control(pers)
    positive = positive_control(men)
    hh, people = derive(men, pers)

    by_household, by_person = distribution(hh), distribution(people)

    print("=== CONTRÔLE NÉGATIF — la variable P7 est-elle vivante ? ===")
    for code, count in negative["modalities"].items():
        print(f"  {code:8} {count:6}  {negative['labels'].get(code, '')}")
    print(f"  non-réponse : {negative['blank_share_pct']} % de l'ensemble, "
          f"{negative['blank_adults_share_pct']} % des majeurs")
    print(f"  → {negative['verdict']}")

    print("\n=== CONTRÔLE POSITIF — motorisation publiée reproduite ? ===")
    for key in ("cars_per_household", "zero", "one", "two_plus"):
        print(f"  {key:20} mesuré {positive['measured'][key]:7.2f}  "
              f"publié {positive['published'][key]:6.2f}  "
              f"écart {positive['delta'][key]:+6.2f}")
    print(f"  → {'PASSÉ' if positive['passed'] else 'ÉCHEC'}")

    print("\n=== car_availability ===")
    print(f"  {'':22}{'all':>8}{'some':>8}{'none':>8}")
    print(f"  {'ménages (COE0)':22}"
          + "".join(f"{by_household[l]:8.1f}" for l in LEVELS))
    print(f"  {'personnes (COE1)':22}"
          + "".join(f"{by_person[l]:8.1f}" for l in LEVELS))
    print(f"\n  {len(hh)} ménages, {len(people)} personnes appariées")

    if not positive["passed"]:
        print("\n[ÉCHEC] le contrôle positif ne passe pas : la lecture ne reproduit pas la "
              "motorisation publiée, donc la distribution dérivée n'est pas opposable. "
              "Rien n'est écrit — corrigez la pondération ou le filtrage avant de publier.")
        return 1

    payload = {
        "source": "EMC² Toulouse 2023, ProGEDO/ADISP lil-1750 — M6 (voitures), P7 (permis)",
        "derivation": "règle eqasim : all si voitures>=permis (majeurs), some si <, "
                      "none si voitures==0",
        "reference_by_household_coe0": by_household,
        "reference_by_person_coe1": by_person,
        "n_households": int(len(hh)),
        "n_persons": int(len(people)),
        "negative_control": negative,
        "positive_control": positive,
        "caveat": "Cible de NIVEAU seulement. Elle ne dit rien de la RIVALITÉ dans le "
                  "temps (deux membres d'un ménage à une voiture conduisant au même "
                  "instant) : c'est l'objet de l'option B du ticket 018, et aucune "
                  "distribution ne la mesure.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"\n  écrit → {args.out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
