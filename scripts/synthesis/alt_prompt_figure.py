"""Les camemberts d'un ajout de prompt : avant / après, sur le périmètre demandé.

    python -m scripts.synthesis.alt_prompt_figure --variant 1                # population entière
    python -m scripts.synthesis.alt_prompt_figure --variant 1 --scope subset # sous-jeu rejoué seul
    python -m scripts.synthesis.alt_prompt_figure --variant 1 --scope both   # les deux étages

**Ce que la figure montre.** Deux anneaux côte à côte — le run sous son prompt de
production, puis le même run dont 495 décisions ont été rejouées sous prompt modifié.

**Deux périmètres, deux amplitudes.** Sur la POPULATION ENTIÈRE (2 911 décisions), l'ajout
déplace au plus 1,7 point : il ne touche que 495 décisions, et l'agrégat dilue son effet
d'un facteur six. Sur le SOUS-JEU rejoué, le même ajout déplace 9,9 points de transport
collectif. Les deux lectures sont vraies ; `--scope both` les empile pour que la dilution
se voie en même temps que l'effet. Quel que soit le périmètre, il est nommé sur la figure —
un camembert de sous-jeu qu'on lirait comme une part modale de ville serait un contresens.

**D'où viennent les chiffres.** Des pages déjà générées par ``alt_prompt_replay render``,
lues et non recopiées : la figure ne peut pas diverger de la page dont elle dérive. Si la
page est régénérée, relancer ce script suffit.
"""
from __future__ import annotations

import argparse
import logging
import math
import re
import sys
import time
from html import unescape
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch  # noqa: E402

from .alt_prompt_variants import VARIANTS_BY_ID  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
PAGES = REPO_ROOT / "docs" / "synthesis"
OUT_DIR = REPO_ROOT / "docs" / "synthesis" / "figures"

# Palette officielle du projet (cf. .claude/CLAUDE.md) : voiture rouge, vélo violet,
# transports collectifs vert, marche cyan. Les teintes sont assombries pour rester
# lisibles sur fond blanc et à l'impression — les noms bruts (« red », « cyan ») sont
# faits pour le fond noir de GAMA, pas pour une figure d'article.
MODES = ["Marche", "Voiture", "Vélo", "Transports collectifs"]
COLORS = {
    "Marche": "#00A5B5",
    "Voiture": "#D6322B",
    "Vélo": "#7B4FBF",
    "Transports collectifs": "#2E9E5B",
}

SCOPES = ("global", "subset", "both")
# Suffixe de fichier par périmètre. `global` n'en porte pas : c'est la figure de
# référence, celle que la documentation et le changelog nomment.
SUFFIX = {"global": "", "subset": "_sousjeu", "both": "_les_deux"}

logger = logging.getLogger("alt_prompt_figure")


# ── Lecture des chiffres dans la page ────────────────────────────────────────

def _cells(row_html: str) -> list[str]:
    return [unescape(re.sub(r"<[^>]+>", "", c)).strip()
            for c in re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)]


def _table_after(text: str, heading: str) -> dict[str, list[float]]:
    """Renvoie {mode: [colonnes numériques]} pour le premier tableau suivant `heading`."""
    start = text.find(heading)
    if start < 0:
        raise SystemExit(f"Titre introuvable dans la page : {heading!r}")
    m = re.search(r"<tbody>(.*?)</tbody>", text[start:], re.S)
    if not m:
        raise SystemExit(f"Aucun tableau après {heading!r}")
    out: dict[str, list[float]] = {}
    for row in re.findall(r"<tr>(.*?)</tr>", m.group(1), re.S):
        cells = _cells(row)
        if len(cells) < 3:
            continue
        out[cells[0]] = [float(c.replace("+", "").replace("−", "-")) for c in cells[1:]]
    missing = [mode for mode in MODES if mode not in out]
    if missing:
        raise SystemExit(f"Modes absents du tableau {heading!r} : {missing}")
    return out


def read_page(variant: int) -> dict:
    page = PAGES / f"detail_simulation_26_08_alternative{variant}.html"
    if not page.exists():
        raise SystemExit(
            f"Page absente : {page.relative_to(REPO_ROOT)}\n"
            f"Le bras V{variant} n'a pas été rejoué. `make alt-prompt-replay` puis "
            f"`make alt-prompt-pages` la produisent."
        )
    text = page.read_text(encoding="utf-8")
    glob = _table_after(text, "Parts modales globales")
    sub = _table_after(text, "Effet sur le sous-jeu seul")
    replayed = re.search(r"(\d+)\s*lignes remplacées", text)
    kept = re.search(r"(\d+)\s*inchangées", text)
    logger.info(
        "Page lue : %s (%d octets) — global %s, sous-jeu %s",
        page.name, len(text),
        {m: glob[m][:2] for m in MODES}, {m: sub[m][:2] for m in MODES},
    )
    return {
        "page": page,
        # Les Δ sont LUS dans la colonne de la page, jamais recalculés depuis les
        # valeurs arrondies : 6,7 → 8,3 donnerait +1,6 là où la page publie +1,7,
        # et deux documents du même dossier se contrediraient d'un dixième.
        "global": {"before": [glob[m][0] for m in MODES],
                   "after": [glob[m][1] for m in MODES],
                   "delta": [glob[m][2] for m in MODES]},
        "subset": {"before": [sub[m][0] for m in MODES],
                   "after": [sub[m][1] for m in MODES],
                   "delta": [sub[m][2] for m in MODES]},
        "n_replayed": int(replayed.group(1)) if replayed else 0,
        "n_kept": int(kept.group(1)) if kept else 0,
    }


