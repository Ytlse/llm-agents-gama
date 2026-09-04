"""seal_population.py — Sélectionner 1 000 personas pile, par MÉNAGES, dans un vivier ; puis sceller.

    # 1. sélection stratifiée dans le vivier généré et pré-imputé (avant le routage du notebook)
    llm-agents/.venv/bin/python -m scripts.AAMAS.seal_population select \\
        --pool scripts/data/population/Temp/4_zone_enriched/toulouse_population_10000.json \\
        --n 1000 --out scripts/data/population/Temp/4_zone_enriched/toulouse_population_1000_AAMAS.json

    # 2. scellement du fichier final, APRÈS post-traitements et contrôle
    llm-agents/.venv/bin/python -m scripts.AAMAS.seal_population seal \\
        --population data/population/toulouse_population_1000_AAMAS.json \\
        --out-dir data/population/population_1000_AAMAS_v5

POURQUOI UNE SÉLECTION. Le service eqasim tire `population_size × 1,15` personnes et renomme
le fichier à la taille DEMANDÉE : `toulouse_population_1000.json` en contient 1 021. Un
effectif rond ne se règle donc pas à la génération. Et une sélection au hasard gaspille la
précision : la note de dimensionnement (§ 4.3.1) demande un tirage STRATIFIÉ sur les strates
mêmes qui serviront à la validation — « 1 000 agents stratifiés valent ≈ 2 000 tirés au hasard ».

LA RÈGLE v5 (`aamas_seal_v5`, ticket 031). Même mécanique que la v4, mais l'allocation porte
sur une DIMENSION DE PLUS — la sous-cellule (cellule × effectif présent × taille déclarée) au
lieu de la cellule seule. Le sel du hachage reste `aamas_seal_v4:` : seule la strate change, pas
l'ordre dans lequel les ménages se présentent. Les cibles `cj1` / `cm1` ne changent pas : elles
sont calculées sur les 453 communes. Le journal du PÉRIMÈTRE (453 communes de l'EMC² 2023,
polygone communal, table `commune_couronne.json` cc1 ; départements de résidence des retenus lus
sur `household.commune_id`) est celui de la v4. En quatre temps :

1. **L'unité est le ménage** (`household.id`, à la racine des enregistrements depuis l'export
   élargi). La v2 sélectionnait des personnes : 1 000 retenus venaient de 865 ménages dont 308
   complets. Un ménage a UNE couronne et UNE motorisation (attributs du ménage : 0 ménage mixte
   mesuré sur 2 791), donc une cellule ; ses membres de 5 ans et + sont tous dans le vivier
   depuis que l'export garde les immobiles — les seuls absents sont les enfants de moins de
   5 ans, hors population enquêtée. Une population sans `household.id` (antérieure à l'export
   élargi) est traitée par ménages d'une personne, et le journal le dit.

2. **Effectifs de cellule** : les 12 cellules couronne × motorisation de la cible jointe sur
   base personne (`cible_jointe_couronne_motorisation.yaml`), effectifs en personnes par plus
   fort reste. Une cellule que le vivier ne remplit pas est un DÉFICIT : reporté d'abord dans la
   même couronne, puis dans le vivier entier, journalisé, alarmé, et code de sortie 1.

3. **Effectifs par SOUS-CELLULE, par programme entier** (HiGHS via `scipy.optimize.milp`). Les
   douze effectifs de cellule en personnes sont des égalités ; la taille de ménage en base
   personne et la motorisation en base MÉNAGE (poids `1/taille`, celui du contrôle) sont bornées
   en écart maximal, à la tolérance la plus fine que le vivier permette (bissection) ; parmi les
   allocations qui la tiennent, l'objectif retient celle qui déplace le moins de ménages par
   rapport à la composition du vivier. La v4 n'allouait que par cellule : la motorisation en
   base ménage y était le seul écart « à publier » (22,8 % de ménages sans voiture contre 19,2 %
   au rapport p. 21) parce que rien ne la visait — et la mettre dans la seule perte de la
   descente ne suffit pas, c'est mesuré. Un échec de résolution est une erreur explicite ; il
   n'y a pas de repli sur l'allocation d'avant. Les ménages entrent ensuite dans l'ordre de
   `sha256("aamas_seal_v4:" + household_id)` À L'INTÉRIEUR de leur sous-cellule.

4. **Descente sur marges multiples** : tant qu'un échange de deux ménages de MÊME SOUS-CELLULE
   — l'un retenu, l'autre non — réduit la perte, on l'applique. La perte est la somme, sur
   toutes les marges contrôlées (occupation et six classes d'âge publiées p. 11 ; âge
   quinquennal, genre, taille de ménage, permis, abonnement TC, logement, immobiles : recalculs
   gelés `cm1`), des écarts absolus en points entre la part observée et la cible. Ordre de
   parcours et de candidature = hachage : déterministe, rejouable. Un échange à sous-cellule
   constante ne déplace ni les douze effectifs de cellule, ni les deux marges allouées : la
   descente ne travaille que sur ce que l'allocation ne fixe pas. Les traits imputés doivent
   être posés SUR LE VIVIER avant la sélection (étape 3ter-a du notebook), sinon la marge est
   vide et la descente l'ignore — en le disant.

La composition retenue épousant les cibles, la cohorte reste AUTO-PONDÉRÉE : chaque persona
garde son poids 1, aucune pondération de plan à propager dans le score.

LE SCELLEMENT REFUSE. `seal` rejoue le contrôle (`control_population.py`) sur le fichier
final ; un verdict `à corriger` interdit le scellement — rien n'est écrit, le fichier
candidat reste en place, le rapport dit quoi. Un dossier scellé porte le fichier, son
sha256, celui du vivier, la règle de sélection, les déficits, le journal de descente, le
rapport de contrôle et la révision git du dépôt. Il ne se modifie pas : toute correction
produit un NOUVEAU dossier.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import yaml
from scipy.optimize import Bounds, LinearConstraint, milp

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from llm_module.core.population_reference import COURONNES, MIN_AGE, OUT_OF_PERIMETER  # noqa: E402
from scripts.AAMAS import control_population as ctl  # noqa: E402
from scripts.AAMAS.reference_marges import (  # noqa: E402
    JOINT_TARGET, MARGES_PERSONNE, MARGES_TARGET, MOTORISATION, Marge, ReferenceError,
    cible_jointe, marges, motorisation_class)

logger = logging.getLogger("aamas.seal")

# Le sel du hachage des MÉNAGES reste celui de la v4, DÉLIBÉRÉMENT : la règle v5 ne change que
# ce qui est visé (la sous-cellule d'allocation, la fonction de perte de la descente), pas
# l'ordre dans lequel les ménages se présentent. Garder le même ordre rend l'effet de la
# nouvelle allocation mesurable en isolation — un sel neuf mêlerait deux causes, et le tableau
# de conformité ne dirait plus laquelle a agi. La v3 → v4 avait changé de sel parce que le cadre
# de tirage changeait ; ici il ne change pas.
SELECTION_NAMESPACE = "aamas_seal_v4"   # sel du hachage des MÉNAGES — inchangé, cf. ci-dessus
SELECTION_RULE = "aamas_seal_v5"
SEAL_VERSION = "sceau1"
DEFAULT_SEAL_DIR = REPO_ROOT / "data" / "population" / "population_1000_AAMAS_v5"

# Périmètre de la population (ticket 031, option A) : les 453 communes de l'EMC² 2023, six
# départements, délimitées par le POLYGONE DES COMMUNES (table `commune_couronne.json`), pas par
# un rayon. La sélection exclut les domiciles hors de ces communes ; le journal dit combien de
# retenus viennent de chaque département, pour qu'un cadre de tirage amputé (Haute-Garonne
# seule, ticket 026) se lise dans le sceau au lieu de s'y cacher.
PERIMETRE = {
    "definition": "453 communes de l'enquête EMC² Toulouse 2023, six départements "
                  "(31, 32, 81, 82, 09, 11), polygone communal — pas de rayon",
    "table_communes": "llm_module/data/commune_couronne.json",
    "departements_attendus": {"31": 346, "32": 38, "81": 27, "82": 22, "09": 10, "11": 10},
}

# Marges de la descente : l'occupation et les SIX classes d'âge publiées par le rapport (p. 11),
# plus les marges personne gelées (cm1). Les six classes publiées ET les quinze quinquennales :
# la classe 15-19 chevauche la frontière 17/18, et tenir les quinze ne tient pas la part des
# 5-17 ans (mesuré sur la v3 : +1,2 pt sur les 5-17 avec 57 % de 15-17 dans les 15-19 contre
# 45 % dans l'enquête). Le référentiel de l'article est le rapport AUAT : ses classes sont
# tenues d'abord. La cellule couronne × motorisation n'en fait pas partie : elle est tenue
# exactement par l'allocation.
# La motorisation en BASE MÉNAGE est dans les marges de la descente depuis la v5, mais c'est
# l'ALLOCATION qui la tient (cf. ALLOCATION_MARGES) : sous l'opérateur d'échange de la v5 elle
# est CONSTANTE, et sa présence ici sert le journal et l'invariant vérifié après la descente.
DESCENTE_MARGES: tuple[str, ...] = ("occupation", "classe_age", "motorisation_menage",
                                    *MARGES_PERSONNE)

# Marges comptées en base MÉNAGE : chaque persona y pèse `1 / taille déclarée de son ménage`,
# comme dans le contrôle (`llm_module.core.population_reference.household_weight`). Compter ces
# marges à poids 1 comparerait une population de personnes à une cible de ménages — l'erreur
# de base que la page de contrôle interdit explicitement.
DESCENTE_MARGES_MENAGE: frozenset[str] = frozenset({"motorisation_menage"})

# Candidats examinés par ménage retenu et par passe (ordre de hachage). Borne le coût sans
# changer le déterminisme ; 150 suffit largement sur un vivier de 10 000.
DESCENTE_CANDIDATS = 150
DESCENTE_PASSES_MAX = 40

# ── Les deux marges que l'ALLOCATION tient (v5) ───────────────────────────────
#
# La v4 laissait un écart « à publier » : ménages sans voiture 22,8 % contre 19,2 % (rapport
# p. 21). Rien ne le visait — l'allocation tenait la motorisation en base PERSONNE (exacte,
# 13,6 %) et les deux bases ne disent pas la même chose : en base ménage un persona pèse
# l'inverse de la taille DÉCLARÉE de son foyer, une personne seule sans voiture pèse 1 et un
# membre d'un foyer de quatre pèse 0,25.
#
# Mettre la marge dans la perte de la descente ne suffit pas, et c'est mesuré (2026-09-04) :
# l'opérateur apparie les ménages par effectif PRÉSENT, si bien que le seul levier est un
# ménage dont la taille déclarée diffère de l'effectif présent — les enfants de moins de 5 ans
# absents, 52 membres sur 1 052. En pondérant la marge de 1 à 50 dans la perte, l'écart ne
# descend que de 3,4 à 2,2 pt, et la taille de ménage se dégrade de 0,9 à 3,0 pt.
#
# La v5 alloue donc sur UNE DIMENSION DE PLUS : la SOUS-CELLULE est le triplet
# (cellule, effectif présent, taille déclarée), et non la cellule seule. Ce triplet détermine
# exactement les deux marges de base ménage / taille :
#   * personnes d'une classe de taille = Σ n(c,S,T) × S sur les T de la classe ;
#   * poids ménage d'une modalité de motorisation = Σ n(c,S,T) × S/T sur les cellules de cette
#     modalité (le poids `1/taille` sommé sur les S membres présents).
# L'opérateur d'échange apparie désormais à SOUS-CELLULE constante : les deux marges — et les
# douze effectifs de cellule en personnes — sont préservés PAR CONSTRUCTION par la descente,
# qui garde toute sa liberté sur les autres (occupation, âge, genre, permis, abonnement,
# logement, immobiles).
ALLOCATION_MARGES: tuple[str, ...] = ("taille_menage_personne", "motorisation_menage")

# L'allocation cherche le plus petit écart MAXIMAL (norme ∞, le critère même du contrôle)
# atteignable sur ces deux marges, par bissection sur la tolérance : un programme entier de
# faisabilité par essai, la faisabilité étant croissante avec la tolérance. Le pas de 0,01 pt
# est un centième de la borne d'indifférence du contrôle. La borne haute est toujours faisable
# (aucun écart de part ne dépasse 100 pt) dès que les douze égalités de cellule le sont : la
# bissection rend donc toujours une allocation, et le journal dit à quelle tolérance.
ALLOCATION_TOLERANCE_PAS_PT = 0.01
ALLOCATION_TOLERANCE_MAX_PT = 100.0
# Au-delà de cette tolérance, le vivier ne permet pas de tenir la marge : ce n'est plus un
# réglage, c'est un écart à déclarer. On l'alarme et on sort en code 1 — jamais un arrondi muet.
ALLOCATION_TOLERANCE_ALARME_PT = 1.0
ALLOCATION_SOLVEUR_TIMEOUT_S = 300.0


# ── Utilitaires ───────────────────────────────────────────────────────────────

def _rank(key: str) -> str:
    return hashlib.sha256(f"{SELECTION_NAMESPACE}:{key}".encode("utf-8")).hexdigest()


def largest_remainder(shares_pct: dict[str, float], n: int) -> dict[str, int]:
    """Arrondi au plus fort reste : les effectifs somment EXACTEMENT à `n`."""
    total = sum(shares_pct.values())
    exact = {k: n * v / total for k, v in shares_pct.items()}
    floors = {k: int(v) for k, v in exact.items()}
    remainder = n - sum(floors.values())
    for k in sorted(exact, key=lambda k: exact[k] - floors[k], reverse=True)[:remainder]:
        floors[k] += 1
    return floors


def _traits(rec: dict) -> dict:
    return (rec.get("identity") or {}).get("traits_json") or {}


def ensure_residence_zone(records: list[dict]) -> Counter:
    """Pose `residence_zone` sur les personas qui ne l'ont pas encore (étage D, ticket 021)."""
    missing = [r for r in records
               if _traits(r).get("residence_zone") not in (*COURONNES, OUT_OF_PERIMETER)]
    counts: Counter = Counter(deja_pose=len(records) - len(missing))
    if not missing:
        return counts
    from llm_module.core.residence_zone import CouronneTable
    from llm_module.core.zone_resolver import ZoneResolver
    from scripts.data.population.enrich_residence_zone import enrich

    feature_spec = REPO_ROOT / "scripts" / "progedo_logit" / "feature_spec.json"
    table = CouronneTable.load()
    resolver = ZoneResolver.load(None, feature_spec if feature_spec.exists() else None)
    t0 = time.monotonic()
    posed = enrich(missing, table, resolver)
    counts.update({f"pose_{k}": v for k, v in posed.items()})
    logger.info("residence_zone posé sur %d personas en %.1fs : %s", len(missing),
                time.monotonic() - t0, posed)
    return counts


