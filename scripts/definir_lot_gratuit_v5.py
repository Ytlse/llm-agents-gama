#!/usr/bin/env python3
"""Ticket 045, lots 4a, 4b et 4e — les quatorze définitions gratuites sur la cohorte v5.

Sept bras, joués **deux fois** : chaîne des véhicules active (le nominal) et coupée. Quatorze
exécutions, **aucun appel de modèle de langue**. L'écart entre les deux lignes chiffre ce que
la contrainte de chaîne impose à un décideur qui ne l'anticipe pas.

| Condition | Bras |
|---|---|
| chaîne active | 3 planchers + 4 familles statistiques |
| chaîne coupée | les mêmes 7 |

Ce que ces définitions fixent, et pourquoi.

**Une seule politique de calendrier pour toute la campagne.** Les définitions v1 mélangeaient
`commune` pour les planchers et `aleatoire` pour les modèles. La différence était **inerte** —
la météo n'entre dans aucune des 21 variables du contrat, ni dans un décideur local — mais elle
obligeait à l'expliquer à chaque comparaison. Tout passe en `aleatoire`, graine 42, comme les
bras LLM à venir : une seule politique, rien à justifier.

**Aucune variante de prompt pour un décideur qui n'en envoie pas.** Les définitions v1 des
décideurs-modèles portaient `gabarit.variante: minimal_persona`, si bien que leur synthèse
annonçait `gabarit.invalide: true` — le prompt ayant été invalidé le 10 septembre — pour une
mesure qui n'a jamais servi de prompt. Le drapeau était du bruit, et il refusait une mesure
saine. Ici `variante: null` : un décideur local ou modèle n'a pas de gabarit.

**Les bras LLM ne sont PAS dans ce lot.** Ils se jouent en chaîne active uniquement (R14), et
seulement après le balayage.

Usage :
    python scripts/definir_lot_gratuit_v5.py --verifier   # écrit les YAML, n'enregistre rien
    python scripts/definir_lot_gratuit_v5.py              # écrit et enregistre via `definir`
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[1]
# Sous `data/experiences/`, seul dossier de `data/` monté dans le conteneur où écrire ait un
# sens (`/app/data` n'est pas un montage unique, seuls des sous-chemins le sont). Le point
# initial le tient hors des listages : `experiences()` et `lister()` exigent un
# `experience.yaml` à la racine du dossier, qu'un dossier de brouillons n'a pas.
BROUILLONS = RACINE / "data" / "experiences" / ".brouillons_lot_gratuit_v5"
BROUILLONS_CONTENEUR = "/app/data/experiences/.brouillons_lot_gratuit_v5"

POPULATION = "/data/eqasim-output/population_1000_AAMAS_v5"
JEU = "population_1000_AAMAS_v5_20260316"
JOUR = "2026-03-16"

TOLERANCES = {
    "walk": "insensible",
    "bike": "insensible",
    "car": "heure",
    "transit": {"pas_min": 10},
    "rail": {"pas_min": 10},
}

# Lot 4a — planchers et heuristiques physiques.
PLANCHERS = [
    ("aleatoire", {"type": "aleatoire", "graine": 42}),
    ("duree_minimale", {"type": "duree_minimale"}),
    ("majoritaire_voiture", {"type": "majoritaire_voiture"}),
]

# Lot 4b — les quatre familles de référence. La régression à noyau en fait partie : l'auteur
# l'a demandée explicitement, et son artefact n'a pas changé depuis son exécution v1.
FAMILLES = [
    ("lgbm", "scripts/progedo_logit/mode_choice_policy.json"),
    ("mnl", "scripts/progedo_logit/mnl_model.json"),
    ("klr", "scripts/progedo_logit/klr_model.json"),
    ("rf", "scripts/progedo_logit/rf_mode_choice_policy.json"),
]

# Lot 4e — les deux conditions de chaîne. Le lot 1 du ticket 040 et RIEN d'autre : position du
# véhicule et verrou de retour. Jamais la possession, le permis ni l'âge, qui sont des
# attributs de la personne présents dans les 21 variables du contrat.
CONDITIONS = [
    ("chaîne active", {"vehicule_chaine": True, "verrou_retour": True}),
    ("chaîne coupée", {"vehicule_chaine": False, "verrou_retour": False}),
]


def _nom_calcule(d: dict) -> str:
    """Le nom canonique, calculé ICI et écrit dans la définition.

    `definir --accepter-nom` ne recalcule rien : il ACCEPTE un nom hors convention. Le nom
    doit donc être juste avant d'y arriver — et il l'est, puisque c'est la même fonction qui
    le calcule des deux côtés.
    """
    if str(RACINE / "services" / "llm-agents") not in sys.path:
        sys.path.insert(0, str(RACINE / "services" / "llm-agents"))
    from experiences.nommage import nom_canonique

    return nom_canonique(d)


def definition(decideur: dict, chaine: dict) -> dict:
    """Une définition complète — aucun champ n'est laissé au hasard (règle E1)."""
    return {
        "nom": "",  # rempli par `_nom_calcule` une fois le reste connu (N1)
        "population": {"chemin": POPULATION},
        "jeu": {"nom": JEU, "dossier": None},
        # Pas de variante : ni un décideur local ni un décideur modèle n'envoie de prompt.
        "gabarit": {"categorie": "itinary_multi_agent", "variante": None},
        "decideur": {
            "type": decideur["type"],
            "modele": None,
            "parametres": {},
            "rejeu_de": None,
            "graine": decideur.get("graine"),
            "artefact": decideur.get("artefact"),
        },
        "mode": "sans_simulateur",
        "calendrier": {"politique": "aleatoire", "date": JOUR, "graine": 42},
        "horizon_jours": 1,
        "memoire": False,
        "evenements": [],
        "graine_ordre": 42,
        "graine_tirage": 42,
        "regroupement": {"parallelisme": 8},
        "tolerances_horaires": TOLERANCES,
        "max_candidats": 6,
        "attente_max_s": 120,
        "vehicule_chaine": chaine["vehicule_chaine"],
        "verrou_retour": chaine["verrou_retour"],
        "derive_de": None,
    }


