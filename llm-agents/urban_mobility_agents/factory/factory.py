import os
import time
import httpx
from settings import settings
from inputs.gtfs.reader import GTFSData
from world import *
from trip_helper.cached_triphelper import CachedTripHelper
from trip_helper.otp import OTPTripHelper
from inputs.population import SyntheticPopulationLoader, PersonCloseToTheStopFilter
from trip_helper import SolariTripHelper
from urban_mobility_agents.simulation_controller import SimulationLoopV1
from urban_mobility_agents.core.scenario import BaseScenario
from urban_mobility_agents.agents.llm_agent import LlmAgent
from loguru import logger


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


def bootstrap() -> BaseScenario:
    gtfs_data = GTFSData.DEFAULT()

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
                    max_distance=500,  # 500 meters
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

    trip_helper = None
    if settings.gtfs.mode == "OTP":
        logger.info("Using OTP trip helper")
        wait_for_all_otp()
        trip_helper = OTPTripHelper(gtfs_data=gtfs_data)
    else:
        logger.info("Using Solari trip helper")
        trip_helper = CachedTripHelper(
            world_model=world_model,
            trip_helper=SolariTripHelper(
                endpoint=settings.gtfs.solari_endpoint,
                gtfs_data=gtfs_data,
            ),
        )

    loop = SimulationLoopV1(
        world_model=world_model,
        trip_helper=trip_helper,
        agent=LlmAgent(),
    )

    return loop