# ── Ménages ───────────────────────────────────────────────────────────────────

@dataclass
class Menage:
    id: str
    cellule: str
    membres: list[dict]
    taille_declaree: int
    rank: str = ""

    @property
    def size(self) -> int:
        return len(self.membres)


def group_households(records: list[dict]) -> tuple[list[Menage], Counter]:
    """Regroupe les personas éligibles par ménage. Les cas écartés sont comptés, jamais tus."""
    excluded: Counter = Counter()
    groups: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        tr = _traits(rec)
        try:
            age = int(float(tr.get("age")))
        except (TypeError, ValueError):
            excluded["sans_age"] += 1
            continue
        if age < MIN_AGE:
            excluded["moins_de_5_ans"] += 1
            continue
        couronne = tr.get("residence_zone")
        if couronne == OUT_OF_PERIMETER:
            excluded["hors_perimetre"] += 1
            continue
        if couronne not in COURONNES:
            excluded["sans_couronne"] += 1
            continue
        if motorisation_class(tr.get("number_of_cars")) is None:
            excluded["sans_motorisation"] += 1
            continue
        hid = (rec.get("household") or {}).get("id")
        if not hid:
            excluded["sans_household_id_menage_d_une_personne"] += 1
            hid = f"p:{rec.get('person_id')}"
        groups[str(hid)].append(rec)

    menages: list[Menage] = []
    for hid, membres in groups.items():
        cells = {f"{_traits(m)['residence_zone']} × {motorisation_class(_traits(m)['number_of_cars'])}"
                 for m in membres}
        if len(cells) != 1:
            excluded["menage_mixte"] += len(membres)
            continue
        try:
            declared = int(float(_traits(membres[0]).get("household_size")))
        except (TypeError, ValueError):
            declared = len(membres)
        menages.append(Menage(hid, cells.pop(), membres, declared, _rank(hid)))
    menages.sort(key=lambda m: m.rank)
    return menages, excluded


