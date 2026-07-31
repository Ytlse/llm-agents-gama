"""Tests de la cohérence de chaîne des véhicules personnels (vélo ET voiture).

Un véhicule est un **lieu** : il reste garé où l'agent l'a laissé. Trois règles,
identiques pour le vélo et la voiture :

1. **verrou de sortie** — le mode n'est proposé que si le véhicule est au point de départ ;
2. **stationnement** — après le choix, le véhicule suit l'agent s'il l'a utilisé, sinon il reste ;
3. **verrou de retour** — un trajet vers le domicile au départ d'un lieu où un véhicule
   est garé est restreint à ce mode (l'agent ramène son véhicule).

Contrairement à `urban_mobility_agents/agents/tests/test_personal_bike.py` (qui
recopie la logique faute de sys.path), ces tests importent les fonctions réelles du
contrôleur — le conftest de ce dossier met le dépôt et `llm-agents/` sur le path.

Lancement : cd llm-agents && .venv/bin/python -m pytest tests/test_vehicle_chain.py
"""

import pytest

from models import (
    Activity,
    Location,
    Person,
    PersonalIdentity,
    PersonState,
    Transit,
    TransitLocation,
    TravelPlan,
)
from urban_mobility_agents.simulation_controller import (
    _orphaned_vehicles,
    _owns_bike,
    _owns_car,
    _park_vehicles,
    _primary_mode,
    _same_place,
    _vehicle_available,
    _vehicle_position,
    _vehicles_parked_at,
)

HOME = Location(lat=43.6000, lon=1.4400)
WORK = Location(lat=43.6100, lon=1.4500)
GYM = Location(lat=43.6200, lon=1.4600)


def _plan(*modes: str, start: Location = HOME, end: Location = WORK) -> TravelPlan:
    """Plan à un tronçon par mode ; les tronçons `foot` d'un plan TC sont des transferts."""
    loc = TransitLocation(stop="", lat=start.lat, lon=start.lon)
    legs = [
        Transit(
            start_time=0, end_time=600, duration=600, distance=1000.0, mode=mode,
            start_location=loc, end_location=loc,
            is_transfer=(mode == "foot" and len(modes) > 1),
        )
        for mode in modes
    ]
    return TravelPlan(
        id="p", start_location=start, end_location=end,
        start_time=0, end_time=600, legs=legs,
    )


def _person(**traits) -> Person:
    """Agent au domicile, véhicules garés au domicile (dict d'état vide)."""
    base = {"personal_bike": "vélo normal", "number_of_cars": 1}
    base.update(traits)
    return Person(
        person_id="p1",
        identity=PersonalIdentity(name="Test", traits_json=base, home=HOME),
        state=PersonState(),
    )


# ── Possession (comportement historique, inchangé pour le vélo) ───────────────

class TestPossession:
    def test_pas_de_velo(self):
        assert _owns_bike({"personal_bike": "Pas de vélo"}) is False

    def test_casse_indifferente(self):
        assert _owns_bike({"personal_bike": "PAS DE VÉLO"}) is False

    def test_velo_normal(self):
        assert _owns_bike({"personal_bike": "vélo normal"}) is True

    def test_vae(self):
        assert _owns_bike({"personal_bike": "VAE"}) is True

    def test_velo_champ_absent_defaut_true(self):
        """Rétrocompatibilité : populations sans le champ → vélo autorisé."""
        assert _owns_bike({}) is True

    def test_voiture_selon_number_of_cars(self):
        assert _owns_car({"number_of_cars": 1}) is True
        assert _owns_car({"number_of_cars": 2}) is True
        assert _owns_car({"number_of_cars": 0}) is False

    def test_voiture_champ_absent_defaut_false(self):
        """Inverse du vélo : sans donnée, pas de voiture (c'est le champ eqasim de référence)."""
        assert _owns_car({}) is False

    def test_voiture_champ_null(self):
        assert _owns_car({"number_of_cars": None}) is False


