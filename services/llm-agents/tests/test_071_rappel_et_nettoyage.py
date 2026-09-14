"""Ticket 071 — quatre défauts du rappel et du nettoyage de la mémoire longue.

Chaque test échoue sur le comportement d'AVANT le ticket. Les quatre défauts viennent
d'une expertise externe et ont été vérifiés dans le code avant d'être corrigés :

A. le nettoyage comparait des souvenirs en temps simulé à l'horloge de la machine ;
B. les entrées retirées des métadonnées restaient dans l'index vectoriel, et
   l'identifiant de document entrait en collision après un nettoyage ;
C. le filtre par jour ouvré court-circuitait la fenêtre d'âge ;
D. une étiquette d'un seul mot plafonnait à 0,70 au score lexical.
"""

import sys
from datetime import timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm.longterm import MultiUserLongTermMemory
from llm.memory import MemoryEntry, MemoryType
from sim_clock import wall_clock

# 16 mars 2026, 05:00 en heure MURALE de simulation. Les souvenirs portent des
# `datetime` NAÏFS aux champs muraux : les construire autrement réintroduirait le
# fuseau du processus.
T0 = 1773637200


class _Ltm(MultiUserLongTermMemory):
    """Instance nue : ni index ni disque, on ne teste que la logique."""

    def __init__(self):
        self.user_metadata = {}
        self.shared_index = None
        self.long_term_memory_filter_by_datetime = False
        self.metrics = {"queries": 0}
        self._dirty = set()

    # neutralise les I/O disque
    def ensure_user_initialized(self, person_id):
        self.user_metadata.setdefault(person_id, {"entries": []})

    def _save_user_metadata(self, person_id):
        pass


@pytest.fixture()
def ltm():
    return _Ltm()


def _entry(ts, kind=MemoryType.CONVERSATION, pid="42", doc_id=None):
    """Entrée de test, ÉPISODIQUE par défaut.

    ⚠ Le défaut était `CONCEPT` avant le lot 1 du ticket 071. Il a changé parce que la règle
    de rétention a changé : un concept ne se purge plus jamais à l'horloge (registre
    sémantique), si bien qu'un concept ne peut plus servir de cobaye aux tests de nettoyage.
    Ces tests portent sur le MÉCANISME de nettoyage, pas sur la rétention des concepts : ils
    prennent donc une entrée épisodique, et le régime sémantique a ses propres tests.
    """
    return MemoryEntry(
        content="le bus 401 est ponctuel",
        timestamp=ts,
        memory_type=kind,
        person_id=pid,
        tags="bus 401",
        doc_id=doc_id,
    )


# ------------------------------------------------------- A. horloge du nettoyage


def test_le_nettoyage_utilise_le_temps_simule_et_non_la_machine(ltm):
    """Un souvenir d'hier en temps simulé survit, même si la machine est des mois plus tard.

    C'est le défaut central : avec `datetime.now()`, tous les souvenirs d'un run rejouant
    une date passée tombaient hors de la fenêtre et étaient supprimés en bloc.
    """
    base = wall_clock(T0)
    ltm.ensure_user_initialized("42")
    ltm.user_metadata["42"]["entries"] = [
        _entry(base - timedelta(days=1)),  # récent en temps SIMULÉ
        _entry(base - timedelta(days=40)),  # ancien, doit partir
    ]
    ltm.cleanup_user_memories("42", days_threshold=30)
    restants = ltm.user_metadata["42"]["entries"]
    assert len(restants) == 1, (
        "le souvenir d'hier a été supprimé : horloge machine encore en jeu"
    )
    assert restants[0].timestamp == base - timedelta(days=1)


def test_le_nettoyage_abandonne_s_il_ne_peut_pas_dater(ltm):
    """Sans souvenir horodaté, on ne nettoie rien plutôt que de retomber sur la machine."""
    ltm.ensure_user_initialized("42")
    ltm.user_metadata["42"]["entries"] = []
    ltm.cleanup_user_memories("42", days_threshold=30)
    assert ltm.user_metadata["42"]["entries"] == []
    assert "last_cleanup" not in ltm.user_metadata["42"], (
        "un nettoyage abandonné ne se date pas"
    )


