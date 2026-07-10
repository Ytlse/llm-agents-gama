# Monitoring & dashboards de pilotage

La supervision repose sur **Prometheus + Grafana**, tous deux provisionnés dans
`docker-compose.yml`. Aucune brique externe (pas de Loki) : les métriques
numériques passent par Prometheus, les rares données textuelles (messages
d'erreur LLM) par un endpoint JSON lu via le plugin Grafana *Infinity*.

## Cibles scrappées (`prometheus.yml`)

| Job | Cible | Expose |
|-----|-------|--------|
| `llm_agents_api`        | `api:8000/metrics`        | Providers, tokens, batching, files de batch, quotas jour, alarmes worker |
| `llm_agents_controller` | `controller:8002/metrics` | Simulation, pile, backpressure, init, agents bloqués, caches, alarmes, modes×motif |
| `node`                  | `node_exporter:9100`      | CPU / RAM / load (global VM Docker) |
| `cadvisor`              | `cadvisor:8080`           | CPU / RAM / réseau **par conteneur** (api, worker, otp, redis, qdrant…) |

## Dashboards (`grafana/dashboards/`)

Refonte 2026-07-10 : **un dashboard = une question**, ordonnés par le cycle de
vie d'un run. Chaque dashboard porte le tag `sim` et un menu déroulant de
navigation vers les autres. Philosophie : le live ne garde que les indicateurs
qui déclenchent une décision *pendant* le run ; l'analyse fine post-run vit
dans `/debug-run` (`make report / capacity / init`).

| # | Fichier / uid | Question |
|---|---------------|----------|
| 01 | `01_cockpit.json` / `cockpit` | Le run va-t-il bien ? (feu santé, alarmes, agents bloqués, fallback %, quotas, caches, erreurs) |
| 02 | `02_init_bootstrap.json` / `init-bootstrap` | L'init est-elle rapide, le cache Qdrant assez peuplé ? |
| 03 | `03_pipeline_scheduling.json` / `pipeline-scheduling` | Le scheduler tient-il la cadence ? (lag, EDF, backpressure, retards, vitesse sim, /sync) |
| 04 | `04_llm_gateway.json` / `llm-gateway` | Les providers suivent-ils ? À quel coût en tokens ? |
| 05 | `05_routing.json` / `routing-otp-osmnx` | Le calcul d'itinéraire (OTP/OSMnx) est-il un goulot ? |
| 06 | `06_cache_llm.json` / `cache-llm` | Le cache sémantique évite-t-il des appels LLM ? |
| 07 | `07_metier_mobilite.json` / `metier-mobilite` | Que choisissent les agents ? (parts modales, distance, motif, biais d'index, états) |
| 08 | `08_systeme.json` / `systeme` | La machine encaisse-t-elle ? (global VM + par conteneur via cAdvisor) |

Le dashboard 07 applique la **palette officielle des modes** (CLAUDE.md) :
voiture rouge, vélo/train violet, TC vert, marche cyan, moto magenta.

## Alarmes

Deux mécanismes complémentaires :

1. **Compteur `alarme_total{source}`** — chaque log ERROR `[ALARME]` incrémente
   le compteur (module `llm_module/telemetry/alarms.py`, `fire_alarme(source)`).
   Sources : `backlog`, `event_loop`, `arrivee_perdue`, `cache_llm_stale`,
   `cache_llm_qdrant`, `gateway_llm` (controller) et `providers_satures`
   (worker, via Redis `alarme:{source}` relu par `WorkerMetricsCollector`).
   Ne pas importer `alarms.py` dans le processus API : la famille y est déjà
   émise par le collecteur Redis. Les deux sites `[ALARME]` de
   `llm_module/config.py` (échec de persistance providers.yaml, rare et non
   critique en live) restent hors compteur — visibles via `make error`.
2. **Alertes Grafana provisionnées** — `grafana/provisioning/alerting/simulation-alerts.yml`
   (7 règles, dossier « Alertes simulation ») : agents bloqués, fallback LLM
   >10 %, alarme `[ALARME]` émise, drainage >10 min, aucun provider actif,
   event loop >5 s, backlog >90 % pendant 10 min.

## Métriques notables

**Gateway** (`llm_module/api/metrics.py`) : appels/erreurs/tokens par provider
(`__all__` = agrégat), `llm_provider_state/…_limit/…_today`, files de batch,
workers Celery, métriques métier worker (`llm_transport_mode_chosen_total`,
`llm_mode_by_distance_total` — 7 tranches jusqu'à `>50km`,
`llm_mode_by_provider_total`, `llm_chosen_index_total`), `alarme_total` (part worker).

**Contrôleur** (`llm-agents/`) : init/pile/backpressure/drain/stuck, famille EDF
(ticket 003), `controller_sync_duration_seconds` (latence du battement de cœur
GAMA↔controller), `controller_event_loop_lag_seconds`,
`trip_mode_by_purpose_total{mode,purpose}` (mode principal × motif d'activité,
compté au push du trajet vers GAMA — couvre décisions LLM **et** cache
sémantique **et** mono-choix, contrairement aux `llm_mode_by_*` de la gateway),
couverture du cache Qdrant (`llm_cache_points_total/exact/stale`,
`llm_cache_agents_covered`), latence OTP par instance (label **`otp_instance`**
— `instance` est réservé par Prometheus pour la cible de scrape).

Le coût est suivi **en tokens** (pas de conversion €) : totaux in/out,
tokens/heure simulée, tokens économisés par le cache (estimation
hits × tokens moyens par appel) — dashboards 04 et 06.

## Dernières erreurs LLM (chemin texte)

Prometheus ne stocke que du numérique. Les messages d'erreur bruts vivent dans
un **ring buffer Redis** plafonné (`llm:recent_errors`, 50 entrées) :

- écriture : `RedisMetricsSink.push_error()`, appelé au point de capture d'erreur
  du worker (`llm_module/worker/task_worker.py`) ;
- lecture : `GET /errors/recent?limit=N` (`llm_module/api/routes.py`) ;
- affichage : datasource *Infinity* (`yesoreyeram-infinity-datasource`, installée
  via `GF_INSTALL_PLUGINS`), provisionnée dans
  `grafana/provisioning/datasources/prometheus.yml` — dashboards 01 et 04.

## Réglages

| Clé | Défaut | Effet |
|-----|--------|-------|
| `world.stuck_agent_threshold_hours` | 20 | Seuil (heures simulées) au-delà duquel un agent sans plan est compté bloqué |
| `providers.yaml` `rpd_limit` / `tpd_limit` | — | Quotas jour, appliqués **et** exposés (ratio d'usage) |
| `world.edf_enabled` | `true` | Dispatcher EDF (`false` = spawn direct FIFO historique) |
| `world.predictive_backpressure_enabled` | `true` | Rétention prédictive (`false` = frein `ratio^k` historique) |
| `world.throughput_ewma_tau_s` | 90 | Constante de temps de l'EWMA de débit D |
| `world.throughput_floor_per_s` | 0.05 | Plancher de D (évite T_estimé = ∞) |
| `world.predictive_margin` | 1.4 | Marge du test de faisabilité EDF |
| `world.throttle_notify_threshold_s` | 5 | Rétention mini avant notification GAMA `system/throttle` |
| `world.throttle_notify_refresh_s` | 30 | Période de rafraîchissement du message throttle |
