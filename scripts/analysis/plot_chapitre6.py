#!/usr/bin/env python3
"""Les figures du chapitre 6 et de l'annexe H, recalculées depuis les `scores.json` du dépôt.

Le chapitre 6 compare treize décideurs sur la même cohorte. Quatre de ses énoncés
se lisent mieux en figure qu'en paragraphe, et c'est ce que ce script produit :

* ``ch6_echelle`` — les treize décideurs rangés sur l'axe du composite EMD–JSD,
  avec la bande de ce qu'une autre cohorte déplacerait ;
* ``ch6_ingenierie`` — la trajectoire que l'ingénierie de prompt fait parcourir à
  chaque modèle, du prompt minimal aux variantes expertes, face à la bande des
  références tabulaires ;
* ``ch6_distance`` — la part voiture par tranche de distance, la pente que le prompt
  installe ;
* ``ch6_residu`` — les deux modes qui portent le résidu, transports collectifs et vélo,
  lus par âge et par occupation.

Les planches de l'**annexe H**, portée par le chapitre 99, prennent le préfixe ``ch99_`` :
le préfixe dit dans quel chapitre la figure est insérée, et ``ch6_`` ne désigne que les
quatre figures du chapitre 6.

* ``ch99_dimensions_voiture`` — la part voiture par strate, sur six dimensions ;
* ``ch99_modes_distance`` — les quatre modes par tranche de distance, un panneau par
  mode : la voiture seule cache ce que la consigne fait du vélo et des transports
  collectifs ;
* ``ch99_modes_occupation`` et ``ch99_modes_motif`` — la même lecture par occupation et
  par motif de déplacement.

**Les figures sont en anglais** : elles partent telles quelles dans le manuscrit
soumis, dont la langue maître est l'anglais. Le texte des chapitres français les
cite et les légende en français.

Aucun chiffre n'est écrit à la main : chaque valeur est lue dans le dernier
`scores.json` de l'expérience. Quand le rejeu sur le jeu corrigé (ticket 088,
suffixe `_c_`) n'a pas encore abouti, la valeur de l'ancien jeu est prise et la
figure le signale — par une astérisque, et par un WARNING au journal.

Ce repli n'a plus de quoi s'exercer : depuis le ticket 098, l'ancien jeu et ses
exécutions sont en archive froide. Les treize décideurs se lisent tous sur le jeu
corrigé, et le journal l'énonce à chaque passage (« 13 sur 13, 0 sur l'ancien jeu »).
Si ce chiffre baisse un jour, c'est qu'un décideur manque au rejeu — pas qu'il faut
aller rouvrir l'archive.

Usage :
    services/llm-agents/.venv/bin/python scripts/analysis/plot_chapitre6.py
    … --sortie docs/paper/figures --copie docs/paper/article/images
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

RACINE = Path(__file__).resolve().parents[2]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from scripts.analysis.figures_versionnees import signaler

logger = logging.getLogger("ch6")

DOSSIER_EXPERIENCES = RACINE / "data" / "experiences"
SORTIE_DEFAUT = RACINE / "docs" / "paper" / "figures"
COPIE_DEFAUT = RACINE / "docs" / "paper" / "article" / "images"

# Ce qu'une autre cohorte de 1 000 personas déplacerait : IC95 par rééchantillonnage
# par grappe de personnes (ticket 080 § 0.3). Tracée en bande sur la figure d'échelle,
# elle dit quels écarts se lisent et lesquels ne se lisent pas.
RESOLUTION = 1.3

SUFFIXE = "_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN"

PLANCHER, MINIMAL, EXPERT, TABULAIRE = "plancher", "minimal", "expert", "tabulaire"
# Cinquième groupe, ticket 096 : un System One model — la catégorie sous laquelle TypeSafe range
# Jev — qui rend une probabilité par option sans produire de texte, ni modèle de langue génératif
# ni méthode ajustée sur l'enquête. Il n'entre dans AUCUNE figure sans `--avec-jev` : le chapitre 6
# de référence en compte treize, et une figure qui en montrerait quinze sans que son texte bouge
# serait pire qu'absente.
JEV = "jev"

COULEURS_GROUPES = {
    PLANCHER: "#8d8b86",
    MINIMAL: "#eb6834",
    EXPERT: "#2a78d6",
    TABULAIRE: "#1baf7a",
    JEV: "#9b51e0",
}
LIBELLES_GROUPES = {
    PLANCHER: "Baselines (no behavioural information)",
    MINIMAL: "Language models, minimal prompt",
    EXPERT: "Language models, expert prompt",
    TABULAIRE: "Tabular methods fitted on the survey",
    JEV: "System One model",
}

COULEURS_MODELES = {
    "gemini-3.5-flash-lite": "#2a78d6",
    "gemini-3.1-flash-lite": "#eb6834",
    "mistral-large-2512": "#1baf7a",
}
NOMS_MODELES = {
    "gemini-3.5-flash-lite": "Gemini 3.5 Flash-Lite",
    "gemini-3.1-flash-lite": "Gemini 3.1 Flash-Lite",
    "mistral-large-2512": "Mistral Large",
}

# Un décideur : un nom affiché, un groupe, et les deux expériences qui peuvent le
# porter — celle du jeu corrigé d'abord, celle de l'ancien jeu en repli.
DECIDEURS = [
    ("alea", "Uniform random", PLANCHER, None,
     f"exp_alea{SUFFIXE}_c_nosim", f"exp_alea{SUFFIXE}_nosim"),
    ("majvoiture", "All-car", PLANCHER, None,
     f"exp_majvoiture{SUFFIXE}_c_nosim", f"exp_majvoiture{SUFFIXE}_nosim"),
    ("durmin", "Shortest duration", PLANCHER, None,
     f"exp_durmin{SUFFIXE}_c_nosim", f"exp_durmin{SUFFIXE}_nosim"),
    ("mistral_min", "Mistral Large", MINIMAL, "mistral-large-2512",
     f"exp_mistral-l-25_promin02{SUFFIXE}_c_t0_nosim",
     f"exp_mistral-l-25_promin02{SUFFIXE}_t0_nosim"),
    ("g31_min", "Gemini 3.1 Flash-Lite", MINIMAL, "gemini-3.1-flash-lite",
     f"exp_gemini-31-fl_promin02{SUFFIXE}_c_t0_nosim",
     f"exp_gemini-31-fl_promin02{SUFFIXE}_t0_nosim"),
    ("g35_min", "Gemini 3.5 Flash-Lite", MINIMAL, "gemini-3.5-flash-lite",
     f"exp_gemini-35-fl_promin02{SUFFIXE}_c_t0_nosim",
     f"exp_gemini-35-fl_promin02{SUFFIXE}_t0_nosim"),
    ("g31_exp", "Gemini 3.1 Flash-Lite", EXPERT, "gemini-3.1-flash-lite",
     f"exp_gemini-31-fl_proexp05{SUFFIXE}_c_t0_nosim",
     f"exp_gemini-31-fl_proexp05{SUFFIXE}_t0_nosim"),
    ("mistral_exp", "Mistral Large", EXPERT, "mistral-large-2512",
     f"exp_mistral-l-25_proexp05{SUFFIXE}_c_t0_nosim",
     f"exp_mistral-l-25_proexp05{SUFFIXE}_t0_nosim"),
    ("g35_exp", "Gemini 3.5 Flash-Lite", EXPERT, "gemini-3.5-flash-lite",
     f"exp_gemini-35-fl_proexp05{SUFFIXE}_c_t0_nosim",
     f"exp_gemini-35-fl_proexp05{SUFFIXE}_t0_nosim"),
    ("mnl", "Multinomial logit", TABULAIRE, None,
     f"exp_mnl{SUFFIXE}_c_nosim", f"exp_mnl{SUFFIXE}_nosim"),
    ("rf", "Random forest", TABULAIRE, None,
     f"exp_rf{SUFFIXE}_c_nosim", f"exp_rf{SUFFIXE}_nosim"),
    ("klr", "Kernel logistic regression", TABULAIRE, None,
     f"exp_klr{SUFFIXE}_c_nosim", f"exp_klr{SUFFIXE}_nosim"),
    ("lgbm", "Gradient boosting (LightGBM)", TABULAIRE, None,
     f"exp_lgbm{SUFFIXE}_c_nosim", f"exp_lgbm{SUFFIXE}_nosim"),
]

# Ticket 096. Séparés de DECIDEURS, et c'est le point : `--avec-jev` les y verse, son absence
# laisse le chapitre de référence exactement où il est.
DECIDEURS_JEV = [
    ("jev_min", "Jev 1.13 (TypeSafe)  · minimal prompt", JEV, "jev-1.13.0",
     f"exp_jev-1130_promin02{SUFFIXE}_c_nosim", f"exp_jev-1130_promin02{SUFFIXE}_nosim"),
    # Ticket 096, addendum du 2026-09-21 : la consigne réglée POUR ce porteur, et la seule
    # dont le score soit EN ÉCHANTILLON — les écarts qui l'ont produite ont été lus sur la
    # cohorte qui la note. Le bras sous prompt_expert_05, consigne reçue d'un autre porteur,
    # ne figure plus parmi les décideurs depuis le 2026-09-21 : deux barres « expert prompt »
    # sur la même échelle ne se lisaient pas. Il reste dans VARIANTES_JEV, où la figure
    # d'ingénierie en fait la pointe hors échantillon de sa flèche.
    ("jev_exp32", "Jev 1.13 (TypeSafe)  · expert prompt", JEV, "jev-1.13.0",
     f"exp_jev-1130_proexp32{SUFFIXE}_c_nosim", f"exp_jev-1130_proexp32{SUFFIXE}_nosim"),
]

# Trois statuts, trois façons de tracer le point : le prompt minimal (aucune
# ingénierie), le prompt expert évalué hors échantillon (celui que le chapitre
# publie), et les variantes ajustées au vu de la cohorte évaluée — borne haute
# d'ajustement en échantillon, § 5.3.5, qui ne se compare pas aux précédentes.
MINIMAL_V, HORS_ECH, EN_ECH = "minimal", "hors_echantillon", "en_echantillon"

# Ticket 096 — versé dans VARIANTES par `--avec-jev` seulement (cf. DECIDEURS_JEV).
VARIANTES_JEV = {
    "jev-1.13.0": [
        ("promin02", "minimal prompt", MINIMAL_V,
         f"exp_jev-1130_promin02{SUFFIXE}_c_nosim", f"exp_jev-1130_promin02{SUFFIXE}_nosim"),
        ("proexp05", "expert prompt", HORS_ECH,
         f"exp_jev-1130_proexp05{SUFFIXE}_c_nosim", f"exp_jev-1130_proexp05{SUFFIXE}_nosim"),
        ("proexp32", "prompt tuned for it", EN_ECH,
         f"exp_jev-1130_proexp32{SUFFIXE}_c_nosim", f"exp_jev-1130_proexp32{SUFFIXE}_nosim"),
    ],
}

VARIANTES = {
    "gemini-3.5-flash-lite": [
        ("promin02", "minimal prompt", MINIMAL_V,
         f"exp_gemini-35-fl_promin02{SUFFIXE}_c_t0_nosim",
         f"exp_gemini-35-fl_promin02{SUFFIXE}_t0_nosim"),
        ("proexp08", "variant 08", EN_ECH,
         f"exp_gemini-35-fl_proexp08{SUFFIXE}_c_t0_nosim",
         f"exp_gemini-35-fl_proexp08{SUFFIXE}_t0_nosim"),
        ("proexp06", "variant 06", EN_ECH,
         f"exp_gemini-35-fl_proexp06{SUFFIXE}_c_t0_nosim",
         f"exp_gemini-35-fl_proexp06{SUFFIXE}_t0_nosim"),
        ("proexp05", "expert prompt", HORS_ECH,
         f"exp_gemini-35-fl_proexp05{SUFFIXE}_c_t0_nosim",
         f"exp_gemini-35-fl_proexp05{SUFFIXE}_t0_nosim"),
    ],
    "gemini-3.1-flash-lite": [
        ("promin02", "minimal prompt", MINIMAL_V,
         f"exp_gemini-31-fl_promin02{SUFFIXE}_c_t0_nosim",
         f"exp_gemini-31-fl_promin02{SUFFIXE}_t0_nosim"),
        ("proexp05", "expert prompt", HORS_ECH,
         f"exp_gemini-31-fl_proexp05{SUFFIXE}_c_t0_nosim",
         f"exp_gemini-31-fl_proexp05{SUFFIXE}_t0_nosim"),
    ],
    "mistral-large-2512": [
        ("promin02", "minimal prompt", MINIMAL_V,
         f"exp_mistral-l-25_promin02{SUFFIXE}_c_t0_nosim",
         f"exp_mistral-l-25_promin02{SUFFIXE}_t0_nosim"),
        ("proexp05", "expert prompt", HORS_ECH,
         f"exp_mistral-l-25_proexp05{SUFFIXE}_c_t0_nosim",
         f"exp_mistral-l-25_proexp05{SUFFIXE}_t0_nosim"),
    ],
}

# La figure des gains et des pertes compare deux consignes SUR LE MÊME SUBSTRAT :
# un delta pris entre deux jeux mêlerait l'effet de la consigne à celui de la
# correction du ticket 088. D'où une liste de candidats par côté, essayés dans
# l'ordre, et un repli complet sur l'ancien jeu si le jeu corrigé ne porte pas
# les deux termes.
PAIRES_SUBSTRAT = {
    "gemini-3.5-flash-lite": [
        # (libellé du substrat, expérience du prompt minimal, expériences expertes)
        ("jeu corrigé", f"exp_gemini-35-fl_promin02{SUFFIXE}_c_t0_nosim",
         [f"exp_gemini-35-fl_proexp05{SUFFIXE}_c_t0_nosim",
          f"exp_gemini-35-fl_proexp04{SUFFIXE}_c_t0_nosim"]),
        # Candidat mort depuis le ticket 098 : ces deux expériences sont en archive froide,
        # `dernier_score` n'y trouve plus rien et le couple est écarté. Gardé pour que la règle
        # « les deux termes d'un delta viennent du MÊME substrat » reste lisible le jour où un
        # troisième jeu la reposera.
        ("jeu antérieur", f"exp_gemini-35-fl_promin02{SUFFIXE}_t0_nosim",
         [f"exp_gemini-35-fl_proexp05{SUFFIXE}_t0_nosim"]),
    ],
}

TRANCHES = ["0-1km", "1-2km", "2-5km", "5-10km", "10-20km", "20-50km"]

# Les quatre modes du référentiel, dans l'ordre de leur part dans l'enquête.
MODES = [("voiture", "Car"), ("marche", "Walking"),
         ("transports_collectifs", "Public transport"), ("velo", "Cycling")]

# Les strates sont nommées en français dans les scores ; les figures parlent anglais.
LIBELLES_STRATES = {
    "0-1km": "0–1 km", "1-2km": "1–2 km", "2-5km": "2–5 km", "5-10km": "5–10 km",
    "10-20km": "10–20 km", "20-50km": "20–50 km", "plus_50km": "50+ km",
    "travail": "Work", "etudes": "Education", "achats": "Shopping",
    "accompagnement": "Escorting",
    "scolaire": "Pupil", "etudiant": "Student", "actif_temps_plein": "Full-time worker",
    "actif_temps_partiel": "Part-time worker", "chomeur_recherche_emploi": "Unemployed",
    "personne_au_foyer": "Homemaker", "Retraité": "Retired",
    "Homme": "Male", "Femme": "Female",
    "Toulouse": "Toulouse", "1ere_couronne": "First ring", "2eme_couronne": "Second ring",
    "3eme_couronne": "Third ring",
    "individuel_isole": "Detached house", "individuel_accole": "Terraced house",
    "petit_habitat_collectif": "Small apartment block",
    "grand_habitat_collectif": "Large apartment block",
    "75-130": "75+",
}
LIBELLES_DIMENSIONS = {
    "distance": "Trip distance", "motif": "Trip purpose", "age": "Age band",
    "occupation": "Occupation", "genre": "Gender", "lieu_residence": "Residence ring",
    "type_logement": "Dwelling type",
}
DIMENSIONS_GAINS_PERTES = ["distance", "motif", "age", "occupation"]

NOTE_REPLI = "* value measured on the dataset prior to the ticket-088 correction"


def libelle_strate(cat: str) -> str:
    return LIBELLES_STRATES.get(cat, cat)


#: Expériences dont le chapitre publie une exécution PRÉCISE, et non « la dernière ».
#:
#: Rejouer un bras à l'identique — pour mesurer le bruit du fournisseur, par exemple — crée une
#: seconde exécution, et « la dernière » déplace alors en silence un chiffre déjà relu. Mesuré
#: le 2026-09-21 : le réplicat du bras Jev sous prompt expert faisait passer toutes les figures
#: de 4,19 à 4,14 sans qu'une ligne du chapitre bouge. L'écart est inférieur au bruit — ce qui
#: est précisément le problème : il ne se voit pas.
#:
#: Épingler ici est réservé aux bras que le texte CITE. Pour les autres, « la dernière » reste
#: la règle : c'est elle qui fait profiter les figures d'un rejeu sans rien demander.
EXECUTIONS_FIGEES = {
    # Le § 6.1 publie 4,19 / 7,25 / 12,59 pour cette exécution-là (ticket 096, lot 2).
    f"exp_jev-1130_proexp05{SUFFIXE}_c_nosim": "2026-09-21_06_25_29",
}


def dernier_score(experience: str) -> dict | None:
    """Le `scores.json` de l'exécution publiée : celle qu'épingle `EXECUTIONS_FIGEES`, sinon la
    plus récente. None si aucune n'est scorée."""
    dossier = DOSSIER_EXPERIENCES / experience / "executions"
    if not dossier.is_dir():
        return None
    figee = EXECUTIONS_FIGEES.get(experience)
    if figee:
        fichier = dossier / figee / "scores.json"
        if fichier.is_file():
            try:
                with fichier.open(encoding="utf-8") as flux:
                    donnees = json.load(flux)
                donnees["_execution"] = figee
                return donnees
            except (OSError, json.JSONDecodeError) as erreur:
                logger.error("scores.json épinglé illisible pour %s (%s) : %s", experience, figee, erreur)
        else:
            # Dire, et non retomber en silence sur une autre exécution : une épingle qui ne
            # pointe rien est une erreur de configuration, pas une valeur par défaut.
            logger.error("exécution épinglée introuvable pour %s : %s — repli sur la plus récente",
                         experience, figee)
    for execution in sorted(dossier.iterdir(), reverse=True):
        fichier = execution / "scores.json"
        if not fichier.is_file():
            continue
        try:
            with fichier.open(encoding="utf-8") as flux:
                donnees = json.load(flux)
        except (OSError, json.JSONDecodeError) as erreur:
            logger.error("scores.json illisible pour %s (%s) : %s", experience, execution.name, erreur)
            continue
        donnees["_execution"] = execution.name
        return donnees
    return None


