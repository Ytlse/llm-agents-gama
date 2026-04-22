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
import json
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

from llm_module.settings.models import AgentSpec, InternalMessage
from llm_module.telemetry.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Schémas JSON par catégorie de template
# ---------------------------------------------------------------------------

SCHEMAS_FILE = Path(__file__).parent / "schemas.json"

with open(SCHEMAS_FILE, "r", encoding="utf-8") as f:
    SCHEMAS: Dict[str, Dict[str, Any]] = json.load(f)

TEMPLATES_DIR = Path(__file__).parent / "templates"

# Marqueurs de section — choisis pour ne jamais apparaître dans du contenu Markdown
_SECTION_SYSTEM = "<!-- SYSTEM -->"
_SECTION_USER   = "<!-- USER -->"


class PromptManager:
    """
    Charge et rend les templates Jinja2 pour assembler les prompts LLM.
    """

    def __init__(self, templates_dir: Path = TEMPLATES_DIR) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(disabled_extensions=("md.j2", "txt.j2")),
            trim_blocks=True,
            lstrip_blocks=True,
        )

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
            "agents":      [a.model_dump() for a in agents],   # Pydantic v2
            "parameters":  parameters,
            "schema":      json.dumps(schema, indent=2, ensure_ascii=False),
            "agent_ids":   [a.agent_id for a in agents],
        }

        rendered = template.render(**context)
        return self._split_sections(rendered)

    def get_output_schema(self, category: str) -> Dict[str, Any]:
        """Retourne le schéma JSON correspondant à la catégorie."""
        if category not in SCHEMAS:
            raise ValueError(f"Schéma inconnu pour la catégorie '{category}'")
        return SCHEMAS[category]

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


# Singleton
prompt_manager = PromptManager()
