"""Lecture de l'état des tickets de `docs/tickets/`.

Les tickets ne portent pas de champ de statut normalisé : l'état est donc
*déduit* de deux signaux présents dans le texte — les cases à cocher
(`- [x]` / `- [ ]`) et la ligne `**État**` / `**État d'avancement**` — puis
surchargeable dans `scripts/dashboard/tickets_status.yaml`, qui reste la source de
vérité quand elle est renseignée.

Ce fichier est aussi ÉCRIT depuis le tableau de bord (`save_override`) : l'écriture
préserve à l'octet tout ce qui n'est pas l'entrée modifiée — commentaires d'en-tête,
ordre des entrées, notes et style des autres tickets.
"""

from __future__ import annotations

import io
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover — yaml est fourni par le venv du projet
    yaml = None

try:
    from ruamel.yaml import YAML
    from ruamel.yaml.comments import CommentedMap
    from ruamel.yaml.scalarstring import FoldedScalarString
except ImportError:  # pragma: no cover — ruamel est fourni par le venv du projet
    YAML = None

REPO_ROOT = Path(__file__).resolve().parents[2]
TICKETS_DIR = REPO_ROOT / "docs" / "tickets"
OVERRIDES_PATH = Path(__file__).resolve().parent / "tickets_status.yaml"

TODO = "à faire"
DOING = "en cours"
DONE = "terminé"
BLOCKED = "bloqué"
PAUSED = "en veille"
DROPPED = "abandonné"
UNKNOWN = "sans statut"

# `en veille` ≠ `bloqué` : rien n'empêche d'avancer, c'est une DÉCISION de ne pas le
# faire maintenant (le travail reprendra tel quel). `bloqué` dit qu'une dépendance
# extérieure manque. Les confondre ferait chercher un déblocage qui n'existe pas.
STATUS_ORDER = [DOING, BLOCKED, TODO, PAUSED, DONE, DROPPED, UNKNOWN]
STATUS_KIND = {
    DOING: "warning",
    BLOCKED: "critical",
    TODO: "muted",
    PAUSED: "muted",
    DONE: "good",
    DROPPED: "muted",
    UNKNOWN: "muted",
}
STATUS_ICON = {
    DOING: "🟠",
    BLOCKED: "🔴",
    TODO: "⚪",
    PAUSED: "🔵",
    DONE: "🟢",
    DROPPED: "⚫",
    UNKNOWN: "❔",
}

# Ce qu'on peut CHOISIR dans l'interface : le vocabulaire fermé, sans `sans statut`
# qui n'est pas une décision mais l'absence d'entrée (R16).
EDITABLE_STATUSES = [TODO, DOING, DONE, BLOCKED, PAUSED, DROPPED]

# 4096 est la SEULE largeur de dump pour laquelle les 1 470 lignes existantes se
# relisent et se réécrivent à l'octet (60, 80, 92 et 100 recassent les notes des autres
# tickets). Les notes neuves portent donc leurs propres positions de repli, sinon elles
# tiendraient sur une seule très longue ligne.
_LARGEUR_DUMP = 4096
_LARGEUR_NOTE = 88


class StatutInconnu(ValueError):
    """Le fichier porte une valeur de statut hors vocabulaire."""


class CleInvalide(ValueError):
    """Une clé du fichier ne désigne pas exactement un ticket."""


def statut_editable(statut: str) -> str:
    """Le statut à pré-sélectionner dans l'interface (R16).

    `sans statut` n'est pas une décision : il n'est pas proposé. Le sélecteur part alors de
    `à faire`, et l'interface doit dire que ce ticket n'a pas encore d'entrée — sinon rien ne
    distingue « je n'ai pas choisi » de « j'ai choisi à faire ».
    """
    return statut if statut in EDITABLE_STATUSES else TODO


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
    # Clé = nom de fichier complet, et rien d'autre : `_verifier_cles` a déjà refusé le
    # reste. Résoudre une forme courte appliquerait un seul statut à deux tickets.
    override = overrides.get(path.stem) or {}
    note = str(override.get("note", "") or "")
    if override.get("status"):
        override_status = str(override["status"])
        if override_status not in STATUS_ICON:
            raise StatutInconnu(
                f"{path.stem} : statut de surcharge inconnu {override_status!r} dans "
                f"{OVERRIDES_PATH.name} — attendu l'un de {EDITABLE_STATUSES}"
            )
        status, source = override_status, "surcharge"

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


def _verifier_cles(overrides: dict[str, dict], stems: set[str]) -> None:
    """Toute clé du fichier doit désigner exactement un ticket (R28).

    Deux pièges, tous deux silencieux aujourd'hui : une clé mal orthographiée ne
    s'applique à rien — on croit avoir posé un statut qui n'est nulle part —, et une
    clé COURTE (`ticket_005`) s'applique aux DEUX tickets qui portent ce numéro, alors
    qu'ils sont distincts. L'écriture depuis l'interface n'en produit pas, mais le
    fichier s'édite aussi à la main.
    """
    inconnues = sorted(cle for cle in overrides if cle not in stems)
    if not inconnues:
        return
    details = []
    for cle in inconnues:
        vises = sorted(s for s in stems if s == cle or s.startswith(f"{cle}_") or _NUM_RE.search(s) and cle == _NUM_RE.search(s).group(1))
        details.append(f"{cle!r} → {', '.join(vises) if vises else 'aucun ticket'}")
    raise CleInvalide(
        f"{OVERRIDES_PATH.name} : {len(inconnues)} clé(s) ne désignent pas exactement un ticket "
        f"({'; '.join(details)}). La clé est le nom de fichier complet, sans extension."
    )


