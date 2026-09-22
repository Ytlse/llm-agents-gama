#!/usr/bin/env python3
"""Les deux figures de l'audit unitaire du ticket 058, lues dans sa sortie JSON.

L'audit confronte neuf décideurs au mode déclaré, déplacement par déplacement, sur les
journées réellement décrites par les enquêtés. Deux de ses énoncés ne se lisent pas dans un
chiffre unique, et le § 6.4 les porte en figures (6.5 et 6.6) ; les tableaux complets,
neuf décideurs et matrice de confusion, vivent à l'annexe I :

* ``ch6_audit_distance`` — l'exactitude par tranche de distance. Elle établit que tout
  l'écart entre décideurs se joue sous 2 km, et qu'au-delà de 10 km le plancher « toujours
  la voiture » rejoint le plafond tabulaire ;
* ``ch6_audit_modes`` — le rappel et la précision par mode. Ils disent par quoi l'écart
  d'exactitude est payé : les paliers rappellent le vélo mieux que toute méthode tabulaire
  et perdent la marche.

**Les figures sont en anglais**, comme toutes celles du manuscrit.

Aucun chiffre n'est écrit à la main. Le JSON d'entrée est celui de
`scripts/progedo_logit/audit_unitaire_058.py --sortie` ; s'il manque, ce script relance
l'audit, qui relit les exécutions archivées sans un appel de modèle.

Usage :
    services/llm-agents/.venv/bin/python scripts/analysis/plot_audit_unitaire.py
    … --sortie docs/paper/figures --copie docs/paper/article/images
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

RACINE = Path(__file__).resolve().parents[2]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from scripts.analysis.figures_versionnees import signaler

logger = logging.getLogger("audit058")

AUDIT = RACINE / "scripts" / "progedo_logit" / "audit_unitaire_058.py"
PYTHON = RACINE / "services" / "llm-agents" / ".venv" / "bin" / "python"
JSON_DEFAUT = (RACINE / "docs" / "traces" / "2026-09-21_08-52_ticket058_audit_unitaire"
               / "audit_unitaire_058.json")
SORTIE_DEFAUT = RACINE / "docs" / "paper" / "figures"
COPIE_DEFAUT = RACINE / "docs" / "paper" / "article" / "images"

# Décision de l'auteur du 2026-09-22 : la planche ne porte plus que le plafond tabulaire et le
# prompt expert de chaque porteur audité. Les prompts minimaux et le plancher tout-voiture en
# sortent — ils restent aux tableaux de l'annexe I, et la planche qui les exploitait, l'accord
# unitaire par tranche de distance, a quitté le chapitre le même jour.
DECIDEURS = [
    ("lgbm", "Gradient boosting (LightGBM)", "#1baf7a", "-", "o"),
    ("gemini-35-fl_proexp05", "Gemini 3.5 Flash-Lite, expert prompt", "#2a78d6", "-", "s"),
]

# Ticket 096 — versés dans DECIDEURS par `--avec-jev` seulement. Sans le drapeau, les deux
# planches restent celles du chapitre de référence, qui n'en cite que quatre.
DECIDEURS_JEV = [
    # prompt_expert_32 est le prompt expert de Jev (décision de l'auteur, 2026-09-22), et c'est
    # le même bras qu'au § 6.1. prompt_expert_05 reste mesuré, il vit aux annexes H.6 et I.
    ("jev-1130_proexp32", "Jev 1.13 (TypeSafe), expert prompt", "#9b51e0", "-", "D"),
]
BANDES = ["0-1km", "1-2km", "2-5km", "5-10km", "10-20km", "20-50km"]
LIBELLES_BANDES = ["0–1 km", "1–2 km", "2–5 km", "5–10 km", "10–20 km", "20–50 km"]
MODES = ["bike", "car", "transit", "walk"]
LIBELLES_MODES = ["Bike", "Car", "Public transport", "Walking"]


def charger(chemin: Path) -> dict:
    """Le JSON de l'audit ; relance l'audit s'il manque, sans un appel de modèle."""
    if not chemin.is_file():
        logger.info("Sortie d'audit absente (%s) — relance de l'audit", chemin)
        chemin.parent.mkdir(parents=True, exist_ok=True)
        depart = time.monotonic()
        issue = subprocess.run(
            [str(PYTHON), str(AUDIT), "--sortie", str(chemin)],
            cwd=RACINE, check=False,
        )
        if issue.returncode != 0 or not chemin.is_file():
            raise SystemExit(f"[ALARME] L'audit a échoué (code {issue.returncode}) : {chemin}")
        logger.info("Audit rejoué en %.1f s", time.monotonic() - depart)
    resultats = json.loads(chemin.read_text(encoding="utf-8"))
    manquants = [c for c, *_ in DECIDEURS if c not in resultats]
    if manquants:
        raise SystemExit(f"[ALARME] Décideur(s) absent(s) de l'audit : {', '.join(manquants)}")
    logger.info("Audit chargé : %d décideurs, %d tracés", len(resultats), len(DECIDEURS))
    return resultats


