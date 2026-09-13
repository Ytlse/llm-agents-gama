"""La table des tracés vient de la recette, ou le runtime l'alarme.

LE DÉFAUT VISÉ
--------------
Pour faire monter un agent dans un véhicule, `Inhabitant.gaml` compare le
`shape_id` du véhicule à la liste que Python a posée sur la jambe de
l'itinéraire. Cette liste vient de `GTFSData.get_shape_id_from_route_info`, qui
lisait une table construite depuis le **seul feed primaire** (Tisséo) alors que
les couches et les courses portent **trois** réseaux depuis le 2026-09-04.
Mesuré ce jour-là : **80 des 199 lignes** du fichier des courses (17 TER,
58 cars liO, 5 lignes circulaires) et **2 277 courses** roulaient dans GAMA
sans qu'aucun itinéraire ne puisse les désigner — la fonction rendait `[]`,
**indistinguable** de « pas de tracé pour ce couple d'arrêts ».

Chaque test porte sur une décision qui, prise à l'envers, produit un silence
plausible :

  * fichier annexe absent → **[ALARME]**, table marquée partielle ; sans ce cri,
    l'échec ressemble à une donnée manquante légitime ;
  * une ligne SANS géométrie publiée (le TER) devient joignable **parce que** la
    recette a publié les `shape_id` qu'elle a fabriqués — le runtime n'en
    refabrique aucun ;
  * un témoin de fraîcheur qui a bougé (les couches refaites seules) → refus et
    alarme : la table ne désignerait plus les tracés que GAMA dessine ;
  * des compteurs qui ne correspondent pas au contenu → refus : un fichier
    tronqué a les bonnes empreintes de ses frères ;
  * une ligne indésignable s'alarme **une fois**, pas à chaque itinéraire ;
  * l'identifiant de ligne d'OTP est recoupé avec le catalogue : `lio:305` est
    la ligne `305`, pas une ligne inconnue.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from inputs.gtfs import reader as reader_module  # noqa: E402
from inputs.gtfs import table_traces  # noqa: E402
from inputs.gtfs.reader import GTFSData  # noqa: E402

# Un tracé de TER tel que la RECETTE le nomme : `<route_id>:<sens>:<empreinte>`.
# Aucun feed ne publie cet identifiant ; seule la recette sait le fabriquer, et
# c'est tout l'objet du fichier annexe.
SHAPE_TER = "FR:Line::ABC:1:7955fdab"
ROUTE_TER = "FR:Line::ABC:"
GARE_A, GARE_B = "StopPoint:OCETrain TER-87611830", "StopPoint:OCETrain TER-87611467"


def _feed_tisseo(dossier: Path) -> Path:
    """Le feed primaire : une ligne de bus, sa géométrie, deux arrêts."""
    dossier.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"route_id": "line:8", "route_short_name": "8",
                   "route_long_name": "Bus 8", "route_type": "3"}]
                 ).to_csv(dossier / "routes.txt", index=False)
    pd.DataFrame([{"stop_id": "stop_point:SP_1", "stop_name": "Arènes",
                   "stop_lat": 43.5940, "stop_lon": 1.4165, "location_type": 0},
                  {"stop_id": "stop_point:SP_2", "stop_name": "Patte d'Oie",
                   "stop_lat": 43.5990, "stop_lon": 1.4210, "location_type": 0}]
                 ).to_csv(dossier / "stops.txt", index=False)
    pd.DataFrame([{"route_id": "line:8", "service_id": "SVC_1", "trip_id": "t1",
                   "direction_id": 0, "shape_id": "14852"}]
                 ).to_csv(dossier / "trips.txt", index=False)
    pd.DataFrame([{"trip_id": "t1", "stop_sequence": 0, "stop_id": "stop_point:SP_1",
                   "arrival_time": "07:00:00", "departure_time": "07:00:00",
                   "shape_dist_traveled": 0.0},
                  {"trip_id": "t1", "stop_sequence": 1, "stop_id": "stop_point:SP_2",
                   "arrival_time": "07:05:00", "departure_time": "07:05:00",
                   "shape_dist_traveled": 700.0}]
                 ).to_csv(dossier / "stop_times.txt", index=False)
    pd.DataFrame([{"shape_id": "14852", "shape_pt_lat": 43.5940, "shape_pt_lon": 1.4165,
                   "shape_pt_sequence": 0, "shape_dist_traveled": 0.0},
                  {"shape_id": "14852", "shape_pt_lat": 43.5990, "shape_pt_lon": 1.4210,
                   "shape_pt_sequence": 1, "shape_dist_traveled": 700.0}]
                 ).to_csv(dossier / "shapes.txt", index=False)
    pd.DataFrame([{"service_id": "SVC_1", "date": "20260316", "exception_type": 1}]
                 ).to_csv(dossier / "calendar_dates.txt", index=False)
    (dossier / "calendar.txt").write_text(
        "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
        "start_date,end_date\n", encoding="utf-8")
    return dossier


def _feed_ter(dossier: Path) -> Path:
    """Un réseau à la façon du TER : `shapes.txt` réduit à son en-tête.

    Il sert au CATALOGUE des lignes (joint par `init_route_lookup_maps`) ; sa
    géométrie, elle, n'existe pas — d'où le fichier annexe.
    """
    dossier.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"route_id": ROUTE_TER, "route_short_name": "P2",
                   "route_long_name": "L'Isle-Jourdain — Toulouse", "route_type": "2"}]
                 ).to_csv(dossier / "routes.txt", index=False)
    pd.DataFrame([{"stop_id": GARE_A, "stop_name": "Pibrac",
                   "stop_lat": 43.62133, "stop_lon": 1.28912, "location_type": 0},
                  {"stop_id": GARE_B, "stop_name": "Colomiers",
                   "stop_lat": 43.60373, "stop_lon": 1.33422, "location_type": 0}]
                 ).to_csv(dossier / "stops.txt", index=False)
    (dossier / "shapes.txt").write_text(
        "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence,shape_dist_traveled\n",
        encoding="utf-8")
    return dossier


def _couches(dossier: Path) -> dict[str, str]:
    """Les deux frères dont le fichier annexe note l'empreinte."""
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "routes.shp").write_bytes(b"couche des traces, generation 1")
    (dossier / "routes.dbf").write_bytes(b"attributs des traces, generation 1")
    (dossier / "trip_info.json").write_text('{"trip_list": []}', encoding="utf-8")
    return {"routes.shp": "routes.shp", "routes.dbf": "routes.dbf",
            "trip_info.json": "trip_info.json"}


