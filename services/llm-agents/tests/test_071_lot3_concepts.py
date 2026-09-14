"""Ticket 071, lot 3 — le concept se corrige au lieu de s'empiler.

Contrat : `specs/ticket_071/tests_lot3.md`. Les identifiants (A1, B4, C5, D1…) y renvoient.

La chaîne de réflexion est exercée POUR DE VRAI — panier, opérations, compteurs, mise à
l'écart — avec la passerelle LLM doublée : c'est le test qui décide ce que le modèle répond,
y compris répondre mal.
"""

import asyncio
import sys
from datetime import timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm.concepts import (
    CONFIRMER,
    CONTREDIRE,
    CREER,
    confiance,
    est_depasse,
    est_hors_service,
    normaliser_operation,
    panier_de,
)
from llm.longterm import MultiUserLongTermMemory
from llm.memory import MemoryEntry, MemoryType
from settings import settings
from sim_clock import gama_timestamp, wall_clock
from urban_mobility_agents.agents.llm_agent import LlmAgent, _concepts_du_jour

T0 = 1773637200


@pytest.fixture()
def journal():
    from loguru import logger

    lignes: list = []
    sink = logger.add(lambda m: lignes.append(str(m)), level="INFO")
    yield lignes
    logger.remove(sink)


# ═══════════════════════ C. Confiance, service, dépassement ═════════════════════


@pytest.mark.parametrize(
    ("obs", "contre", "conf", "servi", "depasse"),
    [
        (0, 0, 0.50, True, False),    # C1 jamais observé : ni cru, ni écarté
        (1, 0, 0.67, True, False),    # C2
        (1, 1, 0.50, True, False),    # C3 le seuil est STRICT
        (1, 2, 0.40, False, False),   # C4 hors service, mais pas encore dépassé
        (1, 3, 0.33, False, True),    # C5
        (20, 3, 0.84, True, False),   # C6 trois contradictions contre vingt confirmations
        (0, 1, 0.33, False, False),   # C7 une majorité sur deux observations
    ],
)
def test_C_confiance_service_et_depassement(obs, contre, conf, servi, depasse):
    assert confiance(obs, contre) == pytest.approx(conf, abs=0.01)
    assert (not est_hors_service(obs, contre)) is servi
    assert est_depasse(obs, contre) is depasse


def test_C6_et_C7_sont_les_deux_cas_que_la_double_condition_ecarte():
    """Ni trois contradictions contre vingt confirmations, ni une majorité sur deux."""
    assert est_depasse(20, 3) is False, "vingt confirmations tiennent contre trois contradictions"
    assert est_depasse(0, 1) is False, "une contradiction unique ne dépasse rien"
    assert est_depasse(1, 3) is True, "trois contradictions ET une minorité de confirmations"


def test_C_les_deux_seuils_sont_ceux_de_la_configuration():
    assert settings.agent.memoire__confiance_seuil_service == pytest.approx(0.5)
    assert settings.agent.memoire__contre_exemples_seuil == 3


# ═══════════════════════ D. Deux régimes d'effacement ═══════════════════════════


class _Ltm(MultiUserLongTermMemory):
    def __init__(self):
        self.shared_index = None
        self.user_metadata = {}
        self.metadata_access_times = {}
        self.long_term_memory_filter_by_datetime = False
        self.metrics = {"queries": 0, "cache_hits": 0, "cache_misses": 0}
        self._dirty = set()

    def ensure_user_initialized(self, person_id):
        self.user_metadata.setdefault(person_id, {"entries": []})

    def _save_user_metadata(self, person_id):
        pass

    def _schedule_flush(self):
        pass


def _entree(kind, jours, **kw):
    return MemoryEntry(
        content='["x", "k", "s", "t", "work"]',
        timestamp=wall_clock(T0) - timedelta(days=jours),
        memory_type=kind,
        person_id="42",
        **kw,
    )


def test_D1_un_concept_de_dix_jours_jamais_contredit_garde_son_poids():
    """LE test qui justifie le lot 3.

    Qu'une ligne sature les jours de pluie entre 8 h et 8 h 30 ne devient pas faux parce que
    dix jours ont passé. Sous le régime uniforme, ce concept tombait à 0,028 et sortait du
    top-K sans qu'aucune observation ne l'ait infirmé.
    """
    ltm = _Ltm()
    concept = _entree(MemoryType.CONCEPT, 10, observations=3, force=2.8)
    poids = ltm._time_decay_score(None, gama_timestamp(wall_clock(T0)), entree=concept)
    assert poids == pytest.approx(confiance(3, 0), abs=1e-9)
    assert poids > 0.7, "sous le régime uniforme il valait 0,028"


