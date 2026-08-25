"""
audit_perimetre.py — Les neuf écarts de base entre la population enquêtée et la
population simulée, mesurés un par un.

    llm-agents/.venv/bin/python -m scripts.data.population.audit_perimetre
    llm-agents/.venv/bin/python -m scripts.data.population.audit_perimetre \
        --population data/population/toulouse_population_1000.json \
        --run experiments/current \
        --trace docs/traces/2026-08-24_perimetre_population

CE QUE ÇA MESURE, ET POURQUOI ÇA EXISTE (ticket 020). Toute la chaîne de mesure du
dépôt compare des parts modales simulées aux cibles de `cerema_values.yaml` —
globalement et dans huit sous-catégories. Cette comparaison suppose que les deux côtés
parlent de la même population et du même objet compté. Ce n'était pas établi : c'était
supposé. Les tickets 015, 016, 017 et 019 ont tous montré le même motif — un
coefficient appris sur une variable, appliqué à une autre, et l'écart invisible dans
les agrégats. Le périmètre de population est le maillon le plus en amont : un biais de
périmètre déplace TOUTES les cibles à la fois.

LE PRINCIPE DE SORTIE. Chaque axe rend une ligne : valeur enquête, valeur simulée,
écart, et verdict. **Un axe non mesuré est un axe qui passe**, et c'est exactement le
motif de vacuité que le projet traque : le script rend donc `non mesurable` avec sa
raison, jamais un silence ni un 0.

TROIS VERDICTS POSSIBLES, et ils ne sont pas interchangeables :
  * `conforme`     — l'écart est sous la tolérance ; rien à corriger.
  * `à corriger`   — l'écart agit sur les résultats ; il ouvre un ticket.
  * `à publier`    — l'écart est réel et non corrigeable dans ce ticket ; il figure
                     aux limites de la publication AVEC SON AMPLITUDE.

CE QUE ÇA NE FAIT PAS. Aucune correction. Le ticket 020 établit et qualifie les
écarts ; les corrections qui dépassent un ajustement de mesure ouvrent leurs propres
tickets. En particulier le script NE MODIFIE PAS `geo_reference.residence_zone` : ce
classement facture le temps terminal (ticket 013), donc le changer demande un bump de
`version` dans `terminal_time.yaml` et invalide trois caches.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from llm_module.core.geo_reference import haversine_km, hypercenter, residence_zone  # noqa: E402
from llm_module.core.population_reference import (  # noqa: E402
    COURONNES, MIN_AGE, OUT_OF_PERIMETER, couronne_commune_counts,
    couronne_population_shares, household_targets, household_weight,
    population_reference, survey_window, surveyed_weekdays)
from llm_module.core.residence_zone import CommunalZones  # noqa: E402

DEFAULT_POPULATION = REPO_ROOT / "data" / "population" / "toulouse_population_1000.json"
DEFAULT_RUN = REPO_ROOT / "experiments" / "current"
CEREMA_VALUES = REPO_ROOT / "scripts" / "data" / "population" / "cerema_values.yaml"
COURONNE_GEOJSON = REPO_ROOT / "llm_module" / "data" / "couronne_perimetre.geojson"
WEATHER_CSV = REPO_ROOT / "data" / "weather" / "meteo_toulouse_12_mois.csv"

SCORED_MODES = ("voiture", "marche", "transports_collectifs", "velo")
MOVE_MODE_MAP = {
    "Voiture Privée": "voiture",
    "Marche": "marche",
    "Vélo": "velo",
    "Transports_collectifs": "transports_collectifs",
}

CONFORME = "conforme"
A_CORRIGER = "à corriger"
A_PUBLIER = "à publier"
NON_MESURABLE = "non mesurable"


@dataclass
class Finding:
    """Un axe instruit. `simule=None` signifie non mesurable, avec sa raison."""

    axe: str
    titre: str
    enquete: str
    simule: str
    ecart: str
    verdict: str
    detail: str = ""
    tables: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"axe": self.axe, "titre": self.titre, "enquete": self.enquete,
                "simule": self.simule, "ecart": self.ecart, "verdict": self.verdict,
                "detail": self.detail, "tables": self.tables}


# ── Lecture des entrées ───────────────────────────────────────────────────────

def load_population(path: Path) -> list[dict]:
    people = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(people, list):
        raise SystemExit(f"{path} : une population est une liste de personas.")
    return people


def load_moves(run_dir: Path) -> tuple[list[dict], Optional[str]]:
    """Lignes de `moves.csv` du run, ou `(<vide>, raison)`."""
    import csv

    path = run_dir / "moves.csv"
    if not path.exists():
        return [], f"{path} absent"
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return rows, None


def traits(person: dict) -> dict:
    return (person.get("identity") or {}).get("traits_json") or {}


def home(person: dict) -> dict:
    return (person.get("identity") or {}).get("home") or {}


# ── Classement communal (la définition de l'enquête) ──────────────────────────

# `CommunalZones` a vécu ici. Elle est montée dans `llm_module.core.residence_zone` au
# ticket 021, lot 1, quand un second appelant est apparu (le post-traitement qui pose la
# couronne sur le persona) : deux copies d'une classification de référence finissent par
# diverger, et celle-ci définit ce qui est « hors périmètre ». L'audit la lit désormais au
# même endroit que la production, ce qui est le seul moyen que ses verdicts portent sur ce
# qui tourne.

# ── Axes ──────────────────────────────────────────────────────────────────────

def axis_a1_age(people: list[dict]) -> Finding:
    ages = [traits(p).get("age") for p in people]
    known = [float(a) for a in ages if isinstance(a, (int, float))]
    missing = len(ages) - len(known)
    under = [a for a in known if a < MIN_AGE]
    share = 100.0 * len(under) / len(known) if known else 0.0
    verdict = CONFORME if not under else A_CORRIGER
    detail = (
        f"Âge minimum observé : {min(known):.0f} ans ; {missing} persona(s) sans âge. "
        "Le contrôle n'est pas gratuit même à zéro : `frames.age_to_cat` teste "
        "`a <= 9`, donc un persona de 3 ans tomberait dans la classe « 5-9 » et serait "
        "comparé à la cible d'une classe dont il ne fait pas partie, sans qu'aucun log "
        "ne le signale. La conformité est ici HÉRITÉE de la chaîne eqasim (les chaînes "
        "d'activités sont appariées sur une enquête qui commence à 5 ans), elle n'est "
        "garantie par aucune assertion.")
    return Finding(
        "A1", "Âge minimum de la population comptée",
        f"population cible = {MIN_AGE} ans et plus",
        f"{len(under)} persona(s) de moins de {MIN_AGE} ans sur {len(known)}",
        f"{share:.2f} pt de population", verdict, detail,
        {"age_min": min(known) if known else None, "n_sous_seuil": len(under),
         "n_total": len(known), "n_sans_age": missing})


def axis_a2_couronnes(people: list[dict], zones: Optional[CommunalZones],
                      moves: list[dict], cerema: dict) -> Finding:
    if zones is None:
        return Finding(
            "A2", "Définition des couronnes", "découpage par liste de communes",
            "—", "—", NON_MESURABLE,
            "Ressource `llm_module/data/couronne_perimetre.geojson` absente : "
            "`make communes-couronnes` l'exige, et cette cible exige les données "
            "PROGEDO d'accès restreint.")

    confusion: Counter = Counter()
    per_person: dict[str, tuple[str, str]] = {}
    for person in people:
        h = home(person)
        metric = residence_zone(h.get("lat"), h.get("lon"))
        communal = zones.classify(h.get("lat"), h.get("lon"))
        confusion[(metric, communal)] += 1
        per_person[str(person.get("person_id"))] = (metric, communal)

    total = sum(confusion.values())
    moved = sum(n for (m, c), n in confusion.items() if m != c)
    share = 100.0 * moved / total if total else 0.0

    # Cible implicite : la part voiture à laquelle chaque agent est comparé, moyennée.
    targets = (cerema.get("parts_modales_2023") or {}).get("lieu_residence") or {}

    def implied_car(index: int) -> Optional[float]:
        weighted, mass = 0.0, 0
        for pair, n in confusion.items():
            key = pair[index].replace(" ", "_")
            node = targets.get(key)
            if not node:
                continue
            weighted += float(node["voiture"]) * n
            mass += n
        return weighted / mass if mass else None

    car_metric, car_communal = implied_car(0), implied_car(1)

    # Effet sur les parts modales publiées par zone, quand un run est disponible.
    tables: dict[str, Any] = {
        "confusion": {f"{m} → {c}": n for (m, c), n in sorted(confusion.items())},
        "cible_voiture_implicite": {"metrique": car_metric, "communal": car_communal},
    }
    if moves:
        tables["parts_par_zone"] = modal_shares_by_zone(moves, per_person, cerema)

    detail = (
        "Une couronne administrative n'est pas un anneau métrique. Le disque de 8 km "
        "autour du Capitole sort largement de la commune de Toulouse et mord sur "
        "Blagnac, Balma, Colomiers, Tournefeuille et Ramonville — de 1ʳᵉ couronne dans "
        "l'enquête. L'erreur est UNIDIRECTIONNELLE : les 179 zones fines de Toulouse "
        "sont toutes à moins de 7 km du centre, donc aucun Toulousain n'est classé "
        "dehors. Elle gonfle Toulouse et vide la 1ʳᵉ couronne. Enjeu direct : la cible "
        "`voiture` vaut 31 % à Toulouse et 64 % en 1ʳᵉ couronne — un agent mal classé "
        "n'est pas comparé à une cible un peu décalée, il l'est à une cible qui diffère "
        "de plus de 30 points.")
    ecart = f"{share:.1f} % des personas changent de couronne"
    if car_metric is not None and car_communal is not None:
        ecart += (f" ; cible voiture implicite {car_metric:.1f} % → "
                  f"{car_communal:.1f} %")
    return Finding(
        "A2", "Définition des couronnes",
        "découpage par liste de communes : "
        + " / ".join(f"{n}" for n in couronne_commune_counts().values()),
        "classement par distance à l'hypercentre (8 / 20 / 40 km)",
        ecart, A_CORRIGER, detail, tables)


def modal_shares_by_zone(moves: list[dict], per_person: dict[str, tuple[str, str]],
                         cerema: dict) -> dict:
    """Parts modales par couronne sous les deux classements, plus l'écart L1 aux cibles."""
    targets = (cerema.get("parts_modales_2023") or {}).get("lieu_residence") or {}
    out: dict[str, Any] = {}
    for index, label in ((0, "metrique"), (1, "communal")):
        mass: dict[str, Counter] = defaultdict(Counter)
        for row in moves:
            mode = MOVE_MODE_MAP.get((row.get("Mode de transport Choisi") or "").strip())
            if mode is None:
                continue
            pair = per_person.get((row.get("ID Personne") or "").strip())
            if pair is None:
                continue
            mass[pair[index]][mode] += 1
        zones: dict[str, Any] = {}
        for zone, counter in mass.items():
            total = sum(counter.values())
            if not total:
                continue
            shares = {m: 100.0 * counter[m] / total for m in SCORED_MODES}
            node = targets.get(zone.replace(" ", "_"))
            l1 = None
            if node:
                renorm = sum(float(node[m]) for m in SCORED_MODES)
                target = {m: 100.0 * float(node[m]) / renorm for m in SCORED_MODES}
                l1 = sum(abs(shares[m] - target[m]) for m in SCORED_MODES)
            zones[zone] = {"n": total, "shares": shares, "l1": l1}
        weighted = [(z["l1"], z["n"]) for z in zones.values() if z["l1"] is not None]
        out[label] = {
            "zones": zones,
            "l1_pondere": (sum(l * n for l, n in weighted) / sum(n for _, n in weighted)
                           if weighted else None),
        }
    return out


