"""Périmètre d'admission de la population au chargement (ticket 031, partie 2).

Le périmètre d'étude est celui de l'enquête EMC² 2023 : les **453 communes** de six départements,
délimitées par le polygone des communes (`llm_module/data/couronne_perimetre.geojson`, table
`llm_module/data/commune_couronne.json`). Jusqu'au 2026-09-03, `_prepare_population` filtrait
sur un RECTANGLE — `TOULOUSE_OSM_ROUTES_30K_BBOX`, le plus grand rectangle inscrit dans le graphe
OSMnx de 30 km — et écartait tout agent dont le domicile ou UNE SEULE activité sortait du
rectangle : 79 agents de la v3, toute la 3ᵉ couronne de la v4, donc un sceau refusé.

Ce que ce module décide, et dans cet ordre :

1. **Le domicile fait le périmètre, et c'est la commune qui tranche.** `household.commune_id`
   (renseigné pour tous les personas depuis la v4) ∈ 453 → admis ; renseigné et hors des 453 →
   rejeté. Sans commune, le trait `residence_zone` (ticket 021) décide : une couronne → admis,
   `hors périmètre` → rejeté. Sans l'un ni l'autre, la GÉOMÉTRIE tranche (le domicile est-il dans
   le polygone ?) et une `[ALARME]` dit que le périmètre n'a pas été vérifié par la commune —
   ce n'est pas un repli dégradé (même périmètre, autre mesure), mais une population non
   enrichie doit se voir à chaque chargement.
2. **Une activité hors du polygone n'écarte pas l'agent** (école ou lieu de travail hors
   périmètre : décision de l'auteur, question 3 du ticket 031). Elle est comptée, journalisée, et
   une `[ALARME]` se lève sur front montant au-dessus de `ACTIVITY_OUTSIDE_ALARM_SHARE` (1 % des
   activités localisées : au-delà, c'est la population ou le périmètre qui a changé, pas quelques
   destinations périphériques). Le graphe OSMnx du polygone ne couvre pas ces points : leur trajet
   se rabat sur le nœud le plus proche du bord, ce que le compteur rend visible.
3. **Un fichier scellé se charge entier ou se refuse** — `sealed_population_complete` : l'effectif
   après filtre doit être exactement `population_size`, sinon `[ALARME]` et rien n'est chargé.

Le second filtre de la chaîne (`world/population.py` → `eqasim_loader.perimeter_verdict`, sur le
trait `residence_zone`) est déjà par périmètre et reste tel quel : les deux disent la même chose,
la commune du domicile est dans les 453 ou n'y est pas.
"""

from __future__ import annotations

import functools
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from loguru import logger

from models import BBox

from llm_module.core.population_reference import COURONNES, OUT_OF_PERIMETER
from llm_module.core.residence_zone import TRAIT_KEY as RESIDENCE_TRAIT_KEY

PERIMETER_LABEL = "453 communes, six départements, polygone communal"

# Part des activités localisées (hors domicile) hors du polygone au-delà de laquelle l'alarme se
# lève. 1 % : recommandation de la question ouverte n° 3 du ticket 031 (au-delà, étendre le graphe).
ACTIVITY_OUTSIDE_ALARM_SHARE = 0.01

# Valeurs de `household.commune_id` qui comptent comme « non renseigné » (export eqasim v3 :
# « undefined »).
_UNDEFINED = frozenset({"", "undefined", "none", "null", "nan"})

# Nombre d'exemples de rejets détaillés dans le journal (le compte complet est toujours donné).
_MAX_REJECT_EXAMPLES = 10


@dataclass
class PerimeterStats:
    """Ce que le filtre a vu et décidé — journalisé en une ligne, et rendu à l'appelant."""

    total: int = 0
    kept: int = 0
    admitted_by_commune: int = 0
    admitted_by_trait: int = 0
    admitted_by_geometry: int = 0
    rejected_commune_outside: int = 0
    rejected_trait_outside: int = 0
    rejected_geometry_outside: int = 0
    rejected_no_home: int = 0
    activities_located: int = 0       # activités hors domicile avec des coordonnées
    activities_outside: int = 0       # … dont hors du polygone des 453 communes
    agents_with_activity_outside: int = 0
    duration_s: float = 0.0

    @property
    def rejected(self) -> int:
        return self.total - self.kept

    @property
    def unverified_by_commune(self) -> int:
        """Personas jugés par la géométrie faute de commune et de trait."""
        return self.admitted_by_geometry + self.rejected_geometry_outside

    @property
    def activities_outside_share(self) -> float:
        return self.activities_outside / self.activities_located if self.activities_located else 0.0

    def as_dict(self) -> dict:
        d = asdict(self)
        d["rejected"] = self.rejected
        d["activities_outside_share"] = round(self.activities_outside_share, 5)
        return d


