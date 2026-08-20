"""Lecture de l'état des tickets de `docs/tickets/`.

Les tickets ne portent pas de champ de statut normalisé : l'état est donc
*déduit* de deux signaux présents dans le texte — les cases à cocher
(`- [x]` / `- [ ]`) et la ligne `**État**` / `**État d'avancement**` — puis
surchargeable à la main dans `scripts/dashboard/tickets_status.yaml`, qui
reste la source de vérité quand elle est renseignée.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover — yaml est fourni par le venv du projet
    yaml = None

REPO_ROOT = Path(__file__).resolve().parents[2]
TICKETS_DIR = REPO_ROOT / "docs" / "tickets"
OVERRIDES_PATH = Path(__file__).resolve().parent / "tickets_status.yaml"

TODO = "à faire"
DOING = "en cours"
DONE = "terminé"
BLOCKED = "bloqué"
DROPPED = "abandonné"
UNKNOWN = "sans statut"

STATUS_ORDER = [DOING, BLOCKED, TODO, DONE, DROPPED, UNKNOWN]
STATUS_KIND = {
    DOING: "warning",
    BLOCKED: "critical",
    TODO: "muted",
    DONE: "good",
    DROPPED: "muted",
    UNKNOWN: "muted",
}
STATUS_ICON = {DOING: "🟠", BLOCKED: "🔴", TODO: "⚪", DONE: "🟢", DROPPED: "⚫", UNKNOWN: "❔"}

_DONE_RE = re.compile(r"^\s*[-*]\s*\[[xX]\]")
_TODO_RE = re.compile(r"^\s*[-*]\s*\[ \]")
_TITLE_RE = re.compile(r"^#\s+(.*)$")
_STATE_RE = re.compile(r"^\*\*(État[^*:]*)\*\*\s*:\s*(.+)$")
_NUM_RE = re.compile(r"ticket[_-]?(\d+)")


@dataclass
class Ticket:
    path: Path
    number: str
    title: str
    status: str
    status_source: str  # "surcharge" | "cases" | "texte" | "défaut"
    done: int
    todo: int
    state_line: str
    note: str
    modified: datetime
    lines: int

    @property
    def total_boxes(self) -> int:
        return self.done + self.todo

    @property
    def progress(self) -> float | None:
        return self.done / self.total_boxes if self.total_boxes else None

    @property
    def rel_path(self) -> str:
        return str(self.path.relative_to(REPO_ROOT))


def _load_overrides() -> dict[str, dict]:
    if yaml is None or not OVERRIDES_PATH.is_file():
        return {}
    data = yaml.safe_load(OVERRIDES_PATH.read_text(encoding="utf-8")) or {}
    tickets = data.get("tickets", data) if isinstance(data, dict) else {}
    return {str(k): (v or {}) for k, v in tickets.items()} if isinstance(tickets, dict) else {}


def _derive_from_text(state_line: str) -> tuple[str, str] | None:
    """Déduit un statut de la ligne `**État**`, quand elle est explicite."""
    low = state_line.lower()
    if any(k in low for k in ("abandonn", "annulé", "annule")):
        return DROPPED, "texte"
    if any(k in low for k in ("bloqué", "bloque ", "en attente de")):
        return BLOCKED, "texte"
    if any(k in low for k in ("aucune correction engagée", "non démarré", "à engager", "à faire")):
        return TODO, "texte"
    if any(k in low for k in ("livré", "livrée", "livrées", "reste ", "en cours")):
        return DOING, "texte"
    if any(k in low for k in ("clos", "terminé", "complet")):
        return DONE, "texte"
    return None


def parse_ticket(path: Path, overrides: dict[str, dict]) -> Ticket:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    title = next((m.group(1).strip() for m in map(_TITLE_RE.match, lines) if m), path.stem)
    done = sum(1 for line in lines if _DONE_RE.match(line))
    todo = sum(1 for line in lines if _TODO_RE.match(line))
    state_line = next((m.group(2).strip() for m in map(_STATE_RE.match, lines) if m), "")
    number = (_NUM_RE.search(path.stem) or re.match(r"()", "")).group(1) or "—"

    # 1) cases à cocher — le signal le plus fiable quand il existe
    if done + todo > 0:
        status = DONE if todo == 0 else (TODO if done == 0 else DOING)
        source = "cases"
    # 2) ligne d'état explicite
    elif (derived := _derive_from_text(state_line)) is not None:
        status, source = derived
    else:
        status, source = UNKNOWN, "défaut"

    # 3) surcharge manuelle : elle gagne toujours
    override = overrides.get(path.stem) or overrides.get(f"ticket_{number}") or overrides.get(number) or {}
    note = str(override.get("note", "") or "")
    if override.get("status"):
        status, source = str(override["status"]), "surcharge"

    return Ticket(
        path=path,
        number=number,
        title=title,
        status=status,
        status_source=source,
        done=done,
        todo=todo,
        state_line=state_line,
        note=note,
        modified=datetime.fromtimestamp(path.stat().st_mtime),
        lines=len(lines),
    )


def load_tickets() -> list[Ticket]:
    if not TICKETS_DIR.is_dir():
        return []
    overrides = _load_overrides()
    tickets = [parse_ticket(p, overrides) for p in sorted(TICKETS_DIR.glob("ticket_*.md"))]
    rank = {s: i for i, s in enumerate(STATUS_ORDER)}
    return sorted(tickets, key=lambda t: (rank.get(t.status, 99), t.number))


def summary(tickets: list[Ticket]) -> dict[str, int]:
    counts = {s: 0 for s in STATUS_ORDER}
    for t in tickets:
        counts[t.status] = counts.get(t.status, 0) + 1
    return counts
