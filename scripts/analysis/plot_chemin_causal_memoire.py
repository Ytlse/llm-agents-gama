#!/usr/bin/env python3
"""Générateur du schéma causal de la mémoire (Section 6, Contribution C3).

Trace le chemin d'un événement non tabulé jusqu'à la décision :
1. Incident physique & gravité
2. Entrée en mémoire (STM) & Consolidation
3. Filtrage des 4 voies de prompt (1 active, 3 inactives)
4. Infiltration dans le prompt de décision (75 / 376 prompts)
5. Impact comportemental (chute de la propension voiture)
6. Extinction par usure à J+15 sans contradiction.
"""

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

RACINE = Path(__file__).resolve().parents[2]
SORTIE = RACINE / "docs" / "paper" / "figures"
SORTIE.mkdir(parents=True, exist_ok=True)

fig, ax = plt.subplots(figsize=(11.5, 5.8), dpi=200)
ax.set_xlim(0, 115)
ax.set_ylim(0, 58)
ax.axis("off")

# Styles & Couleurs
C_BG_BOX = "#F8FAFC"
C_BORDER = "#CBD5E1"
C_TEXT = "#0F172A"
C_MUTED = "#64748B"
C_SHOCK = "#DC2626"      # Rouge choc
C_ACTIVE = "#2563EB"     # Bleu canal actif
C_INACTIVE = "#94A3B8"   # Gris inactif
C_DECISION = "#D97706"   # Ambre décision
C_RETURN = "#16A34A"     # Vert retour à la normale

# Titre
ax.text(57.5, 55.5, "TRACING AN UN-TABULATED EVENT THROUGH MEMORY TO MODE CHOICE (§ 6)",
        ha="center", va="center", fontsize=12, fontweight="bold", color=C_TEXT, family="sans-serif")
ax.text(57.5, 53.0, "How a single perturbation infiltrates the prompt, changes decisions for 15 days, and decays by wear-out",
        ha="center", va="center", fontsize=9.5, color=C_MUTED, family="sans-serif", style="italic")

# 1. ÉVÉNEMENT PHYSIQUE (COLONNE 1)
rect_inc = patches.FancyBboxPatch((2, 33), 18, 14, boxstyle="round,pad=0.8",
                                  facecolor="#FEF2F2", edgecolor=C_SHOCK, linewidth=1.8)
ax.add_patch(rect_inc)
ax.text(11, 44.5, "1. Un-tabulated Shock", ha="center", va="center", fontsize=9.5, fontweight="bold", color=C_SHOCK)
ax.text(11, 41.5, "March 30 · Engine Failure", ha="center", va="center", fontsize=8.5, fontweight="semibold", color=C_TEXT)
ax.text(11, 38.5, "30-min delay on car trip\nValence: negative\nSeverity: 0.70 (declared)", ha="center", va="center", fontsize=7.5, color=C_MUTED)
ax.text(11, 34.5, "No survey variable carries this", ha="center", va="center", fontsize=7, color=C_SHOCK, style="italic")

# Flèche 1 -> 2
ax.annotate("", xy=(24.5, 40), xytext=(20.5, 40),
            arrowprops=dict(arrowstyle="->", lw=1.8, color=C_MUTED))

# 2. ENTRÉE MÉMOIRE (COLONNE 2)
rect_stm = patches.FancyBboxPatch((25, 33), 18, 14, boxstyle="round,pad=0.8",
                                  facecolor=C_BG_BOX, edgecolor=C_BORDER, linewidth=1.5)
ax.add_patch(rect_stm)
ax.text(34, 44.5, "2. Memory Ingestion", ha="center", va="center", fontsize=9.5, fontweight="bold", color=C_TEXT)
ax.text(34, 41.5, "Short-Term Buffer (STM)", ha="center", va="center", fontsize=8.5, fontweight="semibold", color=C_TEXT)
ax.text(34, 38.0, "Recorded at trip end\nService window computed:\nt_window = 15.29 days", ha="center", va="center", fontsize=7.5, color=C_MUTED)
ax.text(34, 34.5, "Nightly consolidation", ha="center", va="center", fontsize=7.5, color=C_ACTIVE, fontweight="semibold")

# Flèche 2 -> 3
ax.annotate("", xy=(47.5, 40), xytext=(43.5, 40),
            arrowprops=dict(arrowstyle="->", lw=1.8, color=C_MUTED))

# 3. LES 4 VOIES VERS LE PROMPT (COLONNE 3)
rect_voies = patches.FancyBboxPatch((48, 8), 28, 39, boxstyle="round,pad=0.8",
                                    facecolor="#FFFFFF", edgecolor=C_BORDER, linewidth=1.5)
ax.add_patch(rect_voies)
ax.text(62, 44.5, "3. Candidate Pathways to Prompt", ha="center", va="center", fontsize=9.5, fontweight="bold", color=C_TEXT)
ax.text(62, 42.5, "4 mechanisms evaluated in the architecture", ha="center", va="center", fontsize=7.5, color=C_MUTED, style="italic")

# Voie A: ACTIVE
rect_va = patches.FancyBboxPatch((50, 31.5), 24, 8.5, boxstyle="round,pad=0.5",
                                 facecolor="#EFF6FF", edgecolor=C_ACTIVE, linewidth=1.6)
ax.add_patch(rect_va)
ax.text(51, 37.8, "✔ Channel 1: Recent Changes", fontsize=8.5, fontweight="bold", color=C_ACTIVE)
ax.text(51, 35.3, "Active in 75 / 376 decision prompts", fontsize=7.5, fontweight="semibold", color=C_TEXT)
ax.text(51, 33.0, "Window open from March 30 to April 13", fontsize=7, color=C_MUTED)