class PopulationPerimeter:
    """Les 453 communes (table INSEE) et leur polygone dissous (WGS84), chargés une fois."""

    def __init__(self, communes, polygon, label: str = PERIMETER_LABEL) -> None:
        from shapely import prepare

        self.communes = communes          # llm_module.core.residence_zone.CommuneTable
        self.polygon = polygon            # shapely (Multi)Polygon, EPSG:4326
        prepare(self.polygon)
        min_lon, min_lat, max_lon, max_lat = polygon.bounds
        self.bbox = BBox(min_lon=min_lon, min_lat=min_lat, max_lon=max_lon, max_lat=max_lat)
        self.label = label

    @classmethod
    def load(cls, geojson: Optional[Path] = None, commune_table: Optional[Path] = None) -> "PopulationPerimeter":
        """Charge la géométrie des couronnes et la table des communes. Jamais de repli sur un rectangle."""
        from llm_module.core.residence_zone import (DEFAULT_GEOJSON, CommuneTable,
                                                     ResidenceZoneError)

        path = Path(geojson) if geojson else DEFAULT_GEOJSON
        if not path.exists():
            raise ResidenceZoneError(
                f"géométrie des couronnes absente : {path} (`make communes-couronnes`). Sans elle, "
                "le périmètre d'admission ne se calcule pas — rien n'est chargé à sa place.")
        import geopandas as gpd

        t0 = time.monotonic()
        layer = gpd.read_file(path).to_crs(4326)
        inconnues = sorted(set(map(str, layer["couronne"])) - set(COURONNES))
        if inconnues:
            raise ResidenceZoneError(f"couronnes inattendues dans {path.name} : {inconnues}.")
        polygon = layer.union_all() if hasattr(layer, "union_all") else layer.unary_union
        communes = CommuneTable.load(commune_table)
        perimeter = cls(communes, polygon)
        logger.info(
            f"[perimetre] {perimeter.label} : {len(communes)} communes, polygone "
            f"{polygon.geom_type} lon {perimeter.bbox.min_lon:.3f}→{perimeter.bbox.max_lon:.3f} "
            f"lat {perimeter.bbox.min_lat:.3f}→{perimeter.bbox.max_lat:.3f}, chargé en "
            f"{time.monotonic() - t0:.1f}s depuis {path.name}")
        return perimeter

    # ── Tests d'appartenance ─────────────────────────────────────────────────

    def contains(self, lon: float, lat: float) -> bool:
        from shapely import contains_xy

        return bool(contains_xy(self.polygon, lon, lat))

    def home_verdict(self, entry: dict) -> tuple[bool, str]:
        """`(admis, motif)` d'un enregistrement eqasim (dict brut).

        Motif si admis : `commune`, `trait` ou `geometrie` — ce qui a tranché. Motif si rejeté :
        `sans domicile`, `commune hors périmètre`, `trait hors périmètre`, `zone inconnue (…)`,
        `géométrie hors polygone`.
        """
        identity = entry.get("identity") or {}
        home = identity.get("home") or {}
        lon, lat = home.get("lon"), home.get("lat")
        if lon is None or lat is None:
            return False, "sans domicile"

        insee = str((entry.get("household") or {}).get("commune_id") or "").strip()
        if insee.lower() not in _UNDEFINED:
            if self.communes.contains(insee):
                return True, "commune"
            return False, "commune hors périmètre"

        zone = (identity.get("traits_json") or {}).get(RESIDENCE_TRAIT_KEY)
        if zone:
            if zone in COURONNES:
                return True, "trait"
            if zone == OUT_OF_PERIMETER:
                return False, "trait hors périmètre"
            return False, f"zone inconnue ({zone})"

        if self.contains(float(lon), float(lat)):
            return True, "geometrie"
        return False, "géométrie hors polygone"

    def activities_outside(self, entry: dict) -> tuple[int, int]:
        """`(hors polygone, localisées)` parmi les activités hors domicile de l'enregistrement."""
        outside = located = 0
        for act in (entry.get("identity") or {}).get("activities") or []:
            if act.get("purpose") == "home":
                continue
            loc = act.get("location") or {}
            lon, lat = loc.get("lon"), loc.get("lat")
            if lon is None or lat is None:
                continue
            located += 1
            if not self.contains(float(lon), float(lat)):
                outside += 1
        return outside, located


