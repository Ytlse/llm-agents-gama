#!/usr/bin/env python3
"""Contrôle mécanique des consignes de forme de l'article court.

Vérifie ce qui s'automatise parmi les dix-sept consignes de CONSIGNES_FORME.md :
R1 longueur de phrase, R2 deux-points, R4 référent avant pronom, R5 clivées,
R9 renvois vers l'avant, R10 budget de mots, R11 lexique, R14 placeholders.

Les neuf autres se contrôlent en lisant ; --squelette outille la plus utile (R7).

Usage :
    verifier_forme.py FICHIER [FICHIER...]
    verifier_forme.py --squelette FICHIER
    verifier_forme.py --regle R1,R5 FICHIER

Sort en code 1 si au moins une consigne est en faute, 0 sinon.
"""

import argparse
import re
import sys
from pathlib import Path

# --- Seuils. Ils viennent de CONSIGNES_FORME.md et s'y modifient d'abord. ---
MOTS_MAX_PHRASE = 30
DEUX_POINTS_MAX_PAR_PARAGRAPHE = 1

# R11 — table de conversion lexicale. Clé : motif ; valeur : ce qu'il faut écrire.
LEXIQUE_PROSCRIT = {
    r"\bthe (agentic )?device\b": "the system / the framework",
    r"\bthe itinerary supply\b": "the choice set",
    r"\bthe carrier\b": "the language model",
    r"\bplates\b": "panels / figures",
    r"\ban arm\b": "a condition",
    r"\bagnosticity\b": "territory-agnostic constraint",
    r"\bguard-rails?\b": "constraints",
    r"\ban adaptability\b": "adaptability",
    # famille lexicale proscrite par la charte anti-IA (article-verrou)
    r"\b(crucial|pivotal|delve|seamless|underscore|ultimately)\b": "à remplacer (lexique prédictible)",
}

# R5 — clivées et inversions littéraires.
CLIVEES = [
    (r"\bWhat is [^.]{1,60}? is\b", "clivée « What is X is Y » → sujet + verbe actif"),
    (r"\bIt is [^.]{1,60}? that\b", "clivée « It is X that Y » → sujet + verbe actif"),
    (r"\bWhat [^.]{1,40}? does is\b", "clivée « What X does is » → sujet + verbe actif"),
    (r"\bIt is there, and only there\b", "inversion emphatique"),
]

# R4 — ouvertures de phrase sur un démonstratif sans référent écrit.
CATAPHORES = re.compile(
    r"^(This|That|These|Those|Such)\s+"
    r"(obvious |methodological |elementary |last |very )?"
    r"(fact|detail|rating|consequence|point|choice|reading|property|result|"
    r"distinction|constraint|asymmetry|restriction|mechanism|movement|level)\b"
)

# R14 — placeholders.
PLACEHOLDERS = [
    (r"\\todo\{", "\\todo{} imprimé en gras dans le PDF"),
    (r"\bTBC\b", "TBC"),
    (r"\bTODO\b", "TODO"),
    (r"\bxx\.y\b|\bxx\b(?=\s*\\?%)", "gabarit de chiffre non mesuré"),
    (r"\[à mesurer\]|\[à chiffrer\]", "mesure annoncée et absente"),
]

ABREVIATIONS = r"(?<!\be\.g)(?<!\bi\.e)(?<!\bcf)(?<!\bFig)(?<!\bTab)(?<!\bSec)(?<!\bApp)(?<!\bNo)(?<!\bvs)"


