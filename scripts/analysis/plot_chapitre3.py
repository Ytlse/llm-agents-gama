#!/usr/bin/env python3
"""La figure du chapitre 3 : ce qui s'oublie, et ce qui ne s'oublie pas.

Le § 3.4 affirme que deux registres coexistent sous deux horloges — les traces
épisodiques s'érodent, les concepts non — et donne trois nombres pour le dire :
une constante de temps de 2,8 jours, un plafond de durée de vie à trente, une
demi-vie de 1,9 jour. Les mettre sur un même axe montre l'écart que la phrase
énonce sans le faire voir.

La figure est **en anglais**, comme toutes les figures du manuscrit soumis. Sa légende
suit les règles de style de l'article : elle définit ce qui est tracé, sans formule en
« X, pas Y », sans défense d'un choix, et sans rien dire de la fabrication — la
traçabilité vit dans le dépôt et dans les commentaires HTML du chapitre.

``ch3_oubli`` porte, en ordonnée, la COMPOSANTE TEMPORELLE du score de rappel.
Un seul axe, et ce n'est pas un artifice de présentation : pour un concept,
`_time_decay_score` renvoie littéralement sa confiance à la place d'une
décroissance (`llm/longterm.py`, deux régimes du ticket 071 lot 3). Les deux
registres sont bien la même composante, lue de deux façons.

**Aucune constante n'est écrite à la main.** Le script importe les fonctions du
dépôt — `poids_temporel`, `force_initiale`, `confiance` — et les appelle. Les
valeurs viennent de `settings.agent`. La figure ne peut donc pas diverger du
code, et la note de bas de figure imprime les constantes qui l'ont produite.
Si l'import échoue, rien n'est tracé : une figure de mécanisme dessinée avec
des valeurs devinées est pire que pas de figure.

Usage :
    services/llm-agents/.venv/bin/python scripts/analysis/plot_chapitre3.py
    … --sortie docs/paper/figures --copie docs/paper/article/images
"""

from __future__ import annotations

import argparse
import logging
import math
import shutil
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

RACINE = Path(__file__).resolve().parents[2]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from scripts.analysis.figures_versionnees import signaler

logger = logging.getLogger("ch3")

SERVICE = RACINE / "services" / "llm-agents"
SORTIE_DEFAUT = RACINE / "docs" / "paper" / "figures"
COPIE_DEFAUT = RACINE / "docs" / "paper" / "article" / "images"

# Le point de sensibilité du dispositif : la constante de temps publiée par Park et al.
# (2023), contre celle héritée de Vu et al. que le dépôt tient par défaut. Ce n'est pas
# un réglage du dépôt mais une valeur de la littérature — d'où la seule constante
# littérale de ce fichier, et le commentaire qui la rattache à sa source.
S0_PARK_JOURS = 8.3

# Le concept illustré est celui du bloc « Ce que je sais » servi au modèle : douze
# observations, aucun contre-exemple. Le second est le même après cinq contre-exemples.
CONCEPT_OBSERVATIONS = 12
CONCEPT_CONTRE_EXEMPLES = 5

HORIZON_JOURS = 30

# Le seuil de mise à l'écart ne vaut QUE pour les concepts. Tracé sur toute la largeur, il
# se lisait comme un couperet sur les courbes épisodiques, qui n'en ont pas : elles passent
# sous 0,5 et continuent d'être servies, moins fort.
DEBUT_SEUIL_CONCEPTS = 15.5

EPISODIQUE = "#c0562c"
CONCEPT = "#008572"
REFERENCE = "#6f6c66"
ENCRE = "#2b2a28"
ENCRE_SECONDE = "#55534f"
GRILLE = "#e2e0dc"


class Dispositif:
    """Les fonctions et les constantes du dépôt, lues une fois et portées ensemble."""

    def __init__(self, poids_temporel, force_initiale, confiance, agent) -> None:
        self.poids_temporel = poids_temporel
        self.force_banale = force_initiale(0.0)
        self.poids_temps = float(agent.long_term_retrieval__time_weight)
        self.delta_rappel = float(agent.memoire__force_delta_rappel_jours)
        self.force_marquante = force_initiale(1.0)
        self.confiance_confirmee = confiance(CONCEPT_OBSERVATIONS, 0)
        self.confiance_contredite = confiance(CONCEPT_OBSERVATIONS, CONCEPT_CONTRE_EXEMPLES)
        self.seuil_service = float(agent.memoire__confiance_seuil_service)
        self.seuil_purge = float(agent.memoire__purge_seuil_poids)
        self.force_base = float(agent.long_term_retrieval__force_base_jours)
        self.force_max = float(agent.memoire__force_max_jours)
        self.k_importance = float(agent.memoire__force_k_importance)

    @property
    def demi_vie(self) -> float:
        return math.log(2) * self.force_banale

    @property
    def age_de_purge(self) -> float:
        """L'ancienneté à laquelle une trace banale jamais rappelée passe sous le seuil."""
        return -self.force_banale * math.log(self.seuil_purge)


