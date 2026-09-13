"""
core/selection.py — Algorithme Smooth Weighted Round-Robin (SWRR, type NGINX).

Fonction pure : construit la séquence de rotation pondérée une seule fois ;
le parcours circulaire (curseur) reste dans le LoadBalancer.
"""

from __future__ import annotations


def build_swrr_sequence(weights: dict[str, float]) -> list[str]:
    """
    Construit la liste de rotation pondérée entrelacée.

    Ex : {"mistral": 2.0, "openai": 1.0, "google": 1.0} → séquence où mistral
    apparaît deux fois plus souvent, sans micro-rafales sur un même provider.
    """
    if not weights:
        return []

    total_weight = sum(weights.values())

    names: list[str] = []
    slot_weights: list[int] = []
    for name, weight in weights.items():
        names.append(name)
        slot_weights.append(max(1, round((weight / total_weight) * 100)))

    total_slots = sum(slot_weights)
    current = [0] * len(names)
    sequence: list[str] = []

    for _ in range(total_slots):
        for i, w in enumerate(slot_weights):
            current[i] += w
        best = max(range(len(names)), key=lambda i: current[i])
        current[best] -= total_slots
        sequence.append(names[best])

    return sequence
