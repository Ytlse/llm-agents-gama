# LLM Unified Communication Module

LLM multi-provider : il expose une API FastAPI qui reçoit des requêtes batch d'agents, les distribue via un load balancer Weighted Round-Robin avec circuit breaker vers OpenAI/Mistral/Google/Groq, et retourne des réponses structurées JSON pour piloter les comportements de mobilité des agents. Le traitement asynchrone repose sur Celery+Redis : micro-batching des requêtes, retry exponentiel sur les 5xx, démultiplexage des résultats par agent. Les prompts sont assemblés par un moteur Jinja2 avec schémas JSON par catégorie, puis validés via Pydantic avant persistance.

**Fonctionnalités clés :**
- 🚀 **Micro-batching automatique** : Les requêtes ayant les mêmes paramètres sont regroupées (jusqu'à 20 agents) pour optimiser les appels LLM et éviter les limites de taux (rate-limits).
- ⚖️ **Load Balancer WRR** : Répartition de charge pondérée (Weighted Round-Robin) basée sur les quotas (RPM) de chaque fournisseur.
- 🔌 **Circuit Breaker & Cooldowns** : Exclusion temporaire (60s) des fournisseurs saturés (Erreurs 429 ou 5xx) et bascule automatique sur le fournisseur disponible suivant.
- 🔄 **Retry avec Backoff Exponentiel** : Gestion robuste des pannes réseau via Celery.
- 📝 **Moteur de Prompts Jinja2** : Séparation claire entre la logique Python et le texte des prompts (`.md.j2`), avec validation stricte de la sortie via des JSON Schemas configurables (`schemas.json`).
- 📊 **Télémétrie structurée** : Logs au format JSON (structlog) avec rotation des fichiers, extraction précise de la latence et du coût en tokens.

## Structure (architecture ports & adapters)

Règle de dépendance (vérifiée par import-linter, cf. `pyproject.toml`) :
`api / worker → core + ports` ; `infra → ports + core` ; **`core` n'importe rien du reste**.

```
llm_module/
├── pyproject.toml                 # Package installable (pip install .) — deps runtime minimales
├── config.py                      # Settings pydantic — construits explicitement (get_settings())
├── main.py                        # Point d'entrée uvicorn : app = create_app()
├── sdk.py                         # SDK client typé (LLMGatewayClient → TaskResult)
│
├── core/                          # Domaine pur — AUCUN I/O, aucun import redis/celery/httpx
│   ├── models.py                  # Task, LLMRequest, AgentSpec, AgentResponse…
│   ├── batching.py                # Clé de batch, score de priorité
│   ├── selection.py               # Algorithme SWRR pur (séquence pondérée)
│   ├── mode_choice.py             # Probabilités LLM → mode tiré (politique partagée)
│   └── zone_resolver.py           # Point → zone fine EMC² et variables géo du choix modal
│                                  # I/O confiné à ZoneResolver.load() ; extra 'geo' (geopandas)
│
├── data/                          # Ressources de données — hors dépôt, cf. .gitignore
│   └── zf_zones.gpkg              # Couche des 785 zones fines, produite par `make zones`
│
├── ports/                         # Les interfaces (Protocol) — le contrat du module
│   ├── task_store.py              # TaskStore / SyncTaskStore
│   ├── rate_limiter.py            # RateLimiter (RPM, circuit breaker, concurrence)
│   ├── batch_queue.py             # BatchQueue (micro-batching)
│   ├── metrics.py                 # MetricsSink (compteurs worker)
│   └── llm_adapter.py             # LLMAdapter (call/close)
│
├── infra/
│   ├── redis/                     # RedisTaskStore, RedisRateLimiter (Lua), RedisBatchQueue,
│   │                              # RedisMetricsSink (hash wmetrics, 1 HGETALL/scrape)
│   └── memory/                    # InMemory* — tests unitaires sans Redis
│
├── api/                           # FastAPI — couche transport uniquement
│   ├── app.py                     # create_app(config) : composition + lifespan (reset RPM ICI)
│   ├── routes.py                  # POST /tasks, GET /tasks/{id}[/wait], /health, /metrics
│   ├── deps.py                    # GatewayDeps + build_deps()
│   └── metrics.py                 # Collecteur Prometheus des compteurs worker
│
├── worker/
│   ├── app.py                     # create_celery_app(config)
│   ├── runtime.py                 # WorkerRuntime (composition sync)
│   └── task_worker.py             # process_batch_task + retry backoff exponentiel
│
├── load_balancer/
│   └── router.py                  # LoadBalancer(providers, limiter) — sans effet de bord
│
├── adapters/
│   ├── base.py                    # BaseAdapter + registre + cache d'instances (httpx partagé)
│   ├── openai_adapter.py          # Traducteur OpenAI (Structured Output natif)
│   ├── mistral_adapter.py         # Traducteur Mistral (json_object + schema en system)
│   ├── google_adapter.py          # Traducteur Google Gemini (clé en header x-goog-api-key)
│   ├── groq_adapter.py            # Traducteur Groq (compatible OpenAI)
│   └── cerebras_adapter.py        # Traducteur Cerebras
│
├── prompts/
│   ├── manager.py                 # Moteur Jinja2, split system/user (singleton paresseux)
│   ├── prompts.yaml               # Source unique des prompts système (active/prompts)
│   ├── schemas.json               # Définition des schémas de sortie (Structured Output)
│   └── templates/*.md.j2
│
├── telemetry/
│   └── logger.py                  # loguru — configure_logging() explicite
│
└── settings/, tasks/              # Shims de compatibilité (notebooks) → core.models / config
```

## Démarrage rapide

```bash
# 1. Dépendances (package installable)
pip install .            # ou : pip install -r requirements.txt

# 2. Configuration
cp .env.example .env
# → renseigner les clés API dans .env

# 3. Redis (Docker)
docker run -d -p 6379:6379 redis:7-alpine

# 4. Lancer l'API Gateway
uvicorn llm_module.main:app --reload --port 8000

# 5. Lancer le Worker Celery (dans un terminal séparé)
celery -A llm_module.worker.task_worker.celery_app worker --loglevel=info

# 6. (Optionnel) Monitoring Celery avec Flower
pip install flower
celery -A llm_module.worker.task_worker.celery_app flower --port=5555
```

## Utilisation

### Créer une tâche

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "category": "default",
    "agents": [
      {"agent_id": "ag_01", "role": "navetteur quotidien", "context": "vit à 15km du centre"},
      {"agent_id": "ag_02", "role": "étudiant", "context": "sans voiture"}
    ],
    "parameters": {
      "scenario": "choix modal matin",
      "time_of_day": "08h00",
      "weather": "pluie légère"
    }
  }'
