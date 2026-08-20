"""fix_minor_traits.py — Rendre aux mineurs leur âge (ticket 008, A1.b).

Correctif **de surface** sur une population déjà générée. Il existe parce que la
cause racine est dans eqasim (`config_toulouse.yml`, `synthesis/population/`) et que
la relancer suppose l'accès aux données sources, hors dépôt. Ce script débloque le
run sans attendre cet accès ; les garde-fous d'eqasim (A1.a) sont ce qui rendra le
correctif inutile au prochain cycle de génération.

**Ce qu'il corrige.** L'appariement HTS perdait `age_class` (vivier de donneurs
réduit au seul département 31, dégradation qui retire les colonnes par la fin), et
un `bool(nan)` valant `True` distribuait le permis à toute personne non appariée.
Résultat : 131 des 165 mineurs de la population portaient `has_driving_license`,
et un écolier de neuf ans arrivait au LLM avec la chaîne d'activités d'un actif.

Cinq transformations, dans l'ordre :

1. `has_driving_license → false` sous 18 ans ;
2. `purpose: "work" → "education"` pour les scolaires et les étudiants ;
3. recalcul de `travel_purposes` d'après les activités corrigées ;
4. recalcul de `car_availability` par ménage, les permis de mineurs ne comptant plus ;
5. `personal_bike: "VAE" → "vélo normal"` sous 14 ans.

**Ce qu'il ne corrige pas.** Les *chaînes d'activités* restent celles de donneurs
adultes : horaires de départ d'actifs, destinations d'actifs. Renommer `work` en
`education` ne rapproche pas l'école du domicile, et un enfant peut donc rester
attendu à 8 h à l'autre bout de l'agglomération. C'est la limite assumée du
correctif de surface, rappelée dans son rapport de sortie à chaque exécution.

Idempotent : une seconde exécution ne change rien (les règles sont des états
cibles, pas des incréments).

Usage :
    python -m scripts.data.population.fix_minor_traits data/population/toulouse_population_1000.json
    python -m scripts.data.population.fix_minor_traits data/population/*.json --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Âge du permis, et âge en dessous duquel un vélo à assistance électrique n'a pas
# de sens. Valeurs en dur : ce sont des seuils légaux et physiques, pas des réglages.
DRIVING_AGE = 18
VAE_MIN_AGE = 14

# Motif d'activité → libellé de `travel_purposes`, **le même mapping** que
# `_PURPOSE_FR` de eqasim-toulouse/synthesis/population/llm_agents.py. Toute
# divergence ferait diverger la population corrigée du format de génération.
PURPOSE_FR = {
    "work": "Travail",
    "education": "Etude",
    "shop": "Achats",
}

# Un agent « en études » au sens de la règle 2. `professional_activity` porte selon
# les versions le code eqasim (`student`, `under14`) ou son libellé lisible
# (`Student`, `Child (under 14)`) : les deux sont acceptés.
STUDENT_ACTIVITIES = {"student", "under14", "Student", "Child (under 14)"}
STUDENT_OCCUPATION = "Scolaire (jusqu'au Bac)"


def _is_student(traits: dict) -> bool:
    return (
        str(traits.get("professional_activity", "")) in STUDENT_ACTIVITIES
        or traits.get("main_occupation") == STUDENT_OCCUPATION
    )


def _home_key(person: dict) -> tuple | None:
    """Clé de ménage : les coordonnées du domicile, arrondies.

    Faute de `household_id` dans la population exportée, le domicile *est* le
    ménage. L'arrondi (≈ 1 cm) absorbe les écarts de sérialisation sans jamais
    fusionner deux adresses distinctes.
    """
    home = (person.get("identity") or {}).get("home") or {}
    lat, lon = home.get("lat"), home.get("lon")
    if lat is None or lon is None:
        return None
    return (round(float(lat), 7), round(float(lon), 7))


def fix(population: list[dict]) -> Counter:
    """Applique les cinq règles en place. Renvoie le décompte des corrections."""
    counts: Counter = Counter()

    # ── Règles 1, 2, 3, 5 — au niveau de la personne ─────────────────────────
    for person in population:
        identity = person.get("identity") or {}
        traits = identity.get("traits_json")
        if traits is None:
            counts["sans_traits"] += 1
            continue
        counts["personnes"] += 1
        age = traits.get("age")
        age = int(age) if age is not None else None

        # 1. Personne ne conduit avant l'âge légal.
        if age is not None and age < DRIVING_AGE and traits.get("has_driving_license"):
            traits["has_driving_license"] = False
            counts["permis_retires"] += 1

        # 2. Un scolaire va à l'école, pas au travail. Le motif `work` d'un donneur
        #    adulte devient `education` — le lieu, lui, reste celui du donneur.
        activities = identity.get("activities") or []
        if _is_student(traits):
            counts["scolaires"] += 1
            for activity in activities:
                if activity.get("purpose") == "work":
                    activity["purpose"] = "education"
                    counts["motifs_reclasses"] += 1

        # 3. `travel_purposes` découle des activités : il se recalcule, il ne se
        #    corrige pas. Ordre stable (celui de PURPOSE_FR) pour que deux
        #    exécutions produisent un fichier identique octet pour octet.
        purposes = {a.get("purpose") for a in activities}
        recomputed = [label for key, label in PURPOSE_FR.items() if key in purposes]
        if traits.get("travel_purposes") != recomputed:
            traits["travel_purposes"] = recomputed
            counts["travel_purposes_recalcules"] += 1

        # 5. Pas de VAE avant 14 ans (tirage aléatoire d'eqasim, sans filtre d'âge).
        if age is not None and age < VAE_MIN_AGE and traits.get("personal_bike") == "VAE":
            traits["personal_bike"] = "vélo normal"
            counts["vae_declasses"] += 1

    # ── Règle 4 — au niveau du ménage, après le retrait des permis ───────────
    #
    # ⚠ LIMITE MESURÉE : le ménage est reconstitué par coordonnées du domicile, mais
    # la population exportée est un ÉCHANTILLON — 127 des 547 « ménages » de
    # toulouse_population_1000.json comptent moins de membres présents que ne
    # l'annonce leur `household_size` (2 personnes pour un ménage de 3). Les permis
    # des membres absents ne sont donc pas comptés, `cars >= licenses` passe trop
    # souvent, et `car_availability` penche vers « all » — ce qui remonte jusqu'au
    # prompt via le narratif de persona (« voiture toujours dispo » au lieu de « à
    # partager »). C'est signalé (`menages_incomplets`) plutôt que subi : la
    # correction propre exige un `household_id` à la génération.
    licenses_by_home: dict[tuple, int] = defaultdict(int)
    cars_by_home: dict[tuple, int] = {}
    members_by_home: dict[tuple, int] = defaultdict(int)
    declared_size_by_home: dict[tuple, int] = {}
    for person in population:
        key = _home_key(person)
        traits = (person.get("identity") or {}).get("traits_json")
        if key is None or traits is None:
            continue
        age = traits.get("age")
        if traits.get("has_driving_license") and (age is None or int(age) >= DRIVING_AGE):
            licenses_by_home[key] += 1
        cars = int(traits.get("number_of_cars", 0) or 0)
        # Le champ est censé être une propriété du ménage ; s'il diverge entre
        # colocataires, on retient le maximum et on le signale.
        if key in cars_by_home and cars_by_home[key] != cars:
            counts["menages_number_of_cars_incoherent"] += 1
        cars_by_home[key] = max(cars_by_home.get(key, 0), cars)
        members_by_home[key] += 1
        declared_size_by_home[key] = max(
            declared_size_by_home.get(key, 0),
            int(traits.get("household_size", 0) or 0))

    for key, declared in declared_size_by_home.items():
        if declared > members_by_home[key]:
            counts["menages_incomplets"] += 1
        if cars_by_home.get(key, 0) > 0 and licenses_by_home[key] == 0:
            # Voiture au foyer, personne pour la conduire parmi les membres PRÉSENTS.
            # Les non-conducteurs y sont pourtant éligibles au mode passager
            # (`_is_car_passenger` ne teste que `household_size > 1`) : ils seraient
            # conduits par un adulte qui n'existe pas dans les données.
            counts["menages_voiture_sans_conducteur"] += 1

    for person in population:
        key = _home_key(person)
        traits = (person.get("identity") or {}).get("traits_json")
        if traits is None:
            continue
        if key is None:
            counts["sans_domicile"] += 1
            continue
        cars = cars_by_home[key]
        licenses = licenses_by_home[key]
        if cars == 0:
            availability = "none"
        elif cars >= licenses:
            availability = "all"
        else:
            availability = "some"
        if traits.get("car_availability") != availability:
            traits["car_availability"] = availability
            counts["car_availability_recalcules"] += 1
        counts[f"car_availability::{availability}"] += 1

    counts["menages"] = len(cars_by_home)
    return counts


def report(population: list[dict], counts: Counter) -> None:
    """Corrections appliquées, état résiduel, et limite non couverte."""
    traits = [(p.get("identity") or {}).get("traits_json") or {} for p in population]
    minors = [t for t in traits if (t.get("age") or 0) < DRIVING_AGE]
    purposes = Counter(a.get("purpose")
                       for p in population
                       for a in ((p.get("identity") or {}).get("activities") or []))

    print(f"\n  {counts['personnes']} personnes, {counts['menages']} ménages "
          f"(regroupés par coordonnées du domicile)")
    for key, label in (
        ("permis_retires",              "permis retirés (< 18 ans)"),
        ("motifs_reclasses",            "activités work → education"),
        ("travel_purposes_recalcules",  "travel_purposes recalculés"),
        ("car_availability_recalcules", "car_availability recalculés"),
        ("vae_declasses",               "VAE → vélo normal (< 14 ans)"),
    ):
        print(f"  {label:38s} {counts.get(key, 0):5d}")
    for key, label in (
        ("sans_traits",   "personas sans traits_json"),
        ("sans_domicile", "personas sans domicile (ménage indéterminé)"),
        ("menages_number_of_cars_incoherent",
         "number_of_cars divergent dans un ménage"),
        ("menages_incomplets",
         "ménages partiellement exportés"),
        ("menages_voiture_sans_conducteur",
         "ménages : voiture, aucun conducteur"),
    ):
        if counts.get(key):
            print(f"  ⚠ {label:36s} {counts[key]:5d}")

    print("\n  État après correction :")
    print(f"    mineurs avec permis                  "
          f"{sum(1 for t in minors if t.get('has_driving_license')):5d}  (cible 0)")
    print(f"    activités « education »              {purposes.get('education', 0):5d}  (cible > 120)")
    print(f"    activités « work »                   {purposes.get('work', 0):5d}")
    print("    car_availability : " + ", ".join(
        f"{k} {counts.get('car_availability::' + k, 0)}" for k in ("all", "some", "none")))

    print("\n  ⚠ Limite non couverte par ce script (ticket 008, D1) : les chaînes "
          "d'activités\n    restent celles de donneurs adultes — horaires de départ "
          "et destinations d'actifs.\n    Renommer `work` en `education` ne rapproche "
          "pas l'école du domicile. Seuls les\n    garde-fous eqasim (A1.a) et une "
          "regénération de population lèvent cette limite.")

    if counts.get("menages_incomplets") or counts.get("menages_voiture_sans_conducteur"):
        print("\n  ⚠ Ménage reconstitué par coordonnées, sur un échantillon : la règle 4 "
              "compte les\n    permis des membres PRÉSENTS seulement. Un ménage "
              "partiellement exporté a donc\n    moins de permis qu'en réalité, et son "
              "`car_availability` penche vers « all ».\n    Là où aucun conducteur n'est "
              "présent, les non-conducteurs restent éligibles au\n    mode passager "
              "(`_is_car_passenger` ne teste que `household_size > 1`) : ils sont\n    "
              "conduits par un adulte absent des données. Correction propre : un "
              "`household_id`\n    à la génération, ou un trait "
              "`household_has_licensed_driver` posé ici et lu par\n    le contrôleur.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("population", type=Path, nargs="+",
                        help="Fichiers de population JSON à corriger (modifiés en place)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Calcule et rapporte sans réécrire les fichiers")
    args = parser.parse_args()

    for path in args.population:
        if not path.exists():
            print(f"[ERREUR] Population introuvable : {path}", file=sys.stderr)
            return 1
        population = json.loads(path.read_text(encoding="utf-8"))
        counts = fix(population)
        print(f"\n=== {path}")
        report(population, counts)
        if args.dry_run:
            print("\n  [dry-run] fichier non réécrit")
            continue
        # Écriture atomique : un plantage en cours d'écriture ne doit pas laisser
        # une population tronquée derrière lui.
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(population, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
        print(f"\n  écrit → {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
