# `Toulouse.osm.pbf` — provenance (2026-09-03, ticket 031 partie 2, action T1)

| | Avant le 2026-09-03 | Depuis le 2026-09-03 |
|---|---|---|
| Fichier | `Toulouse_bbox30km_2026-05-06.osm.pbf` (conservé ici) | `Toulouse.osm.pbf` |
| Emprise | rectangle 1.085/43.336 → 1.815/43.868 (`TOULOUSE_OSM_ROUTES_30K_BBOX`, 73 × 72 km) | polygone exact des **453 communes** de l'enquête EMC² 2023 (0.866/43.115 → 1.928/43.954, 86 × 93 km, 5 428 km² de communes) |
| Millésime OSM | 2026 (téléchargement bbbike du 2026-05-06) | **2022-01-01** (pbf régionaux Geofabrik du fork eqasim) |
| Taille / md5 | 88 204 065 o / `cc9520bf0200752d031f65b9f6c3b4ae` | 76 475 294 o / `62d45fe568aa822b794603149d4e492d` |
| Recette | aucune dans le dépôt | `scripts/data/population/build_osmnx_perimeter_graph.py` → `data/cache/osmnx/perimetre_453/perimetre_453.osm.pbf` (osmium extract --polygon, aucun téléchargement) |

Le dossier réellement chargé par les instances OTP de `docker-compose.yml` est `data/gtfs/`
(montage `/var/otp/toulouse`, `--load`) : la copie de référence y est identique, et l'ancien extrait
avec son `graph.obj` sont archivés dans `data/gtfs/archives/2026-09-03_pre_perimetre_453/`.

Pourquoi : trois gares TER et les domiciles de 3ᵉ couronne de la population scellée v4 étaient hors
du rectangle — OTP ne pouvait pas les rattacher au graphe de rue (« Couldn't link »). Limite à
connaître : la voirie passe de 2026 à 2022 (fraîcheur notée au ticket 031 § 1.0) ; un extrait 2026
du même polygone demande un téléchargement régional (~270 Mo), qui n'est pas fait sans accord.

`dvc` n'est pas installé : le `.dvc` voisin est écrit à la main (md5 et taille recalculés).
