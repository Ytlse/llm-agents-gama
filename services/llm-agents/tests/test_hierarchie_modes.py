"""Ticket 022 — le mode principal suit l'enquête, et le mode de véhicule reste à part.

Deux invariants, dont la violation ne lève aucune exception :

1. **Le journal suit la hiérarchie de l'enquête.** `move_logger._plan_transport_mode`
   testait la voiture EN PREMIER, alors qu'elle est au rang 19 de l'annexe publiée
   (rapport AUAT/CEREMA p. 53), sous les rangs 1 à 13 du collectif. L'enquête code 760
   de ses 770 déplacements mixtes voiture + TC en « transports collectifs ».

2. **Un mode principal n'est pas un mode de véhicule.** La chaîne de véhicules du
   ticket 008 demande « où est la voiture », pas « quel est le mode principal ». Confondre
   les deux, c'est faire disparaître la voiture d'un rabattement du verrou de retour.
   `_primary_mode` et `_vehicle_mode` doivent donc DIVERGER sur un plan mixte, et c'est
   ce que ce fichier fixe.

Lancement : cd llm-agents && .venv/bin/python -m pytest tests/test_hierarchie_modes.py
"""

import pytest

from models import Location, TransitLocation, Transit, TravelPlan
from urban_mobility_agents.simulation_controller import _primary_mode, _vehicle_mode
from urban_mobility_agents.utils.move_logger import (_BUS_MODES, _CANONICAL_FR,
                                                     _CAR_MODES, _RAIL_MODES,
                                                     _plan_transport_mode)


def _jambe(mode: str, is_transfer: bool = False) -> Transit:
    depart = TransitLocation(stop=f"{mode}-A", lat=43.5, lon=1.4)
    arrivee = TransitLocation(stop=f"{mode}-B", lat=43.6, lon=1.45)
    return Transit(
        start_time=0, end_time=600_000, start_location=depart, end_location=arrivee,
        is_transfer=is_transfer, transit_route="X", shape_id=None, duration=600,
        distance=5_000.0, mode=mode)


def _plan(*modes: str) -> TravelPlan:
    jambes = [_jambe(m) for m in modes]
    return TravelPlan(id="-".join(modes) or "vide", start_location=Location(lat=43.5, lon=1.4),
                      end_location=Location(lat=43.6, lon=1.45), start_time=0,
                      end_time=600_000, legs=jambes)


# ── 1. Le journal suit la hiérarchie ─────────────────────────────────────────

@pytest.mark.parametrize("modes,attendu", [
    (("bus",), "Transports_collectifs"),
    (("rail",), "Train"),
    (("car",), "Voiture Privée"),
    (("bicycle",), "Vélo"),
    (("foot",), "Marche"),
    (("school_bus",), "Transports_collectifs"),
    # Les deux crans qui comptent, et le sens dans lequel ils tranchent.
    (("bus", "rail"), "Transports_collectifs"),     # bus rang 4 < TER rang 8
    (("metro", "rail"), "Transports_collectifs"),   # métro rang 1
    (("car", "bus"), "Transports_collectifs"),      # voiture rang 19, sous tout le collectif
    (("car", "rail"), "Train"),
    (("car", "bicycle"), "Voiture Privée"),         # voiture rang 19 < vélo rang 23
    (("bicycle", "bus"), "Transports_collectifs"),
])
def test_le_libelle_du_journal_suit_l_ordre_de_l_enquete(modes, attendu):
    assert _plan_transport_mode(_plan(*modes)) == attendu


def test_les_jambes_de_transfert_ne_comptent_pas():
    """Une correspondance à pied n'est pas un déplacement à pied (jambes terminales, T13)."""
    plan = TravelPlan(id="transferts", start_location=Location(lat=43.5, lon=1.4),
                      end_location=Location(lat=43.6, lon=1.45), start_time=0,
                      end_time=600_000,
                      legs=[_jambe("foot", is_transfer=True), _jambe("bus"),
                            _jambe("foot", is_transfer=True)])
    assert _plan_transport_mode(plan) == "Transports_collectifs"


