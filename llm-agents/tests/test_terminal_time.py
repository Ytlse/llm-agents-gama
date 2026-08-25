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
    """Cache vidé avant/après, ET chemin de config restauré.

    ⚠ `_write_config` réassigne `terminal_time._CONFIG_PATH` vers un fichier
    temporaire sans le remettre : sans cette restauration, tout test exécuté APRÈS un
    test de configuration lisait un YAML de test jeté dans `tmp_path`. La fuite était
    invisible tant qu'aucun test ne dépendait des valeurs de PRODUCTION ; le
    garde-fou d'alignement sur l'enquête, lui, en dépend — il passait seul et
    tombait en suite.
    """
    original_path = terminal_time._CONFIG_PATH
    terminal_time.reset()
    yield
    terminal_time._CONFIG_PATH = original_path
    terminal_time.reset()


# Temps terminaux CERTAINS, en minutes, pour les tests de structure et de rendu.
# Depuis tt3 le temps terminal est TIRÉ dans la loi d'enquête, massée à zéro (88 à
# 96 % des trajets n'en ont aucun) : un plan de production n'a donc le plus souvent
# qu'une seule jambe. C'est le comportement voulu, mais il rend indécidable un test
# qui veut vérifier la DÉCOMPOSITION — il faut un cas où les deux bouts existent.
# Cette fixture installe une loi certaine, ce qui restaure le déterminisme sans
# revenir à des constantes : le mécanisme testé reste bien celui du tirage.
CERTAIN_ACCESS_MIN = 2
CERTAIN_EGRESS_MIN = 3


@pytest.fixture
def certain_terminal():
    """Force accès et diffusion à des valeurs certaines, pour les deux modes véhiculés."""
    conf = terminal_time._load()
    for mode in ("car", "bicycle"):
        profile = conf["modes"][mode]
        conf["modes"][mode] = terminal_time.TerminalProfile(
            mode=profile.mode,
            access_by_zone=profile.access_by_zone,
            egress_by_zone=profile.egress_by_zone,
            provenance=profile.provenance,
            spatialise=profile.spatialise,
            labels=profile.labels,
            access_law_by_zone={"default": {CERTAIN_ACCESS_MIN * 60: 1.0}},
            egress_law_by_zone={"default": {CERTAIN_EGRESS_MIN * 60: 1.0}},
        )
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
def test_nombre_de_jambes_par_mode(mode, expected_legs, certain_terminal):
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

def test_rendu_voiture_decompose(certain_terminal):
    """Critères 1 et 2 : la décomposition est affichée et elle somme à son total.

    Les durées attendues sont DÉRIVÉES de la fixture, pas recopiées : depuis tt3 le
    temps terminal est tiré dans la loi d'enquête, et figer « 3 min d'accès » ferait
    de ce test un test de la table tt2 plutôt que du rendu.
    """
    drive_min, terminal_min = 3, CERTAIN_ACCESS_MIN + CERTAIN_EGRESS_MIN
    desc = direct("car", drive_min * 60, distance_m=1800.0).describe()
    assert desc.startswith(f" Temps de trajet : {drive_min + terminal_min} minutes, "
                           f"dont {terminal_min} minutes d'accès et de stationnement. "
                           f"Distance : 1.8 km.")
    assert f"\n- Rejoindre la voiture : {CERTAIN_ACCESS_MIN} minutes." in desc
    assert f"\n- Conduite : {drive_min} minutes." in desc
    assert (f"\n- Stationnement et marche jusqu'à 'shop' : "
            f"{CERTAIN_EGRESS_MIN} minutes.") in desc


def test_rendu_velo_decompose(certain_terminal):
    """Le vélo change de RENDU sans changer de durée — et c'est voulu (T5).

    Les 2 minutes terminales sont celles que ``park_base`` ajoutait déjà en
    silence : ce ticket les rend visibles, il ne les invente pas. Si les parts
    vélo bougent, ce sera par la seule salience.
    """
    ride_min, terminal_min = 5, CERTAIN_ACCESS_MIN + CERTAIN_EGRESS_MIN
    desc = direct("bicycle", ride_min * 60, distance_m=1400.0).describe()
    assert desc.startswith(f" Temps de trajet : {ride_min + terminal_min} minutes, "
                           f"dont {terminal_min} minutes d'accès et d'attache. "
                           f"Distance : 1.4 km.")
    assert f"\n- Déverrouiller le vélo : {CERTAIN_ACCESS_MIN} minutes." in desc
    assert f"\n- Trajet à vélo : {ride_min} minutes." in desc
    assert f"\n- Attacher le vélo à 'shop' : {CERTAIN_EGRESS_MIN} minutes." in desc


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


