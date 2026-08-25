"""Tests de la couronne de résidence (core/residence_zone.py, ticket 021).

Le trait est **observé**, pas imputé : un domicile est dans une commune ou il n'y est pas.
Il n'y a donc rien à verrouiller sur une distribution — ce qui est verrouillé ici, ce sont
les propriétés sans lesquelles le classement par CODE de zone fine ne serait pas légitime :

- **le classement par code est identique au classement par appartenance géométrique.**
  C'est la porte qui autorise tout le ticket : elle a été mesurée une fois par
  `make audit-couronnes` (trace `docs/traces/2026-08-24_couronne_equivalences/`), et elle
  est rejouée ici à chaque exécution des tests, sur les ressources versionnées. Une mesure
  ponctuelle se périme ; un test non ;
- **les modalités sont exactement celles de la référence EMC²** — c'est la clé de jointure
  de la page de synthèse, une divergence d'un caractère y ferait disparaître l'axe sans
  erreur ;
- **`hors périmètre` n'est pas une couronne** — le confondre avec la 3ᵉ a fait publier un
  stratum dont 76 % des habitants n'étaient pas dans l'enquête ;
- **rien ne se devine** — un code inconnu rend `None`, une commune ne se déduit jamais d'un
  secteur, une ressource absente ou d'une autre version lève au chargement ;
- **la divergence avec le classement métrique est réelle et voulue** — un test la fixe sur
  un point connu, pour qu'un futur « alignement » des deux soit un acte délibéré et non un
  effet de bord.

Hors ligne, sans les données PROGEDO d'accès restreint. Les tests qui exigent les
ressources exportées se sautent d'eux-mêmes quand elles n'ont pas été produites.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from llm_module.core.population_reference import COURONNES, OUT_OF_PERIMETER
from llm_module.core.residence_zone import (
    COMMUNE_TRAIT_KEY,
    CommuneTable,
    DEFAULT_GEOJSON,
    DEFAULT_TABLE,
    RESOURCE_VERSION,
    SECTOR_PREFIX_LEN,
    TRAIT_KEY,
    CommunalZones,
    CouronneTable,
    ResidenceZoneError,
    ZoneCouronne,
    secteur_of,
)

COMMUNE_TABLE = Path("llm_module/data/commune_couronne.json")
ZF_LAYER = Path("llm_module/data/zf_zones.gpkg")

needs_table = pytest.mark.skipif(not DEFAULT_TABLE.exists(),
                                 reason="zf_couronne.json absent (make communes-couronnes)")
needs_geojson = pytest.mark.skipif(not DEFAULT_GEOJSON.exists(),
                                   reason="couronne_perimetre.geojson absent")
needs_layer = pytest.mark.skipif(not ZF_LAYER.exists(),
                                 reason="zf_zones.gpkg absent (make zones)")


@pytest.fixture(scope="module")
def table() -> CouronneTable:
    return CouronneTable.load()


# ── Le module, sans ressource ────────────────────────────────────────────────

def test_secteur_of_prend_les_trois_premiers_chiffres():
    assert SECTOR_PREFIX_LEN == 3
    assert secteur_of("218102000") == "218"
    assert secteur_of(101101000) == "101"
    # Un code trop court n'est pas tronqué en silence : il n'a pas de secteur.
    assert secteur_of("21") == ""
    assert secteur_of(None) == ""
    assert secteur_of("") == ""


def test_hors_perimetre_n_est_pas_une_couronne():
    assert OUT_OF_PERIMETER not in COURONNES


def test_les_cles_de_trait_sont_distinctes_et_lisibles():
    assert TRAIT_KEY == "residence_zone"
    assert COMMUNE_TRAIT_KEY == "residence_commune"
    assert TRAIT_KEY != COMMUNE_TRAIT_KEY


def test_un_secteur_a_deux_couronnes_est_refuse():
    """La table doit être une FONCTION du secteur, sinon le classement est ambigu."""
    zones = [ZoneCouronne("101101000", "101", "Toulouse", "31555", "Toulouse"),
             ZoneCouronne("101102000", "101", "1ere couronne", "31555", "Toulouse")]
    with pytest.raises(ResidenceZoneError, match="deux couronnes"):
        CouronneTable(zones)


def test_ressource_absente_leve_au_chargement(tmp_path):
    with pytest.raises(ResidenceZoneError, match="absente"):
        CouronneTable.load(tmp_path / "pas_la.json")


def test_ressource_d_une_autre_version_est_refusee(tmp_path):
    """Une ressource périmée n'est pas servie « au mieux » : elle est refusée."""
    path = tmp_path / "zf_couronne.json"
    path.write_text(json.dumps({"version": "zc0", "zones": []}), encoding="utf-8")
    with pytest.raises(ResidenceZoneError, match="version"):
        CouronneTable.load(path)


