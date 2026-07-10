# Inventaire des éléments Grafana (AVANT refonte — document historique)

> **⚠️ Cet inventaire décrit les 5 dashboards d'AVANT la refonte du 2026-07-10**
> (cockpit, bottleneck, llm_agents, business, system — supprimés depuis).
> L'organisation actuelle (8 dashboards `01_…08_`) est documentée dans
> [docs/arch/monitoring.md](docs/arch/monitoring.md) ; l'analyse et les décisions
> de la refonte dans [grafana_report.md](grafana_report.md).

> Généré le 2026-07-10 à partir de `grafana/dashboards/*.json` (branche `feat_cache_population`).
> 5 dashboards, ~120 panels (hors rows). Datasources : **Prometheus** (uid `ffj2fwnh387pce`, scrape 5s
> sur `api:8000`, `controller:8002`, `node_exporter:9100`) et **Infinity** (uid `infinity1`,
> JSON `GET /errors/recent` sur la gateway).

**Légende des phases** : `INIT` = /init + bootstrap itinéraires · `RUN` = simulation en cours (live)
· `POST` = analyse a posteriori / métier · `∞` = valable en continu (infra).

**Légende des sources** : `CTRL` = controller (llm-agents, :8002) · `API` = gateway llm_module (:8000,
inclut les compteurs Worker relus depuis Redis via `WorkerMetricsCollector`) · `NODE` = node_exporter
· `INF` = Infinity (endpoint JSON).

---

## 1. Cockpit — Pilotage Simulation (`cockpit.json`, uid `cockpit-sim`, refresh 10s)

**Rôle** : vue pilote unique pour surveiller un run du démarrage à la fin. Organisé en étapes numérotées ①→⑥.

### Row ① Initialisation — phase INIT
| Panel | Type | Métrique(s) | Source | Fonction |
|---|---|---|---|---|
| Étape d'init en cours | stat | `controller_init_stage` | CTRL | Étape 0..5 du /init (0=idle, 1=prépa population, 2=population prête, 3=scénario, 4=bootstrap itinéraires, 5=prêt) |
| Progression init | gauge | `controller_init_progress_ratio` | CTRL | Progression globale 0..1 (= étape/5) |
| Agents dans la simulation | stat | `gama_sim_agents_total` | CTRL | Population déclarée au /init |
| Accélération sim / réel | stat | `sim_wall_clock_ratio` | CTRL | Ratio temps simulé / temps réel entre deux /sync |

### Row ①·4 Bootstrap itinéraires (pré-calcul /init) — phase INIT
| Panel | Type | Métrique(s) | Source | Fonction |
|---|---|---|---|---|
| Progression bootstrap | gauge | `agent_bootstrap_progress_ratio` | CTRL | Vague 1 : part des agents avec 1er itinéraire calculé |
| Agents planifiés (bootstrap) | stat | `agent_bootstrap_completed` | CTRL | Nb agents dont le 1er itinéraire est prêt |
| Cache hit bootstrap % | stat | `agent_bootstrap_cache_hits`, `agent_bootstrap_cache_misses` | CTRL | Taux de hit du cache LLM sur les 1ers itinéraires ; 100 % = init sans appel LLM |
| Vague d'anticipation | stat | `agent_bootstrap_wave` | CTRL | 1 = 1er itinéraire, ≥2 = act[N+k] pré-calculées |
| Trajets futurs pré-cachés | stat | `agent_bootstrap_future_moves` | CTRL | Cumul des déplacements futurs pré-calculés (lissage pic du matin) |