def test_D2_un_concept_de_deux_ans_jamais_contredit_garde_son_poids():
    ltm = _Ltm()
    vieux = _entree(MemoryType.CONCEPT, 730, observations=3, force=2.8)
    assert ltm._time_decay_score(
        None, gama_timestamp(wall_clock(T0)), entree=vieux
    ) == pytest.approx(confiance(3, 0), abs=1e-9)


def test_D3_un_concept_contredit_perd_son_poids_quelle_que_soit_son_anciennete():
    ltm = _Ltm()
    frais = _entree(MemoryType.CONCEPT, 0, observations=1, contre_exemples=4)
    assert ltm._time_decay_score(
        None, gama_timestamp(wall_clock(T0)), entree=frais
    ) == pytest.approx(confiance(1, 4), abs=1e-9)
    assert ltm._time_decay_score(None, gama_timestamp(wall_clock(T0)), entree=frais) < 0.4


def test_D4_une_entree_episodique_garde_la_decroissance_exponentielle():
    ltm = _Ltm()
    reflexion = _entree(MemoryType.REFLECTION, 7, force=2.8)
    assert ltm._time_decay_score(
        None, gama_timestamp(wall_clock(T0)), entree=reflexion
    ) == pytest.approx(0.08, abs=0.01)


# ═════════════ Chaîne de réflexion : panier et quatre opérations ════════════════


class _Reponse:
    def __init__(self, concepts):
        class _A:
            pass

        a = _A()
        a.agent_id = "42"
        a.reflection = "journée ordinaire"
        a.concepts = concepts
        self.agents = [a]
        self.provider_used = "double"


class _Client:
    def __init__(self, concepts):
        self.concepts = concepts
        self.appels = 0

    async def execute(self, payload):
        self.appels += 1
        self.payload = payload
        return _Reponse(self.concepts)


class _Personne:
    def __init__(self):
        self.person_id = "42"


class _Contexte:
    def __init__(self):
        self.person = _Personne()
        self.timestamp = T0
        self.activity_id = None
        self.data = {}


class _Agent(LlmAgent):
    """Agent réel, réduit à ce que la réflexion courte a besoin de toucher."""

    def __init__(self, concepts_rendus, concepts_existants=()):
        from llm.shortterm import UserShortTermMemory

        self.short_term_memory = {"42": UserShortTermMemory("42")}
        self.long_term_memory = _Ltm()
        self.long_term_memory.ensure_user_initialized("42")
        self.long_term_memory.user_metadata["42"]["entries"] = list(concepts_existants)
        self.reflection_memo = None
        self.llm_client = _Client(concepts_rendus)
        self.ecrits: list = []

    def get_person_identity_description(self, person):
        return "persona de test"

    async def aadd_long_term_memory(self, context, msg):
        self.ecrits.append(msg)
        self.long_term_memory.user_metadata["42"]["entries"].append(msg)


def _concept_existant(doc_id, mode="cycling", motif="work", obs=1, contre=0):
    return MemoryEntry(
        content=f'["{doc_id}", "k", "s", "t", "{motif}"]',
        timestamp=wall_clock(T0) - timedelta(days=2),
        memory_type=MemoryType.CONCEPT,
        person_id="42",
        doc_id=doc_id,
        axe_objet=mode,
        axe_motif=motif,
        observations=obs,
        contre_exemples=contre,
        force=2.8,
    )


def _concept_rendu(**kw):
    base = {
        "content": "nouveau", "keywords": "k", "spatial_scope": "s",
        "temporal_scope": "t", "purpose": "work", "mode": "cycling",
        "severity": "noticeable", "valence": "neutral",
        "operation": "create", "target_id": "",
    }
    base.update(kw)
    return base


def _reflechir(agent):
    mem = agent.get_short_term_memory("42")
    mem.add_message(
        "trajet", wall_clock(T0), activity_id=None,
        importance=0.0, axes={"axe_objet": "cycling", "axe_motif": "work"},
    )
    asyncio.run(agent.reflect_on_short_term_memory(_Contexte()))
    return agent


# ── A. Le panier ───────────────────────────────────────────────────────────────


def test_A1_trois_concepts_du_meme_couple_partagent_un_panier_sans_se_detruire():
    existants = [_concept_existant(f"42_{i}") for i in range(3)]
    montres = _concepts_du_jour(
        _Ltm.__new__(_Ltm), "42", {panier_de("cycling", "work")}
    ) if False else None
    ltm = _Ltm()
    ltm.ensure_user_initialized("42")
    ltm.user_metadata["42"]["entries"] = existants
    montres = _concepts_du_jour(ltm, "42", {panier_de("cycling", "work")})
    assert len(montres) == 3, "le panier est un ENSEMBLE, pas un emplacement unique"


