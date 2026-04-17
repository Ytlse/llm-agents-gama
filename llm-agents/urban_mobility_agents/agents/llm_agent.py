import asyncio
from datetime import datetime
import json
import demjson3
import os
import random
import re
import traceback
from typing import Optional

from typing import Tuple
from loguru import logger
import numpy as np
from openai import BaseModel
from helper import categorize_date_time_short, get_weekday_category, humanize_date, humanize_date_short, humanize_time, time_to_bucket_text
from llm.longterm import MultiUserLongTermMemory
from llm.memory import MemoryEntry, MemoryType
from llm.shortterm import UserShortTermMemory
from models import Person, TravelPlan
from llm_module.client import LLMClient
from urban_mobility_agents.utils.history_log import HistoryStreamLog
from text_helper import env_ob_to_text
from settings import settings
from typing import Dict, Any
from urban_mobility_agents.agents.prompt_manager import PromptManager
from urban_mobility_agents.agents.prompt_types import PromptName
from llama_index.core.llms import ChatMessage, ChatResponse
import time
from world.population import PersonScheduler
from loguru import logger


history_log = HistoryStreamLog.get_instance()


class Context(BaseModel):
    person: Person
    timestamp: int
    activity_id: Optional[str] = None
    data: Optional[dict] = None


def log_chat(prompt: str, response: str, context: Context) -> str:
    log_dir = settings.agent.chat_log_dir
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    type_suffix = f"-{context.data['type']}" if context.data and context.data.get('type') else ""
    sim_time = datetime.strftime(datetime.fromtimestamp(context.timestamp), "%d_%H%M")
    file_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{sim_time}-{context.person.person_id}-{context.activity_id}{type_suffix}.txt"

    with open(os.path.join(log_dir, file_name), "a") as f:
        f.write("--------------------\n")
        f.write(f"Prompt: \n{prompt}\n")
        f.write("--------------------\n")
        f.write(f"Response: \n{response}\n\n")
        f.write("--------------------\n")
        f.write(f"Data: \n{context.model_dump_json()}\n")

    return file_name

