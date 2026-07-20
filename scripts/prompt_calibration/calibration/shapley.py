"""Attribution de crédit Shapley — phase 5 du ticket 004 (DB).

**Pourquoi une répartition de crédit et pas un simple retrait bloc-à-bloc.** Mesurer
``score(prompt − bloc_i) − score(prompt)`` suppose les blocs **indépendants**. Deux
cas réels mettent cette hypothèse en défaut :

- **Redondance** : deux blocs disent la même chose → retirer l'un ne change rien
  (l'autre compense), chacun paraît inutile pris isolément, alors qu'en retirer
  *les deux* serait coûteux. Le retrait bloc-à-bloc conclut « supprimez les deux ».
- **Synergie** : un bloc « pense au vélo » n'agit que combiné à « par beau temps » ;
  isolément chacun semble neutre, mais le retrait depuis le prompt complet leur
  attribue *chacun* toute la synergie (double comptage — la somme dépasse le gain réel).

**Principe.** Chaque bloc mutable = un **joueur** ; la « valeur » d'une coalition de
blocs = la loss (composite) du prompt reconstruit avec ces blocs seulement (plus les
blocs verrouillés, toujours présents). La **valeur de Shapley** d'un bloc est sa
contribution marginale moyenne sur tous les ordres d'ajout possibles — elle répartit
*exactement* le gain total entre les blocs (redondances et synergies comprises).

**Convention de signe.** On mesure la **réduction de loss** apportée par un bloc :
``φ_i = moyenne des (v(coalition) − v(coalition ∪ {i}))``. Positif = bloc utile
(sa présence fait baisser la loss), négatif = bloc nuisible (``φ > 2`` utile,
``φ < -2`` nuisible, cf. ``USEFUL_THRESHOLD``/``HARMFUL_THRESHOLD``). Les consommateurs
(carte colorée du dashboard, contexte du mutateur, passe de compaction) lisent la
méthode ``shapley`` persistée dans la table ``ablations``.

**Budget (Truncated Monte-Carlo Shapley, Ghorbani & Zou 2019).** On échantillonne
``M`` permutations aléatoires plutôt que les ``N!`` ordres ; dans chaque permutation,
dès que la coalition courante atteint la loss du prompt complet
(``|v_full − v_courant| < truncation_tol``), les blocs restants ont un marginal ≈ 0 et
ne sont **pas évalués** (grosse économie). Une coalition = un prompt = une clé de
cache : les coalitions se répètent entre permutations (et entre runs) → beaucoup
d'évals gratuites (``store`` content-addressed).
"""

from __future__ import annotations

import random
from typing import Callable

# Seuils de verdict (docs §2.1 : φ > +2 utile, φ < −2 nuisible) — orientent la carte
# colorée du dashboard et le contexte du mutateur.
USEFUL_THRESHOLD = 2.0
HARMFUL_THRESHOLD = -2.0


def planned_permutations(base: int, addon_per_accept: int, accepted: int,
                         cap: int) -> int:
    """Nombre de permutations d'une passe Shapley en mode CUMULATIF.

    ``base`` permutations au départ, ``addon_per_accept`` de plus par mutation
    acceptée, plafonné à ``cap``. Le plafond est relu dans la config à chaque
    passe : le modifier en cours de campagne (YAML) étend ou raccourcit la
    séquence à la reprise suivante, sans invalider le cache — les permutations
    forment une séquence stable par préfixe (voir :func:`shapley_scores`).
    """
    if addon_per_accept <= 0:
        return base
    return min(base + accepted * addon_per_accept, max(base, cap))


def coalition_blocks(blocks: list[dict], present_names: set[str]) -> list[dict]:
    """Blocs d'une coalition, dans l'ordre du prompt.

    Les blocs **verrouillés** (``mutable=False``, ex. ``json_schema``) sont
    toujours présents (ils ne sont pas des joueurs) ; les blocs mutables ne sont
    gardés que si leur nom est dans ``present_names``. L'ordre d'origine est
    préservé → le prompt reconstruit est identique à « prompt complet moins les
    blocs absents », quel que soit l'ordre d'ajout de la permutation.
    """
    return [b for b in blocks
            if (not b["mutable"]) or b["name"] in present_names]


