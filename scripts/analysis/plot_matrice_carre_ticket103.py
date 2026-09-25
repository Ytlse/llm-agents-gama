#!/usr/bin/env python3
"""Générateur de la matrice 2x3 et de la comparaison hors échantillon (Ticket 103 / Section 5.3).

Visualise le carré de croisement 2 modèles x 3 prompts :
- Modèle génératif (Gemini 3.5 Flash Lite) vs Classifieur typé (TypeSafe Jev-1.13.0)
- Prompt Minimal vs Expert Gemini (05) vs Expert Jev (32)
- Bande des références tabulaires [3.60, 4.09]
- Asymétrie des coûts (Facteur 50x)
"""

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

RACINE = Path(__file__).resolve().parents[2]
SORTIE = RACINE / "docs" / "paper" / "figures"
SORTIE.mkdir(parents=True, exist_ok=True)

fig, (ax_mat, ax_cout) = plt.subplots(1, 2, figsize=(11.5, 4.8), gridspec_kw={"width_ratios": [1.6, 1.0]}, dpi=200)

# Couleurs
C_BG = "#FFFFFF"
C_TAB_BAND = "#E2E8F0"
C_TAB_TEXT = "#475569"
C_JEV = "#C2185B"
C_GEMINI = "#1565C0"

# --- PANNEAU 1 : MATRICE 2 x 3 DU CROISEMENT ---
# Données composites (EMD-JSD) :
# Colonnes : Prompt Minimal 02, Expert Gemini 05, Expert Jev 32
# Lignes : Gemini 3.5 Flash Lite, Jev 1.13.0
matrice = np.array([
    [7.02, 4.86, 5.12],   # Gemini 3.5 (c1 / c2 estimate)
    [13.75, 4.35, 3.65]   # Jev 1.13.0 (c1 / c2 estimate)
])

# Affichage heatmap
im = ax_mat.imshow(matrice, cmap="YlGnBu_r", vmin=3.0, vmax=15.0, aspect="auto")

# Labels axes
prompts = [
    "Prompt Minimal 02\n(Factual, no general criteria)",
    "Prompt Expert 05\n(4 criteria, tuned for Gemini)",
    "Prompt Expert 32\n(5 criteria, tuned for Jev)"
]
modeles = [
    "Gemini 3.5 Flash Lite\n(Generative LLM with CoT)",
    "TypeSafe Jev-1.13.0\n(Typed Classifier, no text)"
]

ax_mat.set_xticks(range(3))
ax_mat.set_xticklabels(prompts, fontsize=8.5, fontweight="semibold")
ax_mat.set_yticks(range(2))
ax_mat.set_yticklabels(modeles, fontsize=8.5, fontweight="semibold")

# Annotations dans les cellules
annotations = [
    [("7.02", "Under physical floor\n(26.97)"), ("4.86", "Out-of-sample\n[4.30 - 4.86]"), ("5.12 [c2]", "Cross-prompt\nevaluation")],
    [("13.75", "Minimal prompt\nperformance"), ("4.35 [c2]", "Transferred instruction\n(out-of-sample)"), ("3.65", "In tabular band\n[3.60 - 4.09]")]
]

for i in range(2):
    for j in range(3):
        val_str, sub_str = annotations[i][j]
        c_text = "white" if matrice[i, j] > 9.0 else "#0F172A"
        ax_mat.text(j, i - 0.12, val_str, ha="center", va="center", fontsize=11, fontweight="bold", color=c_text)
        ax_mat.text(j, i + 0.18, sub_str, ha="center", va="center", fontsize=7.2, color=c_text, alpha=0.9, style="italic")

# Bande tabulaire de référence indiquée sous la matrice
ax_mat.set_title("Cross-over Matrix: 2 Backbone Models × 3 Instructions (EMD–JSD composite)", fontsize=10, fontweight="bold", pad=12)

# Barre de couleur
cbar = fig.colorbar(im, ax=ax_mat, orientation="horizontal", fraction=0.06, pad=0.22)
cbar.set_label("Composite score (lower is closer to survey distribution)", fontsize=8)
cbar.ax.tick_params(labelsize=7.5)

# --- PANNEAU 2 : COMPROMIS PERFORMANCE VS COÛT (§ 5.3 & § 7.1) ---
decideurs = [
    ("Random Floor", 50.16, 0.0, "#94A3B8", "x"),
    ("Min Duration", 26.97, 0.0, "#94A3B8", "x"),
    ("Tabular (LightGBM)", 3.60, 0.01, "#475569", "D"),
    ("Tabular (Multinomial Logit)", 4.02, 0.01, "#475569", "D"),
    ("Gemini 3.5 (Minimal)", 7.02, 31.50, C_GEMINI, "o"),
    ("Gemini 3.5 (Expert)", 4.86, 49.28, C_GEMINI, "o"),
    ("Jev 1.13.0 (Minimal)", 13.75, 1.06, C_JEV, "s"),
    ("Jev 1.13.0 (Expert)", 3.65, 1.06, C_JEV, "s"),
]

# Zone bande tabulaire
ax_cout.axhspan(3.60, 4.09, color=C_TAB_BAND, alpha=0.7, zorder=1)
ax_cout.text(0.015, 3.85, "Tabular Reference Band [3.60 ; 4.09]", fontsize=7.5, color=C_TAB_TEXT, fontweight="semibold", va="center")

for label, comp, cost, color, marker in decideurs:
    if cost > 0:
        ax_cout.scatter(cost, comp, color=color, s=70, marker=marker, zorder=4, edgecolor="black", linewidth=0.5)
        # Position du texte
        offset_y = 0.5 if "Expert" in label and "Jev" in label else (-0.7 if "LightGBM" in label else 0.4)
        ha = "left" if cost > 10 else ("right" if cost < 1 else "left")
        dx = 1.15 if ha == "left" else 0.85
        ax_cout.annotate(label.replace(" (", "\n("), (cost * dx, comp + offset_y), fontsize=7, color=color, ha=ha)

ax_cout.set_xscale("log")
ax_cout.set_xlim(0.005, 120)
ax_cout.set_ylim(2.5, 16.0)
ax_cout.set_xlabel("Cost per 23,026 decisions in USD (log scale)", fontsize=8.5)
ax_cout.set_ylabel("Composite EMD–JSD (lower is better)", fontsize=8.5)
ax_cout.set_title("The 50× Cost Disruption of Typed Classifier", fontsize=10, fontweight="bold")
ax_cout.grid(True, which="both", ls="--", lw=0.4, alpha=0.5)

# Annotation facteur 50
ax_cout.annotate("Factor ~50× cheaper\nat equal fidelity",
                 xy=(1.06, 3.65), xytext=(4.0, 1.8),
                 arrowprops=dict(arrowstyle="->", color=C_JEV, lw=1.2),
                 fontsize=7.8, fontweight="bold", color=C_JEV)

plt.tight_layout()
fig.savefig(SORTIE / "matrice_carre_ticket103.png", dpi=250, bbox_inches="tight")
fig.savefig(SORTIE / "matrice_carre_ticket103.svg", bbox_inches="tight")
plt.close(fig)
print("OK: matrice_carre_ticket103.png et .svg générés avec succès dans", SORTIE)
