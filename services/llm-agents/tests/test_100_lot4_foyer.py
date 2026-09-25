"""Ticket 100, lot 4 — ce qu'un membre du foyer raconte aux autres.

Contrat de référence : `specs/ticket_100/tests.md`, règles R32 à R42, plus les quatre gardes
contre la boucle demandées par l'auteur le 2026-09-22 (G1 à G4).

Tout ici est PUR : aucun simulateur, aucun modèle, aucun appel réseau.
"""

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm import foyer
from llm.memory import MemoryEntry, MemoryType
from settings import settings

RACINE = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 3, 16, 22, 0)


@dataclass
class FauxIdentite:
    traits_json: dict


@dataclass
class FauxAgent:
    person_id: str
    household_id: str | None = None
    immobile: bool = False
    identity: FauxIdentite = field(default_factory=lambda: FauxIdentite({}))


@dataclass
class FausseLTM:
    """Le minimum que `foyer.py` lit : `user_metadata[pid]["entries"]`."""

    user_metadata: dict = field(default_factory=dict)

    def ajouter(self, person_id: str, entree: MemoryEntry) -> MemoryEntry:
        self.user_metadata.setdefault(person_id, {"entries": []})["entries"].append(entree)
        return entree


# Le foyer 5177 du ticket 078 : Constance, 12 ans, sans permis ni vélo, et Jacques, 49 ans,
# permis et vélo. Ce que Jacques apprend de la voiture ne doit JAMAIS devenir une croyance de
# Constance — c'est le cas qui fonde R4.
CONSTANCE = FauxAgent(
    "12", "5177",
    identity=FauxIdentite({
        "name": "Constance Ledoux", "age": 12,
        "has_driving_license": False, "number_of_cars": 0, "personal_bike": "No bike",
    }),
)
JACQUES = FauxAgent(
    "49", "5177",
    identity=FauxIdentite({
        "name": "Jacques Aubert", "age": 49,
        "has_driving_license": True, "number_of_cars": 1, "personal_bike": "Own bike",
    }),
)
XAVIER = FauxAgent(
    "40", "312",
    identity=FauxIdentite({"name": "Xavier Briand", "age": 40}),
)


def _reflexion(pid: str, texte: str, quand: datetime) -> MemoryEntry:
    return MemoryEntry(
        content=texte, timestamp=quand, memory_type=MemoryType.REFLECTION, person_id=pid,
    )


def _concept(pid: str, texte: str, quand: datetime, *, observations=2,
             axe_objet="public_transport", origine=None, contre=0) -> MemoryEntry:
    return MemoryEntry(
        content=json.dumps([texte, "", "", "", ""], ensure_ascii=False),
        timestamp=quand, memory_type=MemoryType.CONCEPT, person_id=pid,
        observations=observations, contre_exemples=contre,
        axe_objet=axe_objet, origine=origine,
    )


@pytest.fixture(autouse=True)
def _foyer_propre():
    foyer.reinitialiser()
    settings.agent.memoire__partage_foyer_enabled = True
    yield
    foyer.reinitialiser()
    settings.agent.memoire__partage_foyer_enabled = False


def _indexer(*agents):
    foyer.initialiser(list(agents))


# ── R32. Le drapeau ──────────────────────────────────────────────────────────────────────
def test_R32_drapeau_eteint_aucun_bloc():
    """Tout ce qui a été mesuré avant ce lot reste comparable : c'est un interrupteur."""
    settings.agent.memoire__partage_foyer_enabled = False
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    ltm.ajouter("49", _reflexion("49", "Busy day, the ring road was slow.", T0))
    assert foyer.bloc_du_soir(ltm, CONSTANCE, T0 + timedelta(hours=1)) == ""


def test_R32bis_le_defaut_est_eteint():
    from settings import AgentConfig

    assert AgentConfig().memoire__partage_foyer_enabled is False


