"""
Tests unitaires : filtrage du mode vélo selon personal_bike.

Vérifie que :
- Les trois valeurs valides ("Pas de vélo", "vélo normal", "VAE") sont correctement
  interprétées, y compris avec des variantes de casse.
- Le champ absent revient au défaut include_bike=True (rétrocompatibilité).
- _primary_mode identifie bien un plan vélo OSMnx.
- Le post-filtre supprime effectivement les plans vélo quand include_bike=False.
"""

import pytest
from unittest.mock import MagicMock

# ── helper : reproduit la logique de simulation_controller._compute_move_for_activity ──

def _include_bike(traits: dict) -> bool:
    return traits.get("personal_bike", "vélo normal").lower() != "pas de vélo"


# ── helper : reproduit _primary_mode (simulation_controller) ──────────────────

def _primary_mode(plan) -> str:
    modes = {(leg.mode or "").lower() for leg in plan.legs if not leg.is_transfer}
    if modes & {"car"}:
        return "car"
    if modes & {"bicycle", "bike"}:
        return "bike"
    if not modes - {"foot", "walk", ""}:
        return "walk"
    return "transit"


def _make_plan(mode: str):
    leg = MagicMock()
    leg.mode = mode
    leg.is_transfer = False
    plan = MagicMock()
    plan.legs = [leg]
    return plan


# ── Tests include_bike ────────────────────────────────────────────────────────

class TestIncludeBike:
    def test_pas_de_velo_majuscule(self):
        """Valeur réelle dans la population (P majuscule) → doit exclure le vélo."""
        assert _include_bike({"personal_bike": "Pas de vélo"}) is False

    def test_pas_de_velo_minuscule(self):
        assert _include_bike({"personal_bike": "pas de vélo"}) is False

    def test_pas_de_velo_tout_majuscule(self):
        assert _include_bike({"personal_bike": "PAS DE VÉLO"}) is False

    def test_velo_normal(self):
        assert _include_bike({"personal_bike": "vélo normal"}) is True

    def test_vae(self):
        assert _include_bike({"personal_bike": "VAE"}) is True

    def test_champ_absent_defaut_true(self):
        """Populations sans le champ personal_bike → rétrocompatibilité, vélo autorisé."""
        assert _include_bike({}) is True

    def test_valeur_inconnue_autorise_velo(self):
        """Valeur inattendue → ne doit pas bloquer le vélo (fail-open)."""
        assert _include_bike({"personal_bike": "trottinette"}) is True


# ── Tests _primary_mode ───────────────────────────────────────────────────────

class TestPrimaryMode:
    def test_plan_bicycle(self):
        assert _primary_mode(_make_plan("bicycle")) == "bike"

    def test_plan_bike(self):
        assert _primary_mode(_make_plan("bike")) == "bike"

    def test_plan_foot(self):
        assert _primary_mode(_make_plan("foot")) == "walk"

    def test_plan_car(self):
        assert _primary_mode(_make_plan("car")) == "car"

    def test_plan_bus(self):
        assert _primary_mode(_make_plan("bus")) == "transit"


# ── Tests post-filtre ─────────────────────────────────────────────────────────

class TestPostFilter:
    def _apply_filter(self, itineraries, include_bike: bool):
        if not include_bike:
            return [it for it in itineraries if _primary_mode(it) != "bike"]
        return itineraries

    def test_filtre_supprime_velo_si_pas_de_velo(self):
        plans = [_make_plan("foot"), _make_plan("bicycle"), _make_plan("bus")]
        result = self._apply_filter(plans, include_bike=False)
        modes = [_primary_mode(p) for p in result]
        assert "bike" not in modes
        assert len(result) == 2

    def test_filtre_conserve_velo_si_velo_dispo(self):
        plans = [_make_plan("foot"), _make_plan("bicycle"), _make_plan("bus")]
        result = self._apply_filter(plans, include_bike=True)
        assert len(result) == 3

    def test_filtre_liste_vide(self):
        assert self._apply_filter([], include_bike=False) == []

    def test_filtre_sans_velo_dans_liste(self):
        plans = [_make_plan("foot"), _make_plan("car")]
        result = self._apply_filter(plans, include_bike=False)
        assert len(result) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
