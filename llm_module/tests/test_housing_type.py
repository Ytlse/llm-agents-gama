"""Tests du trait « type de logement » (core/housing_type.py, action A2).

Le trait est **imputé** : aucun contrôle en aval ne peut distinguer une imputation
correcte d'une imputation biaisée en regardant une ligne. Ce qui est verrouillé ici,
ce sont donc les propriétés que l'imputation doit avoir en masse, et les frontières
qu'elle ne doit jamais franchir :

- **les modalités sont exactement celles de la référence EMC²** — c'est la clé de
  jointure de la page de synthèse, une divergence d'un caractère y ferait disparaître
  l'axe sans erreur ;
- **le tirage est déterministe** — pas d'un RNG, pas de `hash()` (randomisé par
  processus) : deux exécutions, deux machines, deux moments donnent le même trait ;
- **il porte sur l'adresse** — deux personas d'un même domicile ne peuvent pas se
  retrouver l'un en maison individuelle et l'autre en tour ;
- **il reproduit la loi qu'on lui donne** — sinon l'axe serait scoré contre EMC² sur
  une distribution inventée, ce qui est pire que l'axe vide qu'il remplace ;
- **il ne devine rien hors couche** — une zone inconnue rend `None`, pas une modalité,
  et une ressource absente lève au chargement au lieu de se replier en silence.

Hors ligne, sans les données PROGEDO. Les tests de parité avec la vraie ressource se
sautent d'eux-mêmes quand elle n'a pas été exportée.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest
import yaml

from llm_module.core.housing_type import (
    DEFAULT_RESOURCE,
    KEY_BY_LABEL,
    LABEL_BY_KEY,
    MODALITY_KEYS,
    REFERENCE_KEYS,
    TRAIT_KEY,
    HousingTypeTable,
    address_key,
    draw,
    key_for,
    label_for,
    uniform,
)

CEREMA = Path("scripts/data/population/cerema_values.yaml")

# Loi de test : volontairement contrastée d'une zone à l'autre, pour que le
# conditionnement géographique soit visible dans les distributions tirées.
_URBAIN = (0.05, 0.05, 0.30, 0.58, 0.02)
_RURAL = (0.80, 0.15, 0.03, 0.02, 0.00)
_SECTEUR = (0.40, 0.15, 0.25, 0.19, 0.01)
_GLOBAL = (0.42, 0.15, 0.24, 0.19, 0.00)


@pytest.fixture
def table() -> HousingTypeTable:
    return HousingTypeTable(
        zones={"100100000": _URBAIN, "200200000": _RURAL},
        sectors={"1001": _SECTEUR},
        global_shares=_GLOBAL,
        meta={},
    )


@pytest.fixture
def written_table(tmp_path, table) -> Path:
    path = tmp_path / "zf_housing_type.json"
    path.write_text(json.dumps({
        "version": 1,
        "modalities": list(MODALITY_KEYS),
        "global": list(table.global_shares),
        "sectors": {k: {"n": 100, "shares": list(v)} for k, v in table.sectors.items()},
        "zones": {k: {"n": 20, "shares": list(v)} for k, v in table.zones.items()},
        "meta": {"source": "test"},
    }), encoding="utf-8")
    return path


class TestModalites:
    """Les modalités sont un contrat partagé, pas une convention locale."""

    def test_les_quatre_modalites_de_reference_sont_celles_de_cerema(self):
        if not CEREMA.exists():
            pytest.skip("cerema_values.yaml absent")
        published = yaml.safe_load(CEREMA.read_text(encoding="utf-8"))
        keys = tuple((published["parts_modales_2023"]["type_logement"] or {}).keys())
        assert REFERENCE_KEYS == keys

    def test_autres_est_connu_du_module_mais_hors_reference(self):
        """L'enquête connaît « Autres » (0,4 %), la ventilation publiée l'ignore."""
        assert "autres" in MODALITY_KEYS
        assert "autres" not in REFERENCE_KEYS

    def test_libelles_et_cles_sont_en_bijection(self):
        assert len(KEY_BY_LABEL) == len(LABEL_BY_KEY) == len(MODALITY_KEYS)
        for key in MODALITY_KEYS:
            assert key_for(label_for(key)) == key

    def test_libelles_exacts_de_l_enquete(self):
        """Ce sont ces chaînes-là qui transitent par traits_json puis moves.csv."""
        assert LABEL_BY_KEY["individuel_isole"] == "Individuel isolé"
        assert LABEL_BY_KEY["individuel_accole"] == "Individuel accolé"
        assert LABEL_BY_KEY["petit_habitat_collectif"] == "Petit habitat collectif"
        assert LABEL_BY_KEY["grand_habitat_collectif"] == "Grand habitat collectif"

    def test_libelle_inconnu_ne_devient_pas_une_modalite(self):
        assert key_for("Maison") is None
        assert key_for("") is None
        assert label_for("individuel_neuf") is None

    def test_le_trait_porte_le_nom_attendu_par_le_journal(self):
        assert TRAIT_KEY == "housing_type"


class TestTirage:

    def test_uniforme_dans_l_intervalle(self):
        values = [uniform(f"adresse-{i}") for i in range(500)]
        assert all(0.0 <= v < 1.0 for v in values)
        assert len(set(values)) == len(values)

    def test_deterministe_entre_appels(self):
        assert uniform("43.600000,1.440000") == uniform("43.600000,1.440000")

    def test_valeur_gelee(self):
        """Un changement de sel ou d'algorithme rebat TOUTES les imputations.

        Ce doit être un acte délibéré : le test échoue si la valeur bouge sans que
        quelqu'un ait mis ce chiffre à jour en connaissance de cause.
        """
        assert uniform("43.600000,1.440000") == pytest.approx(0.3188185, abs=1e-7)

    def test_inverse_de_la_fonction_de_repartition(self):
        shares = (0.25, 0.25, 0.25, 0.25, 0.0)
        assert draw(shares, 0.0) == "individuel_isole"
        assert draw(shares, 0.24) == "individuel_isole"
        assert draw(shares, 0.26) == "individuel_accole"
        assert draw(shares, 0.51) == "petit_habitat_collectif"
        assert draw(shares, 0.99) == "grand_habitat_collectif"

    def test_modalite_de_masse_nulle_jamais_tiree(self):
        shares = (0.0, 0.0, 1.0, 0.0, 0.0)
        assert {draw(shares, i / 1000) for i in range(1000)} == {"petit_habitat_collectif"}

    def test_loi_vide_ou_degeneree_ne_produit_pas_de_modalite(self):
        """Imputer depuis rien serait exactement l'invention que le module refuse."""
        assert draw((), 0.5) is None
        assert draw((0.0, 0.0, 0.0, 0.0, 0.0), 0.5) is None


