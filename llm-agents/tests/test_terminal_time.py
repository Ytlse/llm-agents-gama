"""Temps terminal des itinéraires — ticket 013.

Couvre les critères d'acceptation qui se vérifient sans appel LLM :

1. 100 % des options voiture et vélo décrivent un temps terminal ;
2. le total affiché est SUPÉRIEUR à la seule durée de conduite, et la
   décomposition **somme** au total ;
4. aucune option en transports collectifs n'a changé (pas de double comptage) ;

plus les invariants qui protègent la mesure : code de plan inchangé (clé du cache
de décisions), étiquette de mode inchangée (elle alimente la loss de calibration),
ligne ``Distance`` conservée (elle porte ``dist_km``), et versionnage des deux
caches qui, sans ça, resserviraient des durées périmées.
"""

import sys
from pathlib import Path

import pytest
import yaml

_LLM_AGENTS = Path(__file__).resolve().parents[1]
if str(_LLM_AGENTS) not in sys.path:
    sys.path.insert(0, str(_LLM_AGENTS))

from helper import humanize_duration                      # noqa: E402
from models import Location, Transit, TransitLocation     # noqa: E402
from text_helper.models.travel_plan import (              # noqa: E402
    TravelPlanLiteWrapper, TravelPlanWrapper)
from text_helper.templates import repository              # noqa: E402
from trip_helper import terminal_time                     # noqa: E402
from trip_helper.osmnx_direct import _make_travel_plan    # noqa: E402

# Route GTFS RÉELLE (ligne de bus 13) : avec un identifiant inventé, le gabarit
# rendrait « Unknown 'Unknown' » et le contrôle de non-régression des options en
# transports collectifs ne prouverait rien.
_REAL_BUS_ROUTE = "line:142"

# Points ancrés dans des couronnes CONNUES (le temps terminal est spatialisé depuis
# la version tt2) : sans ancrage, les attendus dépendraient d'un hasard de latitude.
ORIGIN = Location(lon=1.4450, lat=43.5973)   # hypercentre → « Toulouse »
DEST = Location(lon=1.4400, lat=43.6000)     # à 500 m → « Toulouse » aussi
ZONE_LOINTAINE = Location(lon=1.10, lat=43.40)  # ~35 km → « 2eme couronne »
T0 = 1773723994


@pytest.fixture(autouse=True)
def minutes_not_buckets():
    """Force le rendu en minutes, comme la production.

    ``settings.agent.quantify_time_window`` vaut ``True`` par défaut dans le code
    mais ``false`` dans toutes les configs de run (``config/config_*.yaml``) : les
    jeux gelés portent des minutes, pas « moderate (under 10 minutes) ». Sans ce
    forçage, les tests mesureraient un rendu que la production n'utilise pas.
    """
    previous = repository.env.filters['duration_to_bucket_text']
    repository.env.filters['duration_to_bucket_text'] = humanize_duration
    yield
    repository.env.filters['duration_to_bucket_text'] = previous


@pytest.fixture(autouse=True)
def fresh_config():
    terminal_time.reset()
    yield
    terminal_time.reset()


def _wrap(plan, purpose="shop"):
    """Applique la conversion en millisecondes que fait ``get_itineraries``."""
    plan.purpose = purpose
    plan.start_time = int(plan.start_time * 1000)
    plan.end_time = int(plan.end_time * 1000)
    for leg in plan.legs:
        leg.start_time = int(leg.start_time * 1000)
        leg.end_time = int(leg.end_time * 1000)
    return TravelPlanWrapper(**plan.model_dump())


def direct(mode, network_s, distance_m=1800.0, purpose="shop"):
    """Plan direct à partir d'une durée de PARCOURS RÉSEAU pur."""
    return _wrap(_make_travel_plan(ORIGIN, DEST, mode, T0, network_s, distance_m),
                 purpose)


