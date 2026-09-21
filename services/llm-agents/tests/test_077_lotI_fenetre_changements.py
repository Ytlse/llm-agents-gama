"""Ticket 077, lot I — la fenêtre de « ce qui a changé récemment ».

Contrat : `specs/ticket_077/tests.md`, section I.

Pourquoi ce fichier existe. Sur le run `2026-09-19_07_31`, la voiture disparaît puis revient
exactement quatorze jours après le choc — la valeur de `FENETRE_CHANGEMENTS_JOURS`, écrite en
dur. Le rapport attribue ce retour à la décroissance du souvenir ; la fenêtre prédit la même
date. Rien ne permettait de trancher. Ce lot rend le paramètre réglable (donc ablatable) et sa
sortie visible dans le journal du run.

Il ne change AUCUNE règle de mémoire : mêmes valeurs par défaut, même mécanisme.

⚠ MISE À JOUR DU TICKET 095 — ce que ce fichier décrit est devenu le mode `fixe`. Le défaut du
dépôt est désormais `derivee`, où la durée se calcule souvenir par souvenir depuis la gravité.
Tous les cas ci-dessous posent donc explicitement le mode `fixe` : ils restent le contrat du
bras de contrôle méthodologique, celui qui doit reproduire les campagnes des 19 et 20 septembre
2026. Le contrat du mode dérivé vit dans `test_095_lotA_duree_derivee.py`.
"""

import sys
from datetime import timedelta
from pathlib import Path

import pytest
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm import noyau as noyau_module
from llm.memory import MemoryEntry, MemoryType
from llm.noyau import bloc_changements
from settings import settings
from sim_clock import wall_clock

T0 = 1773637200


def _choc(texte, gravite=0.9, jours=1):
    return MemoryEntry(
        content=texte,
        timestamp=wall_clock(T0) - timedelta(days=jours),
        memory_type=MemoryType.REFLECTION,
        person_id="899549",
        importance=gravite,
        force=19.6,
    )


def _banal(texte, jours=1):
    return MemoryEntry(
        content=texte,
        timestamp=wall_clock(T0) - timedelta(days=jours),
        memory_type=MemoryType.REFLECTION,
        person_id="899549",
        importance=0.0,
        force=2.8,
    )


@pytest.fixture(autouse=True)
def _journal_propre():
    noyau_module.reinitialiser()
    yield
    noyau_module.reinitialiser()


@pytest.fixture(autouse=True)
def _mode_fixe(monkeypatch):
    """Tout ce fichier décrit le mode `fixe` (ticket 095) — il le déclare plutôt qu'il ne l'hérite."""
    monkeypatch.setattr(
        settings.agent, "memoire__mode_fenetre_changements", noyau_module.MODE_FIXE,
        raising=False,
    )


@pytest.fixture
def journal():
    lignes: list[tuple[str, str]] = []
    sink = logger.add(lambda m: lignes.append((m.record["level"].name, m.record["message"])), level="INFO")
    yield lignes
    logger.remove(sink)


@pytest.fixture
def fenetre(monkeypatch):
    def _poser(jours=None, maxi=None):
        if jours is not None:
            monkeypatch.setattr(settings.agent, "memoire__fenetre_changements_jours", jours, raising=False)
        if maxi is not None:
            monkeypatch.setattr(settings.agent, "memoire__changements_max", maxi, raising=False)
    return _poser


# ══════════════════════ I1 à I4 — le réglage ════════════════════════════════════


def test_I1_les_valeurs_par_defaut_ne_bougent_pas():
    """I1 — le comportement historique en mode `fixe` : 14 jours, 3 lignes.

    Le DÉFAUT du dépôt, lui, a changé au ticket 095 : `derivee`. C'est vérifié ici même, pour
    qu'un retour silencieux à `fixe` par défaut se voie dans ce fichier plutôt que dans un run.
    """
    assert settings.agent.memoire__fenetre_changements_jours == 14
    assert settings.agent.memoire__changements_max == 3
    assert (
        type(settings.agent).model_fields["memoire__mode_fenetre_changements"].default
        == noyau_module.MODE_DERIVEE
    )
    assert bloc_changements([_choc("panne", jours=13)], wall_clock(T0))
    assert bloc_changements([_choc("panne", jours=15)], wall_clock(T0)) == []


