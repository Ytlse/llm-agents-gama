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

---

## 2. OpenTripPlanner (OTP)

OTP est le moteur de calcul d'itinéraires multi-modal (transit + marche/vélo/voiture).

### Installation

1. Télécharger le binaire OTP depuis le [guide officiel](https://docs.opentripplanner.org/en/v2.7.0/Getting-OTP/) et le placer dans `otp-toulouse/bin/`.

2. Télécharger la carte OSM de Toulouse (format PBF) :
   - Zone précise (bbox personnalisée) : https://extract.bbbike.org/ → *Protocolbuffer (PBF)*
   - Zone standard : https://download.bbbike.org/osm/bbbike/Toulouse/
   - Placer le fichier `Toulouse.osm.pbf` dans `data/gtfs/`.

3. Placer les dossiers GTFS (`tisseo_gtfs/`, `ter_gtfs/`) dans `data/gtfs/`.

### Construction et démarrage (hors Docker)

```shell
# Construire le graphe de transport (une seule fois, résultat : data/gtfs/graph.obj)
java -Xmx4G -jar otp-toulouse/bin/otp-shaded-2.8.1.jar --build data/gtfs --save

# Démarrer le serveur OTP
java -Xmx4G -jar otp-toulouse/bin/otp-shaded-2.8.1.jar --load data/gtfs
```

### Configuration dans le controller

```yaml
# llm-agents/config/config_baseline_1000_current.yaml
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
