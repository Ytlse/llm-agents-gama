"""Ticket 090 — la trace de rejeu épargne les décisions déjà prises.

Contrat : `specs/ticket_090/tests.md`.

À la reprise à chaud, GAMA rejoue les jours déjà vécus pour reconstruire son état. La mémoire est
gelée (ticket 075), mais les décisions sont REFAITES et, cache coupé, repayées. Mesuré le
2026-09-16 : huit jours rejoués, une centaine de décisions, trois quarts d'heure d'attente réseau
pour retrouver un état déjà connu.
"""

from pathlib import Path

import pytest
from urban_mobility_agents.utils import rejeu_decisions as R

RACINE = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _propre():
    R.reinitialiser()
    yield
    R.reinitialiser()


def _tracer_une(workdir, personne="899549", activite="act-1", instant=1000.0, code="car#1"):
    R.charger(workdir)
    R.tracer(
        personne, activite, instant,
        code_plan=code, raison="raison", fournisseur="google_gemini31_key1",
        distribution={"car": 0.7, "bus": 0.3},
    )


class TestTracerEtResservir:
    def test_A1_une_decision_vivante_est_tracee_sous_sa_cle(self, tmp_path):
        _tracer_une(tmp_path)
        assert R.chemin(tmp_path).is_file()
        assert R.charger(tmp_path) == 1

    def test_A4_la_reponse_resservie_est_identique_a_celle_tracee(self, tmp_path):
        _tracer_une(tmp_path)
        R.charger(tmp_path)
        enr = R.chercher("899549", "act-1", 1000.0)
        assert enr is not None
        assert enr["code_plan"] == "car#1"
        assert enr["raison"] == "raison"
        assert enr["distribution"] == {"car": 0.7, "bus": 0.3}

    def test_A5_une_cle_inconnue_rend_None_sans_lever(self, tmp_path):
        _tracer_une(tmp_path)
        R.charger(tmp_path)
        assert R.chercher("899549", "act-INCONNUE", 1000.0) is None

    def test_la_cle_distingue_deux_instants_de_la_meme_activite(self, tmp_path):
        """Une activité qui revient chaque jour ne doit pas resservir la décision de la veille."""
        _tracer_une(tmp_path, instant=1000.0, code="car#1")
        R.tracer("899549", "act-1", 87400.0, code_plan="bus#2", raison="r", fournisseur="p",
                 distribution={})
        R.charger(tmp_path)
        assert R.chercher("899549", "act-1", 1000.0)["code_plan"] == "car#1"
        assert R.chercher("899549", "act-1", 87400.0)["code_plan"] == "bus#2"


class TestLaFenetreDeRejeu:
    def test_seules_les_decisions_anterieures_au_point_sont_indexees(self, tmp_path):
        """Au-delà du point de reprise, la décision doit être REPRISE au modèle, pas resservie :
        c'est là que le run redevient vivant."""
        _tracer_une(tmp_path, instant=1000.0)
        R.tracer("899549", "act-2", 9000.0, code_plan="x", raison="r", fournisseur="p",
                 distribution={})
        assert R.charger(tmp_path, jusqu_a=5000.0) == 1
        assert R.chercher("899549", "act-1", 1000.0) is not None
        assert R.chercher("899549", "act-2", 9000.0) is None


class TestComptageEtAlarme:
    def test_B1_servies_et_manquees_sont_comptees_separement(self, tmp_path):
        _tracer_une(tmp_path)
        R.charger(tmp_path)
        R.chercher("899549", "act-1", 1000.0)
        R.chercher("899549", "absente", 1.0)
        assert "1 décision(s) resservie(s)" in R.bilan()
        assert "1 manquée(s)" in R.bilan()

    def test_B2_un_rejeu_divergent_leve_une_alarme(self, tmp_path, caplog):
        """Un rejeu qui ne retrouve pas ses propres choix ne reconstruit pas l'état qu'on croit."""
        from loguru import logger

        messages: list[str] = []
        puits = logger.add(lambda m: messages.append(str(m)), level="ERROR")
        try:
            R.charger(tmp_path)
            for i in range(25):
                R.chercher("899549", f"absente-{i}", float(i))
        finally:
            logger.remove(puits)
        trace = "\n".join(messages)
        assert "[ALARME]" in trace and "divergent" in trace

    def test_B2_une_alarme_ne_se_repete_pas(self, tmp_path):
        from loguru import logger

        messages: list[str] = []
        puits = logger.add(lambda m: messages.append(str(m)), level="ERROR")
        try:
            R.charger(tmp_path)
            for i in range(60):
                R.chercher("899549", f"absente-{i}", float(i))
        finally:
            logger.remove(puits)
        assert sum("[ALARME]" in m for m in messages) == 1, "front montant, pas un flot"


class TestCeQuiNeDoitPasCasser:
    def test_C1_sans_trace_le_comportement_est_celui_davant(self, tmp_path):
        assert R.charger(tmp_path) == 0
        assert R.chercher("899549", "act-1", 1000.0) is None

    def test_C2_une_trace_tronquee_est_ignoree_ligne_a_ligne(self, tmp_path):
        _tracer_une(tmp_path)
        with R.chemin(tmp_path).open("a", encoding="utf-8") as f:
            f.write('{"personne": "x", "activite"\n')  # ligne coupée en plein vol
        assert R.charger(tmp_path) == 1, "la ligne saine reste exploitable"

    def test_tracer_sans_chargement_prealable_ne_leve_pas(self):
        """Le traçage ne doit jamais faire tomber un run, même mal initialisé."""
        R.tracer("a", "b", 1.0, code_plan="c", raison="r", fournisseur="p", distribution={})


class TestLaChaineEstBranchee:
    """Gardes de chaîne : le module peut être parfait et n'être appelé nulle part."""

    def _source(self) -> str:
        return (RACINE / "urban_mobility_agents" / "agents" / "llm_agent.py").read_text(
            encoding="utf-8"
        )

    def test_A3_la_relecture_est_conditionnee_au_gel(self):
        src = self._source()
        assert "rejeu_decisions" in src, "le module n'est appelé nulle part"
        assert "gel_actif" in src, (
            "resservir hors de la fenêtre de gel transformerait la trace en cache permanent"
        )

    def test_A1_la_decision_vivante_est_tracee(self):
        assert "rejeu_decisions.tracer(" in self._source().replace("R.", "rejeu_decisions.")

    def test_la_trace_est_ouverte_sur_TOUT_run_pas_seulement_a_la_reprise(self):
        """Elle s'écrit pendant la vie normale. Ne l'ouvrir qu'à la reprise la laisse vide,
        donc inerte — constaté le 2026-09-17 : zéro ligne après deux journées simulées."""
        src = (RACINE / "handle" / "application.py").read_text(encoding="utf-8")
        i_ouverture = src.find("rejeu_decisions.charger(_workdir)")
        i_garde = src.find('if _reprise:\n        from urban_mobility_agents.utils.reprise import')
        assert i_ouverture > 0, "la trace n'est jamais ouverte hors reprise"
        assert i_garde < 0 or i_ouverture < i_garde, (
            "l'ouverture inconditionnelle doit précéder le chargement borné de la reprise"
        )
