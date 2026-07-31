"""L'hypercentre du move-log est celui du spec, pas une constante locale.

La colonne « Lieu de résidence » de `moves.csv` classe chaque agent en Toulouse /
1re / 2e / 3e couronne selon la distance de son domicile au centre-ville. Ce centre
doit être celui que publie `scripts/progedo_logit/feature_spec.json` — le même dont
dérivent les `dist_center_*` du modèle de choix modal. `move_logger.py` en portait une
seconde définition codée en dur (43.6047 / 1.4442), distante de 820 m : les agents de
la bande intermédiaire basculaient d'une couronne à l'autre selon le module qui les
regardait.
"""

import json
from pathlib import Path

import pytest

from llm_module.core.geo_reference import (
    FALLBACK_GEO_REFERENCE,
    geo_reference,
    hypercenter,
)
from urban_mobility_agents.utils.move_logger import _haversine_km, _residence_zone

FEATURE_SPEC = Path(__file__).resolve().parents[2] / "scripts/progedo_logit/feature_spec.json"

# L'ancienne constante concurrente. Elle ne doit plus jamais être le centre servi.
_LEGACY_CENTER = (43.6047, 1.4442)

SPEC_CENTER = (FALLBACK_GEO_REFERENCE["hypercenter"]["lat"],
               FALLBACK_GEO_REFERENCE["hypercenter"]["lon"])


@pytest.fixture(autouse=True)
def _resolution_fraiche():
    """La résolution est mise en cache pour le run : chaque test la rejoue."""
    geo_reference.cache_clear()
    yield
    geo_reference.cache_clear()


class TestSourceDeLHypercentre:

    @pytest.mark.skipif(not FEATURE_SPEC.exists(),
                        reason="feature_spec.json absent (données PROGEDO restreintes)")
    def test_hypercentre_lu_dans_le_feature_spec(self, monkeypatch):
        monkeypatch.setenv("MODE_CHOICE_FEATURE_SPEC", str(FEATURE_SPEC))
        geo_reference.cache_clear()
        published = json.loads(FEATURE_SPEC.read_text(encoding="utf-8"))["geo_reference"]["hypercenter"]
        assert hypercenter() == (published["lat"], published["lon"])

    @pytest.mark.skipif(not FEATURE_SPEC.exists(),
                        reason="feature_spec.json absent (données PROGEDO restreintes)")
    def test_le_repli_recopie_bien_la_valeur_publiee(self):
        """Repli et spec doivent rester la même valeur : sinon le repli ment."""
        published = json.loads(FEATURE_SPEC.read_text(encoding="utf-8"))["geo_reference"]["hypercenter"]
        assert FALLBACK_GEO_REFERENCE["hypercenter"]["lat"] == published["lat"]
        assert FALLBACK_GEO_REFERENCE["hypercenter"]["lon"] == published["lon"]

    def test_spec_absent_replie_sur_la_valeur_publiee_pas_sur_l_ancienne(self, monkeypatch, tmp_path):
        """Les données PROGEDO sont d'accès restreint : le module doit rester utilisable."""
        monkeypatch.setattr("llm_module.core.geo_reference._REPO_SPEC", tmp_path / "absent.json")
        monkeypatch.setattr("llm_module.core.geo_reference._CONTAINER_SPEC", tmp_path / "absent.json")
        monkeypatch.delenv("MODE_CHOICE_FEATURE_SPEC", raising=False)
        geo_reference.cache_clear()
        assert hypercenter() == SPEC_CENTER
        assert hypercenter() != _LEGACY_CENTER

    def test_spec_illisible_replie_sans_lever(self, monkeypatch, tmp_path):
        casse = tmp_path / "feature_spec.json"
        casse.write_text("{ pas du json", encoding="utf-8")
        monkeypatch.setenv("MODE_CHOICE_FEATURE_SPEC", str(casse))
        geo_reference.cache_clear()
        assert hypercenter() == SPEC_CENTER

    def test_le_spec_prime_sur_le_repli(self, monkeypatch, tmp_path):
        """C'est le fichier qui fait autorité, pas la constante recopiée."""
        autre = tmp_path / "feature_spec.json"
        autre.write_text(json.dumps(
            {"geo_reference": {"hypercenter": {"lat": 43.5, "lon": 1.5}}}), encoding="utf-8")
        monkeypatch.setenv("MODE_CHOICE_FEATURE_SPEC", str(autre))
        geo_reference.cache_clear()
        assert hypercenter() == (43.5, 1.5)


class TestCouronnesDeResidence:

    def _point_au_sud(self, km: float) -> tuple[float, float]:
        """Point situé `km` au sud de l'hypercentre du spec (même longitude)."""
        return SPEC_CENTER[0] - km / 111.19, SPEC_CENTER[1]

    def test_seuils_mesures_depuis_l_hypercentre_du_spec(self):
        assert _residence_zone(*SPEC_CENTER) == "Toulouse"
        assert _residence_zone(*self._point_au_sud(5)) == "Toulouse"
        assert _residence_zone(*self._point_au_sud(12)) == "1ere couronne"
        assert _residence_zone(*self._point_au_sud(30)) == "2eme couronne"
        assert _residence_zone(*self._point_au_sud(60)) == "3eme couronne"

    def test_la_bande_des_820_m_suit_le_spec_et_non_l_ancienne_constante(self):
        """Un domicile à 7,99 km du centre du spec, mais à plus de 8 km de l'ancien.

        C'est exactement le cas que les deux définitions classaient différemment :
        « Toulouse » pour le spec, « 1ere couronne » pour la constante abandonnée.
        """
        lat, lon = self._point_au_sud(7.99)
        assert _haversine_km(*SPEC_CENTER, lat, lon) < 8
        assert _haversine_km(*_LEGACY_CENTER, lat, lon) > 8
        assert _residence_zone(lat, lon) == "Toulouse"

    def test_domicile_inconnu_laisse_la_cellule_vide(self):
        assert _residence_zone(None, None) == ""
        assert _residence_zone(43.6, None) == ""
