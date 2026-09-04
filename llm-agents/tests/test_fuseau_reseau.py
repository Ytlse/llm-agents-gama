"""L'heure demandée aux moteurs de routage est l'heure MURALE de GAMA (2026-09-04).

Le défaut corrigé : `GAMA/CityTransport/models/Settings.gaml` publie son horloge comme
`int(current_date - UTC_START_DATE)`, une différence de deux dates **naïves** — donc une
heure murale locale encodée comme si elle était UTC (1773637200 pour lundi 16 mars 2026
5 h). Le runtime la lisait avec `datetime.fromtimestamp(...)`, sans fuseau, donc dans
celui du **processus** : sous `TZ=Europe/Paris`, 5 h murales étaient demandées à OTP comme
**6 h locales**, et le facteur de congestion tarifé à 6 h lui aussi.

Ce que ça coûtait, mesuré sur les 2 580 points de la population scellée v4
(`docs/traces/2026-09-04_13-15_fuseau_otp/`) : **235** points sans itinéraire TC à
l'heure demandée contre **605** à l'heure des agents. Le biais valait une heure en mars
et **deux** pour une journée simulée en été — il n'était même pas constant.

Ces tests échouent si la convention rechange : ils vérifient l'heure à la seconde près,
en hiver ET en été, l'égalité entre tous les consommateurs de `departure_time`,
l'indépendance au `TZ` du processus, et le refus explicite quand le fuseau n'a pas de
source (une heure devinée serait un résultat plausible tiré d'une donnée absente).
"""

import asyncio
import calendar
import itertools
import os
import time
from datetime import datetime, timezone

import pytest

import sim_clock
from models import Location
from trip_helper.osmnx_persistent_cache import OsmnxPersistentCache
from trip_helper.otp import OTPTripHelper
from trip_helper.otp_persistent_cache import OtpPersistentCache
from settings import settings


def _gama_ts(annee, mois, jour, heure, minute=0, seconde=0) -> int:
    """L'horodatage que GAMA publie pour une heure MURALE donnée.

    Reproduit `int(current_date - UTC_START_DATE)` : une différence de dates naïves,
    soit l'heure murale comptée comme si elle était UTC.
    """
    return int(calendar.timegm((annee, mois, jour, heure, minute, seconde, 0, 0, 0)))


# Lundi 16 mars 2026, 5 h murales — le t0 de `starting_date` dans Settings.gaml, et la
# valeur relevée dans la colonne « Temps simulé » de moves.csv.
TS_HIVER = 1773637200
# Lundi 13 juillet 2026, 5 h murales — heure d'été, où l'écart valait DEUX heures.
TS_ETE = _gama_ts(2026, 7, 13, 5)

ORIGIN = Location(lat=43.6045, lon=1.4440, public_transport=True)
DEST = Location(lat=43.5710, lon=1.4020, public_transport=True)


@pytest.fixture(autouse=True)
def _horloge_propre():
    """Le fuseau est résolu une fois et mis en cache : chaque test repart à zéro."""
    sim_clock.reset_cache()
    yield
    sim_clock.reset_cache()


def test_lhorodatage_de_gama_est_une_heure_murale():
    """Le témoin de l'énoncé : 1773637200 EST lundi 16 mars 2026 5 h murales."""
    assert TS_HIVER == _gama_ts(2026, 3, 16, 5)
    assert sim_clock.wall_clock(TS_HIVER) == datetime(2026, 3, 16, 5, 0, 0)
    assert sim_clock.wall_clock(TS_ETE) == datetime(2026, 7, 13, 5, 0, 0)


