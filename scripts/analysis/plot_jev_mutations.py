#!/usr/bin/env python3
"""Les mutations de prompt du bras Jev, mesurées sur la cohorte scellée (2026-09-21).

Deux panneaux, lus dans les `scores.json` du dépôt, aucun chiffre écrit à la main :

* à gauche, le composite EMD–JSD de chaque consigne, avec **la bande de bruit du témoin** —
  l'écart entre deux exécutions du MÊME prompt à la même graine. Une barre qui ne sort pas
  de cette bande n'a rien mesuré d'autre que le fournisseur ;
* à droite, l'écart L1 par strate, témoin contre mutation, sur les strates qui portaient la
  dérive et sur celles que le témoin traitait déjà bien. C'est le panneau qui compte : le
  composite global dit qu'une mutation gagne, il ne dit pas ce qu'elle casse pour gagner.

**Cette figure ne touche à aucune figure de l'article.** Elle vit dans sa trace, et son
intégration éventuelle au chapitre 6 est une décision de l'auteur.

**Figure en anglais**, comme toutes celles du manuscrit.

Usage :
    services/llm-agents/.venv/bin/python scripts/analysis/plot_jev_mutations.py \
        --sortie docs/traces/2026-09-21_jev_mutations
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
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

logger = logging.getLogger("jev_mutations")
DOSSIER = RACINE / "data" / "experiences"
SUFFIXE = "_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_nosim"

RETENUE, REJETEE, TEMOIN = "retenue", "rejetee", "temoin"
COULEURS = {RETENUE: "#1baf7a", REJETEE: "#eb6834", TEMOIN: "#8d8b86"}

#: Panneau de droite : une teinte par bras. Toutes les mutations rejetées partageant une seule
#: couleur, la légende ne permettait plus de dire laquelle casse quoi — c'est pourtant la seule
#: question que ce panneau est là pour trancher.
TEINTES = {
    "A2": "#1baf7a",
    "A1": "#2a78d6",
    "A4": "#9b51e0",
    "A3": "#d9a21b",
    "B1": "#c0392b",
    "B2": "#eb6834",
}

#: Les deux exécutions du témoin sont désignées par leur horodatage : « la dernière » en
#: choisirait une seule, et c'est justement leur ÉCART qui fait le plancher de bruit.
TEMOIN_1 = f"exp_jev-1130_proexp05{SUFFIXE}/executions/2026-09-21_06_25_29"
TEMOIN_2 = f"exp_jev-1130_proexp05{SUFFIXE}/executions/2026-09-21_09_35_52"

BRAS = [
    ("Expert prompt in service (run 1)", TEMOIN, TEMOIN_1),
    ("Expert prompt in service (run 2)", TEMOIN, TEMOIN_2),
    ("A2 — chain friction, two-sided", RETENUE, f"exp_jev-1130_proexp32{SUFFIXE}"),
    ("A1 — walking effort, added clause", REJETEE, f"exp_jev-1130_proexp31{SUFFIXE}"),
    ("A4 — A2 plus short walk kept", REJETEE, f"exp_jev-1130_proexp36{SUFFIXE}"),
    ("A3 — A4 plus 'only when'", REJETEE, f"exp_jev-1130_proexp35{SUFFIXE}"),
    ("B1 — cost borne by the household", REJETEE, f"exp_jev-1130_proexp33{SUFFIXE}"),
    ("B2 — regularity of a usual trip", REJETEE, f"exp_jev-1130_proexp34{SUFFIXE}"),
]

#: Les strates du panneau de droite : celles qui portaient la dérive, ET celles que le témoin
#: traitait déjà bien. Sans les secondes, la figure ne pourrait pas montrer une casse.
STRATES = [
    ("distance", "0-1km", "0–1 km"),
    ("distance", "1-2km", "1–2 km"),
    ("distance", "2-5km", "2–5 km"),
    ("distance", "5-10km", "5–10 km"),
    ("motif", "etudes", "Study trips"),
    ("occupation", "etudiant", "Students"),
    ("occupation", "scolaire", "Pupils"),
    ("lieu_residence", "3eme_couronne", "3rd ring"),
    ("type_logement", "individuel_isole", "Detached house"),
    ("type_logement", "petit_habitat_collectif", "Small flats"),
    ("age", "75-130", "Aged 75+"),
]


def scores(reference: str) -> dict | None:
    """Le `scores.json` d'une exécution désignée, ou de la dernière d'une expérience."""
    chemin = DOSSIER / reference
    if "/executions/" not in reference:
        executions = sorted((chemin / "executions").glob("*")) if chemin.is_dir() else []
        if not executions:
            logger.warning(f"[figure] aucune exécution pour {reference} — bras ignoré")
            return None
        chemin = executions[-1]
    fichier = chemin / "scores.json"
    if not fichier.is_file():
        logger.warning(f"[figure] {fichier} absent — bras ignoré")
        return None
    return json.loads(fichier.read_text(encoding="utf-8"))


def l1_strate(score: dict, dimension: str, categorie: str) -> float | None:
    for strate in score["detail"][dimension]["strates"]:
        if strate["cat"] == categorie and strate.get("covered"):
            return strate["l1"]
    return None


def tracer(sortie: Path) -> Path:
    lus = [(nom, genre, scores(ref)) for nom, genre, ref in BRAS]
    manquants = [nom for nom, _, s in lus if s is None]
    if manquants:
        logger.warning(f"[figure] {len(manquants)} bras sans score : {', '.join(manquants)}")
    lus = [(nom, genre, s) for nom, genre, s in lus if s is not None]
    if len(lus) < 2:
        raise SystemExit("[figure] moins de deux bras lisibles : rien à comparer")

    temoins = [s for _, genre, s in lus if genre == TEMOIN]
    bruit = (
        abs(temoins[0]["composite"]["emd_jsd"] - temoins[1]["composite"]["emd_jsd"])
        if len(temoins) == 2
        else 0.0
    )
    base = temoins[0]
    logger.info(f"[figure] plancher de bruit du témoin : {bruit:.3f} point de composite")

    figure, (gauche, droite) = plt.subplots(1, 2, figsize=(15.5, 6.4))

    # ── panneau gauche : le composite, et ce qui n'est que du bruit ────────────────────
    noms = [nom for nom, _, _ in lus]
    valeurs = [s["composite"]["emd_jsd"] for _, _, s in lus]
    couleurs = [COULEURS[genre] for _, genre, _ in lus]
    y = range(len(noms))
    gauche.barh(list(y), valeurs, color=couleurs, height=0.62)
    reference = base["composite"]["emd_jsd"]
    gauche.axvspan(reference - bruit, reference + bruit, color="#8d8b86", alpha=0.22, zorder=0)
    gauche.axvline(reference, color="#4a4a4a", lw=1.0, ls="--", zorder=1)
    for i, valeur in enumerate(valeurs):
        gauche.text(valeur + 0.08, i, f"{valeur:.2f}", va="center", fontsize=9)
    gauche.set_yticks(list(y))
    gauche.set_yticklabels(noms, fontsize=9)
    gauche.invert_yaxis()
    gauche.set_xlabel("EMD–JSD composite (lower is better)")
    gauche.set_title(
        f"Prompt mutations on the typed zero-shot arm\n"
        f"grey band = run-to-run noise of the unchanged prompt (±{bruit:.2f})",
        fontsize=10,
    )
    gauche.set_xlim(0, max(valeurs) * 1.16)
    gauche.grid(axis="x", alpha=0.25)

    # ── panneau droit : par strate, ce qui progresse et ce qui casse ───────────────────
    mutations = [(nom, genre, s) for nom, genre, s in lus if genre != TEMOIN]
    libelles = [libelle for _, _, libelle in STRATES]
    positions = range(len(STRATES))
    largeur = 0.8 / max(len(mutations), 1)
    for rang, (nom, genre, score) in enumerate(mutations):
        cle = nom.split(" — ")[0]
        deltas, ordonnees = [], []
        for index, (dimension, categorie, _) in enumerate(STRATES):
            avant, apres = l1_strate(base, dimension, categorie), l1_strate(score, dimension, categorie)
            if avant is None or apres is None:
                continue
            deltas.append(apres - avant)
            ordonnees.append(index + (rang - (len(mutations) - 1) / 2) * largeur)
        droite.barh(ordonnees, deltas, height=largeur * 0.9,
                    color=TEINTES.get(cle, COULEURS[genre]),
                    alpha=0.95 if genre == RETENUE else 0.7,
                    edgecolor="white", linewidth=0.3,
                    label=f"{cle} (kept)" if genre == RETENUE else cle)
    droite.axvline(0, color="#4a4a4a", lw=1.0)
    droite.set_yticks(list(positions))
    droite.set_yticklabels(libelles, fontsize=9)
    droite.invert_yaxis()
    droite.set_xlabel("Change in per-stratum L1 against the prompt in service\n← improvement    degradation →")
    droite.set_title("Where each mutation gains, and what it costs elsewhere", fontsize=10)
    droite.grid(axis="x", alpha=0.25)
    droite.legend(fontsize=8, loc="lower right", framealpha=0.95, ncol=2)

    figure.tight_layout()
    sortie.mkdir(parents=True, exist_ok=True)
    fichier = sortie / "jev_mutations_prompt.png"
    figure.savefig(fichier, dpi=170)
    plt.close(figure)
    logger.info(f"[figure] écrite : {fichier}")
    return fichier


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--sortie", type=Path, required=True, help="dossier de trace où écrire la figure")
    arguments = parseur.parse_args()
    fichier = tracer(arguments.sortie)
    print(fichier)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
