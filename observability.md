# Observability — LLM Agents GAMA

Prometheus scrape toutes les 5 s les deux endpoints suivants :

| Service       | Endpoint scrapeé        |
|---------------|-------------------------|
| `api`         | `http://api:8000/metrics`        |
| `controller`  | `http://controller:8002/metrics` |

Le **worker Celery** n'expose pas d'endpoint HTTP. Ses métriques sont stockées
dans Redis (compteurs persistants, sans TTL) et lues par un collecteur custom
enregistré dans l'API au moment du scrape.

---

## Métriques exposées par `api:8000`

### Flux d'agents entrants (avant mini-batching)

| Métrique | Type | Labels | Description |
|---|---|---|---|
| `gama_agents_received_total` | Counter | `category` | Nombre d'agents reçus depuis GAMA. Incrémenté de `len(agents)` à chaque appel `POST /tasks`. Permet de mesurer le débit brut avant regroupement. |

> **Requête Grafana utile**
> ```promql
> rate(gama_agents_received_total[1m])
> ```

---

### Appels LLM par provider *(Worker → Redis → API)*

Ces compteurs sont incrémentés dans le worker Celery après chaque appel HTTP
vers un LLM, puis lus par le `WorkerMetricsCollector` lors du scrape.

| Métrique | Type | Labels | Description |
|---|---|---|---|
| `llm_provider_calls_ok_total` | Counter | `provider` | Appels LLM ayant retourné une réponse valide, par fournisseur (`openai`, `mistral`, `google`, `groq`, …). |
| `llm_provider_calls_err_total` | Counter | `provider` | Appels LLM ayant levé une exception (timeout, 5xx, parse error, …), par fournisseur. |

> **Requêtes Grafana utiles**
> ```promql
> # Débit par provider (appels/s)
> rate(llm_provider_calls_ok_total[1m])
>
> # Taux d'erreur par provider
> rate(llm_provider_calls_err_total[1m])
> / (rate(llm_provider_calls_ok_total[1m]) + rate(llm_provider_calls_err_total[1m]))
> ```

---

### Ratio mini-batching *(Worker → Redis → API)*

Le mini-batching regroupe plusieurs agents en un seul prompt LLM.
Ces deux compteurs permettent de mesurer l'efficacité de ce regroupement.

| Métrique | Type | Labels | Description |
|---|---|---|---|
| `llm_prompts_sent_total` | Counter | `category` | Nombre de prompts effectivement envoyés au LLM, par catégorie (`itinary_multi_agent`, `perception_filter`, …). Un prompt peut couvrir N agents. |
| `llm_agents_batched_total` | Counter | `category` | Somme cumulée des agents traités dans ces prompts. Divisé par `llm_prompts_sent_total`, donne la taille moyenne des batchs. |

> **Requêtes Grafana utiles**
> ```promql
> # Agents reçus/s vs prompts envoyés/s
> rate(gama_agents_received_total[1m])
> rate(llm_prompts_sent_total[1m])
>
> # Taille moyenne des batchs (agents par prompt)
> rate(llm_agents_batched_total[1m]) / rate(llm_prompts_sent_total[1m])
> ```

---

## Métriques exposées par `controller:8002`

### Endpoints GAMA → Controller

| Métrique | Type | Labels | Description |
|---|---|---|---|
| `controller_sync_requests_total` | Counter | — | Nombre de requêtes `POST /sync` reçues depuis GAMA. Chaque step de simulation déclenche un sync. |
| `controller_init_requests_total` | Counter | — | Nombre de requêtes `POST /init` reçues depuis GAMA. Normalement 1 par run de simulation. |

> **Requête Grafana utile**
> ```promql
> # Fréquence des steps de simulation
> rate(controller_sync_requests_total[1m])
> ```

---

### Boucle de simulation (SimulationLoopV1)

| Métrique | Type | Labels | Description |
|---|---|---|---|
| `gama_process_person_calls_total` | Counter | — | Nombre d'appels à `process_person()`. Représente le nombre d'agents traités par la boucle principale. |
| `gama_evaluate_plan_calls_total` | Counter | — | Nombre d'appels à `evaluate_and_choose_travel_plan()`. Déclenché quand un agent doit choisir un plan de déplacement. |
| `gama_actions_created_total` | Counter | — | Nombre d'actions créées et envoyées à GAMA. |

> **Requête Grafana utile**
> ```promql
> # Ratio plans évalués / personnes traitées (indice d'activité de mobilité)
> rate(gama_evaluate_plan_calls_total[1m]) / rate(gama_process_person_calls_total[1m])
> ```

---

### Client LLM (polling asynchrone)

Ces métriques tracent le cycle de vie d'une tâche côté contrôleur,
depuis la soumission jusqu'à la réponse.

| Métrique | Type | Labels | Description |
|---|---|---|---|
| `llm_tasks_in_progress` | Gauge | — | Nombre de tâches LLM actuellement en attente de réponse (soumises et non encore résolues). |
| `llm_tasks_sent_total` | Counter | — | Nombre total de tâches soumises à l'API (`POST /tasks`). |
| `llm_tasks_responses_total` | Counter | — | Nombre total de réponses reçues (succès + échecs). |
| `llm_tasks_responses_success_total` | Counter | — | Réponses avec `status == success` et résultat non vide. |
| `llm_tasks_responses_failure_total` | Counter | — | Réponses avec `status == failed` ou timeout de polling. |
| `llm_mode_chosen_total` | Counter | `mode` | Distribution des modes de transport choisis par le LLM (`car`, `transit`, `walk`, …). |
| `llm_index_chosen_total` | Counter | `index` | Distribution des indices de plan choisis par le LLM (indice dans la liste des alternatives OTP). |

> **Requêtes Grafana utiles**
> ```promql
> # Taux de succès des réponses LLM
> rate(llm_tasks_responses_success_total[1m]) / rate(llm_tasks_responses_total[1m])
>
> # Distribution des modes de transport (camembert)
> llm_mode_chosen_total
>
> # Latence de traitement (approx) : tâches en cours / débit de réponses
> llm_tasks_in_progress / rate(llm_tasks_responses_total[1m])
> ```

---

## Vue d'ensemble du flux de données

```
GAMA
  │
  ├─ POST /sync  ──► controller_sync_requests_total
  │                   └─► gama_process_person_calls_total
  │                   └─► gama_evaluate_plan_calls_total
  │
  └─ POST /tasks ──► gama_agents_received_total       (par category)
  (via LLMClient)     └─► [mini-batch grouping]
                          └─► llm_prompts_sent_total  (1 prompt pour N agents)
                          └─► llm_agents_batched_total
                          └─► llm_provider_calls_ok_total / err  (par provider)
                          └─► llm_tasks_responses_success_total
                          └─► llm_mode_chosen_total / llm_index_chosen_total
                          └─► gama_actions_created_total
```
