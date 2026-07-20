"""Attribution de crédit Shapley — phase 5 du ticket 004 (DB).

On teste la fonction **pure** ``shapley_values`` sur des fonctions de valeur
déterministes qui isolent chaque propriété (additivité, redondance, synergie,
efficacité, troncature), puis l'intégration ``run_shapley`` avec l'``Evaluator``
réel (cache content-addressed) et le câblage dans la boucle.
"""

import pytest

from calibration.evaluation import Evaluator
from calibration.loop import CalibrationLoop, run_shapley
from calibration.metrics import L1Composite
from calibration.models import RunConfig
from calibration.shapley import (build_shapley_results, coalition_blocks,
                                 shapley_scores, shapley_values)
from calibration.store import RunStore
from .test_metrics import CEREMA


SCHEMA = {"name": "json_schema", "mutable": False, "content": "{}"}


def _blocks(*names):
    return [{"name": n, "mutable": True, "content": n} for n in names] + [SCHEMA]


# ── Fonctions de valeur (loss ; plus bas = mieux) ────────────────────────────

def _additive(coalition):
    """a réduit la loss de 3, b de 1, indépendamment (blocs additifs)."""
    present = {b["name"] for b in coalition}
    v = 10.0
    v -= 3.0 if "a" in present else 0.0
    v -= 1.0 if "b" in present else 0.0
    return v


def _redundant(coalition):
    """a et b redondants : −3 si AU MOINS UN présent, rien de plus si les deux."""
    present = {b["name"] for b in coalition}
    return 7.0 if ("a" in present or "b" in present) else 10.0


def _synergy(coalition):
    """a et b synergiques : −4 seulement si les DEUX présents."""
    present = {b["name"] for b in coalition}
    return 6.0 if ("a" in present and "b" in present) else 10.0


# ── Propriétés de base ───────────────────────────────────────────────────────

def test_additive_blocks_get_their_own_reduction():
    blocks = _blocks("a", "b")
    phi = shapley_values(blocks, _additive, m_permutations=10, seed=1)
    assert phi["a"] == pytest.approx(3.0, abs=1e-9)
    assert phi["b"] == pytest.approx(1.0, abs=1e-9)


def test_coalition_keeps_locked_blocks_and_order():
    blocks = _blocks("a", "b")
    # Coalition vide : seul le bloc verrouillé subsiste ; ordre préservé.
    empty = coalition_blocks(blocks, set())
    assert [b["name"] for b in empty] == ["json_schema"]
    part = coalition_blocks(blocks, {"b"})
    assert [b["name"] for b in part] == ["b", "json_schema"]


def test_efficiency_sum_equals_full_gain():
    """Σ φ_i = v(∅) − v(complet) (le gain total est réparti exactement)."""
    blocks = _blocks("a", "b", "c")

    def v(coalition):
        present = {b["name"] for b in coalition}
        return 20.0 - 2.0 * len(present & {"a", "b", "c"})

    phi = shapley_values(blocks, v, m_permutations=12, seed=3)
    v_full = v(coalition_blocks(blocks, {"a", "b", "c"}))
    v_empty = v(coalition_blocks(blocks, set()))
    assert sum(phi.values()) == pytest.approx(v_empty - v_full, abs=1e-9)


def test_redundancy_splits_credit_unlike_single_drop():
    """Shapley répartit le crédit entre deux blocs redondants ; le retrait
    bloc-à-bloc les voit nuls."""
    blocks = _blocks("a", "b")
    phi = shapley_values(blocks, _redundant, m_permutations=40, seed=2)
    # Chacun ≈ 1.5 (moitié du gain partagé de 3), somme = 3.
    assert phi["a"] == pytest.approx(1.5, abs=0.3)
    assert phi["b"] == pytest.approx(1.5, abs=0.3)
    assert phi["a"] + phi["b"] == pytest.approx(3.0, abs=1e-9)
    # Retrait bloc-à-bloc depuis le prompt complet : retirer a ne change rien
    # (b compense) → 0.
    drop_a = _redundant(coalition_blocks(blocks, {"b"})) - \
        _redundant(coalition_blocks(blocks, {"a", "b"}))
    assert drop_a == pytest.approx(0.0)


