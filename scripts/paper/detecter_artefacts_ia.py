#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Détecte dans les chapitres de l'article les marqueurs d'une écriture générée.

Une évaluation à double insu lit un manuscrit rédigé avec assistance. Les marqueurs
d'écriture générée ne relèvent pas du goût : ils se mesurent, et sur ce corpus ils se
concentrent dans les chapitres les moins retravaillés (ticket 083).

Le script mesure sur la PROSE SEULE. Il retire d'abord les blocs de code, les tableaux,
les schémas ASCII, les commentaires HTML, les cibles de liens, le code inline, les lignes
d'en-tête éditorial (`**Statut :**`, `**Version antérieure :**`) et les sections de queue
qui listent les tickets. Sans ce retrait, `fr/02_Related_work.md` afficherait quinze gras
alors que sa prose n'en porte aucun.

Usage : python3 scripts/paper/detecter_artefacts_ia.py [--fichier CHEMIN] [--racine DIR]
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

RACINE_DEFAUT = Path(__file__).resolve().parents[2] / "docs" / "paper" / "article"
DOSSIERS = ("fr", "en")  # overleaf/ est du .tex, relecture/ des notes de travail : hors périmètre
# Si overleaf/ entre un jour dans le périmètre : le .tex écrit le cadratin de DEUX façons, le
# caractère « — » et la ligature « --- », et il faut compter les deux. Le 2026-09-15,
# 03_Architecture.tex en portait 8 du premier genre et 14 du second — compter le seul
# caractère aurait raté les deux tiers du tic. Les commentaires LaTeX (%) ne sont pas du texte.

# --- Seuils -----------------------------------------------------------------------------
# Calés sur le corpus, pas posés arbitrairement. Mesures du 2026-09-15 sur la prose seule
# des quatre chapitres les plus relus par l'auteur (l'introduction compte quinze versions
# archivées) : fr/01 0,7 cadratin et 6,1 gras pour 1000 mots, fr/02 0,0 et 0,0, en/01 0,7
# et 7,1, en/02 0,0 et 0,0. Les brouillons de la même passe montaient à 17,5 (fr/99) et
# 36,1 (fr/08). Les seuils laissent donc respirer la norme interne sans laisser passer le
# facteur 20 qui séparait les deux groupes.
SEUIL_CADRATINS = 5.0   # pour 1000 mots de prose
SEUIL_GRAS = 10.0       # pour 1000 mots de prose
MOTS_MINIMUM = 150      # en deçà, une densité ne veut rien dire : le chapitre est signalé à part

# Symétrie mécanique : n sections consécutives de même longueur à ce pli près.
SYM_FENETRE = 4
SYM_ECART = 0.20
SYM_MOTS_MIN = 80

# --- Découpage --------------------------------------------------------------------------
# 60 et non 45 : « **Point ouvert, à trancher en remplaçant les emplacements :** » ouvre les
# deux abstracts et relève du même échafaudage éditorial que « **Statut :** ». Vérifié sur le
# corpus, l'élargissement ne fait basculer que ces deux lignes hors du calcul.
RE_META = re.compile(r"^\*\*[A-ZÉÈÀÎÔÛ][^*:]{2,60}\s?:\*\*")
RE_HTMLC = re.compile(r"<!--.*?-->", re.S)
RE_LIEN = re.compile(r"\]\([^)]*\)")
RE_INLINE = re.compile(r"`[^`]*`")
RE_QUEUE = re.compile(r"^#{2,4}\s+(Tickets?\b|Open dependency|Dépendance ouverte)", re.I)
CARACTERES_ASCII = set("┌┐└┘├┤┬┴┼─│═╔╗╚╝")
RE_TITRE_H2 = re.compile(r"^##\s+(?!#)")

