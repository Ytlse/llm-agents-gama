"""Îlots parallèles, migration et merge — phase 6 du ticket 004 (D7, DC).

Plusieurs branches (« îlots ») évoluent **dans le même store**, chacune avec sa
propre boucle de recuit reprenable (``CalibrationLoop``). L'orchestrateur les fait
avancer **à tour de rôle** par rondes de ``migrate_every`` itérations ; entre deux
rondes :

- **Migration (D7)** : le meilleur nœud de chaque îlot est *proposé* (pas imposé) à
  l'îlot suivant en anneau — adopté seulement s'il améliore le composite courant de
  la destination (l'acceptation reste locale à chaque branche).
- **Merge / crossover (8.3, optionnel)** : toutes les ``crossover_every`` rondes,
  deux parents **complémentaires** de l'archive Pareto (``pareto.py``) sont fusionnés
  par le mutateur en un nœud à **deux parents**, soumis à l'éval de l'îlot cible.

**Départs diversifiés (DC/GEPA)** : au premier run (store vide) tous les îlots
partent du seed ; dès qu'une archive Pareto existe, les îlots ``k>0`` démarrent de
points *diversifiés* du front plutôt que de cloner le champion.

**Reprise.** Chaque boucle d'îlot est déjà reprenable (cache d'éval + rejeu de
mutations). L'orchestrateur snapshote en plus le n° de **ronde** terminée sous une
clé réservée (``__islands__``) : relancer repart à la ronde suivante ; les rondes
déjà jouées ne rappellent pas le LLM (évals servies par le cache) et la migration
est **idempotente** (une arête ``migrate``/``crossover`` déjà écrite n'est pas
redoublée).
"""

from __future__ import annotations

import math
from typing import Callable, Optional

from . import pareto
from .evaluation import Evaluator
from .loop import CalibrationLoop
from .models import RunConfig
from .store import RunStore

# Clé réservée de ``run_state`` pour l'état de l'orchestrateur (jamais une branche
# de nœuds → n'apparaît pas dans le DAG ni la liste des branches du dashboard).
ISLANDS_STATE_KEY = "__islands__"

# Fabrique de fonction d'appel provider par îlot (config → call_fn), injectable
# pour les tests (un double déterministe partagé par tous les îlots).
CallFactory = Callable[[RunConfig], Callable[[dict], list[dict]]]


def island_branches(config: RunConfig) -> list[str]:
    """Noms des branches d'îlots : ``{prefix}-0 … {prefix}-(n-1)``."""
    n = max(1, config.n_islands)
    return [f"{config.island_prefix}-{k}" for k in range(n)]


