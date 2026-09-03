"""enrich_personal_bike.py — Le vélo du persona, réécrit depuis EMC² (ticket 015, voie 1).

Relit un fichier de population, **regroupe les agents par adresse du domicile**, tire le
nombre de vélos du ménage, l'attribue nominativement, et réécrit `personal_bike`. Même
patron qu'`enrich_housing_type.py` : aucune régénération, applicable aux populations
existantes.

Ce que ça remplace : eqasim tirait `p = min(1, vélos_du_donneur / taille)` où le nombre de
vélos est **recopié** d'un ménage de l'ENTD 2008 apparié sans la taille du foyer ni
l'habitat. Le total sortait à peu près juste et la répartition était fausse — gradient de
taille de ménage **inversé**. Le détail des trois étages et des décisions de
conditionnement est dans `llm_module/core/bike_ownership.py`.

## L'adresse comme clé de ménage : utilisable, imparfaite, et il faut le savoir

Le JSON ne porte pas le ménage — décision d'architecture du ticket : le foyer n'existe que
le temps de tirer `k` et de le répartir, l'agent ne reçoit qu'une valeur. Il faut donc
reconstituer les foyers, et la seule clé disponible est l'adresse du domicile. C'est
**déjà** la clé de ménage du dépôt : `housing_type` hache l'adresse pour que deux personas
d'un même foyer partagent le type de logement. Cette étape ne fait donc pas une hypothèse
nouvelle, elle réutilise celle du dépôt.

Deux défauts, tous deux traités explicitement et comptés dans le rapport :

- **Collisions.** Deux ménages distincts au même point d'adresse. Repérables parce que la
  grappe dépasse le `household_size` de ses membres, ou en porte plusieurs valeurs (8
  grappes sur 547 dans `toulouse_population_1000.json`). Elles sont **scindées** par
  `household_size`, puis par paquets de cette taille — jamais traitées comme un seul gros
  foyer, qui hériterait d'un `k` de famille nombreuse.
- **Ménages partiellement présents.** Le filtre par emprise ne garde que les agents dont
  le domicile est dans la zone : ~25 % des agents appartiennent à un foyer dont tous les
  membres ne sont pas dans le fichier. On tire donc sur la taille **nominale**
  (`household_size`) et on ne matérialise que les membres présents. Sans cela, les `k`
  vélos du foyer se concentreraient sur les seuls agents retenus et on les
  sur-équiperait.

## Ce que la validation refuse de laisser passer

Un `personal_bike = None` massif doit faire **échouer** la validation, pas la réussir :
c'est le motif « vacuité ≠ perfection » que le dépôt traque. `--check` sort en échec si la
couverture est insuffisante ou si une cible est hors tolérance, et il dit laquelle.

Codes de sortie de `--check`, et la distinction est utile à l'appelant :

| Code | Sens |
|---|---|
| 0 | toutes les cibles servies sont dans la tolérance |
| 1 | ressource ou fichier introuvable — rien n'a été fait |
| 2 | une cible servie est **démentie** : le modèle ou la population est en cause |
| 3 | population **enrichie mais non validée** — pas assez de foyers pour trancher |

Usage :
    python -m scripts.data.population.enrich_personal_bike data/population/toulouse_population_1000.json
    python -m scripts.data.population.enrich_personal_bike data/population/*.json --dry-run
    python -m scripts.data.population.enrich_personal_bike data/population/*.json --check
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from llm_module.core.bike_ownership import (
    ELECTRIC_BIKE,
    K_MAX,
    MIN_AGE_ELIGIBLE,
    NO_BIKE,
    PLAIN_BIKE,
    TRAIT_KEY,
    VAE_SHARE,
    BikeOwnershipModel,
    Member,
    address_key,
    assign,
    bike_label,
)

REPO_ROOT = Path(__file__).resolve().parents[3]

# Tolérances des critères d'acceptation du ticket 015. Deux d'entre elles sont
# **restatées** par rapport à la lettre du ticket, sur la base d'une mesure, et le
# rapport le dit à chaque fois qu'il les affiche :
#
# - `bikes_per_household` : le ticket demande 1,22 (± 0,05), qui porte sur `M21` NON
#   écrêté. Le modèle est écrêté à `4+` — l'écrêtage que le ticket spécifie lui-même —
#   et plafonne donc à 1,151. La cible opposable est la moyenne écrêtée, servie par la
#   ressource (`validation.stock.clipping_cost`). L'écrêtage ne coûte que 0,011 vélo par
#   ménage sur le trait réellement produit.
# - `by_housing` : le ticket demande 71 % → 38 % (± 4 pts). Inatteignable par
#   construction, l'habitat du persona étant lui-même imputé depuis la loi de sa zone
#   (accord 47,6 %). La cible opposable est la courbe **diluée**, servie par la
#   ressource (`validation.housing_reference.attainable_on_imputed_housing`).
TOLERANCES = {
    "holders_pct": 3.0,
    "equipped_pct": 2.0,
    "bikes_per_household": 0.05,
    "by_size_pct": 5.0,
    "by_housing_pct": 4.0,
    "vae_pct": 1.5,
}

# Écrêtage des buckets de taille, identique à celui des tables servies par
# `export_bike_ownership.SIZE_BUCKET_MAX`. Les deux côtés DOIVENT bucketer pareil :
# un bucket « 5+ » côté population face à un « 5+ » côté enquête compare deux mélanges
# de tailles différents (le taux de porteurs passe de 52 % à 40 % entre 5 et 6), et
# fabrique un écart de 14 points qui n'est qu'un effet de composition.
SIZE_BUCKET_MAX = 6

# Effectifs minimaux, **en ménages** et non en personnes, pour qu'une cellule soit
# opposable. Le ticket exige déjà de signaler les cellules de l'enquête sous 30
# observations pondérées ; c'est la même règle appliquée au côté mesure.
#
# En dessous, le verdict n'est ni « ok » ni « ÉCHEC » mais **non concluant**, et la
# nuance compte : déclarer un échec sur du bruit apprend à ignorer les échecs, et
# déclarer un succès ferait passer l'absence de matière pour un résultat — c'est
# exactement le motif « vacuité ≠ perfection » que ce script existe pour refuser.
#
# Conséquence pratique : les populations de 10 et 100 agents ne peuvent pas arbitrer les
# croisements (18 foyers dans leur plus grosse cellule d'habitat). Elles restent
# enrichissables, leur rapport reste lisible, mais seule une population de l'ordre de
# 1 000 agents rend le contrôle opposable.
MIN_CELL_HOUSEHOLDS = 30
SLOPE_MIN_CELL = 30

# Nombre minimal de contrôles ayant réellement tranché pour qu'un rapport vaille
# validation. Sans ce garde-fou, une population de 10 agents passerait `--check` avec
# zéro contrôle concluant — le score parfait par absence de mesure, précisément ce que
# le ticket interdit (« aucune cible atteinte par absence de mesure »).
MIN_CONCLUSIVE_CHECKS = 4

# Codes de sortie de `--check`, et la distinction compte pour l'appelant (le notebook de
# génération, la CI) : « la cible est manquée » et « il n'y a pas de quoi mesurer » ne
# demandent pas la même action. Le premier est un défaut du modèle ou de la population,
# le second est une propriété du fichier — une population de 10 agents ne peut pas
# arbitrer un croisement, et ce n'est pas un bug.
EXIT_OK = 0
EXIT_TARGET_MISSED = 2
EXIT_NOT_MEASURABLE = 3

# Préfixe qui marque un échec « pas assez de matière » dans la liste des échecs.
NOT_MEASURABLE = "population non mesurable"

# Couverture minimale du trait. En dessous, la population n'est pas exploitable et
# aucune cible n'a de sens : une cible « atteinte » sur 10 % des agents ne mesure rien.
MIN_COVERAGE = 0.80


@dataclass
class Household:
    """Un foyer reconstitué à l'adresse, le temps du tirage.

    `nominal_size` est la taille déclarée par les personas (le foyer réel), `members`
    ceux que le fichier contient. La différence est matérialisée par des places absentes
    au moment du tirage.
    """

    key: str
    nominal_size: int
    members: list[int] = field(default_factory=list)


def build_households(population: list[dict], addresses: list[Optional[str]]) -> tuple[list[Household], Counter]:
    """Regroupe les agents en foyers, en scindant les collisions d'adresse.

    Une grappe est **cohérente** si tous ses membres déclarent la même `household_size`
    et qu'elle n'est pas plus grande que cette taille. Sinon c'est une collision : on la
    scinde d'abord par `household_size` déclarée, puis par paquets de cette taille. Deux
    célibataires au même point font donc deux foyers d'un, et non un foyer de deux — ce
    qui leur donnerait le `k` d'un couple.
    """
    clusters: dict[str, list[int]] = defaultdict(list)
    counts: Counter = Counter()
    for index, key in enumerate(addresses):
        if key is None:
            counts["sans_adresse"] += 1
            continue
        clusters[key].append(index)

    households: list[Household] = []
    for key, members in clusters.items():
        by_size: dict[int, list[int]] = defaultdict(list)
        for index in members:
            traits = (population[index].get("identity") or {}).get("traits_json") or {}
            size = traits.get("household_size")
            by_size[max(1, int(size)) if size else 1].append(index)

        coherent = len(by_size) == 1 and len(members) <= next(iter(by_size))
        counts["grappes_coherentes" if coherent else "grappes_en_collision"] += 1

        for size, group in sorted(by_size.items()):
            # Paquets de `size` : une grappe de 5 personnes déclarant toutes un foyer de
            # 2 devient trois foyers (2, 2, 1), pas un foyer de 5.
            for offset in range(0, len(group), size):
                chunk = group[offset:offset + size]
                suffix = "" if coherent else f"#s{size}n{offset // size}"
                households.append(Household(key=f"{key}{suffix}",
                                            nominal_size=size, members=chunk))
    return households, counts


def enrich(population: list[dict], model: BikeOwnershipModel, resolver) -> Counter:
    """Pose `personal_bike` sur chaque persona. Renvoie le décompte par modalité.

    Le rattachement des domiciles est fait en un seul appel vectorisé : c'est une requête
    d'index spatial par lot, pas une par persona — même règle qu'`enrich_housing_type`.
    """
    homes = [(person.get("identity") or {}).get("home") or {} for person in population]
    lats = [home.get("lat") for home in homes]
    lons = [home.get("lon") for home in homes]

    resolvable = [i for i, (la, lo) in enumerate(zip(lats, lons))
                  if la is not None and lo is not None]
    zones = resolver.resolve_many([lats[i] for i in resolvable],
                                  [lons[i] for i in resolvable])
    zone_by_index = dict(zip(resolvable, zones))
    addresses: list[Optional[str]] = [
        address_key(lats[i], lons[i]) if i in zone_by_index else None
        for i in range(len(population))
    ]

    households, counts = build_households(population, addresses)
    # Renormalisée une fois pour tout le fichier : appliquer VAE_SHARE aux seuls
    # porteurs de 14 ans et plus ferait sortir le parc sous la cible.
    electric_p = model.electric_p

    def traits_of(index: int) -> Optional[dict]:
        return (population[index].get("identity") or {}).get("traits_json")

    def clear(index: int, reason: str) -> None:
        """Aucun trait, et on retire celui qui traînait d'un enrichissement antérieur.

        `personal_bike` hérité d'eqasim est précisément ce qu'on remplace : le laisser en
        place hors couche donnerait une population moitié apprise, moitié recopiée, sans
        que rien ne le signale.
        """
        traits = traits_of(index)
        if traits is None:
            counts["sans_traits"] += 1
            return
        traits.pop(TRAIT_KEY, None)
        counts[reason] += 1

    for household in households:
        zone = zone_by_index.get(household.members[0])
        if zone is None:
            for index in household.members:
                clear(index, "hors_couche")
            continue

        # ── Étage 1 : combien de vélos dans ce foyer ─────────────────────────
        # La motorisation est un attribut du ménage ; les personas d'un même foyer la
        # portent identique, on lit donc celle du premier membre. La taille utilisée est
        # la taille NOMINALE, pas le nombre de membres présents.
        first = traits_of(household.members[0]) or {}
        k = model.draw_stock(
            household_size=household.nominal_size,
            number_of_cars=first.get("number_of_cars"),
            density_hh_km2=zone.density_hh_km2,
            dist_center_km=zone.dist_center_km,
            household_key=household.key,
        )
        if k is None:
            for index in household.members:
                clear(index, "sans_loi")
            continue

        # ── Étage 2 : qui les tient ──────────────────────────────────────────
        present: list[Member] = []
        skipped: list[int] = []
        for index in household.members:
            traits = traits_of(index)
            if traits is None:
                skipped.append(index)
                continue
            age = traits.get("age")
            present.append(Member(
                index=index,
                propensity=model.propensity_of(
                    k=k,
                    household_size=household.nominal_size,
                    age=age,
                    gender=traits.get("gender"),
                    main_occupation=traits.get("main_occupation"),
                    density_hh_km2=zone.density_hh_km2,
                    dist_center_km=zone.dist_center_km,
                ),
                eligible=(age is not None and float(age) >= MIN_AGE_ELIGIBLE),
                present=True,
            ))
        for index in skipped:
            counts["sans_traits"] += 1

        # Places absentes : les membres du foyer nominal que le filtre spatial n'a pas
        # retenus. Elles portent la propension moyenne du foyer, concourent au tirage, et
        # peuvent emporter un vélo — mais rien n'est écrit pour elles. Sans ce
        # complément, un célibataire extrait d'un foyer de quatre recevrait à lui seul
        # les vélos des quatre.
        mean_propensity = (statistics.fmean([m.propensity for m in present])
                           if present else 0.0)
        absent = [
            Member(index=-1 - position, propensity=mean_propensity,
                   eligible=True, present=False)
            for position in range(max(0, household.nominal_size - len(household.members)))
        ]
        if absent:
            counts["places_absentes"] += len(absent)

        holders = assign(present + absent, k, household.key)

        # ── Étage 3 : quel type de vélo ──────────────────────────────────────
        for member in present:
            traits = traits_of(member.index)
            if member.index in holders:
                label = bike_label(household.key, member.index,
                                   (traits or {}).get("age"), electric_p)
            else:
                label = NO_BIKE
            traits[TRAIT_KEY] = label
            counts[label] += 1

    return counts


# ── Rapport et contrôle ──────────────────────────────────────────────────────

def measure(population: list[dict]) -> dict:
    """Les grandeurs des critères d'acceptation, relues sur le fichier enrichi.

    Tout est mesuré **par personne**, sur les seuls agents portant le trait : mêler les
    agents hors couche aux dénominateurs ferait baisser mécaniquement les parts et
    présenterait l'absence de mesure comme un résultat.

    Chaque cellule est comptée **deux fois** : en personnes et en **ménages distincts**.
    Le second compte est celui qui gouverne la précision, et c'est un point de fond, pas
    une coquetterie : `k` est tiré une fois **par foyer**, donc les membres d'un même
    ménage ne sont pas des observations indépendantes. Sur la population de 100 agents,
    la cellule « individuel isolé » compte 37 personnes mais seulement 18 adresses :
    calculer son écart-type sur 37 surestime la précision d'un facteur √2 et transforme
    du bruit de tirage en écart reproché au modèle.
    """
    holders_by_size: dict[int, list[int]] = defaultdict(list)
    holders_by_housing: dict[str, list[int]] = defaultdict(list)
    households_by_size: dict[int, set] = defaultdict(set)
    households_by_housing: dict[str, set] = defaultdict(set)
    fleet = electric = holders = 0
    with_trait = 0
    all_households: set = set()
    for person in population:
        identity = person.get("identity") or {}
        traits = identity.get("traits_json") or {}
        label = traits.get(TRAIT_KEY)
        if label is None:
            continue
        home = identity.get("home") or {}
        key = (address_key(home["lat"], home["lon"])
               if home.get("lat") is not None else f"?{with_trait}")
        with_trait += 1
        all_households.add(key)
        has = label != NO_BIKE
        holders += int(has)
        if has:
            fleet += 1
            electric += int(label == ELECTRIC_BIKE)
        size = traits.get("household_size")
        if size:
            bucket = min(SIZE_BUCKET_MAX, max(1, int(size)))
            holders_by_size[bucket].append(int(has))
            households_by_size[bucket].add(key)
        housing = traits.get("housing_type")
        if housing:
            holders_by_housing[housing].append(int(has))
            households_by_housing[housing].add(key)

    return {
        "n": len(population),
        "with_trait": with_trait,
        "households": len(all_households),
        "fleet": fleet,
        "coverage": with_trait / len(population) if population else 0.0,
        "holders_pct": 100.0 * holders / with_trait if with_trait else float("nan"),
        "vae_pct_of_fleet": 100.0 * electric / fleet if fleet else float("nan"),
        "holders_by_size": {
            size: (100.0 * sum(values) / len(values), len(values),
                   len(households_by_size[size]))
            for size, values in sorted(holders_by_size.items())
        },
        "holders_by_housing": {
            housing: (100.0 * sum(values) / len(values), len(values),
                      len(households_by_housing[housing]))
            for housing, values in sorted(holders_by_housing.items())
        },
    }


def household_measure(population: list[dict]) -> dict:
    """Les grandeurs au niveau **ménage** : part équipée et vélos par foyer.

    Reconstituées à l'adresse, comme au tirage. Les foyers partiellement présents sont
    écartés de ce compte : on ne peut pas mesurer « les vélos du ménage » sur un foyer
    dont il manque des membres — le numérateur serait tronqué et le dénominateur non.

    **Le décompte est ventilé par taille, et c'est indispensable.** Écarter les foyers
    incomplets ne prélève pas un échantillon neutre : un foyer d'une personne est
    toujours complet, un foyer de cinq presque jamais. Sur
    `toulouse_population_1000.json`, les foyers mesurables sont à 50,7 % des personnes
    seules contre 39,3 % dans l'ensemble. Comparer leur taux d'équipement au 53,6 % de
    l'enquête — qui porte sur *toutes* les tailles — compare deux compositions
    différentes et fabrique un écart de 5 points qui n'existe pas. `report` standardise
    donc la cible sur la composition réellement mesurée.
    """
    addresses = []
    for person in population:
        home = (person.get("identity") or {}).get("home") or {}
        addresses.append(address_key(home["lat"], home["lon"])
                         if home.get("lat") is not None else None)
    households, _ = build_households(population, addresses)

    by_size: dict[int, dict[str, int]] = defaultdict(
        lambda: {"n": 0, "equipped": 0, "bikes": 0})
    complete = equipped = bikes = 0
    for household in households:
        labels = [((population[i].get("identity") or {}).get("traits_json") or {}).get(TRAIT_KEY)
                  for i in household.members]
        if any(label is None for label in labels):
            continue
        if len(household.members) != household.nominal_size:
            continue
        count = sum(1 for label in labels if label != NO_BIKE)
        complete += 1
        bikes += count
        equipped += int(count > 0)
        bucket = by_size[min(SIZE_BUCKET_MAX, household.nominal_size)]
        bucket["n"] += 1
        bucket["equipped"] += int(count > 0)
        bucket["bikes"] += count
    return {
        "complete_households": complete,
        "equipped_pct": 100.0 * equipped / complete if complete else float("nan"),
        "bikes_per_household": bikes / complete if complete else float("nan"),
        "by_size": {size: dict(values) for size, values in sorted(by_size.items())},
    }


def standardise(by_size: dict[int, dict[str, int]],
                reference: dict[int, float]) -> Optional[float]:
    """Cible de l'enquête recomposée sur la ventilation par taille réellement mesurée.

    Standardisation directe : `Σ_s part_mesurée(s) × valeur_enquête(s)`. C'est la façon
    correcte de comparer deux populations dont la composition diffère — sans elle, on
    impute à l'imputation un écart qui n'est qu'un effet de structure.

    `None` si la référence ne couvre pas les tailles mesurées : mieux vaut ne pas servir
    de cible que d'en servir une bancale.
    """
    total = sum(values["n"] for values in by_size.values())
    if not total or any(size not in reference for size in by_size):
        return None
    return sum(values["n"] / total * reference[size]
               for size, values in by_size.items())


def report(measured: dict, household: dict, counts: Counter,
           model: BikeOwnershipModel) -> list[str]:
    """Affiche le résultat en regard des cibles. Renvoie la liste des échecs."""
    validation = model.validation
    targets = validation.get("targets") or {}
    stock = validation.get("stock") or {}
    housing_ref = validation.get("housing_reference") or {}
    failures: list[str] = []
    # Combien de contrôles ont réellement tranché. Un rapport où tout est « non
    # concluant » ne doit PAS passer pour un succès : c'est le motif « vacuité ≠
    # perfection » — l'absence de mesure produit le score parfait.
    verdicts = {"ok": 0, "echec": 0, "non_concluant": 0}

    print(f"\nTrait posé sur {measured['with_trait']}/{measured['n']} personas "
          f"({100 * measured['coverage']:.1f} %)")
    for key in ("hors_couche", "sans_loi", "sans_traits", "sans_adresse"):
        if counts.get(key):
            print(f"  {key:22s} {counts[key]:5d} (trait absent)")
    for key in ("grappes_coherentes", "grappes_en_collision", "places_absentes"):
        if counts.get(key):
            print(f"  {key:22s} {counts[key]:5d}")

    if measured["coverage"] < MIN_COVERAGE:
        failures.append(
            f"couverture {100 * measured['coverage']:.1f} % < "
            f"{100 * MIN_COVERAGE:.0f} % — population inexploitable, et AUCUNE cible "
            f"ci-dessous n'a de sens sur si peu d'agents")

    def check(label: str, got: float, target: Optional[float], tolerance: float,
              note: str = "", n: Optional[int] = None,
              sd: Optional[float] = None) -> None:
        """Compare une grandeur mesurée à sa cible, **bruit d'échantillonnage compris**.

        Une population de 1 000 agents donne des cellules de 150 à 350 personnes. À
        n = 164, l'écart-type d'une proportion autour de 50 % est déjà de 3,9 points :
        exiger ± 4 points sur une telle cellule, c'est mesurer au niveau du bruit, et un
        fichier correct « échouerait » une fois sur trois pour rien.

        La marge est donc `tolérance + 2 σ`, avec σ l'écart-type binomial de la cellule.
        Sur un fichier à 10 000 agents σ se divise par trois et le contrôle se resserre
        de lui-même — c'est le comportement voulu : plus il y a de matière, plus la
        cible est opposable. Sans `n`, seule la tolérance s'applique.
        """
        if target is None:
            print(f"  {label:42s} {got:8.2f}   (pas de cible servie){note}")
            return
        if n is not None and 0 < n < MIN_CELL_HOUSEHOLDS:
            # Ni « ok » ni « ÉCHEC » : la cellule n'a pas de quoi trancher. Déclarer un
            # échec sur si peu de foyers apprend à ignorer les échecs, et le déclarer
            # « ok » ferait passer l'absence de matière pour un succès.
            verdicts["non_concluant"] += 1
            print(f"  {label:42s} {got:8.2f}  cible {target:7.2f} "
                  f"{'':>16s}  {got - target:+6.2f}  NON CONCLUANT "
                  f"({n} foyers < {MIN_CELL_HOUSEHOLDS}){note}")
            return
        delta = got - target
        sigma = 0.0
        if n and n > 0:
            if sd is not None:
                # Moyenne d'un comptage : σ = écart-type / √n, l'écart-type venant de
                # l'enquête (servi dans la ressource).
                sigma = sd / n ** 0.5
            elif 0.0 <= target <= 100.0:
                share = min(max(target / 100.0, 0.0), 1.0)
                sigma = 100.0 * (share * (1.0 - share) / n) ** 0.5
        margin = tolerance + 2.0 * sigma
        ok = abs(delta) <= margin
        band = f"± {tolerance:.2f}" + (f"+2σ({2 * sigma:.1f})" if sigma else "")
        print(f"  {label:42s} {got:8.2f}  cible {target:7.2f} "
              f"{band:>16s}  {delta:+6.2f}  {'ok' if ok else 'ÉCHEC'}{note}")
        verdicts["ok" if ok else "echec"] += 1
        if not ok:
            failures.append(f"{label} : {got:.2f} contre {target:.2f} ± {margin:.2f}")

    print("\n── Niveau personne ─────────────────────────────────────────────────────")
    published_holders = targets.get("holders_pct")
    check("personnes dotées d'un vélo (%)", measured["holders_pct"],
          targets.get("holders_pct_mechanism"), TOLERANCES["holders_pct"],
          f"   [publiée : {published_holders:.1f}]" if published_holders else "",
          n=measured["households"])
    check("part de VAE dans le parc (%)", measured["vae_pct_of_fleet"],
          targets.get("vae_share_of_fleet_pct"), TOLERANCES["vae_pct"],
          n=measured["fleet"])

    print("\n── Gradient de taille de ménage (le contrôle qui échouait) ─────────────")
    # Référence sous les règles du mécanisme (k écrêté, éligibilité à 5 ans), et non le
    # chiffre publié : sinon on reproche au mécanisme de ne pas produire les porteurs
    # qu'il refuse délibérément de produire.
    rows_size = targets.get("holders_by_household_size") or []
    reference = {row["size"]: row.get("holders_pct_mechanism", row["holders_pct"])
                 for row in rows_size}
    published_by_size = {row["size"]: row["holders_pct"] for row in rows_size}
    curve = []
    for size, (got, n, n_hh) in measured["holders_by_size"].items():
        curve.append(got)
        published = published_by_size.get(size)
        check(f"taille {size} (n={n}, {n_hh} foyers)", got, reference.get(size),
              TOLERANCES["by_size_pct"],
              f"   [publiée : {published:.1f}]" if published is not None else "",
              n=n_hh)
    # Le SIGNE de la pente sur les tailles 1 à 4 est un critère à part entière : c'est
    # lui qui était inversé (76 % chez les personnes seules contre 33 % observés).
    cells = [measured["holders_by_size"].get(s, (None, 0, 0)) for s in (1, 2, 3, 4)]
    ordered = [value for value, _, _ in cells]
    smallest = min((n_hh for _, _, n_hh in cells), default=0)
    if not all(v is not None for v in ordered):
        print("  pente sur les tailles 1→4 : non calculable (une taille est absente)")
    elif smallest < SLOPE_MIN_CELL:
        # Le signe d'une pente sur quatre cellules de 25 personnes est du bruit : à
        # n = 25, σ vaut 10 points par cellule et deux points voisins s'inversent une
        # fois sur trois sans qu'aucun modèle soit en cause. On ne prononce donc rien.
        print(f"  {'pente sur les tailles 1→4':42s} "
              f"{' / '.join(f'{v:.1f}' for v in ordered)}  "
              f"NON CONCLUANT (plus petite cellule : {smallest} foyers "
              f"< {SLOPE_MIN_CELL})")
    else:
        increasing = all(a < b for a, b in zip(ordered, ordered[1:]))
        print(f"  {'pente croissante sur les tailles 1→4':42s} "
              f"{' < '.join(f'{v:.1f}' for v in ordered)}  "
              f"{'ok' if increasing else 'ÉCHEC'}")
        if not increasing:
            failures.append("la pente sur les tailles 1→4 n'est pas croissante — c'est "
                            "le défaut même que le ticket 015 corrige")

    if measured["holders_by_housing"]:
        print("\n── Équipement par type d'habitat ───────────────────────────────────────")
        attainable = housing_ref.get("attainable_on_imputed_housing") or {}
        published = housing_ref.get("published_on_observed_housing") or {}
        from llm_module.core.housing_type import key_for
        if not attainable:
            print("  [cible diluée non servie : ré-exportez la ressource avec la table "
                  "du type de logement présente (make housing-type)]")
        else:
            # Les chiffres viennent de la ressource, jamais d'un littéral : ils
            # bougent à chaque amélioration de l'imputation d'habitat (ticket 019).
            accord = housing_ref.get("imputed_vs_observed_agreement_pct")
            spread = housing_ref.get("attainable_spread_pts")
            # Amplitude publiée : les DEUX bornes doivent être servies. Un
            # `get("grand_habitat_collectif", 0.0)` fabriquerait une amplitude à partir
            # d'une borne absente — elle vaudrait alors la borne haute, chiffre faux et
            # parfaitement plausible. On préfère ne pas l'annoncer.
            low = published.get("individuel_isole")
            high = published.get("grand_habitat_collectif")
            published_spread = (low - high) if (low is not None and high is not None) else None
            print("  Cible = courbe DILUÉE (habitat imputé), non la courbe publiée : "
                  "l'habitat du\n  persona est lui-même tiré de la loi de sa zone et de "
                  "sa taille de ménage"
                  + (f"\n  (accord avec l'habitat observé : {accord:.1f} %)"
                     if accord is not None else "")
                  + ", ce qui écrase l'amplitude"
                  + (f" de {published_spread:.1f}\n  à {spread:.1f} points (en part de "
                     f"ménages équipés)"
                     if (spread is not None and published_spread is not None) else "")
                  + ". Viser la publiée serait sur-corriger le\n  modèle pour compenser "
                    "le bruit de l'axe de mesure.\n"
                    "  Les cibles ci-dessous sont en part de PERSONNES dotées — l'unité "
                    "du trait.")
        for housing, (got, n, n_hh) in measured["holders_by_housing"].items():
            key = key_for(housing)
            note = ""
            if key and key in published:
                # Étiquetage explicite de l'unité : la courbe publiée est une part de
                # MÉNAGES équipés, la mesure ci-contre une part de PERSONNES dotées.
                # Les mettre côte à côte sans le dire est exactement la confusion qui a
                # fait croire un temps à un biais négatif sur les quatre modalités.
                note = (f"   [réf. publiée, part de MÉNAGES sur habitat observé : "
                        f"{published[key]:.1f}]")
            check(f"{housing} (n={n}, {n_hh} foyers)", got,
                  attainable.get(key) if key else None,
                  TOLERANCES["by_housing_pct"], note, n=n_hh)

    print("\n── Niveau ménage (foyers complets, cibles standardisées) ───────────────")
    clipping = stock.get("clipping_cost") or {}
    rows = stock.get("by_household_size") or []
    complete = household["complete_households"]
    print(f"  foyers complets mesurables : {complete}")
    print("  Cibles STANDARDISÉES sur la ventilation par taille réellement mesurée :\n"
          "  écarter les foyers incomplets sur-représente les personnes seules (50,7 %\n"
          "  des mesurables contre 39,3 % de l'ensemble), qui sont les moins équipées.\n"
          "  La cible brute de l'enquête porterait sur une autre composition.")
    equipped_ref = {row["size"]: row["equipped_pct_observed"] for row in rows}
    # Vélos ATTRIBUABLES, pas le stock : le trait ne porte que les vélos qui ont un
    # titulaire, et l'enquête compte des vélos que personne du foyer ne peut porter
    # (0,44 de stock contre 0,33 d'attribuable chez les personnes seules).
    bikes_ref = {row["size"]: row.get("attributable_per_household_observed")
                 for row in rows
                 if row.get("attributable_per_household_observed") is not None}
    equipped_target = standardise(household["by_size"], equipped_ref)
    bikes_target = standardise(household["by_size"], bikes_ref)
    raw_equipped = (stock.get("overall") or {}).get("equipped_pct_observed")
    check("ménages équipés (%)", household["equipped_pct"], equipped_target,
          TOLERANCES["equipped_pct"],
          f"   [brute, toutes tailles : {raw_equipped:.1f}]" if raw_equipped else "",
          n=complete)
    published_stock = clipping.get("bikes_per_household_unclipped")
    check("vélos attribués par ménage", household["bikes_per_household"], bikes_target,
          TOLERANCES["bikes_per_household"],
          f"   [stock publié sur M21 non écrêté, toutes tailles : {published_stock:.3f}]"
          if published_stock is not None else "",
          n=complete, sd=clipping.get("attributable_sd"))

    # Note explicative sur le coût de l'écrêtage. `if clipping:` ne garantissait que le
    # dict non vide, et les cinq accès entre crochets qui suivaient plantaient le rapport
    # sur une ressource exportée par une autre version — APRÈS avoir affiché les verdicts,
    # donc `--check` ne rendait jamais son code de sortie. Une note n'est pas un verdict :
    # si les chiffres manquent, on se taît, on ne fait pas tomber la validation.
    _needed = ("k_max", "bikes_per_household_unclipped", "bikes_per_household_clipped",
               "attributable_per_household_unclipped",
               "attributable_per_household_clipped")
    if all(clipping.get(field) is not None for field in _needed):
        stock_cost = (clipping["bikes_per_household_unclipped"]
                      - clipping["bikes_per_household_clipped"])
        trait_cost = (clipping["attributable_per_household_unclipped"]
                      - clipping["attributable_per_household_clipped"])
        print(f"  (cible écrêtée à {clipping['k_max']}+ : l'écrêtage retire "
              f"{stock_cost:.3f} au stock publié\n   mais seulement {trait_cost:.3f} "
              f"au trait produit — les vélos surnuméraires des foyers à 5+ n'ont de "
              f"toute\n   façon personne pour les porter.)")
    elif clipping:
        print("  (coût de l'écrêtage non publié par cette ressource — ré-exportez-la "
              "avec `make bike-ownership`)")

    conclusive = verdicts["ok"] + verdicts["echec"]
    print(f"\n  verdicts : {verdicts['ok']} ok, {verdicts['echec']} échec(s), "
          f"{verdicts['non_concluant']} non concluant(s)")
    if conclusive < MIN_CONCLUSIVE_CHECKS:
        failures.append(
            f"{NOT_MEASURABLE}: seulement {conclusive} contrôle(s) concluant(s) sur "
            f"{conclusive + verdicts['non_concluant']} — cette population est trop "
            f"petite pour être validée. Elle est enrichie, mais rien n'est vérifié : "
            f"ne pas lire ce rapport comme un succès (il faut de l'ordre de 1 000 "
            f"agents pour que les croisements tranchent)")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("population", type=Path, nargs="+",
                        help="Fichiers de population JSON à enrichir (modifiés en place)")
    parser.add_argument("--model", type=Path, default=None,
                        help="Modèle d'équipement vélo (défaut : llm_module/data/)")
    parser.add_argument("--zones", type=Path, default=None,
                        help="Couche de zones fines (défaut : llm_module/data/)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Calcule et rapporte sans réécrire les fichiers")
    parser.add_argument("--check", action="store_true",
                        help="Sort en échec si une cible est hors tolérance")
    args = parser.parse_args()

    from llm_module.core.zone_resolver import ZoneResolver

    feature_spec = REPO_ROOT / "scripts" / "progedo_logit" / "feature_spec.json"
    try:
        model = BikeOwnershipModel.load(args.model)
        resolver = ZoneResolver.load(args.zones,
                                     feature_spec if feature_spec.exists() else None)
    except FileNotFoundError as exc:
        print(f"[ERREUR] {exc}", file=sys.stderr)
        return 1

    practice = model.validation.get("practice") or {}
    print(f"Modèle exporté le {model.meta.get('exported_at', '?')}")
    print(f"  étage 1 : k sur les classes {model.stock.classes}, "
          f"{len(model.stock.features)} covariables de ménage")
    print(f"  étage 2 : {len(model.propensity.features)} covariables, "
          f"{practice.get('overall_practice_pct_predicted', '?')} % de pratiquants "
          f"prédits pour {practice.get('overall_practice_pct_observed', '?')} % observés")

    all_failures: list[tuple[Path, list[str]]] = []
    for path in args.population:
        if not path.exists():
            print(f"[ERREUR] Population introuvable : {path}", file=sys.stderr)
            return 1
        population = json.loads(path.read_text(encoding="utf-8"))
        counts = enrich(population, model, resolver)
        print(f"\n=== {path}")
        failures = report(measure(population), household_measure(population),
                          counts, model)
        if failures:
            all_failures.append((path, failures))
        if args.dry_run:
            print("  [dry-run] fichier non réécrit")
            continue
        # Écriture atomique : un plantage en cours d'écriture ne doit pas laisser une
        # population tronquée derrière lui.
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(population, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
        print(f"  écrit → {path}")

    if all_failures:
        print("\n── Cibles hors tolérance ───────────────────────────────────────────────")
        for path, failures in all_failures:
            for failure in failures:
                print(f"  {path.name} : {failure}")
        if args.check:
            # Si TOUS les échecs sont des « pas assez de matière », le fichier n'est pas
            # fautif : il est trop petit pour être jugé. On le signale par un code
            # distinct, que l'appelant peut traiter autrement qu'une cible manquée.
            measurable = [failure for _, failures in all_failures
                          for failure in failures
                          if not failure.startswith(NOT_MEASURABLE)]
            if not measurable:
                print(f"\n  → code {EXIT_NOT_MEASURABLE} : population enrichie mais NON "
                      f"VALIDÉE (pas assez de foyers pour trancher), et non « en "
                      f"échec ». Aucune cible servie n'est démentie.")
                return EXIT_NOT_MEASURABLE
            return EXIT_TARGET_MISSED
        print("  (informatif : relancez avec --check pour en faire un échec)")
    elif args.check:
        print("\nToutes les cibles servies sont dans la tolérance.")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