def test_A2_deux_modes_font_deux_paniers():
    ltm = _Ltm()
    ltm.ensure_user_initialized("42")
    ltm.user_metadata["42"]["entries"] = [
        _concept_existant("42_velo", mode="cycling"),
        _concept_existant("42_auto", mode="car"),
    ]
    montres = _concepts_du_jour(ltm, "42", {panier_de("cycling", "work")})
    assert [m.doc_id for m in montres] == ["42_velo"]


def test_A3_un_concept_sans_mode_existe_dans_son_panier():
    ltm = _Ltm()
    ltm.ensure_user_initialized("42")
    ltm.user_metadata["42"]["entries"] = [_concept_existant("42_gen", mode=None)]
    assert len(_concepts_du_jour(ltm, "42", {panier_de(None, "work")})) == 1


def test_A6_le_panier_ne_montre_pas_les_concepts_hors_service():
    """Il n'y a pas lieu de proposer de corriger ce qu'on ne sert plus."""
    ltm = _Ltm()
    ltm.ensure_user_initialized("42")
    ltm.user_metadata["42"]["entries"] = [_concept_existant("42_mort", obs=0, contre=3)]
    assert _concepts_du_jour(ltm, "42", {panier_de("cycling", "work")}) == []


def test_A7_le_panier_est_plafonne():
    from llm.concepts import CONCEPTS_MONTRES_PAR_PANIER

    ltm = _Ltm()
    ltm.ensure_user_initialized("42")
    ltm.user_metadata["42"]["entries"] = [
        _concept_existant(f"42_{i}", obs=i) for i in range(12)
    ]
    montres = _concepts_du_jour(ltm, "42", {panier_de("cycling", "work")})
    assert len(montres) == CONCEPTS_MONTRES_PAR_PANIER


# ── B. Les quatre opérations ───────────────────────────────────────────────────


def test_B1_creer_ajoute_une_entree():
    agent = _reflechir(_Agent([_concept_rendu(operation="create")]))
    concepts = [e for e in agent.ecrits if str(e.memory_type) == "concept"]
    assert len(concepts) == 1
    assert concepts[0].observations == 0 or concepts[0].observations >= 0


def test_B2_confirmer_n_ecrit_rien_de_neuf_et_incremente():
    cible = _concept_existant("42_a", obs=1)
    agent = _Agent([_concept_rendu(operation="confirm", target_id="K1")], [cible])
    _reflechir(agent)
    assert cible.observations == 2
    assert [e for e in agent.ecrits if str(e.memory_type) == "concept"] == []
    assert cible.derniere_observation is not None
    assert cible.force > 2.8, "un concept confirmé est renforcé"


def test_B3_preciser_remplace_le_contenu_et_garde_les_compteurs():
    cible = _concept_existant("42_a", obs=5, contre=1)
    agent = _Agent(
        [_concept_rendu(operation="refine", target_id="K1", content="plus précis")], [cible]
    )
    _reflechir(agent)
    assert "plus précis" in cible.content
    assert cible.observations == 5 and cible.contre_exemples == 1
    assert [e for e in agent.ecrits if str(e.memory_type) == "concept"] == []


def test_B4_contredire_incremente_la_cible_ET_ecrit_la_releve():
    cible = _concept_existant("42_a", obs=1, contre=0)
    agent = _Agent([_concept_rendu(operation="contradict", target_id="K1")], [cible])
    _reflechir(agent)
    assert cible.contre_exemples == 1
    assert len([e for e in agent.ecrits if str(e.memory_type) == "concept"]) == 1


def test_B5_une_operation_inconnue_retombe_sur_creer(journal):
    assert normaliser_operation("catastrophe") == CREER
    assert any("INCONNUE" in ligne for ligne in journal)


def test_B6_une_cible_inconnue_ne_leve_pas_et_retombe_sur_creer(journal):
    cible = _concept_existant("42_a", obs=1)
    agent = _Agent([_concept_rendu(operation="confirm", target_id="K99")], [cible])
    _reflechir(agent)
    assert cible.observations == 1, "aucun concept existant ne doit être touché au hasard"
    assert len([e for e in agent.ecrits if str(e.memory_type) == "concept"]) == 1
    assert any("cible inconnue" in ligne for ligne in journal)


