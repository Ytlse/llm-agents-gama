"""enrich_equipment.py — Poser l'abonnement TC et le permis appris sur EMC² (lot 2).

Voie 1 des [tickets 016](../../../docs/tickets/ticket_016_abonnement_tc_progedo.md) et
[017](../../../docs/tickets/ticket_017_permis_progedo.md) : on relit un fichier de
population, on réécrit deux champs de `traits_json`, et on le sauve. Aucune régénération,
applicable aux populations existantes.

Les deux traits sont traités par **un seul script** parce que les tickets écrivent que
leurs lots 1 et 2 sont communs, et parce que l'ordre entre eux et `car_availability`
est un piège qu'un seul point d'entrée ferme :

    has_pt_subscription   ← tirage Bernoulli de la loi pt_subscription.json
    has_driving_license   ← tirage Bernoulli de la loi driving_license.json
    car_availability      ← DÉRIVE du nombre de permis du ménage : elle est PÉRIMÉE
                            dès que la ligne précédente s'exécute

⚠ **Ce script ne recalcule pas `car_availability`, et c'est délibéré.** La règle vit déjà
dans `fix_minor_traits.py` (règle 4, majeurs seulement, ticket 008 A1.a), qui est
**idempotent** — la recopier ici en ferait deux définitions à tenir d'accord. Le notebook
de génération rejoue donc `fix_minor_traits` **après** cet enrichissement, et ce script
échoue bruyamment en `--check` si les permis qu'il vient de poser ne sont plus cohérents
avec le `car_availability` du fichier. Un `car_availability` calculé sur les anciens permis
ne se voit nulle part : c'est l'avertissement exact du ticket 017.

## Ce qui est imputé, et ce qui ne l'est pas

Les traits restent des **booléens**, comme aujourd'hui : ils sont lus par la politique de
choix modal, par le narratif du persona et par la page de synthèse, et les rendre nullables
casserait trois consommateurs pour rien. En revanche le **repli est explicite et compté** :

| Niveau | Quand | Ce qui est servi |
|---|---|---|
| `zone` | domicile dans la couche, zone à ménages enquêtés | densité et distance de la zone |
| `zone_sans_densite` | domicile dans la couche, zone sans ménage enquêté (81 sur 785) | distance de la zone, densité médiane du périmètre |
| `perimetre` | domicile hors de la couche | distance **calculée** depuis l'hypercentre publié, densité médiane |

Le niveau `perimetre` ne met **jamais** la distance à zéro : ce serait poser le domicile à
l'hypercentre, c'est-à-dire imputer la variable la plus discriminante de la loi par sa
valeur la plus favorable aux transports collectifs. Elle est calculée en Lambert-93 depuis
`feature_spec.json`, le même hypercentre que le volet 3 de la page de synthèse.

Sous l'âge de champ d'un trait, aucune propension n'est évaluée : le permis vaut `false`
sous 18 ans par construction (plancher légal, pas paramètre de modèle) et le compte sort
en `sous_age_champ`.

## Déterminisme

Bernoulli de la propension, clé `(adresse du domicile, identifiant de personne, sel
versionné)`. Deux exécutions, deux machines, deux moments donnent le même résultat. Le
tirage porte sur la **personne** et non sur l'adresse — un abonnement est nominatif, deux
colocataires n'ont aucune raison de partager le leur.

Usage :
    python -m scripts.data.population.enrich_equipment data/population/toulouse_population_1000.json
    python -m scripts.data.population.enrich_equipment data/population/*.json --dry-run
    python -m scripts.data.population.enrich_equipment data/population/toulouse_population_1000.json --check
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

from llm_module.core.equipment_propensity import (
    DRIVING_LICENSE,
    PT_SUBSCRIPTION,
    PropensityLaw,
    TraitSpec,
)

REPO_ROOT = Path(__file__).resolve().parents[3]

EXIT_OK = 0
EXIT_RESOURCE_MISSING = 1
EXIT_TARGET_MISSED = 2
EXIT_NOT_MEASURABLE = 3
# Le code 4 n'est PAS un échec du trait, et la distinction est le cœur de la recette :
# les portes d'ensemble passent, mais une STRATE s'écarte parce que la population n'a
# pas la composition de l'enquête à l'intérieur de cette strate. Ça se corrige dans le
# TIRAGE, pas dans l'enrichissement — même vocabulaire que l'axe A9 du ticket 020, que
# le notebook sait déjà lire comme non bloquant.
#
# La règle qui les sépare : un écart d'ENSEMBLE ou un défaut de couverture accusent la
# loi ou la pose (code 2) ; un écart de STRATE seul, ensemble tenu, accuse la
# composition de la population (code 4). Les confondre ferait bloquer la chaîne de
# génération sur un défaut qu'aucun enrichissement ne peut réparer.
EXIT_COMPOSITION_GAP = 4

# Couverture minimale : en dessous, la population n'est pas exploitable et aucune cible
# n'a de sens. Un trait absent partout ne « réussit » pas la recette, il l'invalide.
MIN_COVERAGE = 0.95

# Tolérances de recette. Celles des tickets, augmentées du bruit d'échantillonnage de la
# strate — une population de 1 000 agents porte ~50 personnes par modalité d'occupation,
# soit ~7 points d'écart-type sur une part à 50 %.
TOLERANCE_OVERALL_PT = 6.0
TOLERANCE_STRATUM_PT = 12.0

# Sous cet effectif, une strate ne tranche rien : elle est affichée, pas opposée.
THIN_STRATUM = 20

SPECS = (PT_SUBSCRIPTION, DRIVING_LICENSE)

# Cibles opposables. Celles des tickets, avec la cible « Étudiant » de l'abonnement
# RESTATÉE de 74,3 à 72,2 % : le ticket mesure sur `P9 == 4` seul, tandis que le recodage
# du dépôt range aussi l'alternance/stage (`P9 == 3`, 146 personnes, 56,7 % d'abonnés)
# dans « Étudiant ». C'est la définition du dépôt qui doit gagner, puisque c'est celle que
# le persona porte — opposer 74,3 % noterait la loi sur une strate qu'elle ne voit pas.
TARGETS = {
    "has_pt_subscription": {
        "_overall": 25.8,
        "Étudiant": 72.2,
        "Scolaire (jusqu'au Bac)": 33.3,
        "Chômeur/recherche d'emploi": 28.8,
        "Personne au foyer": 24.0,
        "Travail à temps partiel": 21.5,
        "Retraité": 17.7,
        "Travail à plein temps": 14.8,
    },
    "has_driving_license": {
        "_overall": 85.9,
        "Travail à plein temps": 94.8,
        "Retraité": 92.6,
        "Travail à temps partiel": 86.5,
        "Chômeur/recherche d'emploi": 69.4,
        "Personne au foyer": 63.9,
        "Étudiant": 59.2,
    },
}

# L'écart qui est le cœur du ticket 016 : il tient le SIGNE et l'AMPLITUDE, et c'est le
# critère le plus discriminant — la recopie ENTD le mettait à +5,7 pt contre +54,5
# observés (72,2 − 17,7), soit un facteur 10 d'écrasement.
STUDENT_MINUS_RETIRED_TARGET = 54.5
STUDENT_MINUS_RETIRED_MIN = 25.0


def _home(person: dict) -> tuple[Optional[float], Optional[float]]:
    home = (person.get("identity") or {}).get("home") or {}
    return home.get("lat"), home.get("lon")


def _hypercenter(spec_path: Path) -> tuple[float, float]:
    """Hypercentre en Lambert-93, lu dans le spec du modèle.

    Le même que celui du volet 3 de la page de synthèse et des couronnes de résidence :
    trois consommateurs qui mesureraient depuis trois centres différents produiraient
    trois distances qui auraient l'air comparables.
    """
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    center = spec["geo_reference"]["hypercenter"]
    return float(center["x_l93"]), float(center["y_l93"])


def enrich(population: list[dict], laws: dict[str, PropensityLaw], resolver,
           hypercenter: tuple[float, float]) -> Counter:
    """Pose les deux traits en place. Renvoie les décomptes, replis compris."""
    from pyproj import Transformer

    to_l93 = Transformer.from_crs("EPSG:4326", "EPSG:2154", always_xy=True)
    cx, cy = hypercenter
    counts: Counter = Counter()

    for person in population:
        identity = person.get("identity") or {}
        traits = identity.get("traits_json")
        if not isinstance(traits, dict):
            counts["sans_traits"] += 1
            continue
        lat, lon = _home(person)

        # Géographie du domicile, avec son niveau de repli.
        density: Optional[float] = None
        dist_center: Optional[float] = None
        level = "perimetre"
        zone = resolver.resolve(float(lat), float(lon)) if (
            lat is not None and lon is not None) else None
        if zone is not None:
            dist_center = zone.dist_center_km
            density = zone.density_hh_km2
            level = "zone" if density is not None else "zone_sans_densite"
        elif lat is not None and lon is not None:
            # Hors couche : la distance se CALCULE, elle ne se met pas à zéro.
            x, y = to_l93.transform(float(lon), float(lat))
            dist_center = math.hypot(x - cx, y - cy) / 1000.0
        counts[f"repli::{level}"] += 1

        for spec in SPECS:
            law = laws[spec.key]
            value, reason = law.value(
                traits.get("age"), traits.get("gender"),
                traits.get("main_occupation"), traits.get("number_of_cars"),
                density, dist_center, lat, lon, person.get("person_id"))
            if traits.get(spec.key) != value:
                counts[f"{spec.key}::modifie"] += 1
            traits[spec.key] = value
            counts[f"{spec.key}::{reason}"] += 1
            if value:
                counts[f"{spec.key}::vrai"] += 1
        counts["personnes"] += 1
    return counts


# ── Mesure ───────────────────────────────────────────────────────────────────

def measure(population: list[dict], spec: TraitSpec) -> dict:
    """Part du trait, en tout et par occupation, sur le champ d'âge du trait."""
    total = 0
    held = 0
    by_occupation: dict[str, list[int]] = {}
    for person in population:
        traits = ((person.get("identity") or {}).get("traits_json") or {})
        age = traits.get("age")
        if age is None or float(age) < spec.min_age:
            continue
        value = traits.get(spec.key)
        if not isinstance(value, bool):
            continue
        total += 1
        held += int(value)
        occupation = traits.get("main_occupation") or "(inconnue)"
        bucket = by_occupation.setdefault(occupation, [0, 0])
        bucket[0] += 1
        bucket[1] += int(value)
    return {
        "n": total,
        "pct": (100.0 * held / total) if total else None,
        "by_occupation": {
            occupation: {"n": n, "pct": 100.0 * k / n}
            for occupation, (n, k) in sorted(by_occupation.items())
        },
    }


