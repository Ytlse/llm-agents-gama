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
    RETURN_LOCK_MIN_DISTANCE_KM,
    _can_drive,
    _is_car_passenger,
    _orphaned_vehicles,
    _owns_bike,
    _owns_car,
    _park_vehicles,
    _primary_mode,
    _road_distance_km,
    _same_place,
    _vehicle_available,
    _vehicle_position,
    _vehicles_parked_at,
)

HOME = Location(lat=43.6000, lon=1.4400)
WORK = Location(lat=43.6100, lon=1.4500)
GYM = Location(lat=43.6200, lon=1.4600)
# ~250 m du domicile à vol d'oiseau : sous le seuil du verrou de retour (A3), même
# après le facteur de détour 1,3.
SHOP = Location(lat=43.6020, lon=1.4415)


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
    """Agent au domicile, véhicules garés au domicile (dict d'état vide).

    Par défaut : **adulte titulaire du permis, vivant seul**. Depuis le mode
    passager (ticket 008, A2), conduire suppose l'âge et le permis — un persona
    muet sur ces deux traits ne se verrait plus jamais proposer la voiture, et les
    tests des trois règles porteraient sur un agent incapable de conduire. Vivant
    seul, il n'est pas non plus passager : les cas passager sont explicites.
    """
    base = {"personal_bike": "vélo normal", "number_of_cars": 1,
            "has_driving_license": True, "age": 40, "household_size": 1}
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


# ── Mode passager : l'enfant va à l'école en voiture (ticket 008, A2) ─────────

def _child(**traits) -> Person:
    """Enfant de 12 ans, foyer de 4 personnes avec 3 voitures — passager type."""
    base = {"age": 12, "has_driving_license": False, "household_size": 4,
            "number_of_cars": 3}
    base.update(traits)
    return _person(**base)


class TestPeutConduire:
    def test_adulte_avec_permis(self):
        assert _can_drive({"age": 40, "has_driving_license": True}) is True

    def test_mineur_meme_avec_permis(self):
        """Verrou dur : une population mal générée distribue des permis à des
        enfants de neuf ans (ticket 008, A1). L'âge tranche."""
        assert _can_drive({"age": 12, "has_driving_license": True}) is False

    def test_adulte_sans_permis(self):
        assert _can_drive({"age": 40, "has_driving_license": False}) is False

    def test_traits_muets(self):
        assert _can_drive({}) is False


class TestPassager:
    def test_enfant_du_foyer_motorise(self):
        assert _is_car_passenger(_child()) is True

    def test_enfant_sans_voiture_au_foyer(self):
        assert _is_car_passenger(_child(number_of_cars=0)) is False

    def test_adulte_sans_permis_vivant_seul(self):
        """Personne pour l'emmener : ce n'est pas un passager."""
        p = _person(age=40, has_driving_license=False, household_size=1)
        assert _is_car_passenger(p) is False

    def test_adulte_sans_permis_en_famille(self):
        p = _person(age=40, has_driving_license=False, household_size=3)
        assert _is_car_passenger(p) is True

    def test_conducteur_n_est_pas_passager(self):
        assert _is_car_passenger(_person(household_size=4)) is False

    def test_voiture_proposee_sans_test_de_position(self):
        """Ce n'est pas sa voiture : peu importe où le foyer l'a laissée."""
        child = _child()
        child.state.planning_vehicle_at["car"] = GYM
        assert _vehicle_available(child, "car", HOME) is True
        assert _vehicle_available(child, "car", WORK) is True

    def test_non_conducteur_non_passager_jamais_de_voiture(self):
        """Le verrou dur : plus aucun mineur ni sans-permis ne conduit."""
        seul = _person(age=40, has_driving_license=False, household_size=1)
        assert _vehicle_available(seul, "car", HOME) is False
        enfant_sans_voiture = _child(number_of_cars=0)
        assert _vehicle_available(enfant_sans_voiture, "car", HOME) is False

    def test_le_velo_reste_ouvert_aux_mineurs(self):
        """Le permis ne conditionne que la voiture."""
        assert _vehicle_available(_child(), "bike", HOME) is True

    def test_la_voiture_ne_se_gare_pas_a_destination(self):
        """Un tiers conduit et repart : la voiture ne dort pas à l'école."""
        child = _child()
        _park_vehicles(child, _plan("car", start=HOME, end=WORK), HOME, WORK)
        assert child.state.planning_vehicle_at == {}
        assert _vehicle_position(child, "car") == HOME

    def test_pas_de_retour_force_pour_le_passager(self):
        """Le point le plus facile à casser : l'enfant déposé à l'école ne doit
        pas être sommé de ramener la voiture. Rien n'y étant garé, il n'y a rien
        à ramener — c'est la conséquence directe du test précédent."""
        child = _child()
        _park_vehicles(child, _plan("car", start=HOME, end=WORK), HOME, WORK)
        assert _vehicles_parked_at(child, WORK) == set()
        assert _orphaned_vehicles(child) == set()

    def test_le_conducteur_ne_change_pas_de_comportement(self):
        """Non-régression : pour un adulte avec permis, les trois règles sont
        strictement celles d'avant le mode passager."""
        adulte = _person(household_size=4, number_of_cars=3)
        assert _vehicle_available(adulte, "car", HOME) is True
        _park_vehicles(adulte, _plan("car"), HOME, WORK)
        assert _vehicle_position(adulte, "car") == WORK
        assert _vehicle_available(adulte, "car", HOME) is False
        assert _vehicles_parked_at(adulte, WORK) == {"car"}

    def test_velo_du_passager_suit_normalement(self):
        """Seule la voiture est concernée : son vélo, lui, reste où il le laisse."""
        child = _child()
        _park_vehicles(child, _plan("bicycle"), HOME, WORK)
        assert _vehicle_position(child, "bike") == WORK
        assert _vehicles_parked_at(child, WORK) == {"bike"}


# ── Seuil de distance du verrou de retour (ticket 008, A3) ────────────────────

class TestSeuilRetourCourt:
    def test_distance_routiere_facteur_de_detour(self):
        """Vol d'oiseau × 1,3, la convention de `_estimate_fallback_duration`."""
        assert _road_distance_km(HOME, HOME) == 0.0
        assert _road_distance_km(HOME, None) is None
        assert 0.2 < _road_distance_km(HOME, SHOP) < RETURN_LOCK_MIN_DISTANCE_KM

    def test_trajet_long_au_dessus_du_seuil(self):
        assert _road_distance_km(HOME, WORK) > RETURN_LOCK_MIN_DISTANCE_KM

    def test_le_verrou_reste_pertinent_au_dela_du_seuil(self):
        """Le seuil ne désarme pas la règle 3 : au-delà, le véhicule est à ramener."""
        person = _person()
        person.state.planning_vehicle_at["car"] = WORK
        assert _vehicles_parked_at(person, WORK) == {"car"}
        assert _road_distance_km(WORK, HOME) > RETURN_LOCK_MIN_DISTANCE_KM


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