def test_lheure_demandee_a_otp_egale_lheure_murale_de_gama_hiver_et_ete():
    """Décalage résiduel nul, à la seconde près, des deux côtés du changement d'heure.

    C'est la mesure demandée : l'heure murale de GAMA et l'heure locale reçue par OTP
    doivent être la même, en hiver (+01:00) comme en été (+02:00).
    """
    for ts in (TS_HIVER, TS_ETE):
        demande = datetime.fromisoformat(sim_clock.network_iso(ts))
        mur = sim_clock.wall_clock(ts)
        assert demande.replace(tzinfo=None) == mur, ts
        # Et le décalage porté est bien celui de la saison : la même heure murale
        # n'est pas le même instant en mars et en juillet.
        assert demande.utcoffset().total_seconds() == (3600 if ts == TS_HIVER else 7200)

    assert sim_clock.network_iso(TS_HIVER) == "2026-03-16T05:00:00+01:00"
    assert sim_clock.network_iso(TS_ETE) == "2026-07-13T05:00:00+02:00"


def test_lancienne_convention_demandait_une_heure_de_trop():
    """Garde-fou de non-retour : la lecture sans fuseau reste fausse, et de combien.

    Sans ce test, revenir à `datetime.fromtimestamp(ts)` ne casserait rien tant que la
    machine de test tourne en UTC — c'est précisément l'asymétrie qui a laissé passer
    le défaut (`otp_link_check.py` interrogeait OTP en heure locale, le runtime non).
    """
    ancien_tz = os.environ.get("TZ")
    try:
        os.environ["TZ"] = "Europe/Paris"
        time.tzset()
        assert datetime.fromtimestamp(TS_HIVER).hour == 6   # une heure de trop
        assert datetime.fromtimestamp(TS_ETE).hour == 7     # deux heures de trop
        # Et l'ancien `dateTime` : l'heure murale estampillée UTC, qu'OTP traduisait
        # dans le fuseau de son réseau (donc 06:00 puis 07:00 locales).
        assert datetime.fromtimestamp(TS_HIVER, tz=timezone.utc).isoformat() == \
            "2026-03-16T05:00:00+00:00"
    finally:
        if ancien_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = ancien_tz
        time.tzset()


@pytest.mark.parametrize("tz_processus", ["UTC", "Europe/Paris", "America/Los_Angeles",
                                          "Pacific/Kiritimati"])
def test_le_fuseau_vient_de_la_configuration_pas_du_processus(tz_processus):
    """Un conteneur mal configuré ne doit pas déplacer les itinéraires.

    Les réplicas `osmnx` tournent en UTC, le `controller` en Europe/Paris et le
    peupleur sur l'hôte : trois lectures d'un même entier, trois heures différentes.
    """
    ancien_tz = os.environ.get("TZ")
    try:
        os.environ["TZ"] = tz_processus
        time.tzset()
        sim_clock.reset_cache()
        assert sim_clock.network_iso(TS_HIVER) == "2026-03-16T05:00:00+01:00"
        assert sim_clock.network_iso(TS_ETE) == "2026-07-13T05:00:00+02:00"
        assert sim_clock.wall_clock(TS_HIVER) == datetime(2026, 3, 16, 5, 0, 0)
    finally:
        if ancien_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = ancien_tz
        time.tzset()


# ── D'où vient le fuseau ─────────────────────────────────────────────────────

def _feed(repertoire, nom, fuseau):
    """Un feed GTFS minimal : `stops.txt` (pour être vu en service) + `agency.txt`."""
    feed = repertoire / nom
    feed.mkdir(parents=True)
    (feed / "stops.txt").write_text("stop_id,stop_lat,stop_lon\nA,43.6,1.44\n", encoding="utf-8")
    if fuseau is not None:
        (feed / "agency.txt").write_text(
            f"agency_id,agency_name,agency_timezone\n1,Test,{fuseau}\n", encoding="utf-8")
    return feed


def test_le_fuseau_est_lu_dans_le_feed_gtfs(tmp_path, monkeypatch):
    """La source est l'`agency_timezone` du feed, pas un littéral dans le code.

    C'est la seule source qui ne peut pas s'écarter d'OTP : c'est celle qu'OTP lui-même
    utilise pour interpréter les horaires du réseau. Ce test le prouve en déplaçant le
    réseau à New York — un « Europe/Paris » codé en dur le ferait échouer.
    """
    feed = _feed(tmp_path / "build", "reseau_gtfs", "America/New_York")
    monkeypatch.setattr(settings.gtfs, "gtfs_file", str(feed))
    monkeypatch.setattr(settings.gtfs, "network_timezone", None)
    sim_clock.reset_cache()
    assert sim_clock.network_timezone_name() == "America/New_York"
    # 5 h murales à New York, mi-mars : heure d'été américaine, décalage −04:00.
    assert sim_clock.network_iso(TS_HIVER) == "2026-03-16T05:00:00-04:00"