def axis_a3_ponderation(people: list[dict], moves: list[dict]) -> Finding:
    targets = household_targets()
    sizes = [(traits(p).get("household_size"), traits(p).get("number_of_cars"))
             for p in people]
    usable = [(float(s), float(c)) for s, c in sizes
              if isinstance(s, (int, float)) and s and isinstance(c, (int, float))]
    if not usable:
        return Finding("A3", "Base de pondération", "poids COE0 (ménages) / COEP (personnes)",
                       "—", "—", NON_MESURABLE,
                       "Aucun persona ne porte à la fois `household_size` et `number_of_cars`.")

    raw_size = sum(s for s, _ in usable) / len(usable)
    raw_cars = sum(c for _, c in usable) / len(usable)
    raw_zero = 100.0 * sum(1 for _, c in usable if c == 0) / len(usable)
    weights = [household_weight(s) for s, _ in usable]
    mass = sum(weights)
    w_size = sum(w * s for w, (s, _) in zip(weights, usable)) / mass
    w_cars = sum(w * c for w, (_, c) in zip(weights, usable)) / mass
    w_zero = 100.0 * sum(w for w, (_, c) in zip(weights, usable) if c == 0) / mass

    detail = (
        "L'écart brut n'est pas un défaut de la population : c'est un défaut de BASE. "
        "Une population synthétique échantillonne des PERSONNES, donc un ménage de 5 y "
        "apparaît cinq fois et un ménage de 1 une seule ; la moyenne brute d'un attribut "
        "de ménage y est mécaniquement tirée vers les grands ménages. Pondérer chaque "
        "personne par 1/taille rend à chaque ménage un poids de 1 — et l'écart de 30 % "
        "sur la taille de ménage tombe à 3 %. C'est le même raisonnement que le ticket "
        "019 a appliqué à la loi du logement. Les parts modales, elles, sont des "
        "comptages de DÉPLACEMENTS non pondérés : c'est la bonne base pour une cible "
        "`COEP`, à ceci près qu'un persona qui se déplace beaucoup y pèse plus qu'un "
        "sédentaire, ce que le redressement d'enquête corrige et que la simulation ne "
        "corrige pas.")
    return Finding(
        "A3", "Base de pondération des cibles",
        f"taille {targets['taille_moyenne_menage']:.2f} · "
        f"{targets['voitures_par_menage']:.2f} voiture/ménage · "
        f"{targets['sans_voiture_pct']:.0f} % sans voiture (poids COE0)",
        f"brut : {raw_size:.2f} · {raw_cars:.2f} · {raw_zero:.1f} % — "
        f"pondéré ménages : {w_size:.2f} · {w_cars:.2f} · {w_zero:.1f} %",
        f"taille : {raw_size - targets['taille_moyenne_menage']:+.2f} en brut, "
        f"{w_size - targets['taille_moyenne_menage']:+.2f} pondéré",
        A_PUBLIER, detail,
        {"brut": {"taille": raw_size, "voitures": raw_cars, "sans_voiture_pct": raw_zero},
         "pondere_menages": {"taille": w_size, "voitures": w_cars,
                             "sans_voiture_pct": w_zero},
         "cible": targets,
         "n_deplacements_non_ponderes": len(moves)})


