#!/usr/bin/env python3
"""Composite EMD/JSD et composite L1, par FAMILLE de décideur.

Trois familles sont mises en regard, chacune avec sa couleur et sa forme :

* les modèles classiques (booster, logit, forêt aléatoire, logistique à noyau) ;
* les LLM conduits par un prompt minimal ;
* les LLM conduits par un prompt expert.

Les repères naïfs (aléatoire, durée minimale, tout-voiture) sont tracés en gris
neutre, hors familles : ils donnent l'échelle de ce qui est gagné, ils ne
participent pas à la comparaison.

Deux figures sont produites, qui disent la même chose de deux façons :

* ``*_barres`` — deux panneaux (composite EMD/JSD, composite L1), une ligne par
  exécution, MÊME ordre dans les deux panneaux. Les rangs se lisent donc, et
  surtout leurs désaccords : une ligne mieux classée à gauche qu'à droite dit
  que les deux métriques ne hiérarchisent pas pareil.
* ``*_nuage`` — composite EMD en abscisse, composite L1 en ordonnée, enveloppe
  colorée par famille. Montre la séparation des familles d'un coup d'œil.

La lecture passe par ``scripts.dashboard.experiences.lister()`` — la même source
que le tableau de bord, à dessein : la famille d'un modèle classique se dérive
du FORMAT de son artefact (``modele:klr``, ``modele:lightgbm``), et redériver
cela ici l'aurait fait diverger du tableau au premier changement.

Usage :
    python scripts/analysis/plot_familles.py
    python scripts/analysis/plot_familles.py --sans-naifs --chaine toutes
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import date
from math import log10
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator

RACINE = Path(__file__).resolve().parents[2]
# Les deux entrées sont nécessaires : `scripts/` pour importer le paquet `dashboard`,
# la racine parce que `dashboard.experiences` s'importe lui-même en `scripts.dashboard.*`.
for _chemin in (RACINE, RACINE / "scripts"):
    if str(_chemin) not in sys.path:
        sys.path.insert(0, str(_chemin))

from scripts.dashboard import experiences as registre  # noqa: E402

logger = logging.getLogger("plot_familles")

# ── Familles ─────────────────────────────────────────────────────────────────
# Palette catégorielle validée (les trois mêmes slots que `plot_experiences.py`,
# contrôle « toutes paires » en mode clair). Au-delà de trois teintes le nuage ne
# tiendrait plus les seuils daltonisme : les repères passent donc en gris neutre.
# La couleur ne porte jamais seule l'identité — chaque famille a AUSSI sa forme,
# et le nom de l'exécution est écrit sur l'axe des barres.
CLASSIQUES, MINIMAL, EXPERT, NAIFS = "classiques", "llm_minimal", "llm_expert", "naifs"
FAMILLES = {
    CLASSIQUES: ("Modèles classiques", "#2a78d6", "D"),
    MINIMAL: ("LLM · prompt minimal", "#eb6834", "o"),
    EXPERT: ("LLM · prompt expert", "#1baf7a", "s"),
    NAIFS: ("Repères naïfs (hors familles)", "#52514e", "X"),
}
ORDRE_FAMILLES = (CLASSIQUES, MINIMAL, EXPERT, NAIFS)

# Décideurs qui ne consultent ni modèle estimé ni LLM : ils fixent l'échelle.
DECIDEURS_NAIFS = {"aleatoire", "duree_minimale", "majoritaire_voiture"}

ETIQUETTES_DECIDEURS = {
    "modele:lightgbm": "LightGBM",
    "modele:klr": "Logistique à noyau",
    "modele:mnl": "Logit multinomial",
    "modele:rf": "Forêt aléatoire",
    "aleatoire": "Aléatoire",
    "duree_minimale": "Durée minimale",
    "majoritaire_voiture": "Tout voiture",
    "gemini-3.5-flash-lite": "Gemini 3.5 FL",
    "gemini-3.1-flash-lite": "Gemini 3.1 FL",
    "antigravity:gemini-3.8-flash": "Gemini 3.8 F (agent)",
}
ETIQUETTES_PROMPTS = {
    "prompt_minimal": "minimal",
    "expert_gem_3.8_v2": "expert v2",
    "expert_gem_3.8_v2_neutre_justif": "expert v2 neutre",
    "expert_gem_3.8_v3": "expert v3",
    "prompt_optimise_v4": "optimisé v4",
}

INK_PRIMAIRE = "#0b0b0b"
INK_SECONDAIRE = "#52514e"
INK_DISCRET = "#8a8880"
SURFACE = "#fcfcfb"
GRILLE = "#e6e5e0"


class RienATracer(RuntimeError):
    """Aucune exécution scorée ne satisfait le périmètre demandé."""


def famille_de(ligne: dict) -> str | None:
    """La famille d'une ligne du registre, ou None si elle n'entre dans aucune.

    Le prompt `prompt_optimise_v4` est rangé avec les experts : c'est un prompt
    long, porteur d'a priori modaux, et l'opposer au minimal est précisément ce
    que la figure compare. Le distinguer demanderait une quatrième teinte, que
    la palette ne peut pas tenir sans perdre la séparation daltonisme.
    """
    decideur = ligne.get("decideur") or ""
    if decideur.startswith("modele:") or decideur == "modele":
        return CLASSIQUES
    if decideur in DECIDEURS_NAIFS:
        return NAIFS
    prompt = ligne.get("prompt") or ""
    if "minimal" in prompt:
        return MINIMAL
    if prompt.startswith(("expert", "prompt_optimise")):
        return EXPERT
    return None


def etiquette(ligne: dict) -> str:
    """Nom lisible d'une exécution : le décideur, et le prompt s'il y en a un."""
    decideur = ligne.get("decideur") or "?"
    libelle = ETIQUETTES_DECIDEURS.get(decideur, decideur)
    prompt = ligne.get("prompt") or "—"
    if prompt == "—":
        return libelle
    return f"{libelle} · {ETIQUETTES_PROMPTS.get(prompt, prompt)}"


def charger(*, chaine: str, avec_naifs: bool) -> list[dict]:
    """Les exécutions traçables, avec leur famille — et le compte de ce qui est écarté.

    Ne sont retenues que les DERNIÈRES exécutions terminées et scorées d'une
    expérience active. Une exécution plus ancienne de la même expérience porte
    un score obsolète : la tracer ferait apparaître deux points pour une seule
    condition, sans que rien sur la figure ne dise lequel fait foi.
    """
    lignes = registre.lister()
    logger.info("Registre lu : %d ligne(s) sous %s", len(lignes), registre.DOSSIER)

    ecartes: dict[str, int] = {}

    def ecarter(motif: str) -> None:
        ecartes[motif] = ecartes.get(motif, 0) + 1

    points = []
    for ligne in lignes:
        if ligne.get("statut") != "actif":
            ecarter("expérience archivée ou invalidée")
            continue
        if ligne.get("execution") is None:
            ecarter("expérience définie, jamais exécutée")
            continue
        if not ligne.get("derniere"):
            ecarter("exécution remplacée par une plus récente")
            continue
        if ligne.get("etat") != registre.ETAT_TERMINEE:
            ecarter(f"exécution non terminée ({ligne.get('etat')})")
            continue
        if ligne.get("composite_emd") is None or ligne.get("composite_l1") is None:
            ecarter("exécution sans score composite")
            continue
        if chaine != "toutes" and ligne.get("chaine") != chaine:
            ecarter(f"chaîne des véhicules ≠ « {chaine} »")
            continue
        famille = famille_de(ligne)
        if famille is None:
            ecarter("décideur hors des familles comparées")
            continue
        if famille == NAIFS and not avec_naifs:
            ecarter("repère naïf, écarté sur demande")
            continue
        points.append({
            "nom": ligne["experience"],
            "execution": ligne["execution"],
            "famille": famille,
            "etiquette": etiquette(ligne),
            "emd": float(ligne["composite_emd"]),
            "l1": float(ligne["composite_l1"]),
            "couverture": ligne.get("couverture"),
            "chaine": ligne.get("chaine"),
            "jeu": ligne.get("jeu"),
            "formule": ligne.get("formule"),
            "formule_perimee": bool(ligne.get("formule_perimee")),
        })

    for motif, n in sorted(ecartes.items(), key=lambda kv: -kv[1]):
        logger.info("Écarté — %s : %d ligne(s)", motif, n)

    perimees = [p["nom"] for p in points if p["formule_perimee"]]
    if perimees:
        logger.error(
            "[ALARME] %d exécution(s) scorée(s) avec une formule périmée, comparaison "
            "faussée : %s", len(perimees), ", ".join(perimees),
        )
    formules = {p["formule"] for p in points}
    if len(formules) > 1:
        logger.error(
            "[ALARME] %d formules de score différentes sur la même figure (%s) : "
            "les composites ne sont pas comparables entre eux",
            len(formules), ", ".join(sorted(str(f) for f in formules)),
        )

    if not points:
        raise RienATracer(
            f"aucune exécution retenue sur {len(lignes)} ligne(s) "
            f"(chaîne « {chaine} », repères naïfs {'inclus' if avec_naifs else 'exclus'})"
        )
    for famille in ORDRE_FAMILLES:
        n = sum(1 for p in points if p["famille"] == famille)
        logger.info("Famille « %s » : %d exécution(s)", FAMILLES[famille][0], n)
    return points


# ── Habillage commun ─────────────────────────────────────────────────────────
def _nettoyer(axes) -> None:
    axes.set_facecolor(SURFACE)
    axes.grid(True, color=GRILLE, linewidth=0.8, zorder=0)
    axes.set_axisbelow(True)
    for cote in ("top", "right"):
        axes.spines[cote].set_visible(False)
    for cote in ("left", "bottom"):
        axes.spines[cote].set_color("#d8d7d1")
    axes.tick_params(colors=INK_SECONDAIRE, labelsize=9)


def _pied(figure, points: list[dict], resume: str) -> None:
    jeux = sorted({p["jeu"] for p in points if p["jeu"]})
    chaines = sorted({p["chaine"] for p in points if p["chaine"]})
    figure.text(
        0.012, 0.015,
        f"{resume} · jeu {', '.join(jeux) or '?'} · chaîne des véhicules : "
        f"{', '.join(chaines) or '?'} · référentiel CEREMA · "
        f"figure générée le {date.today().isoformat()}",
        fontsize=7.5, color=INK_DISCRET, ha="left",
    )


def _legende_handles(points: list[dict]) -> list[Line2D]:
    return [
        Line2D([], [], marker=FAMILLES[f][2], linestyle="", markersize=9,
               markerfacecolor=FAMILLES[f][1], markeredgecolor=SURFACE, label=FAMILLES[f][0])
        for f in ORDRE_FAMILLES if any(p["famille"] == f for p in points)
    ]


# ── Figure 1 : deux panneaux de barres ───────────────────────────────────────
def dessiner_barres(points: list[dict], sortie: Path) -> list[Path]:
    """Deux panneaux, même ordre de lignes : le désaccord de rang devient visible."""
    # Tri sur le L1 (le plus lisible : des points de pourcentage), meilleur en haut.
    ordonnes = sorted(points, key=lambda p: p["l1"])
    y = range(len(ordonnes))
    hauteur = max(4.2, 0.42 * len(ordonnes) + 2.0)

    figure, (gauche, droite) = plt.subplots(
        1, 2, figsize=(12.4, hauteur), dpi=300, sharey=True,
        gridspec_kw={"wspace": 0.06},
    )
    figure.patch.set_facecolor(SURFACE)

    for axes, cle, titre in ((gauche, "emd", "Composite EMD/JSD"), (droite, "l1", "Composite L1")):
        _nettoyer(axes)
        valeurs = [p[cle] for p in ordonnes]
        axes.barh(list(y), valeurs, height=0.66, zorder=3,
                  color=[FAMILLES[p["famille"]][1] for p in ordonnes],
                  edgecolor=SURFACE, linewidth=0.8)
        marge = max(valeurs) * 0.16
        axes.set_xlim(0, max(valeurs) + marge)
        for i, (p, v) in enumerate(zip(ordonnes, valeurs)):
            axes.text(v + max(valeurs) * 0.015, i, f"{v:.1f}", va="center", ha="left",
                      fontsize=8.5, color=INK_SECONDAIRE, zorder=4)
        axes.set_title(f"{titre}  —  plus bas = meilleur", fontsize=10.5,
                       color=INK_PRIMAIRE, loc="left", pad=8)

    # Une seule inversion : les axes partagent leur axe des ordonnées, en inverser
    # deux remettrait la meilleure exécution en bas.
    gauche.invert_yaxis()
    gauche.set_yticks(list(y))
    gauche.set_yticklabels([p["etiquette"] for p in ordonnes], fontsize=9, color=INK_PRIMAIRE)

    # Marges posées en POUCES, pas en fractions : la hauteur de la figure suit le
    # nombre de lignes, et des fractions fixes feraient grossir le bandeau de titre
    # avec elle — jusqu'à écraser les barres sur un lot fourni.
    figure.subplots_adjust(left=0.185, right=0.985,
                           top=1 - 1.05 / hauteur, bottom=0.95 / hauteur)

    figure.suptitle(
        "Fidélité des parts modales : modèles classiques, prompt minimal, prompt expert",
        fontsize=13.5, color=INK_PRIMAIRE, x=0.012, ha="left", y=1 - 0.30 / hauteur,
    )
    figure.text(
        0.012, 1 - 0.56 / hauteur,
        "Lignes ordonnées sur le composite L1 (panneau de droite) ; le panneau de gauche "
        "garde le même ordre, ses barres non décroissantes signalent un désaccord de rang "
        "entre les deux métriques.",
        fontsize=9, color=INK_SECONDAIRE, ha="left", va="top",
    )
    figure.legend(handles=_legende_handles(points), loc="lower right",
                  bbox_to_anchor=(0.985, 0.06 / hauteur), frameon=False, fontsize=9,
                  ncols=2, labelcolor=INK_SECONDAIRE)
    _pied(figure, points, f"{len(ordonnes)} exécutions")
    return _ecrire(figure, sortie)


# ── Figure 2 : nuage EMD × L1 ────────────────────────────────────────────────
def _enveloppe(xs: list[float], ys: list[float]) -> list[tuple[float, float]]:
    """Enveloppe convexe (parcours monotone d'Andrew), sans dépendance externe."""
    pts = sorted(set(zip(xs, ys)))
    if len(pts) <= 2:
        return pts

    def demi(sequence):
        pile: list[tuple[float, float]] = []
        for p in sequence:
            while len(pile) >= 2:
                (x1, y1), (x2, y2) = pile[-2], pile[-1]
                if (x2 - x1) * (p[1] - y1) - (y2 - y1) * (p[0] - x1) > 0:
                    break
                pile.pop()
            pile.append(p)
        return pile

    return demi(pts)[:-1] + demi(reversed(pts))[:-1]


def dessiner_nuage(points: list[dict], sortie: Path) -> list[Path]:
    """Nuage EMD × L1, familles cerclées.

    Les deux axes sont logarithmiques : du meilleur modèle (4,5) au tirage
    aléatoire (56,0), le composite EMD couvre un facteur 12, et en échelle
    linéaire les repères naïfs écrasaient les trois familles comparées dans le
    coin inférieur gauche — la figure ne montrait plus que ce qu'on savait déjà,
    à savoir que tirer au hasard est mauvais.
    """
    figure, axes = plt.subplots(figsize=(10.4, 7.0), dpi=300)
    figure.patch.set_facecolor(SURFACE)
    _nettoyer(axes)
    axes.set_xscale("log")
    axes.set_yscale("log")

    # Enveloppes : seulement pour les trois familles comparées. Les repères naïfs
    # n'en reçoivent pas — les cercler suggérerait un groupe cohérent alors qu'ils
    # ne partagent que le fait de ne rien consulter. Le calcul se fait dans
    # l'espace des logarithmes, celui où les axes sont droits : une enveloppe
    # convexe calculée sur les valeurs brutes serait concave à l'écran.
    for famille in (CLASSIQUES, MINIMAL, EXPERT):
        groupe = [p for p in points if p["famille"] == famille]
        if len(groupe) < 3:
            continue
        sommets = _enveloppe([log10(p["emd"]) for p in groupe], [log10(p["l1"]) for p in groupe])
        if len(sommets) >= 3:
            axes.add_patch(Polygon([(10 ** x, 10 ** y) for x, y in sommets], closed=True,
                                   facecolor=FAMILLES[famille][1], edgecolor=FAMILLES[famille][1],
                                   alpha=0.12, linewidth=1.2, zorder=1))

    for famille in ORDRE_FAMILLES:
        groupe = [p for p in points if p["famille"] == famille]
        if not groupe:
            continue
        libelle, couleur, forme = FAMILLES[famille]
        axes.scatter([p["emd"] for p in groupe], [p["l1"] for p in groupe],
                     s=150, c=couleur, marker=forme, edgecolors=SURFACE,
                     linewidths=2.0, zorder=3, label=libelle)

    axes.set_xlabel("Composite EMD/JSD  —  plus bas = meilleur  (échelle log)",
                    fontsize=10, color=INK_PRIMAIRE)
    axes.set_ylabel("Composite L1  —  plus bas = meilleur  (échelle log)",
                    fontsize=10, color=INK_PRIMAIRE)

    # Graduations écrites en clair : sur un axe logarithmique, les graduations
    # automatiques de matplotlib sont des puissances de dix, et il n'y en aurait
    # qu'une seule dans l'intervalle utile.
    xs, ys = [p["emd"] for p in points], [p["l1"] for p in points]
    axes.set_xlim(min(xs) / 1.35, max(xs) * 1.35)
    axes.set_ylim(min(ys) / 1.35, max(ys) * 1.35)
    for axe, valeurs in ((axes.xaxis, (4, 6, 10, 15, 25, 40, 60)),
                         (axes.yaxis, (40, 60, 100, 150, 200, 300))):
        axe.set_major_locator(FixedLocator(valeurs))
        axe.set_minor_locator(NullLocator())
        axe.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))

    # Le sens de lecture, posé en haut à gauche : le couloir libre de la figure,
    # les points s'alignant sur la diagonale montante.
    axes.annotate("", xy=(0.045, 0.855), xytext=(0.130, 0.940),
                  xycoords="axes fraction", textcoords="axes fraction",
                  arrowprops={"arrowstyle": "-|>", "color": INK_DISCRET, "linewidth": 1.4}, zorder=2)
    axes.text(0.140, 0.944, "meilleur", transform=axes.transAxes, fontsize=9,
              color=INK_DISCRET, style="italic", va="bottom")

    legende = axes.legend(handles=_legende_handles(points), title="Famille de décideur",
                          loc="lower right", frameon=False, fontsize=9.5,
                          title_fontsize=9.5, labelcolor=INK_SECONDAIRE)
    legende.get_title().set_color(INK_PRIMAIRE)

    figure.suptitle("Fidélité des parts modales par famille de décideur",
                    fontsize=13.5, color=INK_PRIMAIRE, x=0.055, ha="left", y=0.975)
    axes.set_title(
        f"{len(points)} exécutions · les deux composites sont des écarts aux parts "
        f"modales de référence, plus bas = plus fidèle",
        fontsize=9.5, color=INK_SECONDAIRE, loc="left", pad=10,
    )
    _pied(figure, points, f"{len(points)} exécutions")
    figure.tight_layout(rect=(0.0, 0.030, 1.0, 0.960))
    return _ecrire(figure, sortie)


