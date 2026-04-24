import os
import time
import yaml
import httpx
from settings import settings
from inputs.gtfs.reader import GTFSData
from world import *
from trip_helper.base import TripHelper
from trip_helper.cached_triphelper import CachedTripHelper
from trip_helper.otp import OTPTripHelper
from inputs.population import SyntheticPopulationLoader, PersonCloseToTheStopFilter
from trip_helper import SolariTripHelper
from urban_mobility_agents.simulation_controller import SimulationLoopV1
from urban_mobility_agents.core.scenario import BaseScenario
from urban_mobility_agents.agents.llm_agent import LlmAgent
from loguru import logger
from dataclasses import dataclass


def _otp_endpoints_to_wait() -> list[str]:
    """Return the list of OTP transmodel endpoints that will actually be used."""
    env = os.getenv("OTP_ENDPOINTS", "")
    if env:
        return [e.strip() for e in env.split(",") if e.strip()]
    return [settings.gtfs.otp_endpoint]


def wait_for_otp(endpoint: str, timeout: int = 300, interval: int = 5) -> bool:
    """Poll a single OTP endpoint until it responds, logging progress."""
    health_url = endpoint.replace("/otp/transmodel/v3", "/otp")
    logger.info(f"Waiting for OTP at {health_url} ...")
    deadline = time.monotonic() + timeout
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        try:
            resp = httpx.get(health_url, timeout=3.0)
            if resp.status_code < 500:
                logger.info(f"✅ OTP accessible (HTTP {resp.status_code}) après {attempt} tentative(s) — {health_url}")
                return True
        except Exception as e:
            logger.debug(f"OTP pas encore prêt (tentative {attempt}) : {e} — {health_url}")
        time.sleep(interval)
    logger.error(f"❌ OTP inaccessible après {timeout}s — {health_url}")
    return False


def wait_for_all_otp(timeout: int = 300, interval: int = 5) -> bool:
    """Wait for every OTP endpoint listed in OTP_ENDPOINTS (or the single otp_endpoint)."""
    endpoints = _otp_endpoints_to_wait()
    results = [wait_for_otp(ep, timeout=timeout, interval=interval) for ep in endpoints]
    return all(results)


@dataclass
class StaticWorldData:
    gtfs_data: GTFSData
    trip_helper: TripHelper


def init_static_data() -> StaticWorldData:
    """Initialise les données lourdes et partagées (GTFS, Routeurs) au démarrage du serveur."""
    logger.info("Initialisation des données statiques du monde...")
    gtfs_data = GTFSData.DEFAULT()
    
    trip_helper = None
    if settings.gtfs.mode == "OTP":
        logger.info("Using OTP trip helper")
        wait_for_all_otp()
        trip_helper = OTPTripHelper(gtfs_data=gtfs_data)
    else:
        logger.info("Using Solari trip helper")
        trip_helper = CachedTripHelper(
            world_model=None, # Sera injecté plus tard si nécessaire, ou on modifie CachedTripHelper pour ne pas en dépendre
            trip_helper=SolariTripHelper(
                endpoint=settings.gtfs.solari_endpoint,
                gtfs_data=gtfs_data,
            ),
        )
    return StaticWorldData(gtfs_data=gtfs_data, trip_helper=trip_helper)


def _save_scenario_params(
    population_size: int,
    llm_agents: int,
    long_term_memory_enabled: bool,
    long_term_self_reflect_enabled: bool,
) -> None:
    """Persiste les paramètres effectifs du scénario GAMA dans le répertoire d'expérience."""
    workdir = getattr(settings, 'workdir', None)
    if workdir is None:
        return
    params = {
        'population_size': population_size,
        'number_of_llm_based_agents': llm_agents,
        'long_term_memory_enabled': long_term_memory_enabled,
        'long_term_self_reflect_enabled': long_term_self_reflect_enabled,
    }
    scenario_file = workdir / 'scenario_params.yaml'
    with open(scenario_file, 'w') as f:
        yaml.dump(params, f, default_flow_style=False, allow_unicode=True)
    logger.info(f"Paramètres de scénario sauvegardés dans {scenario_file}")


def init_dynamic_scenario(
    static_data: StaticWorldData,
    population_size: int = None,
    part_of_llm_agents: float = None,
    long_term_memory_enabled: bool = None,
    long_term_self_reflect_enabled: bool = None
) -> BaseScenario:
    """Initialise un nouveau run de simulation avec ses agents dynamiques."""
    logger.info("Création d'un nouveau scénario dynamique...")
    gtfs_data = static_data.gtfs_data

    # Surcharge des paramètres si fournis par GAMA, sinon on garde les valeurs courantes des settings
    if population_size is not None:
        settings.data.population_size = population_size
    if part_of_llm_agents is not None:
        settings.data.number_of_llm_based_agents = int(settings.data.population_size * part_of_llm_agents)
    if long_term_memory_enabled is not None:
        settings.agent.long_term_memory_enabled = long_term_memory_enabled
    if long_term_self_reflect_enabled is not None:
        settings.agent.long_term_self_reflect_enabled = long_term_self_reflect_enabled

    _save_scenario_params(
        population_size=settings.data.population_size,
        llm_agents=settings.data.number_of_llm_based_agents,
        long_term_memory_enabled=settings.agent.long_term_memory_enabled,
        long_term_self_reflect_enabled=settings.agent.long_term_self_reflect_enabled,
    )

    min_lon, min_lat, max_lon, max_lat = gtfs_data.get_bounding_box()
    buffer = 0.05  # degrees ~ 5km
    world_bbox = BBox(
        min_lon=min_lon - buffer,
        min_lat=min_lat - buffer,
        max_lon=max_lon + buffer,
        max_lat=max_lat + buffer,
    )

    world_grid = WorldGrid(world_bbox)
    time_grid = TimeGrid()

    population = WorldPopulation(
        SyntheticPopulationLoader(
            filters=[
                # TODO: supprimer ce filtre quand le mode voiture sera ajouté
                # (les agents pourront alors atteindre des destinations non desservies par les TC)
                PersonCloseToTheStopFilter(
                    max_distance=5000,  # 5000 meters
                    stop_locations=gtfs_data.all_stop_locations()
                )
            ]
        )
    ).init(world_bbox=world_bbox)

    # Set all people start from home
    for person in population.get_people_list():
        home_location = PersonScheduler(person).get_home_location()
        person.state.last_location = home_location

    world_model = WorldModel(
        world_grid=world_grid,
        time_grid=time_grid,
        gtfs_data=gtfs_data,
        bbox=world_bbox,
        population=population,
    )

    # Si utilisation de Solari, mettre à jour sa référence au world_model dynamiquement si nécessaire
    if hasattr(static_data.trip_helper, 'world_model'):
        static_data.trip_helper.world_model = world_model

    loop = SimulationLoopV1(
        world_model=world_model,
        trip_helper=static_data.trip_helper,
        agent=LlmAgent(),
    )

    return loop
