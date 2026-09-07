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

from llm_gateway.ports.category import CategoryBundle, CategorySpec
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


def bundle() -> CategoryBundle:
    """Le bundle que le gateway charge par entry point."""
    return CategoryBundle(
        name=BUNDLE_NAME,
        templates_dir=TEMPLATES_DIR,
        schemas_file=SCHEMAS_FILE,
        prompts_file=PROMPTS_FILE,
        categories=dict(CATEGORIES),
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
    "bundle",
    "departure_priority",
    "prompt_manager",
]