def test_synergy_splits_credit_unlike_single_drop_double_count():
    """Shapley alloue la synergie une fois ; la somme des retraits bloc-à-bloc la
    compte deux fois."""
    blocks = _blocks("a", "b")
    phi = shapley_values(blocks, _synergy, m_permutations=80, seed=5)
    # La synergie de 4 est partagée entre les deux blocs (≈ 2 chacun) — l'écart à
    # 2 vient du bruit d'échantillonnage des permutations.
    assert phi["a"] == pytest.approx(2.0, abs=0.7)
    assert phi["b"] == pytest.approx(2.0, abs=0.7)
    assert phi["a"] + phi["b"] == pytest.approx(4.0, abs=1e-9)
    # Retrait bloc-à-bloc : retirer a OU b depuis le complet perd toute la synergie
    # → +4 chacun, somme = 8 ≠ 4 (double comptage que Shapley corrige).
    full = coalition_blocks(blocks, {"a", "b"})
    drop_a = _synergy(coalition_blocks(blocks, {"b"})) - _synergy(full)
    drop_b = _synergy(coalition_blocks(blocks, {"a"})) - _synergy(full)
    assert drop_a + drop_b == pytest.approx(8.0)


def test_truncation_saves_evaluations():
    """La troncature évalue moins de coalitions quand la loss complète est vite atteinte."""
    blocks = _blocks("a", "b", "c", "d")

    class Counter:
        def __init__(self):
            self.n = 0

        def __call__(self, coalition):
            self.n += 1
            # Loss complète dès qu'un bloc est présent → marginaux suivants nuls.
            present = {b["name"] for b in coalition}
            return 5.0 if present & {"a", "b", "c", "d"} else 10.0

    trunc = Counter()
    shapley_values(blocks, trunc, m_permutations=8, truncation_tol=0.5, seed=0)
    no_trunc = Counter()
    shapley_values(blocks, no_trunc, m_permutations=8, truncation_tol=0.0, seed=0)
    assert trunc.n < no_trunc.n


def test_no_mutable_blocks_returns_empty():
    assert shapley_values([SCHEMA], _additive, m_permutations=5) == {}


def test_build_results_shape_and_sorting():
    blocks = _blocks("a", "b")
    phi = {"a": 3.0, "b": -3.0}
    results = build_shapley_results(blocks, phi)
    assert [r["bloc"] for r in results] == ["a", "b"]      # trié décroissant
    assert results[0]["useful"] and not results[0]["harmful"]
    assert results[1]["harmful"] and not results[1]["useful"]
    assert results[0]["delta"] == 3.0 and results[0]["content"] == "a"
    assert results[0]["detail"] == {}                      # φ scalaire : pas de détail


# ── Décomposition par dimension (shapley_scores) ─────────────────────────────

def _additive_dims(coalition):
    """Deux composantes : a agit sur 'age' (−6 bruts), b sur 'motif' (−2 bruts).
    Composite = 0.5·age + 0.5·motif (poids fictifs pour tester la linéarité)."""
    present = {b["name"] for b in coalition}
    age = 10.0 - (6.0 if "a" in present else 0.0)
    motif = 8.0 - (2.0 if "b" in present else 0.0)
    return {"composite": 0.5 * age + 0.5 * motif, "age": age, "motif": motif}


def test_shapley_scores_decomposes_each_dimension():
    blocks = _blocks("a", "b")
    phi = shapley_scores(blocks, _additive_dims, m_permutations=10,
                         truncation_tol=0.0, seed=1)
    assert phi["a"]["age"] == pytest.approx(6.0)
    assert phi["a"]["motif"] == pytest.approx(0.0)
    assert phi["b"]["motif"] == pytest.approx(2.0)
    # Linéarité : φ_composite = Σ w_d · φ_d, exactement.
    for n in ("a", "b"):
        assert phi[n]["composite"] == pytest.approx(
            0.5 * phi[n]["age"] + 0.5 * phi[n]["motif"])


def test_shapley_values_wrapper_matches_scores():
    blocks = _blocks("a", "b")
    scalar = shapley_values(blocks, _additive, m_permutations=10, seed=1)
    multi = shapley_scores(blocks, lambda c: {"composite": _additive(c)},
                           m_permutations=10, seed=1)
    assert scalar == {n: p["composite"] for n, p in multi.items()}


def test_build_results_weighted_detail():
    blocks = _blocks("a")
    phi = {"a": {"composite": 3.0, "age": 6.0, "motif": 0.0}}
    results = build_shapley_results(blocks, phi,
                                    weights={"age": 0.5, "motif": 0.5})
    r = results[0]
    assert r["delta"] == 3.0
    # Détail pondéré (pts de composite) : il somme au delta.
    assert r["detail"] == {"age": 3.0, "motif": 0.0}
    assert sum(r["detail"].values()) == pytest.approx(r["delta"])


