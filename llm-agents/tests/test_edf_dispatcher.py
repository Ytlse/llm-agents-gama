"""Tests du dispatcher EDF (ticket 003) : la file de priorité sert les tâches de
planification par échéance croissante (heure de départ simulée), et non dans
l'ordre d'arrivée.

Le heap + les consommateurs sont testés sur une instance minimale (SimulationLoopV1
construit via __new__ pour éviter les dépendances world_model / trip_helper), en ne
peuplant que les attributs touchés par _dispatch / _edf_consumer. Les tests pilotent
la boucle asyncio via asyncio.run (pas de dépendance à pytest-asyncio).

Lancement : cd llm-agents && .venv/bin/python -m pytest tests/test_edf_dispatcher.py
"""

import asyncio

import settings as settings_module
from urban_mobility_agents.simulation_controller import SimulationLoopV1


def _make_loop(edf_enabled: bool = True) -> SimulationLoopV1:
    settings_module.settings.world.edf_enabled = edf_enabled
    loop = SimulationLoopV1.__new__(SimulationLoopV1)
    loop._edf_heap = []
    loop._edf_seq = 0
    loop._edf_event = asyncio.Event()
    loop._edf_consumers = []
    loop._inflight_tasks = set()
    return loop


async def _drain(loop: SimulationLoopV1, n_consumers: int = 1, timeout: float = 2.0) -> None:
    """Lance n_consumers consommateurs, attend que la file soit vide, puis les annule."""
    consumers = [asyncio.create_task(loop._edf_consumer(i)) for i in range(n_consumers)]
    loop._edf_consumers = consumers

    async def _wait_empty():
        while loop._edf_heap:
            await asyncio.sleep(0.005)
        await asyncio.sleep(0.02)  # laisse la dernière coroutine se terminer

    await asyncio.wait_for(_wait_empty(), timeout=timeout)
    for c in consumers:
        c.cancel()
    await asyncio.gather(*consumers, return_exceptions=True)


def test_ordre_croissant_des_deadlines_avec_un_consommateur():
    async def _scenario():
        loop = _make_loop()
        executed: list[float] = []

        def _job(d):
            async def _run():
                executed.append(d)
            return _run

        for d in (500.0, 100.0, 900.0, 300.0, 700.0):
            loop._dispatch(deadline_sim=d, kind="plan", make_coro=_job(d), person_id="p")

        await _drain(loop, n_consumers=1)
        return executed

    assert asyncio.run(_scenario()) == [100.0, 300.0, 500.0, 700.0, 900.0]


def test_refill_lointain_ne_passe_pas_devant_un_plan_proche():
    async def _scenario():
        loop = _make_loop()
        executed: list[str] = []

        def _job(tag):
            async def _run():
                executed.append(tag)
            return _run

        # Un refill à J+1 soumis AVANT un plan urgent
        loop._dispatch(deadline_sim=1_000_000.0, kind="refill", make_coro=_job("refill_lointain"), person_id="p")
        loop._dispatch(deadline_sim=10.0, kind="plan", make_coro=_job("plan_proche"), person_id="p")

        await _drain(loop, n_consumers=1)
        return executed

    assert asyncio.run(_scenario()) == ["plan_proche", "refill_lointain"]


def test_push_passe_devant_tout():
    async def _scenario():
        loop = _make_loop()
        executed: list[str] = []

        def _job(tag):
            async def _run():
                executed.append(tag)
            return _run

        loop._dispatch(deadline_sim=5.0, kind="plan", make_coro=_job("plan"), person_id="p")
        loop._dispatch(deadline_sim=0.0, kind="push", make_coro=_job("push"), person_id="p")

        await _drain(loop, n_consumers=1)
        return executed

    assert asyncio.run(_scenario())[0] == "push"


def test_snapshot_exclut_les_push():
    async def _scenario():
        loop = _make_loop()

        async def _noop():
            return None

        loop._dispatch(deadline_sim=300.0, kind="plan", make_coro=_noop, person_id="p")
        loop._dispatch(deadline_sim=100.0, kind="refill", make_coro=_noop, person_id="p")
        loop._dispatch(deadline_sim=0.0, kind="push", make_coro=_noop, person_id="p")
        return loop.edf_snapshot_deadlines(), loop.edf_queue_depth

    deadlines, depth = asyncio.run(_scenario())
    assert deadlines == [100.0, 300.0]
    assert depth == 3


def test_edf_desactive_utilise_le_spawn_direct():
    async def _scenario():
        loop = _make_loop(edf_enabled=False)
        executed: list[str] = []

        def _job(tag):
            async def _run():
                executed.append(tag)
            return _run

        # Sans EDF, _dispatch fait un _spawn direct (fire-and-forget), rien en file.
        loop._dispatch(deadline_sim=5.0, kind="plan", make_coro=_job("a"), person_id="p")
        heap_empty = (loop._edf_heap == [])
        await asyncio.gather(*list(loop._inflight_tasks), return_exceptions=True)
        return heap_empty, executed

    heap_empty, executed = asyncio.run(_scenario())
    assert heap_empty
    assert executed == ["a"]
