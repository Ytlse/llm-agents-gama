# API HTTP

Six endpoints, définis dans `api/routes.py`. Le contrat n'a pas changé avec le découpage en
trois paquets : le contrôleur GAMA et le SDK le consomment tel quel. Les dépendances (store,
file, balancer, registre) sont lues dans `request.app.state.deps`, composées par
`create_app()`.

## `POST /tasks` — soumettre un lot

Corps : `LLMRequest`.

| Champ | Type | Rôle |
|---|---|---|
| `category` | `str`, obligatoire | doit être déclarée par un bundle enregistré |
| `agents` | liste d'items, **au moins un** | chaque item porte `agent_id` (int accepté, converti en str) ; les autres champs sont validés par le modèle d'item de la catégorie |
| `parameters` | objet, défaut `{}` | passé au template ; entre dans la clé de lot ; `max_tokens` (budget par tâche, défaut 4096 côté worker), `temperature` (défaut 0.7), `prompt_variant` y sont lus |
| `force_provider` | `str | None` | contourne la rotation ; entre dans la clé de lot |
| `min_tpm_required` | `int | None` | exclut les providers dont `tpm_limit` est inférieur ; entre dans la clé de lot |
| `context` | `str | None` | contexte global (météo, trafic), disponible dans le template |

Traitement : le registre résout la catégorie, valide les items, calcule le score de
priorité, persiste la tâche (`PENDING`), l'ajoute à la file `<catégorie>:<md5>` et planifie
le dispatch — immédiat si la file atteint `get_dispatch_threshold` (10 par défaut), sinon
différé de `batch_delay_seconds` (3 s) avec un flag SETNX qui garantit un seul dispatch
différé par cycle.

| Code | Quand | Corps |
|---|---|---|
| **202** | tâche acceptée | `{"task_id": "<uuid>", "status": "pending", "provider_used": null, "message": "Tâche acceptée. Pollez GET /tasks/<id> pour le résultat."}` |
| **422** | catégorie inconnue | `{"detail": "Catégorie inconnue 'x'. Catégories enregistrées : [...]"}` |
| **422** | item refusé par le modèle de la catégorie | `{"detail": "Items invalides pour la catégorie 'x' : [erreurs pydantic]"}` |
| **422** | corps mal formé (FastAPI) | `agents` vide, `category` absent… |

## `GET /tasks/{task_id}` — statut (polling)

| Code | Corps |
|---|---|
| **200** | `TaskStatusResponse` (ci-dessous) |
| **404** | `{"detail": "Tâche '<id>' introuvable ou expirée."}` |

## `GET /tasks/{task_id}/wait` — long-poll

Paramètre de requête `timeout` (secondes, défaut 120, **borné à [1, 300]**). Bloque
jusqu'à l'état terminal (`success` ou `failed`) via Redis Pub/Sub, avec reconnexion si la
socket est interrompue avant la fin du budget. À l'expiration, renvoie le dernier état
connu (donc `pending` ou `running` : c'est au client de traiter ce cas ; le SDK le rend en
`failed` avec `error="Timeout expiré"`).

| Code | Corps |
|---|---|
| **200** | `TaskStatusResponse` |
| **404** | tâche inconnue |

### `TaskStatusResponse`

| Champ | Type | Rempli par |
|---|---|---|
| `task_id` | `str` | API |
| `status` | `pending` · `running` · `success` · `failed` | API puis worker |
| `created_at`, `updated_at` | datetime UTC | API / worker |
| `result` | liste d'`AgentResponse` ou `null` | worker, en cas de succès : les éléments de la réponse dont l'`agent_id` appartient à cette tâche |
| `error` | `str | null` | worker, en cas d'échec |
| `provider_used` | `str | null` | worker |
| `latency_ms` | `float | null` | durée de l'appel LLM du lot |
| `timing_p5` | objet ou `null` | `P4_4_ms` attente en file, `P5_1_ms` attente d'un provider, `P5_3_ms` rendu du prompt, `P5_4_ms` appel LLM, `P5_5_ms` démultiplexage, `provider`, `retries`, `tokens_in`, `tokens_out` (part de la tâche) |

`AgentResponse` : `agent_id` (str) et, tous facultatifs, `probabilities`
(liste de `{index, mode, probability, reason}`), `chosen_index`, `mode`, `reason`,
`summary` ; `extra="allow"` — tout champ du schéma de la catégorie est conservé.

## `GET /health`

```json
{"status": "ok",
 "providers": {"mistral": {"current_rpm": 3, "rpm_limit": 60, "active_tasks": 1, "usage_pct": 5.0,
                           "cooldown": false, "daily_requests": 412, "rpd_limit": null,
                           "daily_tokens": 1203411, "tpd_limit": 100000000,
                           "quota_exhausted": false, "available": true}}}
```

`available` = ni désactivé, ni en cooldown, ni quota du jour épuisé, RPM courant sous la
limite, workers actifs sous `concurrency_limit`. Seuls les providers **avec clé** figurent.

`available` répond à « peut prendre une requête *maintenant* » : il vaut aussi `false` quand le
provider est seulement **occupé** (`active_tasks` ≥ `concurrency_limit`, cas normal d'un modèle
local à un appel à la fois). Un client qui veut savoir si le provider est **hors service** lit
`disabled` et `cooldown`, pas `available` — la plateforme d'expériences l'a appris le 2026-09-08.

## `GET /errors/recent`

Paramètre `limit` (défaut 50, borné à [1, 50]). Les dernières erreurs LLM lues dans le ring
buffer Redis `llm:recent_errors` (50 entrées max), de la plus récente à la plus ancienne :

```json
[{"time": "2026-09-07T06:12:41+00:00", "provider": "groq_openai_120",
  "error_type": "rate limit reached for model …", "http_status": 429,
  "message": "[groq_openai_120] HTTP 429: …", "task_id": "batch_3f1c…_2"}]
```

Consommé par le panneau « Dernières erreurs » du cockpit Grafana (Prometheus ne stocke que
du numérique).

## `GET /metrics`

Export Prometheus (`text/plain; version=0.0.4`). La génération lit Redis de manière
synchrone et est isolée dans un thread. Catalogue : [Métriques](metriques.md).

## OpenAPI

L'application FastAPI publie `/docs` (Swagger UI), `/redoc` et `/openapi.json`. Hors
serveur :

```python
from llm_gateway import create_app
schema = create_app().openapi()      # exige Redis joignable pour build_deps ; sinon passer deps=… en mémoire
```

Le titre déclaré est encore « LLM Unified Communication Module », version « 1.0.0 » (valeur
codée dans `api/app.py`, distincte de `llm_gateway.__version__`).

## CORS

`allow_origins=["*"]`, toutes méthodes, tous en-têtes — à restreindre en production ;
l'authentification est le ticket 036.
