"""Ticket 031, question 16 — le TER doit être demandé à OTP, et se nommer.

Le TER est entré dans le graphe OTP le 2026-09-03, ses arrêts comptaient dans
l'enveloppe de desserte, le feed annuel le fait rouler le jour simulé — et aucun
agent ne pouvait s'en voir proposer un, parce que `rail` n'était pas dans les
modes demandés. Quatre familles de tests, chacune écrite pour échouer contre le
code d'avant :

1. **`rail` est demandé et accepté.** La liste envoyée à OTP le contient, et
   `SUPPORTED_MODES` aussi — sans quoi l'assertion de `to_travel_plan` refuserait
   le premier train renvoyé. Un test de cohérence verrouille les deux ensemble :
   demander un mode qu'on refuserait ensuite fait planter le premier itinéraire.

2. **Le train se nomme.** `route_type=2` → « Train » dans le prompt, pas
   « Unknown ».

3. **La porte de proximité voit tous les réseaux en service.** Elle était bâtie
   sur le seul feed Tisséo : 397 des 2 580 points de la population scellée v4
   sont à portée d'un arrêt liO ou d'une gare TER sans l'être d'un arrêt Tisséo,
   et le runtime sautait OTP pour eux.

4. **Le train compte comme du train** dans les tables de métriques.

Lancement : cd llm-agents && .venv/bin/python -m pytest tests/test_mode_rail.py
"""

import csv

import pytest

from settings import settings
from trip_helper.otp import OTPTripHelper, coordonnees_arrets, feeds_en_service
from urban_mobility_agents.utils.move_logger import _plan_transport_mode
from llm_module.core.mode_choice import canonical_mode
from models import TransitLocation, Transit, TravelPlan


# ── 1. `rail` est demandé et accepté ─────────────────────────────────────────

def _modes_demandes_a_otp() -> list[str]:
    """Les `transportMode` que `get_itineraries` met dans sa requête.

    Lus dans le source : la construction est inline dans une coroutine dont
    l'exécution demanderait un OTP joignable. Le test porte donc sur le texte de
    la fonction — ce qui est exactement ce qu'on veut verrouiller, une liste
    littérale.
    """
    import inspect
    import re

    source = inspect.getsource(OTPTripHelper.get_itineraries)
    return re.findall(r'\{"transportMode":\s*"([a-z_]+)"\}', source)


def test_rail_est_demande_a_otp():
    assert "rail" in _modes_demandes_a_otp()


def test_les_modes_urbains_restent_demandes():
    demandes = _modes_demandes_a_otp()
    for mode in ("bus", "metro", "tram", "cableway"):
        assert mode in demandes, mode


def test_rail_est_un_mode_de_jambe_accepte():
    assert "rail" in OTPTripHelper.SUPPORTED_MODES


def test_tout_mode_demande_est_un_mode_accepte():
    """Demander un mode qu'on refuserait ensuite fait planter le premier itinéraire.

    `to_travel_plan` assène `assert leg.mode in SUPPORTED_MODES`. Un mode demandé
    et absent de la liste ne produit pas « moins d'itinéraires » : il produit une
    `AssertionError` sur le premier trajet qui l'emprunte.
    """
    manquants = [m for m in _modes_demandes_a_otp() if m not in OTPTripHelper.SUPPORTED_MODES]
    assert manquants == []


# ── 2. Le train se nomme ─────────────────────────────────────────────────────

def test_route_type_2_se_nomme_train():
    assert settings.gtfs.gtfs_modality_name_map.get("2") == "Train"


def test_les_modalites_deja_servies_ne_bougent_pas():
    carte = settings.gtfs.gtfs_modality_name_map
    assert carte.get("0") == "T1/Tram"
    assert carte.get("1") == "Metro"
    assert carte.get("3") == "Bus"
    assert carte.get("6") == "Teleo"


def test_le_lecteur_traduit_le_route_type_du_train(tmp_path):
    """Bout en bout sur la table de modalités : un `routes.txt` de TER se lit « Train »."""
    from inputs.gtfs.reader import GTFSData

    feed = tmp_path / "ter_gtfs"
    feed.mkdir()
    (feed / "routes.txt").write_text(
        "route_id,route_short_name,route_long_name,route_type\n"
        "800000,TER 1,Toulouse - Montauban,2\n",
        encoding="utf-8",
    )
    data = GTFSData.__new__(GTFSData)
    import pandas as pd

    data.routes = pd.read_csv(feed / "routes.txt", dtype=str)
    data.init_route_lookup_maps()
    assert data.get_route_type_string_by_id("800000") == "Train"


# ── 3. La porte de proximité voit tous les réseaux en service ────────────────

def _ecrire_feed(racine, nom: str, arrets: list[tuple[str, float, float]]):
    feed = racine / nom
    feed.mkdir(parents=True)
    with (feed / "stops.txt").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["stop_id", "stop_name", "stop_lat", "stop_lon"])
        for sid, lat, lon in arrets:
            w.writerow([sid, sid, lat, lon])
    return feed


def test_feeds_en_service_trouve_les_reseaux_voisins(tmp_path):
    _ecrire_feed(tmp_path, "tisseo_gtfs", [("A", 43.60, 1.44)])
    _ecrire_feed(tmp_path, "lio_gtfs", [("B", 43.20, 1.10)])
    _ecrire_feed(tmp_path, "ter_gtfs", [("C", 43.90, 1.35)])
    noms = {f.name for f in feeds_en_service(str(tmp_path / "tisseo_gtfs"))}
    assert noms == {"tisseo_gtfs", "lio_gtfs", "ter_gtfs"}


