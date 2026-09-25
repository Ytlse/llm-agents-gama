"""Rejeu à prompt exact — une réponse déjà obtenue se ressert tant que le prompt n'a pas bougé.

Les deux bras d'une expérience mémoire (le traité, puis le témoin) posent les mêmes questions au
même modèle jusqu'à l'événement. À température 0, gemini-3.5-flash-lite rend pourtant des
réponses différentes à des prompts identiques. Les bras divergeaient dès le premier soir (a09 V2,
2026-09-25), et l'écart mesuré mêlait l'effet de l'événement au bruit du modèle.

Chaque tâche servie par un fournisseur est consignée sous la clé de SON prompt exact : catégorie,
messages rendus pour cette tâche seule, paramètres, contraintes de routage. La consignation se
fait dans un espace que nomme l'appelant (`LLMRequest.espace_rejeu`). Une tâche de même clé dans
le même espace reçoit la réponse consignée, sans appel. Une requête sans espace garde exactement
le comportement antérieur.

La clé est celle de la tâche, pas du lot : le micro-batching fusionne des tâches selon leur ordre
d'arrivée, qui n'est pas le même d'un bras à l'autre.

Stockage : un fichier JSON par clé, `<racine>/<espace>/<clé>.json`, écrit par renommage atomique.
L'API lit, le worker écrit, sur le même montage : aucun verrou n'est nécessaire, et un espace
s'inspecte ou s'archive comme un répertoire.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from llm_gateway.telemetry.logger import get_logger

logger = get_logger(__name__)

_ESPACE_VALIDE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")


def espace_valide(espace: str | None) -> str | None:
    """L'espace tel quel s'il peut nommer un répertoire sans en sortir, None sinon."""
    if espace and _ESPACE_VALIDE.match(espace) and ".." not in espace:
        return espace
    return None


def cle_rejeu(request: Any, messages: list[Any]) -> str:
    """Empreinte du prompt exact d'UNE tâche.

    Entrent : la catégorie, les messages rendus (tout ce que l'adaptateur envoie), les
    paramètres (température, budget, variante…), le fournisseur épinglé, les instances admises
    (triées : c'est un ensemble) et le contexte. N'entrent pas : l'origine (elle nomme le bras,
    qui diffère par construction), l'identifiant de tâche, l'espace lui-même.
    """
    corps = {
        "category": request.category,
        "messages": [
            m.model_dump(mode="json") if hasattr(m, "model_dump") else m for m in messages
        ],
        "parameters": request.parameters,
        "force_provider": request.force_provider,
        "instances_admises": sorted(set(request.instances_admises or [])),
        "context": request.context,
    }
    brut = json.dumps(corps, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(brut.encode("utf-8")).hexdigest()


class MagasinRejeu:
    """Réponses consignées, un fichier par clé et par espace."""

    def __init__(self, racine: Path):
        self.racine = Path(racine)

    def _chemin(self, espace: str, cle: str) -> Path:
        return self.racine / espace / f"{cle}.json"

    def lire(self, espace: str, cle: str) -> dict[str, Any] | None:
        chemin = self._chemin(espace, cle)
        try:
            return json.loads(chemin.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as exc:
            # Illisible = absent : la tâche part au fournisseur, rien n'est servi de travers.
            logger.error(
                f"[ALARME] Rejeu : enregistrement illisible, tâche envoyée au fournisseur | "
                f"espace={espace} cle={cle[:12]} erreur={exc!r}"
            )
            return None

    def ecrire(self, espace: str, cle: str, enregistrement: dict[str, Any]) -> bool:
        """Consigne une réponse. Vrai si elle est neuve ; la première consignée fait foi."""
        chemin = self._chemin(espace, cle)
        if chemin.exists():
            return False
        chemin.parent.mkdir(parents=True, exist_ok=True)
        provisoire = chemin.with_suffix(f".{os.getpid()}.{id(enregistrement)}.tmp")
        provisoire.write_text(
            json.dumps(enregistrement, ensure_ascii=False, default=str), encoding="utf-8"
        )
        os.replace(provisoire, chemin)
        return True


@lru_cache(maxsize=4)
def _magasin(racine: str) -> MagasinRejeu:
    return MagasinRejeu(Path(racine))


def magasin_rejeu(settings: Any) -> MagasinRejeu | None:
    """Le magasin déclaré par `rejeu.dir`, ou None si le rejeu n'est pas configuré."""
    rejeu = getattr(settings, "rejeu", None)
    racine = getattr(rejeu, "dir", None) if rejeu is not None else None
    return _magasin(str(racine)) if racine else None


def enregistrement(
    *, cle: str, espace: str, request: Any, provider: str, agents: list[Any],
    tokens_in: int, tokens_out: int, task_id: str,
) -> dict[str, Any]:
    """Ce qui est consigné pour une tâche servie : de quoi la resservir et savoir d'où elle vient."""
    return {
        "cle": cle,
        "espace": espace,
        "category": request.category,
        "provider": provider,
        "agents": [a.model_dump() if hasattr(a, "model_dump") else a for a in agents],
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "task_id": task_id,
        "origine": request.origine,
        "time": datetime.now(UTC).isoformat(timespec="seconds"),
    }


__all__ = ["MagasinRejeu", "cle_rejeu", "enregistrement", "espace_valide", "magasin_rejeu"]