#: Où l'ancien jeu a été gelé (ticket 098). Le repli ci-dessous ne peut donc plus aboutir ;
#: le chemin sert à le DIRE, pas à y lire quoi que ce soit.
ARCHIVE_ANCIEN_JEU = "archive/2026-09-21_ancien_jeu_v6_EN"


def resoudre(exp_corrige: str, exp_ancien: str) -> tuple[dict | None, bool]:
    """Le score du jeu corrigé si le rejeu a abouti, celui de l'ancien jeu sinon.

    Le second terme est mort depuis le ticket 098 : l'ancien jeu et ses exécutions sont en
    archive froide, `dernier_score` n'y trouve plus rien. Le repli reste écrit parce qu'il
    documente l'ordre de préférence, et parce qu'un jeu futur reposera la même question — mais
    son échec doit nommer l'archive, sans quoi un rejeu incomplet et un substrat gelé rendraient
    le même `None` muet, et se diagnostiqueraient comme le même problème.
    """
    score = dernier_score(exp_corrige)
    if score is not None:
        return score, False
    score = dernier_score(exp_ancien)
    if score is None:
        logger.error(
            "[ALARME] Aucun score pour ce décideur sur le jeu corrigé (%s), et le repli sur "
            "l'ancien jeu (%s) ne peut plus aboutir : il est gelé sous %s/ depuis le ticket 098. "
            "Ce décideur doit être rejoué sur le jeu corrigé.",
            exp_corrige,
            exp_ancien,
            ARCHIVE_ANCIEN_JEU,
        )
        return None, False
    logger.warning(
        "Rejeu non abouti sur le jeu corrigé, valeur de l'ancien jeu retenue : %s", exp_corrige
    )
    return score, True