def transit_plan(purpose="shop"):
    """Plan ``foot,bus,foot`` tel que le produit le parseur OTP."""
    stop_a = TransitLocation(stop="Pradettes", lat=43.60, lon=1.40)
    stop_b = TransitLocation(stop="Gare SNCF Baziège", lat=43.61, lon=1.41)
    orig = TransitLocation(stop="", lat=43.60, lon=1.40)
    dest = TransitLocation(stop="", lat=43.61, lon=1.41)
    base = T0 * 1000
    legs = [
        Transit(start_time=base, end_time=base + 180_000, duration=180, mode="foot",
                start_location=orig, end_location=stop_a, is_transfer=True),
        Transit(start_time=base + 180_000, end_time=base + 300_000, duration=120,
                mode="bus", start_location=stop_a, end_location=stop_b,
                is_transfer=False, transit_route=_REAL_BUS_ROUTE),
        Transit(start_time=base + 300_000, end_time=base + 780_000, duration=480,
                mode="foot", start_location=stop_b, end_location=dest,
                is_transfer=True),
    ]
    return TravelPlanWrapper(id="t", start_location=ORIGIN, end_location=DEST,
                             start_time=base, end_time=base + 780_000, duration=780,
                             distance=1400.0, purpose=purpose, legs=legs)


# ── Structure du plan ────────────────────────────────────────────────────────

@pytest.mark.parametrize("mode, expected_legs", [
    ("car", 3), ("bicycle", 3), ("foot", 1),
])
def test_nombre_de_jambes_par_mode(mode, expected_legs):
    """Voiture et vélo portent accès + trajet + diffusion ; la marche non.

    La marche est porte-à-porte par construction (§4.1) : lui ajouter un temps
    terminal serait inventer un coût qui n'existe pas.
    """
    plan = direct(mode, 300)
    assert len(plan.legs) == expected_legs


def test_marche_et_tc_sans_temps_terminal():
    """Critère 4 : aucun temps terminal ajouté là où il serait un double comptage."""
    assert not direct("foot", 600).has_terminal_legs
    assert not transit_plan().has_terminal_legs
    assert terminal_time.terminal_profile("foot") is None
    assert terminal_time.terminal_profile("bus") is None


def test_code_de_plan_inchange():
    """INVARIANT : décomposer l'affichage ne doit pas changer l'identité du plan.

    ``get_code()`` est la clé du cache de décisions LLM et de la déduplication
    d'itinéraires. Si les jambes terminales y entraient, chaque option voiture
    deviendrait une option « nouvelle » et tout le cache serait perdu en silence.
    """
    assert direct("car", 300).get_code() == "__DIRECT_CAR__^^"
    assert direct("bicycle", 300).get_code() == "__DIRECT_BICYCLE__^^"
    assert direct("foot", 300).get_code() == "__DIRECT_FOOT__^^"


def test_etiquette_de_mode_inchangee():
    """L'étiquette reste ``car`` — c'est elle que lit ``parse_option_modes``.

    Sans exclusion des jambes terminales, elle vaudrait ``"None,car,None"`` : le
    mode de chaque option serait mal attribué, donc ``categorize_mode``, donc la
    loss de calibration et les parts modales de ``moves.csv``.
    """
    assert direct("car", 300).mode_label() == "car"
    assert direct("bicycle", 300).mode_label() == "bicycle"
    assert direct("foot", 300).mode_label() == "foot"
    assert transit_plan().mode_label() == "foot,bus,foot"


# ── Rendu ────────────────────────────────────────────────────────────────────

def test_rendu_voiture_decompose():
    """Critère 1 et 2, sur le cas de référence du ticket (1,4 km, agent 70156)."""
    # 3 min de conduite réseau ; l'ancien code affichait 7 min (3 + 4 de park_base
    # invisibles) et rien pour l'accès.
    # Trajet interne à Toulouse : accès 3 min, stationnement 7 min (centre-ville).
    desc = direct("car", 180, distance_m=1800.0).describe()
    assert desc.startswith(" Temps de trajet : 13 minutes, "
                           "dont 10 minutes d'accès et de stationnement. "
                           "Distance : 1.8 km.")
    assert "\n- Rejoindre la voiture : 3 minutes." in desc
    assert "\n- Conduite : 3 minutes." in desc
    assert "\n- Stationnement et marche jusqu'à 'shop' : 7 minutes." in desc


