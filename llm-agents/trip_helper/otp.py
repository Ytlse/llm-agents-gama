import itertools
import json
import os
import time
from typing import List, Optional

from datetime import datetime, timezone
from loguru import logger
from inputs.gtfs import GTFSData
from settings import settings
from models import Location, TransitLocation, TravelPlan, Transit
import aiohttp
import asyncio
from trip_helper.base import TripHelper
from trip_helper.osmnx_direct import get_direct_plan
from utils import random_uuid
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from prometheus_client import Counter, Gauge, Histogram
import math
import numpy as np

OTP_REQUESTS_OK  = Counter(
    'otp_requests_ok_total',
    'Requêtes OTP réussies (après éventuels retries)',
)
OTP_REQUESTS_ERR = Counter(
    'otp_requests_err_total',
    'Tentatives OTP échouées (chaque retry compte)',
    ['reason'],  # 'timeout' | 'http_error' | 'other'
)
OTP_REQUEST_LATENCY = Histogram(
    'otp_request_duration_seconds',
    'Durée des requêtes OTP réussies',
    ['instance'],
    buckets=[0.1, 0.25, 0.5, 1, 2, 5, 10],
)
OTP_REQUESTS_INFLIGHT = Gauge(
    'otp_requests_inflight',
    'Requêtes OTP transit en cours (agents attendant la réponse OTP)',
)


QUERY = """
query trip($accessEgressPenalty: [PenaltyForStreetMode!], $alightSlackDefault: Int, $alightSlackList: [TransportModeSlack], $arriveBy: Boolean, $banned: InputBanned, $bicycleOptimisationMethod: BicycleOptimisationMethod, $bikeSpeed: Float, $boardSlackDefault: Int, $boardSlackList: [TransportModeSlack], $bookingTime: DateTime, $dateTime: DateTime, $filters: [TripFilterInput!], $from: Location!, $ignoreRealtimeUpdates: Boolean, $includePlannedCancellations: Boolean, $includeRealtimeCancellations: Boolean, $itineraryFilters: ItineraryFilters, $locale: Locale, $maxAccessEgressDurationForMode: [StreetModeDurationInput!], $maxDirectDurationForMode: [StreetModeDurationInput!], $maximumAdditionalTransfers: Int, $maximumTransfers: Int, $modes: Modes, $numTripPatterns: Int, $pageCursor: String, $relaxTransitGroupPriority: RelaxCostInput, $searchWindow: Int, $timetableView: Boolean, $to: Location!, $transferPenalty: Int, $transferSlack: Int, $triangleFactors: TriangleFactors, $useBikeRentalAvailabilityInformation: Boolean, $via: [TripViaLocationInput!], $waitReluctance: Float, $walkReluctance: Float, $walkSpeed: Float, $wheelchairAccessible: Boolean, $whiteListed: InputWhiteListed) {
  trip(
    accessEgressPenalty: $accessEgressPenalty
    alightSlackDefault: $alightSlackDefault
    alightSlackList: $alightSlackList
    arriveBy: $arriveBy
    banned: $banned
    bicycleOptimisationMethod: $bicycleOptimisationMethod
    bikeSpeed: $bikeSpeed
    boardSlackDefault: $boardSlackDefault
    boardSlackList: $boardSlackList
    bookingTime: $bookingTime
    dateTime: $dateTime
    filters: $filters
    from: $from
    ignoreRealtimeUpdates: $ignoreRealtimeUpdates
    includePlannedCancellations: $includePlannedCancellations
    includeRealtimeCancellations: $includeRealtimeCancellations
    itineraryFilters: $itineraryFilters
    locale: $locale
    maxAccessEgressDurationForMode: $maxAccessEgressDurationForMode
    maxDirectDurationForMode: $maxDirectDurationForMode
    maximumAdditionalTransfers: $maximumAdditionalTransfers
    maximumTransfers: $maximumTransfers
    modes: $modes
    numTripPatterns: $numTripPatterns
    pageCursor: $pageCursor
    relaxTransitGroupPriority: $relaxTransitGroupPriority
    searchWindow: $searchWindow
    timetableView: $timetableView
    to: $to
    transferPenalty: $transferPenalty
    transferSlack: $transferSlack
    triangleFactors: $triangleFactors
    useBikeRentalAvailabilityInformation: $useBikeRentalAvailabilityInformation
    via: $via
    waitReluctance: $waitReluctance
    walkReluctance: $walkReluctance
    walkSpeed: $walkSpeed
    wheelchairAccessible: $wheelchairAccessible
    whiteListed: $whiteListed
  ) {
    previousPageCursor
    nextPageCursor
    tripPatterns {
      aimedStartTime
      aimedEndTime
      expectedEndTime
      expectedStartTime
      duration
      distance
      legs {
        id
        mode
        aimedStartTime
        aimedEndTime
        expectedEndTime
        expectedStartTime
        realtime
        distance
        duration
        fromPlace {
          name
          latitude
          longitude
          quay {
            id
          }
        }
        toPlace {
          name
          latitude
          longitude
          quay {
            id
          }
        }
        toEstimatedCall {
          destinationDisplay {
            frontText
          }
        }
        line {
          publicCode
          name
          id
          presentation {
            colour
          }
        }
        authority {
          name
          id
        }
        pointsOnLink {
          points
        }
        interchangeTo {
          staySeated
        }
        interchangeFrom {
          staySeated
        }
      }
      systemNotices {
        tag
      }
    }
  }
}
"""