def test_le_nettoyage_separe_l_episodique_du_semantique(ltm):
    """Ticket 071, lot 1 — la règle de rétention a CHANGÉ, et ce test dit comment.

    AVANT : un seuil d'âge commun, plus une exemption par TYPE — les réflexions et les
    résumés ne partaient jamais, quel que soit leur âge.

    MAINTENANT, deux régimes (Tulving, 1972) :
      - sémantique (concepts, résumés) : jamais purgé par l'horloge, il se perd par
        contradiction (lot 3) ;
      - épisodique (entrées brutes, réflexions) : purgé quand son poids temporel passe sous
        le seuil. Une réflexion de cent jours, de gravité nulle, pèse 1e-16 : elle part.

    La conséquence à assumer est que les réflexions ne s'accumulent plus sans fin. Celles
    qui portent une forte gravité survivent quand même, par leur durée de vie allongée —
    c'est l'objet de l'assertion finale.
    """
    base = wall_clock(T0)
    ltm.ensure_user_initialized("42")
    marquante = _entry(base - timedelta(days=100), MemoryType.REFLECTION)
    marquante.importance, marquante.force = 1.0, 19.6
    ltm.user_metadata["42"]["entries"] = [
        _entry(base - timedelta(days=100), MemoryType.REFLECTION),  # banale : part
        _entry(base - timedelta(days=100), MemoryType.SUMMARY),     # sémantique : reste
        _entry(base - timedelta(days=100), MemoryType.CONCEPT),     # sémantique : reste
        _entry(base),                                               # récente : reste
    ]
    ltm.cleanup_user_memories("42", days_threshold=30)
    restants = ltm.user_metadata["42"]["entries"]
    types = {str(e.memory_type) for e in restants}

    assert "summary" in types and "concept" in types, "le sémantique ne s'oublie pas à l'horloge"
    assert "reflection" not in types, "une réflexion banale de cent jours pèse 1e-16"
    assert len(restants) == 3

    # Deux réflexions du MÊME âge, trente jours, que seule la gravité distingue. C'est le
    # cœur du lot 1 : la durée de vie d'un souvenir dépend de ce qu'il raconte.
    #   - banale, durée de vie 2,8 j  → poids exp(-30/2,8)  = 2,2e-5, sous le seuil : part
    #   - marquante, durée de vie 19,6 j → poids exp(-30/19,6) = 0,22, bien au-dessus : reste
    # L'entrée d'ancrage fixe le « maintenant » simulé, qui est le souvenir le plus récent de
    # l'agent : sans elle, les deux réflexions auraient zéro jour d'âge et rien ne bougerait.
    marquante.timestamp = base - timedelta(days=30)
    banale = _entry(base - timedelta(days=30), MemoryType.REFLECTION)
    ancre = _entry(base)
    ltm.user_metadata["42"]["entries"] = [banale, marquante, ancre]

    ltm.cleanup_user_memories("42", days_threshold=7)
    restants = ltm.user_metadata["42"]["entries"]

    assert marquante in restants, "la gravité doit décider de la survie, pas le type"
    assert banale not in restants, "une réflexion banale d'un mois ne pèse plus rien"
    assert restants == [marquante, ancre]


def test_la_date_de_nettoyage_est_en_temps_simule(ltm):
    base = wall_clock(T0)
    ltm.ensure_user_initialized("42")
    ltm.user_metadata["42"]["entries"] = [_entry(base)]
    ltm.cleanup_user_memories("42", days_threshold=30)
    assert ltm.user_metadata["42"]["last_cleanup"] == base.isoformat()


# ------------------------------------------- B. suppression dans l'index vectoriel


class _IndexEspion:
    def __init__(self):
        self.supprimes = []

    def delete_ref_doc(self, doc_id, delete_from_docstore=False):
        self.supprimes.append(doc_id)


def test_les_entrees_supprimees_sortent_aussi_de_l_index(ltm):
    """Sans cela, un souvenir oublié continue d'être resservi au modèle."""
    base = wall_clock(T0)
    idx = _IndexEspion()
    ltm.shared_index = idx
    ltm.ensure_user_initialized("42")
    ltm.user_metadata["42"]["entries"] = [
        _entry(base - timedelta(days=40), doc_id="42_0"),
        _entry(base, doc_id="42_1"),
    ]
    ltm.cleanup_user_memories("42", days_threshold=30)
    assert idx.supprimes == ["42_0"], "le souvenir purgé est resté dans l'index"


def test_une_suppression_qui_echoue_ne_perd_pas_les_metadonnees(ltm):
    class _IndexCasse:
        def delete_ref_doc(self, *a, **k):
            raise RuntimeError("index indisponible")

    base = wall_clock(T0)
    ltm.shared_index = _IndexCasse()
    ltm.ensure_user_initialized("42")
    ltm.user_metadata["42"]["entries"] = [
        _entry(base - timedelta(days=40), doc_id="42_0"),
        _entry(base, doc_id="42_1"),
    ]
    ltm.cleanup_user_memories("42", days_threshold=30)  # ne doit pas lever
    assert len(ltm.user_metadata["42"]["entries"]) == 1


def test_les_entrees_sans_identifiant_ne_font_pas_echouer_le_nettoyage(ltm):
    """Entrées écrites avant le ticket 071 : non adressables, donc non supprimables.

    Elles sortent des métadonnées et restent dans l'index. C'est le résiduel assumé du
    ticket, et il est journalisé plutôt que silencieux.
    """
    base = wall_clock(T0)
    idx = _IndexEspion()
    ltm.shared_index = idx
    ltm.ensure_user_initialized("42")
    ltm.user_metadata["42"]["entries"] = [
        _entry(base - timedelta(days=40), doc_id=None),   # ancien, sans identifiant
        _entry(base, doc_id="42_9"),                      # récent : fixe le « maintenant »
    ]
    ltm.cleanup_user_memories("42", days_threshold=30)
    assert idx.supprimes == [], "une entrée sans identifiant n'est pas adressable"
    assert len(ltm.user_metadata["42"]["entries"]) == 1


