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
from collections.abc import Mapping, Sequence
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
    # Familles (specs/hygiene-prompts-et-plateforme-experiences.md §4.1) : la règle appliquée
    # à un prompt dépend de sa famille, la même phrase étant licite dans l'une et fautive dans
    # l'autre. Déclarée, jamais devinée du nom.
    data.setdefault("familles", {"minimale": [], "defaut": "experte"})
    return data


def _strip_schema_block(content: str) -> str:
    """Retire le bloc « Schéma JSON attendu : {...} » d'un prompt calibré."""
    return _SCHEMA_HEADING.sub("", content).rstrip()


class VariantePromptInvalide(ValueError):
    """Une variante portant `_invalidation` a été demandée pour être SERVIE à un modèle.

    Sous-classe de ValueError : les appelants qui filtraient déjà les variantes inconnues
    continuent de fonctionner. Le refus ne vaut que pour le service — calculer une empreinte
    ou relire une archive passe par `verifier_validite=False`, sinon les empreintes scellées
    des exécutions passées cesseraient d'être reproductibles.
    """

    def __init__(self, variante: str, invalidation: Mapping[str, Any]) -> None:
        self.variante = variante
        self.regle = invalidation.get("regle")
        self.motif = (invalidation.get("motif") or "").strip()
        self.remplace_par = invalidation.get("remplace_par")
        self.le = invalidation.get("le")
        remplacant = (
            f" Utiliser {self.remplace_par!r} à la place."
            if self.remplace_par
            else " Aucun remplaçant déclaré."
        )
        super().__init__(
            f"variante de prompt {variante!r} INVALIDÉE le {self.le or '?'} "
            f"(règle {self.regle or '?'}) : {self.motif}{remplacant}"
        )


class AvisNeutraliteManquant(ValueError):
    """La variante n'a pas d'avis de neutralité valide, en mode strict (spec hygiène §4.2)."""


def _sha_contenu(contenu: str) -> str:
    return hashlib.sha256(contenu.encode("utf-8")).hexdigest()