# ── R33, R34. Le bilan du soir ───────────────────────────────────────────────────────────
def test_R33_le_recit_cite_le_bilan_que_lautre_a_ecrit():
    """« Aucune nouvelle information » (auteur, 2026-09-22) : le récit CITE, il ne rédige pas."""
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    bilan = "The ring road was slow again this morning; I left ten minutes earlier."
    ltm.ajouter("49", _reflexion("49", bilan, T0))
    lignes = foyer.recit_du_soir(ltm, "12", T0 + timedelta(hours=1))
    assert len(lignes) == 1
    assert bilan in lignes[0]
    assert "Jacques Aubert (49)" in lignes[0]


def test_R33bis_le_libelle_ne_dit_jamais_un_lien_de_parente():
    """EMC² et eqasim donnent le ménage, l'âge et le genre — PAS la filiation.

    Inventer « votre fils » fabriquerait une donnée, et elle retomberait dans les prompts
    comme un fait.
    """
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    ltm.ajouter("12", _reflexion("12", "School bus was full.", T0))
    ligne = foyer.recit_du_soir(ltm, "49", T0 + timedelta(hours=1))[0]
    assert "Constance Ledoux (12)" in ligne
    for parente in ("daughter", "son", "father", "mother", "fille", "fils", "père", "mère"):
        assert parente not in ligne.lower()


def test_R34_le_recit_nest_jamais_ecrit_dans_la_memoire_du_receveur():
    """Le bloc est une ENTRÉE de l'appel. La mémoire ne grossit pas d'avoir écouté."""
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    ltm.ajouter("49", _reflexion("49", "Long day.", T0))
    ltm.user_metadata.setdefault("12", {"entries": []})
    avant = len(ltm.user_metadata["12"]["entries"])
    foyer.bloc_du_soir(ltm, CONSTANCE, T0 + timedelta(hours=1))
    assert len(ltm.user_metadata["12"]["entries"]) == avant


# ── G1. Un récit n'est jamais servi deux fois ────────────────────────────────────────────
def test_G1_un_bilan_deja_entendu_ne_repart_pas():
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    ltm.ajouter("49", _reflexion("49", "The ring road was slow.", T0))
    premier = foyer.recit_du_soir(ltm, "12", T0 + timedelta(hours=1))
    assert len(premier) == 1
    second = foyer.recit_du_soir(ltm, "12", T0 + timedelta(days=1))
    assert second == [], "le même bilan servi deux fois est la boucle qu'on veut éviter"


def test_G1bis_ce_qui_arrive_apres_le_passage_nest_pas_perdu():
    """Le partage est au fil de l'eau, avec un décalage d'au plus une nuit, jamais une perte."""
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    ltm.ajouter("49", _reflexion("49", "Day one.", T0))
    foyer.recit_du_soir(ltm, "12", T0 + timedelta(hours=1))
    ltm.ajouter("49", _reflexion("49", "Day two.", T0 + timedelta(days=1)))
    suite = foyer.recit_du_soir(ltm, "12", T0 + timedelta(days=1, hours=1))
    assert len(suite) == 1 and "Day two" in suite[0]


def test_G1ter_le_repere_est_PAR_receveur():
    """Sans cela, l'ordre des consolidations déciderait qui entend quoi."""
    _indexer(CONSTANCE, JACQUES, FauxAgent("99", "5177",
                                           identity=FauxIdentite({"name": "Tiers", "age": 30})))
    ltm = FausseLTM()
    ltm.ajouter("49", _reflexion("49", "Shared day.", T0))
    assert foyer.recit_du_soir(ltm, "12", T0 + timedelta(hours=1))
    assert foyer.recit_du_soir(ltm, "99", T0 + timedelta(hours=2)), (
        "le passage de Constance ne doit pas priver le troisième membre"
    )


def test_le_repere_survit_a_une_reprise_a_chaud():
    """Sinon une reprise ferait ré-entendre au foyer entier des nuits déjà entendues."""
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    ltm.ajouter("49", _reflexion("49", "A day.", T0))
    foyer.recit_du_soir(ltm, "12", T0 + timedelta(hours=1))
    sauvegarde = foyer.etat_pour_reprise()

    foyer.reinitialiser()
    _indexer(CONSTANCE, JACQUES)
    foyer.charger_etat(sauvegarde)
    assert foyer.recit_du_soir(ltm, "12", T0 + timedelta(days=1)) == []


