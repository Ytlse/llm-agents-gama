# Cycle de vie des agents

Ce document décrit le cycle de planification d'un agent dans le controller, depuis le déclenchement jusqu'à l'envoi de la décision à GAMA.

---

## Déclenchement

Un agent entre en phase de planification quand :
- Il est déclaré **IDLE** (arrivé à destination, aucun déplacement en cours)
- Il reçoit un **feedback d'arrivée** de GAMA (`arrival`) qui invalide son plan courant
- Il reçoit un **feedback de timeout TC** de GAMA (`tc_timeout`) — l'agent a attendu un véhicule TC plus de 30 min sans succès, a été téléporté à sa destination finale et son plan a été abandonné

---

## Arbre d'exécution

```text
[Déclenchement : agent IDLE ou retour d'observation]
└── _try_schedule_person()
    └── Soumission à la file EDF (_edf_heap, deadline = heure de départ) → consommateur libre
    └── Requête des options de transport (CachedTripHelper)
        ├── OTP transit → appel GraphQL (arriveBy=True)
        └── OSMnx directs → appels parallèles (walk, bike, drive)
    └── Consolidation et déduplication des itinéraires
    └── LlmAgent.evaluate_and_choose_travel_plan()
        └── Extraction mémoire long terme (ChromaDB, score composite)
        └── Lookup cache sémantique (LlmSemanticCache)
            ├── Cache HIT → retourne l'index immédiatement
            └── Cache MISS → injection Persona + Météo + Historique + Itinéraires
                └── Inférence LLM (sortie structurée JSON)
                    └── Store asynchrone dans le cache (fire-and-forget)
    └── Traitement du résultat
        └── Écriture décision en mémoire court terme
        └── Stockage trajet dans next_planned_move (état PLANNED)
        └── Émission via WebSocket GAMA (Point 1 ou 2)
```

---

## Points d'injection WebSocket

La décision calculée est envoyée à GAMA via deux chemins possibles selon l'état de l'agent au moment où le LLM répond :

**Point 1 — Fin de calcul synchrone**
L'agent est immobile (IDLE) quand le LLM valide. La décision est immédiatement poussée au topic GAMA `action/data`.

**Point 2 — Feedback d'arrivée / timeout TC**
L'agent est encore en transit. La décision reste en attente dans `next_planned_move` et est exécutée de manière déterministe dès réception de la notification `arrival` ou `tc_timeout`, en tenant compte du feedback pour replanifier l'activité suivante. En cas de `tc_timeout`, le rescheduling de retard n'est pas déclenché (l'agent n'est pas arrivé en retard, il n'est simplement jamais arrivé).