def load_tickets() -> list[Ticket]:
    if not TICKETS_DIR.is_dir():
        return []
    overrides = _load_overrides()
    chemins = sorted(TICKETS_DIR.glob("ticket_*.md"))
    _verifier_cles(overrides, {p.stem for p in chemins})
    tickets = [parse_ticket(p, overrides) for p in chemins]
    rank = {s: i for i, s in enumerate(STATUS_ORDER)}
    return sorted(tickets, key=lambda t: (rank.get(t.status, 99), t.number))


def summary(tickets: list[Ticket]) -> dict[str, int]:
    counts = {s: 0 for s in STATUS_ORDER}
    for t in tickets:
        counts[t.status] = counts.get(t.status, 0) + 1
    return counts


# ── Écriture du statut ────────────────────────────────────────────────────────
def _rt_yaml():
    """Le lecteur/écrivain round-trip : il conserve commentaires, ordre et style."""
    if YAML is None:  # pragma: no cover — ruamel est fourni par le venv du projet
        raise RuntimeError(
            "ruamel.yaml est requis pour écrire les statuts de tickets "
            "(pip install ruamel.yaml dans llm-agents/.venv)"
        )
    parseur = YAML()
    parseur.preserve_quotes = True
    parseur.width = _LARGEUR_DUMP
    return parseur


def _normaliser_note(note: str) -> str:
    """Le texte tel qu'il sera STOCKÉ : espaces d'un paragraphe réduits, paragraphes gardés.

    L'écriture et la comparaison doivent normaliser pareil, sinon une retouche purement
    cosmétique produit un diff, et l'interface annonce « rien à enregistrer » pour un texte
    qu'elle vient de recevoir.
    """
    paragraphes = [" ".join(bloc.split()) for bloc in re.split(r"\n\s*\n", note.strip()) if bloc.strip()]
    return "\n\n".join(paragraphes)


def _note_pliee(note: str) -> "FoldedScalarString":
    """La note en bloc replié `>-`, replié autour de 88 colonnes comme les notes existantes.

    Les espaces multiples d'un paragraphe sont normalisés ; une ligne vide sépare toujours
    deux paragraphes. Le repli est explicite parce que le dump se fait à 4096 colonnes.
    """
    texte = _normaliser_note(note)
    scalaire = FoldedScalarString(texte)
    positions: list[int] = []
    depart = 0
    for i, caractere in enumerate(texte):
        if caractere == "\n":
            depart = i + 1
        elif caractere == " " and i - depart >= _LARGEUR_NOTE:
            positions.append(i)
            depart = i
    scalaire.fold_pos = positions
    return scalaire


def save_override(key: str, status: str, note: str | None = None, *, path: Path | None = None) -> bool:
    """Écrit le statut (et la note) du ticket `key` dans la source de vérité.

    `key` est le NOM DE FICHIER COMPLET sans extension : deux tickets distincts partagent
    le numéro 005, une clé courte appliquerait un seul statut aux deux.

    `note=None` laisse la note en place ; `note=""` la retire. La distinction compte :
    changer un statut sans y penser ne doit pas effacer la phrase qui le justifie.

    Renvoie True si le fichier a changé, False si l'entrée disait déjà cela — auquel cas
    rien n'est écrit, pour ne pas salir `git status` sans raison. Le fichier est relu à
    chaque appel : une édition faite à la main entre-temps est conservée.
    """
    if status not in EDITABLE_STATUSES:
        raise StatutInconnu(f"statut inconnu {status!r} — attendu l'un de {EDITABLE_STATUSES}")

    # Écrire une clé courte rendrait l'onglet illisible au prochain chargement : ce que la
    # lecture refuse (R28), l'écriture doit le refuser aussi.
    stems = {p.stem for p in TICKETS_DIR.glob("ticket_*.md")} if TICKETS_DIR.is_dir() else set()
    if stems and key not in stems:
        vises = sorted(s for s in stems if s.startswith(f"{key}_"))
        raise CleInvalide(
            f"clé refusée {key!r} : elle ne désigne pas exactement un ticket "
            f"({', '.join(vises) if vises else 'aucun ticket'}). La clé est le nom de fichier "
            f"complet, sans extension."
        )

    # Défaut résolu à l'APPEL, pas à l'import : lié à l'import, il ignorait une
    # redirection de `OVERRIDES_PATH` en test et écrivait dans le vrai fichier.
    path = Path(path) if path is not None else OVERRIDES_PATH
    parseur = _rt_yaml()
    avant = path.read_text(encoding="utf-8") if path.is_file() else "tickets:\n"
    data = parseur.load(avant)
    if data is None:
        data = CommentedMap()
    entrees = data["tickets"] if "tickets" in data else data
    if entrees is None:
        data["tickets"] = entrees = CommentedMap()

    entree = entrees.get(key)
    if entree is None:
        entree = CommentedMap()
        entrees[key] = entree  # ordre d'insertion : la nouvelle entrée va en fin de liste

    entree["status"] = status
    propre = None if note is None else note.strip()
    if propre is None:
        pass  # la note n'est pas dans la demande : on n'y touche pas
    elif not propre:
        entree.pop("note", None)
    elif _normaliser_note(propre) != _normaliser_note(str(entree.get("note", "") or "")):
        # La note n'est reconstruite que si son texte a bougé : sinon on garderait le
        # texte mais on lui imposerait NOS positions de repli, donc un diff pour rien.
        entree["note"] = _note_pliee(propre)

    tampon = io.StringIO()
    parseur.dump(data, tampon)
    apres = tampon.getvalue()
    if apres == avant:
        return False

    provisoire = path.with_name(path.name + ".tmp")
    provisoire.write_text(apres, encoding="utf-8")
    os.replace(provisoire, path)
    return True
