# LLM Unified Communication Module

Architecture asynchrone multi-fournisseur LLM avec load balancing RPM.

## Structure

```
llm_module/
├── main.py                        # API Gateway FastAPI (POST /tasks, GET /tasks/{id})
├── config.py                      # Configuration centralisée (pydantic-settings + .env)
├── models.py                      # Modèles Pydantic partagés
│
├── broker/
│   └── redis_broker.py            # Connexion Redis, CRUD tâches, compteurs RPM
│
├── worker/
│   └── task_worker.py             # Worker Celery + retry backoff exponentiel
│
├── load_balancer/
│   └── router.py                  # Weighted Round-Robin + Circuit Breaker
│
├── adapters/
│   ├── base.py                    # Interface commune (Adapter Pattern) + registre
│   ├── openai_adapter.py          # Traducteur OpenAI (Structured Output natif)
│   ├── mistral_adapter.py         # Traducteur Mistral (json_object + schema en system)
│   └── google_adapter.py          # Traducteur Google Gemini (format contents/parts)
│
├── prompts/
│   ├── manager.py                 # Moteur Jinja2, split system/user, schéma JSON
│   └── templates/
│       └── default.md.j2          # Template générique (agents + paramètres libres)
│
├── telemetry/
│   └── logger.py                  # Logging structuré (structlog, JSON en prod)
│
├── requirements.txt
└── .env.example
```

## Démarrage rapide

```bash
# 1. Dépendances
pip install -r requirements.txt

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

### Ajouter un nouveau fournisseur LLM

1. Créer `adapters/mon_provider_adapter.py` avec `@register_adapter`
2. Implémenter `call()` selon le format de l'API cible
3. Ajouter la config dans `.env` et `config.py`

Le LoadBalancer et le Worker le prendront en compte automatiquement.