def axis_a4_exclusions(people: list[dict], zones: Optional[CommunalZones]) -> Finding:
    if zones is None:
        return Finding("A4", "Populations et déplacements hors périmètre",
                       "touristes, EHPAD, marchandises exclus ; 95,9 % des "
                       "déplacements internes au périmètre",
                       "—", "—", NON_MESURABLE,
                       "Ressource `couronne_perimetre.geojson` absente.")
    center = hypercenter()
    outside, distances = 0, []
    activities_total = activities_outside = 0
    residents_with_external = 0
    for person in people:
        h = home(person)
        zone = zones.classify(h.get("lat"), h.get("lon"))
        inside_home = zone != OUT_OF_PERIMETER and zone != ""
        if not inside_home:
            outside += 1
            if h.get("lat") is not None:
                distances.append(haversine_km(center[0], center[1], h["lat"], h["lon"]))
        has_external = False
        for activity in (person.get("identity") or {}).get("activities") or []:
            loc = activity.get("location") or {}
            if loc.get("lat") is None:
                continue
            activities_total += 1
            if zones.classify(loc.get("lat"), loc.get("lon")) == OUT_OF_PERIMETER:
                activities_outside += 1
                has_external = True
        if inside_home and has_external:
            residents_with_external += 1
    total = len(people)
    share = 100.0 * outside / total if total else 0.0
    verdict = A_CORRIGER if share > 1.0 else CONFORME
    detail = (
        "L'enquête ne compte QUE le périmètre de 453 communes : ni touristes, ni "
        "EHPAD, ni marchandises, et 95,9 % de ses déplacements pondérés sont internes "
        "au périmètre (le recalcul sur les internes seuls redonne exactement la cible "
        "publiée de 55 % voiture). Un domicile hors périmètre n'a donc AUCUNE cible à "
        "laquelle se comparer — et le classement métrique lui en donne une quand même, "
        "celle de la 3ᵉ couronne, parce que « au-delà de 40 km » n'a pas de borne "
        "supérieure. C'est le mécanisme exact du motif de vacuité : l'absence de "
        "périmètre produit une classification, pas une erreur.")
    return Finding(
        "A4", "Populations et déplacements hors périmètre",
        "453 communes ; 95,9 % des déplacements internes au périmètre",
        f"{outside} domicile(s) hors périmètre sur {total}",
        f"{share:.1f} % des personas"
        + (f", jusqu'à {max(distances):.0f} km du Capitole" if distances else ""),
        verdict, detail,
        {"n_hors_perimetre": outside, "n_total": total,
         "distance_max_km": max(distances) if distances else None,
         "distance_min_km": min(distances) if distances else None,
         "activites_hors_perimetre_pct":
             100.0 * activities_outside / activities_total if activities_total else None,
         "residents_avec_activite_externe": residents_with_external})


