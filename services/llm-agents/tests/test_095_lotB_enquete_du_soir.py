"""Ticket 095, lot B — l'enquête du soir, alignée sur Adam & Gaudou (2025).

Contrat : `specs/ticket_095/tests.md`, sections D, E et F.

Pourquoi ce fichier existe. L'enquête existe depuis le ticket 077 et n'a jamais tourné : les
quatre variables `EXPERIMENT_*` n'étaient pas déclarées dans compose. Mais le passe-plat ne
suffisait pas — la perception servie au modèle tenait en quatre champs (nom, âge, genre,
occupation). Telle qu'écrite, la sonde mesurait l'a priori du modèle de base sur une femme de
53 ans à temps partiel : identique au jour 12 et au jour 29, identique dans les deux bras. Elle
n'aurait rien détecté, et son silence aurait été pris pour une absence d'effet.

Deux exigences distinctes sont testées ici : la FIDÉLITÉ en entrée (section D) et l'ÉTANCHÉITÉ
en sortie (section E). Le module ne portait que la seconde.
"""

import asyncio
import csv
import sys
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm import noyau as noyau_module
from llm.memory import MemoryEntry, MemoryType
from llm.noyau import memoire_noyau, noter_trajet
from settings import settings
from sim_clock import wall_clock
from urban_mobility_agents import enquetes

T0 = 1773637200


# ── Un agent LLM de papier, qui porte juste ce dont la sonde a besoin ────────────


class _MemoireFactice:
    def __init__(self, entrees, journal):
        self.user_metadata = {"899549": {"entries": entrees}}
        self._journal = journal
        self.rappels = 0  # compte les renforcements : doit rester à 0

    def journal_trajets(self, person_id):
        return self._journal


class _ClientFactice:
    """Note chaque appel et rend six scores. Le provider est fixe et connu des tests."""

    def __init__(self, scores=None, echoue_sur=None, vide_sur=None):
        self.appels: list[dict] = []
        self._scores = scores or dict.fromkeys(enquetes.CRITERES, 5)
        self._echoue_sur = echoue_sur or set()
        self._vide_sur = vide_sur or set()

    async def execute(self, payload):
        self.appels.append(payload)
        mode = payload["agents"][0].get("mode_interroge")
        if mode in self._echoue_sur:
            raise RuntimeError("passerelle indisponible")
        if mode in self._vide_sur:
            return SimpleNamespace(agents=[], provider_used="google_gemini31_key1")
        return SimpleNamespace(
            agents=[
                SimpleNamespace(
                    agent_id=payload["agents"][0]["agent_id"],
                    scores=dict(self._scores),
                    justification="Une seule phrase, pour l'ensemble.",
                )
            ],
            provider_used="google_gemini31_key1",
        )


def _choc(texte="panne sur voie rapide", gravite=0.70, jours=1.0):
    return MemoryEntry(
        content=texte,
        timestamp=wall_clock(T0) - timedelta(days=jours),
        memory_type=MemoryType.REFLECTION,
        person_id="899549",
        importance=gravite,
        force=14.56,
    )


def _agent(entrees=None, journal=None, client=None, recit="Corinne, 53 ans, temps partiel."):
    entrees = entrees if entrees is not None else [_choc()]
    journal = journal if journal is not None else {}
    memoire = _MemoireFactice(entrees, journal)
    return SimpleNamespace(
        llm_client=client or _ClientFactice(),
        long_term_memory=memoire,
        get_person_identity_description=lambda person: recit,
    )


def _personne(pid="899549"):
    return SimpleNamespace(person_id=pid, identity=SimpleNamespace(name="Corinne"))


def _jouer(agent, dossier, jour=17, personnes=None):
    return asyncio.run(
        enquetes.executer_enquetes_jalon(
            jour, T0, personnes or [_personne()], agent, Path(dossier)
        )
    )


@pytest.fixture(autouse=True)
def _propre(monkeypatch):
    enquetes.reinitialiser()
    noyau_module.reinitialiser()
    monkeypatch.delenv("EXPERIMENT_SURVEY_MODES", raising=False)
    monkeypatch.delenv("EXPERIMENT_TARGET_PERSONAS", raising=False)
    yield
    enquetes.reinitialiser()
    noyau_module.reinitialiser()