# ── Position initiale : clé absente ⇒ domicile ────────────────────────────────

class TestPositionInitiale:
    def test_etat_par_defaut_vide(self):
        assert PersonState().planning_vehicle_at == {}

    @pytest.mark.parametrize("mode", ["bike", "car"])
    def test_vehicule_au_domicile_par_defaut(self, mode):
        assert _vehicle_position(_person(), mode) == HOME

    @pytest.mark.parametrize("mode", ["bike", "car"])
    def test_position_memorisee_prime(self, mode):
        person = _person()
        person.state.planning_vehicle_at[mode] = WORK
        assert _vehicle_position(person, mode) == WORK


# ── Règle 1 : verrou de sortie ────────────────────────────────────────────────

class TestVerrouDeSortie:
    @pytest.mark.parametrize("mode", ["bike", "car"])
    def test_disponible_au_point_de_depart(self, mode):
        assert _vehicle_available(_person(), mode, HOME) is True

    @pytest.mark.parametrize("mode", ["bike", "car"])
    def test_indisponible_gare_ailleurs(self, mode):
        """Le cœur du correctif : possession sans présence ⇒ pas d'option."""
        person = _person()
        person.state.planning_vehicle_at[mode] = WORK
        assert _vehicle_available(person, mode, HOME) is False
        assert _vehicle_available(person, mode, WORK) is True

    def test_velo_non_possede_meme_au_domicile(self):
        assert _vehicle_available(_person(personal_bike="Pas de vélo"), "bike", HOME) is False

    def test_voiture_non_possedee_meme_au_domicile(self):
        assert _vehicle_available(_person(number_of_cars=0), "car", HOME) is False

    @pytest.mark.parametrize("mode", ["bike", "car"])
    def test_domicile_inconnu_degrade_vers_possession(self, mode):
        """Sans domicile, on ne sait pas où est le véhicule : ancien comportement."""
        person = _person()
        person.identity.home = None
        assert _vehicle_available(person, mode, WORK) is True

    @pytest.mark.parametrize("mode", ["bike", "car"])
    def test_origine_inconnue_bloque(self, mode):
        assert _vehicle_available(_person(), mode, None) is False


# ── Règle 2 : stationnement après le trajet ───────────────────────────────────

class TestStationnement:
    def test_trajet_a_velo_le_velo_suit(self):
        person = _person()
        _park_vehicles(person, _plan("bicycle"), HOME, WORK)
        assert _vehicle_position(person, "bike") == WORK
        assert _vehicle_position(person, "car") == HOME  # la voiture n'a pas bougé

    def test_trajet_en_voiture_la_voiture_suit(self):
        person = _person()
        _park_vehicles(person, _plan("car"), HOME, WORK)
        assert _vehicle_position(person, "car") == WORK
        assert _vehicle_position(person, "bike") == HOME

    def test_trajet_en_bus_rien_ne_bouge(self):
        person = _person()
        _park_vehicles(person, _plan("foot", "bus", "foot"), HOME, WORK)
        assert person.state.planning_vehicle_at == {}

    def test_retour_au_domicile_libere_la_cle(self):
        """Invariant « clé absente ⇒ domicile » : le retour purge l'entrée."""
        person = _person()
        _park_vehicles(person, _plan("car"), HOME, WORK)
        _park_vehicles(person, _plan("car", start=WORK, end=HOME), WORK, HOME)
        assert person.state.planning_vehicle_at == {}
        assert _vehicle_position(person, "car") == HOME

    def test_plus_de_retour_implicite_au_domicile(self):
        """Régression : rentrer en bus ne fait plus réapparaître le vélo au domicile."""
        person = _person()
        _park_vehicles(person, _plan("bicycle"), HOME, WORK)
        _park_vehicles(person, _plan("foot", "bus", "foot", start=WORK, end=HOME), WORK, HOME)
        assert _vehicle_position(person, "bike") == WORK
        assert _vehicle_available(person, "bike", HOME) is False

    def test_plan_absent_rien_ne_bouge(self):
        person = _person()
        _park_vehicles(person, None, HOME, WORK)
        assert person.state.planning_vehicle_at == {}

    def test_plan_vide_compte_comme_marche(self):
        person = _person()
        assert _primary_mode(_plan()) == "walk"
        _park_vehicles(person, _plan(), HOME, WORK)
        assert person.state.planning_vehicle_at == {}

    def test_vehicule_absent_du_depart_ne_se_teleporte_pas(self):
        """Défense en profondeur : un plan voiture au départ d'un lieu sans voiture."""
        person = _person()
        person.state.planning_vehicle_at["car"] = GYM
        _park_vehicles(person, _plan("car", start=HOME, end=WORK), HOME, WORK)
        assert _vehicle_position(person, "car") == GYM