def axis_a5_saison(moves: list[dict]) -> Finding:
    debut, fin = survey_window()
    md_start, md_end = debut[5:], fin[5:]

    def in_window(month_day: str) -> bool:
        return month_day >= md_start or month_day <= md_end

    rows = _read_weather()
    window_stats = year_stats = None
    if rows:
        year_stats = _rain_stats(rows)
        window_stats = _rain_stats([r for r in rows if in_window(r["md"])])

    dates = sorted({(row.get("Heure de départ") or "")[:10] for row in moves
                    if (row.get("Heure de départ") or "")[:10]})
    in_win = [d for d in dates if in_window(d[5:])]
    rain_share = None
    if moves:
        wet = sum(1 for row in moves
                  if _to_float(row.get("Météo Précipitations (mm)")) > 0)
        rain_share = 100.0 * wet / len(moves)

    detail = (
        "CE QUE L'ENQUÊTE MESURE, vérifié deux fois. La méthode EMC² recueille les "
        "« déplacements de la VEILLE » (passation du mardi au samedi hors fériés et "
        "vacances scolaires, jour de référence du lundi au vendredi) : elle n'interroge "
        "personne sur ses habitudes annuelles. Les dates de référence des microdonnées "
        "le confirment — seuls les mois 09 à 12 de 2022 et 01 à 02 de 2023 y "
        "apparaissent, aucune observation de mars à août, et le jour de référence est "
        "toujours ouvré. Les cibles sont donc bien des déplacements d'automne-hiver.\n\n"
        "MAIS CE QU'ELLE PUBLIE est « un jour moyen de semaine ». La fenêtre "
        "automne-hiver et l'exclusion des congés sont le MOYEN d'obtenir une journée "
        "ordinaire, pas une revendication saisonnière. L'écart n'est donc pas « cible "
        "d'automne contre simulation de printemps » : c'est un écart de MOYENNAGE, et il "
        "se sépare en deux.\n\n"
        "(1) LES JEUX GELÉS MOYENNENT, mais sur la mauvaise fenêtre. Un jour est tiré "
        "indépendamment par décision, sur 365 jours : la pluie y est donc bien "
        "représentée (42,5 % contre 44,7 % en fenêtre), et l'écart est THERMIQUE — 18,0 "
        "contre 12,7 °C à midi. Restreindre le tirage à la fenêtre d'enquête corrige "
        "cet écart-là, et lui seul.\n\n"
        "(2) UN RUN NE MOYENNE PAS. Il rejoue des jours calendaires consécutifs réels — "
        "ici cinq jours de mi-mars, tous secs. Thermiquement ces jours sont TYPIQUES de "
        "la fenêtre d'enquête (14,6 °C à midi, chacun entre le 56ᵉ et le 81ᵉ centile de "
        "sa distribution), et mi-mars est une semaine scolaire ordinaire : le grief "
        "calendaire est faible. Le grief réel est qu'une réalisation de 5 jours est "
        "comparée à une moyenne de 152 jours. Et 0 % de pluie n'est pas un tirage "
        "exotique qu'il suffirait d'éviter : 27,7 % des fenêtres de 5 jours consécutifs "
        "de la période d'enquête sont elles aussi entièrement sèches. AUCUN choix de "
        "jours ne rend un run de 5 jours comparable à la moyenne sur le mode le plus "
        "sensible à la météo — le vélo, dont les mouvements de 4 à 5 points ont déjà "
        "arbitré les tickets 013 et 014. C'est une limite de variance, à publier, pas un "
        "réglage à trouver.")
    simule = (f"{len(dates)} jour(s) simulé(s) : {', '.join(dates)}" if dates
              else "aucun run exploitable")
    if rain_share is not None:
        simule += f" ; {rain_share:.1f} % des trajets sous la pluie"
    ecart = "—"
    if window_stats and year_stats:
        ecart = (f"pluie : {window_stats['rain_pct']:.1f} % de jours en fenêtre "
                 f"d'enquête, {year_stats['rain_pct']:.1f} % sur l'année tirée par les "
                 f"jeux gelés, {rain_share:.1f} % dans ce run — et T° midi "
                 f"{window_stats['temp_midi_moy']:.1f} contre "
                 f"{year_stats['temp_midi_moy']:.1f} °C"
                 if rain_share is not None else
                 f"jours pluvieux : {window_stats['rain_pct']:.1f} % contre "
                 f"{year_stats['rain_pct']:.1f} %")
    return Finding(
        "A5", "Fenêtre saisonnière de la mesure",
        f"{debut} → {fin}, hors vacances scolaires", simule, ecart,
        # Verdict A_PUBLIER même si les jours simulés tombent DANS la fenêtre : le
        # grief principal est la variance d'un run de quelques jours face à une moyenne
        # de 152, et changer les dates ne la supprime pas.
        A_PUBLIER, detail,
        {"jours_simules": dates, "jours_dans_la_fenetre": in_win,
         "fenetre": window_stats, "annee": year_stats,
         "part_trajets_sous_la_pluie": rain_share})


def _read_weather() -> list[dict]:
    if not WEATHER_CSV.exists():
        return []
    import csv

    out = []
    with WEATHER_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            stamp = (row.get("DATE") or "")
            if len(stamp) < 10:
                continue
            out.append({"md": stamp[5:10],
                        "precip": _to_float(row.get("PRECIP_TOTAL_DAY_MM")),
                        "noon": _to_float(row.get("TEMPERATURE_NOON_C_12H"))})
    return out


def _rain_stats(rows: list[dict]) -> Optional[dict]:
    if not rows:
        return None
    return {"n_jours": len(rows),
            "rain_pct": 100.0 * sum(1 for r in rows if r["precip"] > 0) / len(rows),
            "precip_moy_mm": sum(r["precip"] for r in rows) / len(rows),
            "temp_midi_moy": sum(r["noon"] for r in rows) / len(rows)}


