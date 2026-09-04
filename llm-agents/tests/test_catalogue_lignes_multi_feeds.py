"""Le catalogue des lignes réunit les trois réseaux en service, ou il le dit.

Le lecteur GTFS ne charge qu'un feed (Tisséo) alors que le graphe OTP en porte trois depuis le
2026-09-04. Un identifiant de ligne liO ou TER ne se trouvait donc dans aucune table, et le
prompt de l'agent lisait « Trajet en Unknown 392 » pour les 319 lignes des deux réseaux
régionaux — le mode et le numéro perdus.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from inputs.gtfs import reader as reader_module  # noqa: E402
from inputs.gtfs.reader import GTFSData  # noqa: E402


def _ecrire_feed(dossier: Path, routes: list[dict], avec_stops: bool = True) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(routes).to_csv(dossier / "routes.txt", index=False)
    if avec_stops:
        pd.DataFrame([{"stop_id": "s1", "stop_name": "A", "stop_lat": 43.6, "stop_lon": 1.44}]
                     ).to_csv(dossier / "stops.txt", index=False)
    return dossier


def _gtfs_primaire(routes: list[dict]) -> GTFSData:
    """Un GTFSData minimal dont seule la table des lignes compte pour ces tests."""
    vide = pd.DataFrame()
    g = GTFSData.__new__(GTFSData)
    g.routes = pd.DataFrame(routes)
    g.trips = vide
    g.stop_times = vide
    g.stops = vide
    g.shapes = vide
    g.calendar = vide
    g.calendar_dates = vide
    return g


@pytest.fixture
def trois_feeds(tmp_path, monkeypatch):
    racine = tmp_path / "gtfs"
    primaire = _ecrire_feed(racine / "tisseo_gtfs", [
        {"route_id": "T1", "route_short_name": "1", "route_long_name": "Bus 1", "route_type": "3"},
    ])
    _ecrire_feed(racine / "lio_gtfs", [
        {"route_id": "L392", "route_short_name": "392", "route_long_name": "Car 392", "route_type": "3"},
        {"route_id": "L1", "route_short_name": "1", "route_long_name": "Car 1 (nom court déjà pris)", "route_type": "3"},
    ])
    _ecrire_feed(racine / "ter_gtfs", [
        {"route_id": "R_K1", "route_short_name": "K1", "route_long_name": "Matabiau — Brive", "route_type": "2"},
    ])
    monkeypatch.setattr(reader_module.settings.gtfs, "gtfs_file", str(primaire), raising=False)
    return primaire


def test_les_lignes_des_autres_feeds_entrent_avec_leur_mode(trois_feeds):
    g = _gtfs_primaire([{"route_id": "T1", "route_short_name": "1",
                         "route_long_name": "Bus 1", "route_type": "3"}])
    g.init_route_lookup_maps()
    # Le car régional et le train sont nommés, et leur mode est celui de la table des modalités.
    assert g.route_id_map["L392"]["route_short_name"] == "392"
    assert g.route_id_map["L392"]["route_type"] == "Bus"
    assert g.route_id_map["R_K1"]["route_short_name"] == "K1"
    assert g.route_id_map["R_K1"]["route_type"] == "Train"
    # Plus aucun « Unknown » : c'était le défaut à fermer.
    assert all(v["route_type"] != "Unknown" for v in g.route_id_map.values())


def test_un_nom_court_deja_pris_reste_au_feed_primaire(trois_feeds):
    g = _gtfs_primaire([{"route_id": "T1", "route_short_name": "1",
                         "route_long_name": "Bus 1", "route_type": "3"}])
    g.init_route_lookup_maps()
    # « 1 » existe dans les deux réseaux : le feed primaire garde le nom court, et la ligne
    # régionale reste joignable par son identifiant.
    assert g.route_name_id_map["1"] == "T1"
    assert "L1" in g.route_id_map


def test_un_identifiant_revendique_deux_fois_s_alarme(tmp_path, monkeypatch, caplog):
    racine = tmp_path / "gtfs"
    primaire = _ecrire_feed(racine / "tisseo_gtfs", [
        {"route_id": "DOUBLON", "route_short_name": "1", "route_long_name": "Bus 1", "route_type": "3"},
    ])
    _ecrire_feed(racine / "autre_gtfs", [
        {"route_id": "DOUBLON", "route_short_name": "9", "route_long_name": "Autre", "route_type": "2"},
    ])
    monkeypatch.setattr(reader_module.settings.gtfs, "gtfs_file", str(primaire), raising=False)
    g = _gtfs_primaire([{"route_id": "DOUBLON", "route_short_name": "1",
                         "route_long_name": "Bus 1", "route_type": "3"}])
    journal = g.init_route_lookup_maps()
    assert journal["collisions_identifiant"] == 1
    # Le feed primaire gagne : le mode affiché reste le sien, pas celui de l'intrus.
    assert g.route_id_map["DOUBLON"]["route_type"] == "Bus"


def test_un_feed_sans_catalogue_de_lignes_n_est_pas_une_erreur(tmp_path, monkeypatch):
    racine = tmp_path / "gtfs"
    primaire = _ecrire_feed(racine / "tisseo_gtfs", [
        {"route_id": "T1", "route_short_name": "1", "route_long_name": "Bus 1", "route_type": "3"},
    ])
    sans_routes = racine / "arrets_seuls"
    sans_routes.mkdir()
    pd.DataFrame([{"stop_id": "s9", "stop_name": "B", "stop_lat": 43.7, "stop_lon": 1.5}]
                 ).to_csv(sans_routes / "stops.txt", index=False)
    monkeypatch.setattr(reader_module.settings.gtfs, "gtfs_file", str(primaire), raising=False)
    g = _gtfs_primaire([{"route_id": "T1", "route_short_name": "1",
                         "route_long_name": "Bus 1", "route_type": "3"}])
    journal = g.init_route_lookup_maps()
    assert journal["lignes_ajoutees"] == 0
    assert g.route_id_map["T1"]["route_short_name"] == "1"