@functools.lru_cache(maxsize=1)
def load_population_perimeter() -> PopulationPerimeter:
    """Le périmètre du dépôt, chargé une fois par processus."""
    return PopulationPerimeter.load()


# ── Filtre ───────────────────────────────────────────────────────────────────

_activity_alarm_on = False


def filter_population(raw: list, perimeter: PopulationPerimeter,
                      source: str = "population") -> tuple[list, PerimeterStats]:
    """Garde les enregistrements dont le domicile est dans le périmètre ; compte le reste.

    Journalise une ligne de synthèse (succès explicite compris), jusqu'à dix rejets détaillés,
    une `[ALARME]` si des personas ont dû être jugés par la géométrie, et une `[ALARME]` sur front
    montant si la part d'activités hors polygone dépasse `ACTIVITY_OUTSIDE_ALARM_SHARE`.
    """
    global _activity_alarm_on

    t0 = time.monotonic()
    stats = PerimeterStats(total=len(raw))
    kept: list = []
    rejects: Counter = Counter()
    examples: list[str] = []

    for entry in raw:
        admis, motif = perimeter.home_verdict(entry)
        if not admis:
            rejects[motif] += 1
            if motif == "sans domicile":
                stats.rejected_no_home += 1
            elif motif == "commune hors périmètre":
                stats.rejected_commune_outside += 1
            elif motif == "géométrie hors polygone":
                stats.rejected_geometry_outside += 1
            else:
                stats.rejected_trait_outside += 1
            if len(examples) < _MAX_REJECT_EXAMPLES:
                home = (entry.get("identity") or {}).get("home") or {}
                insee = (entry.get("household") or {}).get("commune_id")
                examples.append(f"{entry.get('person_id', '?')} ({motif}, commune={insee}, "
                                f"lat={home.get('lat')}, lon={home.get('lon')})")
            continue

        kept.append(entry)
        stats.kept += 1
        if motif == "commune":
            stats.admitted_by_commune += 1
        elif motif == "trait":
            stats.admitted_by_trait += 1
        else:
            stats.admitted_by_geometry += 1

        outside, located = perimeter.activities_outside(entry)
        stats.activities_located += located
        stats.activities_outside += outside
        if outside:
            stats.agents_with_activity_outside += 1

    stats.duration_s = round(time.monotonic() - t0, 3)

    detail = ", ".join(f"{n} {m}" for m, n in rejects.most_common()) or "aucun rejet"
    logger.info(
        f"[{source}] filtre de périmètre ({perimeter.label}) : {stats.total} → {stats.kept} agents "
        f"en {stats.duration_s:.2f}s — admis par commune {stats.admitted_by_commune}, par trait "
        f"{stats.admitted_by_trait}, par géométrie {stats.admitted_by_geometry} ; écartés "
        f"{stats.rejected} ({detail}) ; activités hors polygone {stats.activities_outside} / "
        f"{stats.activities_located} localisées ({100 * stats.activities_outside_share:.2f} %, "
        f"{stats.agents_with_activity_outside} agent(s) concerné(s))")
    for ex in examples:
        logger.warning(f"[{source}] agent écarté du périmètre : {ex}")

    if stats.unverified_by_commune:
        # Pas de front montant : c'est un état de la population, il doit se voir à chaque chargement.
        logger.error(
            f"[ALARME] [{source}] {stats.unverified_by_commune}/{stats.total} persona(s) sans "
            f"`household.commune_id` ni trait `{RESIDENCE_TRAIT_KEY}` : leur périmètre a été jugé "
            f"par la géométrie du polygone ({stats.admitted_by_geometry} admis, "
            f"{stats.rejected_geometry_outside} rejetés), pas par la commune du domicile. "
            "Population antérieure à la v4 : régénérez-la ou enrichissez-la (`make residence-zone`).")

    share = stats.activities_outside_share
    if share > ACTIVITY_OUTSIDE_ALARM_SHARE:
        if not _activity_alarm_on:
            _activity_alarm_on = True
            logger.error(
                f"[ALARME] [{source}] {stats.activities_outside} activité(s) sur "
                f"{stats.activities_located} ({100 * share:.2f} %) hors du polygone des 453 communes, "
                f"au-dessus du seuil de {100 * ACTIVITY_OUTSIDE_ALARM_SHARE:.0f} %. Les agents sont "
                "gardés (le domicile fait le périmètre) mais le graphe OSMnx du polygone ne couvre pas "
                "ces points : leurs trajets se rabattent sur le bord du graphe. Une population ou un "
                "périmètre a changé — étendre le polygone du graphe ou revoir la population.")
    elif _activity_alarm_on:
        _activity_alarm_on = False
        logger.info(f"[{source}] part d'activités hors polygone revenue sous le seuil "
                    f"({100 * share:.2f} %) — alarme levée")
    return kept, stats