# ── Dessin ───────────────────────────────────────────────────────────────────

def _donut(ax, values: list[float], *, label_size: float, ring: float) -> None:
    """Un anneau. Les secteurs sont proportionnels, mais l'étiquette porte la valeur
    PUBLIÉE et non la valeur renormalisée : les parts arrondies au dixième somment à
    100,1 sur le sous-jeu, et renormaliser afficherait 75,3 là où la page dit 75,4."""
    wedges, _ = ax.pie(
        values,
        colors=[COLORS[m] for m in MODES],
        startangle=90,
        counterclock=False,
        wedgeprops=dict(width=ring, edgecolor="white", linewidth=2.4),
    )
    total = sum(values)
    for wedge, mode, value in zip(wedges, MODES, values):
        rad = math.radians((wedge.theta1 + wedge.theta2) / 2)
        r = 1 - ring / 2
        if 100 * value / total < 4.0:  # secteur trop mince pour porter son chiffre
            ax.annotate(
                f"{value:.1f}",
                xy=(0.98 * r * math.cos(rad), 0.98 * r * math.sin(rad)),
                xytext=(1.28 * math.cos(rad), 1.28 * math.sin(rad)),
                ha="center", va="center", fontsize=label_size - 2, fontweight="bold",
                color=COLORS[mode],
                arrowprops=dict(arrowstyle="-", lw=0.9, color=COLORS[mode]),
            )
        else:
            ax.text(r * math.cos(rad), r * math.sin(rad), f"{value:.1f}",
                    ha="center", va="center", fontsize=label_size, fontweight="bold",
                    color="white")
    ax.set_aspect("equal")


def _delta_lines(deltas: list[float]) -> list[tuple[str, float]]:
    """Les écarts qui valent d'être lus, du plus grand au plus petit."""
    named = [("TC" if m == "Transports collectifs" else m, d)
             for m, d in zip(MODES, deltas)]
    return sorted(named, key=lambda kv: -abs(kv[1]))


def _rows(data: dict, scope: str) -> list[tuple[str, str, dict]]:
    """Les étages à dessiner, de haut en bas : (titre, sous-titre, séries)."""
    n_all = data["n_replayed"] + data["n_kept"]
    catalogue = {
        "global": ("Population entière",
                   f"les {n_all} décisions du run\n"
                   f"({data['n_replayed']} rejouées,\n{data['n_kept']} inchangées)",
                   data["global"]),
        "subset": ("Sous-jeu rejoué",
                   f"les {data['n_replayed']} décisions où\nle modèle a pris le TC\n"
                   "alors que la marche\nlui était proposée",
                   data["subset"]),
    }
    keys = ["global", "subset"] if scope == "both" else [scope]
    return [catalogue[k] for k in keys]


