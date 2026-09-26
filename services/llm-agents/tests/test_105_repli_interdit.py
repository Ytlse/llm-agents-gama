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


# ── La logique d'arrêt, lue dans la source ───────────────────────────────────────────────


class TestLogiqueDArret:
    @staticmethod
    def _bloc_repli() -> str:
        """Isole la branche décision ; la consolidation emploie le même verrou plus haut."""
        return SOURCE.split('selection_method = "LLM"')[1].split("plan: TravelPlan")[0]

    def test_le_compteur_est_declare(self):
        assert "self._replis_consecutifs: int = 0" in SOURCE

    def test_une_decision_reussie_casse_la_serie(self):
        """Sans remise à zéro, trois replis étalés sur tout un run finiraient par arrêter."""
        bloc = SOURCE.split('selection_method = "LLM"')[1][:300]
        assert "self._replis_consecutifs = 0" in bloc

    def test_le_compteur_monte_avant_toute_decision_d_arret(self):
        bloc = self._bloc_repli()
        assert bloc.index("self._replis_consecutifs += 1") < bloc.index(
            "if _arret_sur_repli_arme():"
        )

    def test_le_premier_echec_non_absorbe_suspend_avant_repli(self):
        bloc = self._bloc_repli()
        assert "_declencher_hibernation_propre" in bloc
        assert 'motif="decision_absente"' in bloc
        assert bloc.index('motif="decision_absente"') < bloc.index("plan_index = 0")

    def test_le_chemin_quota_du_077_est_preserve(self):
        """Lui seul connaît l'heure de réouverture : il ne doit pas être absorbé par le neuf."""
        garde = 'if _genre in ("quota_journalier", "surcharge_fournisseur"):'
        assert '_genre = _trace_decision.get("genre_erreur")' in SOURCE
        assert garde in SOURCE
        bloc = SOURCE.split(garde)[1][:500]
        assert "motif=_genre" in bloc, "le marqueur dit lequel des deux a arrêté le run"
        assert "reprise_a" in bloc, "l'heure de réouverture doit continuer de voyager"

    def test_une_surcharge_qualifiee_arrete_au_premier_echec(self):
        """2026-09-25 — le worker rend le lot `surcharge_fournisseur` avant l'abandon du client.

        Sans ce genre, trois `Timeout expiré` muets entraient d'abord dans la mesure en replis
        (2026-09-23 : 16 mars 05:00, 07:48, puis le troisième) avant que le seuil n'arrête le run.
        """
        bloc = self._bloc_repli()
        assert "surcharge_fournisseur" in bloc
        assert bloc.index("surcharge_fournisseur") < bloc.index(
            'motif="decision_absente"'
        ), "la surcharge qualifiée conserve son motif et son heure de reprise"

    def test_l_arret_pour_surcharge_le_dit_en_alarme(self):
        bloc = SOURCE.split('elif motif == "surcharge_fournisseur":')[1][:600]
        assert "[ALARME] [hibernation]" in bloc

    def test_les_deux_arrets_rendent_la_main_sans_choisir(self):
        """Un `return None, None` : surtout pas un plan_index=0 après avoir décidé d'arrêter."""
        bloc = self._bloc_repli()
        assert bloc.count("return None, None") == 2

    def test_une_consolidation_absente_suspend_aussi_l_experience(self):
        assert "ConsolidationMemoryUnavailable" in SOURCE
        assert 'motif="consolidation_memoire"' in SOURCE


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

    def test_l_arret_pour_decision_absente_le_dit_en_alarme(self):
        bloc = SOURCE.split('if motif == "decision_absente":')[1][:600]
        assert "[ALARME] [hibernation]" in bloc
        assert "Arrêt au premier échec" in bloc

    def test_l_arret_reste_un_sigterm(self):
        """`sys.exit` se ravale en erreur de requête sous l'ASGI ; l'orchestrateur attend un 0."""
        assert "os.kill(os.getpid(), signal.SIGTERM)" in SOURCE


# ── Le banc : une surcharge qualifiée reste transitoire ──────────────────────────────────


def test_le_banc_range_la_surcharge_qualifiee_en_passerelle_occupee():
    """R2 : transitoire, jamais `epuise` — et sans dépendre de la formulation du motif."""
    import inspect

    from experiences import decideurs as D

    source = inspect.getsource(D)
    branche = source.split('genre_erreur") == "surcharge_fournisseur"')[1][:600]
    assert '"passerelle_occupee: "' in branche
    assert "epuise" not in branche.split("elif")[0].replace("jamais `epuise`", "")