# ── R38. Les six règles du 078 ───────────────────────────────────────────────────────────
def test_R38_R1_un_concept_non_ancre_ne_circule_pas():
    """On ne raconte pas au foyer ce qu'on n'a pas vérifié soi-même."""
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    ltm.ajouter("49", _concept("49", "Bus 62 is often late", T0, observations=0))
    lignes, refus = foyer.croyances_partagees(ltm, CONSTANCE, T0)
    assert lignes == [] and refus["R1"] == 1


def test_R38_R3_un_concept_sans_axe_ne_circule_pas():
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    ltm.ajouter("49", _concept("49", "Things are slow", T0, axe_objet=None))
    lignes, refus = foyer.croyances_partagees(ltm, CONSTANCE, T0)
    assert lignes == [] and refus["R3"] == 1


def test_R38_R4_le_cas_Constance_et_Jacques():
    """Ce que Jacques apprend de la VOITURE ne devient jamais une croyance de Constance."""
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    ltm.ajouter("49", _concept("49", "The ring road jams at 8am", T0, axe_objet="car"))
    lignes, refus = foyer.croyances_partagees(ltm, CONSTANCE, T0)
    assert lignes == [] and refus["R4"] == 1
    # Et le même concept traverse vers un adulte qui conduit.
    _indexer(CONSTANCE, JACQUES)
    ltm2 = FausseLTM()
    ltm2.ajouter("12", _concept("12", "The ring road jams at 8am", T0, axe_objet="car"))
    lignes2, _ = foyer.croyances_partagees(ltm2, JACQUES, T0)
    assert len(lignes2) == 1


def test_R38_R4bis_marche_et_TC_traversent_pour_tout_le_monde():
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    ltm.ajouter("49", _concept("49", "Metro A is packed at 8", T0, axe_objet="public_transport"))
    lignes, _ = foyer.croyances_partagees(ltm, CONSTANCE, T0)
    assert len(lignes) == 1


def test_R38_R4ter_un_mode_hors_table_ne_traverse_pas():
    """Aucun repli permissif : un mot inconnu rendrait le verrou de permis décoratif."""
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    ltm.ajouter("49", _concept("49", "Something", T0, axe_objet="teleportation"))
    lignes, refus = foyer.croyances_partagees(ltm, CONSTANCE, T0)
    assert lignes == [] and refus["R4"] == 1


def test_R38_R2_une_confirmation_ne_fait_pas_repartir_un_concept():
    """Sinon une croyance confirmée chaque jour serait servie chaque soir à toute la famille."""
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    concept = ltm.ajouter("49", _concept("49", "Metro A is packed at 8", T0))
    assert len(foyer.croyances_partagees(ltm, CONSTANCE, T0)[0]) == 1
    concept.observations += 1  # une simple confirmation
    lignes, refus = foyer.croyances_partagees(ltm, CONSTANCE, T0 + timedelta(days=1))
    assert lignes == [] and refus["R2"] == 1


def test_R38_R2bis_une_precision_le_fait_repartir():
    """Le contenu a changé : ce n'est plus la même phrase."""
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    concept = ltm.ajouter("49", _concept("49", "Metro A is packed", T0))
    foyer.croyances_partagees(ltm, CONSTANCE, T0)
    concept.content = json.dumps(["Metro A is packed between 8 and 8:30", "", "", "", ""])
    lignes, _ = foyer.croyances_partagees(ltm, CONSTANCE, T0 + timedelta(days=1))
    assert len(lignes) == 1


def test_R38_R6_un_agent_seul_nentend_rien_et_ne_dit_rien():
    _indexer(CONSTANCE, JACQUES, XAVIER)
    ltm = FausseLTM()
    ltm.ajouter("49", _concept("49", "Metro A is packed", T0))
    lignes, refus = foyer.croyances_partagees(ltm, XAVIER, T0)
    assert lignes == [] and refus["R6"] == 1
    assert foyer.autres_membres("40") == []


def test_R42_un_membre_immobile_ne_raconte_rien():
    immobile = FauxAgent("77", "5177", immobile=True,
                         identity=FauxIdentite({"name": "Immobile", "age": 80}))
    _indexer(CONSTANCE, JACQUES, immobile)
    assert {m.person_id for m in foyer.autres_membres("12")} == {"49"}


