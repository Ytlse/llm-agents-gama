"""L'hypercentre servi est celui du spec, et la colonne de résidence ne le consulte plus.

Deux décisions cohabitent dans ce fichier, et il faut les tenir séparées.

**L'hypercentre** (ticket 013) doit être celui que publie
`scripts/progedo_logit/feature_spec.json` — le même dont dérivent les `dist_center_*` du
modèle de choix modal. `move_logger.py` en portait une seconde définition codée en dur
(43.6047 / 1.4442), distante de 820 m : les agents de la bande intermédiaire basculaient
d'une couronne à l'autre selon le module qui les regardait. Ce centre ne sert plus qu'aux
distances (`dist_center_*` du modèle, axe A4 de l'audit) : depuis le ticket 028, le
**temps terminal** classe lui aussi ses points par commune.

**La colonne « Lieu de résidence »** de `moves.csv`, elle, ne se calcule plus du tout
(ticket 021) : elle recopie le trait `residence_zone` du persona, posé à la génération
depuis le découpage **par liste de communes** de l'enquête. Classer par distance
comparait 24,4 % des personas à la cible d'une autre zone et rangeait 45 domiciles hors
périmètre en 3ᵉ couronne. Les tests de seuils métriques restent — mais ils portent sur
`geo_reference.residence_zone`, qui n'a plus aucun appelant de production : c'est un
témoin d'audit, et les scripts de mesure archivés doivent rester rejouables.
"""

import json
from pathlib import Path

import pytest

from llm_module.core.geo_reference import (
    FALLBACK_GEO_REFERENCE,
    geo_reference,
    hypercenter,
)
from llm_module.core.geo_reference import haversine_km
from llm_module.core.geo_reference import residence_zone as classement_metrique
from urban_mobility_agents.utils.move_logger import _residence_zone

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


class TestClassementMetrique:
    """Les seuils de distance — TÉMOIN D'AUDIT, sans appelant de production (ticket 028).

    Jusqu'à tt3 ils servaient le temps terminal, dont les lois étaient stratifiées avec
    eux. Depuis tt4 le temps terminal classe par commune, comme la résidence. Les seuils
    restent verrouillés pour une autre raison : trois scripts de mesure les utilisent
    comme COMPARATEUR (`audit_perimetre`, `enrich_residence_zone --check`,
    `measure_couronne_v7`), et une trace archivée doit rester rejouable à l'identique.
    Ce n'est plus la définition de rien — cf. `TestColonneDeResidence`.
    """

    def _point_au_sud(self, km: float) -> tuple[float, float]:
        """Point situé `km` au sud de l'hypercentre du spec (même longitude)."""
        return SPEC_CENTER[0] - km / 111.19, SPEC_CENTER[1]

    def test_seuils_mesures_depuis_l_hypercentre_du_spec(self):
        assert classement_metrique(*SPEC_CENTER) == "Toulouse"
        assert classement_metrique(*self._point_au_sud(5)) == "Toulouse"
        assert classement_metrique(*self._point_au_sud(12)) == "1ere couronne"
        assert classement_metrique(*self._point_au_sud(30)) == "2eme couronne"
        assert classement_metrique(*self._point_au_sud(60)) == "3eme couronne"

    def test_la_bande_des_820_m_suit_le_spec_et_non_l_ancienne_constante(self):
        """Un point à 7,99 km du centre du spec, mais à plus de 8 km de l'ancien.

        C'est exactement le cas que les deux définitions classaient différemment :
        « Toulouse » pour le spec, « 1ere couronne » pour la constante abandonnée.
        """
        lat, lon = self._point_au_sud(7.99)
        assert haversine_km(*SPEC_CENTER, lat, lon) < 8
        assert haversine_km(*_LEGACY_CENTER, lat, lon) > 8
        assert classement_metrique(lat, lon) == "Toulouse"

    def test_point_inconnu_ne_recoit_pas_de_modalite(self):
        assert classement_metrique(None, None) == ""
        assert classement_metrique(43.6, None) == ""


class TestColonneDeResidence:
    """La colonne du journal RECOPIE le trait du persona. Elle ne calcule plus rien."""

    def test_le_trait_est_recopie_tel_quel(self):
        for zone in ("Toulouse", "1ere couronne", "2eme couronne", "3eme couronne"):
            assert _residence_zone({"residence_zone": zone}) == zone

    def test_hors_perimetre_est_une_valeur_de_la_colonne(self):
        """Axe A4 : un domicile hors des 453 communes n'est pas en 3ᵉ couronne.

        Il n'a aucune cible EMC², sa masse doit être comptée à part. La colonne doit
        donc pouvoir porter la valeur, sinon elle disparaîtrait dans le stratum voisin.
        """
        assert _residence_zone({"residence_zone": "hors périmètre"}) == "hors périmètre"

    def test_trait_absent_laisse_la_cellule_vide(self):
        """Population générée avant le ticket 021, ou domicile sans coordonnées."""
        assert _residence_zone({}) == ""
        assert _residence_zone({"residence_zone": ""}) == ""
        assert _residence_zone({"residence_zone": None}) == ""

    def test_valeur_hors_referentiel_ramenee_a_vide(self):
        """La synthèse joint cette colonne sur les libellés EMC² : une valeur exotique
        y disparaîtrait sans être comptée. Mieux vaut vide, qui est visible."""
        assert _residence_zone({"residence_zone": "4eme couronne"}) == ""
        assert _residence_zone({"residence_zone": "Blagnac"}) == ""

    def test_aucun_repli_a_la_distance_nest_possible(self):
        """Le module n'importe plus la fonction métrique : le repli est IMPOSSIBLE.

        C'est le cœur du lot 3 du ticket 021. Tant que l'import existait, un « repli
        raisonnable » pouvait être rétabli en une ligne par inadvertance — et il aurait
        reproduit exactement l'écart que ce ticket corrige, silencieusement.
        """
        import urban_mobility_agents.utils.move_logger as move_logger

        assert not hasattr(move_logger, "residence_zone")
        # Un persona sans trait mais avec un domicile en plein centre reste vide : la
        # cellule ne se remplit pas « au mieux ».
        assert _residence_zone({"lat": SPEC_CENTER[0], "lon": SPEC_CENTER[1]}) == ""
