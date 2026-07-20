"""Lecture robuste de ``llm_exchanges.jsonl``.

Le fichier n'est pas toujours du JSONL strict : selon les versions du logger,
les entrées peuvent être des objets JSON *pretty-printed* concaténés sur
plusieurs lignes. On lit donc en flux avec ``json.JSONDecoder.raw_decode``,
qui accepte indifféremment les deux formats.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator


def iter_exchanges(path: str | Path) -> Iterator[dict]:
    """Itère sur toutes les entrées du journal, quel que soit son format
    (JSONL une-ligne-par-objet ou objets pretty-printed concaténés)."""
    decoder = json.JSONDecoder()
    buf = Path(path).read_text(encoding="utf-8")
    idx, size = 0, len(buf)
    while idx < size:
        while idx < size and buf[idx] in " \t\r\n":
            idx += 1
        if idx >= size:
            break
        obj, end = decoder.raw_decode(buf, idx)
        idx = end
        if isinstance(obj, dict):
            yield obj


def itinerary_entries(path: str | Path,
                      category: str = "itinary_multi_agent") -> list[dict]:
    """Renvoie les entrées de choix d'itinéraire (catégorie ``category``)."""
    return [e for e in iter_exchanges(path) if e.get("category") == category]