def sealed_population_complete(sealed_path: str, kept: int, population_size: int,
                               stats: Optional[PerimeterStats] = None) -> bool:
    """Un sceau se prend entier : `kept == population_size`, sinon `[ALARME]` et refus.

    Ré-échantillonner 1 000 agents dans un fichier scellé de 1 000 dont le filtre a écarté 12
    reviendrait à publier une population qui n'est plus celle du MANIFEST — sans que rien ne le
    signale.
    """
    if kept == population_size:
        logger.info(f"[population] Population scellée chargée entière : {kept}/{population_size} "
                    f"agents, 0 écarté au chargement — {sealed_path}")
        return True
    ecartes = f" ({stats.rejected} écartés par le filtre de périmètre)" if stats is not None else ""
    logger.error(
        f"[ALARME] [population] Population scellée {sealed_path} : {kept} agents après filtre de "
        f"périmètre pour population_size={population_size}{ecartes}. Un sceau ne se rogne pas : "
        "alignez population_size sur l'effectif scellé, ou corrigez la population (domiciles hors "
        "des 453 communes). Rien n'est chargé.")
    return False


# ── Emprise du monde ─────────────────────────────────────────────────────────

def world_extent(stops_bbox: Optional[BBox], perimeter: Optional[PopulationPerimeter] = None) -> BBox:
    """Enveloppe du monde : polygone des 453 communes ∪ emprise des arrêts GTFS (± tampon).

    `WorldGrid` assertionne que toute localisation est dans son rectangle : avant le 2026-09-03 ce
    rectangle était celui des arrêts Tisséo ± 0,05°, qui ne contient que 221 des 453 communes —
    un domicile de 3ᵉ couronne y faisait tomber l'assertion. Le monde couvre désormais le
    périmètre entier ; l'union avec les arrêts garde tout arrêt GTFS dans la grille.
    """
    perimeter = perimeter or load_population_perimeter()
    p = perimeter.bbox
    if stops_bbox is None:
        extent = BBox(min_lon=p.min_lon, min_lat=p.min_lat, max_lon=p.max_lon, max_lat=p.max_lat)
    else:
        extent = BBox(
            min_lon=min(p.min_lon, stops_bbox.min_lon), min_lat=min(p.min_lat, stops_bbox.min_lat),
            max_lon=max(p.max_lon, stops_bbox.max_lon), max_lat=max(p.max_lat, stops_bbox.max_lat),
        )
    logger.info(
        f"[world] emprise du monde = polygone des 453 communes ∪ arrêts GTFS : "
        f"lon {extent.min_lon:.4f}→{extent.max_lon:.4f}, lat {extent.min_lat:.4f}→{extent.max_lat:.4f} "
        f"(polygone seul : {p.min_lon:.4f}→{p.max_lon:.4f}, {p.min_lat:.4f}→{p.max_lat:.4f})")
    return extent
