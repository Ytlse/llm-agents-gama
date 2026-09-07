# llm-gateway

Gateway asynchrone multi-fournisseur pour appels LLM structurés. Un client soumet un lot
d'items par **catégorie** (`POST /tasks`), le gateway regroupe les lots compatibles en un
seul prompt (micro-batching), choisit un fournisseur selon ses quotas (SWRR, réservation
RPM/TPM atomique dans Redis), appelle le modèle, valide la réponse JSON contre le schéma de
la catégorie et redistribue chaque résultat à son `agent_id`. Le gateway **ne contient aucun
prompt** : templates, schémas et règles métier sont apportés par des *bundles* installés à
côté de lui.

Version : `llm_gateway.__version__` = 1.1.0 · Python ≥ 3.12 · licence : non encore choisie
(question ouverte du ticket 037).

## Les trois paquets frères

| Paquet | Rôle | Dépend de |
|---|---|---|
| `llm_gateway` (ce dossier) | API FastAPI, worker Celery, adapters de fournisseurs, balancer, moteur Jinja2 sans contenu, télémétrie, SDK | rien du dépôt |
| `mobility_core` | domaine de l'enquête EMC² Toulouse : couronnes, zones fines, hiérarchie des modes, vélo, logement, cadrage de population | rien du dépôt |
| `mobility_llm` | les quatre catégories LLM de la simulation de mobilité : persona, templates, schémas, variantes de prompt, choix modal, métriques métier ; s'enregistre auprès du gateway par entry point | les deux autres |

La règle est vérifiée par import-linter (`.importlinter` à la racine, 5 contrats) :
`llm_gateway` n'importe ni `mobility_core`, ni `mobility_llm`, ni l'ancienne coquille
`llm_module` ; `llm_gateway.core` et `llm_gateway.ports` n'importent aucune infra.

## Installation

Depuis la racine du dépôt, en editable :

```bash
pip install -e ./mobility_core -e ./llm_gateway[test] -e ./mobility_llm
```

Extras du gateway : `test` (pytest, fakeredis[lua], hypothesis), `dev` (ruff, mypy,
import-linter, pre-commit), `docs` (mkdocs-material, mkdocstrings), `monitoring` (flower).

Image Docker (contexte = racine du dépôt, les trois paquets embarqués, utilisateur non-root) :

```bash
docker build -f llm_gateway/Dockerfile .
```

## Démarrage rapide

```bash
docker run -d -p 6379:6379 redis:7-alpine        # 1. Redis
cp llm_gateway/.env.example .env                  # 2. clés : PROVIDER_KEYS__<nom>=...
llm-gateway config validate                       #    → « OK — N provider(s) avec clé »
llm-gateway categories                            # 3. catégories apportées par les bundles
llm-gateway serve --port 8000                     # 4. API (uvicorn)
llm-gateway worker --concurrency 25 --pool threads   # 5. worker Celery, autre terminal
```

Équivalents utilisés par `docker-compose.yml` (services `api` et `worker`) :
`uvicorn llm_gateway.main:app --host 0.0.0.0 --port 8000` et
`celery -A llm_gateway.worker.task_worker.celery_app worker --loglevel=info --concurrency=25 -P threads`.

`GET /health` liste l'état RPM de chaque provider ; `GET /metrics` expose Prometheus.

## Les catégories viennent des bundles

Le gateway découvre ses catégories par l'entry point `llm_gateway.categories`. Un bundle
est un `CategoryBundle` (répertoire de templates `<catégorie>.md.j2`, fichier
`schemas.json`, `prompts.yaml` facultatif) qui déclare des `CategorySpec` (modèle d'item,
fonction de priorité, hook d'observation des métriques). Le registre valide chaque
catégorie **au démarrage** : template ou schéma manquant → `ValueError` avant la première
requête.

Sans bundle installé, `llm-gateway categories` rend le code 1 et **toute requête est
refusée en 422** (« Catégorie inconnue … Catégories enregistrées : [] »). Le paquet
`mobility_llm` apporte `itinary_multi_agent`, `perception_filter`, `stm_reflection` et
`ltm_self_reflection`. Pour écrire le vôtre : `docs/guides/ajouter-une-categorie.md`.

## SDK Python

```python
import asyncio
from llm_gateway import LLMGatewayClient, LLMRequest

async def main() -> None:
    client = LLMGatewayClient("http://localhost:8000", wait_timeout=90.0, dialogue_log_file=None)
    result = await client.execute(LLMRequest(
        category="perception_filter",
        agents=[{"agent_id": "ag_1", "perception": "34 ans, cadre, sans voiture, abonnée TC."}],
    ))
    if result.ok:
        print(result.provider_used, result.agents[0].summary, result.timing.wait_ms)
    else:
        print(result.status, result.error)
    await client.aclose()

asyncio.run(main())
```

`execute` ne lève pas sur un échec de tâche (`TaskResult.status`/`error` le portent) ; il
lève `httpx.HTTPStatusError` si le gateway refuse la soumission (4xx). Le disjoncteur du
client suspend les soumissions après 10 échecs consécutifs et re-sonde toutes les 60 s —
détails dans `docs/reference/sdk-python.md`.

## Arborescence

```
llm_gateway/
├── pyproject.toml            # version dynamique (llm_gateway.__version__), extras, pytest, coverage ≥ 80 %
├── Dockerfile                # image api/worker/flower — contexte : racine du dépôt
├── mkdocs.yml, docs/         # site de documentation (mkdocs-material, français)
├── tests/                    # unit / contract / integration / e2e (marqueurs par dossier)
└── src/llm_gateway/
    ├── __init__.py           # façade paresseuse : LLMGatewayClient, LLMRequest, CategoryBundle…
    ├── cli.py                # llm-gateway serve | worker | config validate|show | categories
    ├── main.py               # app = create_app() pour uvicorn
    ├── core/                 # domaine pur : models, batching (clé de lot), selection (SWRR)
    ├── ports/                # Protocol : TaskStore, BatchQueue, RateLimiter, MetricsSink, LLMAdapter, category
    ├── infra/redis/, infra/memory/   # implémentations des ports (Lua Redis / pur Python)
    ├── adapters/             # openai, mistral, google, groq, cerebras — @register_adapter
    ├── balancer/router.py    # LoadBalancer : séquence SWRR + réservation via RateLimiter
    ├── prompts/              # engine (Jinja2 sans contenu), registry (bundles validés au démarrage)
    ├── api/                  # create_app, routes, deps (build_deps), metrics (collecteur Redis)
    ├── worker/               # create_celery_app, runtime (build_worker_runtime), task_worker
    ├── sdk/client.py         # LLMGatewayClient, TaskResult, TaskTiming
    ├── telemetry/            # logger (loguru, journaux JSONL), alarms (fire_alarme)
    ├── testing/              # echo_bundle, build_registry, FakeAdapter, ports mémoire
    └── config/               # settings.py (pydantic-settings), providers.yaml
```

## Documentation

Site mkdocs (Diátaxis : tutoriel, guides, référence, explications, ADR) :

```bash
pip install -e ./llm_gateway[docs]
cd llm_gateway && mkdocs serve      # http://127.0.0.1:8000 ; `mkdocs build --strict` en CI
```

Tests : `make test-gateway` (depuis la racine) ou `cd llm_gateway && pytest -m "not e2e"`.
Historique des changements : `CHANGELOG.md`.