def nettoyer(texte: str, extension: str) -> str:
    """Retire ce qui n'est pas de la prose : commentaires, verbatim, descriptions alt."""
    if extension == ".tex":
        texte = re.sub(r"^%.*$", "", texte, flags=re.MULTILINE)
        # Les titres deviennent un marqueur neutre : sinon le dépouillement des
        # commandes, plus bas, les efface avant que sections() puisse les voir.
        texte = re.sub(r"\\(?:sub)*section\*?\{([^{}]*)\}", "\n\n@@SEC@@\\1\n\n", texte)
        texte = re.sub(r"(?<!\\)%.*$", "", texte, flags=re.MULTILINE)
        # verbatim (LaTeX) et Verbatim (fancyvrb/fvextra, annexes du matériel supplémentaire).
        texte = re.sub(r"\\begin\{([Vv]erbatim)\}.*?\\end\{\1\}", "", texte, flags=re.DOTALL)
        texte = re.sub(r"\\Description\{(?:[^{}]|\{[^{}]*\})*\}", "", texte, flags=re.DOTALL)
        texte = re.sub(r"\\begin\{tabular\w*\}.*?\\end\{tabular\w*\}", "", texte, flags=re.DOTALL)
        # Titre de paragraphe en ligne : il ne compte pas dans la phrase qui le suit (R1).
        texte = re.sub(r"\\paragraph\*?\{[^}]*\}", " ", texte)
        texte = re.sub(r"\\(label|includegraphics|graphicspath|setcounter|renewcommand|newcolumntype)\{[^}]*\}", "", texte)
        texte = re.sub(r"\\(texttt|textbf|emph|textit|citep|citet|ref)\{([^{}]*)\}", r"\2", texte)
        texte = re.sub(r"\\[a-zA-Z]+\*?", " ", texte)
        texte = texte.replace("{", " ").replace("}", " ").replace("&", " ").replace("\\\\", " ")
    else:
        texte = re.sub(r"^<!--.*?-->", "", texte, flags=re.DOTALL | re.MULTILINE)
        texte = re.sub(r"<!--.*?-->", "", texte, flags=re.DOTALL)
        texte = re.sub(r"```.*?```", "", texte, flags=re.DOTALL)
        texte = re.sub(r"^\s*\|.*\|\s*$", "", texte, flags=re.MULTILINE)
        # Titre de paragraphe en ligne (« **Titre court.** ») : hors de la phrase qui suit (R1).
        texte = re.sub(r"^\*\*(?:\S+\s+){0,7}\S+\.\*\*\s+", "", texte, flags=re.MULTILINE)
    return texte


def reperer(brut: str, para: str) -> int:
    """Numéro de ligne du paragraphe dans le fichier d'origine, 0 si introuvable."""
    mots = [m for m in para.split() if len(m) > 3 and m.isalpha()]
    for debut in range(0, max(1, len(mots) - 4)):
        sonde = " ".join(mots[debut:debut + 5])
        position = brut.find(sonde)
        if position > 0:
            return brut[:position].count("\n") + 1
    return 0


def paragraphes(texte: str):
    for bloc in re.split(r"\n\s*\n", texte):
        bloc = " ".join(bloc.split())
        if len(bloc.split()) >= 8 and not bloc.startswith(("#", "@@SEC@@")):
            yield bloc


def phrases(paragraphe: str):
    decoupe = re.split(rf"{ABREVIATIONS}(?<=[.!?])\s+(?=[A-Z«\"'])", paragraphe)
    return [p.strip() for p in decoupe if p.strip()]


def sections(texte: str, extension: str):
    """Rend (titre, corps) pour chaque section ou sous-section."""
    if extension == ".tex":
        motif = r"^@@SEC@@(.*)$"
    else:
        motif = r"^#{1,4}\s+(.*)$"
    morceaux = re.split(motif, texte, flags=re.MULTILINE)
    if len(morceaux) == 1:
        return [("(document)", texte)]
    resultat = []
    for i in range(1, len(morceaux), 2):
        resultat.append((morceaux[i].strip(), morceaux[i + 1]))
    return resultat