def test_le_maintenant_est_le_souvenir_le_plus_recent_de_l_agent(ltm):
    """Propriété de `_sim_now` : un agent dont le vécu s'arrête il y a deux mois ne voit
    pas sa mémoire purgée pour autant. Son « maintenant » est sa dernière expérience."""
    base = wall_clock(T0)
    ltm.ensure_user_initialized("42")
    vieux = [_entry(base - timedelta(days=60 + j)) for j in range(3)]
    ltm.user_metadata["42"]["entries"] = list(vieux)
    ltm.cleanup_user_memories("42", days_threshold=30)
    assert len(ltm.user_metadata["42"]["entries"]) == 3


def test_l_identifiant_de_document_est_monotone(ltm):
    """Après un nettoyage la liste raccourcit : un compteur fondé sur sa longueur
    réutiliserait des identifiants déjà indexés."""
    meta = {"entries": [], "next_doc_index": 0}
    ltm.user_metadata["42"] = meta
    vus = []
    for _ in range(3):
        i = meta.get("next_doc_index", len(meta["entries"]))
        meta["next_doc_index"] = i + 1
        vus.append(f"42_{i}")
        meta["entries"].append(_entry(wall_clock(T0), doc_id=vus[-1]))
    meta["entries"] = meta["entries"][:1]  # nettoyage : la liste raccourcit
    i = meta.get("next_doc_index", len(meta["entries"]))
    assert f"42_{i}" not in vus, "collision d'identifiant après nettoyage"


def test_memory_entry_conserve_son_identifiant_au_round_trip():
    e = _entry(wall_clock(T0), doc_id="42_7")
    assert MemoryEntry.from_dict(e.to_dict()).doc_id == "42_7"


def test_memory_entry_relit_un_ancien_format_sans_identifiant():
    d = _entry(wall_clock(T0)).to_dict()
    d.pop("doc_id")
    assert MemoryEntry.from_dict(d).doc_id is None


# --------------------------------------------------- C. cumul des deux filtres


def _filtre(ltm, entry_dt, query_dt, max_past_days, par_date):
    """Réplique la décision de `filter_message`, isolée de la requête vectorielle."""
    ltm.long_term_memory_filter_by_datetime = par_date
    if max_past_days >= 0 and not ltm._filter_memory_by_past_days(
        entry_dt, query_dt, max_past_days
    ):
        return False
    if par_date and query_dt:
        return ltm._filter_memory_by_working_day(
            entry_dt, query_dt
        ) and ltm._filter_memory_by_peak_time(entry_dt, query_dt)
    return True


def test_la_fenetre_d_age_s_applique_meme_avec_le_filtre_par_jour(ltm):
    """Le défaut C : un souvenir de trois ans passait s'il tombait le bon jour de semaine."""
    query = wall_clock(T0)
    vieux = query - timedelta(days=364)  # même jour de semaine, très ancien
    assert vieux.weekday() == query.weekday(), (
        "le cas de test doit isoler le jour de semaine"
    )
    assert _filtre(ltm, vieux, query, 30, par_date=True) is False


def test_la_fenetre_d_age_s_applique_sans_le_filtre_par_jour(ltm):
    query = wall_clock(T0)
    assert _filtre(ltm, query - timedelta(days=40), query, 30, par_date=False) is False
    assert _filtre(ltm, query - timedelta(days=5), query, 30, par_date=False) is True


# ------------------------------------------------ D. plafond des étiquettes


def test_une_etiquette_d_un_seul_mot_peut_atteindre_un(ltm):
    """Le défaut D : elle plafonnait à 0,70 faute de bigrammes."""
    assert ltm._bleu_score("je prends le métro ce soir", "métro") == pytest.approx(1.0)


def test_une_etiquette_de_deux_mots_atteint_toujours_un(ltm):
    assert ltm._bleu_score("le bus 401 est ponctuel", "bus 401") == pytest.approx(1.0)


def test_une_etiquette_mono_terme_absente_vaut_zero(ltm):
    assert ltm._bleu_score("je prends le tram", "métro") == pytest.approx(0.0)


def test_les_bigrammes_comptent_encore_quand_ils_existent(ltm):
    """La pondération 0,7 / 0,3 reste en vigueur dès qu'un bigramme est disponible."""
    s = ltm._bleu_score(
        "bus 401 ponctualité", "401 bus"
    )  # unigrammes oui, bigramme non
    assert s == pytest.approx(0.7)
