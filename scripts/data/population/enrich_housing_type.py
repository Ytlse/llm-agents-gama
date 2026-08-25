"""enrich_housing_type.py — Le trait « type de logement » du persona (action A2).

Dernière étape d'enrichissement de la population synthétique, dans la même veine que
l'étape 3bis du notebook (zone urbaine/périurbaine/rurale depuis les tables INSEE) :
elle relit un fichier de population, ajoute un champ à `traits_json`, et le réécrit.

Ce qu'elle ajoute : `traits_json["housing_type"]`, le type d'habitat au sens EMC²
(« Individuel isolé », « Individuel accolé », « Petit habitat collectif », « Grand
habitat collectif », « Autres »). Sans lui, la colonne « Type de logement » du journal
de déplacements est écrite vide et l'axe correspondant de la page de synthèse reste
à zéro.

**Le trait est imputé, pas observé.** Aucune source de la chaîne de génération ne le
porte : ni eqasim, ni les tables INSEE mobilisées par le notebook. Il est donc tiré
dans la loi que l'enquête EMC² observe **pour la zone fine du domicile, corrigée de la
taille du ménage** (cf. `llm_module/core/housing_type.py` pour le détail, le levier de
taille du ticket 019 et les garde-fous). Trois conséquences à ne jamais taire :

- la ventilation par type de logement de la page mesure un axe **imputé**, dont la
  loi marginale vient de l'enquête qui sert aussi de cible : elle dit si la
  simulation choisit les mêmes modes *à type de logement donné*, pas si elle place
  correctement les gens dans les logements ;
- un domicile hors de la couche de zones fines n'a pas de type : le trait est absent,
  et il doit le rester. La colonne du journal est alors vide, ce qui n'est pas une
  modalité. Un persona **sans `household_size`** est dans le même cas depuis le ticket
  019 : imputer sur la zone seule ferait rentrer par la fenêtre le gradient aplati que
  le levier de taille corrige ;
- la taille utilisée est la taille **nominale** déclarée par le persona, jamais le
  nombre de membres présents dans le fichier. 118 des 498 grappes d'adresse de
  `toulouse_population_1000.json` sont partielles (filtrage par bbox) : compter les
  présents mettrait des familles de quatre dans des lois de personne seule.

Deux ressources d'accès restreint sont nécessaires (`make zones`, `make housing-type`).
Leur absence est un cas normal : la commande échoue alors avec le message qui dit
laquelle manque et comment la produire, sans jamais imputer à l'aveugle.

`--check` confronte le résultat aux cibles du ticket 019 (part d'individuel isolé par
taille de ménage, **signe** de la pente, couverture du trait) et sort en échec si l'une
d'elles est hors tolérance. Un `None` massif y échoue explicitement : une population
dont le trait manque partout ne « réussit » pas la recette, elle l'invalide.

Usage :
    python -m scripts.data.population.enrich_housing_type data/population/toulouse_population_1000.json
    python -m scripts.data.population.enrich_housing_type data/population/*.json --dry-run
    python -m scripts.data.population.enrich_housing_type data/population/toulouse_population_1000.json --check
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

from llm_module.core.housing_type import (
    MODALITY_KEYS,
    SIZE_MAX,
    SIZE_TRAIT_KEY,
    TRAIT_KEY,
    HousingTypeTable,
    address_key,
    key_for,
    size_bucket,
)

REPO_ROOT = Path(__file__).resolve().parents[3]

# Couverture minimale du trait. En dessous, la population n'est pas exploitable et
# aucune cible n'a de sens — c'est le critère « un None massif doit faire échouer la
# validation, pas la réussir » du ticket 019.
MIN_COVERAGE = 0.80

# Tolérance sur la part d'individuel isolé d'une classe de taille, en points. Le ticket
# demande ± 4 pts ; le bruit d'échantillonnage de la cellule s'y ajoute (2 σ).
TOLERANCE_PT = 4.0

# Sous ce nombre d'adresses, une cellule ne tranche pas. La compter « atteinte » serait
# le motif « vacuité ≠ perfection » : l'absence de mesure produirait le score parfait.
MIN_CELL_ADDRESSES = 20

# Codes de sortie, les mêmes qu'`enrich_personal_bike` — le notebook et le Makefile les
# distinguent : une population de 10 agents n'est pas en faute, elle est trop petite pour
# être jugée, et cela ne doit pas arrêter une chaîne d'enrichissement.
EXIT_OK = 0
EXIT_RESOURCE_MISSING = 1
EXIT_TARGET_MISSED = 2
EXIT_NOT_MEASURABLE = 3

# Préfixe des échecs qui ne mettent en cause que la taille du fichier, pas l'imputation.
NOT_MEASURABLE = "population non mesurable"


def enrich(population: list[dict], table: HousingTypeTable, resolver) -> Counter:
    """Pose `housing_type` sur chaque persona. Renvoie le décompte par modalité.

    Le rattachement des domiciles est fait en un seul appel vectorisé : c'est une
    requête d'index spatial par lot, pas une par persona.
    """
    homes = [(person.get("identity") or {}).get("home") or {} for person in population]
    lats = [home.get("lat") for home in homes]
    lons = [home.get("lon") for home in homes]

    resolvable = [i for i, (la, lo) in enumerate(zip(lats, lons))
                  if la is not None and lo is not None]
    zones = resolver.resolve_many([lats[i] for i in resolvable],
                                  [lons[i] for i in resolvable])
    zone_by_index: dict[int, Optional[object]] = dict(zip(resolvable, zones))

    counts: Counter = Counter()
    for i, person in enumerate(population):
        traits = (person.get("identity") or {}).get("traits_json")
        if traits is None:
            counts["sans_traits"] += 1
            continue
        zone = zone_by_index.get(i)
        if zone is None:
            # Hors couche, ou domicile sans coordonnées : on n'invente pas. Le trait
            # est retiré s'il traînait d'un enrichissement antérieur.
            traits.pop(TRAIT_KEY, None)
            counts["hors_couche"] += 1
            continue
        # Taille NOMINALE du foyer, telle que le persona la déclare : le fichier ne
        # contient pas toujours tous ses membres (cf. le docstring).
        size = size_bucket(traits.get(SIZE_TRAIT_KEY))
        if size is None:
            traits.pop(TRAIT_KEY, None)
            counts["sans_taille"] += 1
            continue
        label = table.housing_type(zone.zf, lats[i], lons[i],
                                   traits.get(SIZE_TRAIT_KEY))
        if label is None:
            traits.pop(TRAIT_KEY, None)
            counts["sans_loi"] += 1
            continue
        traits[TRAIT_KEY] = label
        counts[key_for(label) or "inconnu"] += 1
        # Niveau de repli servi : publié à chaque enrichissement, comme le demande le
        # ticket 019. Une population majoritairement servie par le périmètre n'aurait
        # plus de conditionnement géographique du tout.
        counts[f"repli_{table.level_for(zone.zf)}"] += 1
    return counts


def measure_by_size(population: list[dict]) -> dict[int, dict]:
    """Part d'individuel isolé par classe de taille de ménage, et son effectif utile.

    L'effectif qui compte pour le bruit d'échantillonnage est le nombre d'**adresses**
    distinctes, pas de personas : le tirage porte sur le domicile, et les six membres
    d'un foyer partagent un unique tirage.
    """
    rows: dict[int, dict] = defaultdict(
        lambda: {"n": 0, "isolated": 0, "addresses": set()})
    for person in population:
        identity = person.get("identity") or {}
        traits = identity.get("traits_json") or {}
        label = traits.get(TRAIT_KEY)
        size = size_bucket(traits.get(SIZE_TRAIT_KEY))
        if label is None or size is None:
            continue
        home = identity.get("home") or {}
        row = rows[size]
        row["n"] += 1
        row["isolated"] += int(label == "Individuel isolé")
        if home.get("lat") is not None and home.get("lon") is not None:
            row["addresses"].add((address_key(home["lat"], home["lon"]), size))
    return {size: {"n": row["n"],
                   "isolated_pct": 100.0 * row["isolated"] / row["n"],
                   "n_addresses": len(row["addresses"])}
            for size, row in sorted(rows.items()) if row["n"]}


def report(counts: Counter, table: HousingTypeTable, population: list[dict]) -> list[str]:
    """Distribution obtenue, gradient de taille, replis. Renvoie la liste des échecs.

    L'écart à la loi de l'enquête sur tout le périmètre n'est pas un défaut en soi : la
    population simulée n'occupe pas le périmètre d'enquête de façon uniforme. Il doit
    néanmoins être lu, parce qu'un écart massif signalerait un rattachement de zones qui
    a dérapé. Le **gradient de taille**, lui, est une cible : c'est l'objet du ticket
    019, et son signe est un critère à part entière.
    """
    n = len(population)
    attributed = sum(counts.get(key, 0) for key in MODALITY_KEYS)
    failures: list[str] = []

    print(f"\nTypes de logement imputés : {attributed}/{n} personas "
          f"({100.0 * attributed / n if n else 0:.1f} %)")
    for key in ("hors_couche", "sans_taille", "sans_loi", "sans_traits"):
        if counts.get(key):
            print(f"  {key:26s} {counts[key]:5d} (trait absent, colonne vide)")
    levels = [(level, counts.get(f"repli_{level}", 0))
              for level in ("zone", "secteur", "perimetre")]
    if any(value for _, value in levels):
        print("  niveau de loi servi : " + ", ".join(
            f"{level} {value}" for level, value in levels))
        if attributed and counts.get("repli_zone", 0) / attributed < 0.5:
            print("  [avertissement] moins de la moitié des personas reçoivent la loi "
                  "de LEUR zone : le conditionnement géographique est largement replié")

    if not n or attributed / n < MIN_COVERAGE:
        failures.append(
            f"couverture {100.0 * attributed / n if n else 0:.1f} % < "
            f"{100 * MIN_COVERAGE:.0f} % — trait absent sur trop d'agents : la "
            f"population n'est pas exploitable, et aucune cible ci-dessous n'a de sens")

    if not attributed:
        return failures

    print(f"\n  {'modalité':26s} {'simulée':>9s} {'EMC² (périmètre)':>18s} {'écart':>8s}")
    for key, share in zip(MODALITY_KEYS, table.global_shares):
        got = 100.0 * counts.get(key, 0) / attributed
        target = 100.0 * share
        print(f"  {key:26s} {got:8.2f}% {target:17.2f}% {got - target:+7.2f}")
    l1 = sum(abs(100.0 * counts.get(k, 0) / attributed - 100.0 * s)
             for k, s in zip(MODALITY_KEYS, table.global_shares))
    print(f"  {'écart L1 cumulé':26s} {l1:8.2f} points")
    print("  (la population n'occupe pas le périmètre d'enquête uniformément : cet "
          "écart\n   se lit, il ne se valide pas — cf. le gradient de taille ci-dessous)")

    return failures + check_size_gradient(measure_by_size(population), table)


def check_size_gradient(measured: dict[int, dict],
                        table: HousingTypeTable) -> list[str]:
    """Le critère de recette du ticket 019 : le gradient de taille, valeurs ET signe."""
    targets = table.observed_isolated_share_by_size()
    failures: list[str] = []
    print("\n── Part d'individuel isolé par taille de ménage (ticket 019) ────────────")
    if not targets:
        print("  [cibles non servies : ré-exportez la table (make housing-type) pour "
              "que son bloc de validation soit présent]")
        return ["la table ne porte pas les parts observées par taille : le critère de "
                "recette du ticket 019 ne peut pas être évalué"]

    print(f"  {'taille':>7s} {'simulée':>9s} {'EMC²':>8s} {'écart':>7s} "
          f"{'marge':>7s} {'adresses':>9s}")
    conclusive = 0
    for size, row in measured.items():
        target = targets.get(size)
        if target is None:
            print(f"  {size:>7d} {row['isolated_pct']:8.1f}%   (pas de cible)")
            continue
        addresses = row["n_addresses"]
        # Marge = tolérance du ticket + 2 σ de la cellule, σ binomial sur les ADRESSES :
        # à 42 adresses, l'écart-type d'une proportion autour de 55 % vaut déjà 7,7 pts.
        p = target / 100.0
        sigma = 100.0 * math.sqrt(p * (1 - p) / addresses) if addresses else float("inf")
        margin = TOLERANCE_PT + 2 * sigma
        gap = row["isolated_pct"] - target
        if addresses < MIN_CELL_ADDRESSES:
            verdict = f"NON CONCLUANT ({addresses} adresses)"
        elif abs(gap) <= margin:
            verdict, conclusive = "ok", conclusive + 1
        else:
            verdict, conclusive = "ÉCHEC", conclusive + 1
            failures.append(
                f"taille {size} : {row['isolated_pct']:.1f} % d'individuel isolé pour "
                f"{target:.1f} % observés (écart {gap:+.1f} pt, marge ±{margin:.1f})")
        print(f"  {size:>7d} {row['isolated_pct']:8.1f}% {target:7.1f}% {gap:+7.1f} "
              f"{margin:7.1f} {addresses:9d}   {verdict}")

    # Le signe de la pente est un critère à part entière : c'est lui qui était faux
    # avant le ticket 019. Il n'est jugé que si les DEUX cibles sont servies et qu'elles
    # décrivent une pente non nulle — un `targets.get(size, 0)` par défaut fabriquerait
    # une pente attendue à partir d'une cible absente, et jugerait contre du vide.
    low, high = measured.get(1), measured.get(SIZE_MAX)
    expected = (None if targets.get(1) is None or targets.get(SIZE_MAX) is None
                else targets[SIZE_MAX] - targets[1])
    if low is not None and high is not None and expected:
        slope = high["isolated_pct"] - low["isolated_pct"]
        ok = slope > 0 if expected > 0 else slope < 0
        print(f"  pente personne seule → ménage de {SIZE_MAX}+ : {slope:+.1f} pt "
              f"(observée {expected:+.1f} pt)   {'ok' if ok else 'ÉCHEC'}")
        if not ok:
            failures.append(
                f"la pente entre la personne seule et le ménage de {SIZE_MAX}+ vaut "
                f"{slope:+.1f} pt pour {expected:+.1f} pt observés — c'est le défaut "
                f"même que le ticket 019 corrige, et son signe est un critère à part")
        conclusive += 1
    else:
        print(f"  pente personne seule → ménage de {SIZE_MAX}+ : non jugée (une des deux "
              f"classes de taille est absente, ou la pente observée est nulle)")
    if not conclusive:
        failures.append(
            f"{NOT_MEASURABLE} : aucun contrôle n'a tranché sur le gradient de taille. "
            f"Elle est enrichie, mais rien n'est vérifié — ne pas lire ce rapport comme "
            f"un succès")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("population", type=Path, nargs="+",
                        help="Fichiers de population JSON à enrichir (modifiés en place)")
    parser.add_argument("--table", type=Path, default=None,
                        help="Table du type de logement (défaut : llm_module/data/)")
    parser.add_argument("--zones", type=Path, default=None,
                        help="Couche de zones fines (défaut : llm_module/data/)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Calcule et rapporte sans réécrire les fichiers")
    parser.add_argument("--check", action="store_true",
                        help="Sort en échec si une cible du ticket 019 est hors tolérance")
    args = parser.parse_args()

    from llm_module.core.zone_resolver import ZoneResolver

    feature_spec = REPO_ROOT / "scripts" / "progedo_logit" / "feature_spec.json"
    try:
        table = HousingTypeTable.load(args.table)
        resolver = ZoneResolver.load(args.zones,
                                     feature_spec if feature_spec.exists() else None)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[ERREUR] {exc}", file=sys.stderr)
        return EXIT_RESOURCE_MISSING

    print(f"Table exportée le {table.meta.get('exported_at', '?')} — "
          f"{table.meta.get('conditioning', 'conditionnement non documenté')}")

    all_failures: list[tuple[Path, list[str]]] = []
    for path in args.population:
        if not path.exists():
            print(f"[ERREUR] Population introuvable : {path}", file=sys.stderr)
            return EXIT_RESOURCE_MISSING
        population = json.loads(path.read_text(encoding="utf-8"))
        counts = enrich(population, table, resolver)
        print(f"\n=== {path}")
        failures = report(counts, table, population)
        if failures:
            all_failures.append((path, failures))
        if args.dry_run:
            print("  [dry-run] fichier non réécrit")
            continue
        # Écriture atomique : un plantage en cours d'écriture ne doit pas laisser une
        # population tronquée derrière lui.
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(population, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
        print(f"  écrit → {path}")

    if all_failures:
        print("\n── Cibles hors tolérance ───────────────────────────────────────────────")
        for path, failures in all_failures:
            for failure in failures:
                print(f"  [{path.name}] {failure}")
        if args.check:
            # Si TOUS les échecs sont des « pas assez de matière », le fichier n'est pas
            # fautif : il est trop petit pour être jugé. Code distinct, que l'appelant
            # peut traiter autrement qu'une cible démentie.
            missed = [failure for _, failures in all_failures for failure in failures
                      if not failure.startswith(NOT_MEASURABLE)]
            if not missed:
                print(f"\n  → code {EXIT_NOT_MEASURABLE} : population enrichie mais NON "
                      f"VALIDÉE (pas assez d'adresses par classe de taille pour "
                      f"trancher), et non « en échec ». Aucune cible servie n'est "
                      f"démentie.")
                return EXIT_NOT_MEASURABLE
            return EXIT_TARGET_MISSED
        print("  (informatif : relancez avec --check pour en faire un échec)")
    elif args.check:
        print("\nToutes les cibles servies sont dans la tolérance.")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
