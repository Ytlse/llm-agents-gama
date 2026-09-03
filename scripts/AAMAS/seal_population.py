"""seal_population.py — Sélectionner 1 000 personas pile, par MÉNAGES, dans un vivier ; puis sceller.

    # 1. sélection stratifiée dans le vivier généré et pré-imputé (avant le routage du notebook)
    llm-agents/.venv/bin/python -m scripts.AAMAS.seal_population select \\
        --pool scripts/data/population/Temp/4_zone_enriched/toulouse_population_10000.json \\
        --n 1000 --out scripts/data/population/Temp/4_zone_enriched/toulouse_population_1000_AAMAS.json

    # 2. scellement du fichier final, APRÈS post-traitements et contrôle
    llm-agents/.venv/bin/python -m scripts.AAMAS.seal_population seal \\
        --population data/population/toulouse_population_1000_AAMAS.json \\
        --out-dir data/population/population_1000_AAMAS_v4

POURQUOI UNE SÉLECTION. Le service eqasim tire `population_size × 1,15` personnes et renomme
le fichier à la taille DEMANDÉE : `toulouse_population_1000.json` en contient 1 021. Un
effectif rond ne se règle donc pas à la génération. Et une sélection au hasard gaspille la
précision : la note de dimensionnement (§ 4.3.1) demande un tirage STRATIFIÉ sur les strates
mêmes qui serviront à la validation — « 1 000 agents stratifiés valent ≈ 2 000 tirés au hasard ».

LA RÈGLE v4 (`aamas_seal_v4`, ticket 031). Même mécanique que la v3 (ticket 029), avec les
SIX CLASSES D'ÂGE publiées par le rapport AUAT (p. 11) dans la descente — la v3 tenait les quinze
classes quinquennales, qui ne tiennent pas la part des 5-17 ans (+1,2 pt mesuré) —, un espace de
noms de hachage distinct (`aamas_seal_v4:`), et un journal du PÉRIMÈTRE : la définition (453
communes de l'EMC² 2023, polygone communal, table `commune_couronne.json` cc1) et les
départements de résidence des retenus, lus sur `household.commune_id`. Les cibles `cj1` / `cm1`
ne changent pas : elles sont calculées sur les 453 communes. En trois temps :

1. **L'unité est le ménage** (`household.id`, à la racine des enregistrements depuis l'export
   élargi). La v2 sélectionnait des personnes : 1 000 retenus venaient de 865 ménages dont 308
   complets. Un ménage a UNE couronne et UNE motorisation (attributs du ménage : 0 ménage mixte
   mesuré sur 2 791), donc une cellule ; ses membres de 5 ans et + sont tous dans le vivier
   depuis que l'export garde les immobiles — les seuls absents sont les enfants de moins de
   5 ans, hors population enquêtée. Une population sans `household.id` (antérieure à l'export
   élargi) est traitée par ménages d'une personne, et le journal le dit.

2. **Allocation par cellule** : les 12 cellules couronne × motorisation de la cible jointe sur
   base personne (`cible_jointe_couronne_motorisation.yaml`), effectifs en personnes par plus
   fort reste ; les ménages entrent dans l'ordre de `sha256("aamas_seal_v4:" + household_id)`,
   un ménage n'entre que s'il tient dans le reste de sa cellule. Une cellule que le vivier ne
   remplit pas est un DÉFICIT : comblé d'abord dans la même couronne, puis dans le vivier
   entier, journalisé, alarmé, et code de sortie 1.

3. **Descente sur marges multiples** : tant qu'un échange de deux ménages de MÊME TAILLE et de
   MÊME CELLULE — l'un retenu, l'autre non — réduit la perte, on l'applique. La perte est la
   somme, sur toutes les marges contrôlées (occupation et six classes d'âge publiées p. 11 ; âge
   quinquennal, genre, taille de ménage, permis, abonnement TC, logement, immobiles : recalculs
   gelés `cm1`), des
   écarts absolus en points entre la part observée et la cible. Ordre de parcours et de
   candidature = hachage : déterministe, rejouable. Les effectifs des cellules ne bougent pas
   d'une unité ; les traits imputés doivent donc être posés SUR LE VIVIER avant la sélection
   (étape 3ter-a du notebook), sinon la marge est vide et la descente l'ignore — en le disant.

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

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from llm_module.core.population_reference import COURONNES, MIN_AGE, OUT_OF_PERIMETER  # noqa: E402
from scripts.AAMAS import control_population as ctl  # noqa: E402
from scripts.AAMAS.reference_marges import (  # noqa: E402
    JOINT_TARGET, MARGES_PERSONNE, MARGES_TARGET, MOTORISATION, Marge, ReferenceError,
    cible_jointe, marges, motorisation_class)

logger = logging.getLogger("aamas.seal")

SELECTION_NAMESPACE = "aamas_seal_v4"   # sel du hachage des MÉNAGES
SELECTION_RULE = "aamas_seal_v4"
SEAL_VERSION = "sceau1"
DEFAULT_SEAL_DIR = REPO_ROOT / "data" / "population" / "population_1000_AAMAS_v4"

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
DESCENTE_MARGES: tuple[str, ...] = ("occupation", "classe_age", *MARGES_PERSONNE)
# Candidats examinés par ménage retenu et par passe (ordre de hachage). Borne le coût sans
# changer le déterminisme ; 150 suffit largement sur un vivier de 10 000.
DESCENTE_CANDIDATS = 150
DESCENTE_PASSES_MAX = 40


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


# ── Allocation ────────────────────────────────────────────────────────────────

def allocate(menages: list[Menage], targets: dict[str, int]) -> tuple[dict[str, Menage], dict, dict, list]:
    by_cell: dict[str, list[Menage]] = defaultdict(list)
    for m in menages:
        by_cell[m.cellule].append(m)
    chosen: dict[str, Menage] = {}
    taken: dict[str, int] = {c: 0 for c in targets}
    deficits: dict[str, int] = {}
    for cell, want in targets.items():
        remaining = want
        for m in by_cell.get(cell, []):
            if m.size <= remaining:
                chosen[m.id] = m
                remaining -= m.size
                if remaining == 0:
                    break
        taken[cell] = want - remaining
        if remaining:
            deficits[cell] = remaining

    reports: list[dict] = []
    for cell, short in list(deficits.items()):
        couronne = cell.split(" × ")[0]
        remaining = short
        # 1) même couronne : la marge spatiale déplace les cibles modales de 30 points.
        siblings = [c for c in targets if c.startswith(couronne + " × ") and c != cell]
        others = [c for c in targets if c != cell and c not in siblings]
        for portee, cells in (("même couronne", siblings), ("vivier entier", others)):
            for other in sorted(cells, key=lambda c: -targets[c]):
                for m in by_cell.get(other, []):
                    if remaining == 0:
                        break
                    if m.id in chosen or m.size > remaining:
                        continue
                    chosen[m.id] = m
                    taken[other] += m.size
                    remaining -= m.size
                    reports.append({"deficit": cell, "vers": other, "n": m.size, "portee": portee})
                if remaining == 0:
                    break
            if remaining == 0:
                break
        if remaining:
            raise ValueError(f"impossible de compléter {cell} : {remaining} persona(s) manquants "
                             "dans tout le vivier")
    return chosen, taken, deficits, reports


# ── Descente sur marges multiples ─────────────────────────────────────────────

class _Etat:
    """Comptes par marge de la sélection courante ; perte en points, mise à jour incrémentale."""

    def __init__(self, marges_defs: list[tuple[str, Callable, dict[str, float]]]):
        self.defs = marges_defs
        self.counts: dict[str, Counter] = {nom: Counter() for nom, _, _ in marges_defs}
        self.fields: dict[str, int] = {nom: 0 for nom, _, _ in marges_defs}

    def add(self, persona, sign: int = 1) -> None:
        for nom, fn, _ in self.defs:
            mod = fn(persona)
            if mod is None:
                continue
            self.counts[nom][mod] += sign
            self.fields[nom] += sign

    def loss(self) -> float:
        total = 0.0
        for nom, _, target in self.defs:
            f = self.fields[nom]
            if f <= 0:
                continue
            c = self.counts[nom]
            for mod, cible in target.items():
                total += abs(100.0 * c[mod] / f - cible)
        return total

    def snapshot(self) -> dict[str, dict[str, float]]:
        out = {}
        for nom, _, target in self.defs:
            f = self.fields[nom]
            out[nom] = {mod: (round(100.0 * self.counts[nom][mod] / f, 2) if f else None)
                        for mod in target}
        return out


def descend(chosen: dict[str, Menage], menages: list[Menage], personas: dict[str, ctl.Persona],
            marges_defs: list[tuple[str, Callable, dict[str, float]]]) -> dict:
    """Échanges de ménages de même taille et même cellule qui réduisent la perte multi-marges."""
    t0 = time.monotonic()
    etat = _Etat(marges_defs)
    for m in chosen.values():
        for rec in m.membres:
            etat.add(personas[str(rec["person_id"])])
    avant = etat.snapshot()
    perte0 = etat.loss()
    # Candidats par (cellule, taille), ordre de hachage.
    rest: dict[tuple[str, int], list[Menage]] = defaultdict(list)
    for m in menages:
        if m.id not in chosen:
            rest[(m.cellule, m.size)].append(m)

    swaps = passes = 0
    perte = perte0
    while passes < DESCENTE_PASSES_MAX:
        passes += 1
        improved = False
        for hid in sorted(chosen, key=lambda h: chosen[h].rank):
            h = chosen[hid]
            candidates = rest.get((h.cellule, h.size), [])
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
                               "champ": etat.fields[nom],
                               "mesuree": etat.fields[nom] > 0}
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
    chosen, taken, deficits, reports = allocate(menages, targets)
    assert sum(m.size for m in chosen.values()) == n, (sum(m.size for m in chosen.values()), n)

    personas_list, _counters = ctl.normalize(records)
    personas = {p.id: p for p in personas_list}
    descente = descend(chosen, menages, personas, _marges_defs(personas))

    # Contrôle interne : la descente n'a déplacé ni effectif de cellule ni effectif total.
    cell_counts = Counter()
    for m in chosen.values():
        cell_counts[m.cellule] += m.size
    assert cell_counts == Counter({c: t for c, t in taken.items() if t}), "la descente a déplacé une cellule"
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
        "regle": ("unité = ménage (household.id) ; allocation proportionnelle à la cible jointe "
                  "couronne × motorisation (base personne), effectifs par plus fort reste, ménages "
                  f"dans l'ordre sha256('{SELECTION_NAMESPACE}:' + household_id) s'ils tiennent dans "
                  "la cellule ; exclus : hors périmètre, moins de 5 ans, sans motorisation ; puis "
                  "descente par échanges de ménages de même taille et même cellule minimisant la "
                  "somme des écarts absolus (en points) aux marges : " + ", ".join(DESCENTE_MARGES)),
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
        "descente": descente,
        "person_ids": [str(r.get("person_id")) for r in retenus],
        "household_ids": sorted(chosen),
        "duree_s": round(time.monotonic() - t0, 2),
    }
    logger.info("sélection terminée en %.1fs : %d retenus (%d ménages) sur %d éligibles (%d exclus), "
                "%d déficit(s), %d échange(s)", journal["duree_s"], len(retenus), len(chosen), eligible,
                sum(excluded.values()), len(deficits), descente["echanges"])
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
    print(f"descente : {d['echanges']} échange(s) en {d['passes']} passe(s), perte {d['perte_avant_pt']} → "
          f"{d['perte_apres_pt']} pt" + (f" ; marges non mesurées : {d['marges_non_mesurees']}"
                                        if d["marges_non_mesurees"] else ""))
    for nom, j in d["marges"].items():
        if j["mesuree"]:
            print(f"   {nom:24s} écart max {j['ecart_max_avant_pt']:5.2f} → {j['ecart_max_apres_pt']:5.2f} pt")
    if journal["deficits"]:
        print(f"⚠ {len(journal['deficits'])} cellule(s) en déficit, {sum(r['n'] for r in journal['reports'])} report(s) : "
              + ", ".join(f"{k} −{v}" for k, v in journal["deficits"].items()))
        return 1
    return 0


# ── Scellement ────────────────────────────────────────────────────────────────

def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=str(REPO_ROOT), capture_output=True,
                              text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return "inconnu"


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