def test_distance_conservee_sur_voiture_et_velo(certain_terminal):
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
def test_total_egale_somme_des_sous_etapes(mode, network_s, certain_terminal):
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


def test_forme_courte_reconnait_les_plans_a_trois_jambes(certain_terminal):
    """La requête mémoire doit encore décrire le trajet, pas une liste vide.

    Le test portait sur ``legs | length == 1`` ; un plan voiture en compte trois
    depuis ce ticket et serait tombé dans la branche « List of transits », qui
    n'affiche que les jambes de transport collectif — donc rien.
    """
    total = 3 + CERTAIN_ACCESS_MIN + CERTAIN_EGRESS_MIN
    lite = TravelPlanLiteWrapper(**direct("car", 180).model_dump())
    assert lite.describe() == (f"Direct car; Duration: {total} minutes; "
                               f"Distance: 1.8 km.")


def test_libelle_de_diffusion_sans_destination_connue(certain_terminal):
    """Sans ``purpose``, on ne fabrique pas un nom de destination."""
    desc = direct("car", 180, purpose=None).describe()
    assert (f"Stationnement et marche jusqu'à la destination : "
            f"{CERTAIN_EGRESS_MIN} minutes.") in desc
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


def test_provenance_du_velo_est_sourcee_depuis_tt3():
    """T2 : une valeur sans source doit se déclarer, pas se dissimuler.

    Aucune référence chiffrée n'a été trouvée pour le temps terminal d'un vélo
    personnel ; la valeur reprend celle du code antérieur. L'écrire dans la
    configuration est ce qui empêche de la citer plus tard comme sourcée.
    """
    # tt2 déclarait le vélo `unsourced`, faute de valeur publiée pour le temps
    # terminal d'un vélo PERSONNEL. tt3 en a une : l'enquête le mesure (T2/T6 sur
    # T3 ∈ {11, 17}, 2 047 trajets, 0,11 min par bout). Les deux modes sont donc
    # sourcés — et laisser le vélo non sourcé en face d'une voiture corrigée aurait
    # laissé un biais non documenté contre un biais documenté.
    assert terminal_time.terminal_profile("bicycle").provenance == "sourced"
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
    # Sur l'ESPÉRANCE de la loi : depuis tt3 `egress_s()` tire, et comparer deux
    # tirages ne dirait rien de la mise à l'échelle.
    base = terminal_time.terminal_profile("car")
    ecart_base = (base.mean_s("egress", "Toulouse")
                  - base.mean_s("egress", "3eme couronne"))
    terminal_time.apply_variant("high")
    haut = terminal_time.terminal_profile("car")
    assert haut.mean_s("egress", "Toulouse") > base.mean_s("egress", "Toulouse")
    assert (haut.mean_s("egress", "Toulouse")
            - haut.mean_s("egress", "3eme couronne")) > ecart_base
    # L'invariant des multiples de 60 survit à la mise à l'échelle — y compris sur
    # les CLÉS de la loi, qui sont les durées réellement affichables.
    for zone in ("Toulouse", "1ere couronne", "2eme couronne", "3eme couronne",
                 "default"):
        for laws in (haut.access_law_by_zone, haut.egress_law_by_zone):
            for seconds in (laws.get(zone) or {}):
                assert seconds % 60 == 0, (zone, seconds)