def coverage(population: list[dict], spec: TraitSpec) -> float:
    eligible = 0
    typed = 0
    for person in population:
        traits = ((person.get("identity") or {}).get("traits_json") or {})
        age = traits.get("age")
        if age is None or float(age) < spec.min_age:
            continue
        eligible += 1
        typed += int(isinstance(traits.get(spec.key), bool))
    return (typed / eligible) if eligible else 0.0


def car_availability_is_stale(population: list[dict]) -> Optional[int]:
    """Nombre de ménages dont `car_availability` ne dérive plus des permis posés.

    On applique la règle d'eqasim — `none` si aucune voiture, `all` si voitures ≥ permis
    des majeurs, `some` sinon — et on compte les désaccords. Ce script ne corrige pas :
    la règle appartient à `fix_minor_traits`, et deux implémentations dériveraient.
    """
    households: dict[tuple, dict] = {}
    for person in population:
        identity = person.get("identity") or {}
        traits = identity.get("traits_json") or {}
        home = identity.get("home") or {}
        lat, lon = home.get("lat"), home.get("lon")
        if lat is None or lon is None:
            continue
        key = (round(float(lat), 7), round(float(lon), 7))
        entry = households.setdefault(key, {"cars": 0, "licences": 0, "labels": set()})
        entry["cars"] = max(entry["cars"], int(traits.get("number_of_cars") or 0))
        if traits.get("has_driving_license") and (traits.get("age") or 0) >= 18:
            entry["licences"] += 1
        if traits.get("car_availability"):
            entry["labels"].add(traits["car_availability"])

    stale = 0
    for entry in households.values():
        expected = ("none" if entry["cars"] == 0
                    else ("all" if entry["cars"] >= entry["licences"] else "some"))
        if entry["labels"] and entry["labels"] != {expected}:
            stale += 1
    return stale