def test_les_trois_feeds_de_production_declarent_le_meme_fuseau():
    """Tisséo, liO et le TER annuel : `Europe/Paris` dans les trois `agency.txt`."""
    monkeypatched = getattr(settings.gtfs, "network_timezone", None)
    assert monkeypatched is None, "le réglage de production doit rester la lecture du feed"
    assert sim_clock.network_timezone_name() == "Europe/Paris"


def test_le_reglage_explicite_prime_sur_le_feed(tmp_path, monkeypatch):
    """L'échappatoire documentée, pour un feed absent du service ou contradictoire."""
    feed = _feed(tmp_path / "build", "reseau_gtfs", "America/New_York")
    monkeypatch.setattr(settings.gtfs, "gtfs_file", str(feed))
    monkeypatch.setattr(settings.gtfs, "network_timezone", "Europe/Lisbon")
    sim_clock.reset_cache()
    assert sim_clock.network_timezone_name() == "Europe/Lisbon"
    assert sim_clock.network_iso(TS_HIVER) == "2026-03-16T05:00:00+00:00"


def test_deux_feeds_qui_se_contredisent_refusent(tmp_path, monkeypatch):
    """En choisir un au hasard décalerait les horaires d'un réseau entier."""
    build = tmp_path / "build"
    _feed(build, "a_gtfs", "Europe/Paris")
    feed_b = _feed(build, "b_gtfs", "America/New_York")
    monkeypatch.setattr(settings.gtfs, "gtfs_file", str(feed_b))
    monkeypatch.setattr(settings.gtfs, "network_timezone", None)
    sim_clock.reset_cache()
    with pytest.raises(sim_clock.NetworkTimezoneError, match="contradictoires"):
        sim_clock.network_timezone()


def test_sans_feed_lisible_la_conversion_refuse(tmp_path, monkeypatch):
    """L'absence de mesure ne produit pas un résultat plausible.

    Un repli sur « Europe/Paris » rendrait la bonne heure ici et la mauvaise ailleurs,
    sans aucun signal — exactement la forme du défaut corrigé.
    """
    feed = _feed(tmp_path / "build", "reseau_gtfs", None)  # stops.txt mais pas d'agency
    monkeypatch.setattr(settings.gtfs, "gtfs_file", str(feed))
    monkeypatch.setattr(settings.gtfs, "network_timezone", None)
    sim_clock.reset_cache()
    with pytest.raises(sim_clock.NetworkTimezoneError, match="agency_timezone"):
        sim_clock.network_timezone()


def test_un_fuseau_inconnu_de_la_base_iana_refuse(tmp_path, monkeypatch):
    monkeypatch.setattr(settings.gtfs, "network_timezone", "Mars/Olympus_Mons")
    sim_clock.reset_cache()
    with pytest.raises(sim_clock.NetworkTimezoneError, match="fuseau inconnu"):
        sim_clock.network_timezone()


# ── Ce que reçoivent réellement les deux moteurs ─────────────────────────────

class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    def raise_for_status(self):
        return None

    async def json(self):
        return self._payload


class _FakeSession:
    """Capture le corps POSTé vers OTP au lieu de l'envoyer."""

    def __init__(self, reponse):
        self.reponse = reponse
        self.corps = []

    def post(self, url, json=None, timeout=None):
        self.corps.append(json)
        return _FakeResponse(self.reponse)


def _helper(session, fixed_day=None):
    """Un `OTPTripHelper` sans GTFS ni réseau : seule la construction de la requête
    est sous test, et `GTFSData.DEFAULT()` coûterait plusieurs secondes de lecture."""
    h = object.__new__(OTPTripHelper)
    h.fixed_day = fixed_day
    h._endpoint_iter = itertools.cycle(["http://otp/otp/transmodel/v3"])
    h._semaphore = asyncio.Semaphore(4)
    h._session = None
    h.gtfs_data = None
    h._stop_coords = None

    async def _get_session():
        return session

    h.get_session = _get_session
    return h


