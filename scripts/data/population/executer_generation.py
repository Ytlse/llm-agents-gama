#!/usr/bin/env python3
"""Ticket 074, C-1 — exécute `generate_population.ipynb` ÉTAPE PAR ÉTAPE, hors notebook.

Pourquoi pas `papermill` : il joue le carnet d'un bout à l'autre. Or la chaîne dure des heures,
ses étapes ont des coûts très inégaux (eqasim, routage, réchauffage OSMnx), et la moitié d'entre
elles écrasent des checkpoints. On veut pouvoir s'arrêter après chacune, lire son bilan, et
décider de la suivante — c'est aussi ce que la revue humaine demande.

Les cellules de code sont exécutées **dans un seul espace de noms**, dans l'ordre, exactement
comme le carnet : les variables d'une étape servent à la suivante. Les paramètres de la cellule 2
sont remplacés par ceux passés en ligne de commande, et le remplacement est JOURNALISÉ — un
paramètre changé en silence est la façon la plus simple de sceller une cohorte sous un cadre que
personne n'a voulu (c'est arrivé le 2026-09-03, une v2 exportée sous un nom v3).

    cd scripts/data/population
    ../../../services/llm-agents/.venv/bin/python executer_generation.py --jusqu-a 1
    ../../../services/llm-agents/.venv/bin/python executer_generation.py --de 2 --jusqu-a 3ter
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ICI = Path(__file__).resolve().parent
CARNET = ICI / "generate_population.ipynb"

# Ce que l'étape 3ter POSE dans l'espace de noms et dont tout l'aval dépend :
# `POPULATION_SIZES = [SELECT_N]` et `POPULATION_TAG = SELECT_TAG`. Dans le carnet,
# ces valeurs survivent parce que le noyau ne meurt pas. Ici, une reprise à l'étape 4
# repart d'un espace de noms neuf — et `pop_filename()` rend alors le nom du VIVIER.
#
# Ce n'est pas une erreur bruyante : l'étape 4 se met à router les 33 420 paires du
# vivier entier au lieu des ~4 000 des retenus, pendant des heures, et l'étape 7
# exporterait le vivier sous le nom de la cohorte. C'est arrivé le 2026-09-14.
# L'état est donc ÉCRIT après 3ter et RELU à la reprise, en le disant.
ETAT = ICI / "Temp" / ".etat_generation.json"
ETAT_CHAMPS = ("POPULATION_SIZES", "POPULATION_TAG", "SELECT_N", "SELECT_TAG")

# Nom d'étape → indice de la cellule de CODE qui la porte, dans l'ordre du carnet.
# Relevé sur le carnet du 2026-09-14 ; `--lister` réaffiche la table telle qu'elle est lue,
# de sorte qu'un décalage se voie avant de lancer trois heures de calcul.
ETAPES: dict[str, int] = {
    "prelude": 1,        # certifi
    "parametres": 2,
    "chemins": 4,
    "imports": 6,
    "sante": 8,
    "1": 10,             # eqasim → Temp/1_raw
    "2": 12,             # validation des activités → Temp/2_fixed
    "3": 14,             # transports en commun → Temp/3_pt_enriched
    "3bis": 16,          # zone AAV2020 + densité → Temp/4_zone_enriched
    "3ter": 18,          # sélection stratifiée
    "4": 20,             # temps de trajet + horaires → Temp/5_scheduled
    "5": 22,             # fusionnée avec 4
    "6": 24,             # réchauffage OSMnx
    "export": 26,
    "7": 28,             # export final → data/population/
    "8": 30,             # traits imputés EMC²
    "9": 32,             # audit de complétude
}
ORDRE = list(ETAPES)


def _cellules_code(carnet: dict) -> list[str]:
    """Les sources des cellules, indexées comme dans le carnet (markdown → chaîne vide)."""
    return ["".join(c["source"]) if c["cell_type"] == "code" else ""
            for c in carnet["cells"]]


def _remplacer_parametres(source: str, valeurs: dict[str, str]) -> tuple[str, list[str]]:
    """Réécrit les affectations de premier niveau nommées dans `valeurs`. Rend les lignes changées."""
    lignes = source.splitlines()
    changees: list[str] = []
    restants = dict(valeurs)
    for i, ligne in enumerate(lignes):
        nu = ligne.strip()
        if not nu or nu.startswith("#"):
            continue
        nom = nu.split("=", 1)[0].strip() if "=" in nu else ""
        if nom in restants:
            commentaire = ""
            if "#" in ligne:
                commentaire = "  " + ligne[ligne.index("#"):]
            lignes[i] = f"{nom} = {restants[nom]}{commentaire}"
            changees.append(f"{nom} : {nu.split('=', 1)[1].split('#')[0].strip()} → "
                            f"{restants[nom]}")
            del restants[nom]
    if restants:
        raise SystemExit(
            f"REFUSÉ — paramètre(s) introuvable(s) dans la cellule de paramètres : "
            f"{sorted(restants)}. Le carnet a changé ; vérifier avant de lancer."
        )
    return "\n".join(lignes), changees


def _ecrire_etat(espace: dict) -> None:
    """Consigne ce que 3ter vient de poser, pour qu'une reprise le retrouve."""
    etat = {champ: espace.get(champ) for champ in ETAT_CHAMPS}
    ETAT.parent.mkdir(parents=True, exist_ok=True)
    ETAT.write_text(json.dumps(etat, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"── état de sélection consigné dans {ETAT.name} : "
          f"POPULATION_SIZES={etat['POPULATION_SIZES']} POPULATION_TAG="
          f"{etat['POPULATION_TAG']!r}")


def _etat_a_injecter(de: str, deja_passes: dict[str, str]) -> dict[str, str]:
    """Valeurs posées par 3ter à réinjecter quand on reprend APRÈS elle.

    Refuse plutôt que de deviner : sans état consigné, une reprise à l'étape 4 travaille
    sur le vivier en croyant travailler sur la cohorte, et rien ne le dit.
    """
    if ORDRE.index(de) <= ORDRE.index("3ter"):
        return {}
    # Les avoir passés à la main vaut état : c'est la sortie de secours que le refus
    # ci-dessous propose, et elle doit marcher.
    if {"POPULATION_SIZES", "POPULATION_TAG"} <= set(deja_passes):
        return {}
    if not ETAT.exists():
        raise SystemExit(
            f"REFUSÉ — reprise à l'étape {de} sans état de sélection ({ETAT}).\n"
            "L'étape 3ter pose POPULATION_SIZES et POPULATION_TAG ; sans eux, l'aval "
            "routerait et exporterait le VIVIER sous le nom de la cohorte.\n"
            "Rejouer 3ter, ou passer les valeurs à la main :\n"
            "    --param \"POPULATION_SIZES=[1000]\" --param \"POPULATION_TAG='AAMAS_v6'\"")
    etat = json.loads(ETAT.read_text(encoding="utf-8"))
    injecte = {c: repr(etat[c]) for c in ETAT_CHAMPS
               if etat.get(c) is not None and c not in deja_passes}
    if injecte:
        print(f"── reprise après 3ter : état relu dans {ETAT.name}")
    return injecte


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--de", default="prelude", help=f"première étape ({'|'.join(ORDRE)})")
    p.add_argument("--jusqu-a", dest="jusqu_a", default="1", help="dernière étape incluse")
    p.add_argument("--param", action="append", default=[], metavar="NOM=VALEUR",
                   help="remplace un paramètre de la cellule 2 (répétable)")
    p.add_argument("--lister", action="store_true", help="affiche la table des étapes et sort")
    a = p.parse_args(argv)

    carnet = json.loads(CARNET.read_text(encoding="utf-8"))
    sources = _cellules_code(carnet)

    if a.lister:
        print(f"{'étape':10s} {'cellule':>7s}  première ligne de code")
        for nom, idx in ETAPES.items():
            tete = next((l for l in sources[idx].splitlines()
                         if l.strip() and not l.strip().startswith("#")), "(vide)")
            print(f"{nom:10s} {idx:7d}  {tete[:80]}")
        return 0

    for nom in (a.de, a.jusqu_a):
        if nom not in ETAPES:
            raise SystemExit(f"étape inconnue : {nom!r} (connues : {', '.join(ORDRE)})")
    debut, fin = ORDRE.index(a.de), ORDRE.index(a.jusqu_a)
    if debut > fin:
        raise SystemExit(f"--de {a.de} vient après --jusqu-a {a.jusqu_a}")

    valeurs = dict(v.split("=", 1) for v in a.param)

    # Les cellules d'amorce (paramètres, chemins, imports) sont TOUJOURS rejouées : elles ne
    # coûtent rien et sans elles l'espace de noms est vide. Ne pas les rejouer reviendrait à
    # reprendre au milieu d'une phrase.
    amorce = [ETAPES[n] for n in ("prelude", "parametres", "chemins", "imports")]
    a_jouer = amorce + [ETAPES[n] for n in ORDRE[debut:fin + 1] if ETAPES[n] not in amorce]

    print("=" * 88)
    print(f"Génération de population — étapes {a.de} → {a.jusqu_a}"
          f"   ({datetime.now(timezone.utc).isoformat(timespec='seconds')})")
    print("=" * 88)

    espace: dict = {"__name__": "__main__"}
    reprise = _etat_a_injecter(a.de, valeurs)
    depart_total = time.time()
    for idx in a_jouer:
        source = sources[idx]
        if not source.strip():
            continue
        etiquette = next((n for n, i in ETAPES.items() if i == idx), f"cellule {idx}")
        if idx == ETAPES["parametres"] and (valeurs or reprise):
            source, changees = _remplacer_parametres(source, {**reprise, **valeurs})
            print(f"\n── paramètres remplacés ({len(changees)}) ──")
            for c in changees:
                print(f"   {c}")
        print(f"\n{'─' * 88}\n── étape {etiquette} (cellule {idx}) ──")
        depart = time.time()
        try:
            exec(compile(source, f"<carnet:cellule {idx}>", "exec"), espace)
        except Exception:
            print(f"\n[ALARME] étape {etiquette} INTERROMPUE après "
                  f"{time.time() - depart:.0f} s :", file=sys.stderr)
            traceback.print_exc()
            return 1
        print(f"── étape {etiquette} terminée en {time.time() - depart:.0f} s")
        if etiquette == "3ter":
            _ecrire_etat(espace)

    print(f"\n{'=' * 88}")
    print(f"Étapes {a.de} → {a.jusqu_a} : SUCCÈS, en {time.time() - depart_total:.0f} s "
          f"({datetime.now(timezone.utc).isoformat(timespec='seconds')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
