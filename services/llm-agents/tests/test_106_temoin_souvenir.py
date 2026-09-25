"""Ticket 106 — le souvenir injecté a-t-il atteint la mémoire longue ?

Ce que ces tests auraient attrapé le 2026-09-23 : la campagne c3 v4 a injecté une panne de métro
jugée `grave` (0,75) dans la mémoire courte de 861500, la consolidation du soir a écrit *« Today
went very smoothly overall »*, et aucun des 123 documents de mémoire longue du run ne parlait de
métro, d'éclairage ni d'annonce. Le run a continué 2 h 22 à mesurer l'effet d'un souvenir qui
n'existait pas.

Les textes utilisés ici sont les VRAIS : celui de `config/evenements/c3_panne_reseau.yaml` et les
réflexions effectivement écrites par les runs `11_10` (qui garde le choc) et `13_54` (qui le
perd). Un test sur du texte inventé ne dirait rien du corpus que le témoin doit trier.
"""

from __future__ import annotations

from pathlib import Path

from llm.evenements import temoin
from llm.evenements.injection import PREFIXE_LU, PREFIXE_VECU
from settings import settings

RACINE = Path(__file__).resolve().parents[3]

TEXTE_C3 = (
    "The metro stopped between two stations and the lighting went out. No announcement was made "
    "for 25 minutes. When the service restarted the carriage was packed full. I missed the "
    "appointment I was travelling to, and arrived 28 minutes after the time I had planned. It is "
    "the fourth time this month that this line has stopped."
)

# Run 11_10 — le choc est passé. Extrait réel de la réflexion consolidée.
GARDE = (
    "The metro stopped between two stations and the lighting went out, with no announcement for "
    "25 minutes. When the service restarted the carriage was packed full and I missed the "
    "appointment I was travelling to."
)

# Run 13_54 — le choc est perdu. Extrait réel de la consolidation qui a suivi l'injection.
PERDU = (
    "Today went very smoothly overall, with all my trips adhering closely to schedule. My morning "
    "public transport trip using Bus 35 went well, with only a short walk between errands."
)


# ── Repérer l'entrée injectée ────────────────────────────────────────────────────────────


class TestLAncrage:
    def test_une_consolidation_ordinaire_ne_declenche_rien(self):
        """L'immense majorité des consolidations : aucune entrée injectée, aucun contrôle."""
        assert temoin.texte_injecte(["I drove to work.", "I walked home."]) is None

    def test_le_prefixe_du_vecu_est_reconnu(self):
        entree = f"Arrived on time.\n{PREFIXE_VECU} {TEXTE_C3}"
        assert temoin.texte_injecte(["I walked home.", entree]) == TEXTE_C3

    def test_le_prefixe_du_lu_est_reconnu(self):
        """Le canal `lu` du ticket 100 passe par le même témoin."""
        entree = f"{PREFIXE_LU} I read in the paper: « {TEXTE_C3} »"
        assert TEXTE_C3 in (temoin.texte_injecte([entree]) or "")

    def test_le_texte_est_pris_apres_le_prefixe_pas_avant(self):
        """L'observation d'arrivée est JOINTE au texte : la confondre avec lui fausserait tout."""
        entree = f"Arrived on time. Distance 4.2 km.\n{PREFIXE_VECU} {TEXTE_C3}"
        assert "Distance" not in (temoin.texte_injecte([entree]) or "")


# ── Les mots distinctifs ─────────────────────────────────────────────────────────────────


