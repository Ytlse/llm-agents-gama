from jinja2 import Environment, FileSystemLoader
from loguru import logger
from helper import duration_to_bucket_text, humanize_time, humanize_duration, ensure_timestamp_in_seconds, time_to_bucket_text
from inputs.gtfs import GTFSData
from settings import settings
import os

env = Environment(loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), 'tpl')))

def to_timestamp(t: int) -> int:
    return ensure_timestamp_in_seconds(t)

gtfs_data = GTFSData.DEFAULT()
# Ticket 077, lot B2.4 — une ligne introuvable au GTFS se SIGNALE, elle ne se maquille pas.
# `get_route_type_string_by_id` et `get_route_short_name_by_id` rendent tous deux la chaîne
# « Unknown » quand l'identifiant est absent du référentiel, d'où les « Trip by Unknown
# Unknown » du run du ticket 075. Le mot reste dans le référentiel — c'est sa valeur de repli —
# mais il ne doit plus atteindre le modèle : une phrase qui nomme une ligne inexistante est
# une phrase fausse, et elle sera consolidée en concept.
_ROUTE_INCONNUE = "Unknown"
# Comptées et journalisées UNE SEULE FOIS par identifiant : au-delà, un run de mille agents
# noierait son journal sous la même ligne.
ROUTES_INCONNUES: dict[str, int] = {}


def _signaler_route_inconnue(route_id: str) -> None:
    clef = str(route_id or "")
    ROUTES_INCONNUES[clef] = ROUTES_INCONNUES.get(clef, 0) + 1
    if ROUTES_INCONNUES[clef] == 1:
        logger.warning(
            f"[gtfs] ligne « {clef} » introuvable dans le référentiel — l'observation sera "
            f"rendue sans nom de ligne plutôt qu'avec « {_ROUTE_INCONNUE} »"
        )


def route_est_connue(route_id: str) -> bool:
    """La ligne est-elle dans le référentiel ? Interrogé par le gabarit avant de la nommer."""
    connue = (
        gtfs_data.get_route_type_string_by_id(route_id) != _ROUTE_INCONNUE
        or gtfs_data.get_route_short_name_by_id(route_id) != _ROUTE_INCONNUE
    )
    if not connue:
        _signaler_route_inconnue(route_id)
    return connue


def get_transit_route_type(route_id: str) -> str:
    return gtfs_data.get_route_type_string_by_id(route_id)

def get_transit_route_name(route_id: str) -> str:
    return gtfs_data.get_route_long_name_by_id(route_id)

def get_transit_route_short_name(route_id: str) -> str:
    return gtfs_data.get_route_short_name_by_id(route_id)

env.filters['humanize_time'] = humanize_time
env.filters['humanize_duration'] = humanize_duration
env.filters['to_timestamp'] = to_timestamp
env.filters['get_transit_route_type'] = get_transit_route_type
env.filters['route_est_connue'] = route_est_connue
env.filters['get_transit_route_long_name'] = get_transit_route_name
# env.filters['format_route_id'] = format_route_id
env.filters['format_route_id'] = get_transit_route_short_name
env.filters['duration_to_bucket_text'] = duration_to_bucket_text if settings.agent.quantify_time_window else humanize_duration
env.filters['time_to_bucket_text'] = time_to_bucket_text
def humanize_distance(distance):
    if not distance:
        return "Unknown distance"
    if distance >= 1000:
        return f"{distance / 1000:.1f} km"
    return f"{round(distance)} m"

env.filters['humanize_distance'] = humanize_distance


tpl_describe_the_travel_plan = env.get_template('descriptions/travel_plan_describe_v2.j2')
tpl_describe_the_travel_plan_lite = env.get_template('descriptions/travel_plan_describe_lite.j2')
tpl_describe_the_ob_transit = env.get_template('descriptions/ob_transit.j2')
tpl_describe_the_ob_transfer = env.get_template('descriptions/ob_transfer.j2')
tpl_describe_the_ob_vehicle = env.get_template('descriptions/ob_vehicle.j2')
tpl_describe_the_ob_trip_feedback = env.get_template('descriptions/ob_trip_feedback.j2')
tpl_describe_the_ob_wait_in_stop = env.get_template('descriptions/ob_wait_in_stop.j2')
