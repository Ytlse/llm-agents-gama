"""Métriques de score (loss pluggable) — phase 1 du ticket 004.

Interface commune ``Metric.compute(df, reference, prompt_text) -> Scores`` : la
loss active est choisie dans ``RunConfig``. La phase 1 fournit ``L1Composite``
(portage de l'ancienne L1 pondérée) ; EMD/JSD/vraisemblance arrivent en phase 3.

Le store conservant les décisions brutes, toute loss est recalculable
rétroactivement sur l'historique complet (backtest, phase 3) sans réappel LLM.

Fonctions **pures** (pandas uniquement, aucun réseau) → testables sur cas limites.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from .models import Scores

# ── Modes & catégorisation ───────────────────────────────────────────────────

MODES = ["marche", "voiture", "velo", "transports_collectifs"]
MODE_COLORS = {"marche": "#00CCCC", "voiture": "#EE4444",
               "velo": "#8844BB", "transports_collectifs": "#22AA44"}
EXCLUDE_MODES = {"autres_modes", "autres"}


def categorize_mode(m: str) -> str:
    """Normalise le mode brut renvoyé par le LLM vers une catégorie Cerema."""
    if not isinstance(m, str):
        return "Autre"
    ml = m.lower()
    # TC en premier ('foot,bus,foot' contient aussi 'foot').
    if any(k in ml for k in ("bus", "metro", "métro", "tram", "transit", "public_transport")):
        return "transports_collectifs"
    if "foot,bus" in ml or "bus,foot" in ml:
        return "transports_collectifs"
    if any(k in ml for k in ("voiture", "car", "conducteur")):
        return "voiture"
    if any(k in ml for k in ("vélo", "velo", "bicycle", "cycling")):
        return "velo"
    if any(k in ml for k in ("marche", "foot", "walk", "pied")):
        return "marche"
    return "Autre"


def l1_error(actual: pd.Series, reference: dict) -> float:
    """Erreur L1 (points de %) entre distribution LLM et référence Cerema."""
    ref = {k: v for k, v in reference.items() if k not in EXCLUDE_MODES}
    ref_sum = sum(ref.values())
    if ref_sum == 0:
        return 0.0
    ref_norm = {k: v * 100.0 / ref_sum for k, v in ref.items()}
    total = actual.sum()
    if total == 0:
        return sum(ref_norm.values())
    return sum(abs(actual.get(m, 0) / total * 100 - ref_norm.get(m, 0)) for m in MODES)


# Dimensions par strate : (label, colonne du df, clé dans cerema.parts_modales_2023).
_STRATA_DIMS = [
    ("age", "age_cat", "Age"),
    ("occupation", "occupation", "occupation"),
    ("genre", "genre", "genre"),
    ("motif", "motif", "motif_deplacement"),
    ("distance", "dist_cat", "distance"),
]


def worst_strata_modes(df: pd.DataFrame, cerema: dict, top_k: int = 6,
                       min_count: int = 5) -> list[dict]:
    """Pires croisements strate × mode (écart signé actuel-cible, pondéré par effectif).

    Information fine perdue dans la moyenne du composite : permet au mutateur de
    cibler la strate ET le mode les plus mal prédits (impact = |Δ| × effectif).
    """
    if df.empty or "mode_cat" not in df.columns:
        return []
    parts = cerema["parts_modales_2023"]
    rows = []
    for dim_label, col, cerema_key in _STRATA_DIMS:
        if col not in df.columns or cerema_key not in parts:
            continue
        for cat, ref in parts[cerema_key].items():
            sub = df[df[col] == cat]["mode_cat"]
            total = sub.count()
            if total < min_count:
                continue
            ref_clean = {k: v for k, v in ref.items() if k not in EXCLUDE_MODES}
            ref_sum = sum(ref_clean.values())
            if ref_sum == 0:
                continue
            counts = sub.value_counts()
            for m in MODES:
                actual = counts.get(m, 0) / total * 100
                target = ref_clean.get(m, 0) * 100.0 / ref_sum
                diff = actual - target
                rows.append({
                    "dim": dim_label, "cat": cat, "mode": m,
                    "actual": actual, "target": target,
                    "diff": diff, "n": int(total),
                    "impact": abs(diff) * int(total),
                })
    rows.sort(key=lambda r: r["impact"], reverse=True)
    return rows[:top_k]


def normalized_global_gaps(dist_counts: pd.Series, cerema: dict) -> dict:
    """Écart (actuel − cible) en points de % par mode vs EMC² global normalisé."""
    ref = {k: v for k, v in cerema["parts_modales_2023"]["global"].items()
           if k not in EXCLUDE_MODES}
    ref_sum = sum(ref.values()) or 1
    total = dist_counts.sum() or 1
    gaps = {}
    for m in MODES:
        actual = dist_counts.get(m, 0) / total * 100
        target = ref.get(m, 0) * 100.0 / ref_sum
        gaps[m] = actual - target
    return gaps


# ── Interface pluggable ──────────────────────────────────────────────────────

class Metric(ABC):
    """Interface commune de loss. ``compute`` renvoie un :class:`Scores`."""

    name: str = "metric"

    @abstractmethod
    def compute(self, df: pd.DataFrame, reference: dict,
                prompt_text: str = "") -> Scores:
        ...


class L1Composite(Metric):
    """Score composite L1 pondéré vs EMC² 2023 (loss historique).

    Somme pondérée des L1 par dimension + pénalité de mode absent (×5 de la part
    cible d'un mode jamais choisi) + pénalité de longueur (incitation faible).
    """

    name = "l1_composite"

    # Poids fixes des dimensions (identiques à l'ancienne lib).
    WEIGHTS = {"global": 1.0, "absent_penalty": 1.0, "age": 0.5, "occupation": 0.5,
               "genre": 0.3, "motif": 0.5, "distance": 0.3, "length_penalty": 1.0}

    def __init__(self, length_penalty_per_word: float = 0.05):
        self.length_penalty_per_word = length_penalty_per_word

    def _dim_mean(self, df: pd.DataFrame, col: str, ref_by_cat: dict) -> float:
        errs = [
            l1_error(df[df[col] == cat]["mode_cat"].value_counts(), ref)
            for cat, ref in ref_by_cat.items()
            if df[df[col] == cat]["mode_cat"].count() >= 5
        ]
        return float(np.mean(errs)) if errs else 0.0

    def compute(self, df: pd.DataFrame, reference: dict,
                prompt_text: str = "") -> Scores:
        if df.empty or "mode_cat" not in df.columns:
            return Scores()

        parts = reference["parts_modales_2023"]
        s: dict = {}

        s["global"] = l1_error(df["mode_cat"].value_counts(), parts["global"])

        mode_counts = df["mode_cat"].value_counts()
        cerema_g = parts["global"]
        s["absent_penalty"] = float(sum(
            5 * cerema_g.get(m, 0) for m in MODES if mode_counts.get(m, 0) == 0))

        s["age"] = (self._dim_mean(df, "age_cat", parts["Age"])
                    if "age_cat" in df.columns else 0.0)
        s["occupation"] = (self._dim_mean(df, "occupation", parts["occupation"])
                           if "occupation" in df.columns else 0.0)
        s["genre"] = (self._dim_mean(df, "genre", parts["genre"])
                      if "genre" in df.columns else 0.0)
        s["motif"] = (self._dim_mean(df, "motif", parts["motif_deplacement"])
                      if "motif" in df.columns else 0.0)
        s["distance"] = (self._dim_mean(df, "dist_cat", parts["distance"])
                         if "dist_cat" in df.columns else 0.0)

        s["length_penalty"] = (len(prompt_text.split()) * self.length_penalty_per_word
                               if prompt_text else 0.0)

        w = self.WEIGHTS
        s["composite"] = (
            s["global"] * w["global"]
            + s["absent_penalty"] * w["absent_penalty"]
            + s["age"] * w["age"]
            + s["occupation"] * w["occupation"]
            + s["genre"] * w["genre"]
            + s["motif"] * w["motif"]
            + s["distance"] * w["distance"]
            + s["length_penalty"] * w["length_penalty"]
        )
        return Scores.model_validate(s)


# ── Loss v2 : EMD (ordinal) + JSD (nominal) + pondération continue (phase 3) ──
#
# Limite de la L1 (doc §2.2) : elle traite toutes les catégories comme
# interchangeables — déplacer la préférence bus des 15-19 ans vers les 20-24
# coûte autant que vers les 50-54. Les dimensions **ordinales** (âge, distance)
# doivent respecter l'ordre des catégories → EMD ; les dimensions **nominales**
# (occupation, genre, motif, global) → JSD inter-modes.
#
# Toutes ces fonctions sont **pures** et recalculables rétroactivement sur les
# décisions brutes du store (backtest, aucun réappel LLM).

# Axes ordinaux (ordre des buckets Cerema — identique à metadata._AGE/_DIST_BUCKETS).
AGE_ORDER = ["5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
             "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74",
             "75-130"]
DIST_ORDER = ["0-1km", "1-2km", "2-5km", "5-10km", "10-20km", "20-50km",
              "plus_50km"]


def _ref_probs(ref: dict) -> np.ndarray:
    """Vecteur de probabilité EMC² sur ``MODES`` (autres_modes exclus, renormalisé)."""
    clean = {k: v for k, v in ref.items() if k not in EXCLUDE_MODES}
    vals = np.array([float(clean.get(m, 0)) for m in MODES])
    s = vals.sum()
    return vals / s if s > 0 else vals


def _actual_probs(counts: pd.Series) -> np.ndarray:
    """Vecteur de probabilité LLM sur ``MODES`` à partir d'un ``value_counts``."""
    vals = np.array([float(counts.get(m, 0)) for m in MODES])
    s = vals.sum()
    return vals / s if s > 0 else vals


def jsd(p: np.ndarray, q: np.ndarray) -> float:
    """Divergence de Jensen-Shannon (base 2, bornée dans [0, 1]) entre deux lois.

    Symétrique et finie même quand un mode a une masse nulle d'un côté, contrairement
    à la KL — d'où son usage pour comparer les distributions **inter-modes** (nominal).
    """
    p, q = np.asarray(p, float), np.asarray(q, float)
    m = 0.5 * (p + q)

    def _kl(a: np.ndarray) -> float:
        mask = (a > 0) & (m > 0)
        return float(np.sum(a[mask] * np.log2(a[mask] / m[mask])))

    return max(0.0, 0.5 * _kl(p) + 0.5 * _kl(q))


def emd_1d(p: np.ndarray, q: np.ndarray) -> float:
    """EMD / Wasserstein-1 sur support **ordonné** : ``Σ_k |CDF_p(k) − CDF_q(k)|``.

    Résultat en unités d'index de bin (0 = lois identiques ; K−1 = toute la masse
    transportée d'un bout à l'autre de l'axe). C'est ce qui rend un décalage vers
    un bucket **adjacent** moins coûteux qu'un décalage vers un bucket **distant**.
    """
    p, q = np.asarray(p, float), np.asarray(q, float)
    return float(np.sum(np.abs(np.cumsum(p) - np.cumsum(q))))


def jsd_nominal_dim(df: pd.DataFrame, col: str, ref_by_cat: dict) -> float:
    """JSD inter-modes moyenne sur les catégories d'une dimension **nominale**.

    Pondération **continue par effectif** (remplace le seuil binaire ``n ≥ 5``) :
    une strate peu peuplée pèse proportionnellement moins au lieu d'être ignorée
    d'un coup. Échelle ×100 pour rester comparable aux points de % de la L1.
    """
    if df.empty or col not in df.columns:
        return 0.0
    num = den = 0.0
    for cat, ref in ref_by_cat.items():
        sub = df[df[col] == cat]["mode_cat"]
        n = int(sub.count())
        if n == 0:
            continue
        d = jsd(_actual_probs(sub.value_counts()), _ref_probs(ref))
        num += n * d
        den += n
    return (num / den * 100.0) if den > 0 else 0.0


def emd_ordinal_dim(df: pd.DataFrame, col: str, order: list[str],
                    ref_by_cat: dict) -> float:
    """EMD moyenne (pondérée par effectif du mode) des profils de mode le long d'un axe **ordinal**.

    Pour chaque mode, on compare *comment il se répartit le long de l'axe* (ex. « qui
    prend le bus, par tranche d'âge ») : profil normalisé LLM vs EMC² le long des
    buckets ordonnés, distance EMD (``Σ|ΔCDF|``). Un glissement d'un bucket coûte ~1,
    un glissement de sept buckets coûte ~7 → l'ordre est respecté. Normalisé par la
    longueur de l'axe et ×100 (comparable aux points de %).
    """
    cats = [c for c in order if c in ref_by_cat]
    if df.empty or col not in df.columns or len(cats) < 2:
        return 0.0
    axis_len = len(cats) - 1
    # Parts modales par bucket : matrice mode × bucket, côté LLM et côté EMC².
    llm = {m: np.array([0.0] * len(cats)) for m in MODES}
    ref = {m: np.array([0.0] * len(cats)) for m in MODES}
    for k, cat in enumerate(cats):
        sub = df[df[col] == cat]["mode_cat"]
        ap = _actual_probs(sub.value_counts())
        rp = _ref_probs(ref_by_cat[cat])
        for j, m in enumerate(MODES):
            llm[m][k] = ap[j]
            ref[m][k] = rp[j]
    num = den = 0.0
    for m in MODES:
        w_llm, w_ref = llm[m].sum(), ref[m].sum()
        if w_llm <= 0 or w_ref <= 0:
            continue
        # Profil du mode le long de l'axe (distribution sur les buckets).
        prof_llm, prof_ref = llm[m] / w_llm, ref[m] / w_ref
        # Poids = présence du mode côté LLM (masse effectivement observée).
        weight = float((df["mode_cat"] == m).sum())
        num += weight * emd_1d(prof_llm, prof_ref) / axis_len * 100.0
        den += weight
    return (num / den) if den > 0 else 0.0


class EMDJSDComposite(Metric):
    """Loss hiérarchique v2 (doc §2.2) : EMD sur les axes ordinaux, JSD sur le nominal.

    - ``age`` / ``distance`` : EMD du profil de chaque mode le long de l'axe (ordinal) ;
    - ``global`` / ``occupation`` / ``genre`` / ``motif`` : JSD inter-modes (nominal),
      pondérée en continu par effectif (plus de seuil binaire ``n ≥ 5``) ;
    - ``absent_penalty`` et ``length_penalty`` : identiques à la L1.

    Le composite réutilise les poids de dimension de :class:`L1Composite` (même
    structure) ; les échelles JSD/EMD sont ramenées en ×100 pour rester du même
    ordre de grandeur que les points de % de la L1. Le store conservant les
    décisions brutes, cette loss est calculable rétroactivement sur tout
    l'historique (backtest).
    """

    name = "emd_jsd"

    WEIGHTS = L1Composite.WEIGHTS

    def __init__(self, length_penalty_per_word: float = 0.05):
        self.length_penalty_per_word = length_penalty_per_word

    def compute(self, df: pd.DataFrame, reference: dict,
                prompt_text: str = "") -> Scores:
        if df.empty or "mode_cat" not in df.columns:
            return Scores()

        parts = reference["parts_modales_2023"]
        s: dict = {}

        # Global : JSD entre la loi modale globale LLM et EMC² global (×100).
        s["global"] = jsd(_actual_probs(df["mode_cat"].value_counts()),
                          _ref_probs(parts["global"])) * 100.0

        mode_counts = df["mode_cat"].value_counts()
        cerema_g = parts["global"]
        s["absent_penalty"] = float(sum(
            5 * cerema_g.get(m, 0) for m in MODES if mode_counts.get(m, 0) == 0))

        # Ordinal (EMD le long de l'axe) pour âge et distance.
        s["age"] = (emd_ordinal_dim(df, "age_cat", AGE_ORDER, parts["Age"])
                    if "age_cat" in df.columns else 0.0)
        s["distance"] = (emd_ordinal_dim(df, "dist_cat", DIST_ORDER, parts["distance"])
                         if "dist_cat" in df.columns else 0.0)

        # Nominal (JSD inter-modes) pour occupation, genre, motif.
        s["occupation"] = jsd_nominal_dim(df, "occupation", parts["occupation"])
        s["genre"] = jsd_nominal_dim(df, "genre", parts["genre"])
        s["motif"] = jsd_nominal_dim(df, "motif", parts["motif_deplacement"])

        s["length_penalty"] = (len(prompt_text.split()) * self.length_penalty_per_word
                               if prompt_text else 0.0)

        w = self.WEIGHTS
        s["composite"] = (
            s["global"] * w["global"]
            + s["absent_penalty"] * w["absent_penalty"]
            + s["age"] * w["age"]
            + s["occupation"] * w["occupation"]
            + s["genre"] * w["genre"]
            + s["motif"] * w["motif"]
            + s["distance"] * w["distance"]
            + s["length_penalty"] * w["length_penalty"]
        )
        return Scores.model_validate(s)


# Registre des losses disponibles (nom RunConfig → fabrique).
_METRIC_REGISTRY = {
    "l1": "l1_composite", "l1_composite": "l1_composite",
    "emd_jsd": "emd_jsd", "emd": "emd_jsd", "jsd": "emd_jsd",
}


def get_metric(name: str, config) -> Metric:
    """Fabrique la loss active depuis son nom (``RunConfig.loss``).

    Losses disponibles : ``l1_composite`` (historique, phase 1) et ``emd_jsd``
    (v2, phase 3 : EMD ordinal + JSD nominal + pondération continue). Toute loss
    partage l'interface :class:`Metric` → interchangeable et backtestable.
    """
    canonical = _METRIC_REGISTRY.get(name)
    if canonical == "l1_composite":
        return L1Composite(length_penalty_per_word=config.length_penalty_per_word)
    if canonical == "emd_jsd":
        return EMDJSDComposite(length_penalty_per_word=config.length_penalty_per_word)
    raise ValueError(
        f"Loss inconnue : {name!r} (disponibles : l1_composite, emd_jsd)")