class TestMotsDistinctifs:
    def test_le_vocabulaire_de_l_incident_est_retenu(self):
        mots = temoin.mots_distinctifs(TEXTE_C3)
        for attendu in ("lighting", "announcement", "carriage", "packed", "missed"):
            assert attendu in mots, attendu

    def test_le_vocabulaire_banal_du_domaine_est_ecarte(self):
        """« minutes », « line », « metro » sont dans toutes les réflexions, choc ou non."""
        mots = temoin.mots_distinctifs(TEXTE_C3)
        for banal in ("minutes", "line", "metro", "time", "stopped", "arrived", "month"):
            assert banal not in mots, banal

    def test_between_est_ecarte(self):
        """LE CAS CALIBRÉ : c'était le seul mot que le run perdu retrouvait, dans
        « a short walk between errands » — une phrase sans aucun rapport avec la panne."""
        assert "between" not in temoin.mots_distinctifs(TEXTE_C3)

    def test_l_ordre_du_texte_est_conserve(self):
        """Une alarme qui nomme les mots doit se relire dans l'ordre de la phrase injectée."""
        mots = temoin.mots_distinctifs(TEXTE_C3)
        assert mots.index("lighting") < mots.index("carriage") < mots.index("appointment")

    def test_pas_de_doublon(self):
        assert len(set(temoin.mots_distinctifs(TEXTE_C3))) == len(
            temoin.mots_distinctifs(TEXTE_C3)
        )


# ── La recherche dans ce qui a été écrit ─────────────────────────────────────────────────


class TestLaRecherche:
    def test_le_run_qui_garde_le_choc_est_reconnu(self):
        mots = temoin.mots_distinctifs(TEXTE_C3)
        trouves = temoin.mots_retrouves(mots, [GARDE])
        assert len(trouves) >= settings.agent.temoin_souvenir_mots_min
        assert "lighting" in trouves

    def test_le_run_qui_perd_le_choc_est_reconnu(self):
        """LE CAS DU 2026-09-23 : la consolidation parle d'une journée sans histoire."""
        mots = temoin.mots_distinctifs(TEXTE_C3)
        trouves = temoin.mots_retrouves(mots, [PERDU])
        assert len(trouves) < settings.agent.temoin_souvenir_mots_min, trouves

    def test_une_flexion_compte(self):
        """« announcements » doit valoir « announcement » : le modèle paraphrase, il ne copie pas."""
        assert "announcement" in temoin.mots_retrouves(
            ["announcement"], ["There were no announcements at all."]
        )

    def test_une_sous_chaine_ne_compte_pas(self):
        """« rain » ne doit pas se reconnaître dans « train » — le piège classique."""
        assert temoin.mots_retrouves(["rain"], ["I took the train."]) == []

    def test_la_casse_est_indifferente(self):
        assert temoin.mots_retrouves(["carriage"], ["The CARRIAGE was full."]) == [
            "carriage"
        ]


# ── Le contrôle complet ──────────────────────────────────────────────────────────────────


class TestLeControle:
    def _entrees(self):
        return [f"Arrived on time.\n{PREFIXE_VECU} {TEXTE_C3}"]

    def test_aucune_injection_aucun_constat(self):
        assert (
            temoin.controler(
                person_id="861500",
                sim_ts=1774620168,
                contenus_courts=["I drove to work."],
                textes_longs=["A quiet day."],
                seuil=2,
            )
            is None
        )

    def test_le_souvenir_retrouve_rend_un_constat_positif(self):
        constat = temoin.controler(
            person_id="861500",
            sim_ts=1774620168,
            contenus_courts=self._entrees(),
            textes_longs=[GARDE],
            seuil=2,
        )
        assert constat is not None and constat.retrouve is True
        assert constat.verdict == "retrouvé"

    def test_le_souvenir_perdu_rend_un_constat_negatif(self):
        constat = temoin.controler(
            person_id="861500",
            sim_ts=1774620168,
            contenus_courts=self._entrees(),
            textes_longs=[PERDU],
            seuil=2,
        )
        assert constat is not None and constat.retrouve is False
        assert constat.verdict == "PERDU"
        assert "lighting" in constat.mots_cherches

    def test_le_controle_ne_leve_jamais(self):
        """Un témoin qui ferait tomber une consolidation coûterait plus que le défaut surveillé."""
        assert (
            temoin.controler(
                person_id="x",
                sim_ts=0,
                contenus_courts=None,  # type: ignore[arg-type]
                textes_longs=None,  # type: ignore[arg-type]
                seuil=2,
            )
            is None
        )


# ── Le branchement et le réglage ─────────────────────────────────────────────────────────


