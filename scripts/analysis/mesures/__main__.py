"""`python -m scripts.analysis.mesures <run>` — recalcule et réécrit les CSV d'un run."""

from __future__ import annotations

import argparse
from pathlib import Path

from scripts.analysis.mesures.calcul import calculer
from scripts.analysis.mesures.ecriture import ecrire


def main(argv=None) -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("run", type=Path, help="répertoire du run")
    parseur.add_argument("-o", "--sortie", type=Path, default=None,
                         help="répertoire des CSV (défaut : <run>/mesures)")
    args = parseur.parse_args(argv)

    mesures = calculer(args.run)
    chemins = ecrire(mesures, args.sortie)

    jours = mesures.journees
    print(f"{len(jours)} journée(s) vécue(s)"
          + (f", du jour {jours[0].index} au jour {jours[-1].index}" if jours else "")
          + f" · {mesures.trajets_rejoues} trajet(s) et {mesures.rappels_rejoues} rappel(s)"
          " rejoué(s) écarté(s)")
    if not mesures.operations_tracees:
        print("  ⚠ operations_concept.jsonl absent : les colonnes d'opérations restent VIDES "
              "(et non à zéro — « aucune contradiction » n'est pas « on ne mesure pas »).")
    for nom, chemin in chemins.items():
        lignes = max(0, len(chemin.read_text(encoding="utf-8").splitlines()) - 1)
        print(f"  {nom:16s} {lignes:>5} ligne(s) → {chemin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
