"""core/residence_zone.py — La couronne de résidence, LUE et non calculée.

L'enquête EMC² 2023 découpe son périmètre en quatre couronnes **par liste de communes**
(`Toulouse`, `1ere couronne`, `2eme couronne`, `3eme couronne`), et c'est contre ce
découpage que ses parts modales sont publiées. Ce module sert ce découpage à partir du
**code de zone fine** du domicile, que `zone_resolver` résout déjà.

⚠ **NE PAS CONFONDRE AVEC `geo_reference.residence_zone`.** Cette dernière classe un point
par sa **distance à l'hypercentre** (8 / 20 / 40 km). Ce n'est pas la définition de
l'enquête — le ticket 020 a mesuré 24,4 % de personas mal classés et 66 faux Toulousains
— et elle ne survit que pour le **temps terminal**, qui classe des points quelconques et
dont les lois sont stratifiées avec elle (`terminal_time_emc2.json`, `meta.crown_definition`).
La divergence entre les deux est assumée, bornée et documentée (ticket 021) : 34 s par bout
de trajet sur le pire couple observé. Un appelant qui veut la couronne d'un **domicile**
lit le trait du persona ; il ne rappelle jamais la fonction métrique.

**Le rattachement passe par le code, pas par une géométrie.** Le code `ZF` compte 9
chiffres dont les **trois premiers sont le numéro du secteur de tirage** (`NUM_DTIR`), et
le secteur porte la couronne. Mesuré (ticket 021, lot 0) : ce classement est identique à
100 % au classement par appartenance géométrique, sur les 785 zones fines comme sur les
1 021 domiciles de la population de référence.

*Au passage* : `housing_type` découpe le même code sur **quatre** chiffres pour ses replis
de secteur. Les deux partitions sont identiques — 88 classes de part et d'autre, et un
découpage plus long ne peut que raffiner — donc les deux modules parlent bien des mêmes
secteurs malgré la longueur différente.

**Hors périmètre n'est pas une couronne.** Un domicile hors des 453 communes reçoit
`population_reference.OUT_OF_PERIMETER`, jamais « 3ᵉ couronne » : il n'a aucune cible EMC²
à laquelle être comparé, et le confondre avec la couronne la plus externe a fait publier un
stratum dont 76 % des habitants n'étaient pas dans l'enquête. Deux emprises coexistent —
la couche de zones fines (`zone_resolver.resolve()` rend `None` dehors) et la dissolution
des quatre couronnes (`CommunalZones`) — et le lot 0 a mesuré qu'elles désignent exactement
le même ensemble. **L'emprise normative est la seconde** : c'est celle de l'enquête.

Les entrées/sorties sont confinées aux `load` des deux classes, conformément au contrat
d'architecture de `llm_module.core`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from llm_module.core.population_reference import COURONNES, OUT_OF_PERIMETER

# Clés du trait dans `traits_json`. Le persona porte le LIBELLÉ de l'enquête
# (`1ere couronne`), pas une clé technique : c'est ce que relit le journal de
# déplacements, et ce qu'un humain relit dans le JSON de population.
TRAIT_KEY = "residence_zone"

# La commune n'est pas décorative : c'est elle qui rend le classement auditable, et elle
# survit à un redécoupage des couronnes. Le code INSEE l'accompagne, parce qu'un nom de
# commune n'est pas une clé de jointure.
COMMUNE_TRAIT_KEY = "residence_commune"
INSEE_TRAIT_KEY = "residence_insee"

# Longueur du préfixe de secteur de tirage dans le code de zone fine (`218102000` → `218`).
SECTOR_PREFIX_LEN = 3

# Version de ressource acceptée. Une ressource d'une autre version n'est pas servie « au
# mieux » : elle est refusée, parce qu'un classement de résidence silencieusement périmé se
# lit comme une part modale et non comme un bug.
RESOURCE_VERSION = "zc1"

DEFAULT_TABLE = Path(__file__).resolve().parent.parent / "data" / "zf_couronne.json"
DEFAULT_GEOJSON = (Path(__file__).resolve().parent.parent / "data"
                   / "couronne_perimetre.geojson")
DEFAULT_COMMUNE_TABLE = (Path(__file__).resolve().parent.parent / "data"
                         / "commune_couronne.json")


class ResidenceZoneError(ValueError):
    """Ressource absente, périmée ou incohérente. Jamais un repli silencieux."""


def secteur_of(zf: object) -> str:
    """Préfixe de secteur d'un code de zone fine. Chaîne vide si le code est inutilisable."""
    code = str(zf or "").strip()
    return code[:SECTOR_PREFIX_LEN] if len(code) >= SECTOR_PREFIX_LEN else ""


@dataclass(frozen=True)
class ZoneCouronne:
    """Une zone fine, réduite à ce que le trait de résidence demande."""

    zf: str
    secteur: str
    couronne: str
    insee: str
    commune: str


