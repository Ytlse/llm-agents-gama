# Pipeline de données géospatiales

Ce document couvre les trois sources de données géospatiales utilisées par la simulation : GTFS (horaires transport), OpenTripPlanner (routage transit) et OSMnx (routage direct).

---

## 1. Données GTFS — Tisséo + TER

La simulation utilise deux sources GTFS concaténées, placées dans `data/gtfs/` :

| Source | Dossier | Lien |
|--------|---------|------|
| Tisséo (réseau urbain Toulouse) | `data/gtfs/tisseo_gtfs/` | https://data.toulouse-metropole.fr/explore/dataset/tisseo-gtfs/information/ |
| TER SNCF (réseau régional) | `data/gtfs/ter_gtfs/` | https://www.data.gouv.fr/fr/datasets/horaires-des-lignes-ter-sncf/ |

OTP lit directement le dossier `data/gtfs/` au complet lors de la construction du graphe. Les deux sources sont fusionnées automatiquement.

Le notebook `scripts/data/gtfs/gtfs_merge.ipynb` permet de vérifier la cohérence des deux flux, d'analyser les routes et arrêts communs, et de produire un GTFS consolidé si besoin.

### Préparer les données GTFS pour GAMA

Ce script génère le fichier `trip_info.json` consommé par le modèle GAMA et le copie dans `GAMA/CityTransport/includes/` :

```shell
bash scripts/update_gtfs_data.sh
```

Il exécute successivement :
1. `llm-agents/inputs/gtfs/reader.py` — génère les shapefiles d'arrêts et de routes
2. `llm-agents/inputs/gtfs/gama.py` — construit le calendrier et les horaires de chaque voyage au format JSON

### Le monde GAMA : le périmètre des 453 communes (ticket 031, G1)

```shell
llm-agents/.venv/bin/python scripts/data/gama/export_perimetre_shapefile.py
```

écrit `GAMA/CityTransport/includes/perimetre_453.shp` (polygone dissous des quatre couronnes,
EPSG:4326 comme `routes.shp`). `Settings.gaml` en fait l'emprise du monde —
`geometry shape <- envelope(perimetre_shape_file)`, **86 × 93 km** (mesuré en Lambert-93 sur le
polygone dissous : 85,8 × 92,9 km, 5 428 km² de communes dans une enveloppe de 7 971 km² ; GAMA
annonce 87 × 94 km dans sa propre projection) — à la place de l'enveloppe des lignes Tisséo. Ce que
cette dernière laissait dehors, mesuré sur la population scellée v4 : **201 des 1 000 domiciles**
(le rapport de périmètre citait 163, mesurés sur la v3, moins riche en 3ᵉ couronne) ; sur le monde
actuel, **0 / 1 000**. Le rapport de périmètre annonçait « 106 × 93 km » :
c'est un degré de longitude compté à 111 km sans le cosinus de la latitude (à 43,5°, un degré de
longitude vaut 80,8 km) — la hauteur était juste, la largeur surestimée de 23 %. Au chargement, GAMA écrit la part
du monde couverte par les lignes TC (`[PERIMETRE] … les lignes TC n'en couvrent que N %`) et, à la
création des habitants, le nombre d'agents hors du monde (`[PERIMETRE] 1000 habitants créés, 0 hors
du monde GAMA` ; `[ALARME]` sinon). Le dossier `includes/` n'est pas versionné : ce script est la
recette, à rejouer après tout changement de `couronne_perimetre.geojson`.

**`roads.shp` / `nodes.shp` (G4)** : leur `.prj` déclare `WGS 84 / UTM zone 48N` (EPSG:32648, la
projection par défaut de GAMA) alors que Toulouse est en zone 31N — et leurs coordonnées
(x ≈ −4 025 000, y ≈ 12 208 000) ne sont celles d'aucune des deux : ce sont les coordonnées
internes de GAMA, sauvegardées telles quelles par `OSMLoadDriving.gaml` (`save road to:
"../includes/roads.shp"`). Ces fichiers ne sont lus par aucun modèle (`City.gaml` ne charge que
`perimetre_453.shp`, `routes.shp`, `stops.shp`, `trip_info.json`) ; ils ne sont pas géoréférencés et
ne se « corrigent » pas en changeant le `.prj`. À régénérer avec une projection explicite si la voirie
GAMA devait servir un jour ; laissés en place, documentés ici (2026-09-03).

---

## 2. OpenTripPlanner (OTP)

OTP est le moteur de calcul d'itinéraires multi-modal (transit + marche/vélo/voiture).

### Installation

1. Télécharger le binaire OTP depuis le [guide officiel](https://docs.opentripplanner.org/en/v2.7.0/Getting-OTP/) et le placer dans `otp-toulouse/bin/`.

2. L'extrait OSM `data/gtfs/Toulouse.osm.pbf` est, **depuis le 2026-09-03 (ticket 031, T1)**,
   l'extrait du **polygone exact des 453 communes** de l'enquête EMC² 2023 — produit sans
   téléchargement par `scripts/data/population/build_osmnx_perimeter_graph.py` (`osmium extract
   --polygon` sur les pbf régionaux du fork eqasim, millésime OSM 2022-01-01, 76 Mo, md5
   `62d45fe5…`), copié depuis `data/cache/osmnx/perimetre_453/perimetre_453.osm.pbf`. Il remplace un
   extrait bbbike de 2026 limité au rectangle de 30 km (`TOULOUSE_OSM_ROUTES_30K_BBOX`), hors duquel
   OTP ne pouvait pas rattacher les domiciles de 3ᵉ couronne ni trois gares TER (« Couldn't link ») ;
   l'ancien extrait et son `graph.obj` sont archivés dans `data/gtfs/archives/2026-09-03_pre_perimetre_453/`,
   la provenance est consignée dans `otp-toulouse/toulouse/Toulouse.osm.pbf.dvc` (écrit à la main,
   `dvc` n'étant pas installé) et `README_Toulouse.osm.pbf.md`. Limite : la voirie passe de 2026 à
   2022 ; un extrait 2026 du même polygone demande un téléchargement régional (~270 Mo), non fait sans
   accord. Un autre extrait se pose au même endroit (`Toulouse.osm.pbf`), puis le graphe se reconstruit.

3. Placer les dossiers GTFS (`tisseo_gtfs/`, `ter_gtfs/`) dans `data/gtfs/`. `data/gtfs/build-config.json`
   fixe la fenêtre de service `[2026-01-01, 2027-12-31]` (T5), alignée sur les feeds annuels et la
   date simulée.

### Construction et démarrage (hors Docker)

```shell
# Construire le graphe de transport (une seule fois, résultat : data/gtfs/graph.obj)
java -Xmx4G -jar otp-toulouse/bin/otp-shaded-2.8.1.jar --build data/gtfs --save

