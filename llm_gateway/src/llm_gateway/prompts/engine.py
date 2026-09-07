"""
prompts/engine.py — Moteur de templating Jinja2 pour les prompts, SANS contenu.

Le moteur ne connaît aucun template, aucun schéma, aucun prompt système : tout lui est
fourni à la construction par un bundle de catégories (cf. ``ports.category``) —
``templates_dir`` (un ``<catégorie>.md.j2`` par catégorie), ``schemas_file`` (un objet JSON
``{catégorie: schéma de sortie}``) et, facultatif, ``prompts_file`` (``active:`` /
``prompts:`` des variantes de prompt système).

Chaque template reçoit :
  - agents     : les items validés du lot, sous forme de dicts
  - parameters : Dict[str, Any]
  - schema     : str (JSON Schema sérialisé, injecté automatiquement)
  - system_prompt : le prompt système actif (ou la variante demandée)

Le manager retourne une liste de InternalMessage prête à être passée à n'importe quel adapter.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape
from pydantic import BaseModel

from llm_gateway.core.models import InternalMessage
from llm_gateway.telemetry.logger import get_logger

logger = get_logger(__name__)


def _load_schemas(path: Path) -> dict[str, dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# Marqueurs de section — choisis pour ne jamais apparaître dans du contenu Markdown
_SECTION_SYSTEM = "<!-- SYSTEM -->"
_SECTION_USER   = "<!-- USER -->"

# Le contenu calibré dans prompts.yaml inclut le schéma JSON littéral en fin de texte
# (« Schéma JSON attendu : {...} »). Le template le ré-injecte dynamiquement via
# {{ schema }} depuis schemas.json ; on retire donc ce bloc du prompt système.
_SCHEMA_HEADING = re.compile(r"\n\s*Schéma JSON attendu\s*:.*", re.DOTALL)


def _load_prompts_store(path: Path | None) -> dict[str, Any]:
    """Charge le store de prompts (active: + prompts:). Vide si absent ou non fourni."""
    if path is None or not path.exists():
        return {"active": {}, "prompts": {}}
    with open(path, encoding="utf-8") as f:
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
        templates_dir: Path,
        schemas_file: Path,
        prompts_file: Path | None = None,
    ) -> None:
        self._templates_dir = Path(templates_dir)
        self._schemas_file = Path(schemas_file)
        self._prompts_file = Path(prompts_file) if prompts_file else None
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
        agents: Sequence[BaseModel],
        parameters: dict[str, Any],
    ) -> list[InternalMessage]:
        """
        Rend le template associé à `category` et retourne une liste de messages.
        """
        template_name = f"{category}.md.j2"

        try:
            schema = self.get_output_schema(category)
            template = self._env.get_template(template_name)
        except (TemplateNotFound, ValueError) as e:
            raise ValueError(f"Erreur de template pour '{category}': {str(e)}") from e

        context = {
            "agents":        [a.model_dump() for a in agents],
            "parameters":    parameters,
            "schema":        json.dumps(schema, indent=2, ensure_ascii=False),
            "agent_ids":     [getattr(a, "agent_id", None) for a in agents],
            # La requête peut désigner sa variante de prompt (ticket 035) ; `parameters` entre dans
            # la clé de lot, donc deux variantes ne partagent jamais un même appel.
            "system_prompt": self.get_system_prompt(category, (parameters or {}).get("prompt_variant")) or "",
        }

        rendered = template.render(**context)
        return self._split_sections(rendered)

    def check_category(self, category: str) -> None:
        """Vérifie qu'une catégorie est servable : template ET schéma présents. Lève ValueError.

        Appelé par le registre à la construction, pour échouer au démarrage et non à la
        première requête.
        """
        if category not in self._schemas:
            raise ValueError(
                f"Catégorie {category!r} : schéma de sortie absent de {self._schemas_file}"
            )
        try:
            self._env.get_template(f"{category}.md.j2")
        except TemplateNotFound:
            raise ValueError(
                f"Catégorie {category!r} : template {category}.md.j2 absent de {self._templates_dir}"
            ) from None

    @property
    def categories(self) -> list[str]:
        """Catégories pour lesquelles un schéma de sortie est déclaré."""
        return sorted(self._schemas)

    def get_output_schema(self, category: str) -> dict[str, Any]:
        """Retourne le schéma JSON correspondant à la catégorie."""
        if category not in self._schemas:
            raise ValueError(f"Schéma inconnu pour la catégorie '{category}'")
        return self._schemas[category]

    def get_system_prompt(self, category: str, variante: str | None = None) -> str | None:
        """
        Retourne le texte du prompt système pour `category` — la variante ACTIVE, ou `variante`.

        `variante` (ticket 035) : clé de `prompts:` désignée par une expérience (le gabarit fait
        partie de sa configuration, E1) et transmise par la requête (`parameters.prompt_variant`).
        Une variante inconnue lève ValueError : mieux vaut refuser que servir le prompt actif à la
        place de celui demandé (aucune substitution silencieuse, EF-62).

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
        if variante:
            entry = self._store["prompts"].get(variante)
            if not entry or "content" not in entry:
                raise ValueError(
                    f"variante de prompt {variante!r} introuvable dans prompts.yaml "
                    f"(connues : {', '.join(sorted(self._store['prompts']))})"
                )
            return _strip_schema_block(entry["content"])
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

    def variantes(self) -> list[str]:
        """Clés de `prompts:` disponibles (pour valider une expérience avant de la lancer)."""
        return sorted(self._store["prompts"])

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

    def _split_sections(self, rendered: str) -> list[InternalMessage]:
        """
        Découpe le texte rendu en messages system/user selon les marqueurs.

        Marqueurs supportés dans le template :
          <!-- SYSTEM -->
          <!-- USER -->

        Si aucun marqueur n'est présent, le contenu entier devient un message user.
        """
        messages: list[InternalMessage] = []

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


__all__ = ["PromptManager"]
