# CR — Restructuration de `llm_module` en package

**Date** : 2026-07-07
**Statut** : ✅ implémenté le 2026-07-07 (phases 0 à 5, cf. §5 pour les écarts au plan)
**Origine** : relecture complète du module (~5 300 lignes) du 2026-07-07, qui a aussi produit
4 correctifs de bugs (cf. [changelog](../changelog.md)). Ce CR traite le chantier structurel
identifié à cette occasion.

---

## 1. Pourquoi restructurer

Le module fonctionne et il est conceptuellement solide (micro-batching, réservation RPM
atomique en Lua, circuit breaker, SWRR). Mais trois maux structurels freinent son évolution,
sa testabilité et son déploiement :

### 1.1 Effets de bord à l'import

Importer un module ne devrait jamais exécuter de logique. Aujourd'hui :

| Import de… | Déclenche… |
|---|---|
| `tasks/llm_config.py` | `Settings()` + lecture de `providers.yaml` + filtrage des providers + logs |
| `load_balancer/router.py` | `LoadBalancer()` singleton → **connexion Redis + reset des compteurs RPM** |
| `prompts/manager.py` | `PromptManager()` → lecture disque de `prompts.yaml` + `schemas.json` |
| `telemetry/logger.py` | reconfiguration globale de loguru |
| `worker/task_worker.py` | création de l'app Celery |

Conséquences concrètes :
- **Le reset RPM à l'import est dangereux** : chaque process qui importe `router` (API,
  chaque worker Celery, un test) remet à zéro les fenêtres RPM en cours. Un redémarrage de
  worker en pleine simulation autorise un dépassement de quota free-tier.
- Impossible d'importer le module sans Redis disponible.
- Les adapters font des `from llm_module.tasks.llm_config import settings` *dans le corps
  des méthodes* pour esquiver les cycles d'import — symptôme classique de dépendances
  implicites.
- Les tests ne peuvent pas construire une configuration isolée : ils héritent du singleton
  global et de son état.

### 1.2 Pas de frontières entre responsabilités

`broker/redis_broker.py` (~470 lignes) expose **~30 fonctions libres** sur une connexion
globale, couvrant quatre responsabilités distinctes :

1. **Task store** — `save_task_*`, `get_task_*` (persistance statut/résultat)
2. **Rate limiting** — `try_reserve_rpm*`, `mark_cooldown`, `disable_provider`,
   `increment_active_worker`… (quotas, circuit breaker, concurrence)
3. **Files de batch** — `add_task_to_batch_async`, `pop_tasks_from_batch_sync`,
   `try_mark_batch_scheduled_async`… (micro-batching)
4. **Métriques** — `increment_worker_metric`, `scan_worker_metrics`… (compteurs Prometheus)

Chaque fonction existe parfois en double (sync pour Celery, async pour FastAPI). Le
`main.py` importe 12 symboles du broker, le worker 14. Personne ne peut substituer une
implémentation (mémoire, mock) sans monkeypatcher des fonctions une à une.

À cela s'ajoute un **couplage caché inter-projets** : `telemetry/logger.py:122` fait
`from settings import settings` — qui résout le `settings.py` de `llm-agents/` selon le
`sys.path` du process appelant. Le module n'est donc pas réellement autonome.

### 1.3 Packaging inexistant

- Pas de `pyproject.toml` : le module n'est pas installable (`pip install -e .`), les
  imports `llm_module.*` ne marchent que si le repo racine est dans le path.
- `requirements.txt` embarque tout l'écosystème de la simulation (llama-index, faiss,
  sentence-transformers, geopandas, pandas 3, gtfs-kit, qdrant, wordcloud…) alors que le
  runtime du gateway n'a besoin que d'une dizaine de paquets. L'image Docker en pâtit
  directement (build lent, image de plusieurs Go).
- Le SDK client (`client.py`) retourne des dicts bruts avec des conventions magiques
  (`"EXPECTED_ERROR"`, clés `"_post_ms"`/`"_wait_ms"` injectées) — le code GAMA appelant
  n'a aucune garantie de type.

---

## 2. Architecture cible

### 2.1 Arborescence