def controler(chemin: Path, regles: set) -> list:
    brut = chemin.read_text(encoding="utf-8")
    ext = chemin.suffix
    texte = nettoyer(brut, ext)
    constats = []

    def note(regle, ligne, message, extrait=""):
        if regles and regle not in regles:
            return
        constats.append((regle, ligne, message, extrait))

    # R14 — placeholders, cherchés sur le texte BRUT : ils vivent souvent en commentaire.
    for num, ligne in enumerate(brut.splitlines(), 1):
        if ligne.lstrip().startswith("%") or ligne.lstrip().startswith("<!--"):
            continue
        for motif, libelle in PLACEHOLDERS:
            if re.search(motif, ligne):
                note("R14", num, f"placeholder : {libelle}", ligne.strip()[:90])

    # R9 — renvoi vers l'avant : un \ref qui précède son \label dans le même fichier.
    if ext == ".tex":
        labels = {m.group(1): m.start() for m in re.finditer(r"\\label\{([^}]*)\}", brut)}
        for m in re.finditer(r"\\ref\{([^}]*)\}", brut):
            cible = m.group(1)
            if cible in labels and m.start() < labels[cible]:
                ligne = brut[: m.start()].count("\n") + 1
                note("R9", ligne, f"renvoi vers l'avant : \\ref{{{cible}}} précède son \\label")

    # R1, R2, R4, R5, R11 — sur la prose nettoyée.
    for para in paragraphes(texte):
        ligne = reperer(brut, para)

        n_deux_points = para.count(":")
        if n_deux_points > DEUX_POINTS_MAX_PAR_PARAGRAPHE:
            note("R2", ligne, f"{n_deux_points} deux-points dans le paragraphe (max {DEUX_POINTS_MAX_PAR_PARAGRAPHE})",
                 para[:90])

        for ph in phrases(para):
            n = len(ph.split())
            if n > MOTS_MAX_PHRASE:
                note("R1", ligne, f"phrase de {n} mots (max {MOTS_MAX_PHRASE})", ph[:90])
            if ph.count(":") >= 2:
                note("R2", ligne, "deux deux-points dans une même phrase", ph[:90])
            if CATAPHORES.match(ph):
                note("R4", ligne, "phrase ouvrant sur un démonstratif sans référent", ph[:90])
            for motif, libelle in CLIVEES:
                if re.search(motif, ph):
                    note("R5", ligne, libelle, ph[:90])
            for motif, remplacement in LEXIQUE_PROSCRIT.items():
                trouve = re.search(motif, ph, flags=re.IGNORECASE)
                if trouve:
                    note("R11", ligne, f"« {trouve.group(0)} » → {remplacement}", ph[:90])

    return constats


def squelette(chemin: Path):
    brut = chemin.read_text(encoding="utf-8")
    texte = nettoyer(brut, chemin.suffix)
    print(f"\n=== Squelette de {chemin.name} ===")
    print("Lire d'une traite. Si cela ne raconte pas la section, les phrases-sujets manquent (R7).\n")
    for titre, corps in sections(texte, chemin.suffix):
        paras = list(paragraphes(corps))
        if not paras:
            continue
        print(f"--- {titre} ---")
        for para in paras:
            premiere = phrases(para)[0]
            print(f"  · {premiere}")
        print()


def budget(chemin: Path):
    brut = chemin.read_text(encoding="utf-8")
    texte = nettoyer(brut, chemin.suffix)
    total = 0
    lignes = []
    for titre, corps in sections(texte, chemin.suffix):
        n = sum(len(p.split()) for p in paragraphes(corps))
        total += n
        lignes.append((titre, n))
    return total, lignes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fichiers", nargs="+", type=Path)
    ap.add_argument("--squelette", action="store_true",
                    help="imprime la première phrase de chaque paragraphe (test de R7)")
    ap.add_argument("--regle", default="", help="ne contrôler que ces consignes, ex. R1,R5")
    args = ap.parse_args()

    regles = {r.strip().upper() for r in args.regle.split(",") if r.strip()}
    en_faute = False

    for chemin in args.fichiers:
        if not chemin.exists():
            print(f"[ERREUR] fichier absent : {chemin}", file=sys.stderr)
            en_faute = True
            continue

        if args.squelette:
            squelette(chemin)
            continue

        total, par_section = budget(chemin)
        constats = controler(chemin, regles)

        print(f"\n=== {chemin} ===")
        print(f"{total} mots de prose, {len(par_section)} sections (R10)")
        for titre, n in par_section:
            if n:
                print(f"    {n:>5}  {titre}")

        if not constats:
            print("\nAucune consigne mécanique en faute.")
            continue

        en_faute = True
        par_regle = {}
        for regle, ligne, message, extrait in constats:
            par_regle.setdefault(regle, []).append((ligne, message, extrait))

        print()
        for regle in sorted(par_regle):
            entrees = par_regle[regle]
            print(f"[{regle}] {len(entrees)} constat(s)")
            for ligne, message, extrait in entrees[:12]:
                repere = f"l.{ligne}" if ligne else "l.?"
                print(f"    {repere:<8} {message}")
                if extrait:
                    print(f"             « {extrait} »")
            if len(entrees) > 12:
                print(f"    … et {len(entrees) - 12} autres")
            print()

    return 1 if en_faute else 0


if __name__ == "__main__":
    sys.exit(main())
