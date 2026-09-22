#!/usr/bin/env python3
"""Figure 7.1 — la grille des signes pré-enregistrée, cinq articles par quatre modes.

Lit la grille gelée (`docs/paper/sources/actualites/grille_signes.yaml`) et rend un damier
de vingt cellules : le SENS attendu du déplacement de part modale sous l'article brut (C2)
par rapport à la journée nominale (C1), et son intensité ordinale.

La figure se compose en ANGLAIS — c'est la règle des figures de l'article.

La grille est pré-enregistrée : cette figure ne contient AUCUNE mesure. Elle montre ce qui
est prédit avant le premier appel au modèle, et c'est précisément ce qu'on ne peut plus
changer après la campagne. L'empreinte du YAML est journalisée à chaque rendu.

Usage :
    services/llm-agents/.venv/bin/python scripts/analysis/presse/figure_grille_signes.py
"""
from __future__ import annotations

import hashlib
import logging
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.analysis.figures_versionnees import signaler  # noqa: E402

RACINE = Path(__file__).resolve().parents[3]
GRILLE = RACINE / "docs/paper/sources/actualites/grille_signes.yaml"
# Convention du dépôt : les figures vivent dans `docs/paper/figures/` et sont RECOPIÉES dans
# `docs/paper/article/images/`, seul dossier que `../images/` atteint depuis `fr/` et `en/`.
# Écrire ailleurs produit un chapitre dont les images ne s'affichent pas.
STOCK = RACINE / "docs/paper/figures"
COPIE = RACINE / "docs/paper/article/images"
# Deux formats, le même dessin : le PNG est celui qu'appelle le chapitre, parce qu'un SVG ne
# s'affiche pas dans tous les lecteurs Markdown ; le SVG reste pour le rendu LaTeX.
FORMATS = ("png", "svg")
SORTIES = tuple(
    dossier / f"ch7_grille_signes.{ext}" for dossier in (STOCK, COPIE) for ext in FORMATS
)

CELLULES_ATTENDUES = 20

# Le signe porte la couleur et la flèche, l'intensité la saturation et les trois pastilles.
# Palette divergente sûre pour les daltonismes courants, et distincte de la palette modale du
# projet (rouge/violet/vert/cyan) pour qu'on ne lise pas un mode là où il y a un sens.
TEINTE = {"+": "#0E7C66", "-": "#B4541F", "0": "#94A3B8"}
SATURATION = {0: 0.12, 1: 0.26, 2: 0.52, 3: 0.82}
ENCRE = "#1F2933"
ENCRE_PALE = "#6B7684"

# Libellés anglais des quatre modes, et la pastille de la palette officielle du projet.
MODES = [
    ("voiture", "Car", "#D32F2F"),
    ("velo", "Bicycle", "#7B1FA2"),
    ("marche", "Walking", "#00ACC1"),
    ("tc", "Public transport", "#2E7D32"),
]

# Libellés anglais des cinq articles, en deux lignes : le fait, puis ce qui le rend lisible.
ARTICLES = {
    "a09_vent_autan": ("Autan wind gusts", "parks closed, bridges exposed"),
    "a13_punaises_metro": ("Bedbug rumour", "seats intact, credibility dented"),
    "a07_greve_eboueurs": ("Refuse collectors' strike", "pavements impassable"),
    "a18_la_machine": ("La Machine parade", "city centre pedestrianised"),
    "a25_velotoulouse": ("Electric bike-share", "hillside gradient erased"),
}

logger = logging.getLogger("figure_grille_signes")