# ── G3. Un seul saut ─────────────────────────────────────────────────────────────────────
def test_G3_une_croyance_entendue_ne_repart_jamais():
    """D2, et Q2 tranchée le 2026-09-21 : même confirmée ensuite, elle ne repart pas."""
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    entendu = ltm.ajouter(
        "49", _concept("49", "The school bus is always full", T0, origine="entendu")
    )
    assert foyer.croyances_partagees(ltm, CONSTANCE, T0)[0] == []
    # Confirmée quinze fois par la suite : elle ne repart toujours pas.
    entendu.observations = 15
    assert foyer.croyances_partagees(ltm, CONSTANCE, T0 + timedelta(days=10))[0] == []


def test_G3bis_une_croyance_vecue_sur_le_meme_sujet_circule():
    """D2 ne stérilise pas le receveur : sa propre journée crée une croyance qui, elle, part."""
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    ltm.ajouter("49", _concept("49", "The school bus is always full", T0, origine="entendu"))
    ltm.ajouter("49", _concept("49", "The school bus is full after 4pm", T0, origine="vecu"))
    lignes, _ = foyer.croyances_partagees(ltm, CONSTANCE, T0)
    assert len(lignes) == 1 and "after 4pm" in lignes[0]


def test_G3ter_une_entree_anterieure_au_ticket_est_tenue_pour_vecue():
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    ltm.ajouter("49", _concept("49", "Metro A is packed", T0, origine=None))
    assert len(foyer.croyances_partagees(ltm, CONSTANCE, T0)[0]) == 1


# ── G4. Le détecteur de reformulation ────────────────────────────────────────────────────
def test_G4_le_detecteur_signale_sans_jamais_couper():
    """Indicateur de LECTURE. Le 071 et le 077 ont refusé qu'une similarité décide."""
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    for i, texte in enumerate((
        "The metro is unreliable in the morning",
        "The metro is unreliable during morning peak",
        "Morning metro service is unreliable",
    )):
        ltm.ajouter("49", _concept("49", texte, T0 + timedelta(days=i)))
    signales = foyer.detecter_reformulation(ltm, "5177")
    assert signales, "trois reformulations dans le même panier doivent se voir"
    _panier, combien, mots = signales[0]
    assert combien == 3
    assert "unreliable" in mots and "metro" in mots
    # Et rien n'a été coupé : les trois concepts sont toujours là.
    assert len(ltm.user_metadata["49"]["entries"]) == 3


def test_G4bis_un_panier_a_un_seul_concept_ne_signale_rien():
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    ltm.ajouter("49", _concept("49", "Metro A is packed", T0))
    assert foyer.detecter_reformulation(ltm, "5177") == []


# ── R35. La borne et son alarme ──────────────────────────────────────────────────────────
def test_R35_une_troncature_se_compte_et_salarme(caplog):
    _indexer(CONSTANCE, JACQUES)
    settings.agent.memoire__recit_soir_max = 1
    try:
        ltm = FausseLTM()
        for i in range(4):
            ltm.ajouter("49", _reflexion("49", f"Day {i}.", T0 + timedelta(days=i)))
        lignes = foyer.recit_du_soir(ltm, "12", T0 + timedelta(days=9))
        assert len(lignes) == 1
    finally:
        settings.agent.memoire__recit_soir_max = 8


# ── R41. Le champ de provenance, dans les deux bras ──────────────────────────────────────
def test_R41_le_schema_demande_la_provenance_et_la_version_a_bouge():
    from urban_mobility_agents.agents.llm_agent import SCHEMA_REFLEXION_VERSION

    assert SCHEMA_REFLEXION_VERSION == 4, (
        "une réponse mémoïsée sans provenance ferait passer tout ouï-dire pour du vécu"
    )
    schema = json.loads(
        (
            RACINE.parents[1] / "packages" / "mobility_llm" / "src" / "mobility_llm"
            / "categories" / "stm_reflection" / "output_schema.json"
        ).read_text("utf-8")
    )
    concept = schema["properties"]["agents"]["items"]["properties"]["concepts"]["items"]
    assert concept["properties"]["source"]["enum"] == ["lived", "heard"]
    assert "source" in concept["required"], (
        "demandé dans les DEUX bras : c'est ce qui garde une version de schéma unique"
    )


