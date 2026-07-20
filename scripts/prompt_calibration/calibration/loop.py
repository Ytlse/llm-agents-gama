"""Boucle d'optimisation (recuit simulé) reprenable — phase 1 du ticket 004.

Orchestre : run initial + attribution Shapley → itérations {mutation → éval train
→ score → veto collatéral → accepter/rejeter (recuit) → attribution Shapley} → éval
de validation périodique + early stopping. Tout est écrit dans le store (nœuds,
mutations, évals, ablations) et l'état de la boucle est snapshoté à chaque
itération dans ``run_state``.

**Reprise** (critère d'acceptation phase 1) : au démarrage, si le store contient
déjà l'état de la branche, la boucle repart exactement à l'itération suivante ;
l'init n'est rejouée que si le store ne contient aucun nœud pour le prompt seed.
Les mutations déjà jouées sont rejouées depuis le store et les évals déjà
calculées sont servies par le cache → zéro appel LLM redondant.
"""

from __future__ import annotations

import copy
import json
import math
from typing import Optional

import pandas as pd

from .bandit import UCBBandit
from .blocks import blocks_to_prompt, prompt_word_count
from .evaluation import Evaluator, decisions_to_df
from .metrics import _STRATA_DIMS, MODES, l1_error, worst_strata_modes
from .models import MUTATOR_OPERATORS, RunConfig, Scores, blocks_hash
from .mutation import MutationGenerator, apply_mutation
from .shapley import build_shapley_results, planned_permutations, shapley_scores
from .stats import (bootstrap_delta, bootstrap_verdict, noninferiority_verdict,
                    significance_threshold)
from .store import RunStore
from .tabu import TabuArchive

_GUARDED_DIMS = ["age", "occupation", "genre", "motif", "distance"]

# Opérateurs dont le bloc produit (``new_content``) est un argument comportemental
# capitalisable dans la bibliothèque (DL, phase 6.4).
_SNIPPET_OPS = {"insert", "modify", "condense", "merge_blocks", "split"}

# Verdicts de rejet qui entrent au tabu : une mutation évaluée puis rejetée pour ces
# raisons ne doit pas être resoumise à l'identique (garde-fou dur, toute config). La
# tenure du tabu la ré-autorise plus tard, quand le contexte a changé.
_TABU_ON_REJECT = {"rejected_score", "rejected_stat", "rejected_race", "vetoed"}


def run_shapley(store: RunStore, evaluator: Evaluator, blocks: list[dict],
                node_hash: str, records: list[dict], dataset: str,
                m_permutations: int, truncation_tol: float, seed: int,
                branch: str, label: str = "shapley") -> list[dict]:
    """Attribution de crédit Shapley (phase 5, DB) : contribution moyenne de chaque
    bloc mutable, redondances et synergies comprises.

    Les évals des coalitions passent par l'``Evaluator`` (donc par le cache
    content-addressed du store) : une coalition déjà vue — pendant ce calcul, un run
    précédent ou une permutation antérieure — ne rappelle pas le LLM. Les évals
    tournent sur ``records``/``dataset`` (le jeu de screening en usage réel).
    Résultats persistés dans ``ablations`` (``shapley``, détail par dimension dans
    ``scores_json``).
    """
    seen: dict[str, dict[str, float]] = {}
    stats = {"cache": 0, "paid": 0}

    def scores_fn(coalition: list[dict]) -> dict[str, float]:
        key = blocks_hash(coalition)
        if key in seen:
            return seen[key]
        node = store.get_or_create_node(coalition, branch=branch)
        # Hash court dans le libellé : deux coalitions de même taille (ex. le [2b]
        # de chaque permutation) sont ainsi discernables dans la console.
        tag = f"{label}[{len(coalition)}b:{node[:8]}]"
        hit = store.cached_eval(node, dataset,
                                evaluator.config.eval_params_key()) is not None
        stats["cache" if hit else "paid"] += 1
        if hit:
            print(f"  ✓ cache : {tag}")
        result, cdf = evaluator.evaluate(node, coalition, dataset, records,
                                         desc=tag)
        scores = result.scores.model_dump(by_alias=True)
        # Parts modales de la coalition, ajoutées comme composantes ``mode:{m}`` :
        # ``shapley_scores`` décompose chaque composante sur les MÊMES évals →
        # la matrice bloc × mode (φ par part modale) est gratuite.
        counts = (cdf["mode_cat"].value_counts()
                  if cdf is not None and not cdf.empty and "mode_cat" in cdf.columns
                  else {})
        total = (len(cdf) if cdf is not None else 0) or 1
        for m in MODES:
            scores[f"mode:{m}"] = counts.get(m, 0) / total * 100
        seen[key] = scores
        return seen[key]

    phi = shapley_scores(blocks, scores_fn, m_permutations=m_permutations,
                         truncation_tol=truncation_tol, seed=seed)
    print(f"  Shapley : {stats['paid']} coalition(s) payée(s), "
          f"{stats['cache']} servie(s) par le cache")
    results = build_shapley_results(blocks, phi,
                                    weights=getattr(evaluator.metric, "WEIGHTS", None))
    for r in results:
        # ``modes`` persistés avec le détail (clés ``mode:{m}``) : le backfill et le
        # dashboard les retrouvent dans ``scores_json`` sans re-calcul Shapley.
        stored = {**r["detail"],
                  **{f"mode:{m}": v for m, v in (r.get("modes") or {}).items()}}
        store.record_ablation(node_hash, r["bloc"], "shapley", r["delta"],
                              scores_json=json.dumps(stored, ensure_ascii=False),
                              diag=r["diag"])
    return results


