"""
prompts/manager.py — Moteur de templating Jinja2 pour les prompts.

Les templates sont des fichiers .md.j2 stockés dans prompts/templates/.
Chaque template reçoit :
  - agents     : List[AgentSpec]
  - parameters : Dict[str, Any]
  - schema     : str (JSON Schema sérialisé, injecté automatiquement)

Le manager retourne une liste de InternalMessage prête à être passée
à n'importe quel adapter.

"""

from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List

import yaml
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

from llm_module.settings.models import AgentSpec, InternalMessage
from llm_module.telemetry.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Schémas JSON par catégorie de template
# ---------------------------------------------------------------------------

SCHEMAS_FILE = Path(__file__).parent / "schemas.json"


def _load_schemas(path: Path = SCHEMAS_FILE) -> Dict[str, Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# Store unique des prompts système (fusionné avec l'historique de calibration).
# Voir active:/prompts: dans le fichier. Source unique, écrite aussi par le pipeline
# de calibration (scripts/models_influence/prompt_calibration_V3.ipynb).
PROMPTS_FILE = Path(__file__).parent / "prompts.yaml"

TEMPLATES_DIR = Path(__file__).parent / "templates"

# Marqueurs de section — choisis pour ne jamais apparaître dans du contenu Markdown
_SECTION_SYSTEM = "<!-- SYSTEM -->"
_SECTION_USER   = "<!-- USER -->"

# Le contenu calibré dans prompts.yaml inclut le schéma JSON littéral en fin de texte
# (« Schéma JSON attendu : {...} »). Le template le ré-injecte dynamiquement via
# {{ schema }} depuis schemas.json ; on retire donc ce bloc du prompt système.
_SCHEMA_HEADING = re.compile(r"\n\s*Schéma JSON attendu\s*:.*", re.DOTALL)


def _load_prompts_store(path: Path = PROMPTS_FILE) -> Dict[str, Any]:
    """Charge le store de prompts (active: + prompts:). Vide si absent."""
    if not path.exists():
        return {"active": {}, "prompts": {}}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("active", {})
    data.setdefault("prompts", {})
    return data


def _strip_schema_block(content: str) -> str:
    """Retire le bloc « Schéma JSON attendu : {...} » d'un prompt calibré."""
    return _SCHEMA_HEADING.sub("", content).rstrip()


class PromptManager:
    """
    Charge et rend les templates Jinja2 pour assembler les prompts LLM.
    """

    def __init__(
        self,
        templates_dir: Path = TEMPLATES_DIR,
        prompts_file: Path = PROMPTS_FILE,
        schemas_file: Path = SCHEMAS_FILE,
    ) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(disabled_extensions=("md.j2", "txt.j2")),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._store = _load_prompts_store(prompts_file)
        self._schemas = _load_schemas(schemas_file)

    def render(
        self,
        category: str,
        agents: List[AgentSpec],
        parameters: Dict[str, Any],
    ) -> List[InternalMessage]:
        """
        Rend le template associé à `category` et retourne une liste de messages.
        """
        template_name = f"{category}.md.j2"

        try:
            schema = self.get_output_schema(category)
            template = self._env.get_template(template_name)
        except (TemplateNotFound, ValueError) as e:
            raise ValueError(f"Erreur de template pour '{category}': {str(e)}")

        context = {
            "agents":        [a.model_dump() for a in agents],   # Pydantic v2
            "parameters":    parameters,
            "schema":        json.dumps(schema, indent=2, ensure_ascii=False),
            "agent_ids":     [a.agent_id for a in agents],
            "system_prompt": self.get_system_prompt(category) or "",
        }

        rendered = template.render(**context)
        return self._split_sections(rendered)

    def get_output_schema(self, category: str) -> Dict[str, Any]:
        """Retourne le schéma JSON correspondant à la catégorie."""
        if category not in self._schemas:
            raise ValueError(f"Schéma inconnu pour la catégorie '{category}'")
        return self._schemas[category]

    def get_system_prompt(self, category: str) -> str | None:
        """
        Retourne le texte du prompt système actif pour `category`, ou None.

        La variante active est désignée par `active[category]` dans prompts.yaml et
        son contenu est cherché dans `prompts[<clé>]`. Le bloc « Schéma JSON attendu »
        est retiré (le template ré-injecte le schéma via {{ schema }}). Les catégories
        absentes de `active:` retournent None.

        Attention : selon le template, None n'a pas le même effet. Un template qui
        garde un SYSTEM en dur ignore simplement `system_prompt`. En revanche,
        `itinary_multi_agent.md.j2` n'a PLUS de SYSTEM en dur et rend entièrement
        `{{ system_prompt }}` : si sa catégorie disparaît de `active:` (ou si son
        entrée est introuvable), le prompt système se réduit silencieusement au seul
        schéma. Garder `active.itinary_multi_agent` renseigné dans prompts.yaml.
        """
        key = self._store["active"].get(category)
        if not key:
            return None
        entry = self._store["prompts"].get(key)
        if not entry or "content" not in entry:
            logger.warning(
                "Prompt actif '%s' introuvable pour la catégorie '%s'", key, category
            )
            return None
        return _strip_schema_block(entry["content"])

    def active_prompt_checksum(self, *categories: str, length: int = 12) -> str:
        """
        Empreinte stable des prompts système actifs — change dès qu'un prompt change.

        Sans argument : empreinte de toutes les catégories de `active:` (toute évolution
        d'un prompt système invalide l'empreinte). Avec arguments : restreint aux
        catégories données. Sert de clé d'isolation du cache LLM : un changement de
        prompt produit un nouveau checksum → un nouveau répertoire de cache.
        """
        cats = list(categories) if categories else sorted(self._store["active"])
        parts = [f"{cat}:{self.get_system_prompt(cat) or ''}" for cat in cats]
        raw = "\n".join(parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]

    # ------------------------------------------------------------------

    def _split_sections(self, rendered: str) -> List[InternalMessage]:
        """
        Découpe le texte rendu en messages system/user selon les marqueurs.

        Marqueurs supportés dans le template :
          <!-- SYSTEM -->
          <!-- USER -->

        Si aucun marqueur n'est présent, le contenu entier devient un message user.
        """
        messages: List[InternalMessage] = []

        has_markers = _SECTION_SYSTEM in rendered or _SECTION_USER in rendered

        if not has_markers:
            messages.append(InternalMessage(role="user", content=rendered.strip()))
            return messages

        # Découpage par marqueurs connus
        MARKER_ROLE = {
            _SECTION_SYSTEM: "system",
            _SECTION_USER:   "user",
        }

        # On insère un sentinel unique pour pouvoir splitter proprement
        _SENTINEL = "\x00SECTION\x00"
        tagged = rendered
        for marker in MARKER_ROLE:
            tagged = tagged.replace(marker, f"{_SENTINEL}{marker}{_SENTINEL}")

        parts = tagged.split(_SENTINEL)
        current_role: str | None = None
        buffer: list[str] = []

        for part in parts:
            stripped = part.strip()
            if stripped in MARKER_ROLE:
                # Flush du buffer précédent
                if buffer and current_role:
                    content = "\n".join(buffer).strip()
                    if content:
                        messages.append(InternalMessage(role=current_role, content=content))
                current_role = MARKER_ROLE[stripped]
                buffer = []
            else:
                if current_role and stripped:
                    buffer.append(stripped)

        # Flush final
        if buffer and current_role:
            content = "\n".join(buffer).strip()
            if content:
                messages.append(InternalMessage(role=current_role, content=content))

        return [m for m in messages if m.content]


# ---------------------------------------------------------------------------
# Singleton paresseux — la lecture disque (prompts.yaml, schemas.json) n'a lieu
# qu'au premier accès, plus à l'import du module. `from llm_module.prompts.manager
# import prompt_manager` reste supporté (PEP 562).
# ---------------------------------------------------------------------------

_prompt_manager: PromptManager | None = None


def get_prompt_manager() -> PromptManager:
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager


def __getattr__(name: str):
    if name == "prompt_manager":
        return get_prompt_manager()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
