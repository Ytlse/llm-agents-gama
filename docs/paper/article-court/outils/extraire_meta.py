#!/usr/bin/env python3
"""
extraire_meta.py — Extrait les commentaires internes des chapitres LaTeX anglais
vers des fichiers compagnons .meta.md et nettoie les fichiers .tex.

Consigne :
- Préserve intacts les \\% (pourcentages échappés) et le contenu des blocs Verbatim.
- Sépare l'en-tête de traçabilité/dépendances et les notes éditoriales du corps.
- Propose un mode --dry-run (par défaut) et un mode --apply.
"""

import os
import sys
import re
import argparse
from pathlib import Path

CHAPTER_FILES = [
    "00_Abstract.tex",
    "01_Introduction.tex",
    "02_Related_work.tex",
    "03_Agent.tex",
    "04_Bench.tex",
    "05_Results.tex",
    "06_Non_tabulated.tex",
    "07_Implications.tex",
    "08_Appendices.tex",
]

def parse_tex_file(filepath: Path):
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    header_lines = []
    body_lines = []
    body_comments = [] # list of dicts: {'line_num': int, 'context': str, 'comment': str}
    
    in_header = True
    in_verbatim = False
    current_context = "Introduction / Début de section"

    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\r\n")
        stripped = line.strip()

        # Détection verbatim
        if re.search(r"\\begin\{(?:Verbatim|verbatim)\}", stripped):
            in_verbatim = True
        elif re.search(r"\\end\{(?:Verbatim|verbatim)\}", stripped):
            in_verbatim = False

        if in_verbatim:
            in_header = False
            body_lines.append(raw_line)
            continue

        # Suivi du contexte pour le corps
        m_sec = re.search(r"\\(?:sub)*section\*?\{([^}]+)\}", stripped)
        if m_sec:
            current_context = m_sec.group(1).strip()
        m_lbl = re.search(r"\\label\{([^}]+)\}", stripped)
        if m_lbl:
            current_context = f"{current_context} ({m_lbl.group(1).strip()})"
        m_float = re.search(r"\\begin\{(?:table\*?|figure\*?)\}", stripped)
        if m_float:
            current_context = f"Flottant {m_float.group(0)}"

        # Phase 1 : En-tête
        if in_header:
            if stripped.startswith("%") or stripped == "":
                header_lines.append((idx, line))
                continue
            else:
                in_header = False

        # Phase 2 : Corps
        if stripped.startswith("%"):
            # C'est un commentaire pur de ligne
            clean_comment = re.sub(r"^%\s?", "", stripped)
            body_comments.append({
                "line_num": idx,
                "context": current_context,
                "raw": stripped,
                "text": clean_comment
            })
            # On ne l'ajoute pas à body_lines
        else:
            body_lines.append(raw_line)

    return header_lines, body_comments, body_lines


def format_header_markdown(header_lines):
    # Nettoyer les séparateurs % ===...===
    cleaned = []
    for idx, l in header_lines:
        s = l.strip()
        if re.match(r"^%\s*=+\s*$", s):
            continue
        # Retirer le % initial
        s_clean = re.sub(r"^%\s?", "", l)
        cleaned.append(s_clean)
    
    # Éliminer les lignes vides en tête et en queue
    while cleaned and not cleaned[0].strip():
        cleaned.pop(0)
    while cleaned and not cleaned[-1].strip():
        cleaned.pop()
    
    return "\n".join(cleaned)


