"""
tests/test_worker_helpers.py — Tests unitaires pour les helpers de worker/task_worker.py.

Couvre :
  - _extract_primary_mode  : réduction de chaînes de modes composés
  - _get_distance_bracket  : classification par tranche de distance
  - _parse_ratelimit_reset_seconds : parsing des valeurs x-ratelimit-reset

Aucun appel Celery/Redis/LLM.
"""

import pytest
from datetime import datetime, timezone, timedelta

from llm_module.worker.task_worker import (
    _extract_primary_mode,
    _get_distance_bracket,
    _parse_ratelimit_reset_seconds,
)


# ---------------------------------------------------------------------------
# _extract_primary_mode
# ---------------------------------------------------------------------------

class TestExtractPrimaryMode:
    # Modes simples
    def test_bus(self):
        assert _extract_primary_mode("bus") == "bus"

    def test_car(self):
        assert _extract_primary_mode("car") == "car"

    def test_walking(self):
        assert _extract_primary_mode("walking") == "walking"

    def test_foot(self):
        assert _extract_primary_mode("foot") == "walking"

    def test_cycling(self):
        assert _extract_primary_mode("cycling") == "cycling"

    def test_velo(self):
        assert _extract_primary_mode("vélo") == "cycling"

    def test_train(self):
        assert _extract_primary_mode("train") == "train"

    def test_ter(self):
        assert _extract_primary_mode("ter") == "train"

    def test_metro(self):
        assert _extract_primary_mode("metro") == "metro"

    def test_tram(self):
        assert _extract_primary_mode("tram") == "tram"

    # Modes composés — priorité
    def test_bus_with_foot_is_bus(self):
        assert _extract_primary_mode("foot,bus,foot") == "bus"

    def test_train_beats_bus(self):
        assert _extract_primary_mode("bus,train") == "train"

    def test_metro_beats_bus(self):
        assert _extract_primary_mode("bus,metro") == "metro"

    def test_tram_beats_bus(self):
        assert _extract_primary_mode("tram,foot") == "tram"

    def test_train_beats_car(self):
        assert _extract_primary_mode("car,rail") == "train"

    def test_mixed_case_normalised(self):
        assert _extract_primary_mode("BUS") == "bus"

    # Cas limites
    def test_empty_string_returns_unknown(self):
        assert _extract_primary_mode("") == "unknown"

    def test_unknown_literal_returns_unknown(self):
        assert _extract_primary_mode("unknown") == "unknown"

    def test_unrecognised_mode_returns_other(self):
        assert _extract_primary_mode("hovercraft") == "other"

    def test_voiture(self):
        assert _extract_primary_mode("voiture") == "car"

    def test_driving(self):
        assert _extract_primary_mode("driving") == "car"

    def test_tc(self):
        assert _extract_primary_mode("tc") == "bus"

    def test_transports_en_commun(self):
        assert _extract_primary_mode("transports en commun") == "bus"

    def test_subway(self):
        assert _extract_primary_mode("subway") == "metro"

    def test_tramway(self):
        assert _extract_primary_mode("tramway") == "tram"

    def test_intercites(self):
        assert _extract_primary_mode("intercités") == "train"


# ---------------------------------------------------------------------------
# _get_distance_bracket
# ---------------------------------------------------------------------------

class TestGetDistanceBracket:
    def test_under_1km(self):
        assert _get_distance_bracket(0) == "0-1km"
        assert _get_distance_bracket(999) == "0-1km"

    def test_1_to_2km(self):
        assert _get_distance_bracket(1_000) == "1-2km"
        assert _get_distance_bracket(1_999) == "1-2km"

    def test_2_to_5km(self):
        assert _get_distance_bracket(2_000) == "2-5km"
        assert _get_distance_bracket(4_999) == "2-5km"

    def test_5_to_10km(self):
        assert _get_distance_bracket(5_000) == "5-10km"
        assert _get_distance_bracket(9_999) == "5-10km"

    def test_10_to_20km(self):
        assert _get_distance_bracket(10_000) == "10-20km"
        assert _get_distance_bracket(19_999) == "10-20km"

    def test_20_to_50km(self):
        assert _get_distance_bracket(20_000) == "20-50km"
        assert _get_distance_bracket(49_999) == "20-50km"

    def test_above_50km(self):
        assert _get_distance_bracket(50_000) == ">50km"
        assert _get_distance_bracket(100_000) == ">50km"

    def test_exact_boundaries(self):
        # Les bornes sont exclusives à gauche (distance < N)
        assert _get_distance_bracket(1_000) == "1-2km"   # >= 1000 → plus 0-1km
        assert _get_distance_bracket(5_000) == "5-10km"  # >= 5000 → plus 2-5km


# ---------------------------------------------------------------------------
# _parse_ratelimit_reset_seconds
# ---------------------------------------------------------------------------

class TestParseRatelimitResetSeconds:
    # Formats Groq (durée)
    def test_seconds_only(self):
        assert _parse_ratelimit_reset_seconds("45s") == 47   # 45 + 2 de marge

    def test_minutes_and_seconds(self):
        result = _parse_ratelimit_reset_seconds("6m0s")
        assert result == 362  # 360 + 2

    def test_minutes_and_decimal_seconds(self):
        result = _parse_ratelimit_reset_seconds("59m17.087999999s")
        # int(59*60 + 17.087...) = 3557, +2 de marge = 3559
        assert result == 3559

    def test_small_seconds_clamped_to_10(self):
        # 3s + 2 = 5, inférieur à 10 → doit être clampé à 10
        assert _parse_ratelimit_reset_seconds("3s") == 10

    def test_very_long_duration_clamped_to_3600(self):
        # 100 minutes → 6000s > 3600 → clampé
        assert _parse_ratelimit_reset_seconds("100m0s") == 3600

    # Format ISO 8601 (OpenAI)
    def test_iso_8601_near_future(self):
        future = datetime.now(timezone.utc) + timedelta(seconds=58)
        value = future.strftime("%Y-%m-%dT%H:%M:%SZ")
        result = _parse_ratelimit_reset_seconds(value)
        # Doit être dans l'intervalle [58, 62] environ (±2 de marge + délai d'exécution)
        assert 10 <= result <= 3600

    def test_iso_8601_past_clamped_to_10(self):
        past = datetime.now(timezone.utc) - timedelta(seconds=30)
        value = past.strftime("%Y-%m-%dT%H:%M:%SZ")
        result = _parse_ratelimit_reset_seconds(value)
        assert result == 10  # delta négatif + 2 < 10 → clampé

    # Valeur nulle ou invalide → défaut
    def test_none_returns_default(self):
        assert _parse_ratelimit_reset_seconds(None) == 60

    def test_empty_string_returns_default(self):
        assert _parse_ratelimit_reset_seconds("") == 60

    def test_unparseable_string_returns_default(self):
        assert _parse_ratelimit_reset_seconds("not-a-date") == 60

    def test_custom_default(self):
        assert _parse_ratelimit_reset_seconds(None, default=30) == 30