def test_build_results_extracts_mode_push():
    """Les composantes ``mode:{m}`` de φ deviennent la matrice bloc × mode.

    φ mesure une réduction (``v_sans − v_avec``) → la poussée (effet de la
    PRÉSENCE du bloc sur la part) vaut ``−φ``. Les clés ``mode:`` ne polluent
    pas le détail par dimension."""
    blocks = _blocks("a")
    phi = {"a": {"composite": 3.0, "age": 6.0,
                 "mode:velo": -4.0, "mode:voiture": 2.0}}
    results = build_shapley_results(blocks, phi, weights={"age": 0.5})
    r = results[0]
    assert r["modes"] == {"velo": 4.0, "voiture": -2.0}
    assert "mode:velo" not in r["detail"] and "velo" not in r["detail"]
    # φ scalaire (sans décomposition) : pas de matrice modes.
    scalar = build_shapley_results(blocks, {"a": 3.0})
    assert scalar[0]["modes"] == {}


# ── Intégration avec l'Evaluator réel + cache ────────────────────────────────

def _rec(agent_id):
    section = (f"--- agent_id={agent_id} | Destination : work | Départ : 08:00 ---\n"
               "Persona. Options : foot.")
    return {"agent_id": str(agent_id), "section": section, "context": "Météo : sec.",
            "age": 30, "age_cat": "20-24", "occupation": "actif_temps_plein",
            "genre": "Homme", "motif": "travail", "dist_cat": "1-2km"}


class _WordCountCall:
    """Décision fonction du nombre de mots du prompt → coalitions ≠ scores ≠."""

    def __init__(self):
        self.calls = 0

    def __call__(self, entry):
        self.calls += 1
        prompt = entry["messages"][0]["content"]
        modes = ["foot", "car", "bicycle", "foot,bus,foot"]
        pick = modes[len(prompt.split()) % len(modes)]
        return [{"agent_id": aid, "mode": pick} for aid in entry["meta"]]


REAL_SEED = [
    {"name": "intro_s1", "mutable": True, "content": "Bloc intro un deux trois."},
    {"name": "intro_s2", "mutable": True, "content": "Bloc deux quatre cinq six sept."},
    {"name": "json_schema", "mutable": False, "content": '{"type":"object"}'},
]


def test_run_shapley_records_and_uses_cache(tmp_path):
    config = RunConfig(store_path=tmp_path / "s.db", eval_rpm=100000, eval_samples=1,
                       eval_batch_max=10, eval_workers=1, branch="main")
    store = RunStore(config.store_path)
    records = [_rec(i) for i in range(6)]
    meta = {r["agent_id"]: r for r in records}
    call = _WordCountCall()
    ev = Evaluator(config, store, L1Composite(0.0), CEREMA, meta, call)

    node = store.get_or_create_node(REAL_SEED, branch="main", iteration=0)
    results = run_shapley(store, ev, REAL_SEED, node, records, "train",
                          m_permutations=6, truncation_tol=0.5, seed=1, branch="main")

    names = {r["bloc"] for r in results}
    assert names == {"intro_s1", "intro_s2"}
    # Persistées avec la méthode 'shapley', détail par dimension dans scores_json.
    rows = [a for a in store.ablations(node) if a["method"] == "shapley"]
    assert {r["block_name"] for r in rows} == {"intro_s1", "intro_s2"}
    import json
    detail = json.loads(rows[0]["scores_json"])
    assert "age" in detail and "global" in detail
    # Matrice bloc × mode : poussées modales calculées sur les MÊMES évals,
    # présentes en mémoire ET persistées (clés ``mode:{m}`` du scores_json).
    from calibration.metrics import MODES
    for r in results:
        assert set(r["modes"]) == set(MODES)
    assert any(k.startswith("mode:") for k in detail)
    # Résultats en mémoire : détail pondéré qui somme au delta (linéarité).
    for r in results:
        assert sum(r["detail"].values()) == pytest.approx(r["delta"], abs=1e-9)

    # Cache content-addressed : un second run ne rappelle plus le provider.
    calls_before = call.calls
    run_shapley(store, ev, REAL_SEED, node, records, "train",
                m_permutations=6, truncation_tol=0.5, seed=1, branch="main")
    assert call.calls == calls_before, "coalitions déjà évaluées → zéro appel LLM"
    store.close()


class _DetMutator:
    def propose(self, blocks, df, best_score, history, ablation):
        return ({"target_block": "intro_s1", "action": "modify",
                 "new_content": "Version alpha beta du bloc.", "rationale": "x"}, "msg")


