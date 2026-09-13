"""Une paire sans transport en commun à 5 h du matin n'est pas une paire sans transport.

La liste noire d'OTP évite de rappeler le routeur pour une paire dont on sait qu'il ne rend
rien. Sa clé ne portait que les coordonnées, alors que `cached_triphelper` la remplit dès que le
résultat est **vide**, motif compris — et `noTransitConnectionInSearchWindow` est horaire :
mesuré le 2026-09-04, 29 points sans itinéraire à 6 h contre **341 à 5 h** sur les mêmes 2 580.
Une paire noircie au petit matin rendait donc « aucun transport en commun » à 17 h, sans appel
et sans journal — et les vagues de pré-planification interrogent la même paire à des heures
successives, donc le défaut se déclenchait dans un seul run.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models import Location  # noqa: E402
from trip_helper.otp_persistent_cache import OtpPersistentCache  # noqa: E402

_O = Location(lat=43.6045, lon=1.4440)
_D = Location(lat=43.5290, lon=1.3270)
# 2026-03-16, horloge murale de GAMA (naïf-comme-UTC) : 5 h, 6 h, 17 h.
_5H, _6H, _17H = 1773637200, 1773640800, 1773680400


def test_deux_heures_differentes_donnent_deux_cles():
    assert (OtpPersistentCache.make_blacklist_key(_O, _D, _5H)
            != OtpPersistentCache.make_blacklist_key(_O, _D, _17H))


def test_la_meme_heure_donne_la_meme_cle():
    assert (OtpPersistentCache.make_blacklist_key(_O, _D, _5H)
            == OtpPersistentCache.make_blacklist_key(_O, _D, _5H))


def test_le_creneau_est_de_dix_minutes_comme_le_cache_de_plans():
    """Deux départs de la même dizaine de minutes partagent la clé : c'est ce qui fait
    encore économiser des appels à l'intérieur d'une vague de pré-planification."""
    assert (OtpPersistentCache.make_blacklist_key(_O, _D, _5H)
            == OtpPersistentCache.make_blacklist_key(_O, _D, _5H + 599))
    assert (OtpPersistentCache.make_blacklist_key(_O, _D, _5H)
            != OtpPersistentCache.make_blacklist_key(_O, _D, _5H + 601))


def test_le_sens_du_trajet_compte():
    assert (OtpPersistentCache.make_blacklist_key(_O, _D, _5H)
            != OtpPersistentCache.make_blacklist_key(_D, _O, _5H))


def test_sans_heure_la_cle_ne_collisionne_pas_avec_une_cle_horaire():
    """Un appelant sans heure garde une clé de topologie, mais elle est marquée : les deux
    familles ne doivent pas se mélanger, sinon une entrée sans heure masquerait toutes les
    heures — le défaut qu'on ferme."""
    sans = OtpPersistentCache.make_blacklist_key(_O, _D)
    assert sans != OtpPersistentCache.make_blacklist_key(_O, _D, _5H)
    assert sans == OtpPersistentCache.make_blacklist_key(_O, _D)


def test_une_paire_noircie_a_cinq_heures_est_rejouee_a_dix_sept(tmp_path):
    """Le comportement de bout en bout, sur une vraie base."""
    cache = OtpPersistentCache(str(tmp_path))
    k5 = OtpPersistentCache.make_blacklist_key(_O, _D, _5H)
    k17 = OtpPersistentCache.make_blacklist_key(_O, _D, _17H)

    cache.blacklist_add(k5)

    assert cache.is_blacklisted(k5), "la paire reste noircie à son heure"
    assert not cache.is_blacklisted(k17), "mais elle est réinterrogée à une autre heure"


def test_l_heure_est_celle_du_reseau_pas_celle_du_processus(monkeypatch):
    """La clé passe par `sim_clock`, donc par le fuseau des feeds GTFS : le `TZ` du
    processus ne doit pas la déplacer."""
    import os
    import time as _time
    avant = OtpPersistentCache.make_blacklist_key(_O, _D, _5H)
    monkeypatch.setenv("TZ", "America/New_York")
    if hasattr(_time, "tzset"):
        _time.tzset()
    try:
        assert OtpPersistentCache.make_blacklist_key(_O, _D, _5H) == avant
    finally:
        os.environ.pop("TZ", None)
        if hasattr(_time, "tzset"):
            _time.tzset()