def test_modalite_inattendue_est_refusee(tmp_path):
    path = tmp_path / "zf_couronne.json"
    path.write_text(json.dumps({
        "version": RESOURCE_VERSION,
        "zones": [{"zf": "101101000", "secteur": "101", "couronne": "4eme couronne",
                   "insee": "31555", "commune": "Toulouse"}]}), encoding="utf-8")
    with pytest.raises(ResidenceZoneError, match="inattendues"):
        CouronneTable.load(path)


# ── La ressource publiée ─────────────────────────────────────────────────────

@needs_table
def test_la_table_couvre_les_785_zones_et_les_88_secteurs(table: CouronneTable):
    assert len(table) == 785
    assert len(table.secteurs) == 88
    assert table.meta["n_zones"] == 785
    assert table.meta["n_secteurs"] == 88
    assert set(table.meta["counts"]) == set(COURONNES)
    assert sum(table.meta["counts"].values()) == 785


@needs_table
def test_les_codes_de_zone_fine_sont_bien_formes(table: CouronneTable):
    for zf, zone in table._by_zf.items():  # noqa: SLF001 - contrôle de forme interne
        assert len(zf) == 9 and zf.isdigit(), zf
        assert zone.secteur == zf[:SECTOR_PREFIX_LEN]
        assert zone.couronne in COURONNES
        assert len(zone.insee) == 5 and zone.insee.isdigit(), zone.insee
        assert zone.commune


@needs_table
def test_la_lecture_par_code_et_par_secteur_concordent(table: CouronneTable):
    for zf, zone in table._by_zf.items():  # noqa: SLF001
        assert table.couronne_of_zf(zf) == zone.couronne
        assert table.couronne_of_secteur(zone.secteur) == zone.couronne


@needs_table
def test_rien_ne_se_devine_hors_de_la_table(table: CouronneTable):
    # Code inconnu mais secteur connu : la couronne vient du secteur, qui est le vrai
    # porteur de l'information dans l'enquête.
    assert table.couronne_of_zf("101999999") == table.couronne_of_secteur("101")
    # La COMMUNE, elle, ne se déduit pas d'un secteur : plusieurs communes par secteur.
    assert table.commune_of_zf("101999999") is None
    # Secteur inconnu : rien.
    assert table.couronne_of_zf("999999999") is None
    assert table.couronne_of_zf(None) is None
    assert table.commune_of_zf("") is None


@needs_table
@pytest.mark.skipif(not COMMUNE_TABLE.exists(), reason="commune_couronne.json absent")
def test_la_table_de_zones_est_coherente_avec_celle_des_communes(table: CouronneTable):
    """Deux ressources produites par le même export doivent raconter la même chose."""
    communes = json.loads(COMMUNE_TABLE.read_text(encoding="utf-8"))
    par_insee = {row["insee"]: row["couronne"] for row in communes["communes"]}
    vues = {}
    for zone in table._by_zf.values():  # noqa: SLF001
        assert par_insee.get(zone.insee) == zone.couronne, zone
        vues[zone.insee] = zone.commune
    # Toutes les communes du périmètre portent au moins une zone fine : sinon la table de
    # zones décrirait un périmètre plus petit que celle des communes, en silence.
    assert set(vues) == set(par_insee)
    assert len(vues) == communes["n_communes"] == 453


# ── La porte du ticket 021 : code contre géométrie ───────────────────────────

@needs_table
@needs_geojson
@needs_layer
def test_le_classement_par_code_egale_le_classement_geometrique(table: CouronneTable):
    """La porte B du lot 0, rejouée à chaque exécution des tests.

    Deux chemins indépendants : un rattachement par les trois premiers chiffres du code,
    et une jointure spatiale contre la dissolution des secteurs. Le ticket 021 repose
    entièrement sur leur égalité — mesurée une fois le 2026-08-24, verrouillée ici.
    """
    geopandas = pytest.importorskip("geopandas")
    pyproj = pytest.importorskip("pyproj")

    layer = geopandas.read_file(ZF_LAYER)
    zones = CommunalZones.load()
    to_wgs = pyproj.Transformer.from_crs(2154, 4326, always_xy=True)

    desaccords = []
    for row in layer.itertuples():
        par_code = table.couronne_of_zf(row.ZF)
        lon, lat = to_wgs.transform(row.XL93, row.YL93)
        par_geometrie = zones.classify(lat, lon)
        if par_code != par_geometrie:
            desaccords.append((str(row.ZF), par_code, par_geometrie))

    assert len(layer) == 785
    assert not desaccords, (
        f"{len(desaccords)} zone(s) fine(s) classée(s) différemment selon le chemin : "
        f"{desaccords[:5]}. Le classement par code n'est plus légitime — reprendre le "
        f"lot 0 du ticket 021 avant de servir ce trait.")


