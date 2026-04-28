"""
Ce module définit la boucle de simulation principale (SimulationLoopV1) pour le scénario.

Son rôle est d'orchestrer le déroulement de la simulation au fil du temps. Il gère :
- La synchronisation de l'état du monde et des agents.
- Le déclenchement des actions des agents (planification des déplacements).
- Le traitement des observations de l'environnement.
- L'orchestration des cycles de réflexion (mémoire à court et long terme) des agents.
"""

import asyncio
import math
import time
from typing import Optional, Tuple
import datetime

from loguru import logger
from gama_models import WorldSyncIdlePeople
from helper import humanize_duration, humanize_time, to_timestamp_based_on_day, humanize_date, to_24h_timestamp_full
from models import Activity, BBox, Person, PersonMove, TravelPlan
from urban_mobility_agents.core.scenario import Action, BaseScenario, Observation
from urban_mobility_agents.utils.history_log import HistoryStreamLog
from urban_mobility_agents.agents.llm_agent import Context, LlmAgent
from text_helper import env_ob_to_text, parse_ob
from trip_helper.base import TripHelper
from utils import random_uuid
from world.population import WorldPopulation
from world.world_data import WorldModel
from settings import settings

from prometheus_client import Counter, Gauge

history_logger = HistoryStreamLog.get_instance()

PROCESS_PERSON_CALLS = Counter('gama_process_person_calls_total', 'Total calls to process_person')
EVALUATE_PLAN_CALLS = Counter('gama_evaluate_plan_calls_total', 'Total calls to evaluate_and_choose_travel_plan')
ACTIONS_CREATED = Counter('gama_actions_created_total', 'Total actions created')
PLANNING_LATE = Counter('controller_planning_late_total', 'Agents dont la date de départ était déjà passée lors de la planification')
ITINERARY_100_COMPLETION = Gauge('agent_itinerary_100_completion_seconds', 'Durée réelle (secondes) pour traiter 100 itinéraires réussis consécutifs')
BOOTSTRAP_DURATION = Gauge('agent_bootstrap_duration_seconds', 'Durée réelle (secondes) du bootstrap_all_agents (calcul initial des itinéraires au /init)')


def _estimate_fallback_duration(origin, destination) -> int:
    """Estimate travel time in seconds from crow-flies distance at 30 km/h with 1.3 detour factor."""
    if origin is None or destination is None:
        return 30 * 60
    lat1, lon1 = math.radians(origin.lat), math.radians(origin.lon)
    lat2, lon2 = math.radians(destination.lat), math.radians(destination.lon)
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    distance_m = 2 * 6_371_000 * math.asin(math.sqrt(a))
    road_distance_m = distance_m * 1.3
    speed_ms = 30_000 / 3600  # 30 km/h
    return max(5 * 60, int(road_distance_m / speed_ms))


