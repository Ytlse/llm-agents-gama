"""Ticket 105 — un repli par défaut n'est pas une décision, et un run d'expérience s'arrête.

Ce que ces tests auraient attrapé le 2026-09-23 : la campagne c3 v4 a laissé quatre décisions
être prises par `itineraries[0]` dans la fenêtre de mesure — 0/48 replis avant le choc, 4/39
après — sans que rien ne s'arrête ni ne le signale. Le garde-fou du ticket 077 existait déjà mais
ne regardait que `genre_erreur == "quota_journalier"`, et une saturation amont (54 × HTTP 503
« high demand » ce jour-là, zéro RESOURCE_EXHAUSTED) ne renvoie AUCUN genre_erreur.

Les tests portent sur la LOGIQUE d'arrêt et sur ce qui la déclenche, lus dans la source : le
chemin complet demande GAMA, un modèle et un pipeline, et un test qui monterait tout cela ne
dirait plus lequel des trois a cassé.
"""

from __future__ import annotations

from pathlib import Path

from settings import settings
from urban_mobility_agents import simulation_controller as sc

SOURCE = Path(sc.__file__).read_text(encoding="utf-8")
# Les tests tournent depuis `services/llm-agents/` : la racine du dépôt se remonte, elle ne
# se suppose pas. Sans cela, deux tests lisaient un chemin relatif qui n'existait pas.
RACINE = Path(__file__).resolve().parents[3]


# ── Le verrou : armé en expérience, muet ailleurs ────────────────────────────────────────


class TestVerrouDExperience:
    def test_muet_par_defaut(self, monkeypatch):
        """Un run ordinaire garde son comportement : il se rabat, il ne s'arrête pas."""
        for nom in sc._VERROUS_ARRET_EXPERIENCE:
            monkeypatch.delenv(nom, raising=False)
        assert sc._arret_sur_repli_arme() is False

    def test_arme_par_le_nom_neuf(self, monkeypatch):
        for nom in sc._VERROUS_ARRET_EXPERIENCE:
            monkeypatch.delenv(nom, raising=False)
        monkeypatch.setenv("EXPERIMENT_STOP_ON_FALLBACK", "1")
        assert sc._arret_sur_repli_arme() is True

    def test_l_ancien_nom_reste_admis(self, monkeypatch):
        """`EXPERIMENT_HIBERNATE_ON_QUOTA` est écrit dans des scripts de campagne déjà lancés."""
        for nom in sc._VERROUS_ARRET_EXPERIENCE:
            monkeypatch.delenv(nom, raising=False)
        monkeypatch.setenv("EXPERIMENT_HIBERNATE_ON_QUOTA", "1")
        assert sc._arret_sur_repli_arme() is True

    def test_une_valeur_autre_que_1_n_arme_pas(self, monkeypatch):
        for nom in sc._VERROUS_ARRET_EXPERIENCE:
            monkeypatch.delenv(nom, raising=False)
        monkeypatch.setenv("EXPERIMENT_STOP_ON_FALLBACK", "true")
        assert sc._arret_sur_repli_arme() is False

    def test_la_campagne_pose_le_verrou(self):
        """Toute campagne est protégée d'office : pas de levier à penser au lancement."""
        chemin = RACINE / "scripts/experiment/run_sequential_cohort.py"
        cohorte = chemin.read_text(encoding="utf-8")
        assert 'env["EXPERIMENT_STOP_ON_FALLBACK"] = "1"' in cohorte

    def test_le_verrou_traverse_le_conteneur(self):
        """Une variable non déclarée dans compose n'atteint jamais le contrôleur."""
        compose = (RACINE / "infra/docker-compose.yml").read_text(encoding="utf-8")
        assert "EXPERIMENT_STOP_ON_FALLBACK:" in compose
        assert "EXPERIMENT_HIBERNATE_ON_QUOTA:" in compose, (
            "l'alias doit rester transmis"
        )


# ── Le seuil ─────────────────────────────────────────────────────────────────────────────