def test_variante_de_sensibilite_change_la_version_de_donnees():
    """Les trois jeux de sensibilité ne doivent pas partager de clé de cache.

    Sans suffixe de version, une éval sous la variante haute lirait le cache de la
    variante centrale : les trois mesures de T6 se confondraient.
    """
    base = terminal_time.data_version()
    terminal_time.apply_variant("high")
    assert terminal_time.data_version() == f"{base}-high"
    # La variante haute majore bien l'espérance centrale (600 s était l'attendu de
    # tt2, où le temps terminal était constant ; sous loi c'est l'espérance qui monte).
    haut = terminal_time.terminal_profile("car")
    terminal_time.reset()
    central = terminal_time.terminal_profile("car")
    assert (haut.mean_s("access", "Toulouse") + haut.mean_s("egress", "Toulouse")
            > central.mean_s("access", "Toulouse")
            + central.mean_s("egress", "Toulouse"))
    terminal_time.apply_variant("high")
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
    def esperance():
        return terminal_time.terminal_profile("car").mean_s("egress", "Toulouse")

    central = esperance()
    terminal_time.apply_variant("low")
    attendu_low = esperance()

    terminal_time.reset()
    terminal_time.apply_variant("high")
    terminal_time.apply_variant("low")
    assert esperance() == pytest.approx(attendu_low)
    assert attendu_low < central  # et la variante basse reste bien basse

    # Idem dans l'autre sens, et le retour à `central` rend les valeurs de base.
    terminal_time.apply_variant("central")
    assert esperance() == pytest.approx(central)


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
    # ⚠ Depuis tt3 la durée est TIRÉE : comparer `access_s()` comparerait deux
    # tirages, pas deux couronnes. Le gradient s'exprime sur l'ESPÉRANCE de la loi.
    p = terminal_time.terminal_profile("car")
    assert p.spatialise is True
    assert (p.mean_s("access", "Toulouse") > p.mean_s("access", "1ere couronne")
            and p.mean_s("access", "2eme couronne")
            > p.mean_s("access", "3eme couronne"))
    assert (p.mean_s("egress", "Toulouse") > p.mean_s("egress", "1ere couronne")
            and p.mean_s("egress", "2eme couronne")
            > p.mean_s("egress", "3eme couronne"))


def test_zone_inconnue_retombe_sur_le_defaut():
    """Un point hors couche EMC² ne doit pas faire disparaître le temps terminal.

    ``residence_zone`` rend une chaîne vide pour un point inconnu. Sans entrée
    ``default``, la table serait consultée à vide — et le mode redeviendrait gratuit,
    c'est-à-dire le bug que ce ticket corrige, ressuscité par un trou de zonage.
    """
    p = terminal_time.terminal_profile("car")
    # La loi `default` est servie pour toute couronne inconnue, et son espérance est
    # non nulle : un trou de zonage ne rend pas la voiture gratuite. On teste
    # l'espérance et non un tirage — un tirage vaut 0 dans ~92 % des cas, ce qui est
    # le comportement voulu et ne dit rien du repli.
    assert p.mean_s("access", "") == p.mean_s("access", "default")
    assert p.mean_s("egress", "zone inexistante") == p.mean_s("egress", "default")
    assert p.mean_s("access", "") > 0 and p.mean_s("egress", "") > 0


def test_les_deux_bouts_sont_tarifes_separement():
    """Accès sur la couronne d'ORIGINE, stationnement sur celle de DESTINATION."""
    from trip_helper.osmnx_direct import _make_travel_plan

    vers_centre = _wrap(_make_travel_plan(ZONE_LOINTAINE, ORIGIN, "car", T0, 180, 1800.0))
    vers_peripherie = _wrap(_make_travel_plan(ORIGIN, ZONE_LOINTAINE, "car", T0, 180, 1800.0))
    # Aller au centre coûte plus cher qu'en partir : le stationnement domine. En
    # ESPÉRANCE — un couple de tirages ne prouverait rien, la loi étant massée à zéro.
    p = terminal_time.terminal_profile("car")
    attendu_centre = (p.mean_s("access", "2eme couronne")
                      + p.mean_s("egress", "Toulouse"))
    attendu_peripherie = (p.mean_s("access", "Toulouse")
                          + p.mean_s("egress", "2eme couronne"))
    assert attendu_centre > attendu_peripherie
    # Et le total reste la somme des sous-étapes affichées.
    for plan in (vers_centre, vers_peripherie):
        assert plan.total_seconds // 60 == sum(s // 60 for _, s in plan.described_steps)


