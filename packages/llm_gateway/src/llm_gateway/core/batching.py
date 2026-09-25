"""
core/batching.py — Logique pure de regroupement des requêtes en batchs.

La clé de batch garantit qu'on ne merge que des tâches parfaitement
compatibles : même catégorie, mêmes paramètres, même provider forcé,
même contrainte TPM.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable

from llm_gateway.core.models import _FALLBACK_PRIORITY_SCORE, LLMRequest

#: Identifiant de lot forgé par le worker : `batch_<8 hex>_<nombre d'agents>`.
_MOTIF_LOT = re.compile(r"^batch_[0-9a-f]+_(\d+)$")


def compute_batch_key(request: LLMRequest) -> str:
    """Clé de batch : MD5(catégorie + paramètres + provider forcé + min_tpm + instances admises
    + origine).

    ⚠ **Toute contrainte de routage doit entrer ici** (ticket 084). Un lot est servi par UNE
    instance : deux requêtes aux restrictions différentes fusionnées dans le même lot feraient
    servir l'une par un fournisseur qu'elle excluait, sans qu'aucune trace ne le dise. C'est la
    seule garde contre ce mélange, et elle est silencieuse quand on l'oublie.

    Les instances admises entrent TRIÉES et dédupliquées : c'est un ensemble, pas une séquence,
    et deux déclarations du même ensemble dans un ordre différent doivent partager leur lot.

    L'origine y entre aussi : un lot ne porte qu'UNE origine dans le journal des échanges, et
    fusionner deux clients l'attribuerait tout entier au premier. `None` (client qui ne la pose
    pas) garde la clé historique des lots sans origine.
    """
    params_str = json.dumps(request.parameters, sort_keys=True)
    admises = (
        ",".join(sorted(set(request.instances_admises)))
        if request.instances_admises
        else None
    )
    hash_str = hashlib.md5(
        f"{request.category}:{params_str}:{request.force_provider}:"
        f"{request.min_tpm_required}:{admises}:{request.origine}".encode()
    ).hexdigest()
    return f"{request.category}:{hash_str}"


def compute_priority_score(scores: Iterable[float | None]) -> float:
    """Score de priorité d'un lot = plus petit score fourni — plus bas = plus urgent.

    Les scores viennent de la catégorie (``CategorySpec.priority``) ; le gateway ne sait pas
    ce qu'ils mesurent (un horodatage de départ pour la mobilité). Aucun score → repli.
    """
    known = [s for s in scores if s is not None]
    return float(min(known)) if known else _FALLBACK_PRIORITY_SCORE


def compute_batch_max_agents(
    *,
    tpm_limit: int | None,
    rpm_limit: int,
    max_tokens_per_request: int | None,
    tokens_per_agent: int,
    plafond: int,
) -> int:
    """Combien d'agents une instance peut porter dans UNE requête fournisseur.

    Extrait de `GatewaySettings._resolve`, qui l'appelle désormais : c'est la seule
    définition du plafond de lot. L'estimation de coût d'une expérience
    (`experiences/lots.py`) la réutilise pour convertir des déplacements en requêtes, et
    une formule recopiée là-bas aurait dérivé en silence le jour où celle-ci change.

    `tokens_per_agent` = `assumed_prompt_tokens + assumed_output_tokens` ; `plafond` =
    `max_batch_agents`. Sans `tpm_limit`, le RPM sert de borne (une instance sans limite de
    jetons déclarée ne doit pas se retrouver plafonnée par une division par zéro) ; sans
    `max_tokens_per_request`, seul le plafond absolu joue.
    """
    tpm_bound = int(tpm_limit / tokens_per_agent) if tpm_limit else rpm_limit
    req_bound = (
        int(max_tokens_per_request / tokens_per_agent)
        if max_tokens_per_request
        else plafond
    )
    return max(1, min(tpm_bound, req_bound, rpm_limit, plafond))


def taille_de_lot(task_id: str | None) -> int | None:
    """Nombre d'agents fusionnés dans une requête, lu sur son identifiant de lot.

    Le worker nomme chaque requête `batch_<8 hex>_<n>` (cf. `worker/task_worker.py`) et
    `llm_exchanges.jsonl` en porte la trace : c'est le seul endroit où le journal d'échanges
    dit combien d'agents ont voyagé ensemble. Sans cette lecture, les `tokens_in`/`tokens_out`
    d'une ligne — qui sont ceux du LOT — passent pour ceux d'un agent, et toute estimation
    bâtie dessus est multipliée par le facteur de regroupement.

    Rend `None` si l'identifiant ne suit pas la forme : mieux vaut ignorer la ligne que la
    compter pour un agent, ce qui serait exactement l'erreur qu'on corrige.
    """
    if not task_id:
        return None
    m = _MOTIF_LOT.match(str(task_id))
    if not m:
        return None
    n = int(m.group(1))
    return n if n > 0 else None
