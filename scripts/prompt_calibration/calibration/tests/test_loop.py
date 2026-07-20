"""Test de bout en bout de la boucle reprenable — critère d'acceptation phase 1.

« Tuer le process en pleine itération N, relancer → la boucle repart à N sans
aucun appel LLM redondant. » On simule cela avec un évaluateur et un mutateur
déterministes (aucun réseau) et on vérifie que la reprise ne rappelle jamais le
provider ni le mutateur pour des itérations déjà jouées.
"""

import pytest

from calibration.evaluation import Evaluator
from calibration.loop import CalibrationLoop
from calibration.metrics import L1Composite
from calibration.models import RunConfig
from calibration.mutation import MutationGenerator
from calibration.store import RunStore
from .test_metrics import CEREMA


def _rec(agent_id):
    section = (f"--- agent_id={agent_id} | Destination : work | Départ : 08:00 ---\n"
               "Persona. Options : foot.")
    return {"agent_id": str(agent_id), "section": section, "context": "Météo : sec.",
            "age": 30, "age_cat": "20-24", "occupation": "actif_temps_plein",
            "genre": "Homme", "motif": "travail", "dist_cat": "1-2km"}


class _DetCall:
    """Décisions déterministes fonction du prompt système → scores reproductibles."""

    def __init__(self):
        self.calls = 0

    def __call__(self, entry):
        self.calls += 1
        prompt = entry["messages"][0]["content"]
        # Le nombre de mots du prompt biaise le mode → prompts différents,
        # scores différents, donc accept/reject non triviaux.
        modes = ["foot", "car", "bicycle", "foot,bus,foot"]
        pick = modes[len(prompt.split()) % len(modes)]
        return [{"agent_id": aid, "mode": pick} for aid in entry["meta"]]


class _DetMutator:
    """Mutateur déterministe : à l'itération i, modifie intro_s1 avec un texte fixe."""

    def __init__(self):
        self.calls = 0

    def propose(self, blocks, df, best_score, history, ablation, snippets=None, lessons=None):
        self.calls += 1
        i = len([h for h in history if h["iteration"] > 0]) + 1
        mutation = {"target_block": "intro_s1", "action": "modify",
                    "new_content": f"Version numero {i} du bloc intro.",
                    "rationale": f"iter {i}"}
        return mutation, f"user msg iter {i}"  # (mutation, prompt) — contrat courant


class _ReflectMutator:
    """Mutateur qui émet une réflexion et journalise la mémoire de leçons reçue.

    Permet de vérifier l'aller-retour : la synthèse (``reflection``) produite à un
    tour est absorbée dans ``state['lessons']`` puis réinjectée au tour suivant."""

    def __init__(self):
        self.calls = 0
        self.lessons_seen = []

    def propose(self, blocks, df, best_score, history, ablation, snippets=None, lessons=None):
        self.calls += 1
        self.lessons_seen.append(lessons)
        i = len([h for h in history if h["iteration"] > 0]) + 1
        return ({"target_block": "intro_s1", "action": "modify",
                 "new_content": f"Version numero {i} du bloc intro.",
                 "rationale": f"iter {i}",
                 "reflection": f"lecon apres iter {i}"}, f"user msg iter {i}")


def test_reflection_absorbed_and_reinjected(tmp_path):
    """La réflexion émise à l'itération i alimente ``state['lessons']`` et est
    réinjectée au mutateur à l'itération i+1 (mémoire roulante bornée, persistée)."""
    call, mutator = _DetCall(), _ReflectMutator()
    _, store, loop = _make_loop(tmp_path, call, mutator)
    state = loop.run(SEED, max_iterations=3)

    # Mémoire non vide en fin de run (dernière synthèse absorbée).
    assert state["lessons"].startswith("lecon apres iter")
    # 1er tour : aucune leçon ; tours suivants : la leçon du tour précédent est servie.
    assert mutator.lessons_seen[0] in ("", None)
    assert mutator.lessons_seen[1] == "lecon apres iter 1"
    assert mutator.lessons_seen[2] == "lecon apres iter 2"
    # Persistée dans run_state (survit à la reprise).
    assert store.resume_state("main")["lessons"] == state["lessons"]
    store.close()


