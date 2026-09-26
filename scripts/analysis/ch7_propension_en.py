#!/usr/bin/env python3
"""Figure 5 de l'article court, en anglais.

POURQUOI CE FICHIER EXISTE. `ch7_choc_figures.py` compose ses figures en français : il sert
l'article long, dont les masters sont français. L'article court se compose en anglais, et la
consigne est asymétrique — une figure anglaise dans la version française ne gêne personne,
une figure française dans la version anglaise se voit. Plutôt que de basculer la langue du
script partagé, qui casserait l'article long, ce module réutilise sa lecture de données et ne
réécrit que les libellés.

Sortie : docs/paper/article-court/overleaf{,-fr}/images/ch7_propension_quotidienne.png
Les deux projets reçoivent la même figure anglaise, par la règle ci-dessus.
"""
import datetime
import statistics
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "scripts/analysis"))
from ch7_choc_figures import CHOC, COULEUR, SORTIE, TEMOIN, TRAITE, propension_par_jour


def figure_propension_en(sorties: list[Path]) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.2))
    for run, nom in ((TEMOIN, "control"), (TRAITE, "exposed")):
        d = propension_par_jour(run)
        jours = [j for j in sorted(d) if d[j]]
        ax.plot(jours, [statistics.mean(d[j]) for j in jours], marker="o", ms=3.5, lw=1.6,
                color=COULEUR["témoin" if nom == "control" else "traité"], label=nom)
    ax.axvline(CHOC, color="#CE3B4B", ls="--", lw=1.2)
    ax.annotate("suspicious noise in car engine", (CHOC, 103), color="#CE3B4B", fontsize=9, ha="center")
    ax.axvline(SORTIE, color="#333", ls=":", lw=1.2)
    ax.annotate("the account leaves the context", (SORTIE, 103), color="#333", fontsize=9,
                ha="center")
    ax.set_ylim(-5, 115)
    ax.set_ylabel("Stated P(car), daily mean (%)")
    ax.set_title("Daily propensity to the car, stated at every decision")
    ax.legend(loc="lower right", frameon=False)
    ax.grid(alpha=.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    for chemin in sorties:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(chemin, format=chemin.suffix.lstrip("."), dpi=200, bbox_inches="tight")
        print(f"écrit : {chemin.relative_to(RACINE)}")
    plt.close(fig)


if __name__ == "__main__":
    base = RACINE / "docs/paper/article-court"
    figure_propension_en([
        base / "overleaf/images/ch7_propension_quotidienne.png",
        base / "overleaf-fr/images/ch7_propension_quotidienne.png",
        RACINE / "docs/paper/figures/ch7_propension_quotidienne_en.png",
    ])