def l1_pondere(score: dict, dimension: str) -> dict[str, float]:
    """L'erreur L1 de chaque strate couverte d'une dimension."""
    strates = score["detail"].get(dimension, {}).get("strates", [])
    return {s["cat"]: s["l1"] for s in strates if s.get("covered") and s.get("n")}


def effectifs(score: dict, dimension: str) -> dict[str, int]:
    strates = score["detail"].get(dimension, {}).get("strates", [])
    return {s["cat"]: s["n"] for s in strates if s.get("covered") and s.get("n")}


def lire_decideurs() -> list[dict]:
    """Les treize décideurs avec leurs trois lectures, et la provenance de chacun."""
    lus, manquants, replis = [], 0, 0
    for cle, label, groupe, modele, exp_c, exp_a in DECIDEURS:
        score, repli = resoudre(exp_c, exp_a)
        if score is None:
            manquants += 1
            continue
        replis += int(repli)
        lus.append({
            "cle": cle, "label": label, "groupe": groupe, "modele": modele,
            "composite": score["composite"]["emd_jsd"],
            "hors_choix_unique": score["composite"]["emd_jsd_hors_choix_unique"],
            "l1": score["global"]["l1"],
            "repli": repli, "score": score,
        })
    logger.info(
        "Décideurs lus : %d sur %d (%d sur l'ancien jeu, %d sans aucun score)",
        len(lus), len(DECIDEURS), replis, manquants,
    )
    return lus


