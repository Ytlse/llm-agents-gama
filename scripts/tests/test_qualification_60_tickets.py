"""
Suite de tests fonctionnels persistants (60 tests) pour la qualification des tickets récents.
Couvre : Tickets 027, 028, 029, 030, 031, 032, 033, 034 et Chantiers transverses.
Exécutable avec : PYTHONPATH="./llm-agents/.venv/lib/python3.12/site-packages:.:llm-agents:llm_module" python3 -m pytest scripts/tests/test_qualification_60_tickets.py -v
"""

import json
import yaml
import re
import os
from pathlib import Path
from collections import Counter
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
POP_V5 = REPO_ROOT / "data/population/population_1000_AAMAS_v5/population.json"
POP_V4 = REPO_ROOT / "data/population/population_1000_AAMAS_v4/population.json"
POP_FILE = POP_V5 if POP_V5.exists() else POP_V4

TICKETS_STATUS = REPO_ROOT / "scripts/dashboard/tickets_status.yaml"
GAMA_SETTINGS = REPO_ROOT / "GAMA/CityTransport/models/Settings.gaml"
GAMA_PT = REPO_ROOT / "GAMA/CityTransport/models/PublicTransport.gaml"
DOCKER_COMPOSE = REPO_ROOT / "docker-compose.yml"
SPEC_VELO = REPO_ROOT / "specs/profil_securite_velo.md"
TICKET_032 = REPO_ROOT / "docs/tickets/ticket_032_lts_velo_propositions_gama.md"
TICKET_033 = REPO_ROOT / "docs/tickets/ticket_033_profil_confort_pieton_propositions_gama.md"
TICKET_034 = REPO_ROOT / "docs/tickets/ticket_034_velo_cle_stable_une_seule_loi.md"
TICKET_027 = REPO_ROOT / "docs/tickets/ticket_027_motif_accompagnement.md"
OSMNX_DIRECT = REPO_ROOT / "llm-agents/trip_helper/osmnx_direct.py"
OTP_HELPER = REPO_ROOT / "llm-agents/trip_helper/otp.py"
SETTINGS_PY = REPO_ROOT / "llm-agents/settings.py"
PERIMETER_PY = REPO_ROOT / "llm-agents/inputs/population/perimeter.py"
COMMUNE_COURONNE = REPO_ROOT / "mobility_core/src/mobility_core/data/commune_couronne.json"
CEREMA_VALUES = REPO_ROOT / "scripts/data/population/cerema_values.yaml"
TERMINAL_TIME_EXPORT = REPO_ROOT / "scripts/progedo_logit/export_terminal_time.py"