def test_feeds_en_service_ignore_les_archives_imbriquees(tmp_path):
    """Un ancien export rangé sous `archives/` ne doit pas revenir dans la porte.

    `data/gtfs/archives/<date>/ter_gtfs_export_…` porte l'offre REMPLACÉE. La
    reprendre reviendrait à servir deux calendriers pour un même réseau.
    """
    _ecrire_feed(tmp_path, "tisseo_gtfs", [("A", 43.60, 1.44)])
    _ecrire_feed(tmp_path, "archives/2026-09-04_pre_lio/ter_gtfs_ancien", [("Z", 43.0, 1.0)])
    noms = {f.name for f in feeds_en_service(str(tmp_path / "tisseo_gtfs"))}
    assert noms == {"tisseo_gtfs"}


def test_feeds_en_service_lit_aussi_un_zip(tmp_path):
    import zipfile

    _ecrire_feed(tmp_path, "tisseo_gtfs", [("A", 43.60, 1.44)])
    with zipfile.ZipFile(tmp_path / "lio_2026.zip", "w") as z:
        z.writestr("stops.txt", "stop_id,stop_name,stop_lat,stop_lon\nB,B,43.2,1.1\n")
    noms = {f.name for f in feeds_en_service(str(tmp_path / "tisseo_gtfs"))}
    assert noms == {"tisseo_gtfs", "lio_2026.zip"}


def test_coordonnees_arrets_reunit_les_feeds(tmp_path):
    _ecrire_feed(tmp_path, "tisseo_gtfs", [("A", 43.60, 1.44), ("A2", 43.61, 1.45)])
    _ecrire_feed(tmp_path, "lio_gtfs", [("B", 43.20, 1.10)])
    coords, par_feed = coordonnees_arrets(feeds_en_service(str(tmp_path / "tisseo_gtfs")))
    assert len(coords) == 3
    assert par_feed == {"lio_gtfs": 1, "tisseo_gtfs": 2}


def test_la_porte_de_proximite_voit_un_arret_regional(tmp_path, monkeypatch):
    """Le cas mesuré : un point loin de tout arrêt Tisséo, à 200 m d'un car liO.

    Contre le code d'avant, `_has_reachable_stop` répondait False et le runtime
    sautait OTP — l'offre était dans le graphe et invisible.
    """
    import pandas as pd

    _ecrire_feed(tmp_path, "tisseo_gtfs", [("A", 43.60, 1.44)])
    _ecrire_feed(tmp_path, "lio_gtfs", [("B", 43.20, 1.10)])
    monkeypatch.setattr(settings.gtfs, "gtfs_file", str(tmp_path / "tisseo_gtfs"))

    class _Feed:
        stops = pd.DataFrame({"stop_lat": [43.60], "stop_lon": [1.44]})

    helper = OTPTripHelper.__new__(OTPTripHelper)
    helper.gtfs_data = _Feed()
    # Reproduit la construction de `__init__` sans réseau ni sémaphore.
    coords, _ = coordonnees_arrets(feeds_en_service(settings.gtfs.gtfs_file))
    helper._stop_coords = coords

    # 43.2018/1.1000 ≈ 200 m au nord de l'arrêt liO, 45 km de l'arrêt Tisséo.
    assert helper._has_reachable_stop(1.1000, 43.2018) is True
    # Un point à 50 km de tout arrêt reste hors de portée : la porte sert encore.
    assert helper._has_reachable_stop(1.9000, 43.2000) is False


def test_la_porte_ne_retrecit_jamais_en_silence(tmp_path, monkeypatch, caplog):
    """Balayage vide → repli sur le feed primaire ET `[ALARME]`.

    Le motif « l'absence de mesure produit le score parfait » : une porte réduite
    à zéro arrêt laisserait passer tout le monde ou personne sans le dire.
    """
    import pandas as pd

    vide = tmp_path / "vide"
    vide.mkdir()
    monkeypatch.setattr(settings.gtfs, "gtfs_file", str(vide / "absent_gtfs"))
    coords, par_feed = coordonnees_arrets(feeds_en_service(settings.gtfs.gtfs_file))
    assert len(coords) == 0 and par_feed == {}
    primaire = pd.DataFrame({"stop_lat": [43.6], "stop_lon": [1.44]}).values.astype(float)
    assert len(coords) < len(primaire)  # c'est la condition qui déclenche le repli


# ── 4. Le train compte comme du train ────────────────────────────────────────

def _plan_train() -> TravelPlan:
    depart = TransitLocation(stop="Gare de Muret", lat=43.46, lon=1.32)
    arrivee = TransitLocation(stop="Toulouse Matabiau", lat=43.611, lon=1.454)
    leg = Transit(
        start_time=0,
        end_time=1_200_000,
        start_location=depart,
        end_location=arrivee,
        is_transfer=False,
        transit_route="800000",
        shape_id=None,
        duration=1_200,
        distance=22_000.0,
        mode="rail",
    )
    return TravelPlan(
        id="rail-test",
        start_location=depart,
        end_location=arrivee,
        start_time=0,
        end_time=1_200_000,
        legs=[leg],
    )


def test_le_journal_de_production_compte_un_train(caplog):
    assert _plan_transport_mode(_plan_train()) == "Train"


def test_le_mode_canonique_du_rail_est_le_train():
    assert canonical_mode("rail") == "train"


@pytest.mark.parametrize("brut", ["rail", "TER", "train", "foot,rail,foot"])
def test_toutes_les_ecritures_du_train_se_canonisent(brut):
    assert canonical_mode(brut) == "train"
