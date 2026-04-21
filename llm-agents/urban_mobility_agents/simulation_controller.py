"""
Ce module définit la boucle de simulation principale (SimulationLoopV1) pour le scénario.

Son rôle est d'orchestrer le déroulement de la simulation au fil du temps. Il gère :
- La synchronisation de l'état du monde et des agents.
- Le déclenchement des actions des agents (planification des déplacements).
- Le traitement des observations de l'environnement.
- L'orchestration des cycles de réflexion (mémoire à court et long terme) des agents.
"""

import asyncio
import time
from typing import Optional, Tuple
import datetime

from loguru import logger
from gama_models import WorldSyncIdlePeople
from helper import humanize_duration, humanize_time, to_timestamp_based_on_day, humanize_date
from models import BBox, Person, PersonMove, TravelPlan
from urban_mobility_agents.core.scenario import Action, BaseScenario, Observation
from urban_mobility_agents.utils.history_log import HistoryStreamLog
from urban_mobility_agents.agents.llm_agent import Context, LlmAgent
from text_helper import env_ob_to_text, parse_ob
from trip_helper.base import TripHelper
from utils import random_uuid
from world.population import WorldPopulation
from world.world_data import WorldModel
from settings import settings

from prometheus_client import Counter

history_logger = HistoryStreamLog.get_instance()

PROCESS_PERSON_CALLS = Counter('gama_process_person_calls_total', 'Total calls to process_person')
EVALUATE_PLAN_CALLS = Counter('gama_evaluate_plan_calls_total', 'Total calls to evaluate_and_choose_travel_plan')
ACTIONS_CREATED = Counter('gama_actions_created_total', 'Total actions created')