def axis_a6_jour(moves: list[dict]) -> Finding:
    if not moves:
        return Finding("A6", "Jour de la semaine",
                       "veille enquêtée = lundi à vendredi", "—", "—", NON_MESURABLE,
                       "Aucun `moves.csv` exploitable.")
    days: Counter = Counter()
    for row in moves:
        stamp = (row.get("Heure de départ") or "")[:10]
        if len(stamp) != 10:
            continue
        try:
            days[date.fromisoformat(stamp).isoweekday()] += 1
        except ValueError:
            continue
    noms = {1: "lundi", 2: "mardi", 3: "mercredi", 4: "jeudi", 5: "vendredi",
            6: "samedi", 7: "dimanche"}
    weekend = sum(n for d, n in days.items() if d >= 6)
    total = sum(days.values()) or 1
    expected = set(surveyed_weekdays())
    detail = (
        "Le garde-fou existe et il est actif : `no_weekend_departures` reporte tout "
        "départ de samedi ou dimanche au lundi suivant à la même heure. Il n'est "
        "jamais exercé sur les runs courants, qui démarrent un lundi et durent au plus "
        "cinq jours. Deux nuances mesurées à l'intérieur d'EMC² : les parts modales ne "
        "varient que de 1,3 point au plus entre les cinq jours ouvrés (voiture 54,5 à "
        "55,8 %), donc un run mono-journalier ne biaise pas les PARTS ; mais le lundi "
        "porte 3,16 déplacements par personne contre 3,51 le mercredi, soit 10 % de "
        "volume en moins — l'écart compterait si un VOLUME était un jour comparé. "
        "Attention au report : sur un run de plus de cinq jours, il empilerait les "
        "départs de week-end sur le lundi et fabriquerait un lundi atypique.")
    return Finding(
        "A6", "Jour de la semaine",
        f"veille enquêtée = jours {sorted(expected)} (lundi à vendredi), "
        "répartis à peu près uniformément",
        " · ".join(f"{noms[d]} {100.0 * n / total:.0f} %"
                  for d, n in sorted(days.items())),
        f"{100.0 * weekend / total:.1f} % de trajets de week-end",
        CONFORME if not weekend and set(days) <= expected else A_CORRIGER,
        detail, {"trajets_par_jour_semaine": {noms[d]: n
                                             for d, n in sorted(days.items())}})


def axis_a7_objet_compte(moves: list[dict]) -> Finding:
    if not moves:
        return Finding("A7", "Objet compté : le déplacement à mode principal",
                       "un déplacement = un mode principal", "—", "—", NON_MESURABLE,
                       "Aucun `moves.csv` exploitable.")
    trip_ids = [row.get("ID Trajet") for row in moves if row.get("ID Trajet")]
    unique = len(set(trip_ids))
    modes = Counter((row.get("Mode de transport Choisi") or "").strip()
                    for row in moves)
    detail = (
        "Deux questions distinctes, et les réponses ne vont pas dans le même sens.\n\n"
        "CE QUI EST CONFORME. Une ligne de `moves.csv` est bien un DÉPLACEMENT, pas une "
        "jambe : les jambes terminales du ticket 013 portent `is_transfer=True` et "
        "`_plan_transport_mode` ne regarde que les jambes non-transfert, donc la marche "
        "d'accès à une voiture ou à un bus n'est jamais comptée comme un déplacement à "
        "pied. L'enquête fait la même chose, et c'est vérifié dans ses microdonnées : "
        "AUCUN de ses déplacements en voiture ou en transports collectifs ne porte de "
        "trajet à pied — l'accès y est une DURÉE (T2/T6), pas un trajet. La marche n'est "
        "donc pas surestimée par construction.\n\n"
        "CE QUI DIVERGE. La hiérarchie de mode principal est INVERSÉE. `_plan_transport_"
        "mode` teste la voiture AVANT les transports collectifs ; l'enquête fait le "
        "contraire — sur ses 770 déplacements mêlant voiture et transports collectifs, "
        "760 sont codés « transports collectifs » et 10 seulement « voiture ». Ces "
        "déplacements pèsent 1,4 point de part modale, soit 11,5 % de la cible "
        "transports collectifs de 12 %. La divergence est aujourd'hui LATENTE : OTP est "
        "interrogé mode par mode, donc aucun itinéraire simulé ne mêle voiture et "
        "transports collectifs, et zéro déplacement est aujourd'hui mal classé. Mais "
        "l'effet miroir est réel : la simulation ne peut STRUCTURELLEMENT pas produire "
        "les 1,4 point de rabattement que la cible compte en transports collectifs.")
    return Finding(
        "A7", "Objet compté : le déplacement à mode principal",
        "un déplacement, un mode principal ; hiérarchie plaçant les transports "
        "collectifs au-dessus de la voiture (760/770 déplacements mixtes)",
        f"{len(moves)} lignes pour {unique} identifiants de trajet distincts ; "
        "aucune ligne de jambe",
        "0 déplacement mal classé aujourd'hui ; 1,4 pt de rabattement inatteignable",
        A_PUBLIER, detail,
        {"n_lignes": len(moves), "n_trajets_uniques": unique,
         "modes": dict(modes.most_common()),
         "part_rabattement_dans_cible_tc_pct": 11.5,
         "part_rabattement_absolue_pct": 1.41})


