#!/usr/bin/env python3
"""Contrôles de la source météo pour le bulletin enrichi — ticket 023, lot 4.

Chiffre les trois pièges de `data/weather/meteo_toulouse_12_mois.csv` avant d'écrire
la moindre ligne de bulletin. **Aucun appel LLM.** Écrit `controles_source.json`.

    prompt_calibration/.venv/bin/python \\
        docs/traces/2026-08-25_premesure_meteo_v9/controles_source_bulletin.py
"""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WEATHER = ROOT / "data" / "weather" / "meteo_toulouse_12_mois.csv"
CODES = ROOT / "data" / "weather" / "meteo_toulouse_codes.csv"

TEMP = {"night": "TEMPERATURE_NIGHT_C_3H", "morning": "TEMPERATURE_MORNING_C_6H",
        "noon": "TEMPERATURE_NOON_C_12H", "evening": "TEMPERATURE_EVENING_C_18H"}
CODE = {"night": "WEATHER_CODE_NIGHT_3H", "morning": "WEATHER_CODE_MORNING_6H",
        "noon": "WEATHER_CODE_NOON_12H", "evening": "WEATHER_CODE_EVENING_18H"}
BUCKETS = ("night", "morning", "noon", "evening")

# La neige l'emporte sur la pluie : « Légères averses de neige » contient « averse »
# mais n'est pas de la pluie. L'ordre des deux tests porte donc du sens.
SNOW = re.compile(r"neige|grésil|blizzard", re.I)
RAIN = re.compile(r"pluie|bruine|averse|orage", re.I)


def famille(label: str) -> str | None:
    if SNOW.search(label):
        return "neige"
    if RAIN.search(label):
        return "pluie"
    return None


def main() -> int:
    labels = {}
    for r in csv.DictReader(CODES.open(encoding="utf-8")):
        try:
            labels[int(r["CodeMétéo"])] = r["Condition"].strip()
        except ValueError:
            continue
    days = list(csv.DictReader(WEATHER.open(encoding="utf-8")))

    mm_orphelins, creneaux_secs, jours_neige = [], [], []
    hors_bornes, ecart_max = 0, 0
    for row in days:
        tmin = int(float(row["MIN_TEMPERATURE_C"]))
        tmax = int(float(row["MAX_TEMPERATURE_C"]))
        precip = float(row["PRECIP_TOTAL_DAY_MM"])
        familles = {famille(labels.get(int(float(row[CODE[b]])), "")) for b in BUCKETS} - {None}
        for b in BUCKETS:
            t = int(float(row[TEMP[b]]))
            if t < tmin or t > tmax:
                hors_bornes += 1
                ecart_max = max(ecart_max, tmin - t, t - tmax)
        if precip > 0 and not familles:
            mm_orphelins.append((row["DATE"], precip))
        if precip == 0 and familles:
            creneaux_secs.append(row["DATE"])
        if "neige" in familles:
            jours_neige.append(row["DATE"])

    cumuls = sorted(p for _, p in mm_orphelins)
    res = {
        "date": "2026-08-25", "ticket": "023", "appels_llm": 0,
        "source": str(WEATHER.relative_to(ROOT)), "n_jours": len(days),
        "mm_sans_creneau_precipitant": {
            "n_jours": len(mm_orphelins),
            "cumul_min_mm": cumuls[0], "cumul_median_mm": cumuls[len(cumuls) // 2],
            "cumul_max_mm": cumuls[-1],
            "n_jours_au_moins_1mm": sum(1 for v in cumuls if v >= 1.0),
            "consequence": "repli obligatoire sur la formulation actuelle : la forme "
                           "enrichie ajoute, n'enlève jamais"},
        "creneaux_hors_bornes_min_max": {
            "n_creneaux": hors_bornes, "sur_total": len(days) * len(BUCKETS),
            "ecart_max_c": ecart_max,
            "consequence": "bornes du jour élargies aux créneaux lus ; source inchangée"},
        "creneau_precipitant_sans_cumul": {"n_jours": len(creneaux_secs)},
        "jours_avec_neige": {"n_jours": len(jours_neige), "dates": jours_neige},
        "colonnes_absentes": ["probabilité de précipitation — aucun « risque de pluie » "
                              "chiffré n'est dérivable de cette source"],
    }
    (Path(__file__).parent / "controles_source.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(days)} jours analysés — controles_source.json écrit")
    print(f"  mm sans créneau précipitant : {len(mm_orphelins)} jours "
          f"(médiane {cumuls[len(cumuls)//2]} mm, max {cumuls[-1]} mm, "
          f"{res['mm_sans_creneau_precipitant']['n_jours_au_moins_1mm']} ≥ 1 mm)")
    print(f"  créneaux hors [MIN, MAX]    : {hors_bornes}/{len(days)*4}, "
          f"écart max {ecart_max} °C")
    print(f"  créneau pluvieux à 0 mm     : {len(creneaux_secs)} jours")
    print(f"  jours avec neige            : {len(jours_neige)} → {jours_neige}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
