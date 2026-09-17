"""Ticket 077, lot C — les trajets à itinéraire unique et le journal des habitudes.

Contrat : `specs/ticket_077/tests.md` § C.

Deux défauts distincts, tous deux mesurés sur `experiments/archive/2026-09-14_23_58` :
116 trajets sur 514 n'écrivaient aucune entrée de décision, et le journal des habitudes
remontait au dernier `axe_objet` du tampon — donc au trajet précédent.
"""

import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from llm.noyau import bloc_habitudes, cle_journal, noter_trajet

CONTROLEUR = (RACINE / "urban_mobility_agents" / "simulation_controller.py").read_text(
    encoding="utf-8"
)
AGENT = (
    RACINE / "urban_mobility_agents" / "agents" / "llm_agent.py"
).read_text(encoding="utf-8")


class TestC1EcritureDeLaDecisionContrainte:
    """C1 — un trajet sans alternative écrit tout de même son entrée de décision."""

    def test_la_branche_itineraire_unique_note_la_decision(self):
        branche = CONTROLEUR.split('selection_method = "Un seul itinéraire disponible"')[1]
        # La notation doit intervenir AVANT la sortie de la branche (le `plan:` final).
        avant_plan = branche.split("plan: TravelPlan = itineraries[plan_index]")[0]
        assert "note_decision_contrainte" in avant_plan, (
            "un trajet à itinéraire unique doit écrire son entrée de décision : sans elle, "
            "la mémoire ignore que le déplacement a eu lieu"
        )

    def test_l_ecriture_porte_les_axes_de_la_decision(self):
        corps = AGENT.split("def note_decision_contrainte")[1].split("\n    async def")[0]
        assert "_axes_de_la_decision" in corps, (
            "sans axes, l'entrée est invisible au panier et au journal des habitudes"
        )

    def test_l_ecriture_est_sans_effet_sans_plan(self):
        corps = AGENT.split("def note_decision_contrainte")[1].split("\n    async def")[0]
        assert re.search(r"if plan is None:\s*\n\s*return", corps), (
            "un plan absent ne doit pas faire tomber la planification"
        )


class TestC2LeTexteDitQueLeChoixEtaitContraint:
    """C2 — l'agent doit pouvoir distinguer ce qu'il a décidé de ce qu'il a subi."""

    def test_le_message_ne_pretend_pas_qu_un_modele_a_choisi(self):
        corps = AGENT.split("def note_decision_contrainte")[1].split("\n    async def")[0]
        message = corps.split("stm_msg = (")[1].split(")")[0]
        assert "chosen by gateway LLM" not in message
        assert "only available itinerary" in message

    def test_le_message_dit_que_le_mode_n_est_pas_prefere(self):
        corps = AGENT.split("def note_decision_contrainte")[1].split("\n    async def")[0]
        assert "not preferred" in corps, (
            "sans cela l'agent tire une préférence d'une absence d'option"
        )


class TestC3C4JournalDesHabitudes:
    """C3 et C4 — l'arrivée est enregistrée sous SON motif, ou pas du tout."""

    def _bloc_journal(self) -> str:
        return CONTROLEUR.split("# Ticket 071, lot 4 — le trajet accompli entre au JOURNAL")[
            1
        ].split("_weather = get_weather")[0]

    def test_C3_le_mode_est_appariee_sur_l_activite(self):
        bloc = self._bloc_journal()
        assert "(person.person_id, str(observation.activity_id))" in bloc, (
            "sans appariement sur l'activité, l'arrivée est attribuée au trajet précédent"
        )

    def test_C3_le_mode_ne_vient_PAS_du_tampon_de_memoire_courte(self):
        """Régression du 2026-09-15 : le tampon est vidé par les consolidations.

        Chercher la décision dans la mémoire courte à l'arrivée ne trouvait presque plus
        rien — 2 trajets journalisés pour 40 arrivées — et le bloc « Mes habitudes »
        avait disparu de TOUS les prompts de décision. Le mode se note à la décision.
        """
        bloc = self._bloc_journal()
        assert "get_short_term_memory" not in bloc, (
            "le tampon court est vidé entre la décision et l'arrivée : il ne peut pas "
            "servir de source au journal des habitudes"
        )
        assert "_mode_par_activite" in bloc

    def test_C3_le_mode_est_note_a_la_decision(self):
        assert "self._mode_par_activite[(person.person_id, str(next_activity.id))]" in (
            CONTROLEUR
        ), "le mode doit être noté là où il est certain : au moment de la décision"
        assert "mode_canonique(plan.mode_label())" in CONTROLEUR

    def test_C3_la_table_est_bornee_par_purge_a_la_lecture(self):
        """Sinon elle grandirait sans fin sur un run long."""
        bloc = self._bloc_journal()
        assert "_mode_par_activite.pop(" in bloc, (
            "lire sans retirer ferait grandir la table à chaque trajet"
        )

    def test_C3_le_motif_vient_de_l_arrivee_pas_de_la_decision(self):
        bloc = self._bloc_journal()
        assert "_decision.axe_motif" not in bloc, (
            "le motif de la décision antérieure rangeait les retours sous le motif de l'aller"
        )
        assert 'observation.data.get("purpose")' in bloc

    def test_C3_le_creneau_vient_de_l_arrivee(self):
        bloc = self._bloc_journal()
        assert "_decision.axe_creneau" not in bloc
        assert "creneau_de(wall_clock(observation.timestamp))" in bloc

    def test_C4_une_arrivee_sans_mode_connu_n_enregistre_rien(self):
        bloc = self._bloc_journal()
        avant_note = bloc.split("noter_trajet")[0]
        assert "if _mode_retenu is None:" in avant_note
        assert "NON journalisé" in avant_note, (
            "l'écart doit se voir : une habitude fausse est pire qu'une habitude absente"
        )


class TestC5C6ComportementDuJournal:
    """C5 et C6 — ce que le journal doit contenir, vérifié sur la fonction elle-même."""

    def test_C5_un_agent_dont_les_retours_sont_contraints_porte_ses_deux_motifs(self):
        """Le scénario exact de l'agent 609 : aller décidé, retour contraint.

        Avant le ticket, les 58 retours étaient rangés sous « work » et le bloc ne portait
        aucun `home`. Ici, chaque arrivée est notée sous son propre motif.
        """
        journal = {}
        for _ in range(20):
            noter_trajet(journal, "work", "matin", "car")
            noter_trajet(journal, "home", "soir", "car")

        assert cle_journal("work", "matin") in journal
        assert cle_journal("home", "soir") in journal
        assert journal[cle_journal("home", "soir")]["total"] == 20

        motifs = {ligne.split(" ")[0] for ligne in bloc_habitudes(journal)}
        assert motifs == {"work", "home"}

    def test_C6_le_compte_du_journal_suit_les_arrivees_notees(self):
        journal = {}
        for i in range(10):
            noter_trajet(journal, "shop", "midi", "public_transport", retard_s=0)
        assert sum(e["total"] for e in journal.values()) == 10

    def test_C6_un_mode_non_resolu_ne_fait_pas_deriver_le_denominateur(self):
        journal = {}
        noter_trajet(journal, "work", "matin", "car")
        noter_trajet(journal, "work", "matin", None)
        assert journal[cle_journal("work", "matin")]["total"] == 1