class TestSeuil:
    def test_le_seuil_existe_et_vaut_plus_de_un(self):
        """Pas 1 : un 503 isolé est rattrapé par les tentatives et ne produit aucun repli.
        Ce qu'on attrape est un RÉGIME, pas un incident."""
        seuil = settings.agent.replis_consecutifs_max
        assert isinstance(seuil, int)
        assert seuil >= 2, "un seuil à 1 arrêterait un run sur un incident absorbable"

    def test_le_seuil_par_defaut_est_trois(self):
        assert settings.agent.replis_consecutifs_max == 3


# ── La logique d'arrêt, lue dans la source ───────────────────────────────────────────────


class TestLogiqueDArret:
    def test_le_compteur_est_declare(self):
        assert "self._replis_consecutifs: int = 0" in SOURCE

    def test_une_decision_reussie_casse_la_serie(self):
        """Sans remise à zéro, trois replis étalés sur tout un run finiraient par arrêter."""
        bloc = SOURCE.split('selection_method = "LLM"')[1][:300]
        assert "self._replis_consecutifs = 0" in bloc

    def test_le_compteur_monte_avant_toute_decision_d_arret(self):
        garde = SOURCE.split("if _arret_sur_repli_arme():")[0]
        assert "self._replis_consecutifs += 1" in garde[-2000:]

    def test_le_seuil_declenche_l_hibernation(self):
        assert (
            "self._replis_consecutifs >= settings.agent.replis_consecutifs_max"
            in SOURCE
        )
        bloc = SOURCE.split(
            "self._replis_consecutifs >= settings.agent.replis_consecutifs_max"
        )[1][:400]
        assert "_declencher_hibernation_propre" in bloc
        assert 'motif="replis_consecutifs"' in bloc

    def test_le_chemin_quota_du_077_est_preserve(self):
        """Lui seul connaît l'heure de réouverture : il ne doit pas être absorbé par le neuf."""
        assert '_trace_decision.get("genre_erreur") == "quota_journalier"' in SOURCE
        bloc = SOURCE.split(
            '_trace_decision.get("genre_erreur") == "quota_journalier"'
        )[1][:500]
        assert 'motif="quota_journalier"' in bloc
        assert "reprise_a" in bloc, "l'heure de réouverture doit continuer de voyager"

    def test_les_deux_arrets_rendent_la_main_sans_choisir(self):
        """Un `return None, None` : surtout pas un plan_index=0 après avoir décidé d'arrêter."""
        bloc = SOURCE.split("if _arret_sur_repli_arme():")[1][:1500]
        assert bloc.count("return None, None") == 2


# ── La visibilité ────────────────────────────────────────────────────────────────────────


class TestLeRepliSeVoit:
    def test_le_repli_est_journalise_en_alarme(self):
        """Il était en `debug` : il a fallu fouiller moves.csv à la main pour le découvrir."""
        assert "[ALARME] [repli]" in SOURCE

    def test_l_alarme_porte_de_quoi_agir(self):
        bloc = SOURCE.split("[ALARME] [repli]")[1][:600]
        for attendu in ("agent=", "instant=", "consecutifs="):
            assert attendu in bloc, attendu

    def test_le_repli_n_est_plus_en_debug(self):
        assert "No suitable plan found for person" not in SOURCE


# ── Le marqueur d'arrêt ──────────────────────────────────────────────────────────────────


class TestMarqueurDArret:
    def test_le_marqueur_porte_le_motif(self):
        assert '"motif": motif' in SOURCE

    def test_une_saturation_n_invente_pas_d_heure_de_reouverture(self):
        """Écrire la chaîne "None" dans `resume_at` ferait croire à une date."""
        assert "if resume_at is None" in SOURCE
        assert '"replis_consecutifs": self._replis_consecutifs' in SOURCE

    def test_l_arret_pour_replis_le_dit_en_alarme(self):
        assert "[ALARME] [hibernation]" in SOURCE
        bloc = SOURCE.split("[ALARME] [hibernation]")[1][:600]
        assert "replis CONSÉCUTIFS" in bloc

    def test_l_arret_reste_un_sigterm(self):
        """`sys.exit` se ravale en erreur de requête sous l'ASGI ; l'orchestrateur attend un 0."""
        assert "os.kill(os.getpid(), signal.SIGTERM)" in SOURCE