def test_reflection_disabled_keeps_lessons_empty(tmp_path):
    """``reflection_enabled=False`` : aucune mémoire n'est constituée ni injectée."""
    call, mutator = _DetCall(), _ReflectMutator()
    config = RunConfig(store_path=tmp_path / "r.db", eval_rpm=100000, eval_samples=1,
                       eval_batch_max=10, eval_workers=1, max_iterations=3,
                       val_every=100, branch="main",
                       accept_test="sa", compact_every=0, reflection_enabled=False)
    store = RunStore(config.store_path)
    records = [_rec(i) for i in range(6)]
    meta = {r["agent_id"]: r for r in records}
    evaluator = Evaluator(config, store, L1Composite(0.0), CEREMA, meta, call)
    loop = CalibrationLoop(config, store, evaluator, mutator, CEREMA, records, [])
    state = loop.run(SEED, max_iterations=3)
    assert state["lessons"] == ""
    assert all(l in ("", None) for l in mutator.lessons_seen)
    store.close()


class _FixedMutator:
    """Propose EXACTEMENT la même mutation à chaque tour (test du garde-fou dur)."""

    FIXED = "Contenu fixe repropose identique a chaque tour ici."

    def __init__(self):
        self.calls = 0

    def propose(self, blocks, df, best_score, history, ablation, snippets=None, lessons=None):
        self.calls += 1
        return ({"target_block": "intro_s1", "action": "modify",
                 "new_content": self.FIXED, "rationale": "fixe"}, "user msg")


def test_hard_guard_blocks_identical_resubmission_single(tmp_path):
    """Chemin single-candidat (défaut) : une proposition resoumise à l'identique est
    écartée SANS éval — ``rejected_tabu`` si la 1ʳᵉ tentative a été rejetée, ``invalid``
    (no-op) si elle a été acceptée puis re-proposée telle quelle. Le nœud muté n'est
    évalué qu'une seule fois : le garde-fou est bien dur, quelle que soit la config."""
    from calibration.models import blocks_hash

    call, mutator = _DetCall(), _FixedMutator()
    config = RunConfig(store_path=tmp_path / "h.db", eval_rpm=100000, eval_samples=1,
                       eval_batch_max=10, eval_workers=1, max_iterations=4,
                       val_every=100, branch="main",
                       accept_test="sa", compact_every=0, racing_enabled=False)
    store = RunStore(config.store_path)
    records = [_rec(i) for i in range(6)]
    meta = {r["agent_id"]: r for r in records}
    evaluator = Evaluator(config, store, L1Composite(0.0), CEREMA, meta, call)
    loop = CalibrationLoop(config, store, evaluator, mutator, CEREMA, records, [])
    assert loop._use_funnel is False
    loop.run(SEED, max_iterations=4)

    verdicts = [m["verdict"] for m in store.mutations("main")]
    # Toutes les resoumissions après la 1ʳᵉ sont bloquées à sec (tabu ou no-op).
    assert verdicts[1:] and all(v in ("rejected_tabu", "invalid") for v in verdicts[1:])
    # Le nœud muté (contenu fixe) n'est évalué qu'une seule fois sur 'train'.
    mutated = [{"name": "intro_s1", "mutable": True, "content": _FixedMutator.FIXED},
               {"name": "json_schema", "mutable": False, "content": '{"type":"object"}'}]
    n = store.conn.execute("SELECT COUNT(*) FROM evals WHERE node_hash=? AND dataset='train'",
                           (blocks_hash(mutated),)).fetchone()[0]
    assert n <= 1
    store.close()


