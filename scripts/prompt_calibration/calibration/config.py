"""Constantes de configuration — phase 0.

La configuration complète (RunConfig pydantic chargée d'un YAML) arrive en
phase 1 ; ce module ne porte que les décisions de mesure de la phase 0.
"""

# Phase 0.3 — température d'évaluation minimale (ticket 004, D6).
# Toutes les évals train/val/test utilisent cette température. Le
# non-déterminisme résiduel du provider existe malgré tout : c'est le test
# statistique d'acceptation (bootstrap, phase 3) qui protège contre le bruit
# d'échantillon restant — pas de mesure de plancher de bruit par répétition
# (trop cher en tokens).
EVAL_TEMP = 0.0

# Bornes des jeux gelés (phase 0.2) : hash(agent_id) % 100 → intervalle [lo, hi).
DATASET_SPLITS = (
    ("train", 0, 70),
    ("val",   70, 85),
    ("test",  85, 100),
)

# Jeu de screening (phase 4.2, DD) : sous-échantillon gelé du **train** (~20 %),
# buckets [0, SCREEN_MAX_BUCKET) — utilisé par l'entonnoir multi-candidats pour
# filtrer les k candidats à bas coût avant l'éval complète. C'est un sous-ensemble
# strict du train (mêmes personas → réutilisation du cache d'éval).
SCREEN_MAX_BUCKET = 14  # 14/70 ≈ 20 % du train

# Effectif minimal d'une catégorie pour qu'elle soit jugée couverte dans le
# rapport de couverture des jeux (strate sous ce seuil = warning explicite).
COVERAGE_MIN_COUNT = 5