def _neutralite_de(entry: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Bloc `_neutralite` d'une entrée, ou None."""
    if not isinstance(entry, Mapping):
        return None
    bloc = entry.get("_neutralite")
    return dict(bloc) if isinstance(bloc, Mapping) else None


def _etat_neutralite(entry: Mapping[str, Any]) -> tuple[str, str]:
    """(état, explication) de l'avis de neutralité d'une variante.

    États : `conforme`, `reserve`, `refus`, `absent`, `perime`. Le sceau compte autant que le
    verdict : un avis rendu sur un texte qui a changé depuis ne vaut plus rien, sans quoi il
    suffirait de faire valider une version puis d'en servir une autre.
    """
    avis = _neutralite_de(entry)
    if avis is None:
        return "absent", "aucun avis de neutralité (agent prompt-auditor)"
    verdict = str(avis.get("verdict") or "")
    scelle = str(avis.get("sha256_texte") or "")
    if scelle and scelle != _sha_contenu(str(entry.get("content") or "")):
        return (
            "perime",
            f"avis rendu le {avis.get('le') or '?'} sur un texte différent "
            f"(sceau {scelle[:12]}…) — le contenu a changé depuis",
        )
    if verdict == "non_conforme":
        constats = avis.get("constats") or []
        regles = ", ".join(
            str(c.get("regle")) for c in constats if isinstance(c, Mapping) and c.get("regle")
        )
        return "refus", f"verdict non_conforme{f' (règles {regles})' if regles else ''}"
    if verdict == "conforme_avec_reserve":
        return "reserve", "verdict conforme_avec_reserve"
    if verdict == "conforme":
        return "conforme", "verdict conforme"
    return "absent", f"verdict {verdict!r} non reconnu"


def _invalidation_de(entry: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Bloc `_invalidation` d'une entrée de prompt, si elle est déclarée invalide."""
    if not isinstance(entry, Mapping):
        return None
    bloc = entry.get("_invalidation")
    if isinstance(bloc, Mapping) and bloc.get("statut") == "invalide":
        return dict(bloc)
    return None


class PromptManager:
    """
    Charge et rend les templates Jinja2 pour assembler les prompts LLM.
    """

    def __init__(
        self,
        templates_dir: Path | Sequence[Path],
        schemas_file: Path | None = None,
        prompts_file: Path | None = None,
        *,
        template_names: Mapping[str, str] | None = None,
        schema_paths: Mapping[str, Path] | None = None,
        exiger_avis_neutralite: bool = True,
    ) -> None:
        """
        `templates_dir` : un répertoire (ou plusieurs) où Jinja2 cherche les templates ;
        `schemas_file` : objet JSON {catégorie: schéma} (facultatif si `schema_paths` couvre tout) ;
        `template_names` : nom de template par catégorie (défaut `<catégorie>.md.j2`, relatif à
        `templates_dir`, ex. `itinary_multi_agent/template.md.j2`) ;
        `schema_paths` : fichier JSON du schéma de sortie par catégorie (prime sur `schemas_file`).
        """
        dirs = [Path(templates_dir)] if isinstance(templates_dir, (str, Path)) else [Path(d) for d in templates_dir]
        self._templates_dirs = dirs
        self._schemas_file = Path(schemas_file) if schemas_file else None
        self._prompts_file = Path(prompts_file) if prompts_file else None
        self._template_names: dict[str, str] = dict(template_names or {})
        # ARMÉ depuis le 2026-09-10 : les 18 variantes ont été auditées par l'agent
        # `prompt-auditor` et portent un `_neutralite` scellé. Servir un prompt non audité est
        # désormais un refus, pas un avertissement. Se désarme explicitement pour un bac à
        # sable ou un test qui fabrique ses propres variantes.
        self.exiger_avis_neutralite = bool(exiger_avis_neutralite)
        self._env = Environment(
            loader=FileSystemLoader([str(d) for d in dirs]),
            autoescape=select_autoescape(disabled_extensions=("md.j2", "txt.j2")),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._store = _load_prompts_store(self._prompts_file)
        self._schemas: dict[str, dict[str, Any]] = _load_schemas(self._schemas_file) if self._schemas_file else {}
        for category, path in (schema_paths or {}).items():
            self._schemas[category] = json.loads(Path(path).read_text(encoding="utf-8"))

    def template_name(self, category: str) -> str:
        return self._template_names.get(category, f"{category}.md.j2")

    def render(
        self,
        category: str,
        agents: Sequence[BaseModel],
        parameters: dict[str, Any],
    ) -> list[InternalMessage]:
        """
        Rend le template associé à `category` et retourne une liste de messages.
        """
        template_name = self.template_name(category)

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
            where = self._schemas_file or "aucun schemas_file ni schema_path"
            raise ValueError(f"Catégorie {category!r} : schéma de sortie absent ({where})")
        name = self.template_name(category)
        try:
            self._env.get_template(name)
        except TemplateNotFound:
            raise ValueError(
                f"Catégorie {category!r} : template {name} absent de {[str(d) for d in self._templates_dirs]}"
            ) from None
        # Un prompt actif invalidé doit tomber au démarrage, pas à la millième requête.
        key = self._store["active"].get(category)
        bloc = _invalidation_de(self._store["prompts"].get(key)) if key else None
        if bloc is not None:
            raise VariantePromptInvalide(key, bloc)

    @property
    def categories(self) -> list[str]:
        """Catégories pour lesquelles un schéma de sortie est déclaré."""
        return sorted(self._schemas)

    def get_output_schema(self, category: str) -> dict[str, Any]:
        """Retourne le schéma JSON correspondant à la catégorie."""
        if category not in self._schemas:
            raise ValueError(f"Schéma inconnu pour la catégorie '{category}'")
        return self._schemas[category]

    def get_system_prompt(
        self,
        category: str,
        variante: str | None = None,
        *,
        verifier_validite: bool = True,
    ) -> str | None:
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
            if verifier_validite:
                bloc = _invalidation_de(entry)
                if bloc is not None:
                    raise VariantePromptInvalide(variante, bloc)
                self._verifier_neutralite(variante, entry)
            return _strip_schema_block(entry["content"])
        key = self._store["active"].get(category)
        if not key:
            return None
        entry = self._store["prompts"].get(key)
        if not entry or "content" not in entry:
            logger.warning(
                f"Prompt actif {key!r} introuvable pour la catégorie {category!r}"
            )
            return None
        if verifier_validite:
            bloc = _invalidation_de(entry)
            if bloc is not None:
                raise VariantePromptInvalide(key, bloc)
            self._verifier_neutralite(key, entry)
        return _strip_schema_block(entry["content"])

    def _verifier_neutralite(self, variante: str, entry: Mapping[str, Any]) -> None:
        """Applique l'avis du `prompt-auditor` sur le chemin de SERVICE.

        Un verdict `non_conforme`, ou un avis périmé par une retouche du texte, refuse
        toujours : ce sont des constats, pas des lacunes. En revanche un avis **absent** ne
        refuse que si `exiger_avis_neutralite` est armé — sinon la mise en place de la règle
        aurait rendu inutilisables les 25 variantes existantes, l'active comprise, avant même
        qu'un audit ait pu être rendu. Le rattrapage se fait variante par variante, puis on arme.
        """
        etat, pourquoi = _etat_neutralite(entry)
        if etat in ("refus", "perime"):
            raise AvisNeutraliteManquant(
                f"variante de prompt {variante!r} refusée par l'audit de neutralité : "
                f"{pourquoi} → faire réexaminer par l'agent prompt-auditor "
                f"(specs/hygiene-prompts-et-plateforme-experiences.md §4.2)"
            )
        if etat == "absent":
            if self.exiger_avis_neutralite:
                raise AvisNeutraliteManquant(
                    f"variante de prompt {variante!r} sans avis de neutralité valide "
                    f"({pourquoi}) → faire auditer par l'agent prompt-auditor, ou désarmer "
                    f"`exiger_avis_neutralite`"
                )
            # loguru : pas d'interpolation %s — le message doit être formé avant l'appel.
            logger.warning(
                f"Prompt {variante!r} servi sans avis de neutralité ({pourquoi}) — "
                "audit prompt-auditor à rendre"
            )

    def neutralite(self, variante: str) -> dict[str, Any] | None:
        """Avis de neutralité déclaré pour une variante, tel quel. Ne lève jamais."""
        return _neutralite_de(self._store["prompts"].get(variante))

    def etat_neutralite(self, variante: str) -> tuple[str, str]:
        """(état, explication) — `conforme`, `reserve`, `refus`, `absent` ou `perime`."""
        entry = self._store["prompts"].get(variante)
        if not entry:
            return "absent", "variante inconnue"
        return _etat_neutralite(entry)

    def invalidation(self, variante: str) -> dict[str, Any] | None:
        """Bloc `_invalidation` d'une variante, ou None si elle est valide. Ne lève jamais."""
        return _invalidation_de(self._store["prompts"].get(variante))

    def famille(self, variante: str) -> str:
        """Famille déclarée d'une variante : « minimale » ou « experte » (défaut du store)."""
        fam = self._store.get("familles") or {}
        if variante in (fam.get("minimale") or []):
            return "minimale"
        entry = self._store["prompts"].get(variante) or {}
        return str(entry.get("famille") or fam.get("defaut") or "experte")

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
        # Empreinte, pas service : ne refuse pas une variante invalidée, sinon un prompt actif
        # invalidé ferait tomber le calcul de clé de cache au lieu de le faire tomber au rendu.
        parts = [
            f"{cat}:{self.get_system_prompt(cat, verifier_validite=False) or ''}"
            for cat in cats
        ]
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
