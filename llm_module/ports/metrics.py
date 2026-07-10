"""
ports/metrics.py — Contrat des compteurs de métriques worker.

Le worker Celery n'expose pas de /metrics : ses compteurs sont persistés
(sans TTL) et relus par le collecteur Prometheus custom de l'API.
Les noms sont composés « metrique:label[:label2] », ex. "llm_calls_ok_total:groq_llama4".
"""

from __future__ import annotations
from typing import Protocol


class MetricsSink(Protocol):
    def incr(self, name: str, amount: int = 1) -> None: ...

    def get(self, name: str) -> int: ...

    def items(self) -> dict[str, int]:
        """Snapshot de tous les compteurs — une seule lecture par scrape."""
        ...
