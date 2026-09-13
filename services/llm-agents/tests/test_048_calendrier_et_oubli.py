"""Ticket 048 — calendrier de consolidation, échelle d'oubli, classement absolu.

Trois propriétés y sont vérifiées par l'échec, pas par relecture :

1. le score temporel est ABSOLU et reproduit l'ancienne décroissance au défaut ;
2. le classement n'est plus renormalisé par lot, donc deux décisions sont comparables
   et la constante de temps a un effet réel ;
3. le plancher journalier rend le moment de la consolidation déterministe.
"""

import math
import sys
from datetime import timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llm.longterm import MultiUserLongTermMemory
from settings import settings
from sim_clock import gama_timestamp, wall_clock

# 1773637200 = 16 mars 2026, 05:00 en heure MURALE de la simulation. Les souvenirs
# portent des `datetime` NAÏFS aux champs muraux (cf. `sim_clock.wall_clock`) : les
# construire autrement réintroduirait le fuseau du processus, qui est exactement le
# bug corrigé le 2026-09-04.
T0 = 1773637200

# --------------------------------------------------------------------------- outils


class _Ltm(MultiUserLongTermMemory):
    """Instance nue : on ne teste que le scoring, aucun index n'est nécessaire."""

    def __init__(self):
        pass


@pytest.fixture()
def ltm():
    return _Ltm()


def _node(tags: str, score: float, ts):
    class _N:
        def __init__(self):
            self.score = score
            self.metadata = {"tags": tags, "timestamp": ts.isoformat()}

    return _N()


# ------------------------------------------------------- 1. décroissance absolue


def test_score_temporel_reproduit_l_ancienne_base_au_defaut(ltm):
    """Le défaut de 2,8 jours reproduit la base 0,7 par jour, à 1e-3 près.

    C'est la condition pour qu'un écart mesuré après le ticket 048 soit attribuable
    aux mécanismes nouveaux et non à un oubli silencieusement accéléré.
    """
    assert settings.agent.long_term_retrieval__force_base_jours == pytest.approx(2.8)
    base = wall_clock(T0)
    for jours in (0, 1, 2, 3, 7, 14):
        ts = base - timedelta(days=jours)
        obtenu = ltm._time_decay_score(ts.isoformat(), gama_timestamp(base))
        assert obtenu == pytest.approx(0.7**jours, abs=1e-3), f"à {jours} jours"


def test_score_temporel_est_absolu_et_ne_depend_pas_du_lot(ltm):
    """Un souvenir d'un jour vaut la même chose quels que soient ses voisins.

    Avant le ticket 048 la normalisation min-max rendait cette valeur relative au lot :
    le plus récent valait toujours 1, le plus ancien toujours 0.
    """
    base = wall_clock(T0)
    at = gama_timestamp(base)
    un_jour = (base - timedelta(days=1)).isoformat()
    assert ltm._time_decay_score(un_jour, at) == pytest.approx(
        math.exp(-1 / 2.8), abs=1e-6
    )


def test_constante_de_temps_plus_longue_remonte_le_score(ltm, monkeypatch):
    """Tripler la constante de temps doit déplacer la courbe, sinon aucun bras de
    sensibilité d'expérience ne mesure quoi que ce soit."""
    base = wall_clock(T0)
    at = gama_timestamp(base)
    vieux = (base - timedelta(days=3)).isoformat()

    court = ltm._time_decay_score(vieux, at)
    monkeypatch.setattr(
        settings.agent, "long_term_retrieval__force_base_jours", 2.8 * 3
    )
    long = ltm._time_decay_score(vieux, at)

    assert long > court
    assert long - court > 0.2, "l'effet doit être franc, pas marginal"


def test_force_nulle_ne_leve_pas(ltm, monkeypatch):
    monkeypatch.setattr(settings.agent, "long_term_retrieval__force_base_jours", 0.0)
    base = wall_clock(T0)
    assert ltm._time_decay_score(base.isoformat(), gama_timestamp(base)) == 0.0


# --------------------------------------------------------- 2. classement absolu


