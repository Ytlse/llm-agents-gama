import asyncio
from datetime import datetime, timezone
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
from pydantic import BaseModel
from helper import categorize_date_time_short, get_weekday_category, humanize_date, humanize_date_short, humanize_time, time_to_bucket_text
from llm.longterm import MultiUserLongTermMemory
from llm.memory import MemoryEntry, MemoryType
from llm.shortterm import UserShortTermMemory
from models import Person, TravelPlan
from llm_module.core.mode_choice import (
    UniformFallback,
    draw_index,
    mode_distribution,
    normalize_option_probabilities,
)
from llm_module.sdk import LLMGatewayClient
from llm_module.prompts.manager import prompt_manager as llm_module_prompt_manager
from urban_mobility_agents.utils.history_log import HistoryStreamLog
from text_helper import env_ob_to_text
from settings import settings
from typing import Dict, Any
from urban_mobility_agents.agents.prompt_manager import PromptManager
from urban_mobility_agents.agents.prompt_types import PromptName
from urban_mobility_agents.utils.pipeline_logger import PipelineLogger
from urban_mobility_agents.utils.weather_loader import get_weather, weather_to_natural_language
import time
from utils import create_background_task
from world.population import PersonScheduler
from loguru import logger
from llm.cache import LlmSemanticCache
from llm.reflection_store import ReflectionMemoStore


history_log = HistoryStreamLog.get_instance()


