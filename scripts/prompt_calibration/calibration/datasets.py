"""Jeux d'évaluation gelés, stratifiés, versionnés — phase 0.2 du ticket 004.

- **Affectation stable par hash** : ``sha256(agent_id) % 100`` → train [0-69],
  val [70-84], test [85-99]. Un agent ne change jamais de jeu, même si les
  fichiers sont régénérés ou que des données s'ajoutent.
- **Gel et versionnage** : ``calibration_datasets/vN/{train,val,test}.jsonl``
  + ``manifest.yaml`` (hash des sources, date, effectifs par strate). Un jeu
  n'est **jamais modifié** — toute évolution = nouveau ``vN+1/``.
- **Rapport de couverture** : effectifs par catégorie Cerema (âge, occupation,
  genre, motif, distance) pour chaque jeu ; catégorie sous le seuil = warning
  explicite imprimé à la génération.

Rôles : train = boucle d'optimisation ; val = early stopping ; test = une
seule éval en fin de campagne, jamais vu par la boucle.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .config import DATASET_SPLITS, COVERAGE_MIN_COUNT, SCREEN_MAX_BUCKET
from .metadata import strip_memory_section

# Catégories Cerema attendues par dimension (cerema_values.yaml) — la
# couverture est mesurée contre ces marginales.
CEREMA_CATEGORIES = {
    "age_cat": ["5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
                "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74",
                "75-130"],
    "occupation": ["scolaire", "etudiant", "actif_temps_plein",
                   "actif_temps_partiel", "chomeur_recherche_emploi",
                   "personne_au_foyer", "Retraité"],
    "genre": ["Homme", "Femme"],
    "motif": ["travail", "etudes", "achats"],
    "dist_cat": ["0-1km", "1-2km", "2-5km", "5-10km", "10-20km", "20-50km",
                 "plus_50km"],
}


def _bucket(agent_id: str) -> int:
    """Bucket stable [0, 100) d'un agent (sha256, indépendant du process)."""
    return int(hashlib.sha256(str(agent_id).encode()).hexdigest(), 16) % 100


def split_of(agent_id: str) -> str:
    """Jeu d'appartenance d'un agent — stable, indépendant du run et du process
    (sha256, pas ``hash()`` qui est salé par interpréteur)."""
    bucket = _bucket(agent_id)
    for name, lo, hi in DATASET_SPLITS:
        if lo <= bucket < hi:
            return name
    raise AssertionError(f"bucket {bucket} hors de tout intervalle")


def in_screen(agent_id: str) -> bool:
    """Un agent train appartient-il au sous-échantillon de screening (~20 %) ?

    Screening = buckets [0, SCREEN_MAX_BUCKET), strictement inclus dans le train
    ([0, 70)) → mêmes personas, réutilisation du cache d'éval (phase 4.2, DD).
    """
    return _bucket(agent_id) < SCREEN_MAX_BUCKET


