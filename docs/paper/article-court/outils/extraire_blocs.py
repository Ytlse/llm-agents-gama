#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sort d'une section de l'article court le texte à confier à un traducteur externe.

La traduction ne passe pas par un modèle de langue : elle se fait dehors, dans l'outil de
votre choix, et revient telle quelle. Ce script prépare le texte à coller, et le modèle de
document qui permettra de le reposer exactement là où il a été pris.

Il écrit deux choses dans `traductions/` :

  <slug>.a-traduire.txt        le texte, blocs numérotés `[[n]]`, découpé en parties si besoin
  <slug>.modele.json           la structure du fichier source, pour l'injection

Ce qui ne part PAS chez le traducteur : les commentaires `<!-- source: … -->` (déjà en
français), le bloc de compte-rendu, les maths, les cellules numériques des tableaux.

Usage :
    extraire_blocs.py sections/01_introduction.en.md
    extraire_blocs.py --section 01 [--decouper 4500] [--sans-balises]

Sort en code 1 si la section est introuvable ou vide.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from modele_document import Document, compter_mots, lire, unites_traduisibles  # noqa: E402

RACINE = Path(__file__).resolve().parent.parent
SECTIONS = RACINE / "sections"
TRADUCTIONS = RACINE / "traductions"

# Limite de la fenêtre de saisie de DeepL gratuit. Un lot plus long se coupe en parties,
# sur une frontière de bloc — jamais au milieu d'un paragraphe.
SIGNES_PAR_PARTIE = 4500


def trouver_section(designation: str) -> Path:
    """Accepte un chemin, ou le seul numéro de section ('01', '1')."""
    candidat = Path(designation)
    if candidat.is_file():
        return candidat
    numero = designation.strip().lstrip("0") or "0"
    for f in sorted(SECTIONS.glob("*.en.md")):
        if (f.name.split("_")[0].lstrip("0") or "0") == numero:
            return f
    raise SystemExit(f"ERREUR : aucune section ne correspond à « {designation} » dans {SECTIONS}")


def composer_lot(unites: list[tuple[str, str]], balises: bool) -> str:
    if balises:
        return "\n\n".join(f"[[{ident}]]\n{texte}" for ident, texte in unites) + "\n"
    return "\n\n".join(texte for _, texte in unites) + "\n"


def decouper(unites: list[tuple[str, str]], balises: bool, limite: int) -> list[str]:
    """Coupe en parties équilibrées, toujours sur une frontière de bloc.

    Le découpage vise `total / nombre de parties` plutôt que la limite brute : sans cela un
    lot de 9 205 signes sortait en 4 163 + 4 354 + 686, et une queue de 686 signes se
    oublie. Il sort ici trois parties d'environ 3 070.
    """
    total = len(composer_lot(unites, balises))
    parts = max(1, -(-total // limite))
    limite = -(-total // parts) + 40  # marge pour les en-têtes de bloc
    parties, courante, taille = [], [], 0
    for unite in unites:
        morceau = composer_lot([unite], balises)
        # Jamais plus de `parts` parties : une fois la dernière ouverte, on la remplit
        # jusqu'au bout plutôt que d'en créer une de deux cents signes qu'on oubliera.
        derniere = len(parties) == parts - 1
        if courante and not derniere and taille + len(morceau) > limite:
            parties.append(composer_lot(courante, balises))
            courante, taille = [], 0
        courante.append(unite)
        taille += len(morceau)
    if courante:
        parties.append(composer_lot(courante, balises))
    return parties


def main() -> int:
    debut = time.time()
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("fichier", nargs="?", help="chemin de la section, ou rien avec --section")
    p.add_argument("--section", "-s", help="numéro de section, par exemple 01")
    p.add_argument("--decouper", type=int, default=SIGNES_PAR_PARTIE,
                   help=f"signes par partie (défaut {SIGNES_PAR_PARTIE}, 0 pour ne pas couper)")
    p.add_argument("--sans-balises", action="store_true",
                   help="lot sans les repères [[n]] ; l'injection se recalera sur l'ordre des blocs")
    args = p.parse_args()

    if not args.fichier and not args.section:
        p.error("donnez un fichier ou --section")
    source = trouver_section(args.fichier or args.section)

    print(f"[extraction] lecture de {source}")
    doc = lire(source)
    unites = unites_traduisibles(doc)
    if not unites:
        print(f"ERREUR : aucun bloc traduisible dans {source}", file=sys.stderr)
        return 1

    slug = source.name.replace(".en.md", "")
    TRADUCTIONS.mkdir(exist_ok=True)
    modele = TRADUCTIONS / f"{slug}.modele.json"
    modele.write_text(doc.en_json(), encoding="utf-8")

    balises = not args.sans_balises
    entier = composer_lot(unites, balises)
    parties = ([entier] if not args.decouper or len(entier) <= args.decouper
               else decouper(unites, balises, args.decouper))

    ecrits = []
    if len(parties) == 1:
        cible = TRADUCTIONS / f"{slug}.a-traduire.txt"
        cible.write_text(parties[0], encoding="utf-8")
        ecrits.append(cible)
    else:
        for n, partie in enumerate(parties, 1):
            cible = TRADUCTIONS / f"{slug}.a-traduire.partie{n}.txt"
            cible.write_text(partie, encoding="utf-8")
            ecrits.append(cible)

    genres = {}
    for b in doc.blocs:
        genres[b.genre] = genres.get(b.genre, 0) + 1
    detail = ", ".join(f"{v} {k}" for k, v in sorted(genres.items()))

    print(f"[extraction] {len(doc.blocs)} blocs lus : {detail}")
    print(f"[extraction] {len(unites)} unités traduisibles, {compter_mots(doc)} mots, "
          f"{len(entier)} signes")
    print(f"[extraction] modèle écrit : {modele.relative_to(RACINE)}")
    for f in ecrits:
        print(f"[extraction] lot à traduire : {f.relative_to(RACINE)} ({len(f.read_text())} signes)")
    print(f"[extraction] terminé en {time.time() - debut:.2f} s — "
          f"{len(ecrits)} fichier(s) à passer au traducteur")
    return 0


if __name__ == "__main__":
    sys.exit(main())