def _make_loop(tmp_path, call, mutator):
    # accept_test="sa" : ce test vérifie la mécanique de reprise (recuit simple,
    # phase 1) ; l'acceptation bootstrap est testée à part (test_stats).
    config = RunConfig(store_path=tmp_path / "c.db", eval_rpm=100000, eval_samples=1,
                       eval_batch_max=10, eval_workers=1, max_iterations=4,
                       val_every=100, branch="main",
                       accept_test="sa", compact_every=0)
    store = RunStore(config.store_path)
    records = [_rec(i) for i in range(6)]
    meta = {r["agent_id"]: r for r in records}
    evaluator = Evaluator(config, store, L1Composite(0.0), CEREMA, meta, call)
    loop = CalibrationLoop(config, store, evaluator, mutator, CEREMA, records, [])
    return config, store, loop


SEED = [
    {"name": "intro_s1", "mutable": True, "content": "Prompt initial de calibration."},
    {"name": "json_schema", "mutable": False, "content": '{"type":"object"}'},
]


def test_full_run_then_resume_no_redundant_calls(tmp_path):
    call, mutator = _DetCall(), _DetMutator()
    _, store, loop = _make_loop(tmp_path, call, mutator)
    state1 = loop.run(SEED, max_iterations=4)
    calls_after_run = call.calls
    mut_after_run = mutator.calls
    assert state1["iteration"] == 4
    assert calls_after_run > 0
    store.close()

    # Reprise à budget identique : aucune itération à rejouer.
    call2, mutator2 = _DetCall(), _DetMutator()
    _, store2, loop2 = _make_loop(tmp_path, call2, mutator2)
    state2 = loop2.run(SEED, max_iterations=4)
    assert call2.calls == 0, "reprise ne doit émettre aucun appel provider"
    assert mutator2.calls == 0, "reprise ne doit rappeler aucune mutation"
    assert state2["iteration"] == 4
    assert state2["best_score"] == state1["best_score"]
    store2.close()


def test_resume_backfills_ablation_detail(tmp_path):
    """Un état snapshoté par une version antérieure (entrées d'ablation sans
    ``detail``) est complété à la reprise depuis la table ``ablations`` — le
    mutateur reçoit les crochets par dimension sans payer d'éval."""
    import json

    call, mutator = _DetCall(), _DetMutator()
    _, store, loop = _make_loop(tmp_path, call, mutator)
    state = loop.run(SEED, max_iterations=2)

    node = state["sa_node"]
    # Ligne Shapley : le détail pondéré (pts de composite) est stocké tel quel.
    store.record_ablation(node, "intro_s1", "shapley", 4.0,
                          scores_json=json.dumps({"global": 2.0, "age": 2.0}))

    # État ancien format : entrée d'ablation sans champ ``detail``.
    state["ablation"] = [{"bloc": "intro_s1", "content": "x", "delta": 4.0,
                          "score": 0.0, "useful": True,
                          "harmful": False, "diag": ""}]
    store.save_run_state("main", state)
    store.close()

    call2, mutator2 = _DetCall(), _DetMutator()
    _, store2, loop2 = _make_loop(tmp_path, call2, mutator2)
    state2 = loop2.run(SEED, max_iterations=2)      # reprise pure, zéro éval
    assert call2.calls == 0
    entry = next(r for r in state2["ablation"] if r["bloc"] == "intro_s1")
    assert entry["detail"]["global"] == pytest.approx(2.0)
    assert entry["detail"]["age"] == pytest.approx(2.0)
    assert sum(entry["detail"].values()) == pytest.approx(4.0)
    store2.close()


class _NoImproveMutator:
    """Mutateur dont la mutation garde le MÊME nombre de mots que le bloc seed.

    ``_DetCall`` choisit le mode via ``len(prompt.split()) % 4`` : à nombre de mots
    égal, l'essai produit exactement le même mode → même composite que le prompt
    courant → aucune amélioration → abandon au premier palier (25 %)."""

    def __init__(self):
        self.calls = 0

    def propose(self, blocks, df, best_score, history, ablation, snippets=None, lessons=None):
        self.calls += 1
        i = len([h for h in history if h["iteration"] > 0]) + 1
        # « variante quatre mots » = 4 mots, comme « Prompt initial de calibration. ».
        return ({"target_block": "intro_s1", "action": "modify",
                 "new_content": "variante quatre mots ok", "rationale": f"iter {i}"},
                f"user msg iter {i}")