def _commune_of(rec: dict) -> Optional[str]:
    """Commune INSEE du domicile : `household.commune_id` (export eqasim), sinon le trait."""
    hh = rec.get("household") or {}
    code = hh.get("commune_id")
    if code is None or str(code) in ("", "undefined", "None"):
        code = _traits(rec).get("residence_insee")
    return str(code).zfill(5) if code not in (None, "") else None


def count_removed_out_of_perimeter(records: list[dict]) -> dict:
    """Activités hors du polygone retirées à l'étape 2 du notebook (`perimetre` à la racine).

    `controle: False` quand aucun enregistrement ne porte la clé : la population a été produite
    avant le garde-fou, et « 0 » serait alors une invention."""
    total, touches, controles = 0, 0, 0
    for rec in records:
        per = rec.get("perimetre") or {}
        if "activites_hors_perimetre_supprimees" not in per:
            continue
        controles += 1
        k = int(per["activites_hors_perimetre_supprimees"] or 0)
        total += k
        touches += 1 if k else 0
    return {"controle": controles == len(records) and bool(records),
            "personas_controles": controles, "activites_hors_perimetre_supprimees": total,
            "personas_touches": touches}


def perimeter_journal(retenus: list[dict]) -> dict:
    """Le périmètre déclaré, les départements de résidence des retenus (`household.commune_id`) et
    les activités hors polygone retirées de leurs chaînes."""
    by_dep: Counter = Counter()
    sans_commune = 0
    for rec in retenus:
        code = _commune_of(rec)
        if code is None:
            sans_commune += 1
            continue
        by_dep[code[:2]] += 1
    return {
        **PERIMETRE,
        "retenus_par_departement": dict(sorted(by_dep.items())),
        "departements_representes": len(by_dep),
        "retenus_sans_commune": sans_commune,
        "communes_distinctes": len({c for c in (_commune_of(r) for r in retenus) if c}),
        "activites_hors_perimetre": count_removed_out_of_perimeter(retenus),
    }


# ── Allocation par sous-cellules (cellule × effectif présent × taille déclarée) ─

SousCellule = tuple[str, int, int]


class AllocationError(ValueError):
    """L'allocation n'a pas de solution entière. Jamais un repli sur l'allocation d'avant."""


def sous_cellule(m: Menage) -> SousCellule:
    """La strate d'allocation de la v5 : cellule, effectif PRÉSENT, taille DÉCLARÉE.

    C'est aussi la clé d'appariement de l'opérateur d'échange : ce que l'allocation fixe, la
    descente le préserve par construction.
    """
    return (m.cellule, m.size, m.taille_declaree)


def _libelle(key: SousCellule) -> str:
    return f"{key[0]} | présents {key[1]} | déclarés {key[2]}"


def inventaire(menages: list[Menage]) -> dict[SousCellule, int]:
    """Ménages du vivier par sous-cellule — l'inventaire dont l'allocation ne peut pas sortir."""
    inv: Counter = Counter(sous_cellule(m) for m in menages)
    return dict(sorted(inv.items()))


def cibles_allocation(joint_path: Path = JOINT_TARGET,
                      marges_path: Path = MARGES_TARGET) -> dict[str, dict[str, float]]:
    """Les cibles des deux marges tenues par l'allocation, en %, renormalisées à 100.

    Elles sont LUES sur les cibles gelées (`cj1`, `cm1`) comme celles de la descente — aucun
    littéral recopié ici, sans quoi une cible qui bouge ne bougerait pas la sélection.
    """
    out: dict[str, dict[str, float]] = {}
    for m in marges(joint_path, marges_path):
        if m.nom not in ALLOCATION_MARGES:
            continue
        if not m.mesurable:
            raise AllocationError(
                f"la marge « {m.nom} » est allouée par la v5 mais n'a pas de cible : "
                f"{m.source_cible}. On n'alloue pas sur une cible absente.")
        total = sum(m.cible_pct.values())
        out[m.nom] = {k: 100.0 * v / total for k, v in m.cible_pct.items()}
    manquantes = [nom for nom in ALLOCATION_MARGES if nom not in out]
    if manquantes:
        raise AllocationError(f"marges d'allocation absentes des références : {manquantes}")
    return out


@dataclass
class _Contexte:
    """Les tableaux du programme entier, dans l'ordre trié de l'inventaire (déterminisme)."""
    keys: list[SousCellule]
    dispo: "np.ndarray"          # ménages disponibles par sous-cellule
    presents: "np.ndarray"       # effectif présent S
    declares: "np.ndarray"       # taille déclarée T
    cellule: list[str]
    motorisation: list[str]
    classe_taille: list[Optional[str]]
    effectif: dict[str, int]     # effectif cible en PERSONNES par cellule (après reports)
    n: int
    cibles: dict[str, dict[str, float]]
    reference: "np.ndarray"      # allocation proportionnelle au vivier, arrondie


def _contexte(inv: dict[SousCellule, int], effectif: dict[str, int], n: int,
              cibles: dict[str, dict[str, float]]) -> _Contexte:
    from scripts.AAMAS.reference_marges import taille_menage_class
    keys = list(inv)
    dispo = np.array([inv[k] for k in keys], dtype=float)
    presents = np.array([k[1] for k in keys], dtype=float)
    declares = np.array([k[2] for k in keys], dtype=float)
    cellule = [k[0] for k in keys]
    motorisation = [k[0].split(" × ")[1] for k in keys]
    classe_taille = [taille_menage_class(k[2]) for k in keys]
    capacite: Counter = Counter()
    for j, k in enumerate(keys):
        capacite[k[0]] += inv[k] * k[1]
    reference = np.array([round(dispo[j] * effectif[cellule[j]] / capacite[cellule[j]])
                          if capacite[cellule[j]] else 0.0 for j in range(len(keys))])
    return _Contexte(keys, dispo, presents, declares, cellule, motorisation, classe_taille,
                     effectif, n, cibles, reference)


