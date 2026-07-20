"""Tests de la phase 0.2 — affectation stable par hash, gel des versions,
manifest et rapport de couverture."""

import json

import pytest
import yaml

from calibration.datasets import split_of, build_datasets, coverage_report
from calibration.config import DATASET_SPLITS


def test_split_of_stable():
    # Valeurs figées : si ce test casse, la règle d'affectation a changé et
    # TOUS les jeux gelés existants sont invalidés — c'est volontairement dur.
    assert [split_of(a) for a in ("503036", "5327", "19826", "42")] == \
        [split_of(a) for a in ("503036", "5327", "19826", "42")]
    snapshot = {a: split_of(a) for a in ("503036", "5327", "19826", "42")}
    assert snapshot == {"503036": "train", "5327": "test",
                        "19826": "train", "42": "train"}


def test_split_of_proportions():
    counts = {"train": 0, "val": 0, "test": 0}
    n = 10_000
    for i in range(n):
        counts[split_of(str(i))] += 1
    for name, lo, hi in DATASET_SPLITS:
        expected = (hi - lo) / 100
        assert counts[name] / n == pytest.approx(expected, abs=0.03)


def _record(agent_id, **overrides):
    base = {"agent_id": agent_id, "genre": "Homme", "age": 30,
            "age_cat": "30-34", "occupation": "actif_temps_plein",
            "motif": "travail", "dist_km": 3.0, "dist_cat": "2-5km",
            "context": "", "section": "--- agent_id=… ---"}
    base.update(overrides)
    return base


def test_coverage_report_warnings():
    coverage, warnings = coverage_report(
        {"train": [_record(str(i)) for i in range(10)]}, min_count=5)
    assert coverage["train"]["age_cat"]["30-34"] == 10
    assert coverage["train"]["age_cat"]["5-9"] == 0
    assert "train/age_cat/5-9: effectif 0 < 5" in warnings
    assert not any(w.startswith("train/age_cat/30-34") for w in warnings)


def test_build_datasets_gel_et_manifest(tmp_path):
    src = tmp_path / "source.jsonl"
    src.write_text("{}", encoding="utf-8")
    records = [_record(str(i)) for i in range(50)]

    version_dir = build_datasets(records, tmp_path / "ds", "v1",
                                 sources={"llm_exchanges": src})

    total = 0
    for split in ("train", "val", "test"):
        lines = (version_dir / f"{split}.jsonl").read_text().splitlines()
        for line in lines:
            assert split_of(json.loads(line)["agent_id"]) == split
        total += len(lines)
    assert total == 50

    # Jeu de screening (phase 4.2) : sous-ensemble STRICT du train (overlay, pas
    # une partition) → mêmes agents, présents aussi dans train.jsonl.
    from calibration.datasets import in_screen
    train_ids = {json.loads(l)["agent_id"]
                 for l in (version_dir / "train.jsonl").read_text().splitlines()}
    screen_ids = {json.loads(l)["agent_id"]
                  for l in (version_dir / "screen.jsonl").read_text().splitlines()}
    assert screen_ids <= train_ids
    assert all(in_screen(aid) for aid in screen_ids)

    manifest = yaml.safe_load((version_dir / "manifest.yaml").read_text())
    assert manifest["version"] == "v1"
    assert manifest["sources"]["llm_exchanges"]["sha256"]
    # La partition train/val/test somme à 50 (screen est un overlay, non compté).
    assert sum(manifest["counts"][s]["records"] for s in ("train", "val", "test")) == 50
    assert manifest["coverage_warnings"]  # petits effectifs → warnings attendus

    # Gel : réécrire la même version est interdit
    with pytest.raises(FileExistsError):
        build_datasets(records, tmp_path / "ds", "v1")