def test_update_ablation_uses_shapley_on_screen_set(tmp_path):
    """Après CHAQUE acceptation, ``_update_ablation`` recalcule le crédit par
    attribution Shapley sur le jeu de screening (méthode 'shapley' écrite, évals
    sur le jeu 'screen')."""
    config = RunConfig(store_path=tmp_path / "u.db", eval_rpm=100000, eval_samples=1,
                       eval_batch_max=10, eval_workers=1, branch="main",
                       compact_every=0, shapley_permutations=4)
    store = RunStore(config.store_path)
    records = [_rec(i) for i in range(6)]
    screen = [_rec(i) for i in range(3)]
    meta = {r["agent_id"]: r for r in records}
    ev = Evaluator(config, store, L1Composite(0.0), CEREMA, meta, _WordCountCall())
    loop = CalibrationLoop(config, store, ev, _DetMutator(), CEREMA, records, [],
                           screen_records=screen)

    node = store.get_or_create_node(REAL_SEED, branch="main", iteration=1)
    state = {"accepted": 1, "ablation": []}
    loop._update_ablation(state, REAL_SEED, node)

    # L'ablation de l'état est reconstruite depuis Shapley (les deux blocs mutables).
    assert {r["bloc"] for r in state["ablation"]} == {"intro_s1", "intro_s2"}
    # Persistée avec la méthode 'shapley' sur le jeu de screening.
    assert {a["method"] for a in store.ablations(node)} == {"shapley"}
    shap = store.conn.execute(
        "SELECT COUNT(*) FROM ablations WHERE method='shapley'").fetchone()[0]
    assert shap > 0
    screen_evals = store.conn.execute(
        "SELECT COUNT(*) FROM evals WHERE dataset='screen'").fetchone()[0]
    assert screen_evals > 0
    store.close()


# ── Mode cumulatif : graine fixe + addon plafonné (économie de tokens) ───────

def test_planned_permutations_growth_and_cap():
    from calibration.shapley import planned_permutations
    assert planned_permutations(25, 5, 0, 50) == 25    # init : le socle seul
    assert planned_permutations(25, 5, 3, 50) == 40    # +5 par acceptation
    assert planned_permutations(25, 5, 10, 50) == 50   # plafonné
    assert planned_permutations(25, 0, 10, 50) == 25   # addon=0 → historique
    assert planned_permutations(25, 5, 10, 10) == 25   # cap < socle → socle


def test_prefix_stability_extends_coalitions():
    """Augmenter m ÉTEND la séquence de permutations : les coalitions évaluées à
    m petit sont un sous-ensemble de celles à m grand (même graine). C'est la
    propriété qui rend le mode cumulatif compatible avec le cache — le socle est
    rejoué à l'identique, seules les permutations fraîches paient du neuf."""
    blocks = _blocks("a", "b", "c", "d")

    class Recorder:
        def __init__(self):
            self.seen = set()

        def __call__(self, coalition):
            self.seen.add(frozenset(b["name"] for b in coalition if b["mutable"]))
            return _additive(coalition)

    small, large = Recorder(), Recorder()
    shapley_values(blocks, small, m_permutations=3, truncation_tol=0.0, seed=0)
    shapley_values(blocks, large, m_permutations=8, truncation_tol=0.0, seed=0)
    assert small.seen <= large.seen


def test_loop_shapley_modes_pick_m_and_seed(tmp_path, monkeypatch):
    """`_shapley` : mode cumulatif → graine fixe 0 et m croissant plafonné ;
    mode historique (addon=0) → graine = accepted et m constant."""
    import calibration.loop as loop_mod

    captured = {}

    def fake_run_shapley(store, evaluator, blocks, node_hash, records, dataset,
                         m_permutations, truncation_tol, seed, branch):
        captured["m"], captured["seed"] = m_permutations, seed
        return []

    monkeypatch.setattr(loop_mod, "run_shapley", fake_run_shapley)

    def make_loop(**over):
        config = RunConfig(store_path=tmp_path / "m.db", branch="main",
                           shapley_permutations=25, **over)
        store = RunStore(config.store_path)
        ev = Evaluator(config, store, L1Composite(0.0), CEREMA, {}, _WordCountCall())
        return CalibrationLoop(config, store, ev, _DetMutator(), CEREMA,
                               [_rec(0)], [], screen_records=[_rec(0)])

    # Cumulatif : graine fixe, m = min(socle + accepted*addon, cap).
    lp = make_loop(shapley_addon_per_accept=5, shapley_max_permutations=50)
    lp._shapley(REAL_SEED, "n0", accepted=3)
    assert (captured["m"], captured["seed"]) == (40, 0)
    lp._shapley(REAL_SEED, "n0", accepted=99)
    assert (captured["m"], captured["seed"]) == (50, 0)   # plafonné

    # Historique : ré-échantillonnage complet (graine = accepted), m constant.
    lp = make_loop(shapley_addon_per_accept=0)
    lp._shapley(REAL_SEED, "n0", accepted=7)
    assert (captured["m"], captured["seed"]) == (25, 7)