def figure_echelle(decideurs: list[dict], sortie: Path) -> list[Path]:
    """Les treize décideurs sur l'axe du composite, groupe par groupe."""
    ordre = sorted(decideurs, key=lambda d: d["composite"], reverse=True)
    figure, axes = plt.subplots(figsize=(9.2, 6.4))

    positions = range(len(ordre))
    valeurs = [d["composite"] for d in ordre]
    couleurs = [COULEURS_GROUPES[d["groupe"]] for d in ordre]
    axes.barh(list(positions), valeurs, color=couleurs, height=0.68, zorder=3)

    meilleur = min(valeurs)
    axes.axvspan(meilleur, meilleur + RESOLUTION, color="#c9c7c2", alpha=0.5, zorder=1)
    axes.annotate(
        f"±{RESOLUTION:.1f} points: cohort-to-cohort variation\n(another cohort of 1,000 personas)",
        xy=(meilleur + RESOLUTION, len(ordre) - 1.4),
        xytext=(max(valeurs) * 0.24, len(ordre) - 0.9),
        fontsize=8.5, color="#55534f", va="center",
        arrowprops={"arrowstyle": "-", "color": "#a8a6a1", "linewidth": 0.9},
    )

    for position, decideur in zip(positions, ordre):
        etiquette = f"{decideur['composite']:.2f}"
        if decideur["repli"]:
            etiquette += " *"
        axes.text(decideur["composite"] + 0.6, position, etiquette,
                  va="center", fontsize=9, color="#2b2a28")

    suffixes = {MINIMAL: "  · minimal prompt", EXPERT: "  · expert prompt"}
    axes.set_yticks(list(positions))
    axes.set_yticklabels(
        [d["label"] + suffixes.get(d["groupe"], "") for d in ordre], fontsize=9.5
    )
    axes.set_xlabel("Composite EMD–JSD over all decisions of the day (lower = closer to the survey)")
    axes.set_xlim(0, max(valeurs) * 1.12)
    axes.grid(axis="x", color="#e2e0dc", zorder=0)
    axes.set_axisbelow(True)
    for bord in ("top", "right", "left"):
        axes.spines[bord].set_visible(False)

    groupes_presents = [g for g in (PLANCHER, MINIMAL, EXPERT, JEV, TABULAIRE)
                        if any(d["groupe"] == g for d in ordre)]
    legende = [Patch(facecolor=COULEURS_GROUPES[g], label=LIBELLES_GROUPES[g])
               for g in groupes_presents]
    axes.legend(handles=legende, loc="upper right", fontsize=8.5, frameon=False,
                bbox_to_anchor=(1.0, 0.62))
    figure.tight_layout(rect=(0, 0.035, 1, 1))
    if any(d["repli"] for d in ordre):
        figure.text(0.012, 0.012, NOTE_REPLI, fontsize=8, color="#55534f")
    return ecrire(figure, sortie, "ch6_echelle")