def _programme(ctx: _Contexte, tol: float, avec_objectif: bool):
    """Le programme entier à tolérance `tol` (écart maximal, en points, des marges allouées).

    Variables : le nombre de ménages retenus par sous-cellule (entier, borné par l'inventaire),
    et — quand `avec_objectif` — l'écart absolu à l'allocation proportionnelle au vivier.
    Contraintes : les douze effectifs de cellule en PERSONNES (égalités), la taille de ménage en
    base personne et la motorisation en base ménage à ± `tol` point. La contrainte de motorisation
    est écrite `|100·W_m − cible_m·W| ≤ tol·W` : le dénominateur W (somme des poids `S/T`) est
    lui-même une variable, et la forme reste LINÉAIRE — ce qui évite d'estimer W d'avance.
    """
    nk = len(ctx.keys)
    nvar = 2 * nk if avec_objectif else nk
    cellules = sorted(ctx.effectif)
    cel = np.array(ctx.cellule)
    mot = np.array(ctx.motorisation)
    cls = np.array([c or "" for c in ctx.classe_taille])
    poids = ctx.presents / ctx.declares          # poids ménage d'une sous-cellule
    rows, lo, hi = [], [], []

    def _contrainte(coefficients: "np.ndarray", borne_basse: float, borne_haute: float) -> None:
        rows.append(coefficients)
        lo.append(borne_basse)
        hi.append(borne_haute)

    for c in cellules:                            # 1) douze effectifs de cellule, EXACTS
        r = np.zeros(nvar)
        r[:nk] = np.where(cel == c, ctx.presents, 0.0)
        _contrainte(r, float(ctx.effectif[c]), float(ctx.effectif[c]))
    for modalite, cible in ctx.cibles["taille_menage_personne"].items():
        r = np.zeros(nvar)                        # 2) taille de ménage, base PERSONNE
        r[:nk] = np.where(cls == modalite, 100.0 * ctx.presents / ctx.n, 0.0)
        _contrainte(r, cible - tol, cible + tol)
    for modalite, cible in ctx.cibles["motorisation_menage"].items():
        base = (np.where(mot == modalite, 100.0, 0.0) - cible) * poids
        for signe in (+1.0, -1.0):                # 3) motorisation, base MÉNAGE
            r = np.zeros(nvar)
            r[:nk] = signe * base - tol * poids
            _contrainte(r, -np.inf, 0.0)
    if avec_objectif:
        for j in range(nk):                       # 4) écart à l'allocation proportionnelle
            for signe in (+1.0, -1.0):
                r = np.zeros(nvar)
                r[j] = signe
                r[nk + j] = -1.0
                _contrainte(r, -np.inf, signe * ctx.reference[j])
    cons = LinearConstraint(np.array(rows), np.array(lo), np.array(hi))
    borne_haute = (np.concatenate([ctx.dispo, np.full(nk, np.inf)]) if avec_objectif else ctx.dispo)
    bounds = Bounds(np.zeros(nvar), borne_haute)
    integralite = (np.concatenate([np.ones(nk), np.zeros(nk)]) if avec_objectif else np.ones(nk))
    objectif = np.zeros(nvar)
    if avec_objectif:
        objectif[nk:] = 1.0
    return milp(c=objectif, constraints=cons, integrality=integralite, bounds=bounds,
                options={"presolve": True, "mip_rel_gap": 0.0,
                         "time_limit": ALLOCATION_SOLVEUR_TIMEOUT_S})


def _parts_obtenues(ctx: _Contexte, n_par_sous_cellule: "np.ndarray") -> dict[str, dict[str, float]]:
    """Parts des deux marges allouées, recalculées sur les effectifs retenus."""
    cls = np.array([c or "" for c in ctx.classe_taille])
    mot = np.array(ctx.motorisation)
    personnes = float(np.sum(n_par_sous_cellule * ctx.presents)) or 1.0
    poids = n_par_sous_cellule * ctx.presents / ctx.declares
    total_poids = float(np.sum(poids)) or 1.0
    return {
        "taille_menage_personne": {
            mod: round(100.0 * float(np.sum(n_par_sous_cellule[cls == mod]
                                            * ctx.presents[cls == mod])) / personnes, 4)
            for mod in ctx.cibles["taille_menage_personne"]},
        "motorisation_menage": {
            mod: round(100.0 * float(np.sum(poids[mot == mod])) / total_poids, 4)
            for mod in ctx.cibles["motorisation_menage"]},
    }


def allouer_sous_cellules(inv: dict[SousCellule, int], effectif: dict[str, int], n: int,
                          cibles: dict[str, dict[str, float]]) -> tuple[dict[SousCellule, int], dict]:
    """Effectifs cibles par sous-cellule : la tolérance la plus fine que le vivier permette.

    Bissection sur l'écart maximal admis aux deux marges allouées (faisabilité croissante avec
    la tolérance), puis un dernier programme qui, à cette tolérance, minimise le nombre de
    ménages déplacés par rapport à la composition du vivier — c'est le tirage qui déforme le
    moins ce que le vivier porte déjà, et il rend la solution reproductible plutôt qu'arbitraire.
    """
    t0 = time.monotonic()
    ctx = _contexte(inv, effectif, n, cibles)
    essais: list[dict] = []

    def faisable(tol: float) -> bool:
        res = _programme(ctx, tol, avec_objectif=False)
        essais.append({"tolerance_pt": round(tol, 4), "faisable": bool(res.success),
                       "statut": int(res.status), "message": str(res.message)[:120]})
        return bool(res.success)

    if not faisable(ALLOCATION_TOLERANCE_MAX_PT):
        raise AllocationError(
            "aucune allocation entière ne tient les douze effectifs de cellule en personnes sur "
            f"cet inventaire ({len(inv)} sous-cellules, {sum(inv.values())} ménages) — même à "
            f"tolérance {ALLOCATION_TOLERANCE_MAX_PT} pt. Le vivier ne porte pas les tailles de "
            "ménage qu'il faudrait pour composer ces effectifs exactement.")
    bas, haut = 0.0, ALLOCATION_TOLERANCE_MAX_PT
    while haut - bas > ALLOCATION_TOLERANCE_PAS_PT:
        milieu = round((bas + haut) / 2, 6)
        if faisable(milieu):
            haut = milieu
        else:
            bas = milieu
    tol = round(haut, 4)

    res = _programme(ctx, tol, avec_objectif=True)
    if not res.success:
        raise AllocationError(
            f"le programme d'allocation est faisable à {tol} pt mais son optimisation a échoué "
            f"(statut {res.status} : {res.message}). Pas de repli : la sélection s'arrête.")
    n_par = np.rint(res.x[:len(ctx.keys)]).astype(int)
    if np.any(n_par < 0) or np.any(n_par > ctx.dispo + 1e-6):
        raise AllocationError("solution d'allocation hors de l'inventaire du vivier")

    parts = _parts_obtenues(ctx, n_par.astype(float))
    ecarts = {nom: {mod: round(parts[nom][mod] - cible, 4) for mod, cible in cibles[nom].items()}
              for nom in cibles}
    ecart_max = max((abs(v) for row in ecarts.values() for v in row.values()), default=0.0)
    depassee = ecart_max > ALLOCATION_TOLERANCE_ALARME_PT
    cibles_sc = {ctx.keys[j]: int(n_par[j]) for j in range(len(ctx.keys)) if n_par[j]}
    personnes = int(np.sum(n_par * ctx.presents))
    journal = {
        "methode": ("programme entier (HiGHS via scipy.optimize.milp) sur les sous-cellules "
                    "(cellule × effectif présent × taille déclarée) : les douze effectifs de "
                    "cellule en personnes sont des égalités, les deux marges allouées sont "
                    "bornées en écart maximal — tolérance trouvée par bissection —, et "
                    "l'objectif minimise le nombre de ménages déplacés par rapport à la "
                    "composition du vivier"),
        "marges_allouees": list(ALLOCATION_MARGES),
        "cibles_pct": cibles,
        "parts_obtenues_pct": parts,
        "ecarts_pt": ecarts,
        "ecart_max_pt": round(ecart_max, 4),
        "tolerance": {"pas_pt": ALLOCATION_TOLERANCE_PAS_PT, "retenue_pt": tol,
                      "borne_alarme_pt": ALLOCATION_TOLERANCE_ALARME_PT, "depassee": depassee,
                      "essais": essais, "programmes_resolus": len(essais) + 1},
        "sous_cellules": {
            "vivier": len(inv), "servies": len(cibles_sc),
            "cibles_menages": {_libelle(k): v for k, v in sorted(cibles_sc.items())},
            "vivier_menages": {_libelle(k): v for k, v in inv.items()}},
        "menages": int(n_par.sum()),
        "personnes": personnes,
        "menages_deplaces_vs_vivier": int(round(float(res.fun))),
        "duree_s": round(time.monotonic() - t0, 2),
    }
    if personnes != sum(effectif.values()):
        raise AllocationError(f"l'allocation compose {personnes} personnes pour "
                              f"{sum(effectif.values())} demandées — incohérence du programme")
    if depassee:
        logger.error("[ALARME] allocation : le vivier ne tient pas les marges allouées — écart "
                     "maximal %.2f pt (> %.2f pt) sur %s ; écarts %s", ecart_max,
                     ALLOCATION_TOLERANCE_ALARME_PT, list(ALLOCATION_MARGES), ecarts)
    else:
        logger.info("allocation : %d sous-cellules servies sur %d, %d ménages / %d personnes, "
                    "écart maximal %.3f pt (tolérance %.2f pt, %d programmes, %.1fs)",
                    len(cibles_sc), len(inv), int(n_par.sum()), personnes, ecart_max, tol,
                    len(essais) + 1, journal["duree_s"])
    return cibles_sc, journal