class LlmAgent:
    DEFAULT_IDENTITY = ""

    def __init__(self):
        self.llm = None
        
        self.short_term_memory: dict[str, UserShortTermMemory] = {}
        if settings.agent.long_term_memory_enabled:
            self.long_term_memory = MultiUserLongTermMemory(
                storage_dir=settings.agent.long_term_memory_storage_dir,
                long_term_memory_filter_by_datetime=settings.agent.long_term_memory_filter_by_datetime,
            )
        else:
            self.long_term_memory = None
            logger.info("Long-term memory disabled — ChromaDB initialization skipped")
        
        # Instance du client LLM (Singleton naturel pour cet Agent)
        self.llm_client = LLMClient(base_url=os.getenv("LLM_API_URL", "http://localhost:8000"), poll_timeout=settings.agent.remote_llm_poll_timeout)
        self.prompt_manager = PromptManager(os.path.join(os.path.dirname(__file__), "prompts"))

    def get_short_term_memory(self, user_id: str) -> UserShortTermMemory:
        if user_id not in self.short_term_memory:
            self.short_term_memory[user_id] = UserShortTermMemory(user_id)
        return self.short_term_memory[user_id]
    
    def add_short_term_memory(self, context: Context, msg: str, timestamp: Optional[int] = None):
        memory = self.get_short_term_memory(context.person.person_id)
        memory.add_message(
            msg, 
            datetime.fromtimestamp(timestamp or context.timestamp), 
            activity_id=context.activity_id
        )
        history_log.log_shortterm_memory(
            timestamp=context.timestamp,
            person_id=context.person.person_id,
            activity_id=context.activity_id,
            message=msg,
            data=context.data,
        )

    async def aadd_long_term_memory(self, context: Context, msg: MemoryEntry):
        await self.long_term_memory.aadd_memory(msg)
        history_log.log_longterm_memory(
            timestamp=context.timestamp,
            person_id=context.person.person_id,
            message=msg.content,
            data=context.data,
        )

    async def execute_llm_chat(self, context: Context, prompt: str, system_prompt: Optional[str] = None, params: Optional[dict] = None, type: Optional[str] = None) -> str:
        """
        Central method to send asynchronous chat requests to the LLM with built-in retries, logging, and metrics.

        Args:
            context (Context): The simulation context containing the person, current time, and shared data.
            prompt (str): The main instruction/query for the LLM.
            system_prompt (Optional[str], optional): The system prompt defining the agent's persona and rules.
            params (Optional[dict], optional): Additional generation parameters (e.g., temperature) to pass to the LLM.
            type (Optional[str], optional): Optional chat type identifier (mostly managed via context.data['type']).

        Returns:
            str: The stripped text content of the LLM's response.

        Raises:
            AssertionError: If the LLM call fails after exhausting all retries.
        """
        start_time = time.time()
        response = None
        for _ in range(settings.agent.llm_retry_count):
            try:
                # Use the LLM's chat method to get a response
                messages = [] if not system_prompt else [ChatMessage(role="system", content=system_prompt)]
                messages.append(ChatMessage(role="user", content=prompt))
                response: ChatResponse = await self.llm.achat(messages, **(params or {}))
                break  # Exit loop if successful
            except Exception as e:
                logger.error(f"LLM chat failed: {e}")
                await asyncio.sleep(settings.agent.llm_retry_delay)

        assert response is not None, "LLM chat response is None after retries."

        duration = time.time() - start_time

        # Try to get token usage stats if available
        total_tokens = getattr(response, "usage", {}).get("total_tokens", None)

        stats = {
            "duration": duration,
            "total_tokens": total_tokens,
        }
        context.data = context.data or {}
        context.data["llm_stats"] = stats

        combine_prompt = f"***** ------------------ System Prompt ------------------ :\n{system_prompt}\n***** ------------------ User Prompt ------------------ :\n{prompt}"
        log_chat(combine_prompt, response, context)
        return response.message.content.strip()

    def parse_response_json(self, response: str) -> Tuple[Optional[dict], str]:
        try:
            match = re.search(r'\{.*\}', response, re.DOTALL)
            assert match is not None, "No JSON found in response"

            json_str = match.group(0)
        except Exception as e:
            traceback.print_exc()
            print(f"Error parsing response: {e}, response raw: {response}")
            json_str = response.strip()

        try:
            parsed = json.loads(json_str)
            return parsed, ""
        except Exception as e:
            traceback.print_exc()
            print(f"Error parsing response: {e}, response raw: {response}")
            
        try:
            parsed = demjson3.decode(json_str)
            return parsed, ""
        except demjson3.JSONDecodeError as e:
            traceback.print_exc()
            print(f"Error parsing response: {e}, response raw: {response}")
        
        return None, response.strip()

    def get_person_identity_description(self, person: Person) -> str:
        i = person.identity
        text = json.dumps(i.traits_json, ensure_ascii=False, indent=2)
        return text

    async def query_past_experiences_for_travel(self, context: Context, options: list[TravelPlan]) -> list[str]:
        def get_plan_text(plan: TravelPlan) -> str:
            return env_ob_to_text("travel_plan_query", plan.model_dump())

        index = 1
        travel_options = ""
        for option in options:
            travel_options += f"{index}. \n{get_plan_text(option)}\n"
            index += 1

        text = self.prompt_manager.get_prompt(
            PromptName.QUERY_EXPERIENCES,
            current_time=humanize_date_short(context.timestamp),
            temporal_keyword=categorize_date_time_short(context.timestamp),
            weekday=get_weekday_category(context.timestamp).upper(),
            destination=options[0].purpose,
            travel_options=travel_options
        )

        logger.debug(f"Querying experiences with travel plans for user {context.person.person_id}, activity {context.activity_id}, query text: {text}")

        hist = await self.long_term_memory.aquery_user_memories(
            person_id=context.person.person_id,
            query=text,
            top_k=settings.agent.long_term_max_entries_query,
            max_past_days=settings.agent.long_term_max_days_query,
            query_at=context.timestamp,
        )

        # deduplicate entries based on content
        unique_hist = {}
        for entry in hist:
            if entry.content not in unique_hist:
                unique_hist[entry.content] = entry
        hist = sorted(list(unique_hist.values()), key=lambda x: x.metadata['timestamp'], reverse=True)

        logger.debug(f"Found {len(hist)} relevant experiences for travel plans for user {context.person.person_id}, activity {context.activity_id}")

        # resp = [
        #     # f"[{datetime.strftime(datetime.fromisoformat(entry.metadata['timestamp']), '%A, %H:%M:%S')}] {entry.content}"
        #     # TODO: we asked the LLM to return the time within the day, so only need to append the day of week here
        #     f"[{datetime.strftime(datetime.fromisoformat(entry.metadata['timestamp']), '%A')} at {time_to_bucket_text(datetime.fromisoformat(entry.metadata['timestamp']).timestamp())}] {entry.content}" if entry.content else ""
        #     for entry in hist
        # ]

        resp = []
        ts = []
        for entry in hist:
            if str(entry.metadata["memory_type"]) == str(MemoryType.REFLECTION.value):
                resp.append([entry.content, datetime.strftime(datetime.fromisoformat(entry.metadata['timestamp']), '%A, %B %d')])
                ts.append(datetime.fromisoformat(entry.metadata['timestamp']).timestamp())
            elif str(entry.metadata["memory_type"]) == str(MemoryType.CONCEPT.value):
                resp.append(json.loads(entry.content))
                ts.append(datetime.fromisoformat(entry.metadata['timestamp']).timestamp())
            else:
                logger.debug(f"Unknown memory type for entry: {entry.metadata['memory_type']}")

        # sort the entries by timestamp asc
        ts = np.array(ts)
        sorted_indices = np.argsort(ts)
        resp = [resp[i] for i in sorted_indices]
        return resp

    def get_personal_system_prompt(self, person: Person) -> str:
        identity_description = self.get_person_identity_description(person)
        return self.prompt_manager.get_prompt(PromptName.PERSONAL_SYSTEM, identity_description=identity_description)
    
    async def build_travel_plan_payload(self, context: Context, options: list[TravelPlan], destination: str) -> Dict[str, Any]:
        agent_id = context.person.person_id
        perception = self.get_person_identity_description(context.person) # TODO To be remplace by feeling and perception about transport modes
        constraints = "None" #TODO To be replaced by real constraints from persona
        current_time = humanize_time(context.timestamp)
        city_context = "None" #TODO To be replaced by real context from GAMA (ex meteo)

        history = []
        if settings.agent.long_term_memory_enabled:
            history = await self.query_past_experiences_for_travel(context, options)

        # Utilisation d'une compréhension de liste pour la performance et la clarté
        trajectories = [
            {
                "index": i,
                "mode": ",".join([str(leg.mode) for leg in opt.legs]) if opt.legs else "unknown",
                "description": env_ob_to_text("travel_plan", opt.model_dump()),
                # Distance totale du trajet (en mètres) — utilisée pour les métriques Prometheus
                "total_distance_m": (
                    opt.distance
                    if opt.distance is not None
                    else sum(leg.get_distance() for leg in (opt.legs or []))
                ),
            }
            for i, opt in enumerate(options)
        ]

        return {
            "category": "itinary_multi_agent",
            "agents": [
                {
                    "agent_id": agent_id,
                    "perception": f"{perception} Contraintes : {constraints}",
                    "destination": destination,
                    "current_time": current_time,
                    "history": history,
                    "trajectories": trajectories
                }
            ],
            "context": city_context
        }

    async def evaluate_and_choose_travel_plan(self, context: Context, options: list[TravelPlan], destination: str) -> tuple[int, str]:
        assert options, "No travel options provided for planning trip."
        
        if len(options) == 1:
            # If only one option, return it directly
            return 0, "Only one travel option available, no need to choose."

        # shuffle options to avoid bias
        random.shuffle(options)
        payload = await self.build_travel_plan_payload(context, options, destination)

        try:
            response_data = await self.llm_client.execute_async(payload)

            if response_data.get("status") == "success" and response_data.get("result"):
                agent_result = response_data["result"][0]
                index = agent_result.get("chosen_index")
                
                # L'index retourné par Structured Output correspond déjà à l'index (0-based) envoyé
                if isinstance(index, int) and 0 <= index < len(options):
                    reason = agent_result.get("reason", "Pas de justification fournie.")

                    # Normalisation de la raison (alignement avec aplan_trip_old)
                    if "is chosen because it" in reason:
                        reason = f"This plan {reason.split('is chosen because it', 1)[1].strip()}"

                    # Écriture de la décision en short-term memory pour alimenter la réflexion journalière
                    chosen_plan = options[index]
                    plan_summary = env_ob_to_text("travel_plan", chosen_plan.model_dump())
                    stm_msg = f"[ TRAVEL_PLAN ] Plan to head <{destination}> chosen by gateway LLM.\n{plan_summary}\nReasoning: {reason}"
                    self.add_short_term_memory(context, stm_msg, timestamp=context.timestamp)

                    return index, reason
                    
            error_msg = response_data.get("error", "Format de réponse invalide ou timeout.")
            logger.warning(f"aplan_trip: gateway a retourné un résultat invalide pour {context.person.person_id}: {error_msg}")
            return -1, error_msg
            
        except Exception as e:
            logger.error(f"Erreur lors de l'appel à l'API Gateway LLM: {e}")
            return -1, str(e)

    def get_reflection_prompt(self, context: Context) -> tuple[str, list[MemoryEntry]]:
        mem = self.get_short_term_memory(context.person.person_id)
        group_messages, all_messages = mem.get_all_message_and_group()

        if not all_messages:
            return "", []

        exp = []
        for group in group_messages:
            if group:
                activity = PersonScheduler(context.person).get_activity(group[0].activity_id) if group[0].activity_id else None
                exp.append({
                    "purpose": activity.purpose if activity else None,
                    "observations": [msg.content for msg in group],
                })
        experiences_text = json.dumps(exp, indent=2, ensure_ascii=False)

        custom_guidelines_text = f"\n**IMPORTANT CUSTOM GUIDELINES** {settings.agent.reflection_custom_guidelines}" if settings.agent.reflection_custom_guidelines else ""
        
        prompt_text = self.prompt_manager.get_prompt(
            PromptName.REFLECTION,
            experiences_text=experiences_text if experiences_text else "[]",
            custom_guidelines=custom_guidelines_text
        )
        return prompt_text, all_messages

    def get_longterm_memory_reflection_prompt(self, context: Context, from_date: datetime):
        all_entries = self.long_term_memory.get_last_user_memories(
            person_id=context.person.person_id,
            from_date=from_date,
        )
        if not all_entries:
            return None, []

        entries_text = "\n".join(f"- Time {humanize_date(entry.timestamp.timestamp())}: {entry.content}" for entry in all_entries)

        prompt = self.prompt_manager.get_prompt(PromptName.LONGTERM_REFLECTION, entries_text=entries_text)
        return prompt, all_entries
    
    async def trigger_short_term_reflection_for_all_people(self, timestamp: int, people: list[Person]):
        """
        Reflect on all short-term memories of all people at the given timestamp.
        This is used to process all short-term memories at once, e.g. at the end of the day.
        """
        if settings.agent.long_term_memory_enabled is False:
            logger.info("Long-term memory is disabled, skipping reflection.")
            return
        
        for person in people:
            context = Context(
                person=person,
                timestamp=timestamp,
                data={"type": "reflection"}
            )
            await self.reflect_on_short_term_memory(context)

    async def trigger_long_term_reflection_for_all_people(self, timestamp: int, from_date: datetime, people: list[Person]):
        if settings.agent.long_term_memory_enabled is False or settings.agent.long_term_self_reflect_enabled is False:
            logger.info("Long-term memory is disabled or Self reflection is disable, skipping self reflection.")
            return

        for person in people:
            context = Context(
                person=person,
                timestamp=timestamp,
                data={"type": "self_reflection"}
            )
            await self.reflect_on_long_term_memory(context, from_date)

    async def reflect_on_long_term_memory(self, context: Context, from_date: datetime):
        if settings.agent.long_term_memory_enabled is False:
            logger.info("Long-term memory is disabled, skipping reflection.")
            return
        
        prompt, all_entries = self.get_longterm_memory_reflection_prompt(context, from_date)
        if not all_entries:
            logger.info(f"No long-term memory available for reflection for {context.person.person_id}")
            return
        system_prompt = self.get_personal_system_prompt(context.person)
        response_text = await self.execute_llm_chat(context, prompt, system_prompt=system_prompt)
        resp, fallback = self.parse_response_json(response_text)
        try:
            reflection = resp["reflection"]
            entry = MemoryEntry(
                person_id=context.person.person_id,
                content=reflection,
                timestamp=datetime.fromtimestamp(context.timestamp),
                memory_type=MemoryType.REFLECTION,
            )
            await self.aadd_long_term_memory(context, entry)
        except Exception as e:
            logger.error(f"Failed to parse reflection response for person {context.person.person_id}, err: {e}")
            return

    async def reflect_on_short_term_memory(self, context: Context):
        prompt, all_messages = self.get_reflection_prompt(context)
        if not all_messages:
            logger.info("No short-term memory available for reflection.")
            return
        
        system_prompt = self.get_personal_system_prompt(context.person)
        response_text = await self.execute_llm_chat(context, prompt, system_prompt=system_prompt)
        #TODO: hotfix - avoid null in the list
        response_text = response_text.replace("\nnull", "").replace("null\n", "").replace("\nnull\n", "")
        resp, fallback = self.parse_response_json(response_text)

        # remove all messages from short-term memory
        self.get_short_term_memory(context.person.person_id).remove_batch(all_messages)
        # TODO: Add to long-term memory
        start_timestamp = all_messages[0].timestamp


        # add new memory to long-term memory
        entries = []
        try:
            reflection = resp.get("reflection", "").strip() if resp else ""
            concepts = resp.get("concepts", [])

            entries.append(MemoryEntry(
                person_id=context.person.person_id,
                content=reflection,
                timestamp=start_timestamp,
                memory_type=MemoryType.REFLECTION,
            ))

            for concept in concepts:
                entries.append(MemoryEntry(
                    person_id=context.person.person_id,
                    content=json.dumps(concept, ensure_ascii=False),
                    timestamp=start_timestamp,
                    memory_type=MemoryType.CONCEPT,
                    tags=",".join(concept[1:] if isinstance(concept, list) and len(concept) > 1 else [])
                ))
        except Exception as e:
            traceback.print_exc()
            logger.error(f"Failed to parse reflection response: {e}")

        for entry in entries:
            await self.aadd_long_term_memory(context, entry)