# ── Règle 3 : verrou de retour ────────────────────────────────────────────────

class TestVerrouDeRetour:
    def test_vehicule_gare_ici_doit_etre_ramene(self):
        person = _person()
        person.state.planning_vehicle_at["car"] = WORK
        assert _vehicles_parked_at(person, WORK) == {"car"}

    def test_les_deux_vehicules_gares_ici(self):
        person = _person()
        person.state.planning_vehicle_at["car"] = WORK
        person.state.planning_vehicle_at["bike"] = WORK
        assert _vehicles_parked_at(person, WORK) == {"bike", "car"}

    def test_vehicule_gare_ailleurs_non_concerne(self):
        person = _person()
        person.state.planning_vehicle_at["car"] = GYM
        assert _vehicles_parked_at(person, WORK) == set()

    def test_depart_du_domicile_rien_a_ramener(self):
        """Les véhicules au domicile n'ont rien à ramener : pas de verrou au départ."""
        assert _vehicles_parked_at(_person(), HOME) == set()

    def test_non_possede_jamais_a_ramener(self):
        person = _person(personal_bike="Pas de vélo", number_of_cars=0)
        person.state.planning_vehicle_at["bike"] = WORK
        assert _vehicles_parked_at(person, WORK) == set()


# ── Orphelins : véhicule laissé à une étape intermédiaire ─────────────────────

class TestOrphelins:
    def test_aucun_orphelin_au_depart(self):
        assert _orphaned_vehicles(_person()) == set()

    def test_voiture_restee_au_travail(self):
        person = _person()
        person.state.planning_vehicle_at["car"] = WORK
        assert _orphaned_vehicles(person) == {"car"}

    def test_non_possede_jamais_orphelin(self):
        person = _person(number_of_cars=0)
        person.state.planning_vehicle_at["car"] = WORK
        assert _orphaned_vehicles(person) == set()


# ── Comparaison de position ───────────────────────────────────────────────────

class TestSamePlace:
    def test_identique(self):
        assert _same_place(HOME, Location(lat=43.6, lon=1.44)) is True

    def test_arrondi_de_serialisation_tolere(self):
        assert _same_place(HOME, Location(lat=43.6000001, lon=1.4400001)) is True

    def test_lieux_distincts(self):
        assert _same_place(HOME, WORK) is False

    def test_none(self):
        assert _same_place(None, HOME) is False
        assert _same_place(HOME, None) is False


# ── Chaînes de journée complètes ──────────────────────────────────────────────

