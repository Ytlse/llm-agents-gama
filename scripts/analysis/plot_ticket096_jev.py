#!/usr/bin/env python3
"""Ticket 096, lot 2 — Jev (TypeSafe) face aux treize décideurs du chapitre 6.

Deux panneaux, lus dans les `scores.json` du dépôt, aucun chiffre écrit à la main :

* à gauche, l'axe du composite EMD–JSD, les quinze décideurs rangés, la bande de
  résolution de cohorte (±1,3 point) tracée pour dire quels écarts se lisent ;
* à droite, les parts modales de chaque famille face à la cible EMC², parce que le
  composite seul ne dit pas *par où* un décideur se trompe.

**Ce script ne touche PAS aux figures de l'article.** `plot_chapitre6.py` reste à treize
décideurs : y ajouter Jev changerait `ch6_echelle` sans que le texte qui la commente bouge,
et `docs/paper/article/` est sous verrou. L'intégration au chapitre 6 est une décision de
l'auteur, pas un effet de bord de ce script.

**Figure en anglais**, comme toutes celles du manuscrit.

Usage :
    services/llm-agents/.venv/bin/python scripts/analysis/plot_ticket096_jev.py \
        --sortie docs/traces/<horodatage>_ticket096_lot2
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
from matplotlib.patches import Patch

RACINE = Path(__file__).resolve().parents[2]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

logger = logging.getLogger("ticket096")
DOSSIER = RACINE / "data" / "experiences"
SUFFIXE = "_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN"

# Résolution de cohorte, ticket 080 § 0.3 : deux scores plus proches que cela ne se
# départagent pas sur cette figure.
RESOLUTION = 1.3

PLANCHER, MINIMAL, EXPERT, TABULAIRE, JEV = "plancher", "minimal", "expert", "tabulaire", "jev"
COULEURS = {
    PLANCHER: "#8d8b86",
    MINIMAL: "#eb6834",
    EXPERT: "#2a78d6",
    TABULAIRE: "#1baf7a",
    JEV: "#9b51e0",
}
LIBELLES = {
    PLANCHER: "Baselines (no behavioural information)",
    MINIMAL: "Language models, minimal prompt",
    EXPERT: "Language models, expert prompt",
    TABULAIRE: "Tabular methods fitted on the survey",
    JEV: "Typed zero-shot classifier (Jev 1.13)",
}

DECIDEURS = [
    ("Uniform random", PLANCHER, f"exp_alea{SUFFIXE}_c_nosim"),
    ("All-car", PLANCHER, f"exp_majvoiture{SUFFIXE}_c_nosim"),
    ("Shortest duration", PLANCHER, f"exp_durmin{SUFFIXE}_c_nosim"),
    ("Mistral Large, min.", MINIMAL, f"exp_mistral-l-25_promin02{SUFFIXE}_c_t0_nosim"),
    ("Gemini 3.1 FL, min.", MINIMAL, f"exp_gemini-31-fl_promin02{SUFFIXE}_c_t0_nosim"),
    ("Gemini 3.5 FL, min.", MINIMAL, f"exp_gemini-35-fl_promin02{SUFFIXE}_c_t0_nosim"),
    ("Gemini 3.1 FL, exp.", EXPERT, f"exp_gemini-31-fl_proexp05{SUFFIXE}_c_t0_nosim"),
    ("Mistral Large, exp.", EXPERT, f"exp_mistral-l-25_proexp05{SUFFIXE}_c_t0_nosim"),
    ("Gemini 3.5 FL, exp.", EXPERT, f"exp_gemini-35-fl_proexp05{SUFFIXE}_c_t0_nosim"),
    ("Jev 1.13, min.", JEV, f"exp_jev-1130_promin02{SUFFIXE}_c_nosim"),
    ("Jev 1.13, exp.", JEV, f"exp_jev-1130_proexp05{SUFFIXE}_c_nosim"),
    ("Multinomial logit", TABULAIRE, f"exp_mnl{SUFFIXE}_c_nosim"),
    ("Random forest", TABULAIRE, f"exp_rf{SUFFIXE}_c_nosim"),
    ("Kernel logistic regr.", TABULAIRE, f"exp_klr{SUFFIXE}_c_nosim"),
    ("Gradient boosting", TABULAIRE, f"exp_lgbm{SUFFIXE}_c_nosim"),
]

MODES = ["marche", "velo", "transports_collectifs", "voiture"]
MODES_EN = ["Walking", "Cycling", "Public transport", "Car"]
COULEURS_MODES = {"marche": "cyan", "velo": "purple", "transports_collectifs": "green", "voiture": "red"}


def dernier_score(experience: str) -> dict | None:
    dossier = DOSSIER / experience / "executions"
    if not dossier.is_dir():
        return None
    for execution in sorted(dossier.iterdir(), reverse=True):
        fichier = execution / "scores.json"
        if not fichier.is_file():
            continue
        try:
            donnees = json.loads(fichier.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            logger.error("scores.json illisible (%s / %s) : %s", experience, execution.name, e)
            continue
        donnees["_execution"] = execution.name
        return donnees
    return None


def lire() -> list[dict]:
    lus, manquants = [], []
    for label, groupe, exp in DECIDEURS:
        score = dernier_score(exp)
        if score is None:
            # Un décideur absent se DIT, il ne disparaît pas de la figure en silence.
            logger.error("[ALARME] aucun score pour %s (%s) — absent de la figure", label, exp)
            manquants.append(label)
            continue
        lus.append({
            "label": label,
            "groupe": groupe,
            "composite": score["composite"]["emd_jsd"],
            "l1": score["global"]["l1"],
            "actual": score["global"]["actual"],
            "target": score["global"]["target"],
            "execution": score["_execution"],
        })
    logger.info("Décideurs lus : %d sur %d%s", len(lus), len(DECIDEURS),
                f" — MANQUANTS : {', '.join(manquants)}" if manquants else "")
    return lus


def figure(decideurs: list[dict], sortie: Path) -> Path:
    ordre = sorted(decideurs, key=lambda d: d["composite"])
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.5, 6.4),
                                   gridspec_kw={"width_ratios": [1.25, 1]})

    # ── panneau gauche : l'axe du composite ──────────────────────────────────
    y = range(len(ordre))
    ax1.barh(list(y), [d["composite"] for d in ordre],
             color=[COULEURS[d["groupe"]] for d in ordre],
             edgecolor="black", linewidth=.5, height=.68)
    meilleur = ordre[0]["composite"]
    ax1.axvspan(meilleur, meilleur + RESOLUTION, color="0.85", alpha=.55, zorder=0)
    for i, d in enumerate(ordre):
        ax1.text(d["composite"] + .6, i, f"{d['composite']:.2f}", va="center", fontsize=8.5)
    ax1.set_yticks(list(y))
    ax1.set_yticklabels([d["label"] for d in ordre], fontsize=9)
    ax1.invert_yaxis()
    ax1.set_xlabel("EMD–JSD composite (lower is better)")
    ax1.set_xlim(0, max(d["composite"] for d in ordre) * 1.14)
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.set_title("Fifteen deciders on the same frozen set\n"
                  "(grey band: what another cohort would move, ±1.3)", fontsize=10.5)
    ax1.legend(handles=[Patch(facecolor=COULEURS[g], edgecolor="black", label=LIBELLES[g])
                        for g in (PLANCHER, MINIMAL, EXPERT, JEV, TABULAIRE)],
               fontsize=8, frameon=False, loc="center right",
               bbox_to_anchor=(1.0, .62))

    # ── panneau droit : par où chaque famille se trompe ──────────────────────
    familles = [
        ("EMC² target", None),
        ("All-car", "All-car"),
        ("Gemini 3.5 FL, exp.", "Gemini 3.5 FL, exp."),
        ("Jev 1.13, exp.", "Jev 1.13, exp."),
        ("Gradient boosting", "Gradient boosting"),
    ]
    par_label = {d["label"]: d for d in decideurs}
    # Une seule passe : nom, valeurs et L1 voyagent ensemble. Les construire séparément
    # désalignait la légende dès qu'un décideur manquait — le cas exact d'un rejeu non abouti.
    series: list[tuple[str, list[float], float | None]] = []
    for nom, cle in familles:
        if cle is None:
            if decideurs:
                series.append((nom, [decideurs[0]["target"].get(m, 0.0) for m in MODES], None))
            continue
        d = par_label.get(cle)
        if d is None:
            logger.warning("panneau droit : %s absent, série omise", nom)
            continue
        series.append((nom, [d["actual"].get(m, 0.0) for m in MODES], d["l1"]))

    n = len(series)
    h = .8 / max(n, 1)
    yy = range(len(MODES))
    hachures = ["", "..", "", "///", "xx"][:n]
    for i, (nom, vals, _) in enumerate(series):
        ax2.barh([v + (n / 2 - i - .5) * h for v in yy], vals, h,
                 color=[COULEURS_MODES[m] for m in MODES],
                 edgecolor="black", linewidth=.5,
                 alpha=1.0 if i == 0 else .55, hatch=hachures[i])
    ax2.set_yticks(list(yy))
    ax2.set_yticklabels(MODES_EN, fontsize=9)
    ax2.set_xlabel("Modal share (%)")
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.set_title("Where each family misses\n(global shares, whole day)", fontsize=10.5)
    ax2.legend(handles=[Patch(facecolor="0.7", edgecolor="black",
                              alpha=1.0 if i == 0 else .55, hatch=hachures[i],
                              label=nom if l1 is None else f"{nom}   L1 = {l1:.2f}")
                        for i, (nom, _, l1) in enumerate(series)],
               fontsize=8, frameon=False, loc="lower right")

    fig.suptitle("Ticket 096 — Jev 1.13 (TypeSafe) replayed on the frozen AAMAS v6 set "
                 "(population_1000_AAMAS_v6_20260316_EN_c)", fontsize=12, y=.99)
    fig.tight_layout()
    sortie.mkdir(parents=True, exist_ok=True)
    chemin = sortie / "ticket096_jev_vs_treize.png"
    fig.savefig(chemin, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return chemin


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sortie", default=str(RACINE / "docs" / "traces" / "ticket096_lot2"))
    a = ap.parse_args()
    decideurs = lire()
    if not decideurs:
        logger.error("[ALARME] aucun score lu — rien à tracer")
        return 1
    chemin = figure(decideurs, Path(a.sortie))
    print(f"figure écrite : {chemin}")
    for d in sorted(decideurs, key=lambda x: x["composite"]):
        print(f"  {d['label']:<24} composite {d['composite']:6.2f}   L1 {d['l1']:6.2f}   "
              f"({d['execution']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
