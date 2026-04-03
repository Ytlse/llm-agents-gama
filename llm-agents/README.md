# llm-agents

Projet de simulation multi-agents urbaine combinant un backend de simulation GAMA, des agents cognitifs pilotés par LLM, et un serveur API asynchrone. L'objectif est de modéliser des comportements de mobilité urbaine à partir de populations synthétiques, de données GTFS et de scénarios de déplacement.

---

## Arborescence générale

```
llm-agents/
├── api_server.py
├── backup_helper.py
├── errors.py
├── gama_models.py
├── helper.py
├── models.py
├── server.py
├── settings.py
├── utils.py
├── api/
├── config/
├── handle/
├── input/
│   ├── experiments/
│   └── gtfs/
├── llm/
├── scenario/
│   └── scenario_v1/
├── text_helper/
│   ├── models/
│   └── templates/
├── trip_helper/
└── world/
```

---

## Fichiers racine

| Fichier | Description |
|---|---|
| `api_server.py` | Initialisation du serveur API. Point d'entrée secondaire ou utilitaire de démarrage. |
| `backup_helper.py` | Mécanisme de roulement de fichiers (log rotation ou backup). Rôle précis à clarifier. **TBD** |
| `errors.py` | Définition centralisée des exceptions custom utilisées dans le projet. |
| `gama_models.py` | Classes de liaison avec GAMA : réponses, limites, synchronisation, objets d'échange avec le moteur de simulation. |
| `helper.py` | Fonctions utilitaires générales difficiles à classer ailleurs : conversions temporelles (ex. tranche horaire → label "matin"), conversion de dates, utilitaires de sentiment, etc. |
| `models.py` | Classes du domaine métier reflétant le modèle GAML : personnes, transitions, états. Miroir Python du modèle GAMA. |
| `server.py` | Point d'entrée principal. Contient la classe `main`, charge la configuration et les settings, lance le serveur via `uvicorn.run`. |
| `settings.py` | Configurations globales du projet : modèles LLM, serveur, paramètres d'environnement. Regroupe l'ensemble des classes de configuration (pattern Settings). |
| `utils.py` | Utilitaires divers : génération aléatoire, calculs de distance, fonctions mathématiques d'appoint. |

---

## `api/`

Couche API asynchrone gérant les échanges entre le serveur et la simulation GAMA.

| Fichier | Description |
|---|---|
| `application.py` | Déclare les objets FastAPI et le logger de chargement de simulation. Fichier court, rôle de bootstrap de l'application. |
| `batch.py` | Fonctions asynchrones de gestion des déplacements en batch : `query_move` (demande de déplacement pour un agent, avec sémaphore), `batch_move_next` (création asynchrone des tâches de déplacement), `batch_ob_update` (mise à jour des observations — **non encore implémentée, TBD**). |
| `handles.py` | Gestion de l'initialisation de l'environnement simulé. La fonction `init` envoie un message `world_init` à GAMA avec la liste des personnes, le nombre d'agents et la date de départ. |

---

## `config/`

Contient les fichiers YAML de configuration des expériences (baseline et variantes testées). Ces fichiers sont probablement sélectionnés ou copiés dynamiquement selon le scénario lancé.

---

## `handle/`

Couche d'interface bas niveau avec GAMA et WebSocket.

| Fichier | Description |
|---|---|
| `application.py` | Interface principale avec GAMA. Boucle d'écoute des nouveaux messages entrants, traitement des observations, initialisation de GAMA, définition des handlers FastAPI. |
| `websocket.py` | Gestion de la connexion WebSocket avec GAMA : `connect`, `disconnect`, `send_message`, `listen`. Rôle précis dans l'architecture à approfondir. **TBC** |

---

## `input/`

Données d'entrée de la simulation.

### `experiments/`
Configuration courante de l'expérience en cours (probablement copiée automatiquement depuis `config/` au lancement).

### `gtfs/`

| Fichier | Description |
|---|---|
| `gamma.py` | Constructeurs GAMA pour les objets GTFS : chargement des trips, déclaration des classes `TripInfo`, alimentation du modèle GAMA à partir des données de transport. |
| `reader.py` | Lecture et parsing du zip GTFS. Initialise les routes, stops et informations horaires. Crée les objets Python correspondants pour injection dans GAMA. |

### `population/`

| Fichier | Description |
|---|---|
| `base.py` | Classe de base abstraite pour la gestion de la population simulée. |
| `spatial_filter.py` | Filtre la population selon une proximité spatiale aux arrêts de transport (rayon configurable). |
| `synthetic.py` | Chargement d'une population synthétique à partir de fichiers externes. |