**Cas Bootstrap** (pendant l'initialisation)
Avant la fin de l'init, les décisions sont placées dans une file globale `_messages` vidée périodiquement (fréquence 1s).

### Fiabilité du push (keepalive, rollback, watchdog d'arrivée)

Trois mécanismes garantissent qu'un push perdu ne transforme pas l'agent en « zombie »
(GAMA sans trajet, Python en attente d'une arrivée qui ne viendra jamais — cf. run du
2026-07-08 : ~250 agents inactifs après des coupures WebSocket 1006, invisibles de la
pile de backpressure et du scan) :

1. **Keepalive tolérant** : le client WebSocket (`handle/websocket.py`) utilise
   `ping_timeout=60` (au lieu de 10) — les blocages ponctuels de l'event loop
   (7-20 s observés : calculs CPU, réflexions STM) faisaient expirer le keepalive
   et fermaient la socket (1006) en pleine rafale de push. Les stalls restent
   surveillés par `controller_event_loop_lag_seconds` (`[ALARME]` au-delà de 5 s).
2. **Rollback sur envoi non délivré** : `send_message` (`handle/websocket.py`) avale les
   exceptions d'envoi et retourne `False`. `_push_planned_move` vérifie ce retour au même
   titre qu'une exception : rollback complet (agent remis en IDLE, move restauré), le scan
   de fallback retente le push après reconnexion (`ANOMALIE push`).
3. **Watchdog d'arrivée** : chaque push réussi arme `heading_expected_arrive_at`
   (désarmé à la réception de l'`arrival`/`tc_timeout`). Si le temps simulé dépasse cette
   échéance de plus de `world.arrival_watchdog_hours` (défaut 1 h sim, 0 = désactivé), le
   scan lève une `[ALARME] Arrivée perdue`, force `finish_activity()` et remet l'agent
   dans le circuit (re-push du plan en main ou replanification). Couvre les pertes que le
   rollback ne voit pas : envoi accepté par l'OS mais jamais reçu par GAMA (socket
   moribonde avant détection keepalive), message perdu côté GAMA. La marge doit rester
   au-dessus des retards légitimes dans GAMA (attente TC plafonnée à 30 min par
   `MAX_VEHICLE_WAIT`). Métrique : `controller_lost_arrivals_recovered_total`.

---

## Bootstrap et horizon glissant

À l'initialisation, le controller pré-calcule les itinéraires du cycle complet (toutes les activités de la journée) pour lisser la charge future, puis maintient cet horizon en permanence.

### Phase bootstrap (au démarrage)

```text
[POST /init reçu]
└── Lecture de la population (fichier scellé `data.population_file`, ou toulouse_population_N.json)
    └── Filtre de PÉRIMÈTRE par commune du domicile : household.commune_id ∈ 453 communes
        (repli : trait residence_zone, puis géométrie du polygone + [ALARME]) ; une activité
        hors polygone est comptée et alarmée au-delà de 1 %, l'agent est gardé ; un fichier
        scellé se charge entier ou se refuse ([ALARME])            — inputs/population/perimeter.py
    └── Second filtre au chargement des Person : trait residence_zone (eqasim_loader.perimeter_verdict)
    └── (PersonCloseToTheStopFilter ≤ 5 km d'un arrêt : désactivé)
└── Vérification enrichissement OSMnx dans le cache JSON
    ├── Présent → skip enrichissement
    └── Absent → calcul synchrone des routes inter-activités
└── Instanciation mémoire (ChromaDB + structures locales)
└── Génération réponse d'init vers GAMA
└── Lancement vagues de pré-calcul (background)
    └── Vague 1 : act[N+1] → next_planned_move
    └── Vague 2 : act[N+2] → precomputed_moves
    └── Vague K : act[N+K] → precomputed_moves  (jusqu'à cycle complet)
    └── Initialisation de precomputed_horizon_act / precomputed_horizon_ts
        pour chaque agent (dernière activité calculée par les vagues)
```

**Périmètre au chargement (ticket 031, partie 2 — 2026-09-03).** Jusqu'à ce jour, `_prepare_population`
écartait tout agent dont le domicile **ou une seule activité** sortait du rectangle de 30 km du graphe
OSMnx (`TOULOUSE_OSM_ROUTES_30K_BBOX`) : 77 des 1 000 agents de la population scellée v4 (60 domiciles,
dont 55 de 3ᵉ couronne, et 105 activités), donc un sceau refusé. Le filtre porte désormais sur le
**périmètre de l'enquête** — la commune du domicile est l'une des 453 (`household.commune_id`,
renseigné pour tous depuis la v4). Une activité hors du polygone (école ou travail hors périmètre)
n'écarte pas l'agent : elle est comptée dans le journal (`activités hors polygone k / n`) et une
`[ALARME]` se lève sur front montant au-dessus de 1 % des activités localisées. Mesuré au premier
chargement de la v4 : **1 000 / 1 000 admis par commune, 0 écarté, 0 activité hors polygone**. Le
monde (`WorldGrid`) couvre l'enveloppe du polygone unie à celle des arrêts GTFS — avant, le seul
rectangle des arrêts Tisséo ± 0,05°, qui ne contenait que 221 des 453 communes.

**Lissage de la rafale (vague 1)** — au `/init`, tous les agents éligibles lancent leur
premier itinéraire quasi simultanément. Sans plafond, cette rafale sature les quotas RPM/TPM
des providers et déclenche une cascade de 429/5xx → fallbacks massifs. La vague 1 est donc
bornée par un sémaphore dédié (`world.bootstrap_concurrency`, défaut : 30) : toutes les tâches
sont créées d'un coup mais n'entrent dans le calcul OTP+LLM que par vagues, au fil des
libérations. Cela étale la charge sur la gateway sans allonger le temps de bootstrap global.

### Horizon glissant (en régime continu)

À chaque `popleft()` sur `precomputed_moves` (Point 1 ou Point 2), le controller déclenche immédiatement `_refill_precomputed_queue` pour recalculer l'activité suivant l'horizon courant et la réappendre en queue. La profondeur de `precomputed_moves` reste ainsi constante (= nombre d'activités du planning moins 1).

```text
[Arrivée agent → popleft() de precomputed_moves]
└── next_planned_move ← move dépilé
└── _refill_precomputed_queue()          ← non-bloquant
    └── Guard : precompute_in_progress ?  → skip
    └── Guard : horizon_act / horizon_ts définis ? → sinon skip
    └── next_act = activities[(horizon_idx + 1) % N]
    └── precompute_in_progress = True
    └── asyncio.create_task(_precompute_one)
        └── _compute_move_for_activity (sous _worker_sem)
        └── precomputed_moves.append(move)
        └── Mise à jour precomputed_horizon_act / precomputed_horizon_ts
        └── precompute_in_progress = False
```

---

## Dispatcher EDF (Earliest Deadline First)

En régime permanent, les tâches de planification ne sont plus servies dans l'ordre d'arrivée mais **par échéance croissante** (heure de départ simulée du trajet). Le couple « spawn direct + sémaphore FIFO » est remplacé par une **file de priorité** (`_edf_heap`, min-heap sur `(deadline_sim, seq)`) consommée par `world.worker_concurrency` tâches (`_edf_consumer`). Le nombre de consommateurs **est** la limite de concurrence : ils remplacent le sémaphore.

Ainsi une replanification urgente (départ imminent) passe systématiquement devant un refill d'horizon lointain (J+1), au lieu d'attendre derrière lui un jeton de concurrence.

Deadlines posées aux points de spawn (aucun calcul nouveau) :

| Site de spawn | `kind` | `deadline_sim` |
|---|---|---|
| `_try_schedule_person` / scan de fallback | `plan` | `timestamp` (départ dû maintenant) |
| `_try_schedule_next_after` (act[N+1]) | `plan` | `act_end_ts` (fin de l'activité en cours) |
| `_refill_precomputed_queue` | `refill` | `from_act_end_ts` (départ lointain → dépriorisé) |
| push d'un move déjà calculé | `push` | `0` (toujours prioritaire) |

Le `seq` monotone départage les égalités (heapq exige un tri total). Les invariants sont préservés : `scheduling_in_progress` / `precompute_in_progress` / `_worker_in_progress` sont posés **au spawn** (une tâche en file compte comme « en vol »), et `activities_to_compute_count` conserve sa sémantique (file + en exécution). La file est vidée et les consommateurs annulés par `stop_worker()` au remplacement de scénario.

**Feature flag** : `world.edf_enabled` (défaut `true`). `false` restaure le comportement historique (spawn direct fire-and-forget borné par `_worker_sem`), pour comparaison A/B sur le taux de deadlines manquées.

Le **sémaphore `_worker_sem`** reste utilisé par le **bootstrap** (`bootstrap_all_agents`, hors dispatcher, awaité par `/init` et déjà ordonné par vagues) et par le chemin non-EDF. Configurable via `world.worker_concurrency` (défaut : 20). Sous forte charge, les agents en attente contribuent à `controller_scheduling_in_progress`.

Les deux chemins de calcul sont indépendants et peuvent se chevaucher par agent :

| Flag | Chemin | Écrit vers |
|---|---|---|
| `scheduling_in_progress` | Réactif N+1 (`_plan_one`) | `next_planned_move` |
| `precompute_in_progress` | Refill glissant (`_precompute_one`) | `precomputed_moves` |

---

## Contre-pression prédictive pilotée par les échéances

Le frein réactif au remplissage (`cap·ratio^k`) est aveugle aux échéances : il freine trop tard quand le débit LLM s'effondre (quota), et freine pour rien quand le backlog n'est composé que de refills non urgents. La contre-pression **prédictive** (flag `world.predictive_backpressure_enabled`, défaut `true`) ne retient le `/sync` que si le temps estimé de résolution de la file menace une échéance.

**Insight** : les échéances sont en temps *simulé*, et le temps simulé n'avance que si Python répond au `/sync`. Retenir le `/sync` gèle donc les échéances elles-mêmes — la pause « achète » réellement du temps par rapport aux deadlines (contrairement à un système temps-réel). Ce qui débloque la file pendant la rétention, c'est le drainage par les consommateurs (`T_k = k/D` baisse), pas l'avancée du temps.

**Test de faisabilité EDF** (`backpressure.edf_feasibility`, pur/testé) — avec les deadlines triées `d_1 ≤ … ≤ d_N` (snapshot du heap, hors push), le débit `D` (EWMA des complétions, `ThroughputEwma`) et le rythme `R` (EWMA du `sim_wall_clock_ratio`) :

```
pour k = 1..N :
    T_k     = k / D                      # temps réel pour résoudre les k plus urgentes
    slack_k = (d_k − now_sim) / R        # temps réel avant expiration de d_k
retenir le /sync si ∃k : T_k · marge > slack_k        (marge = world.predictive_margin, défaut 1.4)
```

La rétention réutilise la boucle du mode drainage (ré-échantillonnage toutes les `drain_poll_interval` s, borne dure `min_internal_coeff_cap` = read timeout HTTP de GAMA). `R` est **figé** à l'entrée en rétention (pendant la rétention, aucun `/sync` n'est servi → le rythme mesuré s'effondrerait et rétroagirait sur la condition de sortie). Le **mode drainage à hystérésis** (`drain_*`) reste évalué en **dernier recours** (surcharge permanente > 100 % d'utilisation → EDF fait tout rater, le gel par ratio est la protection ultime).

Le moniteur de débit `D` mesure la fin de `_plan_one` / `_precompute_one` (le pipeline complet OTP+LLM est l'unité qui draine la file ; les hits du cache sémantique complètent en ms et gonflent naturellement `D`). `tau` configurable via `world.throughput_ewma_tau_s` (défaut 90 s — assez court pour réagir à un épuisement de quota par minute), plancher `world.throughput_floor_per_s` (défaut 0.05, évite `T=∞`).

**Notification GAMA** (topic `system/throttle`, hystérésis) : au-delà de `world.throttle_notify_threshold_s` (défaut 5 s) de rétention cumulée sur un `/sync`, Python pousse un message `active: true` (débit LLM réel, vitesse sim, backlog, T estimé), rafraîchi toutes les `world.throttle_notify_refresh_s` (défaut 30 s), levé (`active: false`) au premier `/sync` servi sans rétention. Côté GAMA (`LLMAgent.gaml`), les globales `THROTTLE_ACTIVE` / `LLM_RATE_PER_MIN` / `SIM_RATIO_PYTHON` alimentent l'UI ; le champ `message` reste autoporteur (traitable comme un log).

---

## Arrêt de simulation et remplacement de scénario

L'arrêt d'une simulation dans GAMA ne stoppe pas le process Python : il n'existe pas d'endpoint `/stop`, c'est le `/init` suivant qui fait office de reset via `set_scenario()`. Pour qu'un nouveau run reparte propre, deux nettoyages sont effectués au remplacement du scénario :

- **Annulation des tâches en vol** : toutes les tâches fire-and-forget du scénario (planifications `_plan_one`, refills `_precompute_one`, push, réflexions STM/LTM, checkpoints) sont suivies dans `_inflight_tasks` et annulées en bloc par `stop_worker()`, en plus de la boucle de scan. Sans cela, les planifications LLM/OTP de l'ancien run continueraient après le stop GAMA et pousseraient leurs actions à la simulation suivante (mêmes `person_id` d'un run à l'autre → trajets périmés injectés).
- **Purge du buffer de retry** : les actions non délivrées du `publish_loop` (socket morte au moment du stop) sont conservées dans `LoopContainer._pending` pour retry ; ce buffer est vidé par `set_scenario()` avec un WARNING indiquant le nombre d'actions écartées.

Entre le stop GAMA et le `/init` suivant, l'ancien scénario reste en mémoire et le client WebSocket boucle en reconnexion (toutes les 5 s, indéfiniment). Les données statiques (GTFS, OTP) restent chargées : elles ne sont pas rechargées à l'init suivant.

---

## Contexte météo dans les observations GAMA

Chaque observation reçue de GAMA est enrichie avec les données météo du timestamp concerné avant d'être stockée en mémoire court terme. La granularité est journalière (4 tranches horaires : nuit / matin / midi / soir).

| Type d'observation | Données météo injectées |
|---|---|
| `transfer` | Température, condition, précipitations (mm) si > 0 |
| `wait_in_stop` | Température, condition, précipitations (mm) si > 0 |
| `transit` | Température, condition |
| `arrival` | Température, condition, précipitations (mm) si > 0 |

Les précipitations ne sont affichées que si `precip_mm > 0` afin de ne pas alourdir les observations par temps sec. Pour `transfer` et `wait_in_stop`, l'info pluie est particulièrement utile pour que le LLM infère un inconfort lors de la marche ou de l'attente exposée.

---

## Métriques associées

Voir [observability.md](../../observability.md) et [pipeline.md](../../pipeline.md) pour le détail des métriques et des points de mesure temporels.

| Métrique | Description |
|----------|-------------|
| `controller_scheduling_in_progress` | Agents en planification active |
| `agent_scheduling_lag_seconds` | Écart entre départ théorique et envoi effectif |
| `gama_sim_step_interval_seconds` | Temps entre deux pas de simulation |
| `gama_evaluate_plan_calls_total` | Nombre de plans évalués |
| `agent_activity_decisions_total{outcome,phase}` | Décisions de mobilité ventilées par issue (`llm`/`llm_fallback`/`single`/…) **et par phase** (`bootstrap` = pré-calcul /init, `live` = simulation en marche) |
| `agent_bootstrap_active` | 1 pendant le bootstrap, 0 sinon |
| `agent_bootstrap_completed` / `agent_bootstrap_total` | Agents dont le 1ᵉʳ itinéraire est calculé / total éligible (vague 1) |
| `agent_bootstrap_progress_ratio` | Progression de la vague 1 (0..1) |
| `agent_bootstrap_cache_hits` / `agent_bootstrap_cache_misses` | Premiers itinéraires servis par le cache vs calculés via LLM |
| `agent_bootstrap_wave` | Vague d'anticipation courante (1, puis ≥2 pour act[N+k]) |
| `agent_bootstrap_future_moves` | Trajets futurs (act[N+k]) pré-cachés cumulés |

> **Phase `bootstrap` vs `live`** — un fallback LLM pendant le bootstrap **n'est pas** une
> activité ratée : l'agent partira quand même sur l'itinéraire le plus rapide. Le cockpit
> (dashboard `01_cockpit`, « Activités ratées faute de LLM ») ne compte donc que `phase="live"`, ce qui garantit
> un compteur à **0 avant le démarrage** de la simulation.