class CalibrationLoop:
    def __init__(self, config: RunConfig, store: RunStore, evaluator: Evaluator,
                 mutator: MutationGenerator, cerema: dict,
                 train_records: list[dict], val_records: list[dict],
                 screen_records: Optional[list[dict]] = None):
        self.config = config
        self.store = store
        self.evaluator = evaluator
        self.mutator = mutator
        self.cerema = cerema
        self.train_records = train_records
        self.val_records = val_records
        self.screen_records = screen_records or []
        self.branch = config.branch

        # ── Phase 4 : entonnoir (DD) — actif seulement si k>1 candidats ET le
        # mutateur sait en produire ; sinon chemin single-candidat (phase 3),
        # ce qui préserve les doubles de test à contrat ``propose`` unique.
        self._use_funnel = (config.n_candidates > 1
                            and hasattr(mutator, "propose_candidates"))
        self.tabu = (TabuArchive(store, config.tabu_threshold, config.tabu_tenure)
                     if config.tabu_enabled else None)
        self.bandit = (UCBBandit(store, self.branch, MUTATOR_OPERATORS, config.bandit_c)
                       if config.bandit_enabled else None)

    # ── Init / reprise ───────────────────────────────────────────────────────

    def _init(self, seed_blocks: list[dict]) -> dict:
        seed_hash = self.store.get_or_create_node(seed_blocks, branch=self.branch,
                                                  iteration=0)
        print(f"▶ Run initial (branche={self.branch}, seed={seed_hash})…")
        result, _ = self.evaluator.evaluate(seed_hash, seed_blocks, "train",
                                            self.train_records, desc="run initial")
        best_score = result.scores.composite
        print(f"  Score initial composite={best_score:.2f}")
        print("▶ Attribution Shapley initiale…")
        ablation = self._shapley(seed_blocks, seed_hash, accepted=0)
        return {
            "iteration": 0, "accepted": 0,
            "sa_node": seed_hash, "sa_score": best_score,
            "sa_scores": result.scores.model_dump(by_alias=True),
            "best_node": seed_hash, "best_score": best_score,
            "val_best": math.inf, "val_no_improve": 0,
            "ablation": ablation,
            # Mémoire de leçons (synthèse roulante des rejets, DA-réflexion) : vide au
            # départ, alimentée par le champ ``reflection`` du mutateur à chaque tour.
            "lessons": "",
            "history": [{"iteration": 0, "scores": result.scores.model_dump(by_alias=True),
                         "best_score": best_score, "kept": True, "mutation": None,
                         "verdict": "accepted"}],
        }

    def _shapley(self, blocks: list[dict], node_hash: str,
                 accepted: int) -> list[dict]:
        """Attribution Shapley d'un nœud sur le jeu de screening (train à défaut).

        Recalcul GLOBAL de tous les blocs mutables, exécuté après chaque acceptation
        (et à l'init). Le cache content-addressed du store amortit le coût : les
        coalitions déjà évaluées ne rappellent pas le LLM.

        Deux régimes d'échantillonnage selon ``shapley_addon_per_accept`` :

        - **cumulatif** (``> 0``) : graine FIXE → le socle de permutations est
          rejoué à l'identique à chaque passe (les coalitions sans le bloc muté
          sont des cache hits ; seules celles contenant du contenu nouveau sont
          payées), et ``accepted × addon`` permutations fraîches s'y ajoutent
          (plafond ``shapley_max_permutations``) — la précision de φ croît au fil
          de la campagne pour un coût par passe borné ;
        - **historique** (``0``, défaut) : ré-échantillonnage complet à chaque
          passe (graine = ``accepted``), M constant.
        """
        cfg = self.config
        records = self.screen_records or self.train_records
        dataset = cfg.screen_dataset if self.screen_records else "train"
        if cfg.shapley_addon_per_accept > 0:
            m = planned_permutations(cfg.shapley_permutations,
                                     cfg.shapley_addon_per_accept, accepted,
                                     cfg.shapley_max_permutations)
            seed = 0            # graine fixe : socle stable par préfixe → cache
            if m > cfg.shapley_permutations:
                print(f"  🔷 Shapley cumulatif : {m} permutations "
                      f"(socle {cfg.shapley_permutations}, plafond "
                      f"{cfg.shapley_max_permutations})")
        else:
            m, seed = cfg.shapley_permutations, accepted
        return run_shapley(self.store, self.evaluator, blocks, node_hash, records,
                           dataset, m, cfg.shapley_truncation_tol,
                           seed=seed, branch=self.branch)

    def _sa_df(self, state: dict) -> Optional[pd.DataFrame]:
        """Reconstruit le df du nœud SA courant depuis son éval cachée."""
        cached = self.store.cached_eval(state["sa_node"], "train",
                                        self.config.eval_params_key())
        if cached is None:
            return None
        return decisions_to_df(cached.decisions, self.evaluator.metadata_by_id)

    # ── Ciblage de strate (racing, phase 4.6) ────────────────────────────────

    @staticmethod
    def _stratum_records(records: list[dict], dim: str, cat: str) -> list[dict]:
        """Sous-ensemble des ``records`` appartenant à la strate ``dim==cat``.

        ``dim`` est un libellé de :data:`metrics._STRATA_DIMS` (``genre``, ``motif``…) ;
        la colonne physique du record (``dist_cat`` pour ``distance``, ``age_cat`` pour
        ``age``, etc.) est résolue via cette table — mêmes clés que ``_record_metadata``.
        """
        col = next((c for d, c, _ in _STRATA_DIMS if d == dim), dim)
        return [r for r in records if r.get(col) == cat]

    def _stratum_gap(self, df: Optional[pd.DataFrame], dim: str, cat: str) -> float:
        """Écart L1 (points de %) de la strate ``dim==cat`` vs sa cible Cerema.

        Mesure locale (une seule strate) servant de critère au gate : plus bas =
        mieux. ``+inf`` si la strate est absente/vide du df (candidat inévaluable
        sur cette strate → ne peut pas prétendre l'améliorer)."""
        if df is None or df.empty or "mode_cat" not in df.columns:
            return math.inf
        col, cerema_key = next(((c, k) for d, c, k in _STRATA_DIMS if d == dim),
                               (dim, dim))
        parts = self.cerema["parts_modales_2023"]
        ref = parts.get(cerema_key, {}).get(cat)
        if ref is None or col not in df.columns:
            return math.inf
        sub = df[df[col] == cat]["mode_cat"].value_counts()
        if sub.sum() == 0:
            return math.inf
        return l1_error(sub, ref)

    # ── Bibliothèque de snippets (DL, phase 6.4) ─────────────────────────────

    def _under_mode(self, df: Optional[pd.DataFrame]) -> Optional[str]:
        """Mode le plus **sous-représenté** vs EMC² (le levier du moment)."""
        if df is None or df.empty or "mode_cat" not in df.columns:
            return None
        from .metrics import MODES
        cerema_g = self.cerema["parts_modales_2023"]["global"]
        total = len(df)
        dist = df["mode_cat"].value_counts()
        return min(MODES, key=lambda m: dist.get(m, 0) / total * 100 - cerema_g.get(m, 0))

    def _top_snippets(self, df: Optional[pd.DataFrame]) -> Optional[list[dict]]:
        """Meilleurs snippets pour le levier courant (mode sous-représenté), repli global.

        Fournit au mutateur les arguments comportementaux capitalisés les plus
        rentables (DL) — d'abord ceux qui ont aidé le mode sous-représenté, sinon
        les meilleurs toutes cibles. ``None`` si la bibliothèque est désactivée/vide.
        """
        if not self.config.snippets_enabled:
            return None
        mode = self._under_mode(df)
        rows = self.store.top_snippets(self.config.snippet_topk, tag_mode=mode)
        if not rows:
            rows = self.store.top_snippets(self.config.snippet_topk)
        return [dict(r) for r in rows] or None

    def _capture_snippet(self, mutation: dict, node_to: str,
                         df: Optional[pd.DataFrame], delta: float) -> None:
        """Capitalise un bloc accepté avec **gain significatif** (DL).

        ``delta = composite(muté) − composite(courant)`` (négatif = amélioration) →
        ``gain = −delta``. Seuls les opérateurs qui produisent un contenu de bloc
        réutilisable et un gain ≥ ``snippet_min_gain`` entrent dans la bibliothèque,
        taggés par le mode qu'ils ont aidé.
        """
        cfg = self.config
        gain = -delta
        action = mutation.get("action", "modify")
        content = mutation.get("new_content", "")
        if (not cfg.snippets_enabled or gain < cfg.snippet_min_gain
                or action not in _SNIPPET_OPS or not content.strip()):
            return
        self.store.record_snippet(
            node_origin=node_to, branch=self.branch, operator=action,
            block_name=mutation.get("target_block", ""), content=content,
            tag_mode=self._under_mode(df) or "", gain=gain)

    def _backfill_ablation_detail(self, state: dict) -> None:
        """Rétro-compat : un état snapshoté **avant** la décomposition par
        dimension (ou avant la matrice bloc × mode) n'a pas de champ ``detail``
        (resp. ``modes``) dans ses entrées d'ablation. On les reconstitue depuis la
        table ``ablations`` (``detail_from_stored`` / ``modes_from_stored``, mêmes
        règles que la carte du dashboard) — crochets par dimension et poussées
        modales sont ainsi fournis au mutateur dès la première itération reprise,
        sans attendre un recalcul Shapley ni payer une éval."""
        entries = [r for r in state.get("ablation", [])
                   if not r.get("detail") or "modes" not in r]
        weights = getattr(self.evaluator.metric, "WEIGHTS", None)
        if not entries or not weights:
            return
        from .mutation import detail_from_stored, modes_from_stored

        filled = 0
        for r in entries:
            row = self.store.conn.execute(
                "SELECT method, scores_json FROM ablations "
                "WHERE block_name=? AND ABS(value - ?) < 1e-6 "
                "ORDER BY id DESC LIMIT 1", (r["bloc"], r["delta"])).fetchone()
            if row is None or row["method"] != "shapley":
                r.setdefault("detail", {})
                r.setdefault("modes", {})
                continue
            stored = json.loads(row["scores_json"]) if row["scores_json"] else {}
            if not r.get("detail"):
                r["detail"] = detail_from_stored(stored, weights)
            if "modes" not in r:
                r["modes"] = modes_from_stored(stored)
            filled += bool(r["detail"] or r["modes"])
        if filled:
            print(f"  ↺ détail par dimension / modes reconstitués pour {filled}/"
                  f"{len(entries)} bloc(s) d'ablation (état antérieur)")

    # ── Mémoire de leçons (réflexion sur les rejets) ─────────────────────────

    def _absorb_reflection(self, state: dict, mutation: dict) -> None:
        """Met à jour la mémoire de leçons avec la synthèse du mutateur (champ
        ``reflection``).

        La synthèse résume les raisons RÉCURRENTES des rejets précédents (fond vs
        bruit) ; elle **remplace** la mémoire courante — mémoire roulante bornée à
        ``lessons_max_chars`` (anti-ancrage) — et sera réinjectée au tour suivant via
        ``build_mutation_user_msg``. No-op à la reprise/rejeu (mutation reconstruite
        depuis le store, sans champ ``reflection``) et si la réflexion est désactivée.
        """
        if not self.config.reflection_enabled:
            return
        refl = (mutation.get("reflection") or "").strip()
        if not refl:
            return
        cap = self.config.lessons_max_chars
        if len(refl) > cap:
            refl = refl[:cap].rstrip() + "…"
        state["lessons"] = refl

    # ── Garde-fou dur anti-resoumission (toute config) ───────────────────────

    def _single_prescreen(self, state: dict, sa_blocks: list[dict],
                          mutated: list[dict], mutation: dict) -> Optional[tuple[str, str]]:
        """Filtre dur d'une proposition **avant toute éval** (chemin single-candidat).

        Refuse une proposition qui **ne change rien** (prompt muté identique au prompt
        courant) ou **quasi identique à un rejet non expiré** (tabu) : dans les deux cas
        elle recevrait le même verdict → éval gaspillée. C'est le pendant, pour le chemin
        single-candidat (défaut), du filtre que l'entonnoir applique déjà dans
        ``_select_candidate`` — la règle « ne resoumets jamais le même texte ni une
        variante triviale » devient ainsi dure **quelle que soit la config**.

        Renvoie ``(verdict, cause)`` si la proposition est écartée, sinon ``None``.
        """
        if blocks_to_prompt(mutated) == blocks_to_prompt(sa_blocks):
            return "invalid", "aucun changement de texte"
        if self.tabu is not None:
            is_tabu, sim = self.tabu.is_tabu(mutation, state["accepted"])
            if is_tabu:
                return "rejected_tabu", f"cos={sim:.2f} (resoumission triviale)"
        return None

    # ── Boucle ───────────────────────────────────────────────────────────────

    def run(self, seed_blocks: list[dict],
            max_iterations: Optional[int] = None) -> dict:
        cfg = self.config
        max_iterations = max_iterations or cfg.max_iterations

        state = self.store.resume_state(self.branch)
        if state is None:
            state = self._init(seed_blocks)
            self.store.save_run_state(self.branch, state)
        else:
            print(f"↺ Reprise branche={self.branch} à l'itération "
                  f"{state['iteration'] + 1} (best={state['best_score']:.2f})")
            self._backfill_ablation_detail(state)

        ran_any = False
        for i in range(state["iteration"] + 1, max_iterations + 1):
            temperature = cfg.sa_t0 * (cfg.sa_alpha ** i)
            sa_blocks = self.store.node_blocks(state["sa_node"])
            sa_scores = Scores.model_validate(state["sa_scores"])

            # 1. Mutation — rejeu depuis le store, ou nouvelle proposition ──────
            row = self.store.mutation_row_at(self.branch, i)
            if row is not None and row["verdict"] and row["verdict"] != "proposed":
                # Itération déjà entièrement traitée (reprise pile sur la frontière).
                continue
            if row is not None:
                mutation = {"target_block": row["target_block"], "action": row["operator"],
                            "new_content": row["new_content"], "rationale": row["rationale"],
                            "second_block": (row["second_block"] or ""),
                            "anchor": (row["anchor"] or "")}
                mutation_id = row["id"]
            elif self._use_funnel:
                # Entonnoir (DD) : bandit → k candidats → tabu → screening → meilleur.
                sel = self._select_candidate(state, i)
                if sel is None:                       # aucun candidat évaluable
                    state["iteration"] = i
                    self.store.save_run_state(self.branch, state)
                    ran_any = True
                    continue
                mutation, mutation_id = sel
            else:
                # Chemin single-candidat (phase 3).
                sa_df = self._sa_df(state)
                try:
                    mutation, user_msg = self.mutator.propose(
                        sa_blocks, sa_df, state["sa_score"],
                        state["history"], state["ablation"],
                        snippets=self._top_snippets(sa_df),
                        lessons=state.get("lessons", ""))
                except Exception as exc:  # noqa: BLE001
                    print(f"  ⚠ mutation iter {i}: {exc}")
                    continue
                mutation_id = self.store.record_mutation(
                    branch=self.branch, iteration=i, node_from=state["sa_node"],
                    node_to=None, operator=mutation.get("action", "modify"),
                    target_block=mutation.get("target_block", ""),
                    new_content=mutation.get("new_content", ""),
                    rationale=mutation.get("rationale", ""), verdict="proposed",
                    mutation_prompt_text=user_msg)
            ran_any = True
            # Nouvelle proposition (single ou entonnoir) : on capitalise la synthèse
            # des rejets. No-op sur le rejeu depuis le store (mutation sans réflexion).
            self._absorb_reflection(state, mutation)

            print(f"{'═'*60}\n  Itér {i}/{max_iterations} | SA={state['sa_score']:.2f} "
                  f"| best={state['best_score']:.2f} | T={temperature:.2f} "
                  f"| bloc={mutation.get('target_block')} ({mutation.get('action')})")

            # 2. Appliquer ─────────────────────────────────────────────────────
            mutated = apply_mutation(sa_blocks, mutation)
            if mutated is None:
                self.store.update_mutation(mutation_id, verdict="invalid", node_to=None)
                state["history"].append({"iteration": i, "scores": sa_scores.model_dump(by_alias=True),
                                         "best_score": state["best_score"], "kept": False,
                                         "mutation": mutation, "verdict": "invalid"})
                state["iteration"] = i
                self.store.save_run_state(self.branch, state)
                print("  ⏭ mutation invalide")
                continue

            # 2b. Garde-fou dur anti-resoumission (chemin single-candidat) : proposition
            # sans changement réel, ou quasi-doublon d'un rejet non expiré → écartée SANS
            # éval. L'entonnoir applique déjà ce filtre dans ``_select_candidate``.
            if not self._use_funnel:
                pre = self._single_prescreen(state, sa_blocks, mutated, mutation)
                if pre is not None:
                    verdict, cause = pre
                    self.store.update_mutation(mutation_id, verdict=verdict,
                                               node_to=None, reject_cause=cause)
                    state["history"].append(
                        {"iteration": i, "scores": sa_scores.model_dump(by_alias=True),
                         "best_score": state["best_score"], "kept": False,
                         "mutation": mutation, "reject_cause": cause, "verdict": verdict})
                    state["iteration"] = i
                    self.store.save_run_state(self.branch, state)
                    print(f"  {verdict}  {cause}")
                    continue

            # 3. Évaluer sur le train ──────────────────────────────────────────
            node_to = self.store.get_or_create_node(mutated, branch=self.branch,
                                                    parent=state["sa_node"], iteration=i)

            # 3a. Paliers progressifs (25/50/75 %) — candidat unique. On évalue l'essai
            # sur une fraction croissante du train et on l'ABANDONNE dès qu'un palier
            # n'améliore pas le prompt courant : aucune éval complète payée pour un
            # essai non prometteur. (Le chemin multi-candidats fait son racing dans
            # ``_select_candidate`` ; ici on ne gate que le single-candidat.)
            if cfg.racing_enabled and not self._use_funnel:
                passed, cause = self._rung_gate(state, i, mutated, node_to)
                if not passed:
                    self.store.update_mutation(mutation_id, verdict="rejected_race",
                                               node_to=node_to, reject_cause=cause)
                    if self.tabu is not None:
                        self.tabu.add(mutation, mutation_id, state["accepted"])
                    state["history"].append(
                        {"iteration": i, "scores": sa_scores.model_dump(by_alias=True),
                         "best_score": state["best_score"], "kept": False,
                         "mutation": mutation, "reject_cause": cause,
                         "verdict": "rejected_race"})
                    state["iteration"] = i
                    self.store.save_run_state(self.branch, state)
                    print(f"  rejected_race  {cause}")
                    continue

            eval_cfg = self.evaluator.config
            batch_cap = eval_cfg.eval_batch_max or len(self.train_records)
            n_batches = math.ceil(len(self.train_records) / (batch_cap or 1))
            n_calls = n_batches * eval_cfg.eval_samples
            print(f"  → Éval. prompt muté sur {len(self.train_records)} décisions train ({n_calls} appels "
                  f"≈ {n_batches} lots × {eval_cfg.eval_samples} samples) via "
                  f"{eval_cfg.eval_provider}/{eval_cfg.eval_model} @ T={eval_cfg.eval_temp}…")
            result, df = self.evaluator.evaluate(node_to, mutated, "train",
                                                 self.train_records, desc=f"iter {i}")
            run_scores = result.scores
            composite = run_scores.composite

            # 3b. Veto collatéral ──────────────────────────────────────────────
            rs, bs = run_scores.model_dump(by_alias=True), sa_scores.model_dump(by_alias=True)
            collateral = [(d, rs.get(d, 0) - bs.get(d, 0)) for d in _GUARDED_DIMS
                          if rs.get(d, 0) - bs.get(d, 0) > cfg.collateral_tol]
            vetoed = bool(collateral)

            # 4. Meilleur toutes itérations ────────────────────────────────────
            if composite < state["best_score"] and not vetoed:
                state["best_node"] = node_to
                state["best_score"] = composite
                print(f"  🏆 nouveau meilleur : {composite:.2f}")

            # 5. Accepter / rejeter ────────────────────────────────────────────
            delta = composite - state["sa_score"]
            if vetoed:
                accept, verdict = False, "vetoed"
                reject_cause = ", ".join(f"{d} +{v:.0f}" for d, v in collateral)
            elif cfg.accept_test == "bootstrap":
                accept, verdict, reject_cause = self._bootstrap_accept(
                    state, sa_blocks, mutated, df, run_scores, temperature, seed=i)
            else:
                accept, verdict = self._anneal_accept(delta, temperature)
                reject_cause = ""
            self.store.update_mutation(mutation_id, verdict=verdict, node_to=node_to,
                                       reject_cause=reject_cause)

            # Récompense du bandit (DE) : le bras = l'opérateur du candidat retenu ;
            # récompense = 1 si l'amélioration a été acceptée, 0 sinon.
            if self.bandit is not None and self._use_funnel:
                self.bandit.update(mutation.get("action", "modify"), 1.0 if accept else 0.0)

            # Archive tabu dure (D3) : une mutation évaluée puis rejetée entre au
            # tabu → ses quasi-doublons seront écartés sans éval jusqu'à expiration
            # de la tenure. Actif **quelle que soit la config** (single ET entonnoir) :
            # c'est le garde-fou dur derrière « ne resoumets jamais le même texte ».
            # Sa cause de rejet nourrit déjà le mutateur (reject_cause).
            if not accept and self.tabu is not None and verdict in _TABU_ON_REJECT:
                self.tabu.add(mutation, mutation_id, state["accepted"])

            if accept:
                state["accepted"] += 1
                state["sa_node"] = node_to
                state["sa_score"] = composite
                state["sa_scores"] = run_scores.model_dump(by_alias=True)
                self._capture_snippet(mutation, node_to, df, delta)
                self._update_ablation(state, mutated, node_to)
                # Passe de compaction périodique (DM) : minimiser le prompt à score constant.
                if cfg.compact_every > 0 and state["accepted"] % cfg.compact_every == 0:
                    self._compaction_pass(state, seed=i * 1000)

            state["history"].append({"iteration": i,
                                     "scores": run_scores.model_dump(by_alias=True),
                                     "best_score": state["best_score"], "kept": accept,
                                     "mutation": mutation, "reject_cause": reject_cause,
                                     "verdict": verdict})
            print(f"  {verdict}  composite={composite:.2f} (Δ={delta:+.2f})")

            # 6. Validation + early stopping ───────────────────────────────────
            if i % cfg.val_every == 0 and self.val_records:
                if self._validate(state, i):
                    state["iteration"] = i
                    self.store.save_run_state(self.branch, state)
                    print("  🛑 early stopping")
                    break

            state["iteration"] = i
            self.store.save_run_state(self.branch, state)

        # Compaction systématique en fin de campagne (DM) — seulement si des
        # itérations ont réellement tourné ce lancement (évite le doublon à la
        # reprise pure, où tout est déjà joué).
        if ran_any and cfg.compact_every > 0:
            print("▶ Compaction finale (fin de campagne)…")
            self._compaction_pass(state, seed=999_000)
            self.store.save_run_state(self.branch, state)

        best_words = prompt_word_count(self.store.node_blocks(state["best_node"]))
        print(f"\n✅ Calibration terminée — best composite={state['best_score']:.2f} "
              f"(nœud {state['best_node']}, {best_words} mots)")
        return state

    # ── Entonnoir multi-candidats (DD) ────────────────────────────────────────

    def _select_candidate(self, state: dict, i: int) -> Optional[tuple[dict, int]]:
        """Bandit → k candidats → filtre tabu → screening → meilleur candidat.

        Enregistre au passage les candidats rejetés (tabu / invalides) avec leur
        verdict, puis le candidat retenu en ``proposed`` (dernière ligne de
        l'itération → repris tel quel par ``mutation_row_at``). Renvoie
        ``(mutation, mutation_id)`` ou ``None`` si aucun candidat n'est évaluable.
        """
        cfg = self.config
        sa_blocks = self.store.node_blocks(state["sa_node"])
        sa_df = self._sa_df(state)
        sa_prompt = blocks_to_prompt(sa_blocks)
        suggested = self.bandit.select() if self.bandit is not None else None
        try:
            candidates, user_msg = self.mutator.propose_candidates(
                sa_blocks, sa_df, state["sa_score"], state["history"], state["ablation"],
                n_candidates=cfg.n_candidates, suggested_operator=suggested,
                snippets=self._top_snippets(sa_df), lessons=state.get("lessons", ""))
        except Exception as exc:  # noqa: BLE001
            print(f"  ⚠ mutation iter {i}: {exc}")
            return None
        if not candidates:
            return None
        print(f"  🎣 {len(candidates)} candidat(s) proposé(s) "
              f"(opérateur suggéré : {suggested})")
        for k, cand in enumerate(candidates, 1):
            rationale = (cand.get("rationale", "") or "").strip().replace("\n", " ")
            if len(rationale) > 80:
                rationale = rationale[:77] + "…"
            print(f"      {k}. {cand.get('action', 'modify')}/{cand.get('target_block', '')}"
                  + (f" — {rationale}" if rationale else ""))

        def _record(cand: dict, verdict: str, cause: str = "") -> int:
            return self.store.record_mutation(
                branch=self.branch, iteration=i, node_from=state["sa_node"], node_to=None,
                operator=cand.get("action", "modify"),
                target_block=cand.get("target_block", ""),
                new_content=cand.get("new_content", ""),
                rationale=cand.get("rationale", ""), verdict=verdict, reject_cause=cause,
                mutation_prompt_text=user_msg, second_block=cand.get("second_block", ""),
                anchor=cand.get("anchor", ""))

        # 1. Filtre tabu (gratuit) + validité / no-op + diversité de cible.
        survivors: list[tuple[dict, list[dict]]] = []
        targeted: set[str] = set()
        for cand in candidates:
            if self.tabu is not None:
                is_t, sim = self.tabu.is_tabu(cand, state["accepted"])
                if is_t:
                    _record(cand, "rejected_tabu", f"cos={sim:.2f}")
                    print(f"    ⛔ tabu {cand.get('action')}/{cand.get('target_block')} (cos={sim:.2f})")
                    continue
            # Diversité : un seul candidat par bloc réellement modifié (le mutateur
            # tend à ré-empiler le même bloc). On garde le premier, on écarte les
            # doublons sans les évaluer → le screening compare des blocs distincts.
            # ``insert`` crée un NOUVEAU bloc : il ne rentre pas en collision avec un
            # ``modify`` du même point d'ancrage (clé action-consciente).
            target = cand.get("target_block", "")
            action = cand.get("action", "modify")
            div_key = f"insert::{target}::{i}::{len(survivors)}" if action == "insert" else target
            if div_key in targeted:
                _record(cand, "rejected_dup_block", f"bloc={target}")
                print(f"    ♻ doublon de bloc écarté : {action}/{target}")
                continue
            applied = apply_mutation(sa_blocks, cand)
            if applied is None or blocks_to_prompt(applied) == sa_prompt:
                _record(cand, "invalid")
                continue
            targeted.add(div_key)
            survivors.append((cand, applied))

        if not survivors:
            return None

        print(f"    ➡ {len(survivors)} survivant(s) après filtre "
              f"(tabu/doublon/invalide) : "
              + ", ".join(f"{c.get('action')}/{c.get('target_block')}"
                          for c, _ in survivors))

        # 2. Sélection : racing ciblé par strate (4.6) OU screening one-shot (4.2).
        if cfg.racing_enabled and len(survivors) > 1:
            best_cand = self._race_candidates(state, i, survivors, _record)
        elif self.screen_records and len(survivors) > 1:
            # Screening (~20 % du train) → le meilleur composite passe l'éval complète.
            scored = []
            for cand, applied in survivors:
                node = self.store.get_or_create_node(applied, branch=self.branch,
                                                     parent=state["sa_node"])
                res, _ = self.evaluator.evaluate(
                    node, applied, cfg.screen_dataset, self.screen_records,
                    desc=f"screen[{cand.get('action')}/{cand.get('target_block')}]")
                scored.append((res.scores.composite, cand))
            scored.sort(key=lambda x: x[0])
            best_cand = scored[0][1]
            print(f"    🔎 screening ({len(scored)} candidats, jeu "
                  f"'{cfg.screen_dataset}') :")
            for rank, (comp, cand) in enumerate(scored, 1):
                mark = "✓ retenu" if rank == 1 else "✗ écarté"
                print(f"       {mark} {cand.get('action')}/{cand.get('target_block')} "
                      f"screen={comp:.2f}")
        else:
            best_cand = survivors[0][0]
            if len(survivors) > 1:
                # Pas de départage possible (jeu 'screen' absent, racing off) : on
                # prend le 1ᵉʳ survivant. Éval complète (+ bootstrap) reste le juge.
                print(f"    ⚠ ni racing ni jeu '{cfg.screen_dataset}' → aucun "
                      f"départage, 1ᵉʳ survivant retenu : {best_cand.get('action')}/"
                      f"{best_cand.get('target_block')} ({len(survivors) - 1} autre(s) "
                      f"non évalué(s))")
            else:
                print(f"    → 1 seul survivant : {best_cand.get('action')}/"
                      f"{best_cand.get('target_block')}")

        mutation_id = _record(best_cand, "proposed")
        return best_cand, mutation_id

    # ── Racing ciblé par strate (successive halving, phase 4.6) ───────────────

    def _race_candidates(self, state: dict, i: int,
                         survivors: list[tuple[dict, list[dict]]],
                         record) -> dict:
        """Gate strate (tour 0) + successive halving → unique survivant.

        - **Gate** (périodique, ``racing_target_every``) : évalue chaque candidat
          sur les seuls agents de la strate la plus mal représentée et élimine ceux
          qui n'améliorent pas son écart (``rejected_gate``) ; si le gate vide la
          liste, **repli global** (tous repassent en racing, on ne bloque pas l'itération).
        - **Racing** : évaluation sur une fraction croissante du train
          (``racing_rungs``) ; à chaque palier on garde la meilleure moitié
          (``racing_keep_frac``), sans jamais départager deux candidats à moins de
          ``racing_min_gap`` (ou dont l'IC bootstrap chevauche — ``bootstrap_delta``),
          qui restent alors tous deux en lice (``rejected_race`` pour les éliminés).

        Chaque palier passe par ``Evaluator.evaluate`` → le cache content-addressed
        sert toute coalition déjà vue (palier antérieur, run précédent). Renvoie le
        candidat retenu (jamais ``None`` : au pire l'unique survivant du dernier palier).
        """
        cfg = self.config
        alive = list(survivors)

        # ── Tour 0 : gate sur la strate la plus mal représentée ──────────────
        sa_df = self._sa_df(state)
        if (cfg.racing_target_gate and cfg.racing_target_every > 0
                and i % cfg.racing_target_every == 0
                and sa_df is not None and not sa_df.empty):
            rows = worst_strata_modes(sa_df, self.cerema)
            if rows:
                dim, cat = rows[0]["dim"], rows[0]["cat"]
                sub = self._stratum_records(self.train_records, dim, cat)
                sa_gap = self._stratum_gap(sa_df, dim, cat)
                if len(sub) < cfg.racing_min_n or not math.isfinite(sa_gap):
                    print(f"    🎯 gate {dim}[{cat}] sauté (strate trop faible : "
                          f"n={len(sub)} < {cfg.racing_min_n})")
                else:
                    print(f"    🎯 gate strate {dim}[{cat}] (écart SA={sa_gap:.1f}, "
                          f"n={len(sub)}) sur {len(alive)} candidat(s)")
                    # Label de dataset dédié : un sous-ensemble de ``train`` ne doit
                    # PAS collisionner avec l'éval full-train du même nœud dans le
                    # cache (clé = nœud × dataset × params). ``train`` reste réservé
                    # à la seule éval complète (rung f≥1.0), réutilisée par la boucle.
                    gate_ds = f"gate:{dim}:{cat}"
                    gated: list[tuple[dict, list[dict]]] = []
                    failed: list[tuple[dict, str]] = []
                    for cand, applied in alive:
                        node = self.store.get_or_create_node(
                            applied, branch=self.branch, parent=state["sa_node"])
                        _, cdf = self.evaluator.evaluate(
                            node, applied, gate_ds, sub,
                            desc=f"gate[{dim}/{cat}·{cand.get('action')}]")
                        gap = self._stratum_gap(cdf, dim, cat)
                        if gap < sa_gap:
                            gated.append((cand, applied))
                        else:
                            failed.append((cand, f"{dim}[{cat}] {gap:.1f}≥{sa_gap:.1f}"))
                    if gated:
                        # Au moins un candidat améliore la strate → les autres sont
                        # bel et bien éliminés (``rejected_gate``).
                        for cand, cause in failed:
                            record(cand, "rejected_gate", cause)
                            print(f"      ⛔ gate {cand.get('action')}/"
                                  f"{cand.get('target_block')} ({cause})")
                        alive = gated
                    else:
                        # Repli global : personne n'améliore la strate → on ne bloque
                        # pas l'itération, tous les survivants repassent en racing
                        # (aucun ``rejected_gate`` : ils restent en lice).
                        print("      ↩ gate a tout éliminé → repli global "
                              "(tous les candidats repassent en racing)")

        # ── Tours suivants : successive halving sur des fractions croissantes ─
        n_train = len(self.train_records)
        metric = self.evaluator.metric
        for f in cfg.racing_rungs:
            if len(alive) <= 1:
                break
            k = max(1, min(n_train, int(round(f * n_train))))
            subset = self.train_records[:k]
            # ``train`` uniquement pour l'éval COMPLÈTE (f≥1.0) : elle est identique
            # à celle que la boucle refera pour le gagnant → servie par le cache.
            # Les paliers partiels ont leur propre label (pas de collision de cache).
            rung_ds = "train" if k >= n_train else f"race:{f:.2f}"
            scored = []
            for cand, applied in alive:
                node = self.store.get_or_create_node(applied, branch=self.branch,
                                                     parent=state["sa_node"])
                res, cdf = self.evaluator.evaluate(
                    node, applied, rung_ds, subset, desc=f"race[f={f:.2f}·n={k}]")
                scored.append((res.scores.composite, cand, applied, cdf))
            scored.sort(key=lambda x: x[0])
            keep = max(1, math.ceil(cfg.racing_keep_frac * len(scored)))
            last_comp, _, last_applied, last_df = scored[keep - 1]
            print(f"    🏁 palier f={f:.2f} (n={k}) : {len(alive)} candidat(s), "
                  f"garde les {keep} meilleur(s) (seuil composite≈{last_comp:.2f})")
            kept = scored[:keep]
            for comp, cand, applied, cdf in kept:                # au-dessus du couperet
                print(f"       ✓ {cand.get('action')}/{cand.get('target_block')} "
                      f"composite={comp:.2f}")
            for comp, cand, applied, cdf in scored[keep:]:       # sous le couperet
                tag = f"{cand.get('action')}/{cand.get('target_block')}"
                gap = comp - last_comp                     # ≥ 0 : candidat plus mauvais
                if gap < cfg.racing_min_gap:
                    kept.append((comp, cand, applied, cdf))  # trop proche → garde-fou
                    print(f"       ≈ {tag} composite={comp:.2f} "
                          f"(Δ={gap:+.2f}<{cfg.racing_min_gap} → gardé, garde-fou)")
                    continue
                summary = bootstrap_delta(
                    last_df, cdf, metric, self.cerema,
                    blocks_to_prompt(last_applied), blocks_to_prompt(applied),
                    b=cfg.bootstrap_b, seed=i * 1000 + k)
                if summary is not None and summary["ci_lo"] <= 0.0 <= summary["ci_hi"]:
                    kept.append((comp, cand, applied, cdf))  # IC chevauchant → garde-fou
                    print(f"       ≈ {tag} composite={comp:.2f} "
                          f"(IC90 Δ=[{summary['ci_lo']:+.2f},{summary['ci_hi']:+.2f}] "
                          f"chevauche 0 → gardé, garde-fou)")
                else:
                    record(cand, "rejected_race", f"Δ={gap:+.2f}@n={k}")
                    print(f"       ✗ {tag} composite={comp:.2f} éliminé "
                          f"(Δ={gap:+.2f} vs seuil@n={k})")
            print(f"    🏁 → {len(kept)} survivant(s) (meilleur composite={scored[0][0]:.2f})")
            alive = [(cand, applied) for _, cand, applied, _ in kept]

        best_cand = alive[0][0]
        print(f"    🏆 racing : retenu {best_cand.get('action')}/"
              f"{best_cand.get('target_block')}")
        return best_cand

    # ── Paliers progressifs (candidat unique, phase 4.6) ──────────────────────

    def _rung_gate(self, state: dict, i: int, mutated: list[dict],
                   node_to: str) -> tuple[bool, str]:
        """Arrêt précoce d'un essai unique le long des paliers ``racing_rungs``.

        Pour chaque fraction croissante du train (défaut 25/50/75 %), on compare le
        composite de l'essai à celui du prompt courant (``sa_node``) sur **le même
        sous-échantillon**. Dès qu'un palier n'apporte **aucune amélioration**
        (``Δ = essai − courant ≥ 0``), on renvoie ``(False, cause)`` : l'essai est
        abandonné sans jamais payer l'éval complète. S'il franchit tous les paliers,
        on renvoie ``(True, "")`` et la boucle enchaîne l'éval complète + le bootstrap.

        Les évals partielles passent par le cache content-addressed (label ``race:{f}``,
        distinct de ``train``) : le baseline ``sa_node`` est mis en cache et réutilisé
        tant qu'aucune mutation n'est acceptée.
        """
        cfg = self.config
        n_train = len(self.train_records)
        sa_blocks = self.store.node_blocks(state["sa_node"])
        for f in cfg.racing_rungs:
            if f >= 1.0:
                continue  # l'éval complète (f≥1.0) est faite par la boucle juste après
            k = max(1, min(n_train, int(round(f * n_train))))
            subset = self.train_records[:k]
            rung_ds = f"race:{f:.2f}"
            cand_res, _ = self.evaluator.evaluate(
                node_to, mutated, rung_ds, subset, desc=f"palier[f={f:.2f}·n={k}]")
            base_res, _ = self.evaluator.evaluate(
                state["sa_node"], sa_blocks, rung_ds, subset,
                desc=f"palier-SA[f={f:.2f}·n={k}]")
            gap = cand_res.scores.composite - base_res.scores.composite
            verdict = "améliore" if gap < 0 else "n'améliore pas → arrêt"
            print(f"    🏁 palier f={f:.2f} (n={k}) : essai={cand_res.scores.composite:.2f} "
                  f"vs courant={base_res.scores.composite:.2f} (Δ={gap:+.2f}) → {verdict}")
            if gap >= 0.0:
                return False, f"palier f={f:.2f} Δ={gap:+.2f}@n={k}"
        return True, ""

    # ── Passe de compaction (DM) ──────────────────────────────────────────────

    def _compaction_pass(self, state: dict, seed: int) -> None:
        """Minimise le prompt à score constant : suppression des blocs de
        contribution ≈ nulle sous test de **non-infériorité** bootstrap (§4.5).

        Candidats = blocs mutables de ``|Δ ablation| < compact_abl_tol``, triés du
        plus long au plus court. Chaque suppression est tentée puis acceptée si la
        borne haute de l'IC90 du Δ composite reste sous ``compact_margin`` — « réduire
        tant que ça ne dégrade pas le score ». Les suppressions sont des mutations
        normales (``operator='compact_delete'``) : visibles au dashboard, réversibles
        par lignage.
        """
        cfg = self.config
        abl_by_block = {r["bloc"]: r["delta"] for r in state.get("ablation", [])}
        sa_blocks = self.store.node_blocks(state["sa_node"])
        candidates = [b for b in sa_blocks
                      if b["mutable"] and b["name"] != "json_schema"
                      and abs(abl_by_block.get(b["name"], 0.0)) < cfg.compact_abl_tol]
        candidates.sort(key=lambda b: len(b["content"]), reverse=True)
        if not candidates:
            return
        print(f"  ✂ compaction : {len(candidates)} bloc(s) candidat(s) "
              f"(prompt = {prompt_word_count(sa_blocks)} mots)")

        for k, block in enumerate(candidates):
            current = self.store.node_blocks(state["sa_node"])
            if not any(b["name"] == block["name"] for b in current):
                continue                                   # déjà retiré
            mutation = {"target_block": block["name"], "action": "compact_delete",
                        "new_content": "",
                        "rationale": "compaction : bloc de contribution ≈ nulle"}
            compacted = apply_mutation(current, mutation)
            if compacted is None or blocks_to_prompt(compacted) == blocks_to_prompt(current):
                continue
            node_to = self.store.get_or_create_node(compacted, branch=self.branch,
                                                    parent=state["sa_node"])
            mut_id = self.store.record_mutation(
                branch=self.branch, iteration=state["iteration"],
                node_from=state["sa_node"], node_to=None, operator="compact_delete",
                target_block=block["name"], new_content="", rationale=mutation["rationale"],
                verdict="proposed")
            result, df = self.evaluator.evaluate(
                node_to, compacted, "train", self.train_records,
                desc=f"compaction[{block['name']}]")
            cur_df = self._sa_df(state)
            summary = bootstrap_delta(
                cur_df, df, self.evaluator.metric, self.cerema,
                blocks_to_prompt(current), blocks_to_prompt(compacted),
                b=cfg.bootstrap_b, seed=seed + k)
            accept, cause = noninferiority_verdict(summary, cfg.compact_margin)
            verdict = "accepted" if accept else "rejected_stat"
            self.store.update_mutation(mut_id, verdict=verdict, node_to=node_to,
                                       reject_cause=cause)
            if accept:
                state["sa_node"] = node_to
                state["sa_score"] = result.scores.composite
                state["sa_scores"] = result.scores.model_dump(by_alias=True)
                state["compacted"] = state.get("compacted", 0) + 1
                state["ablation"] = [r for r in state["ablation"]
                                     if r["bloc"] != block["name"]]
                if result.scores.composite < state["best_score"]:
                    state["best_node"] = node_to
                    state["best_score"] = result.scores.composite
                state["history"].append(
                    {"iteration": state["iteration"],
                     "scores": result.scores.model_dump(by_alias=True),
                     "best_score": state["best_score"], "kept": True, "mutation": mutation,
                     "verdict": "accepted"})
                print(f"    ✂ retiré {block['name']} → {prompt_word_count(compacted)} mots "
                      f"(composite={result.scores.composite:.2f})")

    # ── Décision d'acceptation ────────────────────────────────────────────────

    @staticmethod
    def _anneal_accept(delta: float, temperature: float) -> tuple[bool, str]:
        """Recuit simple (phase 1) : accepte toute amélioration, + les dégradations
        sous la température courante (exploration à chaud)."""
        if delta < 0:
            return True, "accepted"
        if temperature > 0.5 and delta < temperature:
            return True, "accepted"
        return False, "rejected_score"

    def _bootstrap_accept(self, state: dict, sa_blocks: list[dict],
                          mutated: list[dict], mut_df: pd.DataFrame,
                          run_scores: Scores, temperature: float,
                          seed: int) -> tuple[bool, str, str]:
        """Acceptation statistique (phase 3, DA) : bootstrap apparié sur les agents.

        Une mutation n'est acceptée que si l'amélioration du composite est
        significative (``p_improve ≥ seuil``) ; le seuil est assoupli à chaud par
        le recuit, jamais le signe. Repli sur le signe ponctuel si l'appariement
        bootstrap est impossible (aucun agent commun).
        """
        cfg = self.config
        sa_df = self._sa_df(state)
        summary = None
        if sa_df is not None:
            summary = bootstrap_delta(
                sa_df, mut_df, self.evaluator.metric, self.cerema,
                blocks_to_prompt(sa_blocks), blocks_to_prompt(mutated),
                b=cfg.bootstrap_b, seed=seed)
        if summary is None:
            point = run_scores.composite - state["sa_score"]
            if point < 0:
                return True, "accepted", ""
            return False, "rejected_score", f"Δ={point:+.2f} (bootstrap indisponible)"
        threshold = significance_threshold(temperature, cfg.sa_t0,
                                           cfg.bootstrap_conf_min, cfg.bootstrap_conf_max)
        return bootstrap_verdict(summary, threshold)

    def _update_ablation(self, state: dict, blocks: list[dict], node_hash: str) -> None:
        # Recalcul GLOBAL Shapley après CHAQUE acceptation : il répartit exactement
        # le gain entre tous les blocs, redondances et synergies comprises. Le cache
        # content-addressed du store amortit le coût (coalitions déjà vues gratuites).
        dataset = self.config.screen_dataset if self.screen_records else "train"
        print(f"  🔷 attribution Shapley (accepted={state['accepted']}, jeu={dataset})")
        state["ablation"] = self._shapley(blocks, node_hash,
                                          accepted=state["accepted"])

    def _validate(self, state: dict, iteration: int) -> bool:
        best_blocks = self.store.node_blocks(state["best_node"])
        result, _ = self.evaluator.evaluate(state["best_node"], best_blocks, "val",
                                            self.val_records, desc=f"val {iteration}")
        val_comp = result.scores.composite
        if val_comp < state["val_best"]:
            state["val_best"] = val_comp
            state["val_no_improve"] = 0
            print(f"  📊 val={val_comp:.2f} ↓ (nouveau meilleur val)")
        else:
            state["val_no_improve"] += 1
            print(f"  📊 val={val_comp:.2f} (no_improve={state['val_no_improve']}"
                  f"/{self.config.early_stop_patience})")
        return state["val_no_improve"] >= self.config.early_stop_patience
