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

    peers = []
    for name, weight in weights.items():
        effective_weight = max(1, round((weight / total_weight) * 100))
        peers.append({"name": name, "weight": effective_weight, "current_weight": 0})

    total_slots = sum(p["weight"] for p in peers)
    sequence: list[str] = []

    for _ in range(total_slots):
        for p in peers:
            p["current_weight"] += p["weight"]
        best = max(peers, key=lambda x: x["current_weight"])
        best["current_weight"] -= total_slots
        sequence.append(best["name"])

    return sequence
