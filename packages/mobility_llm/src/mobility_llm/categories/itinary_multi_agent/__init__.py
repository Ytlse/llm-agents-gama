"""Catégorie `itinary_multi_agent` : template, schéma de sortie et hook d'observation.

Le dossier porte les trois pièces de la catégorie : `template.md.j2`, `output_schema.json` et
`observe.py` (métriques métier). Les noms publics sont réexportés ici pour que
`from mobility_llm.categories.itinary_multi_agent import extract_primary_mode` reste valable.
"""
from mobility_llm.categories.itinary_multi_agent.observe import (
    MODE_MISMATCH_ALARM_RATIO,
    MODE_MISMATCH_MIN_SAMPLE,
    WORKER_MODE_ALIASES,
    WORKER_MODE_LABEL,
    count_mode_mismatches,
    distance_bracket,
    extract_primary_mode,
    observe_itinary,
)

__all__ = [
    "MODE_MISMATCH_ALARM_RATIO",
    "MODE_MISMATCH_MIN_SAMPLE",
    "WORKER_MODE_ALIASES",
    "WORKER_MODE_LABEL",
    "count_mode_mismatches",
    "distance_bracket",
    "extract_primary_mode",
    "observe_itinary",
]
