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

import numpy as np

from inputs.population.base import Filter, PopulationLoader
from models import Activity, BBox, Location, Person, PersonalIdentity, PersonState
from settings import settings
from utils import fake


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
        return Activity(
            id=act["id"],
            scheduled_start_time=act.get("scheduled_start_time"),
            start_time=float(act["start_time"]),
            end_time=float(act["end_time"]),
            purpose=act["purpose"],
            location=Location(lon=loc["lon"], lat=loc["lat"]) if loc and loc.get("lon") is not None else None,
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
                if act.get("purpose") != "other"
            ]

            home_raw = identity_data.get("home")
            home = Location(lon=home_raw["lon"], lat=home_raw["lat"]) if home_raw and home_raw.get("lon") is not None else None

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
                is_llm_based=entry.get("is_llm_based", False),
            )
            people.append(person)

        total_parsed = len(people)
        print(f"[EqasimJSONPopulationLoader] Parsed {total_parsed} people from JSON")

        # Bbox filter: keep only people whose home is inside the bounding box
        if bbox is not None:
            no_home = [p for p in people if not p.identity.home]
            outside = [
                p for p in people
                if p.identity.home and not (
                    bbox.min_lon <= p.identity.home.lon <= bbox.max_lon and
                    bbox.min_lat <= p.identity.home.lat <= bbox.max_lat
                )
            ]
            people = [
                p for p in people
                if p.identity.home and
                   bbox.min_lon <= p.identity.home.lon <= bbox.max_lon and
                   bbox.min_lat <= p.identity.home.lat <= bbox.max_lat
            ]
            print(
                f"[EqasimJSONPopulationLoader] BBox filter: {total_parsed} → {len(people)} "
                f"(dropped {len(no_home)} without home, {len(outside)} outside bbox "
                f"lon=[{bbox.min_lon:.4f},{bbox.max_lon:.4f}] lat=[{bbox.min_lat:.4f},{bbox.max_lat:.4f}])"
            )

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