# --- Motifs -----------------------------------------------------------------------------
# Bloquants : structure d'essai et lissage sémantique.
STRUCTURE = {
    "ouverture de conclusion":
        r"^(En résumé|En conclusion|Pour conclure|En somme|In summary|In conclusion|Overall)\b",
    "triptyque tout d'abord / ensuite / enfin":
        r"^(Tout d'abord|Premièrement|Deuxièmement|Troisièmement|First,|Second,|Finally,)\b",
    "d'une part / d'autre part":
        r"\bd'une part\b.{0,200}\bd'autre part\b|\bon the one hand\b.{0,200}\bon the other hand\b",
}
LISSAGE = {
    "concessif équilibré (bien que X, Y offre)":
        r"[Bb]ien qu[e'].{0,120}?\b(offre|présente|permet|apporte)\b",
    "concessif équilibré (il n'en demeure pas moins)":
        r"il n'en (reste|demeure) pas moins\b",
    "certes … mais":
        r"\bCertes\b[^.]{0,160}?\bmais\b",
    "while / although X offers Y":
        r"\b[Ww]hile\b.{0,120}?\b(offers|presents|provides)\b"
        r"|\b[Aa]lthough\b.{0,120}?\b(challenges|opportunities|offers)\b",
    "non seulement … mais aussi":
        r"non seulement .{0,120}? mais (aussi|également)\b|not only .{0,120}? but also\b",
}
# Informatif seulement. La passe du 2026-09-15 a relevé treize occurrences et zéro correction :
# `robust`/`robustness` est le vocabulaire de certification de SILICA, « paysage de perte » est
# loss landscape, « ni … ni … ni » une énumération française ordinaire. Faire échouer le script
# là-dessus imposerait une liste d'exemptions qui vieillirait mal ; la décision reste humaine.
LEXIQUE = {
    "fr": {
        "transition stéréotypée":
            r"\ben fin de compte\b|\bil convient de\b|\bil est important de\b"
            r"|\bil est à noter\b|\bnotons que\b|\bforce est de constater\b",
        "métaphore consensuelle":
            r"\btiss(e|er|ent|ant|ée?s?)\b|\bnavigu(e|er|ent|ant)\b|\bdévoil(e|er|ent|ant|ée?s?)\b"
            r"|\bcatalyseur\b|\bpierre angulaire\b|\bau cœur de\b|\bà l'ère d",
        "emphase creuse":
            r"\bcrucial(e|s|es|aux)?\b|\bvéritables?\b|\bincontournables?\b|\bprofondément\b",
    },
    "en": {
        "transition stéréotypée":
            r"\bultimately\b|\bit is important to\b|\bit should be noted\b|\bthat said,",
        "métaphore consensuelle":
            r"\bdelv(e|es|ed|ing)\b|\bunveil(s|ed|ing)?\b|\btapestry\b|\brealms?\b"
            r"|\bcatalyst\b|\bcornerstone\b|\btestament to\b|shed(s|ding)? light on",
        "emphase creuse":
            r"\bcrucial\b|\bpivotal\b|\bseamless(ly)?\b|\bcomprehensive(ly)?\b|\bnuanced\b"
            r"|\bunderscor(e|es|ed|ing)\b|\bshowcas(e|es|ed|ing)\b",
    },
}


def decouper(chemin: Path) -> tuple[list[tuple[int, str]], int]:
    """Retourne (lignes de prose numérotées, nombre de lignes écartées)."""
    brut = RE_HTMLC.sub("", chemin.read_text(encoding="utf-8"))
    prose: list[tuple[int, str]] = []
    ecartees = 0
    dans_code = False
    dans_queue = False
    for no, ligne in enumerate(brut.split("\n"), 1):
        nu = ligne.strip()
        if nu.startswith("```"):
            dans_code = not dans_code
            ecartees += 1
            continue
        if dans_code:
            ecartees += 1
            continue
        if RE_QUEUE.match(nu):
            dans_queue = True
        elif nu.startswith("#"):
            dans_queue = False
        if dans_queue or nu.startswith("|") or (set(nu) & CARACTERES_ASCII) or RE_META.match(nu):
            ecartees += 1
            continue
        prose.append((no, ligne))
    return prose, ecartees


def nettoyer(texte: str) -> str:
    """Retire les cibles de liens et le code inline, qui ne sont pas de la prose."""
    return RE_INLINE.sub(" ", RE_LIEN.sub("]( )", texte))


def chercher(motifs: dict[str, str], lignes: list[tuple[int, str]],
             ancre: bool = False) -> list[tuple[int, str, str]]:
    trouves = []
    for no, ligne in lignes:
        texte = nettoyer(ligne).strip() if ancre else nettoyer(ligne)
        for nom, motif in motifs.items():
            for m in re.finditer(motif, texte):
                trouves.append((no, nom, m.group(0).strip()[:70]))
    return trouves


def symetrie(lignes: list[tuple[int, str]]) -> list[tuple[int, str, str]]:
    """Signale n sections `##` consécutives de longueur quasi identique."""
    sections: list[tuple[int, str, int]] = []
    for no, ligne in lignes:
        if RE_TITRE_H2.match(ligne):
            sections.append((no, ligne.strip()[:40], 0))
        elif sections:
            no_t, titre, mots = sections[-1]
            sections[-1] = (no_t, titre, mots + len(nettoyer(ligne).split()))
    trouves = []
    for i in range(len(sections) - SYM_FENETRE + 1):
        fenetre = sections[i:i + SYM_FENETRE]
        tailles = [m for _, _, m in fenetre]
        if min(tailles) < SYM_MOTS_MIN:
            continue
        moyenne = sum(tailles) / len(tailles)
        if (max(tailles) - min(tailles)) / moyenne <= SYM_ECART:
            trouves.append((fenetre[0][0], "symétrie mécanique des sections",
                            f"{SYM_FENETRE} sections consécutives de {min(tailles)} à "
                            f"{max(tailles)} mots"))
    return trouves