# Démarrer le serveur OTP
java -Xmx4G -jar otp-toulouse/bin/otp-shaded-2.8.1.jar --load data/gtfs
```

Mesuré le 2026-09-03 sur l'extrait du polygone (JDK 25, `-Xmx4G`) : **46 s de construction, 2,0 Go
de RSS de pointe, `graph.obj` de 66 Mo** (contre 77 Mo pour le rectangle de 2026 : la voirie 2022
est moins détaillée), 4 056 arrêts dont 3 757 rattachés à la voirie — les 167 « isolés » sont les
arrêts TER hors du polygone (234 arrêts TER, 68 dedans). Puis `docker compose restart otp1 otp2 otp3`
(≈ 20 s jusqu'au healthcheck, 1,2 à 1,4 Go par instance chargée). Contrôle de rattachement d'une
population : `scripts/data/gtfs/otp_link_check.py --population <fichier>` compte les
`routingErrors` OTP (`LOCATION_NOT_FOUND` = « Couldn't link ») pour chaque domicile et lieu
d'activité.

### Configuration dans le controller

```yaml
# llm-agents/config/config.yaml
gtfs:
  mode: OTP
  otp_endpoint: http://localhost:8080/otp/transmodel/v3
  otp_max_concurrent: 30
```

### Déploiement Docker

En Docker, **trois instances OTP** (`otp1`, `otp2`, `otp3`) tournent en parallèle sur les ports `8080`, `8081` et `8082`. Le controller les consomme via :

```
OTP_ENDPOINTS=http://otp1:8080/otp/transmodel/v3,http://otp2:8080/otp/transmodel/v3,http://otp3:8080/otp/transmodel/v3
```

Chaque instance charge le même `graph.obj` (volume partagé en lecture seule) et absorbe une partie du trafic de requêtes.

---

## 3. OSMnx — routage pédestre / vélo / voiture

OSMnx calcule les itinéraires directs (sans transport en commun) : marche, vélo, voiture.

### Fonctionnement

Les graphes OSMnx sont téléchargés depuis OpenStreetMap au premier démarrage puis mis en cache dans `data/osmnx_cache/` (persistant entre les redémarrages). Le calcul Dijkstra est délégué à des workers de processus dédiés par mode pour contourner le GIL Python.

### Déploiement Docker

En Docker, OSMnx tourne dans un microservice dédié (`osmnx1`, port `8090`). Des replicas supplémentaires (`osmnx2`, `osmnx3`) peuvent être activés dans `docker-compose.yml` si la charge le nécessite.

Le controller les contacte via :

```
OSMNX_ENDPOINTS=http://osmnx1:8090/route
# Plusieurs replicas séparés par des virgules, distribués en round-robin
```

### Configuration dans le controller

```yaml
gtfs:
  osmnx_cache_dir: /app/osmnx_cache
```

### Références

- GTFS : https://gtfs.org/resources/gtfs/
- GTFS Tisséo : https://data.toulouse-metropole.fr/explore/dataset/tisseo-gtfs/information/
- GTFS TER SNCF : https://www.data.gouv.fr/fr/datasets/horaires-des-lignes-ter-sncf/
- OpenTripPlanner : https://www.opentripplanner.org/
