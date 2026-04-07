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
 
SCHEMAS: Dict[str, Dict[str, Any]] = {
 
    # Schéma générique (default.md.j2 et tout template sans schéma dédié)
    "default": {
        "type": "object",
        "properties": {
            "agents": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string"},
                        "reponse":  {"type": "string"},
                    },
                    "required": ["agent_id", "reponse"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["agents"],
        "additionalProperties": False,
    },
 
    # Schéma sélection d'itinéraire (itenary_multi_agent.md.j2)
    "itenary_multi_agent": {
        "type": "object",
        "properties": {
            "agents": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "agent_id":     {"type": "string"},
                        "chosen_index": {"type": "integer"},
                        "mode":         {"type": "string"},
                        "reason":       {"type": "string"},
                    },
                    "required": ["agent_id", "chosen_index", "mode", "reason"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["agents"],
        "additionalProperties": False,
    },
}
 
# Alias pour compatibilité avec le code existant
OUTPUT_SCHEMA = SCHEMAS["default"]
 
TEMPLATES_DIR = Path(__file__).parent / "templates"
 
 
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
        schema = self.get_output_schema(category)
 
        try:
            template = self._env.get_template(template_name)
        except TemplateNotFound:
            template = self._env.get_template("default.md.j2")
 
        context = {
            "agents": [a.dict() if hasattr(a, 'dict') else a for a in agents],
            "parameters": parameters,
            "schema": json.dumps(schema, indent=2, ensure_ascii=False),
            "agent_ids": [a.agent_id for a in agents],
        }
 
        rendered = template.render(**context)
        return self._split_sections(rendered)
 
    def get_output_schema(self, category: str = "default") -> Dict[str, Any]:
        """Retourne le schéma JSON correspondant à la catégorie, ou le défaut."""
        return SCHEMAS.get(category, SCHEMAS["default"])
 
    # ------------------------------------------------------------------
 
    def _split_sections(self, rendered: str) -> List[InternalMessage]:
        """
        Découpe le texte rendu en messages system/user selon les marqueurs.
 
        Marqueurs supportés dans le template :
          --- SYSTEM ---
          --- USER ---
 
        Si aucun marqueur n'est présent, le contenu entier devient un message user.
        """
        messages: List[InternalMessage] = []
 
        if "--- SYSTEM ---" in rendered or "--- USER ---" in rendered:
            parts = rendered.split("---")
            current_role: str | None = None
            buffer: List[str] = []
 
            for part in parts:
                stripped = part.strip()
                if stripped.upper() == "SYSTEM":
                    if buffer and current_role:
                        messages.append(InternalMessage(role=current_role, content="\n".join(buffer).strip()))
                    current_role = "system"
                    buffer = []
                elif stripped.upper() == "USER":
                    if buffer and current_role:
                        messages.append(InternalMessage(role=current_role, content="\n".join(buffer).strip()))
                    current_role = "user"
                    buffer = []
                else:
                    if current_role:
                        buffer.append(stripped)
 
            if buffer and current_role:
                messages.append(InternalMessage(role=current_role, content="\n".join(buffer).strip()))
        else:
            messages.append(InternalMessage(role="user", content=rendered.strip()))
 
        return [m for m in messages if m.content]
 
 
# Singleton
prompt_manager = PromptManager()