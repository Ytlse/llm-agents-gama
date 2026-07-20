"""Tests de l'archive de Pareto (phase 6, DC) — dominance et front, purs."""

from calibration import pareto

DIMS = ["age", "motif"]


def _it(h, age, motif, composite=None):
    d = {"hash": h, "age": age, "motif": motif}
    if composite is not None:
        d["composite"] = composite
    return d


def test_dominance_strict():
    a = _it("a", 1.0, 1.0)
    b = _it("b", 2.0, 2.0)
    assert pareto.dominates(a, b, DIMS)          # a meilleur partout
    assert not pareto.dominates(b, a, DIMS)


def test_no_dominance_on_tradeoff():
    a = _it("a", 1.0, 5.0)                        # fort en age, faible en motif
    b = _it("b", 5.0, 1.0)                        # l'inverse
    assert not pareto.dominates(a, b, DIMS)
    assert not pareto.dominates(b, a, DIMS)


def test_equal_is_not_strict_domination():
    a = _it("a", 2.0, 2.0)
    b = _it("b", 2.0, 2.0)
    assert not pareto.dominates(a, b, DIMS)       # égal partout → pas de dominance


def test_ties_plus_one_better_dominates():
    a = _it("a", 2.0, 1.0)
    b = _it("b", 2.0, 2.0)                        # égal en age, pire en motif
    assert pareto.dominates(a, b, DIMS)


def test_missing_dimension_never_dominates():
    a = {"hash": "a", "age": 1.0}                 # pas de motif
    b = _it("b", 2.0, 2.0)
    assert not pareto.dominates(a, b, DIMS)
    assert not pareto.dominates(b, a, DIMS)


def test_pareto_front_keeps_nondominated():
    items = [
        _it("A", 1.0, 5.0),      # extrême age
        _it("B", 5.0, 1.0),      # extrême motif
        _it("C", 3.0, 3.0),      # équilibré, non dominé
        _it("D", 4.0, 4.0),      # dominé par C
    ]
    front = {it["hash"] for it in pareto.pareto_front(items, DIMS)}
    assert front == {"A", "B", "C"}
    assert "D" not in front


def test_pareto_front_dedups_by_hash():
    items = [_it("A", 1.0, 1.0), _it("A", 1.0, 1.0)]
    assert len(pareto.pareto_front(items, DIMS)) == 1


def test_diversified_seeds_spreads_extremes():
    items = [
        _it("A", 0.0, 10.0, composite=10.0),
        _it("B", 10.0, 0.0, composite=10.0),
        _it("C", 5.0, 5.0, composite=10.0),
    ]
    front = pareto.pareto_front(items, DIMS)
    seeds = pareto.diversified_seeds(front, 2, DIMS)
    hashes = {s["hash"] for s in seeds}
    assert len(seeds) == 2
    # Les deux extrêmes (les plus éloignés) sont préférés à l'équilibré.
    assert hashes == {"A", "B"}


def test_diversified_seeds_small_front():
    front = [_it("A", 1.0, 1.0)]
    assert pareto.diversified_seeds(front, 3, DIMS) == front
    assert pareto.diversified_seeds([], 3, DIMS) == []


def test_complementary_pair_most_distant():
    items = [
        _it("A", 0.0, 10.0),
        _it("B", 10.0, 0.0),
        _it("C", 4.0, 6.0),
    ]
    front = pareto.pareto_front(items, DIMS)
    pair = pareto.complementary_pair(front, DIMS)
    assert pair is not None
    assert {pair[0]["hash"], pair[1]["hash"]} == {"A", "B"}


def test_complementary_pair_needs_two():
    assert pareto.complementary_pair([_it("A", 1.0, 1.0)], DIMS) is None
