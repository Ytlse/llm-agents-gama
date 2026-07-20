"""Modèles pydantic et configuration — phase 1 du ticket 004.

Toute la configuration d'un run passe par ``RunConfig`` (chargée d'un YAML) :
plus aucun global mutable, contrairement à l'ancienne lib
(``configure()`` + variables de module). Les autres modèles décrivent les
objets échangés par le moteur (blocs, mutations, scores, résultats d'éval) et
sérialisés dans le store SQLite.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

# ── Blocs ────────────────────────────────────────────────────────────────────

class Block(BaseModel):
    """Un bloc de prompt : une phrase / puce / item, mutable ou verrouillé.

    Le schéma JSON du prompt (``json_schema``) est ``mutable=False`` — jamais
    touché par les mutations.
    """
    name: str
    mutable: bool = True
    content: str


def blocks_to_dicts(blocks: list[Block] | list[dict]) -> list[dict]:
    """Normalise une liste de blocs (Block ou dict) en liste de dicts."""
    return [b.model_dump() if isinstance(b, Block) else dict(b) for b in blocks]


def blocks_hash(blocks: list[Block] | list[dict]) -> str:
    """Hash content-addressed d'un jeu de blocs (identité d'un nœud du DAG).

    Basé sur le texte reconstruit du prompt (l'identité d'un nœud = son prompt,
    comme un commit git est identifié par son arbre). Deux décompositions qui
    reconstruisent le même texte tombent sur le même hash.
    """
    from .blocks import blocks_to_prompt  # import tardif : évite le cycle
    text = blocks_to_prompt(blocks_to_dicts(blocks))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ── Mutations ────────────────────────────────────────────────────────────────

# Opérateurs de la boucle :
# - phase 1  : modify / delete / insert
# - phase 4  : reorder / merge_blocks / condense / split  (opérateurs riches, DE)
#              + compact_delete  (passe de compaction, DM)
# - phase 6  : crossover  (merge de deux parents) / migrate  (migration inter-îlots)
Operator = Literal[
    "modify", "delete", "insert",
    "reorder", "merge_blocks", "condense", "split", "compact_delete",
    "crossover", "migrate",
]

# Opérateurs proposables par le mutateur / arbitrés par le bandit UCB (phase 4).
# ``compact_delete`` et ``crossover`` sont pilotés par la boucle (compaction,
# merge), pas proposés librement par le mutateur.
MUTATOR_OPERATORS = ["modify", "delete", "insert",
                     "reorder", "merge_blocks", "condense", "split"]

Verdict = Literal[
    "accepted", "rejected_score", "rejected_stat", "rejected_tabu",
    "vetoed", "invalid",
]


class Mutation(BaseModel):
    """Une proposition de mutation d'un bloc (sortie du modèle de mutation).

    ``second_block`` / ``anchor`` ne servent qu'aux opérateurs riches (phase 4) :
    - ``merge_blocks`` fusionne ``target_block`` et ``second_block`` ;
    - ``reorder`` déplace ``target_block`` juste après ``anchor``
      (``anchor="__start__"`` → en tête).
    """
    target_block: str
    action: Operator = "modify"
    new_content: str = ""
    rationale: str = ""
    second_block: str = ""
    anchor: str = ""


# ── Scores ───────────────────────────────────────────────────────────────────

class Scores(BaseModel):
    """Décomposition du score composite par dimension (↓ = meilleur)."""
    composite: float = 0.0
    global_: float = Field(0.0, alias="global")
    absent_penalty: float = 0.0
    age: float = 0.0
    occupation: float = 0.0
    genre: float = 0.0
    motif: float = 0.0
    distance: float = 0.0
    length_penalty: float = 0.0

    model_config = {"populate_by_name": True}

    def to_json(self) -> str:
        return json.dumps(self.model_dump(by_alias=True), ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict) -> "Scores":
        return cls.model_validate(d)


# ── Configuration du run ─────────────────────────────────────────────────────

class RunConfig(BaseModel):
    """Configuration complète d'une campagne de calibration.

    Chargée d'un YAML (``RunConfig.from_yaml``) — remplace intégralement le
    ``configure()`` + globals de l'ancienne lib. Tout paramètre du moteur vit
    ici ; aucun état mutable de module.
    """

    # Identité du run / store
    branch: str = "main"
    seed_prompt: str = "expert"          # clé dans prompts.yaml (prompts.<seed>)

    # Modèles (DG : un seul modèle d'éval épinglé, un modèle distinct de mutation)
    eval_provider: str = "google_gemini31"
    eval_model: str = "gemini-3.1-flash-lite-preview"
    eval_temp: float = 0.0               # phase 0.3 : température minimale
    eval_samples: int = 3                # tirages par lot, mis en commun
    eval_rpm: int = 15
    eval_workers: int = 2
    eval_batch_max: int = 0              # 0 → lu depuis llm_config à l'exécution

    mutation_model: str = "gemini-3.1-flash-lite-preview"
    mutation_temp: float = 0.8
    mutation_provider: str = "google_gemini31"

    # Loss active (phase 3) : "l1_composite" (historique) ou "emd_jsd"
    # (EMD ordinal + JSD nominal + pondération continue par effectif).
    loss: str = "l1_composite"

    # Boucle (recuit simulé) — repris de l'ancien notebook
    max_iterations: int = 50
    sa_t0: float = 10.0
    sa_alpha: float = 0.92
    collateral_tol: float = 15.0
    val_every: int = 5
    early_stop_patience: int = 3
    length_penalty_per_word: float = 0.05

    # Acceptation (phase 3, DA) : "bootstrap" (test statistique sur les décisions)
    # ou "sa" (recuit simulé simple, phase 1). En mode bootstrap, une mutation
    # n'est acceptée que si l'amélioration du composite est **significative** ; le
    # recuit n'assouplit que le seuil de signification, jamais le signe.
    accept_test: str = "bootstrap"
    bootstrap_b: int = 1000              # rééchantillonnages (IC du Δ composite)
    bootstrap_conf_max: float = 0.90     # seuil de signification à froid (IC 90 %)
    bootstrap_conf_min: float = 0.55     # seuil assoupli à chaud (recuit)

    # ── Réflexion sur les rejets (mémoire de leçons) ─────────────────────────
    # À chaque tour, le mutateur synthétise dans un champ ``reflection`` les raisons
    # RÉCURRENTES des rejets précédents — en distinguant rejets de FOND (une leçon
    # existe) des rejets de BRUIT/seuil (non significatif : l'idée n'est pas invalidée).
    # Cette synthèse est persistée dans ``run_state`` (mémoire roulante bornée) et
    # réinjectée au tour suivant, pour ne pas re-proposer des variantes déjà écartées.
    # False → comportement antérieur (causes brutes seulement, sans mémoire de synthèse).
    reflection_enabled: bool = True
    lessons_max_chars: int = 800         # borne de la mémoire de leçons (anti-ancrage)

    # Hard negatives : nombre max d'exemples RÉELS de décisions sur-représentées
    # (persona → mode choisi, pires strates) montrés au mutateur à chaque tour.
    # Corrige le schéma mental sur du concret, pas seulement des agrégats. 0 → désactivé.
    hard_negatives_k: int = 4

    # ── Phase 4 : rendement de la boucle ─────────────────────────────────────
    # 4.1 Tabu dur (D3) : rejet des mutations quasi identiques à un rejet récent,
    # AVANT toute éval payée. Ré-éligibilité après ``tabu_tenure`` acceptations.
    tabu_enabled: bool = True
    tabu_threshold: float = 0.9          # similarité cosinus → rejet immédiat
    tabu_tenure: int = 10                # ré-éligible après N mutations acceptées
    # 4.2 Multi-candidats + entonnoir (DD) : le mutateur propose k candidats en un
    # appel ; filtre tabu (gratuit) → éval de screening (~20 % du train) → le
    # meilleur passe seul l'éval complète + le test bootstrap. ``n_candidates=1``
    # reproduit le comportement phase 3 (un seul essai, pas de screening) : c'est le
    # défaut retenu — un unique candidat filtré par paliers progressifs (voir 4.6).
    n_candidates: int = 1
    screen_dataset: str = "screen"       # jeu de screening gelé (généré avec les jeux)
    # 4.3 Opérateurs riches + bandit UCB (DE) : le bandit arbitre l'opérateur
    # suggéré au mutateur (bras = opérateur, récompense = amélioration significative).
    bandit_enabled: bool = True
    bandit_c: float = 1.4                # coefficient d'exploration UCB1
    # 4.5 Passes de compaction (DM) : minimiser le prompt à score constant.
    compact_every: int = 10              # passe toutes les N acceptations (+ fin de run)
    compact_margin: float = 1.0          # non-infériorité : IC90 haut du Δ < +marge
    compact_abl_tol: float = 2.0         # |Δ ablation| < tol → candidat suppression

    # 4.6 Paliers progressifs (successive halving / rejection).
    # * Multi-candidats (``n_candidates > 1``) : racing multi-tours précédé d'un gate
    #   sur la strate la plus mal représentée — on garde la meilleure moitié à chaque
    #   palier (garde-fou : ``racing_min_gap`` ou IC bootstrap chevauchant).
    # * Candidat unique (``n_candidates == 1``, défaut) : chaque palier (25/50/75 %)
    #   évalue l'unique essai sur une fraction croissante du train et l'ABANDONNE dès
    #   qu'il n'améliore pas le composite du prompt courant sur le même sous-échantillon
    #   (arrêt précoce → aucune éval complète payée pour un essai non prometteur).
    # ``racing_enabled=False`` reproduit le comportement sans paliers (éval complète directe).
    racing_enabled: bool = True
    racing_rungs: list[float] = Field(  # fractions cumulées du train, croissantes
        default_factory=lambda: [0.25, 0.50, 0.75])
    racing_keep_frac: float = 0.5        # part conservée à chaque palier (≥ 1 candidat)
    racing_target_gate: bool = True      # tour 0 = strate la plus mal représentée
    racing_target_every: int = 2         # 1 itération sur N en mode ciblé (sinon global)
    racing_min_gap: float = 1.0          # ne pas éliminer si écart composite < ce seuil
    racing_min_n: int = 8                # taille mini de la strate cible (sinon gate sauté)

    # ── Phase 5 : attribution de crédit Shapley (DB) ─────────────────────────
    # Recalcul GLOBAL de la contribution de chaque bloc après CHAQUE acceptation
    # (et à l'init). Échantillonnage Monte-Carlo tronqué sur le jeu de screening
    # (~20 % du train). Répartit exactement le gain entre les blocs, redondances
    # et synergies comprises ; le cache content-addressed du store amortit le coût.
    shapley_permutations: int = 25       # M permutations Monte-Carlo (socle en mode cumulatif)
    shapley_truncation_tol: float = 0.5  # |v_full − v_courant| < tol → marginaux restants ≈ 0
    # Mode CUMULATIF (économie de tokens) : graine FIXE (les permutations du socle
    # sont rejouées à l'identique → coalitions sans le bloc muté servies par le
    # cache) + ``addon`` permutations fraîches par acceptation, plafonné. 0 =
    # comportement historique (ré-échantillonnage complet, graine = accepted).
    shapley_addon_per_accept: int = 0    # permutations ajoutées par mutation acceptée
    shapley_max_permutations: int = 50   # plafond du cumul — modifiable en cours de
                                         # campagne (relu du YAML à chaque reprise)

    # ── Phase 6 : îlots parallèles, merge, Pareto, bibliothèque (D7, DC, DL) ──
    # Îlots (D7) : ``n_islands`` branches évoluent en parallèle dans le même store,
    # nommées ``{island_prefix}-{k}``. n_islands=1 → boucle mono-branche (phases 1-5).
    n_islands: int = 1
    island_prefix: str = "isl"
    # Migration (D7) : toutes les ``migrate_every`` itérations, le meilleur nœud de
    # chaque îlot est PROPOSÉ (pas imposé) à l'îlot suivant (anneau) — adopté seulement
    # s'il améliore le composite courant de la destination.
    migrate_every: int = 10
    # Merge / crossover (8.3) : toutes les ``crossover_every`` rondes de migration,
    # deux parents complémentaires de l'archive Pareto sont fusionnés par le mutateur
    # en un nœud à deux parents, soumis à l'éval de l'îlot cible. 0 → désactivé.
    crossover_every: int = 0
    # Archive Pareto (DC) : dimensions de dominance (minimisées). Sert aux départs
    # d'îlots diversifiés et au choix des parents de merge — jamais au critère
    # d'acceptation (le composite + bootstrap reste seul juge dans chaque branche).
    pareto_dims: list[str] = Field(
        default_factory=lambda: ["global", "age", "occupation", "genre", "motif", "distance"])
    # Bibliothèque d'arguments comportementaux (DL) : chaque bloc inséré/réécrit
    # accepté avec un gain composite ≥ ``snippet_min_gain`` entre dans la table
    # ``snippets`` (taggé mode/strate ciblés) ; les ``snippet_topk`` plus rentables
    # sont fournis au mutateur comme matériau de réécriture (les îlots se fertilisent
    # ainsi même sans merge).
    snippets_enabled: bool = True
    snippet_min_gain: float = 2.0
    snippet_topk: int = 3

    # ── Phase 7 : consolidation / publication ────────────────────────────────
    # Le jeu ``test`` n'est évalué **qu'une fois**, à la finalisation d'une
    # campagne — c'est le chiffre publiable (jamais vu par la boucle). La
    # publication écrit le prompt calibré dans ``prompts.yaml`` sous une clé
    # ``{publish_prefix}_{horodatage}`` (convention historique du projet).
    test_dataset: str = "test"
    publish_prefix: str = "calibrated"

    # Retries provider
    max_retries: int = 5
    max_retry_wait: float = 300.0

    # Chemins (relatifs au répertoire de travail de la CLI)
    dataset_dir: Path = Path("calibration_datasets")
    dataset_version: str = "v1"
    store_path: Path = Path("calibration_results/calibration.db")
    cerema_path: Path = Path("../data/population/cerema_values.yaml")
    prompts_path: Path = Path("../../llm_module/prompts/prompts.yaml")
    schemas_path: Path = Path("../../llm_module/prompts/schemas.json")
    category: str = "itinary_multi_agent"

    model_config = {"arbitrary_types_allowed": True}

    @classmethod
    def from_yaml(cls, path: str | Path) -> "RunConfig":
        import yaml
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls.model_validate(data)

    def eval_params_key(self) -> str:
        """Empreinte des paramètres qui déterminent une éval (clé de cache).

        Deux évals partageant prompt + entrées + cette clé sont identiques et ne
        sont calculées qu'une fois (idempotence / reprise).
        """
        return (f"prov={self.eval_provider}|model={self.eval_model}"
                f"|temp={self.eval_temp}|samples={self.eval_samples}")


# ── Résultat d'éval brut (décisions conservées → recalcul rétroactif) ─────────

class EvalResult(BaseModel):
    """Résultat d'une éval : décisions brutes + scores calculés.

    Les décisions ``[(agent_id, mode), …]`` sont conservées telles quelles dans
    le store : toute métrique (loss v2 en phase 3) est recalculable rétroactivement
    sans réappel LLM.
    """
    node_hash: str
    dataset: str                          # train / val / test / screen
    decisions: list[tuple[str, str]]      # [(agent_id, mode), …]
    scores: Scores
    eval_model: str = ""
    eval_temp: float = 0.0

    def decisions_json(self) -> str:
        return json.dumps(self.decisions, ensure_ascii=False)