def coverage_report(records_by_split: dict[str, list[dict]],
                    min_count: int = COVERAGE_MIN_COUNT,
                    ) -> tuple[dict, list[str]]:
    """Effectifs par dimension × catégorie × jeu, et warnings de couverture.

    Renvoie ``(coverage, warnings)`` : ``coverage[split][dim][cat] = n`` sur
    toutes les catégories Cerema (0 si absente) ; un warning par catégorie
    sous ``min_count`` dans un jeu.
    """
    coverage: dict = {}
    warnings: list[str] = []
    for split, records in records_by_split.items():
        coverage[split] = {}
        for dim, expected in CEREMA_CATEGORIES.items():
            counts = Counter(r[dim] for r in records if r.get(dim) is not None)
            coverage[split][dim] = {cat: counts.get(cat, 0) for cat in expected}
            for cat in expected:
                n = counts.get(cat, 0)
                if n < min_count:
                    warnings.append(
                        f"{split}/{dim}/{cat}: effectif {n} < {min_count}")
    return coverage, warnings


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_datasets(records: list[dict],
                   out_dir: str | Path,
                   version: str,
                   sources: dict[str, str | Path] | None = None,
                   min_count: int = COVERAGE_MIN_COUNT,
                   ) -> Path:
    """Écrit ``out_dir/version/{train,val,test}.jsonl`` + ``manifest.yaml``.

    Les jeux sont **gelés** : si le répertoire de version existe déjà, lève
    ``FileExistsError`` — toute évolution passe par une nouvelle version.
    Le rapport de couverture est imprimé et archivé dans le manifest.
    """
    version_dir = Path(out_dir) / version
    if version_dir.exists():
        raise FileExistsError(
            f"{version_dir} existe déjà : les jeux sont gelés, "
            f"créer une nouvelle version au lieu de modifier celle-ci.")
    version_dir.mkdir(parents=True)

    records_by_split: dict[str, list[dict]] = {name: [] for name, _, _ in DATASET_SPLITS}
    for record in records:
        split = split_of(record["agent_id"])
        # Phase 0.2 — les jeux val/test ne doivent pas dépendre de la mémoire
        # STM/LTM du run source (non reproductible) : on retire la section
        # ``**Historique :**`` du bloc persona (le train la garde : il ne sert
        # qu'à la boucle d'optimisation, pas à la mesure de référence).
        if split in ("val", "test") and record.get("section"):
            record = {**record, "section": strip_memory_section(record["section"])}
        records_by_split[split].append(record)

    # Jeu de screening (phase 4.2, DD) : sous-ensemble du train (~20 %), gelé lui
    # aussi. Mêmes records que le train → cache d'éval partagé.
    records_by_split["screen"] = [r for r in records_by_split["train"]
                                  if in_screen(r["agent_id"])]

    for split, split_records in records_by_split.items():
        with open(version_dir / f"{split}.jsonl", "w", encoding="utf-8") as f:
            for record in split_records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    coverage, warnings = coverage_report(records_by_split, min_count)
    manifest = {
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "split_rule": "sha256(agent_id) % 100 -> train [0,70), val [70,85), test [85,100)",
        "sources": {name: {"path": str(path), "sha256": _sha256_file(Path(path))}
                    for name, path in (sources or {}).items()},
        "counts": {split: {"records": len(recs),
                           "agents": len({r["agent_id"] for r in recs})}
                   for split, recs in records_by_split.items()},
        "coverage_min_count": min_count,
        "coverage": coverage,
        "coverage_warnings": warnings,
    }
    import yaml
    with open(version_dir / "manifest.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(manifest, f, allow_unicode=True, sort_keys=False)

    for split, recs in records_by_split.items():
        agents = len({r["agent_id"] for r in recs})
        print(f"[{version}] {split}: {len(recs)} décisions, {agents} agents")
    if warnings:
        print(f"[{version}] ⚠ {len(warnings)} strate(s) sous le seuil "
              f"de {min_count} :")
        for w in warnings:
            print(f"  - {w}")
    else:
        print(f"[{version}] couverture complète (seuil {min_count})")
    return version_dir


def _main() -> int:
    """CLI : génère une version de jeux gelés depuis un répertoire d'expérience.

    Usage : python -m calibration.datasets <experiment_dir> <out_dir> <version>
    Ex.    : python -m calibration.datasets ../../experiments/current \\
             calibration_datasets v1
    """
    import argparse
    from .exchanges import itinerary_entries
    from .metadata import load_population, build_decision_records

    parser = argparse.ArgumentParser(description=_main.__doc__)
    parser.add_argument("experiment_dir", type=Path)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("version")
    args = parser.parse_args()

    exchanges_path = args.experiment_dir / "llm_exchanges.jsonl"
    population_path = next(args.experiment_dir.glob("population_*[0-9].json"))
    entries = itinerary_entries(exchanges_path)
    traits = load_population(population_path)
    records, anomalies = build_decision_records(entries, traits)
    if anomalies:
        print(f"⚠ {len(anomalies)} section(s) non rattachée(s) — génération refusée "
              f"(critère phase 0 : 100 % de jointure) :")
        for a in anomalies[:10]:
            print(f"  - {a}")
        return 1
    build_datasets(records, args.out_dir, args.version,
                   sources={"llm_exchanges": exchanges_path,
                            "population": population_path})
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
