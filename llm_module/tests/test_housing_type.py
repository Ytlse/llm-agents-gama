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
- **il conditionne sur la taille du ménage** (ticket 019) — le levier doit déplacer la
  loi dans le bon sens, laisser la géographie où elle est, et ne jamais ressusciter une
  modalité que l'enquête n'a pas vue dans la zone ;
- **il ne devine rien hors couche** — une zone inconnue rend `None`, pas une modalité,
  une ressource absente lève au chargement au lieu de se replier en silence, et une
  ressource d'avant le ticket 019 (v1, sans leviers) est refusée plutôt que servie.

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
    MIN_RESOURCE_VERSION,
    MODALITY_KEYS,
    REFERENCE_KEYS,
    SIZE_MAX,
    SIZE_TRAIT_KEY,
    TRAIT_KEY,
    HousingTypeTable,
    address_key,
    draw,
    key_for,
    label_for,
    rake,
    size_bucket,
    uniform,
)

CEREMA = Path("scripts/data/population/cerema_values.yaml")

# Loi de test : volontairement contrastée d'une zone à l'autre, pour que le
# conditionnement géographique soit visible dans les distributions tirées.
_URBAIN = (0.05, 0.05, 0.30, 0.58, 0.02)
_RURAL = (0.80, 0.15, 0.03, 0.02, 0.00)
_SECTEUR = (0.40, 0.15, 0.25, 0.19, 0.01)
_GLOBAL = (0.42, 0.15, 0.24, 0.19, 0.00)

# Leviers de test, dans l'esprit de ceux que l'enquête donne : la personne seule est
# tirée vers le collectif, le grand ménage vers l'individuel. Le levier neutre (taille
# 2) sert à vérifier qu'il ne déplace alors rien du tout.
_LEVIERS = {
    1: (0.45, 0.70, 1.40, 1.45, 2.00),
    2: (1.00, 1.00, 1.00, 1.00, 1.00),
    3: (1.30, 1.45, 0.72, 0.64, 0.26),
    4: (1.55, 1.35, 0.57, 0.54, 0.30),
}

# Effectifs par taille, tels que la ressource les publie (ticket 019 : « les effectifs
# de cellule sont écrits »). Sans conséquence sur le tirage, lus par la recette.
_BY_SIZE = [
    {"size": size, "individuel_isole_observed_pct": pct}
    for size, pct in ((1, 15.7), (2, 46.4), (3, 45.5), (4, 53.9))
]


@pytest.fixture
def table() -> HousingTypeTable:
    return HousingTypeTable(
        zones={"100100000": _URBAIN, "200200000": _RURAL},
        sectors={"1001": _SECTEUR},
        global_shares=_GLOBAL,
        size_leverage=dict(_LEVIERS),
        meta={},
        validation={"delivered": {"by_size": _BY_SIZE}},
    )


def _document(version: int = MIN_RESOURCE_VERSION, **overrides) -> dict:
    """Une ressource écrite sur disque, telle que l'export la produit."""
    doc = {
        "version": version,
        "modalities": list(MODALITY_KEYS),
        "sizes": list(range(1, SIZE_MAX + 1)),
        "global": list(_GLOBAL),
        "size_leverage": {str(size): {"n": 1000, "leverage": list(values),
                                      "cells": []}
                          for size, values in _LEVIERS.items()},
        "sectors": {"1001": {"n": 100, "shares": list(_SECTEUR)}},
        "zones": {"100100000": {"n": 20, "n_persons": 31, "shares": list(_URBAIN)},
                  "200200000": {"n": 20, "n_persons": 44, "shares": list(_RURAL)}},
        "validation": {"delivered": {"by_size": _BY_SIZE}},
        "meta": {"source": "test"},
    }
    doc.update(overrides)
    return doc


@pytest.fixture
def written_table(tmp_path) -> Path:
    path = tmp_path / "zf_housing_type.json"
    path.write_text(json.dumps(_document()), encoding="utf-8")
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
        assert uniform("43.600000,1.440000") == pytest.approx(0.0759474, abs=1e-7)

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
        assert table.zone_shares("100100000") == _URBAIN

    def test_zone_inconnue_se_replie_sur_son_secteur(self, table):
        assert table.zone_shares("100199000") == _SECTEUR

    def test_secteur_inconnu_se_replie_sur_le_perimetre(self, table):
        assert table.zone_shares("999999999") == _GLOBAL

    def test_hors_couche_ne_donne_aucune_loi(self, table):
        assert table.zone_shares(None) == ()

    def test_hors_couche_ne_donne_aucun_type(self, table):
        assert table.housing_type(None, 43.6, 1.44, 2) is None

    def test_le_niveau_de_repli_servi_est_publiable(self, table):
        """Le ticket 019 exige le compte par niveau à chaque enrichissement."""
        assert table.level_for("100100000") == "zone"
        assert table.level_for("100199000") == "secteur"
        assert table.level_for("999999999") == "perimetre"
        assert table.level_for(None) is None


