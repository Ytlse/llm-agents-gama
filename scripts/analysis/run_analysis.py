#!/usr/bin/env python3
"""Run all analysis notebooks with a configurable LOG_DIR."""

import argparse
import subprocess
import sys
from pathlib import Path

NOTEBOOKS = [
    "current_stats.ipynb",
    "llm_traffic_analyse.ipynb",
    "pipeline_delays.ipynb",
]

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

    results = {}
    for nb in NOTEBOOKS:
        results[nb] = run_notebook(nb, args.log_dir, output_dir)

    failed = [nb for nb, ok in results.items() if not ok]
    if failed:
        print(f"\nFailed: {', '.join(failed)}")
        sys.exit(1)
    print("\nAll notebooks completed successfully.")


if __name__ == "__main__":
    main()