@pytest.fixture
def journal_logs():
    lignes: list[tuple[str, str]] = []
    sink = logger.add(
        lambda m: lignes.append((m.record["level"].name, m.record["message"])), level="INFO"
    )
    yield lignes
    logger.remove(sink)


def _lire(dossier) -> list[dict]:
    fichier = Path(dossier) / "affinites_declarees.csv"
    if not fichier.is_file():
        return []
    with open(fichier, encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ══════════════════════ D — fidélité en entrée ══════════════════════════════════


def test_D1_la_perception_porte_les_trois_blocs_de_la_memoire_noyau():
    """D1 — sans eux, la sonde interroge le modèle de base sur un âge et une occupation."""
    journal = {}
    for _ in range(4):
        noter_trajet(journal, "work", "matin", "car")
    agent = _agent(entrees=[_choc()], journal=journal)
    perception = enquetes.perception_de(agent, _personne(), T0)
    assert "Mes habitudes" in perception
    assert "Ce qui a changé récemment" in perception
    assert "panne sur voie rapide" in perception


def test_D2_la_perception_porte_le_recit_d_identite_complet():
    """D2 — le MÊME que celui du prompt de décision, pas un résumé parallèle."""
    perception = enquetes.perception_de(_agent(recit="Corinne, 53 ans, deux véhicules."), _personne(), T0)
    assert "Corinne, 53 ans, deux véhicules." in perception


def test_D3_un_bloc_memoire_vide_ne_fabrique_pas_de_titre_creux():
    """D3 — un titre sans contenu dit au modèle qu'il devrait y avoir quelque chose."""
    perception = enquetes.perception_de(_agent(entrees=[], journal={}), _personne(), T0)
    assert "Ce qui a changé récemment" not in perception
    assert "Mes habitudes" not in perception


def test_D4_la_sonde_voit_passer_le_temps():
    """D4 — J17 et J40 ne rendent pas la même perception : c'est tout l'enjeu du lot.

    Au jour 17 le souvenir de choc est dans le bloc ; 30 jours plus tard, sa durée dérivée
    (15,29 j à gravité 0,70) l'en a fait sortir.
    """
    agent = _agent(entrees=[_choc(jours=1.0)])
    tot = enquetes.perception_de(agent, _personne(), T0)
    tard = enquetes.perception_de(agent, _personne(), T0 + 30 * 86400)
    assert "panne sur voie rapide" in tot
    assert "panne sur voie rapide" not in tard


def test_D5_le_bloc_est_celui_du_prompt_de_decision_caractere_pour_caractere():
    """D5 — une variante « allégée » divergerait en silence, et on ne saurait plus quoi comparer."""
    journal = {}
    for _ in range(4):
        noter_trajet(journal, "work", "matin", "car")
    entrees = [_choc()]
    agent = _agent(entrees=entrees, journal=journal)
    attendu = "\n".join(memoire_noyau(journal, entrees, wall_clock(T0), "899549"))
    assert attendu in enquetes.perception_de(agent, _personne(), T0)


# ══════════════════════ E — étanchéité en sortie ════════════════════════════════


def test_E3_l_enquete_n_est_pas_un_rappel(tmp_path):
    """E3 — une sonde qui renforce la force prolonge la durée de vie de ce qu'elle observe."""
    souvenir = _choc()
    force_avant, rappel_avant = souvenir.force, souvenir.dernier_rappel
    agent = _agent(entrees=[souvenir])
    _jouer(agent, tmp_path)
    assert souvenir.force == force_avant
    assert souvenir.dernier_rappel == rappel_avant
    assert souvenir.rappels == 0


def test_E2_aucune_entree_n_est_ajoutee_en_memoire(tmp_path):
    """E2 — la mémoire longue compte autant d'entrées après qu'avant."""
    entrees = [_choc()]
    agent = _agent(entrees=entrees)
    _jouer(agent, tmp_path)
    assert agent.long_term_memory.user_metadata["899549"]["entries"] == entrees
    assert len(entrees) == 1


def test_E5_la_reponse_n_atteint_que_le_csv(tmp_path):
    """E5 — un seul fichier écrit, et c'est celui-là."""
    _jouer(_agent(), tmp_path)
    ecrits = sorted(p.name for p in Path(tmp_path).iterdir())
    assert ecrits == ["affinites_declarees.csv"]


# ══════════════════════ F — les cinq prompts et leur sortie ═════════════════════


def test_F1_un_jalon_declenche_cinq_appels(tmp_path):
    """F1 — quatre modes plus les priorités."""
    client = _ClientFactice()
    _jouer(_agent(client=client), tmp_path)
    assert len(client.appels) == 5


def test_F2_un_prompt_de_mode_ne_cite_aucun_autre_mode(tmp_path):
    """F2 — nommé seul, le mode se note en ABSOLU ; les 24 scores d'un coup donnaient une grille plate."""
    client = _ClientFactice()
    _jouer(_agent(client=client), tmp_path)
    interroges = [a["agents"][0]["mode_interroge"] for a in client.appels]
    assert interroges == [
        "the car", "public transport", "the bicycle", "walking", None
    ]
    assert len(set(interroges[:4])) == 4


def test_F3_le_prompt_de_priorites_ne_nomme_aucun_mode(tmp_path):
    """F3 — c'est le second vecteur d'Adam & Gaudou, indépendant de tout mode."""
    client = _ClientFactice()
    _jouer(_agent(client=client), tmp_path)
    assert client.appels[-1]["agents"][0]["mode_interroge"] is None


def test_F6_les_modes_sont_declares(monkeypatch, tmp_path):
    """F6 — codés en dur, ils rendraient l'instrument aveugle aux chocs C4 et C5."""
    monkeypatch.setenv("EXPERIMENT_SURVEY_MODES", "voiture,train")
    enquetes.reinitialiser()
    client = _ClientFactice()
    _jouer(_agent(client=client), tmp_path)
    assert len(client.appels) == 3  # deux modes + priorités
    assert client.appels[1]["agents"][0]["mode_interroge"] == "the train"


def test_F6b_un_mode_inconnu_est_ecarte_et_signale(monkeypatch, journal_logs):
    """F6b — un mode sans libellé poserait six questions dans le vide."""
    monkeypatch.setenv("EXPERIMENT_SURVEY_MODES", "voiture,trottinette")
    enquetes.reinitialiser()
    assert enquetes.modes_interroges() == ("voiture",)
    assert [m for n, m in journal_logs if n == "ERROR" and "trottinette" in m]


def test_F7_le_csv_est_en_format_long(tmp_path):
    """F7 — le format large à 24 colonnes obligeait à réécrire l'en-tête à chaque mode ajouté."""
    _jouer(_agent(), tmp_path)
    lignes = _lire(tmp_path)
    assert len(lignes) == 5 * len(enquetes.CRITERES)
    assert set(lignes[0]) == set(enquetes.COLONNES_CSV)
    voiture = [l for l in lignes if l["mode"] == "voiture"]
    assert sorted(l["critere"] for l in voiture) == sorted(enquetes.CRITERES)


def test_F8_les_priorites_sont_dans_le_meme_fichier(tmp_path):
    """F8 — un second fichier obligerait à les rapprocher pour calculer le score."""
    _jouer(_agent(), tmp_path)
    prio = [l for l in _lire(tmp_path) if l["mode"] == enquetes.MODE_PRIORITES]
    assert len(prio) == len(enquetes.CRITERES)


def test_F9_chaque_ligne_porte_le_fournisseur_et_le_modele(tmp_path):
    """F9 — une décision lue sans son modèle oblige à recouper deux fichiers (lot E)."""
    lignes = _jouer(_agent(), tmp_path) or _lire(tmp_path)
    for ligne in _lire(tmp_path):
        assert ligne["provider"] == "google_gemini31_key1"
        assert ligne["model"] and ligne["model"] != ""


def test_F10_un_score_hors_domaine_est_alarme_et_ecrit_tel_quel(tmp_path, journal_logs):
    """F10 — raboter un 14 en 10 fabriquerait un avis maximal là où l'échelle n'a pas été suivie."""
    scores = dict.fromkeys(enquetes.CRITERES, 5) | {"securite": 14}
    _jouer(_agent(client=_ClientFactice(scores=scores)), tmp_path)
    alarmes = [m for n, m in journal_logs if n == "ERROR" and "hors du domaine" in m]
    assert alarmes
    valeurs = {l["score"] for l in _lire(tmp_path) if l["critere"] == "securite"}
    assert valeurs == {"14"}


def test_F11_un_jalon_muet_leve_une_alarme(tmp_path, journal_logs):
    """F11 — un silence se lirait comme « rien n'a bougé », ce qui est le pire des comptes rendus."""
    tous = {"the car", "public transport", "the bicycle", "walking", None}
    _jouer(_agent(client=_ClientFactice(vide_sur=tous)), tmp_path)
    assert [m for n, m in journal_logs if n == "ERROR" and "SANS AUCUNE réponse" in m]
    assert _lire(tmp_path) == []


def test_F12_un_appel_en_echec_n_emporte_pas_les_autres(tmp_path, journal_logs):
    """F12 — l'enquête est partielle, et elle le dit."""
    _jouer(_agent(client=_ClientFactice(echoue_sur={"the bicycle"})), tmp_path)
    lignes = _lire(tmp_path)
    assert {l["mode"] for l in lignes} == {
        "voiture", "transports_collectifs", "marche", enquetes.MODE_PRIORITES
    }
    assert [m for n, m in journal_logs if n == "ERROR" and "incomplet" in m]


def test_F13_la_formule_de_score_se_calcule_depuis_le_seul_csv(tmp_path):
    """F13 — `score(mode) = Σ val(mode, critère) × prio(critère)`, sans autre source."""
    scores = {"rapidite": 8, "praticite": 7, "confort": 6, "securite": 5, "cout": 4, "ecologie": 3}
    _jouer(_agent(client=_ClientFactice(scores=scores)), tmp_path)
    lignes = _lire(tmp_path)
    prio = {
        l["critere"]: int(l["score"])
        for l in lignes
        if l["mode"] == enquetes.MODE_PRIORITES
    }
    val = {
        l["critere"]: int(l["score"]) for l in lignes if l["mode"] == "voiture"
    }
    assert sum(val[c] * prio[c] for c in enquetes.CRITERES) == sum(
        scores[c] * scores[c] for c in enquetes.CRITERES
    )


def test_E1_E4_frontiere_le_module_n_importe_rien_qui_ecrive_la_memoire():
    """E1 et E4 — l'étanchéité se prouve sur les IMPORTS, pas sur une intention.

    Un test qui vérifie « la STM n'a pas bougé » sur un agent de papier ne prouve rien : c'est
    l'agent de papier qui n'a pas de STM. Ce qui se prouve, c'est que le module n'a aucun moyen
    d'écrire — ni mémoire courte, ni mémoire longue, ni ChromaDB, ni journal de mémoire.

    `memoire_noyau` est la seule porte ouverte sur la mémoire, et elle ne fait que LIRE.
    """
    import ast

    source = Path(enquetes.__file__).read_text(encoding="utf-8")
    arbre = ast.parse(source)
    importes = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.ImportFrom) and noeud.module:
            importes.add(noeud.module)
        elif isinstance(noeud, ast.Import):
            importes.update(a.name for a in noeud.names)

    interdits = {
        "llm.shortterm", "llm.longterm", "llm.memory", "llm.journal_memoire",
        "llm.concepts", "chromadb",
    }
    assert not (importes & interdits), (
        "le module d'enquête importe de quoi écrire la mémoire : "
        + ", ".join(sorted(importes & interdits))
    )
    assert "llm.noyau" in importes, (
        "la mémoire noyau est la porte d'ENTRÉE de la sonde : sans elle, l'enquête mesure le "
        "modèle de base."
    )
    # Aucune écriture de mémoire, même par un attribut d'objet passé en paramètre. La
    # recherche porte sur les APPELS de l'arbre syntaxique et non sur le texte : le module
    # NOMME `force_apres_rappel` dans sa docstring, précisément pour dire qu'il ne l'appelle pas.
    appeles = {
        n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
        for n in ast.walk(arbre)
        if isinstance(n, ast.Call)
    }
    interdits_appels = {"aadd_memory", "add_message", "remove_batch", "force_apres_rappel"}
    assert not (appeles & interdits_appels), (
        "le module appelle " + ", ".join(sorted(appeles & interdits_appels))
        + " : l'étanchéité est rompue."
    )