# Voies B, C, D: INACTIVES
rect_vb = patches.FancyBboxPatch((50, 23.5), 24, 6.5, boxstyle="round,pad=0.5",
                                 facecolor="#F1F5F9", edgecolor=C_INACTIVE, linewidth=1.0)
ax.add_patch(rect_vb)
ax.text(51, 28.0, "✖ Channel 2: Consolidated Belief", fontsize=8, fontweight="semibold", color=C_INACTIVE)
ax.text(51, 25.2, "0 prompts reached (below priority threshold)", fontsize=7, color=C_MUTED)

rect_vc = patches.FancyBboxPatch((50, 15.5), 24, 6.5, boxstyle="round,pad=0.5",
                                 facecolor="#F1F5F9", edgecolor=C_INACTIVE, linewidth=1.0)
ax.add_patch(rect_vc)
ax.text(51, 20.0, "✖ Channel 3: Similarity Retrieval (RAG)", fontsize=8, fontweight="semibold", color=C_INACTIVE)
ax.text(51, 17.2, "0 retrievals triggered for this trip type", fontsize=7, color=C_MUTED)

rect_vd = patches.FancyBboxPatch((50, 9.5), 24, 4.8, boxstyle="round,pad=0.5",
                                 facecolor="#F1F5F9", edgecolor=C_INACTIVE, linewidth=1.0)
ax.add_patch(rect_vd)
ax.text(51, 12.2, "– Channel 4: Household Evening Account", fontsize=7.5, color=C_INACTIVE)
ax.text(51, 10.3, "Not exercised (single-agent setup)", fontsize=6.8, color=C_MUTED, style="italic")

# Flèche Voie A -> 4
ax.annotate("", xy=(80.5, 35.8), xytext=(74.5, 35.8),
            arrowprops=dict(arrowstyle="->", lw=2.2, color=C_ACTIVE))

# 4. IMPACT DÉCISIONNEL (COLONNE 4)
rect_dec = patches.FancyBboxPatch((81, 26), 31, 21, boxstyle="round,pad=0.8",
                                  facecolor="#FFFBEB", edgecolor=C_DECISION, linewidth=1.8)
ax.add_patch(rect_dec)
ax.text(96.5, 44.5, "4. Behavioral Impact (§ 6.4)", ha="center", va="center", fontsize=9.5, fontweight="bold", color=C_DECISION)
ax.text(96.5, 41.5, "Car offered every morning (unconstrained)", ha="center", va="center", fontsize=8, color=C_TEXT)

# Sous-boîtes stats
ax.text(83, 38.0, "• Daily propensity :", fontsize=8, fontweight="bold", color=C_TEXT)
ax.text(100, 38.0, "90% → 40% (day of event)", fontsize=8, color=C_SHOCK, fontweight="semibold")
ax.text(83, 35.2, "• 15-day range :", fontsize=8, fontweight="bold", color=C_TEXT)
ax.text(100, 35.2, "5% to 52% (vs 65–90% control)", fontsize=8, color=C_DECISION)
ax.text(83, 32.4, "• Car taken if offered :", fontsize=8, fontweight="bold", color=C_TEXT)
ax.text(100, 32.4, "94% (34/36) → 32% (12/38)", fontsize=8, color=C_SHOCK, fontweight="semibold")
ax.text(83, 29.6, "• Stated safety rating :", fontsize=8, fontweight="bold", color=C_TEXT)
ax.text(100, 29.6, "8 / 10 → 3 / 10 (ecology stays 3/10)", fontsize=7.8, color=C_MUTED)

# 5. EXTINCTION PAR USURE (BAS DROITE)
rect_ext = patches.FancyBboxPatch((81, 8), 31, 15, boxstyle="round,pad=0.8",
                                  facecolor="#F0FDF4", edgecolor=C_RETURN, linewidth=1.6)
ax.add_patch(rect_ext)
ax.text(96.5, 20.5, "5. Decay by Wear-Out, Not Contradiction", ha="center", va="center", fontsize=9, fontweight="bold", color=C_RETURN)
ax.text(96.5, 17.5, "April 13 : Text leaves prompts (15 days elapsed)", ha="center", va="center", fontsize=7.8, color=C_TEXT)
ax.text(96.5, 14.8, "April 15 : Propensity re-enters control band (88%)", ha="center", va="center", fontsize=7.8, color=C_RETURN, fontweight="semibold")
ax.text(96.5, 12.0, "12 car rides taken during shock with ZERO belief contradiction", ha="center", va="center", fontsize=7.2, color=C_MUTED)
ax.text(96.5, 9.8, "Dates confirmed across 2 independent sources (prompt text & probabilities)", ha="center", va="center", fontsize=6.8, color=C_MUTED, style="italic")

# Flèche de 4 vers 5
ax.annotate("", xy=(96.5, 23.5), xytext=(96.5, 25.5),
            arrowprops=dict(arrowstyle="->", lw=1.6, color=C_RETURN))

plt.tight_layout()
fig.savefig(SORTIE / "schema_chemin_causal_memoire.png", dpi=250, bbox_inches="tight")
fig.savefig(SORTIE / "schema_chemin_causal_memoire.svg", bbox_inches="tight")
plt.close(fig)
print("OK: schema_chemin_causal_memoire.png et .svg générés avec succès dans", SORTIE)