def test_single_candidate_early_stops_on_non_improving_rung(tmp_path):
    """``n_candidates=1`` + paliers : un essai qui n'améliore pas le prompt courant au
    premier palier (25 %) est abandonné (``rejected_race``) sans jamais payer l'éval
    complète ni les paliers suivants."""
    call, mutator = _DetCall(), _NoImproveMutator()
    config = RunConfig(store_path=tmp_path / "g.db", eval_rpm=100000, eval_samples=1,
                       eval_batch_max=10, eval_workers=1, max_iterations=3,
                       val_every=100, branch="main",
                       accept_test="sa", compact_every=0,
                       racing_enabled=True, racing_rungs=[0.25, 0.50, 0.75])
    store = RunStore(config.store_path)
    records = [_rec(i) for i in range(8)]
    meta = {r["agent_id"]: r for r in records}
    evaluator = Evaluator(config, store, L1Composite(0.0), CEREMA, meta, call)
    loop = CalibrationLoop(config, store, evaluator, mutator, CEREMA, records, [])
    assert loop._use_funnel is False               # un seul essai : pas d'entonnoir
    loop.run(SEED, max_iterations=3)

    verdicts = [m["verdict"] for m in store.mutations("main")]
    assert "rejected_race" in verdicts
    labels = {r[0] for r in store.conn.execute(
        "SELECT DISTINCT dataset FROM evals").fetchall()}
    assert "race:0.25" in labels                   # 1er palier évalué (essai + courant)
    assert "race:0.50" not in labels               # arrêt précoce : pas de 2ᵉ palier
    store.close()


def test_resume_extends_to_more_iterations(tmp_path):
    call, mutator = _DetCall(), _DetMutator()
    _, store, loop = _make_loop(tmp_path, call, mutator)
    loop.run(SEED, max_iterations=2)
    store.close()

    # Reprise avec un budget supérieur : seules les itérations 3-4 sont jouées.
    call2, mutator2 = _DetCall(), _DetMutator()
    _, store2, loop2 = _make_loop(tmp_path, call2, mutator2)
    state = loop2.run(SEED, max_iterations=4)
    assert state["iteration"] == 4
    assert mutator2.calls == 2, "seules les 2 nouvelles itérations proposent une mutation"
    store2.close()


def test_bootstrap_acceptance_path_runs_and_resumes(tmp_path):
    """La boucle en mode bootstrap (phase 3) tourne et reste reprenable sans réappel."""
    call, mutator = _DetCall(), _DetMutator()
    config = RunConfig(store_path=tmp_path / "b.db", eval_rpm=100000, eval_samples=1,
                       eval_batch_max=10, eval_workers=1, max_iterations=3,
                       val_every=100, branch="main",
                       accept_test="bootstrap", bootstrap_b=50, compact_every=0,
                       racing_enabled=False)
    store = RunStore(config.store_path)
    records = [_rec(i) for i in range(6)]
    meta = {r["agent_id"]: r for r in records}
    evaluator = Evaluator(config, store, L1Composite(0.0), CEREMA, meta, call)
    loop = CalibrationLoop(config, store, evaluator, mutator, CEREMA, records, [])
    state1 = loop.run(SEED, max_iterations=3)
    assert state1["iteration"] == 3
    # Tout verdict de mutation est un verdict connu de la phase 3.
    verdicts = {m["verdict"] for m in store.mutations("main")}
    assert verdicts <= {"accepted", "rejected_score", "rejected_stat", "vetoed",
                        "invalid", "proposed"}
    store.close()

    # Reprise : zéro appel provider ni mutation redondants (bootstrap = pur recalcul).
    call2, mutator2 = _DetCall(), _DetMutator()
    store2 = RunStore(config.store_path)
    evaluator2 = Evaluator(config, store2, L1Composite(0.0), CEREMA, meta, call2)
    loop2 = CalibrationLoop(config, store2, evaluator2, mutator2, CEREMA, records, [])
    loop2.run(SEED, max_iterations=3)
    assert call2.calls == 0 and mutator2.calls == 0
    store2.close()