```text
llm_gateway/                      # nouveau nom de package (ou llm_module conservé)
├── pyproject.toml                # deps runtime minimales ; extras [test], [dev]
├── src/llm_gateway/
│   ├── core/                     # domaine pur — AUCUN I/O, AUCUN import redis/celery/httpx
│   │   ├── models.py             # Task, LLMRequest, AgentSpec, AgentResponse… (ex settings/models.py)
│   │   ├── batching.py           # logique de regroupement, clés de batch, priorités
│   │   └── selection.py          # algorithme SWRR pur (séquence pondérée, curseur)
│   ├── ports/                    # les interfaces (Protocol) — le contrat du module
│   │   └── …                     # TaskStore, RateLimiter, BatchQueue, MetricsSink, LLMAdapter
│   ├── infra/                    # implémentations concrètes des ports
│   │   ├── redis/                # RedisTaskStore, RedisRateLimiter, RedisBatchQueue, RedisMetrics
│   │   ├── memory/               # InMemory* — pour les tests, zéro dépendance
│   │   └── adapters/             # OpenAI, Google, Groq, Mistral, Cerebras (+ client httpx partagé)
│   ├── api/                      # FastAPI — couche transport uniquement
│   │   ├── app.py                # create_app(config) -> FastAPI
│   │   └── routes.py
│   ├── worker/                   # Celery — couche exécution
│   │   └── app.py                # create_worker(config) -> Celery
│   ├── prompts/                  # PromptManager + templates + schemas (inchangé)
│   ├── client/                   # SDK typé pour les consommateurs (GAMA, tests, notebooks)
│   │   └── sdk.py                # LLMGatewayClient.execute() -> TaskResult
│   └── config.py                 # Settings pydantic — construit explicitement, jamais à l'import
└── tests/
```

Règle de dépendance (à faire respecter par import-linter en CI) :
`api / worker → core + ports` ; `infra → ports + core` ; **`core` n'importe rien du reste**.

### 2.2 Les interfaces (ports)

C'est le cœur de la proposition — remplacer les 30 fonctions libres par 5 contrats :

```python
# ports/task_store.py
class TaskStore(Protocol):
    async def save(self, task: Task) -> None: ...
    async def get(self, task_id: str) -> Task | None: ...
    async def wait_done(self, task_id: str, timeout: float) -> Task | None: ...  # pub/sub

class SyncTaskStore(Protocol):        # variante worker (Celery est synchrone)
    def save(self, task: Task) -> None: ...
    def publish_done(self, task: Task) -> None: ...

# ports/rate_limiter.py
class RateLimiter(Protocol):
    def try_reserve(self, provider: str) -> bool: ...   # RPM + lissage + concurrence
    def release(self, provider: str) -> None: ...        # restitue le slot (échec appel)
    def cooldown(self, provider: str, seconds: int) -> None: ...
    def disable(self, provider: str, seconds: int) -> None: ...
    def snapshot(self) -> dict[str, ProviderStatus]: ... # pour /health

# ports/batch_queue.py
class BatchQueue(Protocol):
    async def add(self, batch_key: str, task_id: str, score: float) -> int: ...
    async def try_mark_scheduled(self, batch_key: str, ttl: int) -> bool: ...
    def pop(self, batch_key: str, max_agents: int) -> list[Task]: ...
    def requeue(self, batch_key: str, tasks: list[Task]) -> None: ...

# ports/metrics.py
class MetricsSink(Protocol):
    def incr(self, name: str, amount: int = 1, **labels: str) -> None: ...
    def collect(self) -> Iterable[Metric]: ...           # pour /metrics

# ports/llm_adapter.py — BaseAdapter existe déjà, on formalise le cycle de vie
class LLMAdapter(Protocol):
    def call(self, request: InternalRequest) -> LLMCallResult: ...
    def close(self) -> None: ...                          # libère le client httpx partagé
```

Bénéfices immédiats :
- **Tests unitaires sans Redis** : `InMemoryTaskStore`, `InMemoryRateLimiter` remplacent
  le monkeypatching fonction par fonction. La logique de batching et de sélection devient
  testable en pur Python.
- **Le hash Redis pour les métriques** (recommandation perf de la relecture : un
  `HGETALL` au lieu de dizaines de `SCAN`+`GET` par scrape) devient un simple changement
  d'implémentation de `RedisMetricsSink`, invisible du reste du code.
