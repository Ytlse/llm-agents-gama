"""Tests du test d'acceptation bootstrap (phase 3, DA)."""

import pandas as pd

from calibration.metrics import L1Composite
from calibration.stats import (bootstrap_delta, bootstrap_verdict,
                              noninferiority_verdict, significance_threshold)
from .test_metrics import CEREMA


def _df(modes: list[str]) -> pd.DataFrame:
    """df apparié : un agent par mode fourni (agent_id = index)."""
    return pd.DataFrame([{"agent_id": str(i), "mode_cat": m, "age_cat": "20-24"}
                         for i, m in enumerate(modes)])


# Cible globale CEREMA : voiture 50, marche 25, TC 20, velo 5 (autres exclus).
_BAD = ["marche"] * 40           # 100% marche → très loin de la cible
_GOOD = (["voiture"] * 20 + ["marche"] * 10 + ["transports_collectifs"] * 8
         + ["velo"] * 2)          # ≈ cible


def test_significance_threshold_monotonic_in_temperature():
    hot = significance_threshold(10.0, t0=10.0, conf_min=0.55, conf_max=0.90)
    cold = significance_threshold(0.0, t0=10.0, conf_min=0.55, conf_max=0.90)
    mid = significance_threshold(5.0, t0=10.0, conf_min=0.55, conf_max=0.90)
    assert hot == 0.55 and cold == 0.90
    assert hot < mid < cold


def test_bootstrap_detects_clear_improvement():
    sa, mut = _df(_BAD), _df(_GOOD)
    summary = bootstrap_delta(sa, mut, L1Composite(0.0), CEREMA, "", "", b=200, seed=1)
    assert summary is not None
    assert summary["point"] < 0, "le prompt muté est nettement meilleur"
    assert summary["p_improve"] > 0.95
    accept, verdict, _ = bootstrap_verdict(summary, threshold=0.90)
    assert accept and verdict == "accepted"


def test_bootstrap_rejects_non_improvement_on_sign():
    # Muté identique au courant → Δ = 0 → rejeté sur le signe quel que soit le seuil.
    sa = mut = _df(_GOOD)
    summary = bootstrap_delta(sa, mut, L1Composite(0.0), CEREMA, "", "", b=100, seed=2)
    accept, verdict, _ = bootstrap_verdict(summary, threshold=0.55)
    assert not accept and verdict == "rejected_score"


def test_bootstrap_marginal_improvement_rejected_when_strict():
    # Amélioration minime et bruitée : significative à chaud, pas à froid.
    sa = _df(["marche"] * 19 + ["voiture"] * 21)
    mut = _df(["marche"] * 20 + ["voiture"] * 20)
    summary = bootstrap_delta(sa, mut, L1Composite(0.0), CEREMA, "", "", b=300, seed=3)
    assert summary is not None
    # Un seuil très strict (0.999) rejette le bruit ; un seuil lâche l'accepte si Δ<0.
    strict_accept, strict_verdict, _ = bootstrap_verdict(summary, threshold=0.999)
    if summary["point"] < 0:
        assert not strict_accept and strict_verdict == "rejected_stat"


def test_bootstrap_no_common_agents_returns_none():
    sa = pd.DataFrame([{"agent_id": "a", "mode_cat": "marche", "age_cat": "20-24"}])
    mut = pd.DataFrame([{"agent_id": "b", "mode_cat": "voiture", "age_cat": "20-24"}])
    assert bootstrap_delta(sa, mut, L1Composite(0.0), CEREMA, "", "", b=50) is None
    accept, verdict, _ = bootstrap_verdict(None, threshold=0.90)
    assert not accept and verdict == "rejected_stat"


# ── Non-infériorité (compaction, phase 4.5 DM) ───────────────────────────────

def test_noninferiority_accepts_when_score_preserved():
    # Compaction sans effet sur les décisions (df identique) → Δ ≈ 0 < marge.
    sa = mut = _df(_GOOD)
    summary = bootstrap_delta(sa, mut, L1Composite(0.0), CEREMA, "long prompt", "court",
                              b=200, seed=7)
    accept, _ = noninferiority_verdict(summary, margin=1.0)
    assert accept, "une compaction qui ne dégrade rien doit passer"


def test_noninferiority_rejects_real_degradation():
    # Retirer un bloc dégrade nettement (GOOD → BAD) → borne haute du Δ ≥ marge.
    sa, mut = _df(_GOOD), _df(_BAD)
    summary = bootstrap_delta(sa, mut, L1Composite(0.0), CEREMA, "", "", b=200, seed=8)
    accept, cause = noninferiority_verdict(summary, margin=1.0)
    assert not accept and "dégrad" in cause.lower()


def test_noninferiority_none_summary_refuses():
    accept, cause = noninferiority_verdict(None, margin=1.0)
    assert not accept and "indisponible" in cause