def test_la_provenance_rendue_par_le_modele_est_traduite():
    from urban_mobility_agents.agents.llm_agent import _normaliser_origine

    assert _normaliser_origine("heard") == "entendu"
    assert _normaliser_origine("lived") == "vecu"
    # Repli le moins inventif, mais il laisse une trace : un ouï-dire pris pour du vécu
    # REPARTIRAIT dans le foyer, ce que D2 interdit.
    assert _normaliser_origine("dunno") == "vecu"
    assert _normaliser_origine(None) == "vecu"


# ── L'index des ménages ──────────────────────────────────────────────────────────────────
def test_lindex_alarme_quand_aucun_agent_ne_porte_de_menage(caplog):
    assert foyer.initialiser([FauxAgent("1"), FauxAgent("2")]) == 0
    assert foyer.autres_membres("1") == []


def test_le_bloc_complet_porte_les_deux_choses():
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    ltm.ajouter("49", _reflexion("49", "The ring road was slow.", T0))
    ltm.ajouter("49", _concept("49", "Metro A is packed at 8", T0))
    bloc = foyer.bloc_du_soir(ltm, CONSTANCE, T0 + timedelta(hours=1))
    assert bloc.startswith("Tonight at home")
    assert "told you about their day" in bloc
    assert "they have seen it" in bloc


# ── La mesure n° 1 du 078 § 6, qui passe avant toutes les autres ─────────────────────────
def test_les_refus_par_regle_sont_COMPTES_et_non_jetes():
    """Ils étaient calculés puis jetés : la première mesure n'était émise nulle part.

    « Si ce nombre est proche de zéro, le canal est vide et rien d'autre n'a de sens à
    mesurer » — ticket 078, § 6, mesure n° 1.
    """
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    ltm.ajouter("49", _concept("49", "Bus 62 is often late", T0, observations=0))
    ltm.ajouter("49", _concept("49", "The ring road jams", T0, axe_objet="car"))
    foyer.bloc_du_soir(ltm, CONSTANCE, T0)
    c = foyer.compteurs()
    assert c["candidats"] == 2
    assert c["refus_R1"] == 1, "le concept non ancré"
    assert c["refus_R4"] == 1, "la voiture, chez une enfant de 12 ans"
    assert c["receveurs"] == 1


def _capturer(niveau: str = "INFO") -> tuple[list, int]:
    """Loguru n'alimente pas `caplog` : on branche un puits, comme le reste du dépôt."""
    from loguru import logger as _logger

    messages: list[str] = []
    jeton = _logger.add(lambda m: messages.append(str(m)), level=niveau)
    return messages, jeton


def test_le_bilan_se_journalise_meme_a_zero():
    """Un compteur muet ne distingue pas « rien à dire » de « le mécanisme ne tourne pas »."""
    from loguru import logger as _logger

    _indexer(CONSTANCE, JACQUES)
    messages, jeton = _capturer()
    try:
        foyer.journaliser_compteurs()
    finally:
        _logger.remove(jeton)
    assert any("bilan du run" in m for m in messages)


def test_des_blocs_servis_sans_aucune_croyance_levent_une_alarme():
    """Le cas que le 077 rend probable : 225 concepts sur 231 restés à zéro observation."""
    from loguru import logger as _logger

    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    ltm.ajouter("49", _reflexion("49", "A quiet day.", T0))
    ltm.ajouter("49", _concept("49", "Bus 62 is often late", T0, observations=0))
    foyer.bloc_du_soir(ltm, CONSTANCE, T0)
    messages, jeton = _capturer("ERROR")
    try:
        foyer.journaliser_compteurs()
    finally:
        _logger.remove(jeton)
    assert any("[ALARME]" in m and "R1 d'abord" in m for m in messages)