def effectifs_par_cellule(menages: list[Menage],
                          targets: dict[str, int]) -> tuple[dict[str, int], dict[str, int], list[dict]]:
    """Effectifs de cellule que le vivier peut servir, et les reports de ce qu'il ne peut pas.

    Une cellule que le vivier ne remplit pas est un DÉFICIT : il est reporté d'abord dans la
    MÊME COURONNE (la marge spatiale déplace les cibles modales de 30 points), puis dans le
    vivier entier, dans la limite de ce que les autres cellules peuvent absorber. Chaque report
    est journalisé et alarmé ; rien n'est comblé en silence.
    """
    capacite: Counter = Counter()
    for m in menages:
        capacite[m.cellule] += m.size
    effectif = {c: min(targets[c], capacite.get(c, 0)) for c in targets}
    deficits = {c: targets[c] - effectif[c] for c in targets if targets[c] > effectif[c]}
    reports: list[dict] = []
    for cell, manque in deficits.items():
        couronne = cell.split(" × ")[0]
        reste = manque
        soeurs = [c for c in targets if c.startswith(couronne + " × ") and c != cell]
        autres = [c for c in targets if c != cell and c not in soeurs]
        for portee, cells in (("même couronne", soeurs), ("vivier entier", autres)):
            for other in sorted(cells, key=lambda c: -targets[c]):
                marge = capacite.get(other, 0) - effectif[other]
                if marge <= 0 or reste == 0:
                    continue
                pris = min(marge, reste)
                effectif[other] += pris
                reste -= pris
                reports.append({"deficit": cell, "vers": other, "n": pris, "portee": portee})
            if reste == 0:
                break
        if reste:
            raise ValueError(f"impossible de compléter {cell} : {reste} persona(s) manquants "
                             "dans tout le vivier")
    return effectif, deficits, reports


def allocate(menages: list[Menage], targets: dict[str, int],
             n: int) -> tuple[dict[str, Menage], dict, dict, list, dict]:
    """Retient les ménages : effectifs de cellule, puis effectifs par sous-cellule, puis hachage.

    Les ménages entrent dans l'ordre de leur `sha256` À L'INTÉRIEUR de chaque sous-cellule —
    le déterminisme de la v4, à une dimension de plus.
    """
    effectif, deficits, reports = effectifs_par_cellule(menages, targets)
    inv = inventaire(menages)
    cibles_sc, alloc = allouer_sous_cellules(inv, effectif, n, cibles_allocation())

    par_sous_cellule: dict[SousCellule, list[Menage]] = defaultdict(list)
    for m in menages:
        par_sous_cellule[sous_cellule(m)].append(m)     # `menages` est déjà trié par rang
    chosen: dict[str, Menage] = {}
    taken: dict[str, int] = {c: 0 for c in targets}
    manques: list[dict] = []
    for key in sorted(cibles_sc):
        veut = cibles_sc[key]
        pris = 0
        for m in par_sous_cellule.get(key, []):
            if pris >= veut:
                break
            chosen[m.id] = m
            taken[key[0]] += m.size
            pris += 1
        if pris < veut:
            manques.append({"sous_cellule": _libelle(key), "manque_menages": veut - pris,
                            "manque_personnes": (veut - pris) * key[1]})

    # Garde-fou : l'inventaire borne le programme, donc une sous-cellule sous-remplie est
    # impossible par construction. Si elle arrive quand même, elle se comble DANS LA MÊME
    # CELLULE (les douze effectifs en personnes sont la contrainte à ne pas lâcher), puis dans
    # la même couronne, puis dans le vivier — journalisée, alarmée, code de sortie 1.
    if manques:
        logger.error("[ALARME] allocation : %d sous-cellule(s) sous-remplie(s) — %s ; report en "
                     "cours, la composition allouée n'est plus exacte", len(manques), manques)
        for manque in manques:
            reste = manque["manque_personnes"]
            cell = manque["sous_cellule"].split(" | ")[0]
            couronne = cell.split(" × ")[0]
            for portee, cibles_report in (
                    ("même cellule (autre sous-cellule)", [cell]),
                    ("même couronne", [c for c in targets
                                       if c.startswith(couronne + " × ") and c != cell]),
                    ("vivier entier", [c for c in targets if c != cell
                                       and not c.startswith(couronne + " × ")])):
                for other in sorted(cibles_report, key=lambda c: -targets[c]):
                    for m in menages:
                        if reste == 0:
                            break
                        if m.cellule != other or m.id in chosen or m.size > reste:
                            continue
                        chosen[m.id] = m
                        taken[other] += m.size
                        reste -= m.size
                        reports.append({"deficit": manque["sous_cellule"], "vers": other,
                                        "n": m.size, "portee": portee})
                    if reste == 0:
                        break
                if reste == 0:
                    break
            if reste:
                raise AllocationError(
                    f"sous-cellule {manque['sous_cellule']} sous-remplie de {reste} persona(s) "
                    "et rien à reporter dans tout le vivier")
            deficits[cell] = deficits.get(cell, 0) + manque["manque_personnes"]
    alloc["manques"] = manques
    alloc["retenus_par_sous_cellule"] = {
        _libelle(k): v for k, v in sorted(Counter(sous_cellule(m) for m in chosen.values()).items())}
    return chosen, taken, deficits, reports, alloc


# ── Descente sur marges multiples ─────────────────────────────────────────────