def test_init_runs_once(tmp_path):
    call, mutator = _DetCall(), _DetMutator()
    _, store, loop = _make_loop(tmp_path, call, mutator)
    loop.run(SEED, max_iterations=1)
    seed_hash = store.get_or_create_node(SEED, branch="main")
    # Le nœud seed est évalué (éval train en cache) → init faite une fois.
    assert store.cached_eval(seed_hash, "train", loop.config.eval_params_key()) is not None
    store.close()


# ── Phase 4 : entonnoir multi-candidats + bandit + compaction ────────────────

class _CandMutator:
    """Mutateur multi-candidats déterministe (contrat ``propose_candidates``)."""

    def __init__(self):
        self.calls = 0
        self.last_suggested = None

    def propose_candidates(self, blocks, df, best_score, history, ablation,
                           n_candidates=4, suggested_operator=None, snippets=None,
                           lessons=None):
        self.calls += 1
        self.last_suggested = suggested_operator
        i = len([h for h in history if h["iteration"] > 0]) + 1
        cands = [
            {"target_block": "intro_s1", "action": "modify",
             "new_content": f"Alternative {i} alpha du bloc.", "rationale": "a"},
            {"target_block": "intro_s1", "action": "modify",
             "new_content": f"Autre piste {i} beta tres differente ici.", "rationale": "b"},
            {"target_block": "intro_s1", "action": "insert",
             "new_content": f"Bloc insere numero {i}.", "rationale": "c"},
        ]
        return cands[:n_candidates], f"user msg iter {i}"


def _make_funnel_loop(tmp_path, call, mutator, screen, **overrides):
    cfg = dict(store_path=tmp_path / "f.db", eval_rpm=100000, eval_samples=1,
               eval_batch_max=10, eval_workers=1, max_iterations=4, val_every=100,
               branch="main", accept_test="sa",
               n_candidates=3, compact_every=0, racing_enabled=False)
    cfg.update(overrides)
    config = RunConfig(**cfg)
    store = RunStore(config.store_path)
    records = [_rec(i) for i in range(8)]
    meta = {r["agent_id"]: r for r in records}
    evaluator = Evaluator(config, store, L1Composite(0.0), CEREMA, meta, call)
    loop = CalibrationLoop(config, store, evaluator, mutator, CEREMA, records, [],
                           screen_records=screen)
    return config, store, loop, records


def test_funnel_runs_screening_and_bandit_then_resumes(tmp_path):
    screen = [_rec(i) for i in range(3)]           # sous-ensemble de screening
    call, mutator = _DetCall(), _CandMutator()
    _, store, loop, _ = _make_funnel_loop(tmp_path, call, mutator, screen)
    assert loop._use_funnel is True
    state = loop.run(SEED, max_iterations=4)
    assert state["iteration"] == 4
    # Verdicts tous connus de la phase 4 (dont rejected_tabu possible).
    verdicts = {m["verdict"] for m in store.mutations("main")}
    assert verdicts <= {"accepted", "rejected_score", "rejected_stat", "rejected_tabu",
                        "rejected_dup_block", "vetoed", "invalid", "proposed"}
    # La diversité a écarté au moins un candidat re-ciblant le même bloc.
    assert "rejected_dup_block" in verdicts
    # Le screening a produit des évals sur le jeu 'screen'.
    screen_evals = store.conn.execute(
        "SELECT COUNT(*) FROM evals WHERE dataset='screen'").fetchone()[0]
    assert screen_evals > 0
    # Le bandit a été alimenté (au moins un tirage).
    assert sum(p for p, _ in store.bandit_stats("main").values()) > 0
    store.close()

    # Reprise : aucun appel provider ni mutateur redondant.
    call2, mutator2 = _DetCall(), _CandMutator()
    store2 = RunStore(loop.config.store_path)
    records2 = [_rec(i) for i in range(8)]
    meta2 = {r["agent_id"]: r for r in records2}
    ev2 = Evaluator(loop.config, store2, L1Composite(0.0), CEREMA, meta2, call2)
    loop2 = CalibrationLoop(loop.config, store2, ev2, mutator2, CEREMA, records2, [],
                            screen_records=[_rec(i) for i in range(3)])
    loop2.run(SEED, max_iterations=4)
    assert call2.calls == 0 and mutator2.calls == 0
    store2.close()