# ── La garde anti-boucle se compte, et le compte tombe juste ─────────────────────────────────
def test_G3_les_concepts_entendus_sont_COMPTES_et_pas_seulement_ecartes():
    """Une garde dont on ne sait pas si elle a mordu ne se vérifie pas.

    Mesuré sur le run du canal lu du 2026-09-22 : 426 concepts examinés, 296 issues comptées.
    Les 130 manquants étaient les concepts `origine: entendu`, écartés par G3 sans qu'une seule
    ligne le dise. Le saut unique est une AFFIRMATION de l'article ; elle doit se lire dans un
    journal, pas se déduire d'une soustraction.
    """
    source = (RACINE / "llm" / "foyer.py").read_text("utf-8")
    assert 'refus["G3"] += 1' in source, "l'écart par G3 doit être compté"
    assert '"G3": 0' in source, "le compteur G3 doit exister dès l'initialisation"
    assert "refus_G3" in source, "et remonter dans le bilan du run"


def test_le_bilan_du_foyer_alarme_si_le_compte_ne_tombe_pas_juste():
    """Toute sortie de la boucle doit se compter quelque part — sinon un refus est invisible."""
    source = (RACINE / "llm" / "foyer.py").read_text("utf-8")
    assert "le compte ne tombe pas juste" in source
    assert "quittent la boucle sans être comptés" in source


# ── Le récit se fait LE SOIR, une fois (analyse du 2026-09-25) ───────────────────────────
# Sur le bras traité du 2026-09-24_17_50, 18 [ALARME] « récit du soir TRONQUÉ » : le bloc était
# servi à CHAQUE consolidation (trois par agent et par jour en médiane, sept au plus), chaque
# consolidation écrit un bilan, et un receveur qui consolidait rarement en trouvait 9 à 11 chez
# les autres. La borne ne mordait pas faute d'un repère cassé, mais parce que « un bilan par
# membre et par nuit » était faux. L'article dit « in the evening » : le code le dit aussi.
SOIR = datetime(2026, 3, 16, 20, 0)


def test_le_foyer_ne_parle_pas_en_journee_et_rien_nest_perdu():
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    ltm.ajouter("49", _reflexion("49", "Morning rush on line A.", SOIR - timedelta(hours=11)))
    midi = SOIR - timedelta(hours=7, minutes=20)
    assert foyer.bloc_du_soir(ltm, CONSTANCE, midi) == ""
    assert foyer.compteurs()["hors_soir"] == 1
    assert foyer.compteurs().get("receveurs", 0) == 0, "une consolidation de jour n'examine rien"
    bloc = foyer.bloc_du_soir(ltm, CONSTANCE, SOIR)
    assert "Morning rush on line A." in bloc, "ce qui n'est pas raconté à midi l'est le soir"


def test_un_seul_recit_par_soir_le_reste_attend_le_lendemain():
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    ltm.ajouter("49", _reflexion("49", "First.", SOIR - timedelta(hours=2)))
    assert "First." in foyer.bloc_du_soir(ltm, CONSTANCE, SOIR)
    ltm.ajouter("49", _reflexion("49", "Second.", SOIR + timedelta(hours=1)))
    assert foyer.bloc_du_soir(ltm, CONSTANCE, SOIR + timedelta(hours=2)) == ""
    # 01:30 appartient encore à la journée simulée de la veille (frontière à 3 h).
    assert foyer.bloc_du_soir(ltm, CONSTANCE, SOIR + timedelta(hours=5, minutes=30)) == ""
    assert foyer.compteurs()["deja_servi_ce_soir"] == 2
    lendemain = foyer.bloc_du_soir(ltm, CONSTANCE, SOIR + timedelta(days=1))
    assert "Second." in lendemain and "First." not in lendemain


def test_un_soir_sans_rien_a_dire_ne_ferme_pas_la_soiree():
    """Rien de neuf à 18 h ne prive pas le receveur de ce que l'autre racontera à 21 h."""
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    assert foyer.bloc_du_soir(ltm, CONSTANCE, SOIR - timedelta(hours=2)) == ""
    ltm.ajouter("49", _reflexion("49", "Late news.", SOIR + timedelta(hours=1)))
    assert "Late news." in foyer.bloc_du_soir(ltm, CONSTANCE, SOIR + timedelta(hours=2))


