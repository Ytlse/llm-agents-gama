import csv
import os
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

_base_dir = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.normpath(os.path.join(_base_dir, "../../../"))
_WEATHER_CSV = os.path.join(_REPO_ROOT, "data", "weather", "meteo_toulouse_12_mois.csv")
_CODES_CSV = os.path.join(_REPO_ROOT, "data", "weather", "meteo_toulouse_codes.csv")

_TZ = ZoneInfo("Europe/Paris")

# (month, day) → row dict from the CSV
_weather_index: dict[tuple[int, int], dict] = {}
# code int → French label
_code_labels: dict[int, str] = {}
_loaded = False
_load_error: Optional[str] = None


def _load():
    global _loaded, _load_error
    if _loaded or _load_error:
        return

    try:
        with open(_CODES_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                code = int(row["CodeMétéo"])
                _code_labels[code] = row["Condition"].strip()

        with open(_WEATHER_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                date = datetime.strptime(row["DATE"], "%Y-%m-%d")
                _weather_index[(date.month, date.day)] = row

        _loaded = True
    except FileNotFoundError as e:
        _load_error = str(e)
        import logging
        logging.getLogger(__name__).warning(f"[weather_loader] Fichiers météo introuvables, get_weather() retournera None. ({e})")


def _time_bucket(hour: int) -> str:
    if hour < 6:
        return "night"
    if hour < 12:
        return "morning"
    if hour < 18:
        return "noon"
    return "evening"


_TEMP_COLS = {
    "night": "TEMPERATURE_NIGHT_C_3H",
    "morning": "TEMPERATURE_MORNING_C_6H",
    "noon": "TEMPERATURE_NOON_C_12H",
    "evening": "TEMPERATURE_EVENING_C_18H",
}
_CODE_COLS = {
    "night": "WEATHER_CODE_NIGHT_3H",
    "morning": "WEATHER_CODE_MORNING_6H",
    "noon": "WEATHER_CODE_NOON_12H",
    "evening": "WEATHER_CODE_EVENING_18H",
}


def get_weather(timestamp: int) -> Optional[dict]:
    """Return weather info for the given Unix timestamp (matched by month+day, ignoring year).

    Returns a dict with keys: temperature, weather_code, weather_label, precip_mm.
    Returns None if data is missing.
    """
    _load()
    if _load_error:
        return None
    dt = datetime.fromtimestamp(timestamp, tz=_TZ)
    row = _weather_index.get((dt.month, dt.day))
    if row is None:
        return None

    bucket = _time_bucket(dt.hour)
    try:
        temp = float(row[_TEMP_COLS[bucket]])
        code = int(float(row[_CODE_COLS[bucket]]))
        precip = float(row["PRECIP_TOTAL_DAY_MM"])
    except (ValueError, KeyError):
        return None

    label = _code_labels.get(code, str(code))
    return {
        "temperature": temp,
        "weather_code": code,
        "weather_label": label,
        "precip_mm": precip,
    }


# Ordre chronologique des tranches météo intra-journée et libellés français
# pour la ligne « Météo du jour » (ticket 014 — anticipation).
_BUCKET_ORDER = ("night", "morning", "noon", "evening")
_BUCKET_FR = {"night": "nuit", "morning": "matin", "noon": "après-midi", "evening": "soirée"}


def day_weather_outlook(timestamp: int) -> Optional[str]:
    """Météo des tranches RESTANTES de la journée (après celle du timestamp).

    Ticket 014 : au moment de choisir un mode, l'agent doit voir la météo à venir
    (sortir le vélo le matin alors qu'il pleuvra le soir). Retourne par ex.
    « après-midi 12°C, Ciel dégagé · soirée 13°C, Pluie » — ou None quand il ne
    reste aucune tranche (départ en soirée) ou que les données manquent.
    Déterministe (fonction du jour et de l'heure) : la chaîne participe à la clé
    du cache de décisions via la signature d'anticipation.
    """
    _load()
    if _load_error:
        return None
    dt = datetime.fromtimestamp(timestamp, tz=_TZ)
    row = _weather_index.get((dt.month, dt.day))
    if row is None:
        return None

    current = _time_bucket(dt.hour)
    remaining = _BUCKET_ORDER[_BUCKET_ORDER.index(current) + 1:]
    parts = []
    for bucket in remaining:
        try:
            temp = int(float(row[_TEMP_COLS[bucket]]))
            code = int(float(row[_CODE_COLS[bucket]]))
        except (ValueError, KeyError):
            continue
        label = _code_labels.get(code, str(code))
        parts.append(f"{_BUCKET_FR[bucket]} {temp}°C, {label}")
    return " · ".join(parts) if parts else None


def weather_to_natural_language(w: Optional[dict]) -> Optional[str]:
    """Format weather dict as a French natural-language sentence for the LLM prompt."""
    if w is None:
        return None
    temp = int(w["temperature"])
    label = w["weather_label"]
    precip = w["precip_mm"]
    precip_str = f"{precip:.1f}".replace(".", ",")
    if precip > 0:
        return f"Météo : {temp}°C, {label}. Précipitations prévues dans la journée : {precip_str} mm."
    return f"Météo : {temp}°C, {label}. Pas de précipitations prévues."