def test_rendu_velo_decompose():
    """Le vélo change de RENDU sans changer de durée — et c'est voulu (T5).

    Les 2 minutes terminales sont celles que ``park_base`` ajoutait déjà en
    silence : ce ticket les rend visibles, il ne les invente pas. Si les parts
    vélo bougent, ce sera par la seule salience.
    """
    desc = direct("bicycle", 300, distance_m=1400.0).describe()
    assert desc.startswith(" Temps de trajet : 7 minutes, "
                           "dont 2 minutes d'accès et d'attache. "
                           "Distance : 1.4 km.")
    assert "\n- Déverrouiller le vélo : 1 minute." in desc
    assert "\n- Trajet à vélo : 5 minutes." in desc
    assert "\n- Attacher le vélo à 'shop' : 1 minute." in desc


def test_rendu_marche_inchange():
    assert direct("foot", 960, distance_m=1400.0).describe() == (
        " Durée estimée : 16 minutes. Distance : 1.4 km.")


def test_rendu_transports_collectifs_inchange():
    """Critère 4 : le texte des options TC est identique au caractère.

    Chaîne attendue recopiée du rendu ANTÉRIEUR au ticket 013 (format des jeux
    gelés v3) : c'est le seul contrôle qui détecte une régression introduite par
    la nouvelle branche du gabarit.
    """
    assert transit_plan().describe() == (
        " Temps de trajet : 13 minutes, dont 11 minutes de marche."
        "\n- Marche jusqu'à 'Pradettes' : 3 minutes."
        "\n- Bus '13' vers 'Gare SNCF Baziège' : 2 minutes."
        "\n- Marche jusqu'à 'shop' : 8 minutes.")


def test_distance_conservee_sur_voiture_et_velo():
    """La ligne ``Distance`` porte ``dist_km`` des records de calibration.

    ``metadata.extract_min_distance_km`` prend le MINIMUM des distances affichées
    dans la section. Mesuré sur ``v3`` : 579 records (13,5 %) ne tiennent leur
    distance QUE des lignes voiture/vélo. La branche TC n'affiche pas de distance ;
    si les plans directs basculaient dessus sans garder la leur, ces décisions
    perdraient ``dist_cat`` et sortiraient de la strate distance de la mesure —
    un score qui s'améliore parce qu'on mesure moins.
    """
    for mode in ("car", "bicycle"):
        assert "Distance : 2.3 km." in direct(mode, 300, distance_m=2300.0).describe()