_AUCUN_MOTIF = {"data": {"trip": {"tripPatterns": []}}}


@pytest.mark.parametrize("ts,attendu", [(TS_HIVER, "2026-03-16T05:00:00+01:00"),
                                        (TS_ETE, "2026-07-13T05:00:00+02:00")])
def test_le_datetime_envoye_a_otp_porte_lheure_murale_de_gama(ts, attendu):
    """Le `dateTime` de la requête GraphQL, tel qu'OTP le reçoit."""
    session = _FakeSession(_AUCUN_MOTIF)
    helper = _helper(session)
    asyncio.run(helper.get_itineraries(ORIGIN, DEST, ts, include_direct=False))
    assert len(session.corps) == 1
    assert session.corps[0]["variables"]["dateTime"] == attendu


@pytest.mark.parametrize("ts,heure,jour", [(TS_HIVER, 5, "Mon"), (TS_ETE, 5, "Mon")])
def test_la_congestion_est_lue_a_la_meme_heure_que_otp(monkeypatch, ts, heure, jour):
    """Un seul horaire pour les deux moteurs.

    Le facteur TomTom est tabulé par jour de la semaine et heure pleine
    (`osmnx_direct._zone_factor`) : lu une heure trop tard, il tarifait la pointe du
    matin sur un trajet qui part avant elle. Et la clé du cache de routage porte ce
    même créneau, donc l'erreur se mémorisait.
    """
    vus = []

    async def _fake_direct(origin, destination, trip_mode, departure_time, congestion_dt,
                           _timing_sink=None):
        vus.append((trip_mode, departure_time, congestion_dt))
        return None

    monkeypatch.setattr("trip_helper.otp.get_direct_plan", _fake_direct)
    session = _FakeSession(_AUCUN_MOTIF)
    helper = _helper(session)
    asyncio.run(helper.get_itineraries(ORIGIN, DEST, ts, include_direct=True,
                                       include_car=True, include_transit=False))

    assert vus, "aucun appel OSMnx capté"
    for trip_mode, departure_time, congestion_dt in vus:
        assert departure_time == ts, trip_mode
        assert congestion_dt.hour == heure, trip_mode
        assert congestion_dt.strftime("%a") == jour, trip_mode
        # L'instant est conscient du fuseau du réseau : la ligne de cache et le
        # journal disent quelle heure a été tarifée, pas seulement laquelle il était
        # dans le processus. Et c'est EXACTEMENT l'instant envoyé à OTP.
        assert congestion_dt.tzinfo is not None, trip_mode
        assert congestion_dt.replace(tzinfo=None) == sim_clock.wall_clock(ts)
        assert congestion_dt.isoformat() == sim_clock.network_iso(ts), trip_mode


def _motif(depart_iso, arrivee_iso):
    place_o = {"name": "Origin", "latitude": ORIGIN.lat, "longitude": ORIGIN.lon}
    place_d = {"name": "Destination", "latitude": DEST.lat, "longitude": DEST.lon}
    leg = {"mode": "foot", "aimedStartTime": depart_iso, "aimedEndTime": arrivee_iso,
           "expectedStartTime": depart_iso, "expectedEndTime": arrivee_iso,
           "realtime": False, "distance": 900.0, "duration": 720,
           "fromPlace": place_o, "toPlace": place_d}
    return {"data": {"trip": {"tripPatterns": [{
        "aimedStartTime": depart_iso, "aimedEndTime": arrivee_iso,
        "expectedStartTime": depart_iso, "expectedEndTime": arrivee_iso,
        "duration": 720, "distance": 900.0, "legs": [leg], "systemNotices": []}]}}}


