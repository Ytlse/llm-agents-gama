"""Tests de la loss v2 : EMD ordinal + JSD nominal + pondération continue (phase 3).

Cas de test dédié du critère d'acceptation : la loss ordinale doit classer
« moins grave » un décalage de strate **adjacente** qu'un décalage **distant**
(bus 15-19 → 20-24 vs 15-19 → 50-54).
"""

import numpy as np
import pandas as pd

from calibration.metrics import (EMDJSDComposite, emd_1d, emd_ordinal_dim,
                                 get_metric, jsd, jsd_nominal_dim)
from calibration.models import RunConfig


# ── Primitives ───────────────────────────────────────────────────────────────

def test_jsd_identical_is_zero_and_symmetric():
    p = np.array([0.5, 0.3, 0.2, 0.0])
    assert jsd(p, p) < 1e-12
    q = np.array([0.1, 0.4, 0.4, 0.1])
    assert abs(jsd(p, q) - jsd(q, p)) < 1e-12
    assert 0.0 <= jsd(p, q) <= 1.0


def test_jsd_disjoint_is_one():
    # Supports disjoints → JSD maximale (1 bit en base 2).
    assert abs(jsd(np.array([1.0, 0.0]), np.array([0.0, 1.0])) - 1.0) < 1e-9


def test_emd_1d_adjacent_cheaper_than_distant():
    ref = np.array([1.0, 0.0, 0.0, 0.0, 0.0])
    adjacent = np.array([0.0, 1.0, 0.0, 0.0, 0.0])   # décalage d'un bin
    distant = np.array([0.0, 0.0, 0.0, 0.0, 1.0])    # décalage de quatre bins
    assert emd_1d(ref, ref) == 0.0
    assert emd_1d(ref, adjacent) == 1.0
    assert emd_1d(ref, distant) == 4.0
    assert emd_1d(ref, adjacent) < emd_1d(ref, distant)


# ── EMD ordinal : le cas de test du ticket ───────────────────────────────────

# Référence : sur l'axe âge, le bus (TC) est concentré chez les jeunes.
_AGE_REF = {
    "15-19": {"transports_collectifs": 100, "voiture": 0, "marche": 0, "velo": 0},
    "20-24": {"transports_collectifs": 0, "voiture": 100, "marche": 0, "velo": 0},
    "50-54": {"transports_collectifs": 0, "voiture": 100, "marche": 0, "velo": 0},
}


def _age_df(bus_bucket: str) -> pd.DataFrame:
    """df où le bus n'apparaît que dans ``bus_bucket`` ; les autres buckets en voiture."""
    rows = []
    for cat in ("15-19", "20-24", "50-54"):
        mode = "transports_collectifs" if cat == bus_bucket else "voiture"
        rows += [{"age_cat": cat, "mode_cat": mode}] * 20
    return pd.DataFrame(rows)


def test_emd_ordinal_adjacent_less_severe_than_distant():
    order = ["15-19", "20-24", "50-54"]
    # Référence : bus chez les 15-19.
    err_adjacent = emd_ordinal_dim(_age_df("20-24"), "age_cat", order, _AGE_REF)
    err_distant = emd_ordinal_dim(_age_df("50-54"), "age_cat", order, _AGE_REF)
    assert err_adjacent < err_distant, (
        "un décalage vers un bucket adjacent doit coûter moins qu'un décalage distant")


def test_l1_treats_adjacent_and_distant_equally():
    # Contraste : la L1 (via jsd_nominal ici pour illustrer le nominal) ignore l'ordre.
    order = ["15-19", "20-24", "50-54"]
    # En nominal, déplacer le bus de 15-19 vers 20-24 ou 50-54 donne le même écart
    # par-strate (chaque strate isolément a la même divergence).
    j_adjacent = jsd_nominal_dim(_age_df("20-24"), "age_cat", _AGE_REF)
    j_distant = jsd_nominal_dim(_age_df("50-54"), "age_cat", _AGE_REF)
    assert abs(j_adjacent - j_distant) < 1e-9


# ── JSD nominal + pondération continue ───────────────────────────────────────

_OCC_REF = {"actif_temps_plein": {"voiture": 60, "marche": 20, "velo": 5,
                                  "transports_collectifs": 15}}


def test_jsd_nominal_perfect_match_is_zero():
    df = pd.DataFrame([{"occupation": "actif_temps_plein", "mode_cat": m}
                       for m, n in [("voiture", 60), ("marche", 20),
                                    ("velo", 5), ("transports_collectifs", 15)]
                       for _ in range(n)])
    assert jsd_nominal_dim(df, "occupation", _OCC_REF) < 1e-6


def test_jsd_nominal_continuous_weighting_no_hard_cutoff():
    # Une strate d'un seul individu compte (pondérée par n=1), pas ignorée d'un coup.
    df = pd.DataFrame([{"occupation": "actif_temps_plein", "mode_cat": "marche"}])
    # 1 seule décision, 100% marche vs cible 20% marche → JSD > 0, pas neutralisée.
    assert jsd_nominal_dim(df, "occupation", _OCC_REF) > 0.0


def test_jsd_nominal_larger_strata_weigh_more():
    ref = {"a": {"voiture": 50, "marche": 50}, "b": {"voiture": 50, "marche": 50}}
    # Strate a (grande) parfaite ; strate b (petite) déséquilibrée.
    rows = [{"col": "a", "mode_cat": m} for m in ["voiture"] * 50 + ["marche"] * 50]
    rows += [{"col": "b", "mode_cat": "voiture"}] * 4
    df = pd.DataFrame(rows)
    # Le résultat est tiré vers 0 par la grande strate parfaite (pondération par n).
    weighted = jsd_nominal_dim(df, "col", ref)
    # Sans pondération, la moyenne simple des deux strates serait bien plus haute.
    unweighted = 0.5 * (0.0 + jsd(np.array([1.0, 0.0]), np.array([0.5, 0.5])) * 100)
    assert weighted < unweighted


# ── Composite complet ────────────────────────────────────────────────────────

def test_emdjsd_composite_empty_df():
    assert EMDJSDComposite().compute(pd.DataFrame(), {"parts_modales_2023": {}}).composite == 0.0


def test_get_metric_selects_emd_jsd():
    m = get_metric("emd_jsd", RunConfig())
    assert isinstance(m, EMDJSDComposite)
    assert get_metric("l1", RunConfig()).name == "l1_composite"
