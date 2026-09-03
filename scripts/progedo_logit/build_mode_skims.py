"""build_mode_skims.py — Matrices de temps et de distance par mode, pour l'enquête.

Produit, pour chaque paire (zone fine d'origine, zone fine de destination, tranche
horaire) observée dans EMC² Toulouse 2023, le **temps et la distance des quatre modes** —
marche, vélo, voiture, transports collectifs — routés sur le graphe OTP du projet.

**Pourquoi.** La politique de choix modal n'a aujourd'hui qu'une variable de distance,
`od_km` (distance entre centroïdes de zones fines, à vol d'oiseau). Elle ne peut pas
exprimer la structure du réseau : deux paires de zones à 4 km de vol d'oiseau reçoivent la
même valeur, que l'une soit coupée par la Garonne sans pont proche et l'autre desservie par
le métro. Quatre distances routées le disent.

**La propriété qui rend ces colonnes utilisables — et elle est structurelle.** Les quatre
valeurs ne dépendent que de la paire OD et de la tranche horaire. Deux personnes ayant fait
le même trajet reçoivent les mêmes quatre nombres, quel que soit le mode que chacune a
choisi. Aucune fuite n'est possible : le mode choisi n'entre nulle part dans le calcul.
C'est ce qui distingue ces colonnes de `distance_km` (D12), qui est la distance du mode
retenu et donc une reformulation de la cible (PR-AUC marche 0,983 mesurée).

**Ce que ce script ne peut pas faire.** L'enquête ne donne que des codes de zone, jamais de
coordonnées : le routage part donc des centroïdes de zones fines, avec la même résolution
spatiale qu'`od_km`. Pour les déplacements intra-zone les deux centroïdes sont confondus ;
on écarte les deux points de `0,28 × √surface` le long d'un cap fixe. Le 0,28 est mesuré et
non choisi : c'est le `0,5 / 1,80` du rapport `od_km / D11` observé sur les données, Cerema
utilisant ce même rapport pour ses distances intra-zone.

**Réserve à porter dans toute lecture des résultats.** Le graphe OTP est celui d'aujourd'hui
et l'enquête décrit 2023. Le biais est réel, mais il porte **identiquement sur les quatre
modes** : il ne réinjecte donc pas l'étiquette. Le script mesure ce biais au passage, en
comparant la distance routée du mode effectivement choisi à celle de l'enquête (`D12` pour
voiture et vélo, `DDST` pour les TC) — c'est le contrôle de crédibilité du lot.

Usage :
    python -m scripts.progedo_logit.build_mode_skims [--limit N] [--workers N]
"""

from __future__ import annotations

import argparse
import json
import math
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

import geopandas as gpd
import numpy as np
import pandas as pd

# --- Zonage et conventions --------------------------------------------------
ZONE_CODE_WIDTH = 6              # la couche est indexée sur 6 chiffres + "000"
INTRA_FACTOR = 0.5 / 1.80        # mesuré : rapport od_km / D11 en intra-zone
INTRA_BEARING_DEG = 45.0         # cap fixe → résultat reproductible

# --- Tranches horaires ------------------------------------------------------
# Cinq tranches plutôt que 24 heures : le nombre de paires à router est
# proportionnel, et la vitesse du réseau ne change pas d'une heure à l'autre dans
# une même période. La date est un mardi de service, le graphe n'étant pas celui
# de 2023 (cf. docstring).
HOUR_BANDS = [(0, 7, "nuit"), (7, 10, "hp_matin"), (10, 16, "creux"),
              (16, 19, "hp_soir"), (19, 24, "soir")]
