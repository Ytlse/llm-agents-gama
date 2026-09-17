"""Trace structurée des opérations de concept — ticket 093, lot 3.

POURQUOI UNE SOURCE DE PLUS
---------------------------
Les quatre opérations — créé, confirmé, précisé, contredit — sont déjà écrites, mais seulement
dans le journal lisible `memoires/<agent>.md`, dont l'en-tête dit lui-même : *« Ce n'est pas une
source de mesure. Les chiffres d'un article se prennent dans les métadonnées de la mémoire et dans
moves.csv, pas dans un texte formaté pour être lu. »* Le respecter suppose une source structurée,
et c'est ce fichier.

Ce que cette courbe porte est le mécanisme même de l'étude. Mesuré sur le run du 2026-09-16, cinq
agents, dix jours : **38 créés, 61 confirmés, 1 seul contredit** — l'unique contradiction étant
celle de Corinne, le jour du choc. Sans événement injecté, la mémoire n'a jamais rien révisé. Une
mesure qui ne distingue pas « aucune contradiction » de « on ne compte pas les contradictions »
laisserait ce résultat indécidable.

CE QUE CE MODULE GARANTIT
-------------------------
1. **Rien quand c'est éteint.** `agent.trace_concepts_enabled` est faux par défaut.
2. **Rien pendant le rejeu.** Une opération rejouée n'est pas une opération : la mémoire est
   gelée, elle ne décide rien. La compter gonflerait la courbe d'autant — défaut déjà constaté
   sur `trace_rappel`, qui n'a pas ce garde-fou et dont 81 lignes sur 196 sont du rejeu.
3. **Jamais d'exception vers l'appelant.** Une trace qui fait tomber un run de soixante jours
   serait pire que pas de trace du tout.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from loguru import logger
from settings import _run_artifacts_disabled, settings
from urban_mobility_agents.utils.reprise import gel_actif

# Le vocabulaire des quatre opérations, tel que le journal et les mesures le connaissent. Une
# opération hors de cette liste est tracée quand même : c'est en aval qu'elle est comptée à part,
# pour qu'un vocabulaire qui change en silence ne se lise pas comme un changement de comportement.
OPERATIONS = ("créé", "confirmé", "précisé", "contredit")


def tracer_operation(
    person_id: str,
    operation: str,
    quand: datetime | int | None,
    *,
    doc_id: str = "",
) -> None:
    """Écrit une ligne JSONL par opération de concept. Ne lève jamais.

    `quand` est l'instant SIMULÉ de l'opération. `sim_day` en est dérivé en UTC, comme le fait
    `trace_rappel` : les deux traces doivent se recouper jour par jour, et deux conventions de
    date rendraient leur superposition fausse d'un jour sans que rien ne le dise.
    """
    try:
        if not getattr(settings.agent, "trace_concepts_enabled", False):
            return
        if _run_artifacts_disabled():
            # Un test qui importe la chaîne mémoire n'ouvre pas un run et ne sème pas de
            # fichier dans le répertoire d'une simulation en cours (leçon du ticket 075).
            return
        if gel_actif():
            return
        instant = _epoch(quand)
        entree = {
            "sim_ts": instant,
            "sim_day": datetime.fromtimestamp(instant, tz=timezone.utc).strftime("%Y-%m-%d")
            if instant is not None
            else None,
            "person_id": str(person_id),
            "operation": str(operation),
            "doc_id": str(doc_id or ""),
        }
        with open(settings.app.trace_concepts_file, "a", encoding="utf-8") as flux:
            flux.write(json.dumps(entree, ensure_ascii=False, default=str) + "\n")
    except Exception as err:  # noqa: BLE001 — une trace ne fait jamais tomber une consolidation
        logger.warning(f"[trace_concepts] trace non écrite pour {person_id} ({err})")


def _epoch(quand: datetime | int | None) -> int | None:
    if quand is None:
        return None
    if isinstance(quand, datetime):
        return int(quand.timestamp())
    try:
        return int(quand)
    except (TypeError, ValueError):
        return None