def figure_ingenierie(sortie: Path, tabulaires: list[float]) -> list[Path]:
    """Ce que l'ingénierie de prompt fait parcourir à chaque modèle."""
    figure, axes = plt.subplots(figsize=(9.6, 5.0))
    modeles = [m for m in ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite",
                           "mistral-large-2512", "jev-1.13.0")
               if m in VARIANTES]
    # Quatre porteurs au lieu de trois : la légende, posée en haut à droite, tombait sur la
    # deuxième ligne. Elle descend hors de la zone tracée dès qu'un quatrième apparaît.
    legende_sous_axe = len(modeles) > 3

    if tabulaires:
        axes.axvspan(min(tabulaires), max(tabulaires), color="#1baf7a", alpha=0.16, zorder=1)
        axes.text((min(tabulaires) + max(tabulaires)) / 2, len(modeles) - 0.42,
                  "tabular methods", fontsize=8.5, color="#12805a", ha="center", va="bottom")

    replis = False
    for rang, modele in enumerate(modeles):
        ligne = len(modeles) - 1 - rang
        points = []
        for cle, label, statut, exp_c, exp_a in VARIANTES[modele]:
            score, repli = resoudre(exp_c, exp_a)
            if score is None:
                logger.warning("Variante absente de la figure, aucun score : %s", exp_c)
                continue
            replis = replis or repli
            points.append((score["composite"]["emd_jsd"], label, statut, repli))
        if not points:
            continue
        depart = next(v for v, _, statut, _ in points if statut == MINIMAL_V)
        arrivee = next(v for v, _, statut, _ in points if statut == HORS_ECH)
        axes.annotate(
            "", xy=(arrivee, ligne), xytext=(depart, ligne),
            arrowprops={"arrowstyle": "-|>", "color": COULEURS_MODELES[modele],
                        "linewidth": 1.6, "shrinkA": 0, "shrinkB": 0, "alpha": 0.55},
            zorder=2,
        )
        for rang_point, (valeur, label, statut, repli) in enumerate(sorted(points)):
            axes.scatter(
                [valeur], [ligne], s=90, zorder=4,
                facecolor="white" if statut == MINIMAL_V else COULEURS_MODELES[modele],
                edgecolor=COULEURS_MODELES[modele], linewidth=1.8,
                marker="s" if statut == EN_ECH else "o",
                alpha=0.55 if statut == EN_ECH else 1.0,
            )
            # Étiquettes alternées : sur Gemini 3.5, quatre variantes tiennent dans
            # deux points de composite et se recouvriraient toutes du même côté.
            haut = rang_point % 2 == 0
            axes.annotate(label + (" *" if repli else ""), (valeur, ligne),
                          textcoords="offset points", xytext=(0, 13 if haut else -24),
                          ha="center", fontsize=8, color="#55534f")
            axes.annotate(f"{valeur:.2f}", (valeur, ligne), textcoords="offset points",
                          xytext=(0, 24 if haut else -14), ha="center",
                          fontsize=8.5, color="#2b2a28")

    axes.set_yticks(range(len(modeles)))
    axes.set_yticklabels([NOMS_MODELES[m] for m in reversed(modeles)], fontsize=10)
    axes.set_ylim(-0.6, len(modeles) - 0.25)
    axes.set_xlabel("Composite EMD–JSD (lower = closer to the survey)")
    axes.grid(axis="x", color="#e2e0dc", zorder=0)
    axes.set_axisbelow(True)
    for bord in ("top", "right", "left"):
        axes.spines[bord].set_visible(False)
    legende = [
        Line2D([], [], marker="o", color="#55534f", markerfacecolor="white",
               markersize=8, linestyle="none", label="minimal prompt"),
        Line2D([], [], marker="o", color="#55534f", markerfacecolor="#55534f",
               markersize=8, linestyle="none", label="expert prompt, out of sample"),
        Line2D([], [], marker="s", color="#55534f", markerfacecolor="#55534f",
               markersize=8, linestyle="none", alpha=0.55,
               label="variants tuned on the evaluated cohort"),
    ]
    axes.legend(handles=legende, fontsize=8.5, frameon=False,
                **({"loc": "lower center", "bbox_to_anchor": (0.5, -0.30), "ncol": 3}
                   if legende_sous_axe
                   else {"loc": "upper right", "bbox_to_anchor": (1.0, 0.72)}))
    axes.set_xlim(right=axes.get_xlim()[1] + 0.9)
    figure.tight_layout(rect=(0, 0.16 if legende_sous_axe else 0.045, 1, 1))
    if replis:
        figure.text(0.012, 0.012, NOTE_REPLI, fontsize=8, color="#55534f")
    return ecrire(figure, sortie, "ch6_ingenierie")


def _meilleure_reference(decideurs: list[dict], dimension: str) -> dict | None:
    """La méthode tabulaire la plus proche de l'enquête sur cette dimension."""
    candidats = []
    for decideur in decideurs:
        if decideur["groupe"] != TABULAIRE:
            continue
        erreurs = l1_pondere(decideur["score"], dimension)
        tailles = effectifs(decideur["score"], dimension)
        total = sum(tailles.values())
        if not total:
            continue
        moyenne = sum(erreurs[c] * tailles[c] for c in erreurs) / total
        candidats.append((moyenne, decideur))
    if not candidats:
        return None
    return min(candidats, key=lambda couple: couple[0])[1]


