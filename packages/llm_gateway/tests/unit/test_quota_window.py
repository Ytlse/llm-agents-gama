"""Fenêtre des quotas journaliers : le bon fuseau, et le `retryDelay` remis à sa place.

Incident de référence (2026-09-08). Une expérience s'arrête à 10 % : `google_gemini35_key2`
répond 429 en boucle pendant 15 min. Le corps de Google est explicite —
`quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier`, `quotaValue: 500` — mais deux
choses l'ont rendu illisible pour la plateforme :

1. les compteurs internes étaient datés en UTC, donc vidés à 02:00 heure de Paris, alors que
   la journée de facturation Gemini ne se terminait qu'à 09:00 (minuit Pacifique). Redis
   affichait 49 requêtes sur 500 quand Google refusait pour dépassement des 500 ;
2. le `retryDelay` annoncé valait 0,7 s à 57 s — un délai de débit par minute, qui ne mesure
   PAS le temps jusqu'au reset. Le suivre faisait boucler indéfiniment.

Ces tests figent les deux points sur les valeurs réellement observées ce jour-là.
"""

from datetime import datetime, timezone

from llm_gateway.core.quota import (
    is_daily_quota_error,
    next_quota_reset,
    quota_day,
    seconds_until_quota_reset,
)

# Corps réel du 429 du 2026-09-08 (extrait de experiments/.../llm_errors.jsonl), réduit à
# ce qui porte le sens : le quotaId, et un retryDelay court qui ne dit rien du reset.
CORPS_429_JOURNALIER = """{"error": {"code": 429,
 "message": "You exceeded your current quota... Quota exceeded for metric:
   generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 500,
   model: gemini-3.5-flash-lite. Please retry in 33.173905726s.",
 "status": "RESOURCE_EXHAUSTED",
 "details": [{"@type": "type.googleapis.com/google.rpc.QuotaFailure",
   "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
                   "quotaValue": "500"}]},
  {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "33s"}]}}"""

CORPS_429_PAR_MINUTE = """{"error": {"code": 429, "status": "RESOURCE_EXHAUSTED",
 "details": [{"@type": "type.googleapis.com/google.rpc.QuotaFailure",
   "violations": [{"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier",
                   "quotaValue": "15"}]}]}}"""


class TestNatureDuRefus:
    def test_le_429_reel_du_8_septembre_est_journalier(self):
        assert is_daily_quota_error(CORPS_429_JOURNALIER) is True

    def test_un_429_par_minute_ne_l_est_pas(self):
        """À ne pas confondre : celui-là se règle par un cooldown court, pas par une attente."""
        assert is_daily_quota_error(CORPS_429_PAR_MINUTE) is False

    def test_corps_absent_ou_vide(self):
        assert is_daily_quota_error(None) is False
        assert is_daily_quota_error("") is False

    def test_libelles_en_clair(self):
        assert is_daily_quota_error("limit: RequestsPerDay exceeded") is True
        assert is_daily_quota_error("quota per day exhausted") is True
        assert is_daily_quota_error("TokensPerDay limit reached") is True


class TestFenetreDuJour:
    # 2026-09-08 06:44 UTC = 08:44 à Paris = 23:44 le 7 au Pacifique.
    INSTANT_DU_BLOCAGE = datetime(2026, 9, 8, 6, 44, tzinfo=timezone.utc)

    def test_les_deux_fuseaux_ne_datent_pas_la_meme_journee(self):
        """La cause racine : à 08:44 Paris, le compteur UTC a tourné, celui de Google pas."""
        assert quota_day("UTC", self.INSTANT_DU_BLOCAGE) == "20260908"
        assert quota_day("America/Los_Angeles", self.INSTANT_DU_BLOCAGE) == "20260907"

    def test_la_reouverture_tombe_a_9h_a_paris(self):
        """Mesuré : les sondes sur les deux clés repassent en HTTP 200 à 09:01 heure de Paris."""
        assert next_quota_reset("America/Los_Angeles", self.INSTANT_DU_BLOCAGE) == datetime(
            2026, 9, 8, 7, 0, tzinfo=timezone.utc
        )

    def test_l_attente_reelle_depasse_de_loin_le_retry_delay_annonce(self):
        """33 s annoncées par Google contre 16 min d'attente réelle : le délai est à jeter."""
        restant = seconds_until_quota_reset("America/Los_Angeles", self.INSTANT_DU_BLOCAGE)
        assert restant == 960
        assert restant > 33

    def test_passage_a_l_heure_d_hiver_pacifique(self):
        """Le 1er novembre 2026, le Pacifique repasse en PST : minuit local = 08:00 UTC."""
        apres = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
        assert next_quota_reset("America/Los_Angeles", apres) == datetime(
            2026, 11, 6, 8, 0, tzinfo=timezone.utc
        )

    def test_passage_a_l_heure_d_ete_pacifique(self):
        """Fin mars, PDT : minuit local = 07:00 UTC."""
        ete = datetime(2026, 3, 30, 12, 0, tzinfo=timezone.utc)
        assert next_quota_reset("America/Los_Angeles", ete) == datetime(
            2026, 3, 31, 7, 0, tzinfo=timezone.utc
        )

    def test_fuseau_inconnu_retombe_sur_utc_sans_lever(self):
        """Un fuseau illisible (tzdata absente) ne doit pas empêcher le gateway de démarrer."""
        t = datetime(2026, 9, 8, 6, 44, tzinfo=timezone.utc)
        assert next_quota_reset("Mars/Olympus_Mons", t) == datetime(
            2026, 9, 9, 0, 0, tzinfo=timezone.utc
        )
        assert next_quota_reset(None, t) == datetime(2026, 9, 9, 0, 0, tzinfo=timezone.utc)

    def test_l_attente_est_toujours_strictement_positive(self):
        """Une seconde avant le reset, on attend 1 s — jamais 0, qui ferait boucler l'appelant."""
        juste_avant = datetime(2026, 9, 8, 6, 59, 59, tzinfo=timezone.utc)
        assert seconds_until_quota_reset("America/Los_Angeles", juste_avant) >= 1
