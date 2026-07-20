"""Test d'acceptation statistique par bootstrap — phase 3 du ticket 004 (DA).

Une amélioration du composite inférieure au bruit d'échantillonnage ne doit pas
être acceptée (doc §2.3). Le test : **bootstrap apparié sur les agents** — on
rééchantillonne les agents avec remise et on recalcule le Δ composite
(prompt muté − prompt courant) sur chaque tirage, ce qui donne un intervalle de
confiance sur l'amélioration. Une mutation n'est conservée que si l'amélioration
est **significative**.

Le rééchantillonnage se fait sur les **décisions brutes** (déjà dans le store) :
zéro appel LLM. Il est **apparié** — le même sous-ensemble d'agents est utilisé
des deux côtés — pour que le Δ ne mesure que l'effet du prompt, pas la variance
de composition de l'échantillon.

Recuit (DA) : le seuil de signification est **assoupli à chaud** (exploration) et
resserré à froid, mais le **signe** ne l'est jamais — une mutation qui dégrade le
composite (Δ ≥ 0) n'est jamais acceptée, contrairement au recuit classique.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .metrics import Metric


def significance_threshold(temperature: float, t0: float,
                           conf_min: float, conf_max: float) -> float:
    """Seuil de signification (proba minimale d'amélioration) fonction de la température.

    À chaud (``temperature ≈ t0``) → ``conf_min`` (on accepte des améliorations peu
    significatives, exploration) ; à froid (``temperature → 0``) → ``conf_max``
    (IC 90 %). Interpolation linéaire, bornée.
    """
    frac = min(1.0, max(0.0, temperature / t0)) if t0 > 0 else 0.0
    return conf_max - (conf_max - conf_min) * frac


def bootstrap_delta(sa_df: pd.DataFrame, mut_df: pd.DataFrame, metric: Metric,
                    cerema: dict, prompt_sa: str, prompt_mut: str, *,
                    b: int = 1000, seed: int = 0,
                    ci: float = 0.90) -> Optional[dict]:
    """IC bootstrap apparié sur ``Δ composite = composite(muté) − composite(courant)``.

    Renvoie ``None`` si l'appariement est impossible (aucun agent commun). Sinon un
    dict ``{point, ci_lo, ci_hi, p_improve, b}`` où :
    - ``point`` = Δ sur l'échantillon complet (l'estimation ponctuelle) ;
    - ``p_improve`` = fraction des tirages bootstrap où ``Δ < 0`` (amélioration) ;
    - ``ci_lo`` / ``ci_hi`` = bornes de l'IC au niveau ``ci``.

    ``metric.compute`` (loss active) est appliquée à chaque sous-échantillon : le
    test porte sur la loss réellement optimisée.
    """
    if sa_df.empty or mut_df.empty:
        return None
    agents = np.array(sorted(set(sa_df["agent_id"]) & set(mut_df["agent_id"])))
    if agents.size == 0:
        return None

    # Positions de lignes par agent, de chaque côté (rééchantillonnage rapide).
    sa_pos = {a: g.to_numpy() for a, g in
              pd.Series(np.arange(len(sa_df)), index=sa_df["agent_id"].to_numpy()).groupby(level=0)}
    mut_pos = {a: g.to_numpy() for a, g in
               pd.Series(np.arange(len(mut_df)), index=mut_df["agent_id"].to_numpy()).groupby(level=0)}

    def _composite(df: pd.DataFrame, prompt: str) -> float:
        return metric.compute(df, cerema, prompt_text=prompt).composite

    point = _composite(mut_df, prompt_mut) - _composite(sa_df, prompt_sa)

    rng = np.random.default_rng(seed)
    n = agents.size
    deltas = np.empty(b)
    for i in range(b):
        chosen = agents[rng.integers(0, n, n)]
        sa_idx = np.concatenate([sa_pos[a] for a in chosen])
        mut_idx = np.concatenate([mut_pos[a] for a in chosen])
        deltas[i] = (_composite(mut_df.iloc[mut_idx], prompt_mut)
                     - _composite(sa_df.iloc[sa_idx], prompt_sa))

    tail = (1.0 - ci) / 2.0 * 100.0
    return {
        "point": float(point),
        "ci_lo": float(np.percentile(deltas, tail)),
        "ci_hi": float(np.percentile(deltas, 100.0 - tail)),
        "p_improve": float(np.mean(deltas < 0.0)),
        "b": int(b),
    }


def bootstrap_verdict(summary: Optional[dict], threshold: float) -> tuple[bool, str, str]:
    """Décision d'acceptation à partir d'un résumé bootstrap et du seuil courant.

    Renvoie ``(accept, verdict, cause)``. Le **signe** prime : ``Δ ≥ 0`` (pas
    d'amélioration) → ``rejected_score`` quel que soit le seuil. Une amélioration
    n'est acceptée que si ``p_improve ≥ threshold`` ; sinon ``rejected_stat``
    (bruit d'échantillon). ``summary is None`` → repli sur le signe ponctuel.
    """
    if summary is None:
        return False, "rejected_stat", "bootstrap indisponible"
    if summary["point"] >= 0.0:
        return False, "rejected_score", f"Δ={summary['point']:+.2f} (pas d'amélioration)"
    if summary["p_improve"] >= threshold:
        return True, "accepted", ""
    return (False, "rejected_stat",
            f"p={summary['p_improve']:.2f}<{threshold:.2f} "
            f"(IC90 Δ=[{summary['ci_lo']:+.2f},{summary['ci_hi']:+.2f}])")


def noninferiority_verdict(summary: Optional[dict], margin: float,
                           ) -> tuple[bool, str]:
    """Test de **non-infériorité** pour la compaction (phase 4.5, DM).

    On retire un bloc (ou on le condense) : la mutation ``Δ = composite(compacté) −
    composite(courant)`` est acceptée si l'on est confiant que la dégradation reste
    **sous la marge de tolérance** — c.-à-d. la borne haute de l'IC90 du Δ est
    ``< margin``. « Réduire tant que ça ne dégrade pas le score. »

    Renvoie ``(accept, cause)``. ``summary is None`` (pas d'appariement) → refus
    prudent. Une compaction qui améliore franchement le score passe évidemment.
    """
    if summary is None:
        return False, "non-infériorité indisponible"
    if summary["ci_hi"] < margin:
        return True, ""
    return (False,
            f"IC90 haut Δ={summary['ci_hi']:+.2f} ≥ marge {margin:+.2f} "
            f"(compaction dégraderait le score)")
