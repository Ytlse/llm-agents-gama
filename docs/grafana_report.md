# Rapport Grafana — anomalies, personas & proposition de refactoring (v2)

> **✅ IMPLÉMENTÉ le 2026-07-10.** Les 8 dashboards `01_…08_` sont en place
> (`grafana/dashboards/`), les 5 anciens supprimés, les 7 alertes provisionnées
> (`grafana/provisioning/alerting/`), cAdvisor ajouté, les corrections code faites
> (label `otp_instance`, suppression métriques SDK, `alarme_total`,
> `controller_sync_duration_seconds`, `trip_mode_by_purpose_total`), `/debug-run` étendu.
> Décision finale : coût suivi **en tokens** (pas de conversion €). État courant documenté
> dans [docs/arch/monitoring.md](docs/arch/monitoring.md) ; ce fichier reste comme trace
> de l'analyse et des décisions.

> Généré le 2026-07-10, révisé après retours. Basé sur le croisement de `grafana/dashboards/*.json`
> avec les métriques réellement exposées par le code (`llm-agents/`, `llm_module/`, `prometheus.yml`).
> Inventaire complet : [grafana_elements.md](grafana_elements.md).

**Philosophie retenue** : Grafana = **monitoring en direct** (pilotage d'un run en cours, décisions
en secondes). L'analyse profonde post-run reste dans `/debug-run` et `make report/capacity/init/error`.
Tout indicateur qui ne sert pas une décision *pendant* le run est retiré du live.

**Décisions actées** (échange du 2026-07-10) :
- Pas de limite sur le nombre de dashboards.
- uid propres (les anciennes URL de dashboards meurent — assumé).
- Métriques SDK dupliquées (`llm_tasks_*`, `llm_mode_chosen_total`, `llm_index_chosen_total`) : **à supprimer**.
- Panel « Part LLM-Based (%) » : **à supprimer** (au lieu de corriger le dénominateur).
- Le ratio de choix d'itinéraire par défaut sur erreur définitive LLM doit aussi être remonté par **`/debug-run`**.

---

## Partie 1 — Anomalies détectées

### 🔴 Cassé (le panel n'affiche rien ou affiche faux)

**1. `llm_agents.json` — « Débit de tokens par provider & modèle » : PromQL invalide**
Les deux requêtes utilisent `rate((llm_tokens_in_total unless llm_tokens_in_total{provider="__all__"})[1m])`.
Un sélecteur de plage `[1m]` ne peut s'appliquer qu'à un sélecteur simple ; sur une expression
parenthésée il faut une subquery `[1m:]`. Prometheus renvoie une erreur de parsing → panel vide
en permanence.
**Fix** : `rate(llm_tokens_in_total[1m]) unless rate(llm_tokens_in_total{provider="__all__"}[1m])`
puis la jointure `* on(provider) group_left(model) llm_provider_info` (même schéma que le panel
« Débit de tokens (tokens/s par provider) » qui, lui, est correct).

**2. `bottleneck.json` ⑤ — « Latence OTP p95 par instance » : label `instance` écrasé**
Le code expose `otp_request_duration_seconds` avec un label applicatif `instance`
([otp.py:32-37](llm-agents/trip_helper/otp.py:32)). Prometheus réserve `instance` pour la cible de
scrape : sans `honor_labels: true`, le label applicatif est renommé `exported_instance` et `instance`
vaut toujours `controller:8002`. La ventilation par instance OTP n'a jamais fonctionné.
**Fix** : renommer le label applicatif en `otp_instance` dans le code.

**3. `business.json` — « Part LLM-Based (%) » : dénominateur faux, ~100 % structurel**
`llm_agents_batched_total / gama_agents_received_total` : les deux compteurs couvrent la même
population (agents déjà envoyés à la gateway, [routes.py:75](llm_module/api/routes.py:75)).
**Décision : panel supprimé.**

**4. `business.json` — « Évolution des indices choisis dans le temps » : compteurs cumulés moyennés**
`avg_over_time` sur des compteurs cumulatifs : les courbes montent indéfiniment, illisible pour
détecter une dérive. **Fix** : `sum by (index) (increase(llm_chosen_index_total[5m]))` — ou
suppression du live (voir Partie 4), l'analyse de biais étant un sujet post-run.

