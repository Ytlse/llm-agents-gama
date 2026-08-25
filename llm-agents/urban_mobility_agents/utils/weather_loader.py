"""Météo du prompt — bulletin du jour au créneau de départ (ticket 023, lot 4).

La ligne météo ne portait que la température du créneau, la condition, et un cumul de
précipitations. Elle ne disait ni **quand** il pleut dans la journée, ni **quelle
amplitude** thermique attend l'agent, ni **s'il fera nuit** au retour — trois choses qu'un
humain consulte avant de sortir un vélo. Le bulletin enrichi les ajoute.

⚠ **Il n'y a pas de « risque de pluie » chiffré, et il ne peut pas y en avoir.** La source
ne porte aucune colonne de probabilité de précipitation ; un pourcentage serait fabriqué.
Ce qui est annonçable est factuel : les créneaux dont le **code météo** est précipitant.

⚠ **La forme enrichie AJOUTE, elle n'enlève jamais.** 25 jours sur 365 portent des
millimètres sans qu'aucun créneau ne soit codé précipitant ; ils gardent la formulation
d'origine plutôt que d'annoncer « pas de précipitations » sur un jour qui en porte. Mesuré
dans `docs/traces/2026-08-25_premesure_meteo_v9/`.
"""

import csv
import os
import re
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
        **day_frame(row),
    }


# ── Le cadre du jour : amplitude, soleil, créneaux précipitants ───────────────

# La neige l'emporte sur la pluie : « Légères averses de neige » contient « averse »
# mais n'est pas de la pluie. L'ordre des deux tests porte donc du sens.
_SNOW_RE = re.compile(r"neige|grésil|blizzard", re.I)
_RAIN_RE = re.compile(r"pluie|bruine|averse|orage", re.I)

# Complément circonstanciel, et non le libellé nu de `_BUCKET_FR` : on écrit « Pluie
# prévue le matin », pas « Pluie prévue matin ».
_BUCKET_WHEN = {"night": "la nuit", "morning": "le matin",
                "noon": "l'après-midi", "evening": "en soirée"}


def _precip_family(label: str) -> Optional[str]:
    """Famille de précipitation d'un libellé de condition, `None` si sec."""
    if _SNOW_RE.search(label):
        return "neige"
    if _RAIN_RE.search(label):
        return "pluie"
    return None


def _hhmm(value: Optional[str]) -> Optional[str]:
    """`"20:57:00"` → `"20:57"`. `None` si la source ne porte pas l'heure."""
    text = (value or "").strip()
    return text[:5] if len(text) >= 5 else None


def day_frame(row: dict) -> dict:
    """Cadre de la journée : amplitude thermique, soleil, créneaux précipitants.

    ⚠ **Les bornes sont élargies aux créneaux effectivement lus.** 30 créneaux sur 1 460
    sortent de `[MIN_TEMPERATURE_C, MAX_TEMPERATURE_C]` dans la source, jusqu'à 3 °C, tous
    de nuit. Sans cet élargissement, le prompt se contredirait lui-même : « Météo : 11°C …
    Aujourd'hui 13°C à 20°C ». La source n'est pas modifiée — seule la phrase est rendue
    cohérente avec ce qu'elle annonce par ailleurs.
    """
    try:
        slots = [int(float(row[_TEMP_COLS[b]])) for b in _BUCKET_ORDER]
        temp_min = min(int(float(row["MIN_TEMPERATURE_C"])), *slots)
        temp_max = max(int(float(row["MAX_TEMPERATURE_C"])), *slots)
    except (ValueError, KeyError, TypeError):
        temp_min = temp_max = None

    precip_slots = []
    for bucket in _BUCKET_ORDER:
        try:
            code = int(float(row[_CODE_COLS[bucket]]))
        except (ValueError, KeyError, TypeError):
            continue
        family = _precip_family(_code_labels.get(code, ""))
        if family:
            precip_slots.append((bucket, family))

    return {
        "temp_min": temp_min,
        "temp_max": temp_max,
        "sunrise": _hhmm(row.get("SUNRISE")),
        "sunset": _hhmm(row.get("SUNSET")),
        "precip_slots": precip_slots,
    }


def _enumerate_fr(items: list[str]) -> str:
    """`["le matin", "l'après-midi", "en soirée"]` → `"le matin, l'après-midi et en soirée"`."""
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} et {items[-1]}"


def _precipitation_phrase(w: dict) -> str:
    """Phrase de précipitation — créneaux si on les connaît, cumul sinon.

    Trois cas, dans cet ordre, et le second est celui qui compte :

    1. des créneaux sont codés précipitants → on dit **quand**, avec le cumul entre
       parenthèses quand il est non nul ;
    2. aucun créneau précipitant **mais** un cumul non nul → on garde **mot pour mot** la
       formulation d'origine. 25 jours sur 365 sont dans ce cas, jusqu'à 2,5 mm. Annoncer
       « pas de précipitations » y serait une régression d'information ;
    3. rien du tout → « Pas de précipitations prévues. »
    """
    precip = w.get("precip_mm") or 0.0
    precip_str = f"{precip:.1f}".replace(".", ",")
    slots = w.get("precip_slots") or []

    if slots:
        by_family: dict[str, list[str]] = {}
        for bucket, family in slots:
            by_family.setdefault(family, []).append(_BUCKET_WHEN[bucket])
        parts = [f"{family.capitalize()} prévue {_enumerate_fr(quand)}"
                 for family, quand in by_family.items()]
        phrase = " ; ".join(parts)
        return (f"{phrase} ({precip_str} mm sur la journée)." if precip > 0
                else f"{phrase}.")
    if precip > 0:
        return f"Précipitations prévues dans la journée : {precip_str} mm."
    return "Pas de précipitations prévues."


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
    """Bulletin du jour au créneau de départ, pour le prompt.

        Météo : 2°C, Partiellement nuageux. Aujourd'hui 2°C à 7°C, lever 07:55,
        coucher 17:25. Pluie prévue en soirée (0,2 mm sur la journée).

    Le cadre du jour couvre la **journée entière**, créneaux déjà passés compris : il
    répond à « quelle journée fait-il », question distincte de celle que traite la ligne
    « Météo plus tard », qui ne porte que les créneaux restants.

    Un dictionnaire sans les champs de cadre (`temp_min`, `sunrise`…) rend la phrase
    d'origine. Ce n'est pas une tolérance de confort : les jeux gelés antérieurs au
    ticket 023 portent des météos sans cadre, et ils doivent continuer à se relire tels
    quels — sinon leur ré-évaluation ne porterait plus sur ce qui a été mesuré.
    """
    if w is None:
        return None
    temp = int(w["temperature"])
    label = w["weather_label"]
    tail = _precipitation_phrase(w)

    frame = []
    if w.get("temp_min") is not None and w.get("temp_max") is not None:
        frame.append(f"Aujourd'hui {int(w['temp_min'])}°C à {int(w['temp_max'])}°C")
    if w.get("sunrise"):
        frame.append(f"lever {w['sunrise']}")
    if w.get("sunset"):
        frame.append(f"coucher {w['sunset']}")
    if not frame:
        return f"Météo : {temp}°C, {label}. {tail}"
    return f"Météo : {temp}°C, {label}. {', '.join(frame)}. {tail}"
