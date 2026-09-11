#!/usr/bin/env python3
"""Nuage de points comparant les expériences de choix modal.

Chaque expérience de ``data/experiences/`` est positionnée sur deux métriques
composites, toutes deux « plus bas = mieux » :

* en abscisse, le composite EMD/JSD ;
* en ordonnée, le composite L1.

La couleur code le modèle de décision, la forme code le gabarit de prompt. Les
références sans prompt (LightGBM, heuristiques) sont en gris neutre : elles ne
participent pas à la comparaison de prompts.

Usage :
    python scripts/analysis/plot_experiences.py exp_a exp_b ...
    python scripts/analysis/plot_experiences.py --sortie docs/paper/figures/comparaison
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import yaml
from matplotlib.lines import Line2D

RACINE = Path(__file__).resolve().parents[2]
DOSSIER_EXPERIENCES = RACINE / "data" / "experiences"

# exp_gemini-31-fl_expcham5_jtir_t0_nosim est volontairement absente : son
# exécution du 2026-09-08 n'était pas terminée. L'ajouter ici une fois scorée.
EXPERIENCES_PAR_DEFAUT = [
    "exp_gemini-35-fl_expcham5_jtir_t0_nosim_2",
    "exp_gemini-31-fl_expcha_jtir_t0_nosim",
    "exp_gemini-35-fl_expcha_jtir_t0_nosim",
    "exp_gemini-35-fl_minper_jtir_t0_nosim_2",
    "exp_lgbm_jtir_nosim",
    "exp_mistral-s_minper_jtir_t0_nosim",
    "exp_durmin_nosim",
    "exp_alea_nosim",
    "exp_gemini-31-fl_minper_jtir_t0_nosim",
    "exp_majvoiture_nosim",
]

# Palette catégorielle validée (slots 1-3, contrôle « toutes paires » en mode
# clair : pire ΔE CVD 9.2, pire ΔE vision normale 21.8). Au-delà de trois
# teintes, le nuage ne tiendrait plus les seuils daltonisme : les références
# passent donc en gris neutre, distinguées par leur forme et leur étiquette.
COULEUR_NEUTRE = "#52514e"
COULEURS_MODELES = {
    "gemini-3.5-flash-lite": "#2a78d6",
    "gemini-3.1-flash-lite": "#eb6834",
    # Nom fautif conservé : les exécutions archivées avant le 2026-09-10 le portent,
    # et sans cette entrée leurs points tomberaient en gris neutre.
    "gemini-3.1-flash-lite-preview": "#eb6834",
    "mistral-small-latest": "#1baf7a",
    "gemini-3.8-flash": "#9c27b0",
}

# Formes par gabarit de prompt, puis par type de décideur pour les références.
FORMES_PROMPTS = {
    "minimal_persona": ("o", "Persona minimal", "persona"),
    "expert_chaine": ("s", "Expert chaîne", "chaîne"),
    "expert_chaine_m5": ("^", "Expert chaîne (m5)", "chaîne m5"),
}
FORMES_REFERENCES = {
    "modele": ("D", "LightGBM (référence ML)"),
    "duree_minimale": ("P", "Durée minimale"),
    "majoritaire_voiture": ("X", "Tout voiture"),
    "aleatoire": ("*", "Aléatoire"),
    "antigravity": ("v", "Antigravity (sous-agent)"),
}

ETIQUETTES_MODELES = {
    "gemini-3.5-flash-lite": "Gemini 3.5 Flash-Lite",
    "gemini-3.1-flash-lite": "Gemini 3.1 Flash-Lite",
    "gemini-3.1-flash-lite-preview": "Gemini 3.1 Flash-Lite",   # archives
    "mistral-small-latest": "Mistral Small",
    "gemini-3.8-flash": "Gemini 3.8 Flash",
}

# Étiquettes courtes tracées à côté des points : le nuage LLM est resserré,
# les libellés longs s'y recouvrent.
ETIQUETTES_COURTES = {
    "gemini-3.5-flash-lite": "G3.5",
    "gemini-3.1-flash-lite": "G3.1",
    "gemini-3.1-flash-lite-preview": "G3.1",   # archives
    "mistral-small-latest": "Mistral S",
    "gemini-3.8-flash": "G3.8",
}

# Décalage de l'étiquette (en points typographiques) par expérience, réglé à la
# main : le nuage est trop dense pour un placement automatique.
DECALAGES = {
    "exp_lgbm_jtir_nosim": (16, 2),
    "exp_alea_nosim": (-14, 4),
    "exp_majvoiture_nosim": (14, 2),
    "exp_durmin_nosim": (14, -12),
    "exp_mistral-s_minper_jtir_t0_nosim": (-14, 2),
    "exp_gemini-31-fl_minper_jtir_t0_nosim": (14, 0),
    "exp_gemini-35-fl_minper_jtir_t0_nosim_2": (14, 0),
    "exp_gemini-31-fl_expcha_jtir_t0_nosim": (14, -10),
    "exp_gemini-31-fl_expcham5_jtir_t0_nosim": (14, 10),
    "exp_gemini-35-fl_expcha_jtir_t0_nosim": (-14, 2),
    "exp_gemini-35-fl_expcham5_jtir_t0_nosim_2": (-14, -12),
}

INK_PRIMAIRE = "#0b0b0b"
INK_SECONDAIRE = "#52514e"
INK_DISCRET = "#8a8880"
SURFACE = "#fcfcfb"

logger = logging.getLogger("plot_experiences")


class ExperienceIllisible(RuntimeError):
    """Une expérience demandée n'a pas de résultat exploitable."""


