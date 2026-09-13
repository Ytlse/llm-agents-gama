"""Marqueurs par étage : le dossier d'un test dit ce qu'il est (unit, contract, integration, e2e).

Un test peut aussi porter son marqueur explicitement ; `--strict-markers` refuse les inconnus.
"""
from __future__ import annotations

import pytest

_BY_DIR = ("unit", "contract", "integration", "e2e")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        parts = set(item.path.parts)
        for marker in _BY_DIR:
            if marker in parts:
                item.add_marker(getattr(pytest.mark, marker))
                break