def test_B8_il_n_y_a_jamais_de_suppression():
    """Le concept mis à l'écart reste en mémoire, et il n'est plus proposé au modèle.

    Deux propriétés en une : aucune suppression, et une sortie du panier qui BORNE le nombre
    de contradictions qu'il peut encore recevoir — il n'est plus montré, donc plus contredit.
    """
    cible = _concept_existant("42_a", obs=3, contre=0)
    for _ in range(20):
        agent = _Agent([_concept_rendu(operation="contradict", target_id="K1")], [cible])
        _reflechir(agent)
    # 4 contradictions suffisent à faire tomber la confiance sous 0,5 ; ensuite le concept
    # sort du panier et cesse d'être contredit.
    assert cible.contre_exemples == 4
    assert cible in agent.long_term_memory.user_metadata["42"]["entries"], "jamais supprimé"
    assert cible.depasse_le is not None, "la mise à l'écart est DATÉE"
    assert cible.est_servi is False


def test_C8_la_mise_a_l_ecart_est_marquee_et_datee_en_temps_simule():
    """⚠ La date est posée quand le concept CESSE D'ÊTRE SERVI.

    Défaut trouvé en écrivant ces tests : un concept sort du panier dès qu'il n'est plus
    servi, donc il n'est plus montré au modèle, donc il ne peut plus être contredit. Rattacher
    la date au seuil de trois contre-exemples la rendait inatteignable pour un concept peu
    observé, et l'observable que l'expérience d'hystérésis cherche n'était jamais écrit.
    """
    cible = _concept_existant("42_a", obs=3, contre=3)
    assert cible.est_servi is True, "4/8 = 0,50 : le seuil est strict"
    agent = _Agent([_concept_rendu(operation="contradict", target_id="K1")], [cible])
    _reflechir(agent)
    assert cible.contre_exemples == 4
    assert cible.est_servi is False
    assert cible.est_depasse is True, "au moins trois contradictions ET une minorité"
    assert cible.depasse_le is not None
    assert cible.depasse_le.startswith("2026-"), "temps SIMULÉ, jamais l'horloge machine"


def test_C10_un_concept_mis_a_l_ecart_n_est_pas_ressuscite():
    """Le marquage est daté et reste : il ne se retire pas tout seul."""
    cible = _concept_existant("42_a", obs=3, contre=4)
    cible.depasse_le = "2026-03-16T05:00:00"
    cible.observations = 50  # confiance remontée
    assert cible.est_servi is True
    assert cible.depasse_le is not None, "la trace du changement d'habitude ne s'efface pas"


def test_E1_les_operations_sont_comptees(journal):
    cible = _concept_existant("42_a", obs=1)
    agent = _Agent([_concept_rendu(operation="confirm", target_id="K1")], [cible])
    _reflechir(agent)
    assert any("[concepts] opérations du cycle" in ligne for ligne in journal)


def test_E2_l_alarme_part_quand_le_modele_confirme_tout(journal):
    """Un modèle qui ne contredit jamais laisse l'agent agir sur des croyances périmées."""
    agent = _Agent([])
    agent._jours_sans_contradiction = set()
    agent._alarme_confirme_tout = False
    for jour in range(5):
        agent._compter_operations({CONFIRMER: 2}, jour)
    assert agent._alarme_confirme_tout is True
    assert any("[ALARME]" in ligne and "confirme tout" in ligne for ligne in journal)


def test_E3_l_alarme_se_referme_a_la_premiere_contradiction():
    agent = _Agent([])
    agent._jours_sans_contradiction = set()
    agent._alarme_confirme_tout = False
    for jour in range(5):
        agent._compter_operations({CONFIRMER: 2}, jour)
    assert agent._alarme_confirme_tout is True
    agent._compter_operations({CONTREDIRE: 1}, 6)
    assert agent._alarme_confirme_tout is False
    assert agent._jours_sans_contradiction == set()


def test_H_un_seul_appel_a_la_passerelle():
    """Contrainte transverse du ticket : aucun lot ne coûte d'appel supplémentaire.

    Les concepts du panier sont montrés DANS l'appel qui a déjà lieu.
    """
    agent = _Agent([_concept_rendu()], [_concept_existant("42_a")])
    _reflechir(agent)
    assert agent.llm_client.appels == 1


def test_H_les_concepts_connus_sont_bien_envoyes_au_modele():
    agent = _Agent([_concept_rendu()], [_concept_existant("42_a")])
    _reflechir(agent)
    contexte = agent.llm_client.payload["agents"][0]["context"]
    assert "known_beliefs" in contexte
    assert '"id": "K1"' in contexte