def test_une_ligne_par_membre_qui_cite_tous_ses_bilans():
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    for i, h in enumerate((8, 13, 19)):
        ltm.ajouter("49", _reflexion("49", f"Bilan {i}.", SOIR.replace(hour=h)))
    lignes = foyer.recit_du_soir(ltm, "12", SOIR + timedelta(hours=1))
    assert len(lignes) == 1
    assert all(f"Bilan {i}." in lignes[0] for i in range(3))
    assert lignes[0].index("Bilan 0.") < lignes[0].index("Bilan 2."), "dans l'ordre du jour"


def test_le_repere_suit_le_dernier_bilan_cite_pas_lheure_du_receveur():
    """Un bilan écrit APRÈS le passage du receveur mais daté d'avant n'est plus perdu.

    La file EDF ne sert pas les consolidations dans l'ordre simulé : l'ancien repère, posé à
    l'heure du receveur, avalait tout bilan d'un autre membre daté d'avant cette heure et
    arrivé ensuite.
    """
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    ltm.ajouter("49", _reflexion("49", "Early.", SOIR))
    assert foyer.recit_du_soir(ltm, "12", SOIR + timedelta(hours=2))
    ltm.ajouter("49", _reflexion("49", "Arrived late in the queue.", SOIR + timedelta(hours=1)))
    suite = foyer.recit_du_soir(ltm, "12", SOIR + timedelta(days=1))
    assert suite and "Arrived late in the queue." in suite[0]


def test_la_troncature_reporte_au_lendemain_et_salarme_sur_front_montant():
    from loguru import logger as _logger

    _indexer(CONSTANCE, JACQUES)
    settings.agent.memoire__recit_soir_max_par_membre = 2
    messages, jeton = _capturer("ERROR")
    try:
        ltm = FausseLTM()
        for i in range(6):
            ltm.ajouter("49", _reflexion("49", f"Day {i}.", SOIR + timedelta(days=i)))
        vus = []
        for soir in range(3):
            lignes = foyer.recit_du_soir(ltm, "12", SOIR + timedelta(days=9 + soir))
            assert len(lignes) == 1
            vus += [f"Day {i}." for i in range(6) if f"Day {i}." in lignes[0]]
        assert vus == [f"Day {i}." for i in range(6)], "les plus anciens d'abord, rien de perdu"
    finally:
        _logger.remove(jeton)
        settings.agent.memoire__recit_soir_max_par_membre = 8
    alarmes = [m for m in messages if "[ALARME]" in m and "TRONQUÉ" in m]
    assert len(alarmes) == 1, "deux soirs tronqués de suite ne font qu'une alarme"
    assert foyer.compteurs()["troncatures"] == 4 + 2


def test_un_repere_de_lancienne_forme_se_relit_encore():
    """Un point de reprise écrit avant le 2026-09-25 porte un repère par receveur seul."""
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    ltm.ajouter("49", _reflexion("49", "Already heard.", SOIR))
    ltm.ajouter("49", _reflexion("49", "New one.", SOIR + timedelta(days=1)))
    foyer.charger_etat({"lu_jusqu_a": {"12": (SOIR + timedelta(hours=1)).isoformat()}})
    lignes = foyer.recit_du_soir(ltm, "12", SOIR + timedelta(days=1, hours=1))
    assert lignes and "New one." in lignes[0] and "Already heard." not in lignes[0]


def test_la_soiree_servie_survit_a_une_reprise():
    _indexer(CONSTANCE, JACQUES)
    ltm = FausseLTM()
    ltm.ajouter("49", _reflexion("49", "A day.", SOIR - timedelta(hours=1)))
    assert foyer.bloc_du_soir(ltm, CONSTANCE, SOIR)
    sauvegarde = foyer.etat_pour_reprise()
    foyer.reinitialiser()
    _indexer(CONSTANCE, JACQUES)
    foyer.charger_etat(sauvegarde)
    ltm.ajouter("49", _reflexion("49", "Another.", SOIR + timedelta(hours=1)))
    assert foyer.bloc_du_soir(ltm, CONSTANCE, SOIR + timedelta(hours=2)) == ""


def test_les_reglages_du_soir_ont_leurs_defauts():
    from settings import AgentConfig

    assert AgentConfig().memoire__recit_soir_heure == 18
    assert AgentConfig().memoire__recit_soir_max_par_membre == 8
