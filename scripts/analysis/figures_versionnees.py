"""Avertit quand une figure régénérée écrase un fichier SUIVI PAR GIT.

Ticket 039, pas 6. Les figures de l'article vivent dans `docs/paper/figures/`, qui est
versionné — et c'est voulu : un chapitre gelé doit pouvoir montrer la figure qu'il cite.
Mais `plot_experiences.py` et `plot_familles.py` écrivent là PAR DÉFAUT. Chaque
régénération commitée ajoute donc un blob de plus dans le pack, définitivement, alors
qu'une seule version a jamais d'intérêt : la dernière.

Le dépôt a mesuré que le problème n'est PAS le poids installé — les 34 Mo suivis sous
`docs/paper/` ont chacun exactement UNE version dans l'historique, ce que git stocke
au mieux. Le problème est la croissance à venir, et elle est déjà amorcée (les quatre
`familles_composite_l1_*` datent du 2026-09-14, les deux `comparaison_experiences_*`
du 2026-09-09). D'où : pas de migration LFS, qui n'économiserait rien et coûterait une
dépendance à chaque clone — mais une régénération qui ANNONCE ce qu'elle vient de créer.

Ce module n'interdit rien et n'échoue jamais : il rend visible, au moment où ça se
produit, un coût qui ne se voit autrement qu'au `git status`.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger("figures")

RACINE = Path(__file__).resolve().parents[2]


def _suivi_par_git(chemin: Path) -> bool:
    """Le fichier est-il versionné ? Toute panne de git répond « non » — on n'alarme qu'à coup sûr."""
    try:
        # argv fixe, chemin passé après `--` : aucun chemin ne peut se faire lire en option.
        # check=False : le code de retour EST la réponse (1 = non suivi), pas une erreur.
        issue = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", str(chemin)],
            cwd=RACINE, capture_output=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return issue.returncode == 0


def signaler(ecrits: list[Path]) -> None:
    """Journalise les figures écrites, et distingue celles qui coûteront un blob de plus."""
    versionnees = [p for p in ecrits if _suivi_par_git(p)]
    for chemin in ecrits:
        try:
            relatif = chemin.relative_to(RACINE)
        except ValueError:
            relatif = chemin
        taille = chemin.stat().st_size / 1024 if chemin.is_file() else 0
        logger.info("Figure écrite : %s (%.0f Ko)", relatif, taille)

    if not versionnees:
        return
    poids = sum(p.stat().st_size for p in versionnees if p.is_file()) / 1024
    logger.warning(
        "%d figure(s) suivie(s) par git viennent d'être écrasées (%.0f Ko). "
        "Un `git commit` les ajoutera au pack DÉFINITIVEMENT, en plus des versions "
        "précédentes. Ne committez une figure que si un chapitre la cite dans son état "
        "gelé ; pour une exploration, écrivez ailleurs : --sortie docs/synthesis/<nom>",
        len(versionnees), poids,
    )
