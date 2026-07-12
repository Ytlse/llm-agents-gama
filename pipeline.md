# Pipeline de mesure — Scénario de transport (agents LLM uniquement)

**T0** : Arrivée du POST `/sync` de GAMA au controller  
**Fin** : Message d'action envoyé à GAMA via WebSocket

Chaque point de mesure est un **timestamp Unix (float, secondes)** relevé avec `time.time()`.  
Les durées et les écarts entre segments se calculent par soustraction dans le notebook d'analyse.  
Les colonnes du worker Celery (P5) restent en millisecondes (processus séparé, pas de référence d'horloge commune).

---

## Points de mesure

### Réception (application.py)

| Timestamp | Relevé | Description |
|-----------|--------|-------------|
| `T0` | Début du handler `/sync` (avant lecture du body) | Proxy le plus proche de l'arrivée de la requête GAMA. |
| `T_parse` | Après `orjson.loads()` + validation Pydantic | Fin du parsing — `T_parse - T0` ≈ durée de lecture/parsing requête. |

---

### Filtrage (simulation_controller.py)

| Timestamp | Relevé | Description |
|-----------|--------|-------------|
| `T_flag` | Après le parcours synchrone de tous les agents | `T_flag - T_parse` ≈ durée du filtrage des agents éligibles (`heading_to is None` et `scheduling_in_progress is False`). |

> Tous les agents éligibles entrent ensuite en phase OTP **en parallèle** (concurrence non bornée via `asyncio.create_task()`).  
> `T_otp_start - T_flag` capture le délai de scheduling asyncio entre le lancement des tâches et leur démarrage effectif.

---

### Calcul d'itinéraires (par agent, en parallèle entre agents)

| Timestamp | Relevé | Description |
|-----------|--------|-------------|
| `T_otp_start` | Avant `trip_helper.get_itineraries()` | Début de l'appel OTP/OSMnx. |
| `T_otp_end` | Après `trip_helper.get_itineraries()` | `T_otp_end - T_otp_start` ≈ durée totale (OTP transit + OSMnx direct en parallèle interne, sémaphore inclus). |

En mode **OTP direct** (mode courant), le trip helper appelle OTP transit et OSMnx en parallèle interne — un seul bloc de temps est capturé.  
En mode **Solari + CachedTripHelper**, `T_otp_start / T_otp_end` capturent le cache lookup + appels éventuels.

---

### Requête LLM (par agent)

| Timestamp | Relevé | Description |
|-----------|--------|-------------|
| `T_ltm_start` | Avant la requête ChromaDB | Début de la requête vectorielle mémoire long terme. Absent (`null`) si LTM désactivée. |
| `T_ltm_end` | Après la requête ChromaDB | `T_ltm_end - T_ltm_start` ≈ durée requête LTM. |
| `T_llm_start` | Avant `LLMGatewayClient.execute()` | Début du POST `/tasks` vers le gateway LLM. |
| `T_llm_sent` | `T_llm_start + timing.post_ms / 1000` | Fin du POST (tâche créée, `task_id` reçu). `T_llm_sent - T_llm_start` ≈ durée HTTP POST création tâche. |
| `T_llm_result` | Après retour de `execute()` | Fin du long-poll Pub/Sub. `T_llm_result - T_llm_sent` ≈ attente résultat LLM (micro-batch + worker + publish). |

---

### Traitement LLM — worker Celery (durées, pas timestamps)

Ces valeurs sont retournées dans le résultat Redis par le worker Celery (processus séparé).

| Colonne | Description |
|---------|-------------|
| `P4_4_ms` | Attente micro-batch (entre création tâche et déclenchement worker Celery). |
| `P5_1_ms` | Attente provider disponible (polling load balancer, jusqu'à 60s si saturé). |
| `P5_3_ms` | Construction du prompt (merge batch + rendu template + schema JSON). |
| `P5_4_ms` | Appel LLM provider (réseau + inférence + retries éventuels). |
| `P5_5_ms` | Démuxage + persistance Redis + publication Pub/Sub `task_done:{id}`. |

---

### Retour résultat & publication GAMA

| Timestamp | Relevé | Description |
|-----------|--------|-------------|
| `T_extract_end` | Après extraction `chosen_index` + remapping | `T_extract_end - T_llm_result` ≈ durée d'extraction et de remapping vers l'index original (post-shuffle). |
| `T_enqueue` | Après `self._messages.append(Action(...))` | `T_enqueue - T_extract_end` ≈ durée construction `PersonMove` + MoveLogger I/O + enqueue. |
| `T_fin` | Après l'envoi WebSocket dans `publish_loop()` | `T_fin - T_enqueue` ≈ attente publication WebSocket (retry infini toutes 1s si déconnecté). |

**Durée totale** : `T_fin - T0` (millisectets : `(T_fin - T0) * 1000`).

---

## Colonnes CSV

Un fichier par run de simulation — une ligne = un agent LLM par cycle de scheduling.

| Colonne | Type | Description |
|---------|------|-------------|
| `agent_id` | string | Identifiant de l'agent GAMA |
| `sim_time` | int | Horloge simulation envoyée par GAMA (secondes) |
| `T0` | float | Timestamp Unix — début du handler `/sync` |
| `T_parse` | float | Timestamp Unix — fin du parsing JSON/Pydantic |
| `T_flag` | float | Timestamp Unix — fin du filtrage agents éligibles |
| `T_otp_start` | float | Timestamp Unix — avant `trip_helper.get_itineraries()` |
| `T_otp_end` | float | Timestamp Unix — après `trip_helper.get_itineraries()` |
| `T_ltm_start` | float\|null | Timestamp Unix — avant ChromaDB (null si LTM désactivée) |
| `T_ltm_end` | float\|null | Timestamp Unix — après ChromaDB |
| `T_llm_start` | float | Timestamp Unix — avant `LLMGatewayClient.execute()` |
| `T_llm_sent` | float | Timestamp Unix — après POST tâche soumise |
| `T_llm_result` | float | Timestamp Unix — après retour long-poll |
| `T_extract_end` | float | Timestamp Unix — après extraction + remapping résultat |
| `T_enqueue` | float | Timestamp Unix — après enqueue `PersonMove` |
| `T_fin` | float | Timestamp Unix — après envoi WebSocket à GAMA |

Celery worker durations (kept as-is, separate process)
| `P4_4_ms` | float | Durée attente micro-batch (ms, depuis worker Celery) |
| `P5_1_ms` | float | Durée attente provider disponible (ms) |
| `P5_3_ms` | float | Durée construction prompt (ms) |
| `P5_4_ms` | float | Durée appel LLM provider, retries inclus (ms) |
| `P5_5_ms` | float | Durée démuxage + persistance Redis + Pub/Sub (ms) |

Others
| `P5_llm_provider` | string | Nom du provider LLM utilisé |
| `P5_llm_retries` | int | Nombre de retries LLM |
| `P5_tokens_in` | int | Tokens d'entrée |
| `P5_tokens_out` | int | Tokens de sortie |
| `plan_selected_index` | int | Index du plan sélectionné (dans la liste originale non mélangée) |
| `selection_method` | string | Méthode de sélection (`LLM` / `Un seul itinéraire disponible` / fallback) |

---

## Calculs notebook recommandés

```python
df["parse_ms"]    = (df["T_parse"]       - df["T0"])          * 1000
df["flag_ms"]     = (df["T_flag"]        - df["T_parse"])      * 1000
df["gap_otp_ms"]  = (df["T_otp_start"]   - df["T_flag"])       * 1000  # délai asyncio task
df["otp_ms"]      = (df["T_otp_end"]     - df["T_otp_start"])  * 1000
df["ltm_ms"]      = (df["T_ltm_end"]     - df["T_ltm_start"])  * 1000  # NaN si LTM off
df["llm_post_ms"] = (df["T_llm_sent"]    - df["T_llm_start"])  * 1000
df["llm_wait_ms"] = (df["T_llm_result"]  - df["T_llm_sent"])   * 1000
df["extract_ms"]  = (df["T_extract_end"] - df["T_llm_result"]) * 1000
df["enqueue_ms"]  = (df["T_enqueue"]     - df["T_extract_end"])* 1000
df["ws_ms"]       = (df["T_fin"]         - df["T_enqueue"])    * 1000
df["total_ms"]    = (df["T_fin"]         - df["T0"])           * 1000
```

---

## Notes d'implémentation

- `T0` et `T_parse` sont relevés dans `application.py::sync()` et propagés jusqu'à `PipelineLogger.begin()` via `_t_sync` / `_t_parse`.
- `T_flag` est relevé dans `schedule_person_move()` après la boucle de filtrage, avant `asyncio.create_task()`.
- `T_otp_start` / `T_otp_end` sont relevés dans `_compute_move_for_activity()` autour de `trip_helper.get_itineraries()`.
- `T_ltm_*` sont relevés dans `build_travel_plan_payload()` si `long_term_memory_enabled`.
- `T_llm_*` et `T_extract_end` sont relevés dans `evaluate_and_choose_travel_plan()`.
- `T_enqueue` est relevé dans `_schedule_one()` via `PipelineLogger.mark_enqueued()`.
- `T_fin` est relevé dans `publish_loop()` via `PipelineLogger.complete()`.
- Les colonnes P5 viennent du champ `timing_p5` du résultat Redis, peuplé par `task_worker.py`.
- `gap_otp_ms` peut être significatif sous forte charge : un grand nombre d'agents éligibles simultanément retarde les tâches asyncio les plus tardives.