---

## `llm/`

Couche d'intégration LLM et gestion de la mémoire des agents.

| Fichier | Description |
|---|---|
| `llm_model.py` | Constructeurs d'interfaces LLM pour différents providers (OpenAI, vLLM, HuggingFace, etc.). Initialisation des clients selon le provider configuré. |
| `longterm.py` | Mémoire long terme des agents : logique de stockage, récupération, consolidation. Module riche, à documenter en détail. **TBC** |
| `memory.py` | Définition de la classe `MemoryEntry` : entrée de mémoire unitaire avec toutes ses métadonnées (timestamp, type, contenu, etc.). |
| `shortterm.py` | Mémoire court terme : liste ordonnée de `MemoryEntry`, gestion de la fenêtre contextuelle de l'agent. |
| `vllm_server.py` | Client pour serveur LLM compatible OpenAI (vLLM). Fournit deux fonctions d'envoi de messages : synchrone et asynchrone. |

---

## `scenario/`

### `scenario_v1/`

| Fichier | Description |
|---|---|
| `base.py` | Classe abstraite définissant le contrat d'un scénario : méthodes `find_observation`, `assign_message`, `init_population`, etc. |
| `history.py` | Journalisation des événements de simulation au format JSON. Permet de tracer l'historique complet d'une exécution. |
| `llm_config.py` | Construit les configurations LLM à la volée depuis `settings.py` selon le provider actif (OpenAI ou vLLM) : URL d'API, température, nombre max de tokens, etc. |

---

## `text_helper/`

Génération de texte narratif décrivant les déplacements des agents (feedback LLM, prompts de contexte).

### `models/`

| Fichier | Description |
|---|---|
| `arrival.py` | Décrit l'arrivée d'un agent à destination : à l'heure, en retard, feedback associé. |
| `transfer.py` | Décrit un segment de marche entre deux points. |
| `transit.py` | Décrit un segment en transport en commun : distance, durée, ligne empruntée. |
| `travel_plan.py` | Agrège les informations de l'ensemble des segments d'un déplacement : temps de marche total, distance totale, etc. |
| `wait_in_stop.py` | Décrit le temps d'attente à un arrêt. |

### `templates/`

Sous-dossier contenant des templates Jinja2 (`.j2`) pour la génération de descriptions textuelles de plans de voyage, transferts et attentes aux arrêts. À approfondir. **TBC**

| Fichier | Description |
|---|---|
| `repository.py` | Chargement et sélection des templates `.j2` selon le contexte. Logique de filtrage à clarifier. **TBD** |

---

## `trip_helper/`

Interface de planification d'itinéraires via des outils externes (OTP, Solari).

| Fichier | Description |
|---|---|
| `cached_triphelper.py` | Interface commune (facade) pour la récupération de scénarios de trajet. Délègue à l'implémentation sélectionnée (OTP ou Solari) via des méthodes de type `get_itinerary`. |
| `otp.py` | Client OTP (OpenTripPlanner) : construction des requêtes, parsing des réponses, retour des itinéraires structurés. |
| `solari.py` | Client Solari : semble être une version antérieure ou alternative à OTP, avec un endpoint différent. Probablement la V1 du planificateur. **TBC** |

---

## `world/`

Gestion de l'état global de la simulation.

| Fichier | Description |
|---|---|
| `population.py` | Classe `Population` : gestion des actions individuelles sur les agents (démarrer une activité, récupérer la suivante, terminer). Classe `WorldPopulation` : initialisation de l'environnement GAMA avec la population, statistiques globales et état courant de la simulation. |
| `world_data.py` | Données environnementales de la simulation : grille temporelle, données géospatiales, projections cartographiques. |

---

## Points à approfondir

| Élément | Nature | Priorité |
|---|---|---|
| `backup_helper.py` | Rôle exact du roulement de fichiers | **TBD** |
| `api/batch.py` → `batch_ob_update` | Feedback observations, non implémenté | **TBD** |
| `handle/websocket.py` | Positionnement dans l'architecture (GAMA WS vs client externe ?) | **TBC** |
| `llm/longterm.py` | Détail des stratégies de mémoire long terme | **TBC** |
| `text_helper/templates/repository.py` | Logique de sélection des templates | **TBD** |
| `trip_helper/solari.py` | Relation exacte avec OTP, statut actif/déprécié | **TBC** |

---

*README généré à partir d'une description vocale du projet — certaines interprétations sont approximatives et marquées TBD (à définir) ou TBC (à confirmer).*
