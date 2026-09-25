#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Repose un texte traduit de l'extérieur dans la structure de son master anglais.

Le français de l'article court est un rendu, pas une source (consigne R17). Ce script
garantit que le rendu ne bouge que là où la langue bouge : mêmes coupes de paragraphe,
mêmes commentaires de source, mêmes chiffres, même ordre. Rien n'est réécrit, rien n'est
amélioré au passage.

Deux formes d'entrée sont acceptées :
  * lot balisé   — les lignes `[[n]]` produites par extraire_blocs.py ont survécu ;
  * texte nu     — le traducteur les a mangées : le recalage se fait sur l'ordre des blocs,
                   et le script refuse d'écrire si les comptes ne tombent pas juste.

Usage :
    injecter_traduction.py --section 01 --texte traductions/01_introduction.traduit.txt
    injecter_traduction.py --section 01 --texte … --sortie /tmp/candidat.fr.md

Sort en code 1 si le recalage échoue, si un chiffre a disparu, ou si le texte est vide.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from modele_document import Document, lire, replier, unites_traduisibles  # noqa: E402

RACINE = Path(__file__).resolve().parent.parent
SECTIONS = RACINE / "sections"
TRADUCTIONS = RACINE / "traductions"

# Un copier-coller à travers un traducteur perd volontiers un crochet : on accepte
# « [[10]] », « [10]] », « [[10] » et « [10] ». Le contenu reste chiffré, donc un
# emplacement comme « [c2, …] » ne peut pas être pris pour un repère.
RE_BALISE = re.compile(r"^\[{1,2}([\d.]+)\]{1,2}\s*(.*)$")

# --- Typographie française des nombres. Idempotent : un texte déjà français ne bouge pas.
# L'ordre compte : le séparateur de milliers se traite avant la virgule décimale.
RE_MILLIERS = re.compile(r"(?<![\w.,])(\d{1,3}),(\d{3})(?![\d])")
RE_DECIMALE = re.compile(r"(?<![\w.\-])(\d+)\.(\d+)(?![\w.\-])")


def franciser_nombres(texte: str) -> tuple[str, list[str]]:
    """1,000 → 1 000 et 3.30 → 3,30. Rend le texte et la liste des conversions faites."""
    faits: list[str] = []

    def milliers(m):
        faits.append(f"{m.group(0)} → {m.group(1)} {m.group(2)}")
        return f"{m.group(1)} {m.group(2)}"

    def decimale(m):
        faits.append(f"{m.group(0)} → {m.group(1)},{m.group(2)}")
        return f"{m.group(1)},{m.group(2)}"

    texte = RE_MILLIERS.sub(milliers, texte)
    texte = RE_DECIMALE.sub(decimale, texte)
    return texte, faits


def lire_traduction(chemin: Path) -> tuple[dict[str, str], bool]:
    """Rend {identifiant: texte} et un drapeau disant si les balises étaient présentes."""
    brut = chemin.read_text(encoding="utf-8")
    if re.search(r"^\[{1,2}[\d.]+\]{1,2}", brut, re.M):
        morceaux, ident, courant = {}, None, []
        for ligne in brut.split("\n"):
            m = RE_BALISE.match(ligne.strip())
            if m:
                if ident:
                    morceaux[ident] = " ".join(l.strip() for l in courant if l.strip())
                ident, courant = m.group(1), ([m.group(2)] if m.group(2).strip() else [])
            elif ident is not None:
                courant.append(ligne)
        if ident:
            morceaux[ident] = " ".join(l.strip() for l in courant if l.strip())
        return {k: v for k, v in morceaux.items() if v}, True

    blocs = [" ".join(l.strip() for l in b.split("\n") if l.strip())
             for b in re.split(r"\n\s*\n", brut) if b.strip()]
    return {str(i): t for i, t in enumerate(blocs)}, False


def apparier(doc: Document, morceaux: dict[str, str], balises: bool) -> dict[str, str]:
    """Associe chaque unité traduisible du master à son texte traduit."""
    unites = unites_traduisibles(doc)
    if balises:
        manquants = [i for i, _ in unites if i not in morceaux]
        if manquants:
            raise SystemExit(
                f"ERREUR : {len(manquants)} bloc(s) absent(s) de la traduction : "
                f"{', '.join(manquants[:10])}. Rien n'a été écrit.")
        return {i: morceaux[i] for i, _ in unites}

    if len(morceaux) != len(unites):
        apercu = "\n".join(
            f"  bloc {i:>6} attendu : {t[:70]}…" for i, t in unites[:3])
        raise SystemExit(
            f"ERREUR : recalage impossible sans balises — {len(unites)} blocs attendus, "
            f"{len(morceaux)} reçus. Rien n'a été écrit.\n{apercu}")
    return {ident: morceaux[str(n)] for n, (ident, _) in enumerate(unites)}


def rapport_existant(cible: Path) -> list[str] | None:
    """Le bloc de compte-rendu écrit à la main dans la cible, s'il y en a un : on ne l'écrase pas."""
    if not cible.exists():
        return None
    doc = lire(cible)
    for b in doc.blocs:
        if b.genre == "commentaire" and b.role == "rapport":
            return b.lignes
    return None


