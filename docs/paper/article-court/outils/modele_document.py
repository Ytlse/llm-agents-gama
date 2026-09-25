#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Modèle de document des sections de l'article court.

Un fichier `sections/NN_<slug>.<lang>.md` se lit ici comme une suite de blocs typés. Ce
modèle est le contrat partagé entre l'extraction (qui sort le texte à traduire) et
l'injection (qui remonte la traduction) : les deux voient la même numérotation de blocs,
donc un texte traduit se repose exactement là où il a été pris.

Ce qui sort vers le traducteur : titres, paragraphes, items de liste, cellules de tableau
porteuses de texte. Ce qui ne sort jamais : les commentaires `<!-- source: … -->` (déjà
français des deux côtés), les maths, les cellules numériques, le bloc de compte-rendu.

Usage : importé par extraire_blocs.py et injecter_traduction.py. Pas de point d'entrée.
"""
from __future__ import annotations

import json
import re
import textwrap
from dataclasses import dataclass, field, asdict
from pathlib import Path

# Largeur de repli des lignes de prose, mesurée sur le corpus des sections (les lignes
# plus longues du corpus sont toutes dans des commentaires, qui ne se replient pas).
LARGEUR = 95

RE_TITRE = re.compile(r"^(#{1,6})\s+((?:\d+(?:\.\d+)*\.?)\s+)?(.+)$")
RE_ITEM = re.compile(r"^(\s*(?:\d+\.|[-*])\s+)(.*)$")
RE_MATHS = re.compile(r"^\s*\$\$")
RE_TABLEAU = re.compile(r"^\s*\|")
RE_SEPARATEUR_TABLEAU = re.compile(r"^\s*\|[\s:|-]+\|\s*$")

# Cellules et segments qui ne partent jamais chez le traducteur. Une cellule est figée si
# elle correspond à l'un de ces motifs EN ENTIER ; un segment cité ici à l'intérieur d'une
# phrase reste à la charge du traducteur, qui ne touche pas à ce genre de chaîne.
NE_PAS_TRADUIRE = [
    r"^\s*$",
    r"^[\s\d.,±%+\-–—/()\[\]]+$",          # purement numérique ou symbolique
    r"^\[replay pending\]$",                # étiquette d'état de ticket, anglaise des deux côtés
    r"^\[c2[^\]]*\]$",                      # emplacement nommé en attente du ticket 103
    r"^(gemini|mistral|gpt|claude)[-\w.]*$",
]
RE_FIGE = re.compile("|".join(NE_PAS_TRADUIRE), re.IGNORECASE)


@dataclass
class Bloc:
    """Un bloc du document. `texte` est vide quand le bloc ne se traduit pas."""

    id: int
    genre: str                              # commentaire | titre | paragraphe | item | tableau | maths
    texte: str = ""                         # texte traduisible, déplié sur une seule ligne
    prefixe: str = ""                       # "## 1.1 ", "- ", "1. " — remis tel quel à l'injection
    lignes: list[str] = field(default_factory=list)   # contenu verbatim (commentaires, maths)
    cellules: list[list[dict]] = field(default_factory=list)  # tableau : {"fige": bool, "v": str}
    role: str = ""                          # commentaire : entete | source | rapport

    @property
    def traduisible(self) -> bool:
        return self.genre in ("titre", "paragraphe", "item") or (
            self.genre == "tableau" and any(not c["fige"] for r in self.cellules for c in r)
        )


@dataclass
class Document:
    chemin: str
    langue: str
    blocs: list[Bloc]

    def en_json(self) -> str:
        return json.dumps(
            {"chemin": self.chemin, "langue": self.langue,
             "blocs": [asdict(b) for b in self.blocs]},
            ensure_ascii=False, indent=1,
        )

    @staticmethod
    def depuis_json(chemin: Path) -> "Document":
        d = json.loads(Path(chemin).read_text(encoding="utf-8"))
        return Document(d["chemin"], d["langue"], [Bloc(**b) for b in d["blocs"]])


def _figee(cellule: str) -> bool:
    return bool(RE_FIGE.fullmatch(cellule.strip()))


def _deplier(lignes: list[str]) -> str:
    """Une suite de lignes repliées à 95 colonnes redevient une seule ligne."""
    return " ".join(l.strip() for l in lignes if l.strip())


def replier(texte: str, largeur: int = LARGEUR, indent: str = "") -> str:
    """Repli inverse, pour écrire un bloc dans un .md au format du corpus."""
    return textwrap.fill(
        texte, width=largeur, initial_indent=indent, subsequent_indent=indent,
        break_long_words=False, break_on_hyphens=False,
    )


def lire(chemin: Path) -> Document:
    """Découpe un fichier de section en blocs typés et numérotés."""
    chemin = Path(chemin)
    lignes = chemin.read_text(encoding="utf-8").split("\n")
    langue = "fr" if chemin.name.endswith(".fr.md") else "en"
    blocs: list[Bloc] = []
    i, n = 0, len(lignes)

    while i < n:
        ligne = lignes[i]
        if not ligne.strip():
            i += 1
            continue

        # --- commentaire HTML, du <!-- au --> ---
        if ligne.lstrip().startswith("<!--"):
            debut = i
            while i < n and "-->" not in lignes[i]:
                i += 1
            i = min(i, n - 1)
            corps = lignes[debut:i + 1]
            joint = "\n".join(corps)
            role = ("source" if "source:" in corps[0]
                    else "rapport" if "SECTION REPORT" in joint or "RAPPORT" in joint
                    else "entete")
            blocs.append(Bloc(len(blocs) + 1, "commentaire", lignes=corps, role=role))
            i += 1
            continue

        # --- titre ---
        if ligne.startswith("#"):
            m = RE_TITRE.match(ligne)
            diese, numero, texte = m.group(1), m.group(2) or "", m.group(3)
            blocs.append(Bloc(len(blocs) + 1, "titre",
                              texte=texte.strip(), prefixe=f"{diese} {numero}"))
            i += 1
            continue

        # --- maths, verbatim ---
        if RE_MATHS.match(ligne):
            debut = i
            if ligne.strip().count("$$") < 2:
                i += 1
                while i < n and "$$" not in lignes[i]:
                    i += 1
            blocs.append(Bloc(len(blocs) + 1, "maths", lignes=lignes[debut:i + 1]))
            i += 1
            continue

        # --- tableau ---
        if RE_TABLEAU.match(ligne):
            debut = i
            while i < n and RE_TABLEAU.match(lignes[i]):
                i += 1
            cellules = []
            for brute in lignes[debut:i]:
                if RE_SEPARATEUR_TABLEAU.match(brute):
                    cellules.append([{"fige": True, "v": brute}])   # ligne de séparation
                    continue
                champs = [c.strip() for c in brute.strip().strip("|").split("|")]
                cellules.append([{"fige": _figee(c), "v": c} for c in champs])
            blocs.append(Bloc(len(blocs) + 1, "tableau", cellules=cellules))
            continue

        # --- item de liste ---
        m = RE_ITEM.match(ligne)
        if m:
            prefixe, premiere = m.group(1), m.group(2)
            suite = [premiere]
            i += 1
            while i < n and lignes[i].strip() and not RE_ITEM.match(lignes[i]) \
                    and not lignes[i].startswith("#") and not lignes[i].lstrip().startswith("<!--"):
                suite.append(lignes[i])
                i += 1
            blocs.append(Bloc(len(blocs) + 1, "item", texte=_deplier(suite), prefixe=prefixe))
            continue

        # --- paragraphe ---
        debut = i
        while i < n and lignes[i].strip() and not lignes[i].startswith("#") \
                and not lignes[i].lstrip().startswith("<!--") and not RE_TABLEAU.match(lignes[i]) \
                and not RE_MATHS.match(lignes[i]):
            i += 1
        blocs.append(Bloc(len(blocs) + 1, "paragraphe", texte=_deplier(lignes[debut:i])))

    return Document(str(chemin), langue, blocs)


def unites_traduisibles(doc: Document) -> list[tuple[str, str]]:
    """Liste ordonnée des (identifiant, texte) à confier au traducteur.

    L'identifiant est `12` pour un bloc simple, `12.3.1` pour la cellule ligne 3 colonne 1
    d'un tableau. Il est écrit tel quel dans le lot, entre doubles crochets.
    """
    unites: list[tuple[str, str]] = []
    for b in doc.blocs:
        if b.genre in ("titre", "paragraphe", "item"):
            unites.append((str(b.id), b.texte))
        elif b.genre == "tableau":
            for il, rang in enumerate(b.cellules):
                for ic, cell in enumerate(rang):
                    if not cell["fige"]:
                        unites.append((f"{b.id}.{il}.{ic}", cell["v"]))
    return unites


def compter_mots(doc: Document) -> int:
    return sum(len(t.split()) for _, t in unites_traduisibles(doc))
