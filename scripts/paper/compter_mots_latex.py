#!/usr/bin/env python3
"""Compte les mots du corps d'un résumé LaTeX — le seul décompte qui fait foi.

Le corps est ce que délimite `\\begin{abstract}` … `\\end{abstract}`. Les notes de
bas de page en sont retirées (elles ne comptent pas dans la limite des GAMA Days),
les séparateurs `\\\\` aussi, et les commandes LaTeX sont effacées en gardant le
contenu de leurs accolades : `EMC\\textsuperscript{2}` vaut un mot, `100\\,\\%` aussi.

Usage : python3 scripts/paper/compter_mots_latex.py docs/paper/gama_days/GAMA_DAYS_ABSTRACT_EN_TEX.md
"""

import argparse
import re
import sys
from pathlib import Path


def retirer_notes(texte: str) -> str:
    """Retire chaque \\footnote{...} en suivant l'appariement des accolades."""
    morceaux, i, retirees = [], 0, 0
    while i < len(texte):
        debut = texte.find(r"\footnote{", i)
        if debut < 0:
            morceaux.append(texte[i:])
            break
        morceaux.append(texte[i:debut])
        curseur, profondeur = debut + len(r"\footnote{"), 1
        while curseur < len(texte) and profondeur:
            profondeur += (texte[curseur] == "{") - (texte[curseur] == "}")
            curseur += 1
        if profondeur:
            raise ValueError(f"accolade de \\footnote non fermée à l'offset {debut}")
        retirees += 1
        i = curseur
    print(f"notes de bas de page retirées : {retirees}", file=sys.stderr)
    return "".join(morceaux)


def compter(chemin: Path) -> int:
    source = chemin.read_text(encoding="utf-8")
    if r"\begin{abstract}" not in source or r"\end{abstract}" not in source:
        raise SystemExit(f"{chemin} : aucun environnement abstract trouvé")
    corps = source.split(r"\begin{abstract}")[1].split(r"\end{abstract}")[0]
    corps = retirer_notes(corps)
    corps = re.sub(r"\\\\+", " ", corps)
    corps = re.sub(r"\\[a-zA-Z]+\*?", "", corps)
    corps = corps.replace("{", "").replace("}", "")
    return len(corps.split())


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("source", type=Path, help="fichier .tex (ou .md porteur du LaTeX)")
    parseur.add_argument("--limite", type=int, default=None, help="limite à ne pas dépasser")
    arguments = parseur.parse_args()

    total = compter(arguments.source)
    print(f"{total} mots — {arguments.source}")
    if arguments.limite is not None and total > arguments.limite:
        print(f"[ALARME] {total} mots pour une limite de {arguments.limite}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
