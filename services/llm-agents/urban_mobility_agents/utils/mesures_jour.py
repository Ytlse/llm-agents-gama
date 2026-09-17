"""Écriture des mesures au point du jour — ticket 093, lot 3.

Ce module est la COUTURE entre le contrôleur et le module de calcul
`scripts.analysis.mesures`, qui est pur et ne connaît ni Prometheus ni la simulation. Le même
calcul alimente les CSV et les séries : ils ne peuvent pas diverger.

QUAND
-----
Au point de reprise quotidien, à 3 h simulées, juste après son écriture — donc sur une journée
close, tampons de mémoire courte vides, et avec l'instantané d'état que le point vient de
produire.

FAIL-OPEN, SANS DISCUSSION
--------------------------
Une mesure qui échoue lève une `[ALARME]` et laisse le run continuer. Perdre les mesures d'une
journée coûte une journée de courbe ; faire tomber un run de soixante jours coûte le run.

ÉTEINT PAR DÉFAUT
-----------------
`agent.mesures_jour_enabled`. Éteint, ce module ne lit rien, n'écrit rien, et ne déclare aucune
famille de métrique — une famille déclarée sans données se lirait comme une mesure à zéro.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger
from settings import _run_artifacts_disabled, settings

_gauges: dict[str, Any] | None = None


def _gauges_prometheus() -> dict[str, Any]:
    """Déclare les familles à la PREMIÈRE écriture, jamais à l'import (cf. H1/H2)."""
    global _gauges
    if _gauges is None:
        from prometheus_client import Gauge

        from scripts.analysis.mesures.prometheus import _familles

        _gauges = _familles(lambda nom, aide, labels: Gauge(nom, aide, labels))
    return _gauges


def reinitialiser() -> None:
    """Oublie les gauges déclarées, et les RETIRE du registre. Réservé aux tests.

    Oublier la référence sans désenregistrer faisait lever « Duplicated timeseries » à la
    déclaration suivante — et comme tout ici est fail-open, l'erreur était ravalée en alarme :
    le run continuait sans aucune série, sans que rien d'autre ne le dise.
    """
    global _gauges
    if _gauges:
        from prometheus_client import REGISTRY

        for gauge in _gauges.values():
            try:
                REGISTRY.unregister(gauge)
            except KeyError:
                pass
    _gauges = None


def actif() -> bool:
    return bool(getattr(settings.agent, "mesures_jour_enabled", False)) and not (
        _run_artifacts_disabled()
    )


def ecrire_mesures_du_jour(workdir: Path | str | None = None) -> int:
    """Recalcule, réécrit les CSV et règle les séries. Rend le dernier jour clos publié (0 sinon).

    Ne lève jamais : le retour vaut 0 quand rien n'a pu être mesuré, et l'alarme dit pourquoi.
    """
    if not actif():
        return 0
    racine = Path(workdir or settings.workdir)
    try:
        from scripts.analysis.mesures.calcul import calculer
        from scripts.analysis.mesures.ecriture import ecrire
        from scripts.analysis.mesures.prometheus import publier

        mesures = calculer(racine)
        ecrire(mesures, racine / settings.app.mesures_dir)
        jour = publier(mesures, _gauges_prometheus())
        logger.info(
            f"[mesures] jour {jour} clos — {len(mesures.choix_modal)} ligne(s) de choix modal, "
            f"{len(mesures.habitudes)} d'habitude, {len(mesures.memoire)} de mémoire ; "
            f"{mesures.trajets_rejoues} trajet(s) et {mesures.rappels_rejoues} rappel(s) "
            f"rejoué(s) écarté(s)"
        )
        if not mesures.operations_tracees:
            logger.warning(
                "[mesures] operations_concept.jsonl absent : les colonnes d'opérations de "
                "concept restent VIDES. « Aucune contradiction » et « on ne mesure pas les "
                "contradictions » ne doivent pas se lire pareil — activez "
                "agent.trace_concepts_enabled."
            )
        return jour
    except Exception as exc:  # noqa: BLE001 — l'observation ne fait pas tomber la simulation
        logger.error(
            f"[ALARME] [mesures] écriture impossible pour {racine} ({exc!r}) — la journée "
            f"n'aura pas de ligne dans les CSV, et les séries gardent leur valeur précédente. "
            f"Le run continue."
        )
        return 0
