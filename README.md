# LLM Agents & GAMA platform
Modeling realistic human behavior using generative agents in a multimodal transport system: Software architecture and Application to Toulouse.

<!-- ![intro](docs/paper/raw_assets/toulouse_transport_system.png) -->

## Dépôts externes

Ce projet dépend de modules dont les sources ne sont pas hébergées dans ce dépôt.

| Module | Emplacement local | Dépôt git séparé |
|--------|------------------|-----------------|
| EQUASIM Toulouse | `eqasim-toulouse/` | géré dans un repo indépendant |

Le dossier `eqasim-toulouse/` est intentionnellement absent du suivi git de ce dépôt (`.gitignore`). Il doit être cloné/configuré manuellement après avoir cloné ce projet (voir la section [Population synthétique — EQUASIM](#0-population-synthétique--equasim) ci-dessous).

## Source references

- GTFS references: https://gtfs.org/resources/gtfs/
- GTFS Tisséo: https://data.toulouse-metropole.fr/explore/dataset/tisseo-gtfs/information/
- GTFS TER SNCF: https://www.data.gouv.fr/fr/datasets/horaires-des-lignes-ter-sncf/
- EQUASIM Toulouse guide: https://github.com/eqasim-org/eqasim-france/blob/main/docs/cases/toulouse.md
- OpenTripPlanner: https://www.opentripplanner.org/

## Architecture

![architecture](docs/paper/raw_assets/architecture.png)

## User guide

### 0. Population synthétique — EQUASIM

Le module EQUASIM génère une population synthétique réaliste (activités, localisation, démographie) à partir des données publiques françaises (INSEE, OSM, GTFS, BAN, BDTOPO).

Le guide officiel de configuration pour Toulouse est disponible ici :
**https://github.com/eqasim-org/eqasim-france/blob/main/docs/cases/toulouse.md**

#### Mise en place du dépôt eqasim-toulouse

Le dossier `eqasim-toulouse/` n'est **pas inclus** dans ce dépôt git. Il faut le configurer manuellement :

```shell
# Cloner le fork EQUASIM dans le bon dossier
git clone <url-du-fork-eqasim> eqasim-toulouse
```

Pour gérer tes modifications (fichiers custom : `synthesis/population/llm_agents.py`, `config_toulouse.yml`, `generate_population.py`) de manière indépendante :

```shell
cd eqasim-toulouse
git remote add upstream https://github.com/eqasim-org/eqasim-france.git
# Tes commits vont dans ton fork ; les mises à jour upstream via git pull upstream
```

#### Données d'entrée requises

Télécharger et placer les données dans `eqasim-toulouse/data/` (voir le [guide officiel](https://github.com/eqasim-org/eqasim-france/blob/main/docs/cases/toulouse.md)) :

| Données | Sous-dossier |
|---------|--------------|
| FILOSOFI (revenus INSEE) | `filosofi_2019/` |
| Recensement INSEE | `rp_2019/` |
| ENTD (enquête nationale déplacements) | `entd_2008/` |
| BD TOPO | `bdtopo_toulouse/` |
| OSM Toulouse | `osm_toulouse/` |
| GTFS Tisséo | `gtfs_toulouse/` |
| BAN (adresses) | `ban_toulouse/` |

#### Configuration eqasim (`config_toulouse.yml`)

Le fichier `eqasim-toulouse/config_toulouse.yml` contrôle le pipeline de génération :

```yaml
config:
  departments: ["31"]          # département(s) à inclure
  sampling_rate: 0.01          # taux d'échantillonnage (1 % ≈ 5 000 agents)
  random_seed: 1234
  data_path: /path/to/data
  output_path: /path/to/output
  output_prefix: toulouse_

  gtfs_path: gtfs_toulouse
  osm_path: osm_toulouse
  ban_path: ban_toulouse
  bdtopo_path: bdtopo_toulouse
```

#### Filtrage de la population par bounding box (bbox)

La zone de simulation est automatiquement dérivée de l'emprise géographique des arrêts GTFS, augmentée d'un tampon de **~5 km** (0,05°) :

```
world_bbox = GTFS stops extent ± 0.05°
```

Au chargement, seuls les agents dont le **domicile** est situé à l'intérieur de cette bbox sont retenus. Les agents qui travaillent ou étudient hors de la bbox restent dans la simulation mais leurs déplacements sont filtrés lors de la planification.

Pour analyser la distribution spatiale de la population et choisir une bbox adaptée à un pourcentage des flux :

```shell
python scripts/data/gtfs/analyze_mobility_bbox.py \
  --population data/eqasim_output/toulouse_population_5194.json \
  --percentile 95 \
  --output scripts/bbox_analysis.png
```

#### Générer la population manuellement (hors Docker)

```shell
cd eqasim-toulouse
poetry run python generate_population.py
# Résultat : output/toulouse_population_N.json
```

Variables d'environnement utilisées par `generate_population.py` :

| Variable | Défaut | Description |
|----------|--------|-------------|
| `EQASIM_POPULATION_SIZE` | lu depuis `APP_CONFIG_PATH` ou `1000` | Nombre d'agents cibles |
| `EQASIM_GENERATE_PERSONALITY` | `false` | Générer les scores Big Five (OCEAN) |
| `EQASIM_RANDOM_SEED` | `1234` | Graine de reproductibilité |

#### Activer le mode EQUASIM dans le controller

Dans le fichier de config YAML du controller (ex. `llm-agents/config/config_baseline_1000_current.yaml`) :

```yaml
gtfs:
  mode: OTP          # OTP (recommandé) ou SOLARI
  cache_enabled: false
```

En mode Docker, le service `eqasim` démarre automatiquement et expose une API HTTP sur le port 8003. Le controller interroge ce service pour récupérer la population générée.

---

### 1. Données GTFS — Tisséo + TER

La simulation utilise deux sources GTFS concaténées, placées dans `data/gtfs/` :

| Source | Dossier | Lien de téléchargement |
|--------|---------|------------------------|
| Tisséo (réseau urbain Toulouse) | `data/gtfs/tisseo_gtfs/` | https://data.toulouse-metropole.fr/explore/dataset/tisseo-gtfs/information/ |
| TER SNCF (réseau régional) | `data/gtfs/ter_gtfs/` | https://www.data.gouv.fr/fr/datasets/horaires-des-lignes-ter-sncf/ |

OTP lit directement le dossier `data/gtfs/` au complet (tous les sous-dossiers) lors de la construction du graphe. Les données sont ainsi fusionnées automatiquement.

Le notebook `scripts/data/gtfs/gtfs_merge.ipynb` permet de vérifier la cohérence des deux flux, d'analyser les routes et arrêts communs, et de produire un GTFS consolidé si besoin.

#### Préparer les données GTFS pour GAMA

Ce script génère le fichier `trip_info.json` consommé par le modèle GAMA et le copie dans `GAMA/CityTransport/includes/` :

```shell
bash scripts/update_gtfs_data.sh
```

Il exécute successivement :
1. `llm-agents/inputs/gtfs/reader.py` — génère les shapefiles d'arrêts et de routes
2. `llm-agents/inputs/gtfs/gama.py` — construit le calendrier et les horaires de chaque voyage au format JSON

---

### 2. OpenTripPlanner (OTP)

OTP est le moteur de calcul d'itinéraires multi-modal (transit + marche/vélo/voiture).

#### Installation

1. Télécharger le binaire OTP depuis le [guide officiel](https://docs.opentripplanner.org/en/v2.7.0/Getting-OTP/) et le placer dans `otp-toulouse/bin/`.

2. Télécharger la carte OSM de Toulouse (format PBF) :
   - Zone précise (bbox personnalisée) : https://extract.bbbike.org/ → *Protocolbuffer (PBF)*
   - Zone standard : https://download.bbbike.org/osm/bbbike/Toulouse/
   - Placer le fichier `Toulouse.osm.pbf` dans `data/gtfs/`.

3. Placer les dossiers GTFS (`tisseo_gtfs/`, `ter_gtfs/`) dans `data/gtfs/`.

#### Construction et démarrage

```shell
# Construire le graphe de transport (une seule fois, résultat : data/gtfs/graph.obj)
java -Xmx4G -jar otp-toulouse/bin/otp-shaded-2.8.1.jar --build data/gtfs --save

# Démarrer le serveur OTP
java -Xmx4G -jar otp-toulouse/bin/otp-shaded-2.8.1.jar --load data/gtfs
```

#### Configuration dans le controller

```yaml
# llm-agents/config/config_baseline_1000_current.yaml
gtfs:
  mode: OTP
  otp_endpoint: http://localhost:8080/otp/transmodel/v3
  otp_max_concurrent: 15    # requêtes OTP simultanées max
```

En Docker, plusieurs instances OTP peuvent tourner en parallèle. L'environnement les déclare via :

```
OTP_ENDPOINTS=http://otp1:8080/otp/transmodel/v3,http://otp2:8080/otp/transmodel/v3,...
```

---

### 3. OSMnx — routage pédestre / vélo / voiture

OSMnx calcule les itinéraires directs (sans transport en commun) : marche, vélo, voiture.

#### Fonctionnement

Les graphes OSMnx sont téléchargés depuis OpenStreetMap au premier démarrage puis mis en cache dans `data/osmnx_cache/` (persistant entre les redémarrages). Le calcul est délégué à des workers de processus dédiés par mode (foot, bike, car) pour contourner le GIL Python.

#### Mode HTTP distribué

En production Docker, OSMnx tourne dans un microservice dédié. Le controller le contacte via :

```
OSMNX_ENDPOINTS=http://osmnx1:8090/route
```

Plusieurs replicas peuvent être listés séparés par des virgules ; les requêtes sont distribuées en round-robin.

#### Configuration dans le controller

```yaml
gtfs:
  osmnx_cache_dir: /app/osmnx_cache   # dossier de cache des graphes
```

---

### 4. Providers LLM (`llm_module/config/providers.yaml`)

Le fichier `llm_module/config/providers.yaml` définit l'ensemble des fournisseurs LLM disponibles et leur paramétrage. La charge est distribuée entre providers actifs selon leur `weight`.

#### Structure d'un provider

```yaml
providers:
  <nom_unique>:
    adapter: <openai|google|groq|cerebras>   # facultatif si = nom
    rpm_limit: 15              # requêtes par minute max
    base_url: https://...      # endpoint de l'API
    default_model: gpt-4o-mini # modèle par défaut
    weight: 1.0                # poids de sélection (load balancing)
    batch_max_agents: 10       # agents traités par batch
    concurrency_limit: 3       # batches simultanés max
    disable_timeout: 180       # timeout en secondes
```

#### Providers actuellement disponibles

| Provider | Adapter | Modèle par défaut |
|----------|---------|-------------------|
| `openai` | openai | gpt-4o-mini |
| `mistral` | mistral | mistral-small-latest |
| `google_gemini31` | google | gemini-3.1-flash-lite-preview |
| `google_gemma42/43` | google | gemma-4-26b / 31b |
| `groq_llama3/4` | groq | llama-3.3-70b / llama-4-scout |
| `groq_qwen` | groq | qwen3-32b |
| `cerebras_*` | cerebras | gpt-oss-120b / llama3.1-8b / qwen-3 |

#### Clés API

Les clés sont injectées via des variables d'environnement, **jamais** dans le YAML :

```
PROVIDER_KEYS__openai=sk-...
PROVIDER_KEYS__groq=gsk-...
PROVIDER_KEYS__google=AIza...
PROVIDER_KEYS__mistral=...
PROVIDER_KEYS__cerebras=...
```

Pour plusieurs instances d'un même fournisseur (ex. `groq_llama3`, `groq_llama4`), la clé est partagée via l'`adapter` commun (`groq`).

---

### 5. Run the simulation

Démarrer tous les services Docker (LLM agents, Redis, OTP, OSMnx, EQUASIM) :

```shell
docker compose up
```

Le service `eqasim` génère la population synthétique au démarrage. Le controller attend qu'il soit prêt avant d'initialiser la simulation.

Options utiles :

```shell
# Forcer la regénération de la population
EQASIM_FORCE_REGENERATE=true docker compose up

# Surcharger la taille de population
EQASIM_POPULATION_SIZE=5000 docker compose up

# Choisir un fichier de config spécifique
CONFIG_FILE=config_baseline_100_current.yaml docker compose up
```

Ensuite :

- Ouvrir le modèle GAMA : `GAMA/CityTransport/City.gaml`
- Cliquer sur Play. Le controller se connecte à GAMA automatiquement via WebSocket.

---

### 6. Scripts disponibles

#### Analyse des résultats (`scripts/analysis/`)

| Script | Description |
|--------|-------------|
| `current_stats.ipynb` | Statistiques générales de la simulation en cours |
| `llm_traffic_analyse.ipynb` | Analyse du trafic généré par les agents LLM |
| `pipeline_delays.ipynb` | Analyse des délais du pipeline de planification |
| `run_analysis.py` | Script CLI pour lancer les analyses |

#### Données GTFS (`scripts/data/gtfs/`)

| Script | Description |
|--------|-------------|
| `analyze_mobility_bbox.py` | Analyse la distribution spatiale des déplacements pour calibrer la bbox |
| `gtfs_analysis.ipynb` | Exploration et statistiques des données GTFS |
| `gtfs_merge.ipynb` | Fusion et vérification des flux GTFS Tisséo + TER |
| `gtfs_to_shapefile.py` | Export des arrêts et tracés GTFS en Shapefile / GeoJSON |

#### Données population (`scripts/data/population/`)

| Script | Description |
|--------|-------------|
| `generate_population.ipynb` | Notebook de génération et inspection de la population EQUASIM |
| `statistics_population.ipynb` | Statistiques démographiques et de mobilité de la population |
| `travel_time.py` | Calcul des temps de trajet pour la population |
| `route_worker.py` | Worker de calcul d'itinéraires en batch |
| `cerema_values.yaml` | Valeurs de référence CEREMA EMC² 2023 pour calibration |
| `population_emc2_2023.yaml` | Données de l'Enquête Mobilité Certifiée CEREMA |

#### Infrastructure / debug (`scripts/infra/`)

| Script | Description |
|--------|-------------|
| `direct_trip.ipynb` | Test de calcul d'itinéraire direct (OTP / OSMnx) |
| `otp_shape.ipynb` | Visualisation des shapes OTP |
| `graph.ipynb` | Exploration du graphe de transport |
| `load_test_sync.ipynb` | Test de charge du controller |
| `live_chart.example.py` | Exemple de visualisation en temps réel |

---

## Reference

```
@misc{vu2025modelingrealistichumanbehavior,
      title={Modeling realistic human behavior using generative agents in a multimodal transport system: Software architecture and Application to Toulouse}, 
      author={Trung-Dung Vu and Benoit Gaudou and Kamaldeep Singh Oberoi},
      year={2025},
      eprint={2510.19497},
      archivePrefix={arXiv},
      primaryClass={cs.MA},
      url={https://arxiv.org/abs/2510.19497}, 
}
```