def test_I2_la_fenetre_se_regle(fenetre):
    """I2 — c'est ce réglage qui rend le bras d'ablation possible."""
    souvenir = _choc("panne sur voie rapide", jours=10)
    fenetre(jours=7)
    assert bloc_changements([souvenir], wall_clock(T0)) == []
    fenetre(jours=21)
    assert bloc_changements([souvenir], wall_clock(T0))


def test_I3_la_valeur_est_relue_a_chaque_appel(fenetre):
    """I3 — figée à l'import, une surcharge d'environnement ne servirait à rien."""
    souvenir = _choc("panne", jours=10)
    fenetre(jours=7)
    assert bloc_changements([souvenir], wall_clock(T0)) == []
    fenetre(jours=14)
    assert bloc_changements([souvenir], wall_clock(T0))


def test_I4_le_nombre_de_lignes_se_regle(fenetre):
    """I4 — le bloc est plafonné, et le plafond est déclaré."""
    entrees = [_choc("panne A", jours=1), _choc("panne B", jours=2), _choc("panne C", jours=3)]
    fenetre(maxi=1)
    assert len(bloc_changements(entrees, wall_clock(T0))) == 1
    fenetre(maxi=3)
    assert len(bloc_changements(entrees, wall_clock(T0))) == 3


def test_I5_fenetre_a_zero_est_la_valeur_d_ablation(fenetre):
    """I5 — le bras « sans fenêtre » : aucun épisodique de choc n'entre dans le bloc."""
    fenetre(jours=0)
    assert bloc_changements([_choc("panne", jours=0)], wall_clock(T0)) == []
    assert bloc_changements([_choc("panne", jours=13)], wall_clock(T0)) == []


def test_I6_fenetre_negative_est_ramenee_a_zero_et_journalisee(fenetre, journal):
    """I6 — une valeur qui n'a pas de sens ne doit pas se lire comme un réglage accepté."""
    fenetre(jours=-3)
    assert bloc_changements([_choc("panne", jours=1)], wall_clock(T0)) == []
    assert [m for n, m in journal if n == "WARNING" and "négative" in m]


# ══════════════════════ I7 à I10 — la sortie de fenêtre se voit ═════════════════


def test_I7_la_sortie_de_fenetre_est_journalisee(journal, fenetre):
    """I7 — l'événement qui, le 13 avril, coïncide avec le retour de la voiture."""
    fenetre(jours=14)
    bloc_changements([_choc("panne sur voie rapide", jours=15)], wall_clock(T0), person_id="899549")
    sorties = [m for n, m in journal if "sorti" in m and "899549" in m]
    assert sorties, "la sortie de fenêtre n'a laissé aucune trace dans le journal"
    assert "14" in sorties[0], "la fenêtre appliquée n'est pas dite"


def test_I8_un_souvenir_encore_dans_la_fenetre_ne_journalise_rien(journal, fenetre):
    """I8 — l'événement est la SORTIE, pas la présence."""
    fenetre(jours=14)
    assert bloc_changements([_choc("panne", jours=3)], wall_clock(T0), person_id="899549")
    assert not [m for _, m in journal if "sorti" in m]


def test_I9_un_agent_sans_choc_ne_journalise_rien(journal, fenetre):
    """I9 — ne jamais avoir eu de choc n'est pas en sortir."""
    fenetre(jours=14)
    bloc_changements([_banal("trajet ordinaire", jours=30)], wall_clock(T0), person_id="899549")
    assert not [m for _, m in journal if "sorti" in m]


def test_I10_front_montant_une_seule_ligne_par_jour(journal, fenetre):
    """I10 — sinon la ligne se répète à chaque décision et noie ce qu'elle annonce."""
    fenetre(jours=14)
    entrees = [_choc("panne", jours=15)]
    for _ in range(4):
        bloc_changements(entrees, wall_clock(T0), person_id="899549")
    assert len([m for _, m in journal if "sorti" in m]) == 1


def test_I10b_le_lendemain_ne_rejournalise_pas(journal, fenetre):
    """I10 (suite) — la sortie est un événement daté, pas un état quotidien."""
    fenetre(jours=14)
    entrees = [_choc("panne", jours=15)]
    bloc_changements(entrees, wall_clock(T0), person_id="899549")
    bloc_changements(entrees, wall_clock(T0) + timedelta(days=1), person_id="899549")
    assert len([m for _, m in journal if "sorti" in m]) == 1