def figure_distance(resultats: dict, sortie: Path) -> list[Path]:
    figure, axe = plt.subplots(figsize=(7.4, 4.3))
    effectifs = [resultats["lgbm"]["par_bande"][b]["n"] for b in BANDES]
    for cle, libelle, couleur, style, marque in DECIDEURS:
        valeurs = [resultats[cle]["par_bande"][b]["exactitude"] * 100 for b in BANDES]
        axe.plot(range(len(BANDES)), valeurs, style, color=couleur, marker=marque,
                 markersize=4.0, linewidth=1.3, label=libelle, zorder=3)
    axe.set_xticks(range(len(BANDES)))
    axe.set_xticklabels([f"{lib}\nn = {n:,}".replace(",", " ")
                         for lib, n in zip(LIBELLES_BANDES, effectifs)], fontsize=8.5)
    axe.set_ylim(30, 95)
    axe.set_ylabel("Agreement with the declared mode (%)", fontsize=9.5)
    axe.set_title("Unit agreement by trip distance", fontsize=10.5, loc="left")
    axe.grid(axis="y", color="#d8d6d1", linewidth=0.7, zorder=1)
    axe.set_axisbelow(True)
    for bord in ("top", "right"):
        axe.spines[bord].set_visible(False)
    axe.legend(fontsize=8.5, frameon=False, loc="upper left", bbox_to_anchor=(0.0, -0.18), ncol=2)
    return ecrire(figure, sortie, "ch6_audit_distance")


def figure_modes(resultats: dict, sortie: Path) -> list[Path]:
    figure, axes = plt.subplots(1, 2, figsize=(8.6, 3.9), sharey=True)
    traces = [d for d in DECIDEURS if d[0] != "majvoiture"]
    largeur = 0.14
    for axe, grandeur, titre in ((axes[0], "rappel", "Recall"), (axes[1], "precision", "Precision")):
        for rang, (cle, libelle, couleur, _, _) in enumerate(traces):
            valeurs = [resultats[cle]["par_mode"][m][grandeur] * 100 for m in MODES]
            positions = [i + (rang - 1) * largeur for i in range(len(MODES))]
            axe.bar(positions, valeurs, largeur, color=couleur, label=libelle, zorder=3)
        axe.set_xticks(range(len(MODES)))
        axe.set_xticklabels(LIBELLES_MODES, fontsize=8.5)
        axe.set_title(titre, fontsize=10, loc="left", pad=8)
        axe.grid(axis="y", color="#d8d6d1", linewidth=0.7, zorder=1)
        axe.set_axisbelow(True)
        for bord in ("top", "right"):
            axe.spines[bord].set_visible(False)
    axes[0].set_ylabel("%", fontsize=9.5)
    axes[0].set_ylim(0, 90)
    figure.suptitle("Recall and precision by transport mode",
                    fontsize=10.5, x=0.02, y=1.02, ha="left")
    axes[0].legend(fontsize=8.5, frameon=False, loc="upper left",
                   bbox_to_anchor=(0.0, -0.13), ncol=3)
    return ecrire(figure, sortie, "ch6_audit_modes")


def ecrire(figure, sortie: Path, nom: str) -> list[Path]:
    """Écrit la figure en PNG et en SVG, et rend les chemins écrits."""
    sortie.mkdir(parents=True, exist_ok=True)
    ecrits = []
    for extension in ("png", "svg"):
        chemin = sortie / f"{nom}.{extension}"
        figure.savefig(chemin, dpi=200, bbox_inches="tight", facecolor="white")
        ecrits.append(chemin)
    plt.close(figure)
    return ecrits


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--audit", type=Path, default=JSON_DEFAUT)
    analyseur.add_argument("--sortie", type=Path, default=SORTIE_DEFAUT)
    analyseur.add_argument("--copie", type=Path, default=COPIE_DEFAUT)
    analyseur.add_argument("--sans-copie", action="store_true")
    analyseur.add_argument(
        "--avec-jev", action="store_true",
        help="ajoute le prompt expert de Jev 1.13 (ticket 096) aux planches",
    )
    arguments = analyseur.parse_args()
    if arguments.avec_jev:
        DECIDEURS.extend(DECIDEURS_JEV)
        logger.info("Bras Jev versé : %d décideurs tracés", len(DECIDEURS))

    depart = time.monotonic()
    resultats = charger(arguments.audit)
    ecrits = figure_distance(resultats, arguments.sortie)
    ecrits += figure_modes(resultats, arguments.sortie)
    signaler(ecrits)

    copies = 0
    if not arguments.sans_copie:
        arguments.copie.mkdir(parents=True, exist_ok=True)
        for chemin in ecrits:
            (arguments.copie / chemin.name).write_bytes(chemin.read_bytes())
            copies += 1
    logger.info("Terminé en %.1f s : %d fichier(s) écrit(s), %d recopié(s)",
                time.monotonic() - depart, len(ecrits), copies)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