class SimulationLoopV1(BaseScenario):
    MAX_ADJUST_START_TIME = 15*60  # 15 minutes

    def __init__(self,
                 world_model: "WorldModel",
                 trip_helper: "TripHelper" = None,
                 agent: Optional["LlmAgent"] = None):
        self.MAX_ADJUST_START_TIME = settings.agent.max_reschedule_amount or self.MAX_ADJUST_START_TIME
        self._messages = []
        self._late_count = 0
        self._itinerary_success_count = 0
        self._itinerary_window_start = time.monotonic()
        self.model = world_model
        self.trip_helper = trip_helper
        self.agent = agent
        # schedule next reflection
        self.reflect_period = settings.agent.long_term_reflect_interval
        self.next_reflection_at = None
        self.next_self_reflection_at = None

        if settings.agent.reschedule_activity__version == 2:
            self.reschedule_amount_function = self.reschedule_amount_v2
            logger.info("Using reschedule activity function version v2")
        else:
            self.reschedule_amount_function = self.reschedule_amount
            logger.info("Using reschedule activity function version v1")

    @property
    def population(self) -> "WorldPopulation":
        """Get the current population of the scenario"""
        return self.model.population

    @property
    def world_bbox(self) -> BBox:
        return self.model.bbox

    async def sync(self, timestamp: int, idle_people: list[WorldSyncIdlePeople] = None):
        _sync_start = time.monotonic()
        all_people = self.population.get_people_list()
        currently_idle = [p for p in all_people if p.state.heading_to is None]
        currently_moving = [p for p in all_people if p.state.heading_to is not None]
        logger.info(
            f"[sync] START sim_time={humanize_date(timestamp)} "
            f"total_people={len(all_people)} idle={len(currently_idle)} moving={len(currently_moving)} "
            f"gama_idle_update={len(idle_people) if idle_people else 0} "
            f"late_since_last_sync={self._late_count}"
        )
        self._late_count = 0

        # --- Phase 1 : mise à jour d'état depuis GAMA (rapide, synchrone) ---
        # Doit être fait avant de retourner pour que les nouveaux arrivants
        # soient visibles comme "idle" lors du scheduling qui suit.
        if idle_people:
            for person_data in idle_people:
                personPy = self.population.get_person(person_data.person_id)
                if personPy:
                    # On met à jour la dernière location connue de la personne, même si elle est en train de se déplacer vers une destination (heading_to).
                    personPy.state.last_location = person_data.location
                    # TODO le scheduler ne devrait pas être instancié à chaque fois, voir être un attribut de Person
                    self.population.get_person_default_scheduler(personPy).finish_activity()
                else:
                    logger.warning(f"[sync] Person {person_data.person_id} not found in population")

        # --- Phase 2 : reflection (peu fréquente, on la garde ici) ---
        if not self.next_reflection_at:
            self.next_reflection_at = timestamp + self.reflect_period
        elif timestamp >= self.next_reflection_at:
            logger.info(f"[timestamp: {humanize_date(timestamp)}] Reflecting the state of the world")
            await self.trigger_short_term_reflection_for_all(timestamp=timestamp)
            self.next_reflection_at = timestamp + self.reflect_period

        if settings.agent.long_term_self_reflect_enabled:
            if not self.next_self_reflection_at:
                self.next_self_reflection_at = timestamp + settings.agent.long_term_self_reflect_interval_days*24*3600
            elif timestamp >= self.next_self_reflection_at:
                logger.info(f"[timestamp: {humanize_date(timestamp)}] Self reflecting the state of the world")
                _duration_days = settings.agent.long_term_self_reflect_window_days
                from_date = datetime.datetime.fromtimestamp(timestamp) - datetime.timedelta(days=_duration_days)
                from_date = from_date.replace(hour=0, minute=0, second=0, microsecond=0)
                await self.agent.trigger_long_term_reflection_for_all_people(timestamp=timestamp, from_date=from_date, people=self.population.get_people_list())
                self.next_self_reflection_at = timestamp + settings.agent.long_term_self_reflect_interval_days*24*3600

        # --- Phase 3 : scheduling (toujours fire-and-forget) ---
        # Le bootstrap initial est géré dans /init, pas ici.
        _task = asyncio.create_task(self.schedule_person_move(timestamp=timestamp))
        _task.add_done_callback(
            lambda t: logger.error(f"[schedule_move] task error: {t.exception()}") if not t.cancelled() and t.exception() else None
        )
        _sync_duration = time.monotonic() - _sync_start
        logger.info(
            f"[sync] END sim_time={humanize_date(timestamp)} "
            f"state_update_duration={_sync_duration:.3f}s scheduling=background"
        )

    async def trigger_short_term_reflection_for_all(self, timestamp: int):
        idle_people = [
            p for p in self.population.get_people_list()
            if p.is_llm_based and p.state.heading_to is None
        ]

        async def reflect_person(person):
            await self.agent.trigger_short_term_reflection_for_all_people(timestamp=timestamp, people=[person])

        tasks = [reflect_person(person) for person in idle_people]
        await asyncio.gather(*tasks)

    async def trigger_long_term_reflection_for_all(self, timestamp: int):
        people = self.population.get_people_list()

        async def self_reflect_person(person):
            await self.agent.reflect_on_long_term_memory(timestamp=timestamp, people=[person])

        tasks = [self_reflect_person(person) for person in people]
        await asyncio.gather(*tasks)

    async def handle_observation(self, observation: Observation):
        """Handle observation data"""
        # logger.debug(f"[timestamp: {humanize_date(observation.timestamp)}] Handling observation for person {observation.person_id} at location {observation.location}")
        person = self.population.get_person(observation.person_id)
        if not person:
            logger.warning(f"[timestamp: {humanize_date(observation.timestamp)}] Person {observation.person_id} not found in population")
            return
        # Update person's state based on observation
        person.state.last_location = observation.location
        on_purpose = person.state.heading_to

        # Put the observation into the person's short-term memory
        ob_text = env_ob_to_text(
            code=observation.env_ob_code,
            ob=observation.data,
            purpose=on_purpose,
        )
        # history_logger.log_shortterm_memory(
        #     timestamp=observation.timestamp,
        #     person_id=person.person_id,
        #     message=ob_text,
        #     data={
        #         "location": observation.location.model_dump(exclude_none=True),
        #         "heading_to": person.state.heading_to,
        #         "data": observation.data,
        #     }
        # )
        if observation.env_ob_code == "arrival":
            # person.state.heading_to = None  # Clear the heading_to state if it's an arrival observation
            # Adjust the scheduled time for the next activity
            # TODO: finetune or remove this rule
            if person.state.cache_current_activity:
                activity = person.state.cache_current_activity
                ob = parse_ob(code=observation.env_ob_code, ob=observation.data)
                if settings.agent.reschedule_activity_departure_time:
                    # Support adjust in both directions
                    duration = self.reschedule_amount_function(arrival_late_seconds=ob.late)
                    self.population.get_person_default_scheduler(person).reschedule_activity(activity, duration)
                    # add to the short term memory
                    _context = Context(
                        person=person,
                        activity_id=observation.activity_id,
                        timestamp=observation.timestamp,
                        data={
                            "location": observation.location.model_dump(exclude_none=True),
                            "heading_to": person.state.heading_to,
                            "data": observation.data,
                        }
                    )
                    self.agent.add_short_term_memory(
                        context=_context,
                        msg=f"According to the past late time, you rescheduled the {activity.purpose} activity. Now it will start at {humanize_time(activity.scheduled_start_time)}, mean {humanize_duration(activity.start_time - activity.scheduled_start_time)} before.",
                        timestamp=observation.timestamp
                    )
            self.population.get_person_default_scheduler(person).finish_activity()
            #self.population.dump_population_state()

        _context = Context(
            person=person,
            activity_id=observation.activity_id,
            timestamp=observation.timestamp,
            data={
                "location": observation.location.model_dump(exclude_none=True),
                "heading_to": person.state.heading_to,
                "data": observation.data,
            }
        )
        self.agent.add_short_term_memory(
            context=_context,
            msg=ob_text,
            timestamp=observation.timestamp
        )

        #logger.debug(f"[timestamp: {humanize_date(observation.timestamp)}] Person {observation.person_id} observed: {ob_text}")

    def reschedule_amount(self, arrival_late_seconds: int) -> int:
        """Calculate the reschedule amount based on arrival late seconds"""
        if arrival_late_seconds <= 0:
            return 0
        amount = min(int(abs(arrival_late_seconds) * settings.agent.reschedule_transition_ratio), self.MAX_ADJUST_START_TIME)
        amount = amount if arrival_late_seconds > 0 else -amount
        return amount

    def reschedule_amount_v2(self, arrival_late_seconds: int) -> int:
        """Calculate the reschedule amount based on arrival late seconds"""
        if arrival_late_seconds <= 0:
            return 0
        k = settings.agent.reschedule_activity_v2__k or 0.02
        arrival_late_minutes = arrival_late_seconds / 60.0
        amount = min(k * arrival_late_minutes * arrival_late_minutes * 60, self.MAX_ADJUST_START_TIME)
        amount = int(amount) if arrival_late_seconds > 0 else -int(amount)
        return amount

    async def has_messages(self) -> bool:
        """Check if there are messages to process"""
        return len(self._messages) > 0

    async def pop_all_messages(self) -> list[Action]:
        """Pop all messages from the queue"""
        messages = self._messages.copy()
        self._messages.clear()
        return messages

    async def bootstrap_all_agents(self, timestamp: int):
        """Pre-compute the first upcoming itinerary for every agent.

        Called from /init so GAMA's reflex init blocks on the HTTP response until
        every OTP query is done. Uses next_upcoming_activity (no time-window logic):
        for each agent, find the first activity with scheduled_start_time >= time24h,
        scanning forward up to 24 h from the current sim time.
        """
        all_people = self.population.get_people_list()
        _, _time24h = to_24h_timestamp_full(timestamp)

        eligible: list[tuple[Person, Activity]] = []
        for person in all_people:
            if person.state.heading_to is not None or person.state.scheduling_in_progress:
                continue
            sched = self.population.get_person_default_scheduler(person)
            next_act = sched.next_upcoming_activity(timestamp)
            if next_act is None:
                continue
            person.state.scheduling_in_progress = True
            person.state.scheduling_started_at = _time24h
            eligible.append((person, next_act))

        logger.info(
            f"[bootstrap] sim_time={humanize_date(timestamp)} "
            f"computing itineraries for {len(eligible)}/{len(all_people)} agents — GAMA blocked"
        )
        _bootstrap_start = time.monotonic()
        tasks = [asyncio.create_task(self._schedule_one(person, act, timestamp))
                 for person, act in eligible]
        await asyncio.gather(*tasks, return_exceptions=True)
        _bootstrap_duration = time.monotonic() - _bootstrap_start
        BOOTSTRAP_DURATION.set(_bootstrap_duration)
        logger.info(f"[bootstrap] done — {len(eligible)} itineraries computed in {_bootstrap_duration:.2f}s")

    async def schedule_person_move(self, timestamp: int):
        all_people = self.population.get_people_list()

        # Step 1: filter and flag synchronously — no await before the flag,
        # so no two sync() calls can double-schedule the same agent.
        _flag_start = time.monotonic()
        _, _time24h = to_24h_timestamp_full(timestamp)
        eligible: list[tuple[Person, Activity]] = []
        for person in all_people:
            if person.state.heading_to is not None or person.state.scheduling_in_progress:
                continue
            sched = self.population.get_person_default_scheduler(person)
            next_act = sched.next_activity(timestamp)

            # Advance past any activities whose scheduled departure has already passed.
            # next_activity() uses a circular sort and does not track last_activity_index,
            # so we bound the loop to avoid cycling indefinitely on the same activity.
            _seen = set()
            while next_act is not None and next_act.scheduled_start_time < _time24h:
                if id(next_act) in _seen:
                    next_act = None  # all remaining activities are in the past
                    break
                _seen.add(id(next_act))
                self._late_count += 1
                PLANNING_LATE.inc()
                _late_s = _time24h - next_act.scheduled_start_time
                logger.warning(
                    f"[schedule_move] LATE — skipping | person={person.person_id} "
                    f"activity={next_act.purpose} "
                    f"scheduled={humanize_time(next_act.scheduled_start_time)} "
                    f"sim_time={humanize_time(_time24h)} "
                    f"late={humanize_duration(_late_s)}"
                )
                sched.start_on_activity(next_act)
                sched.finish_activity()
                next_act = sched.next_activity(timestamp)

            if next_act is None:
                continue
            person.state.scheduling_in_progress = True
            person.state.scheduling_started_at = _time24h
            eligible.append((person, next_act))
        _flag_duration = time.monotonic() - _flag_start

        if not eligible:
            return

        # Most urgent departures first
        eligible.sort(key=lambda x: x[1].scheduled_start_time)

        in_progress_count = sum(1 for p in all_people if p.state.scheduling_in_progress)
        logger.info(
            f"[schedule_move] START sim_time={humanize_date(timestamp)} "
            f"eligible={len(eligible)} flag_duration={_flag_duration*1000:.1f}ms "
            f"scheduling_in_progress={in_progress_count}"
        )

        # Step 2: fire-and-forget per agent
        for i, (person, next_act) in enumerate(eligible, 1):
            asyncio.create_task(self._schedule_one(person, next_act, timestamp))
            if i % 5 == 0:
                in_progress_count = sum(1 for p in all_people if p.state.scheduling_in_progress)
                logger.info(
                    f"[schedule_move] tasks_fired={i}/{len(eligible)} "
                    f"scheduling_in_progress={in_progress_count}"
                )

    async def _schedule_one(self, person: Person, next_activity: Activity, timestamp: int):
        try:
            PROCESS_PERSON_CALLS.inc()
            move, reasoning = await self._compute_move_for_activity(person, next_activity, timestamp)

            if move:
                ACTIONS_CREATED.inc()
                self._itinerary_success_count += 1
                if self._itinerary_success_count >= 100:
                    ITINERARY_100_COMPLETION.set(time.monotonic() - self._itinerary_window_start)
                    self._itinerary_success_count = 0
                    self._itinerary_window_start = time.monotonic()
                self._messages.append(Action(
                    person_id=person.person_id,
                    action=move.model_dump(exclude_none=False)
                ))
                # logger.info(
                #     f"[schedule_move] person={person.person_id} action_queued "
                #     f"sim_time={humanize_date(timestamp)} "
                #     f"planned_departure={humanize_time(move.for_activity.start_time)}"
                # )

                # TODO: log travel plan to short-term memory
                # self.agent.add_short_term_memory(...)

                self.population.get_person_default_scheduler(person).start_on_activity(
                    activity=next_activity,
                )
        except Exception as e:
            logger.error(f"[schedule_move] error for person {person.person_id}: {e}")
        finally:
            person.state.scheduling_in_progress = False
            person.state.scheduling_started_at = None

    async def _compute_move_for_activity(
        self,
        person: Person,
        next_activity: Activity,
        timestamp: int,
    ) -> Tuple[Optional[PersonMove], Optional[str]]:
        # logger.info(
        #     f"[schedule_move] person={person.person_id} "
        #     f"sim_time={humanize_date(timestamp)} → OTP+LLM for {next_activity.purpose} at {humanize_time(next_activity.start_time)}"
        # )

        from_location = person.state.last_location

        # Use the activity's actual scheduled start time as departure time, not the current
        # simulation timestamp. When pre_schedule_duration > 0, the agent is triggered early
        # but should still get an itinerary computed for its real departure time so that
        # transit connections are correct.
        actual_departure_time = to_timestamp_based_on_day(
            target_24h_timestamp=next_activity.start_time,
            based_on=timestamp,
        )
        _otp_start = time.monotonic()
        itineraries = await self.trip_helper.get_itineraries(
            origin=from_location,
            destination=next_activity.location,
            departure_time=actual_departure_time,
            include_car=True,
        )
        _otp_duration = time.monotonic() - _otp_start
        if _otp_duration > 5.0:
            logger.warning(
                f"[otp] Slow itinerary query | person={person.person_id} "
                f"duration={_otp_duration:.2f}s n_results={len(itineraries)}"
            )
        # Populate purpose
        for itinerary in itineraries:
            itinerary.purpose = next_activity.purpose

        if not itineraries:
            estimated_duration = _estimate_fallback_duration(from_location, next_activity.location)
            logger.warning(
                f"[timestamp: {humanize_date(timestamp)}] Can't get to destination {next_activity.location} by public transport, "
                f"estimated travel time: {humanize_duration(estimated_duration)}"
            )
            plan = TravelPlan(
                id=random_uuid(),
                start_location=from_location,
                end_location=next_activity.location,
                start_time=timestamp,
                end_time=timestamp + estimated_duration,
                purpose=next_activity.purpose,
                legs=[],
            )
            plan_index = 0
            reasoning = "Can't find a suitable public transport plan, walk to the destination anyway"
        else:
            plan_index = 0
            reasoning = "Hard to choice, just pick the first one"

            # Ask LLM agent to choose a best plan
            if person.is_llm_based and self.agent:
                # Use the agent to choose the best plan
                context = Context(
                    person=person,
                    timestamp=timestamp,
                    activity_id=next_activity.id,
                    data={"type": "travel_plan"},
                )
                EVALUATE_PLAN_CALLS.inc()
                plan_index, reasoning = await self.agent.evaluate_and_choose_travel_plan(
                    context=context,
                    options=itineraries,
                    destination=next_activity.purpose,
                )
                if isinstance(plan_index, int) and 0 <= plan_index < len(itineraries):
                    pass
                else:
                    plan_index = 0
                    logger.debug(f"[timestamp: {humanize_date(timestamp)}] No suitable plan found for person {person.person_id} to {next_activity.location}")

            plan: TravelPlan = itineraries[plan_index]
            plan.purpose = next_activity.purpose
            # is_car_plan = any(leg.transit_route == "__CAR__" for leg in plan.legs)
            # if is_car_plan:
            #     logger.info(f"[schedule_move] person={person.person_id} selected CAR plan (index={plan_index})")

        # Define the person move based on the plan
        move = PersonMove(
            id=random_uuid(),
            person_id=person.person_id,
            current_time=timestamp,
            expected_arrive_at=to_timestamp_based_on_day(
                target_24h_timestamp=next_activity.start_time,
                based_on=timestamp,
            ),
            prepare_before_seconds=0,
            purpose=next_activity.purpose,
            target_location=next_activity.location,
            for_activity=next_activity,
            plan=plan,
        )

        history_logger.log_query_travel_plan(
            timestamp=timestamp,
            person_id=person.person_id,
            message=f"Querying travel plan for {next_activity.purpose}",
            data={
                "purpose": next_activity.purpose,
                "activity_id": next_activity.id,
                "itineraries": [itin.get_code() for itin in itineraries],
                "selected_plan_index": plan_index,
            }
        )

        history_logger.log_travel_plan(
            timestamp=timestamp,
            person_id=person.person_id,
            message=f"Planning trip for {next_activity.purpose}",
            data={
                "purpose": next_activity.purpose,
                "activity_id": next_activity.id,
                "plan_code": plan.get_code(),
            }
        )

        return move, reasoning