def _ecrire(figure, sortie: Path) -> list[Path]:
    ecrits = []
    for extension in ("png", "svg"):
        chemin = sortie.with_suffix(f".{extension}")
        chemin.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(chemin, facecolor=SURFACE)
        ecrits.append(chemin)
    plt.close(figure)
    return ecrits


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    analyseur.add_argument(
        "--sortie", type=Path,
        default=RACINE / "docs" / "paper" / "figures" / "familles_composite_l1",
        help="préfixe de sortie sans extension (suffixé _barres / _nuage, PNG et SVG écrits)")
    analyseur.add_argument("--figures", choices=("barres", "nuage", "toutes"), default="toutes")
    analyseur.add_argument(
        "--chaine", choices=("active", "coupée", "toutes"), default="active",
        help="état de la chaîne des véhicules retenu (défaut : active — le seul état où les "
             "trois familles coexistent ; « toutes » mélange des conditions non comparables)")
    analyseur.add_argument("--sans-naifs", action="store_true",
                           help="écarte aléatoire, durée minimale et tout-voiture")
    options = analyseur.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    debut = time.monotonic()
    try:
        points = charger(chaine=options.chaine, avec_naifs=not options.sans_naifs)
    except RienATracer as erreur:
        logger.error("[ALARME] figure non produite : %s", erreur)
        return 1

    ecrits: list[Path] = []
    if options.figures in ("barres", "toutes"):
        ecrits += dessiner_barres(points, options.sortie.with_name(options.sortie.name + "_barres"))
    if options.figures in ("nuage", "toutes"):
        ecrits += dessiner_nuage(points, options.sortie.with_name(options.sortie.name + "_nuage"))

    logger.info(
        "Figures produites : %d exécution(s) tracée(s) en %.1f s → %s",
        len(points), time.monotonic() - debut,
        ", ".join(str(c.relative_to(RACINE)) for c in ecrits),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