def _parts(score: dict, dimension: str, strates: list[str], mode: str = "voiture",
           champ: str = "actual") -> list[float]:
    par_cat = {s["cat"]: s for s in score["detail"].get(dimension, {}).get("strates", [])}
    return [par_cat[c][champ][mode] if c in par_cat else float("nan") for c in strates]


def _strates_ordonnees(score: dict, dimension: str) -> tuple[list[str], dict[str, int]]:
    tailles = effectifs(score, dimension)
    strates = [c for c in tailles if tailles[c]]
    if dimension == "distance":
        strates = [c for c in TRANCHES + ["plus_50km"] if c in strates]
    elif dimension == "age":
        strates = sorted(strates, key=lambda c: int(c.split("-")[0]))
    return strates, tailles


def _planche_parts(decideurs: list[dict], sortie: Path, nom: str, dimensions: list[str],
                   avec_minimal: bool, titre: str, colonnes: int = 2) -> list[Path]:
    """La part voiture par strate : la cible, l'agent, et la meilleure référence.

    Trois courbes par panneau — quatre en annexe, où le prompt minimal montre d'où
    l'agent part. Au-delà, les panneaux cessent d'être lisibles.
    """
    par_cle = {d["cle"]: d for d in decideurs}
    agent = par_cle.get("g35_exp")
    minimal = par_cle.get("g35_min")
    if agent is None:
        logger.error("[ALARME] Aucun score pour gemini-3.5 sous prompt expert : %s non produite", nom)
        return []

    lignes = (len(dimensions) + colonnes - 1) // colonnes
    figure, grille = plt.subplots(lignes, colonnes, figsize=(5.2 * colonnes, 3.3 * lignes))
    axes_plats = list(grille.flat) if hasattr(grille, "flat") else [grille]

    for axes, dimension in zip(axes_plats, dimensions):
        strates, tailles = _strates_ordonnees(agent["score"], dimension)
        if not strates:
            continue
        abscisses = range(len(strates))
        par_cat = {s["cat"]: s for s in agent["score"]["detail"][dimension]["strates"]}
        cible = [par_cat[c]["target"]["voiture"] if c in par_cat else float("nan") for c in strates]
        axes.plot(list(abscisses), cible, color="#2b2a28", linewidth=2.4, marker="o",
                  markersize=5, zorder=5, label="Survey EMC² 2023")

        reference = _meilleure_reference(decideurs, dimension)
        if reference is not None:
            axes.plot(list(abscisses), _parts(reference["score"], dimension, strates),
                      color=COULEURS_GROUPES[TABULAIRE], linewidth=2.0, linestyle="-",
                      marker="s", markersize=4.5, zorder=3,
                      label=f"{reference['label']} (best tabular here)")
        if avec_minimal and minimal is not None:
            axes.plot(list(abscisses), _parts(minimal["score"], dimension, strates),
                      color=COULEURS_GROUPES[MINIMAL], linewidth=1.8, linestyle="--",
                      marker="o", markersize=4, zorder=3, label="Gemini 3.5, minimal prompt")
        axes.plot(list(abscisses), _parts(agent["score"], dimension, strates),
                  color=COULEURS_GROUPES[EXPERT], linewidth=2.2, linestyle="-",
                  marker="o", markersize=4.5, zorder=4, label="Gemini 3.5, expert prompt")

        axes.set_xticks(list(abscisses))
        if dimension == "age":
            axes.set_xticklabels([libelle_strate(c) if i % 2 == 0 else ""
                                  for i, c in enumerate(strates)],
                                 fontsize=7.5, rotation=45, ha="right")
        else:
            axes.set_xticklabels([f"{libelle_strate(c)}\n(n={tailles.get(c, 0)})" for c in strates],
                                 fontsize=7.5, rotation=25, ha="right")
        titre_panneau = LIBELLES_DIMENSIONS.get(dimension, dimension)
        if dimension in ("lieu_residence", "type_logement"):
            titre_panneau += "  (outside the calibration cycle)"
        axes.set_title(titre_panneau, fontsize=10, loc="left")
        axes.set_ylabel("Car share (%)", fontsize=9)
        axes.set_ylim(0, 100)
        axes.grid(axis="y", color="#e2e0dc")
        axes.set_axisbelow(True)
        for bord in ("top", "right"):
            axes.spines[bord].set_visible(False)
        axes.legend(fontsize=7.5, frameon=False, loc="upper left" if dimension == "distance" else "best")

    for axes in axes_plats[len(dimensions):]:
        axes.set_visible(False)

    figure.suptitle(titre, fontsize=11, x=0.012, ha="left")
    figure.tight_layout(rect=(0, 0.02, 1, 0.94))
    if agent["repli"]:
        figure.text(0.012, 0.004, NOTE_REPLI, fontsize=8, color="#55534f")
    return ecrire(figure, sortie, nom)


