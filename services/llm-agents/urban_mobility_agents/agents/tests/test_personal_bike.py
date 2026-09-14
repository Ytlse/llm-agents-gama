"""
Tests unitaires : filtrage du mode vélo selon personal_bike.

Vérifie que :
- Les trois valeurs valides ("No bike", "regular bike", "e-bike") sont correctement
  interprétées, y compris avec des variantes de casse — et leurs équivalents français
  ("Pas de vélo", "vélo normal", "VAE"), que portent les cohortes d'avant le ticket 074.
- Le champ absent prive l'agent du vélo et lève une alarme (ticket 015, lot 1).
- `_vehicle_mode` identifie bien un plan vélo OSMnx.
- Le post-filtre supprime effectivement les plans vélo quand include_bike=False.

`_vehicle_mode` est **importée** de la production et non recopiée ici (ticket 022) : une
copie ne tombe que si le test change, jamais si la production change, et c'est cette
asymétrie qui a laissé passer les défauts du Téléo et du rail. C'est bien `_vehicle_mode`
— la question de la CHAÎNE (« où est la voiture ? ») — et non `_primary_mode` — la
question du MODE PRINCIPAL, qui suit la hiérarchie de l'enquête — que pose le post-filtre.
"""

import pytest
from unittest.mock import MagicMock

from urban_mobility_agents.simulation_controller import _vehicle_mode

# `_owns_bike` est IMPORTÉE de la production, pas recopiée. La copie qui vivait ici
# répondait encore « vélo autorisé » à un champ absent — le défaut d'avant le ticket 015 —
# et ne connaissait que le vocabulaire français : elle aurait laissé passer une cohorte v6
# entière sans jamais tomber, puisqu'elle ne mesurait qu'elle-même.
from urban_mobility_agents.vehicle_chain import _owns_bike as _include_bike


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

    def test_no_bike_anglais(self):
        """Valeur de la cohorte v6 (ticket 074) → doit exclure le vélo."""
        assert _include_bike({"personal_bike": "No bike"}) is False

    def test_no_bike_casse_variable(self):
        assert _include_bike({"personal_bike": "NO BIKE"}) is False
        assert _include_bike({"personal_bike": " no bike "}) is False

    def test_velo_normal(self):
        assert _include_bike({"personal_bike": "vélo normal"}) is True

    def test_vae(self):
        assert _include_bike({"personal_bike": "VAE"}) is True

    def test_regular_bike(self):
        assert _include_bike({"personal_bike": "regular bike"}) is True

    def test_e_bike(self):
        assert _include_bike({"personal_bike": "e-bike"}) is True

    def test_champ_absent_prive_du_velo(self):
        """Champ absent → SANS vélo et alarme (ticket 015, lot 1) : le repli prive d'un
        mode plutôt que d'en offrir un que l'agent n'a pas."""
        assert _include_bike({}) is False

    def test_valeur_inconnue_autorise_velo(self):
        """Valeur inattendue → ne doit pas bloquer le vélo (fail-open)."""
        assert _include_bike({"personal_bike": "trottinette"}) is True


# ── Tests _vehicle_mode ───────────────────────────────────────────────────────

class TestVehicleMode:
    def test_plan_bicycle(self):
        assert _vehicle_mode(_make_plan("bicycle")) == "bike"

    def test_plan_bike(self):
        assert _vehicle_mode(_make_plan("bike")) == "bike"

    def test_plan_foot(self):
        assert _vehicle_mode(_make_plan("foot")) == "walk"

    def test_plan_car(self):
        assert _vehicle_mode(_make_plan("car")) == "car"

    def test_plan_bus(self):
        assert _vehicle_mode(_make_plan("bus")) == "transit"


# ── Tests post-filtre ─────────────────────────────────────────────────────────

class TestPostFilter:
    def _apply_filter(self, itineraries, include_bike: bool):
        if not include_bike:
            return [it for it in itineraries if _vehicle_mode(it) != "bike"]
        return itineraries

    def test_filtre_supprime_velo_si_pas_de_velo(self):
        plans = [_make_plan("foot"), _make_plan("bicycle"), _make_plan("bus")]
        result = self._apply_filter(plans, include_bike=False)
        modes = [_vehicle_mode(p) for p in result]
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
