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
| 07 | `07_metier_mobilite.json` / `metier-mobilite` | Que choisissent les agents ? (parts modales, distance, motif, biais d'index, états, ponctualité des départs) |
| 08 | `08_systeme.json` / `systeme` | La machine encaisse-t-elle ? (global VM + par conteneur via cAdvisor) |

Le dashboard 07 applique la **palette officielle des modes** (CLAUDE.md) :
voiture rouge, vélo/train violet, TC vert, marche cyan, moto magenta.

**Row « Répartition attendue vs tirée »** (depuis le choix probabiliste) : le LLM
annonce une distribution, l'agent tire dedans — deux camemberts côte à côte
(`llm_mode_probability_pct_total` vs `trip_mode_by_purpose_total`), l'écart en points
de %, et un bandeau d'intégrité des étiquettes de mode. Trois clés de lecture :

- les deux vocabulaires sont ramenés à un socle commun par `label_replace`
  (marche/vélo/voiture/TC) — le **train est fondu dans les TC**, comme côté contrôleur ;
- l'écart est **structurellement non nul** : les décisions mono-choix et les points de
  cache hérités arrivent dans « tiré » sans exister dans « attendu ». C'est la
  **tendance** qui compte, pas la valeur absolue ;
- le bandeau `llm_mode_label_mismatch_total / llm_mode_label_checked_total` doit rester
  à **0 %**. Non nul = le modèle note une autre option que celle qu'il croit, donc ses
  probabilités partent sur les mauvais index et toute la répartition est fausse
  (alarme `mode_label_mismatch` au-delà de 5 % sur 200 options observées).

Le symptôme jumeau se lit dans les logs plutôt que dans Grafana : un modèle qui
**renumérote les options** place sa masse sur des index inexistants. Le réalignement par
libellé de mode la rattrape (cf. `docs/arch/llm-inference.md`) ; ce qui reste sort en
`make error` sous `[ALARME] Vecteur de probabilités inexploitable` — la décision du modèle
a été remplacée par une distribution uniforme, la part modale du run en porte la trace.
`make warning | grep "hors bornes"` donne le détail (masse réalignée ou perdue).

Les graphiques temporels du dashboard 07 (parts modales, trajets par motif,
états des agents) sont indexés sur l'**heure simulée**, pas l'heure réelle :
chaque panel interroge en plus `gama_sim_logical_time_seconds * 1000` puis une
chaîne de transformations Grafana (`joinByField` sur Time → `convertFieldType`
du champ `__sim_time` en temps → `organize` qui masque le Time réel) fait de
l'heure simulée l'axe X. Lire « à 8h les agents prennent la voiture » signifie
donc 8h *dans la simulation*. Conséquences : la fenêtre temporelle sélectionnée
en haut de Grafana reste en temps réel (elle borne les échantillons Prometheus),
et si la plage couvre plusieurs runs, l'axe X repart en arrière à chaque /init —
restreindre la plage au run courant pour une lecture propre.

## Alarmes

Deux mécanismes complémentaires :

1. **Compteur `alarme_total{source}`** — chaque log ERROR `[ALARME]` incrémente
   le compteur (module `llm_module/telemetry/alarms.py`, `fire_alarme(source)`).
   Sources : `backlog`, `event_loop`, `arrivee_perdue`, `cache_llm_stale`,
   `cache_llm_qdrant`, `gateway_llm`, `vehicule_orphelin` (controller) et `providers_satures`
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
(`__all__` = agrégat), `llm_provider_state/…_limit/…_today`,
`llm_provider_disable_ttl_seconds` (secondes avant réactivation — couvre la
désactivation temporaire **et** le cooldown 429/5xx, valeur = max des deux
TTL), files de batch,
workers Celery, métriques métier worker (`llm_transport_mode_chosen_total`,
`llm_mode_by_distance_total` — 7 tranches jusqu'à `>50km`,
`llm_mode_by_provider_total`, `llm_chosen_index_total`), `alarme_total` (part worker).
Depuis que le LLM renvoie une **distribution** de probabilités (cf.
`docs/arch/llm-inference.md`), `llm_transport_mode_chosen_total` et
`llm_chosen_index_total` portent l'option **la plus probable** (le tirage a lieu côté
contrôleur) ; `llm_mode_probability_pct_total{mode}` cumule la masse de probabilité par
mode canonique — c'est la répartition *attendue*, dont `trip_mode_by_purpose_total`
donne la réalisation tirée.

**Contrôleur** (`llm-agents/`) : init/pile/backpressure/drain/stuck, famille EDF
(ticket 003), `controller_sync_duration_seconds` (latence du battement de cœur
GAMA↔controller), `controller_event_loop_lag_seconds`,
`trip_mode_by_purpose_total{mode,purpose}` (mode principal × motif d'activité,
compté au push du trajet vers GAMA — couvre décisions LLM **et** cache
sémantique **et** mono-choix, contrairement aux `llm_mode_by_*` de la gateway),
`agent_vehicle_chain_total{mode,event}` (cohérence de chaîne vélo/voiture :
`unavailable` = mode écarté faute de véhicule sur place, `forced_return` /
`return_failed` = verrou de retour au domicile, `orphaned` / `reset_home` =
véhicule laissé à une étape intermédiaire puis rattrapé — cf.
[vehicle-chain.md](vehicle-chain.md)),
couverture du cache Qdrant (`llm_cache_points_total/exact/stale`,
`llm_cache_agents_covered`), `agent_bootstrap_wave_moves{wave,status}` (détail par vague du bootstrap,
vague 1 comprise — status `planned`/`done`/`ok`/`cache_hit`/`cache_miss` ;
le dashboard 02 affiche 8 lignes « progression / traités / cache hit », une
par vague ; le nombre réel de vagues est dynamique, les lignes au-delà
restent vides),
latence OTP par instance (label **`otp_instance`**
— `instance` est réservé par Prometheus pour la cible de scrape),
famille **ponctualité des départs** (row dédiée du dashboard 07, phase live
uniquement — le bootstrap pré-calcule au /init et n'est pas un vrai départ) :
`agent_departures_punctuality_total{status=on_time|late}` (à l'heure = action
poussée vers GAMA au plus 60 s après l'heure prévue),
`agent_departure_delay_seconds` (histogramme des seuls retards, sum/count =
retard moyen), `agent_departure_delay_max_seconds` (pire retard du run),
complétée par `controller_planning_late_total` (départs « ratés » : la
planification — typiquement la réponse LLM — est arrivée après que même
l'heure d'arrivée prévue soit passée) et
`agent_activity_decisions_total{outcome="llm_fallback", phase="live"}`
(parti sur l'itinéraire par défaut faute de réponse LLM).

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