def derniere_execution_scoree(dossier: Path) -> Path:
    """Renvoie la dernière exécution possédant un ``scores.json``."""
    executions = sorted((dossier / "executions").glob("*"))
    ignorees = 0
    for execution in reversed(executions):
        if (execution / "scores.json").exists():
            if ignorees:
                logger.info(
                    "%s : %d exécution(s) plus récente(s) ignorée(s), sans scores.json",
                    dossier.name,
                    ignorees,
                )
            return execution
        ignorees += 1
    raise ExperienceIllisible(
        f"{dossier.name} : aucune des {len(executions)} exécution(s) n'a de scores.json"
    )


def lire_experience(nom: str) -> dict:
    """Assemble configuration et scores d'une expérience."""
    dossier = DOSSIER_EXPERIENCES / nom
    if not dossier.is_dir():
        raise ExperienceIllisible(f"{nom} : dossier absent sous {DOSSIER_EXPERIENCES}")

    config = yaml.safe_load((dossier / "experience.yaml").read_text(encoding="utf-8"))
    execution = derniere_execution_scoree(dossier)
    scores = json.loads((execution / "scores.json").read_text(encoding="utf-8"))

    decideur = config.get("decideur") or {}
    gabarit = config.get("gabarit") or {}
    modele = decideur.get("modele")
    type_decideur = decideur.get("type")
    est_reference = modele is None

    return {
        "nom": nom,
        "execution": execution.name,
        "modele": modele,
        "type_decideur": type_decideur,
        "variante": gabarit.get("variante"),
        "est_reference": est_reference,
        "emd_jsd": scores["composite"]["emd_jsd"],
        "l1": scores["composite"]["l1"],
        "couverture": scores["couverture"]["taux"],
        "n_agents": scores["global"]["n_agents"],
        "jour": (scores.get("lecture") or {}).get("jour_retenu"),
        "genere_le": scores.get("genere_le"),
    }


def style_du_point(point: dict) -> tuple[str, str, str]:
    """Renvoie (couleur, forme, étiquette de la forme) pour un point."""
    if point["est_reference"]:
        forme, libelle = FORMES_REFERENCES.get(point["type_decideur"], ("o", point["type_decideur"]))
        return COULEUR_NEUTRE, forme, libelle
    couleur = COULEURS_MODELES.get(point["modele"])
    if couleur is None:
        raise ExperienceIllisible(
            f"{point['nom']} : modèle « {point['modele']} » absent de la palette "
            f"(slots disponibles : {', '.join(COULEURS_MODELES)})"
        )
    forme, libelle, _ = FORMES_PROMPTS.get(point["variante"], ("o", str(point["variante"]), str(point["variante"])))
    return couleur, forme, libelle