def format_body_comments(body_comments):
    if not body_comments:
        return "_Aucune note éditoriale ou commentaire interne dans le corps de ce chapitre._"
    
    # Regrouper les commentaires consécutifs par bloc de contexte
    grouped = []
    current_block = []
    last_idx = -2

    for c in body_comments:
        if c["line_num"] == last_idx + 1:
            current_block.append(c)
        else:
            if current_block:
                grouped.append(current_block)
            current_block = [c]
        last_idx = c["line_num"]
    if current_block:
        grouped.append(current_block)

    out = []
    for block in grouped:
        first = block[0]
        line_info = f"L{first['line_num']}" if len(block) == 1 else f"L{first['line_num']}-L{block[-1]['line_num']}"
        ctx = first["context"]
        text_lines = [b["text"] for b in block]
        text_block = "\n".join(text_lines)
        
        # Détection de tag fort (ex: A TRANCHER, A VÉRIFIER, source)
        if any("A TRANCHER" in t for t in text_lines):
            badge = "⚠️ **À TRANCHER**"
        elif any("A VÉRIFIER" in t for t in text_lines):
            badge = "🔍 **À VÉRIFIER**"
        elif any("source" in t.lower() for t in text_lines):
            badge = "📊 **Source / Données**"
        elif any("master" in t.lower() for t in text_lines):
            badge = "📝 **Alignement Master**"
        else:
            badge = "📌 **Note**"

        out.append(f"### {badge} — `{ctx}` ({line_info})\n\n```text\n{text_block}\n```\n")

    return "\n".join(out)


def clean_body_tex(body_lines):
    # Nettoyer les lignes blanches consécutives
    text = "".join(body_lines)
    # Remplacer plus de 2 sauts de lignes par 2 sauts de ligne
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Retirer les espaces en fin de ligne
    lines = [l.rstrip() for l in text.split("\n")]
    # Retirer les lignes blanches initiales
    while lines and not lines[0].strip():
        lines.pop(0)
    return "\n".join(lines).rstrip() + "\n"


def process_file(tex_path: Path, apply: bool = False):
    header_lines, body_comments, body_lines = parse_tex_file(tex_path)
    
    meta_path = tex_path.with_suffix(".meta.md")
    
    header_md = format_header_markdown(header_lines)
    body_md = format_body_comments(body_comments)
    
    meta_content = f"""# Métadonnées et notes de rédaction — {tex_path.name}

## 1. En-tête et traçabilité

```text
{header_md}
```

## 2. Notes éditoriales et décisions de rédaction (corps)

{body_md}
"""

    cleaned_tex = clean_body_tex(body_lines)
    
    print(f"\n[{tex_path.name}]")
    print(f"  - Lignes en-tête extraites  : {len(header_lines)}")
    print(f"  - Commentaires corps extraits : {len(body_comments)}")
    print(f"  - Lignes .tex d'origine     : {len(header_lines) + len(body_lines)}")
    print(f"  - Lignes .tex nettoyé       : {len(cleaned_tex.splitlines())}")
    print(f"  - Fichier meta cible        : {meta_path.name}")
    
    if apply:
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write(meta_content)
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(cleaned_tex)
        print(f"  -> Écrit {meta_path.name} et mis à jour {tex_path.name}")
    
    return meta_content, cleaned_tex


def main():
    parser = argparse.ArgumentParser(description="Extraire les commentaires LaTeX vers .meta.md")
    parser.add_argument("--apply", action="store_true", help="Appliquer les modifications (écrit les .meta.md et modifie les .tex)")
    parser.add_argument("--dir", default="docs/paper/article-court/overleaf/chapters", help="Répertoire contenant les chapitres .tex")
    args = parser.parse_args()

    base_dir = Path(args.dir)
    if not base_dir.is_dir():
        print(f"Erreur : répertoire {base_dir} introuvable", file=sys.stderr)
        sys.exit(1)

    print(f"Mode : {'APPLY (écriture)' if args.apply else 'DRY-RUN (simulation)'}")
    print(f"Dossier : {base_dir}")

    for filename in CHAPTER_FILES:
        tex_path = base_dir / filename
        if not tex_path.exists():
            print(f"Attention : {tex_path} n'existe pas, ignoré.")
            continue
        process_file(tex_path, apply=args.apply)

    if not args.apply:
        print("\nNote : exécuté en mode --dry-run. Utilisez --apply pour effectuer les modifications.")

if __name__ == "__main__":
    main()
