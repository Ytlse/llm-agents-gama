#!/usr/bin/env python3
"""Ticket 103 — le carré Jev × Gemini hors échantillon, et les graines.

Deux panneaux, lus dans les `scores.json` du dépôt, **aucun chiffre écrit à la main** :

* à gauche, l'échelle de chaque cohorte côte à côte. Les deux bandes tabulaires ne se
  superposent pas (c1 [3,60 ; 3,71+], c2 plus basse d'environ un point), et c'est tout
  l'intérêt du panneau : il montre pourquoi un score c2 ne se lit QUE contre la bande c2.
  La zone grisée est la bande des quatre références tabulaires de la cohorte ;
* à droite, la dispersion inter-graines : l'écart de chaque graine à la moyenne de son
  bras, contre la bande de résolution de cohorte (±1,3 point) centrée sur zéro. Tracer
  les composites bruts contre une bande partant de zéro serait un contresens — ±1,3 est
  une incertitude autour d'une valeur, pas un intervalle absolu.

**Ce script ne touche PAS aux figures de l'article** : `docs/paper/article/` est sous verrou,
et l'intégration de ces résultats est une décision de l'auteur, pas un effet de bord.

Un bras non encore mesuré est simplement absent de la figure, sans faire échouer le tracé :
les phases du ticket se jouent dans l'ordre et la figure doit se régénérer entre deux.

**Figure en anglais**, comme toutes celles du manuscrit.

Usage :
    services/llm-agents/.venv/bin/python scripts/analysis/plot_ticket103_hors_echantillon.py \
        --sortie docs/traces/<horodatage>_ticket103
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

RACINE = Path(__file__).resolve().parents[2]
EXPS = RACINE / "data" / "experiences"

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
logger = logging.getLogger("ticket103")

C1 = "_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c"
C2 = "_jtir_pop-1000_AAMAS_v6_c2_jeu-20260316_EN_c"

# Palette officielle du dépôt pour les familles de décideurs de cette figure.
COUL = {"tabular": "#4C4C4C", "jev": "#C2185B", "gemini": "#1565C0", "floor": "#9E9E9E"}


def composite(nom: str) -> float | None:
    """Le composite EMD–JSD de la DERNIÈRE exécution scorée de ce bras, ou None.

    None n'est pas une erreur : un bras des phases à venir n'a pas encore de score, et la
    figure doit pouvoir se régénérer entre deux phases.
    """
    fichiers = sorted((EXPS / nom).glob("executions/*/scores.json"))
    if not fichiers:
        logger.info("[figure] %s : aucun score, bras omis", nom)
        return None

    def trouver(o, cle):
        if isinstance(o, dict):
            for a, b in o.items():
                if a == cle:
                    return b
                r = trouver(b, cle)
                if r is not None:
                    return r
        return None

    c = trouver(json.loads(fichiers[-1].read_text(encoding="utf-8")), "composite")
    return None if c is None else float(c["emd_jsd"])


def echelle(suffixe_cohorte: str, t0: str) -> dict:
    """Les bras d'une cohorte : références tabulaires, planchers, Jev, Gemini."""
    tab = {k: composite(f"exp_{k}{suffixe_cohorte}_nosim") for k in ("mnl", "lgbm", "klr", "rf")}
    sols = {
        "Jev · expert 32": composite(f"exp_jev-1130_proexp32{suffixe_cohorte}_nosim"),
        "Jev · expert 05": composite(f"exp_jev-1130_proexp05{suffixe_cohorte}_nosim"),
        "Gemini · expert 32": composite(f"exp_gemini-35-fl_proexp32{suffixe_cohorte}{t0}_nosim"),
        "Gemini · expert 05": composite(f"exp_gemini-35-fl_proexp05{suffixe_cohorte}{t0}_nosim"),
    }
    return {"tabular": {k: v for k, v in tab.items() if v is not None},
            "solveurs": {k: v for k, v in sols.items() if v is not None}}


