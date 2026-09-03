# Quickstart — Lancer la simulation

## Prérequis

- Docker + Docker Compose
- GAMA Platform installé sur l'hôte (hors Docker) — **uniquement pour le mode IHM** ; le mode offline utilise l'image Docker officielle `gamaplatform/gama`
- Données GTFS et graph OTP construits (voir [data-pipeline.md](data-pipeline.md))
- Population EQUASIM configurée (voir [population.md](population.md))
- Fichier `.env` avec les clés API (voir [llm-providers.md](llm-providers.md))

---

## Ordre de démarrage (mode IHM)

```
1. docker compose up      ← démarre tous les services Docker
2. Ouvrir GAMA            ← fichier GAMA/CityTransport/City.gaml
3. Cliquer Play dans GAMA ← le controller se connecte via WebSocket ws://host.docker.internal:3001
```

Le service `eqasim` génère (ou charge depuis le cache) la population synthétique. Le controller attend sa disponibilité avant de s'initialiser.

---

## Mode offline — GAMA headless en conteneur

Tout démarre avec Docker, sans IHM GAMA ni intervention manuelle :

```shell
make run OFFLINE=1        # ou l'alias : make run-offline
```

(`make run --offline` n'est pas une syntaxe make valide — utiliser `OFFLINE=1`.)

Options combinables :

```shell
make run OFFLINE=1 NO_GOOGLE=1   # campagne sans les modèles Google (gemini/gemma) :
                                 # clés blanchies, instances google* hors rotation,
                                 # cascade sur mistral/groq/cerebras

make run OFFLINE=1 MEM=0         # coupe la mémoire des agents : LTM ET auto-réflexion
                                 # (MEM=1 pour les réactiver ; sans MEM, réglage inchangé).
                                 # Écrit dans GAMA/CityTransport/config/sim_params.yaml —
                                 # réglage PERSISTANT, il vaut aussi pour les runs IHM
                                 # suivants. L'injection de paramètres GAMA Server ne
                                 # fonctionne pas pour ces drapeaux : Settings.gaml
                                 # (load_sim_config) les écrase depuis ce fichier.

make stop-run                    # arrêt à chaud : stoppe GAMA et le launcher,
                                 # laisse le reste de la pile en place
make run OFFLINE=1 CONT=1        # reprise : réutilise le workdir du run précédent
                                 # (experiments/current) — journaux appendés,
                                 # state.json et checkpoints retrouvés, métriques
                                 # Grafana/Prometheus/Redis conservées
```

Sémantique de la reprise (`CONT=1`) : le contrôleur reprend **le même répertoire
d'expérience** ; la simulation GAMA, elle, repart à `t0` du jour simulé — GAMA ne
sait pas geler son état en plein trajet (ticket 002). Les caches (décisions LLM,
OTP, OSMnx) et `state.json` rendent ce rejeu quasi instantané et déterministe :
en pratique, la simulation « rattrape » le point d'interruption en quelques
minutes sans re-consommer de quota LLM.

Ce que fait le mode offline :

1. Démarre les services avec le profil compose `offline`, qui ajoute le service `gama` (image officielle `gamaplatform/gama:2025.06.4`, alignée sur la version validée des modèles) en mode **GAMA Server** (`-socket 6868`).
2. Le controller et l'api reçoivent `GAMA_WS_URL=ws://gama:3001` (au lieu de `ws://host.docker.internal:3001`).
3. Une fois les services prêts, le launcher `scripts/gama/launch_headless.py` (exécuté dans le conteneur controller) envoie `load` puis `play` au protocole GAMA Server, en injectant les paramètres `http_url`/`http_port` de l'expériment `e` pour que le modèle poste sur `http://controller:8002`.
4. La console GAMA est relayée dans `experiments/current/gama_headless.log`.

Points d'attention :

- Le launcher **garde sa connexion WebSocket ouverte pendant tout le run** : GAMA Server arrête les expériences dont le client se déconnecte. L'arrêt propre passe par `make down` (ou `docker compose --profile offline down`).
- À la pause de fin d'horizon (`simulation_max_days`), le controller **continue de drainer les réflexions STM en attente** (écritures LTM, utiles aux runs qui reprennent cette population). Si la LTM du run doit être réutilisée, attendre dans les logs controller le message `[drainage] Réflexions STM épuisées — LTM complète, arrêt sûr (make down)` avant d'arrêter les services.
- Les paramètres de scénario (population, jours simulés…) restent lus depuis `GAMA/CityTransport/config/sim_params.yaml`, comme en mode IHM.
- Sans display, l'observation passe par Grafana, vizpop (port 5050) et `make report`. Le protocole GAMA Server permet aussi d'évaluer des expressions GAML à chaud (port 6868 exposé sur l'hôte).

---

## Commandes Docker

```shell
# Démarrage standard — configuration unique : llm-agents/config/config.yaml
# (pour changer de config, éditer directement ce fichier)
docker compose up

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
| `population_emc2_2023.yaml` | **Cadrage** de la population interrogée par l'enquête CEREMA — périmètre, âge minimum, poids de redressement, couronnes. Chargé et validé par `llm_module.core.population_reference` ; toute valeur y est recoupée sur les microdonnées (cf. [périmètre de population](../arch/perimetre-population.md)) |
| `audit_perimetre.py` | `make audit-perimetre` — les neuf écarts de base entre population enquêtée et population simulée. Sortie 0 conforme / 2 à corriger / **3 axe non mesurable** |

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
