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


def test_toute_categorie_qui_exige_un_agent_id_le_montre_au_modele():
    """Un identifiant exigé en sortie mais jamais donné en entrée est INVENTÉ par le modèle.

    Trouvé le 2026-09-21 sur le premier run du ticket 095, après une heure et demie de
    simulation. Le gabarit `enquete_affinite` était le seul des cinq à ne jamais rendre
    `agent.agent_id`. Le modèle répondait parfaitement — six scores cohérents, l'écologie de la
    voiture à 3 et celle des transports en commun à 8 — mais il signait « Capucine », le nom du
    persona, seule chose qu'il pouvait lire. La passerelle range les réponses par `agent_id` :
    les douze réponses ont été jetées au démultiplexage, et l'enquête a rendu zéro ligne.

    Le gabarit de décision porte déjà l'avertissement — « copy its agent_id exactly as provided
    above (numeric identifier only, without the persona's name) ». Ce test le rend obligatoire
    partout où le schéma de sortie l'exige, au lieu de compter sur la vigilance.
    """
    import json

    from mobility_llm import CATEGORIES

    manquants = []
    for nom, spec in CATEGORIES.items():
        if spec.schema_path is None or not spec.schema_path.is_file():
            continue
        schema = json.loads(spec.schema_path.read_text(encoding="utf-8"))
        items = (
            schema.get("properties", {}).get("agents", {}).get("items", {})
        )
        if "agent_id" not in (items.get("required") or []):
            continue
        gabarit = (CATEGORIES_DIR / spec.template_name).read_text(encoding="utf-8")
        if "agent.agent_id" not in gabarit:
            manquants.append(nom)

    assert not manquants, (
        "ces catégories exigent `agent_id` en sortie sans jamais le montrer au modèle : "
        + ", ".join(sorted(manquants))
        + " — leurs réponses seront jetées au démultiplexage."
    )