class TestImputation:

    def test_meme_adresse_meme_logement(self, table):
        """930 personas se partagent 498 domiciles : les colocataires vont ensemble."""
        first = table.housing_type("100100000", 43.6047, 1.4442, 3)
        second = table.housing_type("100100000", 43.6047, 1.4442, 3)
        assert first is not None and first == second

    def test_adresses_voisines_tirent_independamment(self, table):
        types = {table.housing_type("100100000", 43.6 + i * 1e-4, 1.44, 2)
                 for i in range(200)}
        assert len(types) > 1

    def test_la_cle_d_adresse_est_arrondie_au_decimicron(self):
        assert address_key(43.60470004, 1.44420001) == address_key(43.6047, 1.4442)
        assert address_key(43.6047, 1.4442) != address_key(43.6048, 1.4442)

    def test_la_distribution_tiree_reproduit_la_loi(self, table):
        """Sans cette propriété, l'axe serait scoré contre EMC² sur une loi inventée.

        Tirée à la taille 2, dont le levier de test est neutre : ce que le tirage doit
        reproduire ici, c'est la loi de zone elle-même.
        """
        counts = Counter(table.housing_type("100100000", 43.0 + i * 1e-5, 1.4, 2)
                         for i in range(20_000))
        for key, share in zip(MODALITY_KEYS, _URBAIN):
            got = counts[LABEL_BY_KEY[key]] / 20_000
            assert got == pytest.approx(share, abs=0.015)

    def test_la_geographie_change_le_resultat(self, table):
        """Un trait tiré indépendamment de la zone mettrait des tours en rase campagne."""
        def part(zf: str, label: str) -> float:
            counts = Counter(table.housing_type(zf, 43.0 + i * 1e-5, 1.4, 2)
                             for i in range(5_000))
            return counts[label] / 5_000

        assert part("100100000", "Grand habitat collectif") > 0.5
        assert part("200200000", "Grand habitat collectif") < 0.05
        assert part("200200000", "Individuel isolé") > 0.7


class TestLevierDeTaille:
    """Le cœur du ticket 019 : la taille du ménage entre, la géographie reste."""

    def test_le_levier_neutre_ne_deplace_rien(self):
        assert rake(_URBAIN, (1.0,) * 5) == pytest.approx(_URBAIN)

    def test_levier_absent_laisse_la_loi_intacte(self):
        assert rake(_URBAIN, None) == pytest.approx(_URBAIN)

    def test_la_loi_rakee_reste_une_distribution(self, table):
        for size in range(1, SIZE_MAX + 1):
            shares = table.shares_for("100100000", size)
            assert sum(shares) == pytest.approx(1.0)
            assert all(s >= 0.0 for s in shares)

    def test_la_personne_seule_est_tiree_vers_le_collectif(self, table):
        """Dans une même zone, c'est tout l'objet du ticket : les familles dans les
        maisons, les personnes seules dans les appartements."""
        seule = table.shares_for("200200000", 1)
        famille = table.shares_for("200200000", 4)
        index = MODALITY_KEYS.index("individuel_isole")
        assert seule[index] < _RURAL[index] < famille[index]

    def test_une_modalite_absente_de_la_zone_ne_ressuscite_pas(self, table):
        """Le levier ne crée pas un logement que l'enquête n'a pas vu à cet endroit."""
        index = MODALITY_KEYS.index("autres")
        assert _RURAL[index] == 0.0
        for size in range(1, SIZE_MAX + 1):
            assert table.shares_for("200200000", size)[index] == 0.0

    def test_le_conditionnement_change_le_type_tire(self, table):
        """Sinon le levier serait écrit dans la ressource sans effet observable."""
        types = {size: Counter(
            table.housing_type("200200000", 43.0 + i * 1e-5, 1.4, size)
            for i in range(5_000)) for size in (1, 4)}
        assert (types[4]["Individuel isolé"] - types[1]["Individuel isolé"]) > 500

    def test_la_taille_est_ecretee_a_quatre(self, table):
        """Un ménage de six tire dans la loi des « 4 et plus » : l'enquête n'en dit
        pas plus, et découper plus fin estimerait un levier sur quelques dizaines."""
        assert size_bucket(6) == SIZE_MAX
        assert table.shares_for("100100000", 6) == table.shares_for("100100000", 4)

    def test_taille_absente_ou_absurde_ne_donne_aucune_loi(self, table):
        """Pas de repli sur la loi de zone seule : ce serait le gradient aplati qui
        revient par la fenêtre, sans que rien ne le signale."""
        for size in (None, 0, -1, "", "quatre"):
            assert size_bucket(size) is None
            assert table.shares_for("100100000", size) == ()
            assert table.housing_type("100100000", 43.6, 1.44, size) is None

    def test_la_cle_du_trait_de_taille_est_celle_du_persona(self):
        assert SIZE_TRAIT_KEY == "household_size"

    def test_un_levier_de_mauvaise_longueur_leve(self):
        """Ressource et module divergents : lever plutôt que raker de travers."""
        with pytest.raises(ValueError, match="Levier"):
            rake(_URBAIN, (1.0, 1.0))