### Row ② Pile & cadence — phase RUN
| Panel | Type | Métrique(s) | Source | Fonction |
|---|---|---|---|---|
| Remplissage de la pile | gauge | `controller_backlog_fill_ratio` | CTRL | Activités à calculer / population (1.0 = pile pleine) |
| Activités en attente de calcul | stat | `controller_scheduling_in_progress` | CTRL | Agents avec `scheduling_in_progress=True` |
| Frein backpressure appliqué (s) | timeseries | `controller_backpressure_interval_seconds` | CTRL | Ralentissement imposé à GAMA à la dernière réponse /sync |
| Délai réel / step | stat | `gama_sim_step_interval_seconds` | CTRL | Durée wall-clock entre deux /sync |
| Mode drainage | stat | `controller_drain_mode_active` | CTRL | 1 = /sync retenu jusqu'au vidage de la pile |

### Row ③ Agents bloqués — phase RUN (alarme)
| Panel | Type | Métrique(s) | Source | Fonction |
|---|---|---|---|---|
| Agents bloqués (aucun plan > seuil h sim) | stat | `controller_agents_stuck` | CTRL | Agents sans planification réussie au-delà du seuil |
| Évolution des agents bloqués | timeseries | `controller_agents_stuck` | CTRL | Tendance de la même gauge |
| Activités ratées faute de LLM (fallback %) | stat | `agent_activity_decisions_total{outcome="llm_fallback", phase="live"}` | CTRL | Part des décisions retombées sur l'index par défaut (saturation/timeout LLM), hors bootstrap |
| Activités ratées faute de LLM (nb) | stat | idem | CTRL | Valeur absolue |
| Débit des activités ratées (fallback LLM /min) | timeseries | idem, `rate[2m]×60` | CTRL | Tendance du fallback en live |

### Row ④ Providers — phase ∞
| Panel | Type | Métrique(s) | Source | Fonction |
|---|---|---|---|---|
| Taux de réussite global | stat | `llm_provider_calls_ok_total`, `llm_provider_calls_err_total` | API | % appels LLM OK depuis le démarrage |
| Quota jour consommé par provider (rpd) | bargauge | `llm_provider_daily_usage_ratio` | API | requests_today / rpd_limit |
| État providers & consommation du jour | table | `llm_provider_state`, `llm_provider_requests_today`, `llm_provider_rpd_limit`, `llm_provider_quota_exhausted` | API | Vue synthèse par provider (0=sans clé, 1=désactivé tmp, 2=cooldown, 3=actif) |

### Row ⑤ Cache — phase ∞
| Panel | Type | Métrique(s) | Source | Fonction |
|---|---|---|---|---|
| Cache LLM (hit %) | stat | `llm_cache_hits_total`, `llm_cache_misses_total` | CTRL | Taux de hit cache sémantique Qdrant |
| Cache OTP (hit %) | stat | `trip_cache_hit_ratio` | CTRL | Taux de hit CachedTripHelper |
| Cache OSMnx (hit %) | stat | `osmnx_cache_hit_ratio` | CTRL | Taux de hit itinéraires directs (foot/bike/car) |

### Row ⑥ Dernières erreurs LLM — phase ∞
| Panel | Type | Source | Fonction |
|---|---|---|---|
| Dernières erreurs remontées par les providers | table | INF `GET /errors/recent` | Heure, provider, type, HTTP, message, task_id des dernières erreurs (Prometheus ne stocke pas de texte) |

---

## 2. Goulots d'étranglement — Simulation (`bottleneck.json`, uid `bottleneck-v1`, refresh 10s)

**Rôle** : diagnostic de saturation — trouver QUI est le goulot (scheduler, LLM, OTP, ChromaDB, workers). Panels numérotés ①→⑩. Phase RUN.

