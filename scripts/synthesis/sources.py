"""Résolution et sondage des sources de la page de synthèse.

Une source est décrite dans ``sources.yaml`` puis sondée : présente ou non,
empreinte, date. Rien n'échoue ici — une source absente devient une carte
« Données manquantes » dans la page.
"""
from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

# Empreinte : plafonnée, un moves.csv de 6 000 lignes n'a pas besoin d'être lu
# en entier pour être identifié de façon stable entre deux régénérations.
_HASH_MAX_BYTES = 4 * 1024 * 1024


@dataclass
class Source:
    """Une entrée du manifeste, sondée sur disque."""

    id: str
    path: Path
    role: str = ""
    exists: bool = False
    is_dir: bool = False
    size: Optional[int] = None
    mtime: Optional[str] = None
    sha256: Optional[str] = None
    resolved: Optional[str] = None
    note: str = ""

    @property
    def rel(self) -> str:
        try:
            return str(self.path.relative_to(REPO_ROOT))
        except ValueError:
            return str(self.path)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "path": self.rel, "role": self.role,
            "exists": self.exists, "is_dir": self.is_dir, "size": self.size,
            "mtime": self.mtime, "sha256": self.sha256,
            "resolved": self.resolved, "note": self.note,
        }


def probe(source_id: str, path: Path | str, role: str = "", note: str = "") -> Source:
    """Sonde un chemin : existence, taille, date, empreinte partielle."""
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    src = Source(id=source_id, path=p, role=role, note=note)
    if not p.exists():
        return src
    src.exists = True
    src.is_dir = p.is_dir()
    resolved = p.resolve()
    if resolved != p:
        try:
            src.resolved = str(resolved.relative_to(REPO_ROOT))
        except ValueError:
            src.resolved = str(resolved)
    stat = p.stat()
    src.mtime = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds")
    if not src.is_dir:
        src.size = stat.st_size
        src.sha256 = _digest(p)
    return src


def _digest(path: Path) -> Optional[str]:
    h = hashlib.sha256()
    read = 0
    try:
        with path.open("rb") as fh:
            while read < _HASH_MAX_BYTES:
                chunk = fh.read(min(1 << 20, _HASH_MAX_BYTES - read))
                if not chunk:
                    break
                h.update(chunk)
                read += len(chunk)
    except OSError:
        return None
    return h.hexdigest()


@dataclass
class Manifest:
    """Le manifeste chargé, plus le registre des sources sondées."""

    raw: dict
    sources: dict[str, Source] = field(default_factory=dict)

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.raw
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def track(self, source_id: str, path: Path | str, role: str = "",
              note: str = "") -> Source:
        src = probe(source_id, path, role, note)
        self.sources[source_id] = src
        return src

    def path_of(self, dotted: str) -> Optional[Path]:
        value = self.get(dotted)
        if not value:
            return None
        p = Path(value)
        return p if p.is_absolute() else REPO_ROOT / p


def load_manifest(path: Path | str | None = None) -> Manifest:
    """Charge ``sources.yaml`` (ou un manifeste alternatif)."""
    p = Path(path) if path else Path(__file__).with_name("sources.yaml")
    if not p.is_absolute():
        p = REPO_ROOT / p
    with p.open(encoding="utf-8") as fh:
        return Manifest(raw=yaml.safe_load(fh) or {})


# ── Accès au moteur de calibration ───────────────────────────────────────────
#
# Les métriques vivent dans prompt_calibration/, dépôt git autonome. On l'ajoute
# au sys.path plutôt que de dupliquer la loss : un score affiché ici doit être
# *exactement* celui du moteur, sinon la comparaison ne veut rien dire.

def import_calibration(repo: Path | str = "prompt_calibration") -> tuple[Optional[Any], str]:
    """Importe le paquet ``calibration``. Renvoie ``(module, message d'erreur)``."""
    root = Path(repo)
    if not root.is_absolute():
        root = REPO_ROOT / root
    if not (root / "calibration" / "metrics.py").exists():
        return None, (f"Le dépôt de calibration est introuvable ({root}). "
                      "Le score ne peut pas être calculé : clonez-le à cet emplacement.")
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        import calibration  # noqa: F401
        from calibration import metrics  # noqa: F401
    except Exception as exc:  # dépendance manquante dans l'interpréteur courant
        return None, (f"Import du moteur de calibration impossible : {exc}. "
                      "Utilisez un interpréteur disposant de pandas/numpy/pydantic "
                      "(par ex. llm-agents/.venv/bin/python).")
    return calibration, ""