### 🟠 Obsolète / désynchronisé du code

**5. Tranches de distance incomplètes (`business.json`)** — le code produit 7 brackets
([task_worker.py:558](llm_module/worker/task_worker.py:558)), le dashboard n'en affiche que 5 :
les trajets **10-20 km et 20-50 km sont invisibles** (plage périurbaine, la plus intéressante pour
l'arbitrage voiture/TC).

**6. Couverture du cache LLM : le code référence un panel qui n'existe pas**
[cache.py:40](llm-agents/llm/cache.py:40) : *« cf. cockpit ⑤ »*. Les 4 gauges
`llm_cache_points_total/exact/stale` et `llm_cache_agents_covered` (cœur de `feat_cache_population`)
ne sont affichées nulle part. La question « le cache est-il assez peuplé pour l'init ? » n'a pas de
réponse visuelle.

**7. Famille EDF / backpressure jamais exposée** — `controller_throughput_tasks_per_min`,
`controller_min_slack_sim_seconds`, `controller_predictive_hold_seconds`, `controller_edf_queue_depth`,
`controller_deadline_misses_total`, `controller_event_loop_lag_seconds`,
`controller_lost_arrivals_recovered_total` : instrumentation récente du scheduler sans aucun panel.
`bottleneck.json` diagnostique l'ancien pipeline.

**8. Doublons de métriques côté SDK controller** — [sdk.py:36-49](llm_module/sdk.py:36) :
`llm_mode_chosen_total`, `llm_index_chosen_total`, `llm_tasks_*`. **Décision : suppression**
(seule `llm_task_e2e_duration_seconds` du même fichier est conservée, elle alimente le panel E2E).

**9. Titre figé « time step - 2 minutes »** (`business.json`) — la durée logique d'un step est
mesurée dynamiquement (`gama_sim_step_logical_duration_seconds`) ; le titre ment si le pas change.

**10. OSMnx affiché à 20 %** — `osmnx_requests_ok/err_total` et `osmnx_request_duration_seconds`
existent mais ne sont pas affichés, alors que le routage direct (marche/vélo/voiture) est majoritaire
en volume.

### 🟡 Trompeur / qualité

**11. « Via LLM vs Réponse directe OTP » (business)** — `gama_evaluate_plan_calls_total` inclut les
décisions servies par le **cache sémantique** (aucun appel LLM réel) : « Via LLM » surestime depuis
l'ajout du cache. À renommer « multi-choix vs mono-choix ».

**12. « Taux de réussite par provider (%/min) » (llm_agents)** — division sans `clamp_min` → NaN
hors trafic, courbes à trous.

**13. Même métrique, plusieurs noms** — `controller_scheduling_in_progress` s'appelle « Activités
en attente de calcul » (cockpit) et « Agents en attente de décision LLM » (bottleneck).

**14. Duplications inter-dashboards** — cache LLM (cockpit + llm_agents), OTP (bottleneck +
llm_agents), vitesse sim (4 dashboards), état providers (cockpit + llm_agents). Chaque copie a divergé.

**15. `system.json` mesure la VM Docker Desktop**, pas le Mac hôte, et rien par service. Aucune
mention dans le dashboard.

**16. Panel mal rangé** — « Agents en attente de routage — OTP & OSMnx » est dans la row « Tokens
par Provider & Modèle ».

---

## Partie 2 — Analyse par persona : qu'est-ce qui manque ?

### 👨‍💻 Développeur — « les perfos tiennent-elles ? »

**Couvert** : scheduling lag, E2E LLM, latences OTP, profondeur de file, utilisation workers, vitesse sim.
**Manque** :
| Manque | Besoin | Existant ? |
|---|---|---|
| CPU/RAM **par conteneur** (worker vs OTP vs Qdrant vs Redis) | Savoir *qui* mange la machine, pas juste « 90 % global » | ❌ nécessite **cAdvisor** dans docker-compose (petit conteneur qui expose les stats Docker à Prometheus) |
| Durée de traitement d'un `/sync` côté controller | Le /sync est le battement de cœur GAMA↔controller ; s'il ralentit, tout ralentit | ❌ nouvelle métrique `controller_sync_duration_seconds` (Histogram) — seul un compteur existe |
| Débit de complétion tâches/min | Une seule courbe qui dit « le pipeline avance à X tâches/min » | ✅ `controller_throughput_tasks_per_min` existe, jamais affichée (anomalie 7) |
| Event loop / stalls asyncio | Détecter les gels silencieux du controller | ✅ `controller_event_loop_lag_seconds` existe, jamais affichée |

### 👔 Client — « que choisissent les agents ? »

**Couvert** : camemberts modes par distance/provider, répartition globale, indices choisis.
**Manque** :
| Manque | Besoin | Existant ? |
|---|---|---|
| **Parts modales dans le temps** (courbe empilée, `increase[10m]`) | Les camemberts sont cumulatifs depuis le démarrage : impossible de voir « à 8h les agents prennent la voiture, à 14h le vélo » | ✅ métrique existe, panel à créer |
| **Palette officielle des modes non appliquée** | La charte projet (Car=rouge, Vélo=violet, TC=vert, Marche=cyan, Moto=magenta) est définie dans CLAUDE.md pour « notebooks, GAMA, Grafana » — les camemberts utilisent les couleurs aléatoires de Grafana | ✅ config panels uniquement (overrides de couleur par valeur de label) |
| Tranches 10-20 km et 20-50 km | Trous actuels (anomalie 5) | ✅ métrique existe |
| Répartition modale **par motif d'activité** (travail, courses, loisir) | Lire le comportement, pas juste la distance | ❌ nouvelle métrique (label `purpose` sur le choix de mode, côté worker) — *optionnel, à discuter* |

### 🛠️ Ingénieur — « le logiciel respecte-t-il la spec ? blocages ? erreurs ? »

**Couvert** : agents bloqués, fallback LLM %, états providers, table des dernières erreurs, retards de planification.
**Manque** :
| Manque | Besoin | Existant ? |
|---|---|---|
| **Compteur d'[ALARME]** | La convention projet (CLAUDE.md) logge les anomalies confirmées en `[ALARME]`, mais elles ne sont visibles qu'en CLI (`make error`). Un stat rouge « N alarmes depuis /init » dans le cockpit est LE signal manquant | ❌ nouvelle métrique `alarme_total{source}` incrémentée aux mêmes endroits que les logs `[ALARME]` |
| Stat « santé globale » (OK / DÉGRADÉ / CRITIQUE) | Un seul feu tricolore en haut du cockpit, dérivé des seuils (stuck > 0, fallback % > seuil, alarmes > 0, provider épuisé) | ✅ expression Grafana sur métriques existantes |
| Ratio d'issues des décisions (llm / cache / single / fallback / no_solution) | Vérifier que la répartition des chemins de décision reste conforme à l'attendu | ✅ `agent_activity_decisions_total{outcome}` existe, seul le fallback est affiché |
| Watchdog & deadline misses | Arrivées perdues récupérées, échéances ratées | ✅ métriques existent, jamais affichées (anomalie 7) |
| Seuils visuels homogènes | Les stats du cockpit n'ont pas tous de thresholds (vert/orange/rouge) cohérents | ✅ config panels |

### 💰 Financier — « combien ça coûte, le cache rapporte-t-il ? »

**Couvert** : tokens in/out totaux, par provider/modèle, quotas jour, hit ratio des 3 caches.
**Manque** :
| Manque | Besoin | Existant ? |
|---|---|---|
| **Coût estimé en €/$** | Les tokens bruts ne parlent pas ; il faut tokens × prix du modèle | ❌ table de prix par modèle à ajouter dans `providers.yaml` + gauge `llm_provider_price_per_mtoken_{in,out}` ; le panel fait la multiplication |
| **Économies du cache** | « Le cache a évité N appels ≈ M tokens ≈ X € » — la seule justification chiffrée de `feat_cache_population` | ✅ approximable en panel : `llm_cache_hits_total × (tokens moyens par appel)` ; version exacte = compteur `llm_cache_tokens_saved_total` (❌ code) |
| Coût par heure simulée / par agent | Unit economics : « simuler 24 h × 900 agents = X € » | ✅ expression combinant tokens et `gama_sim_*` (une fois le prix exposé) |

---

## Partie 3 — Allègement : live vs `/debug-run`

Le live doit tenir sur peu d'écrans et chaque panel doit déclencher une décision *pendant* le run.
Retiré du live (l'info reste dans Prometheus, requêtable à la demande, et `/debug-run` couvre le post-mortem) :

| Retiré du live | Pourquoi | Où ça vit désormais |
|---|---|---|
| « Cumul appels par provider » (compteurs bruts) | Un cumul qui monte ne déclenche aucune action | `/debug-run` |
| « Taux de réussite par provider (%) » lifetime **et** « %/min » | Doublon ; on garde une seule vue (le %/min, corrigé du NaN) | — |
| 8 panels tokens → 4 (total, débit/s, par modèle, moyens/appel) | Les déclinaisons in/out séparées et cumuls redondants surchargent | `/debug-run` |
| Row « Choix d'itinéraire » : 6 panels → 1 stat « part index 0 % » | Le biais de position est une analyse post-run, pas du pilotage | `/debug-run` |
| « Évolution des indices choisis » (anomalie 4) | Analyse fine post-run | `/debug-run` |
| Latences cache LLM embed/insert (on garde le lookup p95 seul) | 6 courbes d'histogrammes pour un composant qui marche = bruit | `/debug-run` |
| États agents : 5 panels → timeseries + 1 stat | Camembert + 3 stats redondants avec la courbe | — |
| CPU par mode, RAM par catégorie, load 15m | Détail système sans action associée en live | Prometheus à la demande |
| « Distribution retard départ (skips) » détaillée par bucket | La sévérité fine du drift est un sujet post-mortem | `/debug-run` |

**Extension `/debug-run` demandée** : ajouter au rapport le **ratio de choix d'itinéraire par défaut
sur erreur définitive LLM** — à partir de `agent_activity_decisions_total{outcome="llm_fallback", phase="live"}`
côté métriques et des entrées `LLM Error (Default index)` du move-log côté logs, rapporté au total
des décisions de la phase live.

---

## Partie 4 — Cible : 8 dashboards `01_…`

| # | Fichier / uid | Question | Contenu (allégé, avec les ajouts persona) |
|---|---|---|---|
| **01** | `01_cockpit.json` / `cockpit` | Le run va bien, oui ou non ? | **Nouveau : feu santé globale + stat [ALARME]**. Init stage + progression, backlog/backpressure/drain, agents bloqués, fallback % live, quota jour providers, 3 hit-ratios cache, table erreurs Infinity, liens vers 02-08. Zéro timeseries d'analyse. |
| **02** | `02_init_bootstrap.json` / `init-bootstrap` | L'init est-elle rapide et le cache assez peuplé ? | Progression bootstrap, vague, futurs pré-cachés, hit bootstrap %, durée bootstrap, **couverture Qdrant** (`llm_cache_points_*`, `agents_covered`) (fix 6). |
| **03** | `03_pipeline_scheduling.json` / `pipeline-scheduling` | Le scheduler tient-il la cadence ? | Scheduling lag p95, agents en attente (nom unique, fix 13), **EDF : profondeur, throughput/min, min slack, predictive hold, deadline misses, event loop lag, watchdog** (fix 7), retards de planification, vitesse sim (1 seul panel « temps réel pour 1h logique »), **durée /sync p95 (nouvelle métrique)**. |
| **04** | `04_llm_gateway.json` / `llm-gateway` | Les providers suivent-ils ? À quel coût ? | Débits OK/KO par provider, %/min corrigé (fix 12), état + TTL réactivation, erreurs par type, file batch, workers Celery, E2E par catégorie, batching. **Tokens réduits à 4 panels + coût estimé €/$ + économies cache** (persona financier). |
| **05** | `05_routing.json` / `routing-otp-osmnx` | Le calcul d'itinéraire est-il un goulot ? | OTP ok/err + latence p95 (label `otp_instance` corrigé, fix 2), **OSMnx ok/err + latence** (fix 10), inflight OTP/OSMnx (fix 16), hit ratios OTP/OSMnx en tendance. |
| **06** | `06_cache_llm.json` / `cache-llm` | Le cache sémantique évite-t-il des appels ? | Hits/misses + taux, misses par raison, hits par activity_purpose, lookup p95 seul, couverture Qdrant en tendance, **tokens/appels économisés**. |
| **07** | `07_metier_mobilite.json` / `metier-mobilite` | Que choisissent les agents ? | **Parts modales dans le temps (courbe empilée)**, répartition globale, modes × distance en **barres empilées 7 brackets** (fix 5, remplace 5 camemberts), modes par provider (`$provider`), « multi-choix vs mono-choix » renommé (fix 11), stat « part index 0 % », états agents (timeseries + stat), **palette officielle appliquée partout** (Car=rouge, Vélo=violet, TC=vert, Marche=cyan, Moto=magenta). Refresh 30s. |
| **08** | `08_systeme.json` / `systeme` | La machine encaisse-t-elle ? | CPU/RAM/load globaux (réduits), note « VM Docker Desktop », **cAdvisor : CPU & RAM par conteneur** (api, worker, otp, redis, qdrant, controller). |

**Disparaissent** : `llm_agents.json`, `bottleneck.json`, `business.json`, `cockpit.json`, `system.json`
(contenu redistribué), et toutes les duplications de l'anomalie 14.

---

## Partie 5 — Travaux code associés (hors JSON)

| Action | Fichiers | Persona servi |
|---|---|---|
| Renommer label `instance` → `otp_instance` | [otp.py](llm-agents/trip_helper/otp.py) | dev |
| Supprimer `llm_tasks_*`, `llm_mode_chosen_total`, `llm_index_chosen_total` (garder `llm_task_e2e_duration_seconds`) | [sdk.py](llm_module/sdk.py) | — (dette) |
| Nouvelle métrique `alarme_total{source}` aux points d'émission des logs `[ALARME]` | controller + gateway | ingénieur |
| Nouvelle métrique `controller_sync_duration_seconds` (Histogram) | [application.py](llm-agents/handle/application.py) | dev |
| Prix par modèle dans `providers.yaml` + gauge `llm_provider_price_per_mtoken_{in,out}` | [providers.yaml](llm_module/config/providers.yaml), [metrics.py](llm_module/api/metrics.py) | financier |
| (Option) compteur exact `llm_cache_tokens_saved_total` | [cache.py](llm-agents/llm/cache.py) | financier |
| cAdvisor dans docker-compose + job Prometheus | [docker-compose.yml](docker-compose.yml), [prometheus.yml](prometheus.yml) | dev |
| `/debug-run` : ajouter le ratio de choix par défaut sur erreur définitive LLM | skill debug-run | ingénieur |
| Mettre à jour le commentaire « cf. cockpit ⑤ » | [cache.py:40](llm-agents/llm/cache.py:40) | — |
| Docs : `docs/arch/*` concernés, `docs/changelog.md`, README (section monitoring) | — | — |

### Plan de migration (après validation finale)
1. Fixes code (labels, suppressions SDK, nouvelles métriques, cAdvisor).
2. Création des 8 JSON, suppression des 5 anciens (provisioning recharge en ≤10s).
3. Extension `/debug-run` (ratio fallback).
4. Docs + changelog.
5. Vérification sur un run réel : chaque panel a des données ou une raison documentée de ne pas en avoir.

---

## Questions restantes

1. **Nouvelles métriques code** (Partie 5) : OK pour toutes ? Les indispensables à mes yeux :
   `alarme_total` (feu rouge cockpit) et le prix par modèle (sans lui, pas de coût en €).
   `controller_sync_duration_seconds` et `llm_cache_tokens_saved_total` sont des nice-to-have.
2. **cAdvisor** : conteneur léger qui expose CPU/RAM *par conteneur Docker* à Prometheus — c'est le
   seul moyen de voir « qui » consomme. Je propose de l'ajouter. OK ?
3. **Répartition modale par motif d'activité** (persona client) : nécessite un nouveau label côté
   worker. On le fait maintenant ou on note pour plus tard ?
