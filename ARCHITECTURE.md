# Architecture du Système — LLM Agents GAMA

> Document technique à destination des ingénieurs logiciel.  
> Décrit l'architecture complète du système de simulation multi-agents urbaine couplant GAMA, des LLMs et OpenTripPlanner pour modéliser le comportement de déplacement d'habitants synthétiques de Toulouse.

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Carte des services](#2-carte-des-services)
3. [Flux de données de bout en bout](#3-flux-de-données-de-bout-en-bout)
4. [EQUASIM Toulouse — Génération de la population](#4-equasim-toulouse--génération-de-la-population)
5. [GAMA — Moteur de simulation multi-agents](#5-gama--moteur-de-simulation-multi-agents)
6. [Controller — Cerveau Python de la simulation](#6-controller--cerveau-python-de-la-simulation)
7. [LLM Module — Passerelle d'inférence LLM](#7-llm-module--passerelle-dinférence-llm)
8. [OpenTripPlanner — Moteur de routage multimodal](#8-opentripplanner--moteur-de-routage-multimodal)
9. [Infrastructure transversale](#9-infrastructure-transversale)
10. [Observabilité](#10-observabilité)
11. [Schéma réseau Docker](#11-schéma-réseau-docker)

---

## 1. Vue d'ensemble

Le projet simule une ville (Toulouse) peuplée d'agents synthétiques dotés de comportements de déplacement réalistes, générés par des LLMs. L'architecture repose sur quatre domaines fonctionnels distincts interconnectés :

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Domaine simulation                           │
│                                                                      │
│   ┌──────────┐  HTTP/WS   ┌────────────────┐  HTTP   ┌───────────┐  │
│   │   GAMA   │◄──────────►│   Controller   │────────►│    OTP    │  │
│   │ (GAML)   │            │  (Python/ASGI) │         │  :8080    │  │
│   └──────────┘            └───────┬────────┘         └───────────┘  │
│                                   │ HTTP                             │
│                          ┌────────▼────────┐                        │
│                          │   LLM Module    │                        │
│                          │  API  │ Worker  │                        │
│                          │ :8000 │ Celery  │                        │
│                          └────────┬────────┘                        │
│                                   │                                  │
│                          ┌────────▼────────┐                        │
│                          │     Redis       │                        │
│                          │  DB0/DB1/DB2    │                        │
│                          └─────────────────┘                        │
│                                                                      │
│              ┌─────────────────────────────────────┐                │
│              │       Monitoring Stack               │                │
│              │  Prometheus :9090 | Grafana :3000    │                │
│              │  Flower :5555     | Node Exporter    │                │
│              └─────────────────────────────────────┘                │
└──────────────────────────────────────────────────────────────────────┘
```

**Principe fondamental :** GAMA est le moteur de simulation qui délègue les décisions de déplacement au Controller Python. Le Controller interroge OTP pour les itinéraires, puis appelle le LLM Module pour que les agents choisissent leur trajet selon leur personnalité et leur historique. Les décisions sont renvoyées à GAMA via WebSocket.

---

## 2. Carte des services

| Service | Image/Build | Port | Rôle |
|---------|-------------|------|------|
| `eqasim-init` | `./eqasim-toulouse` | — | **One-shot** : génère la population synthétique JSON avant le démarrage du controller |
| `redis` | `redis:7-alpine` | 6379 | Broker de messages, cache d'état des tâches, backend Celery |
| `otp` / `otp2` | `./otp-toulouse` | 8080/8081 | Moteur de routage multimodal (bus, tram, métro, marche) |
| `api` | `./llm_module` | 8000 | Passerelle REST LLM — reçoit les tâches, orchestre les workers |
| `worker` | `./llm_module` | — | Worker Celery — exécute les inférences LLM (concurrence 8) |
| `controller` | `./llm-agents` | 8002 | Orchestrateur de simulation — interface GAMA ↔ LLM |
| `flower` | `./llm_module` | 5555 | Monitoring Celery (UI web) |
| `prometheus` | `prom/prometheus` | 9090 | Collecte des métriques |
| `grafana` | `grafana/grafana` | 3000 | Dashboards de monitoring |
| `node_exporter` | `prom/node-exporter` | 9100 | Métriques système de l'hôte |
| `gama` | *(non dockerisé)* | — | Simulation multi-agents GAML (lancé manuellement) |

### Dépendances de démarrage

```
eqasim-init ──────────────────────────────────────────────┐
  (one-shot : génère toulouse_population_N.json)           │
                                                           ▼
redis ──────────────────────┐                         controller
                            ▼                              ▲
otp ────────────────────► api ─────────────────────────────┘
                            │
                            └──────────────► worker
                                                │
                                                └──────► flower
```

L'ordre de démarrage recommandé en pratique :
1. `docker compose up` (tous les services Docker — eqasim-init se lance en premier)
2. Lancer GAMA manuellement
3. Démarrer la simulation GAML

---

## 3. Flux de données de bout en bout

### 3.1 Initialisation de la simulation

```
[Docker startup]
  eqasim-init (one-shot)
    └─► generate_population.py
          ├─ Vérifie si toulouse_population_N.json existe dans eqasim_output (cache)
          ├─ Cache hit  → exit 0 immédiatement
          └─ Cache miss → synpp pipeline (INSEE → activités → JSON)
                └─► toulouse_population_N.json → volume eqasim_output

[GAMA démarre]
  └─► POST http://controller:8002/init
        └─► init_dynamic_scenario()
              ├─ EqasimJSONPopulationLoader.load_population()
              │     ├─ Lit toulouse_population_N.json (volume eqasim_output)
              │     ├─ Filtre : bbox GTFS + PersonCloseToTheStopFilter (≤5km arrêt)
              │     └─ Échantillonne population_size personnes
              ├─ Construction du monde (WorldModel, GTFS)
              └─► WorldInitResponse{ persons: [...] }  ◄── GAMA reçoit la liste
```

### 3.2 Cycle de simulation (par pas de temps)

```
[Pas de temps GAMA]
  └─► POST /sync  { idle_agents: [agent_id, location, time, ...] }
        └─► SimulationLoopV1.sync()
              ├─ Phase 1: Mise à jour des positions des agents au repos
              ├─ Phase 2: Déclenchement de la réflexion mémoire (toutes les N heures sim.)
              └─ Phase 3: asyncio.create_task(schedule_person_move())  [non-bloquant]
                    │
                    ▼  [tâche de fond, en parallèle pour chaque agent]
              determine_next_move_for_person()
                    ├─► PersonScheduler.next_activity()    — quelle est la prochaine activité ?
                    ├─► trip_helper.get_itineraries()      — OTP/Solari: N options d'itinéraires
                    └─► LlmAgent.evaluate_and_choose_travel_plan()
                              └─► LLMClient.execute_async()
                                        ├─► POST api:8000/tasks
                                        └─► poll GET /tasks/{id}  jusqu'à status=success
```

### 3.3 Retour des décisions vers GAMA

```
LoopContainer.publish_loop()  [boucle fond, toutes les ~1s]
  └─ si scenario.has_messages():
        └─► WebSocket → GAMA topic "action/data"
                  { agent_id, chosen_itinerary, departure_time, reason }
                        └─► GAMA déplace l'agent physiquement dans la simulation
```

### 3.4 Pipeline d'inférence LLM

```
POST /tasks  { category, agents[], parameters }
  └─► Task créée (status=PENDING) → Redis key task:{uuid}
  └─► batch_key = MD5(category + params + force_provider)
  └─► Redis RPUSH batch:{batch_key}
        ├─ si queue_size == 1  → process_batch_task.apply_async(countdown=1s)
        └─ si queue_size >= batch_limit → process_batch_task.delay()  [immédiat]

[Worker Celery]
process_batch_task(batch_key)
  ├─► load_balancer.select_provider()     — SWRR + vérification RPM
  ├─► pop_tasks_from_batch_sync()         — LPOP jusqu'à batch_max_agents entrées
  ├─► prompt_manager.render(category, agents, params)
  │         └─ template Jinja2 {category}.md.j2 → [system_msg, user_msg]
  ├─► adapter.call(internal_request)      — appel HTTP vers l'API du fournisseur LLM
  │         └─ structured output JSON → LLMOutput{ agents: [AgentResponse...] }
  ├─► démultiplexage agent_id → AgentResponse
  └─► Task.status=SUCCESS, Task.result=[...] → Redis
```

---

## 4. EQUASIM Toulouse — Génération de la population

### Description

EQUASIM est un pipeline de synthèse de population (package Python `synpp`) qui génère des habitants synthétiques réalistes à partir de données publiques françaises (INSEE, OSM, GTFS, BAN, BDTOPO). Les sources ne sont pas dans ce dépôt — elles sont gérées dans un repo git séparé, dans le dossier `eqasim-toulouse/` (ignoré par ce repo).

### Pipeline de génération

```
données INSEE ──► enrichissement démographique ──► échantillonnage
     (RP, FILOSOFI, ENTD)                          (sampling_rate)
                                                        │
                              ┌─────────────────────────┘
                              ▼
                   synthesis.population.llm_agents
                              │
                              ▼
              toulouse_population_N.json
              ┌──────────────────────────────────┐
              │ person_id, name (Faker fr_FR)    │
              │ age, sex, household_size         │
              │ income, socioprofessional_class  │
              │ employment_sector                │
              │ activities[] (horaires + coords) │
              │ home {lon, lat}                  │
              │ big_five (si flag activé)        │
              └──────────────────────────────────┘
```

### Intégration Docker

| Aspect | Valeur |
|--------|--------|
| Service | `eqasim-init` (one-shot, `restart: no`) |
| Volume données brutes | `./data/eqasim/data:/eqasim-data` (lecture seule) |
| Volume cache pipeline | `eqasim_cache` (accélère les re-runs) |
| Volume sortie | `eqasim_output` (partagé avec `controller` en lecture seule) |

### Variables d'environnement

| Variable | Description |
|----------|-------------|
| `EQASIM_POPULATION_SIZE` | Agents cibles (sinon lu depuis `APP_CONFIG_PATH`) |
| `EQASIM_GENERATE_PERSONALITY` | `true` → remplit les scores Big Five (OCEAN), déterministe par `person_id` |
| `EQASIM_FORCE_REGENERATE` | `true` → ignore le cache et relance synpp |
| `EQASIM_RANDOM_SEED` | Graine synpp (défaut 1234) |

### Cache

Si un fichier `toulouse_population_N.json` existe dans `eqasim_output` avec N ≥ `population_size`, synpp est sauté. Les populations générées sont conservées entre les redémarrages.

---

## 5. GAMA — Moteur de simulation multi-agents

### Description

GAMA est une plateforme de simulation multi-agents open source (développée par l'IRD/UMMISCO). Les modèles sont écrits en **GAML** (GAMA Modeling Language). Dans ce projet, GAMA simule la ville de Toulouse et ses habitants.

**Fichiers GAML principaux** (`GAMA/CityTransport/`) :

| Fichier | Rôle |
|---------|------|
| `City.gaml` | Expérience principale, point d'entrée de la simulation |
| `LLMAgent.gaml` | Agents qui appellent le controller via HTTP |
| `Inhabitant.gaml` | Agent de base — résidents de la ville |
| `PublicTransport.gaml` | Modélisation des transports en commun |
| `Settings.gaml` | Paramètres globaux de la simulation |

### Protocole de communication GAMA ↔ Controller

| Direction | Protocole | Endpoint / Topic | Contenu |
|-----------|-----------|-----------------|---------|
| GAMA → Controller | HTTP POST | `/init` | Démarrage : demande la liste des agents |
| GAMA → Controller | HTTP POST | `/sync` | Chaque pas : envoie les agents au repos |
| GAMA → Controller | WebSocket | `observation/data` | Observations en temps réel |
| Controller → GAMA | WebSocket | `action/data` | Décisions de déplacement |

> **Note** : GAMA n'est pas encore Dockerisé (service commenté dans `docker-compose.yml`). La communication HTTP depuis GAMA vers le Controller utilise `ws://host.docker.internal:3001` pour traverser la frontière Docker/hôte.

---

## 6. Controller — Cerveau Python de la simulation

### Description

Le Controller (`llm-agents/`) est une application **FastAPI** (servie par **Hypercorn** pour le support HTTP/2 — requis par GAMA avec Java 21) qui orchestre l'ensemble de la logique métier de la simulation.

**Point d'entrée Docker** :
```sh
python /app/archive_log.py && hypercorn handle.application:app --bind 0.0.0.0:8002
```

### API REST

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/init` | Génère la population synthétique pour GAMA |
| `POST` | `/sync` | Reçoit les agents au repos, déclenche le planning |
| `POST` | `/reflect` | Force une réflexion mémoire à un timestamp donné |
| `GET` | `/metrics` | Métriques Prometheus |

### Architecture interne du Controller

```
handle/application.py  (FastAPI app)
  │
  ├── SimulationLoopV1  (urban_mobility_agents/simulation_controller.py)
  │     ├── PersonScheduler           — prochaine activité selon l'agenda
  │     ├── OTPTripHelper             — appels à OpenTripPlanner
  │     └── LlmAgent[]                — un agent IA par habitant simulé
  │           ├── UserShortTermMemory  — buffer conversationnel en mémoire
  │           └── MultiUserLongTermMemory — ChromaDB (index vectoriel partagé)
  │
  └── LoopContainer                   — gestion du WebSocket vers GAMA
        └── publish_loop()            — envoi des décisions toutes les ~1s
```

### Système de mémoire des agents

#### Mémoire à court terme (`UserShortTermMemory`)
- Stockage en mémoire Python, structuré par `activity_id`
- Contient : observations environnementales, décisions de trajet, événements
- Effacée après chaque cycle de réflexion

#### Mémoire à long terme (`MultiUserLongTermMemory`)
- Backend : **ChromaDB** (base vectorielle locale)
- Index unique partagé entre tous les agents, partitionné par `person_id`
- Types d'entrées : `REFLECTION` (synthèse narrative) et `CONCEPT` (notion extraite)
- Score de pertinence composite lors de la récupération :
  ```
  score = similarité_cosinus × 0.4
        + BLEU_keywords        × 0.3
        + décroissance_temps   × 0.3
  ```
- Filtres optionnels : jour de la semaine, fenêtre de récence

#### Cycles de réflexion

```
Toutes les 6h (temps simulé) :
  STM → prompt → LLM → { reflection, concepts[] } → LTM
  STM effacée

Tous les N jours (temps simulé, optionnel) :
  LTM récents → prompt → LLM → réflexion de plus haut niveau → LTM
```

### Prise de décision de déplacement

```python
evaluate_and_choose_travel_plan(person, itineraries, current_time)
  ├─ build_travel_plan_payload()
  │   ├─ persona traits (perception JSON)
  │   ├─ destination + current_time
  │   ├─ history: top-k mémoires LTM re-classées
  │   └─ trajectories: liste d'options OTP avec mode, description, distance
  └─► LLMClient.execute_async(category="itinary_multi_agent", ...)
              └─► { chosen_index, mode, reason }
```

Les itinéraires sont mélangés aléatoirement avant envoi au LLM pour éviter le biais de position. Le raisonnement retourné est stocké en STM pour les futures réflexions.

### Ajustement des horaires

Lors d'une arrivée tardive, le Controller adapte l'heure de départ future selon une loi quadratique :
```
ajustement = min(0.02 × (retard_minutes)² × 60, 3600s)
```

---

## 7. LLM Module — Passerelle d'inférence LLM

### Architecture en deux processus

Le module LLM est déployé sous deux containers partageant le même image Docker :

```
┌─────────────────────────────────────────────────────────────┐
│                         llm_module                          │
│                                                             │
│  ┌──────────────────────┐    ┌─────────────────────────┐   │
│  │       api :8000       │    │    worker (Celery x4)   │   │
│  │  (FastAPI/uvicorn)   │    │  process_batch_task()   │   │
│  │                      │    │                         │   │
│  │  POST /tasks         │    │  LoadBalancer (SWRR)    │   │
│  │  GET  /tasks/{id}    │    │  Adapters (OAI/Gemini   │   │
│  │  GET  /health        │    │            Mistral/Groq)│   │
│  │  GET  /metrics       │    │  PromptManager (Jinja2) │   │
│  └──────────┬───────────┘    └────────────┬────────────┘   │
│             │                             │                 │
│             └─────────────┬───────────────┘                 │
│                           ▼                                 │
│                    Redis (DB0/1/2)                          │
└─────────────────────────────────────────────────────────────┘
```

### Routage et load balancing LLM

#### Fournisseurs configurés (`config/providers.yaml`)

| Fournisseur | Modèle | RPM | Batch max | Poids SWRR |
|-------------|--------|-----|-----------|------------|
| `openai` | gpt-4o-mini | 15 | 10 | 1 |
| `mistral` | mistral-small-latest | 100 | 10 | 1 |
| `google_gemini2` | gemini-2.0-flash-lite | 14 | 40 | 2 |
| `google_gemma42/43/3n` | Gemma 4 (variantes) | 25 | 2 | 2 |
| `groq_llama3/4/qwen/llama31/openai` | Modèles Groq hébergés | 25 | 1–4 | 1 |

Les fournisseurs sans clé API dans l'environnement sont automatiquement exclus au démarrage.

#### Algorithme Smooth Weighted Round-Robin (SWRR, style NGINX)

```
1. Au démarrage : construction d'une séquence pondérée
   ex. poids [2,1,1] → [gemini, openai, gemini, mistral, ...]

2. select_provider() :
   Pour chaque candidat dans l'ordre SWRR :
     a. is_provider_disabled() ?        → skip (désactivé sur erreurs consécutives)
     b. is_in_cooldown() ?              → skip (backoff temporaire)
     c. get_rpm() >= rpm_limit ?        → skip (quota atteint, fast path)
     d. try_reserve_rpm() [script Lua]  → atomique : INCR + rollback si dépassement
     
   Si aucun fournisseur disponible → RuntimeError → Celery retry (15s)
```

#### Gestion des erreurs et circuit breaker

| Condition | Action |
|-----------|--------|
| HTTP 5xx / erreur réseau | `mark_cooldown(60s)` + retry exponentiel (1s base, max 30s, 10 tentatives) |
| HTTP 429 (rate limit) | Même cooldown + backoff, `decrement_rpm()` pour rembourser le slot |
| 30 erreurs consécutives | `disable_provider(120–180s)` — exclu du routage jusqu'à expiration |
| Erreur générale | `decrement_rpm()` — le quota non consommé est restitué |

### Batching des requêtes

Le système regroupe dynamiquement les requêtes LLM de même catégorie :

```
POST /tasks x N (même catégorie + paramètres)
  → batch_key = MD5(category + params)
  → Redis RPUSH batch:{batch_key}  ← accumulation
  
Déclenchement worker :
  - Si c'est la 1ère tâche : countdown=1s (fenêtre d'accumulation)
  - Si queue >= batch_limit : immédiat
  
Worker LPOP jusqu'à batch_max_agents entrées → 1 seul appel LLM pour N agents
```

### Templates de prompts

Deux catégories de tâches existent (`prompts/templates/`) :

| Template | Usage |
|----------|-------|
| `itinary_multi_agent.md.j2` | Sélection de mode de transport — cas d'usage principal |
| `perception_filter.md.j2` | Synthèse d'observations environnementales |

Le `PromptManager` (Jinja2) découpe le template rendu selon les marqueurs `<!-- SYSTEM -->` et `<!-- USER -->` et injecte le schéma JSON pour le structured output directement dans le prompt.

### Adapters LLM

Chaque fournisseur possède son adapter (`adapters/`) qui hérite de `BaseAdapter` :

```
BaseAdapter (ABC)
  ├── OpenAIAdapter    — OpenAI + Groq (API compatible)
  ├── GoogleAdapter    — Gemini + Gemma via Google AI Studio
  └── MistralAdapter   — Mistral AI
```

Tous les adapters retournent `(LLMOutput, tokens_in, tokens_out)`. L'output est structuré via JSON Schema (structured outputs / function calling selon le fournisseur).

---

## 8. OpenTripPlanner — Moteur de routage multimodal

### Description

**OpenTripPlanner (OTP)** est un moteur de routage open source qui calcule des itinéraires multimodaux (bus, tram, métro, marche à pied) à partir de données GTFS et OpenStreetMap.

### Données Toulouse (`otp-toulouse/toulouse/`)

| Fichier | Description |
|---------|-------------|
| `graph.obj` | Graphe OTP pré-compilé (versionnée via DVC) |
| `gtfs/` | Données GTFS des transports en commun toulousains |
| `Toulouse.osm.pbf` | Données OpenStreetMap de la métropole |

**Endpoint utilisé** : `GET /otp/transmodel/v3` (API Transmodel v3)

### Modes d'accès depuis le Controller

Le Controller supporte deux modes configurables via `settings.gtfs.mode` :

| Mode | Implémentation | Description |
|------|----------------|-------------|
| `OTP` | `OTPTripHelper` | Appels HTTP directs vers OTP à chaque requête |
| `SOLARI` | `CachedTripHelper(SolariTripHelper)` | Routeur RAPTOR local avec cache — réduit la charge OTP |

---

## 9. Infrastructure transversale

### Redis — Triple rôle

| Base Redis | Usage |
|------------|-------|
| DB 0 | État des tâches LLM (`task:{uuid}`), compteurs RPM, queues batch, circuit breaker |
| DB 1 | Broker Celery (file de messages) |
| DB 2 | Backend résultat Celery |

Les compteurs RPM sont gérés via un **script Lua atomique** côté Redis pour garantir l'absence de race condition entre les workers :
```lua
local current = redis.call('INCR', key)
if current == 1 then redis.call('EXPIRE', key, 60) end
if current > limit then redis.call('DECR', key) return 0 end
return 1
```

### Variables d'environnement clés

| Variable | Service | Description |
|----------|---------|-------------|
| `REDIS_URL` | tous | URL Redis partagée (DB 0) |
| `CELERY_BROKER_URL` | api, worker | Redis DB 1 |
| `CELERY_RESULT_BACKEND` | api, worker | Redis DB 2 |
| `OTP_ENDPOINT` | controller | URL de l'API OTP |
| `APP_CONFIG_PATH` | api, controller | Chemin vers le fichier YAML de config |
| `GAMA_WS_URL` | api, controller | WebSocket vers GAMA |
| `LLM_API_URL` | controller | URL du service `api` |
| `PROVIDER_KEYS__*` | worker | Clés API par fournisseur LLM |

---

## 10. Observabilité

### Métriques Prometheus

Deux collecteurs exposent des métriques sur `/metrics` :

**`api:8000/metrics`** — métriques LLM via `WorkerMetricsCollector` (lit les clés Redis `wmetrics:*`) :

| Métrique | Labels | Description |
|----------|--------|-------------|
| `gama_agents_received_total` | category | Agents reçus par catégorie |
| `llm_provider_calls_ok/err_total` | provider | Appels réussis / en erreur |
| `llm_tokens_in/out_total` | provider | Tokens consommés |
| `llm_errors_by_type_total` | error_type | Répartition des erreurs |
| `llm_transport_mode_chosen_total` | mode | Mode de transport choisi |
| `llm_trip_distance_bracket_total` | bracket | Tranche de distance |
| `llm_mode_by_distance_total` | mode, bracket | Mode × distance |
| `llm_mode_by_provider_total` | mode, provider | Mode × fournisseur |
| `llm_chosen_index_total` | index | Position de l'itinéraire choisi (biais) |

**`controller:8002/metrics`** — métriques de simulation :

| Métrique | Description |
|----------|-------------|
| `controller_sync_requests_total` | Nombre de `/sync` reçus |
| `gama_sim_agents_total` | Agents dans la simulation |
| `gama_sim_step_interval_seconds` | Durée entre deux pas |
| `gama_process_person_calls_total` | Appels de planification |
| `gama_evaluate_plan_calls_total` | Appels LLM de décision |
| `gama_actions_created_total` | Actions retournées à GAMA |

### Stack de monitoring

```
                  ┌─────────────────┐
                  │    Grafana      │  :3000
                  │  Dashboards     │◄──────────┐
                  └─────────────────┘           │
                                                │
                  ┌─────────────────┐           │
                  │   Prometheus    │  :9090 ───┘
                  │  (scraping 5s)  │
                  └────────┬────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   api:8000/metrics  controller:8002  node_exporter
                       /metrics         :9100
```

### Flower — Monitoring Celery

Interface web sur `:5555` permettant de visualiser :
- État des tâches (pending, active, succeeded, failed)
- Utilisation des workers
- Taux de traitement des files d'attente

---

## 11. Schéma réseau Docker

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Réseau Docker interne                        │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  eqasim-init (one-shot)                                     │   │
│  │  synpp → toulouse_population_N.json → 📦 eqasim_output      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                            │ (service_completed_successfully)       │
│                            ▼                                        │
│   ┌──────────┐    ┌─────────────┐    ┌────────────┐                │
│   │   redis  │    │     otp     │    │  prometheus│                │
│   │  :6379   │    │  :8080/8081 │    │   :9090    │                │
│   └─────┬────┘    └──────┬──────┘    └─────┬──────┘                │
│         │                │                 │                        │
│    ┌────┴────────────────┤     ┌───────────┘                        │
│    │                     │     │                                    │
│    ▼                     ▼     ▼                                    │
│  ┌──────────────────┐   ┌───────────────────────────────────────┐  │
│  │       api        │   │  controller  📦 eqasim_output (ro)    │  │
│  │     :8000        │◄──│              :8002                    │  │
│  └──────────────────┘   └───────────────────────────────────────┘  │
│         ▲                                  ▲                        │
│  ┌──────┴───────┐                          │ WebSocket              │
│  │    worker    │                          │ host.docker.internal   │
│  │   (Celery)   │               ┌──────────┴──────────┐            │
│  └──────────────┘               │   GAMA (hôte Mac)   │            │
│         ▲                       │   (non dockerisé)   │            │
│  ┌──────┴───────┐               └─────────────────────┘            │
│  │    flower    │                                                   │
│  │    :5555     │                                                   │
│  └──────────────┘                                                   │
│                                                                     │
│  ┌──────────────┐   ┌────────────────┐                             │
│  │   grafana    │   │  node_exporter │                             │
│  │    :3000     │   │     :9100      │                             │
│  └──────────────┘   └────────────────┘                             │
└─────────────────────────────────────────────────────────────────────┘
           ▲ Ports exposés vers l'hôte
           │
    8000 | 8002 | 8080 | 8081 | 5555 | 9090 | 3000 | 9100 | 6379
```

---

## Annexe — Décisions d'architecture notables

| Décision | Justification |
|----------|---------------|
| **Hypercorn** à la place d'uvicorn pour le Controller | GAMA (Java 21) envoie des headers `Upgrade: h2c` qui brisent la lecture du body sous uvicorn |
| **Script Lua atomique** pour les compteurs RPM | Évite les race conditions entre workers Celery lors de la vérification des quotas |
| **Mélange des itinéraires** avant envoi au LLM | Supprime le biais de position (le LLM tend à sur-choisir le premier élément) |
| **Index ChromaDB partagé** avec filtrage par `person_id` | Réduit l'overhead de création d'index ; permet des requêtes cross-agent si nécessaire |
| **Batching dynamique** (fenêtre 1s) | Amortit le coût par token en envoyant N agents dans un seul appel LLM |
| **SWRR pondéré** plutôt que round-robin simple | Distribue la charge proportionnellement aux capacités de chaque fournisseur |
| **Ajustement quadratique des horaires** | Modèle comportemental : un retard important produit une adaptation plus forte qu'un léger retard |
| **Population EQUASIM via service one-shot** | Découple la génération (lente, peut prendre 30 min) du démarrage du controller. Le cache JSON évite de relancer synpp à chaque `docker compose up`. |
| **Big Five purement aléatoires** (hash person_id) | Alternative délibérée aux ajustements démographiques non sourcés. Reproductible sans biais arbitraire. |