def shapley_scores(blocks: list[dict],
                   scores_fn: Callable[[list[dict]], dict[str, float]],
                   *, m_permutations: int = 25, truncation_tol: float = 0.5,
                   seed: int = 0) -> dict[str, dict[str, float]]:
    """Valeurs de Shapley (Monte-Carlo tronqué) **par composante de score**.

    ``scores_fn(coalition_blocks) -> {clé: valeur}`` renvoie le vecteur de scores
    du prompt reconstruit (au moins la clé ``composite``, qui pilote la
    troncature ; typiquement toutes les dimensions de ``Scores``). Renvoie
    ``{nom_bloc: {clé: φ_clé}}`` — chaque composante a sa propre décomposition,
    obtenue sur les **mêmes évals** (le composite étant linéaire dans les
    dimensions, ``φ_composite = Σ_d w_d · φ_d`` exactement, troncature comprise).

    Propriété d'efficacité (sans troncature) : ``Σ_i φ_i(clé) = v_clé(∅) −
    v_clé(complet)`` pour chaque clé — le gain total est réparti exactement.

    **Stabilité par préfixe** : les permutations sont tirées séquentiellement d'un
    unique RNG seedé une fois, et chaque tour ne consomme qu'un ``shuffle`` (dont
    la consommation ne dépend que du nombre de joueurs). À ``seed`` et liste de
    joueurs identiques, la permutation n° i est donc la même quel que soit
    ``m_permutations`` : augmenter ``m`` ÉTEND la séquence sans changer les
    premières permutations. C'est ce qui rend le mode cumulatif
    (:func:`planned_permutations`) compatible avec le cache content-addressed —
    les coalitions du socle sont rejouées à l'identique d'une passe à l'autre.
    """
    players = [b["name"] for b in blocks if b["mutable"]]
    if not players:
        return {}

    all_names = set(players)
    v_full = scores_fn(coalition_blocks(blocks, all_names))
    v_empty = scores_fn(coalition_blocks(blocks, set()))
    keys = list(v_full.keys())

    phi = {n: {k: 0.0 for k in keys} for n in players}
    rng = random.Random(seed)
    m = max(1, m_permutations)
    for _ in range(m):
        perm = players[:]
        rng.shuffle(perm)
        present: set[str] = set()
        v_prev = v_empty
        for name in perm:
            # Troncature : la coalition atteint déjà la loss complète → les
            # marginaux restants de cette permutation sont ≈ 0, on ne paie pas.
            if abs(v_full["composite"] - v_prev["composite"]) < truncation_tol:
                break
            present.add(name)
            v_curr = scores_fn(coalition_blocks(blocks, present))
            for k in keys:                      # réduction de loss du bloc, par clé
                phi[name][k] += v_prev.get(k, 0.0) - v_curr.get(k, 0.0)
            v_prev = v_curr
    return {n: {k: v / m for k, v in phi[n].items()} for n in players}


def shapley_values(blocks: list[dict], value_fn: Callable[[list[dict]], float],
                   *, m_permutations: int = 25, truncation_tol: float = 0.5,
                   seed: int = 0) -> dict[str, float]:
    """Valeurs de Shapley (Monte-Carlo tronqué) des blocs mutables.

    ``value_fn(coalition_blocks) -> composite`` renvoie la loss du prompt
    reconstruit avec ces blocs. Renvoie ``{nom_bloc: φ}`` où ``φ`` est la
    **réduction moyenne de loss** apportée par le bloc (positif = utile).
    Enveloppe scalaire de ``shapley_scores`` (une seule composante).
    """
    phi = shapley_scores(blocks, lambda c: {"composite": value_fn(c)},
                         m_permutations=m_permutations,
                         truncation_tol=truncation_tol, seed=seed)
    return {n: p["composite"] for n, p in phi.items()}


def build_shapley_results(blocks: list[dict], phi: dict[str, float | dict],
                          weights: dict[str, float] | None = None) -> list[dict]:
    """Formate les valeurs de Shapley en résultats de contribution par bloc.

    Schéma (``bloc``, ``content``, ``delta``, ``useful``, ``harmful``, ``diag``,
    ``detail``, ``modes``) consommé tel quel par ``format_ablation_for_mutation`` et
    la passe de compaction. ``delta = φ`` (réduction de loss), trié décroissant
    (blocs utiles en tête).

    ``phi`` accepte les deux formes : ``{bloc: φ_composite}`` (scalaire, sans
    détail) ou ``{bloc: {clé: φ_clé}}`` (issue de ``shapley_scores``). Avec
    ``weights``, ``detail`` = contributions **pondérées** au φ composite
    (``w_d × φ_d``, en pts de composite — elles somment à ``delta``).

    ``modes`` (matrice bloc × mode) : les clés ``mode:{m}`` de ``phi`` — parts
    modales décomposées sur les mêmes évals — deviennent ``{m: poussée}`` où la
    poussée est l'effet de la **présence** du bloc sur la part du mode (pts de %,
    « + » = le bloc augmente cette part). φ mesurant une *réduction*
    (``v_sans − v_avec``), la poussée vaut ``−φ_mode``.
    """
    by_name = {b["name"]: b for b in blocks}
    results = []
    for name, val in phi.items():
        detail: dict[str, float] = {}
        modes: dict[str, float] = {}
        if isinstance(val, dict):
            comp = val["composite"]
            if weights:
                detail = {d: val[d] * w for d, w in weights.items()
                          if d in val and w > 0}
            modes = {k.split(":", 1)[1]: -v for k, v in val.items()
                     if k.startswith("mode:")}
        else:
            comp = val
        content = by_name.get(name, {}).get("content", "")
        results.append({"bloc": name, "content": content, "value": comp,
                        "delta": comp, "useful": comp > USEFUL_THRESHOLD,
                        "harmful": comp < HARMFUL_THRESHOLD, "diag": "",
                        "detail": detail, "modes": modes})
    return sorted(results, key=lambda r: r["delta"], reverse=True)
