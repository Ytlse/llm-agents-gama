# Métriques Prometheus

Deux processus exposent des métriques. L'**API** sert `GET /metrics` : ses propres
compteurs, plus les compteurs du **worker** relus depuis Redis par un collecteur (le worker
Celery n'a pas de serveur HTTP). Le **SDK** déclare les siennes dans le processus
consommateur (le contrôleur GAMA, scrapé sur `:8002`).

## Comment le worker compte

Le worker écrit dans le hash Redis `wmetrics` (`HINCRBY`), avec des noms
`metrique:label[:label2]` — `llm_calls_ok_total:mistral`, `mode_by_distance:car:2-5km`. Le
collecteur `WorkerMetricsCollector` (`api/metrics.py`) fait **un seul `HGETALL` par
scrape** et projette chaque préfixe sur une famille. Les compteurs n'ont pas de TTL : ils
survivent aux redémarrages, un `FLUSHDB` les remet à zéro.

## Côté API — compteur direct

| Famille | Type | Labels | Sens |
|---|---|---|---|
| `gama_agents_received_total` | compteur | `category` | agents reçus dans `POST /tasks`, avant regroupement |

## Côté API — relues depuis Redis, génériques

| Famille | Labels | Clé Redis | Sens |
|---|---|---|---|
| `llm_provider_calls_ok_total` | `provider` | `llm_calls_ok_total:<p>` | appels LLM réussis ; les providers configurés sans appel apparaissent à 0 |
| `llm_provider_calls_err_total` | `provider` | `llm_calls_err_total:<p>` | appels échoués |
| `llm_prompts_sent_total` | `category` | `prompts_sent_total:<c>` | prompts envoyés (un par lot) |
| `llm_agents_batched_total` | `category` | `agents_batched_total:<c>` | agents fusionnés dans ces prompts ; le rapport des deux est le taux de batching |
| `llm_tokens_in_total` | `provider` | `tokens_in_total:<p>` (et `__all__`) | tokens d'entrée facturés |
| `llm_tokens_out_total` | `provider` | `tokens_out_total:<p>` (et `__all__`) | tokens de sortie |
| `llm_provider_errors_by_type_total` | `provider`, `error_type` | `llm_errors_by_type:<p>:<type>` | `error_type` = 10 premiers mots du message du fournisseur (`rate limit reached for model…`), `max_tokens_truncation`, `parse error …` |
| `llm_capacity_reroute_total` | `provider` | `capacity_reroute_total:<p>` | lots rejoués ailleurs parce que le prompt rendu dépassait `max_tokens_per_request` (413 évité) |
| `alarme_total` | `source` | `alarme:<source>` | alarmes `[ALARME]` du worker et des bundles ; sources connues : `providers_satures`, `mode_label_mismatch` |

## Côté API — relues depuis Redis, métier (mobilité)

Ces familles sont écrites par le hook `observe` du bundle `mobility_llm`
(`categories/itinary_multi_agent.py`) et **restent codées dans le collecteur du gateway**
(hypothèse H11 du ticket 037) parce que les dashboards Grafana 04 et 07 les citent. Un
gateway sans ce bundle les expose vides.

| Famille | Labels | Clé Redis | Sens |
|---|---|---|---|
| `llm_transport_mode_chosen_total` | `mode` | `transport_mode_chosen:<m>` | mode principal de l'option la plus probable (vocabulaire fin : `metro`, `tram`, `bus`, `train`, `car`, `cycling`, `walking`…) |
| `llm_mode_probability_pct_total` | `mode` | `mode_probability_pct:<m>` | somme des probabilités (en %) par mode **canonique** (`public_transport`, `train`, `car`, `cycling`, `walking`, `motorbike`, `other`), modes non proposés inclus à 0 |
| `llm_mode_label_checked_total` | — | `mode_label_checked` | options dont l'étiquette de mode recopiée par le LLM a été comparée à l'option réelle |
| `llm_mode_label_mismatch_total` | — | `mode_label_mismatch` | désaccords ; ratio attendu ≈ 0 |
| `llm_trip_distance_bracket_total` | `bracket` | `trip_distance_bracket:<b>` | `0-1km`, `1-2km`, `2-5km`, `5-10km`, `10-20km`, `20-50km`, `>50km` |
| `llm_mode_by_distance_total` | `mode`, `bracket` | `mode_by_distance:<m>:<b>` | croisement |
| `llm_mode_by_provider_total` | `mode`, `provider` | `mode_by_provider:<m>:<p>` | croisement |
| `llm_chosen_index_total` | `index` | `chosen_index:<i>` | position de l'option retenue (0 = première proposée) |

## Côté API — état des providers (gauges, calculées au scrape)

| Famille | Labels | Sens |
|---|---|---|
| `llm_provider_state` | `provider` | 0 = sans clé API, 1 = désactivé temporairement (30 erreurs consécutives), 2 = cooldown, 3 = actif ; tous les providers de `providers.yaml` figurent |
| `llm_provider_disable_ttl_seconds` | `provider` | secondes avant réactivation (max du TTL de désactivation et du cooldown) |
| `llm_task_queue_depth` | `batch_key` | tâches `PENDING` par file `<catégorie>:<md5>` |
| `llm_task_queue_depth_by_category` | `category` | même chose agrégée par préfixe de clé |
| `celery_worker_utilization_ratio` | `provider` | `active_workers / concurrency_limit` (1.0 = saturé) |
| `llm_provider_info` | `provider`, `model`, `adapter` | toujours 1 ; porte les libellés |
| `llm_provider_rpm_limit`, `llm_provider_rpd_limit`, `llm_provider_tpd_limit` | `provider` | limites configurées (0 = illimité) |
| `llm_provider_requests_today`, `llm_provider_tokens_today` | `provider` | consommation du jour UTC |
| `llm_provider_daily_usage_ratio` | `provider` | `requests_today / rpd_limit` (absent si pas de `rpd_limit`) |
| `llm_provider_quota_exhausted` | `provider` | 1 si écarté jusqu'à minuit UTC |

## Côté SDK

Déclarées à l'import de `llm_gateway.sdk.client` :

| Famille | Type | Labels | Sens |
|---|---|---|---|
| `llm_task_e2e_duration_seconds` | histogramme (1, 2, 5, 10, 30, 60, 120 s) | `category` | `POST /tasks` → état terminal, vu du client |
| `llm_gateway_circuit_open` | gauge | — | 1 = disjoncteur ouvert |
| `llm_gateway_circuit_waiters` | gauge | — | soumissions suspendues |
| `alarme_total` | compteur | `source` | créé au premier `fire_alarme` ; sources `gateway_llm`, `gateway_llm_circuit`, plus celles du contrôleur (`backlog`, `event_loop`, `cache_llm`…) |

`alarme_total` porte le **même nom** des deux côtés : côté API elle est servie par le
collecteur Redis, côté contrôleur par le compteur du SDK. Dans un processus qui expose déjà
la famille (l'API elle-même, si elle importe le SDK), le compteur du SDK passe hors registre
pour éviter `DuplicateTimeseries` — les alarmes restent visibles dans les logs.

## Ce qui n'est pas une métrique

Les messages d'erreur bruts (texte) sont dans le ring buffer `llm:recent_errors`, servi par
`GET /errors/recent`. Les échanges complets (prompt, réponse, tokens, `sim_ts`) sont dans
`APP_WORKDIR/llm_exchanges.jsonl`, les erreurs dans `llm_errors.jsonl`.
