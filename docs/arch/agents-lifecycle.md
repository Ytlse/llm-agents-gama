# Cycle de vie des agents

Ce document décrit le cycle de planification d'un agent dans le controller, depuis le déclenchement jusqu'à l'envoi de la décision à GAMA.

---

## Déclenchement

Un agent entre en phase de planification quand :
- Il est déclaré **IDLE** (arrivé à destination, aucun déplacement en cours)
- Il reçoit un **feedback d'arrivée** de GAMA qui invalide son plan courant

---

## Arbre d'exécution

```text
[Déclenchement : agent IDLE ou retour d'observation]
└── _try_schedule_person()
    └── Acquisition d'un jeton du sémaphore de concurrence (_worker_sem)
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

**Point 2 — Feedback d'arrivée**
L'agent est encore en transit. La décision reste en attente dans `next_planned_move` et est exécutée de manière déterministe dès réception de la notification d'arrivée, en tenant compte du feedback pour replanifier l'activité suivante.

**Cas Bootstrap** (pendant l'initialisation)
Avant la fin de l'init, les décisions sont placées dans une file globale `_messages` vidée périodiquement (fréquence 1s).

---

## Bootstrap et horizon glissant

À l'initialisation, le controller pré-calcule les itinéraires du cycle complet (toutes les activités de la journée) pour lisser la charge future, puis maintient cet horizon en permanence.

### Phase bootstrap (au démarrage)

```text
[POST /init reçu]
└── Lecture toulouse_population_N.json
    └── Filtrage spatial (Bounding Box GTFS)
    └── Filtrage PersonCloseToTheStopFilter (≤ 5 km d'un arrêt)
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

## Sémaphore de concurrence

`_worker_sem` borne le nombre d'agents planifiés simultanément, que ce soit via le chemin réactif (`_plan_one`) ou le refill glissant (`_precompute_one`). Configurable via `world.worker_concurrency` dans la config d'expérience (défaut : 25). Sous forte charge, les agents en attente de jeton contribuent à `controller_scheduling_in_progress` (métrique Prometheus).

Les deux chemins de calcul sont indépendants et peuvent se chevaucher par agent :

| Flag | Chemin | Écrit vers |
|---|---|---|
| `scheduling_in_progress` | Réactif N+1 (`_plan_one`) | `next_planned_move` |
| `precompute_in_progress` | Refill glissant (`_precompute_one`) | `precomputed_moves` |

---

## Métriques associées

Voir [observability.md](../../observability.md) et [pipeline.md](../../pipeline.md) pour le détail des métriques et des points de mesure temporels.

| Métrique | Description |
|----------|-------------|
| `controller_scheduling_in_progress` | Agents en planification active |
| `agent_scheduling_lag_seconds` | Écart entre départ théorique et envoi effectif |
| `gama_sim_step_interval_seconds` | Temps entre deux pas de simulation |
| `gama_evaluate_plan_calls_total` | Nombre de plans évalués |