def test_un_plan_sans_jambe_est_de_la_marche():
    """Rang 36 de l'annexe : « Marche à pied UNIQUEMENT », et c'est mesuré."""
    assert _plan_transport_mode(_plan()) == "Marche"
    assert _primary_mode(_plan()) == "walk"


def test_un_mode_inconnu_leve_une_alarme_sur_front_montant(caplog):
    """Un mode hors hiérarchie tombe dans « Autres modes », qui est EXCLU du scoring.

    Sans alarme, sa masse disparaît d'une part modale sans rien casser — le mécanisme
    exact des défauts du Téléo et du TER. Une seule ligne par jeu de modes.
    """
    import logging

    from urban_mobility_agents.utils import move_logger

    move_logger._UNKNOWN_MODES_SEEN.clear()
    with caplog.at_level(logging.ERROR, logger=move_logger.__name__):
        assert _plan_transport_mode(_plan("hovercraft")) == "Autres modes"
        assert _plan_transport_mode(_plan("hovercraft")) == "Autres modes"
    alarmes = [r for r in caplog.records if "[ALARME]" in r.getMessage()]
    assert len(alarmes) == 1, [r.getMessage() for r in alarmes]
    assert "hovercraft" in alarmes[0].getMessage()
    move_logger._UNKNOWN_MODES_SEEN.clear()


def test_les_listes_du_journal_ne_sont_plus_ecrites_a_la_main():
    """Elles sont des VUES de la hiérarchie gelée : cinq littéraux ne peuvent plus dériver."""
    assert {"bus", "metro", "tram", "cableway", "school_bus"} <= _BUS_MODES
    assert _RAIL_MODES == frozenset({"rail"})
    assert _CAR_MODES == frozenset({"car", "__car__"})
    # Les colonnes P(...) gardent leur ordre d'affichage (les `moves.csv` archivés
    # doivent rester comparables), mais leurs libellés viennent de la hiérarchie.
    assert list(_CANONICAL_FR) == ["walking", "cycling", "car", "public_transport",
                                   "train", "motorbike", "other"]
    assert _CANONICAL_FR["train"] == "Train"
    assert _CANONICAL_FR["public_transport"] == "Transports_collectifs"


# ── 2. Mode principal ≠ mode de véhicule ─────────────────────────────────────

def test_la_metrique_agrege_dans_les_quatre_categories_de_l_enquete():
    """`trip_mode_by_purpose_total` compte en marche / vélo / voiture / TC.

    Le train est DANS les transports en commun : l'annexe p. 53 range les rangs 1 à 13
    sous ce libellé. Fondre `rail` dans `transit` est donc correct ici — ce n'est pas
    l'oubli d'un mode, c'est l'agrégation publiée.
    """
    assert _primary_mode(_plan("rail")) == "transit"
    assert _primary_mode(_plan("bus", "rail")) == "transit"
    assert _primary_mode(_plan("car")) == "car"
    assert _primary_mode(_plan("bicycle")) == "bike"
    assert _primary_mode(_plan("foot")) == "walk"


def test_un_mode_inconnu_nest_plus_compte_en_transports_collectifs():
    """`transit` était le DÉFAUT de la cascade : un mode inconnu gonflait la part TC."""
    assert _primary_mode(_plan("hovercraft")) == "other"


def test_le_mode_de_vehicule_repond_a_une_autre_question():
    """Sur un plan mixte voiture + bus, les deux lectures divergent — et c'est voulu.

    L'enquête classe ce déplacement en transports collectifs (rabattement), donc
    `_primary_mode` dit « transit ». Mais la voiture a bien été prise et doit être garée
    à destination, donc `_vehicle_mode` dit « car ». Confondre les deux ferait perdre la
    voiture au verrou de retour (ticket 008).
    """
    mixte = _plan("car", "bus")
    assert _primary_mode(mixte) == "transit"
    assert _vehicle_mode(mixte) == "car"
    # Sur les plans non mixtes — les seuls qu'OTP produise aujourd'hui — elles s'accordent.
    for mode, attendu in (("car", "car"), ("bicycle", "bike"), ("foot", "walk")):
        assert _vehicle_mode(_plan(mode)) == attendu
        assert _primary_mode(_plan(mode)) == attendu
    assert _vehicle_mode(_plan("bus")) == "transit"