def _table_de_reference() -> dict:
    return {
        ROUTE_TER: {SHAPE_TER: {GARE_A: 3, GARE_B: 5}},
        "line:8": {"14852": {"stop_point:SP_1": 0, "stop_point:SP_2": 1}},
    }


def _ecrire_annexe(dossier: Path, table=None, arrets=None) -> Path:
    document = table_traces.construire(
        table=table if table is not None else _table_de_reference(),
        arrets=arrets if arrets is not None else {
            GARE_A: {"stop_name": "Pibrac", "stop_lat": 43.62133, "stop_lon": 1.28912},
            GARE_B: {"stop_name": "Colomiers", "stop_lat": 43.60373, "stop_lon": 1.33422},
        },
        dossier_temoins=dossier,
        noms_temoins=("routes.shp", "routes.dbf", "trip_info.json"),
        genere_le="2026-09-04T12:00:00",
        recette="scripts/data/gama/export_trip_info.py",
        reseaux={"ter": {"courses_retenues": 884}},
    )
    chemin = dossier / table_traces.NOM_FICHIER
    table_traces.ecrire(chemin, document)
    return chemin


@pytest.fixture
def alarmes():
    """Capture les ERROR de loguru — `caplog` ne les voit pas (pas de propagation)."""
    from loguru import logger

    messages: list[str] = []
    sink = logger.add(lambda m: messages.append(str(m)), level="ERROR")
    yield messages
    logger.remove(sink)


@pytest.fixture
def journal():
    """Capture les INFO de loguru : le succès doit se journaliser explicitement."""
    from loguru import logger

    messages: list[str] = []
    sink = logger.add(lambda m: messages.append(str(m)), level="INFO")
    yield messages
    logger.remove(sink)


@pytest.fixture
def monde(tmp_path, monkeypatch):
    """Un feed primaire, un feed TER à côté, des couches, et la table annexe."""
    racine = tmp_path / "gtfs"
    primaire = _feed_tisseo(racine / "tisseo_gtfs")
    _feed_ter(racine / "ter_gtfs")
    includes = tmp_path / "includes"
    _couches(includes)
    annexe = _ecrire_annexe(includes)
    monkeypatch.setattr(reader_module.settings.gtfs, "gtfs_file", str(primaire),
                        raising=False)
    monkeypatch.setattr(reader_module.settings.gtfs, "shape_lookup_file", str(annexe),
                        raising=False)
    return {"primaire": primaire, "includes": includes, "annexe": annexe}


# ── La ligne sans géométrie devient joignable ────────────────────────────────

