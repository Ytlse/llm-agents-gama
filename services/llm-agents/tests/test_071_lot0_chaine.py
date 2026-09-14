"""Ticket 071, lot 0 — tests FONCTIONNELS de la chaîne, avec doublures.

Les tests de `test_071_lot0_constantes.py` verrouillent des valeurs. Ceux-ci verrouillent
un COMPORTEMENT, de bout en bout et à travers les mêmes appels que la production :

- chaîne de LANCEMENT : définition d'expérience → `appliquer_fenetre_age` → configuration ;
- chaîne de RAPPEL : configuration → `aquery_user_memories` → souvenirs réellement servis.

L'index vectoriel et le modèle de plongement sont doublés : ils ne sont pas l'objet du test
et les charger coûterait plusieurs secondes par cas. Tout le reste est le code de production,
y compris le filtre d'âge, le filtre par jour ouvré et le classement.
"""

import sys
from datetime import timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm.longterm import MultiUserLongTermMemory
from settings import settings
from sim_clock import gama_timestamp, wall_clock

# 16 mars 2026, 05:00 en heure MURALE de simulation.
T0 = 1773637200


# ─────────────────────────────── doublures ──────────────────────────────────────


class _ExperienceFictive:
    """Le strict nécessaire de ce que `appliquer_fenetre_age` lit d'une expérience."""

    def __init__(self, horizon_jours: int, memoire: bool = True):
        self.horizon_jours = horizon_jours
        self.memoire = memoire


class _Noeud:
    """Ce que le retriever de LlamaIndex rend : un texte, un score, des métadonnées."""

    def __init__(self, texte: str, score: float, ts, person_id: str):
        self.text = texte
        self.score = score
        self.metadata = {
            "person_id": person_id,
            "timestamp": ts.isoformat(),
            "memory_type": "reflection",
            "tags": "bus 401",
            "doc_id": f"{person_id}_{texte}",
        }


class _RetrieverDouble:
    def __init__(self, noeuds):
        self._noeuds = noeuds

    async def aretrieve(self, _query):
        return list(self._noeuds)


class _IndexDouble:
    """Doublure de l'index partagé : rend des nœuds fixes, sans plongement ni ChromaDB."""

    def __init__(self, noeuds):
        self._noeuds = noeuds
        self.requetes = 0

    def as_retriever(self, **_kwargs):
        self.requetes += 1
        return _RetrieverDouble(self._noeuds)


class _LtmDouble(MultiUserLongTermMemory):
    """Mémoire longue réelle, branchée sur un index doublé et sans disque."""

    def __init__(self, noeuds):
        self.shared_index = _IndexDouble(noeuds)
        self.user_metadata = {}
        self.metadata_access_times = {}
        self.long_term_memory_filter_by_datetime = False
        self.metrics = {"queries": 0, "cache_hits": 0, "cache_misses": 0}
        self._dirty = set()

    def ensure_user_initialized(self, person_id):
        self.user_metadata.setdefault(person_id, {"entries": []})

    def _save_user_metadata(self, person_id):
        pass


@pytest.fixture()
def fenetre_restauree():
    """La fenêtre est un réglage de processus : le test ne doit pas la laisser modifiée."""
    origine = settings.agent.long_term_max_days_query
    yield
    settings.agent.long_term_max_days_query = origine


# ──────────────────── 1. chaîne de lancement, avec une expérience doublée ───────


def test_le_lancement_regle_la_fenetre_sur_l_horizon(fenetre_restauree, capsys):
    from experiences.cli import appliquer_fenetre_age

    retenue = appliquer_fenetre_age(_ExperienceFictive(horizon_jours=5))

    assert retenue == 5
    assert settings.agent.long_term_max_days_query == 5


def test_le_lancement_plafonne_un_horizon_trop_long(fenetre_restauree):
    from experiences.cli import appliquer_fenetre_age

    retenue = appliquer_fenetre_age(_ExperienceFictive(horizon_jours=90))

    assert retenue == settings.agent.memoire__fenetre_age_max_jours == 60


def test_le_lancement_annonce_la_fenetre_retenue(fenetre_restauree, capsys):
    """Un réglage muet ne se distingue pas d'un réglage absent.

    La fenêtre décide de ce que l'agent peut se rappeler : elle doit être lisible dans la
    sortie du lancement, sans avoir à relire le code.
    """
    from experiences.cli import appliquer_fenetre_age

    appliquer_fenetre_age(_ExperienceFictive(horizon_jours=60))
    sortie = capsys.readouterr().out

    assert "fenêtre d'âge au rappel" in sortie
    assert "60 j" in sortie