def etiquette_point(point: dict) -> str:
    """Étiquette courte, sur une seule ligne, tracée à côté du point."""
    if point["est_reference"]:
        return FORMES_REFERENCES.get(point["type_decideur"], ("", point["type_decideur"]))[1]
    modele = ETIQUETTES_COURTES.get(point["modele"], point["modele"])
    prompt = FORMES_PROMPTS.get(point["variante"], ("", "", point["variante"]))[2]
    return f"{modele} · {prompt}"


def dessiner(points: list[dict], sortie: Path) -> list[Path]:
    figure, axes = plt.subplots(figsize=(10.0, 7.0), dpi=300)
    figure.patch.set_facecolor(SURFACE)
    axes.set_facecolor(SURFACE)

    for point in points:
        couleur, forme, _ = style_du_point(point)
        taille = 320 if forme == "*" else 150
        axes.scatter(
            point["emd_jsd"],
            point["l1"],
            s=taille,
            c=couleur,
            marker=forme,
            edgecolors=SURFACE,
            linewidths=2.0,
            zorder=3,
        )

    # Étiquettes directes : la règle de relief impose des libellés visibles,
    # l'aqua de la palette passant sous 3:1 de contraste sur fond clair.
    for point in points:
        dx, dy = DECALAGES.get(point["nom"], (14, 2))
        axes.annotate(
            etiquette_point(point),
            xy=(point["emd_jsd"], point["l1"]),
            xytext=(dx, dy),
            textcoords="offset points",
            fontsize=9,
            color=INK_SECONDAIRE,
            ha="left" if dx >= 0 else "right",
            va="center" if abs(dy) < 6 else ("bottom" if dy > 0 else "top"),
            linespacing=1.25,
            zorder=4,
        )

    axes.set_xlabel("Composite EMD/JSD  —  plus bas = meilleur", fontsize=10, color=INK_PRIMAIRE)
    axes.set_ylabel("Composite L1  —  plus bas = meilleur", fontsize=10, color=INK_PRIMAIRE)
    axes.grid(True, color="#e6e5e0", linewidth=0.8, zorder=0)
    axes.set_axisbelow(True)
    for cote in ("top", "right"):
        axes.spines[cote].set_visible(False)
    for cote in ("left", "bottom"):
        axes.spines[cote].set_color("#d8d7d1")
    axes.tick_params(colors=INK_SECONDAIRE, labelsize=9)

    marge_x = (max(p["emd_jsd"] for p in points) - min(p["emd_jsd"] for p in points)) * 0.14
    marge_y = (max(p["l1"] for p in points) - min(p["l1"] for p in points)) * 0.14
    axes.set_xlim(min(p["emd_jsd"] for p in points) - marge_x, max(p["emd_jsd"] for p in points) + marge_x)
    axes.set_ylim(min(p["l1"] for p in points) - marge_y, max(p["l1"] for p in points) + marge_y)

    axes.annotate(
        "",
        xy=(0.030, 0.560),
        xytext=(0.105, 0.635),
        xycoords="axes fraction",
        textcoords="axes fraction",
        arrowprops={"arrowstyle": "-|>", "color": INK_DISCRET, "linewidth": 1.4},
        zorder=2,
    )
    axes.text(
        0.115, 0.638, "meilleur", transform=axes.transAxes,
        fontsize=9, color=INK_DISCRET, style="italic", va="bottom",
    )

    modeles_presents = [m for m in COULEURS_MODELES if any(p["modele"] == m for p in points)]
    legende_couleurs = [
        Line2D([], [], marker="o", linestyle="", markersize=9, markerfacecolor=COULEURS_MODELES[m],
               markeredgecolor=SURFACE, label=ETIQUETTES_MODELES.get(m, m))
        for m in modeles_presents
    ]
    if any(p["est_reference"] for p in points):
        legende_couleurs.append(
            Line2D([], [], marker="o", linestyle="", markersize=9, markerfacecolor=COULEUR_NEUTRE,
                   markeredgecolor=SURFACE, label="Références (sans prompt)")
        )

    prompts_presents = [v for v in FORMES_PROMPTS if any(p["variante"] == v and not p["est_reference"] for p in points)]
    legende_formes = [
        Line2D([], [], marker=FORMES_PROMPTS[v][0], linestyle="", markersize=9, markerfacecolor=INK_SECONDAIRE,
               markeredgecolor=SURFACE, label=FORMES_PROMPTS[v][1])
        for v in prompts_presents
    ]
    legende_formes += [
        Line2D([], [], marker=FORMES_REFERENCES[t][0], linestyle="", markersize=9,
               markerfacecolor=COULEUR_NEUTRE, markeredgecolor=SURFACE, label=FORMES_REFERENCES[t][1])
        for t in FORMES_REFERENCES
        if any(p["type_decideur"] == t and p["est_reference"] for p in points)
    ]

    premiere = axes.legend(
        handles=legende_couleurs, title="Modèle (couleur)", loc="upper left",
        frameon=False, fontsize=9, title_fontsize=9, labelcolor=INK_SECONDAIRE,
    )
    premiere.get_title().set_color(INK_PRIMAIRE)
    axes.add_artist(premiere)
    seconde = axes.legend(
        handles=legende_formes, title="Prompt / méthode (forme)", loc="lower right",
        frameon=False, fontsize=9, title_fontsize=9, labelcolor=INK_SECONDAIRE,
    )
    seconde.get_title().set_color(INK_PRIMAIRE)

    jours = sorted({p["jour"] for p in points if p["jour"]})
    executions = sorted(p["execution"][:10] for p in points)
    n_agents = sorted({p["n_agents"] for p in points})
    figure.suptitle(
        "Fidélité des parts modales par modèle et par prompt",
        fontsize=14, color=INK_PRIMAIRE, x=0.055, ha="left", y=0.965,
    )
    axes.set_title(
        f"{len(points)} expériences · jour simulé {', '.join(jours)} · "
        f"{n_agents[0] if len(n_agents) == 1 else f'{n_agents[0]}–{n_agents[-1]}'} agents · "
        f"exécutions du {executions[0]} au {executions[-1]}",
        fontsize=9.5, color=INK_SECONDAIRE, loc="left", pad=10,
    )
    figure.text(
        0.055, 0.018,
        f"Référentiel CEREMA · figure générée le {date.today().isoformat()}",
        fontsize=8, color=INK_DISCRET, ha="left",
    )
    figure.tight_layout(rect=(0.0, 0.035, 1.0, 0.925))

    ecrits = []
    for extension in ("png", "svg"):
        chemin = sortie.with_suffix(f".{extension}")
        chemin.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(chemin, facecolor=SURFACE)
        ecrits.append(chemin)
    plt.close(figure)
    return ecrits


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    analyseur.add_argument("experiences", nargs="*", default=None, help="noms d'expériences (défaut : le lot AAMAS)")
    analyseur.add_argument(
        "--sortie", type=Path,
        default=RACINE / "docs" / "paper" / "raw_assets" / "comparaison_experiences",
        help="chemin de sortie sans extension (PNG et SVG écrits)",
    )
    options = analyseur.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    noms = options.experiences or EXPERIENCES_PAR_DEFAUT
    debut = time.monotonic()
    logger.info("Lecture de %d expérience(s) sous %s", len(noms), DOSSIER_EXPERIENCES)

    points, echecs = [], []
    for nom in noms:
        try:
            point = lire_experience(nom)
        except (ExperienceIllisible, OSError, KeyError, ValueError) as erreur:
            echecs.append((nom, str(erreur)))
            logger.error("[ALARME] expérience illisible : %s", erreur)
            continue
        points.append(point)
        logger.info(
            "%s → exécution %s · EMD/JSD %.2f · L1 %.1f · couverture %.2f%%",
            nom, point["execution"], point["emd_jsd"], point["l1"], point["couverture"] * 100,
        )

    if not points:
        logger.error("[ALARME] aucune expérience exploitable, figure non produite")
        return 1
    if echecs:
        logger.error("[ALARME] %d/%d expérience(s) écartée(s) : %s", len(echecs), len(noms),
                     ", ".join(nom for nom, _ in echecs))

    ecrits = dessiner(points, options.sortie)
    logger.info(
        "Figure produite : %d point(s) tracé(s) en %.1f s → %s",
        len(points), time.monotonic() - debut, ", ".join(str(c.relative_to(RACINE)) for c in ecrits),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