class TestLigneFerroviaireJoignable:
    def test_le_ter_est_desormais_designable(self, monde):
        g = GTFSData.from_gtfs_files(str(monde["primaire"]))
        assert g.source_table_traces == GTFSData.SOURCE_ANNEXE
        assert g.table_traces_partielle is False
        assert g.get_shape_id_from_route_info(ROUTE_TER, GARE_A, GARE_B) == [SHAPE_TER]

    def test_sans_le_fichier_annexe_la_meme_ligne_rend_une_liste_vide(self, monde):
        """L'état d'avant le correctif, reproduit : le feed primaire seul."""
        monde["annexe"].unlink()
        g = GTFSData.from_gtfs_files(str(monde["primaire"]))
        assert g.get_shape_id_from_route_info(ROUTE_TER, GARE_A, GARE_B) == []
        # Et le bus du feed primaire, lui, reste joignable : le repli n'est pas une panne.
        assert g.get_shape_id_from_route_info(
            "line:8", "stop_point:SP_1", "stop_point:SP_2") == ["14852"]

    def test_le_sens_du_couple_d_arrets_est_respecte(self, monde):
        g = GTFSData.from_gtfs_files(str(monde["primaire"]))
        assert g.get_shape_id_from_route_info(ROUTE_TER, GARE_B, GARE_A) == []

    def test_l_identifiant_du_trace_est_celui_de_la_recette(self, monde):
        """Le runtime ne fabrique aucun `shape_id` : il rend celui qui est publié.

        C'est l'invariant qui empêche une seconde implémentation de la règle
        `<route_id>:<sens>:<empreinte>` d'exister dans le dépôt.
        """
        g = GTFSData.from_gtfs_files(str(monde["primaire"]))
        publies = {s for par_trace in json.loads(monde["annexe"].read_text())["table"].values()
                   for s in par_trace}
        rendus = set(g.get_shape_id_from_route_info(ROUTE_TER, GARE_A, GARE_B))
        assert rendus <= publies


# ── Les alarmes ──────────────────────────────────────────────────────────────

class TestAlarmes:
    def test_fichier_absent_alarme_et_marque_la_table_partielle(self, monde, alarmes):
        monde["annexe"].unlink()
        g = GTFSData.from_gtfs_files(str(monde["primaire"]))
        assert g.table_traces_partielle is True
        assert g.source_table_traces == "feed_primaire:absente"
        assert any("[ALARME]" in m and "absente" in m for m in alarmes), alarmes

    def test_temoin_qui_a_bouge_refuse_la_table(self, monde, alarmes):
        """`make gama-layers` seul refait `routes.shp` : la paire est dépareillée."""
        (monde["includes"] / "routes.shp").write_bytes(b"couche des traces, generation 2")
        g = GTFSData.from_gtfs_files(str(monde["primaire"]))
        assert g.source_table_traces == "feed_primaire:depareillee"
        assert g.get_shape_id_from_route_info(ROUTE_TER, GARE_A, GARE_B) == []
        assert any("[ALARME]" in m and "depareillee" in m for m in alarmes), alarmes

    def test_temoin_disparu_refuse_la_table(self, monde, alarmes):
        (monde["includes"] / "trip_info.json").unlink()
        g = GTFSData.from_gtfs_files(str(monde["primaire"]))
        assert g.source_table_traces == "feed_primaire:temoin_absent"
        assert any("[ALARME]" in m for m in alarmes)

    def test_compteurs_qui_ne_correspondent_pas_refusent_la_table(self, monde, alarmes):
        document = json.loads(monde["annexe"].read_text())
        document["table"].pop("line:8")  # tronqué : les empreintes restent bonnes
        monde["annexe"].write_text(json.dumps(document), encoding="utf-8")
        g = GTFSData.from_gtfs_files(str(monde["primaire"]))
        assert g.source_table_traces == "feed_primaire:comptes"
        assert any("[ALARME]" in m for m in alarmes)

    def test_format_inconnu_refuse_la_table(self, monde, alarmes):
        document = json.loads(monde["annexe"].read_text())
        document["format"] = table_traces.FORMAT + 1
        monde["annexe"].write_text(json.dumps(document), encoding="utf-8")
        g = GTFSData.from_gtfs_files(str(monde["primaire"]))
        assert g.source_table_traces == "feed_primaire:format"
        assert any("[ALARME]" in m for m in alarmes)

    def test_fichier_illisible_refuse_la_table(self, monde, alarmes):
        monde["annexe"].write_text("{ ceci n'est pas du json", encoding="utf-8")
        g = GTFSData.from_gtfs_files(str(monde["primaire"]))
        assert g.source_table_traces == "feed_primaire:illisible"
        assert any("[ALARME]" in m for m in alarmes)

    def test_ligne_indesignable_alarme_une_seule_fois(self, monde, alarmes):
        """Front montant : la cause est unique, les itinéraires sont nombreux."""
        g = GTFSData.from_gtfs_files(str(monde["primaire"]))
        for _ in range(5):
            assert g.get_shape_id_from_route_info("inconnue", GARE_A, GARE_B) == []
        vues = [m for m in alarmes if "indésignable" in m]
        assert len(vues) == 1, vues
        assert g.resume_table_traces()["appels_ligne_absente"] == 5
        assert g.resume_table_traces()["lignes_indesignables"] == ["inconnue"]

    def test_jambe_sans_arret_resolu_alarme_aussi(self, monde, alarmes):
        g = GTFSData.from_gtfs_files(str(monde["primaire"]))
        assert g.get_shape_id_from_route_info(ROUTE_TER, None, GARE_B) == []
        assert any("arret non resolu" in m for m in alarmes), alarmes
        assert g.resume_table_traces()["appels_arret_non_resolu"] == 1

    def test_le_succes_se_journalise(self, monde, journal):
        """Un runtime muet quand tout va bien ne distingue pas « lu » de « rien lu »."""
        GTFSData.from_gtfs_files(str(monde["primaire"]))
        assert any("table des tracés lue" in m for m in journal), journal