def test_la_fenetre_est_reglee_meme_si_la_memoire_est_coupee(fenetre_restauree, capsys):
    """Une valeur inerte vaut mieux qu'une valeur fausse si la mémoire est rallumée."""
    from experiences.cli import appliquer_fenetre_age

    assert appliquer_fenetre_age(_ExperienceFictive(horizon_jours=7, memoire=False)) == 7
    assert settings.agent.long_term_max_days_query == 7
    assert "coupée" in capsys.readouterr().out


# ──────────────── 2. chaîne de rappel, de la configuration aux souvenirs servis ─


def _memoire_a_trois_ages(person_id="42"):
    """Trois souvenirs : 10, 45 et 70 jours avant la requête."""
    base = wall_clock(T0)
    return _LtmDouble(
        [
            _Noeud("recent", 0.9, base - timedelta(days=10), person_id),
            _Noeud("second_mois", 0.9, base - timedelta(days=45), person_id),
            _Noeud("hors_horizon", 0.9, base - timedelta(days=70), person_id),
        ]
    )


@pytest.mark.asyncio
async def test_un_run_de_soixante_jours_sert_son_second_mois(fenetre_restauree):
    """C'est le défaut que le lot 0 corrige, vérifié par l'échec.

    À 30 jours — la valeur d'avant — le souvenir de 45 jours était écarté du rappel, donc
    invisible pour la décision, sans qu'aucune ligne de journal ne le dise.
    """
    from experiences.cli import appliquer_fenetre_age

    ltm = _memoire_a_trois_ages()
    appliquer_fenetre_age(_ExperienceFictive(horizon_jours=60))

    servis = await ltm.aquery_user_memories(
        person_id="42",
        query="bus 401",
        top_k=10,
        max_past_days=settings.agent.long_term_max_days_query,
        query_at=gama_timestamp(wall_clock(T0)),
    )
    contenus = {r.content for r in servis}

    assert "recent" in contenus
    assert "second_mois" in contenus, "le second mois est de nouveau rappelé"


@pytest.mark.asyncio
async def test_le_plafond_de_soixante_jours_ecarte_toujours_au_dela(fenetre_restauree):
    """Le plafond reste un filtre réel : la fenêtre s'ouvre, elle ne disparaît pas."""
    from experiences.cli import appliquer_fenetre_age

    ltm = _memoire_a_trois_ages()
    appliquer_fenetre_age(_ExperienceFictive(horizon_jours=60))

    servis = await ltm.aquery_user_memories(
        person_id="42",
        query="bus 401",
        top_k=10,
        max_past_days=settings.agent.long_term_max_days_query,
        query_at=gama_timestamp(wall_clock(T0)),
    )

    assert "hors_horizon" not in {r.content for r in servis}


@pytest.mark.asyncio
async def test_un_horizon_court_referme_la_fenetre(fenetre_restauree):
    """La fenêtre suit l'horizon DANS LES DEUX SENS.

    Sur une expérience de cinq jours, un souvenir de quarante-cinq jours n'a rien à faire
    dans le rappel : il viendrait d'un autre run.
    """
    from experiences.cli import appliquer_fenetre_age

    ltm = _memoire_a_trois_ages()
    appliquer_fenetre_age(_ExperienceFictive(horizon_jours=5))

    servis = await ltm.aquery_user_memories(
        person_id="42",
        query="bus 401",
        top_k=10,
        max_past_days=settings.agent.long_term_max_days_query,
        query_at=gama_timestamp(wall_clock(T0)),
    )

    assert {r.content for r in servis} == set()


@pytest.mark.asyncio
async def test_le_rappel_n_expose_jamais_les_souvenirs_d_un_autre_agent(fenetre_restauree):
    """Invariant d'isolation, re-vérifié côté Python même quand l'index se trompe.

    La doublure rend délibérément un nœud appartenant à un autre agent : c'est le cas
    qu'un filtre délégué au magasin vectoriel ne rattraperait pas tout seul.
    """
    base = wall_clock(T0)
    ltm = _LtmDouble(
        [
            _Noeud("a_moi", 0.9, base - timedelta(days=2), "42"),
            _Noeud("a_quelqu_un_d_autre", 0.99, base - timedelta(days=2), "77"),
        ]
    )
    settings.agent.long_term_max_days_query = 60

    servis = await ltm.aquery_user_memories(
        person_id="42",
        query="bus 401",
        top_k=10,
        max_past_days=settings.agent.long_term_max_days_query,
        query_at=gama_timestamp(wall_clock(T0)),
    )

    assert {r.content for r in servis} == {"a_moi"}