def panneau_echelles(ax) -> None:
    donnees = {"Cohort c1 (in-sample prompt)": echelle(C1, "_t0"),
               "Cohort c2 (out-of-sample)": echelle(C2, "_t0")}
    for i, (titre, d) in enumerate(donnees.items()):
        if d["tabular"]:
            bas, haut = min(d["tabular"].values()), max(d["tabular"].values())
            ax.fill_between([i - 0.34, i + 0.34], bas, haut, color=COUL["tabular"],
                            alpha=0.16, zorder=1)
            ax.plot([i - 0.34, i + 0.34], [haut, haut], color=COUL["tabular"], lw=1.1, zorder=2)
            ax.annotate(f"tabular band\n[{bas:.2f} ; {haut:.2f}]", (i + 0.36, (bas + haut) / 2),
                        fontsize=7.5, color=COUL["tabular"], va="center")
        for nom, val in d["solveurs"].items():
            c = COUL["jev"] if nom.startswith("Jev") else COUL["gemini"]
            plein = "expert 32" in nom
            ax.scatter([i], [val], s=58, color=c, zorder=4,
                       marker="o" if plein else "s",
                       facecolor=c if plein else "white", edgecolor=c, linewidths=1.4)
            ax.annotate(f"{nom.split(' · ')[0]} {nom.split(' · ')[1]} — {val:.2f}",
                        (i - 0.38, val), fontsize=7.5, color=c, ha="right", va="center")
    ax.set_xticks(range(len(donnees)))
    ax.set_xticklabels([k.replace(" (", "\n(") for k in donnees], fontsize=8.5)
    ax.set_xlim(-1.15, len(donnees) - 0.15)
    ax.set_ylabel("Composite EMD–JSD (lower is better)", fontsize=9)
    ax.set_title("Each cohort has its own scale", fontsize=10, loc="left")
    ax.grid(axis="y", alpha=0.25, lw=0.6)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def panneau_graines(ax) -> None:
    """L'écart de chaque graine à la moyenne de son bras, contre la résolution de cohorte.

    On ne trace PAS les composites bruts ici : la résolution de ±1,3 point est une
    incertitude AUTOUR d'une valeur, pas un intervalle partant de zéro. Tracée en absolu
    elle ferait lire « ce bras est hors de la bande », ce qui n'a aucun sens. Centrer sur
    la moyenne du bras est la seule lecture juste : ce qui compte est l'amplitude du
    déplacement qu'une graine provoque, comparée à ce que la cohorte sait résoudre.
    """
    bras = [
        ("Jev · expert 32", f"exp_jev-1130_proexp32{C1}", "", COUL["jev"]),
        ("Jev · expert 05", f"exp_jev-1130_proexp05{C1}", "", COUL["jev"]),
        ("Gemini · expert 05", f"exp_gemini-35-fl_proexp05{C1}", "_t0", COUL["gemini"]),
    ]
    etiquettes, y = [], 0
    ax.axvspan(-1.3, 1.3, color="#BDBDBD", alpha=0.20, zorder=1)
    ax.axvline(0, color="#757575", lw=0.8, zorder=2)
    for libelle, base, t0, coul in bras:
        vals = []
        for seg in ("", "_go123_gt123_gc123", "_go789_gt789_gc789"):
            v = composite(f"{base}{seg}{t0}_nosim")
            if v is not None:
                vals.append(v)
        if len(vals) < 2:
            continue
        moyenne = sum(vals) / len(vals)
        ecarts = [v - moyenne for v in vals]
        ax.plot([min(ecarts), max(ecarts)], [y, y], color=coul, lw=2.4, alpha=0.45, zorder=3)
        ax.scatter(ecarts, [y] * len(ecarts), s=46, color=coul, zorder=4)
        ax.annotate(f"mean {moyenne:.2f} · range {max(vals) - min(vals):.2f}",
                    (max(ecarts) + 0.05, y), fontsize=7.5, color=coul, va="center")
        etiquettes.append(libelle)
        y += 1
    ax.annotate("cohort resolution ±1.3", (0, len(etiquettes) - 0.55), fontsize=7.5,
                color="#616161", ha="center")
    ax.set_yticks(range(len(etiquettes)))
    ax.set_yticklabels(etiquettes, fontsize=8.5)
    ax.set_ylim(-0.6, max(len(etiquettes) - 0.35, 0.6))
    ax.set_xlim(-1.55, 1.55)
    ax.set_xlabel("Deviation from the arm's mean, three seeds (EMD–JSD points)", fontsize=9)
    ax.set_title("Seed spread stays far inside cohort resolution", fontsize=10, loc="left")
    ax.grid(axis="x", alpha=0.25, lw=0.6)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", required=True, help="dossier de trace où écrire la figure")
    a = ap.parse_args()
    sortie = Path(a.sortie)
    sortie.mkdir(parents=True, exist_ok=True)

    fig, (g, d) = plt.subplots(1, 2, figsize=(11.6, 4.5))
    panneau_echelles(g)
    panneau_graines(d)
    fig.tight_layout()
    for ext in ("png", "svg"):
        chemin = sortie / f"ticket103_hors_echantillon.{ext}"
        fig.savefig(chemin, dpi=170, bbox_inches="tight")
        logger.info("[figure] écrite : %s", chemin)
    plt.close(fig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
