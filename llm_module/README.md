# LLM Unified Communication Module

LLM multi-provider : il expose une API FastAPI qui reçoit des requêtes batch d'agents, les distribue via un load balancer Weighted Round-Robin avec circuit breaker vers OpenAI/Mistral/Google/Groq, et retourne des réponses structurées JSON pour piloter les comportements de mobilité des agents. Le traitement asynchrone repose sur Celery+Redis : micro-batching des requêtes, retry exponentiel sur les 5xx, démultiplexage des résultats par agent. Les prompts sont assemblés par un moteur Jinja2 avec schémas JSON par catégorie, puis validés via Pydantic avant persistance.

**Fonctionnalités clés :**
- 🚀 **Micro-batching automatique** : Les requêtes ayant les mêmes paramètres sont regroupées (jusqu'à 20 agents) pour optimiser les appels LLM et éviter les limites de taux (rate-limits).
- ⚖️ **Load Balancer WRR** : Répartition de charge pondérée (Weighted Round-Robin) basée sur les quotas (RPM) de chaque fournisseur.
- 🔌 **Circuit Breaker & Cooldowns** : Exclusion temporaire (60s) des fournisseurs saturés (Erreurs 429 ou 5xx) et bascule automatique sur le fournisseur disponible suivant.
- 🔄 **Retry avec Backoff Exponentiel** : Gestion robuste des pannes réseau via Celery.
- 📝 **Moteur de Prompts Jinja2** : Séparation claire entre la logique Python et le texte des prompts (`.md.j2`), avec validation stricte de la sortie via des JSON Schemas configurables (`schemas.json`).
- 📊 **Télémétrie structurée** : Logs au format JSON (structlog) avec rotation des fichiers, extraction précise de la latence et du coût en tokens.

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
│   ├── manager.py                 # Moteur Jinja2, split system/user
│   ├── schemas.json               # Définition des schémas de sortie (Structured Output)
│   └── templates/
│       ├── itinary_multi_agent.md.j2  # Choix modal avec justifications
│       └── perception_filter.md.j2    # Génération d'histoires à la première personne
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