class SimulationLoopV1(BaseScenario):
    MAX_ADJUST_START_TIME = 15*60  # 15 minutes

    def __init__(self,
                 world_model: "WorldModel",
                 trip_helper: "TripHelper" = None,
                 agent: Optional["LlmAgent"] = None):
        self.MAX_ADJUST_START_TIME = settings.agent.max_reschedule_amount or self.MAX_ADJUST_START_TIME
        self._messages = []
        self.model = world_model
        self.trip_helper = trip_helper
        self.agent = agent
        # schedule next reflection
        self.reflect_period = settings.agent.long_term_reflect_interval
        self.next_reflection_at = None
        self.next_self_reflection_at = None
        # Control the agent's concurrency
        self._concurrent_semaphore = asyncio.Semaphore(settings.agent.remote_llm_max_concurrent_requests)
        # Background scheduling task — un seul à la fois pour éviter de traiter les mêmes agents en double
        self._scheduling_task: Optional[asyncio.Task] = None

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
            f"gama_idle_update={len(idle_people) if idle_people else 0}"
        )

        # --- Phase 1 : mise à jour d'état depuis GAMA (rapide, synchrone) ---
        # Doit être fait avant de retourner pour que les nouveaux arrivants
        # soient visibles comme "idle" lors du scheduling qui suit.
        if idle_people:
            for person_data in idle_people:
                person = self.population.get_person(person_data.person_id)
                if person:
                    person.state.last_location = person_data.location
                    self.population.get_person_default_scheduler(person).finish_activity()
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

        # --- Phase 3 : scheduling non-bloquant ---
        # Les actions partent via le publish_loop WebSocket indépendamment du /sync HTTP.
        # On lance donc le scheduling en background et on répond à GAMA immédiatement.
        scheduling_running = self._scheduling_task is not None and not self._scheduling_task.done()
        if scheduling_running:
            logger.info(
                f"[sync] Scheduling task already running — "
                f"les {len(currently_idle)} idle agents seront capturés au prochain sync"
            )
        else:
            self._scheduling_task = asyncio.create_task(
                self.schedule_person_move(timestamp=timestamp)
            )
            self._scheduling_task.add_done_callback(self._on_scheduling_done)

        _sync_duration = time.monotonic() - _sync_start
        logger.info(
            f"[sync] END sim_time={humanize_date(timestamp)} "
            f"state_update_duration={_sync_duration:.3f}s scheduling=background"
        )

    def _on_scheduling_done(self, task: asyncio.Task) -> None:
        """Callback appelé quand la tâche de scheduling background se termine."""
        if task.cancelled():
            logger.warning("[schedule_move] Background task annulée")
        elif task.exception():
            logger.error(f"[schedule_move] Background task exception: {task.exception()}")

    async def trigger_short_term_reflection_for_all(self, timestamp: int):
        idle_people = [
            p for p in self.population.get_people_list() 
            if p.is_llm_based and p.state.heading_to is None
        ]

        async def reflect_person(person):
            async with self._concurrent_semaphore:
                await self.agent.trigger_short_term_reflection_for_all_people(timestamp=timestamp, people=[person])

        tasks = [reflect_person(person) for person in idle_people]
        await asyncio.gather(*tasks)

    async def trigger_long_term_reflection_for_all(self, timestamp: int):
        people = self.population.get_people_list()

        async def self_reflect_person(person):
            async with self._concurrent_semaphore:
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
            self.population.dump_population_state()

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
    
    async def schedule_person_move(self, timestamp: int):
        idle_people = [p for p in self.population.get_people_list() if p.state.heading_to is None]
        total = len(idle_people)
        if total == 0:
            return

        logger.info(
            f"[schedule_move] START sim_time={humanize_date(timestamp)} "
            f"idle_agents={total} semaphore_slots={settings.agent.remote_llm_max_concurrent_requests}"
        )
        _schedule_start = time.monotonic()
        _done_count = 0
        _done_lock = asyncio.Lock()

        async def process_person(person):
            nonlocal _done_count
            PROCESS_PERSON_CALLS.inc()
            async with self._concurrent_semaphore:
                move, reasoning = await self.determine_next_move_for_person(person, timestamp)
                async with _done_lock:
                    _done_count += 1
                    done = _done_count
                if done % 50 == 0 or done == total:
                    elapsed = time.monotonic() - _schedule_start
                    logger.info(
                        f"[schedule_move] progress={done}/{total} "
                        f"elapsed={elapsed:.1f}s rate={done/elapsed:.1f}/s eta={((total-done)/done*elapsed):.0f}s"
                    )
                if move:
                    ACTIONS_CREATED.inc()
                    self._messages.append(Action(
                        person_id=person.person_id,
                        action=move.model_dump(exclude_none=False)
                    ))

                    action_text = env_ob_to_text(
                        code="travel_plan",
                        ob=move.plan.model_dump(exclude_none=True)
                    )
                    action_text = f"[ TRAVEL_PLAN ] Start traveling following plan: \n{action_text}\n\nReasoning (consumption) for decision: {reasoning}"

                    # TODO: this is duplicated with `add_short_term_memeory`?
                    # history_logger.log_shortterm_memory(
                    #     timestamp=move.current_time,
                    #     person_id=person.person_id,
                    #     activity_id=move.for_activity.id,
                    #     message=action_text,
                    #     data={
                    #         "target_location": move.target_location.model_dump(exclude_none=True),
                    #         "purpose": move.purpose,
                    #         "plan": move.plan.model_dump(exclude_none=True),
                    #     }
                    # )

                    # Add short-term memory for the move
                    # self.agent.add_short_term_memory(
                    #     context=Context(
                    #         person=person,
                    #         activity_id=move.for_activity.id,
                    #         timestamp=move.current_time,
                    #         data={
                    #             "target_location": move.target_location.model_dump(exclude_none=True),
                    #             "purpose": move.purpose,
                    #             "plan": move.plan.model_dump(exclude_none=True),
                    #         }
                    #     ),
                    #     msg=action_text,
                    #     timestamp=move.current_time
                    # )

                    # Update person's state
                    self.population.get_person_default_scheduler(person).start_on_activity(
                        activity=move.for_activity,
                    )

        tasks = [process_person(person) for person in idle_people]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for person, result in zip(idle_people, results):
            if isinstance(result, BaseException):
                logger.error(f"[schedule_move] Unhandled error for person {person.person_id}: {result}")

        _schedule_duration = time.monotonic() - _schedule_start
        new_moves = len(self._messages)
        logger.info(
            f"[schedule_move] END sim_time={humanize_date(timestamp)} "
            f"processed={total} new_moves={new_moves} no_move={total - new_moves} "
            f"total_duration={_schedule_duration:.1f}s"
        )

    # def log_travel_plan_to_shortterm(self, plan: TravelPlan, reasoning: str):
    #     """Log the travel plan to the person's short-term memory"""
    #     if not plan or not plan.id:
    #         return
    #     text = env_ob_to_text(
    #         code="travel_plan_query",
    #         ob=plan.model_dump(exclude_none=True)
    #     )
    #     if reasoning:
    #         text += f"\nReasoning: {reasoning}"
    #     history_logger.log_shortterm_memory(
    #         timestamp=plan.start_time,
    #         person_id=plan.id,
    #         message=text,
    #         data={
    #             "plan": plan.model_dump(exclude_none=True),
    #             "reasoning": reasoning,
    #         }
    #     )

    async def determine_next_move_for_person(self, 
                person: Person, 
                timestamp: int = None,
                depth: int = 0
            ) -> Tuple[Optional[PersonMove], Optional[str]]:
        # Find the next move
        next_activity = self.population.get_person_default_scheduler(person).next_activity(
            timestamp,
            pre_schedule_duration=None,
        )
        if not next_activity:
            # logger.debug(f"[timestamp: {timestamp}] Person {person_id} has no next activity, waiting...")
            return None, None
        
        # Query a new trip plan
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
            logger.debug(f"[timestamp: {humanize_date(timestamp)}] Can't get to destination {next_activity.location} by public transport, move to the destination anyway")
            plan = TravelPlan(
                id=random_uuid(),
                start_location=from_location,
                end_location=next_activity.location,
                start_time=timestamp,
                end_time=timestamp + 30*60,  # Assume 30 minutes travel time
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
                "itineraries": [plan.get_code() for plan in itineraries],
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