- **Le client httpx partagé** (keep-alive, ~100-300 ms gagnées par appel LLM) se loge
  naturellement dans le cycle de vie des adapters (`close()`), au lieu du
  `with httpx.Client()` par appel actuel.

### 2.3 Composition explicite (plus de singletons d'import)

```python
# api/app.py
def create_app(config: Settings | None = None) -> FastAPI:
    config = config or Settings()
    store    = RedisTaskStore(config.redis_url)
    queue    = RedisBatchQueue(config.redis_url)
    limiter  = RedisRateLimiter(config.redis_url, config.providers)
    balancer = LoadBalancer(config.providers, limiter)     # ne touche plus Redis en __init__

    app = FastAPI(lifespan=make_lifespan(limiter))          # reset RPM ICI, une fois,
    app.state.deps = Deps(store, queue, balancer, config)   # au démarrage de l'API seulement
    register_routes(app)
    return app
```

Le reset des compteurs RPM devient un geste **explicite du lifespan de l'API** — plus
jamais un effet de bord d'import de worker ou de test. Même schéma côté Celery avec
`create_worker(config)` et le signal `worker_process_init` pour construire les dépendances.

### 2.4 SDK client typé

```python
class TaskResult(BaseModel):
    status: TaskStatus                    # enum, plus de comparaisons de strings
    agents: list[AgentResponse]
    error: str | None
    provider_used: str | None
    timing: TaskTiming | None             # post_ms, wait_ms, timing_p5 structurés

class LLMGatewayClient:
    def __init__(self, base_url: str, *, timeout: float = 120.0): ...
    async def execute(self, request: LLMRequest) -> TaskResult: ...
    async def aclose(self) -> None: ...   # AsyncClient httpx réutilisé entre appels
```

Disparaissent : `"EXPECTED_ERROR"`, les clés `"_post_ms"` injectées dans le dict de
réponse, la tâche `_heartbeat` morte, et les deux `AsyncClient` créés à chaque tâche.
Le `simulation_controller` de `llm-agents/` devient le premier consommateur migré.

### 2.5 `pyproject.toml`

```toml
[project]
name = "llm-gateway"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115,<0.116", "uvicorn", "celery>=5.4", "redis>=5.0",
  "httpx>=0.27", "jinja2>=3.1", "pydantic>=2.9,<3", "pydantic-settings>=2.9",
  "loguru>=0.7", "prometheus-client>=0.20", "PyYAML>=6.0", "demjson3>=3.0",
]

[project.optional-dependencies]
test = ["pytest", "pytest-asyncio", "fakeredis"]
monitoring = ["flower>=2.0"]
```

Soit ~12 dépendances runtime au lieu des ~45 actuelles. Le Dockerfile du gateway installe
`pip install .` — llama-index, faiss, geopandas et consorts restent dans les requirements
de `llm-agents/` où ils sont réellement utilisés.

---

## 3. Plan de migration