class TestChargement:

    def test_ressource_absente_leve_avec_la_commande_a_lancer(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="make housing-type"):
            HousingTypeTable.load(tmp_path / "nulle-part.json")

    def test_ressource_lue_telle_qu_ecrite(self, written_table, table):
        loaded = HousingTypeTable.load(written_table)
        assert loaded.zones == table.zones
        assert loaded.sectors == table.sectors
        assert loaded.global_shares == table.global_shares
        assert loaded.size_leverage == table.size_leverage
        assert loaded.meta["source"] == "test"

    def test_modalites_divergentes_refusees(self, tmp_path):
        """Une table d'une autre version décalerait silencieusement toute la loi."""
        path = tmp_path / "table.json"
        path.write_text(json.dumps({
            "version": MIN_RESOURCE_VERSION,
            "modalities": ["maison", "appartement"],
            "global": [0.5, 0.5], "sectors": {}, "zones": {},
        }), encoding="utf-8")
        with pytest.raises(ValueError, match="modalités"):
            HousingTypeTable.load(path)

    def test_ressource_d_avant_le_ticket_019_refusee(self, tmp_path):
        """Une v1 n'a pas de leviers : la servir imputerait sans la taille, en silence.

        C'est le scénario du déploiement à moitié fait — module à jour, ressource
        périmée — et il doit lever, pas produire un gradient aplati.
        """
        path = tmp_path / "v1.json"
        document = _document(version=1)
        del document["size_leverage"]
        path.write_text(json.dumps(document), encoding="utf-8")
        with pytest.raises(ValueError, match="version 1"):
            HousingTypeTable.load(path)

    def test_ressource_a_leviers_incomplets_refusee(self, tmp_path):
        """Conditionner certains ménages et pas d'autres serait pire que rien."""
        path = tmp_path / "trous.json"
        document = _document()
        del document["size_leverage"]["4"]
        path.write_text(json.dumps(document), encoding="utf-8")
        with pytest.raises(ValueError, match=r"tailles de ménage \[4\]"):
            HousingTypeTable.load(path)

    def test_une_ligne_de_validation_incomplete_est_ignoree(self, tmp_path):
        """Chemin de VERDICT : mieux vaut une cible absente qu'une cible fabriquée.

        Une ressource écrite par une autre version peut ne pas porter toutes les clés.
        Compléter la ligne par un défaut ferait juger la population contre du vide ;
        l'ignorer laisse le contrôle en aval dire « cible non servie ».
        """
        path = tmp_path / "partiel.json"
        document = _document()
        document["validation"]["delivered"]["by_size"] = [
            {"size": 1, "individuel_isole_observed_pct": 15.7},
            {"size": 2},                                    # clé de mesure absente
            {"individuel_isole_observed_pct": 45.5},        # taille absente
        ]
        path.write_text(json.dumps(document), encoding="utf-8")
        assert HousingTypeTable.load(path).observed_isolated_share_by_size() == {1: 15.7}

    def test_le_bloc_de_validation_sert_les_cibles_de_recette(self, written_table):
        loaded = HousingTypeTable.load(written_table)
        assert loaded.observed_isolated_share_by_size() == {
            1: 15.7, 2: 46.4, 3: 45.5, 4: 53.9}


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

    def test_les_quatre_leviers_sont_servis(self):
        table = HousingTypeTable.load()
        assert set(table.size_leverage) == set(range(1, SIZE_MAX + 1))
        for values in table.size_leverage.values():
            assert len(values) == len(MODALITY_KEYS)
            assert all(v >= 0.0 for v in values)

    def test_le_levier_va_dans_le_sens_de_l_enquete(self):
        """Personne seule → collectif, grand ménage → individuel. Si ce signe
        s'inverse, c'est la ressource qui est fausse, pas le module."""
        table = HousingTypeTable.load()
        assert table.size_leverage[1][0] < 1.0 < table.size_leverage[SIZE_MAX][0]
        assert table.size_leverage[SIZE_MAX][3] < 1.0 < table.size_leverage[1][3]

    def test_le_test_interne_emc2_tient_le_critere_du_ticket(self):
        """Le critère d'acceptation vit dans la ressource, pas dans une promesse."""
        table = HousingTypeTable.load()
        validation = table.validation
        assert validation.get("passes") is True
        assert (validation["delivered"]["mean_abs_error_pt"]
                <= validation["max_mean_abs_error_pt"])

    def test_chaque_zone_a_le_secteur_de_repli_correspondant(self):
        table = HousingTypeTable.load()
        assert table.zones and table.sectors
        for zf in table.zones:
            assert zf[:4] in table.sectors