@pytest.mark.parametrize("mode", ["car", "bicycle"])
@pytest.mark.parametrize("network_s", [1, 59, 60, 61, 119, 137, 300, 613, 3599, 4741])
def test_total_egale_somme_des_sous_etapes(mode, network_s):
    """Critère 2, éprouvé sur une grille de durées non alignées sur la minute.

    ``humanize_duration`` TRONQUE à la minute. L'égalité ne tient que parce que
    les temps terminaux sont des multiples de 60 s
    (``floor(a + k×60) == floor(a) + k``), ce que le chargeur de configuration
    impose. Ce test est ce qui rendrait visible une valeur de 90 s glissée dans le
    YAML.
    """
    plan = direct(mode, network_s)
    total_minutes = plan.total_seconds // 60
    sous_etapes = sum(seconds // 60 for _, seconds in plan.described_steps)
    assert total_minutes == sous_etapes
    # Le total est strictement supérieur à la seule durée de parcours (critère 2).
    assert plan.total_seconds > network_s


def test_forme_courte_reconnait_les_plans_a_trois_jambes():
    """La requête mémoire doit encore décrire le trajet, pas une liste vide.

    Le test portait sur ``legs | length == 1`` ; un plan voiture en compte trois
    depuis ce ticket et serait tombé dans la branche « List of transits », qui
    n'affiche que les jambes de transport collectif — donc rien.
    """
    lite = TravelPlanLiteWrapper(**direct("car", 180).model_dump())
    assert lite.describe() == "Direct car; Duration: 13 minutes; Distance: 1.8 km."


def test_libelle_de_diffusion_sans_destination_connue():
    """Sans ``purpose``, on ne fabrique pas un nom de destination."""
    desc = direct("car", 180, purpose=None).describe()
    assert "Stationnement et marche jusqu'à la destination : 7 minutes." in desc
    assert "{destination}" not in desc


# ── Configuration ────────────────────────────────────────────────────────────

def _write_config(tmp_path, payload):
    path = tmp_path / "terminal_time.yaml"
    path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    terminal_time._CONFIG_PATH = path
    terminal_time.reset()
    return path


_LABELS = {"access": "a", "main": "m", "egress": "e '{destination}'",
           "egress_sans_destination": "e", "terminal": "t"}


def test_config_refuse_un_temps_non_multiple_de_60(tmp_path, monkeypatch):
    monkeypatch.setattr(terminal_time, "_CONFIG_PATH", terminal_time._CONFIG_PATH)
    original = terminal_time._CONFIG_PATH
    try:
        _write_config(tmp_path, {"version": "x",
                                 "modes": {"car": {"access_s": {"default": 90},
                                                   "egress_s": {"default": 120},
                                                   "labels": _LABELS}}})
        with pytest.raises(ValueError, match="multiple de 60"):
            terminal_time.terminal_profile("car")
    finally:
        terminal_time._CONFIG_PATH = original
        terminal_time.reset()


def test_config_refuse_une_version_absente(tmp_path):
    original = terminal_time._CONFIG_PATH
    try:
        _write_config(tmp_path, {"modes": {}})
        with pytest.raises(ValueError, match="version"):
            terminal_time.data_version()
    finally:
        terminal_time._CONFIG_PATH = original
        terminal_time.reset()


def test_config_refuse_des_libelles_incomplets(tmp_path):
    original = terminal_time._CONFIG_PATH
    try:
        _write_config(tmp_path, {"version": "x",
                                 "modes": {"car": {"access_s": {"default": 60},
                                                   "egress_s": {"default": 60},
                                                   "labels": {"access": "a"}}}})
        with pytest.raises(ValueError, match="libellés manquants"):
            terminal_time.terminal_profile("car")
    finally:
        terminal_time._CONFIG_PATH = original
        terminal_time.reset()


def test_provenance_du_velo_declaree_non_sourcee():
    """T2 : une valeur sans source doit se déclarer, pas se dissimuler.

    Aucune référence chiffrée n'a été trouvée pour le temps terminal d'un vélo
    personnel ; la valeur reprend celle du code antérieur. L'écrire dans la
    configuration est ce qui empêche de la citer plus tard comme sourcée.
    """
    assert terminal_time.terminal_profile("bicycle").provenance == "unsourced"
    assert terminal_time.terminal_profile("car").provenance == "sourced"


def test_grille_de_sensibilite_ordonnee():
    """T6 : trois variantes, facteurs strictement croissants.

    Une variante applique un FACTEUR sur toutes les couronnes, pas une valeur
    unique : une constante écraserait la spatialisation, et la sensibilité
    mesurerait « spatialisé ou non » en même temps que l'ampleur du temps terminal.
    """
    variants = terminal_time.sensitivity_variants()
    assert set(variants) == {"low", "central", "high"}
    factors = [variants[n]["car"]["factor"] for n in ("low", "central", "high")]
    assert factors[0] < factors[1] < factors[2]


def test_variante_conserve_le_gradient_par_zone():
    """Une variante met à l'échelle SANS aplatir la spatialisation."""
    base = terminal_time.terminal_profile("car")
    ecart_base = base.egress_s("Toulouse") - base.egress_s("3eme couronne")
    terminal_time.apply_variant("high")
    haut = terminal_time.terminal_profile("car")
    assert haut.egress_s("Toulouse") > base.egress_s("Toulouse")
    assert haut.egress_s("Toulouse") - haut.egress_s("3eme couronne") > ecart_base
    # L'invariant des multiples de 60 survit à la mise à l'échelle.
    for zone in ("Toulouse", "1ere couronne", "2eme couronne", "3eme couronne", "default"):
        assert haut.access_s(zone) % 60 == 0 and haut.egress_s(zone) % 60 == 0


def test_variante_de_sensibilite_change_la_version_de_donnees():
    """Les trois jeux de sensibilité ne doivent pas partager de clé de cache.

    Sans suffixe de version, une éval sous la variante haute lirait le cache de la
    variante centrale : les trois mesures de T6 se confondraient.
    """
    base = terminal_time.data_version()
    terminal_time.apply_variant("high")
    assert terminal_time.data_version() == f"{base}-high"
    assert terminal_time.terminal_profile("car").total_s("Toulouse", "Toulouse") > 600
    # Deux bascules successives n'empilent pas les suffixes.
    terminal_time.apply_variant("low")
    assert terminal_time.data_version() == f"{base}-low"


def test_bascules_successives_nempilent_pas_les_facteurs():
    """Enchaîner deux variantes doit donner la seconde, pas le produit des deux.

    C'est le cas d'usage NORMAL de la grille T6 : une boucle qui parcourt low,
    central, high dans le même processus. En partant des profils courants au lieu
    des profils centraux, `high` puis `low` appliquait 1,5 × 0,5 = 0,75 — des temps
    terminaux qu'aucune variante ne déclare, sous une étiquette de variante juste.
    """
    central = terminal_time.terminal_profile("car").egress_s("Toulouse")
    terminal_time.apply_variant("low")
    attendu_low = terminal_time.terminal_profile("car").egress_s("Toulouse")

    terminal_time.reset()
    terminal_time.apply_variant("high")
    terminal_time.apply_variant("low")
    assert terminal_time.terminal_profile("car").egress_s("Toulouse") == attendu_low
    assert attendu_low < central  # et la variante basse reste bien basse

    # Idem dans l'autre sens, et le retour à `central` rend les valeurs de base.
    terminal_time.apply_variant("central")
    assert terminal_time.terminal_profile("car").egress_s("Toulouse") == central


def test_version_de_donnees_dans_les_trois_cles_de_cache(monkeypatch):
    """Les TROIS caches qui survivent aux runs doivent bouger avec le paramètre.

    Aucun des trois ne peut deviner qu'un temps terminal a changé :

    - **routage OSMnx** — adressé par (mode, coordonnées, créneau) : il resservirait
      des durées calculées sous l'ancienne définition ;
    - **itinéraires OTP** — le plus grave, parce qu'il ne mémorise pas des durées mais
      les ``TravelPlan`` sérialisés, options voiture et vélo comprises : un cache chaud
      resservirait des plans à UNE SEULE jambe portant l'ancien stationnement fondu
      dedans, soit le défaut du ticket 013 ressuscité après sa correction ;
    - **décisions LLM** — adressé par ``get_code()`` (routes et arrêts), donc
      insensible aux durées par construction : il rejouerait des décisions prises sur
      des options qui n'existent plus, et **rien ne le signalerait dans les logs**.
    """
    from datetime import datetime

    from llm.cache import LlmSemanticCache
    from models import Location
    from trip_helper.osmnx_persistent_cache import OsmnxPersistentCache
    from trip_helper.otp_persistent_cache import OtpPersistentCache

    options = [direct("car", 180)]
    dt = datetime(2026, 3, 17, 10, 55)
    ts = int(dt.timestamp())

    before_state = LlmSemanticCache._make_state_hash(options)
    before_route, *_ = OsmnxPersistentCache.make_key(dt, "car", 43.6, 1.4, 43.61, 1.41)
    before_otp = OtpPersistentCache.make_key(ts, ORIGIN, DEST, True, False, True)
    before_bl = OtpPersistentCache.make_blacklist_key(ORIGIN, DEST)

    # Changer le TEMPS TERMINAL doit invalider les caches de PLANS et de DÉCISIONS…
    monkeypatch.setattr(terminal_time, "data_version", lambda: "tt-autre")
    assert LlmSemanticCache._make_state_hash(options) != before_state
    assert OtpPersistentCache.make_key(ts, ORIGIN, DEST, True, False, True) != before_otp

    # …mais PAS le cache de ROUTAGE, qui ne mémorise que du temps réseau. L'invalider
    # ferait recalculer à froid des milliers de routes pour un résultat identique
    # (~2 h pour 930 personas). C'est la distinction que `routing_version` porte.
    assert OsmnxPersistentCache.make_key(dt, "car", 43.6, 1.4, 43.61, 1.41)[0] == before_route

    # Le routage a sa propre version, qui l'invalide bien quand elle bouge.
    monkeypatch.setattr(terminal_time, "routing_version", lambda: "r-autre")
    after_route, *_ = OsmnxPersistentCache.make_key(dt, "car", 43.6, 1.4, 43.61, 1.41)
    assert after_route != before_route

    # La liste noire, elle, ne DOIT PAS bouger : « OTP ne relie pas ces deux points »
    # est un fait de topologie du réseau, indépendant de tout temps terminal. La
    # versionner ferait re-interroger OTP pour rien sur toutes les paires connues comme
    # non reliées — la moitié des avertissements « No usable itinerary » d'un run.
    assert OtpPersistentCache.make_blacklist_key(ORIGIN, DEST) == before_bl


# ── Spatialisation (ticket 013 §4.1, version tt2) ────────────────────────────

def test_le_temps_terminal_depend_de_la_couronne():
    """Le stationnement coûte plus cher au centre qu'en couronne — et c'est sourcé.

    C'est le raffinement que le §4.1 annonçait : « le paramètre devrait dépendre du
    lieu de résidence / destination (le stationnement n'a pas le même coût à Toulouse
    intra-rocade et en 3ᵉ couronne) ». Une constante globale sous-estimait le coût
    d'usage de la voiture au centre et le surestimait en périphérie — donc aplatissait
    précisément l'élasticité spatiale qu'on veut mesurer.
    """
    p = terminal_time.terminal_profile("car")
    assert p.spatialise is True
    assert (p.access_s("Toulouse") > p.access_s("1ere couronne")
            >= p.access_s("2eme couronne") > p.access_s("3eme couronne"))
    assert (p.egress_s("Toulouse") > p.egress_s("1ere couronne")
            > p.egress_s("2eme couronne") > p.egress_s("3eme couronne"))


def test_zone_inconnue_retombe_sur_le_defaut():
    """Un point hors couche EMC² ne doit pas faire disparaître le temps terminal.

    ``residence_zone`` rend une chaîne vide pour un point inconnu. Sans entrée
    ``default``, la table serait consultée à vide — et le mode redeviendrait gratuit,
    c'est-à-dire le bug que ce ticket corrige, ressuscité par un trou de zonage.
    """
    p = terminal_time.terminal_profile("car")
    assert p.access_s("") == p.access_by_zone["default"]
    assert p.egress_s("zone inexistante") == p.egress_by_zone["default"]
    assert p.access_s("") > 0 and p.egress_s("") > 0


def test_les_deux_bouts_sont_tarifes_separement():
    """Accès sur la couronne d'ORIGINE, stationnement sur celle de DESTINATION."""
    from trip_helper.osmnx_direct import _make_travel_plan

    vers_centre = _wrap(_make_travel_plan(ZONE_LOINTAINE, ORIGIN, "car", T0, 180, 1800.0))
    vers_peripherie = _wrap(_make_travel_plan(ORIGIN, ZONE_LOINTAINE, "car", T0, 180, 1800.0))
    # Aller au centre coûte plus cher qu'en partir : le stationnement domine.
    assert vers_centre.terminal_time > vers_peripherie.terminal_time
    # Et le total reste la somme des sous-étapes affichées.
    for plan in (vers_centre, vers_peripherie):
        assert plan.total_seconds // 60 == sum(s // 60 for _, s in plan.described_steps)


def test_une_seule_definition_des_couronnes():
    """`move_logger` et le temps terminal doivent classer identiquement.

    Deux classements divergents feraient facturer un stationnement de centre-ville à
    un agent que la colonne « Lieu de résidence » du move-log dit en 2ᵉ couronne : une
    incohérence invisible dans les logs et fatale à la lecture des parts modales par
    zone.
    """
    from llm_module.core.geo_reference import residence_zone
    from urban_mobility_agents.utils.move_logger import _residence_zone

    for lat, lon in ((43.5973, 1.4450), (43.40, 1.10), (43.75, 1.60), (None, None)):
        assert _residence_zone(lat, lon) == residence_zone(lat, lon)
