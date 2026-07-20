"""Package de calibration de prompt — nouvelle version (ticket 004).

Phase 0 (fiabiliser la mesure) :
- ``metadata``  : jointure structurée agent_id → traits_json (zéro inférence textuelle)
- ``datasets``  : jeux train/val/test gelés, stratifiés, versionnés
- ``exchanges`` : lecture robuste de llm_exchanges.jsonl
- ``config``    : température d'évaluation minimale

Phase 1 (package + store SQLite) :
- ``models``     : RunConfig (YAML) + modèles pydantic (plus aucun global mutable)
- ``blocks``     : décomposition/recomposition pure du prompt
- ``metrics``    : loss pluggable (interface Metric + L1Composite)
- ``store``      : DAG SQLite content-addressed (nœuds/mutations/évals/ablations)
- ``evaluation`` : micro-batching + appels provider + cache store
- ``mutation``   : génération/application de mutations + carte de contribution
- ``shapley``    : attribution de crédit Shapley (contribution des blocs)
- ``loop``       : boucle de recuit simulé reprenable
- ``cli``        : calibrate run / resume / status / export / import

L'ancienne version (scripts/models_influence/prompt_calibration.ipynb + lib)
est conservée intacte comme référence — ne pas y importer.
"""

from .config import EVAL_TEMP
from .exchanges import iter_exchanges, itinerary_entries
from .metadata import (
    GENDER_MAP,
    OCCUPATION_MAP,
    DEST_TO_MOTIF,
    age_to_cat,
    distance_to_cat,
    extract_min_distance_km,
    strip_memory_section,
    split_entry_personas,
    parse_persona_header,
    load_population,
    build_decision_records,
)
from .datasets import split_of, in_screen, build_datasets, coverage_report
from .models import (Block, Mutation, Scores, RunConfig, EvalResult, blocks_hash,
                     MUTATOR_OPERATORS)
from .blocks import decompose_prompt, blocks_to_prompt, split_sentences, prompt_word_count
from .metrics import Metric, L1Composite, MODES, categorize_mode, worst_strata_modes
from .mutation import apply_mutation
from .tabu import TabuArchive, hash_embedding, cosine, mutation_signature
from .bandit import UCBBandit, ucb_scores, select_arm
from .shapley import (shapley_values, shapley_scores, build_shapley_results,
                     coalition_blocks, USEFUL_THRESHOLD, HARMFUL_THRESHOLD)
from .store import RunStore

__all__ = [
    "EVAL_TEMP",
    "iter_exchanges", "itinerary_entries",
    "GENDER_MAP", "OCCUPATION_MAP", "DEST_TO_MOTIF",
    "age_to_cat", "distance_to_cat", "extract_min_distance_km",
    "strip_memory_section",
    "split_entry_personas", "parse_persona_header",
    "load_population", "build_decision_records",
    "split_of", "in_screen", "build_datasets", "coverage_report",
    # Phase 1
    "Block", "Mutation", "Scores", "RunConfig", "EvalResult", "blocks_hash",
    "MUTATOR_OPERATORS",
    "decompose_prompt", "blocks_to_prompt", "split_sentences", "prompt_word_count",
    "Metric", "L1Composite", "MODES", "categorize_mode", "worst_strata_modes",
    "apply_mutation",
    "RunStore",
    # Phase 4
    "TabuArchive", "hash_embedding", "cosine", "mutation_signature",
    "UCBBandit", "ucb_scores", "select_arm",
    # Phase 5
    "shapley_values", "shapley_scores", "build_shapley_results", "coalition_blocks",
    "USEFUL_THRESHOLD", "HARMFUL_THRESHOLD",
]
