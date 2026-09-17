"""L'instant simulé où ce run a commencé — ticket 075.

POURQUOI UN MODULE POUR SI PEU
------------------------------
Trois mécanismes ont besoin de savoir **combien de jours simulés se sont écoulés** depuis le
début du run : la progression de la date météo (`weather_draw`), le point de reprise quotidien,
et le journal de mémoire qui date ses sections. Le contrôleur connaît déjà cet instant — il le
retient dans `_sim_start_ts` pour dater les accidents — mais il est hors d'atteinte du chemin
d'une décision, qui traverse l'agent et non le contrôleur. Le faire descendre en paramètre
aurait demandé de toucher une dizaine de signatures pour une valeur qui ne change jamais de tout
le run.

⚠ **L'ancre se POSE, elle ne se devine pas.** Sans elle, `jours_ecoules` rend zéro : le premier
jour du run, ce qui est la seule valeur sûre et qui reproduit le comportement d'avant le ticket.
Elle le DIT une fois, parce qu'une ancre absente sur un run long ferait relire éternellement le
bulletin du premier jour sans qu'aucune ligne ne le signale.

⚠ **À la reprise à chaud, l'ancre vient du point de reprise, pas du premier timestamp observé.**
GAMA rejoue depuis son t0 : se réancrer sur ce qu'on voit ferait rembobiner la météo de tout le
monde, et les soixante journées cesseraient d'être consécutives.
"""

from __future__ import annotations

from loguru import logger
from sim_clock import wall_clock

_ancre: int | None = None
_absence_signalee = False


def ancrer(timestamp: int, *, origine: str = "premier timestamp observé") -> None:
    """Pose l'instant de départ du run. Sans effet si une ancre est déjà posée.

    La première ancre gagne : une reprise restaure la sienne AVANT que le rejeu ne fasse
    observer son premier timestamp, et l'ancre restaurée ne doit pas être écrasée par lui.
    """
    global _ancre
    if _ancre is not None:
        if int(timestamp) != _ancre:
            logger.info(
                f"[ancre] ancre déjà posée à {wall_clock(_ancre)} — la proposition "
                f"{wall_clock(int(timestamp))} ({origine}) est ignorée."
            )
        return
    _ancre = int(timestamp)
    logger.info(f"[ancre] début du run ancré au {wall_clock(_ancre)} ({origine}).")


def ancre() -> int | None:
    """L'instant de départ du run, ou `None` s'il n'est pas encore connu."""
    return _ancre


def reinitialiser() -> None:
    """Oublie l'ancre. Réservé aux tests et à la fin d'un run."""
    global _ancre, _absence_signalee
    _ancre = None
    _absence_signalee = False


def jours_ecoules(timestamp: int) -> int:
    """Jours simulés ENTIERS écoulés depuis le début du run, jamais négatif.

    Compté en jours de CALENDRIER mural et non en tranches de 86 400 s : le run démarre à
    5 h du matin, et une tranche ferait changer de jour à 5 h du matin le lendemain, au milieu
    de la pointe. Le jour simulé doit changer quand la date change, comme pour un humain.
    """
    global _absence_signalee
    if _ancre is None:
        if not _absence_signalee:
            _absence_signalee = True
            logger.warning(
                "[ancre] aucune ancre posée : tout ce qui dépend du nombre de jours écoulés "
                "se comporte comme au premier jour du run (progression météo figée). "
                "Attendu seulement avant le premier /sync."
            )
        return 0
    ecart = (wall_clock(int(timestamp)).date() - wall_clock(_ancre).date()).days
    return max(0, ecart)
