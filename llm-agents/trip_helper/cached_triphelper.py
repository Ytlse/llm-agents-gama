from collections import defaultdict
import os
import pickle
from trip_helper import TripHelper
from models import Location, TravelPlan
from world import WorldModel
from utils import square_distance, random_uuid
from settings import settings
from loguru import logger
import asyncio
from prometheus_client import Gauge

TRIP_CACHE_HIT_RATIO = Gauge(
    'trip_cache_hit_ratio',
    'Ratio cache hits / total du CachedTripHelper (0-1)',
)

class CachedTripHelper(TripHelper):
    def __init__(self, 
                 world_model: WorldModel,
                 trip_helper: TripHelper):
        super().__init__()
        self.trip_helper = trip_helper
        self.world_grid = world_model.world_grid
        self.time_grid = world_model.time_grid
        self.cache_size_per_grid = settings.gtfs.n_trip_in_grid  # max number of results per grid cell
        # cache top k results for each origin-destination pair
        if settings.gtfs.solari_cache_file and os.path.exists(settings.gtfs.solari_cache_file):
            with open(settings.gtfs.solari_cache_file, 'rb') as f:
                self.cache = pickle.load(f)
        else:
            self.cache = defaultdict(list)
        self.recursion_search_depth = settings.gtfs.recursion_search_depth
        self.max_transfers = 5
        # blacklist pair of (orig, dest) if no route is found, avoid to spam the GTFS server
        self.blacklist = set()
        # cache statistics
        self.cache_enabled = settings.gtfs.cache_enabled
        self._stats_cache_hit = (0, 0)
        self._stats_new_cache = 0
        self._dump_cache_after = 10000
        self._cache_last_hour = None
        self._cache_duration = 900 # 15 minutes cache duration
        self._notfound_cache_last_hour = None
        self._notfound_cache_duration = 1800  # 30 minutes cache duration for not found itineraries

        if not self.cache_enabled:
            logger.warning("[CachedTripHelper]: Cache is disabled, all requests will go to the trip_helper directly.")

        # choose the strategy based on settings
        if settings.gtfs.recursion_search_depth > 0:
            logger.warning(f"[CachedTripHelper]: Using recursive search strategy with depth {settings.gtfs.recursion_search_depth}")
            self.do_get_iteraries = self.do_get_iteraries_v1
        else:
            logger.warning(f"[CachedTripHelper]: Using time-range expanded based search strategy")
            self.do_get_iteraries = self.do_get_iteraries_v2

    def dump_cache_to_file(self):
        pass

    def get_unique_itineraries(self, itineraries: list[TravelPlan]) -> list[TravelPlan]:
        """
        Get unique itineraries by comparing the start and end locations, and the legs of the itinerary.
        """
        unique_itineraries = {}
        for it in itineraries:
            transits = [leg for leg in it.legs if not leg.is_transfer]
            key = (tuple((leg.transit_route, leg.start_location.stop, leg.end_location.stop) for leg in transits))
            if key not in unique_itineraries:
                unique_itineraries[key] = it
        return list(unique_itineraries.values())
    
    def is_circular_route(self, itinerary: TravelPlan) -> bool:
        """
        Check if the itinerary is circular, meaning the start and end locations are the same.
        """
        all_transits = [leg for leg in itinerary.legs if not leg.is_transfer]
        keys = [
            (leg.start_location.stop, leg.end_location.stop, leg.transit_route)
            for leg in all_transits
        ]
        return len(set(keys)) < len(keys)  # if there are duplicates, it's circular
    
    async def do_get_iteraries_v2(self, origin: Location, destination: Location, departure_time: int, include_car: bool = False, arrive_by: bool = False, _pipeline_rec=None) -> list[TravelPlan]:
        import time as _time
        max_transfers = self.max_transfers
        time_step = settings.world.time_step
        departure_time = departure_time // time_step * time_step  # round down to the nearest time step

        access_egress_modes = settings.gtfs.transit_access_egress_modes
        otp_sinks = [{} for _ in access_egress_modes] if _pipeline_rec is not None else [None] * len(access_egress_modes)
        direct_sink: dict | None = {} if _pipeline_rec is not None else None

        tasks = []
        # One OTP call per access/egress mode; all queries use the same departure_time T.
        # arrive_by is forwarded so OTP searches backwards from the target arrival time.
        for idx, mode in enumerate(access_egress_modes):
            tasks.append(
                self.trip_helper.get_itineraries(
                    origin=origin,
                    destination=destination,
                    departure_time=departure_time,
                    include_car=include_car,
                    max_transfers=max_transfers,
                    include_direct=False,
                    arrive_by=arrive_by,
                    access_egress_mode=mode,
                    _timing_sink=otp_sinks[idx],
                )
            )
        # Direct routes once only: foot/bicycle are time-independent, car congestion
        # barely differs across ±15 min so one query at T is sufficient.
        # Direct routes are always computed departure-based; when arrive_by=True the
        # caller is responsible for shifting their times after the fact.
        tasks.append(
            self.trip_helper.get_itineraries(
                origin=origin,
                destination=destination,
                departure_time=departure_time,
                include_car=include_car,
                max_transfers=max_transfers,
                include_transit=False,
                arrive_by=False,
                _timing_sink=direct_sink,
            )
        )
        results = await asyncio.gather(*tasks)

        # Map OTP sink results to pipeline record (positional: mode index 0/1/2 → P3A-2/4/6, P3A-3/5/7)
        if _pipeline_rec is not None:
            _otp_fields = [
                ("P3A_2_ms", "P3A_3_ms"),
                ("P3A_4_ms", "P3A_5_ms"),
                ("P3A_6_ms", "P3A_7_ms"),
            ]
            for idx, sink in enumerate(otp_sinks):
                if sink and idx < len(_otp_fields):
                    sem_f, req_f = _otp_fields[idx]
                    setattr(_pipeline_rec, sem_f, sink.get("sem_ms"))
                    setattr(_pipeline_rec, req_f, sink.get("req_ms"))
            if direct_sink:
                _pipeline_rec.P3B_2_ms = direct_sink.get("osmnx_ms")

        # When arrive_by=True, shift direct plans (last task result) so their end_time
        # equals the target arrival time instead of departure_time + duration.
        if arrive_by and results:
            direct_plans = results[-1]
            target_ms = departure_time * 1000
            for plan in direct_plans:
                duration_ms = plan.end_time - plan.start_time
                plan.end_time = target_ms
                plan.start_time = target_ms - duration_ms
                for leg in plan.legs:
                    leg.end_time = leg.end_time - duration_ms
                    leg.start_time = leg.start_time - duration_ms

        # Deduplication across all results
        _t_dedup = _time.monotonic()
        bl = set()
        rs = []
        for plan in [plan for plans in results for plan in plans]:
            code = plan.get_code()
            if code in bl:
                continue
            bl.add(code)
            rs.append(plan)
        if _pipeline_rec is not None:
            _pipeline_rec.P3B_3_ms = (_time.monotonic() - _t_dedup) * 1000

        itineraries = rs
        return itineraries

    async def do_get_iteraries_v1(self,
                               origin: Location,
                               destination: Location,
                               departure_time: int,
                               include_car: bool = False,
                               arrive_by: bool = False,
                               _pipeline_rec=None) -> list[TravelPlan]:
        max_transfers = self.max_transfers
        recursion_search_depth = self.recursion_search_depth
        itineraries: list[TravelPlan] = await self.trip_helper.get_itineraries(origin, destination, departure_time, include_car=include_car, max_transfers=max_transfers, arrive_by=arrive_by)
        if not itineraries:
            return []
        
        _stats_number_of_calls = 1
        
        first_index = -1
        while recursion_search_depth > 0 and max_transfers > 2:
            # Itinerary includes transfers and transits. For example if the itinerary has 3 transits, for each depth
            # we will try to keep the previous transits and find new ways from this transit to the destination, then 
            # combine them together.
            new_itineraries = []
            max_transfers -= 1
            recursion_search_depth -= 1
            first_index += 1

            tasks = []
            for it in itineraries:
                # find the first transit in the itinerary
                all_transits = [leg for leg in it.legs if not leg.is_transfer]
                if len(all_transits) <= first_index:
                    continue
                first_transit = all_transits[first_index]

                # find the index of the first transit
                first_transit_index = it.legs.index(first_transit)
                # prepare the coroutine for concurrent execution
                tasks.append((
                    it,
                    first_transit_index,
                    self.trip_helper.get_itineraries(
                        origin=first_transit.end_location,
                        destination=destination,
                        departure_time=first_transit.end_time // 1000,  # convert to seconds
                        max_transfers=max_transfers
                    )
                ))

            # Run all get_itineraries concurrently
            results = await asyncio.gather(*(task[2] for task in tasks))
            _stats_number_of_calls += len(results)

            for (it, first_transit_index, _), new_ways in zip(tasks, results):
                if not new_ways:
                    continue
                for new_way in new_ways:
                    # combine the first part of the itinerary with the new way
                    combined_itinerary = TravelPlan(
                        id=random_uuid(),
                        start_location=it.start_location,
                        end_location=new_way.end_location,
                        start_time=it.start_time,
                        end_time=new_way.end_time,
                        legs=it.legs[:first_transit_index] + new_way.legs
                    )
                    if not self.is_circular_route(combined_itinerary):
                        new_itineraries.append(combined_itinerary)
                
            # merge all itineraries
            itineraries = self.get_unique_itineraries(new_itineraries + itineraries)

        return itineraries

    async def get_itineraries(self,
                              origin: Location,
                              destination: Location,
                              departure_time: int,
                              include_car: bool = False,
                              arrive_by: bool = False,
                              _pipeline_rec=None,
                              ) -> list[TravelPlan]:
        import time as _time
        _t_cache = _time.monotonic()

        grid_origin = self.world_grid.get_location_grid(origin)
        grid_destination = self.world_grid.get_location_grid(destination)
        time_slot = self.time_grid.get_time_slot(departure_time)

        # Only save cache for the current hour, because the GTFS data is updated hourly
        day_and_hour = departure_time // self._cache_duration # e.g. 15 minutes cache duration
        if self._cache_last_hour is None or self._cache_last_hour != day_and_hour:
            self.cache.clear()
            # logger.debug(f"[CachedTripHelper]: Cache cleared for new hour {day_and_hour}")
        self._cache_last_hour = day_and_hour

        day_and_hour = departure_time // self._notfound_cache_duration  # e.g. 30 minutes cache duration for not found itineraries
        if self._notfound_cache_last_hour is None or self._notfound_cache_last_hour != day_and_hour:
            self.blacklist.clear()
            # logger.debug(f"[CachedTripHelper]: Blacklist cleared for new hour {day_and_hour}")
        self._notfound_cache_last_hour = day_and_hour

        # include_car and arrive_by are part of the key: they produce different itineraries
        key = "_".join([str(it) for it in (*grid_origin, *grid_destination, time_slot, day_and_hour, int(include_car), int(arrive_by))])
        bl_key = (origin.lon, origin.lat, destination.lon, destination.lat)

        cache_hit = self.cache_enabled
        cache_hit = cache_hit and (key not in self.cache or len(self.cache[key]) < self.cache_size_per_grid)
        cache_hit = cache_hit and (bl_key not in self.blacklist)

        if _pipeline_rec is not None:
            _pipeline_rec.P3_1_ms = (_time.monotonic() - _t_cache) * 1000
            _pipeline_rec.P3_cache_hit = cache_hit

        if not cache_hit:
            itineraries = await self.do_get_iteraries(origin, destination, departure_time, include_car=include_car, arrive_by=arrive_by, _pipeline_rec=_pipeline_rec)
            if itineraries:
                # identify each itinerary with a unique id
                for it in itineraries:
                    it.id = random_uuid()
                self.cache[key].append({
                    'id': random_uuid(),
                    'origin': origin,
                    'destination': destination,
                    'departure_time': departure_time,
                    'itineraries': itineraries,
                })
                self.cache[key] = self.cache[key][:self.cache_size_per_grid]
                self._stats_cache_hit = (self._stats_cache_hit[0], self._stats_cache_hit[1] + 1)
                self._stats_new_cache += 1
            else:
                self.blacklist.add(bl_key)
        else:
            self._stats_cache_hit = (self._stats_cache_hit[0] + 1, self._stats_cache_hit[1] + 1)
            # logger.debug(f"[CachedTripHelper]: Cache hit for key {key}, ratio: {self._stats_cache_hit[0] / self._stats_cache_hit[1]:.2f}")
        _hits, _total = self._stats_cache_hit
        if _total > 0:
            TRIP_CACHE_HIT_RATIO.set(_hits / _total)

        # Dump cache if needed
        if self._stats_new_cache >= self._dump_cache_after:
            self._stats_new_cache = 0
            self.dump_cache_to_file()

        # Find the closest itinerary to the origin and destination
        candidates = self.cache.get(key, [])
        if not candidates:
            return []
        candidates = sorted(candidates, key=lambda x: (square_distance(x['origin'], origin), square_distance(x['destination'], destination)))
        itineraries = candidates[0]['itineraries']

        # Modify the start and end location of the itinerary
        for itinerary in itineraries:
            itinerary.start_location = origin
            itinerary.end_location = destination
            # patch the all time values
            departure_time_ms = departure_time * 1000
            dt = departure_time_ms - itinerary.start_time
            itinerary.start_time = departure_time_ms
            itinerary.end_time = itinerary.end_time + dt
            for leg in itinerary.legs:
                leg.start_time = leg.start_time + dt
                leg.end_time = leg.end_time + dt

        return itineraries