def test_les_deux_classements_sont_desormais_distincts():
    """Ce test disait l'inverse jusqu'au ticket 021, et son inversion EST la décision.

    Il exigeait que `move_logger` et le temps terminal classent identiquement. Mais les
    deux ne classent pas le même objet : le journal classe une PERSONNE par sa commune
    de résidence — la définition de l'enquête —, le temps terminal classe un POINT
    d'origine ou de destination par sa distance à l'hypercentre. Vouloir une définition
    unique revenait à imposer la métrique à la résidence, ce que le ticket 020 a chiffré :
    24,4 % de personas comparés à la cible d'une autre zone.

    Ce qui est verrouillé ici, c'est donc l'inverse : le journal ne recalcule plus rien,
    il LIT le trait du persona, et il n'a même plus accès à la fonction métrique. La
    divergence est bornée à 34 s par bout de trajet (cf. le docstring de
    `geo_reference.residence_zone`) et documentée ; la refermer exige de ré-exporter
    `terminal_time_emc2.json`, pas de rétablir un import.
    """
    import urban_mobility_agents.utils.move_logger as move_logger
    from llm_module.core.geo_reference import residence_zone

    # Le temps terminal, lui, continue de classer par distance : c'est ce que ses lois
    # attendent, et le ticket 021 n'y touche pas.
    assert residence_zone(43.5973, 1.4450) == "Toulouse"
    assert residence_zone(43.40, 1.10) == "2eme couronne"   # ~35 km du Capitole
    assert residence_zone(43.10, 1.10) == "3eme couronne"   # ~64 km

    # Le journal lit le trait, et rien d'autre.
    assert move_logger._residence_zone({"residence_zone": "1ere couronne"}) == "1ere couronne"
    assert move_logger._residence_zone({}) == ""

    # Et le repli à la distance est IMPOSSIBLE, pas seulement déconseillé : le module
    # n'importe plus la fonction métrique. Sans ce contrôle, un « repli raisonnable »
    # reviendrait en une ligne à la première relecture distraite.
    assert not hasattr(move_logger, "residence_zone")


# ── tt3 : le temps terminal est TIRÉ dans la loi d'enquête ───────────────────

def test_la_loi_remplace_la_constante_quand_elle_est_servie():
    """Une loi présente fait foi ; la constante n'est plus consultée.

    Les deux mécanismes coexistent volontairement — un mode futur peut rester sur
    constante — mais ils ne doivent pas se mélanger : servir les deux et lire la
    constante rendrait le fichier de config trompeur.
    """
    profile = terminal_time.TerminalProfile(
        mode="car", access_by_zone={"default": 999 * 60},
        egress_by_zone={"default": 999 * 60}, provenance="sourced",
        spatialise=False, labels={},
        access_law_by_zone={"default": {120: 1.0}},
        egress_law_by_zone={"default": {180: 1.0}})
    assert profile.access_s("", "k") == 120
    assert profile.egress_s("", "k") == 180
    assert profile.mean_s("access") == 120


def test_sans_loi_la_constante_fait_foi():
    """Rétrocompatibilité : un mode sur table constante garde son comportement tt2."""
    profile = terminal_time.TerminalProfile(
        mode="car", access_by_zone={"default": 120}, egress_by_zone={"default": 180},
        provenance="sourced", spatialise=False, labels={})
    assert profile.access_s("", "k") == 120
    assert profile.egress_s("zone inconnue", "k") == 180


def test_le_tirage_est_deterministe_par_trajet():
    """Le même trajet tire toujours pareil — les plans et les décisions LLM sont mis
    en cache, un tirage instable ferait diverger un run de sa reprise."""
    profile = terminal_time.TerminalProfile(
        mode="car", access_by_zone={"default": 0}, egress_by_zone={"default": 0},
        provenance="sourced", spatialise=False, labels={},
        access_law_by_zone={"default": {0: 0.5, 300: 0.5}},
        egress_law_by_zone={"default": {0: 0.5, 300: 0.5}})
    for key in ("a", "b", "trajet:43.6,1.4→43.7,1.5"):
        assert profile.access_s("", key) == profile.access_s("", key)


