# Architecture du Système — LLM Agents GAMA

> Document technique à destination des ingénieurs logiciel.
>
> Voir aussi les documents détaillés par sujet :
> [Cycle des agents](docs/arch/agents-lifecycle.md) · [Inférence LLM](docs/arch/llm-inference.md) · [Routage](docs/arch/routing.md) · [Cache & mémoire](docs/arch/cache-memory.md)

Description de l'architecture du système de simulation multi-agents urbaine couplant GAMA, des LLM et OpenTripPlanner (OTP) pour la modélisation des déplacements d'habitants synthétiques à Toulouse.

## 1. Vue d'ensemble du système

Le système couple un moteur de simulation géospatiale et un écosystème Python chargé de l'optimisation des itinéraires et de la prise de décision par calcul distribué.

### Division fonctionnelle des domaines

*   **Moteur de simulation (GAMA)** : Gère le cycle de temps, l'environnement spatial (Toulouse) et l'état physique des agents. Il délègue toute la logique décisionnelle et le calcul des routes via des interfaces réseau.
*   **Orchestration applicative (Controller FastAPI)** : Pivot central de la simulation. Il reçoit l'état des agents, interroge les moteurs de routage, maintient la mémoire (court/long terme) des agents et pilote les demandes d'inférence.
*   **Moteurs de routage (Calcul d'itinéraires)** :
    *   **Routage Transit (OTP)** : Dédié exclusivement aux transports en commun (bus, tram, métro) en mode horaire contraint.
    *   **Routage Direct (Cluster OSMnx)** : Dédié aux modes routiers et actifs (marche, vélo, voiture) via des graphes NetworkX locaux.
*   **Passerelle d'inférence (LLM Module)** : Abstraie l'accès aux API de modèles de langage, gère la répartition de charge, le regroupement des requêtes (batching) et les reprises sur erreur.

## 2. Cartographie des services et ordonnancement

### Dépendances de cycle de vie au démarrage

L'arbre suivant représente l'ordre strict de validation des services requis pour l'initialisation du système :

```text
[Démarrage du stack]
└── eqasim (Service HTTP persistant, port 8003 — génère ou charge la population)
    └── redis (Initialisation des DB 0, 1 et 2)
        ├── otp1 / otp2 / otp3 (Chargement de graph.obj + GTFS)
        │   └── api (Validation du endpoint /health)
        │       ├── worker (Sous-processus Celery couplés à la DB 1)
        │       └── osmnx1 (Warmup des graphes NetworkX — osmnx2/3 désactivés par défaut)
        └── controller (FastAPI + vizpop sur port 5050)
            └── GAMA (Lancement manuel hors-conteneur)
```

### Registre technique des conteneurs

*   `eqasim` (`./eqasim-toulouse`) : Port `8003`. Service HTTP persistant exposant `/health` et la population générée. Le controller attend sa disponibilité via `service_healthy`.
*   `redis` (`redis:7-alpine`) : Port `6379`. Triple usage : persistance d'état (DB0), broker Celery (DB1), backend de résultats (DB2).
*   `otp1` / `otp2` / `otp3` (`./otp-toulouse`) : Ports `8080`/`8081`/`8082`. API GraphQL Transmodel v3 pour le transit multimodal (6 Go RAM chacune).
*   `osmnx1` (`./llm-agents`) : Port `8090`. Serveur FastAPI exécutant le calcul Dijkstra sur graphes topologiques (4 Go RAM). Des replicas `osmnx2`/`osmnx3` peuvent être activés dans `docker-compose.yml`.
*   `api` (`./llm_module`) : Port `8000`. Passerelle d'orchestration asynchrone des requêtes LLM.
*   `worker` (`./llm_module`) : Processus d'inférence Celery (concurrence : 8).
*   `flower` (`./llm_module`) : Port `5555`. UI de monitoring des tâches Celery.
*   `controller` (`./llm-agents`) : Port `8002` (Hypercorn HTTP/2) + `5050` (Visualisation Folium).
*   `gama` (Hôte physique) : Instance de simulation GAML hors conteneur reliant le contrôleur via `ws://host.docker.internal:3001`.

## 3. Flux de données et cycles logiques

### 3.1 Arbre d'initialisation et de Bootstrap

Le chargement initial s'exécute selon la séquence logique descendante suivante :

```text
[Requête POST /init reçue par le Controller]
└── Étape 1 : Lecture du fichier toulouse_population_N.json
    └── Filtrage spatial (Bounding Box GTFS)
    └── Filtrage d'accessibilité (PersonCloseToTheStopFilter ≤ 5km d'un arrêt)
└── Étape 2 : Vérification du niveau d'enrichissement OSMnx
    ├── Si routes présentes dans le cache JSON -> Skip de la phase d'enrichissement
    └── Si routes absentes -> Calcul synchrone des itinéraires inter-activités via OSMnx
└── Étape 3 : Instanciation des structures mémoire (ChromaDB + structures de données locales)
└── Étape 4 : Génération de la réponse d'initialisation vers GAMA
└── Étape 5 : Lancement des vagues de pré-calcul (Bootstrap de fond)
    └── Vague 1 : act[N+1] → next_planned_move  (tous les agents éligibles)
    └── Vague 2 : act[N+2] → precomputed_moves
    └── Vague K : act[N+K] → precomputed_moves  (jusqu'à cycle complet par agent)
    └── Initialisation de precomputed_horizon_act / precomputed_horizon_ts
        → point de départ de l'horizon glissant pour le reste de la simulation
```

### 3.2 Cycle synchrone et boucle de planification des agents

La boucle d'évaluation d'un agent combine une part asynchrone (Worker) et un déclenchement événementiel (Arrivée d'un agent).

#### Logique de calcul d'itinéraire (arrive_by)

Pour garantir le réalisme des activités à horaire fixe, le système utilise une logique d'inversion temporelle :

*   Calcul du `target_arrival_time` basé sur l'heure de début planifiée de l'activité cible.
*   Si `target_arrival_time` est inférieur au timestamp actuel de la simulation, l'activité est planifiée pour le cycle du lendemain (`+ 86400 s`).
*   OTP est interrogé avec le paramètre `arriveBy=True`.
*   Les itinéraires directs (OSMnx) sont calculés à partir de la vitesse nominale du mode puis décalés en arrière dans le temps pour aligner l'heure de fin du trajet avec l'heure d'arrivée cible.

#### Arbre d'exécution d'une planification d'agent

```text
[Déclenchement : Agent déclaré IDLE ou retour d'observation]
└── Appel de _try_schedule_person()
    └── Acquisition d'un jeton du sémaphore de concurrence (_worker_sem)
    └── Requête des options de transport (CachedTripHelper)
        ├── Branche A : Transports en commun -> Appel OTP (GraphQL) par mode d'accès
        └── Branche B : Modes directs -> Appels parallèles au cluster OSMnx
    └── Consolidation et déduplication des itinéraires (Unification des timestamps en millisecondes)
    └── Phase décisionnelle (LlmAgent.evaluate_and_choose_travel_plan)
        └── Extraction de la mémoire à long terme (ChromaDB) via score composite
        └── Lookup dans le cache sémantique LLM (LlmSemanticCache)
            ├── Cache HIT  -> Retourne l'index immédiatement (mode = "cache:<modes>")
            └── Cache MISS -> Injection du Persona narratif + Météo + Historique + Itinéraires mélangés
                └── Inférence LLM (Sortie structurée JSON)
                    └── Store asynchrone dans le cache (fire-and-forget)
    └── Traitement du résultat
        └── Écriture de la décision dans la mémoire à court terme de l'agent
        └── Stockage du trajet dans next_planned_move (État PLANNED)
        └── Émission immédiate via la WebSocket directe (Point de poussée 1 ou 2)
```

#### Points d’injection des décisions (WebSocket)

*   **Point 1 (Fin de calcul synchrone)** : Si l’agent est immobile (IDLE) au moment où le LLM valide la décision, le plan est immédiatement poussé au topic GAMA `action/data`.
*   **Point 2 (Feedback d’arrivée)** : Si l’agent est en transit, le plan calculé reste en attente dans `next_planned_move` et s’exécute de manière déterministe dès réception de la notification d’arrivée dans GAMA prenant en compte le feedback pour replanifier l’activité.
*   **Cas du Bootstrap** : Utilisation temporaire d’une file d’attente globale `_messages` vidée périodiquement (fréquence 1s) avant la fin de l’initialisation.

#### Horizon glissant 24h (post-bootstrap)

À chaque Point 1 ou Point 2, après le `popleft()` sur `precomputed_moves`, le controller déclenche immédiatement `_refill_precomputed_queue` : calcul asynchrone de l’activité suivant l’horizon courant, sous `_worker_sem`, puis réappend dans `precomputed_moves`. La profondeur de la queue reste constante et égale au nombre d’activités du planning de l’agent (moins 1). Ce mécanisme maintient en permanence un buffer de trajets prêts, sans pic de calcul en cours de simulation.

## 4. Pipeline d'inférence LLM et optimisation réseau

Le module LLM fait office de répartiteur de charge haute performance pour les appels vers les API externes.

### Arbre d'ordonnancement des requêtes LLM (Batching & SWRR)

La file batch est un **Sorted Set Redis** (clé `batch:{batch_key}`) trié par `priority_score = min(departure_time)` des agents de la tâche. Les tâches les plus urgentes (départ imminent) sont extraites en premier. `batch_max_agents` est calculé automatiquement au démarrage à partir des quotas du fournisseur : `min(TPM ÷ tokens_par_agent, RPM, max_batch_agents)`.

```text
[Appels POST /tasks du Controller]
└── Calcul du priority_score = min(departure_time) des agents de la requête
    └── Calcul de la clé de hachage : MD5(Catégorie + Paramètres + Fournisseur_Forcé)
        └── Insertion dans le Sorted Set Redis batch:{batch_key} (score = priority_score)
            ├── Si taille du set = 1 -> Armement d'un compte à rebours Celery (1s)
            └── Si taille du set >= batch_limit -> Déclenchement immédiat du Worker
            └── Exécution par le Worker Celery
                ├── Sélection du fournisseur via l'algorithme SWRR
                │   ├── Vérification du Circuit Breaker (Fournisseur désactivé ?)
                │   ├── Vérification des quotas (Cooldown / Limite RPM via script Lua)
                │   └── Réservation atomique du slot de requête
                ├── Extraction des tâches les plus urgentes (ZPOPMIN jusqu'à batch_max_agents)
                ├── Rendu du prompt unifié via Jinja2 (Injection du schéma JSON)
                ├── Exécution de l'appel HTTP vers l'API du fournisseur sélectionné
                └── Démultiplexage des réponses par agent_id et mise à jour de la DB 2
```

### Gestion des pannes et résilience (Circuit Breaker)

*   **Erreurs réseau / Codes HTTP 5xx** : Activation d'un état de récupération (`mark_cooldown` de 60s) associé à une stratégie de re-tentatives exponentielles (1s à 30s, maximum 10 essais). Les tâches sont replacées dans le Sorted Set avec leur score d'origine.
*   **Limitation de débit (HTTP 429)** : Le cooldown est calé sur le header `x-ratelimit-reset-requests` retourné par le fournisseur (formats supportés : durée Groq `"Xm Y.Zs"` et timestamp ISO 8601 OpenAI), avec fallback à 60s. L'événement `ratelimit_reset` est tracé dans `llm_errors.jsonl`.
*   **Persistance de l'état d'erreur** : Au-delà de 30 échecs consécutifs, le fournisseur est basculé en exclusion totale du routage SWRR pour une durée glissante de 120 à 180 secondes.

## 5. Spécifications techniques des sous-systèmes de routage

### 5.1 Cluster OSMnx (Modes directs)

Chaque réplica du serveur OSMnx instancie à son démarrage trois graphes topologiques distincts en mémoire RAM (4 Go alloués par instance).

*   **Marche (walk)** : Vitesse fixe lue depuis la configuration. Coupure algorithmique des requêtes au-delà de 15 km de distance absolue.
*   **Vélo (bike)** : Vitesse nominale paramétrable. Coupure algorithmique fixée à 30 km.
*   **Voiture (drive)** : Pas de coupure spatiale. Application d'un modèle de congestion dynamique basé sur les profils horaires TomTom Toulouse.

#### Gestion du multi-processing

Afin d'éviter le blocage du GIL (Global Interpreter Lock) lors de l'exécution des algorithmes de Dijkstra, l'architecture s'adapte à l'environnement d'exécution :

*   **Mode conteneurisé standard** : Routage délégué à un `ProcessPoolExecutor` dédié par mode (1 worker par topologie), garantissant une isolation CPU complète.
*   **Mode démonisé (Uvicorn/Hypercorn)** : Repli automatique sur un `ThreadPoolExecutor` pour respecter les contraintes d'interdiction des sous-processus démons en Python.

### 5.2 OpenTripPlanner (Transit)

L'instance OTP n'intervient plus dans l'évaluation des itinéraires routiers ou piétons directs. Sa configuration est optimisée pour l'analyse des tables de correspondances :

*   **API cible** : Endpoint unique GraphQL Transmodel v3 (`/otp/transmodel/v3`).
*   **Données sources** : Couplage d'un export OpenStreetMap de la métropole de Toulouse et des fichiers GTFS des opérateurs de transports locaux Tisseo et SNCF, compilés au format immuable `graph.obj` géré par DVC.

## 6. Architecture de la mémoire et persistance des agents

L'état cognitif des agents repose sur une architecture de mémoire à trois niveaux :

```text
[Événements de simulation et décisions]
└── Mémoire à Court Terme (Python RAM - Isolation par activity_id)
    └── Vidage périodique (Toutes les 6h de temps simulé)
        └── Inférence de synthèse LLM
            └── Écriture en Mémoire à Long Terme (ChromaDB - Base vectorielle locale)
                └── Index partagé / Partitionnement logique par person_id

[Cache Sémantique LLM (LlmSemanticCache — disque local)]
└── Lookup : similarité cosinus sur le vecteur (options + historique + purpose)
    ├── Score ≥ semantic_threshold → Retourne l'index sans appel LLM
    └── Score < threshold → Appel LLM puis store asynchrone dans le cache
```

Le cache sémantique LLM est distinct de la mémoire long terme : il évite les appels LLM redondants pour des situations de mobilité similaires (mêmes options, même contexte) sans chercher à reproduire un raisonnement narratif. Il est activé via `cache.enabled` dans la configuration et stocké dans `data/llm_cache/<population_name>/`.

### Algorithme de récupération mémorielle (ChromaDB)

Lors de l'évaluation d'un itinéraire, les souvenirs pertinents sont extraits de ChromaDB via l'application d'une fonction de score composite normalisée :

$$\text{Score} = (\text{Similarité Cosinus} \times 0.4) + (\text{Score BLEU des mots-clés} \times 0.3) + (\text{Décroissance Temporelle} \times 0.3)$$

## 7. Métriques et observabilité du système

Le système expose trois terminaux de collecte Prometheus synchronisés à une fréquence de scrutation de 5 secondes.

### Indicateurs clés du Controller (`:8002/metrics`)

*   `controller_scheduling_in_progress` : Nombre d'agents en cours de traitement actif par les moteurs de calcul ou les LLM (indicateur de saturation).
*   `agent_scheduling_lag_seconds` : Écart temporel entre l'heure de départ théorique programmée (`scheduled_start_time`) et l'envoi effectif du plan à la simulation.
*   `gama_sim_step_interval_seconds` : Temps d'exécution physique entre deux pas de simulation successifs.

### Indicateurs clés de la Passerelle LLM (`:8000/metrics`)

*   `llm_provider_calls_ok_err_total` : Ratio requêtes réussies/échouées par fournisseur (détection de pannes d'API).
*   `llm_chosen_index_total` : Index de l'itinéraire sélectionné dans la liste fournie (surveillance du biais de positionnement du modèle).
*   `llm_mode_by_distance_total` : Distribution des choix de modes de transport croisés avec la distance des trajets.

### Structure des répertoires d'expérience

Chaque run crée un répertoire horodaté sous `experiments/archive/<YYYY-MM-DD>_<HH_MM>/`. Le lien symbolique `experiments/current` pointe vers `archive/<nom>` pour un accès rapide au dernier run. GAMA écrit ses résultats dans le symlink `GAMA/CityTransport/results` → `../../experiments/archive/<nom>/gama_results`.

### Journaux d'analyse (fichiers CSV exportés dans `gama_results/`)

*   `move_log.csv` : Registre centralisé des décisions (mode choisi, raisons textuelles de l'agent, retards induits, colonnes météo : température, condition, précipitations mm).
*   `gama_arrivals.csv` : Analyse de dérive temporelle entre le temps de trajet théorique calculé et le temps physique mesuré dans l'environnement GAML.