"""prompts — les variantes de prompt système (`prompts.yaml`, clés `active:` et `prompts:`).

Depuis l'itération 2 du ticket 037, templates et schémas de sortie vivent avec chaque catégorie,
dans `mobility_llm/categories/<nom>/` (`template.md.j2`, `output_schema.json`). Ce fichier-ci
reste ici parce que prompt_calibration et les expériences le citent par ce chemin.
"""
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent
PROMPTS_FILE = PROMPTS_DIR / "prompts.yaml"
CATEGORIES_DIR = PROMPTS_DIR.parent / "categories"

__all__ = ["CATEGORIES_DIR", "PROMPTS_DIR", "PROMPTS_FILE"]