class OTPPlace(BaseModel):
    name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    quay: Optional[dict] = None

    @property
    def lat(self) -> Optional[float]:
        return self.latitude

    @property
    def lon(self) -> Optional[float]:
        return self.longitude

class OTPEstimatedCall(BaseModel):
    destinationDisplay: Optional[dict] = None

class OTPLine(BaseModel):
    publicCode: Optional[str] = None
    name: Optional[str] = None
    id: Optional[str] = None
    presentation: Optional[dict] = None

class OTPAuthority(BaseModel):
    name: Optional[str] = None
    id: Optional[str] = None

class OTPPointsOnLink(BaseModel):
    points: str

class OTPInterchange(BaseModel):
    staySeated: Optional[bool] = None

class OTPLeg(BaseModel):
    id: Optional[str] = None
    mode: str
    aimedStartTime: str
    aimedEndTime: str
    expectedEndTime: str
    expectedStartTime: str
    realtime: bool
    distance: float
    duration: int
    fromPlace: OTPPlace
    toPlace: OTPPlace
    toEstimatedCall: Optional[OTPEstimatedCall] = None
    line: Optional[OTPLine] = None
    authority: Optional[OTPAuthority] = None
    pointsOnLink: Optional[OTPPointsOnLink] = None
    interchangeTo: Optional[OTPInterchange] = None
    interchangeFrom: Optional[OTPInterchange] = None

class OTPSystemNotice(BaseModel):
    tag: str

class OTPTripPattern(BaseModel):
    aimedStartTime: str
    aimedEndTime: str
    expectedEndTime: str
    expectedStartTime: str
    duration: int
    distance: float
    legs: List[OTPLeg]
    systemNotices: Optional[List[OTPSystemNotice]] = []


CAR_ROUTE_MARKER = "__CAR__"

