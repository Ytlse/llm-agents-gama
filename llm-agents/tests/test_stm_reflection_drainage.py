"""Tests du drainage nocturne des réflexions STM (ticket 010).

A1 — l'échéance EDF d'une réflexion est le RÉVEIL de son agent (prochaine
occurrence de la première activité planifiée de la journée), pas un délai fixe :
les décisions du soir passent devant, le stock se draine la nuit dans l'ordre
des réveils. A2 — la composition de la pile (décisions vs réflexions, échéances
dépassées) est exposée par le scénario pour l'alarme backlog.

Lancement : cd llm-agents && .venv/bin/python -m pytest tests/test_stm_reflection_drainage.py
"""

import asyncio

import settings as settings_module
from models import Activity, Location, Person, PersonalIdentity
from urban_mobility_agents.simulation_controller import SimulationLoopV1
from world.population import PersonScheduler

# Jour SIM aligné sur une frontière de 24h Unix (to_24h_timestamp_full fait % 86400)
DAY0 = 20_000 * 86400
H = 3600

_LOC = Location(lat=43.6, lon=1.44)


def _person(activities, person_id="p1") -> Person:
    return Person(
        person_id=person_id,
        identity=PersonalIdentity(name="Test", traits_json={}, activities=activities),
    )


def _activity(act_id, start_h, end_h, purpose="work", scheduled_start_h=None) -> Activity:
    return Activity(
        id=act_id,
        start_time=start_h * H,
        end_time=end_h * H,
        scheduled_start_time=scheduled_start_h * H if scheduled_start_h is not None else None,
        purpose=purpose,
        location=_LOC,
    )


class TestNextWakeupTs:
    """Le réveil = prochaine occurrence du plus petit horaire 24h du planning."""

    def test_le_soir_le_reveil_est_le_lendemain_matin(self):
        # Agent rentré le soir : réflexion déclenchée à 21h15, lever à 8h.
        p = _person([_activity("a1", 8, 17, "work"), _activity("a2", 18, 7, "home")])
        ts_2115 = DAY0 + 21 * H + 15 * 60
        assert PersonScheduler(p).next_wakeup_ts(ts_2115) == DAY0 + 86400 + 8 * H

    def test_apres_minuit_le_reveil_est_le_matin_meme(self):
        # Déclenchement à 0h30 : l'échéance est le lever du jour même (8h),
        # pas celui du jour d'après — la LTM doit être prête avant la première
        # décision qui suit la nuit en cours.
        p = _person([_activity("a1", 8, 17, "work"), _activity("a2", 18, 7, "home")])
        ts_0030 = DAY0 + 30 * 60
        assert PersonScheduler(p).next_wakeup_ts(ts_0030) == DAY0 + 8 * H

    def test_scheduled_start_time_prime_sur_start_time(self):
        # Un départ replanifié plus tôt avance le réveil.
        p = _person([_activity("a1", 8, 17, "work", scheduled_start_h=7),
                     _activity("a2", 18, 7, "home")])
        ts_2100 = DAY0 + 21 * H
        assert PersonScheduler(p).next_wakeup_ts(ts_2100) == DAY0 + 86400 + 7 * H

    def test_sans_activite_horodatee_retourne_none(self):
        # Fallback (stm_reflection_deadline_sim_s) à la charge de l'appelant.
        assert PersonScheduler(_person(None)).next_wakeup_ts(DAY0) is None
        assert PersonScheduler(_person([])).next_wakeup_ts(DAY0) is None

    def test_les_leve_tot_ont_l_echeance_la_plus_proche(self):
        # D2 : le stock se draine dans l'ordre des réveils — EDF sert d'abord
        # l'agent qui se lève à 6h, puis celui de 9h.
        early = _person([_activity("a1", 6, 14, "work"), _activity("a2", 15, 5, "home")], "early")
        late = _person([_activity("a1", 9, 18, "work"), _activity("a2", 19, 8, "home")], "late")
        ts_2200 = DAY0 + 22 * H
        due_early = PersonScheduler(early).next_wakeup_ts(ts_2200)
        due_late = PersonScheduler(late).next_wakeup_ts(ts_2200)
        assert due_early < due_late


def _make_loop() -> SimulationLoopV1:
    """Instance minimale (cf. test_edf_dispatcher) : seuls les attributs lus par
    les compteurs de composition sont peuplés."""
    settings_module.settings.world.edf_enabled = True
    loop = SimulationLoopV1.__new__(SimulationLoopV1)
    loop._edf_heap = []
    loop._edf_seq = 0
    loop._edf_event = asyncio.Event()
    loop._edf_consumers = []
    loop._inflight_tasks = set()
    loop._stm_reflecting = set()
    return loop


async def _noop():
    pass


class TestCompositionDeLaPile:
    """A2 : le scénario distingue décisions en retard et réflexions en attente."""

    def test_overdue_ne_compte_que_les_decisions_a_echeance_depassee(self):
        loop = _make_loop()
        now = 1_000.0
        loop._dispatch(deadline_sim=500.0, kind="plan", make_coro=_noop, person_id="p1")     # en retard
        loop._dispatch(deadline_sim=999.0, kind="refill", make_coro=_noop, person_id="p2")   # en retard
        loop._dispatch(deadline_sim=2_000.0, kind="plan", make_coro=_noop, person_id="p3")   # à l'heure
        loop._dispatch(deadline_sim=0.0, kind="push", make_coro=_noop, person_id="p4")       # sentinelle, exclu
        loop._dispatch(deadline_sim=100.0, kind="reflect", make_coro=_noop, person_id="p5")  # réflexion, exclue
        assert loop.overdue_decision_count(now) == 2

    def test_pile_de_reflexions_nocturne_zero_overdue(self):
        # Profil 2026-08-03 : des réflexions en file, échéances au réveil (futur),
        # aucune décision en souffrance → rien à signaler en ERROR.
        loop = _make_loop()
        now = float(DAY0 + 22 * H)
        for i in range(50):
            pid = f"p{i}"
            loop._stm_reflecting.add(pid)
            loop._dispatch(deadline_sim=now + 10 * H, kind="reflect", make_coro=_noop, person_id=pid)
        assert loop.overdue_decision_count(now) == 0
        assert loop.pending_reflections_count == 50

    def test_pending_reflections_compte_file_et_en_vol(self):
        # _stm_reflecting est peuplé avant _dispatch et vidé en finally : il couvre
        # les réflexions en file EDF ET celles en cours d'exécution.
        loop = _make_loop()
        loop._stm_reflecting.update({"en_file", "en_vol"})
        assert loop.pending_reflections_count == 2
