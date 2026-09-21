#!/usr/bin/env python3
"""Figure — durée de l'effet d'un choc, et rôle de la fenêtre de prompt (ticket 077).

Trois bras appariés, mêmes graines, un seul paramètre différent entre les deux bras choqués :
la fenêtre du bloc « ce qui a changé récemment » (14 jours contre 7). La figure montre que la
date de retour de la voiture suit cette fenêtre, et non la décroissance du souvenir.

Bibliothèque standard uniquement, SVG en ligne, sur le modèle de `scripts/synthesis/charts.py`.
Figure composée en ANGLAIS : toutes les figures de l'article le sont.

    python scripts/analysis/figure_fenetre_choc.py -o <sortie.svg>
"""

from __future__ import annotations

import argparse
import csv
import statistics
from datetime import date
from pathlib import Path

# Palette catégorielle validée (dataviz, slots 1-3). Ne pas remplacer sans revalider :
#   node scripts/validate_palette.js "#2a78d6,#eb6834,#1baf7a" --mode light
BRAS = [
    ("Shock · 14-day window", "experiments/archive/2026-09-19_18_09", "#2a78d6", "#3987e5"),
    ("Shock · 7-day window", "experiments/archive/2026-09-20_17_44", "#eb6834", "#d95926"),
    ("No shock (control)", "experiments/archive/2026-09-20_09_53", "#1baf7a", "#199e70"),
]
ANCRE = date(2026, 3, 16)  # jour 1 du run
JOUR_CHOC = 15
SORTIES = {14: 29, 7: 22}  # fenêtre → jour de sortie du souvenir (choc + fenêtre)

L, R, T, B = 66, 150, 58, 62
W, H = 1180, 500


def serie(racine: Path, dossier: str) -> dict[int, float]:
    """P(voiture) moyenne par jour du run, depuis `moves.csv`."""
    par: dict[int, list[float]] = {}
    with (racine / dossier / "moves.csv").open(encoding="utf-8") as f:
        for ligne in csv.DictReader(f):
            j = date(*map(int, ligne["Heure de départ"][:10].split("-")))
            par.setdefault((j - ANCRE).days + 1, []).append(
                float(ligne["P(Voiture Privée) %"])
            )
    return {j: statistics.mean(v) for j, v in sorted(par.items())}


def _x(j: int, jmin: int, jmax: int) -> float:
    return L + (j - jmin) / (jmax - jmin) * (W - L - R)


def _y(p: float) -> float:
    return T + (100 - p) / 100 * (H - T - B)


