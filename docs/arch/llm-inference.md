# Architecture LLM — Inférence et load balancing

Le module LLM (`llm_module/`) fait office de répartiteur de charge haute performance pour les appels vers les API LLM externes. Il découple le controller des fournisseurs et absorbe les variations de débit.

---

## Vue d'ensemble

```
Controller  →  POST /tasks  →  Redis Sorted Set  →  Worker Celery  →  Provider LLM
                                (batch:{key})          (SWRR)
```

Les composants Docker impliqués :
- `api` (port 8000) : réception des tâches, démultiplexage des résultats
- `worker` : exécution Celery des appels LLM (concurrence : 8)
- `redis` DB1 : broker Celery ; DB2 : backend de résultats

---

## Pipeline de batching

### File d'attente (Redis Sorted Set)

Les tâches soumises via `POST /tasks` sont insérées dans un **Sorted Set Redis** (clé `batch:{batch_key}`) trié par `priority_score = min(departure_time)` des agents. Les agents dont le départ est imminent remontent en tête de file.

La clé de hachage est : `MD5(Catégorie + Paramètres + Fournisseur_Forcé)` — les agents avec le même contexte de décision sont regroupés dans le même batch.

```text
[POST /tasks reçu]
└── Calcul priority_score = min(departure_time)
    └── Insertion dans Sorted Set batch:{batch_key}
        ├── Si taille = 1 → armement d'un compte à rebours Celery (1s)
        └── Si taille ≥ batch_limit → déclenchement immédiat
```

`batch_max_agents` est calculé au démarrage : `max(1, min(tpm_limit / tokens_per_agent, rpm_limit, max_batch_agents))`

### Exécution Worker

```text
[Worker Celery déclenché]
└── Sélection provider via SWRR
    ├── Circuit Breaker : provider désactivé ?
    ├── Vérification quota RPM (script Lua atomique)
    └── Réservation du slot
└── ZPOPMIN jusqu'à batch_max_agents tâches
└── Rendu prompt unifié via Jinja2 (schéma JSON injecté)
└── Appel HTTP vers l'API du provider
└── Démultiplexage par agent_id → DB2 Redis + Pub/Sub
```

---

## Load balancing SWRR

L'algorithme **Smooth Weighted Round Robin** distribue les requêtes entre providers actifs proportionnellement à leur `weight`. Un provider avec `weight: 2.0` reçoit deux fois plus de requêtes qu'un provider à `weight: 1.0`.

À chaque sélection :
1. Vérification du Circuit Breaker (provider exclu ?)
2. Vérification des quotas RPM via script Lua atomique (compare `now` au compteur glissant Redis)
3. Réservation atomique du slot de concurrence

Si aucun provider n'est disponible, le worker attend en polling jusqu'à 60s avant d'échouer.

---

## Gestion des pannes — Circuit Breaker

| Événement | Comportement |
|-----------|-------------|
| Erreur réseau / HTTP 5xx | `mark_cooldown` 60s + retry exponentiel (1s→30s, max 10 essais) |
| HTTP 429 (rate limit) | Cooldown calé sur `x-ratelimit-reset-requests` (formats Groq `"Xm Y.Zs"` et OpenAI ISO 8601) ; fallback 60s |
| > 30 échecs consécutifs | Exclusion totale du routage SWRR pendant 120-180s glissantes |

Les tâches en échec sont réinsérées dans le Sorted Set avec leur score d'origine.

L'événement `ratelimit_reset` est tracé dans `llm_errors.jsonl`.

---

## Polling côté controller

Après soumission, le controller attend le résultat via long-poll Pub/Sub Redis (canal `task_done:{task_id}`). Si la socket pubsub est interrompue (`redis.exceptions.TimeoutError`) avant la fin du timeout, le serveur se reconnecte automatiquement et reprend l'attente jusqu'à épuisement du budget de temps — évitant les faux-timeouts (`waited=Xs timeout=90s`) lorsque la socket Redis se déconnecte brièvement. Les métriques de timing sont tracées dans le pipeline de mesure (voir [docs/pipeline.md](../../pipeline.md)).

---

## Configuration

```yaml
# dans le fichier de config d'expérience
llm:
  provider: groq_llama4        # force un provider (sinon SWRR automatique)
  model: meta-llama/llama-4-scout-17b-16e-instruct
```

Voir [docs/setup/llm-providers.md](../setup/llm-providers.md) pour la liste complète des providers et leur paramétrage.
