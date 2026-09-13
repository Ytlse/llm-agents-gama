#!/usr/bin/env python3
"""Run all analysis notebooks with a configurable LOG_DIR."""

import argparse
import subprocess
import sys
from pathlib import Path

NOTEBOOKS = [
    "selected_mode_stats.ipynb",
    "llm_traffic_analyse.ipynb",
    "pipeline.ipynb",
    "delays.ipynb",
]

# Fichiers d'entrée indispensables (relatifs à LOG_DIR) : si absent, le
# notebook est sauté au lieu de faire échouer toute l'analyse.
REQUIRED_FILES = {
    "delays.ipynb": ["gama_results/gama_arrivals.csv"],
}

SCRIPT_DIR = Path(__file__).parent


def run_notebook(notebook: str, log_dir: str, output_dir: Path) -> bool:
    nb_path = SCRIPT_DIR / notebook
    out_path = output_dir / notebook
    cmd = [
        sys.executable, "-m", "papermill",
        str(nb_path), str(out_path),
        "-p", "LOG_DIR", log_dir,
        "--cwd", str(SCRIPT_DIR),
        "--no-progress-bar",
    ]
    print(f"\n>>> {notebook}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"[FAILED] {notebook}")
        return False
    print(f"[OK] {notebook}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Run all analysis notebooks")
    parser.add_argument(
        "--log-dir",
        default="../../experiments/current/",
        help="Path to experiment directory (default: ../../experiments/current/)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to write executed notebooks (default: same as source)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else SCRIPT_DIR

    print(f"LOG_DIR: {args.log_dir}")
    print(f"Output:  {output_dir}")

    log_dir_path = (SCRIPT_DIR / args.log_dir).resolve() if not Path(args.log_dir).is_absolute() else Path(args.log_dir)

    results = {}
    skipped = []
    for nb in NOTEBOOKS:
        missing = [f for f in REQUIRED_FILES.get(nb, []) if not (log_dir_path / f).exists()]
        if missing:
            print(f"\n>>> {nb}")
            print(f"[SKIPPED] {nb} — fichier(s) manquant(s) : {', '.join(missing)}")
            skipped.append(nb)
            continue
        results[nb] = run_notebook(nb, args.log_dir, output_dir)

    failed = [nb for nb, ok in results.items() if not ok]
    if failed:
        print(f"\nFailed: {', '.join(failed)}")
        sys.exit(1)
    if skipped:
        print(f"\nSkipped (données manquantes) : {', '.join(skipped)}")
    print("\nAll notebooks completed successfully.")


if __name__ == "__main__":
    main()
