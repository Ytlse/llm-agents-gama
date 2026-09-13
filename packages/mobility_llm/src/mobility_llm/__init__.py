"""mobility_llm — les catégories LLM de la simulation de mobilité.

Ce paquet est la colle entre le gateway générique (``llm_gateway``) et le domaine de
l'enquête (``mobility_core``) : il apporte le modèle de persona, les templates, les schémas
de sortie, les variantes de prompt système, le tirage du mode dans la distribution renvoyée
par le LLM et les métriques métier du worker.

Le gateway le découvre par l'entry point ``llm_gateway.categories`` (``mobility_llm:bundle``).
Les consommateurs Python (contrôleur, expériences, notebooks) passent par
:func:`prompt_manager` pour le checksum du prompt actif et la liste des variantes.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from llm_gateway.ports.category import CategoryBundle, CategorySpec, MetricFamilySpec
from llm_gateway.prompts.engine import PromptManager

from mobility_llm.categories.itinary_multi_agent import observe_itinary
from mobility_llm.persona import AgentSpec, departure_priority
from mobility_llm.prompts import CATEGORIES_DIR, PROMPTS_FILE

__version__ = "0.2.0"

BUNDLE_NAME = "mobility"

def _cat(name: str, **kw) -> CategorySpec:
    """Une catégorie rangée dans `categories/<nom>/` : template et schéma à côté de son code."""
    return CategorySpec(
        name=name,
        item_model=AgentSpec,
        priority=departure_priority,
        template_name=f"{name}/template.md.j2",
        schema_path=CATEGORIES_DIR / name / "output_schema.json",
        **kw,
    )


CATEGORIES: dict[str, CategorySpec] = {
    "itinary_multi_agent": _cat("itinary_multi_agent", observe=observe_itinary),
    "perception_filter": _cat("perception_filter"),
    "stm_reflection": _cat("stm_reflection"),
    "ltm_self_reflection": _cat("ltm_self_reflection"),
}


# Compteurs alimentés par categories/itinary_multi_agent.observe_itinary, exposés par l'API
# sous ces noms : ce sont ceux que lisent les dashboards Grafana 04 et 07. Ne pas les renommer
# sans mettre à jour les dashboards.
METRIC_FAMILIES: tuple[MetricFamilySpec, ...] = (
    MetricFamilySpec("llm_transport_mode_chosen_total", "Modes de transport principaux choisis par le LLM", "transport_mode_chosen", ("mode",)),
    MetricFamilySpec("llm_mode_probability_pct_total", "Somme des probabilités (en %) attribuées par le LLM à chaque mode", "mode_probability_pct", ("mode",)),
    MetricFamilySpec("llm_mode_label_checked_total", "Options notées par le LLM : étiquettes de mode vérifiées", "mode_label_checked"),
    MetricFamilySpec("llm_mode_label_mismatch_total", "Options notées par le LLM : étiquettes de mode en désaccord avec l'option", "mode_label_mismatch"),
    MetricFamilySpec("llm_trip_distance_bracket_total", "Nombre de trajets par tranche de distance", "trip_distance_bracket", ("bracket",)),
    MetricFamilySpec("llm_mode_by_distance_total", "Modes de transport par tranche de distance", "mode_by_distance", ("mode", "bracket")),
    MetricFamilySpec("llm_mode_by_provider_total", "Modes de transport choisis par provider LLM", "mode_by_provider", ("mode", "provider")),
    MetricFamilySpec("llm_chosen_index_total", "Distribution des indices de trajectoire choisis par le LLM (0 = premier choix proposé)", "chosen_index", ("index",)),
)


def bundle() -> CategoryBundle:
    """Le bundle que le gateway charge par entry point."""
    return CategoryBundle(
        name=BUNDLE_NAME,
        templates_dir=CATEGORIES_DIR,
        prompts_file=PROMPTS_FILE,
        categories=dict(CATEGORIES),
        metric_families=METRIC_FAMILIES,
    )


def build_prompt_manager(prompts_file: Path | None = PROMPTS_FILE) -> PromptManager:
    """Un moteur chargé avec le contenu mobilité ; `prompts_file` permet un autre jeu de variantes (tests)."""
    return PromptManager(
        templates_dir=CATEGORIES_DIR,
        prompts_file=prompts_file,
        template_names={n: sp.template_name for n, sp in CATEGORIES.items() if sp.template_name},
        schema_paths={n: sp.schema_path for n, sp in CATEGORIES.items() if sp.schema_path},
    )


@lru_cache(maxsize=1)
def prompt_manager() -> PromptManager:
    """Moteur de prompts partagé dans le processus, pour les consommateurs hors gateway
    (checksum du prompt actif = clé du cache LLM du contrôleur ; variantes d'une expérience)."""
    return build_prompt_manager()


__all__ = [
    "__version__",
    "AgentSpec",
    "BUNDLE_NAME",
    "CATEGORIES",
    "METRIC_FAMILIES",
    "build_prompt_manager",
    "bundle",
    "departure_priority",
    "prompt_manager",
]
