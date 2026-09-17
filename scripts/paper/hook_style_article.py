#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hook `PostToolUse` : passe le détecteur de style sur un chapitre qui vient d'être écrit.

Lit sur l'entrée standard la charge utile du hook, n'agit que si l'écriture visait un `.md`
de `docs/paper/article/fr/` ou `en/`, et affiche le rapport du détecteur.

**Fail-open par construction.** Ce script sort TOUJOURS en 0 et n'écrit jamais sur le canal
qui bloquerait l'outil. Charge utile illisible, script de détection absent, dépassement de
délai : l'écriture aboutit. Un contrôle de style qui empêcherait d'écrire serait un bug, pas
une fonctionnalité — et il ne voit de toute façon pas les écritures passées par `Bash`
(`sed -i`, heredoc, `>`), ce que la règle écrite couvre à sa place.

Lancement direct, pour le test :
    echo '{"tool_input":{"file_path":"docs/paper/article/fr/02_related_work.md"}}' \
      | python3 scripts/paper/hook_style_article.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

DELAI = 12  # secondes ; le hook déclaré a 15 s, on rend la main avant d'être tué
DOSSIERS = ("fr", "en")


def racine() -> Path:
    depuis_env = os.environ.get("CLAUDE_PROJECT_DIR")
    if depuis_env and Path(depuis_env).is_dir():
        return Path(depuis_env)
    return Path(__file__).resolve().parents[2]


def concerne(chemin: str) -> Path | None:
    """Le chemin désigne-t-il un chapitre de l'article ?"""
    if not chemin or not chemin.endswith(".md"):
        return None
    p = Path(chemin)
    if p.parent.name not in DOSSIERS:
        return None
    if "docs/paper/article" not in p.as_posix():
        return None
    return p


def main() -> int:
    try:
        charge = json.load(sys.stdin)
    except Exception:
        return 0  # charge utile illisible : on ne dit rien, on ne bloque rien

    chemin = concerne(str(charge.get("tool_input", {}).get("file_path", "")))
    if chemin is None:
        return 0

    base = racine()
    detecteur = base / "scripts" / "paper" / "detecter_artefacts_ia.py"
    if not detecteur.exists():
        print(f"(contrôle de style ignoré : {detecteur} est absent)")
        return 0

    try:
        r = subprocess.run(
            [sys.executable, str(detecteur), "--fichier", str(chemin)],
            capture_output=True, text=True, timeout=DELAI, cwd=str(base),
        )
    except subprocess.TimeoutExpired:
        print(f"(contrôle de style abandonné après {DELAI} s — l'écriture, elle, a abouti)")
        return 0
    except Exception as e:  # noqa: BLE001 — aucune exception ne doit remonter jusqu'à l'outil
        print(f"(contrôle de style indisponible : {type(e).__name__})")
        return 0

    print(f"\n🎨 Style de l'article — {chemin.parent.name}/{chemin.name}")
    print(r.stdout.rstrip() or "(pas de sortie)")
    if r.returncode != 0:
        print("Rappel : le détecteur est un signal, pas une autorité. Un passage signalé peut "
              "être conservé — mais la décision s'énonce.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
