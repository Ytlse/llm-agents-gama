#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vérifie la parité des chapitres de l'article entre les trois arbres.

L'arbre par langue (`article/en/`, `article/fr/`, `article/overleaf/`) éloigne les trois
fichiers d'un même chapitre : rien ne signale plus qu'un maître a bougé sans son miroir.
Ce script rétablit le signal. Il relit l'en-tête de version de chaque fichier, aligne les
chapitres par numéro, et sort en code 1 dès qu'un chapitre n'est pas cohérent.

Usage : python3 scripts/paper/verifier_parite.py [--racine docs/paper/article]
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

RACINE_DEFAUT = Path(__file__).resolve().parents[2] / "docs" / "paper" / "article"

RE_FICHIER = re.compile(r"^(\d{2})_([a-z0-9_]+)\.(md|tex)$")
RE_VERSION_MD = re.compile(r"\*\*Version\s?:?\*\*\s*`(v[\d.]+)`")
RE_BROUILLON = re.compile(r"\*\*Statut\s?:?\*\*\s*`(brouillon[^`]*)`")
RE_VERSION_TEX = re.compile(r"%[^\n]*?\bv(\d+\.\d+)\b")
RE_PLAN = re.compile(r"^(\d)\.\s+[A-ZÉÈÀÂÎÔÛÇ]")


def etat(chemin: Path) -> str:
    """Version déclarée, mention de brouillon, ou 'sans en-tête'."""
    if not chemin.exists():
        return "absent"
    texte = chemin.read_text(encoding="utf-8")
    if chemin.suffix == ".tex":
        m = RE_VERSION_TEX.search(texte)
        return f"v{m.group(1)}" if m else "sans en-tête"
    m = RE_VERSION_MD.search(texte)
    if m:
        return m.group(1)
    m = RE_BROUILLON.search(texte)
    if m:
        return m.group(1)
    return "sans en-tête"


def recenser(racine: Path) -> dict[str, dict[str, tuple[str, str]]]:
    """{numéro: {langue: (slug, état)}} pour en/, fr/ et overleaf/."""
    chapitres: dict[str, dict[str, tuple[str, str]]] = {}
    for langue, dossier in (("en", "en"), ("fr", "fr"), ("tex", "overleaf")):
        d = racine / dossier
        if not d.is_dir():
            print(f"ERREUR  arbre manquant : {d}", file=sys.stderr)
            continue
        for f in sorted(d.iterdir()):
            m = RE_FICHIER.match(f.name)
            if not m:
                continue
            num, slug, _ = m.groups()
            chapitres.setdefault(num, {})[langue] = (slug, etat(f))
    return chapitres


def sections_du_plan(racine: Path) -> set[str]:
    plan = racine / "plan" / "PLAN.md"
    if not plan.exists():
        return set()
    return {f"{m.group(1):0>2}" for m in
            (RE_PLAN.match(l.strip()) for l in plan.read_text(encoding="utf-8").split("\n")) if m}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--racine", type=Path, default=RACINE_DEFAUT)
    args = ap.parse_args()
    debut = time.monotonic()
    print(f"parité des chapitres — racine {args.racine}")

    chapitres = recenser(args.racine)
    plan = sections_du_plan(args.racine)
    ecarts: list[str] = []
    conformes = brouillons = 0

    for num in sorted(chapitres):
        langues = chapitres[num]
        slugs = {s for s, _ in langues.values()}
        etats = {lg: e for lg, (_, e) in langues.items()}
        detail = "  ".join(f"{lg}={etats.get(lg, 'absent')}" for lg in ("en", "fr", "tex"))
        slug = sorted(slugs)[0]

        if len(slugs) > 1:
            ecarts.append(f"chapitre {num} : slugs différents entre langues ({', '.join(sorted(slugs))})")
        # un chapitre encore en brouillon ne vit qu'en français : c'est attendu, pas un écart
        if "en" not in langues and all(e.startswith("brouillon") for e in etats.values()):
            brouillons += 1
            print(f"  {num} {slug:<24} brouillon      {detail}")
            continue
        versions = {e for e in etats.values() if e.startswith("v")}
        manquantes = [lg for lg in ("en", "fr", "tex") if lg not in langues]
        if manquantes:
            ecarts.append(f"chapitre {num} ({slug}) : langue(s) manquante(s) {', '.join(manquantes)}")
        if len(versions) > 1:
            ecarts.append(f"chapitre {num} ({slug}) : versions divergentes — {detail}")
        if not manquantes and len(versions) == 1:
            conformes += 1
            print(f"  {num} {slug:<24} conforme {versions.pop():<8} {detail}")
        else:
            print(f"  {num} {slug:<24} ÉCART          {detail}")

    for num in sorted(plan - set(chapitres)):
        ecarts.append(f"section {num} annoncée par PLAN.md sans aucun fichier de chapitre")
    for num in sorted(set(chapitres) - plan):
        if num != "99":
            ecarts.append(f"chapitre {num} présent mais absent de PLAN.md")

    duree = time.monotonic() - debut
    print(f"\n{len(chapitres)} chapitre(s) : {conformes} conforme(s), {brouillons} brouillon(s), "
          f"{len(ecarts)} écart(s) — {duree:.2f} s")
    if ecarts:
        for e in ecarts:
            print(f"ERREUR  {e}", file=sys.stderr)
        return 1
    print("SUCCÈS  tous les chapitres rédigés sont à parité sur les trois arbres.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