| Panel | Type | Métrique(s) | Source | Fonction |
|---|---|---|---|---|
| ① Scheduling Lag (p50/p95/p99) | timeseries | `agent_scheduling_lag_seconds_bucket` | CTRL | δ entre heure prévue et envoi de l'action à GAMA |
| ④ Agents en attente de décision LLM | timeseries | `controller_scheduling_in_progress` | CTRL | Pression instantanée sur le LLM |
| ② Profondeur file de tâches LLM (batch:*) | timeseries | `llm_task_queue_depth` | API | Tâches PENDING dans Redis ; >50 croissant = saturation providers |
| ③ Durée E2E tâche LLM (p50/p95) par catégorie | timeseries | `llm_task_e2e_duration_seconds_bucket` | CTRL (sdk) | POST /tasks → réponse finale (queue + inférence) |
| ⑤ Latence OTP p95 par instance | timeseries | `otp_request_duration_seconds_bucket` | CTRL | OTP goulot ou pas ? (⚠ voir rapport : label `instance` écrasé) |
| ⑥ Ratio cache hit OTP | timeseries | `trip_cache_hit_ratio` | CTRL | <0.3 = cache trop invalidé |
| ⑦ Latence LTM ChromaDB (p50/p95) | timeseries | `ltm_query_duration_seconds_bucket` | CTRL | Durée `aquery_user_memories` |
| ⑧ Ratio accélération simulation | timeseries | `sim_wall_clock_ratio` | CTRL | Décroissant = simulation qui ralentit |
| ⑨ Distribution retard départ agents (skips) | timeseries | `agent_late_departure_seconds_bucket` (le=60/300/1800/7200/+Inf) | CTRL | Sévérité du drift lors des skips d'activité |
| ⑩ Utilisation workers Celery par provider | timeseries | `celery_worker_utilization_ratio` | API | 1.0 en permanence = augmenter la concurrence |

---

## 3. LLM Agents — Monitoring (`llm_agents.json`, uid `llm-agents-v2`, refresh 10s)

**Rôle** : le plus gros dashboard (56 panels) — mélange infra LLM, tokens, cache, OTP, vitesse GAMA. C'est le dashboard historique qui a accumulé les ajouts.

### Row « Vue Globale » — phase ∞
| Panel | Type | Métrique(s) | Source | Fonction |
|---|---|---|---|---|
| Appels LLM réussis (total) | stat | `llm_provider_calls_ok_total` | API | Cumul depuis démarrage |
| Erreurs LLM (total) | stat | `llm_provider_calls_err_total` | API | Cumul |
| Taux de réussite global (%) | gauge | ratio des deux | API | — |
| Agents traités (total) | stat | `llm_agents_batched_total` | API | Agents passés au LLM |
| Ratio batching (agents/prompt) | stat | `llm_agents_batched_total` / `llm_prompts_sent_total` | API | Efficacité du mini-batching |
| Agents reçus de GAMA (total) | stat | `gama_agents_received_total` | API | Volume entrant avant batching |

### Row « Requêtes par Provider » — phase ∞
| Panel | Type | Métrique(s) | Fonction |
|---|---|---|---|
| Débit appels réussis par provider (/min) | timeseries | `rate(llm_provider_calls_ok_total[1m])×60` | Débit OK |
| Débit erreurs par provider (/min) | timeseries | `rate(llm_provider_calls_err_total[1m])×60` | Débit KO |
| Taux de réussite par provider (%) | bargauge | ratio cumulé ok/(ok+err) | Fiabilité lifetime |
| Cumul appels par provider | timeseries | compteurs bruts | Historique |
| Taux de réussite par provider (%/min) | timeseries | ratio de rates 1m | Fiabilité instantanée |

### Row « Analyse des Erreurs » — phase ∞
| Panel | Type | Métrique(s) | Fonction |
|---|---|---|---|
| État des providers | stat | `llm_provider_state` | Mapping 0..3 (désactivation tmp 180s via `disable_provider`) |
| Réactivation dans (secondes) | bargauge | `llm_provider_disable_ttl_seconds` | TTL avant réactivation auto |
| Accumulation des erreurs par type | timeseries | `llm_provider_errors_by_type_total` × `llm_provider_info` | Cumul par provider + error_type, enrichi du modèle |