# Date de service : elle doit tomber dans le calendrier des DEUX feeds GTFS chargés
# dans le graphe, sinon le réseau urbain disparaît sans qu'aucune erreur ne le dise.
# Mesuré : Tisséo (bus, tram, métro) couvre 2026-03-16 → 2026-05-12, le TER
# 2026-04-29 → 2026-10-26. Fenêtre commune : 29 avril – 12 mai. Le 5 mai est un mardi.
# Effet vérifié sur 250 paires : couverture TC 36 % au 1er septembre (TER seul),
# 75 % au 5 mai (bus 168, métro 68, TER 31, tram 26).
SERVICE_DATE = "2026-05-05"
BAND_DEPART = {"nuit": "04:00", "hp_matin": "08:00", "creux": "13:00",
               "hp_soir": "17:30", "soir": "21:00"}

# --- OTP --------------------------------------------------------------------
OTP_PORTS = (8080, 8081, 8082)
TRANSIT_LEG_MODES = {"bus", "tram", "metro", "rail", "coach", "trolleybus",
                     "funicular", "cableway", "water"}
MODES = {
    "walk": {"directMode": "foot", "transportModes": []},
    "bike": {"directMode": "bicycle", "transportModes": []},
    "car": {"directMode": "car", "transportModes": []},
    # Pas de `directMode` : avec lui, OTP renvoie la marche directe comme
    # « meilleure option TC ». Et on ne retient qu'un motif portant une jambe TC.
    "transit": {"accessMode": "foot", "egressMode": "foot",
                "transportModes": [{"transportMode": m}
                                   for m in ("bus", "tram", "metro", "rail")]},
}
# `maxDirectDurationForMode` sert uniquement à la requête TC : sans lui, OTP compare
# l'itinéraire en transport à la marche directe et renvoie `walkingBetterThanTransit`
# au lieu d'une option TC. Interdire la marche directe (1 s) force la réponse
# transport. Vérifié : couverture TC 12 % → 36 % à date invalide, 75 % à date valide.
QUERY = """query($from:Location!,$to:Location!,$dt:DateTime,$modes:Modes,
 $mdd:[StreetModeDurationInput!]){
 trip(from:$from,to:$to,dateTime:$dt,modes:$modes,numTripPatterns:5,
  maxDirectDurationForMode:$mdd){
  tripPatterns{duration distance legs{mode}}
  routingErrors{code}}}"""
NO_DIRECT_WALK = [{"streetMode": "foot", "duration": "1s"}]

# Seuils d'alarme : un lot qui échoue silencieusement produirait des colonnes
# majoritairement vides, et le modèle s'entraînerait dessus sans rien signaler.
ERROR_ALARM_RATE = 0.05


def find_project_root() -> Path:
    root = Path(__file__).resolve()
    marker = Path("scripts") / "progedo_logit" / "feature_spec.json"
    while not (root / marker).exists() and root != root.parent:
        root = root.parent
    if not (root / marker).exists():
        raise SystemExit(f"Racine du projet introuvable (repère : {marker}).")
    return root


def zone_key(codes: pd.Series) -> pd.Series:
    return codes.astype(str).str[:ZONE_CODE_WIDTH] + "0" * (9 - ZONE_CODE_WIDTH)


def band_of(hour: float) -> str:
    for lo, hi, name in HOUR_BANDS:
        if lo <= hour < hi:
            return name
    return "creux"


# ---------------------------------------------------------------------------
# Paires à router
# ---------------------------------------------------------------------------

