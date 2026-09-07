"""prompts — le contenu : templates Jinja2, schémas de sortie, variantes de prompt système.

Le moteur est dans ``llm_gateway.prompts.engine`` ; ce paquet n'apporte que les fichiers.
"""
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = PROMPTS_DIR / "templates"
PROMPTS_FILE = PROMPTS_DIR / "prompts.yaml"
SCHEMAS_FILE = PROMPTS_DIR / "schemas.json"

__all__ = ["PROMPTS_DIR", "PROMPTS_FILE", "SCHEMAS_FILE", "TEMPLATES_DIR"]
