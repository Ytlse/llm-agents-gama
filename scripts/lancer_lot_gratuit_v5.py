#!/usr/bin/env python3
"""Ticket 045 — joue les quatorze exécutions gratuites du lot 4a/4b/4e sur la cohorte v5.

Sept bras × deux conditions de chaîne. **Aucun appel de modèle de langue**, aucun quota.

**Deux chemins d'exécution, et ce n'est pas une commodité.**

Douze bras tournent dans le conteneur `controller`, comme tout le reste de la plateforme.
Les deux bras du **témoin random forest** tournent sur l'**hôte**, et c'est forcé :

- le témoin ne sérialise aucun arbre. Il se **réajuste** au chargement depuis sa matrice, puis
  vérifie qu'il reproduit les métriques publiées (ticket 044) ;
- le conteneur porte scikit-learn 1.9.0, l'artefact a été estimé sous 1.8.0. La forêt
  réajustée y diffère — exactitude à 1,9·10⁻⁴, entropie croisée à 8,0·10⁻⁴ — et le garde-fou
  **refuse**, à juste titre : ce n'est plus la forêt du tableau publié.

On ne desserre pas la tolérance, on change d'environnement. L'hôte porte 1.8.0, la forêt y est
celle des métriques. **L'écart d'environnement est déclaré**, pas dissimulé : il est écrit dans
le compte rendu de ce script et vaut pour les deux bras du témoin, pour aucun autre.

Le témoin n'est par ailleurs **pas câblé** comme les trois arbitres (règle R7 du ticket 044 :
un témoin ne devient pas un arbitre). Son lanceur dédié inscrit sa famille et remplace
`load_policy` dans le seul espace de noms du décideur, pour la durée du processus.

Usage :
    python scripts/lancer_lot_gratuit_v5.py --lister      # dit ce qui serait joué
    python scripts/lancer_lot_gratuit_v5.py --conteneur   # les 12 bras du conteneur
    python scripts/lancer_lot_gratuit_v5.py --temoin      # les 2 bras du témoin, sur l'hôte
    python scripts/lancer_lot_gratuit_v5.py               # les deux, dans cet ordre
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[1]
EXPERIENCES = RACINE / "data" / "experiences"
FORMAT_TEMOIN = "rf_mode_choice_policy"
ARTEFACT_TEMOIN = "rf_mode_choice_policy.json"


def _definitions() -> list[tuple[str, dict]]:
    """(nom, définition) de toutes les expériences en place, triées par nom."""
    out = []
    for d in sorted(EXPERIENCES.iterdir()) if EXPERIENCES.is_dir() else []:
        f = d / "experience.yaml"
        if not f.is_file() or d.name.startswith("archive"):
            continue
        e = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        out.append((d.name, e))
    return out


def _est_temoin(exp: dict) -> bool:
    return ARTEFACT_TEMOIN in str((exp.get("decideur") or {}).get("artefact") or "")


def _deja_jouee(nom: str) -> bool:
    """Une exécution close existe déjà — on ne la rejoue pas en silence."""
    execs = EXPERIENCES / nom / "executions"
    if not execs.is_dir():
        return False
    return any((e / "synthese.json").is_file() for e in execs.iterdir() if e.is_dir())


def _lancer_conteneur(nom: str) -> tuple[bool, str]:
    r = subprocess.run(
        ["make", "experience-lancer", f"EXP={nom}"],
        cwd=RACINE, capture_output=True, text=True, check=False,
    )
    lignes = [l for l in (r.stdout + r.stderr).splitlines() if l.strip()]
    return r.returncode == 0, (lignes[-1] if lignes else "")


def _lancer_temoin(nom: str) -> tuple[bool, str]:
    """Sur l'HÔTE, famille du témoin ouverte pour ce processus seulement."""
    if str(RACINE / "services" / "llm-agents") not in sys.path:
        sys.path.insert(0, str(RACINE / "services" / "llm-agents"))
    if str(RACINE) not in sys.path:
        sys.path.insert(0, str(RACINE))
    from scripts.progedo_logit.lancer_experience_rf import (
        _chemin_population_hote,
        enregistrer_famille_rf,
    )

    # Le chemin de population est celui du CONTENEUR dans la définition : on le ramène côté
    # hôte. Le `population.json` est le même fichier des deux côtés du bind, et c'est son SHA
    # qui fait l'identité — la substitution ne change donc aucune empreinte.
    _chemin_population_hote(EXPERIENCES / nom / "experience.yaml")
    enregistrer_famille_rf()
    from experiences import cli

    code = cli.main(["lancer", "--experience", nom, "--ne-pas-attendre-fenetre"])
    return code == 0, f"code de sortie {code}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lister", action="store_true", help="dit ce qui serait joué, sans rien lancer")
    ap.add_argument("--conteneur", action="store_true", help="les bras du conteneur seulement")
    ap.add_argument("--temoin", action="store_true", help="les bras du témoin seulement (hôte)")
    ap.add_argument("--rejouer", action="store_true", help="rejoue même une expérience déjà close")
    a = ap.parse_args()

    toutes = _definitions()
    if not toutes:
        print("Aucune définition dans data/experiences — lancez d'abord "
              "`python scripts/definir_lot_gratuit_v5.py`.")
        return 1

    temoins = [(n, e) for n, e in toutes if _est_temoin(e)]
    autres = [(n, e) for n, e in toutes if not _est_temoin(e)]
    faire_conteneur = a.conteneur or not (a.conteneur or a.temoin)
    faire_temoin = a.temoin or not (a.conteneur or a.temoin)

    print(f"{len(toutes)} définitions · {len(autres)} dans le conteneur · "
          f"{len(temoins)} sur l'hôte (témoin random forest)\n")

    lots = []
    if faire_conteneur:
        lots.append(("conteneur", autres, _lancer_conteneur))
    if faire_temoin:
        lots.append(("hôte (témoin)", temoins, _lancer_temoin))

    echecs = sautees = 0
    for ou, lot, lanceur in lots:
        if not lot:
            continue
        print(f"── {ou} ──")
        for nom, _e in lot:
            if _deja_jouee(nom) and not a.rejouer:
                print(f"  · {nom} — déjà close, sautée (`--rejouer` pour forcer)")
                sautees += 1
                continue
            if a.lister:
                print(f"  → {nom}")
                continue
            t0 = time.monotonic()
            ok, dernier = lanceur(nom)
            duree = time.monotonic() - t0
            print(f"  {'✓' if ok else '✗'} {nom}  ({duree:.0f} s)  {dernier[:80]}")
            if not ok:
                echecs += 1
        print()

    if not a.lister:
        joue = sum(len(l) for _, l, _ in lots) - sautees - echecs
        print(f"{joue} exécution(s) menée(s), {echecs} en échec, {sautees} sautée(s).")
        if temoins and faire_temoin:
            print(
                "\nÀ DÉCLARER dans le compte rendu : les deux bras du témoin random forest ont "
                "tourné sur l'HÔTE (scikit-learn 1.8.0) et non dans le conteneur (1.9.0), parce "
                "que la forêt s'y réajuste et que son garde-fou refuse une forêt qui ne "
                "reproduit pas les métriques publiées. Les douze autres bras ont tourné dans le "
                "conteneur."
            )
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
