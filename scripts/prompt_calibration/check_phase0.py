"""Critère d'acceptation de la phase 0 (ticket 004).

Vérifie sur une expérience réelle que 100 % des entrées `itinary_multi_agent`
du `llm_exchanges.jsonl` sont rattachées à leurs métadonnées exactes par la
jointure `agent_id → population_N.json` (genre issu de `traits_json.gender`,
zéro inférence). Imprime le rapport de couverture des jeux gelés.

Usage : python check_phase0.py [experiment_dir]   (défaut : experiments/current)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from calibration.exchanges import itinerary_entries
from calibration.metadata import load_population, build_decision_records
from calibration.datasets import split_of, coverage_report


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    experiment_dir = Path(sys.argv[1]) if len(sys.argv) > 1 \
        else project_root / "experiments" / "current"

    exchanges_path = experiment_dir / "llm_exchanges.jsonl"
    population_path = next(experiment_dir.glob("population_*[0-9].json"))
    print(f"Expérience : {experiment_dir}")
    print(f"Population : {population_path.name}")

    entries = itinerary_entries(exchanges_path)
    traits = load_population(population_path)
    records, anomalies = build_decision_records(entries, traits)

    n_sections = len(records) + len(anomalies)
    rate = 100.0 * len(records) / n_sections if n_sections else 0.0
    print(f"\nEntrées itinary_multi_agent : {len(entries)}")
    print(f"Sections persona            : {n_sections}")
    print(f"Rattachées (jointure exacte): {len(records)}  ({rate:.1f} %)")
    print(f"Agents distincts            : {len({r['agent_id'] for r in records})}")

    if anomalies:
        print(f"\n✗ ÉCHEC — {len(anomalies)} section(s) non rattachée(s) :")
        for a in anomalies[:10]:
            print(f"  - {a}")
        return 1

    records_by_split: dict[str, list[dict]] = {"train": [], "val": [], "test": []}
    for r in records:
        records_by_split[split_of(r["agent_id"])].append(r)
    print("\nRépartition des jeux (affectation stable par hash) :")
    for split, recs in records_by_split.items():
        print(f"  {split:5s}: {len(recs):5d} décisions, "
              f"{len({r['agent_id'] for r in recs}):4d} agents")

    _, warnings = coverage_report(records_by_split)
    if warnings:
        print(f"\n⚠ Couverture : {len(warnings)} strate(s) sous le seuil :")
        for w in warnings:
            print(f"  - {w}")
    else:
        print("\nCouverture complète sur toutes les marginales Cerema.")

    print("\n✓ Critère phase 0 satisfait : 100 % des sections rattachées, "
          "genre issu de traits_json.gender.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