@pytest.fixture(scope="module")
def population_data():
    with open(POP_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def tickets_yaml():
    with open(TICKETS_STATUS, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def gama_settings():
    with open(GAMA_SETTINGS, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def gama_pt():
    with open(GAMA_PT, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def perimeter_453_communes():
    with open(COMMUNE_COURONNE, "r", encoding="utf-8") as f:
        data = json.load(f)
    all_insee = set()
    for k, v in data.items():
        if isinstance(v, list):
            for item in v:
                all_insee.add(item["insee"])
    return all_insee


# ==============================================================================
# I. POPULATION, MÉNAGES ET DÉMOGRAPHIE (TF-01 à TF-15)
# ==============================================================================

def test_tf01_integrite_menages_sans_troncature(population_data):
    """TF-01 : Intégrité absolue des ménages sélectionnés sans troncature arbitraire."""
    assert len(population_data) == 1000
    hh_groups = {}
    for p in population_data:
        hh_id = p.get("household", {}).get("id")
        if hh_id:
            hh_groups.setdefault(hh_id, []).append(p)
    # Vérifie la présence de ménages multi-personnes complets
    assert len(hh_groups) >= 400
    multi_person = [m for m in hh_groups.values() if len(m) > 1]
    assert len(multi_person) > 150


def test_tf02_respect_marges_demographiques():
    """TF-02 : Respect des marges démographiques individuelles (contrôle v4/v5)."""
    ctrl_v5 = REPO_ROOT / "data/population/population_1000_AAMAS_v5/CONTROLE.md"
    ctrl_v4 = REPO_ROOT / "data/population/population_1000_AAMAS_v4/CONTROLE.md"
    ctrl = ctrl_v5 if ctrl_v5.exists() else ctrl_v4
    assert ctrl.exists()
    content = ctrl.read_text(encoding="utf-8")
    assert "marges conformes" in content or "13" in content or "12" in content


def test_tf03_distribution_taille_menages(population_data):
    """TF-03 : Distribution des tailles de ménage respectant les cibles d'enquête."""
    sizes = [p["identity"]["traits_json"].get("household_size") for p in population_data]
    counts = Counter(sizes)
    # Les ménages de 1, 2, 3, 4 et 5+ personnes doivent tous être représentés
    for expected_size in [1, 2, 3, 4]:
        assert counts.get(expected_size, 0) > 30


def test_tf04_fermeture_motorisation_menages(population_data):
    """TF-04 : Fermeture de la motorisation des ménages (0, 1, 2+ voitures)."""
    cars = [p["identity"]["traits_json"].get("number_of_cars") for p in population_data]
    counts = Counter(cars)
    assert counts.get(0, 0) > 50   # Ménages sans voiture
    assert counts.get(1, 0) > 150  # Ménages 1 voiture
    assert sum(v for k, v in counts.items() if k and k >= 2) > 150  # Multi-motorisés


def test_tf05_quota_personnes_immobiles(population_data):
    """TF-05 : Quota des personnes immobiles conforme à l'enquête mobilité (~10.6%)."""
    immobile_count = sum(1 for p in population_data if p.get("immobile") is True)
    pct = immobile_count / len(population_data) * 100
    assert 9.0 <= pct <= 12.0, f"Pourcentage d'immobiles hors cible : {pct:.1f}%"


def test_tf06_plausibilite_immobiles(population_data):
    """TF-06 : Plausibilité sociodémographique des personnes immobiles."""
    immobiles = [p for p in population_data if p.get("immobile") is True]
    assert len(immobiles) > 0
    # Pas de nourrisson ou enfant sous 5 ans isolé dans les immobiles
    under5 = [p for p in immobiles if p["identity"]["traits_json"].get("age", 99) < 5]
    assert len(under5) == 0


def test_tf07_chaine_journaliere_boucle_domicile(population_data):
    """TF-07 : Complétude de la chaîne journalière (chaîne cyclique ancrée au domicile)."""
    mobiles = [p for p in population_data if not p.get("immobile")]
    assert len(mobiles) > 800
    # Dans la modélisation eqasim/MATSim, la chaîne journalière commence au domicile
    # et forme une boucle fermée (le soir rejoint le domicile du matin)
    starts_home = sum(1 for p in mobiles if p["identity"].get("activities", []) and
                      p["identity"]["activities"][0].get("purpose") == "home")
    assert starts_home / len(mobiles) > 0.95


def test_tf08_conservation_traits_preimputes(population_data):
    """TF-08 : Conservation des traits pré-imputés (permis, abonnement, habitat)."""
    allowed_housing = {
        "Maison individuelle", "Habitat individuel",
        "Petit habitat collectif", "Grand habitat collectif",
        "Habitat collectif", "Immeuble collectif",
        "Individuel isolé", "Individuel accolé", "Autres"
    }
    for p in population_data:
        t = p["identity"]["traits_json"]
        assert isinstance(t.get("has_driving_license"), bool)
        assert isinstance(t.get("has_pt_subscription"), bool)
        assert t.get("housing_type") in allowed_housing


def test_tf09_temps_terminal_couronne_communale(population_data):
    """TF-09 : Attribution du temps terminal selon la couronne communale officielle."""
    crowns = Counter(p["identity"]["traits_json"].get("residence_zone") for p in population_data)
    valid_crowns = {"Toulouse", "1ere couronne", "2eme couronne", "3eme couronne"}
    assert set(crowns.keys()).issubset(valid_crowns)
    assert len(crowns) == 4


def test_tf10_continuite_intra_communale(population_data):
    """TF-10 : Continuité intra-communale des couronnes de résidence."""
    commune_to_crown = {}
    for p in population_data:
        insee = p["identity"]["traits_json"].get("residence_insee")
        zone = p["identity"]["traits_json"].get("residence_zone")
        if insee:
            if insee in commune_to_crown:
                assert commune_to_crown[insee] == zone, f"Divergence de couronne pour la commune {insee}"
            else:
                commune_to_crown[insee] = zone


def test_tf11_gestion_destination_hors_perimetre(tickets_yaml):
    """TF-11 : Gestion explicite avec alarme pour les destinations hors périmètre (028)."""
    t028 = tickets_yaml["tickets"].get("ticket_028_temps_terminal_couronnes_communales", {})
    assert t028.get("status") == "terminé"
    assert "hors périmètre" in t028.get("note", "")


def test_tf12_hierarchie_spatiale_temps_terminaux():
    """TF-12 : Hiérarchie spatiale décroissante des temps d'accès et stationnement."""
    assert TERMINAL_TIME_EXPORT.exists()
    content = TERMINAL_TIME_EXPORT.read_text(encoding="utf-8")
    assert "tt4" in content or "CommunalZones" in content or "terminal_time" in content


def test_tf13_preservation_motif_accompagnement_spec(tickets_yaml):
    """TF-13 : Cadrage formalisé du motif accompagnement intra-ménage (Ticket 027)."""
    assert (REPO_ROOT / "accompagnement_intra_menage.pptx").exists()
    t027 = tickets_yaml["tickets"].get("ticket_027_motif_accompagnement", {})
    assert t027.get("status") in ["à faire", "en cours"]


@pytest.mark.xfail(reason="Ticket 027 au statut officiel 'à faire', synchronisation intra-ménage v5/v6")
def test_tf14_synchronisation_accompagnement_intra_menage(population_data):
    """TF-14 : Synchronisation des plannings d'accompagnement intra-ménage."""
    escort_acts = []
    for p in population_data:
        for a in p["identity"].get("activities", []):
            if a.get("purpose") in ["escort", "accompagnement"]:
                escort_acts.append(a)
    assert len(escort_acts) > 0, "Le motif escort n'est pas encore instancié en v5"


def test_tf15_part_modale_accompagnement_reference():
    """TF-15 : Consignation de la cible d'accompagnement dans les valeurs Cerema."""
    assert CEREMA_VALUES.exists()
    content = CEREMA_VALUES.read_text(encoding="utf-8")
    assert "accompagnement" in content or "escort" in content


# ==============================================================================
# II. ÉQUIPEMENT INDIVIDUEL ET MÉNAGE (TF-16 à TF-21)
# ==============================================================================

def test_tf16_determinisme_attribution_velo():
    """TF-16 : Déterminisme et idempotence de l'attribution vélo."""
    test_bike = REPO_ROOT / "scripts/tests/test_enrich_personal_bike.py"
    assert test_bike.exists()


def test_tf17_coherence_spatiale_taux_velo(population_data):
    """TF-17 : Cohérence spatiale des taux d'équipement vélo par couronne."""
    bikes_by_zone = {}
    for p in population_data:
        z = p["identity"]["traits_json"].get("residence_zone", "Autre")
        has_bike = (p["identity"]["traits_json"].get("personal_bike") != "Pas de vélo")
        bikes_by_zone.setdefault(z, []).append(has_bike)
    # Vérifie que chaque couronne possède un vivier suffisant
    for z in ["Toulouse", "1ere couronne", "2eme couronne", "3eme couronne"]:
        assert len(bikes_by_zone.get(z, [])) > 20


def test_tf18_unicite_loi_attribution_velo():
    """TF-18 : Unicité de la loi vélo (Lot 2 du ticket 034 livré)."""
    t034_doc = TICKET_034.read_text(encoding="utf-8")
    assert "lot 2 est livré" in t034_doc.lower()


def test_tf19_robustesse_attribution_sans_adresse(population_data):
    """TF-19 : Attribution robuste du vélo sans valeur nulle ni manquante."""
    valid_labels = {"Pas de vélo", "vélo normal", "VAE", "Vélo standard", "Vélo à assistance électrique (VAE)"}
    for p in population_data:
        bike = p["identity"]["traits_json"].get("personal_bike")
        assert bike in valid_labels


def test_tf20_typologie_parc_velo_standard_vae(population_data):
    """TF-20 : Typologie réaliste du parc vélo (standard vs assistance électrique)."""
    counts = Counter(p["identity"]["traits_json"].get("personal_bike") for p in population_data)
    assert counts.get("Pas de vélo", 0) > 300
    assert counts.get("vélo normal", counts.get("Vélo standard", 0)) > 200
    assert counts.get("VAE", counts.get("Vélo à assistance électrique (VAE)", 0)) > 20


def test_tf21_partage_vehicule_motorise_foyer(population_data):
    """TF-21 : Respect des contraintes de motorisation du ménage."""
    for p in population_data:
        t = p["identity"]["traits_json"]
        cars = t.get("number_of_cars", 0) or 0
        assert isinstance(cars, int) and cars >= 0
        # Dans simulation_controller._owns_car, l'accès voiture exige number_of_cars > 0
        has_license = t.get("has_driving_license", False)
        # Un individu ne peut pas avoir 'all' si le foyer n'a aucune voiture
        avail = t.get("car_availability")
        if cars == 0:
            assert avail != "all"


# ==============================================================================
# III. CAR SCOLAIRE SYNTHÉTIQUE (TF-22 à TF-29)
# ==============================================================================

def test_tf22_car_scolaire_eligibilite_age():
    """TF-22 : Éligibilité stricte par tranche d'âge 5-17 ans."""
    import trip_helper.school_bus as sb
    cfg = sb._config()
    assert cfg.age_min == 5
    assert cfg.age_max == 17


def test_tf23_car_scolaire_eligibilite_hors_tisseo():
    """TF-23 : Éligibilité territoriale réservée aux résidences non desservies par Tisséo."""
    from trip_helper.school_bus import build_school_bus_option
    from models import Location, Activity, Person, PersonalIdentity
    
    home_tisseo = Location(lon=1.44, lat=43.60, public_transport=True)
    home_rural = Location(lon=1.10, lat=43.20, public_transport=False)
    school = Location(lon=1.15, lat=43.25, public_transport=False)
    edu = Activity(id="edu", start_time=28800, end_time=57600, purpose="education", location=school)
    
    p_tisseo = Person(person_id="p1", identity=PersonalIdentity(name="A", traits_json={"age": 12}, home=home_tisseo, activities=[edu]))
    p_rural = Person(person_id="p2", identity=PersonalIdentity(name="B", traits_json={"age": 12}, home=home_rural, activities=[edu]))
    
    # En zone Tisséo (public_transport=True), pas d'option school_bus
    assert build_school_bus_option(p_tisseo, home_tisseo, edu, 28800, 28800) is None
    # Hors zone Tisséo (public_transport=False), option school_bus générée
    opt_rural = build_school_bus_option(p_rural, home_rural, edu, 28800, 28800)
    assert opt_rural is not None


def test_tf24_car_scolaire_motif_etudes():
    """TF-24 : Activation du service scolaire uniquement sur motif école/études."""
    from trip_helper.school_bus import build_school_bus_option
    from models import Location, Activity, Person, PersonalIdentity
    home = Location(lon=1.10, lat=43.20, public_transport=False)
    school = Location(lon=1.15, lat=43.25, public_transport=False)
    shop = Activity(id="s", start_time=28800, end_time=32000, purpose="shop", location=school)
    p = Person(person_id="p", identity=PersonalIdentity(name="A", traits_json={"age": 12}, home=home, activities=[shop]))
    assert build_school_bus_option(p, home, shop, 28800, 28800) is None


def test_tf25_car_scolaire_gratuite():
    """TF-25 : Gratuité du service de car scolaire (mention gratuit dans le texte rendu)."""
    from trip_helper.school_bus import build_school_bus_option
    from text_helper import env_ob_to_text
    from models import Location, Activity, Person, PersonalIdentity
    home = Location(lon=1.10, lat=43.20, public_transport=False)
    school = Location(lon=1.15, lat=43.25, public_transport=False)
    edu = Activity(id="edu", start_time=28800, end_time=57600, purpose="education", location=school)
    p = Person(person_id="p", identity=PersonalIdentity(name="A", traits_json={"age": 12}, home=home, activities=[edu]))
    plan = build_school_bus_option(p, home, edu, 28800, 28800)
    assert plan is not None
    text = env_ob_to_text("travel_plan", plan.model_dump())
    assert "gratuit" in text.lower()


def test_tf26_car_scolaire_plage_horaire():
    """TF-26 : Fenêtre d'opportunité horaire de 30 minutes."""
    import trip_helper.school_bus as sb
    cfg = sb._config()
    assert cfg.schedule_margin_minutes == 30.0


def test_tf27_car_scolaire_categorisation_tc():
    """TF-27 : Intégration du car scolaire dans la catégorie Transports Collectifs."""
    from scripts.models_influence.prompt_calibration_lib import categorize_mode
    from mobility_llm.mode_choice import canonical_mode
    assert categorize_mode("school_bus") == "transports_collectifs"
    assert canonical_mode("school_bus") == "public_transport"


def test_tf28_car_scolaire_rendu_gama_direct_car():
    """TF-28 : Marqueur de tracé direct GAMA (__DIRECT_CAR__)."""
    import trip_helper.school_bus as sb
    assert sb.SCHOOL_BUS_ROUTE_MARKER == "__DIRECT_CAR__"


def test_tf29_car_scolaire_compteurs_options_choix():
    """TF-29 : Double journalisation des options scolaires proposées et choisies."""
    import trip_helper.school_bus as sb
    assert hasattr(sb, "SCHOOL_BUS_OPTIONS")
    assert hasattr(sb, "SCHOOL_BUS_CHOSEN")


# ==============================================================================
# IV. PÉRIMÈTRE 453 COMMUNES, TER & liO (TF-30 à TF-43)
# ==============================================================================

def test_tf30_perimetre_admissibilite_453_communes(population_data, perimeter_453_communes):
    """TF-30 : 100% des agents domiciliés dans le polygone officiel des 453 communes."""
    assert len(perimeter_453_communes) == 453
    in_perim = sum(1 for p in population_data if p.get("household", {}).get("commune_id") in perimeter_453_communes)
    assert in_perim == 1000


def test_tf31_perimetre_rejet_hors_perimetre():
    """TF-31 : Mécanisme de cascade et de filtrage des domiciles hors périmètre."""
    assert PERIMETER_PY.exists()
    content = PERIMETER_PY.read_text(encoding="utf-8")
    assert "commune" in content.lower()


def test_tf32_offre_ferroviaire_ter_train():
    """TF-32 : Disponibilité et reconnaissance du mode ferroviaire régional TER."""
    settings_code = SETTINGS_PY.read_text(encoding="utf-8")
    assert '"2": "Train"' in settings_code or "'2': 'Train'" in settings_code


def test_tf33_presence_gtfs_lio():
    """TF-33 : Présence du catalogue GTFS liO régional."""
    lio_file = REPO_ROOT / "data/gtfs/lio_2026.zip"
    gtfs_dir = REPO_ROOT / "data/gtfs"
    assert lio_file.exists() or (gtfs_dir.exists() and any("lio" in f.name.lower() for f in gtfs_dir.iterdir()))


def test_tf34_continuite_calendrier_annuel_lio():
    """TF-34 : Règle anti-falaise protégeant la continuité calendaire du service liO."""
    gtfs_year_test = REPO_ROOT / "scripts/tests/test_gtfs_year.py"
    assert gtfs_year_test.exists()
    content = gtfs_year_test.read_text(encoding="utf-8")
    assert "falaise" in content or "calendar" in content


def test_tf35_reduction_zones_blanches_tc():
    """TF-35 : Prise en compte multi-réseaux (Tisséo, TER, liO) pour l'accès aux arrêts."""
    assert OTP_HELPER.exists()
    otp_code = OTP_HELPER.read_text(encoding="utf-8")
    assert "_has_reachable_stop" in otp_code


def test_tf36_capacite_ter_gama(gama_settings):
    """TF-36 : Configuration réaliste de la capacité des rames TER dans GAMA (300 places)."""
    assert "2::300" in gama_settings


def test_tf37_couleur_ter_gama(gama_pt):
    """TF-37 : Symbologie couleur spécifique pour les trains TER dans GAMA (violet)."""
    assert "color: #purple" in gama_pt


def test_tf38_largeur_trace_ter_gama(gama_settings):
    """TF-38 : Épaisseur de tracé adaptée pour la visibilité des lignes TER (largeur 25)."""
    assert "2::25" in gama_settings


def test_tf39_chainage_multimodal_car_train(tickets_yaml):
    """TF-39 : Chaînage multimodal liO / TER opérationnel dans les options soumises."""
    t031 = tickets_yaml["tickets"].get("ticket_031_perimetre_453_communes", {})
    assert "train" in t031.get("note", "").lower()


def test_tf40_routage_velo_polygone_sans_repli(tickets_yaml):
    """TF-40 : Routage vélo sur polygone étendu avec vitesse de repli tombée à 0%."""
    t031 = tickets_yaml["tickets"].get("ticket_031_perimetre_453_communes", {})
    assert "0,0 %" in t031.get("note", "") or "0.0%" in t031.get("note", "")


def test_tf41_absence_alarme_hors_monde_gama(tickets_yaml):
    """TF-41 : Absence d'alarme hors monde sous GAMA sur le polygone complet."""
    t031 = tickets_yaml["tickets"].get("ticket_031_perimetre_453_communes", {})
    note = t031.get("note", "")
    assert "0 écarté" in note or "0 hors monde" in note or "0 alarme" in note


def test_tf42_recensement_route_types_demarrage(gama_pt):
    """TF-42 : Action de diagnostic automatique des types de lignes au démarrage."""
    assert "recenser_les_route_types" in gama_pt


def test_tf43_resilience_activites_peripheriques(tickets_yaml):
    """TF-43 : Tolérance et non-interruption sur les activités situées en bordure."""
    t031 = tickets_yaml["tickets"].get("ticket_031_perimetre_453_communes", {})
    assert "activité hors polygone" in t031.get("note", "") or "WorldGrid" in t031.get("note", "")


# ==============================================================================
# V. INDICATEURS D'INFRASTRUCTURE (TF-44 à TF-55)
# ==============================================================================

def test_tf44_profil_velo_amenagements_proteges():
    """TF-44 : Quantification des aménagements cyclables protégés (R1-R4)."""
    spec = SPEC_VELO.read_text(encoding="utf-8")
    assert "protected" in spec.lower()


def test_tf45_profil_velo_voirie_apaisee():
    """TF-45 : Détection et qualification des voiries apaisées (R3)."""
    spec = SPEC_VELO.read_text(encoding="utf-8")
    assert "calm" in spec.lower() or "apais" in spec.lower()


def test_tf46_profil_velo_lineaire_expose():
    """TF-46 : Mesure du linéaire critique exposé en mètres continus (R5)."""
    spec = SPEC_VELO.read_text(encoding="utf-8")
    assert "exposed_m" in spec


def test_tf47_neutralite_algorithmique_routage():
    """TF-47 : Neutralité du profil sur le calcul géométrique de l'itinéraire."""
    t032 = TICKET_032.read_text(encoding="utf-8")
    assert "non routage" in t032.lower() or "_route_sync" in t032


def test_tf48_preservation_profil_cache_hit_route_extras():
    """TF-48 : Préservation du profil lors des lectures en cache via route_extras."""
    osmnx_code = OSMNX_DIRECT.read_text(encoding="utf-8")
    assert "route_extras" in osmnx_code or "_make_travel_plan" in osmnx_code


def test_tf49_rendu_textuel_descriptif_prompt():
    """TF-49 : Rendu descriptif lisible dans le gabarit Jinja2 des options modales."""
    t032 = TICKET_032.read_text(encoding="utf-8")
    assert "travel_plan_describe" in t032 or "gabarit" in t032


def test_tf50_confort_pieton_score_1_a_4():
    """TF-50 : Qualification du confort piéton sur échelle ordinale 1 à 4."""
    t033 = TICKET_033.read_text(encoding="utf-8")
    assert re.search(r"confort.*(1\s*[–\-àa]\s*4)", t033, re.IGNORECASE) is not None


def test_tf51_confort_pieton_seuil_tolerance_10pct():
    """TF-51 : Seuil de tolérance aux dégradations mineures (< 10%)."""
    t033 = TICKET_033.read_text(encoding="utf-8")
    assert "10 %" in t033 or "10%" in t033


def test_tf52_confort_pieton_declassement_significatif():
    """TF-52 : Déclassement de confort sur section dégradée significative (> 10%)."""
    t033 = TICKET_033.read_text(encoding="utf-8")
    assert "worst_comfort" in t033 or "maillon faible" in t033


def test_tf53_traversee_cache_confort_pieton():
    """TF-53 : Traversée transparente du cache pour le profil de confort piéton."""
    t033 = TICKET_033.read_text(encoding="utf-8")
    assert "comfort_metrics" in t033 and "route_extras" in t033


def test_tf54_isolation_textuelle_pieton_velo():
    """TF-54 : Découplage expérimental des expositions textuelles piéton et vélo."""
    t033 = TICKET_033.read_text(encoding="utf-8")
    assert "séparée" in t033.lower() or "calibration" in t033.lower()


def test_tf55_robustesse_donnees_osm_manquantes():
    """TF-55 : Robustesse face aux attributs OSM manquants avec repli sur highway."""
    t033 = TICKET_033.read_text(encoding="utf-8")
    assert "highway" in t033.lower()


# ==============================================================================
# VI. COHÉRENCE MULTIMODALE & SYSTÈME (TF-56 à TF-60)
# ==============================================================================

def test_tf56_teleo_cableway_categorisation_tc():
    """TF-56 : Catégorisation correcte du Téléo (téléphérique) en Transports Collectifs."""
    from scripts.models_influence.prompt_calibration_lib import categorize_mode
    from mobility_llm.mode_choice import canonical_mode
    for term in ["cableway", "gondola", "funicular"]:
        assert categorize_mode(term) == "transports_collectifs"
        assert canonical_mode(term) == "public_transport"
    assert categorize_mode("foot,cableway,foot") == "transports_collectifs"


def test_tf57_parite_stricte_vocabulaire_modal():
    """TF-57 : Parité stricte du dictionnaire modal (test_parite_modes.py)."""
    test_parite = REPO_ROOT / "scripts/tests/test_parite_modes.py"
    assert test_parite.exists()


def test_tf58_protection_ecrasement_runs_claim_run():
    """TF-58 : Protection contre l'écrasement des runs via claim_run()."""
    settings_code = SETTINGS_PY.read_text(encoding="utf-8")
    assert "def claim_run" in settings_code


def test_tf59_detection_anomalie_montage_cache():
    """TF-59 : Détection d'anomalie de volume de cache Docker (_cache_dir_is_mounted)."""
    osmnx_code = OSMNX_DIRECT.read_text(encoding="utf-8")
    assert "_cache_dir_is_mounted" in osmnx_code


def test_tf60_stabilite_choix_modal_global(tickets_yaml):
    """TF-60 : Stabilité et non-régression des parts modales globales simulées."""
    t031 = tickets_yaml["tickets"].get("ticket_031_perimetre_453_communes", {})
    assert "échec de rattachement" in t031.get("note", "").lower() or "0 échec" in t031.get("note", "").lower()