# ── Le catalogue d'arrêts, et l'emprise du monde qui ne doit pas bouger ──────

class TestArretsHorsFeedPrimaire:
    def test_la_gare_ter_se_resout_par_le_catalogue_annexe(self, monde):
        g = GTFSData.from_gtfs_files(str(monde["primaire"]))
        gare = g.get_stop(GARE_A)
        assert gare.stop_name == "Pibrac"
        assert gare.stop_lat == pytest.approx(43.62133)

    def test_le_catalogue_annexe_n_elargit_pas_l_emprise_du_monde(self, monde):
        """`get_bounding_box` fixe l'emprise du monde GAMA.

        Y verser des gares de toute l'Occitanie l'étendrait bien au-delà du
        périmètre d'enquête — d'où un catalogue tenu à l'écart de `self.stops`.
        """
        g = GTFSData.from_gtfs_files(str(monde["primaire"]))
        min_lon, min_lat, max_lon, max_lat = g.get_bounding_box()
        assert (min_lon, max_lon) == pytest.approx((1.4165, 1.4210))
        assert (min_lat, max_lat) == pytest.approx((43.5940, 43.5990))

    def test_un_arret_vraiment_inconnu_leve_toujours(self, monde):
        g = GTFSData.from_gtfs_files(str(monde["primaire"]))
        with pytest.raises(ValueError):
            g.get_stop("StopPoint:jamais-vu")


# ── L'identifiant de ligne rendu par OTP ─────────────────────────────────────

class TestResolutionDesIdentifiantsOTP:
    """OTP préfixe du nom du feed. La règle « retirer le premier segment s'il y a
    au moins deux `:` » marchait pour Tisséo et le TER, et **échouait** pour le
    car liO, dont le `route_id` ne contient aucun `:` : `lio:305` traversait
    intact et ne correspondait à rien — ni dans la table des tracés, ni dans
    `ROUTE_VEHICLE_MAP` côté GAMA."""

    @pytest.fixture
    def catalogue(self, monde):
        return GTFSData.from_gtfs_files(str(monde["primaire"]))

    def test_le_car_lio_est_reconnu(self, catalogue):
        catalogue.route_id_map["305"] = {"route_short_name": "305",
                                         "route_long_name": "Car 305",
                                         "route_type": "Bus"}
        assert catalogue.resoudre_route_id("lio:305") == "305"

    def test_le_bus_tisseo_est_reconnu(self, catalogue):
        assert catalogue.resoudre_route_id("tisseo:line:8") == "line:8"

    def test_le_ter_est_reconnu(self, catalogue):
        assert catalogue.resoudre_route_id(f"ter:{ROUTE_TER}") == ROUTE_TER

    def test_un_identifiant_deja_propre_est_rendu_tel_quel(self, catalogue):
        assert catalogue.resoudre_route_id("line:8") == "line:8"

    def test_un_identifiant_inconnu_garde_l_ancien_comportement(self, catalogue):
        assert catalogue.resoudre_route_id("feed:jamais:vu") == "jamais:vu"