class TestChaineJournee:
    def test_bus_aller_puis_plus_de_vehicule_au_bureau(self):
        """domicile → travail en bus : ni vélo ni voiture disponibles au bureau."""
        person = _person()
        _park_vehicles(person, _plan("foot", "bus", "foot"), HOME, WORK)
        assert _vehicle_available(person, "bike", WORK) is False
        assert _vehicle_available(person, "car", WORK) is False

    def test_voiture_aller_voiture_disponible_toute_la_chaine(self):
        person = _person()
        _park_vehicles(person, _plan("car"), HOME, WORK)
        assert _vehicle_available(person, "car", WORK) is True
        _park_vehicles(person, _plan("car", start=WORK, end=GYM), WORK, GYM)
        assert _vehicle_available(person, "car", GYM) is True
        # …mais le vélo est resté au domicile pendant tout ce temps.
        assert _vehicle_available(person, "bike", GYM) is False

    def test_voiture_au_travail_velo_au_domicile_sont_exclusifs(self):
        """L'agent ne peut pas conduire depuis le bureau ET pédaler depuis chez lui."""
        person = _person()
        _park_vehicles(person, _plan("car"), HOME, WORK)
        assert _vehicle_available(person, "car", HOME) is False
        assert _vehicle_available(person, "bike", WORK) is False

    def test_boucle_complete_remet_tout_au_domicile(self):
        person = _person()
        _park_vehicles(person, _plan("bicycle"), HOME, WORK)
        assert _vehicles_parked_at(person, WORK) == {"bike"}  # verrou de retour actif
        _park_vehicles(person, _plan("bicycle", start=WORK, end=HOME), WORK, HOME)
        assert _orphaned_vehicles(person) == set()
        assert _vehicle_available(person, "bike", HOME) is True
        assert _vehicle_available(person, "car", HOME) is True

    def test_etape_intermediaire_orpheline_la_voiture(self):
        """domicile → travail en voiture, travail → sport à pied, sport → domicile en bus."""
        person = _person()
        _park_vehicles(person, _plan("car"), HOME, WORK)
        _park_vehicles(person, _plan("foot", start=WORK, end=GYM), WORK, GYM)
        assert _vehicles_parked_at(person, GYM) == set()  # pas de verrou : rien de garé ici
        _park_vehicles(person, _plan("foot", "bus", "foot", start=GYM, end=HOME), GYM, HOME)
        assert _orphaned_vehicles(person) == {"car"}  # cas résiduel, rattrapé au domicile


# ── Rattrapage au domicile (méthode du contrôleur) ────────────────────────────

class TestSettleVehiclesAtHome:
    def _fresh(self):
        """Instance minimale : on n'appelle que _settle_vehicles_at_home, sans I/O."""
        from urban_mobility_agents.simulation_controller import SimulationLoopV1
        ctrl = SimulationLoopV1.__new__(SimulationLoopV1)
        ctrl._vehicle_home_returns = 0
        ctrl._vehicle_orphan_returns = 0
        ctrl._vehicle_orphan_alarm_on = False
        return ctrl

    @staticmethod
    def _act(purpose: str) -> Activity:
        return Activity(id="a", start_time=0, end_time=3600, purpose=purpose, location=HOME)

    def test_activite_non_domicile_ignoree(self):
        ctrl, person = self._fresh(), _person()
        person.state.planning_vehicle_at["car"] = WORK
        ctrl._settle_vehicles_at_home(person, self._act("work"))
        assert ctrl._vehicle_home_returns == 0
        assert _vehicle_position(person, "car") == WORK

    def test_retour_sans_orphelin(self):
        ctrl, person = self._fresh(), _person()
        ctrl._settle_vehicles_at_home(person, self._act("home"))
        assert (ctrl._vehicle_home_returns, ctrl._vehicle_orphan_returns) == (1, 0)

    def test_orphelin_ramene_au_domicile(self):
        ctrl, person = self._fresh(), _person()
        person.state.planning_vehicle_at["car"] = WORK
        ctrl._settle_vehicles_at_home(person, self._act("home"))
        assert (ctrl._vehicle_home_returns, ctrl._vehicle_orphan_returns) == (1, 1)
        assert person.state.planning_vehicle_at == {}
        assert _vehicle_available(person, "car", HOME) is True

    def test_purpose_casse_indifferente(self):
        ctrl, person = self._fresh(), _person()
        ctrl._settle_vehicles_at_home(person, self._act("HOME"))
        assert ctrl._vehicle_home_returns == 1