def figure_distance_voiture(decideurs: list[dict], sortie: Path) -> list[Path]:
    """La part voiture par tranche de distance : la pente que le prompt installe."""
    par_cle = {d["cle"]: d for d in decideurs}
    agent, minimal = par_cle.get("g35_exp"), par_cle.get("g35_min")
    if agent is None:
        logger.error("[ALARME] Aucun score pour gemini-3.5 sous prompt expert : pente non produite")
        return []
    strates, tailles = _strates_ordonnees(agent["score"], "distance")
    reference = _meilleure_reference(decideurs, "distance")

    figure, axes = plt.subplots(figsize=(8.6, 4.8))
    abscisses = range(len(strates))
    axes.plot(list(abscisses), _parts(agent["score"], "distance", strates, champ="target"),
              color="#2b2a28", linewidth=2.6, marker="o", markersize=5.5, zorder=5,
              label="Survey EMC² 2023")
    if reference is not None:
        axes.plot(list(abscisses), _parts(reference["score"], "distance", strates),
                  color=COULEURS_GROUPES[TABULAIRE], linewidth=2.2, marker="s", markersize=5,
                  zorder=3, label=f"{reference['label']} (best tabular here)")
    if minimal is not None:
        axes.plot(list(abscisses), _parts(minimal["score"], "distance", strates),
                  color=COULEURS_GROUPES[MINIMAL], linewidth=2.0, linestyle="--", marker="o",
                  markersize=4.5, zorder=3, label="Gemini 3.5, minimal prompt")
    axes.plot(list(abscisses), _parts(agent["score"], "distance", strates),
              color=COULEURS_GROUPES[EXPERT], linewidth=2.4, marker="o", markersize=5,
              zorder=4, label="Gemini 3.5, expert prompt")

    axes.set_xticks(list(abscisses))
    axes.set_xticklabels([f"{libelle_strate(c)}\n(n={tailles.get(c, 0)})" for c in strates],
                         fontsize=9)
    axes.set_ylabel("Car share (%)")
    axes.set_xlabel("Trip distance")
    axes.set_ylim(0, 100)
    axes.grid(axis="y", color="#e2e0dc")
    axes.set_axisbelow(True)
    for bord in ("top", "right"):
        axes.spines[bord].set_visible(False)
    axes.legend(loc="upper left", fontsize=8.5, frameon=False)
    figure.tight_layout(rect=(0, 0.04, 1, 1))
    if agent["repli"]:
        figure.text(0.012, 0.012, NOTE_REPLI, fontsize=8, color="#55534f")
    return ecrire(figure, sortie, "ch6_distance")


def _planche_modes_dimensions(decideurs: list[dict], sortie: Path, nom: str,
                              modes: list[tuple[str, str]], dimensions: list[str],
                              titre: str) -> list[Path]:
    """Une grille modes x dimensions : où le résidu se loge, strate par strate.

    Quatre courbes par panneau — la cible, l'agent avant et après ingénierie, et la
    méthode tabulaire la plus proche de la cible sur la dimension regardée.
    """
    par_cle = {d["cle"]: d for d in decideurs}
    agent, minimal = par_cle.get("g35_exp"), par_cle.get("g35_min")
    if agent is None:
        logger.error("[ALARME] Aucun score pour gemini-3.5 sous prompt expert : %s non produite", nom)
        return []

    figure, grille = plt.subplots(len(modes), len(dimensions),
                                  figsize=(5.4 * len(dimensions), 3.3 * len(modes)),
                                  squeeze=False)
    for rang, (mode, nom_mode) in enumerate(modes):
        for colonne, dimension in enumerate(dimensions):
            axes = grille[rang][colonne]
            strates, tailles = _strates_ordonnees(agent["score"], dimension)
            abscisses = range(len(strates))
            reference = _meilleure_reference(decideurs, dimension)
            axes.plot(list(abscisses), _parts(agent["score"], dimension, strates, mode, "target"),
                      color="#2b2a28", linewidth=2.4, marker="o", markersize=5, zorder=5,
                      label="Survey EMC² 2023")
            if reference is not None:
                axes.plot(list(abscisses), _parts(reference["score"], dimension, strates, mode),
                          color=COULEURS_GROUPES[TABULAIRE], linewidth=2.0, marker="s",
                          markersize=4.5, zorder=3,
                          label=f"{reference['label']} (best tabular here)")
            if minimal is not None:
                axes.plot(list(abscisses), _parts(minimal["score"], dimension, strates, mode),
                          color=COULEURS_GROUPES[MINIMAL], linewidth=1.8, linestyle="--",
                          marker="o", markersize=4, zorder=3, label="Gemini 3.5, minimal prompt")
            axes.plot(list(abscisses), _parts(agent["score"], dimension, strates, mode),
                      color=COULEURS_GROUPES[EXPERT], linewidth=2.2, marker="o", markersize=4.5,
                      zorder=4, label="Gemini 3.5, expert prompt")

            axes.set_xticks(list(abscisses))
            if dimension == "age":
                axes.set_xticklabels([libelle_strate(c) if i % 2 == 0 else ""
                                      for i, c in enumerate(strates)],
                                     fontsize=7.5, rotation=45, ha="right")
            else:
                axes.set_xticklabels([f"{libelle_strate(c)}\n(n={tailles.get(c, 0)})"
                                      for c in strates], fontsize=7.5, rotation=25, ha="right")
            axes.set_title(f"{nom_mode} · {LIBELLES_DIMENSIONS.get(dimension, dimension)}",
                           fontsize=10, loc="left")
            axes.set_ylabel("Mode share (%)", fontsize=9)
            axes.set_ylim(0, None)
            axes.grid(axis="y", color="#e2e0dc")
            axes.set_axisbelow(True)
            for bord in ("top", "right"):
                axes.spines[bord].set_visible(False)
    grille[0][0].legend(fontsize=7.5, frameon=False, loc="best")

    figure.suptitle(titre, fontsize=11, x=0.012, ha="left")
    figure.tight_layout(rect=(0, 0.02, 1, 0.94))
    if agent["repli"]:
        figure.text(0.012, 0.004, NOTE_REPLI, fontsize=8, color="#55534f")
    return ecrire(figure, sortie, nom)


def figure_residu(decideurs: list[dict], sortie: Path) -> list[Path]:
    """Les deux modes qui portent le résidu, lus par âge et par occupation."""
    return _planche_modes_dimensions(
        decideurs, sortie, "ch6_residu",
        [("transports_collectifs", "Public transport"), ("velo", "Cycling")],
        ["age", "occupation"],
        "Where the residual sits: public transport and cycling by age and occupation,\n"
        "before and after prompt engineering",
    )


def figure_ch99_motif(decideurs: list[dict], sortie: Path) -> list[Path]:
    """Les quatre modes par motif de déplacement : planche d'annexe."""
    return _planche_modes(
        decideurs, sortie, "ch99_modes_motif", "motif",
        "Mode shares by trip purpose, before and after prompt engineering,\n"
        "against the survey and the closest tabular method",
    )


