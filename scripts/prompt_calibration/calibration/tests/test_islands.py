"""Tests des îlots parallèles + migration + merge (phase 6, D7/DC).

Orchestration de bout en bout avec un évaluateur et un mutateur déterministes
(aucun réseau) : plusieurs branches dans le même store, migration en anneau entre
rondes, reprise idempotente, et merge optionnel produisant un nœud à deux parents.
"""

from calibration.islands import ISLANDS_STATE_KEY, IslandRunner, island_branches
from calibration.metrics import L1Composite
from calibration.models import RunConfig
from calibration.store import RunStore
from .test_metrics import CEREMA


def _rec(agent_id):
    section = (f"--- agent_id={agent_id} | Destination : work | Départ : 08:00 ---\n"
               "Persona. Options : foot.")
    return {"agent_id": str(agent_id), "section": section, "context": "Météo : sec.",
            "age": 30, "age_cat": "20-24", "occupation": "actif_temps_plein",
            "genre": "Homme", "motif": "travail", "dist_cat": "1-2km"}


SEED = [
    {"name": "intro_s1", "mutable": True, "content": "Prompt initial de calibration."},
    {"name": "json_schema", "mutable": False, "content": '{"type":"object"}'},
]


class _DetCall:
    """Décisions déterministes fonction du prompt (mêmes que test_loop)."""

    def __init__(self):
        self.calls = 0

    def __call__(self, entry):
        self.calls += 1
        prompt = entry["messages"][0]["content"]
        modes = ["foot", "car", "bicycle", "foot,bus,foot"]
        pick = modes[len(prompt.split()) % len(modes)]
        return [{"agent_id": aid, "mode": pick} for aid in entry["meta"]]


class _IslMutator:
    """Mutateur déterministe (single-candidat) + crossover déterministe."""

    def __init__(self):
        self.calls = 0
        self.cross_calls = 0

    def propose(self, blocks, df, best_score, history, ablation, snippets=None):
        self.calls += 1
        i = len([h for h in history if h["iteration"] > 0]) + 1
        return ({"target_block": "intro_s1", "action": "modify",
                 "new_content": f"Version numero {i} du bloc intro de calibration.",
                 "rationale": f"iter {i}"}, f"user msg iter {i}")

    def propose_crossover(self, blocks_a, blocks_b, ablation_a=None, ablation_b=None):
        self.cross_calls += 1
        return ([{"name": "intro_s1", "mutable": True,
                  "content": "Fusion complementaire des deux parents ici presente."},
                 {"name": "json_schema", "mutable": False, "content": '{"type":"object"}'}],
                "crossover msg")


def _make(tmp_path, call, mutator, **overrides):
    cfg = dict(store_path=tmp_path / "isl.db", eval_rpm=100000, eval_samples=1,
               eval_batch_max=10, eval_workers=1, val_every=100,
               accept_test="sa", compact_every=0,
               n_candidates=1, n_islands=2, migrate_every=2, max_iterations=4,
               snippets_enabled=False)
    cfg.update(overrides)
    config = RunConfig(**cfg)
    store = RunStore(config.store_path)
    records = [_rec(i) for i in range(6)]
    meta = {r["agent_id"]: r for r in records}
    runner = IslandRunner(config, store, L1Composite(0.0), CEREMA, meta,
                          lambda c: call, mutator, records, [], screen_records=[])
    return config, store, runner


def test_island_branches_naming():
    cfg = RunConfig(n_islands=3, island_prefix="isl")
    assert island_branches(cfg) == ["isl-0", "isl-1", "isl-2"]


def test_islands_run_all_branches_and_rounds(tmp_path):
    call, mutator = _DetCall(), _IslMutator()
    _, store, runner = _make(tmp_path, call, mutator)
    summary = runner.run(SEED, max_iterations=4)

    # Les deux îlots ont tourné et laissé un état.
    assert store.resume_state("isl-0") is not None
    assert store.resume_state("isl-1") is not None
    # L'orchestrateur a terminé ses deux rondes (2 rondes × migrate_every=2 = 4 itér).
    assert store.resume_state(ISLANDS_STATE_KEY)["round"] == 2
    # Résumé : un meilleur nœud toutes branches confondues.
    assert summary["best"] is not None
    assert summary["best"]["branch"] in ("isl-0", "isl-1")
    store.close()


def test_islands_migration_records_edges(tmp_path):
    call, mutator = _DetCall(), _IslMutator()
    _, store, runner = _make(tmp_path, call, mutator)
    runner.run(SEED, max_iterations=4)
    migrate_rows = [m for m in store.mutations() if m["operator"] == "migrate"]
    assert migrate_rows, "au moins une migration inter-îlots doit être enregistrée"
    for m in migrate_rows:
        assert m["verdict"] in ("accepted", "rejected_score")
    store.close()


def test_islands_resume_no_redundant_calls(tmp_path):
    call, mutator = _DetCall(), _IslMutator()
    config, store, runner = _make(tmp_path, call, mutator)
    runner.run(SEED, max_iterations=4)
    assert call.calls > 0
    store.close()

    # Reprise à budget identique : l'orchestrateur a fini ses rondes → rien à rejouer.
    call2, mutator2 = _DetCall(), _IslMutator()
    store2 = RunStore(config.store_path)
    meta2 = {str(i): _rec(i) for i in range(6)}
    runner2 = IslandRunner(config, store2, L1Composite(0.0), CEREMA, meta2,
                           lambda c: call2, mutator2,
                           [_rec(i) for i in range(6)], [], screen_records=[])
    runner2.run(SEED, max_iterations=4)
    assert call2.calls == 0, "reprise ne doit émettre aucun appel provider"
    assert mutator2.calls == 0, "reprise ne doit rappeler aucune mutation"
    store2.close()


def test_islands_resume_extends_rounds(tmp_path):
    call, mutator = _DetCall(), _IslMutator()
    config, store, runner = _make(tmp_path, call, mutator)
    runner.run(SEED, max_iterations=2)                 # 1 ronde
    assert store.resume_state(ISLANDS_STATE_KEY)["round"] == 1
    store.close()

    call2, mutator2 = _DetCall(), _IslMutator()
    store2 = RunStore(config.store_path)
    meta2 = {str(i): _rec(i) for i in range(6)}
    runner2 = IslandRunner(config, store2, L1Composite(0.0), CEREMA, meta2,
                           lambda c: call2, mutator2,
                           [_rec(i) for i in range(6)], [], screen_records=[])
    runner2.run(SEED, max_iterations=4)                # étend à 2 rondes
    assert store2.resume_state(ISLANDS_STATE_KEY)["round"] == 2
    store2.close()


def test_islands_crossover_produces_two_parent_node(tmp_path):
    call, mutator = _DetCall(), _IslMutator()
    _, store, runner = _make(tmp_path, call, mutator, crossover_every=1)
    runner.run(SEED, max_iterations=4)

    assert mutator.cross_calls > 0, "le merge doit avoir été tenté"
    cross_rows = [m for m in store.mutations() if m["operator"] == "crossover"]
    assert cross_rows, "une mutation crossover doit être enregistrée"
    # Le nœud produit a bien DEUX parents (merge).
    node = store.node(cross_rows[0]["node_to"])
    assert node["parent"] is not None and node["parent2"] is not None
    store.close()