def reconstruire(doc: Document, textes: dict[str, str], source: Path,
                 lot: Path, rapport: list[str] | None, typo: bool) -> tuple[str, list[str]]:
    sortie: list[str] = []
    conversions: list[str] = []
    premier_commentaire = True

    def fr(texte: str) -> str:
        if not typo:
            return texte
        t, faits = franciser_nombres(texte)
        conversions.extend(faits)
        return t

    for b in doc.blocs:
        if b.genre == "commentaire":
            if b.role == "entete" and premier_commentaire:
                sortie.append(
                    f"<!-- Rendu français de `{source.name}` (consigne R17), article court "
                    f"AAMAS 2027.\n"
                    f"     Injecté le {date.today().isoformat()} par outils/injecter_traduction.py\n"
                    f"     depuis {lot.name}. L'anglais fait foi : mêmes coupes de paragraphe,\n"
                    f"     mêmes chiffres, mêmes commentaires de source. Aucune décision de fond\n"
                    f"     n'est prise ici ; un problème de fond se signale et se corrige en anglais. -->")
                premier_commentaire = False
            elif b.role == "rapport":
                sortie.extend(["\n".join(rapport)] if rapport else [])
            else:
                sortie.append("\n".join(b.lignes))
        elif b.genre == "titre":
            sortie.append(f"{b.prefixe}{fr(textes[str(b.id)])}")
        elif b.genre == "paragraphe":
            sortie.append(replier(fr(textes[str(b.id)])))
        elif b.genre == "item":
            corps = replier(fr(textes[str(b.id)]), indent=" " * len(b.prefixe))
            sortie.append(b.prefixe + corps[len(b.prefixe):])
        elif b.genre == "maths":
            sortie.append("\n".join(b.lignes))
        elif b.genre == "tableau":
            lignes = []
            for il, rang in enumerate(b.cellules):
                if len(rang) == 1 and rang[0]["fige"] and rang[0]["v"].lstrip().startswith("|"):
                    lignes.append(rang[0]["v"])
                    continue
                cells = [c["v"] if c["fige"] else fr(textes[f"{b.id}.{il}.{ic}"])
                         for ic, c in enumerate(rang)]
                lignes.append("| " + " | ".join(cells) + " |")
            sortie.append("\n".join(lignes))

    return "\n\n".join(sortie).rstrip() + "\n", conversions


def chiffres(texte: str, langue: str) -> list[str]:
    """Multiensemble des nombres d'un texte, sous une forme canonique commune aux deux langues.

    L'anglais sépare les milliers par une virgule et décime par un point, le français fait
    l'inverse : sans cette normalisation, `1,000` et `1 000` seraient deux chiffres
    différents, et le contrôle crierait à chaque rendu.
    """
    sans_commentaires = re.sub(r"<!--.*?-->", "", texte, flags=re.S)
    # Les numéros de titre (## 1.1) sont de la structure, pas des chiffres du papier.
    sans_commentaires = re.sub(r"^#{1,6}\s.*$", "", sans_commentaires, flags=re.M)
    if langue == "en":
        bruts = re.findall(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?", sans_commentaires)
        canon = [b.replace(",", "") for b in bruts]
    else:
        bruts = re.findall(
            r"\d{1,3}(?:[ \u202f\u00a0]\d{3})+(?:,\d+)?|\d+(?:,\d+)?", sans_commentaires)
        canon = [re.sub(r"[ \u202f\u00a0]", "", b).replace(",", ".") for b in bruts]
    return sorted(canon)


def main() -> int:
    debut = time.time()
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--section", "-s", required=True, help="numéro de section, par exemple 01")
    p.add_argument("--texte", "-t", required=True, help="fichier de la traduction reçue")
    p.add_argument("--sortie", "-o", help="chemin d'écriture (défaut : sections/<slug>.fr.md)")
    p.add_argument("--sans-typographie", action="store_true",
                   help="ne pas franciser les nombres reçus")
    args = p.parse_args()

    numero = args.section.strip().lstrip("0") or "0"
    sources = [f for f in sorted(SECTIONS.glob("*.en.md"))
               if (f.name.split("_")[0].lstrip("0") or "0") == numero]
    if not sources:
        print(f"ERREUR : aucune section {args.section} dans {SECTIONS}", file=sys.stderr)
        return 1
    source, lot = sources[0], Path(args.texte)
    if not lot.is_file():
        print(f"ERREUR : traduction introuvable : {lot}", file=sys.stderr)
        return 1

    print(f"[injection] master   : {source.relative_to(RACINE)}")
    print(f"[injection] traduction : {lot}")
    doc = lire(source)
    morceaux, balises = lire_traduction(lot)
    print(f"[injection] lot lu : {len(morceaux)} blocs, "
          f"{'balises [[n]] présentes' if balises else 'sans balises, recalage sur l’ordre'}")
    textes = apparier(doc, morceaux, balises)

    cible = Path(args.sortie) if args.sortie else SECTIONS / source.name.replace(".en.md", ".fr.md")
    garde = rapport_existant(cible)
    if garde:
        print(f"[injection] compte-rendu existant conservé dans {cible.name} "
              f"({len(garde)} lignes) — il n'est pas réécrit")

    contenu, conversions = reconstruire(doc, textes, source, lot, garde,
                                        not args.sans_typographie)

    attendus = chiffres(source.read_text(encoding="utf-8"), "en")
    obtenus = chiffres(contenu, "fr")
    perdus = [c for c in attendus if attendus.count(c) > obtenus.count(c)]
    if perdus:
        print(f"[ALARME] {len(set(perdus))} chiffre(s) du master absent(s) du français : "
              f"{', '.join(sorted(set(perdus))[:12])}", file=sys.stderr)
        print("[injection] rien n'a été écrit — un rendu n'a pas le droit de déplacer un chiffre.",
              file=sys.stderr)
        return 1

    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_text(contenu, encoding="utf-8")

    print(f"[injection] {len(textes)} blocs reposés, {len(conversions)} nombre(s) francisé(s)"
          + (f" ({', '.join(conversions[:6])}…)" if conversions else ""))
    print(f"[injection] chiffres : {len(attendus)} attendus, {len(obtenus)} présents, aucun perdu")
    print(f"[injection] écrit : {cible}")
    print(f"[injection] terminé en {time.time() - debut:.2f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