def test_deux_trajets_tirent_independamment():
    """Sinon tous les trajets d'une couronne recevraient la même valeur, et la loi
    ne servirait à rien."""
    profile = terminal_time.TerminalProfile(
        mode="car", access_by_zone={"default": 0}, egress_by_zone={"default": 0},
        provenance="sourced", spatialise=False, labels={},
        access_law_by_zone={"default": {0: 0.5, 300: 0.5}},
        egress_law_by_zone={"default": {0: 0.5, 300: 0.5}})
    drawn = {profile.access_s("", f"trajet-{i}") for i in range(50)}
    assert drawn == {0, 300}


def test_les_deux_bouts_tirent_independamment():
    """Accès et diffusion ne doivent pas être corrélés à 1 : le temps terminal
    porterait alors une seule source de variation au lieu de deux."""
    profile = terminal_time.TerminalProfile(
        mode="car", access_by_zone={"default": 0}, egress_by_zone={"default": 0},
        provenance="sourced", spatialise=False, labels={},
        access_law_by_zone={"default": {0: 0.5, 300: 0.5}},
        egress_law_by_zone={"default": {0: 0.5, 300: 0.5}})
    pairs = {(profile.access_s("", f"t{i}"), profile.egress_s("", f"t{i}"))
             for i in range(200)}
    assert len(pairs) == 4, pairs


def test_le_tirage_suit_la_loi():
    profile = terminal_time.TerminalProfile(
        mode="car", access_by_zone={"default": 0}, egress_by_zone={"default": 0},
        provenance="sourced", spatialise=False, labels={},
        access_law_by_zone={"default": {0: 0.9, 600: 0.1}},
        egress_law_by_zone={"default": {0: 1.0}})
    zeros = sum(profile.access_s("", f"t{i}") == 0 for i in range(4000))
    assert 0.86 < zeros / 4000 < 0.94, zeros / 4000


def test_config_refuse_une_loi_qui_ne_somme_pas_a_un(tmp_path):
    """Une loi qui ne somme pas à 1 fait taire une partie de la masse sans le dire."""
    _write_config(tmp_path, {"version": "x", "routing_version": "r",
                             "modes": {"car": {"access_law": {"default": {0: 0.5}},
                                               "egress_law": {"default": {0: 1.0}},
                                               "labels": _LABELS}}})
    with pytest.raises(ValueError, match="somme à"):
        terminal_time.terminal_profile("car")


def test_config_refuse_une_loi_vide(tmp_path):
    """Tirer dans une loi vide rendrait 0 — plausible, donc indétectable."""
    _write_config(tmp_path, {"version": "x", "routing_version": "r",
                             "modes": {"car": {"access_law": {"default": {}},
                                               "egress_law": {"default": {0: 1.0}},
                                               "labels": _LABELS}}})
    with pytest.raises(ValueError, match="vide"):
        terminal_time.terminal_profile("car")


def test_config_refuse_une_loi_sans_default(tmp_path):
    """Une zone hors couche EMC² tomberait dans le vide, et le mode redeviendrait
    gratuit — le bug même que le ticket 013 corrige."""
    _write_config(tmp_path, {"version": "x", "routing_version": "r",
                             "modes": {"car": {"access_law": {"Toulouse": {0: 1.0}},
                                               "egress_law": {"default": {0: 1.0}},
                                               "labels": _LABELS}}})
    with pytest.raises(ValueError, match="default"):
        terminal_time.terminal_profile("car")


def test_la_config_de_production_est_alignee_sur_lenquete():
    """Garde-fou d'alignement : les espérances servies doivent rester celles de
    l'enquête (0,55 min pour la voiture, 0,22 pour le vélo, tous bouts confondus).

    Sans lui, une régression vers les valeurs tt2 (2 à 10 min) passerait inaperçue —
    et c'est exactement la régression qui a coûté 2 points de composite au run du
    2026-08-21.
    """
    car = terminal_time.terminal_profile("car")
    bike = terminal_time.terminal_profile("bicycle")
    total_car = (car.mean_s("access", "Toulouse")
                 + car.mean_s("egress", "Toulouse")) / 60
    total_bike = (bike.mean_s("access") + bike.mean_s("egress")) / 60
    assert 0.5 < total_car < 1.5, total_car      # Toulouse, la couronne la plus chère
    assert 0.1 < total_bike < 0.5, total_bike
    assert car.provenance == "sourced" and bike.provenance == "sourced"