@pytest.mark.parametrize("ts,depart,arrivee", [
    (TS_HIVER, "2026-03-16T05:12:00+01:00", "2026-03-16T05:24:00+01:00"),
    (TS_ETE, "2026-07-13T05:12:00+02:00", "2026-07-13T05:24:00+02:00"),
])
def test_les_horaires_rendus_par_otp_reviennent_dans_lhorloge_de_gama(ts, depart, arrivee):
    """Le retour compte autant que l'aller.

    GAMA n'a pas d'instants : ses horaires sont muraux. Un plan dont les horaires
    resteraient en epoch réel donnerait un `start_in` faux du décalage du fuseau — des
    options « partant 55 minutes dans le passé » en hiver, 1 h 48 en été — et des
    jambes poussées à GAMA une heure à côté de son propre `CURRENT_TIMESTAMP`.
    """
    session = _FakeSession(_motif(depart, arrivee))
    helper = _helper(session)
    plans = asyncio.run(helper.get_itineraries(ORIGIN, DEST, ts, include_direct=False))

    assert len(plans) == 1
    plan = plans[0]
    assert plan.start_time // 1000 == ts + 12 * 60      # 12 min après le départ demandé
    assert plan.end_time // 1000 == ts + 24 * 60
    assert plan.start_in == 12 * 60
    # Et l'heure murale du plan est celle qu'OTP a écrite.
    assert sim_clock.wall_clock(plan.start_time // 1000).strftime("%H:%M") == "05:12"


def test_le_remappage_fixed_day_reste_dans_lhorloge_de_gama(monkeypatch):
    """`gtfs.fixed_day` reconstruit un horodatage GAMA, pas un instant réel.

    `self.fixed_day.replace(...).timestamp()` passait par le fuseau du processus : le
    remappage cumulait donc son propre décalage à celui de la requête.
    """
    session = _FakeSession(_AUCUN_MOTIF)
    helper = _helper(session, fixed_day=datetime(2026, 3, 16))
    asyncio.run(helper.get_itineraries(ORIGIN, DEST, TS_ETE, include_direct=False))
    # 5 h murales du 13 juillet, replacées au 16 mars : 5 h murales, +01:00.
    assert session.corps[0]["variables"]["dateTime"] == "2026-03-16T05:00:00+01:00"


def test_le_remappage_fixed_day_rend_les_horaires_au_jour_reel():
    """Et le chemin de retour du remappage : `real_day - fixed_day` en jours.

    `real_day` dérive de `congestion_dt`, désormais CONSCIENT du fuseau, alors que
    `fixed_day` est naïf : soustraire l'un de l'autre lèverait un `TypeError`. Ce
    test parcourt la branche complète, que `gtfs.fixed_day: null` laisse muette en
    production.
    """
    session = _FakeSession(_motif("2026-03-16T05:12:00+01:00", "2026-03-16T05:24:00+01:00"))
    helper = _helper(session, fixed_day=datetime(2026, 3, 16))
    plans = asyncio.run(helper.get_itineraries(ORIGIN, DEST, TS_ETE, include_direct=False))

    assert len(plans) == 1
    # Le plan est rendu au jour RÉEL (13 juillet), à l'heure murale qu'OTP a écrite.
    assert sim_clock.wall_clock(plans[0].start_time // 1000) == datetime(2026, 7, 13, 5, 12)


# ── Les caches ───────────────────────────────────────────────────────────────

def test_la_cle_du_cache_de_routage_suit_lheure_murale():
    """`OsmnxPersistentCache` indexe le créneau du facteur de congestion.

    L'heure murale et l'heure lue doivent coïncider : sinon une durée tarifée à 6 h est
    rangée sous « 6 h » alors qu'elle répond à un départ de 5 h, et la ligne ne dit pas
    laquelle des deux elle décrit.
    """
    _, date_str, dow, bucket = OsmnxPersistentCache.make_key(
        sim_clock.to_network_datetime(TS_HIVER), "car", 43.6045, 1.4440, 43.5710, 1.4020)
    assert (date_str, dow, bucket) == ("2026-03-16", 0, "05:00")

    _, date_ete, dow_ete, bucket_ete = OsmnxPersistentCache.make_key(
        sim_clock.to_network_datetime(TS_ETE), "car", 43.6045, 1.4440, 43.5710, 1.4020)
    assert (date_ete, dow_ete, bucket_ete) == ("2026-07-13", 0, "05:00")


def test_la_cle_du_cache_otp_porte_linstant_avec_son_decalage():
    """Ce qui rend l'ancienne génération inatteignable, sans purge manuelle.

    Ce cache mémorise des `TravelPlan` sérialisés et les DÉCALE au réemploi
    (`lookup` → `departure_time - stored_departure_time`). Une entrée rangée sous
    l'étiquette « 06:00 » alors qu'elle répondait à un départ de 5 h murales serait
    resservie à un départ de 6 h murales, puis décalée d'une heure de plus. Ni
    `data_version()` ni `routing_version` ne l'en empêchaient : la clé doit porter
    l'instant, décalage compris.
    """
    cle_hiver = OtpPersistentCache.make_key(TS_HIVER, ORIGIN, DEST, False, False, True)
    cle_ete = OtpPersistentCache.make_key(TS_ETE, ORIGIN, DEST, False, False, True)
    assert cle_hiver != cle_ete

    # La même heure murale une heure plus tard est une AUTRE entrée…
    cle_six_heures = OtpPersistentCache.make_key(
        TS_HIVER + 3600, ORIGIN, DEST, False, False, True)
    assert cle_six_heures != cle_hiver

    # …et l'ancienne convention (date et heure nues, lues dans le fuseau du processus)
    # ne peut plus produire aucune de ces clés : la forme de la chaîne a changé.
    import hashlib

    from trip_helper.terminal_time import data_version

    ancien = (f"{data_version()}|2026-03-16|06:00|{ORIGIN.lat:.5f}|{ORIGIN.lon:.5f}"
              f"|{DEST.lat:.5f}|{DEST.lon:.5f}|0|0|1")
    assert hashlib.sha256(ancien.encode()).hexdigest() not in (cle_hiver, cle_six_heures)

    # La tranche de 10 min reste la granularité du cache (elle était déjà documentée).
    assert OtpPersistentCache.make_key(TS_HIVER + 120, ORIGIN, DEST, False, False, True) \
        == cle_hiver


# ── Changement d'heure : dit, jamais deviné ──────────────────────────────────

def test_lheure_murale_inexistante_est_alarmee():
    """La journée murale du passage à l'heure d'été compte 24 h, la réalité 23.

    2 h 30 le 29 mars 2026 n'existe pas en Europe/Paris. La conversion continue sur
    `fold=0` — un choix annoncé — mais elle le DIT : sans cette ligne, l'itinéraire
    d'une heure qui n'existe pas serait rendu comme n'importe quel autre.
    """
    from loguru import logger as _loguru

    messages = []
    sink = _loguru.add(lambda m: messages.append(m.record["message"]), level="ERROR")
    try:
        sim_clock.to_network_datetime(_gama_ts(2026, 3, 29, 2, 30))
    finally:
        _loguru.remove(sink)
    assert any("[ALARME]" in m and "n'existe pas" in m for m in messages), messages


def test_lheure_murale_ambigue_est_alarmee():
    """2 h 30 le 25 octobre 2026 existe deux fois : la première est retenue, et dite."""
    from loguru import logger as _loguru

    messages = []
    sink = _loguru.add(lambda m: messages.append(m.record["message"]), level="ERROR")
    try:
        sim_clock.to_network_datetime(_gama_ts(2026, 10, 25, 2, 30))
    finally:
        _loguru.remove(sink)
    assert any("[ALARME]" in m and "DEUX fois" in m for m in messages), messages


def test_lalarme_de_bascule_se_leve_sur_front_montant():
    """Une journée simulée compte des milliers de trajets : une alarme, pas un flot."""
    from loguru import logger as _loguru

    messages = []
    sink = _loguru.add(lambda m: messages.append(m.record["message"]), level="ERROR")
    try:
        for minute in range(0, 60, 5):
            sim_clock.to_network_datetime(_gama_ts(2026, 3, 29, 2, minute))
    finally:
        _loguru.remove(sink)
    assert len([m for m in messages if "n'existe pas" in m]) == 1, messages