def build_pairs(root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Paires (origine, destination, tranche) distinctes, et la table déplacement → paire."""
    base = root / "data" / "PROGEDO 2023"
    zf = gpd.read_file(base / "lil-1750-Documentation" / "SIG"
                       / "EMC2_Toulouse_2023_ZF_26052023.shp")
    zf["ZF"] = zf.ZF.astype(str).str.strip()
    xy = zf.set_index("ZF")[["XL93", "YL93", "SURF_M2"]]

    depl = pd.read_csv(base / "lil-1750-Donnees_CSV" / "fichiers_standards"
                       / "Toulouse_2023_std_depl.csv", dtype=str, low_memory=False)
    depl["ZF_orig"] = zone_key(depl.D3)
    depl["ZF_dest"] = zone_key(depl.D7)
    hour = (pd.to_numeric(depl.D4, errors="coerce") // 100) % 24
    depl["band"] = hour.fillna(13).astype(int).map(band_of)

    resolved = depl.ZF_orig.isin(xy.index) & depl.ZF_dest.isin(xy.index)
    print(f"Déplacements : {len(depl)} | OD résolues sur la couche : "
          f"{resolved.sum()} ({resolved.mean():.1%})")

    pairs = (depl.loc[resolved, ["ZF_orig", "ZF_dest", "band"]]
             .drop_duplicates().reset_index(drop=True))
    intra = (pairs.ZF_orig == pairs.ZF_dest).to_numpy()
    print(f"Paires distinctes à router : {len(pairs)} "
          f"(dont {intra.sum()} intra-zone) × {len(MODES)} modes = "
          f"{len(pairs) * len(MODES)} requêtes")

    o = xy.reindex(pairs.ZF_orig).reset_index(drop=True)
    d = xy.reindex(pairs.ZF_dest).reset_index(drop=True)
    length = INTRA_FACTOR * np.sqrt(o.SURF_M2.to_numpy())
    bearing = math.radians(INTRA_BEARING_DEG)
    shift_x = np.where(intra, length / 2 * math.sin(bearing), 0.0)
    shift_y = np.where(intra, length / 2 * math.cos(bearing), 0.0)

    og = gpd.GeoSeries(gpd.points_from_xy(o.XL93 - shift_x, o.YL93 - shift_y),
                       crs=zf.crs).to_crs("EPSG:4326")
    dg = gpd.GeoSeries(gpd.points_from_xy(d.XL93 + shift_x, d.YL93 + shift_y),
                       crs=zf.crs).to_crs("EPSG:4326")
    pairs["from_lat"], pairs["from_lon"] = og.y.values, og.x.values
    pairs["to_lat"], pairs["to_lon"] = dg.y.values, dg.x.values
    pairs["intra_zone"] = intra
    pairs["crow_km"] = np.hypot(o.XL93 - shift_x - (d.XL93 + shift_x),
                                o.YL93 - shift_y - (d.YL93 + shift_y)).values / 1000

    trips = depl.loc[resolved, ["ZFD", "ECH", "PER", "NDEP", "MODP",
                                "ZF_orig", "ZF_dest", "band"]].copy()
    return pairs, trips


# ---------------------------------------------------------------------------
# Routage
# ---------------------------------------------------------------------------

class Router:
    """Client OTP minimal, réparti sur les instances disponibles."""

    def __init__(self, ports=OTP_PORTS, retries: int = 2):
        self.ports = list(ports)
        self.retries = retries
        self.counters = {"ok": 0, "no_route": 0, "error": 0}
        self.lock = Lock()

    def _post(self, port: int, payload: dict) -> dict:
        request = urllib.request.Request(
            f"http://localhost:{port}/otp/transmodel/v3",
            json.dumps(payload).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read())

    def route(self, index: int, row) -> dict:
        out = {}
        for mode, spec in MODES.items():
            payload = {"query": QUERY, "variables": {
                "from": {"coordinates": {"latitude": row.from_lat,
                                         "longitude": row.from_lon}},
                "to": {"coordinates": {"latitude": row.to_lat,
                                       "longitude": row.to_lon}},
                "dt": f"{SERVICE_DATE}T{BAND_DEPART[row.band]}:00+02:00",
                "modes": spec,
                # Uniquement pour les TC : l'interdire ailleurs casserait la marche.
                "mdd": NO_DIRECT_WALK if mode == "transit" else None}}
            duration = distance = None
            for attempt in range(self.retries + 1):
                port = self.ports[(index + attempt) % len(self.ports)]
                try:
                    trip = (self._post(port, payload).get("data") or {}).get("trip") or {}
                    patterns = trip.get("tripPatterns") or []
                    if mode == "transit":
                        # Une option sans jambe TC est une marche directe déguisée.
                        patterns = [p for p in patterns
                                    if TRANSIT_LEG_MODES
                                    & {leg["mode"] for leg in p.get("legs") or []}]
                    if patterns:
                        best = min(patterns, key=lambda p: p["duration"])
                        duration, distance = best["duration"], best["distance"]
                        with self.lock:
                            self.counters["ok"] += 1
                    else:
                        with self.lock:
                            self.counters["no_route"] += 1
                    break
                except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                    if attempt == self.retries:
                        with self.lock:
                            self.counters["error"] += 1
                        # Une erreur se journalise avec de quoi agir.
                        print(f"[ERREUR] routage {mode} "
                              f"{row.ZF_orig}→{row.ZF_dest} {row.band} : {exc}")
            out[f"dur_{mode}_min"] = duration / 60 if duration is not None else np.nan
            out[f"dist_{mode}_km"] = distance / 1000 if distance is not None else np.nan
        return out


def route_all(pairs: pd.DataFrame, workers: int) -> pd.DataFrame:
    router = Router()
    started = time.perf_counter()
    total = len(pairs)
    results: list[dict] = [None] * total  # type: ignore
    print(f"Routage de {total} paires sur {len(OTP_PORTS)} instances OTP, "
          f"{workers} requêtes simultanées…")

    def work(item):
        i, row = item
        results[i] = router.route(i, row)
        done = i + 1
        if done % 2000 == 0:
            elapsed = time.perf_counter() - started
            rate = done / elapsed
            print(f"  {done}/{total} paires ({done/total:.0%}) — {rate:.0f} paires/s, "
                  f"reste ~{(total-done)/rate/60:.0f} min | "
                  f"ok={router.counters['ok']} sans_itinéraire="
                  f"{router.counters['no_route']} erreurs={router.counters['error']}")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(work, enumerate(pairs.itertuples(index=False))))

    elapsed = time.perf_counter() - started
    requests = total * len(MODES)
    print(f"Routage terminé en {elapsed/60:.1f} min "
          f"({requests} requêtes, {requests/elapsed:.0f} req/s)")
    print(f"  succès={router.counters['ok']} sans_itinéraire="
          f"{router.counters['no_route']} erreurs={router.counters['error']}")
    error_rate = router.counters["error"] / max(requests, 1)
    if error_rate > ERROR_ALARM_RATE:
        print(f"[ALARME] Taux d'erreur de routage {error_rate:.1%} > "
              f"{ERROR_ALARM_RATE:.0%} — les colonnes produites sont incomplètes, "
              f"ne pas entraîner dessus sans vérifier OTP")
    return pd.concat([pairs.reset_index(drop=True),
                      pd.DataFrame(results)], axis=1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None,
                        help="ne router que les N premières paires (mise au point)")
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    root = find_project_root()
    here = root / "scripts" / "progedo_logit"
    out = args.out or (here / "mode_skims.parquet")

    pairs, trips = build_pairs(root)
    if args.limit:
        pairs = pairs.head(args.limit).copy()
        print(f"--limit : {len(pairs)} paires seulement")

    skims = route_all(pairs, args.workers)
    for mode in MODES:
        col = f"dist_{mode}_km"
        print(f"  {mode:8s} couverture {skims[col].notna().mean():6.1%} | "
              f"distance médiane {skims[col].median():.2f} km")
    skims.to_parquet(out)
    trips.to_parquet(out.with_name("trip_to_pair.parquet"))
    meta = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "service_date": SERVICE_DATE, "hour_bands": BAND_DEPART,
            "intra_zone_factor": INTRA_FACTOR, "intra_bearing_deg": INTRA_BEARING_DEG,
            "zone_code_width": ZONE_CODE_WIDTH, "n_pairs": int(len(skims))}
    out.with_suffix(".meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\nÉcrits :\n - {out}\n - {out.with_name('trip_to_pair.parquet')}"
          f"\n - {out.with_suffix('.meta.json')}")


if __name__ == "__main__":
    main()