### Row « Consommation de Tokens » — phase ∞
| Panel | Type | Métrique(s) | Fonction |
|---|---|---|---|
| Tokens totaux consommés | stat | `llm_tokens_in_total{provider="__all__"}` + out | Total in+out |
| Tokens d'entrée (prompt) | stat | `llm_tokens_in_total{provider="__all__"}` | — |
| Tokens de sortie (completion) | stat | `llm_tokens_out_total{provider="__all__"}` | — |
| Tokens in/out moyens par prompt | stat | `__all__` / Σ calls_ok | Taille moyenne prompt/réponse |
| Tokens totaux par provider | bargauge | `(in+out) unless __all__` | Ventilation |
| Tokens consommés dans le temps | timeseries | `in/out unless __all__` | Cumul, la pente = rythme |
| Débit de tokens (tokens/s par provider) | timeseries | `rate(in/out [1m]) unless __all__` | Rythme instantané |
| Tokens moyens par appel LLM par provider | barchart | `(in/out unless __all__) / calls_ok` | Taille moyenne par provider |

### Row « Batching & Catégories » — phase RUN
| Panel | Type | Métrique(s) | Fonction |
|---|---|---|---|
| Agents reçus de GAMA par catégorie | timeseries | `rate(gama_agents_received_total[1m])` | Volume par catégorie de prompt |
| Prompts envoyés vs agents batchés | timeseries | `rate(llm_prompts_sent_total[1m])`, `rate(llm_agents_batched_total[1m])` | Efficacité batching dans le temps |

### Row « OpenTripPlanner (OTP) » — phase RUN
| Panel | Type | Métrique(s) | Fonction |
|---|---|---|---|
| OTP — Requêtes OK vs Erreurs (req/s) | timeseries | `otp_requests_ok_total`, `otp_requests_err_total` | Santé OTP |
| OTP — Latence (p50/p95) | timeseries | `otp_request_duration_seconds_bucket` | Latence routage transit |