class TestLeBranchement:
    def test_le_controle_est_appele_apres_l_ecriture_en_memoire_longue(self):
        """Avant l'écriture, il interrogerait une intention et non ce qui a été écrit."""
        source = (
            RACINE / "services/llm-agents/urban_mobility_agents/agents/llm_agent.py"
        ).read_text(encoding="utf-8")
        assert "temoin.controler(" in source
        avant = source.split("temoin.controler(")[0]
        assert "await self.aadd_long_term_memory(context, entry)" in avant

    def test_le_seuil_est_reglable_et_vaut_deux(self):
        assert settings.agent.temoin_souvenir_mots_min == 2

    def test_le_temoin_n_arrete_pas_le_run(self):
        """Décision du 2026-09-23 : il ALARME. Le témoin est heuristique là où celui du
        ticket 105 est certain ; l'arrêt attend d'avoir observé son taux de fausses alarmes."""
        source = (
            RACINE / "services/llm-agents/llm/evenements/temoin.py"
        ).read_text(encoding="utf-8")
        assert "SIGTERM" not in source
        assert "_declencher_hibernation" not in source

    def test_l_echec_est_une_alarme_et_le_succes_se_dit_aussi(self):
        source = (
            RACINE / "services/llm-agents/llm/evenements/temoin.py"
        ).read_text(encoding="utf-8")
        assert "[ALARME] [temoin]" in source
        assert "logger.info" in source, "un témoin muet ne se distingue pas d'un témoin mort"


class TestLIdentifiantDeLEvenement:
    """Le 2026-09-24, la première trace écrite en conditions réelles portait
    `"evenement_id": ""` : le verdict était juste, mais la ligne ne disait pas de quel choc
    elle parlait. La consolidation du soir ne connaît pas l'événement joint à une arrivée du
    matin — l'identifiant ne vit que dans le registre du run."""

    def test_le_registre_nomme_l_evenement_quand_l_appelant_se_tait(self, monkeypatch):
        class _Evenement:
            evenement_id = "c6_voiture_suspecte"

        class _Registre:
            evenement = _Evenement()

        import llm.evenements as evenements_module

        monkeypatch.setattr(evenements_module, "registre", lambda: _Registre())
        constat = temoin.controler(
            person_id="861500",
            sim_ts=1774849500,
            contenus_courts=[f"On time. {PREFIXE_VECU} The engine stalled on the expressway."],
            textes_longs=["The engine stalled on the expressway near the exit."],
            seuil=2,
        )
        assert constat is not None
        assert constat.evenement_id == "c6_voiture_suspecte"

    def test_l_appelant_garde_le_dernier_mot(self, monkeypatch):
        """Le jour où un run déclarera deux événements, le site d'appel devra passer
        l'identifiant — et ce qu'il passe doit l'emporter sur le repli."""

        class _Evenement:
            evenement_id = "declare_par_le_run"

        class _Registre:
            evenement = _Evenement()

        import llm.evenements as evenements_module

        monkeypatch.setattr(evenements_module, "registre", lambda: _Registre())
        constat = temoin.controler(
            person_id="861500",
            sim_ts=1774849500,
            contenus_courts=[f"On time. {PREFIXE_VECU} The engine stalled on the expressway."],
            textes_longs=["The engine stalled on the expressway near the exit."],
            seuil=2,
            evenement_id="passe_par_l_appelant",
        )
        assert constat is not None
        assert constat.evenement_id == "passe_par_l_appelant"

    def test_sans_registre_la_trace_reste_lisible(self, monkeypatch):
        """Sans événement déclaré, le témoin ne se plaint pas et ne casse rien : il nomme
        simplement moins."""
        import llm.evenements as evenements_module

        monkeypatch.setattr(evenements_module, "registre", lambda: None)
        constat = temoin.controler(
            person_id="861500",
            sim_ts=1774849500,
            contenus_courts=[f"On time. {PREFIXE_VECU} The engine stalled on the expressway."],
            textes_longs=["The engine stalled on the expressway near the exit."],
            seuil=2,
        )
        assert constat is not None
        assert constat.evenement_id == ""
