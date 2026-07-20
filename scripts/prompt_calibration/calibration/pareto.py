"""Archive de Pareto — phase 6 du ticket 004 (DC).

**Pourquoi.** Le composite écrase 6 dimensions (global, âge, occupation, genre,
motif, distance) en **un seul chiffre** via des poids arbitraires. Deux prompts
complémentaires — l'un fort en `âge`, l'autre fort en `motif` — peuvent partager
le même composite ; en n'en gardant qu'un, on jette des acquis. Le **front de
Pareto** conserve tous les prompts *non dominés*, sans les fondre en un chiffre.

**Dominance** (toutes les dimensions se **minimisent** — ce sont des losses) :
``A`` domine ``B`` si ``A`` est ≤ ``B`` sur **toutes** les dimensions ET
strictement < sur **au moins une**. Deux prompts qui se battent chacun sur une
dimension différente ne se dominent pas : ce sont des compromis légitimes.

**Usage (léger, DC).** Le composite + bootstrap **reste le critère d'acceptation**
dans chaque branche. En parallèle, l'archive des nœuds non dominés (toutes branches
confondues) sert à : (1) choisir des **points de départ diversifiés** pour les îlots
(GEPA) ; (2) fournir des **parents complémentaires** aux merges ; (3) rendre le veto
collatéral moins critique — une mutation qui troque une dimension contre une autre
reste archivée si elle est non dominée.

Fonctions **pures** (aucune dépendance store) : ``items`` est une liste de dicts
portant au moins une clé ``hash`` et les valeurs de chaque dimension.
"""

from __future__ import annotations

import math
from typing import Optional

# Dimensions par défaut de la dominance (les losses par dimension, hors composite,
# absent_penalty et length_penalty qui sont des agrégats/pénalités, pas des axes).
DEFAULT_DIMS = ["global", "age", "occupation", "genre", "motif", "distance"]

_EPS = 1e-9


def _vec(item: dict, dims: list[str]) -> Optional[list[float]]:
    """Vecteur des dimensions d'un item, ou ``None`` si une valeur manque."""
    out: list[float] = []
    for d in dims:
        v = item.get(d)
        if v is None:
            return None
        out.append(float(v))
    return out


def dominates(a: dict, b: dict, dims: list[str] = DEFAULT_DIMS) -> bool:
    """``a`` domine-t-il ``b`` ? (minimisation sur toutes les dimensions)

    ``True`` si ``a`` est au moins aussi bon (≤) que ``b`` sur toutes les
    dimensions ET strictement meilleur (<) sur au moins une. Un item auquel il
    manque une dimension ne domine ni n'est dominé (comparaison impossible).
    """
    va, vb = _vec(a, dims), _vec(b, dims)
    if va is None or vb is None:
        return False
    strictly_better = False
    for xa, xb in zip(va, vb):
        if xa > xb + _EPS:
            return False                      # pire sur une dimension → pas de dominance
        if xa < xb - _EPS:
            strictly_better = True
    return strictly_better


def pareto_front(items: list[dict], dims: list[str] = DEFAULT_DIMS) -> list[dict]:
    """Sous-ensemble des items **non dominés**.

    Un item est retenu s'il n'est dominé par aucun autre. Les items privés d'une
    dimension sont exclus (on ne peut pas les situer dans l'espace des objectifs).
    Déduplication par ``hash`` : un même prompt ne figure qu'une fois.
    """
    evaluable = [it for it in items if _vec(it, dims) is not None]
    seen: dict[str, dict] = {}
    for it in evaluable:
        seen.setdefault(it["hash"], it)
    unique = list(seen.values())
    front = []
    for a in unique:
        if not any(dominates(b, a, dims) for b in unique if b is not a):
            front.append(a)
    return front


def _ranges(front: list[dict], dims: list[str]) -> dict[str, tuple[float, float]]:
    """Étendue (min, max) de chaque dimension sur le front (pour normaliser)."""
    ranges = {}
    for d in dims:
        vals = [float(it[d]) for it in front]
        ranges[d] = (min(vals), max(vals)) if vals else (0.0, 1.0)
    return ranges


def _norm(it: dict, dims: list[str], ranges: dict[str, tuple[float, float]]) -> list[float]:
    out = []
    for d in dims:
        lo, hi = ranges[d]
        span = hi - lo
        out.append((float(it[d]) - lo) / span if span > _EPS else 0.0)
    return out


def _dist(u: list[float], v: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(u, v)))


def diversified_seeds(front: list[dict], k: int,
                      dims: list[str] = DEFAULT_DIMS) -> list[dict]:
    """``k`` points **diversifiés** du front (départs d'îlots, DC/GEPA).

    Sélection glouton *farthest-point* dans l'espace des objectifs normalisé : on
    part du meilleur composite (ou du premier point si absent), puis on ajoute à
    chaque tour le point le plus **éloigné** de ceux déjà retenus. On échantillonne
    ainsi les compromis extrêmes plutôt que de cloner ``k`` fois le champion.

    Si le front a moins de ``k`` points, ils sont tous renvoyés (complétés par
    répétition cyclique par l'appelant si besoin).
    """
    if k <= 0 or not front:
        return []
    if len(front) <= k:
        return list(front)
    ranges = _ranges(front, dims)
    coords = {it["hash"]: _norm(it, dims, ranges) for it in front}

    # Point de départ : plus faible composite si disponible, sinon le premier.
    start = min(front, key=lambda it: it.get("composite", math.inf))
    chosen = [start]
    while len(chosen) < k:
        chosen_coords = [coords[c["hash"]] for c in chosen]
        best, best_d = None, -1.0
        for it in front:
            if it in chosen:
                continue
            d = min(_dist(coords[it["hash"]], cc) for cc in chosen_coords)
            if d > best_d:
                best, best_d = it, d
        if best is None:
            break
        chosen.append(best)
    return chosen


def complementary_pair(front: list[dict],
                       dims: list[str] = DEFAULT_DIMS) -> Optional[tuple[dict, dict]]:
    """Paire de parents la plus **complémentaire** du front (merge, DC).

    Renvoie les deux nœuds non dominés les plus éloignés dans l'espace des
    objectifs normalisé — l'un fort là où l'autre est faible, matière première d'un
    crossover utile. ``None`` si le front compte moins de deux points.
    """
    if len(front) < 2:
        return None
    ranges = _ranges(front, dims)
    coords = {it["hash"]: _norm(it, dims, ranges) for it in front}
    best, best_d = None, -1.0
    for i, a in enumerate(front):
        for b in front[i + 1:]:
            d = _dist(coords[a["hash"]], coords[b["hash"]])
            if d > best_d:
                best, best_d = (a, b), d
    return best
