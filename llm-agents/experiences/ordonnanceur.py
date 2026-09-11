"""Ordonnanceur de la file d'attente (ticket 035, spec parallelisation_experiences, R2b/R7/R12).

Tourne côté **hôte** (comme le tableau de bord), car il relance les expériences via
`docker compose exec`. Chaque tour :

1. **réconcilie** les fantômes DANS le conteneur (`reconcilier` teste la vie des pid, ce qui
   n'a de sens que dans le namespace où les exécutions vivent) ;
2. **promeut** en FIFO les expériences en file dont toutes les clés sont désormais libres
   (`reservations.promouvoir_pretes`), sans jamais préempter une exécution active (R2c) ;
3. **relance** chaque promue, en tâche de fond, via `docker compose exec … lancer` — qui
   réservera ses clés à son démarrage et rejouera les contrôles de lancement (R2d).

La logique est isolée dans `tour()` avec ses effets injectés (`reconcilieur`, `lanceur`), pour
être testable sans Docker.
"""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from loguru import logger

from experiences import reservations as R

INTERVALLE_S = 5.0

# Base d'appel dans le conteneur, alignée sur `EXPERIENCES_PY` du Makefile.
_EXEC_BASE = [
    "docker",
    "compose",
    "exec",
    "-T",
    "-e",
    "EXPERIENCES_DIR=/app/data/experiences",
    "-e",
    "JEUX_DIR=/app/data/jeux",
    "-e",
    "REFERENTIEL_ENQUETE=/app/scripts/data/population/cerema_values.yaml",
    "controller",
    "python",
    "-m",
    "experiences",
]


def _racine_depot() -> Path:
    return Path(__file__).resolve().parents[2]


def _argv_lancer(entree: dict) -> list[str]:
    args = entree.get("args") or {}
    argv = [*_EXEC_BASE, "lancer", "--experience", entree["exp"]]
    if args.get("reprendre"):
        argv.append("--reprendre")
    if args.get("accepter_perime"):
        argv.append("--accepter-perime")
    # Attendre la fenêtre est le défaut : on ne transmet que le refus explicite.
    if args.get("attendre_fenetre") is False:
        argv.append("--ne-pas-attendre-fenetre")
    return argv


def _reconcilier_conteneur() -> None:
    """Réconcilie les fantômes dans le conteneur. Fail-open : un échec (conteneur down) ne bloque
    pas le tour ; les promotions n'auront simplement pas les clés fraîchement libérées."""
    try:
        subprocess.run(
            [*_EXEC_BASE, "reconcilier"],
            cwd=str(_racine_depot()),
            check=False,
            capture_output=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning(f"[ordonnanceur] réconciliation conteneur impossible : {e}")


def _lancer_detache(entree: dict) -> None:
    """Relance l'expérience promue en tâche de fond (ne bloque pas la boucle)."""
    argv = _argv_lancer(entree)
    logger.info(f"[ordonnanceur] relance {entree['exp']} : {' '.join(argv)}")
    subprocess.Popen(
        argv,
        cwd=str(_racine_depot()),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        env={**os.environ, "TERM": "dumb", "NO_COLOR": "1", "PYTHONUNBUFFERED": "1"},
    )


def tour(
    reconcilieur: Callable[[], None] = _reconcilier_conteneur,
    lanceur: Callable[[dict], None] = _lancer_detache,
) -> list[str]:
    """Un tour : réconcilie, promeut en FIFO, relance. Renvoie les expériences promues."""
    reconcilieur()
    promues = R.promouvoir_pretes()
    for entree in promues:
        lanceur(entree)
    return [e["exp"] for e in promues]


def boucle(intervalle_s: float = INTERVALLE_S) -> int:
    """Boucle jusqu'à interruption. Journalise début, chaque promotion, et le succès (silence = vivant)."""
    logger.info(f"[ordonnanceur] démarré — tour toutes les {intervalle_s:.0f} s")
    tours = 0
    try:
        while True:
            promues = tour()
            tours += 1
            if promues:
                logger.info(f"[ordonnanceur] promues : {promues}")
            elif tours % 60 == 0:
                logger.info(f"[ordonnanceur] vivant — {tours} tours, file traitée")
            time.sleep(intervalle_s)
    except KeyboardInterrupt:
        logger.info(f"[ordonnanceur] arrêté après {tours} tours")
        return 0


__all__ = ["boucle", "tour"]
