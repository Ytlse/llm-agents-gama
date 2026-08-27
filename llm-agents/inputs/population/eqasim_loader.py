"""
Population loader that reads the JSON output produced by the eqasim pipeline
(synthesis.population.llm_agents stage).

The file is expected at:
  {settings.data.eqasim_output_dir}/{settings.data.synthetic_file_prefix}population_*.json

If several files match, the one with the largest embedded count (highest N in
  toulouse_population_N.json) is used.
"""

import json
import os
import re
from typing import Optional
from loguru import logger

import numpy as np

from inputs.population.base import Filter, PopulationLoader
from models import Activity, BBox, Location, Person, PersonalIdentity, PersonState
from settings import settings
from utils import fake

from llm_module.core.population_reference import COURONNES, OUT_OF_PERIMETER
from llm_module.core.residence_zone import TRAIT_KEY as RESIDENCE_TRAIT_KEY

# Filtre d'ADMISSION de la population (ticket 026, étage 3).
#
# Il portait sur un RECTANGLE — l'emprise des arrêts GTFS élargie de 5 km —, qui ne
# correspond à aucune définition d'enquête : mesuré, ce rectangle ne contient que 221 des
# 453 communes du périmètre EMC² et 51 de ses 277 zones fines de 3ᵉ couronne. Une
# population conforme au périmètre y perdait la moitié de son territoire au chargement.
#
# Il porte désormais sur le PÉRIMÈTRE, lu sur le persona : le trait `residence_zone`
# (ticket 021) dit si le domicile est dans l'une des quatre couronnes de l'enquête ou
# `hors périmètre`. Aucune géométrie au chargement, et la définition est celle de
# l'enquête, pas celle du réseau TC.
#
# ⚠ Le cadre de TIRAGE peut être plus étroit que le périmètre (version Haute-Garonne du
# ticket 026 : 346 communes sur 453). Ce filtre reste sur les 453 : graver la limitation
# du cadre dans le runtime obligerait à la déterrer quand le cadre s'élargira.
_ADMITTED_ZONES = frozenset(COURONNES)


def perimeter_verdict(person, bbox: Optional[BBox]) -> tuple[bool, str]:
    """`(admis, motif de rejet)` — le motif est vide quand la personne est admise.

    Trois cas, et le troisième est le seul qui retombe sur le rectangle :

    - trait présent et dans une couronne → **admis**, où que soit la bbox ;
    - trait présent et `hors périmètre` → **rejeté** : le domicile est connu et il est
      hors des 453 communes de l'enquête, il n'a aucune cible par zone ;
    - trait absent (population générée avant le ticket 021) → repli sur la bbox, et
      l'appelant lève une alarme : le périmètre n'est alors PAS garanti.
    """
    home = person.identity.home
    if home is None or home.lon is None or home.lat is None:
        return False, "sans domicile"

    zone = (person.identity.traits_json or {}).get(RESIDENCE_TRAIT_KEY)
    if zone:
        if zone in _ADMITTED_ZONES:
            return True, ""
        return False, OUT_OF_PERIMETER if zone == OUT_OF_PERIMETER else f"zone inconnue ({zone})"

    if bbox is None:
        return True, ""
    inside = (bbox.min_lon <= home.lon <= bbox.max_lon
              and bbox.min_lat <= home.lat <= bbox.max_lat)
    return (inside, "" if inside else "hors bbox (trait absent)")


def _apply_perimeter_filter(people: list, bbox: Optional[BBox], source: str) -> list:
    """Filtre, compte, et ALARME si le périmètre n'a pas pu être vérifié."""
    from collections import Counter

    motifs: Counter = Counter()
    sans_trait = 0
    retenus = []
    for person in people:
        if not (person.identity.traits_json or {}).get(RESIDENCE_TRAIT_KEY):
            sans_trait += 1
        admis, motif = perimeter_verdict(person, bbox)
        if admis:
            retenus.append(person)
        else:
            motifs[motif] += 1

    detail = ", ".join(f"{n} {m}" for m, n in motifs.most_common()) or "aucun rejet"
    logger.info(f"[{source}] filtre de périmètre : {len(people)} → {len(retenus)} "
                f"({detail})")
    if sans_trait:
        # Front montant volontairement absent : ce cas est un état de la population, pas
        # un événement répété. Une population non enrichie doit se voir à chaque
        # chargement, sinon on croit filtrer sur le périmètre alors qu'on filtre sur un
        # rectangle.
        logger.error(
            f"[ALARME] {sans_trait}/{len(people)} persona(s) sans trait "
            f"`{RESIDENCE_TRAIT_KEY}` : le périmètre d'enquête n'est PAS garanti pour "
            f"eux, le filtre retombe sur la bbox du réseau TC. Corrigez la population "
            f"avec `make residence-zone` (ticket 021)."
        )
    return retenus

def _generate_name(gender: str) -> str:
    if gender == "Male":
        return fake.name_male()
    elif gender == "Female":
        return fake.name_female()
    return fake.name()