### Row « Performance Agent (Itinéraires) » — phases INIT + RUN
| Panel | Type | Métrique(s) | Fonction |
|---|---|---|---|
| Taux de succès des requêtes itinéraire (%/min) | timeseries | `gama_actions_created_total` / `gama_process_person_calls_total` | Part des requêtes aboutissant à un déplacement |
| Débit de complétion — 100 itinéraires réussis | timeseries | `agent_itinerary_100_completion_seconds` | Durée de la dernière fenêtre de 100 succès |
| Heure logique simulée (courante) | stat | `gama_sim_logical_time_seconds×1000` | Horloge de la simulation |
| Temps réel écoulé depuis /init | stat | `gama_sim_real_elapsed_seconds` | Wall-clock du run |
| Pas de temps courant (step #) | stat | `gama_sim_step_count` | — |
| Durée Bootstrap (/init) | stat | `agent_bootstrap_duration_seconds` | Temps du bootstrap (bloque GAMA) |

### Row « Simulation GAMA — Vitesse d'exécution » — phase RUN
| Panel | Type | Métrique(s) | Fonction |
|---|---|---|---|
| Temps réel pour simuler 1h de temps logique | timeseries | `gama_sim_step_interval_seconds / gama_sim_step_logical_duration_seconds × 3600` (+ moyenne 10m) | Vitesse effective de la simulation |

### Row « Latence Critique — Retards de Planification » — phase RUN (alarme)
| Panel | Type | Métrique(s) | Fonction |
|---|---|---|---|
| Retards de planification — courbe cumulative | timeseries | `controller_planning_late_total` (cumul + rate×60) | Agents planifiés après leur heure de départ (warning LATE) |

### Row « Tokens par Provider & Modèle » — phase ∞
| Panel | Type | Métrique(s) | Fonction |
|---|---|---|---|
| Débit de tokens par provider & modèle | timeseries | `rate((tokens unless __all__)[1m]) × llm_provider_info` | ⚠ expression invalide, voir rapport |
| Répartition des tokens par modèle | piechart | `(in+out unless __all__) × llm_provider_info` | Part par modèle |
| Tokens totaux par provider & modèle | bargauge | idem | Cumul |
| Agents en attente de routage — OTP & OSMnx | timeseries | `otp_requests_inflight`, `osmnx_requests_inflight` | Routage goulot ? (mal rangé dans cette row) |

### Row « Cache LLM Sémantique » — phase ∞
| Panel | Type | Métrique(s) | Fonction |
|---|---|---|---|
| Cache Hits (total) | stat | `llm_cache_hits_total` | — |
| Cache Misses (total) | stat | `llm_cache_misses_total` | — |
| Taux de hit cache (%) | gauge | ratio | — |
| Misses par raison | bargauge | `sum by (reason)` | no_result, below_threshold, … |
| Débit hits vs misses (req/min) | timeseries | rates | — |
| Hits par activity_purpose (req/min) | timeseries | `sum by (activity_purpose)` | Quelles activités profitent du cache |
| Latences cache LLM p50/p95 | timeseries | `llm_cache_lookup/embed/insert_seconds_bucket` | Décomposition lookup = embed + Qdrant |

---

## 4. Simulation — Tableau de Bord Métier (`business.json`, uid `simulation-business`, refresh 30s)

**Rôle** : lecture « métier » des choix de mobilité — modes, distances, biais du LLM, états des agents. Phase RUN + POST. Variable de template `$provider` (label_values de `llm_mode_by_provider_total`).

### Row « Agents & Simulation »
| Panel | Type | Métrique(s) | Source | Fonction |
|---|---|---|---|---|
| Agents dans la simulation | stat | `gama_sim_agents_total` | CTRL | Population |
| Agents ayant utilisé le LLM | stat | `llm_agents_batched_total` | API | Cumul délégué au LLM |
| Part LLM-Based (%) | gauge | batched / `gama_agents_received_total` | API | Part des décisions LLM |
| Durée réelle d'un pas de temps simulé | timeseries | `gama_sim_step_interval_seconds` | CTRL | Wall-clock entre /sync (titre : « time step - 2 minutes ») |
| Agents traités par le LLM (rate/min) | timeseries | `rate(llm_agents_batched_total[1m])×60` | API | Débit |
| Répartition : Via LLM vs Réponse directe OTP | piechart | `gama_evaluate_plan_calls_total` vs `gama_process_person_calls_total − evaluate` | CTRL | Agents multi-choix (LLM) vs mono-choix (direct) |
| LLM vs Direct OTP — flux (req/min) | timeseries | idem en rates | CTRL | Même distinction dans le temps |

### Row « Modes de Transport par Tranche de Distance »
| Panel | Type | Métrique(s) | Fonction |
|---|---|---|---|
| Modes — 0-1 km | piechart | `llm_mode_by_distance_total{bracket="0-1km"}` | Répartition modale courte distance |
| Modes — 1-2 km | piechart | bracket `1-2km` | — |
| Modes — 2-5 km | piechart | bracket `2-5km` | — |
| Modes — 5-10 km | piechart | bracket `5-10km` | — |
| Modes — > 50 km | piechart | bracket `>50km` | ⚠ trous 10-20 km et 20-50 km, voir rapport |
| Répartition globale des modes | piechart | `llm_transport_mode_chosen_total` | Vue d'ensemble tous trajets |

### Row « Modes de Transport par Provider LLM » (répétée sur `$provider`)
| Panel | Type | Métrique(s) | Fonction |
|---|---|---|---|
| Modes — $provider | piechart | `llm_mode_by_provider_total{provider="$provider"}` | Biais modal de chaque LLM |

### Row « Choix d'Itinéraire (Chosen Index) »
| Panel | Type | Métrique(s) | Fonction |
|---|---|---|---|
| Total d'itinéraires évalués | stat | `llm_chosen_index_total` | — |
| Premier choix sélectionné (index 0) | stat | `{index="0"}` | — |
| Part du premier choix (%) | gauge | ratio | Détection du biais de position |
| Distribution des indices choisis | piechart | `sum by (index)` | — |
| Fréquence de sélection par index | barchart | `sort_desc(sum by (index))` | — |
| Évolution des indices choisis dans le temps | timeseries | `avg_over_time(...[5m:])` | Dérive des préférences |

### Row « État des Agents (Cycle de Vie) »
| Panel | Type | Métrique(s) | Fonction |
|---|---|---|---|
| Répartition des états agents dans le temps | timeseries | `gama_agent_states{state=~"inactive|ready|active"}` | Synchronisé à chaque /sync |
| Inactifs / Ready / Actifs | 3 × stat | idem par état | Instantané |
| Distribution instantanée des états | piechart | idem | — |

---

## 5. Système — CPU & RAM (`system.json`, uid `system-resources`, refresh 10s)

**Rôle** : ressources machine via node_exporter. Phase ∞.
⚠ Sous Docker Desktop macOS, node_exporter mesure la **VM Linux de Docker**, pas le Mac hôte.

| Panel | Type | Métrique(s) | Fonction |
|---|---|---|---|
| CPU Usage (%) | gauge | `node_cpu_seconds_total{mode="idle"}` | 100 − idle |
| RAM Usage (%) | gauge | `node_memory_MemAvailable/MemTotal` | — |
| RAM totale / disponible | 2 × stat | idem | — |
| Load Average (1/5 min) | 2 × stat | `node_load1`, `node_load5` | — |
| Utilisation CPU globale (%) | timeseries | idem gauge | Tendance |
| CPU par mode | timeseries | user/system/iowait/irq/softirq | Décomposition |
| Load Average (1m/5m/15m) | timeseries | `node_load1/5/15` | — |
| Utilisation RAM (%) | timeseries | idem gauge | Tendance |
| RAM par catégorie (octets) | timeseries | used / cache+buffers / free | Décomposition |

---

## Métriques exposées par le code mais absentes de tous les dashboards

Ces métriques existent et sont scrapées, mais aucun panel ne les affiche :

### Nouvelles (branche `feat_cache_population` — couverture du cache LLM au démarrage)
- `llm_cache_points_total` — points dans la collection Qdrant au démarrage
- `llm_cache_points_exact` — points « mémoire vide » exploitables par le bootstrap
- `llm_cache_points_stale` — points au schéma obsolète (weekday manquant)
- `llm_cache_agents_covered` — agents distincts couverts par le cache

### Pipeline contrôleur (EDF / backpressure avancé)
- `controller_throughput_tasks_per_min` — débit de complétion (EWMA)
- `controller_min_slack_sim_seconds` — échéance la plus proche − temps sim
- `controller_predictive_hold_seconds` — rétention prédictive du /sync
- `controller_edf_queue_depth` — profondeur file EDF
- `controller_deadline_misses_total` — arrivées après l'heure de départ prévue
- `controller_event_loop_lag_seconds` — stalls de l'event loop asyncio
- `controller_lost_arrivals_recovered_total` — récupérations par le watchdog d'arrivée
- `controller_sync_requests_total`, `controller_init_requests_total` — volumétrie HTTP
- `agent_bootstrap_active`, `agent_bootstrap_total` — état/total du bootstrap

### Routage OSMnx (seul l'inflight et le hit ratio sont affichés)
- `osmnx_requests_ok_total`, `osmnx_requests_err_total`, `osmnx_request_duration_seconds`

### Gateway / providers
- `llm_provider_rpm_limit`, `llm_provider_tpd_limit`, `llm_provider_tokens_today`
- `llm_trip_distance_bracket_total` — volume de trajets par tranche (les camemberts n'affichent que la répartition modale)

### Côté SDK controller (doublons des métriques worker — jamais affichés)
- `llm_tasks_in_progress`, `llm_tasks_sent_total`, `llm_tasks_responses_total`, `llm_tasks_responses_success_total`, `llm_tasks_responses_failure_total`
- `llm_mode_chosen_total`, `llm_index_chosen_total` (doublons de `llm_transport_mode_chosen_total` / `llm_chosen_index_total` côté worker)