class OTPTripHelper(TripHelper):
    SUPPORTED_MODES = ["foot", "bus", "metro", "tram", "cableway", "car"]
    # Maximum walking distance (metres) to the nearest transit stop.
    # If both origin and destination have no stop within this radius, OTP is skipped.
    MAX_WALK_TO_STOP_M: int = 1_500

    def __init__(self, endpoint: str = None, gtfs_data: GTFSData = None):
        # Support multiple OTP instances via OTP_ENDPOINTS env var (comma-separated URLs).
        # Falls back to a single endpoint for backward compatibility.
        endpoints_env = os.getenv("OTP_ENDPOINTS", "")
        if endpoints_env:
            endpoints = [e.strip() for e in endpoints_env.split(",") if e.strip()]
        else:
            endpoints = [endpoint or settings.gtfs.otp_endpoint]
        self._endpoint_iter = itertools.cycle(endpoints)
        logger.info(f"OTPTripHelper initialized with {len(endpoints)} endpoint(s): {endpoints}")

        self.fixed_day: datetime = datetime.strptime(settings.gtfs.fixed_day, '%Y%m%d') if settings.gtfs.fixed_day else None
        self.gtfs_data = gtfs_data or GTFSData.DEFAULT()
        self._session: Optional[aiohttp.ClientSession] = None
        self._semaphore = asyncio.Semaphore(settings.gtfs.otp_max_concurrent)

        # Build stop coordinate array once for fast proximity checks (lat, lon).
        stops_df = self.gtfs_data.stops[['stop_lat', 'stop_lon']].dropna()
        self._stop_coords = stops_df.values.astype(float)  # shape (n, 2) — [lat, lon]

    def _has_reachable_stop(self, lon: float, lat: float) -> bool:
        """Return True if a transit stop is within MAX_WALK_TO_STOP_M metres."""
        dlat = self._stop_coords[:, 0] - lat
        dlon = (self._stop_coords[:, 1] - lon) * math.cos(math.radians(lat))
        dist_m = float(np.hypot(dlat, dlon).min()) * 111_320
        return dist_m <= self.MAX_WALK_TO_STOP_M

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            # Limite les connexions simultanées pour ne pas saturer le réseau ni OTP
            connector = aiohttp.TCPConnector(limit=50)
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    def timestamp_from_isoformat(self, iso_format: str) -> int:
        dt = datetime.fromisoformat(iso_format)
        return int(dt.timestamp())
    
    def parse_gtfs_entity_id(self, name: str) -> str:
        # OTP returns NeTEx IDs like "feedId:entityType:entityId" (e.g. "1:line:87")
        # Strip the feedId prefix; keep "entityType:entityId" (e.g. "line:87").
        if name.count(":") >= 2:
            return name.split(":", 1)[1]
        return name

    def _resolve_gtfs_stop(self, raw_id: str):
        """Try to resolve a stop by attempting multiple ID formats.

        OTP NeTEx IDs ("1:stop_point:SP_5672") strip to "stop_point:SP_5672".
        Some GTFS datasets store only the last segment ("SP_5672") as stop_id.
        """
        parsed_id = self.parse_gtfs_entity_id(raw_id)
        try:
            return self.gtfs_data.get_stop(parsed_id)
        except (ValueError, KeyError):
            pass
        # Fallback: try just the last colon-segment
        last_segment = raw_id.rsplit(":", 1)[-1]
        if last_segment != parsed_id:
            return self.gtfs_data.get_stop(last_segment)
        raise ValueError(f"Stop not found for OTP id '{raw_id}' (tried: '{parsed_id}', '{last_segment}')")

    def _parse_otp_travel_plan(self, 
                               travel_plan: dict, 
                               start_location: Optional[Location], 
                               end_location: Optional[Location],
                               real_day: Optional[datetime] = None) -> TravelPlan:
        obj = OTPTripPattern.model_validate(travel_plan)

        def _ptime(iso_time: str) -> int:
            t = self.timestamp_from_isoformat(iso_time)
            if self.fixed_day:
                # revert using real_day
                dt = (real_day - self.fixed_day).days if real_day else 0
                return t + dt * 24 * 60 * 60
            return t

        _proute = self.parse_gtfs_entity_id
        _pstopid = self.parse_gtfs_entity_id

        def _location_from_place(place: OTPPlace) -> TransitLocation:
            if place.name == "Origin":
                return TransitLocation(
                    stop="",
                    lat=start_location.lat,
                    lon=start_location.lon
                )
            elif place.name == "Destination":
                return TransitLocation(
                    stop="",
                    lat=end_location.lat,
                    lon=end_location.lon
                )

            if not (place.quay and place.quay.get("id")):
                raise ValueError(f"Invalid OTP place (missing quay id): {place}")

            try:
                stop = self._resolve_gtfs_stop(place.quay["id"])
                return TransitLocation(
                    stop=stop.stop_name,
                    stop_id=stop.stop_id,
                    lat=stop.stop_lat,
                    lon=stop.stop_lon,
                )
            except (ValueError, KeyError):
                if place.lat is None or place.lon is None:
                    raise ValueError(
                        f"Stop {place.quay['id']} not found in GTFS and OTP returned no coordinates for place '{place.name}'"
                    )
                logger.warning(f"Stop {place.quay['id']} not found in GTFS, using OTP coordinates for '{place.name}'")
                return TransitLocation(
                    stop=place.name,
                    stop_id=None,
                    lat=place.lat,
                    lon=place.lon,
                )


        transits = []
        for leg in obj.legs:
            assert leg.mode in self.SUPPORTED_MODES, f"Unsupported mode: {leg.mode}"
            is_transfer = leg.mode == "foot"
            is_car = leg.mode == "car"

            transit = Transit(
                start_time=_ptime(leg.expectedStartTime) * 1000,
                end_time=_ptime(leg.expectedEndTime) * 1000,
                duration=leg.duration,
                distance=leg.distance,
                mode=leg.mode,
                start_location=_location_from_place(leg.fromPlace),
                end_location=_location_from_place(leg.toPlace),
                is_transfer=is_transfer,
            )
            if is_car:
                transit.transit_route = CAR_ROUTE_MARKER
            elif not is_transfer and leg.line:
                transit.transit_route = _proute(leg.line.id)
                transit.shape_id = self.gtfs_data.get_shape_id_from_route_info(
                    route_id=transit.transit_route,
                    from_stop_id=transit.start_location.stop_id,
                    to_stop_id=transit.end_location.stop_id,
                )
            transits.append(transit)

        return TravelPlan(
            id=random_uuid(),
            start_location=start_location,
            end_location=end_location,
            start_time=_ptime(obj.expectedStartTime) * 1000,
            end_time=_ptime(obj.expectedEndTime) * 1000,
            duration=obj.duration,
            distance=obj.distance,
            legs=transits,
        )

    def remove_duplicates(self, trips: List[TravelPlan]) -> List[TravelPlan]:
        # Get max candidates from all results
        bl = set()
        rs = []
        for plan in trips:
            code = plan.get_code()
            if code in bl:
                continue
            bl.add(code)
            rs.append(plan)
        return rs
    
    def revert_fixed_date(self, timestamp: int, real_date: int) -> int:
        return 0

    async def get_itineraries(self,
                              origin: Location,
                              destination: Location,
                              departure_time: int,
                              search_window_m: int = None,
                              access_egress_mode: str = "foot",
                              include_car: bool=False,
                              include_bike: bool=True,
                              include_direct: bool=True,
                              include_transit: bool=True,
                              arrive_by: bool=False,
                              _timing_sink: dict | None = None) -> List[TravelPlan]:
        """
        Retrieve travel itineraries from OpenTripPlanner (OTP) and direct routes.

        This method fetches transit itineraries via OTP GraphQL API and optionally
        includes direct walking, biking, or driving routes using OSMnx. It handles
        fixed-day remapping for consistent scheduling, parallel requests with retry logic,
        and deduplication of results.

        Args:
            origin: Starting location.
            destination: Ending location.
            departure_time: Unix timestamp. When arrive_by=False (default) this is the
                departure time; when arrive_by=True this is the target arrival time.
            search_window_m: Search window in minutes (default 30).
            include_car: Whether to include car routes.
            arrive_by: When True OTP searches for itineraries that arrive by departure_time
                instead of departing at departure_time.

        Returns:
            List of TravelPlan objects representing itineraries.
        """
        if search_window_m is None:
            search_window_m = settings.gtfs.search_window_m

        # ── Fixed-day remapping ───────────────────────────────────────────────
        # Adjust departure time to a fixed day for consistent OTP queries,
        # while keeping the real day for congestion-aware routing.
        congestion_dt    = datetime.fromtimestamp(departure_time)
        real_day         = congestion_dt if self.fixed_day else None
        real_departure_time = departure_time
        if self.fixed_day is not None:
            departure_time = self.fixed_day.replace(
                hour=real_day.hour, minute=real_day.minute, second=real_day.second
            ).timestamp()
            # logger.debug(
            #     f"Using fixed day {self.fixed_day.date()} for departure_time, "
            #     f"real day is {real_day}, new departure_time is {departure_time}"
            # )
        real_day = real_day.replace(hour=0, minute=0, second=0, microsecond=0) if real_day else None

        # Create an HTTP session for API requests
        session  = await self.get_session()
        # Convert departure time to ISO format for OTP API
        start_at = datetime.fromtimestamp(departure_time, tz=timezone.utc).isoformat()

        # Common variables for OTP GraphQL queries
        common_vars = {
            "from": {"coordinates": {"latitude": origin.lat, "longitude": origin.lon}},
            "to":   {"coordinates": {"latitude": destination.lat, "longitude": destination.lon}},
            "dateTime": start_at,
            "arriveBy": arrive_by,
            "itineraryFilters": {"debug": "limitToNumOfItineraries"},
            "numTripPatterns": settings.gtfs.max_trip_candidates,
            "searchWindow": search_window_m,
        }

        # Define transit modes for OTP query (bus, metro, tram, cableway)
        transit_modes = {
            "accessMode": access_egress_mode,
            "transportModes": [
                {"transportMode": "bus"},
                {"transportMode": "metro"},
                {"transportMode": "tram"},
                {"transportMode": "cableway"},
            ],
            "egressMode": access_egress_mode,
        }
        # Build the payload for transit itinerary request
        transit_payload = {
            "query": QUERY,
            "variables": {**common_vars, "modes": transit_modes},
            "operationName": "trip",
        }

        # Define a retry-decorated function for making HTTP requests to OTP
        @retry(
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
        )
        async def make_request(payload):
            _t0 = time.monotonic()
            otp_url = next(self._endpoint_iter)
            try:
                async with session.post(otp_url, json=payload, timeout=10) as response:
                    response.raise_for_status()
                    result = await response.json()
                OTP_REQUESTS_OK.inc()
                _instance = otp_url.split("//")[-1].split("/")[0]
                OTP_REQUEST_LATENCY.labels(instance=_instance).observe(time.monotonic() - _t0)
                return result
            except asyncio.TimeoutError:
                OTP_REQUESTS_ERR.labels(reason='timeout').inc()
                raise
            except aiohttp.ClientResponseError:
                OTP_REQUESTS_ERR.labels(reason='http_error').inc()
                raise
            except aiohttp.ClientError:
                OTP_REQUESTS_ERR.labels(reason='other').inc()
                raise

        # ── Build parallel task list ──────────────────────────────────────────
        # Prepare tasks for transit (via OTP) and direct routes (via OSMnx).
        # Use semaphore for transit to limit concurrent requests.

        task_names: list[str] = []
        coros = []

        # Use precomputed public_transport flag when available; otherwise compute on-the-fly.
        origin_has_transit = (
            origin.public_transport
            if origin.public_transport is not None
            else self._has_reachable_stop(origin.lon, origin.lat)
        )
        dest_has_transit = (
            destination.public_transport
            if destination.public_transport is not None
            else self._has_reachable_stop(destination.lon, destination.lat)
        )

        async def _timed_otp(coro):
            t0 = time.monotonic()
            result = await coro
            d = time.monotonic() - t0
            if _timing_sink is not None:
                _timing_sink["transit_end"] = time.time()
            return result

        async def _timed_osmnx(coro, mode: str):
            t0 = time.monotonic()
            result = await coro
            d = time.monotonic() - t0
            if _timing_sink is not None:
                _timing_sink["osmnx_end"] = max(_timing_sink.get("osmnx_end", 0), time.time())
            return result

        if include_transit:
            if origin_has_transit and dest_has_transit:
                # logger.debug(
                #     f"OTP transit request | "
                #     f"from=({origin.lon:.7f},{origin.lat:.7f}) "
                #     f"to=({destination.lon:.7f},{destination.lat:.7f})"
                # )
                async def _transit_semaphored():
                    OTP_REQUESTS_INFLIGHT.inc()
                    try:
                        async with self._semaphore:
                            if _timing_sink is not None:
                                _timing_sink["transit_sem_end"] = time.time()
                            return await make_request(transit_payload)
                    finally:
                        OTP_REQUESTS_INFLIGHT.dec()

                task_names.append("transit")
                coros.append(_timed_otp(_transit_semaphored()))
            # else:
            #     logger.debug(
            #         f"Skipping OTP transit: origin_has_transit={origin_has_transit} "
            #         f"(lat={origin.lat:.5f}, lon={origin.lon:.5f}), "
            #         f"dest_has_transit={dest_has_transit} "
            #         f"(lat={destination.lat:.5f}, lon={destination.lon:.5f})"
            #     )

        if include_direct:
            task_names.append("foot")
            coros.append(_timed_osmnx(get_direct_plan(origin, destination, "foot",
                                            int(departure_time), congestion_dt,
                                            _timing_sink=_timing_sink), "foot"))
            if include_bike:
                task_names.append("bicycle")
                coros.append(_timed_osmnx(get_direct_plan(origin, destination, "bicycle",
                                                int(departure_time), congestion_dt,
                                                _timing_sink=_timing_sink), "bicycle"))
            if include_car:
                task_names.append("car")
                coros.append(_timed_osmnx(get_direct_plan(origin, destination, "car",
                                             int(departure_time), congestion_dt,
                                             _timing_sink=_timing_sink), "car"))

        if not coros:
            return []

        # Execute all tasks concurrently
        raw_results = await asyncio.gather(*coros, return_exceptions=True)
        named = dict(zip(task_names, raw_results))

        # ── Parse OTP transit result ──────────────────────────────────────────
        plans: List[TravelPlan] = []
        raw_pattern_counts = []
        parse_errors = 0

        if "transit" in named:
            result = named["transit"]
            if isinstance(result, Exception):
                logger.error(f"OTP transit request failed: {result}")
                raw_pattern_counts.append(-1)
            elif "data" not in result:
                logger.warning(f"OTP returned no data: {result.get('errors', result)}")
                raw_pattern_counts.append(-1)
            else:
                patterns = result["data"]["trip"]["tripPatterns"]
                raw_pattern_counts.append(len(patterns))
                if len(patterns) == 0:
                    logger.warning(
                        f"OTP returned 0 patterns (possible 'Couldn't link') | "
                        f"from=({origin.lon:.7f},{origin.lat:.7f}) "
                        f"to=({destination.lon:.7f},{destination.lat:.7f})"
                    )
                for item in patterns:
                    try:
                        # Parse each trip pattern into a TravelPlan
                        p = self._parse_otp_travel_plan(
                            item,
                            start_location=origin,
                            end_location=destination,
                            real_day=real_day,
                        )
                        # Calculate delay from requested departure (start_time is ms, real_departure_time is s)
                        # Negative = plan departs before query time; intentional, used by LLM to rank options.
                        p.start_in = int(p.start_time // 1000 - real_departure_time)
                        plans.append(p)
                    except Exception as e:
                        parse_errors += 1
                        logger.error(f"Error parsing travel plan: {e}, body: {item}")

        # ── Add OSMnx direct plans ────────────────────────────────────────────
        # Convert osmnx times from seconds to milliseconds to match OTP transit format.
        for mode in ("foot", "bicycle", "car"):
            if mode not in named:
                continue
            plan = named[mode]
            if isinstance(plan, Exception):
                logger.error(f"OSMnx {mode} plan failed: {plan}")
            elif plan is not None:
                plan.start_time *= 1000
                plan.end_time   *= 1000
                for leg in plan.legs:
                    leg.start_time *= 1000
                    leg.end_time   *= 1000
                plan.start_in = 0  # Direct plans start immediately
                plans.append(plan)

        # Filter plans that have legs (valid itineraries)
        plans_with_legs = [p for p in plans if p.legs]
        if not plans_with_legs:
            logger.warning(
                f"No usable itinerary | "
                f"origin=lat={origin.lat:.5f},lon={origin.lon:.5f} "
                f"dest=lat={destination.lat:.5f},lon={destination.lon:.5f} | "
                f"otp_patterns={raw_pattern_counts} parse_errors={parse_errors}"
            )
        # Remove duplicates and limit to max candidates
        plans = self.remove_duplicates(plans_with_legs)
        return plans


if __name__ == '__main__':
    import asyncio
    sth = OTPTripHelper(endpoint="http://localhost:8080/otp/transmodel/v3")
    loop = asyncio.get_event_loop()
    origin = Location(lon=1.53423130511658, lat=43.586655062927974)
    destination = Location(lon=1.486291134338381, lat=43.54970809807004)
    departure_time = 1742845000
    itineraries = loop.run_until_complete(sth.get_itineraries(origin, destination, departure_time))
    print(itineraries)