class EqasimJSONPopulationLoader(PopulationLoader):
    def __init__(self, filters: Optional[list[Filter]] = None):
        self.filters = filters or []

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _find_population_file(output_dir: str, prefix: str) -> str:
        pattern = re.compile(rf"^{re.escape(prefix)}population_(\d+)\.json$")
        candidates = []
        for name in os.listdir(output_dir):
            m = pattern.match(name)
            if m:
                candidates.append((int(m.group(1)), os.path.join(output_dir, name)))
        if not candidates:
            raise FileNotFoundError(
                f"No eqasim population JSON found in {output_dir!r} "
                f"(expected prefix {prefix!r}population_N.json)"
            )
        # Pick the file with the most people
        candidates.sort(reverse=True)
        return candidates[0][1]

    @staticmethod
    def _parse_activity(act: dict) -> Activity:
        loc = act.get("location")
        scheduled_start_time = act.get("scheduled_start_time")
        if act.get("scheduled_start_time") is None:
            scheduled_start_time = act["start_time"] - 15 * 60
        return Activity(
            id=act["id"],
            scheduled_start_time=scheduled_start_time,
            start_time=float(act["start_time"]),
            end_time=float(act["end_time"]),
            purpose=act["purpose"],
            location=Location(lon=loc["lon"], lat=loc["lat"], public_transport=loc.get("public_transport")) if loc and loc.get("lon") is not None else None,
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def load_population(self, max_size: int, bbox: Optional[BBox] = None) -> list[Person]:
        output_dir = settings.data.eqasim_output_dir
        prefix = settings.data.synthetic_file_prefix

        json_file = self._find_population_file(output_dir, prefix)
        print(f"[EqasimJSONPopulationLoader] Loading from {json_file}")

        with open(json_file, encoding="utf-8") as f:
            raw = json.load(f)

        people: list[Person] = []
        for entry in raw:
            identity_data = entry["identity"]

            activities = [
                self._parse_activity(act)
                for act in identity_data.get("activities", [])
            ]

            home_raw = identity_data.get("home")
            home = Location(lon=home_raw["lon"], lat=home_raw["lat"], public_transport=home_raw.get("public_transport")) if home_raw and home_raw.get("lon") is not None else None

            state_raw = entry.get("state", {})
            state = PersonState(
                last_location=None,
                last_activity_index=state_raw.get("last_activity_index", 0),
            )

            traits_json = identity_data["traits_json"]
            name = _generate_name(traits_json.get("gender", ""))
            traits_json["name"] = name

            person = Person(
                person_id=entry["person_id"],
                identity=PersonalIdentity(
                    name=name,
                    traits_json=traits_json,
                    home=home,
                    activities=activities,
                ),
                state=state,
                is_llm_based=entry.get("is_llm_based", True),
            )
            people.append(person)

        total_parsed = len(people)
        print(f"[EqasimJSONPopulationLoader] Parsed {total_parsed} people from JSON")

        # Filtre d'admission : le PÉRIMÈTRE d'enquête, plus le rectangle du réseau TC.
        people = _apply_perimeter_filter(people, bbox, "EqasimJSONPopulationLoader")

        # # Quality filter: at least 3 activities, at least one work/education trip
        # before_quality = len(people)
        # no_work_edu = [
        #     p for p in people
        #     if not any(a.purpose in ("work", "education") for a in (p.identity.activities or []))
        # ]
        # too_few_acts = [
        #     p for p in people
        #     if len(p.identity.activities or []) <= 3
        #     and any(a.purpose in ("work", "education") for a in (p.identity.activities or []))
        # ]
        # people = [
        #     p for p in people
        #     if len(p.identity.activities or []) > 0
        #     and any(a.purpose in ("work", "education") for a in (p.identity.activities or []))
        # ]
        # print(
        #     f"[EqasimJSONPopulationLoader] Quality filter: {before_quality} → {len(people)} "
        #     f"(dropped {len(no_work_edu)} without work/education, {len(too_few_acts)} with ≤3 activities)"
        # )
        # for p in range(len(no_work_edu)):
        #     if (p < 5):  # print up to 5 examples
        #         print(f"  - Person {no_work_edu[p]} dropped: no work/education activities")
        # for p in range(len(too_few_acts)):
        #     if (p < 5):  # print up to 5 examples
        #         print(f"  - Person {too_few_acts[p]} dropped: only {len(too_few_acts[p].identity.activities or [])} activities")

        # Additional caller-supplied filters (e.g. PersonCloseToTheStopFilter)
        for f in self.filters:
            before = len(people)
            people = [p for p in people if f.is_valid(p)]
            print(
                f"[EqasimJSONPopulationLoader] Filter {f.__class__.__name__}: "
                f"{before} → {len(people)}"
            )

        if max_size and max_size < len(people):
            people = list(np.random.choice(people, max_size, replace=False))

        print(f"[EqasimJSONPopulationLoader] Loaded {len(people)} people")
        return people

    def load_population_from_data(self, raw: list, max_size: int, bbox: Optional[BBox] = None) -> list[Person]:
        """Parse pre-loaded eqasim JSON entries into Person objects (same logic as load_population)."""
        people: list[Person] = []
        for entry in raw:
            identity_data = entry["identity"]
            activities = [
                self._parse_activity(act)
                for act in identity_data.get("activities", [])
            ]
            home_raw = identity_data.get("home")
            home = Location(
                lon=home_raw["lon"], lat=home_raw["lat"],
                public_transport=home_raw.get("public_transport"),
            ) if home_raw and home_raw.get("lon") is not None else None
            state_raw = entry.get("state", {})
            state = PersonState(
                last_location=None,
                last_activity_index=state_raw.get("last_activity_index", 0),
            )
            traits_json = identity_data["traits_json"]
            name = traits_json.get("name") or _generate_name(traits_json.get("gender", ""))
            traits_json["name"] = name
            person = Person(
                person_id=entry["person_id"],
                identity=PersonalIdentity(name=name, traits_json=traits_json, home=home, activities=activities),
                state=state,
                is_llm_based=entry.get("is_llm_based", True),
            )
            people.append(person)

        people = _apply_perimeter_filter(people, bbox, "EqasimJSONPopulationLoader/cache")

        if max_size and max_size < len(people):
            people = list(np.random.choice(people, max_size, replace=False))

        print(f"[EqasimJSONPopulationLoader] Loaded {len(people)} people from pre-loaded data")
        return people