def axis_a8_menages(people: list[dict]) -> Finding:
    clusters: dict[tuple, list[dict]] = defaultdict(list)
    for person in people:
        h = home(person)
        if h.get("lat") is None:
            continue
        clusters[(round(float(h["lat"]), 6), round(float(h["lon"]), 6))].append(person)
    if not clusters:
        return Finding("A8", "Structure de ménage", "2,08 personnes par ménage", "—",
                       "—", NON_MESURABLE, "Aucun domicile géolocalisé.")
    complete = incomplete = collisions = 0
    declared = present = 0
    for members in clusters.values():
        sizes = {traits(m).get("household_size") for m in members}
        if len(sizes) > 1:
            collisions += 1
        size = traits(members[0]).get("household_size") or 0
        declared += size
        present += len(members)
        if len(members) == size:
            complete += 1
        elif len(members) < size:
            incomplete += 1
    target = household_targets()["taille_moyenne_menage"]
    declared_mean = declared / len(clusters)
    present_mean = present / len(clusters)
    detail = (
        "La taille de ménage DÉCLARÉE est juste : la moyenne par adresse tombe sur la "
        "cible. Ce qui manque, ce sont des MEMBRES : environ un membre déclaré sur dix "
        "n'existe pas comme persona, et un quart des grappes est incomplet. Deux "
        "conséquences à ne pas confondre. Sur les cibles de ménage, aucune : elles se "
        "lisent sur la taille déclarée, qui est correcte. Sur tout ce qui dépend des "
        "CO-RÉSIDENTS — partage de voiture du foyer, verrous de chaîne, attribution de "
        "vélo — l'effet est réel, et c'est le mécanisme déjà documenté par le ticket 015.")
    return Finding(
        "A8", "Structure de ménage",
        f"{target:.2f} personnes par ménage ; 674 000 ménages",
        f"{declared_mean:.2f} déclarée par adresse, {present_mean:.2f} réellement "
        f"présente ; {complete}/{len(clusters)} grappes complètes",
        f"{declared_mean - target:+.2f} sur la taille déclarée ; "
        f"{100.0 * (declared - present) / declared:.1f} % de membres absents",
        A_PUBLIER, detail,
        {"n_adresses": len(clusters), "grappes_completes": complete,
         "grappes_incompletes": incomplete, "collisions_adresse": collisions,
         "taille_declaree_moyenne": declared_mean,
         "membres_presents_moyenne": present_mean,
         "membres_absents_pct": 100.0 * (declared - present) / declared})


def axis_a9_spatial(people: list[dict], zones: Optional[CommunalZones]) -> Finding:
    if zones is None:
        return Finding("A9", "Représentativité spatiale", "70 % en Toulouse + 1ʳᵉ couronne",
                       "—", "—", NON_MESURABLE,
                       "Ressource `couronne_perimetre.geojson` absente.")
    target = couronne_population_shares()
    counts: Counter = Counter()
    metric_counts: Counter = Counter()
    for person in people:
        h = home(person)
        counts[zones.classify(h.get("lat"), h.get("lon"))] += 1
        metric_counts[residence_zone(h.get("lat"), h.get("lon"))] += 1
    inside = sum(n for z, n in counts.items() if z in COURONNES)
    observed = {z: 100.0 * counts.get(z, 0) / inside for z in COURONNES} if inside else {}
    core_target = target["Toulouse"] + target["1ere couronne"]
    core_observed = observed.get("Toulouse", 0) + observed.get("1ere couronne", 0)
    metric_total = sum(metric_counts.values()) or 1
    core_published = 100.0 * (metric_counts.get("Toulouse", 0)
                              + metric_counts.get("1ere couronne", 0)) / metric_total
    l1 = sum(abs(observed.get(z, 0) - target[z]) for z in COURONNES)
    detail = (
        "Une surconcentration en cœur d'agglomération tire mécaniquement la part "
        "voiture vers le bas, sans qu'aucun modèle de choix ne soit en cause : la cible "
        "voiture vaut 31 % à Toulouse et 71 à 74 % dans les couronnes externes. Sur "
        "cette population, l'excès est modéré et il est CUMULATIF avec l'axe A2 : le "
        "classement métrique gonfle encore Toulouse, si bien que la concentration "
        "PUBLIÉE est plus forte que la concentration réelle de la population.")
    return Finding(
        "A9", "Représentativité spatiale de l'échantillon",
        " · ".join(f"{z} {target[z]:.1f} %" for z in COURONNES),
        " · ".join(f"{z} {observed.get(z, 0):.1f} %" for z in COURONNES),
        f"Toulouse + 1ʳᵉ couronne : {core_observed:.1f} % réel contre "
        f"{core_target:.1f} % cible, et {core_published:.1f} % tel que PUBLIÉ par le "
        f"classement métrique (L1 = {l1:.1f} pt)",
        A_PUBLIER if l1 > 4 else CONFORME, detail,
        {"cible": target, "observe": observed, "l1": l1,
         "coeur_cible_pct": core_target, "coeur_reel_pct": core_observed,
         "coeur_publie_metrique_pct": core_published,
         "n_dans_le_perimetre": inside,
         "n_hors_perimetre": counts.get(OUT_OF_PERIMETER, 0)})


def _to_float(value: Any) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0



# ── Recoupement du cadrage depuis les microdonnées ────────────────────────────
# Le chargeur `population_reference` vérifie que le cadrage est COHÉRENT avec lui-même.
# Il ne peut pas vérifier qu'il dit vrai : cela demande de recalculer chaque valeur
# depuis les microdonnées de l'enquête. Un chiffre recopié d'une publication et un
# chiffre recalculé sont deux mesures indépendantes — le recoupement ne vaut que si
# elles le sont. D'où ce mode séparé, qui exige les données d'accès restreint.

PROGEDO_STD = (REPO_ROOT / "data" / "PROGEDO 2023" / "lil-1750-Donnees_CSV"
               / "fichiers_standards")
SIG_DTIR = (REPO_ROOT / "data" / "PROGEDO 2023" / "lil-1750-Documentation" / "SIG"
            / "EMC2_Toulouse_2023_DTIR_17072023.shp")