def analyser(chemin: Path, langue: str) -> dict:
    prose, ecartees = decouper(chemin)
    texte = "\n".join(nettoyer(l) for _, l in prose)
    mots = len(texte.split())
    cadratins = texte.count("—")
    gras = len(re.findall(r"\*\*[^*\n]+\*\*", texte))
    bloquants: list[tuple[int, str, str]] = []
    bloquants += chercher(STRUCTURE, prose, ancre=True)
    bloquants += chercher(LISSAGE, prose)
    bloquants += symetrie(prose)
    if mots >= MOTS_MINIMUM:
        if cadratins * 1000 / mots > SEUIL_CADRATINS:
            bloquants.append((0, "densité de cadratins",
                              f"{cadratins * 1000 / mots:.1f}/1k mots, seuil {SEUIL_CADRATINS}"
                              f" ({cadratins} occurrences)"))
        if gras * 1000 / mots > SEUIL_GRAS:
            bloquants.append((0, "densité de gras",
                              f"{gras * 1000 / mots:.1f}/1k mots, seuil {SEUIL_GRAS}"
                              f" ({gras} occurrences)"))
    return dict(
        mots=mots, ecartees=ecartees, cadratins=cadratins, gras=gras,
        cadratins_k=cadratins * 1000 / mots if mots else 0.0,
        gras_k=gras * 1000 / mots if mots else 0.0,
        bloquants=sorted(bloquants), lexique=sorted(chercher(LEXIQUE[langue], prose)),
    )


def recenser(racine: Path, fichier: Path | None) -> list[tuple[str, Path]]:
    if fichier:
        langue = fichier.parent.name
        if langue not in DOSSIERS:
            print(f"ERREUR  hors périmètre : {fichier} (attendu dans {'/'.join(DOSSIERS)})",
                  file=sys.stderr)
            return []
        return [(langue, fichier)]
    trouves = []
    for langue in DOSSIERS:
        dossier = racine / langue
        if not dossier.is_dir():
            print(f"ERREUR  arbre manquant : {dossier}", file=sys.stderr)
            continue
        trouves += [(langue, f) for f in sorted(dossier.glob("[0-9]*.md"))]
    return trouves


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--racine", type=Path, default=RACINE_DEFAUT)
    ap.add_argument("--fichier", type=Path, help="un seul chapitre, au lieu de fr/ et en/")
    args = ap.parse_args()

    debut = time.monotonic()
    chapitres = recenser(args.racine, args.fichier)
    if not chapitres:
        print("ERREUR  aucun chapitre à analyser", file=sys.stderr)
        return 1

    resultats = [(langue, f, analyser(f, langue)) for langue, f in chapitres]

    n_bloquants = sum(len(r["bloquants"]) for _, _, r in resultats)
    n_lexique = sum(len(r["lexique"]) for _, _, r in resultats)
    n_courts = sum(1 for _, _, r in resultats if r["mots"] < MOTS_MINIMUM)

    for langue, f, r in resultats:
        if not r["bloquants"] and not r["lexique"]:
            continue
        print(f"\n{langue}/{f.name}")
        for no, nom, extrait in r["bloquants"]:
            ou = f"l.{no}" if no else "chapitre"
            print(f"  {ou:>9}  {nom} : {extrait}")
        for no, nom, extrait in r["lexique"]:
            print(f"  {'l.' + str(no):>9}  [informatif] {nom} : {extrait}")

    print(f"\n{'chapitre':<34}{'mots':>7}{'cadr/1k':>9}{'gras/1k':>9}{'écarts':>8}")
    for langue, f, r in resultats:
        marque = "" if r["mots"] >= MOTS_MINIMUM else "  (trop court pour une densité)"
        print(f"{langue + '/' + f.name:<34}{r['mots']:>7}{r['cadratins_k']:>9.1f}"
              f"{r['gras_k']:>9.1f}{len(r['bloquants']):>8}{marque}")

    duree = time.monotonic() - debut
    print(f"\n{len(resultats)} chapitre(s), {sum(r['mots'] for _, _, r in resultats)} mots de "
          f"prose, {sum(r['ecartees'] for _, _, r in resultats)} ligne(s) écartée(s) du calcul "
          f"— {duree:.2f} s")
    print(f"{n_bloquants} écart(s) bloquant(s), {n_lexique} constat(s) lexical(aux) informatif(s), "
          f"{n_courts} chapitre(s) trop court(s) pour une densité")

    if n_bloquants:
        print(f"ERREUR  {n_bloquants} écart(s) de style sur {sum(1 for _, _, r in resultats if r['bloquants'])} "
              f"chapitre(s) : voir le détail ci-dessus.", file=sys.stderr)
        return 1
    print("SUCCÈS  aucun marqueur d'écriture générée au-dessus des seuils du corpus.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
