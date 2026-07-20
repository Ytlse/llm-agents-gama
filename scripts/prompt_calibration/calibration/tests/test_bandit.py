"""Bandit UCB1 de sélection d'opérateur — phase 4.3 du ticket 004 (DE).

On teste : bras jamais tirés prioritaires, exploitation du meilleur bras une fois
tous essayés, et la persistance store (upsert des (pulls, reward_sum)).
"""

from calibration.bandit import UCBBandit, select_arm, ucb_scores
from calibration.store import RunStore

ARMS = ["modify", "delete", "insert"]


def test_untried_arms_are_prioritized():
    stats = {"modify": (5, 5.0)}  # seul bras essayé
    chosen = select_arm(ARMS, stats, c=1.4)
    assert chosen in ("delete", "insert")  # un bras vierge d'abord


def test_untried_arm_gets_infinite_score():
    scores = ucb_scores({"a": (0, 0.0), "b": (3, 1.0)}, c=1.4)
    assert scores["a"] == float("inf")
    assert scores["b"] < float("inf")


def test_best_mean_wins_once_all_tried():
    # Tous essayés : modify gagne franchement (récompense moyenne 1.0 vs 0.0).
    stats = {"modify": (10, 10.0), "delete": (10, 0.0), "insert": (10, 0.0)}
    assert select_arm(ARMS, stats, c=0.1) == "modify"


def test_exploration_bonus_favors_less_pulled():
    # Moyennes égales (0.5) mais insert peu tiré → bonus d'exploration plus fort.
    stats = {"modify": (100, 50.0), "delete": (100, 50.0), "insert": (2, 1.0)}
    assert select_arm(ARMS, stats, c=2.0) == "insert"


def test_bandit_persists_and_updates(tmp_path):
    store = RunStore(tmp_path / "b.db")
    bandit = UCBBandit(store, "main", ARMS, c=1.4)
    bandit.update("modify", 1.0)
    bandit.update("modify", 0.0)
    bandit.update("delete", 1.0)
    stats = bandit.stats()
    assert stats["modify"] == (2, 1.0)
    assert stats["delete"] == (1, 1.0)
    # Un opérateur hors bras n'est pas enregistré.
    bandit.update("crossover", 1.0)
    assert "crossover" not in bandit.stats()
    store.close()
