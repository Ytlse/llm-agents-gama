"""Chaque catégorie mobilité porte son template, son schéma et, si besoin, son hook, dans son dossier."""
import json

from mobility_llm import CATEGORIES, bundle
from mobility_llm.prompts import CATEGORIES_DIR


def test_chaque_categorie_est_rangee_dans_son_dossier():
    for name, spec in CATEGORIES.items():
        assert (CATEGORIES_DIR / name / "template.md.j2").is_file(), name
        schema = json.loads((CATEGORIES_DIR / name / "output_schema.json").read_text(encoding="utf-8"))
        assert schema.get("type") == "object", f"{name} : le schéma est un objet JSON Schema"
        assert spec.template_name == f"{name}/template.md.j2" and spec.schema_path.name == "output_schema.json"


def test_le_bundle_se_passe_de_schemas_json():
    b = bundle()
    assert b.schemas_file is None and b.templates_dir == CATEGORIES_DIR
