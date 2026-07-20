"""Tests de la loss L1Composite et des cas limites (phase 1)."""

import pandas as pd

from calibration.metrics import (L1Composite, categorize_mode, l1_error,
                                 worst_strata_modes)

# Référence minimale au format cerema_values.yaml.
CEREMA = {
    "parts_modales_2023": {
        "global": {"marche": 25, "voiture": 50, "velo": 5,
                   "transports_collectifs": 20, "autres_modes": 3},
        "Age": {"20-24": {"marche": 30, "voiture": 40, "velo": 10,
                          "transports_collectifs": 20}},
        "occupation": {"actif_temps_plein": {"marche": 20, "voiture": 60,
                                             "velo": 5, "transports_collectifs": 15}},
        "genre": {"Homme": {"marche": 25, "voiture": 50, "velo": 5,
                            "transports_collectifs": 20}},
        "motif_deplacement": {"travail": {"marche": 15, "voiture": 65,
                                          "velo": 5, "transports_collectifs": 15}},
        "distance": {"1-2km": {"marche": 40, "voiture": 30, "velo": 10,
                              "transports_collectifs": 20}},
    }
}


def _df(n_marche, n_voiture, n_velo, n_tc, **strata):
    rows = []
    for mode, n in [("marche", n_marche), ("voiture", n_voiture),
                    ("velo", n_velo), ("transports_collectifs", n_tc)]:
        rows += [{"mode_cat": mode, **strata}] * n
    return pd.DataFrame(rows)


def test_categorize_mode():
    assert categorize_mode("foot,bus,foot") == "transports_collectifs"
    assert categorize_mode("car") == "voiture"
    assert categorize_mode("bicycle") == "velo"
    assert categorize_mode("foot") == "marche"
    assert categorize_mode(None) == "Autre"


def test_l1_error_excludes_autres_and_normalizes():
    # Distribution parfaite → erreur nulle (autres_modes exclu et renormalisé).
    actual = pd.Series({"marche": 25, "voiture": 50, "velo": 5,
                        "transports_collectifs": 20})
    assert l1_error(actual, CEREMA["parts_modales_2023"]["global"]) < 1e-6


def test_empty_df_returns_zero():
    assert L1Composite().compute(pd.DataFrame(), CEREMA).composite == 0.0


def test_absent_mode_penalized():
    # Aucun vélo ni TC → pénalité de mode absent non nulle.
    df = _df(50, 50, 0, 0, age_cat="20-24")
    scores = L1Composite(length_penalty_per_word=0.0).compute(df, CEREMA)
    assert scores.absent_penalty > 0


def test_length_penalty_scales_with_words():
    df = _df(25, 50, 5, 20)
    short = L1Composite(0.05).compute(df, CEREMA, prompt_text="un deux")
    long = L1Composite(0.05).compute(df, CEREMA, prompt_text="un deux trois quatre")
    assert long.length_penalty > short.length_penalty


def test_strata_below_min_count_ignored():
    # Une seule décision dans la strate 20-24 (< 5) → dimension âge neutre (0).
    df = _df(1, 0, 0, 0, age_cat="20-24")
    scores = L1Composite(0.0).compute(df, CEREMA)
    assert scores.age == 0.0


def test_worst_strata_ranks_by_impact():
    df = _df(0, 40, 0, 0, age_cat="20-24")  # 100% voiture vs cible 40%
    rows = worst_strata_modes(df, CEREMA, min_count=5)
    assert rows and rows[0]["n"] == 40
    assert all(r["impact"] >= rows[-1]["impact"] for r in rows)