# Regroupement des modalités `MODP` (mode principal du déplacement) vers les quatre
# modes scorés. Les codes viennent du dictionnaire de l'enquête (`MODPf`).
_MODP_GROUPS = {
    "marche": {"01"},
    "velo": {"10", "11", "12", "17", "18"},
    "voiture": {"21", "22", "61", "62", "71", "81", "82"},
    "transports_collectifs": {"31", "32", "33", "34", "37", "38", "39",
                              "41", "42", "43", "51", "52", "53", "54"},
}


def _modp_group(code: Any) -> str:
    code = str(code).zfill(2)
    for group, codes in _MODP_GROUPS.items():
        if code in codes:
            return group
    return "autres"


def recompute_from_microdata() -> dict:
    """Recalcule les valeurs de cadrage depuis EMC², et les confronte au YAML.

    Rend `{"disponible": False, "raison": ...}` quand les microdonnées sont absentes —
    c'est le cas NORMAL sur un poste ou un conteneur sans l'accès ProGEDO.
    """
    if not PROGEDO_STD.exists() or not SIG_DTIR.exists():
        return {"disponible": False,
                "raison": f"microdonnées absentes ({PROGEDO_STD}) — accès restreint lil-1750"}
    try:
        import geopandas as gpd
        import pandas as pd
    except ImportError as exc:
        return {"disponible": False, "raison": f"pandas/geopandas requis : {exc}"}

    dtir = gpd.read_file(SIG_DTIR)
    couronne_of = dict(zip(dtir["NUM_DTIR"].astype(str), dtir["NOM_D2"]))

    men = pd.read_csv(PROGEDO_STD / "Toulouse_2023_std_men.csv", dtype=str)
    per = pd.read_csv(PROGEDO_STD / "Toulouse_2023_std_pers.csv", dtype=str)
    dep = pd.read_csv(PROGEDO_STD / "Toulouse_2023_std_depl.csv", dtype=str)
    men["COE0"] = pd.to_numeric(men["COE0"], errors="coerce")
    per["COEP"] = pd.to_numeric(per["COEP"], errors="coerce")

    per["couronne"] = per["ZFP"].str[:3].map(couronne_of)
    par_couronne = per.groupby("couronne")["COEP"].sum()
    population_5plus = float(par_couronne.sum())

    men["cars"] = pd.to_numeric(men["M6"], errors="coerce").fillna(0)
    poids = men["COE0"]
    menages = float(poids.sum())

    def part(mask) -> float:
        return 100.0 * float((poids * mask.astype(float)).sum()) / menages

    # Parts modales : pondérées COEP, restreintes aux déplacements INTERNES (TYPD = 1),
    # qui est la définition que la cible publiée reproduit.
    joined = dep.merge(per[["ZFP", "ECH", "PER", "COEP"]].rename(columns={"ZFP": "ZFD"}),
                       on=["ZFD", "ECH", "PER"], how="left")
    joined["groupe"] = joined["MODP"].map(_modp_group)
    interne = joined[joined["TYPD"] == "1"]
    masse = interne.groupby("groupe")["COEP"].sum()
    parts_internes = {g: 100.0 * float(masse.get(g, 0.0)) / float(masse.sum())
                      for g in list(_MODP_GROUPS) + ["autres"]}
    masse_tous = joined.groupby("groupe")["COEP"].sum()
    parts_tous = {g: 100.0 * float(masse_tous.get(g, 0.0)) / float(masse_tous.sum())
                  for g in list(_MODP_GROUPS) + ["autres"]}
    localisation = joined.groupby("TYPD")["COEP"].sum()
    localisation_pct = {t: 100.0 * float(v) / float(localisation.sum())
                        for t, v in localisation.items()}

    reference = population_reference()
    totaux = reference["population"]["totaux_perimetre_2023"]
    equip = reference["menages_equipement_voiture"]["perimetre_2023"]
    cible_couronnes = couronne_population_shares()

    lignes = [
        ("ménages enquêtés", len(men),
         reference["enquete"]["echantillon"]["menages_enquetes"]),
        ("personnes interrogées (PENQ=1)", int((per["PENQ"] == "1").sum()),
         reference["enquete"]["echantillon"]["personnes_interrogees"]),
        ("déplacements recensés", len(dep),
         reference["enquete"]["echantillon"]["deplacements_recenses"]),
        ("secteurs de tirage", len(dtir),
         reference["enquete"]["echantillon"]["secteurs_de_tirage"]),
        ("habitants de 5 ans et + (milliers)", round(population_5plus / 1000),
         round(totaux["habitants_5_ans_et_plus"] / 1000)),
        ("ménages (milliers)", round(menages / 1000),
         round(totaux["nombre_menages"] / 1000)),
        ("voitures par ménage", round(float((poids * men["cars"]).sum()) / menages, 2),
         equip["voitures_par_menage_moyen"]),
        ("ménages sans voiture (%)", round(part(men["cars"] == 0), 1),
         equip["repartition_motorisation"]["sans_voiture"]),
        ("ménages à une voiture (%)", round(part(men["cars"] == 1), 1),
         equip["repartition_motorisation"]["une_voiture"]),
        ("ménages à 2 voitures et + (%)", round(part(men["cars"] >= 2), 1),
         equip["repartition_motorisation"]["deux_voitures_et_plus"]),
        ("déplacements internes au périmètre (%)",
         round(localisation_pct.get("1", 0.0), 2),
         reference["enquete"]["localisation_deplacements"]["interne_au_perimetre"]),
    ]
    for zone, cible in cible_couronnes.items():
        code = {"Toulouse": "Toulouse", "1ere couronne": "1ere couronne",
                "2eme couronne": "2eme couronne", "3eme couronne": "3eme couronne"}[zone]
        observe = 100.0 * float(par_couronne.get(code, 0.0)) / population_5plus
        lignes.append((f"part de population — {zone} (%)", round(observe, 1),
                       round(cible, 1)))

    controles = [{"grandeur": nom, "recalcule": recalc, "cadrage": cadre,
                  "ecart": (round(float(recalc) - float(cadre), 2)
                            if isinstance(recalc, (int, float))
                            and isinstance(cadre, (int, float)) else None)}
                 for nom, recalc, cadre in lignes]
    return {
        "disponible": True,
        "controles": controles,
        "parts_modales_recalculees": {"internes": parts_internes, "tous": parts_tous},
        "localisation_deplacements_pct": localisation_pct,
    }


