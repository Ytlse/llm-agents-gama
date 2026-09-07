"""mobility_core — le domaine de l'enquête EMC² Toulouse, sans dépendance LLM.

Couronnes de résidence, zones fines, hiérarchie des modes, équipement vélo, type de
logement, propensions individuelles et cadrage de la population enquêtée. Chaque module
lit une ressource gelée dans ``mobility_core/data/`` et refuse de deviner ce qu'elle ne
contient pas.

Extra ``geo`` : ``zone_resolver`` et ``residence_zone.CommunalZones`` exigent geopandas,
shapely et pyproj.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
