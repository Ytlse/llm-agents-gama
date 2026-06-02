# Librairies Python clés du projet

Vue d'ensemble des librairies externes ayant un rôle fonctionnel important, organisées par thème.

---

## Serveurs Web & API

**FastAPI** — Sert l'API principale du module LLM. Chaque agent de la simulation envoie ses requêtes ici pour obtenir une réponse du modèle de langage.

**Hypercorn** — Serveur web avec support HTTP/2. Nécessaire car le client Java (GAMA) utilise ce protocole pour communiquer avec Python.

**Flask** — Sert uniquement le serveur de visualisation cartographique (affichage des agents sur la carte via OSMnx).

---

## Validation & Configuration

**Pydantic** — Valide la structure de toutes les données qui transitent dans le système : messages entre agents, configuration des modèles LLM, résultats de simulation. Évite les erreurs silencieuses dues à des données mal formées.

**pydantic-settings** — Charge la configuration depuis les variables d'environnement et les fichiers YAML des expériences.

---

## Intelligence Artificielle & LLM

**OpenAI (client)** — Envoie les requêtes aux modèles GPT ou à tout serveur compatible (vLLM, Groq…). C'est la lib qui "parle" aux LLM.

**LlamaIndex** — Orchestre le pipeline IA : gestion du contexte, mémoire des agents, récupération d'information (RAG). C'est la colonne vertébrale du module LLM.

**sentence-transformers** — Transforme une phrase en vecteur numérique (embedding). Utilisé pour le cache sémantique : détecter si deux questions posées par des agents sont suffisamment proches pour réutiliser la même réponse.

---

## Cache Sémantique & Mémoire Vectorielle

Le projet utilise plusieurs systèmes de stockage vectoriel selon le cas d'usage :

**FAISS** — Bibliothèque Meta de recherche de similarité vectorielle ultra-rapide, utilisée en mémoire vive pour le cache à court terme.

**Qdrant** — Base de données vectorielle avec persistance disque, utilisée pour le cache sémantique LLM (retrouver une réponse déjà calculée à une question similaire).

**ChromaDB** (via LlamaIndex) — Base vectorielle utilisée pour la mémoire long-terme des agents (ce qu'ils ont appris au fil de la simulation).

**SQLite** (stdlib Python) — Stockage local des résultats de calcul d'itinéraires (OTP et OSMnx) pour éviter de recalculer les mêmes trajets.

---

## Traitement Asynchrone

**Celery** — Gère une file d'attente de tâches distribuées. Permet aux agents de soumettre des requêtes LLM sans bloquer la simulation en attendant la réponse.

**Redis** — Sert de broker pour Celery (transit des messages) et stocke les résultats des tâches.

**asyncio-mqtt** — Communication temps-réel entre les agents et l'infrastructure simulée via le protocole MQTT.

---

## Géospatial & Transport

**GeoPandas** — Manipule des données géographiques (fichiers de carte, zones, arrêts de bus…). Permet de faire des calculs spatiaux comme "quels agents sont dans ce quartier".

**OSMnx** — Télécharge le réseau routier depuis OpenStreetMap et calcule des itinéraires à pied ou en voiture directement en Python.

**gtfs-kit** — Lit et valide les données des transports en commun au format GTFS (horaires de bus, métro, TER…).

---

## Données & Calcul

**Pandas** — Manipule les données tabulaires : population des agents, horaires, résultats de simulation.

**SciPy** — Calculs statistiques sur les données de mobilité (distributions, corrélations).

---

## Génération de Population Synthétique (`eqasim-toulouse`)

Ces librairies servent exclusivement à générer la population d'agents à partir de données INSEE et d'enquêtes de mobilité réelles.

**synpp** — Framework pipeline qui orchestre les étapes de génération de population.

**bhepop2** — Génère une population synthétique représentative à partir des données INSEE françaises.

**mobisurvstd** — Standardise les données d'enquêtes de mobilité (EMD, EMP) pour les rendre utilisables.

**scikit-learn** — Algorithmes de machine learning pour combler les données manquantes dans la population (imputation).

**polars** — Alternative à Pandas, beaucoup plus rapide sur les gros fichiers de population.

**numba** — Compile certains calculs Python à la volée pour les accélérer (similaire à du code C).

**osmium** — Lit les fichiers cartographiques OSM binaires (`.pbf`) pour extraire le réseau routier.

---

## Observabilité

**prometheus-client** — Expose des métriques (latence des LLM, taux de cache, nombre d'appels par agent) lisibles par Grafana.

**Loguru** — Gestion des logs avec rotation automatique des fichiers et filtrage par niveau.

---

## Robustesse & HTTP

**httpx** — Client HTTP moderne utilisé par les adaptateurs LLM pour appeler les APIs.

**tenacity** — Réessaie automatiquement un appel LLM en cas d'échec, avec délai croissant entre les tentatives.

**Jinja2** — Moteur de templates pour construire les prompts envoyés aux LLM de façon dynamique.

**demjson3** — Parse du JSON mal formé, utile quand un LLM renvoie une réponse JSON incomplète ou avec des erreurs de syntaxe.
