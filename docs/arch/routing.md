# Architecture du routage

Deux moteurs de calcul d'itinéraires coexistent avec des rôles strictement séparés.

---

## Vue d'ensemble

| Moteur | Modes | Technologie | Instances actives |
|--------|-------|-------------|-------------------|
| OTP | Transit (bus, tram, métro, TER) | GraphQL Transmodel v3 | 3 (`otp1/2/3`, ports 8080-8082) |
| OSMnx | Marche, vélo, voiture | Dijkstra sur graphe NetworkX | 1 (`osmnx1`, port 8090) |

Les deux moteurs sont interrogés **en parallèle** pour chaque agent, puis leurs résultats sont consolidés et dédupliqués avant la phase de décision LLM.

---

## OpenTripPlanner (transit)

OTP est dédié exclusivement aux transports en commun en mode horaire contraint.

### Logique `arrive_by`

Pour garantir que l'agent arrive à l'heure à son activité, le système utilise une inversion temporelle :

1. Calcul du `target_arrival_time` = heure de début de l'activité cible
2. Si `target_arrival_time` < timestamp simulation actuel → planification pour le lendemain (`+ 86400s`)
3. Requête OTP avec `arriveBy=True`

### API

- Endpoint unique : `/otp/transmodel/v3` (GraphQL)
- Données sources : OSM Toulouse (`.pbf`) + GTFS Tisséo + GTFS TER, compilés en `graph.obj`
- Le `graph.obj` est chargé en mémoire au démarrage (6 Go RAM par instance)

### Load balancing

Les trois instances OTP (`otp1`, `otp2`, `otp3`) reçoivent les requêtes via la variable :

```
OTP_ENDPOINTS=http://otp1:8080/otp/transmodel/v3,http://otp2:8080/otp/transmodel/v3,http://otp3:8080/otp/transmodel/v3
```

La concurrence OTP est bornée côté controller : `otp_max_concurrent: 30`.

---

## Cluster OSMnx (modes directs)

Chaque instance OSMnx charge trois graphes topologiques en RAM au démarrage (4 Go par instance).

### Modes et coupures

| Mode | Vitesse | Coupure spatiale | Modèle de congestion |
|------|---------|-----------------|----------------------|
| Marche (`walk`) | Fixe (config) | 15 km | Non |
| Vélo (`bike`) | Paramétrable | 30 km | Non |
| Voiture (`drive`) | Dynamique | Aucune | Profils horaires TomTom Toulouse |

Les requêtes au-delà des coupures spatiales sont rejetées sans calcul Dijkstra.

### Calcul `arrive_by` (modes directs)

Les itinéraires OSMnx ne supportent pas nativement `arriveBy`. Le système calcule le trajet à vitesse nominale, puis décale le résultat en arrière dans le temps pour aligner l'heure de fin sur `target_arrival_time`.

### Gestion du multi-processing

Le GIL Python bloque l'exécution parallèle des algorithmes Dijkstra dans le même processus. L'architecture s'adapte selon l'environnement :

| Contexte | Executor | Raison |
|----------|----------|--------|
| Conteneur Docker standard | `ProcessPoolExecutor` (1 worker/mode) | Isolation CPU complète |
| Processus démonisé (Uvicorn/Hypercorn) | `ThreadPoolExecutor` | Interdit de forker depuis un démon Python |

### Déploiement

En production, une seule instance (`osmnx1`) est active par défaut. Des replicas supplémentaires peuvent être décommentés dans `docker-compose.yml` :

```yaml
# osmnx2:
#   <<: *osmnx-service
#   ports:
#     - "8091:8090"
```

Le controller les répartit en round-robin via `OSMNX_ENDPOINTS`.

---

## Consolidation des résultats

Après les appels OTP et OSMnx (parallèles), le controller :
1. Unifie les timestamps en millisecondes
2. Déduplique les itinéraires identiques
3. Mélange aléatoirement l'ordre de présentation au LLM (anti-biais de position)
4. Transmet la liste au module de décision LLM