class CouronneTable:
    """`zf_couronne.json` : 785 zones fines → secteur, couronne, commune.

    Produite par `scripts/progedo_logit/export_commune_couronne.py` depuis la couche SIG
    d'accès restreint ; la ressource, elle, est versionnée et montée dans les conteneurs.
    """

    def __init__(self, zones: Sequence[ZoneCouronne], meta: Optional[dict] = None) -> None:
        self._by_zf = {z.zf: z for z in zones}
        self._by_secteur: dict[str, str] = {}
        for zone in zones:
            known = self._by_secteur.setdefault(zone.secteur, zone.couronne)
            if known != zone.couronne:
                raise ResidenceZoneError(
                    f"secteur {zone.secteur} rattaché à deux couronnes "
                    f"({known} et {zone.couronne}) : la table n'est pas une fonction.")
        self.meta = meta or {}

    # -- Chargement ---------------------------------------------------------

    @classmethod
    def load(cls, resource: Optional[Path] = None) -> "CouronneTable":
        """Charge la table (seul point d'I/O de la classe)."""
        path = Path(resource) if resource else DEFAULT_TABLE
        if not path.exists():
            raise ResidenceZoneError(
                f"table des couronnes absente : {path}\n"
                "Elle se (re)produit par `make communes-couronnes`, qui exige les données "
                "PROGEDO d'accès restreint (lil-1750). Sans elle, la couronne d'un "
                "domicile ne se devine pas.")
        payload = json.loads(path.read_text(encoding="utf-8"))
        version = str(payload.get("version", ""))
        if version != RESOURCE_VERSION:
            raise ResidenceZoneError(
                f"{path.name} est en version « {version} », attendue « "
                f"{RESOURCE_VERSION} ». Rejouez `make communes-couronnes`.")
        rows = payload.get("zones") or []
        if not rows:
            raise ResidenceZoneError(f"{path.name} ne porte aucune zone.")
        inconnues = sorted({row["couronne"] for row in rows} - set(COURONNES))
        if inconnues:
            raise ResidenceZoneError(
                f"couronnes inattendues dans {path.name} : {inconnues}. Les modalités "
                f"doivent être exactement {list(COURONNES)}.")
        zones = [ZoneCouronne(zf=str(row["zf"]), secteur=str(row["secteur"]),
                              couronne=row["couronne"], insee=str(row["insee"]),
                              commune=str(row["commune"]))
                 for row in rows]
        meta = {k: v for k, v in payload.items() if k != "zones"}
        return cls(zones, meta)

    # -- Lecture ------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._by_zf)

    @property
    def secteurs(self) -> dict[str, str]:
        """`secteur → couronne`, les 88 secteurs de tirage de l'enquête."""
        return dict(self._by_secteur)

    def zone(self, zf: object) -> Optional[ZoneCouronne]:
        """La ligne d'une zone fine. `None` si le code est inconnu — on ne devine pas."""
        return self._by_zf.get(str(zf or "").strip())

    def couronne_of_zf(self, zf: object) -> Optional[str]:
        """Couronne d'un code de zone fine, par sa ligne puis par son secteur.

        Le repli par secteur n'est pas une approximation : le secteur EST le porteur de
        la couronne dans l'enquête, la ligne de zone n'en est qu'une projection. Il sert
        les codes qu'une couche de zones plus récente connaîtrait sans que la table l'ait
        encore vu. `None` quand même le secteur est inconnu.
        """
        zone = self.zone(zf)
        if zone is not None:
            return zone.couronne
        return self._by_secteur.get(secteur_of(zf))

    def couronne_of_secteur(self, secteur: object) -> Optional[str]:
        """Couronne d'un secteur de tirage. `None` si le secteur est inconnu."""
        return self._by_secteur.get(str(secteur or "").strip())

    def commune_of_zf(self, zf: object) -> Optional[tuple[str, str]]:
        """`(insee, commune)` d'une zone fine. `None` si le code est inconnu.

        Pas de repli par secteur ici : un secteur couvre plusieurs communes, et rendre
        « une commune du secteur » serait une invention.
        """
        zone = self.zone(zf)
        return (zone.insee, zone.commune) if zone is not None else None