class _ConstCall:
    """Retourne un mode constant par agent, indépendant du prompt → Δ score = 0."""

    def __init__(self):
        self.calls = 0

    def __call__(self, entry):
        self.calls += 1
        modes = ["voiture", "marche", "transports_collectifs", "velo"]
        return [{"agent_id": aid, "mode": modes[int(aid) % len(modes)]}
                for aid in entry["meta"]]


COMPACT_SEED = [
    {"name": "intro_s1", "mutable": True, "content": "Bloc long et verbeux numero un."},
    {"name": "intro_s2", "mutable": True, "content": "Bloc court."},
    {"name": "json_schema", "mutable": False, "content": '{"type":"object"}'},
]


def test_compaction_removes_null_contribution_blocks(tmp_path):
    """Un bloc sans effet sur les décisions (Δ score ≈ 0) est retiré sous test de
    non-infériorité — « réduire tant que ça ne dégrade pas le score »."""
    from calibration.blocks import prompt_word_count
    call = _ConstCall()
    config = RunConfig(store_path=tmp_path / "c.db", eval_rpm=100000, eval_samples=1,
                       eval_batch_max=10, eval_workers=1, branch="main",
                       bootstrap_b=50, compact_margin=1.0, compact_abl_tol=2.0)
    store = RunStore(config.store_path)
    records = [_rec(i) for i in range(8)]
    meta = {r["agent_id"]: r for r in records}
    ev = Evaluator(config, store, L1Composite(0.0), CEREMA, meta, call)
    loop = CalibrationLoop(config, store, ev, _DetMutator(), CEREMA, records, [])

    node = store.get_or_create_node(COMPACT_SEED, branch="main", iteration=0)
    result, _ = ev.evaluate(node, COMPACT_SEED, "train", records, desc="seed")
    before = prompt_word_count(COMPACT_SEED)
    # État minimal : les deux blocs ont une contribution nulle (Δ ablation = 0).
    state = {"iteration": 1, "accepted": 1, "sa_node": node,
             "sa_score": result.scores.composite,
             "sa_scores": result.scores.model_dump(by_alias=True),
             "best_node": node, "best_score": result.scores.composite,
             "val_best": float("inf"), "val_no_improve": 0,
             "ablation": [{"bloc": "intro_s1", "delta": 0.0},
                          {"bloc": "intro_s2", "delta": 0.0}],
             "history": []}
    loop._compaction_pass(state, seed=1)

    kept = store.node_blocks(state["sa_node"])
    assert prompt_word_count(kept) < before, "la compaction doit raccourcir le prompt"
    compact_rows = [m for m in store.mutations("main") if m["operator"] == "compact_delete"]
    assert compact_rows and any(m["verdict"] == "accepted" for m in compact_rows)
    store.close()


# ── Phase 4.6 : racing ciblé par strate (successive halving) ─────────────────

import json  # noqa: E402
import re  # noqa: E402


class _MarkerCall:
    """Renvoie un mode **uniforme** dicté par un marqueur ``##MODE:x##`` du prompt.

    Chaque candidat encode son mode dans le bloc qu'il modifie → distribution
    déterministe et composite bien séparé par mode (indépendant du sous-échantillon,
    puisque uniforme), ce qui rend le racing et le gate observables sans réseau.
    """

    DEFAULT = "voiture"                               # SA seed = aucun marqueur

    def __init__(self):
        self.calls = 0

    def __call__(self, entry):
        self.calls += 1
        prompt = entry["messages"][0]["content"]
        m = re.search(r"##MODE:(\w+)##", prompt)
        mode = m.group(1) if m else self.DEFAULT
        return [{"agent_id": aid, "mode": mode} for aid in entry["meta"]]