class _Etat:
    """Comptes par marge de la sélection courante ; perte en points, mise à jour incrémentale."""

    def __init__(self, marges_defs: list[tuple[str, Callable, dict[str, float]]]):
        self.defs = marges_defs
        self.counts: dict[str, Counter] = {nom: Counter() for nom, _, _ in marges_defs}
        self.fields: dict[str, float] = {nom: 0.0 for nom, _, _ in marges_defs}

    def add(self, persona, sign: int = 1) -> None:
        for nom, fn, _ in self.defs:
            mod = fn(persona)
            if mod is None:
                continue
            # Base ménage : le persona pèse l'inverse de la taille déclarée de son foyer.
            # Un poids nul (taille absente) retire la personne du champ de la marge sans la
            # retirer des autres — c'est la règle de `household_weight`, pas un repli.
            poids = persona.poids_menage if nom in DESCENTE_MARGES_MENAGE else 1.0
            if not poids:
                continue
            self.counts[nom][mod] += sign * poids
            self.fields[nom] += sign * poids

    def loss(self) -> float:
        total = 0.0
        for nom, _, target in self.defs:
            f = self.fields[nom]
            if f <= 1e-9:
                continue
            c = self.counts[nom]
            for mod, cible in target.items():
                total += abs(100.0 * c[mod] / f - cible)
        return total

    def snapshot(self) -> dict[str, dict[str, float]]:
        out = {}
        for nom, _, target in self.defs:
            f = self.fields[nom]
            out[nom] = {mod: (round(100.0 * self.counts[nom][mod] / f, 2) if f > 1e-9 else None)
                        for mod in target}
        return out


def descend(chosen: dict[str, Menage], menages: list[Menage], personas: dict[str, ctl.Persona],
            marges_defs: list[tuple[str, Callable, dict[str, float]]]) -> dict:
    """Échanges de ménages de MÊME SOUS-CELLULE qui réduisent la perte multi-marges.

    La sous-cellule est le triplet (cellule, effectif présent, taille déclarée) — la strate même
    de l'allocation. Un échange à sous-cellule constante laisse donc intacts, par construction,
    les douze effectifs de cellule en personnes, la taille de ménage en base personne et la
    motorisation en base ménage : la descente ne travaille plus que sur ce que l'allocation ne
    fixe pas. La v4 appariait sur (cellule, effectif présent) : la taille déclarée pouvait
    bouger, et avec elle le poids `1/taille` — ce qui rendait la motorisation ménage
    inatteignable par l'allocation seule.
    """
    t0 = time.monotonic()
    etat = _Etat(marges_defs)
    for m in chosen.values():
        for rec in m.membres:
            etat.add(personas[str(rec["person_id"])])
    avant = etat.snapshot()
    perte0 = etat.loss()
    # Candidats par sous-cellule, ordre de hachage.
    rest: dict[SousCellule, list[Menage]] = defaultdict(list)
    for m in menages:
        if m.id not in chosen:
            rest[sous_cellule(m)].append(m)

    swaps = passes = 0
    perte = perte0
    while passes < DESCENTE_PASSES_MAX:
        passes += 1
        improved = False
        for hid in sorted(chosen, key=lambda h: chosen[h].rank):
            h = chosen[hid]
            candidates = rest.get(sous_cellule(h), [])
            if not candidates:
                continue
            for rec in h.membres:
                etat.add(personas[str(rec["person_id"])], -1)
            best, best_loss = None, perte
            for x in candidates[:DESCENTE_CANDIDATS]:
                for rec in x.membres:
                    etat.add(personas[str(rec["person_id"])], +1)
                l = etat.loss()
                for rec in x.membres:
                    etat.add(personas[str(rec["person_id"])], -1)
                if l < best_loss - 1e-9:
                    best, best_loss = x, l
                    break   # première amélioration, dans l'ordre de hachage : déterministe
            if best is None:
                for rec in h.membres:
                    etat.add(personas[str(rec["person_id"])], +1)
                continue
            for rec in best.membres:
                etat.add(personas[str(rec["person_id"])], +1)
            del chosen[hid]
            chosen[best.id] = best
            candidates.remove(best)
            candidates.append(h)
            candidates.sort(key=lambda m: m.rank)
            perte = best_loss
            swaps += 1
            improved = True
        if not improved:
            break
    apres = etat.snapshot()
    marges_journal = {}
    for nom, _, target in marges_defs:
        ecart_avant = max((abs((avant[nom][k] or 0) - v) for k, v in target.items()), default=0.0)
        ecart_apres = max((abs((apres[nom][k] or 0) - v) for k, v in target.items()), default=0.0)
        marges_journal[nom] = {"cible_pct": target, "avant_pct": avant[nom], "apres_pct": apres[nom],
                               "ecart_max_avant_pt": round(ecart_avant, 2),
                               "ecart_max_apres_pt": round(ecart_apres, 2),
                               "champ": round(etat.fields[nom], 2),
                               "base": "menage" if nom in DESCENTE_MARGES_MENAGE else "personne",
                               "mesuree": etat.fields[nom] > 1e-9}
    non_mesurees = [nom for nom, j in marges_journal.items() if not j["mesuree"]]
    if non_mesurees:
        logger.warning("descente : marges sans aucune valeur sur le vivier, ignorées — %s "
                       "(traits non imputés avant la sélection ?)", non_mesurees)
    logger.info("descente : %d échanges en %d passe(s), perte %.1f → %.1f pt, %.1fs",
                swaps, passes, perte0, perte, time.monotonic() - t0)
    return {"marges": marges_journal, "echanges": swaps, "passes": passes,
            "perte_avant_pt": round(perte0, 2), "perte_apres_pt": round(perte, 2),
            "candidats_par_menage": DESCENTE_CANDIDATS, "marges_non_mesurees": non_mesurees,
            "duree_s": round(time.monotonic() - t0, 2)}


def _marges_defs(personas: dict[str, ctl.Persona]) -> list[tuple[str, Callable, dict[str, float]]]:
    defs = []
    for m in marges(JOINT_TARGET, MARGES_TARGET):
        if m.nom not in DESCENTE_MARGES or not m.mesurable:
            continue
        total = sum(m.cible_pct.values())
        target = {k: 100.0 * v / total for k, v in m.cible_pct.items()}
        defs.append((m.nom, (lambda p, nom=m.nom: ctl.modalite_of(p, nom)), target))
    return defs


# ── Sélection ─────────────────────────────────────────────────────────────────