def composer(series: list[tuple[str, dict[int, float], str, str]]) -> str:
    jours = sorted({j for _, s, _, _ in series for j in s})
    jmin, jmax = jours[0], jours[-1]
    o: list[str] = []
    a = o.append

    a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
      f'font-family="Inter, Helvetica, Arial, sans-serif" role="img" '
      f'aria-label="Car probability per simulated day for three experimental arms">')
    a("<style>"
      ".surface{fill:#fcfcfb}.ink{fill:#1a1a19}.ink2{fill:#5c5b54}.grid{stroke:#e6e5e0}"
      ".rule{stroke:#c9c8c1}"
      "@media (prefers-color-scheme: dark){"
      ".surface{fill:#1a1a19}.ink{fill:#ffffff}.ink2{fill:#c3c2b7}"
      ".grid{stroke:#333330}.rule{stroke:#4a4944}}"
      "</style>")
    a(f'<rect class="surface" width="{W}" height="{H}"/>')

    # Titre et sous-titre : le titre nomme le résultat, pas les axes.
    a(f'<text class="ink" x="{L}" y="26" font-size="17" font-weight="600">'
      f'The effect lasts as long as the prompt window, not as long as the memory</text>')
    a(f'<text class="ink2" x="{L}" y="45" font-size="12.5">'
      f'Same agent, same seeds, same shock on day 15. The two shocked arms differ by one '
      f'setting: how many days a shock memory stays in the prompt.</text>')

    # Grille horizontale, récessive.
    for p in range(0, 101, 25):
        y = _y(p)
        a(f'<line class="grid" x1="{L}" y1="{y:.1f}" x2="{W - R}" y2="{y:.1f}" stroke-width="1"/>')
        a(f'<text class="ink2" x="{L - 10}" y="{y + 4:.1f}" font-size="11.5" text-anchor="end">{p}%</text>')

    # Repères verticaux : le choc, puis chaque sortie de fenêtre.
    def repere(j: int, libelle: str, couleur: str, dy: int) -> None:
        x = _x(j, jmin, jmax)
        a(f'<line x1="{x:.1f}" y1="{T - 6}" x2="{x:.1f}" y2="{H - B}" stroke="{couleur}" '
          f'stroke-width="1.5" stroke-dasharray="4 4" opacity="0.75"/>')
        a(f'<text class="ink2" x="{x + 5:.1f}" y="{T + dy}" font-size="11" fill="{couleur}">{libelle}</text>')

    repere(JOUR_CHOC, "day 15 · engine failure", "#5c5b54", 6)
    repere(SORTIES[7], "day 22 · 7-day memory leaves the prompt", "#eb6834", 24)
    repere(SORTIES[14], "day 29 · 14-day memory leaves the prompt", "#2a78d6", 42)

    # Axe des abscisses.
    a(f'<line class="rule" x1="{L}" y1="{H - B}" x2="{W - R}" y2="{H - B}" stroke-width="1"/>')
    for j in jours:
        if j % 5 == 0 or j in (1, JOUR_CHOC):
            x = _x(j, jmin, jmax)
            a(f'<text class="ink2" x="{x:.1f}" y="{H - B + 18}" font-size="11" text-anchor="middle">{j}</text>')
    a(f'<text class="ink2" x="{(L + W - R) / 2:.0f}" y="{H - B + 38}" font-size="11.5" '
      f'text-anchor="middle">simulated day of the run (weekends are not simulated)</text>')
    a(f'<text class="ink2" x="{L - 46}" y="{T - 14}" font-size="11.5">P(car)</text>')

    # Les séries. Marqueurs >= 8 px avec anneau de surface, étiquette directe en bout.
    for nom, s, clair, _sombre in series:
        pts = [(_x(j, jmin, jmax), _y(p)) for j, p in sorted(s.items())]
        d = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f} {y:.1f}" for i, (x, y) in enumerate(pts))
        a(f'<path d="{d}" fill="none" stroke="{clair}" stroke-width="2" '
          f'stroke-linejoin="round" stroke-linecap="round"/>')
        for x, y in pts:
            a(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{clair}" '
              f'stroke="#fcfcfb" stroke-width="1.5"/>')
        xf, yf = pts[-1]
        a(f'<text x="{xf + 12:.1f}" y="{yf + 4:.1f}" font-size="12" font-weight="600" '
          f'fill="{clair}">{nom}</text>')

    # Lecture, sous la figure : ce que le lecteur doit retenir en une phrase.
    a(f'<text class="ink2" x="{L}" y="{H - 14}" font-size="11.5">'
      f'Collapse takes one day. Recovery takes two weeks and stops short: 80% vs 95% for the '
      f'control — the shock leaves a permanent trace.</text>')
    a("</svg>")
    return "\n".join(o)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("-o", "--sortie", type=Path, required=True)
    p.add_argument("--racine", type=Path, default=Path.cwd())
    args = p.parse_args()

    series = [(nom, serie(args.racine, d), c, cs) for nom, d, c, cs in BRAS]
    for nom, s, _, _ in series:
        print(f"  {nom:<26} {len(s)} jours · P(car) {min(s.values()):.0f}–{max(s.values()):.0f} %")
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    args.sortie.write_text(composer(series), encoding="utf-8")
    print(f"→ {args.sortie}")


if __name__ == "__main__":
    main()