class IslandRunner:
    """Orchestre ``n_islands`` boucles reprenables dans un store partagé."""

    def __init__(self, base_config: RunConfig, store: RunStore, metric,
                 cerema: dict, metadata_by_id: dict[str, dict],
                 call_factory: CallFactory, mutator,
                 train_records: list[dict], val_records: list[dict],
                 screen_records: Optional[list[dict]] = None):
        self.base_config = base_config
        self.store = store
        self.metric = metric
        self.cerema = cerema
        self.meta = metadata_by_id
        self.call_factory = call_factory
        self.mutator = mutator
        self.train = train_records
        self.val = val_records
        self.screen = screen_records or []
        self.branches = island_branches(base_config)

    # ── Fabrique d'objets par îlot ───────────────────────────────────────────

    def _config_for(self, branch: str) -> RunConfig:
        return self.base_config.model_copy(update={"branch": branch})

    def _evaluator_for(self, branch: str) -> Evaluator:
        cfg = self._config_for(branch)
        return Evaluator(cfg, self.store, self.metric, self.cerema, self.meta,
                         self.call_factory(cfg))

    def _loop_for(self, branch: str) -> CalibrationLoop:
        cfg = self._config_for(branch)
        return CalibrationLoop(cfg, self.store, self._evaluator_for(branch),
                               self.mutator, self.cerema, self.train, self.val,
                               screen_records=self.screen)

    def _start_blocks(self, seed_blocks: list[dict], k: int) -> list[dict]:
        """Blocs de départ de l'îlot ``k`` (n'est utilisé qu'au tout premier init).

        Îlot 0 = ancre (toujours le seed). Îlots ``k>0`` : point diversifié du front
        de Pareto s'il en existe, sinon le seed. Sans effet si l'îlot a déjà un état
        (le départ est alors ignoré par la boucle).
        """
        if k == 0:
            return seed_blocks
        front = pareto.pareto_front(self.store.pareto_candidates("train"),
                                    self.base_config.pareto_dims)
        seeds = pareto.diversified_seeds(front, self.base_config.n_islands,
                                         self.base_config.pareto_dims)
        if len(seeds) > k:
            blocks = self.store.node_blocks(seeds[k]["hash"])
            if blocks:
                return blocks
        return seed_blocks

    # ── Boucle principale (rondes) ───────────────────────────────────────────

    def run(self, seed_blocks: list[dict],
            max_iterations: Optional[int] = None) -> dict:
        cfg = self.base_config
        max_iterations = max_iterations or cfg.max_iterations
        migrate_every = max(1, cfg.migrate_every)
        n_rounds = math.ceil(max_iterations / migrate_every)

        meta_state = self.store.resume_state(ISLANDS_STATE_KEY) or {"round": 0}
        start_round = meta_state["round"]
        if start_round > 0:
            print(f"↺ Reprise îlots à la ronde {start_round + 1}/{n_rounds}")

        for r in range(start_round, n_rounds):
            target = min((r + 1) * migrate_every, max_iterations)
            print(f"\n{'━'*64}\n  RONDE {r+1}/{n_rounds} — {len(self.branches)} îlots "
                  f"→ itér ≤ {target}\n{'━'*64}")
            for k, br in enumerate(self.branches):
                print(f"\n▷ Îlot {br} …")
                self._loop_for(br).run(self._start_blocks(seed_blocks, k),
                                       max_iterations=target)
            # Migration en anneau + merge éventuel (idempotents à la reprise).
            self._migrate_ring()
            if cfg.crossover_every > 0 and (r + 1) % cfg.crossover_every == 0:
                self._crossover_round()
            meta_state["round"] = r + 1
            self.store.save_run_state(ISLANDS_STATE_KEY, meta_state)

        return self._summary()

    # ── Migration (D7) ───────────────────────────────────────────────────────

    def _migrate_ring(self) -> None:
        """Chaque îlot propose son meilleur nœud à l'îlot suivant (anneau)."""
        n = len(self.branches)
        if n < 2:
            return
        # Meilleurs nœuds capturés AVANT toute migration (on ne fait pas circuler un
        # migrant tout juste reçu dans la même ronde).
        bests = {}
        for br in self.branches:
            row = self.store.best(br, "train")
            bests[br] = row["hash"] if row else None
        for i, src in enumerate(self.branches):
            dst = self.branches[(i + 1) % n]
            if bests[src] is not None:
                self._migrate_one(dst, bests[src])

    def _migrate_one(self, dst_branch: str, migrant_node: str) -> None:
        state = self.store.resume_state(dst_branch)
        if state is None:
            return
        migrant_blocks = self.store.node_blocks(migrant_node)
        if migrant_blocks is None:
            return
        node_to = self.store.get_or_create_node(
            migrant_blocks, branch=dst_branch, parent=state["sa_node"],
            iteration=state["iteration"])
        if node_to == state["sa_node"]:
            return                                     # migrant = prompt courant → rien
        # Idempotence à la reprise : ne pas redoubler une migration déjà écrite.
        if self.store.conn.execute(
                "SELECT 1 FROM mutations WHERE branch=? AND operator='migrate' "
                "AND node_from=? AND node_to=? LIMIT 1",
                (dst_branch, state["sa_node"], node_to)).fetchone():
            return
        ev = self._evaluator_for(dst_branch)
        result, _ = ev.evaluate(node_to, migrant_blocks, "train", self.train,
                                desc=f"migrate→{dst_branch}")
        comp = result.scores.composite
        accepted = comp < state["sa_score"]
        self.store.record_mutation(
            branch=dst_branch, iteration=state["iteration"], node_from=state["sa_node"],
            node_to=node_to, operator="migrate", target_block="", new_content="",
            rationale=f"migration depuis {migrant_node}",
            verdict="accepted" if accepted else "rejected_score")
        print(f"  ⇄ migration → {dst_branch} : composite {comp:.2f} vs "
              f"{state['sa_score']:.2f} → {'adoptée' if accepted else 'rejetée'}")
        if accepted:
            state["sa_node"] = node_to
            state["sa_score"] = comp
            state["sa_scores"] = result.scores.model_dump(by_alias=True)
            if comp < state["best_score"]:
                state["best_node"] = node_to
                state["best_score"] = comp
            self.store.save_run_state(dst_branch, state)

    # ── Merge / crossover (8.3) ──────────────────────────────────────────────

    def _ablation_dicts(self, node_hash: str) -> list[dict]:
        return [{"bloc": a["block_name"], "delta": a["value"]}
                for a in self.store.ablations(node_hash)]

    def _crossover_round(self) -> None:
        """Fusionne deux parents complémentaires du front de Pareto (8.3)."""
        front = pareto.pareto_front(self.store.pareto_candidates("train"),
                                    self.base_config.pareto_dims)
        pair = pareto.complementary_pair(front, self.base_config.pareto_dims)
        if pair is None:
            return
        a, b = pair
        blocks_a, blocks_b = self.store.node_blocks(a["hash"]), self.store.node_blocks(b["hash"])
        if not blocks_a or not blocks_b:
            return
        merged, _ = self.mutator.propose_crossover(
            blocks_a, blocks_b, self._ablation_dicts(a["hash"]),
            self._ablation_dicts(b["hash"]))
        if not merged:
            return
        dst = self.branches[0]                         # le merge atterrit sur l'îlot 0
        state = self.store.resume_state(dst)
        if state is None:
            return
        node_to = self.store.get_or_create_node(
            merged, branch=dst, parent=a["hash"], parent2=b["hash"],
            iteration=state["iteration"])
        if self.store.conn.execute(
                "SELECT 1 FROM mutations WHERE operator='crossover' AND node_to=? LIMIT 1",
                (node_to,)).fetchone():
            return                                     # déjà tenté (reprise)
        ev = self._evaluator_for(dst)
        result, _ = ev.evaluate(node_to, merged, "train", self.train, desc="crossover")
        comp = result.scores.composite
        accepted = comp < state["sa_score"]
        self.store.record_mutation(
            branch=dst, iteration=state["iteration"], node_from=a["hash"], node_to=node_to,
            operator="crossover", target_block="", new_content="",
            rationale=f"merge {a['hash']}×{b['hash']}",
            verdict="accepted" if accepted else "rejected_score")
        print(f"  ✚ crossover {a['hash']}×{b['hash']} → {dst} : composite {comp:.2f} "
              f"→ {'adopté' if accepted else 'rejeté'}")
        if accepted:
            state["sa_node"] = node_to
            state["sa_score"] = comp
            state["sa_scores"] = result.scores.model_dump(by_alias=True)
            if comp < state["best_score"]:
                state["best_node"] = node_to
                state["best_score"] = comp
            self.store.save_run_state(dst, state)

    # ── Résumé ───────────────────────────────────────────────────────────────

    def _summary(self) -> dict:
        """Meilleur nœud (composite train) toutes branches confondues + par îlot."""
        per_branch = {}
        best_overall = None
        for br in self.branches:
            row = self.store.best(br, "train")
            if row is None:
                continue
            per_branch[br] = {"hash": row["hash"], "composite": row["composite"]}
            if best_overall is None or row["composite"] < best_overall["composite"]:
                best_overall = {"branch": br, "hash": row["hash"],
                                "composite": row["composite"]}
        return {"branches": self.branches, "per_branch": per_branch,
                "best": best_overall}