def select(records: list[dict], n: int, joint_path: Path = JOINT_TARGET) -> tuple[list[dict], dict]:
    """Sélection stratifiée par ménages de `n` personas. Rend `(retenus, journal)`."""
    t0 = time.monotonic()
    joint = cible_jointe(joint_path)
    cells_pct = {f"{c} × {m}": float(joint["cible_pct"][c][m])
                 for c in COURONNES for m in MOTORISATION}
    targets = largest_remainder(cells_pct, n)

    menages, excluded = group_households(records)
    eligible = sum(m.size for m in menages)
    if eligible < n:
        raise ValueError(f"vivier insuffisant : {eligible} personas éligibles pour {n} demandés "
                         f"(exclus : {dict(excluded)})")
    chosen, taken, deficits, reports, allocation = allocate(menages, targets, n)
    assert sum(m.size for m in chosen.values()) == n, (sum(m.size for m in chosen.values()), n)
    sous_cellules_allouees = Counter(sous_cellule(m) for m in chosen.values())

    personas_list, _counters = ctl.normalize(records)
    personas = {p.id: p for p in personas_list}
    descente = descend(chosen, menages, personas, _marges_defs(personas))

    # Contrôle interne : la descente n'a déplacé ni effectif de cellule ni effectif total…
    cell_counts = Counter()
    for m in chosen.values():
        cell_counts[m.cellule] += m.size
    assert cell_counts == Counter({c: t for c, t in taken.items() if t}), "la descente a déplacé une cellule"
    # … ni aucune SOUS-CELLULE : c'est ce qui garantit que les deux marges allouées (taille de
    # ménage en base personne, motorisation en base ménage) sortent de la descente intactes.
    assert Counter(sous_cellule(m) for m in chosen.values()) == sous_cellules_allouees, \
        "la descente a déplacé une sous-cellule (cellule × effectif présent × taille déclarée)"
    retenus = [rec for m in chosen.values() for rec in m.membres]
    assert len(retenus) == n, (len(retenus), n)
    retenus.sort(key=lambda r: int(str(r.get("person_id"))) if str(r.get("person_id")).isdigit()
                 else str(r.get("person_id")))

    if deficits:
        logger.error("[ALARME] sélection : %d cellule(s) en déficit — %s — %d report(s) ; le vivier "
                     "est trop petit pour la cible jointe", len(deficits), dict(deficits),
                     sum(r["n"] for r in reports))
    by_cell_n = Counter()
    for m in menages:
        by_cell_n[m.cellule] += m.size
    for cell in targets:
        logger.info("cellule %-36s cible %4d · vivier %5d · retenus %4d", cell, targets[cell],
                    by_cell_n.get(cell, 0), taken[cell])

    sizes = Counter(m.size for m in chosen.values())
    perimetre = perimeter_journal(retenus)
    if perimetre["departements_representes"] < len(PERIMETRE["departements_attendus"]):
        logger.warning("périmètre : %d département(s) représenté(s) sur %d attendus — cadre de "
                       "tirage restreint (%s) ; la 3ᵉ couronne est amputée de ses communes "
                       "extérieures", perimetre["departements_representes"],
                       len(PERIMETRE["departements_attendus"]), perimetre["retenus_par_departement"])
    journal = {
        "version": SELECTION_RULE,
        "perimetre": perimetre,
        "regle": ("unité = ménage (household.id) ; effectifs de cellule proportionnels à la cible "
                  "jointe couronne × motorisation (base personne) par plus fort reste, puis "
                  "effectif cible par SOUS-CELLULE (cellule × effectif présent × taille déclarée) "
                  "par programme entier tenant " + " et ".join(ALLOCATION_MARGES) + " ; les ménages "
                  f"entrent dans l'ordre sha256('{SELECTION_NAMESPACE}:' + household_id) à "
                  "l'intérieur de leur sous-cellule ; exclus : hors périmètre, moins de 5 ans, "
                  "sans motorisation ; puis descente par échanges de ménages de MÊME SOUS-CELLULE "
                  "minimisant la somme des écarts absolus (en points) aux marges : "
                  + ", ".join(DESCENTE_MARGES)),
        "cible_jointe": {"fichier": str(joint_path), "version": joint.get("version"),
                         "sha256": ctl.sha256_of(joint_path)},
        "cibles_marges": {"fichier": str(MARGES_TARGET), "sha256": ctl.sha256_of(MARGES_TARGET)},
        "n_demande": n,
        "n_retenu": len(retenus),
        "vivier": {"n": len(records), "eligibles": eligible, "exclus": dict(excluded),
                   "menages": len(menages), "par_cellule": dict(by_cell_n)},
        "menages_retenus": {"n": len(chosen), "par_taille": {str(k): v for k, v in sorted(sizes.items())},
                            "membres_declares": sum(m.taille_declaree for m in chosen.values()),
                            "membres_presents": n},
        "cibles": targets,
        "retenus_par_cellule": taken,
        "deficits": deficits,
        "reports": reports,
        "allocation": allocation,
        "descente": descente,
        "person_ids": [str(r.get("person_id")) for r in retenus],
        "household_ids": sorted(chosen),
        "duree_s": round(time.monotonic() - t0, 2),
    }
    logger.info("sélection terminée en %.1fs : %d retenus (%d ménages) sur %d éligibles (%d exclus), "
                "%d sous-cellule(s) servie(s), écart maximal des marges allouées %.3f pt, "
                "%d déficit(s), %d sous-cellule(s) sous-remplie(s), %d échange(s)",
                journal["duree_s"], len(retenus), len(chosen), eligible, sum(excluded.values()),
                allocation["sous_cellules"]["servies"], allocation["ecart_max_pt"], len(deficits),
                len(allocation["manques"]), descente["echanges"])
    return retenus, journal


