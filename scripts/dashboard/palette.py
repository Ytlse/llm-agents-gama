"""Palette du tableau de bord.

Les couleurs de mode sont celles imposées par `.claude/CLAUDE.md` (cohérence
visuelle notebooks / GAMA / Grafana). Chaque teinte est déclinée en deux pas :
un pour la surface claire, un pour la surface sombre.

⚠️  Contrainte assumée : les teintes imposées (rouge / vert / cyan / magenta)
n'atteignent pas le seuil de séparation daltonisme (ΔE deutan ≈ 3–4, seuil 8).
Ce n'est pas corrigeable sans abandonner la palette officielle. La couleur ne
porte donc JAMAIS l'identité dans ce dashboard : tout graphe de modes est un
barres horizontales dont le mode est écrit sur l'axe et la valeur en bout de
barre, doublé d'une vue tableau. La couleur ne fait que renforcer.
"""

from __future__ import annotations

# Modes tels qu'écrits dans moves.csv → (pas clair, pas sombre)
MODE_COLORS: dict[str, tuple[str, str]] = {
    "Voiture Privée": ("#CE3B4B", "#E4646F"),  # rouge
    "Vélo": ("#7C4DDB", "#9C7BEE"),  # violet
    "Transports_collectifs": ("#178A3F", "#3BAE60"),  # vert
    "Marche": ("#0B7A9B", "#329BB8"),  # cyan
    "Deux-roues motorisé": ("#B5259B", "#D658B0"),  # magenta
    "Train": ("#5B3AB8", "#7E68D8"),  # violet profond (famille « purple »)
}

# Modes hors palette officielle (non-déplacements, résidus) : gris neutre.
NEUTRAL = ("#6E6D69", "#98968E")

# États : réservés à la santé, jamais réutilisés comme couleur de série.
STATUS = {
    "good": ("#178A3F", "#3BAE60"),
    "warning": ("#A66A00", "#D19A2E"),
    "critical": ("#C02A2A", "#E36A6A"),
    "muted": ("#6E6D69", "#98968E"),
}

MODE_LABELS = {
    "Voiture Privée": "Voiture",
    "Transports_collectifs": "Transports collectifs",
    "Deux-roues motorisé": "Deux-roues motorisé",
}


def mode_color(mode: str, dark: bool) -> str:
    pair = MODE_COLORS.get(mode, NEUTRAL)
    return pair[1] if dark else pair[0]


def status_color(kind: str, dark: bool) -> str:
    pair = STATUS.get(kind, STATUS["muted"])
    return pair[1] if dark else pair[0]


def mode_label(mode: str) -> str:
    return MODE_LABELS.get(mode, mode)
