"""bi_oracle.py — Score composite à deux oracles, le logit multinomial en arbitre.

Le composite de fidélité ne mesure qu'une chose : l'écart des parts modales à l'enquête
EMC² 2023. C'est nécessaire et insuffisant. Martín-Baos et al. (2023) montrent que le
classement des modèles de choix modal **s'inverse selon la famille d'indicateurs** — les
arbres à gradient boosté devancent le logit multinomial sur l'exactitude désagrégée, le
logit reprend l'avantage sur les parts agrégées et sur les indicateurs comportementaux. Un
scalaire unique ne peut donc pas classer, et ce module produit les deux termes qui manquaient
au chiffre publié.

## Les trois blocs, et ce que chacun répond

| Bloc | Question | Oracle |
|---|---|---|
| **A** — fidélité | les parts modales sont-elles celles de l'enquête ? | l'enquête (inchangé) |
| **B** — accord désagrégé | décision par décision, le prompt répond-il comme un modèle de comportement ? | le MNL, rapporté au booster |
| **C** — cohérence comportementale | les parts bougent-elles dans le **sens** qu'un modèle de comportement prédit ? | le MNL |

Tous les termes sont orientés « perte, plus petit vaut mieux », et le composite reste
**linéaire** :

    S₂ = Σ_dim w_dim·s_dim  +  w_B·s_B  +  w_C·s_C

`w_B` et `w_C` valent **0** (manifeste `score.bi_oracle`, tranché le 2026-09-10) : les deux
termes sont calculés, journalisés et publiés, mais ne choisissent aucun prompt. Un prompt
sélectionné sous un terme mesuré contre un modèle serait ajusté à ce modèle, pas à l'enquête.
La linéarité rend la promotion ultérieure exacte et rétroactive : il suffit d'ajouter
`w·s` au composite déjà stocké, sans repayer un seul appel LLM.

## Bloc B : pourquoi une divergence rapportée, et non une erreur

Par décision, on mesure `KL(p_MNL ‖ p_LLM)` en bits. Deux précautions font toute la
différence entre un chiffre lisible et un chiffre décoratif :

1. **on ne publie pas la CEL brute contre cible molle.** L'entropie croisée du LLM contre les
   probabilités du MNL a un plancher irréductible égal à l'entropie du MNL lui-même (mesuré
   sur l'exemple de la spec : 1,0623 nat dont 0,9999 de plancher). Ce qui porte le signal est
   l'**excès**, soit exactement la divergence de Kullback-Leibler ;
2. **le dénominateur est la divergence entre les deux oracles** sur les mêmes décisions.
   Personne n'a à arbitrer si 0,09 bit « fait beaucoup » : `s_B = 29` se lit « le prompt est
   à 29 % de la distance qui sépare les deux oracles entre eux ». C'est une échelle mesurée,
   pas une constante choisie.

Le MNL n'est **pas** la vérité individuelle : aucune sortie de ce module ne qualifie `s_B`
d'erreur. C'est un accord, et il est publié avec son dénominateur.

## Bloc C : le sens de variation, pas le niveau

`C1` compare, le long de l'axe ordinal de distance, le **signe** des variations de parts
modales du prompt et du MNL. Le logit est monotone par construction sur ses variables
continues : c'est ce qui le qualifie comme arbitre, et c'est aussi ce qui rend la réserve de
Zhao et al. (2020) — élasticités des modèles à arbres « behaviorally unreasonable » —
mesurable chez nous. Une transition où l'arbitre lui-même n'a pas de signe franc est
**écartée et comptée**, jamais utilisée comme référence.

`C2` (élasticités d'arc sur une paire A/B déjà payée) n'est mesuré que si une telle paire est
fournie : ce module ne redemande **aucune** décision à un modèle de langage.

## Vacuité ≠ perfection

Un bloc sans effectif mesuré rend `null` et la mention « non mesuré », **jamais** `0.0` —
qui serait le score parfait. Le dénominateur inter-oracles est vérifié sur le même substrat
que le numérateur (même run, même empreinte `moves.csv`) : sinon `s_B` n'est pas publié.

Usage :
    python -m scripts.synthesis.bi_oracle [--config sources.yaml] [--out data/bi_oracle.json]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import frames
from .model_on_common_set import (
    CANONICAL_TO_CAT,
    PREDICTABLE_CATS,
    STATUS_OK,
    renormalize,
)
from .sources import REPO_ROOT, import_calibration, load_manifest

#: Plancher de probabilité. Une probabilité nulle du prompt sur un mode que l'oracle
#: charge rendrait la divergence infinie : une seule décision emporterait alors tout le
#: score. Le plancher est **déclaré dans la sortie** et le nombre de décisions concernées
#: est compté — c'est une convention de mesure, pas un lissage discret.
EPSILON = 1e-4

#: Axe ordinal du bloc C1, dérivé des mêmes bornes que le binnage des décisions : un axe
#: recopié à la main se désaligne au premier seuil déplacé.
DIST_ORDER = [label for _, label in frames._DIST_BUCKETS] + ["plus_50km"]

#: Effectif minimal d'une classe de distance pour qu'elle porte une transition. En dessous,
#: la part modale d'un mode à 4 % n'est qu'un comptage de quelques décisions.
MIN_STRATUM = 30

#: Amplitude en dessous de laquelle l'arbitre est réputé **sans signe** sur une transition
#: (en points de pourcentage de part modale). Comparer un signe à un bruit de 0,1 point
#: reviendrait à tirer à pile ou face, et à noter le prompt là-dessus.
MIN_ARBITER_SHIFT = 0.5


# ── Divergences ──────────────────────────────────────────────────────────────

def kl_bits(target: dict[str, float], candidate: dict[str, float],
            epsilon: float = EPSILON) -> tuple[float, bool]:
    """`KL(target ‖ candidate)` en bits, et le drapeau « plancher appliqué ».

    Orientée depuis l'oracle : on demande « combien d'information manque au candidat pour
    rendre compte de l'oracle », qui est la question du bloc B. La divergence inverse
    pénaliserait un prompt prudent (masse étalée) au profit d'un prompt catégorique, alors
    que c'est le contraire qu'on veut détecter.
    """
    total = 0.0
    floored = False
    for mode, p in target.items():
        if p <= 0:
            continue
        q = candidate.get(mode, 0.0)
        if q < epsilon:
            q = epsilon
            floored = True
        total += p * math.log2(p / q)
    return total, floored


def entropy_bits(distribution: dict[str, float]) -> float:
    """Entropie de la distribution, en bits — le plancher de toute CEL contre elle."""
    return -sum(p * math.log2(p) for p in distribution.values() if p > 0)


def jsd_bits(left: dict[str, float], right: dict[str, float]) -> float:
    """Divergence de Jensen-Shannon en bits, dans [0, 1]. **Aucune constante requise.**

    C'est la grandeur de tête du bloc B, et la raison est mesurée : 1 118 des 2 593
    décisions du run épinglé portent une distribution quasi dégénérée (un mode au-dessus
    de 0,999), et 1 923 déclenchent le plancher de la divergence de Kullback-Leibler. Le
    rapport de KL y devient donc une fonction du plancher `ε` autant que des décisions —
    autrement dit une convention, pas une mesure. La JSD est définie sur les zéros, bornée
    par 1 bit, et symétrique ; elle ne récompense ni ne punit un prompt catégorique par un
    artefact d'échelle. Le rapport de KL reste publié en second, avec le compte des
    décisions où le plancher a joué : c'est lui qui est comparable à la littérature.
    """
    total = 0.0
    for mode in set(left) | set(right):
        p, q = left.get(mode, 0.0), right.get(mode, 0.0)
        mid = 0.5 * (p + q)
        if p > 0:
            total += 0.5 * p * math.log2(p / mid)
        if q > 0:
            total += 0.5 * q * math.log2(q / mid)
    return total


# ── Lecture des trois décideurs sur le même périmètre ────────────────────────

def llm_distributions(moves: list[dict]) -> tuple[dict[tuple[str, str], dict], dict]:
    """Décisions du prompt, restreintes à l'offre prédictible et renormalisées.

    Le support doit être **celui des oracles** : les modes réellement proposés par OTP,
    hors deux-roues motorisé et « autres modes » (qui sortent des quatre classes de la
    politique). Comparer trois distributions sur trois supports différents produirait des
    divergences qui ne mesurent que le désaccord des périmètres.
    """
    out: dict[tuple[str, str], dict] = {}
    skipped = Counter()
    for move in moves:
        offered = [m for m in move["offered"] if m in PREDICTABLE_CATS]
        if not offered:
            skipped["offre_sans_mode_predictible"] += 1
            continue
        if len(offered) < 2:
            # **Une offre à un seul mode n'est pas une décision comparable.** Le prompt
            # n'a pas été interrogé (méthode « Un seul itinéraire disponible » : 656
            # décisions du run épinglé, aucune ne porte de distribution), et les trois
            # décideurs seraient forcés sur le même mode — soit un accord parfait gratuit
            # pour tout le monde. L'inclure ferait baisser le score sans qu'aucun accord
            # n'ait été mesuré : c'est la vacuité prise pour de la perfection.
            skipped["offre_unique"] += 1
            continue
        distribution = renormalize({m: v for m, v in move["probas"].items()}, offered)
        if distribution is None:
            # Offre à plusieurs modes mais aucune masse dessus : à surveiller, pas à
            # combler. Zéro sur le run épinglé.
            skipped["sans_distribution"] += 1
            continue
        out[(move["agent_id"], move["activity_id"])] = {
            "p": distribution,
            "offered": sorted(offered),
            "dist_cat": move.get("dist_cat"),
            "degenere": max(distribution.values()) > 0.999,
        }
    return out, dict(skipped)


def oracle_distributions(path: Path) -> tuple[dict[tuple[str, str], dict], dict]:
    """Prédictions d'un oracle → distributions par décision, plus le descriptif du parquet.

    Le descriptif voyage dans le parquet (run, empreinte `moves.csv`, sha de l'artefact) :
    c'est lui qui permet de refuser deux colonnes mesurées sur deux substrats.
    """
    try:
        import pyarrow.parquet as pq
    except ImportError:
        return {}, {"error": "pyarrow indisponible"}
    if not Path(path).exists():
        return {}, {"error": f"parquet absent : {path}"}
    table = pq.read_table(path)
    raw = (table.schema.metadata or {}).get(b"progedo_on_common_set")
    try:
        meta = json.loads(raw) if raw else {}
    except ValueError:
        meta = {}
    out: dict[tuple[str, str], dict] = {}
    for record in table.to_pylist():
        if record.get("status") != STATUS_OK:
            continue
        distribution = {c: float(record[f"p_{c}"]) for c in PREDICTABLE_CATS
                        if record.get(f"p_{c}")}
        if not distribution:
            continue
        offered = [CANONICAL_TO_CAT.get(m, m)
                   for m in (record.get("offered_predictable") or "").split("|") if m]
        if len(set(offered)) < 2:
            continue                  # même règle que le prompt : cf. llm_distributions
        out[(record.get("agent_id"), record.get("activity_id"))] = {
            "p": distribution,
            "offered": sorted(set(offered)),
            "dist_cat": record.get("dist_cat"),
            "degenere": max(distribution.values()) > 0.999,
        }
    return out, meta


# ── Bloc B : accord désagrégé au second oracle ───────────────────────────────

def block_b(llm: dict, mnl: dict, lgb: dict, *, n_perimeter: Optional[int] = None,
            llm_skipped: Optional[dict] = None, epsilon: float = EPSILON) -> dict:
    """`s_B` et son détail : divergences appariées, couverture, exclusions comptées.

    Deux rapports, et l'ordre entre eux est motivé (cf. :func:`jsd_bits`) : la JSD en tête
    parce qu'elle ne dépend d'aucune constante, le rapport de KL en second parce qu'il est
    la grandeur de la littérature — publié avec le compte des décisions où son plancher a
    joué, sans quoi on lirait une convention pour une mesure.
    """
    keys = sorted(set(llm) & set(mnl) & set(lgb))
    excluded = {
        "sans_mnl": len(set(llm) - set(mnl)),
        "sans_booster": len(set(llm) - set(lgb)),
        "sans_prompt": len(set(mnl) - set(llm)),
        "offre_divergente": 0,
        **{f"prompt::{k}": v for k, v in (llm_skipped or {}).items()},
    }
    jsd_llm = jsd_lgb = kl_llm = kl_lgb = 0.0
    floored = degenerate = 0
    per_decision: list[dict] = []
    for key in keys:
        if not (llm[key]["offered"] == mnl[key]["offered"] == lgb[key]["offered"]):
            # Même décision, trois offres différentes : la divergence mesurerait le
            # désaccord des périmètres, pas celui des décideurs.
            excluded["offre_divergente"] += 1
            continue
        target = mnl[key]["p"]
        d_jsd_llm = jsd_bits(target, llm[key]["p"])
        d_jsd_lgb = jsd_bits(target, lgb[key]["p"])
        d_kl_llm, floor_llm = kl_bits(target, llm[key]["p"], epsilon)
        d_kl_lgb, floor_lgb = kl_bits(target, lgb[key]["p"], epsilon)
        jsd_llm += d_jsd_llm
        jsd_lgb += d_jsd_lgb
        kl_llm += d_kl_llm
        kl_lgb += d_kl_lgb
        floored += int(floor_llm or floor_lgb)
        degenerate += int(llm[key]["degenere"])
        per_decision.append({"jsd_llm": d_jsd_llm, "jsd_lgb": d_jsd_lgb,
                             "kl_llm": d_kl_llm, "kl_lgb": d_kl_lgb,
                             "entropy_mnl": entropy_bits(target),
                             "dist_cat": mnl[key]["dist_cat"]})

    n = len(per_decision)
    base = n_perimeter if n_perimeter else max(len(llm), 1)
    if n == 0 or jsd_lgb <= 0:
        return {
            "s_B": None,
            "mesure": "non mesuré",
            "raison": ("aucune décision appariée sur les trois décideurs"
                       if n == 0 else
                       "les deux oracles sont exactement d'accord : pas d'échelle"),
            "n_decisions": n,
            "exclusions": excluded,
            "epsilon": epsilon,
        }
    return {
        # Le rapport, en pourcentage de la distance inter-oracles. Un `s_B` de 100
        # signifie « le prompt est aussi loin du MNL que le booster l'est ».
        "s_B": 100.0 * jsd_llm / jsd_lgb,
        "mesure": ("accord au second oracle (JSD), rapporté à la distance "
                   "inter-oracles mesurée sur les mêmes décisions"),
        "jsd_prompt_mnl_bits_mean": jsd_llm / n,
        "jsd_booster_mnl_bits_mean": jsd_lgb / n,
        # Variante Kullback-Leibler, dépendante du plancher : à lire avec
        # `n_plancher_applique`, jamais seule.
        "s_B_kl": (100.0 * kl_llm / kl_lgb) if kl_lgb > 0 else None,
        "kl_prompt_mnl_bits_mean": kl_llm / n,
        "kl_booster_mnl_bits_mean": kl_lgb / n,
        "n_plancher_applique": floored,
        "n_prompt_degenere": degenerate,
        "entropie_mnl_bits_mean": sum(d["entropy_mnl"] for d in per_decision) / n,
        "n_decisions": n,
        "couverture": n / base,
        "base_couverture": base,
        "exclusions": excluded,
        "epsilon": epsilon,
        "par_distance": _by_distance(per_decision),
    }


def _by_distance(per_decision: list[dict]) -> list[dict]:
    """Divergences moyennes par classe de distance — où l'accord se gagne ou se perd."""
    grouped: dict[Optional[str], list[dict]] = defaultdict(list)
    for row in per_decision:
        grouped[row["dist_cat"]].append(row)
    out = []
    for cat in DIST_ORDER:
        rows = grouped.get(cat)
        if not rows:
            continue
        num = sum(r["jsd_llm"] for r in rows)
        den = sum(r["jsd_lgb"] for r in rows)
        out.append({
            "dist_cat": cat,
            "n": len(rows),
            "jsd_prompt_mnl_bits_mean": num / len(rows),
            "jsd_booster_mnl_bits_mean": den / len(rows),
            # `null` plutôt que 0 : sans échelle locale, il n'y a pas de rapport à lire.
            "s_B": (100.0 * num / den) if den > 0 else None,
        })
    return out


# ── Bloc C1 : sens de variation le long de l'axe de distance ─────────────────

def mass_by_stratum(distributions: dict, column: str = "dist_cat") -> dict:
    """Parts modales en masse de probabilité, par classe de l'axe, en pourcentage."""
    totals: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    counts: dict[str, int] = defaultdict(int)
    for entry in distributions.values():
        cat = entry.get(column)
        if cat is None:
            continue
        counts[cat] += 1
        for mode, mass in entry["p"].items():
            totals[cat][mode] += mass
    out = {}
    for cat, masses in totals.items():
        n = counts[cat]
        out[cat] = {"n": n,
                    "shares": {m: 100.0 * masses.get(m, 0.0) / n for m in PREDICTABLE_CATS}}
    return out


def block_c1(llm: dict, mnl: dict, *, min_stratum: int = MIN_STRATUM,
             min_shift: float = MIN_ARBITER_SHIFT) -> dict:
    """`s_C1` : part des couples (mode, transition) dont le signe contredit l'arbitre."""
    llm_strata = mass_by_stratum(llm)
    mnl_strata = mass_by_stratum(mnl)
    transitions: list[dict] = []
    skipped = {"effectif_insuffisant": 0, "arbitre_sans_signe": 0}

    axis = [c for c in DIST_ORDER if c in llm_strata and c in mnl_strata]
    for left, right in zip(axis, axis[1:]):
        thin = min(llm_strata[left]["n"], llm_strata[right]["n"],
                   mnl_strata[left]["n"], mnl_strata[right]["n"]) < min_stratum
        for mode in PREDICTABLE_CATS:
            if thin:
                skipped["effectif_insuffisant"] += 1
                continue
            d_mnl = (mnl_strata[right]["shares"][mode] - mnl_strata[left]["shares"][mode])
            if abs(d_mnl) < min_shift:
                # R20 : l'arbitre n'a pas de signe à donner sur cette transition. La
                # compter comme un accord flatterait le prompt, la compter comme un
                # désaccord le condamnerait — elle sort du score et se compte.
                skipped["arbitre_sans_signe"] += 1
                continue
            d_llm = (llm_strata[right]["shares"][mode] - llm_strata[left]["shares"][mode])
            transitions.append({
                "mode": mode, "de": left, "vers": right,
                "delta_llm_pt": d_llm, "delta_mnl_pt": d_mnl,
                "accord": (d_llm > 0) == (d_mnl > 0),
            })

    if not transitions:
        return {"s_C1": None, "mesure": "non mesuré",
                "raison": "aucune transition ne porte à la fois un effectif et un signe",
                "ecartees": skipped}
    disagreements = [t for t in transitions if not t["accord"]]
    return {
        "s_C1": 100.0 * len(disagreements) / len(transitions),
        "mesure": "part des couples (mode, transition) dont le signe contredit l'arbitre",
        "n_transitions": len(transitions),
        "n_desaccords": len(disagreements),
        "ecartees": skipped,
        "seuils": {"effectif_min": min_stratum, "amplitude_min_pt": min_shift},
        "desaccords": disagreements,
        "transitions": transitions,
    }


# ── Bloc C2 : élasticités d'arc sur une paire A/B déjà payée ─────────────────

def arc_elasticities(before: dict, after: dict) -> dict[str, float]:
    """Variation relative de chaque part modale entre deux états du même périmètre.

    Les deux états doivent porter **les mêmes décisions** : c'est ce qui fait de l'écart
    un effet du traitement, et non un effet de composition.
    """
    keys = sorted(set(before) & set(after))
    if not keys:
        return {}
    out = {}
    for mode in PREDICTABLE_CATS:
        p0 = sum(before[k]["p"].get(mode, 0.0) for k in keys) / len(keys)
        p1 = sum(after[k]["p"].get(mode, 0.0) for k in keys) / len(keys)
        out[mode] = ((p1 - p0) / p0) if p0 > 0 else float("nan")
    return out


def block_c2(llm_before: Optional[dict], llm_after: Optional[dict],
             mnl_before: Optional[dict], mnl_after: Optional[dict],
             variable: Optional[str]) -> dict:
    """`s_C2` : part des modes dont le signe d'élasticité contredit l'arbitre.

    Non mesuré par défaut, et c'est le point : mesurer une élasticité du prompt demande de
    rejouer des décisions, donc des appels LLM. Ce module n'en fait aucun — il exploite une
    paire A/B **déjà payée** quand on lui en désigne une.
    """
    if not all((llm_before, llm_after, mnl_before, mnl_after, variable)):
        return {
            "s_C2": None, "mesure": "non mesuré",
            "raison": ("aucune paire A/B fournie — une élasticité du prompt exige des "
                       "décisions rejouées, que ce module ne redemande jamais"),
            "comment": ("--ab-llm-before/--ab-llm-after (moves.csv des deux bras), "
                        "--ab-mnl-before/--ab-mnl-after (parquets du MNL), "
                        "--ab-variable <une des 21 variables du contrat>"),
        }
    e_llm = arc_elasticities(llm_before, llm_after)
    e_mnl = arc_elasticities(mnl_before, mnl_after)
    rows, skipped = [], 0
    for mode in PREDICTABLE_CATS:
        a, b = e_llm.get(mode), e_mnl.get(mode)
        if a is None or b is None or math.isnan(a) or math.isnan(b) or abs(b) < 1e-6:
            skipped += 1
            continue
        rows.append({"mode": mode, "elasticite_llm": a, "elasticite_mnl": b,
                     "accord": (a > 0) == (b > 0)})
    if not rows:
        return {"s_C2": None, "mesure": "non mesuré",
                "raison": "aucun mode ne porte une élasticité de signe franc chez l'arbitre",
                "ecartes": skipped}
    disagreements = [r for r in rows if not r["accord"]]
    return {
        "s_C2": 100.0 * len(disagreements) / len(rows),
        "mesure": "part des modes dont le signe d'élasticité contredit l'arbitre",
        "variable": variable,
        "n_modes": len(rows),
        "ecartes": skipped,
        "modes": rows,
    }


# ── Composition ──────────────────────────────────────────────────────────────

def compose(fidelity: Optional[float], s_b: Optional[float], s_c: Optional[float],
            weights: dict) -> dict:
    """`S₂` linéaire, et la liste des termes qu'il n'a pas pu inclure.

    Un terme non mesuré n'entre pas dans la somme **et le dit**. Il ne vaut surtout pas 0 :
    dans ce projet, l'absence de mesure produit le score parfait, et c'est le piège que
    cette fonction est là pour fermer.
    """
    w_b = float(weights.get("accord_mnl", 0.0) or 0.0)
    w_c = float(weights.get("coherence_mnl", 0.0) or 0.0)
    terms = [{"terme": "fidelite", "poids": 1.0, "score": fidelity},
             {"terme": "accord_mnl", "poids": w_b, "score": s_b},
             {"terme": "coherence_mnl", "poids": w_c, "score": s_c}]
    missing = [t["terme"] for t in terms if t["score"] is None and t["poids"] > 0]
    total = None
    if fidelity is not None and not missing:
        total = fidelity + w_b * (s_b or 0.0) + w_c * (s_c or 0.0)
    return {
        "S2": total,
        "termes": terms,
        "poids": {"accord_mnl": w_b, "coherence_mnl": w_c},
        "non_mesures_bloquants": missing,
        "note": ("composite linéaire : promouvoir un poids se rétro-applique par simple "
                 "addition de w·s au composite stocké, sans rejouer une décision"),
    }


# ── Substrat : deux oracles, un seul run ─────────────────────────────────────

def check_substrate(mnl_meta: dict, lgb_meta: dict, run_path: Optional[str],
                    moves_sha: Optional[str]) -> dict:
    """Refuse un numérateur et un dénominateur mesurés sur deux substrats (R9).

    L'empreinte n'est pas redondante avec le nom du run : une reprise à chaud réécrit
    `moves.csv` **dans le même dossier**, donc sous le même nom. Seule l'empreinte
    distingue ces deux états.
    """
    problems = []
    for label, meta in (("mnl", mnl_meta), ("booster", lgb_meta)):
        if meta.get("error"):
            problems.append(f"{label} : {meta['error']}")
            continue
        if run_path and meta.get("run") != run_path:
            problems.append(f"{label} : mesuré sur {meta.get('run')}, run épinglé {run_path}")
        if moves_sha and meta.get("moves_sha256") != moves_sha:
            problems.append(f"{label} : empreinte moves.csv divergente "
                            f"({str(meta.get('moves_sha256'))[:12]}… vs {moves_sha[:12]}…)")
    if (mnl_meta.get("spec_version") is not None
            and mnl_meta.get("spec_version") != lgb_meta.get("spec_version")):
        problems.append("les deux oracles n'ont pas le même contrat de variables")
    return {
        "ok": not problems,
        "problemes": problems,
        "run": run_path,
        "moves_sha256": moves_sha,
        "oracles": {
            "mnl": {"format": mnl_meta.get("policy_format"),
                    "sha256": mnl_meta.get("policy_sha256"),
                    "genere_le": mnl_meta.get("policy_generated_at"),
                    "chemin": mnl_meta.get("policy_path")},
            "booster": {"format": lgb_meta.get("policy_format"),
                        "sha256": lgb_meta.get("policy_sha256"),
                        "genere_le": lgb_meta.get("policy_generated_at"),
                        "chemin": lgb_meta.get("policy_path")},
        },
    }


def fidelity_composite(moves: list[dict], manifest, metric: str) -> tuple[Optional[float], str]:
    """Composite de fidélité du volet 1, calculé par le moteur de calibration.

    Jamais réimplémenté ici : le chiffre publié doit être exactement celui que le moteur
    optimise. Moteur absent → `None` et la raison, pas un zéro.
    """
    module, error = import_calibration(manifest.get("arms.calibration.repo",
                                                    "prompt_calibration"))
    if module is None:
        return None, f"moteur de calibration indisponible ({error})"
    cerema_path = manifest.path_of("cerema")
    if cerema_path is None or not cerema_path.exists():
        return None, "référence EMC² introuvable"
    cerema = frames.load_cerema(cerema_path)
    scorer = frames.Scorer(module, manifest.get("score.weights", {}), metric,
                           manifest.get("score.secondary"))
    rows = frames.simulation_frames(moves)["attendu"]
    scores = scorer.score(rows, cerema)
    composite = (scores.get(metric) or {}).get("composite")
    return (float(composite) if composite is not None else None), ""


# ── CLI ──────────────────────────────────────────────────────────────────────

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", help="manifeste de sources (défaut : sources.yaml)")
    parser.add_argument("--out", help="JSON de sortie (défaut : data/bi_oracle.json)")
    parser.add_argument("--ab-variable", help="variable perturbée de la paire A/B (bloc C2)")
    parser.add_argument("--ab-llm-before", help="moves.csv du bras avant")
    parser.add_argument("--ab-llm-after", help="moves.csv du bras après")
    parser.add_argument("--ab-mnl-before", help="parquet MNL du bras avant")
    parser.add_argument("--ab-mnl-after", help="parquet MNL du bras après")
    args = parser.parse_args(argv)

    manifest = load_manifest(args.config)
    exclude = manifest.get("common_set.exclude_selection_methods", [])
    run = frames.resolve_run(manifest)
    if not run.get("exists") or not run.get("moves", {}).get("exists"):
        print(f"[erreur] Run introuvable ou sans moves.csv : "
              f"{manifest.get('common_set.run')}", file=sys.stderr)
        return 2
    moves_path = REPO_ROOT / run["moves"]["path"]
    moves, stats = frames.read_moves(moves_path, exclude)

    llm, llm_skipped = llm_distributions(moves)
    mnl_path = manifest.path_of("arms.model_mnl.predictions")
    lgb_path = manifest.path_of("arms.model.predictions")
    mnl, mnl_meta = oracle_distributions(mnl_path) if mnl_path else ({}, {"error": "chemin absent du manifeste"})
    lgb, lgb_meta = oracle_distributions(lgb_path) if lgb_path else ({}, {"error": "chemin absent du manifeste"})

    print(f"Run épinglé : {run['path']}")
    print(f"Décisions comparables (offre à 2 modes ou plus) : prompt {len(llm)} | "
          f"MNL {len(mnl)} | booster {len(lgb)} — écartées côté prompt : {llm_skipped} "
          f"(sur {stats.get('total')} lignes du journal)")

    substrate = check_substrate(mnl_meta, lgb_meta, run.get("path"),
                                (run.get("moves") or {}).get("sha256"))
    if not substrate["ok"]:
        # Bruyant et non bloquant : la sortie est écrite avec ses blocs « non mesuré »,
        # parce qu'une page sans chiffre est plus utile qu'un chiffre sans substrat.
        for problem in substrate["problemes"]:
            print(f"[ALARME] Substrat divergent — {problem}", file=sys.stderr)

    n_perimeter = len(moves)
    b = (block_b(llm, mnl, lgb, n_perimeter=n_perimeter, llm_skipped=llm_skipped)
         if substrate["ok"]
         else {"s_B": None, "mesure": "non mesuré",
               "raison": "substrat divergent entre les deux oracles et le run épinglé",
               "problemes": substrate["problemes"]})
    c1 = (block_c1(llm, mnl) if substrate["ok"]
          else {"s_C1": None, "mesure": "non mesuré",
                "raison": "substrat divergent entre l'arbitre et le run épinglé"})

    ab = {}
    if args.ab_variable:
        before, _ = (oracle_distributions(Path(args.ab_mnl_before))
                     if args.ab_mnl_before else ({}, {}))
        after, _ = (oracle_distributions(Path(args.ab_mnl_after))
                    if args.ab_mnl_after else ({}, {}))
        llm_before = llm_after = None
        if args.ab_llm_before and args.ab_llm_after:
            rows_before, _ = frames.read_moves(Path(args.ab_llm_before), exclude)
            rows_after, _ = frames.read_moves(Path(args.ab_llm_after), exclude)
            llm_before = llm_distributions(rows_before)
            llm_after = llm_distributions(rows_after)
        ab = {"llm_before": llm_before, "llm_after": llm_after,
              "mnl_before": before or None, "mnl_after": after or None}
    c2 = block_c2(ab.get("llm_before"), ab.get("llm_after"), ab.get("mnl_before"),
                  ab.get("mnl_after"), args.ab_variable)

    metric = manifest.get("score.metric", "emd_jsd")
    fidelity, fidelity_error = fidelity_composite(moves, manifest, metric)
    if fidelity is None:
        print(f"⚠ Composite de fidélité indisponible : {fidelity_error}", file=sys.stderr)

    # `s_C` agrège les deux sous-blocs mesurés — moyenne simple, les deux étant déjà des
    # parts de désaccord en pourcentage. Aucun des deux ne comble l'absence de l'autre.
    measured = [v for v in (c1.get("s_C1"), c2.get("s_C2")) if v is not None]
    s_c = sum(measured) / len(measured) if measured else None

    composition = compose(fidelity, b.get("s_B"), s_c, manifest.get("score.bi_oracle", {}))

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "substrat": substrate,
        "perimetre": {
            "n_decisions_prompt": len(llm),
            "n_decisions_mnl": len(mnl),
            "n_decisions_booster": len(lgb),
            "n_decisions_perimetre": n_perimeter,
            "ecartees_prompt": llm_skipped,
            "exclude_selection_methods": exclude,
            "lecture_moves": stats.get("total"),
        },
        "bloc_A_fidelite": {"metric": metric, "composite": fidelity,
                            "raison": fidelity_error or None},
        "bloc_B_accord_mnl": b,
        "bloc_C_coherence": {"s_C": s_c, "C1_axe_distance": c1, "C2_elasticites_ab": c2},
        "composition": composition,
        "avertissement": ("le MNL est un arbitre comportemental, pas une cible de "
                          "fidélité : s_B et s_C mesurent un ACCORD, jamais une erreur"),
    }

    out_path = Path(args.out) if args.out else (
        REPO_ROOT / "scripts" / "synthesis" / "data" / "bi_oracle.json")
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")

    print(f"\nBloc A — fidélité ({metric}) : "
          + ("non mesuré" if fidelity is None else f"{fidelity:.2f}"))
    if b.get("s_B") is None:
        print(f"Bloc B — accord au MNL : non mesuré ({b.get('raison')})")
    else:
        print(f"Bloc B — accord au MNL : {b['s_B']:.1f} % de la distance inter-oracles "
              f"(JSD prompt {b['jsd_prompt_mnl_bits_mean']:.4f} bit, booster "
              f"{b['jsd_booster_mnl_bits_mean']:.4f} bit, sur {b['n_decisions']} "
              f"décisions, couverture {100 * b['couverture']:.0f} %)")
        print(f"        variante KL (dépend du plancher ε = {b['epsilon']:g}) : "
              f"{b['s_B_kl']:.0f} % — plancher appliqué sur {b['n_plancher_applique']} "
              f"décisions, prompt quasi dégénéré sur {b['n_prompt_degenere']}")
    if c1.get("s_C1") is None:
        print(f"Bloc C1 — sens de variation : non mesuré ({c1.get('raison')})")
    else:
        print(f"Bloc C1 — sens de variation : {c1['s_C1']:.1f} % de désaccord "
              f"({c1['n_desaccords']}/{c1['n_transitions']} transitions, "
              f"{c1['ecartees']} écartées)")
    s_c2 = c2.get("s_C2")
    print("Bloc C2 — élasticités A/B : "
          + ("non mesuré" if s_c2 is None else f"{s_c2:.1f} % de désaccord"))
    total = composition["S2"]
    print(f"\nS₂ (poids {composition['poids']}) : "
          + ("non mesuré" if total is None else f"{total:.2f}"))
    rel = out_path.relative_to(REPO_ROOT) if out_path.is_relative_to(REPO_ROOT) else out_path
    print(f"Écrit : {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
