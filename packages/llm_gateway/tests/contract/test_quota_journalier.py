"""Retrait d'une instance sur quota journalier : jusqu'au reset de SA journée, pas de la nôtre.

Contrat commun aux deux implémentations du port RateLimiter (mémoire et Redis).

Ce que ces tests auraient attrapé le 2026-09-08 : `mark_quota_exhausted_until` n'existait pas,
et le seul chemin qui écartait une instance passait par le compteur local — lequel se vidait à
minuit UTC, soit 02:00 heure de Paris, pour un quota Gemini qui ne rouvrait qu'à 09:00. Une clé
refusée par Google était donc annoncée disponible pendant sept heures.
"""

from datetime import datetime, timedelta, timezone

from llm_gateway.core.quota import next_quota_reset


class TestRetraitSurParoleDuFournisseur:
    """Un 429 « per day » écarte l'instance sans passer par le compteur local."""

    def test_l_instance_est_ecartee_immediatement(self, ports):
        assert ports.limiter.is_quota_exhausted("p_pacifique") is False
        ports.limiter.mark_quota_exhausted_until("p_pacifique", kind="rpd")
        assert ports.limiter.is_quota_exhausted("p_pacifique") is True

    def test_le_retrait_vise_le_reset_pacifique(self, ports):
        """Le TTL doit couvrir l'attente réelle, pas les ~30 s du `retryDelay` annoncé."""
        attendu = (next_quota_reset("America/Los_Angeles") - datetime.now(timezone.utc)).total_seconds()
        ttl = ports.limiter.mark_quota_exhausted_until("p_pacifique", kind="rpd")
        assert abs(ttl - attendu) <= 2
        assert ttl > 60, "un quota du jour ne se règle jamais en moins d'une minute"

    def test_une_heure_de_reprise_explicite_est_respectee(self, ports):
        """Quand le fournisseur donne son heure, c'est elle qui vaut."""
        cible = datetime.now(timezone.utc) + timedelta(hours=3)
        ttl = ports.limiter.mark_quota_exhausted_until("p_pacifique", kind="rpd", until=cible)
        assert abs(ttl - 3 * 3600) <= 2
        assert ports.limiter.is_quota_exhausted("p_pacifique") is True

    def test_le_retrait_ne_touche_que_l_instance_visee(self, ports):
        """Deux modèles sur la même clé ont des seaux distincts : n'écarter que celui qui refuse."""
        ports.limiter.mark_quota_exhausted_until("p_pacifique", kind="rpd")
        assert ports.limiter.is_quota_exhausted("p3") is False


class TestFenetreDuCompteur:
    """Les compteurs du jour sont datés dans le fuseau du fournisseur."""

    def test_le_compteur_suit_le_fuseau_du_fournisseur(self, ports):
        """L'écriture et la lecture doivent viser la MÊME clé de jour.

        C'est leur désaccord qui produisait 49 requêtes comptées pour 500 consommées : si la
        lecture datait la journée autrement que l'écriture, le compteur relu serait à 0.
        (Une seule réservation : le lissage 60 s/rpm refuse deux appels dans la même
        micro-seconde, ce qui ne dit rien du datage.)
        """
        assert ports.limiter.daily_requests("p_pacifique") == 0
        assert ports.limiter.try_reserve("p_pacifique") is True
        assert ports.limiter.daily_requests("p_pacifique") == 1

    def test_les_tokens_du_jour_suivent_la_meme_fenetre(self, ports):
        ports.limiter.record_tokens("p_pacifique", 1_500)
        assert ports.limiter.daily_tokens("p_pacifique") == 1_500