```

Réponse immédiate :
```json
{"task_id": "uuid-...", "status": "pending", "message": "..."}
```

### Récupérer le résultat (polling)

```bash
curl http://localhost:8000/tasks/{task_id}
```

Réponse quand terminé :
```json
{
  "task_id": "...",
  "status": "success",
  "result": [
    {"agent_id": "ag_01", "reponse": "Prend la voiture malgré la pluie..."},
    {"agent_id": "ag_02", "reponse": "Opte pour le tramway..."}
  ],
  "provider_used": "mistral",
  "latency_ms": 1243.5
}
```

### SDK typé (consommateurs Python : controller GAMA, notebooks)

```python
from llm_module.sdk import LLMGatewayClient

client = LLMGatewayClient(base_url="http://localhost:8000", wait_timeout=90.0)
result = await client.execute(payload)      # dict ou LLMRequest → TaskResult
if result.ok:
    # itinary_multi_agent : une probabilité par option (somme = 100) — le mode est
    # ensuite tiré via llm_module.core.mode_choice.draw_index()
    print(result.agents[0].probabilities, result.provider_used, result.timing.wait_ms)
await client.aclose()
```

### Ajouter un nouveau fournisseur LLM

1. Créer `adapters/mon_provider_adapter.py` avec `@register_adapter`
2. Implémenter `call()` selon le format de l'API cible
3. Ajouter la config dans `config/providers.yaml` et la clé API dans `.env`

Le LoadBalancer et le Worker le prendront en compte automatiquement.