def _planche_modes(decideurs: list[dict], sortie: Path, nom: str, dimension: str,
                   titre: str) -> list[Path]:
    """Les quatre modes d'une même dimension, un panneau par mode.

    La voiture seule cache ce que la consigne fait des modes minoritaires : le vélo
    et les transports collectifs bougent en sens opposés sur les mêmes strates.
    """
    par_cle = {d["cle"]: d for d in decideurs}
    agent, minimal = par_cle.get("g35_exp"), par_cle.get("g35_min")
    if agent is None:
        logger.error("[ALARME] Aucun score pour gemini-3.5 sous prompt expert : %s non produite", nom)
        return []
    strates, tailles = _strates_ordonnees(agent["score"], dimension)
    reference = _meilleure_reference(decideurs, dimension)

    figure, grille = plt.subplots(2, 2, figsize=(10.4, 7.0))
    abscisses = range(len(strates))
    for axes, (mode, nom_mode) in zip(grille.flat, MODES):
        axes.plot(list(abscisses), _parts(agent["score"], dimension, strates, mode, "target"),
                  color="#2b2a28", linewidth=2.4, marker="o", markersize=5, zorder=5,
                  label="Survey EMC² 2023")
        if reference is not None:
            axes.plot(list(abscisses), _parts(reference["score"], dimension, strates, mode),
                      color=COULEURS_GROUPES[TABULAIRE], linewidth=2.0, marker="s",
                      markersize=4.5, zorder=3, label=f"{reference['label']} (best tabular here)")
        if minimal is not None:
            axes.plot(list(abscisses), _parts(minimal["score"], dimension, strates, mode),
                      color=COULEURS_GROUPES[MINIMAL], linewidth=1.8, linestyle="--",
                      marker="o", markersize=4, zorder=3, label="Gemini 3.5, minimal prompt")
        axes.plot(list(abscisses), _parts(agent["score"], dimension, strates, mode),
                  color=COULEURS_GROUPES[EXPERT], linewidth=2.2, marker="o", markersize=4.5,
                  zorder=4, label="Gemini 3.5, expert prompt")

        axes.set_xticks(list(abscisses))
        axes.set_xticklabels([f"{libelle_strate(c)}\n(n={tailles.get(c, 0)})" for c in strates],
                             fontsize=7.5, rotation=25, ha="right")
        axes.set_title(nom_mode, fontsize=10, loc="left")
        axes.set_ylabel("Mode share (%)", fontsize=9)
        axes.set_ylim(0, None)
        axes.grid(axis="y", color="#e2e0dc")
        axes.set_axisbelow(True)
        for bord in ("top", "right"):
            axes.spines[bord].set_visible(False)
    grille.flat[0].legend(fontsize=7.5, frameon=False, loc="upper left")

    figure.suptitle(titre, fontsize=11, x=0.012, ha="left")
    figure.tight_layout(rect=(0, 0.02, 1, 0.94))
    if agent["repli"]:
        figure.text(0.012, 0.004, NOTE_REPLI, fontsize=8, color="#55534f")
    return ecrire(figure, sortie, nom)


def figure_ch99_distance(decideurs: list[dict], sortie: Path) -> list[Path]:
    """Les quatre modes par tranche de distance : la figure des modes du chapitre."""
    return _planche_modes(
        decideurs, sortie, "ch99_modes_distance", "distance",
        "Mode shares by trip distance, before and after prompt engineering,\n"
        "against the survey and the closest tabular method",
    )


def figure_ch99_occupation(decideurs: list[dict], sortie: Path) -> list[Path]:
    """Les quatre modes par occupation : planche d'annexe."""
    return _planche_modes(
        decideurs, sortie, "ch99_modes_occupation", "occupation",
        "Mode shares by occupation, before and after prompt engineering,\n"
        "against the survey and the closest tabular method",
    )


def figure_ch99_dimensions(decideurs: list[dict], sortie: Path) -> list[Path]:
    """La même lecture sur six dimensions, avec le prompt minimal : planche d'annexe."""
    return _planche_parts(
        decideurs, sortie, "ch99_dimensions_voiture",
        ["distance", "motif", "age", "occupation", "lieu_residence", "type_logement"],
        avec_minimal=True,
        titre="Car share by stratum, before and after prompt engineering,\n"
              "against the survey and the closest tabular method",
    )


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
    analyseur.add_argument(
        "--avec-jev", action="store_true",
        help="ajoute les deux bras Jev 1.13 (ticket 096) — quinze décideurs au lieu de treize, "
             "et un cinquième groupe. Réservé à la version alternative du chapitre : le chapitre "
             "de référence en compte treize, et ses légendes le disent.",
    )
    arguments = analyseur.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s : %(message)s")
    if arguments.avec_jev:
        DECIDEURS.extend(DECIDEURS_JEV)
        VARIANTES.update(VARIANTES_JEV)
        NOMS_MODELES.update({"jev-1.13.0": "Jev 1.13 (TypeSafe)"})
        COULEURS_MODELES.update({"jev-1.13.0": COULEURS_GROUPES[JEV]})
        logger.info("Deux bras Jev versés : %d décideurs, %d porteurs de consigne",
                    len(DECIDEURS), len(VARIANTES))
    depart = time.monotonic()
    logger.info("Figures du chapitre 6 : lecture des scores du dépôt")

    decideurs = lire_decideurs()
    if not decideurs:
        logger.error("[ALARME] Aucun décideur lisible : aucune figure produite")
        return 1

    tabulaires = [d["composite"] for d in decideurs if d["groupe"] == TABULAIRE]
    ecrits = []
    ecrits += figure_echelle(decideurs, arguments.sortie)
    ecrits += figure_ingenierie(arguments.sortie, tabulaires)
    ecrits += figure_distance_voiture(decideurs, arguments.sortie)
    ecrits += figure_ch99_distance(decideurs, arguments.sortie)
    ecrits += figure_residu(decideurs, arguments.sortie)
    ecrits += figure_ch99_dimensions(decideurs, arguments.sortie)
    ecrits += figure_ch99_occupation(decideurs, arguments.sortie)
    ecrits += figure_ch99_motif(decideurs, arguments.sortie)
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