class _RaceMutator:
    """Propose un candidat par mode, chacun sur un bloc DISTINCT (survit à la diversité)."""

    def __init__(self, modes):
        self.modes = modes
        self.calls = 0

    def propose_candidates(self, blocks, df, best_score, history, ablation,
                           n_candidates=4, suggested_operator=None, snippets=None,
                           lessons=None):
        self.calls += 1
        cands = [{"target_block": f"intro_s{k + 1}", "action": "modify",
                  "new_content": f"Bloc {k + 1} ##MODE:{mode}##", "rationale": mode}
                 for k, mode in enumerate(self.modes)]
        return cands[:n_candidates], "user msg racing"


# Seed à 4 blocs mutables distincts : chaque candidat en cible un → pas de collision
# du filtre de diversité, le racing compare bien 4 blocs différents.
RACE_SEED = [
    {"name": "intro_s1", "mutable": True, "content": "Bloc un initial."},
    {"name": "intro_s2", "mutable": True, "content": "Bloc deux initial."},
    {"name": "intro_s3", "mutable": True, "content": "Bloc trois initial."},
    {"name": "intro_s4", "mutable": True, "content": "Bloc quatre initial."},
    {"name": "json_schema", "mutable": False, "content": '{"type":"object"}'},
]


def _make_race_loop(tmp_path, call, mutator, **overrides):
    cfg = dict(store_path=tmp_path / "r.db", eval_rpm=100000, eval_samples=1,
               eval_batch_max=10, eval_workers=1, max_iterations=1, val_every=100,
               branch="main", accept_test="sa",
               n_candidates=4, compact_every=0, tabu_enabled=False, bandit_enabled=False,
               snippets_enabled=False,
               racing_enabled=True, racing_min_n=4, bootstrap_b=50)
    cfg.update(overrides)
    config = RunConfig(**cfg)
    store = RunStore(config.store_path)
    records = [_rec(i) for i in range(8)]
    meta = {r["agent_id"]: r for r in records}
    evaluator = Evaluator(config, store, L1Composite(0.0), CEREMA, meta, call)
    loop = CalibrationLoop(config, store, evaluator, mutator, CEREMA, records, [])
    return config, store, loop


def _verdicts(store):
    return {m["verdict"] for m in store.mutations("main")}


def test_racing_gate_eliminates_non_improving_candidate(tmp_path):
    """Le gate strate rejette (``rejected_gate``) les candidats qui n'améliorent pas
    la strate la plus mal représentée ; seul le candidat qui la corrige survit."""
    # SA = voiture → pire strate = distance[1-2km] (écart L1 = 140). marche corrige
    # (L1=120 < 140) ; bus/velo/voiture ne corrigent pas (≥ 140).
    call, mutator = _MarkerCall(), _RaceMutator(["marche", "bus", "velo", "voiture"])
    _, store, loop = _make_race_loop(tmp_path, call, mutator,
                                     racing_target_gate=True, racing_target_every=1,
                                     racing_rungs=[1.0])
    state = loop.run(RACE_SEED, max_iterations=1)
    assert state["iteration"] == 1
    assert "rejected_gate" in _verdicts(store)
    # Le gagnant (dernière ligne de l'itération) est le candidat marche — sa ligne
    # est ré-arbitrée par la boucle (accepté/vetoed…) mais reste la plus récente.
    winner = store.mutation_row_at("main", 1)
    assert "##MODE:marche##" in winner["new_content"]
    store.close()


def test_racing_gate_global_fallback_when_all_fail(tmp_path):
    """Si aucun candidat n'améliore la strate cible, le gate ne bloque pas
    l'itération : tous repassent en racing global (aucun ``rejected_gate``)."""
    # Tous ≥ écart SA (140) sur distance[1-2km] : bus(160), velo(180), voiture(140).
    call, mutator = _MarkerCall(), _RaceMutator(["bus", "velo", "voiture"])
    _, store, loop = _make_race_loop(tmp_path, call, mutator, n_candidates=3,
                                     racing_target_gate=True, racing_target_every=1,
                                     racing_rungs=[0.5, 1.0], racing_min_gap=1.0)
    state = loop.run(RACE_SEED, max_iterations=1)
    assert state["iteration"] == 1                    # itération non bloquée
    assert "rejected_gate" not in _verdicts(store)    # repli : personne n'est « gated »
    # Un gagnant a bien été désigné : le meilleur composite global l'emporte (voiture).
    winner = store.mutation_row_at("main", 1)
    assert "##MODE:voiture##" in winner["new_content"]
    store.close()


