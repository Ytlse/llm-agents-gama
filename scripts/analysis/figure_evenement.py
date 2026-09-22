#!/usr/bin/env python3
"""Figure — décrochage et retour, par rôle, pour les deux régimes (ticket 100, lot 5).

UNE SEULE FIGURE POUR LES DEUX RÉGIMES, et c'est tout l'objet du ticket. Un choc subi à
l'arrivée et un article lu au réveil produisent la même courbe : la propension au mode visé,
par jour RELATIF à l'événement, et par rôle. La figure 7.2 du manuscrit en est la première
instance ; le § 7.3 en sera la seconde, sans un script de plus.

TROIS RÔLES, ET ILS NE SE DÉDUISENT PAS L'UN DE L'AUTRE
--------------------------------------------------------
`expose` — l'événement l'a atteint. `co_resident` — il vit sous le même toit qu'un exposé et
n'a RIEN reçu : c'est chez lui que se lit ce qui se transmet, et sans lui l'étage de diffusion
n'a pas d'objet. `temoin` — ni l'un ni l'autre, c'est la ligne de base du run.

L'ABSCISSE EST LE JOUR RELATIF, ET ELLE EXISTE TOUS LES JOURS
--------------------------------------------------------------
Y compris avant l'événement et longtemps après. Une abscisse qui n'existerait que les jours
d'événement ne tracerait rien — et c'est exactement ce que `moves.csv` écrit pour TOUTE
décision, y compris les jours nominaux.

GARDE DE VACUITÉ, NON NÉGOCIABLE
---------------------------------
Un rôle dont l'effectif tombe sous le minimum déclaré sort **« non concluant »**, jamais une
courbe. Dans ce dépôt, l'absence de mesure produit volontiers la valeur parfaite, et ce motif a
déjà menti. Une courbe tracée sur deux décisions ressemble exactement à une courbe tracée sur
deux cents.

Bibliothèque standard uniquement, SVG en ligne, sur le modèle de `figure_fenetre_choc.py`.
Figure composée en ANGLAIS : toutes les figures de l'article le sont.

    python scripts/analysis/figure_evenement.py <run> --mode car -o <sortie.svg>
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]

# Palette catégorielle validée (dataviz, slots 1-3). Ne pas remplacer sans revalider :
#   node scripts/validate_palette.js "#2a78d6,#eb6834,#1baf7a" --mode light
ROLES = (
    ("expose", "Exposed", "#eb6834"),
    ("co_resident", "Co-resident (heard only)", "#2a78d6"),
    ("temoin", "Control", "#1baf7a"),
)

# Mode canonique → colonne de probabilité de `moves.csv`. EXPLICITE et non devinée : trois
# vocabulaires de modes coexistent dans ce dépôt (ticket 077, lot A), et un mot qui passerait
# « par défaut » tracerait la courbe d'un autre mode sans que rien ne le dise.
COLONNE_PROBA = {
    "walking": "P(Marche) %",
    "cycling": "P(Vélo) %",
    "car": "P(Voiture Privée) %",
    "public_transport": "P(Transports_collectifs) %",
    "train": "P(Train) %",
    "motorbike": "P(Deux-roues motorisé) %",
}
LIBELLE_EN = {
    "walking": "walking", "cycling": "cycling", "car": "car",
    "public_transport": "public transport", "train": "train", "motorbike": "motorbike",
}

# Effectif minimal par (rôle, jour relatif) sous lequel le point n'est pas tracé. Déclaré ici,
# et rappelé sur la figure : un seuil qu'on ne lit pas sur l'image ne se discute pas.
EFFECTIF_MINIMAL = 3

L, R, T, B = 66, 170, 62, 66
W, H = 1180, 500


def series(run: Path, mode: str) -> tuple[dict, dict, str]:
    """Propension au mode visé par (rôle, jour relatif), et les effectifs qui la portent.

    Rend `({role: {jour: moyenne}}, {role: {jour: effectif}}, identifiant de l'événement)`.
    """
    colonne = COLONNE_PROBA[mode]
    valeurs: dict[str, dict[int, list[float]]] = {r: {} for r, _, _ in ROLES}
    evenement = ""
    chemin = run / "moves.csv"
    if not chemin.is_file():
        raise SystemExit(f"❌ {chemin} introuvable — ce run n'a pas de journal de décisions")

    with chemin.open(encoding="utf-8") as f:
        lecteur = csv.DictReader(f)
        if colonne not in (lecteur.fieldnames or []):
            raise SystemExit(
                f"❌ colonne « {colonne} » absente de {chemin}. Colonnes de probabilité "
                f"présentes : {[c for c in (lecteur.fieldnames or []) if c.startswith('P(')]}"
            )
        if "Rôle" not in (lecteur.fieldnames or []):
            raise SystemExit(
                f"❌ colonne « Rôle » absente de {chemin} : ce run est antérieur au ticket 100, "
                f"lot 5. Les rôles ne peuvent pas être reconstitués après coup — il faudrait "
                f"savoir qui était exposé, et c'est précisément ce que la colonne porte."
            )
        for ligne in lecteur:
            role = (ligne.get("Rôle") or "").strip()
            relatif = (ligne.get("Jour relatif au choc") or "").strip()
            brut = (ligne.get(colonne) or "").strip()
            # Une cellule VIDE n'est pas un zéro : c'est une décision sans répartition
            # (mono-choix, cache hérité). L'inclure comme 0 % ferait chuter la courbe pour une
            # raison qui n'a rien à voir avec l'événement.
            if not role or not relatif or not brut:
                continue
            evenement = evenement or (ligne.get("Choc") or "").strip()
            try:
                valeurs.setdefault(role, {}).setdefault(int(relatif), []).append(float(brut))
            except ValueError:
                continue

    moyennes = {
        role: {
            j: statistics.mean(v) for j, v in sorted(par.items())
            if len(v) >= EFFECTIF_MINIMAL
        }
        for role, par in valeurs.items()
    }
    effectifs = {role: {j: len(v) for j, v in sorted(par.items())}
                 for role, par in valeurs.items()}
    return moyennes, effectifs, evenement


def _x(j: int, jmin: int, jmax: int) -> float:
    if jmax == jmin:
        return (L + W - R) / 2
    return L + (j - jmin) / (jmax - jmin) * (W - L - R)


def _y(p: float) -> float:
    return T + (100 - p) / 100 * (H - T - B)


def composer(moyennes: dict, effectifs: dict, mode: str, evenement: str) -> str:
    jours = sorted({j for par in moyennes.values() for j in par})
    if not jours:
        raise SystemExit(
            "❌ non concluant : aucun point ne réunit l'effectif minimal de "
            f"{EFFECTIF_MINIMAL} décisions. Ce n'est PAS un résultat nul — c'est une absence "
            "de mesure, et une figure vide se lirait comme une absence d'effet."
        )
    jmin, jmax = jours[0], jours[-1]
    o: list[str] = []
    a = o.append
    libelle = LIBELLE_EN[mode]

    a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
      f'height="{H}" font-family="Inter, Helvetica, Arial, sans-serif" role="img" '
      f'aria-label="Propensity to use {libelle} by day relative to the event, for three roles">')
    a("<style>"
      ".surface{fill:#fcfcfb}.ink{fill:#1a1a19}.ink2{fill:#5c5b54}.grid{stroke:#e6e5e0}"
      ".rule{stroke:#c9c8c1}"
      "@media (prefers-color-scheme: dark){"
      ".surface{fill:#1a1a19}.ink{fill:#ffffff}.ink2{fill:#c3c2b7}"
      ".grid{stroke:#333330}.rule{stroke:#4a4944}}"
      "</style>")
    a(f'<rect class="surface" width="{W}" height="{H}"/>')

    # Le titre nomme le RÉSULTAT, pas les axes.
    a(f'<text class="ink" x="{L}" y="26" font-size="17" font-weight="600">'
      f'Who changes, and for how long</text>')
    a(f'<text class="ink2" x="{L}" y="45" font-size="12.5">'
      f'Propensity to choose {libelle}, by day relative to the event. Exposed agents met the '
      f'event; co-residents only heard about it; controls neither.</text>')

    for p in range(0, 101, 25):
        y = _y(p)
        a(f'<line class="grid" x1="{L}" y1="{y:.1f}" x2="{W - R}" y2="{y:.1f}" stroke-width="1"/>')
        a(f'<text class="ink2" x="{L - 10}" y="{y + 4:.1f}" font-size="11.5" '
          f'text-anchor="end">{p}%</text>')

    # Le jour 0 : celui où l'événement atteint l'exposé.
    if jmin <= 0 <= jmax:
        x0 = _x(0, jmin, jmax)
        a(f'<line x1="{x0:.1f}" y1="{T - 6}" x2="{x0:.1f}" y2="{H - B}" stroke="#5c5b54" '
          f'stroke-width="1.5" stroke-dasharray="4 4" opacity="0.75"/>')
        a(f'<text class="ink2" x="{x0 + 5:.1f}" y="{T + 6}" font-size="11">'
          f'day 0 · the event reaches the exposed agent</text>')

    a(f'<line class="rule" x1="{L}" y1="{H - B}" x2="{W - R}" y2="{H - B}" stroke-width="1"/>')
    for j in jours:
        if j % 5 == 0 or j == 0:
            x = _x(j, jmin, jmax)
            a(f'<text class="ink2" x="{x:.1f}" y="{H - B + 18}" font-size="11" '
              f'text-anchor="middle">{j:+d}</text>')
    a(f'<text class="ink2" x="{(L + W - R) / 2:.0f}" y="{H - B + 38}" font-size="11.5" '
      f'text-anchor="middle">days relative to the event (weekends are not simulated)</text>')
    a(f'<text class="ink2" x="{L - 46}" y="{T - 14}" font-size="11.5">P({libelle})</text>')

    absents = []
    for role, nom, couleur in ROLES:
        points = moyennes.get(role) or {}
        if not points:
            # « Non concluant » ÉCRIT sur la figure, et non une courbe absente : une série
            # manquante se lit comme un effet nul par celui qui ne sait pas qu'elle manque.
            absents.append(nom)
            continue
        pts = [(_x(j, jmin, jmax), _y(p)) for j, p in sorted(points.items())]
        d = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f} {y:.1f}" for i, (x, y) in enumerate(pts))
        a(f'<path d="{d}" fill="none" stroke="{couleur}" stroke-width="2" '
          f'stroke-linejoin="round" stroke-linecap="round"/>')
        for x, y in pts:
            a(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{couleur}" '
              f'stroke="#fcfcfb" stroke-width="1.5"/>')
        xf, yf = pts[-1]
        a(f'<text x="{xf + 12:.1f}" y="{yf + 4:.1f}" font-size="12" font-weight="600" '
          f'fill="{couleur}">{nom}</text>')

    note = (
        f"Event: {evenement or 'undeclared'} · points shown only where at least "
        f"{EFFECTIF_MINIMAL} decisions back them"
    )
    if absents:
        note += " · not conclusive for: " + ", ".join(absents)
    a(f'<text class="ink2" x="{L}" y="{H - 14}" font-size="11">{note}</text>')

    a("</svg>")
    return "".join(o)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run", type=Path, help="répertoire du run (contenant moves.csv)")
    p.add_argument("--mode", required=True, choices=sorted(COLONNE_PROBA),
                   help="le mode visé par l'événement")
    p.add_argument("-o", "--sortie", type=Path,
                   default=RACINE / "docs" / "paper" / "figures" / "figure_evenement.svg")
    args = p.parse_args()

    moyennes, effectifs, evenement = series(args.run, args.mode)
    for role, nom, _ in ROLES:
        total = sum((effectifs.get(role) or {}).values())
        retenus = len(moyennes.get(role) or {})
        print(f"  {nom:28s} {total:5d} décision(s), {retenus} jour(s) au-dessus du seuil")

    svg = composer(moyennes, effectifs, args.mode, evenement)
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    args.sortie.write_text(svg, encoding="utf-8")
    try:
        from scripts.analysis.figures_versionnees import signaler

        signaler([args.sortie])
    except Exception:  # noqa: BLE001 — l'avertissement ne fait jamais échouer une figure
        pass
    print(f"✅ {args.sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