def log_llm_cache_hit(agent_id: str, activity_id: Optional[str], sim_ts: float, mode: str,
                      category: str = "itinary_multi_agent") -> None:
    """Trace une décision servie par le cache sémantique dans workdir/llm_cache_hits.jsonl.

    Un hit ne déclenche aucun appel LLM (donc aucune ligne dans llm_exchanges.jsonl) : ce log
    permet de compter les appels économisés et de ventiler l'économie par jour de simulation
    (sim_day). La valeur en tokens économisés est estimée côté analyse via le coût moyen par
    agent des appels réellement effectués pour la même catégorie."""
    try:
        entry = {
            "time": datetime.now(timezone.utc).isoformat(),
            "sim_ts": sim_ts,
            # sim_day en UTC pour s'aligner avec llm_exchanges.jsonl (cf. logger.log_llm_exchange)
            "sim_day": datetime.fromtimestamp(sim_ts, tz=timezone.utc).strftime("%Y-%m-%d") if sim_ts else None,
            "agent_id": str(agent_id),
            "activity_id": str(activity_id or ""),
            "category": category,
            "mode": mode,
        }
        with open(settings.app.llm_cache_hits_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except OSError as e:
        logger.warning(f"Impossible d'écrire le cache hit LLM : {e}")


def _format_distribution(distribution: dict) -> str:
    """« car 60% · public_transport 30% · walking 10% » — modes à 0 % omis du texte.

    Le dictionnaire complet (modes à 0 % inclus) reste la source pour les métriques :
    ce format n'est destiné qu'aux traces lisibles (mémoire court terme, logs).
    """
    parts = [f"{mode} {pct * 100:.0f}%" for mode, pct in
             sorted(distribution.items(), key=lambda kv: -kv[1]) if pct > 0]
    return " · ".join(parts) or "aucune"


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


# Jambes de transport collectif, pour décider si l'abonnement TC est pertinent à
# annoncer sur une option. `cableway` = Téléo, qui fait partie du réseau Tisséo.
#
# ⚠ Cette liste sert le PROMPT, pas le score. Trois listes de modes TC coexistent dans
# le dépôt et doivent rester cohérentes : celle-ci, `move_logger._BUS_MODES` (journal de
# production) et `categorize_mode` (loss de calibration). Cette dernière ignorait
# `cableway` jusqu'au 2026-08-26 — le Téléo y était compté en marche ; un test de parité
# verrouille désormais les deux dernières. La loss est l'instrument de mesure : toute
# évolution s'y chiffre avant de s'appliquer (amendement A13 du protocole).
_PT_LEG_MODES = ("bus", "metro", "métro", "tram", "cableway", "transit", "public_transport", "rail", "train")


def _pt_subscription_note(mode_label: str, has_pt: bool) -> str:
    """Mention d'abonnement TC à accoler à une option, ou chaîne vide.

    L'information vit sur l'OPTION et non plus sur le persona (2026-08-26) : elle n'est
    pas déductible du jeu d'options — une option bus est proposée qu'on soit abonné ou
    non — mais elle ne pèse sur la décision que là où un transport collectif est
    réellement offert. Une ligne de persona la faisait lire même sans aucune option TC.
    """
    ml = (mode_label or "").lower()
    if not any(k in ml for k in _PT_LEG_MODES):
        return ""
    return (" Abonné aux transports en commun." if has_pt
            else " Pas d'abonnement aux transports en commun.")


def _build_profile_narrative(traits: dict) -> str:
    name = traits.get("name", "")
    first_name = name.split()[0] if name else ""
    age = traits.get("age", "")
    occupation = traits.get("main_occupation") or traits.get("professional_activity", "")
    household = traits.get("household_size")
    _income_map = {
        "Very Low": "très faible", "Low": "faible", "Medium": "moyen",
        "Medium-Low": "moyen-bas", "Medium-High": "moyen-élevé", "High": "élevé", "Very High": "très élevé",
    }
    income = _income_map.get(traits.get("income") or "", (traits.get("income") or "").lower())

    extras = []
    if household == 1:
        extras.append("seul(e)")
    elif household:
        extras.append(f"famille de {household} pers.")
    if income:
        extras.append(f"revenu {income}")
    line1 = f"{first_name}, {age} ans, {occupation}"
    if extras:
        line1 += f" ({', '.join(extras)})"

    # La ligne « Mobilité : » a disparu le 2026-08-26. Ce qu'elle portait :
    #
    # * `car_availability` et le statut de conducteur — RETIRÉS. Le jeu d'options dit déjà
    #   si la voiture est prenable (`_owns_car` / `_can_drive` du contrôleur la proposent
    #   ou non), et le canal narratif a été mesuré puis rejeté : +0,12 pt de part voiture,
    #   au niveau du bruit (ticket 018, docs/traces/2026-08-24_car_availability).
    # * le vélo personnel — RETIRÉ pour la même raison. ⚠ Avec une perte assumée : un
    #   agent qui possède un vélo garé ailleurs (chaîne de véhicules) n'a pas d'option
    #   vélo, et le prompt ne dit plus qu'il en a un. Comme il ne peut pas s'en servir,
    #   l'information ne portait aucune décision.
    # * l'abonnement TC — DÉPLACÉ sur l'option TC (cf. `pt_subscription_suffix`) : il
    #   n'est PAS déductible du jeu d'options (une option bus existe, abonné ou pas),
    #   donc il reste servi — mais là où il pèse, et seulement quand un TC est proposé.
    #
    # Ne reste que l'identité sociale, seule information du bloc que les options ne
    # portent pas. Une ligne vide n'est pas rendue.
    return line1


class LlmAgent:
    DEFAULT_IDENTITY = ""

    def __init__(self):
        self.short_term_memory: dict[str, UserShortTermMemory] = {}
        if settings.agent.long_term_memory_enabled:
            self.long_term_memory = MultiUserLongTermMemory(
                storage_dir=settings.agent.long_term_memory_storage_dir,
                long_term_memory_filter_by_datetime=settings.agent.long_term_memory_filter_by_datetime,
                max_loaded_metadata=settings.agent.long_term_max_loaded_metadata,
            )
        else:
            self.long_term_memory = None
            logger.info("Long-term memory disabled — ChromaDB initialization skipped")
        
        # Instance du client LLM (Singleton naturel pour cet Agent) — SDK typé
        # (AsyncClient httpx réutilisé entre les appels, résultats TaskResult)
        self.llm_client = LLMGatewayClient(
            base_url=os.getenv("LLM_API_URL", "http://localhost:8000"),
            wait_timeout=settings.agent.remote_llm_poll_timeout,
            backpressure_max_inflight=settings.world.worker_concurrency,
            backpressure_release_ratio=settings.agent.remote_llm_backpressure_ratio,
            circuit_failure_threshold=settings.agent.remote_llm_circuit_failure_threshold,
            circuit_probe_interval=settings.agent.remote_llm_circuit_probe_interval,
        )
        self.prompt_manager = PromptManager(os.path.join(os.path.dirname(__file__), "prompts"))

        if settings.cache.enabled:
            population_name = f"{settings.data.synthetic_file_prefix}population_{settings.data.population_size}"
            # Isolation du cache par version de prompt système : si le prompt actif
            # (llm_module/prompts/prompts.yaml) change, le checksum change et le cache
            # repart à neuf au lieu de réutiliser des décisions obsolètes.
            prompt_checksum = llm_module_prompt_manager.active_prompt_checksum()
            cache_dir = os.path.join(settings.cache.cache_dir, prompt_checksum, population_name)
            logger.info(f"LLM cache isolé par prompt — checksum={prompt_checksum}, dir={cache_dir}")
            self.llm_cache = LlmSemanticCache(
                cache_dir=cache_dir,
                semantic_threshold=settings.cache.semantic_threshold,
                embed_model_name=settings.cache.embed_model_name,
            )
            # Mémoïsation exacte des réflexions (ticket 012) — même répertoire que le
            # cache de décisions : l'isolation par checksum de prompt est héritée.
            self.reflection_memo = (
                ReflectionMemoStore(cache_dir=cache_dir)
                if settings.cache.reflection_memo_enabled else None
            )
        else:
            self.llm_cache = None
            self.reflection_memo = None

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
        return _build_profile_narrative(person.identity.traits_json)

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

        # logger.debug(f"Querying experiences with travel plans for user {context.person.person_id}, activity {context.activity_id}, query text: {text}")

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

        # logger.debug(f"Found {len(hist)} relevant experiences for travel plans for user {context.person.person_id}, activity {context.activity_id}")

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
                date_str = datetime.strftime(datetime.fromisoformat(entry.metadata['timestamp']), '%A, %B %d')
                resp.append(f"[{date_str}] {entry.content}")
                ts.append(datetime.fromisoformat(entry.metadata['timestamp']).timestamp())
            elif str(entry.metadata["memory_type"]) == str(MemoryType.CONCEPT.value):
                concept = json.loads(entry.content)
                resp.append(f"[Concept] {concept[0]}" if concept else "")
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
    
    async def build_travel_plan_payload(
        self,
        context: Context,
        options: list[TravelPlan],
        destination: str,
        departure_time: int = 0,
        anticipation: Optional[dict] = None,
    ) -> Dict[str, Any]:
        agent_id = context.person.person_id
        perception = self.get_person_identity_description(context.person) # TODO To be remplace by feeling and perception about transport modes
        current_time = humanize_time(context.timestamp)
        city_context = weather_to_natural_language(get_weather(context.timestamp)) or "None"

        history = []
        if settings.agent.long_term_memory_enabled:
            _pl = PipelineLogger.get()
            _rec = _pl.get_record(context.person.person_id) if _pl is not None else None
            if _rec is not None:
                _rec.T_ltm_start = time.time()
            history = await self.query_past_experiences_for_travel(context, options)
            if _rec is not None:
                _rec.T_ltm_end = time.time()

        # Abonnement TC : porté par l'option, pas par le persona (cf. `_pt_subscription_note`).
        _has_pt = bool((context.person.identity.traits_json or {}).get("has_pt_subscription", False))

        def _describe(opt: TravelPlan) -> str:
            """Texte de l'option, avec la mention d'abonnement sur sa PREMIÈRE ligne.

            Les lignes suivantes sont les étapes de l'itinéraire, ré-indentées en
            sous-puces par le gabarit : y coller la mention la ferait passer pour une
            étape. Elle est donc accolée à la phrase de synthèse.
            """
            text = env_ob_to_text("travel_plan", opt.model_dump())
            note = _pt_subscription_note(opt.mode_label() or "", _has_pt)
            if not note:
                return text
            head, sep, tail = text.partition("\n")
            return f"{head.rstrip()}{note}{sep}{tail}"

        # Utilisation d'une compréhension de liste pour la performance et la clarté
        trajectories = [
            {
                "index": i,
                "mode": opt.mode_label() or "unknown",
                "description": _describe(opt),
                # Distance totale du trajet (en mètres) — utilisée pour les métriques Prometheus
                "total_distance_m": (
                    opt.distance
                    if opt.distance is not None
                    else sum(leg.get_distance() for leg in (opt.legs or []))
                ),
            }
            for i, opt in enumerate(options)
        ]

        dest_zone = options[0].end_location.zone if options and options[0].end_location else None

        return {
            "category": "itinary_multi_agent",
            "agents": [
                {
                    "agent_id": agent_id,
                    # `Contraintes : None` retiré le 2026-08-26 : littéral codé en dur,
                    # jamais implémenté, mesuré constant sur 2 487 records sur 2 487.
                    "perception": perception,
                    "destination": destination,
                    "destination_zone": dest_zone,
                    "departure_time": humanize_time(departure_time) if departure_time else None,
                    "departure_timestamp": float(departure_time) if departure_time else None,
                    "current_time": current_time,
                    # Météo/trafic propre à l'agent (et non plus au niveau requête) :
                    # la clé de batch hache `parameters`, donc en sortant la météo des
                    # parameters, des demandes de météos différentes peuvent fusionner
                    # dans un même appel LLM — chaque persona garde la sienne dans le
                    # prompt (cf. itinary_multi_agent.md.j2, injection par bloc).
                    "context": city_context,
                    # Anticipation de la chaîne (ticket 014) : météo des tranches
                    # restantes de la journée et agenda glissant des trajets
                    # restants — construits par le contrôleur (_build_anticipation),
                    # rendus par bloc dans le gabarit. La position des véhicules
                    # n'est plus énoncée (biais vélo mesuré) : la règle de chaîne
                    # vit dans le prompt système (variante expert_chaine).
                    "day_outlook": (anticipation or {}).get("outlook"),
                    "agenda": (anticipation or {}).get("agenda") or [],
                    "history": history,
                    "trajectories": trajectories
                }
            ],
            "parameters": {
                **settings.agent.llm_params
            }
        }

    async def evaluate_and_choose_travel_plan(
        self, context: Context, options: list[TravelPlan], destination: str, departure_time: int = 0,
        anticipation: Optional[dict] = None,
    ) -> tuple[int, str, str, dict]:
        """Choisit un itinéraire et renvoie (index, justification, provider, répartition).

        La répartition est la distribution de probabilité par mode canonique qui a servi
        au tirage (modes non proposés inclus, à 0) — vide si la décision n'en vient pas
        (réponse à l'ancien format, point de cache hérité, erreur). Elle est tracée
        telle quelle dans `moves.csv`.

        `anticipation` (ticket 014) : contexte d'anticipation construit par le
        contrôleur — injecté dans le prompt, et sa `signature` entre dans la clé du
        cache de décisions (deux anticipations différentes = deux entrées distinctes).
        """
        assert options, "No travel options provided for planning trip."
        anticipation_key = (anticipation or {}).get("signature", "")

        # Ordre déterministe pour les clés de cache (indépendant du shuffle)
        sorted_options = sorted(options, key=lambda p: p.get_code() or "")
        # Shuffle séparé pour le payload LLM (évite le biais de position)
        shuffled_options = list(options)
        random.shuffle(shuffled_options)

        activity_purpose = options[0].purpose or ""
        weather = get_weather(context.timestamp)

        # Graine du tirage : le jour simulé en fait partie, donc un même contexte
        # rejoué le lendemain retire un autre mode (y compris sur un cache hit),
        # tandis qu'un run relancé à l'identique reproduit exactement les mêmes trajets.
        seed_parts = (
            settings.agent.mode_draw_seed,
            context.person.person_id,
            context.activity_id,
            datetime.fromtimestamp(context.timestamp, tz=timezone.utc).strftime("%Y-%m-%d"),
        )

        # --- Cache hybride (avant l'appel LLM) ---
        # Sans souvenir, la décision ne dépend que des conditions factuelles : correspondance
        # exacte, et le payload — donc la requête LTM — n'est construit qu'en cas de miss.
        # Avec des souvenirs, le vécu de l'agent pèse sur la décision : on doit construire le
        # payload d'abord pour comparer la LTM courante à celle qui a produit la décision cachée.
        has_memories = (
            self.long_term_memory is not None
            and self.long_term_memory.has_memories(context.person.person_id)
        )
        payload = None
        memory_text = None
        if has_memories:
            payload = await self.build_travel_plan_payload(context, shuffled_options, destination, departure_time, anticipation)
            # Texte mémoire : sérialisation du champ history déjà calculé dans le payload
            memory_text = json.dumps(payload["agents"][0].get("history", []), ensure_ascii=False)

        if self.llm_cache is not None:
            cache_hit = await self.llm_cache.lookup(
                agent_id=context.person.person_id,
                activity_id=context.activity_id,
                timestamp=context.timestamp,
                options=sorted_options,
                memory_text=memory_text,
                weather=weather,
                activity_purpose=activity_purpose,
                seed_parts=seed_parts,
                extra_key=anticipation_key,
            )
            if cache_hit is not None:
                chosen_plan = sorted_options[cache_hit["index"]]
                original_index = options.index(chosen_plan)
                if cache_hit.get("distribution"):
                    reason = (
                        "Mode tiré au sort dans la distribution mise en cache : "
                        + _format_distribution(cache_hit["distribution"])
                    )
                else:
                    reason = "Décision récupérée depuis le cache sémantique LLM."
                plan_summary = env_ob_to_text("travel_plan", chosen_plan.model_dump())
                stm_msg = f"[ TRAVEL_PLAN ] Plan to head <{destination}> served from LLM cache.\n{plan_summary}\nReasoning: {reason}"
                self.add_short_term_memory(context, stm_msg, timestamp=context.timestamp)
                logger.debug(f"Cache hit for person {context.person.person_id}, activity {context.activity_id}, returning cached plan with reason: {reason}")
                # Écriture jsonl déportée hors de l'event loop (open/write bloquants)
                await asyncio.to_thread(
                    log_llm_cache_hit,
                    agent_id=context.person.person_id,
                    activity_id=context.activity_id,
                    sim_ts=float(context.timestamp),
                    mode=cache_hit.get("mode", ""),
                )
                return (original_index, reason, f"cache:{cache_hit.get('mode', '')}",
                        cache_hit.get("distribution") or {})

        # Cache miss sur la branche « mémoire vide » : le payload reste à construire.
        if payload is None:
            payload = await self.build_travel_plan_payload(context, shuffled_options, destination, departure_time, anticipation)

        _pl = PipelineLogger.get()
        _rec = _pl.get_record(context.person.person_id) if _pl is not None else None

        try:
            if _rec is not None:
                _rec.T_llm_start = time.time()
            llm_result = await self.llm_client.execute(payload)
            _t_after_llm = time.time()
            provider_used = llm_result.provider_used or ""

            if _rec is not None:
                _post_ms = (llm_result.timing.post_ms if llm_result.timing else 0) or 0
                _rec.T_llm_sent = _rec.T_llm_start + _post_ms / 1000
                _rec.T_llm_result = _t_after_llm
                _timing_p5 = llm_result.timing.timing_p5 if llm_result.timing else None
                if _timing_p5 and _pl is not None:
                    _pl.apply_timing_p5(context.person.person_id, _timing_p5)

            if llm_result.ok:
                agent_result = llm_result.agents[0]
                # Le LLM note toutes les options (somme = 100) ; le mode effectif est
                # tiré au sort dans cette distribution. Les poids sont ré-alignés sur
                # `sorted_options` (ordre déterministe par code) pour que le tirage ne
                # dépende pas du mélange anti-biais de position appliqué au prompt.
                weights = None
                weights_are_fallback = False
                if agent_result.probabilities:
                    # Modes tels qu'ils ont été envoyés dans le prompt : ils permettent de
                    # réaligner une réponse dont les index sont hors bornes (le modèle a
                    # renuméroté les options) au lieu d'en perdre la masse.
                    sent_modes = [t.get("mode") for t in payload["agents"][0]["trajectories"]]
                    shuffled_weights = normalize_option_probabilities(
                        agent_result.probabilities, len(shuffled_options),
                        modes=sent_modes,
                        context=f"agent={context.person.person_id} activity={context.activity_id}",
                    )
                    # Repli uniforme (vecteur LLM inexploitable) : le tirage reste valable
                    # pour CE trajet, mais la distribution n'est pas une décision du modèle
                    # — elle ne doit jamais atteindre le cache persistant.
                    weights_are_fallback = isinstance(shuffled_weights, UniformFallback)
                    position_in_sorted = {id(opt): i for i, opt in enumerate(sorted_options)}
                    weights = [0.0] * len(sorted_options)
                    for opt, w in zip(shuffled_options, shuffled_weights):
                        weights[position_in_sorted[id(opt)]] += w
                    index = draw_index(weights, *seed_parts)
                    decision_list = sorted_options
                else:
                    # Réponse à l'ancien format (un index choisi) — repli sans tirage.
                    index = agent_result.chosen_index
                    decision_list = shuffled_options

                if isinstance(index, int) and 0 <= index < len(decision_list):
                    reason = agent_result.reason or "Pas de justification fournie."

                    # Normalisation de la raison (alignement avec aplan_trip_old)
                    if "is chosen because it" in reason:
                        reason = f"This plan {reason.split('is chosen because it', 1)[1].strip()}"

                    chosen_plan = decision_list[index]

                    distribution = {}
                    if weights is not None:
                        modes = [opt.mode_label() for opt in sorted_options]
                        distribution = mode_distribution(weights, modes)
                        reason = (
                            f"{reason} [Répartition estimée : "
                            f"{_format_distribution(distribution)} — mode tiré au sort.]"
                        )

                    # Écriture de la décision en short-term memory pour alimenter la réflexion journalière
                    plan_summary = env_ob_to_text("travel_plan", chosen_plan.model_dump())
                    stm_msg = f"[ TRAVEL_PLAN ] Plan to head <{destination}> chosen by gateway LLM.\n{plan_summary}\nReasoning: {reason}"
                    self.add_short_term_memory(context, stm_msg, timestamp=context.timestamp)

                    original_index = options.index(chosen_plan)
                    if _rec is not None:
                        _rec.T_extract_end = time.time()

                    # --- Insertion asynchrone dans le cache (fire-and-forget) ---
                    # C'est la distribution qui est mise en cache, pas la décision : au
                    # prochain hit, un nouveau tirage aura lieu sur ces mêmes probabilités.
                    # Jamais pour un repli uniforme : le cache n'a pas de mode dégradé,
                    # un repli persisté servirait du hasard aux runs suivants.
                    if self.llm_cache is not None and weights_are_fallback:
                        logger.info(
                            f"[cache] store refusé — distribution de repli uniforme non persistée | "
                            f"agent={context.person.person_id} activity={context.activity_id}"
                        )
                    elif self.llm_cache is not None:
                        mode = chosen_plan.mode_label()
                        _cache_task = create_background_task(self.llm_cache.store(
                            agent_id=context.person.person_id,
                            activity_id=context.activity_id,
                            timestamp=context.timestamp,
                            options=sorted_options,
                            memory_text=memory_text,
                            chosen_plan_code=chosen_plan.get_code(),
                            mode=mode,
                            weather=weather,
                            probabilities=weights,
                            extra_key=anticipation_key,
                        ))
                        _cache_task.add_done_callback(
                            lambda t: logger.warning(f"Cache store failed: {t.exception()}") if not t.cancelled() and t.exception() else None
                        )
                        logger.debug(f"Cache store task created for person {context.person.person_id}, activity {context.activity_id}, chosen plan mode: {mode}")

                    # Retourne l'index dans la liste originale (non mélangée) pour cohérence avec le caller
                    return original_index, reason, provider_used, distribution

                if _rec is not None:
                    _rec.T_extract_end = time.time()

            error_msg = llm_result.error or "Format de réponse invalide ou timeout."
            logger.warning(f"aplan_trip: gateway a retourné un résultat invalide pour {context.person.person_id}: {error_msg}")
            return -1, error_msg, provider_used, {}

        except Exception as e:
            logger.exception(f"Erreur lors de l'appel à l'API Gateway LLM: {e}")
            return -1, str(e), "", {}

    async def trigger_short_term_reflection_for_all_people(self, timestamp: int, people: list[Person]):
        """
        Reflect on all short-term memories of all people at the given timestamp.
        This is used to process all short-term memories at once, e.g. at the end of the day.
        """
        if settings.agent.long_term_memory_enabled is False:
            logger.info("Long-term memory is disabled, skipping reflection.")
            return
        
        import asyncio

        sem = asyncio.Semaphore(10)

        async def _reflect_one(person):
            async with sem:
                context = Context(person=person, timestamp=timestamp, data={"type": "reflection"})
                await self.reflect_on_short_term_memory(context)

        await asyncio.gather(*[_reflect_one(p) for p in people])

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

        all_entries = self.long_term_memory.get_last_user_memories(
            person_id=context.person.person_id,
            from_date=from_date,
        )
        if not all_entries:
            logger.info(f"No long-term memory available for reflection for {context.person.person_id}")
            return

        entries_text = "\n".join(
            f"- Time {humanize_date(entry.timestamp.timestamp())}: {entry.content}"
            for entry in all_entries
        )
        identity_description = self.get_person_identity_description(context.person)

        # Mémoïsation exacte (ticket 012) — même principe que la réflexion STM.
        memo_key = None
        reflection: Optional[str] = None
        if self.reflection_memo is not None:
            memo_key = ReflectionMemoStore.make_key(
                person_id=context.person.person_id,
                category="ltm_self_reflection",
                identity=identity_description,
                context_text=entries_text,
                departure_timestamp=float(context.timestamp),
                llm_params=settings.agent.llm_params,
            )
            hit = await asyncio.to_thread(self.reflection_memo.lookup, memo_key, "ltm_self_reflection")
            if hit is not None:
                reflection = hit["reflection"]
                logger.info(
                    f"[reflection-memo] hit LTM — auto-réflexion servie sans appel LLM | "
                    f"person={context.person.person_id} (payée par {hit['provider'] or '?'})"
                )

        if reflection is None:
            payload = {
                "category": "ltm_self_reflection",
                "agents": [{
                    "agent_id": context.person.person_id,
                    "perception": identity_description,
                    "context": entries_text,
                    "departure_timestamp": float(context.timestamp),
                }],
                "parameters": {**settings.agent.llm_params},
            }

            llm_result = await self.llm_client.execute(payload)
            results = llm_result.agents
            if not results:
                logger.error(f"LTM self-reflection gateway returned no result for {context.person.person_id}")
                return
            # AgentResponse accepte les champs hors schéma (extra=allow) —
            # "reflection" est porté par la catégorie ltm_self_reflection.
            reflection = getattr(results[0], "reflection", "") or ""
            if self.reflection_memo is not None:
                await asyncio.to_thread(
                    self.reflection_memo.store, memo_key, context.person.person_id,
                    "ltm_self_reflection", reflection, None, llm_result.provider_used or "",
                )

        try:
            entry = MemoryEntry(
                person_id=context.person.person_id,
                content=reflection,
                timestamp=datetime.fromtimestamp(context.timestamp),
                memory_type=MemoryType.REFLECTION,
            )
            await self.aadd_long_term_memory(context, entry)
        except Exception as e:
            logger.error(f"Failed to store LTM self-reflection for person {context.person.person_id}, err: {e}")

    async def reflect_on_short_term_memory(self, context: Context):
        mem = self.get_short_term_memory(context.person.person_id)
        group_messages, all_messages = mem.get_all_message_and_group()

        if not all_messages:
            logger.info("No short-term memory available for reflection.")
            return

        exp = []
        for group in group_messages:
            if group:
                activity = PersonScheduler(context.person).get_activity(group[0].activity_id) if group[0].activity_id else None
                exp.append({
                    "purpose": activity.purpose if activity else None,
                    "observations": [msg.content for msg in group],
                })
        experiences_text = json.dumps(exp, indent=2, ensure_ascii=False)

        identity_description = self.get_person_identity_description(context.person)
        custom_guidelines = f"\n**IMPORTANT CUSTOM GUIDELINES** {settings.agent.reflection_custom_guidelines}" if settings.agent.reflection_custom_guidelines else ""

        # Mémoïsation exacte (ticket 012) : même agent, même vécu, mêmes consignes
        # ⇒ même introspection. Hit ⇒ appel LLM évité ; les effets (consommation
        # STM, écritures LTM) restent strictement identiques à un appel réel.
        memo_key = None
        reflection: Optional[str] = None
        concepts: list = []
        if self.reflection_memo is not None:
            memo_key = ReflectionMemoStore.make_key(
                person_id=context.person.person_id,
                category="stm_reflection",
                identity=identity_description,
                context_text=experiences_text,
                guidelines=custom_guidelines,
                departure_timestamp=float(context.timestamp),
                llm_params=settings.agent.llm_params,
            )
            hit = await asyncio.to_thread(self.reflection_memo.lookup, memo_key, "stm_reflection")
            if hit is not None:
                reflection, concepts = hit["reflection"], hit["concepts"]
                logger.info(
                    f"[reflection-memo] hit STM — réflexion servie sans appel LLM | "
                    f"person={context.person.person_id} (payée par {hit['provider'] or '?'})"
                )

        if reflection is None:
            payload = {
                "category": "stm_reflection",
                "min_tpm_required": settings.agent.stm_reflection_min_tpm,
                "agents": [{
                    "agent_id": context.person.person_id,
                    "perception": identity_description,
                    "context": experiences_text,
                    "departure_timestamp": float(context.timestamp),
                }],
                "parameters": {
                    "custom_guidelines": custom_guidelines,
                    **settings.agent.llm_params,
                },
            }

            llm_result = await self.llm_client.execute(payload)
            results = llm_result.agents
            if not results:
                logger.error(f"STM reflection gateway returned no result for {context.person.person_id}")
                return

            agent_result = results[0]
            # AgentResponse accepte les champs hors schéma (extra=allow) —
            # "reflection"/"concepts" sont portés par la catégorie stm_reflection.
            reflection = (getattr(agent_result, "reflection", "") or "").strip()
            concepts = getattr(agent_result, "concepts", []) or []

            if self.reflection_memo is not None:
                # Le store refuse le vide (D3) : un échec de génération ne se rejoue pas.
                await asyncio.to_thread(
                    self.reflection_memo.store, memo_key, context.person.person_id,
                    "stm_reflection", reflection, concepts, llm_result.provider_used or "",
                )

        self.get_short_term_memory(context.person.person_id).remove_batch(all_messages)
        start_timestamp = all_messages[0].timestamp

        entries = []
        try:
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
            logger.exception(f"Failed to parse STM reflection response: {e}")

        for entry in entries:
            await self.aadd_long_term_memory(context, entry)