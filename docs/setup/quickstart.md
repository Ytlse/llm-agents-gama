# Quickstart — Lancer la simulation

## Prérequis

- Docker + Docker Compose
- GAMA Platform installé sur l'hôte (hors Docker)
- Données GTFS et graph OTP construits (voir [data-pipeline.md](data-pipeline.md))
- Population EQUASIM configurée (voir [population.md](population.md))
- Fichier `.env` avec les clés API (voir [llm-providers.md](llm-providers.md))

---

## Ordre de démarrage

```
1. docker compose up      ← démarre tous les services Docker
2. Ouvrir GAMA            ← fichier GAMA/CityTransport/City.gaml
3. Cliquer Play dans GAMA ← le controller se connecte via WebSocket ws://host.docker.internal:3001
```

Le service `eqasim` génère (ou charge depuis le cache) la population synthétique. Le controller attend sa disponibilité avant de s'initialiser.

---

## Commandes Docker

```shell
# Démarrage standard
docker compose up

# Choisir un fichier de config spécifique
CONFIG_FILE=config_baseline_100_current.yaml docker compose up

# Surcharger la taille de population
EQASIM_POPULATION_SIZE=5000 docker compose up

# Forcer la regénération de la population
EQASIM_FORCE_REGENERATE=true docker compose up

# Rebuild après un changement de code
docker compose up --build
```

---

## Ports exposés

| Service | Port | Description |
|---------|------|-------------|
| `controller` | 8002 | API FastAPI principale (Hypercorn HTTP/2) |
| `controller` | 5050 | Visualisation Folium (carte population) |
| `api` (LLM gateway) | 8000 | Passerelle LLM |
| `flower` | 5555 | UI de monitoring Celery |
| `eqasim` | 8003 | Service de génération de population |
| `otp1` | 8080 | OpenTripPlanner instance 1 |
| `otp2` | 8081 | OpenTripPlanner instance 2 |
| `otp3` | 8082 | OpenTripPlanner instance 3 |
| `osmnx1` | 8090 | Serveur de routage OSMnx |
| `redis` | 6379 | Redis (broker + état) |
| `prometheus` | 9090 | Métriques |
| `grafana` | 3000 | Dashboards |

---

## Scripts disponibles

### Analyse des résultats (`scripts/analysis/`)

| Script | Description |
|--------|-------------|
| `current_stats.ipynb` | Statistiques générales de la simulation en cours |
| `llm_traffic_analyse.ipynb` | Analyse du trafic généré par les agents LLM |
| `pipeline_delays.ipynb` | Analyse des délais du pipeline de planification |
| `run_analysis.py` | Script CLI pour lancer les analyses |

### Données GTFS (`scripts/data/gtfs/`)

| Script | Description |
|--------|-------------|
| `analyze_mobility_bbox.py` | Analyse la distribution spatiale des déplacements pour calibrer la bbox |
| `gtfs_analysis.ipynb` | Exploration et statistiques des données GTFS |
| `gtfs_merge.ipynb` | Fusion et vérification des flux GTFS Tisséo + TER |
| `gtfs_to_shapefile.py` | Export des arrêts et tracés GTFS en Shapefile / GeoJSON |

### Données population (`scripts/data/population/`)

| Script | Description |
|--------|-------------|
| `generate_population.ipynb` | Notebook de génération et inspection de la population EQUASIM |
| `statistics_population.ipynb` | Statistiques démographiques et de mobilité de la population |
| `travel_time.py` | Calcul des temps de trajet pour la population |
| `route_worker.py` | Worker de calcul d'itinéraires en batch |
| `cerema_values.yaml` | Valeurs de référence CEREMA EMC² 2023 pour calibration |
| `population_emc2_2023.yaml` | Données de l'Enquête Mobilité Certifiée CEREMA |

### Infrastructure / debug (`scripts/infra/`)

| Script | Description |
|--------|-------------|
| `direct_trip.ipynb` | Test de calcul d'itinéraire direct (OTP / OSMnx) |
| `otp_shape.ipynb` | Visualisation des shapes OTP |
| `graph.ipynb` | Exploration du graphe de transport |
| `load_test_sync.ipynb` | Test de charge du controller |
| `live_chart.example.py` | Exemple de visualisation en temps réel |

---

## Résultats de simulation

Chaque run crée un répertoire horodaté sous `experiments/archive/<YYYY-MM-DD>_<HH_MM>/`. Le lien symbolique `experiments/current` pointe vers le dernier run.

Fichiers CSV exportés dans `gama_results/` :

| Fichier | Description |
|---------|-------------|
| `move_log.csv` | Décisions de mobilité (mode, raisons LLM, retards, météo) |
| `gama_arrivals.csv` | Dérive temporelle entre trajet théorique et temps mesuré |