Chaque phase est livrable indépendamment, tests verts à chaque étape, API HTTP inchangée
(le contrat `POST /tasks` / `GET /tasks/{id}[/wait]` consommé par GAMA n'est jamais touché).

| Phase | Contenu | Effort | Risque |
|---|---|---|---|
| **0** | `pyproject.toml` + requirements slim + Dockerfile ajusté. Aucun changement de code. | ½ j | Faible — vérifier que l'image démarre |
| **1** | Supprimer les effets de bord d'import : factories `create_app()`/`create_worker()`, reset RPM déplacé dans le lifespan, suppression du `from settings import settings` dans `telemetry/logger.py` (chemin de log via config injectée). | 1-2 j | Moyen — c'est la phase qui touche le plus de lignes ; à sécuriser par la suite E2E |
| **2** | Découper `redis_broker.py` en 4 classes (`RedisTaskStore`, `RedisRateLimiter`, `RedisBatchQueue`, `RedisMetricsSink`) derrière les protocols ; ajouter les `InMemory*` et convertir les tests. Inclure la migration métriques → hash Redis (`HINCRBY`/`HGETALL`). | 2-3 j | Moyen — mécanique mais volumineux ; les scripts Lua sont repris tels quels |
| **3** | Cycle de vie des adapters : instances mises en cache, `httpx.Client` partagé par provider, `close()` propre. Clé API Google déplacée en header `x-goog-api-key`. | 1 j | Faible — gain perf immédiat |
| **4** | SDK client typé (`TaskResult`) + migration de `simulation_controller.py` et des notebooks qui utilisent `LLMClient`. | 1 j | Faible — l'ancien client peut coexister le temps de la migration |
| **5** *(option)* | Extraire `core/` pur (batching, SWRR) + import-linter en CI pour verrouiller les frontières. | 1 j | Faible |

**Total estimé : 6 à 8 jours**, découpables (les phases 0 et 3 sont des quick wins
autonomes si le chantier complet doit attendre).

### Prérequis et garde-fous

- **Geler la branche** : mener le chantier après stabilisation de `feat_cache_population`,
  sur une branche dédiée, car la phase 1 touche les mêmes fichiers que le travail en cours.
- **Filet de sécurité** : la suite `llm_module/tests` (145 tests) + un run E2E
  (`test_e2e.py --burst 20`) avant/après chaque phase.
- **Compat GAMA** : aucun changement de contrat HTTP ; seul le SDK Python change (phase 4),
  et de façon opt-in.

---

## 4. Ce que ce CR ne couvre pas

Les points de robustesse restants de la relecture du 2026-07-07 (slots RPM brûlés sur pop
à vide, `max_retries=50`, budget tokens calculé en trois endroits, `llm_exchanges.jsonl`
multi-lignes, CORS `*`) sont des correctifs ponctuels indépendants de la restructuration —
ils peuvent être traités avant, pendant ou après, au fil de l'eau.

---

## 5. Bilan d'implémentation (2026-07-07)

Toutes les phases (0 à 5) ont été livrées en une passe, tests verts (197 unitaires,
dont 52 nouveaux : core pur, implémentations InMemory*, SDK sur MockTransport) et
contrats import-linter vérifiés (`core` et `ports` purs : KEPT).

Écarts assumés par rapport au plan initial :

| Plan (§2) | Réalisé | Pourquoi |
|---|---|---|
| Renommage en `llm_gateway` + layout `src/` | Package **`llm_module` conservé, à plat** | Zéro rupture pour docker-compose (volumes, commandes uvicorn/celery), les notebooks et le controller GAMA. Le CR listait cette option. |
| `infra/adapters/` | `adapters/` reste à la racine du package | Importé par `scripts/models_influence/prompt_calibration_lib.py` ; le déplacer ne changeait rien au découplage (le port `LLMAdapter` existe). |
| `client/sdk.py` | `sdk.py` (module) | `client.py` existe déjà comme module ; un package `client/` serait entré en collision. |
| Suppression de `settings/models.py` et `tasks/llm_config.py` | Conservés en **shims de compatibilité** (ré-export depuis `core.models` / `config`) | Consommés par les notebooks d'analyse et le pipeline de calibration. `broker/redis_broker.py`, sans consommateur externe, a lui été supprimé. |
| Conversion des tests existants aux `InMemory*` | Tests existants inchangés (déjà purs), **52 tests ajoutés** | Les 145 tests d'origine ne touchaient pas Redis ; les InMemory* sont couverts par leurs propres tests contractuels. |

Réalisé conformément au plan : `pyproject.toml` (12 deps runtime vs ~45, extras
`[test]`/`[monitoring]`), reset RPM déplacé dans le lifespan de l'API, `create_app()` /
`create_celery_app()`, suppression du `from settings import settings` de la télémétrie
(remplacé par `LLM_EXCHANGES_FILE`/`APP_WORKDIR`), découpage du broker en 4 classes
derrière les 5 protocols, métriques worker migrées vers un hash Redis (`wmetrics`,
1 `HGETALL` par scrape), adapters mis en cache avec `httpx.Client` partagé et `close()`
à l'arrêt du worker, clé Google en header `x-goog-api-key`, SDK typé `TaskResult` +
migration des trois appels de `llm_agent.py`, `core/` pur + import-linter.

Validation restante avant merge : reconstruire les images (`docker compose build api
worker flower`) et rejouer `test_e2e.py --burst 20` avec la stack complète.
