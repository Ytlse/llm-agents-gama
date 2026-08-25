"""
core/geo_reference.py — L'hypercentre de Toulouse, lu et non redéclaré.

Le centre-ville sert de référence à deux endroits qui doivent parler du même point :
les variables `dist_center_orig_km` / `dist_center_dest_km` du modèle de choix modal
(cuites dans la couche de zones fines, cf. `zone_resolver`) et la colonne
« Lieu de résidence » du move-log, qui classe chaque agent en Toulouse / 1re / 2e /
3e couronne selon sa distance au centre.

**La référence est `scripts/progedo_logit/feature_spec.json`**, bloc
`geo_reference.hypercenter` : la valeur y est calculée depuis les données de l'enquête
EMC² (centroïde des zones fines du secteur 01, Capitole) par
`scripts/progedo_logit/build_mode_choice_dataset.py`, et publiée avec le contrat de
features. Aucun autre module ne doit en redéclarer une : `move_logger.py` en portait
une seconde (43.6047 / 1.4442), distante de 820 m, qui décalait les couronnes de
résidence par rapport aux distances au centre vues à l'entraînement.

**Le spec peut être absent à l'exécution.** Il est produit depuis les microdonnées
PROGEDO d'accès restreint (`data/PROGEDO 2023/`), hors dépôt : un poste ou un
conteneur sans ces données n'a pas le fichier. Le repli est alors la valeur du spec
recopiée en constante ci-dessous (`FALLBACK_GEO_REFERENCE`) — jamais l'ancienne
constante concurrente — et il est tracé une fois dans les logs.

Ce module est le seul point de lecture du bloc `geo_reference` : `zone_resolver.load`
s'en sert pour son garde-fou (il refuse de servir une couche dont la référence
géographique diverge de celle du spec), et `move_logger` pour son classement en
couronnes.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from llm_module.telemetry.logger import get_logger

logger = get_logger(__name__)


# Recopie littérale de `geo_reference.hypercenter` du spec v1 (EMC² Toulouse 2023).
# Sert uniquement de repli quand le spec est introuvable ; toute mise à jour du spec
# doit être répercutée ici, et le test `test_move_logger_hypercenter.py` échoue si les
# deux divergent tant que le spec est présent.
FALLBACK_GEO_REFERENCE = {
    "crs": "IGNF:LAMB93",
    "hypercenter": {
        "definition": "centroïde des zones fines du secteur 01 (Capitole)",
        "x_l93": 574406.1,
        "y_l93": 6278824.6,
        "lat": 43.597347,
        "lon": 1.444997,
    },
}

# Emplacements standards du spec, dans l'ordre de recherche :
#   1. la variable d'environnement, qui prime toujours ;
#   2. la racine du dépôt, quand llm_module est utilisé depuis les sources ;
#   3. le conteneur `controller`, où `scripts/` est monté sous /app/scripts et
#      `llm_module` sous /opt — les deux ne sont plus voisins comme dans le dépôt.
FEATURE_SPEC_ENV = "MODE_CHOICE_FEATURE_SPEC"
_REPO_SPEC = (Path(__file__).resolve().parents[2]
              / "scripts" / "progedo_logit" / "feature_spec.json")
_CONTAINER_SPEC = Path("/app/scripts/progedo_logit/feature_spec.json")


def find_feature_spec() -> Optional[Path]:
    """Premier `feature_spec.json` trouvé aux emplacements standards, ou `None`."""
    from_env = os.getenv(FEATURE_SPEC_ENV)
    candidates = ([Path(from_env)] if from_env else []) + [_REPO_SPEC, _CONTAINER_SPEC]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def read_geo_reference(feature_spec: Path) -> dict:
    """Bloc `geo_reference` d'un spec désigné. Lève si le fichier est illisible.

    Version stricte, pour l'appelant qui sait déjà quel spec il veut comparer
    (`zone_resolver.load`). Un spec sans bloc `geo_reference` rend `{}` : c'est un
    spec plus ancien, pas une erreur de lecture.
    """
    spec = json.loads(Path(feature_spec).read_text(encoding="utf-8"))
    return spec.get("geo_reference", {}) or {}


@lru_cache(maxsize=1)
def geo_reference() -> dict:
    """Référence géographique effective : celle du spec, ou le repli documenté.

    Mise en cache : un run appelle `hypercenter()` à chaque déplacement journalisé,
    ce n'est pas une raison pour relire le spec à chaque fois. `geo_reference.
    cache_clear()` permet aux tests de rejouer la résolution.
    """
    path = find_feature_spec()
    if path is None:
        logger.warning(
            "feature_spec.json introuvable : hypercentre replié sur la valeur "
            f"publiée du spec ({FALLBACK_GEO_REFERENCE['hypercenter']['lat']} / "
            f"{FALLBACK_GEO_REFERENCE['hypercenter']['lon']}). Les données PROGEDO "
            "sont d'accès restreint, leur absence est un cas normal."
        )
        return FALLBACK_GEO_REFERENCE

    try:
        reference = read_geo_reference(path)
    except (OSError, ValueError) as exc:
        logger.warning(
            f"feature_spec.json illisible ({path}) : {exc}. Hypercentre replié sur "
            "la valeur publiée du spec."
        )
        return FALLBACK_GEO_REFERENCE

    center = reference.get("hypercenter") or {}
    if center.get("lat") is None or center.get("lon") is None:
        logger.warning(
            f"feature_spec.json ({path}) ne publie pas d'hypercentre exploitable : "
            "repli sur la valeur publiée du spec."
        )
        return FALLBACK_GEO_REFERENCE

    logger.info(
        f"Hypercentre lu depuis {path} | lat={center['lat']} lon={center['lon']} "
        f"({center.get('definition', 'sans définition')})"
    )
    return reference


def hypercenter() -> tuple[float, float]:
    """Hypercentre `(lat, lon)` en WGS84 — la seule façon de l'obtenir au runtime."""
    center = geo_reference()["hypercenter"]
    return float(center["lat"]), float(center["lon"])


# Bornes des couronnes, en km depuis l'hypercentre. Elles portent les LIBELLÉS de
# `lieu_residence` de la référence EMC², mais elles n'en sont PAS la définition :
# l'enquête découpe par liste de communes (ticket 020, axe A2 — 24,4 % de personas
# reclassés). Ces bornes ne servent donc plus qu'au temps terminal, dont les lois sont
# stratifiées avec elles (`terminal_time_emc2.json`, `meta.crown_definition`) : les
# changer sans ré-exporter la ressource comparerait des durées à des strates qui ne
# désignent pas les mêmes territoires. La couronne de RÉSIDENCE se lit sur le persona,
# cf. `llm_module.core.residence_zone` et le docstring de `residence_zone` plus bas.
COURONNE_BOUNDS_KM: tuple[tuple[float, str], ...] = (
    (8.0,  "Toulouse"),
    (20.0, "1ere couronne"),
    (40.0, "2eme couronne"),
)
COURONNE_OUTER = "3eme couronne"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance orthodromique en kilomètres."""
    import math

    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def residence_zone(lat: Optional[float], lon: Optional[float]) -> str:
    """Classement MÉTRIQUE d'un point, pour le temps terminal — **pas** la résidence.

    Rend ``Toulouse`` / ``1ere`` / ``2eme`` / ``3eme couronne`` selon la seule distance
    à l'hypercentre (8 / 20 / 40 km). Chaîne vide quand le point est inconnu — vide
    n'est pas une modalité, exactement comme une cellule de probabilité vide n'est pas
    un 0.

    ⚠ **CE N'EST PAS LA DÉFINITION DE LA RÉSIDENCE AU SENS D'EMC².** Cette fonction a
    longtemps prétendu servir « les modalités de `lieu_residence` de la référence EMC² » ;
    c'était faux, et ça a coûté deux ans de parts modales par zone mal lues. L'enquête
    découpe son périmètre par **liste de communes**, pas par anneaux métriques. Le
    ticket 020 a chiffré l'écart : **24,4 %** des personas changent de couronne, **66**
    « Toulousains » habitent en réalité Blagnac, Balma ou Colomiers, et **45** domiciles
    rangés en 3ᵉ couronne sont hors du périmètre d'enquête. La couronne de résidence se
    LIT désormais sur le persona (`llm_module.core.residence_zone`, trait
    `residence_zone`, ticket 021) ; `move_logger` n'importe plus cette fonction, pour que
    le repli à la distance soit impossible et non seulement déconseillé.

    **Ce qu'elle sert encore, et pourquoi elle reste.** Le temps terminal spatialisé des
    trajets véhiculés (ticket 013, `trip_helper/terminal_time.py`) classe des points
    d'ORIGINE et de DESTINATION quelconques — pas des domiciles —, et surtout ses lois
    sont **stratifiées avec ce classement** : `llm_module/data/terminal_time_emc2.json`
    l'inscrit dans son `meta.crown_definition`, parce que `export_terminal_time.py` a
    réparti les 785 zones fines de l'enquête avec cette même distance. L'aligner sur le
    découpage communal ne consiste donc pas à changer un `if` : il faut **ré-exporter la
    ressource** (version 2 → 3), ce qui invalide le cache OTP et le cache de décisions
    LLM et exige un run complet. C'est un ticket distinct, à coordonner avec la
    correction de calibre en attente du ticket 013.

    **La divergence assumée, avec son amplitude.** Le journal classe une *personne* par
    sa commune ; le temps terminal classe un *point* par sa distance. Les deux peuvent
    donc désigner des couronnes différentes pour un même domicile. Ce que ça coûte, aux
    lois `tt3` (moyennes accès + stationnement : Toulouse 0,87 min, 1ʳᵉ 0,30, 2ᵉ 0,34,
    3ᵉ 0,15) : **34 s par bout de trajet** sur le pire couple observé (Toulouse contre
    1ʳᵉ couronne, 66 cas), 43 s sur le pire couple possible, qui ne se produit pas. Sous
    `tt2` le même écart valait 4 minutes — c'est le ticket 013 qui a absorbé le risque.
    Une divergence documentée et bornée est une décision ; la même, non écrite, est le
    bug de demain.
    """
    if lat is None or lon is None:
        return ""
    center_lat, center_lon = hypercenter()
    d = haversine_km(center_lat, center_lon, lat, lon)
    for bound, name in COURONNE_BOUNDS_KM:
        if d < bound:
            return name
    return COURONNE_OUTER