# ── Rendu ─────────────────────────────────────────────────────────────────────

def run_audit(population_path: Path, run_dir: Path,
              recompute: Optional[dict] = None) -> dict:
    population_reference()          # lève si le cadrage est absent ou incohérent
    people = load_population(population_path)
    moves, moves_error = load_moves(run_dir)
    cerema = yaml.safe_load(CEREMA_VALUES.read_text(encoding="utf-8"))

    zones: Optional[CommunalZones] = None
    zones_error = None
    if COURONNE_GEOJSON.exists():
        try:
            zones = CommunalZones.load(COURONNE_GEOJSON)
        except RuntimeError as exc:
            zones_error = str(exc)
    else:
        zones_error = f"{COURONNE_GEOJSON} absent (make communes-couronnes)"

    findings = [
        axis_a1_age(people),
        axis_a2_couronnes(people, zones, moves, cerema),
        axis_a3_ponderation(people, moves),
        axis_a4_exclusions(people, zones),
        axis_a5_saison(moves),
        axis_a6_jour(moves),
        axis_a7_objet_compte(moves),
        axis_a8_menages(people),
        axis_a9_spatial(people, zones),
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ticket": "020",
        "recoupement_microdonnees": recompute if recompute is not None else None,
        "inputs": {
            "population": str(population_path.relative_to(REPO_ROOT)
                              if population_path.is_relative_to(REPO_ROOT)
                              else population_path),
            "n_personas": len(people),
            "run": str(run_dir.relative_to(REPO_ROOT)
                       if run_dir.is_relative_to(REPO_ROOT) else run_dir),
            "run_resolved": str(run_dir.resolve().name),
            "n_moves": len(moves),
            "moves_error": moves_error,
            "zones_error": zones_error,
        },
        "findings": [f.as_dict() for f in findings],
        "verdicts": dict(Counter(f.verdict for f in findings)),
    }


def print_report(report: dict) -> None:
    inputs = report["inputs"]
    print("═" * 78)
    print("AUDIT DE PÉRIMÈTRE — population enquêtée EMC² contre population simulée")
    print(f"ticket 020 · {report['generated_at']}")
    print("═" * 78)
    print(f"population : {inputs['population']} ({inputs['n_personas']} personas)")
    print(f"run        : {inputs['run']} → {inputs['run_resolved']} "
          f"({inputs['n_moves']} trajets)")
    for key in ("moves_error", "zones_error"):
        if inputs.get(key):
            print(f"⚠ {inputs[key]}")
    print()
    for finding in report["findings"]:
        print("─" * 78)
        print(f"{finding['axe']} · {finding['titre']}   [{finding['verdict'].upper()}]")
        print(f"   enquête  : {finding['enquete']}")
        print(f"   simulé   : {finding['simule']}")
        print(f"   écart    : {finding['ecart']}")
        if finding["detail"]:
            for line in finding["detail"].split("\n"):
                print(f"   │ {line}" if line else "   │")
    recoupement = report.get("recoupement_microdonnees")
    if recoupement:
        print("─" * 78)
        print("RECOUPEMENT DU CADRAGE — chaque valeur recalculée depuis EMC²")
        if not recoupement.get("disponible"):
            print(f"   non disponible : {recoupement.get('raison')}")
        else:
            print(f"   {'grandeur':40s} {'recalculé':>12s} {'cadrage':>10s} {'écart':>8s}")
            for row in recoupement["controles"]:
                ecart = "—" if row["ecart"] is None else f"{row['ecart']:+.2f}"
                print(f"   {row['grandeur']:40s} {str(row['recalcule']):>12s} "
                      f"{str(row['cadrage']):>10s} {ecart:>8s}")
            parts = recoupement["parts_modales_recalculees"]
            print("   parts modales recalculées (pondéré COEP) :")
            for scope, values in parts.items():
                rendu = " · ".join(f"{k} {v:.1f} %" for k, v in values.items())
                print(f"      {scope:9s} {rendu}")
    print("─" * 78)
    print("Verdicts : " + " · ".join(f"{k} : {v}" for k, v in
                                     sorted(report["verdicts"].items())))
    if NON_MESURABLE in report["verdicts"]:
        print("⚠ Un axe non mesuré est un axe qui passe. Les axes ci-dessus marqués "
              "« non mesurable » ne sont PAS conformes : ils sont inconnus.")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--population", type=Path, default=DEFAULT_POPULATION)
    parser.add_argument("--run", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--trace", type=Path, default=None,
                        help="dossier d'archive (docs/traces/...) ; le JSON y est écrit")
    parser.add_argument("--json", action="store_true", help="ne sortir que le JSON")
    parser.add_argument("--recompute", action="store_true",
                        help="recalculer les valeurs de cadrage depuis les microdonnées "
                             "EMC² (accès restreint) et les confronter au YAML")
    args = parser.parse_args(argv)

    if not args.population.exists():
        raise SystemExit(f"population introuvable : {args.population}")
    recompute = recompute_from_microdata() if args.recompute else None
    report = run_audit(args.population, args.run, recompute)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print_report(report)

    if args.trace:
        args.trace.mkdir(parents=True, exist_ok=True)
        out = args.trace / "audit_perimetre.json"
        out.write_text(json.dumps(report, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        if not args.json:
            print(f"\nTrace archivée : {out}")

    # Code de sortie : 0 tout conforme, 2 au moins un axe à corriger, 3 au moins un
    # axe non mesurable. « À publier » ne fait pas échouer — c'est une limite assumée.
    if NON_MESURABLE in report["verdicts"]:
        return 3
    if A_CORRIGER in report["verdicts"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