def _melange(hexa: str, alpha: float) -> tuple[float, float, float]:
    """Le ton `hexa` posé sur du blanc à l'opacité `alpha` — un aplat, jamais une transparence.

    Un SVG à cellules translucides se recompose mal une fois collé dans Overleaf ; on résout
    le mélange ici.
    """
    r, v, b = (int(hexa[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return tuple(1.0 - alpha * (1.0 - c) for c in (r, v, b))


def charger_grille() -> tuple[dict, str]:
    """La grille et l'empreinte SHA-256 du fichier qui la porte."""
    brut = GRILLE.read_bytes()
    empreinte = hashlib.sha256(brut).hexdigest()
    return yaml.safe_load(brut), empreinte


def verifier(grille: dict) -> list[tuple[str, str, dict]]:
    """Aplatit la grille en cellules et refuse tout ce qui ne se dessine pas honnêtement.

    Trois refus, et aucun n'a de repli : un article inconnu, un compte de cellules qui n'est
    pas vingt, une intensité qui contredit son signe. Dessiner malgré l'un des trois
    produirait une figure d'article fausse et silencieuse.
    """
    cellules: list[tuple[str, str, dict]] = []
    erreurs: list[str] = []

    inconnus = [cle for cle in grille["articles"] if cle not in ARTICLES]
    if inconnus:
        erreurs.append(
            f"articles absents des libellés anglais du script : {inconnus} "
            f"(clés connues : {sorted(ARTICLES)})"
        )

    for cle_article, article in grille["articles"].items():
        for cle_mode, _, _ in MODES:
            cellule = article["cellules"].get(cle_mode)
            if cellule is None:
                erreurs.append(f"cellule manquante : {cle_article} / {cle_mode}")
                continue
            signe, intensite = str(cellule["signe"]), int(cellule["intensite"])
            if (signe == "0") != (intensite == 0):
                erreurs.append(
                    f"signe et intensité en désaccord : {cle_article} / {cle_mode} "
                    f"→ signe '{signe}', intensité {intensite} ; la grille exige "
                    f"signe '0' si et seulement si intensité 0"
                )
            cellules.append((cle_article, cle_mode, cellule))

    if len(cellules) != CELLULES_ATTENDUES:
        erreurs.append(
            f"[ALARME] la grille porte {len(cellules)} cellules, le protocole en annonce "
            f"{CELLULES_ATTENDUES} — le § 7.1.3 du chapitre 7 et la barre d'inférence "
            f"sont à recalculer avant de rendre cette figure"
        )

    for message in erreurs:
        logger.error(message)
    if erreurs:
        raise SystemExit(1)

    return cellules


def _police() -> None:
    """Une grotesque humaniste si la machine en a une, sinon la police par défaut.

    Aucun glyphe de la figure ne sort de l'ASCII : les flèches sont dessinées, pas composées.
    Une police qui n'aurait pas U+2191 ne peut donc pas produire de tofu.
    """
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = [
        "Source Sans 3",
        "Inter",
        "Helvetica Neue",
        "Arial",
        "Avenir Next",
        "DejaVu Sans",
    ]


def _cellule(ax, x, y, signe, intensite):
    """Une case : fond arrondi, flèche du sens, trois pastilles d'intensité."""
    fond = _melange(TEINTE[signe], SATURATION[intensite])
    sombre = SATURATION[intensite] >= 0.5
    encre = "#FFFFFF" if sombre else TEINTE[signe]
    ax.add_patch(
        mpatches.FancyBboxPatch(
            (x - 0.43, y - 0.34),
            0.86,
            0.68,
            boxstyle="round,pad=0,rounding_size=0.09",
            facecolor=fond,
            edgecolor=_melange(TEINTE[signe], 0.32) if signe == "0" else "none",
            linewidth=0.9,
            linestyle=(0, (3, 2)) if signe == "0" else "solid",
        )
    )

    if signe == "0":
        # Un trait court : ni hausse, ni baisse, et c'est une prédiction.
        ax.plot([x - 0.07, x + 0.07], [y - 0.02, y - 0.02], lw=2.2, color=TEINTE["0"], solid_capstyle="round")
        return

    # La flèche est un triangle plein posé sur une hampe : aucun glyphe, donc aucun tofu.
    sens = 1 if signe == "+" else -1
    pointe = y - 0.04 - sens * 0.17
    base = y - 0.04 + sens * 0.05
    ax.add_patch(
        mpatches.Polygon(
            [(x, pointe), (x - 0.085, base), (x + 0.085, base)],
            closed=True,
            facecolor=encre,
            edgecolor="none",
        )
    )
    ax.plot(
        [x, x],
        [base - sens * 0.005, y - 0.04 + sens * 0.175],
        lw=2.6,
        color=encre,
        solid_capstyle="butt",
    )

    # Trois pastilles, les pleines donnent l'intensité attendue.
    for rang in range(3):
        plein = rang < intensite
        ax.add_patch(
            mpatches.Circle(
                (x - 0.08 + rang * 0.08, y + 0.255),
                0.019,
                facecolor=encre if plein else "none",
                edgecolor=encre if plein else _melange(encre, 0.45),
                linewidth=0.8,
            )
        )


def dessiner(grille: dict, cellules: list, empreinte: str) -> None:
    _police()
    ordre = list(grille["articles"])
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")

    for cle_article, cle_mode, cellule in cellules:
        _cellule(
            ax,
            [m[0] for m in MODES].index(cle_mode),
            ordre.index(cle_article),
            str(cellule["signe"]),
            int(cellule["intensite"]),
        )

    # En-têtes de colonnes : la pastille de la palette modale, puis le nom du mode.
    for x, (_, libelle, couleur) in enumerate(MODES):
        ax.add_patch(
            mpatches.FancyBboxPatch(
                (x - 0.075, -0.95),
                0.15,
                0.032,
                boxstyle="round,pad=0,rounding_size=0.016",
                facecolor=couleur,
                edgecolor="none",
            )
        )
        ax.text(x, -0.70, libelle, ha="center", va="center", fontsize=10.5, color=ENCRE)

    # Libellés de lignes : le fait, puis ce qui le rend lisible.
    for y, cle in enumerate(ordre):
        titre, glose = ARTICLES[cle]
        ax.text(-0.60, y - 0.10, titre, ha="right", va="center", fontsize=10.5, color=ENCRE)
        ax.text(-0.60, y + 0.13, glose, ha="right", va="center", fontsize=8.5, color=ENCRE_PALE)

    ax.set_xlim(-2.45, len(MODES) - 0.45)
    ax.set_ylim(len(ordre) - 0.30, -1.10)
    ax.set_xticks([])
    ax.set_yticks([])
    for cote in ax.spines.values():
        cote.set_visible(False)

    poignees = [
        mpatches.Patch(facecolor=_melange(TEINTE["+"], 0.52), label="modal share rises"),
        mpatches.Patch(facecolor=_melange(TEINTE["-"], 0.52), label="modal share falls"),
        mpatches.Patch(
            facecolor=_melange(TEINTE["0"], 0.12),
            edgecolor=_melange(TEINTE["0"], 0.32),
            linestyle=(0, (3, 2)),
            linewidth=0.9,
            label="no net shift expected",
        ),
    ]
    legende = ax.legend(
        handles=poignees,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.02),
        ncol=3,
        frameon=False,
        fontsize=9,
        handlelength=1.5,
        handleheight=0.9,
        columnspacing=2.2,
        handletextpad=0.7,
    )
    for texte in legende.get_texts():
        texte.set_color(ENCRE_PALE)

    fig.text(
        0.5,
        0.005,
        "filled dots: expected intensity, 1 to 3, published without being tested",
        ha="center",
        fontsize=8.5,
        color=ENCRE_PALE,
    )

    for sortie in SORTIES:
        sortie.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(
            sortie,
            format=sortie.suffix.lstrip("."),
            dpi=220,
            bbox_inches="tight",
            facecolor="#FFFFFF",
        )
    plt.close(fig)
    signaler(list(SORTIES))
    logger.info(
        "%d cellules, grille gelée le %s, sha256 %s",
        len(cellules),
        grille["gele_le"],
        empreinte[:12],
    )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    depart = time.monotonic()
    logger.info("lecture de la grille pré-enregistrée : %s", GRILLE.relative_to(RACINE))
    if not GRILLE.exists():
        logger.error("grille introuvable : %s — rien à dessiner", GRILLE)
        raise SystemExit(1)

    grille, empreinte = charger_grille()
    cellules = verifier(grille)
    logger.info(
        "grille lue : %d articles, %d modes, %d cellules, version %s",
        len(grille["articles"]),
        len(MODES),
        len(cellules),
        grille["version"],
    )
    par_signe = {s: sum(1 for *_, c in cellules if str(c["signe"]) == s) for s in "+-0"}
    logger.info(
        "signes attendus : %d hausses, %d baisses, %d sans déplacement net",
        par_signe["+"],
        par_signe["-"],
        par_signe["0"],
    )

    dessiner(grille, cellules, empreinte)
    logger.info("terminé sans erreur en %.2f s", time.monotonic() - depart)


if __name__ == "__main__":
    sys.exit(main())