def test_racing_guardrail_keeps_indistinguishable_candidates(tmp_path):
    """Deux candidats à moins de ``racing_min_gap`` (ici composites identiques) ne
    sont jamais départagés : aucun ``rejected_race``."""
    call, mutator = _MarkerCall(), _RaceMutator(["voiture", "voiture"])
    _, store, loop = _make_race_loop(tmp_path, call, mutator, n_candidates=2,
                                     racing_target_gate=False,
                                     racing_rungs=[0.5, 1.0], racing_min_gap=5.0)
    state = loop.run(RACE_SEED, max_iterations=1)
    assert state["iteration"] == 1
    assert "rejected_race" not in _verdicts(store)
    store.close()


def test_racing_halving_shrinks_survivors_as_eval_set_grows(tmp_path):
    """Successive halving : à chaque palier le jeu d'éval croît et le nombre de
    survivants décroît (4 → 2 → 1)."""
    call = _MarkerCall()
    mutator = _RaceMutator(["voiture", "marche", "transports_collectifs", "velo"])
    _, store, loop = _make_race_loop(tmp_path, call, mutator, n_candidates=4,
                                     racing_target_gate=False,
                                     racing_rungs=[0.25, 0.5, 1.0],
                                     racing_keep_frac=0.5, racing_min_gap=1.0)
    state = loop.run(RACE_SEED, max_iterations=1)
    assert state["iteration"] == 1

    def _count(dataset):
        return store.conn.execute(
            "SELECT COUNT(*) FROM evals WHERE dataset=?", (dataset,)).fetchone()[0]

    # Palier 0.25 (n=2) évalue 4 candidats ; palier 0.50 (n=4) n'en évalue plus que 2.
    n_rung1, n_rung2 = _count("race:0.25"), _count("race:0.50")
    assert n_rung1 == 4 and n_rung2 == 2, (n_rung1, n_rung2)
    # Le jeu d'éval croît : les décisions du palier 2 sont plus nombreuses que celles du palier 1.
    dec1 = store.conn.execute(
        "SELECT decisions FROM evals WHERE dataset='race:0.25' LIMIT 1").fetchone()[0]
    dec2 = store.conn.execute(
        "SELECT decisions FROM evals WHERE dataset='race:0.50' LIMIT 1").fetchone()[0]
    assert len(json.loads(dec2)) > len(json.loads(dec1))
    # Trois candidats éliminés en cours de racing.
    race_rejects = [m for m in store.mutations("main") if m["verdict"] == "rejected_race"]
    assert len(race_rejects) == 3
    store.close()


def test_racing_disabled_keeps_one_shot_screening(tmp_path):
    """``racing_enabled=False`` → chemin screening one-shot strictement inchangé :
    aucun label de dataset ``race:`` / ``gate:`` n'apparaît, le screening tourne."""
    screen = [_rec(i) for i in range(3)]
    call, mutator = _DetCall(), _CandMutator()
    _, store, loop, _ = _make_funnel_loop(tmp_path, call, mutator, screen,
                                          racing_enabled=False)
    loop.run(SEED, max_iterations=4)
    n_race = store.conn.execute(
        "SELECT COUNT(*) FROM evals WHERE dataset LIKE 'race:%' OR dataset LIKE 'gate:%'"
    ).fetchone()[0]
    assert n_race == 0
    screen_evals = store.conn.execute(
        "SELECT COUNT(*) FROM evals WHERE dataset='screen'").fetchone()[0]
    assert screen_evals > 0
    store.close()