def cmd_select(args) -> int:
    if not args.pool.exists():
        logger.error("[ALARME] vivier introuvable : %s", args.pool)
        return 2
    records = ctl.load_population(args.pool)
    pool_digest = ctl.sha256_of(args.pool)
    logger.info("vivier : %s — %d personas, sha256 %s…", args.pool, len(records), pool_digest[:16])
    posed = ensure_residence_zone(records)
    try:
        chosen, journal = select(records, args.n)
    except (ReferenceError, ValueError) as exc:
        logger.error("[ALARME] sélection impossible : %s", exc)
        return 2
    journal["vivier"]["fichier"] = str(args.pool)
    journal["vivier"]["sha256"] = pool_digest
    journal["vivier"]["residence_zone"] = dict(posed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(chosen, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(args.out)
    journal["sortie"] = {"fichier": str(args.out), "sha256": ctl.sha256_of(args.out)}
    sel_path = args.selection_json or args.out.with_name(args.out.stem + "_selection.json")
    sel_path.write_text(json.dumps(journal, ensure_ascii=False, indent=1), encoding="utf-8")
    logger.info("écrit : %s (%d personas) et %s", args.out, len(chosen), sel_path)
    d = journal["descente"]
    print(f"{len(chosen)} personas retenus ({journal['menages_retenus']['n']} ménages) sur "
          f"{journal['vivier']['eligibles']} éligibles ({journal['vivier']['n']} au vivier) → {args.out}")
    per = journal["perimetre"]
    print(f"périmètre : {per['definition']} ; retenus par département : {per['retenus_par_departement']} "
          f"({per['departements_representes']}/{len(PERIMETRE['departements_attendus'])} départements, "
          f"{per['communes_distinctes']} communes"
          + (f", {per['retenus_sans_commune']} sans commune" if per['retenus_sans_commune'] else "") + ")")
    a = journal["allocation"]
    print(f"allocation : {a['sous_cellules']['servies']}/{a['sous_cellules']['vivier']} sous-cellules "
          f"servies, {a['menages']} ménages, tolérance retenue {a['tolerance']['retenue_pt']} pt "
          f"({a['tolerance']['programmes_resolus']} programmes entiers, {a['duree_s']}s) ; "
          f"{a['menages_deplaces_vs_vivier']} ménage(s) déplacé(s) par rapport au vivier")
    for nom in a["marges_allouees"]:
        pire = max(a["ecarts_pt"][nom], key=lambda m: abs(a["ecarts_pt"][nom][m]))
        print(f"   {nom:24s} écart max {a['ecarts_pt'][nom][pire]:+5.2f} pt sur « {pire} » (alloué)")
    print(f"descente : {d['echanges']} échange(s) en {d['passes']} passe(s), perte {d['perte_avant_pt']} → "
          f"{d['perte_apres_pt']} pt" + (f" ; marges non mesurées : {d['marges_non_mesurees']}"
                                        if d["marges_non_mesurees"] else ""))
    for nom, j in d["marges"].items():
        if j["mesuree"]:
            print(f"   {nom:24s} écart max {j['ecart_max_avant_pt']:5.2f} → {j['ecart_max_apres_pt']:5.2f} pt")
    code = 0
    if a["tolerance"]["depassee"]:
        print(f"⚠ marges allouées non tenues : écart maximal {a['ecart_max_pt']} pt "
              f"(> {a['tolerance']['borne_alarme_pt']} pt) — le vivier ne porte pas la composition "
              "de ménages qu'il faudrait ; écart à déclarer, pas à arrondir")
        code = 1
    if a["manques"]:
        print(f"⚠ {len(a['manques'])} sous-cellule(s) sous-remplie(s), reportée(s) : "
              + ", ".join(f"{m['sous_cellule']} −{m['manque_menages']} ménage(s)" for m in a["manques"]))
        code = 1
    if journal["deficits"]:
        print(f"⚠ {len(journal['deficits'])} cellule(s) en déficit, {sum(r['n'] for r in journal['reports'])} report(s) : "
              + ", ".join(f"{k} −{v}" for k, v in journal["deficits"].items()))
        code = 1
    return code


# ── Scellement ────────────────────────────────────────────────────────────────

def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=str(REPO_ROOT), capture_output=True,
                              text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return "inconnu"


def _resume_allocation(allocation: Optional[dict]) -> Optional[dict]:
    """Le résumé d'allocation porté par le MANIFEST : ce qui engage, sans les 130 sous-cellules.

    Le détail (cibles et retenus par sous-cellule, essais de la bissection) reste dans
    `selection.json`, scellé à côté.
    """
    if not allocation:
        return None
    tol = allocation.get("tolerance") or {}
    return {
        "methode": allocation.get("methode"),
        "marges_allouees": allocation.get("marges_allouees"),
        "ecarts_pt": allocation.get("ecarts_pt"),
        "ecart_max_pt": allocation.get("ecart_max_pt"),
        "tolerance_retenue_pt": tol.get("retenue_pt"),
        "tolerance_borne_alarme_pt": tol.get("borne_alarme_pt"),
        "tolerance_depassee": tol.get("depassee"),
        "programmes_entiers_resolus": tol.get("programmes_resolus"),
        "sous_cellules_servies": (allocation.get("sous_cellules") or {}).get("servies"),
        "sous_cellules_vivier": (allocation.get("sous_cellules") or {}).get("vivier"),
        "menages": allocation.get("menages"),
        "menages_deplaces_vs_vivier": allocation.get("menages_deplaces_vs_vivier"),
        "sous_cellules_sous_remplies": len(allocation.get("manques") or []),
    }


def cmd_seal(args) -> int:
    if not args.population.exists():
        logger.error("[ALARME] population introuvable : %s", args.population)
        return 2
    out_dir: Path = args.out_dir
    if out_dir.exists() and any(out_dir.iterdir()):
        logger.error("[ALARME] %s existe déjà et n'est pas vide : un dossier scellé ne se réécrit "
                     "pas. Choisissez un autre nom (--out-dir).", out_dir)
        return 2

    t0 = time.monotonic()
    try:
        report = ctl.run_control(args.population, args.borne, args.n_min, args.n_min_cellule)
    except (ReferenceError, ValueError, OSError) as exc:
        logger.error("[ALARME] contrôle impossible, rien n'est scellé : %s", exc)
        return 2
    verdicts = report["verdicts"]
    n = report["population"]["n"]
    if args.n and n != args.n:
        logger.error("[ALARME] effectif %d ≠ %d attendu — rien n'est scellé", n, args.n)
        print(ctl.render_text(report))
        return 1
    if verdicts[ctl.A_CORRIGER]:
        logger.error("[ALARME] %d marge(s) « à corriger » — le scellement est REFUSÉ, le fichier "
                     "candidat reste en place : %s", verdicts[ctl.A_CORRIGER], args.population)
        print(ctl.render_text(report))
        return 1

    selection = None
    if args.selection_json and args.selection_json.exists():
        selection = json.loads(args.selection_json.read_text(encoding="utf-8"))
    records = ctl.load_population(args.population)
    hors_perimetre = count_removed_out_of_perimeter(records)
    perimetre_manifest = {**PERIMETRE, **((selection or {}).get("perimetre") or {}),
                          "activites_hors_perimetre": hors_perimetre}
    if hors_perimetre["activites_hors_perimetre_supprimees"]:
        logger.warning("périmètre : %d activité(s) hors du polygone retirée(s) chez %d persona(s) — "
                       "hypothèse assumée, déclarée dans le MANIFEST",
                       hors_perimetre["activites_hors_perimetre_supprimees"], hors_perimetre["personas_touches"])
    if not hors_perimetre["controle"]:
        logger.warning("périmètre : les activités hors polygone n'ont PAS été contrôlées sur cette "
                       "population (clé `perimetre` absente : produite avant le garde-fou de l'étape 2)")

    out_dir.mkdir(parents=True, exist_ok=False)
    target = out_dir / "population.json"
    shutil.copy2(args.population, target)
    digest = ctl.sha256_of(target)
    (out_dir / "CONTROLE.md").write_text(ctl.render_markdown(report), encoding="utf-8")
    (out_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    if selection is not None:
        shutil.copy2(args.selection_json, out_dir / "selection.json")

    manifest = {
        "version": SEAL_VERSION,
        "nom": out_dir.name,
        "scelle_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "population": {"fichier": "population.json", "sha256": digest, "n": n,
                       "source": str(args.population), "source_sha256": report["population"]["sha256"]},
        "perimetre": perimetre_manifest,
        "selection": ({"fichier": "selection.json", "version": selection.get("version"),
                       "regle": selection.get("regle"),
                       "vivier": {k: v for k, v in selection.get("vivier", {}).items() if k != "par_cellule"},
                       "menages_retenus": selection.get("menages_retenus"),
                       "deficits": selection.get("deficits"), "reports": len(selection.get("reports", [])),
                       "allocation": _resume_allocation(selection.get("allocation")),
                       "descente": {k: v for k, v in (selection.get("descente") or {}).items() if k != "marges"}}
                      if selection else "aucune (population fournie telle quelle)"),
        "controle": {"rapport": "CONTROLE.md", "verdicts": verdicts,
                     "borne_tost_pt": args.borne, "n_min": args.n_min, "n_min_cellule": args.n_min_cellule,
                     "cible_jointe": report["parametres"]["cible_jointe"],
                     "cibles_marges": report["parametres"].get("cibles_marges"),
                     "menages_et_mobilite": report.get("menages_et_mobilite"),
                     "synthese_des_ecarts": report["synthese"]},
        "depot": {"git_head": _git("rev-parse", "HEAD"), "branche": _git("rev-parse", "--abbrev-ref", "HEAD"),
                  "arbre_propre": _git("status", "--porcelain") == ""},
        "regle": ("Ce dossier ne se modifie pas. Toute correction de la population produit un "
                  "nouveau dossier scellé ; les jeux gelés et les runs qui citent celui-ci "
                  "citent son sha256."),
        "note": args.note or "",
    }
    (out_dir / "MANIFEST.yaml").write_text(
        "# Population scellée pour l'article AAMAS — ne pas modifier (cf. `regle`).\n"
        + yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8")
    logger.info("scellé en %.1fs → %s (sha256 %s…)", time.monotonic() - t0, out_dir, digest[:16])
    print(ctl.render_text(report))
    print(f"\n✅ Scellé : {out_dir} — {n} personas, sha256 {digest}")
    if verdicts[ctl.A_PUBLIER]:
        print(f"   {verdicts[ctl.A_PUBLIER]} marge(s) « à publier » — voir la synthèse des écarts de CONTROLE.md")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("select", help="sélection stratifiée par ménages de N personas dans un vivier")
    s.add_argument("--pool", type=Path, required=True)
    s.add_argument("--n", type=int, default=1000)
    s.add_argument("--out", type=Path, required=True)
    s.add_argument("--selection-json", type=Path, default=None,
                   help="journal de sélection (défaut : <out>_selection.json)")
    s.set_defaults(func=cmd_select)
    z = sub.add_parser("seal", help="contrôler puis sceller une population finale")
    z.add_argument("--population", type=Path, required=True)
    z.add_argument("--out-dir", type=Path, default=DEFAULT_SEAL_DIR)
    z.add_argument("--n", type=int, default=1000, help="effectif exigé (0 = ne pas vérifier)")
    z.add_argument("--selection-json", type=Path, default=None)
    z.add_argument("--borne", type=float, default=1.0)
    z.add_argument("--n-min", type=int, default=30)
    z.add_argument("--n-min-cellule", type=int, default=50)
    z.add_argument("--note", type=str, default=None, help="note libre (paramètres de génération…)")
    z.set_defaults(func=cmd_seal)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s — %(message)s")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