class CommuneTable:
    """`commune_couronne.json` : les 453 communes du périmètre et leur couronne.

    Sert deux usages que rien d'autre ne couvre :

    - le **cadre de tirage** de la génération de population — quelles communes le
      pipeline eqasim est autorisé à peupler (ticket 026) ;
    - le **test d'appartenance** au périmètre d'enquête à partir d'un code INSEE, sans
      géométrie et sans résoudre de zone fine.

    Les deux ne se confondent pas : le cadre peut être un sous-ensemble (version
    Haute-Garonne du ticket 026), le périmètre est toujours les 453.
    """

    def __init__(self, communes: dict[str, str], meta: Optional[dict] = None) -> None:
        self._couronne_by_insee = dict(communes)
        self.meta = meta or {}

    @classmethod
    def load(cls, resource: Optional[Path] = None) -> "CommuneTable":
        path = Path(resource) if resource else DEFAULT_COMMUNE_TABLE
        if not path.exists():
            raise ResidenceZoneError(
                f"table des communes absente : {path} (`make communes-couronnes`).")
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("communes") or []
        if not rows:
            raise ResidenceZoneError(f"{path.name} ne porte aucune commune.")
        inconnues = sorted({r["couronne"] for r in rows} - set(COURONNES))
        if inconnues:
            raise ResidenceZoneError(
                f"couronnes inattendues dans {path.name} : {inconnues}.")
        communes = {str(r["insee"]).zfill(5): r["couronne"] for r in rows}
        meta = {k: v for k, v in payload.items() if k != "communes"}
        return cls(communes, meta)

    def __len__(self) -> int:
        return len(self._couronne_by_insee)

    def couronne_of_insee(self, insee: object) -> Optional[str]:
        """Couronne d'une commune. `None` si elle n'est pas dans le périmètre."""
        return self._couronne_by_insee.get(str(insee or "").strip().zfill(5))

    def contains(self, insee: object) -> bool:
        return self.couronne_of_insee(insee) is not None

    def communes(self, departments: Optional[Sequence[str]] = None) -> list[str]:
        """Codes INSEE du périmètre, éventuellement restreints à des départements.

        `departments=None` rend les 453 — le périmètre d'enquête entier.
        `departments=["31"]` rend le cadre de tirage de la version Haute-Garonne du
        ticket 026 (346 communes). La restriction est un CHOIX DE TRAVAIL, jamais une
        définition : le périmètre reste les 453, et c'est lui qui sert de filtre
        d'admission au chargement.
        """
        codes = sorted(self._couronne_by_insee)
        if departments is None:
            return codes
        prefixes = tuple(str(d).zfill(2) for d in departments)
        if not prefixes:
            raise ResidenceZoneError(
                "liste de départements vide : refus de rendre un cadre de tirage "
                "ambigu. Passez `None` pour le périmètre entier.")
        retenus = [c for c in codes if c.startswith(prefixes)]
        if not retenus:
            raise ResidenceZoneError(
                f"aucune commune du périmètre dans les départements {list(prefixes)} — "
                f"cadre de tirage vide. Sans ce garde-fou, le pipeline retomberait en "
                f"silence sur le département entier.")
        return retenus

    def counts(self, departments: Optional[Sequence[str]] = None) -> dict[str, int]:
        """Nombre de communes par couronne, pour le cadre demandé."""
        retenus = self.communes(departments)
        out = {z: 0 for z in COURONNES}
        for insee in retenus:
            out[self._couronne_by_insee[insee]] += 1
        return out


class CommunalZones:
    """Classe un point par APPARTENANCE à une couronne, non par distance.

    C'est la définition de l'enquête, et l'emprise normative du hors-périmètre. Elle a
    vécu dans `scripts/data/population/audit_perimetre.py` (ticket 020) ; elle est montée
    ici quand un second appelant est apparu — le post-traitement du ticket 021 — parce que
    deux copies d'une classification de référence finissent par diverger.

    Un point hors des quatre couronnes reçoit `hors périmètre` ; un point inconnu (`None`)
    reçoit la chaîne vide, qui n'est pas une modalité.
    """

    def __init__(self, names: Sequence[str], geometries) -> None:
        from shapely import STRtree, points as shapely_points

        self._names = [str(name) for name in names]
        self._tree = STRtree(list(geometries))
        self._points = shapely_points

    @classmethod
    def load(cls, geojson: Optional[Path] = None) -> "CommunalZones":
        """Charge la géométrie des couronnes (seul point d'I/O de la classe)."""
        path = Path(geojson) if geojson else DEFAULT_GEOJSON
        if not path.exists():
            raise ResidenceZoneError(
                f"géométrie des couronnes absente : {path} "
                f"(`make communes-couronnes`).")
        try:
            import geopandas as gpd
        except ImportError as exc:  # pragma: no cover - dépend de l'image
            raise ResidenceZoneError(
                f"geopandas requis pour lire {path.name} : {exc}") from exc
        layer = gpd.read_file(path).to_crs(4326)
        inconnues = sorted(set(map(str, layer["couronne"])) - set(COURONNES))
        if inconnues:
            raise ResidenceZoneError(
                f"couronnes inattendues dans {path.name} : {inconnues}.")
        return cls(list(layer["couronne"]), list(layer.geometry))

    def classify(self, lat: Optional[float], lon: Optional[float]) -> str:
        """Couronne d'un point, `hors périmètre` dehors, chaîne vide si le point manque."""
        if lat is None or lon is None:
            return ""
        hits = self._tree.query(self._points([lon], [lat]), predicate="within")
        # STRtree.query rend (indices d'entrée, indices d'arbre) en shapely 2.
        indices = hits[1] if getattr(hits, "ndim", 1) == 2 else hits
        for index in indices:
            return self._names[int(index)]
        return OUT_OF_PERIMETER
