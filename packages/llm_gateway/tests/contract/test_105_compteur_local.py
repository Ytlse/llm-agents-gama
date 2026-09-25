"""Ticket 105 — le compteur journalier dit, dans son nom, qu'il ne voit qu'ici.

Ce que ces tests auraient attrapé : le 2026-09-23, `redis-cli GET rpd:google_gemini31_key1` a été
lu comme un budget restant et a fait reporter une relance d'une journée, alors que le code disait
déjà le contraire dans une docstring — qui n'est pas là où on lit le chiffre.

Ils verrouillent trois choses : le nom de la clé porte sa limite, le nom de l'accesseur aussi, et
la fonction qui déciderait depuis ce compteur n'existe plus.
"""

from __future__ import annotations

import inspect

from llm_gateway.infra.memory import rate_limiter as memoire
from llm_gateway.infra.redis import rate_limiter as redis_rl
from llm_gateway.ports import rate_limiter as port


class TestNomDeLaCle:
    def test_le_prefixe_rpd_dit_qu_il_est_local(self):
        """C'est `redis-cli --scan` qu'on lit en cherchant où en est un quota."""
        assert redis_rl.RPD_KEY_PREFIX == "rpd_local_seulement:"

    def test_le_prefixe_tpd_dit_qu_il_est_local(self):
        assert redis_rl.TPD_KEY_PREFIX == "tpd_local_seulement:"

    def test_le_verrou_de_quota_garde_son_prefixe(self):
        """Lui fait autorité — il est posé sur un 429 du fournisseur, pas sur un compteur."""
        assert redis_rl.QUOTA_EXHAUSTED_PREFIX == "quota_exhausted:"


class TestNomDeLAccesseur:
    def test_les_deux_implementations_exposent_le_nom_suffixe(self):
        for impl in (redis_rl.RedisRateLimiter, memoire.InMemoryRateLimiter):
            assert hasattr(impl, "daily_requests_local_seulement"), impl.__name__
            assert hasattr(impl, "daily_tokens_local_seulement"), impl.__name__

    def test_l_ancien_nom_n_existe_plus(self):
        """Pas d'alias : un nom neutre qui marche encore est une invitation à se retromper."""
        for impl in (redis_rl.RedisRateLimiter, memoire.InMemoryRateLimiter):
            assert not hasattr(impl, "daily_requests"), impl.__name__
            assert not hasattr(impl, "daily_tokens"), impl.__name__

    def test_le_contrat_de_port_porte_le_meme_nom(self):
        source = inspect.getsource(port)
        assert "daily_requests_local_seulement" in source
        assert "daily_tokens_local_seulement" in source


class TestCodeMort:
    def test_mark_quota_exhausted_depuis_le_compteur_local_a_disparu(self):
        """Sans appelant depuis le ticket 097, et ressemblant à du code vivant : supprimée."""
        assert not hasattr(redis_rl.RedisRateLimiter, "_mark_quota_exhausted")

    def test_la_voie_qui_fait_autorite_reste(self):
        """Celle qui s'appuie sur le 429 du fournisseur, elle, ne bouge pas."""
        for impl in (redis_rl.RedisRateLimiter, memoire.InMemoryRateLimiter):
            assert hasattr(impl, "mark_quota_exhausted_until"), impl.__name__


class TestLeCompteurNeFermeToujoursRien:
    def test_un_compteur_au_dela_du_plafond_n_ecarte_pas_la_cle(self, ports):
        """Le fait du ticket 097, reverrouillé ici : seul le fournisseur ferme une clé."""
        limiter = ports.limiter
        for _ in range(50):
            limiter.record_tokens("p_pacifique", 10_000)
        assert limiter.is_quota_exhausted("p_pacifique") is False