def report(counts: Counter, population: list[dict]) -> list[str]:
    lines = [f"Personnes traitées : {counts['personnes']}"]
    replis = {k.split("::", 1)[1]: v for k, v in counts.items()
              if k.startswith("repli::")}
    lines.append("  Niveau de repli géographique : " + ", ".join(
        f"{k} {v}" for k, v in sorted(replis.items(), key=lambda kv: -kv[1])))
    for spec in SPECS:
        m = measure(population, spec)
        pct = f"{m['pct']:.1f} %" if m["pct"] is not None else "—"
        lines.append(f"  {spec.key} : {pct} sur {m['n']} personnes du champ "
                     f"({counts[f'{spec.key}::modifie']} valeurs modifiées, "
                     f"{counts[f'{spec.key}::sous_age_champ']} sous l'âge de champ)")
        for occupation, stat in m["by_occupation"].items():
            flag = "  ⚠ strate mince" if stat["n"] < THIN_STRATUM else ""
            target = TARGETS[spec.key].get(occupation)
            target_txt = f" | cible {target:5.1f}" if target is not None else ""
            lines.append(f"      {occupation:28s} n={stat['n']:4d} "
                         f"{stat['pct']:5.1f} %{target_txt}{flag}")
    return lines


def check(population: list[dict]) -> tuple[bool, bool, list[str], bool]:
    """Confronte aux cibles.

    Renvoie ``(ensemble_ok, strates_ok, lignes, mesurable)`` — deux booléens et non
    un seul, parce que les deux défauts ne se réparent pas au même endroit.
    """
    lines: list[str] = []
    ok = True          # portes d'ensemble : couverture, part globale, garde-fous
    strata_ok = True   # portes de strate : composition de la population
    measurable = True

    for spec in SPECS:
        cov = coverage(population, spec)
        if cov < MIN_COVERAGE:
            lines.append(f"  ✗ {spec.key} : couverture {100 * cov:.1f} % "
                         f"< {100 * MIN_COVERAGE:.0f} % — trait absent, la recette est "
                         f"INVALIDE, pas réussie")
            ok = False
            continue
        m = measure(population, spec)
        targets = TARGETS[spec.key]
        gap = m["pct"] - targets["_overall"]
        verdict = "✓" if abs(gap) <= TOLERANCE_OVERALL_PT else "✗"
        ok &= abs(gap) <= TOLERANCE_OVERALL_PT
        lines.append(f"  {verdict} {spec.key} ensemble : {m['pct']:.1f} % contre "
                     f"{targets['_overall']} % attendus (écart {gap:+.1f}, "
                     f"tolérance ± {TOLERANCE_OVERALL_PT})")
        for occupation, target in targets.items():
            if occupation == "_overall":
                continue
            stat = m["by_occupation"].get(occupation)
            if stat is None:
                continue
            if stat["n"] < THIN_STRATUM:
                lines.append(f"      ~ {occupation:28s} n={stat['n']:3d} "
                             f"{stat['pct']:5.1f} % — strate mince, non opposée")
                continue
            g = stat["pct"] - target
            v = "✓" if abs(g) <= TOLERANCE_STRATUM_PT else "✗"
            strata_ok &= abs(g) <= TOLERANCE_STRATUM_PT
            lines.append(f"      {v} {occupation:28s} n={stat['n']:3d} "
                         f"{stat['pct']:5.1f} % contre {target:5.1f} (écart {g:+5.1f})")

    # Le critère le plus discriminant du ticket 016 : l'écart étudiant − retraité.
    pt = measure(population, PT_SUBSCRIPTION)["by_occupation"]
    student = pt.get("Étudiant")
    retired = pt.get("Retraité")
    if student and retired and min(student["n"], retired["n"]) >= THIN_STRATUM:
        spread = student["pct"] - retired["pct"]
        v = "✓" if spread >= STUDENT_MINUS_RETIRED_MIN else "✗"
        ok &= spread >= STUDENT_MINUS_RETIRED_MIN
        lines.append(f"  {v} écart étudiant − retraité : {spread:+.1f} pt "
                     f"(≥ {STUDENT_MINUS_RETIRED_MIN} exigé, "
                     f"{STUDENT_MINUS_RETIRED_TARGET} observé dans l'enquête) — "
                     f"c'est le critère que la recopie ENTD écrasait d'un facteur 10")
    else:
        lines.append("  ~ écart étudiant − retraité : strates trop minces pour "
                     "trancher")
        measurable = False

    stale = car_availability_is_stale(population)
    if stale:
        lines.append(f"  ✗ car_availability périmé sur {stale} ménage(s) : il dérive du "
                     f"nombre de permis, que ce script vient de réécrire. Rejouez "
                     f"`python -m scripts.data.population.fix_minor_traits <fichier>` "
                     f"(idempotent, règle 4).")
        ok = False
    else:
        lines.append("  ✓ car_availability cohérent avec les permis posés")
    return ok, strata_ok, lines, measurable


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("population", type=Path, nargs="+",
                        help="fichiers de population à enrichir en place")
    parser.add_argument("--zones", type=Path, default=None,
                        help="couche de zones fines (défaut : llm_module/data/zf_zones.gpkg)")
    parser.add_argument("--spec", type=Path, default=None,
                        help="spec du modèle, pour l'hypercentre")
    parser.add_argument("--dry-run", action="store_true",
                        help="mesure et affiche, sans réécrire les fichiers")
    parser.add_argument("--check", action="store_true",
                        help="confronte aux cibles des tickets 016/017 et sort en échec")
    args = parser.parse_args(argv)

    zones = args.zones or REPO_ROOT / "llm_module" / "data" / "zf_zones.gpkg"
    spec_path = args.spec or REPO_ROOT / "scripts" / "progedo_logit" / "feature_spec.json"
    if not zones.exists():
        print(f"[erreur] Couche de zones absente : {zones} — `make zones`",
              file=sys.stderr)
        return EXIT_RESOURCE_MISSING
    if not spec_path.exists():
        print(f"[erreur] Spec du modèle absent : {spec_path} — `make policy`",
              file=sys.stderr)
        return EXIT_RESOURCE_MISSING

    try:
        laws = {spec.key: PropensityLaw.load(spec) for spec in SPECS}
    except FileNotFoundError as exc:
        print(f"[erreur] {exc}", file=sys.stderr)
        return EXIT_RESOURCE_MISSING

    from llm_module.core.zone_resolver import ZoneResolver
    resolver = ZoneResolver.load(zones, feature_spec=spec_path)
    hypercenter = _hypercenter(spec_path)
    for spec in SPECS:
        law = laws[spec.key]
        print(f"Loi {spec.key} : {len(law.features)} variables, paliers "
              f"{'retenus' if any(f in law.features for f in ('under_26', 'age_62p', 'age_65p')) else 'retirés'}"
              f", générée le {law.meta.get('generated_at', '?')}")

    status = EXIT_OK
    for path in args.population:
        if not path.exists():
            print(f"[erreur] Population introuvable : {path}", file=sys.stderr)
            status = max(status, EXIT_RESOURCE_MISSING)
            continue
        print(f"\n── {path} " + "─" * max(0, 50 - len(str(path))))
        raw = json.loads(path.read_text(encoding="utf-8"))
        population = raw if isinstance(raw, list) else raw.get("agents", raw)
        counts = enrich(population, laws, resolver, hypercenter)
        for line in report(counts, population):
            print(line)

        if not args.dry_run:
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            tmp.replace(path)
            print(f"  Écrit : {path}")
        else:
            print("  --dry-run : fichier inchangé")

        if args.check:
            ok, strata_ok, lines, measurable = check(population)
            print("  Recette (tickets 016 / 017) :")
            for line in lines:
                print(line)
            if not ok:
                status = max(status, EXIT_TARGET_MISSED)
            elif not strata_ok:
                print(f"\n  → code {EXIT_COMPOSITION_GAP} : les portes d'ensemble "
                      f"passent, une strate s'écarte. La loi pose le trait "
                      f"correctement ; c'est la COMPOSITION de la population dans cette "
                      f"strate qui diffère de l'enquête. Ça se corrige dans le tirage, "
                      f"pas ici.")
                status = max(status, EXIT_COMPOSITION_GAP)
            elif not measurable:
                print(f"\n  → code {EXIT_NOT_MEASURABLE} : enrichi mais NON VALIDÉ — "
                      f"population trop petite pour trancher")
                status = max(status, EXIT_NOT_MEASURABLE)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
