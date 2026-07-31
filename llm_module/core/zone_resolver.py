"""
core/zone_resolver.py — Du point aux variables géographiques du choix modal.

Les six features `source: "geo"` de `feature_spec.json` (`od_km`, `same_zone`,
`dist_center_orig_km`, `dist_center_dest_km`, `density_orig`, `density_dest`)
dérivent toutes d'un même préalable : rattacher un point à sa **zone fine** de
l'enquête EMC². À l'entraînement ce rattachement est donné (`D3`/`D7` du fichier
déplacements) ; en simulation il n'y a que des coordonnées. Ce module rejoue donc la
jointure spatiale, et **uniquement à la formule de l'entraînement** :

- `od_km` est une distance entre **centroïdes de zones**, jamais entre les points
  exacts. La tentation d'une haversine origine→destination donne un facteur 2 sur les
  trajets intra-zone (0.65 km contre 1.29 km, ticket 005 §2.1) — or ce sont les
  trajets courts, ceux où marche, vélo et voiture se disputent réellement la
  décision, et `od_km` est de loin la première feature du modèle ;
- pour un trajet intra-zone la distance entre centroïdes vaut 0 : elle est remplacée
  par la longueur caractéristique de la zone, `0.5 × √surface`. `same_zone`
  accompagne la valeur pour que le modèle sache qu'elle est imputée, pas mesurée ;
- `density_*` et `dist_center_*` sont lues telles quelles dans la ressource, calculées
  une fois pour toutes par le constructeur du jeu d'entraînement. L'hypercentre n'est
  pas redéclaré ici : il est déjà cuit dans `dist_center_km`, et les appelants qui en
  ont besoin en clair (les couronnes de résidence du move-log) le lisent dans
  `core.geo_reference`, qui sert aussi le garde-fou de `load` ci-dessous.

**Le rattachement est une jointure point-dans-polygone, pas un plus proche voisin.**
Rattacher au centroïde le plus proche revient à un découpage de Voronoï, qui ne
ressemble pas à des zones administratives allongées et très inégales : mesuré à
72,9 % d'accord seulement, avec 1,19 km d'écart médian quand il se trompe.

**Hors couche, on ne devine pas.** ~5 % des localisations de la population synthétique
tombent hors du périmètre d'enquête, à 22,8 km en médiane de la zone la plus proche :
ce sont des communes franchement extérieures, pas des cas limites. `resolve` renvoie
alors `None` et `geo_features` aussi — au appelant de basculer sur sa politique de
repli (le LLM), jamais d'inventer un rattachement.

La ressource (`llm_module/data/zf_zones.gpkg`) est produite par
`scripts/progedo_logit/export_zone_layer.py`. Les entrées/sorties sont confinées à
`ZoneResolver.load` ; le reste du module est pur, conformément au contrat
d'architecture de `llm_module.core`.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

from llm_module.core.geo_reference import read_geo_reference
from llm_module.telemetry.logger import get_logger

try:
    import numpy as np
    from pyproj import Transformer
    from shapely import STRtree, points as shapely_points
except ImportError as exc:  # pragma: no cover - dépend de l'image
    raise ImportError(
        "llm_module.core.zone_resolver exige numpy, shapely et pyproj. Ils viennent "
        "de geopandas, présent dans llm-agents/requirements.txt (conteneur controller) "
        "mais absent des dépendances du gateway : installez l'extra 'geo' "
        "(pip install -e 'llm_module[geo]') dans l'environnement concerné."
    ) from exc

logger = get_logger(__name__)


# Ressource par défaut : llm_module/data/zf_zones.gpkg, voisine du package.
DEFAULT_RESOURCE = Path(__file__).resolve().parent.parent / "data" / "zf_zones.gpkg"
DEFAULT_META = DEFAULT_RESOURCE.with_suffix(".meta.json")

# CRS des coordonnées d'entrée. La simulation, la population synthétique et OTP
# travaillent tous en WGS84 lon/lat ; la couche, elle, est en Lambert 93.
INPUT_CRS = "EPSG:4326"

# Seuils de l'alarme de couverture. Le taux hors couche attendu est de ~5 % : au-delà
# de 15 % sur un échantillon significatif, c'est la couche ou la population qui a
# changé de périmètre, et les features géo sont massivement manquantes.
_COVERAGE_MIN_SAMPLE = 200
_COVERAGE_ALARM_RATE = 0.15
_COVERAGE_CLEAR_RATE = 0.08


@dataclass(frozen=True)
class Zone:
    """Une zone fine EMC², réduite à ce dont le modèle a besoin."""

    zf: str
    x_l93: float
    y_l93: float
    surf_m2: float
    # Absente pour les 81 zones (sur 785) sans ménage enquêté. `None`, jamais 0 :
    # « inconnu » et « désert » ne sont pas la même information, et le booster route
    # les valeurs manquantes nativement.
    density_hh_km2: Optional[float]
    dist_center_km: float


@dataclass(frozen=True)
class GeoFeatures:
    """Les six features `source: "geo"` du spec, pour une paire origine-destination."""

    od_km: float
    same_zone: bool
    dist_center_orig_km: float
    dist_center_dest_km: float
    density_orig: Optional[float]
    density_dest: Optional[float]

    def as_dict(self) -> dict:
        """Noms de clés strictement ceux de `feature_spec.json`."""
        return {
            "od_km": self.od_km,
            "same_zone": self.same_zone,
            "dist_center_orig_km": self.dist_center_orig_km,
            "dist_center_dest_km": self.dist_center_dest_km,
            "density_orig": self.density_orig,
            "density_dest": self.density_dest,
        }


def od_km(origin: Zone, destination: Zone) -> float:
    """Distance origine-destination **à la formule de l'entraînement**.

    Inter-zone : distance entre centroïdes Lambert 93. Intra-zone : `0.5 × √surface`,
    la distance entre centroïdes étant nulle par construction.
    """
    if origin.zf == destination.zf:
        return 0.5 * math.sqrt(origin.surf_m2) / 1000
    return math.hypot(origin.x_l93 - destination.x_l93,
                      origin.y_l93 - destination.y_l93) / 1000


def geo_features(origin: Zone, destination: Zone) -> GeoFeatures:
    """Assemble les six features géo depuis les deux zones rattachées."""
    return GeoFeatures(
        od_km=od_km(origin, destination),
        same_zone=origin.zf == destination.zf,
        dist_center_orig_km=origin.dist_center_km,
        dist_center_dest_km=destination.dist_center_km,
        density_orig=origin.density_hh_km2,
        density_dest=destination.density_hh_km2,
    )


class ZoneResolver:
    """Rattache des points à leurs zones fines, et en dérive les features géo.

    Construire l'instance charge la couche et bâtit un index spatial une fois ;
    `resolve` est ensuite un appel local, sans I/O. À instancier une fois par
    processus (cf. `load`).
    """

    def __init__(self, zones: Sequence[Zone], geometries, layer_crs,
                 geo_reference: Optional[dict] = None) -> None:
        if len(zones) != len(geometries):
            raise ValueError(
                f"{len(zones)} zones pour {len(geometries)} géométries : ressource incohérente."
            )
        self._zones = tuple(zones)
        self._by_code = {z.zf: z for z in self._zones}
        self._tree = STRtree(geometries)
        self._to_layer = Transformer.from_crs(INPUT_CRS, layer_crs, always_xy=True)
        self.geo_reference = geo_reference or {}

        self._n_inside = 0
        self._n_outside = 0
        self._coverage_alarm = False

    # -- Chargement ---------------------------------------------------------

    @classmethod
    def load(cls, resource: Optional[Path] = None,
             feature_spec: Optional[Path] = None) -> "ZoneResolver":
        """Charge la ressource de zones (seul point d'I/O du module).

        `feature_spec` est facultatif mais recommandé : quand il est fourni, la
        référence géographique de la couche est comparée à celle du spec du modèle, et
        toute divergence lève une erreur au chargement plutôt que de produire
        silencieusement des `dist_center_*` mesurées depuis deux centres différents.
        """
        import geopandas as gpd  # local : seul `load` a besoin de geopandas

        resource = Path(resource) if resource else DEFAULT_RESOURCE
        if not resource.exists():
            raise FileNotFoundError(
                f"Ressource de zones fines absente : {resource}. Produisez-la avec "
                "`make zones` (python -m scripts.progedo_logit.export_zone_layer) — elle "
                "exige les données PROGEDO sous data/PROGEDO 2023/."
            )

        meta_path = resource.with_suffix(".meta.json")
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        layer = gpd.read_file(resource, layer=meta.get("layer", "zf"))

        geo_reference = meta.get("geo_reference", {})
        if feature_spec is not None:
            expected = read_geo_reference(Path(feature_spec))
            if geo_reference and expected and geo_reference != expected:
                raise ValueError(
                    "La couche de zones et feature_spec.json ne décrivent pas la même "
                    f"référence géographique.\n  couche : {geo_reference}\n  spec   : {expected}\n"
                    "Ré-exportez la couche depuis le même run que le spec "
                    "(python -m scripts.progedo_logit.export_zone_layer)."
                )

        zones = [
            Zone(
                zf=str(row.ZF),
                x_l93=float(row.XL93),
                y_l93=float(row.YL93),
                surf_m2=float(row.SURF_M2),
                # NaN du parquet/GPKG → None : la frontière entre « manquant » et
                # « valeur » est portée par le type, pas par un sentinel flottant.
                density_hh_km2=(None if row.density_hh_km2 is None
                                or _is_nan(row.density_hh_km2)
                                else float(row.density_hh_km2)),
                dist_center_km=float(row.dist_center_km),
            )
            for row in layer.itertuples(index=False)
        ]
        logger.info(
            f"Couche de zones fines chargée | zones={len(zones)} source={resource.name} "
            f"crs={layer.crs.to_string() if layer.crs else 'inconnu'}"
        )
        return cls(zones, layer.geometry.values, layer.crs, geo_reference)

    # -- Rattachement -------------------------------------------------------

    def resolve(self, lat: float, lon: float) -> Optional[Zone]:
        """Zone contenant le point WGS84, ou `None` s'il est hors couche."""
        return self.resolve_many([lat], [lon])[0]

    def zone_by_code(self, zf: str) -> Optional[Zone]:
        """Zone par son code ZF, pour l'appelant qui le connaît déjà (enquête, tests)."""
        return self._by_code.get(str(zf))

    def resolve_many(self, lats: Iterable[float],
                     lons: Iterable[float]) -> list[Optional[Zone]]:
        """Version vectorisée : une seule requête d'index pour tout le lot."""
        lat_arr = np.asarray(list(lats), dtype=float)
        lon_arr = np.asarray(list(lons), dtype=float)
        if lat_arr.shape != lon_arr.shape:
            raise ValueError(
                f"{lat_arr.size} latitudes pour {lon_arr.size} longitudes."
            )

        out: list[Optional[Zone]] = [None] * lat_arr.size
        if lat_arr.size == 0:
            return out

        # Les coordonnées absentes ne doivent pas atteindre l'index : NaN y produirait
        # une géométrie vide, silencieusement non appariée.
        valid = ~(np.isnan(lat_arr) | np.isnan(lon_arr))
        # `.tolist()` et non le tableau numpy : pyproj retombe sur son chemin scalaire
        # pour un tableau de taille 1 — celui de `resolve`, donc de chaque décision en
        # simulation — et y déclenche une conversion tableau→scalaire dépréciée, promise
        # à devenir une erreur. Les listes passent par le chemin vectorisé à toute taille.
        x, y = self._to_layer.transform(lon_arr[valid].tolist(), lat_arr[valid].tolist())
        # `intersects` et non `within` : un point tombant exactement sur une frontière
        # partagée appartient bien à la couche, il ne doit pas basculer dans le repli.
        pairs = self._tree.query(shapely_points(x, y), predicate="intersects")

        valid_idx = np.flatnonzero(valid)
        for point_pos, zone_pos in zip(pairs[0], pairs[1]):
            target = valid_idx[point_pos]
            zone = self._zones[zone_pos]
            current = out[target]
            # Frontière partagée : plusieurs zones intersectent. On départage sur le
            # code ZF pour que deux exécutions rattachent le point à la même zone.
            if current is None or zone.zf < current.zf:
                out[target] = zone

        self._record_coverage(out)
        return out

    # -- Features -----------------------------------------------------------

    def geo_features(self, origin: tuple[float, float],
                     destination: tuple[float, float]) -> Optional[GeoFeatures]:
        """Les six features géo pour une paire `(lat, lon)`, ou `None` hors couche.

        `None` dès que l'une des deux extrémités échappe à la couche : une paire à
        moitié rattachée ne donne pas d'`od_km`, et imputer l'extrémité manquante
        reviendrait au rattachement approximatif que le ticket 005 §2.1 écarte.
        """
        pairs = self.geo_features_many([origin], [destination])
        return pairs[0]

    def geo_features_many(self, origins: Sequence[tuple[float, float]],
                          destinations: Sequence[tuple[float, float]],
                          ) -> list[Optional[GeoFeatures]]:
        """Version vectorisée, pour appliquer le modèle à un run entier."""
        if len(origins) != len(destinations):
            raise ValueError(
                f"{len(origins)} origines pour {len(destinations)} destinations."
            )
        if not origins:
            return []

        o_zones = self.resolve_many([p[0] for p in origins], [p[1] for p in origins])
        d_zones = self.resolve_many([p[0] for p in destinations], [p[1] for p in destinations])
        return [
            geo_features(o, d) if o is not None and d is not None else None
            for o, d in zip(o_zones, d_zones)
        ]

    # -- Couverture ---------------------------------------------------------

    def coverage(self) -> dict:
        """Taux de rattachement depuis le chargement — à joindre aux rapports de run."""
        total = self._n_inside + self._n_outside
        return {
            "resolved": self._n_inside,
            "outside": self._n_outside,
            "total": total,
            "outside_rate": (self._n_outside / total) if total else 0.0,
            "alarm": self._coverage_alarm,
        }

    def _record_coverage(self, resolved: Sequence[Optional[Zone]]) -> None:
        """Suit le taux hors couche et alarme s'il s'envole.

        Front montant seulement, réarmement sous un seuil bas : une population hors
        périmètre rend les features géo massivement manquantes, ce qui dégraderait le
        modèle sans qu'aucune erreur ne remonte.
        """
        self._n_outside += sum(1 for z in resolved if z is None)
        self._n_inside += sum(1 for z in resolved if z is not None)

        stats = self.coverage()
        if stats["total"] < _COVERAGE_MIN_SAMPLE:
            return
        rate = stats["outside_rate"]
        if rate > _COVERAGE_ALARM_RATE and not self._coverage_alarm:
            self._coverage_alarm = True
            logger.error(
                f"[ALARME] Rattachement aux zones fines dégradé : {rate:.1%} des points "
                f"hors couche ({stats['outside']}/{stats['total']}), attendu ~5 %. "
                "Les features géographiques du modèle de choix modal sont manquantes "
                "sur ces décisions."
            )
        elif rate < _COVERAGE_CLEAR_RATE and self._coverage_alarm:
            self._coverage_alarm = False
            logger.info(f"Rattachement aux zones fines revenu à {rate:.1%} hors couche.")

    def __len__(self) -> int:
        return len(self._zones)


def _is_nan(value) -> bool:
    try:
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return False