def build(data: dict, variant: int, scope: str, out: Path) -> Path:
    started = time.time()
    meta = VARIANTS_BY_ID.get(variant, {})
    rows = _rows(data, scope)
    single = len(rows) == 1

    # Une seule rangée : les anneaux prennent la place rendue par l'étage supprimé.
    if single:
        fig = plt.figure(figsize=(11.6, 7.4), dpi=200)
        gs_box = dict(left=0.245, right=0.965, top=0.782, bottom=0.245)
        y_sub1, y_sub2, y_head = 0.948, 0.906, 0.828
        y_legend, y_lede, y_note = 0.170, 0.118, 0.072
        ring, label_size = 0.44, 13.0
    else:
        fig = plt.figure(figsize=(12.0, 10.6), dpi=200)
        gs_box = dict(left=0.235, right=0.965, top=0.842, bottom=0.175)
        y_sub1, y_sub2, y_head = 0.962, 0.930, 0.874
        y_legend, y_lede, y_note = 0.118, 0.086, 0.050
        ring, label_size = 0.40, 11.5

    gs = fig.add_gridspec(len(rows), 2, hspace=0.16, wspace=0.02, **gs_box)
    fig.patch.set_facecolor("white")
    axes = [[fig.add_subplot(gs[r, c]) for c in range(2)] for r in range(len(rows))]

    for ax_row, (_, _, series) in zip(axes, rows):
        _donut(ax_row[0], series["before"], label_size=label_size, ring=ring)
        _donut(ax_row[1], series["after"], label_size=label_size, ring=ring)

    # ── Titres ───────────────────────────────────────────────────────────────
    # Pas de titre général : la figure est destinée à un document qui pose lui-même
    # ce qu'elle montre. Reste l'identification de la variante, sans quoi deux
    # figures de la campagne seraient indiscernables l'une de l'autre.
    fig.text(0.5, y_sub1,
             f"Variante V{variant} — {meta.get('heading', 'ajout au prompt système')}",
             ha="center", va="top", fontsize=14, fontweight="bold", color="#111")
    fig.text(0.5, y_sub2,
             "Run du 2026-03-16 · rejeu sous gemini-3.5-flash-lite, température 0 · "
             "parts en % de la masse de probabilité",
             ha="center", va="top", fontsize=9.5, color="#888")

    for col, label in ((0, "Prompt du run"), (1, f"Prompt du run  +  ajout V{variant}")):
        box = axes[0][col].get_position()
        fig.text(box.x0 + box.width / 2, y_head, label, ha="center", va="center",
                 fontsize=13, fontweight="bold" if col else "normal", color="#111")

    # ── Bandeau de gauche : ce que l'étage mesure, et ce que l'ajout y déplace ─
    for ax_row, (label, detail, series) in zip(axes, rows):
        top = ax_row[0].get_position().y1
        # À un seul étage, le titre de la figure nomme déjà le périmètre : le
        # répéter dans le bandeau ne fait qu'occuper la place du détail.
        if not single:
            fig.text(0.022, top - 0.012, label, fontsize=14, fontweight="bold",
                     color="#111", va="top")
        fig.text(0.022, top - (0.012 if single else 0.055), detail, fontsize=9.5,
                 color="#777", va="top", linespacing=1.6)
        base = top - (0.300 if single else 0.175)
        fig.text(0.022, base, "ce que l'ajout déplace", fontsize=8.5, color="#aaa",
                 va="top")
        for i, (name, delta) in enumerate(_delta_lines(series["delta"])):
            fig.text(0.022, base - 0.030 - i * (0.038 if single else 0.026),
                     f"{delta:+5.1f}  {name}", fontsize=10.5, va="top",
                     family="DejaVu Sans Mono",
                     color=COLORS["Transports collectifs"] if name == "TC"
                     else COLORS.get(name, "#444"))

    # Flèche « avant → après », une par étage.
    for ax_row in axes:
        box = ax_row[0].get_position()
        fig.patches.append(FancyArrowPatch(
            (0.598, box.y0 + box.height / 2), (0.630, box.y0 + box.height / 2),
            transform=fig.transFigure, arrowstyle="-|>", mutation_scale=16,
            lw=1.5, color="#c4c4c4", zorder=5))

    handles = [plt.Line2D([], [], marker="o", linestyle="", markersize=11,
                          markerfacecolor=COLORS[m], markeredgecolor="none", label=m)
               for m in MODES]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, y_legend),
               ncol=4, frameon=False, fontsize=11.5, handletextpad=0.5,
               columnspacing=2.4)

    # La phrase de lecture dit ce que le périmètre choisi CACHE : sans elle, la
    # figure « population entière » se lirait comme « le prompt ne fait rien » et
    # celle du sous-jeu comme « le prompt refait la ville ».
    lede = {
        "global": (f"L'ajout n'a été appliqué qu'à {data['n_replayed']} décisions sur "
                   f"{data['n_replayed'] + data['n_kept']} : son effet propre, six fois "
                   "plus ample, se lit sur la figure du sous-jeu."),
        "subset": ("Ces décisions ne sont pas la ville : elles sont les "
                   f"{data['n_replayed']} où l'ajout s'applique, sur "
                   f"{data['n_replayed'] + data['n_kept']}. L'effet sur l'ensemble du "
                   "run est six fois moindre."),
        "both": ("L'ajout n'agit que sur 495 décisions : l'étage du bas montre son "
                 "effet, celui du haut ce qu'il en reste une fois dilué dans le run "
                 "entier."),
    }[scope]
    fig.text(0.5, y_lede, lede, ha="center", va="top", fontsize=10, color="#555",
             style="italic")
    fig.text(0.5, y_note,
             "Deux réserves portées par la page dont ces chiffres sont lus. Le run a "
             "tourné sur quatre fournisseurs quand la variante n'en utilise qu'un : "
             "faute de bras témoin, l'écart mélange l'effet du prompt\net celui du "
             "changement de modèle. Et la simulation n'est pas rejouée : on mesure "
             "l'effet sur la décision, pas ce que la ville en aurait fait ensuite.    "
             "Source : docs/arch/report-marche-tc.md",
             ha="center", va="top", fontsize=8.4, color="#999", linespacing=1.8)

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    try:
        shown = out.relative_to(REPO_ROOT)
    except ValueError:  # --out hors du dépôt
        shown = out
    logger.info("Figure écrite : %s — périmètre %s, %d étage(s), %.0f Ko, %.1f s",
                shown, scope, len(rows), out.stat().st_size / 1024,
                time.time() - started)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", type=int, default=1,
                        help="numéro de la variante rejouée (défaut : 1)")
    parser.add_argument("--scope", choices=SCOPES, default="global",
                        help="périmètre dessiné (défaut : global — la population entière)")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    out = args.out or (OUT_DIR /
                       f"prompt_parts_modales_v{args.variant}{SUFFIX[args.scope]}.png")
    data = read_page(args.variant)
    build(data, args.variant, args.scope, out)
    logger.info("Terminé sans erreur.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
