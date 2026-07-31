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
dans la loi que l'enquête EMC² observe **pour la zone fine du domicile**
(cf. `llm_module/core/housing_type.py` pour le détail et les garde-fous). Deux
conséquences à ne jamais taire :

- la ventilation par type de logement de la page mesure un axe **imputé**, dont la
  loi marginale vient de l'enquête qui sert aussi de cible : elle dit si la
  simulation choisit les mêmes modes *à type de logement donné*, pas si elle place
  correctement les gens dans les logements ;
- un domicile hors de la couche de zones fines n'a pas de type : le trait est absent,
  et il doit le rester. La colonne du journal est alors vide, ce qui n'est pas une
  modalité.

Deux ressources d'accès restreint sont nécessaires (`make zones`, `make housing-type`).
Leur absence est un cas normal : la commande échoue alors avec le message qui dit
laquelle manque et comment la produire, sans jamais imputer à l'aveugle.

Usage :
    python -m scripts.data.population.enrich_housing_type data/population/toulouse_population_1000.json
    python -m scripts.data.population.enrich_housing_type data/population/*.json --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

from llm_module.core.housing_type import (
    MODALITY_KEYS,
    TRAIT_KEY,
    HousingTypeTable,
    key_for,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


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
        label = table.housing_type(zone.zf, lats[i], lons[i])
        if label is None:
            traits.pop(TRAIT_KEY, None)
            counts["sans_loi"] += 1
            continue
        traits[TRAIT_KEY] = label
        counts[key_for(label) or "inconnu"] += 1
    return counts


def report(counts: Counter, table: HousingTypeTable, n: int) -> None:
    """Distribution obtenue, en regard de la loi de l'enquête sur tout le périmètre.

    L'écart n'est pas un défaut en soi : la population simulée n'occupe pas le
    périmètre d'enquête de façon uniforme. Il doit néanmoins être lu, parce qu'un
    écart massif signalerait un rattachement de zones qui a dérapé.
    """
    attributed = sum(counts.get(key, 0) for key in MODALITY_KEYS)
    print(f"\nTypes de logement imputés : {attributed}/{n} personas")
    for key in ("hors_couche", "sans_loi", "sans_traits"):
        if counts.get(key):
            print(f"  {key:26s} {counts[key]:5d} (trait absent, colonne vide)")
    if not attributed:
        return
    print(f"\n  {'modalité':26s} {'simulée':>9s} {'EMC² (périmètre)':>18s} {'écart':>8s}")
    for key, share in zip(MODALITY_KEYS, table.global_shares):
        got = 100.0 * counts.get(key, 0) / attributed
        target = 100.0 * share
        print(f"  {key:26s} {got:8.2f}% {target:17.2f}% {got - target:+7.2f}")
    l1 = sum(abs(100.0 * counts.get(k, 0) / attributed - 100.0 * s)
             for k, s in zip(MODALITY_KEYS, table.global_shares))
    print(f"  {'écart L1 cumulé':26s} {l1:8.2f} points")


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
    args = parser.parse_args()

    from llm_module.core.zone_resolver import ZoneResolver

    feature_spec = REPO_ROOT / "scripts" / "progedo_logit" / "feature_spec.json"
    try:
        table = HousingTypeTable.load(args.table)
        resolver = ZoneResolver.load(args.zones,
                                     feature_spec if feature_spec.exists() else None)
    except FileNotFoundError as exc:
        print(f"[ERREUR] {exc}", file=sys.stderr)
        return 1

    for path in args.population:
        if not path.exists():
            print(f"[ERREUR] Population introuvable : {path}", file=sys.stderr)
            return 1
        population = json.loads(path.read_text(encoding="utf-8"))
        counts = enrich(population, table, resolver)
        print(f"\n=== {path}")
        report(counts, table, len(population))
        if args.dry_run:
            print("  [dry-run] fichier non réécrit")
            continue
        # Écriture atomique : un plantage en cours d'écriture ne doit pas laisser une
        # population tronquée derrière lui.
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(population, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
        print(f"  écrit → {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
