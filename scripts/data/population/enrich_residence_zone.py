"""enrich_residence_zone.py — La couronne de résidence, posée sur le persona (ticket 021).

Relit une population générée, résout chaque domicile en zone fine, et écrit dans
`traits_json` :

- `residence_zone` — la couronne au sens de l'enquête EMC² (`Toulouse`, `1ere couronne`,
  `2eme couronne`, `3eme couronne`), ou `hors périmètre` ;
- `residence_commune` et `residence_insee` — la commune du domicile, qui rend le
  classement auditable et survit à un redécoupage des couronnes.

**Ce trait est OBSERVÉ, pas imputé, et c'est ce qui le distingue de ses deux voisins.**
`housing_type` est tiré dans une loi, `personal_bike` en trois étages ; ici il n'y a ni
tirage, ni hachage, ni sel, ni loi. Un domicile est dans une commune ou il n'y est pas.
Deux conséquences : le script est idempotent au sens fort — deux exécutions, deux machines,
deux moments donnent le même octet — et sa validation ne porte pas sur une distribution
mais sur un ACCORD (cf. `--check`).

**Pourquoi ce post-traitement existe.** La couronne était devinée au runtime par la
distance du domicile à l'hypercentre (`geo_reference.residence_zone`, 8 / 20 / 40 km). Ce
n'est pas le découpage de l'enquête, qui procède par **liste de communes** : le ticket 020 a
mesuré 24,4 % de personas mal classés, 66 « faux Toulousains » habitant Blagnac ou Balma, et
un stratum « 3ᵉ couronne » dont 76 % des habitants n'étaient même pas dans le périmètre
d'enquête. Poser la couronne sur le persona corrige les deux écarts **sans toucher au
runtime** : le classement métrique reste pour le temps terminal, qui classe des points
quelconques et dont les lois sont stratifiées avec lui.

**Trois valeurs, trois significations à ne pas confondre.**

- une couronne : le domicile est dans le périmètre, et voilà sa zone ;
- `hors périmètre` : le domicile est connu et il est **dehors**. Ce n'est pas une couronne
  (le confondre avec la 3ᵉ est l'écart A4), il n'a aucune cible EMC², et sa masse se compte
  au lieu de se diluer ;
- **trait absent** : le domicile n'a pas de coordonnées. On ne sait rien — ni dedans, ni
  dehors — et écrire `hors périmètre` serait une affirmation que rien ne soutient.

⚠ **NE JAMAIS enrichir en place une population épinglée par un manifeste de jeu gelé.**
`prompt_calibration/calibration_datasets/v5` à `v8` épinglent le sha256 de
`experiments/archive/2026-08-19_14_36/population_1000.json` : la réécrire casse quatre jeux
d'un coup. Utiliser `--out` (ou `--dry-run`) pour ces populations. Le trait n'entrant ni
dans le narratif du persona (liste blanche de `_build_profile_narrative`) ni dans la clé du
cache de décisions (options + météo + agent/activité/créneau), l'ajouter ne déplace aucune
décision — c'est toute la raison d'être de cette voie.

`--check` vérifie ce que l'enrichissement MAÎTRISE, et rien d'autre :

1. **couverture** — tout persona ayant des coordonnées porte une valeur décidée ;
2. **accord avec la référence géométrique** — la couronne écrite (obtenue par le CODE de
   zone fine) est recalculée par APPARTENANCE aux polygones de couronnes, et les deux
   doivent coïncider à 100 %. C'est la porte du ticket 021, rejouée sur chaque population ;
3. **modalités** — rien hors `COURONNES ∪ {hors périmètre}` ;
4. **taux hors périmètre** — sous le seuil d'alarme de `zone_resolver` (15 %). Ce contrôle
   ne juge pas le tirage : il attrape une population qui n'est pas celle de ce périmètre.

L'écart au **cadrage** de population par couronne (36,4 / 34,1 / 14,2 / 15,4 %) est
rapporté mais **n'est pas une porte** : il mesure la surconcentration spatiale du tirage
(axe A9 du ticket 020), déclarée hors périmètre du ticket 021 et déjà chiffrée à 76,0 % en
cœur d'agglomération contre 70,5 %. En faire un échec serait poser une porte rouge dès le
premier jour pour une cause qu'on refuse de traiter ici. Il a son propre code de sortie,
pour qu'un appelant puisse le suivre sans le confondre avec un échec.

Codes de sortie de `--check` :
  0  toutes les portes passent
  1  ressource absente (`make zones`, `make communes-couronnes`)
  2  une porte ÉCHOUE — la population n'est pas exploitable pour le scoring par zone
  4  les portes passent, mais l'écart au cadrage dépasse la tolérance (A9, informatif)

Usage :
    python -m scripts.data.population.enrich_residence_zone data/population/toulouse_population_1000.json --check
    python -m scripts.data.population.enrich_residence_zone data/population/*.json --dry-run
    python -m scripts.data.population.enrich_residence_zone \\
      experiments/archive/2026-08-19_14_36/population_1000.json \\
      --out /tmp/population_1000.residence_zone.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

from llm_module.core.population_reference import (
    COURONNES, OUT_OF_PERIMETER, couronne_population_shares)
from llm_module.core.residence_zone import (
    COMMUNE_TRAIT_KEY,
    INSEE_TRAIT_KEY,
    TRAIT_KEY,
    CommunalZones,
    CouronneTable,
    ResidenceZoneError,
)

REPO_ROOT = Path(__file__).resolve().parents[3]

EXIT_OK = 0
EXIT_RESOURCE_MISSING = 1
EXIT_GATE_FAILED = 2
EXIT_FRAMING_GAP = 4

# Seuil d'alarme du taux hors périmètre. C'est celui de `zone_resolver.coverage()` : au-delà
# de 15 %, ce n'est plus une queue de distribution, c'est une population qui ne décrit pas
# le périmètre de l'enquête.
MAX_OUT_OF_PERIMETER_RATE = 0.15

# Tolérance, en points, sur la part de population de chaque couronne face au cadrage. Elle
# n'est PAS une porte (cf. le docstring) : elle décide seulement du code 4.
FRAMING_TOLERANCE_PT = 5.0


def people_of(population) -> list[dict]:
    if isinstance(population, list):
        return population
    for key in ("people", "personas", "persons"):
        if isinstance(population.get(key), list):
            return population[key]
    raise ResidenceZoneError(
        "structure de population inconnue : ni liste, ni clé `people`/`personas`.")


def home_of(person: dict) -> dict:
    return (person.get("identity") or {}).get("home") or {}


def traits_of(person: dict) -> dict:
    identity = person.get("identity")
    if not isinstance(identity, dict):
        raise ResidenceZoneError("persona sans bloc `identity` : population illisible.")
    traits = identity.get("traits_json")
    if not isinstance(traits, dict):
        traits = {}
        identity["traits_json"] = traits
    return traits


def enrich(population, table: CouronneTable, resolver) -> dict:
    """Pose le trait sur chaque persona. Rend les compteurs de la passe.

    Le classement passe par le CODE de zone fine, jamais par une géométrie : c'est le
    chemin que le runtime pourrait suivre, et `--check` le contrôle contre la géométrie.
    """
    counts: Counter = Counter()
    for person in people_of(population):
        traits = traits_of(person)
        home = home_of(person)
        lat, lon = home.get("lat"), home.get("lon")
        avant = traits.get(TRAIT_KEY)

        if lat is None or lon is None:
            # Ni dedans ni dehors : on ne sait pas. Le trait est retiré plutôt que laissé
            # à une valeur héritée qui ne serait plus rattachable à un domicile.
            for key in (TRAIT_KEY, COMMUNE_TRAIT_KEY, INSEE_TRAIT_KEY):
                traits.pop(key, None)
            counts["sans_domicile"] += 1
            continue

        zone = resolver.resolve(lat, lon)
        if zone is None:
            traits[TRAIT_KEY] = OUT_OF_PERIMETER
            # La commune d'un domicile hors couche n'est pas connue : elle ne s'invente pas.
            traits.pop(COMMUNE_TRAIT_KEY, None)
            traits.pop(INSEE_TRAIT_KEY, None)
            counts[OUT_OF_PERIMETER] += 1
        else:
            couronne = table.couronne_of_zf(zone.zf)
            if couronne is None:
                # Zone résolue mais absente de la table : la ressource et la couche ne
                # décrivent pas le même périmètre. On ne devine pas.
                for key in (TRAIT_KEY, COMMUNE_TRAIT_KEY, INSEE_TRAIT_KEY):
                    traits.pop(key, None)
                counts["zone_hors_table"] += 1
                continue
            traits[TRAIT_KEY] = couronne
            commune = table.commune_of_zf(zone.zf)
            if commune is not None:
                traits[INSEE_TRAIT_KEY], traits[COMMUNE_TRAIT_KEY] = commune
            counts[couronne] += 1

        if avant is not None and avant != traits.get(TRAIT_KEY):
            counts["valeur_changee"] += 1
    return dict(counts)


def audit(population, table: CouronneTable, zones: Optional[CommunalZones]) -> dict:
    """Recalcule, contrôle, et rend de quoi trancher — sans jamais réparer en silence."""
    people = people_of(population)
    written: Counter = Counter()
    desaccords: list[dict] = []
    hors_modalite: list[str] = []
    sans_valeur = 0
    metrique_divergent = 0

    from llm_module.core.geo_reference import residence_zone as classement_metrique

    for person in people:
        traits = traits_of(person)
        home = home_of(person)
        lat, lon = home.get("lat"), home.get("lon")
        valeur = traits.get(TRAIT_KEY)

        if lat is None or lon is None:
            continue
        if not valeur:
            sans_valeur += 1
            continue
        written[valeur] += 1
        if valeur not in COURONNES and valeur != OUT_OF_PERIMETER:
            hors_modalite.append(valeur)
            continue
        if zones is not None:
            par_geometrie = zones.classify(lat, lon)
            if par_geometrie != valeur:
                desaccords.append({"lat": lat, "lon": lon, "trait": valeur,
                                   "geometrie": par_geometrie})
        if classement_metrique(lat, lon) != valeur:
            metrique_divergent += 1

    localises = sum(1 for p in people
                    if home_of(p).get("lat") is not None
                    and home_of(p).get("lon") is not None)
    hors = written.get(OUT_OF_PERIMETER, 0)
    return {
        "n_personas": len(people),
        "n_localises": localises,
        "n_sans_valeur": sans_valeur,
        "written": dict(written),
        "hors_perimetre": hors,
        "taux_hors_perimetre": (hors / localises) if localises else 0.0,
        "desaccords_geometrie": desaccords,
        "hors_modalite": sorted(set(hors_modalite)),
        "divergence_metrique": metrique_divergent,
        "taux_divergence_metrique": (metrique_divergent / localises) if localises else 0.0,
    }


def framing_gap(measured: dict) -> tuple[dict, float]:
    """Parts de population par couronne contre le cadrage EMC², hors périmètre exclu.

    Les hors-périmètre n'ont aucune cible : les garder au dénominateur comparerait une
    part à une autre grandeur. Ils sont comptés à part, jamais dilués.
    """
    cible = couronne_population_shares()
    total = sum(measured.get(z, 0) for z in COURONNES)
    lignes = {}
    for zone in COURONNES:
        part = 100.0 * measured.get(zone, 0) / total if total else 0.0
        lignes[zone] = {"observe": part, "cible": cible[zone],
                        "ecart": part - cible[zone]}
    l1 = sum(abs(row["ecart"]) for row in lignes.values())
    return lignes, l1


def report(counts: dict, checks: dict) -> list[str]:
    """Affiche la passe et rend la liste des portes en échec (vide si tout passe)."""
    failures: list[str] = []

    print(f"  personas                : {checks['n_personas']}")
    print(f"  domiciles localisés     : {checks['n_localises']}")
    if counts.get("sans_domicile"):
        print(f"  sans coordonnées        : {counts['sans_domicile']} — trait absent, "
              f"ni dedans ni dehors")
    if counts.get("zone_hors_table"):
        print(f"  zone hors table         : {counts['zone_hors_table']}")
    if counts.get("valeur_changee"):
        print(f"  valeurs modifiées       : {counts['valeur_changee']}")

    for zone in (*COURONNES, OUT_OF_PERIMETER):
        n = checks["written"].get(zone, 0)
        part = 100.0 * n / checks["n_localises"] if checks["n_localises"] else 0.0
        print(f"    {zone:16s} {n:5d}  {part:5.1f} %")

    # Porte 1 — couverture.
    if checks["n_sans_valeur"]:
        failures.append(f"{checks['n_sans_valeur']} persona(s) localisé(s) sans valeur : "
                        f"la couverture doit être totale, un domicile connu se classe "
                        f"toujours (couronne ou hors périmètre)")

    # Porte 2 — accord avec la référence géométrique.
    desaccords = checks["desaccords_geometrie"]
    if desaccords:
        failures.append(
            f"{len(desaccords)} domicile(s) classé(s) différemment par le CODE de zone "
            f"fine et par l'APPARTENANCE géométrique, ex. {desaccords[:3]} — le chemin "
            f"par code n'est plus légitime, reprendre `make audit-couronnes`")
    else:
        print("  accord code ↔ géométrie : 100 %")

    # Porte 3 — modalités.
    if checks["hors_modalite"]:
        failures.append(f"modalités hors référentiel : {checks['hors_modalite']}")

    # Porte 4 — taux hors périmètre.
    taux = checks["taux_hors_perimetre"]
    print(f"  hors périmètre          : {taux * 100:.2f} % "
          f"(seuil d'alarme {MAX_OUT_OF_PERIMETER_RATE * 100:.0f} %)")
    if taux > MAX_OUT_OF_PERIMETER_RATE:
        failures.append(f"{taux * 100:.1f} % de domiciles hors périmètre : ce n'est plus "
                        f"une queue de distribution, c'est une population qui ne décrit "
                        f"pas le périmètre de l'enquête")

    # Information — ce que la correction change par rapport au classement métrique.
    print(f"  divergence / métrique   : {checks['divergence_metrique']} personas "
          f"({checks['taux_divergence_metrique'] * 100:.1f} %) auraient une autre couronne "
          f"par distance à l'hypercentre")
    return failures


def print_framing(checks: dict) -> bool:
    """Rapporte l'écart au cadrage. Rend `True` s'il dépasse la tolérance."""
    lignes, l1 = framing_gap(checks["written"])
    print("  cadrage de population (informatif — axe A9, hors périmètre du ticket 021) :")
    for zone, row in lignes.items():
        print(f"    {zone:16s} {row['observe']:5.1f} % contre {row['cible']:5.1f} % "
              f"→ {row['ecart']:+5.1f} pt")
    print(f"    L1 = {l1:.1f} pt, tolérance par couronne "
          f"± {FRAMING_TOLERANCE_PT:.0f} pt")
    return any(abs(row["ecart"]) > FRAMING_TOLERANCE_PT for row in lignes.values())


def destination(path: Path, out: Optional[Path], n_inputs: int) -> Path:
    if out is None:
        return path
    if n_inputs > 1 or out.is_dir():
        out.mkdir(parents=True, exist_ok=True)
        return out / path.name
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("population", type=Path, nargs="+",
                        help="Fichiers de population JSON (modifiés en place sauf --out)")
    parser.add_argument("--table", type=Path, default=None,
                        help="Table des couronnes (défaut : llm_module/data/)")
    parser.add_argument("--zones", type=Path, default=None,
                        help="Couche de zones fines (défaut : llm_module/data/)")
    parser.add_argument("--geojson", type=Path, default=None,
                        help="Géométrie des couronnes, pour le contrôle d'accord")
    parser.add_argument("--out", type=Path, default=None,
                        help="Écrire ailleurs qu'en place — OBLIGATOIRE pour une "
                             "population épinglée par un manifeste de jeu gelé")
    parser.add_argument("--dry-run", action="store_true",
                        help="Calcule et rapporte sans rien réécrire")
    parser.add_argument("--check", action="store_true",
                        help="Sort en échec si une porte du ticket 021 est démentie")
    args = parser.parse_args()

    from llm_module.core.zone_resolver import ZoneResolver

    feature_spec = REPO_ROOT / "scripts" / "progedo_logit" / "feature_spec.json"
    try:
        table = CouronneTable.load(args.table)
        zones = CommunalZones.load(args.geojson)
        resolver = ZoneResolver.load(args.zones,
                                     feature_spec if feature_spec.exists() else None)
    except (ResidenceZoneError, FileNotFoundError, ValueError) as exc:
        print(f"[ERREUR] {exc}", file=sys.stderr)
        return EXIT_RESOURCE_MISSING

    print(f"Table des couronnes : {len(table)} zones fines, {len(table.secteurs)} "
          f"secteurs, version {table.meta.get('version', '?')}")

    all_failures: list[tuple[Path, list[str]]] = []
    framing_gaps: list[Path] = []

    for path in args.population:
        if not path.exists():
            print(f"[ERREUR] Population introuvable : {path}", file=sys.stderr)
            return EXIT_RESOURCE_MISSING
        population = json.loads(path.read_text(encoding="utf-8"))
        print(f"\n=== {path}")
        try:
            counts = enrich(population, table, resolver)
            checks = audit(population, table, zones)
        except ResidenceZoneError as exc:
            print(f"[ERREUR] {exc}", file=sys.stderr)
            return EXIT_RESOURCE_MISSING

        failures = report(counts, checks)
        if print_framing(checks):
            framing_gaps.append(path)
        if failures:
            all_failures.append((path, failures))

        target = destination(path, args.out, len(args.population))
        if args.dry_run:
            print(f"  [dry-run] {target} non écrit")
            continue
        # Écriture atomique : un plantage en cours d'écriture ne doit pas laisser une
        # population tronquée derrière lui.
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(population, ensure_ascii=False), encoding="utf-8")
        tmp.replace(target)
        print(f"  écrit → {target}")

    if all_failures:
        print("\n── Portes démenties ────────────────────────────────────────────────────")
        for path, failures in all_failures:
            for failure in failures:
                print(f"  [{path.name}] {failure}")
        if args.check:
            return EXIT_GATE_FAILED
        print("  (informatif : relancez avec --check pour en faire un échec)")
        return EXIT_OK

    if args.check:
        print("\nToutes les portes passent.")
        if framing_gaps:
            print(f"  → code {EXIT_FRAMING_GAP} : l'écart au cadrage dépasse la tolérance "
                  f"sur {', '.join(p.name for p in framing_gaps)}. C'est l'axe A9 — la "
                  f"surconcentration spatiale du tirage —, pas un défaut de ce trait : le "
                  f"corriger demande de retoucher le tirage (autre ticket). Le code est "
                  f"distinct pour que l'appelant puisse le suivre sans le confondre avec "
                  f"un échec.")
            return EXIT_FRAMING_GAP
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