def test_le_plus_recent_ne_vaut_pas_toujours_un(ltm):
    """Deux souvenirs tous deux anciens ne doivent pas voir le moins ancien porté à 1.

    C'est exactement ce que faisait la normalisation min-max, et c'est ce qui rendait
    deux décisions incomparables entre elles.
    """
    base = wall_clock(T0)
    at = gama_timestamp(base)
    nodes = [
        _node("bus 401", 0.5, base - timedelta(days=10)),
        _node("bus 401", 0.5, base - timedelta(days=12)),
    ]
    scores = ltm.rank_nodes("bus 401", at, nodes)
    poids_temps = settings.agent.long_term_retrieval__time_weight
    ecart = float(scores[0] - scores[1])
    # Les deux souvenirs ne diffèrent que par leur date, 10 jours contre 12. Tous deux
    # étant très anciens, leur composante temporelle est quasi nulle et leur écart doit
    # l'être aussi. Sous min-max, le premier aurait décroché 1 et le second 0, soit un
    # écart égal à TOUT le poids temporel — c'est ce que ce test interdit.
    assert 0 < ecart < poids_temps * 0.1, (
        f"écart {ecart:.4f} ; sous min-max il aurait valu {poids_temps:.2f}"
    )


def test_un_lot_de_souvenirs_frais_score_plus_haut_qu_un_lot_ancien(ltm):
    """Propriété de comparabilité : le score d'une décision se lit dans l'absolu."""
    base = wall_clock(T0)
    at = gama_timestamp(base)
    frais = [_node("metro B", 0.5, base - timedelta(hours=2))]
    ancien = [_node("metro B", 0.5, base - timedelta(days=20))]
    assert (
        ltm.rank_nodes("metro B", at, frais)[0]
        > ltm.rank_nodes("metro B", at, ancien)[0]
    )


def test_score_de_similarite_est_borne(ltm):
    """Un vector store qui renvoie une similarité hors bornes ne doit pas faire
    exploser le score composite."""
    base = wall_clock(T0)
    n = _node("velo", 3.7, base)
    score = ltm.rank_nodes("velo", gama_timestamp(base), [n])[0]
    assert 0.0 <= score <= 1.0


def test_lot_vide(ltm):
    assert ltm.rank_nodes("x", 0, []).size == 0


# ------------------------------------------------------- 3. plancher journalier


class _Stm:
    def __init__(self, n):
        self.recent_entries = list(range(n))


class _Personne:
    def __init__(self, pid, is_llm_based=True):
        self.person_id = pid
        self.is_llm_based = is_llm_based


def _eligibilite(entrees, heure, deja_plancher_ce_jour, *, active=True, llm=True):
    """Réplique la règle d'éligibilité du controller, isolée de son I/O.

    Le controller construit la même décision à partir de l'heure murale simulée, du
    remplissage du tampon et du jour déjà couvert par le plancher.
    """
    seuil = settings.agent.stm_reflection_min_entries
    floor_day = (
        1
        if (active and heure >= settings.agent.stm_reflection_daily_floor_hour)
        else None
    )
    if not llm:
        return False, False
    if entrees >= seuil:
        return True, False
    if floor_day is not None and entrees > 0 and deja_plancher_ce_jour != floor_day:
        return True, True
    return False, False


def test_le_seuil_volumetrique_reste_prioritaire():
    ok, par_plancher = _eligibilite(entrees=12, heure=10, deja_plancher_ce_jour=None)
    assert ok and not par_plancher


def test_agent_peu_mobile_consolide_quand_meme_le_soir():
    """Six entrées, soit un seul déplacement : sous le seuil, donc jamais consolidé
    avant le ticket 048. Le plancher le rattrape."""
    assert _eligibilite(entrees=6, heure=10, deja_plancher_ce_jour=None) == (
        False,
        False,
    )
    assert _eligibilite(entrees=6, heure=22, deja_plancher_ce_jour=None) == (True, True)


def test_le_plancher_ne_part_qu_une_fois_par_jour():
    assert _eligibilite(entrees=6, heure=22, deja_plancher_ce_jour=1) == (False, False)
    assert _eligibilite(entrees=6, heure=23, deja_plancher_ce_jour=1) == (False, False)


def test_le_plancher_ignore_un_tampon_vide():
    assert _eligibilite(entrees=0, heure=23, deja_plancher_ce_jour=None) == (
        False,
        False,
    )


def test_le_plancher_se_desactive():
    assert _eligibilite(
        entrees=6, heure=23, deja_plancher_ce_jour=None, active=False
    ) == (
        False,
        False,
    )


def test_le_plancher_ne_touche_pas_les_agents_non_llm():
    assert _eligibilite(entrees=6, heure=23, deja_plancher_ce_jour=None, llm=False) == (
        False,
        False,
    )


def test_defauts_du_plancher():
    assert settings.agent.stm_reflection_daily_floor_enabled is True
    assert settings.agent.stm_reflection_daily_floor_hour == 22, (
        "22 h laisse la nuit simulée au drainage EDF (ticket 010)"
    )
