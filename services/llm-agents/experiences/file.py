"""File d'attente FIFO persistante des expériences (ticket 035, spec parallelisation_experiences).

Stockage pur (aucun verrou ici) : la coordination — lecture, promotion, retrait — se fait dans
`reservations.py`, sous le verrou global partagé avec le registre de réservation, pour que
« tester les clés libres → réserver/défiler » reste atomique (R6). Une entrée retient le nom de
l'expérience, son **jeu de clés** calculé à la soumission (pré-filtre de disjonction, R2b) et les
options de relance ; la promotion réelle relance `lancer`, qui recalcule et réserve.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from experiences.experience import dossier_experiences


def _chemin() -> Path:
    return dossier_experiences() / ".file.json"


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def charger() -> list[dict]:
    """Entrées de la file, dans l'ordre FIFO de soumission."""
    p = _chemin()
    if not p.is_file():
        return []
    try:
        contenu = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return contenu if isinstance(contenu, list) else []


def sauver(entrees: list[dict]) -> None:
    p = _chemin()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(entrees, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def entree(exp: str, cles: set[str], args: dict) -> dict:
    """Construit une entrée de file normalisée."""
    return {
        "exp": exp,
        "cles": sorted(cles),
        "args": dict(args or {}),
        "soumis": _iso(),
    }


__all__ = ["charger", "entree", "sauver"]
