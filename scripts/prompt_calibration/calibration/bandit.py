"""Sélection d'opérateur par bandit UCB1 — phase 4.3 du ticket 004 (DE).

Le mutateur peut employer plusieurs opérateurs (modify / delete / insert /
reorder / merge_blocks / condense / split). Lequel privilégier ? On l'apprend en
ligne : chaque opérateur est un **bras** de bandit, la **récompense** est
``1`` si la mutation proposée avec cet opérateur a été acceptée (amélioration
significative du composite), ``0`` sinon.

**UCB1** (Auer et al. 2002) : on tire le bras maximisant
``moyenne + c·√(ln N / nᵢ)`` — la moyenne exploite, le second terme explore les
bras peu essayés. Tout bras jamais tiré est priorisé (moyenne + ∞).

Les statistiques par opérateur vivent dans le store (table ``bandit``, par
branche) → persistées, reprenables, et lisibles au dashboard (« le système
apprend *comment* il progresse »). Les fonctions de score sont **pures** (testées
hors store).
"""

from __future__ import annotations

import math
from typing import Optional

from .store import RunStore


def ucb_scores(stats: dict[str, tuple[int, float]], c: float,
               ) -> dict[str, float]:
    """Score UCB1 par bras. ``stats[op] = (pulls, reward_sum)``.

    Un bras jamais tiré reçoit ``+inf`` (exploration prioritaire). ``N`` = total
    des tirages sur tous les bras.
    """
    total = sum(pulls for pulls, _ in stats.values())
    scores: dict[str, float] = {}
    for op, (pulls, reward_sum) in stats.items():
        if pulls == 0:
            scores[op] = math.inf
        else:
            mean = reward_sum / pulls
            scores[op] = mean + c * math.sqrt(math.log(max(total, 1)) / pulls)
    return scores


def select_arm(arms: list[str], stats: dict[str, tuple[int, float]],
               c: float) -> str:
    """Bras à jouer : plus haut score UCB1 (bras inconnus d'abord, ordre stable)."""
    full = {op: stats.get(op, (0, 0.0)) for op in arms}
    scores = ucb_scores(full, c)
    # ``max`` sur (score, -index) → départage déterministe par l'ordre de ``arms``.
    return max(arms, key=lambda op: (scores[op], -arms.index(op)))


class UCBBandit:
    """Bandit UCB1 persisté par branche dans le store (table ``bandit``)."""

    def __init__(self, store: RunStore, branch: str, arms: list[str], c: float):
        self.store = store
        self.branch = branch
        self.arms = arms
        self.c = c

    def stats(self) -> dict[str, tuple[int, float]]:
        return self.store.bandit_stats(self.branch)

    def select(self) -> str:
        return select_arm(self.arms, self.stats(), self.c)

    def update(self, operator: str, reward: float) -> None:
        """Enregistre le résultat d'un tirage (récompense ∈ [0, 1])."""
        if operator in self.arms:
            self.store.bandit_update(self.branch, operator, reward)