@needs_geojson
def test_la_geometrie_rend_hors_perimetre_et_pas_une_couronne():
    zones = CommunalZones.load()
    # Capitole : le cœur de la commune de Toulouse.
    assert zones.classify(43.6045, 1.4440) == "Toulouse"
    # Un point franchement extérieur au périmètre d'enquête (sud de l'Ariège).
    assert zones.classify(43.10, 1.10) == OUT_OF_PERIMETER
    # Un point inconnu n'est pas une modalité : vide, comme une cellule de probabilité
    # vide n'est pas un 0.
    assert zones.classify(None, None) == ""
    assert zones.classify(43.6, None) == ""


@needs_geojson
def test_la_geometrie_couvre_les_quatre_couronnes():
    zones = CommunalZones.load()
    assert Counter(zones._names) == Counter(COURONNES)  # noqa: SLF001


# ── La divergence assumée avec le classement métrique ────────────────────────

@needs_table
@needs_geojson
def test_le_classement_metrique_diverge_et_c_est_documente(table: CouronneTable):
    """Un « faux Toulousain » : à 7,57 km du Capitole, mais à Auzeville-Tolosane.

    Le point vient de `docs/traces/2026-08-24_perimetre_population/agents_reclassement.csv`
    (persona 39705), l'un des 66 que le disque de 8 km baptise « Toulouse ». Ce test fixe
    la divergence entre les deux définitions : elle est voulue, bornée à 34 s de temps
    terminal sur le pire couple observé, et la refermer exige de ré-exporter les lois de
    `terminal_time_emc2.json` — un autre ticket, pas un effet de bord.
    """
    from llm_module.core.geo_reference import residence_zone as metrique

    lat, lon = 43.535540410127076, 1.484410194839593
    assert metrique(lat, lon) == "Toulouse"
    assert CommunalZones.load().classify(lat, lon) == "1ere couronne"


# ── Le cadre de tirage (ticket 026) ──────────────────────────────────────────

needs_communes = pytest.mark.skipif(
    not Path("llm_module/data/commune_couronne.json").exists(),
    reason="commune_couronne.json absent (make communes-couronnes)")


@needs_communes
def test_le_perimetre_compte_453_communes_sur_six_departements():
    """Le chiffre surprend, donc il est verrouillé : 453 communes, 6 départements.

    Recoupé au ticket 026 par la surface (5 428 km² contre 5 400 km² publiés par l'auat)
    et par le rapport d'enquête lui-même.
    """
    table = CommuneTable.load()
    assert len(table) == 453
    departements = {c[:2] for c in table.communes()}
    assert departements == {"31", "32", "81", "82", "09", "11"}
    assert sum(table.counts().values()) == 453


@needs_communes
def test_le_cadre_haute_garonne_est_un_sous_ensemble_strict():
    """La version légère du ticket 026 : 346 communes, et la 3ᵉ couronne amputée."""
    table = CommuneTable.load()
    complet, cadre = table.counts(), table.counts(["31"])
    assert len(table.communes(["31"])) == 346
    assert cadre["Toulouse"] == complet["Toulouse"] == 1
    assert cadre["1ere couronne"] == complet["1ere couronne"]
    # C'est là que la limite mord, et elle est publiée (perimetre-population.md, n°6).
    assert cadre["3eme couronne"] == 175 < complet["3eme couronne"] == 275


@needs_communes
def test_un_cadre_vide_leve_au_lieu_de_retomber_sur_le_departement():
    """Sans ce garde-fou, une faute de frappe ferait peupler tout le département."""
    table = CommuneTable.load()
    with pytest.raises(ResidenceZoneError, match="cadre de tirage vide"):
        table.communes(["75"])
    with pytest.raises(ResidenceZoneError, match="départements vide"):
        table.communes([])


@needs_communes
def test_l_appartenance_au_perimetre_se_lit_sur_le_code_insee():
    table = CommuneTable.load()
    assert table.couronne_of_insee("31555") == "Toulouse"
    assert table.contains("09038")          # La Bastide-de-Besplas, 3ᵉ couronne (Ariège)
    assert not table.contains("75056")      # Paris
    assert table.couronne_of_insee(None) is None


@needs_communes
@needs_table
def test_les_deux_tables_racontent_la_meme_geographie(table: CouronneTable):
    """`zf_couronne.json` (zones fines) et `commune_couronne.json` (communes) sont
    produites par le même export : leurs communes et leurs couronnes doivent coïncider."""
    communes = CommuneTable.load()
    vues = {z.insee for z in table._by_zf.values()}  # noqa: SLF001
    assert vues == set(communes.communes())
    for zone in table._by_zf.values():  # noqa: SLF001
        assert communes.couronne_of_insee(zone.insee) == zone.couronne
