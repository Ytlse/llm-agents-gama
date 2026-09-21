"""Tests unitaires pour l'analyse comportementale de stabilité et variation modale (modal_variation_rate.py).
"""

from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))

from scripts.analysis.modal_variation_rate import (
    compute_entropy,
    compute_persona_entropy,
    compute_transitions,
    compute_phase_summary,
    compute_activity_summary,
    compute_transition_matrix,
    extract_chosen_route,
)


def test_compute_entropy_properties():
    """Vérifie les propriétés fondamentales de l'entropie de Shannon."""
    # 1. Distribution déterministe (monomodale) -> H = 0 bit
    det_series = pd.Series(["Voiture Privée"] * 20)
    assert compute_entropy(det_series) == 0.0

    # 2. Distribution binaire équiprobable (pile/face) -> H = 1.0 bit
    bin_series = pd.Series(["Voiture Privée", "Vélo"] * 10)
    assert pytest.approx(compute_entropy(bin_series), 0.001) == 1.0

    # 3. Distribution équiprobable 4 modes -> H = 2.0 bits
    quad_series = pd.Series(["Voiture Privée", "Vélo", "Marche", "Transports_collectifs"] * 5)
    assert pytest.approx(compute_entropy(quad_series), 0.001) == 2.0


def test_extract_chosen_route():
    """Vérifie l'extraction de l'itinéraire retenu depuis Options (descriptif)."""
    row_nominal = pd.Series({
        "Mode de transport Choisi": "Marche",
        "Index retenu": 2,
        "Options (descriptif)": "0:car:100s:2km | 1:bike:150s:2.1km | 2:foot:600s:1.8km",
    })
    assert extract_chosen_route(row_nominal) == "foot:600s:1.8km"

    # Index manquant ou invalide -> repli sur le mode
    row_fallback = pd.Series({
        "Mode de transport Choisi": "Voiture Privée",
        "Index retenu": np.nan,
        "Options (descriptif)": "",
    })
    assert extract_chosen_route(row_fallback) == "Voiture Privée"


def test_compute_transitions_synthetic():
    """Vérifie le calcul des transitions pour une activité récurrente."""
    # Données synthétiques pour un agent sur 4 jours
    data = [
        {
            "ID Personne": "101",
            "ID Activité": "act_work",
            "motif_clean": "Travail",
            "Heure de départ": "2026-03-16 08:00:00",
            "depart_dt": pd.to_datetime("2026-03-16 08:00:00"),
            "journee_date": "2026-03-16",
            "jour_simule": 1,
            "phase": "1. Pré-choc (J1-7)",
            "Mode de transport Choisi": "Voiture Privée",
            "chosen_route": "car:1200s",
            "Méthode de sélection": "LLM",
        },
        {
            "ID Personne": "101",
            "ID Activité": "act_work",
            "motif_clean": "Travail",
            "Heure de départ": "2026-03-17 08:00:00",
            "depart_dt": pd.to_datetime("2026-03-17 08:00:00"),
            "journee_date": "2026-03-17",
            "jour_simule": 2,
            "phase": "1. Pré-choc (J1-7)",
            "Mode de transport Choisi": "Vélo",
            "chosen_route": "bike:1800s",
            "Méthode de sélection": "LLM",
        },
        {
            "ID Personne": "101",
            "ID Activité": "act_work",
            "motif_clean": "Travail",
            "Heure de départ": "2026-03-18 08:00:00",
            "depart_dt": pd.to_datetime("2026-03-18 08:00:00"),
            "journee_date": "2026-03-18",
            "jour_simule": 3,
            "phase": "1. Pré-choc (J1-7)",
            "Mode de transport Choisi": "Vélo",
            "chosen_route": "bike:1800s",
            "Méthode de sélection": "LLM",
        },
        {
            "ID Personne": "101",
            "ID Activité": "act_work",
            "motif_clean": "Travail",
            "Heure de départ": "2026-03-24 08:00:00",
            "depart_dt": pd.to_datetime("2026-03-24 08:00:00"),
            "journee_date": "2026-03-24",
            "jour_simule": 9,
            "phase": "2. Péri-choc (J8-9)",
            "Mode de transport Choisi": "Voiture Privée",
            "chosen_route": "car:1200s",
            "Méthode de sélection": "LLM Error (Default index)",
        },
    ]
    df = pd.DataFrame(data)

    transitions = compute_transitions(df, level="activite")
    assert len(transitions) == 3

    # Transition 1 -> 2 : Changement modal Voiture -> Vélo
    assert transitions[0].modal_change is True
    assert transitions[0].route_change is True
    assert transitions[0].is_llm_valid_transition is True

    # Transition 2 -> 3 : Même mode (Vélo -> Vélo)
    assert transitions[1].modal_change is False
    assert transitions[1].route_change is False
    assert transitions[1].is_llm_valid_transition is True

    # Transition 3 -> 4 : Vélo -> Voiture (non LLM valide)
    assert transitions[2].modal_change is True
    assert transitions[2].is_llm_valid_transition is False


def test_summaries_and_matrix():
    """Vérifie la synthèse par phase et matrice de transition."""
    # Simulation d'un jeu de 10 transitions
    from scripts.analysis.modal_variation_rate import TransitionObservation
    dummy_trans = [
        TransitionObservation(
            person_id="1", activite_id="a1", motif="Travail",
            jour_prev=1, jour_curr=2, date_prev="2026-03-16", date_curr="2026-03-17",
            phase_curr="1. Pré-choc (J1-7)",
            mode_prev="Voiture Privée", mode_curr="Vélo",
            route_prev="r1", route_curr="r2",
            modal_change=True, route_change=True, day_gap=1, is_consecutive_day=True,
            selection_prev="LLM", selection_curr="LLM", is_llm_valid_transition=True,
        ),
        TransitionObservation(
            person_id="1", activite_id="a1", motif="Travail",
            jour_prev=2, jour_curr=3, date_prev="2026-03-17", date_curr="2026-03-18",
            phase_curr="1. Pré-choc (J1-7)",
            mode_prev="Vélo", mode_curr="Vélo",
            route_prev="r2", route_curr="r2",
            modal_change=False, route_change=False, day_gap=1, is_consecutive_day=True,
            selection_prev="LLM", selection_curr="LLM", is_llm_valid_transition=True,
        ),
    ]

    p_sum = compute_phase_summary(dummy_trans)
    assert len(p_sum) == 1
    assert p_sum.iloc[0]["taux_variation_modal"] == 0.5
    assert p_sum.iloc[0]["stabilite_modale"] == 0.5

    a_sum = compute_activity_summary(dummy_trans)
    assert len(a_sum) == 1
    assert a_sum.iloc[0]["motif"] == "Travail"

    mat = compute_transition_matrix(dummy_trans)
    assert mat.loc["Vélo", "Vélo"] == 1.0
    assert mat.loc["Voiture Privée", "Vélo"] == 1.0
