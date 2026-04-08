from typing import List, Optional, TypeAlias
from enum import Enum
from pydantic import BaseModel

""" Base models
"""
class LocationType(str, Enum):
    HOME = "home"
    WORK = "work"
    EDUCATION = "education"
    OTHER = "other"


class Location(BaseModel):
    lon: float
    lat: float


class BBox(BaseModel):
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


""" Schedule
"""
ActivityPurpose: TypeAlias = str

class Activity(BaseModel):
    """Activity represents a scheduled task or stay in a person’s daily plan.

    Attributes:
        id: unique activity identifier.
        scheduled_start_time: optional planned start time (across the day).
        start_time: actual or current start time.
        end_time: end time for the activity.
        purpose: type of activity (work, education, leisure, etc.).
        location: optional coordinates of where the activity occurs.
    """

    id: str
    # scheduled start time over the day
    scheduled_start_time: Optional[float] = None
    start_time: float
    end_time: float
    purpose: ActivityPurpose
    location: Optional[Location] = None
    # TODO: how to populate this from location?
    # location_name: Optional[str] = None


""" Travel plan
"""
RouteShape: TypeAlias = str

class TransitLocation(Location):
    """TransitLocation extends Location with a transit stop identifier.

    Attributes:
        stop: stop ID or name.
        lat: latitude (redeclared for transit-specific semantics).
        lon: longitude (redeclared for transit-specific semantics).
    """

    stop: str
    lat: float
    lon: float

class Transit(BaseModel):
    """Transit describes one portion of a trip plan, including transfers.

    Attributes:
        start_time: departure timestamp.
        end_time: arrival timestamp.
        start_location: transit stop/location at start.
        end_location: transit stop/location at end.
        is_transfer: whether this segment is a transfer/wait segment.
        transit_route: optional route ID or name.
        shape_id: optional geometry IDs describing the path.
        transit_agency: optional operator/agency name.
        duration: optional duration (seconds) of the segment.
        distance: optional distance (meters/kilometers) of the segment.
        mode: optional travel mode (walk, bus, subway, etc.).
    """

    start_time: int
    end_time: int
    start_location: TransitLocation
    end_location: TransitLocation
    # route_shape: Optional[RouteShape] = None
    is_transfer: bool = False
    transit_route: Optional[str] = None
    shape_id: Optional[List[str]] = None
    transit_agency: Optional[str] = None
    duration: Optional[int] = None
    distance: Optional[float] = None
    mode: Optional[str] = None

    def get_duration(self) -> int:
        return self.duration or int((self.end_time - self.start_time) // 1000)
    
    def get_distance(self) -> float:
        return self.distance or 100.0

    def get_code(self) -> str:
        return "^".join([self.transit_route, self.start_location.stop, self.end_location.stop])
    
class TravelPlan(BaseModel):
    """TravelPlan represents a complete transportation itinerary for a person.

    Attributes:
        id: unique identifier for the travel plan (UUID, hash, or business code).
        start_location: departure point of the journey (latitude/longitude).
        end_location: destination point of the journey (latitude/longitude).
        start_time: timestamp when the journey starts (usually milliseconds since epoch).
        end_time: timestamp when the journey ends (arrival time).
        start_in: optional countdown before start (seconds from now).
        purpose: optional reason for trip such as work, education or shopping.
        duration: optional total estimated duration of trip (often end_time - start_time).
        distance: optional total estimated distance of trip (meters/kilometers depending on context).
        legs: list of Transit segments composing the trip, including transfers.

    A Transit segment (in legs) contains start/end point/time, route info,
    and optional mode, agency, duration, distance, etc.
    """

    # identifiant unique du plan de déplacement (UUID, hash, code logique)
    id: str

    # point de départ du trajet (latitude/longitude)
    start_location: Location

    # destination du trajet (latitude/longitude)
    end_location: Location

    # timestamp de début du trajet (généralement en ms, cohérent avec Transit)
    start_time: int

    # timestamp d’arrivée/fin du trajet
    end_time: int

    # délai avant le démarrage du plan, en secondes depuis maintenant
    start_in: Optional[int] = 0  # seconds from now

    # objectif / finalité du déplacement (work, education, shopping, etc.)
    purpose: Optional[str] = None

    # durée totale souhaitée ou calculée du trajet (possiblement end_time-start_time)
    duration: Optional[int] = None

    # distance totale estimée du trajet (métrique, km, unité à préciser selon usage)
    distance: Optional[float] = None

    # séquence de segments Transit (mode, durée, itinéraire, transferts)
    legs: List[Transit]

    def get_code(self) -> str:
        """
        Generate a code for the travel plan based on its attributes.
        This can be used to identify the plan in logs or messages.
        """
        return "+".join([
            leg.get_code() for leg in self.legs if not leg.is_transfer
        ])


""" Agent & Simulation
"""
class PersonMove(BaseModel):
    """PersonMove represents an in-progress or planned move for an agent.

    Attributes:
        id: unique identifier used for tracking and updating this move.
        person_id: associated person’s ID.
        current_time: current simulation timestamp.
        expected_arrive_at: expected arrival time at target.
        prepare_before_seconds: optional prep time before departure.
        purpose: optional reason for move.
        target_location: optional location to reach.
        for_activity: optional Activity associated with this move.
        plan: optional TravelPlan containing route legs and timing.
    """

    # the id for quickly identifying and updating the move
    id: str
    person_id: str
    current_time: int
    expected_arrive_at: int
    prepare_before_seconds: Optional[int] = 0
    purpose: Optional[str] = None
    target_location: Optional[Location] = None
    for_activity: Optional[Activity] = None
    plan: Optional[TravelPlan] = None


""" Personal Identity
"""
PersonId: TypeAlias = str

class PersonalIdentity(BaseModel):
    name: str
    traits_json: dict
    home: Optional[Location] = None
    activities: Optional[List[Activity]] = None


class PersonState(BaseModel):
    last_location: Optional[Location] = None
    last_activity_index: Optional[int] = 0
    cache_current_activity: Optional[Activity] = None  # current activity
    heading_to: Optional[str] = None  # purpose of the next activity


class Person(BaseModel):
    person_id: PersonId
    identity: PersonalIdentity
    state: PersonState = PersonState()
    # hybrid technique
    is_llm_based: bool = False