def bras() -> list[tuple[str, dict]]:
    """Les sept bras, chacun en deux conditions : quatorze définitions, chacune nommée."""
    sortie = []
    for etiquette, dec in PLANCHERS:
        for nom_cond, chaine in CONDITIONS:
            sortie.append((f"{etiquette} · {nom_cond}", definition(dec, chaine)))
    for etiquette, artefact in FAMILLES:
        dec = {"type": "modele", "artefact": artefact}
        for nom_cond, chaine in CONDITIONS:
            sortie.append((f"{etiquette} · {nom_cond}", definition(dec, chaine)))
    for _etiquette, d in sortie:
        d["nom"] = _nom_calcule(d)
    noms = [d["nom"] for _e, d in sortie]
    # Deux bras qui porteraient le même nom partageraient le même dossier d'archives : c'est
    # exactement ce que le ticket 045 corrige ailleurs, on ne le réintroduit pas ici.
    doublons = {n for n in noms if noms.count(n) > 1}
    if doublons:
        raise SystemExit(f"noms en double, la campagne serait ambiguë : {sorted(doublons)}")
    return sortie


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--verifier",
        action="store_true",
        help="écrit les brouillons YAML sans les enregistrer dans la plateforme",
    )
    a = ap.parse_args()

    BROUILLONS.mkdir(parents=True, exist_ok=True)
    toutes = bras()
    print(f"{len(toutes)} définitions — 7 bras × 2 conditions de chaîne, toutes GRATUITES\n")

    echecs = 0
    for i, (etiquette, d) in enumerate(toutes, 1):
        fichier = BROUILLONS / f"{i:02d}.yaml"
        fichier.write_text(
            yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        if a.verifier:
            print(f"  [{i:2d}] {etiquette}")
            continue
        # `definir` calcule le nom, valide, et range dans data/experiences/<nom>/.
        chemin_conteneur = f"{BROUILLONS_CONTENEUR}/{fichier.name}"
        r = subprocess.run(
            [
                "docker", "compose", "exec", "-T",
                "-e", "EXPERIENCES_DIR=/app/data/experiences",
                "-e", "JEUX_DIR=/app/data/jeux",
                "controller", "python", "-m", "experiences",
                "definir", chemin_conteneur, "--accepter-nom",
            ],
            cwd=RACINE, capture_output=True, text=True, check=False,
        )
        ligne = (r.stdout or r.stderr or "").strip().splitlines()
        dernier = ligne[-1] if ligne else ""
        etat = "✓" if r.returncode == 0 else "✗"
        if r.returncode != 0:
            echecs += 1
        print(f"  {etat} [{i:2d}] {etiquette:34s} {dernier[:90]}")

    if not a.verifier:
        print(f"\n{len(toutes) - echecs} enregistrée(s), {echecs} en échec.")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
