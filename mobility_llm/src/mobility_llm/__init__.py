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

from llm_gateway.ports.category import CategoryBundle, CategorySpec, MetricFamilySpec
from llm_gateway.prompts.engine import PromptManager

from mobility_llm.categories.itinary_multi_agent import observe_itinary
from mobility_llm.persona import AgentSpec, departure_priority
from mobility_llm.prompts import PROMPTS_FILE, SCHEMAS_FILE, TEMPLATES_DIR

__version__ = "0.1.0"

BUNDLE_NAME = "mobility"

CATEGORIES: dict[str, CategorySpec] = {
    "itinary_multi_agent": CategorySpec(
        name="itinary_multi_agent",
        item_model=AgentSpec,
        priority=departure_priority,
        observe=observe_itinary,
    ),
    "perception_filter": CategorySpec(
        name="perception_filter", item_model=AgentSpec, priority=departure_priority,
    ),
    "stm_reflection": CategorySpec(
        name="stm_reflection", item_model=AgentSpec, priority=departure_priority,
    ),
    "ltm_self_reflection": CategorySpec(
        name="ltm_self_reflection", item_model=AgentSpec, priority=departure_priority,
    ),
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
        templates_dir=TEMPLATES_DIR,
        schemas_file=SCHEMAS_FILE,
        prompts_file=PROMPTS_FILE,
        categories=dict(CATEGORIES),
        metric_families=METRIC_FAMILIES,
    )


@lru_cache(maxsize=1)
def prompt_manager() -> PromptManager:
    """Moteur de prompts chargé avec le contenu mobilité (partagé dans le processus).

    Sert aux consommateurs hors gateway : checksum du prompt actif (clé du cache LLM du
    contrôleur), liste des variantes disponibles pour une expérience.
    """
    return PromptManager(
        templates_dir=TEMPLATES_DIR, schemas_file=SCHEMAS_FILE, prompts_file=PROMPTS_FILE,
    )


__all__ = [
    "__version__",
    "AgentSpec",
    "BUNDLE_NAME",
    "CATEGORIES",
    "METRIC_FAMILIES",
    "bundle",
    "departure_priority",
    "prompt_manager",
]