def charger_le_dispositif() -> Dispositif | None:
    """Importe les fonctions du service. Toute panne d'import interdit la figure."""
    if str(SERVICE) not in sys.path:
        sys.path.insert(0, str(SERVICE))
    try:
        from llm.concepts import confiance
        from llm.gravite import force_initiale, poids_temporel
        from settings import settings
    except ImportError as erreur:
        logger.error(
            "[ALARME] Les fonctions de la mémoire sont introuvables depuis %s : %s. "
            "Lancer le script avec services/llm-agents/.venv/bin/python ; "
            "aucune figure n'est tracée avec des valeurs devinées.",
            SERVICE.relative_to(RACINE), erreur,
        )
        return None
    dispositif = Dispositif(poids_temporel, force_initiale, confiance, settings.agent)
    logger.info(
        "Constantes lues dans le dépôt : S0 = %.1f j, k = %.0f, plafond = %.0f j, "
        "force banale = %.1f j, force marquante = %.1f j, demi-vie = %.2f j, "
        "poids de la composante = %.2f",
        dispositif.force_base, dispositif.k_importance, dispositif.force_max,
        dispositif.force_banale, dispositif.force_marquante, dispositif.demi_vie,
        dispositif.poids_temps,
    )
    return dispositif


def figure_oubli(d: Dispositif, sortie: Path) -> list[Path]:
    """Les deux horloges sur un même axe : ce qui s'érode, ce qui ne bouge qu'observé."""
    jours = np.linspace(0, HORIZON_JOURS, 601)
    banale = np.array([d.poids_temporel(t, d.force_banale) for t in jours])
    marquante = np.array([d.poids_temporel(t, d.force_marquante) for t in jours])
    sensibilite = np.array([d.poids_temporel(t, S0_PARK_JOURS) for t in jours])

    figure, axes = plt.subplots(figsize=(9.0, 5.4))

    # Ce que la gravité achète : l'aplat entre la trace banale et la trace marquante.
    axes.fill_between(jours, banale, marquante, color=EPISODIQUE, alpha=0.10, zorder=1)

    axes.plot(jours, marquante, color=EPISODIQUE, linewidth=2.0, linestyle="--", zorder=3,
              label=f"serious episodic trace — lifetime {d.force_marquante:.1f} d")
    axes.plot(jours, banale, color=EPISODIQUE, linewidth=2.2, zorder=4,
              label=f"ordinary episodic trace — lifetime {d.force_banale:.1f} d")
    axes.plot(jours, sensibilite, color=REFERENCE, linewidth=1.5, linestyle=":", zorder=3,
              label=f"sensitivity arm — S₀ = {S0_PARK_JOURS} d (Park et al., 2023)")

    axes.axhline(d.confiance_confirmee, color=CONCEPT, linewidth=2.2, zorder=5,
                 label=f"concept — {CONCEPT_OBSERVATIONS} observations, no counter-example")
    axes.axhline(d.confiance_contredite, color=CONCEPT, linewidth=2.0, linestyle=(0, (6, 3)),
                 alpha=0.85, zorder=5,
                 label=f"same concept after {CONCEPT_CONTRE_EXEMPLES} counter-examples")

    # Le seuil porte la couleur des concepts et s'arrête avec eux : c'est à eux seuls qu'il
    # s'applique. Les courbes épisodiques le traversent sans que rien ne leur arrive.
    axes.plot([DEBUT_SEUIL_CONCEPTS, HORIZON_JOURS], [d.seuil_service, d.seuil_service],
              color=CONCEPT, linewidth=1.2, linestyle="-.", alpha=0.9, zorder=5)

    # La flèche tient dans la bande libre entre les deux droites, la légende ayant quitté
    # l'aire de tracé. Elle mesure la chute, elle ne la commente pas.
    milieu = (d.confiance_confirmee + d.confiance_contredite) / 2
    axes.annotate(
        "", xy=(19.0, d.confiance_contredite + 0.012), xytext=(19.0, d.confiance_confirmee - 0.012),
        arrowprops={"arrowstyle": "-|>", "color": CONCEPT, "linewidth": 1.4},
    )
    axes.text(19.6, milieu, f"{CONCEPT_CONTRE_EXEMPLES} counter-examples,\n"
              f"confidence {d.confiance_confirmee:.2f} → {d.confiance_contredite:.2f}",
              fontsize=8.5, color=CONCEPT, va="center", linespacing=1.4)
    axes.text(DEBUT_SEUIL_CONCEPTS, d.seuil_service + 0.032,
              f"concepts set aside below {d.seuil_service:g}",
              fontsize=8.5, color=ENCRE_SECONDE)

    # La demi-vie et l'âge de purge : deux repères posés dans le triangle vide sous la
    # courbe ordinaire, le seul endroit où aucune courbe ne passe.
    axes.plot([d.demi_vie, d.demi_vie], [0, 0.5], color=EPISODIQUE, linewidth=0.9,
              linestyle=":", alpha=0.9, zorder=2)
    axes.annotate(
        f"half-life {d.demi_vie:.1f} d", xy=(d.demi_vie, 0.5), xytext=(6.4, 0.205),
        fontsize=8.5, color=ENCRE_SECONDE,
        arrowprops={"arrowstyle": "-", "color": "#a8a6a1", "linewidth": 0.9},
    )
    axes.plot([d.age_de_purge], [d.seuil_purge], marker="o", markersize=5,
              color=EPISODIQUE, zorder=5)
    axes.annotate(
        f"purged at {d.age_de_purge:.0f} d", xy=(d.age_de_purge, d.seuil_purge),
        xytext=(d.age_de_purge + 1.1, 0.062), fontsize=8.5, color=ENCRE_SECONDE,
        arrowprops={"arrowstyle": "-", "color": "#a8a6a1", "linewidth": 0.9},
    )

    axes.set_xlim(0, HORIZON_JOURS)
    axes.set_ylim(0, 1.04)
    axes.set_xlabel("age since last recall (days)", fontsize=10, color=ENCRE)
    axes.set_ylabel("temporal component of the retrieval score", fontsize=10, color=ENCRE)
    axes.tick_params(labelsize=9, colors=ENCRE_SECONDE)
    axes.grid(color=GRILLE, linewidth=0.8, zorder=0)
    axes.set_axisbelow(True)
    for bord in ("top", "right"):
        axes.spines[bord].set_visible(False)
    for bord in ("left", "bottom"):
        axes.spines[bord].set_color(GRILLE)
    # La légende sort de l'aire de tracé : à l'intérieur, elle heurtait la flèche des
    # concepts, seul endroit où celle-ci soit lisible.
    axes.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=2, fontsize=8.5,
                frameon=False, labelcolor=ENCRE_SECONDE, handlelength=2.6,
                columnspacing=2.4, borderaxespad=0.0)

    # La note tient sur deux lignes : d'un seul tenant, `bbox_inches="tight"` élargissait
    # la toile à la longueur du texte et écrasait la figure.
    figure.tight_layout(rect=(0, 0.11, 1, 1))
    figure.text(
        0.012, 0.014,
        f"Lifetime = min(S₀ × (1 + {d.k_importance:.0f} × gravity), {d.force_max:.0f} d), with "
        f"S₀ = {d.force_base} d. Each recall resets the age to zero and adds "
        f"{d.delta_rappel:.0f} day of lifetime.\n"
        f"Concept confidence follows Laplace's rule of succession. A set-aside concept stays in "
        "the index, with the date it was set aside.\n"
        f"An episodic trace is purged below {d.seuil_purge:g} of weight. This component carries "
        f"weight {d.poids_temps:.2f} in the retrieval score.",
        fontsize=7.5, color=ENCRE_SECONDE, linespacing=1.6,
    )
    return ecrire(figure, sortie, "ch3_oubli")


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
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--sortie", type=Path, default=SORTIE_DEFAUT)
    analyseur.add_argument("--copie", type=Path, default=COPIE_DEFAUT,
                           help="dossier où les figures sont recopiées pour l'article")
    analyseur.add_argument("--sans-copie", action="store_true")
    arguments = analyseur.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s : %(message)s")
    depart = time.monotonic()
    logger.info("Figure du chapitre 3 : lecture des constantes de la mémoire")

    dispositif = charger_le_dispositif()
    if dispositif is None:
        return 1

    ecrits = figure_oubli(dispositif, arguments.sortie)
    signaler(ecrits)

    copies = 0
    if not arguments.sans_copie:
        arguments.copie.mkdir(parents=True, exist_ok=True)
        for chemin in ecrits:
            shutil.copy2(chemin, arguments.copie / chemin.name)
            copies += 1

    logger.info(
        "Terminé en %.1f s : %d fichier(s) écrit(s), %d recopié(s) vers %s",
        time.monotonic() - depart, len(ecrits), copies,
        arguments.copie.relative_to(RACINE) if not arguments.sans_copie else "(aucun)",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