class TestLoiParZone:

    def test_zone_connue_sert_sa_propre_loi(self, table):
        assert table.shares_for("100100000") == _URBAIN

    def test_zone_inconnue_se_replie_sur_son_secteur(self, table):
        assert table.shares_for("100199000") == _SECTEUR

    def test_secteur_inconnu_se_replie_sur_le_perimetre(self, table):
        assert table.shares_for("999999999") == _GLOBAL

    def test_hors_couche_ne_donne_aucune_loi(self, table):
        assert table.shares_for(None) == ()

    def test_hors_couche_ne_donne_aucun_type(self, table):
        assert table.housing_type(None, 43.6, 1.44) is None


class TestImputation:

    def test_meme_adresse_meme_logement(self, table):
        """930 personas se partagent 498 domiciles : les colocataires vont ensemble."""
        first = table.housing_type("100100000", 43.6047, 1.4442)
        second = table.housing_type("100100000", 43.6047, 1.4442)
        assert first is not None and first == second

    def test_adresses_voisines_tirent_independamment(self, table):
        types = {table.housing_type("100100000", 43.6 + i * 1e-4, 1.44)
                 for i in range(200)}
        assert len(types) > 1

    def test_la_cle_d_adresse_est_arrondie_au_decimicron(self):
        assert address_key(43.60470004, 1.44420001) == address_key(43.6047, 1.4442)
        assert address_key(43.6047, 1.4442) != address_key(43.6048, 1.4442)

    def test_la_distribution_tiree_reproduit_la_loi(self, table):
        """Sans cette propriété, l'axe serait scoré contre EMC² sur une loi inventée."""
        counts = Counter(table.housing_type("100100000", 43.0 + i * 1e-5, 1.4)
                         for i in range(20_000))
        for key, share in zip(MODALITY_KEYS, _URBAIN):
            got = counts[LABEL_BY_KEY[key]] / 20_000
            assert got == pytest.approx(share, abs=0.015)

    def test_la_geographie_change_le_resultat(self, table):
        """Un trait tiré indépendamment de la zone mettrait des tours en rase campagne."""
        def part(zf: str, label: str) -> float:
            counts = Counter(table.housing_type(zf, 43.0 + i * 1e-5, 1.4)
                             for i in range(5_000))
            return counts[label] / 5_000

        assert part("100100000", "Grand habitat collectif") > 0.5
        assert part("200200000", "Grand habitat collectif") < 0.05
        assert part("200200000", "Individuel isolé") > 0.7


class TestChargement:

    def test_ressource_absente_leve_avec_la_commande_a_lancer(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="make housing-type"):
            HousingTypeTable.load(tmp_path / "nulle-part.json")

    def test_ressource_lue_telle_qu_ecrite(self, written_table, table):
        loaded = HousingTypeTable.load(written_table)
        assert loaded.zones == table.zones
        assert loaded.sectors == table.sectors
        assert loaded.global_shares == table.global_shares
        assert loaded.meta["source"] == "test"

    def test_modalites_divergentes_refusees(self, tmp_path):
        """Une table d'une autre version décalerait silencieusement toute la loi."""
        path = tmp_path / "table.json"
        path.write_text(json.dumps({
            "modalities": ["maison", "appartement"],
            "global": [0.5, 0.5], "sectors": {}, "zones": {},
        }), encoding="utf-8")
        with pytest.raises(ValueError, match="modalités"):
            HousingTypeTable.load(path)


@pytest.mark.skipif(not DEFAULT_RESOURCE.exists(),
                    reason="table du type de logement non exportée (make housing-type)")
class TestPariteAvecLaVraieTable:
    """Vérifications sur la ressource réelle, quand elle est présente."""

    def test_les_lois_sont_des_distributions(self):
        table = HousingTypeTable.load()
        assert sum(table.global_shares) == pytest.approx(1.0, abs=1e-3)
        for shares in list(table.zones.values()) + list(table.sectors.values()):
            assert len(shares) == len(MODALITY_KEYS)
            assert sum(shares) == pytest.approx(1.0, abs=1e-3)
            assert all(s >= 0.0 for s in shares)

    def test_chaque_zone_a_le_secteur_de_repli_correspondant(self):
        table = HousingTypeTable.load()
        assert table.zones and table.sectors
        for zf in table.zones:
            assert zf[:4] in table.sectors
