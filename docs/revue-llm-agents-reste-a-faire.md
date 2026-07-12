# Revue de code `llm-agents` — points restants

Issu de la relecture complète du module `llm-agents` (~11 700 lignes) du 2026-07-07.
Les 4 correctifs prioritaires sont déjà appliqués (cf. [changelog](changelog.md) du 2026-07-07) :
crash de `publish_loop`, persistance LTM, annulation du worker sur ré-init, clé de cache OTP
avec `include_bike`.

**Mise à jour 2026-07-08** : les points #5–#10 (bugs secondaires) et #11–#14 (optimisations)
sont implémentés (cf. changelog du 2026-07-08). Restent ouverts : **#15, #16**.

Ce document liste les points de la revue, classés par nature. Les numéros (#5–#16)
correspondent à la liste de tâches de la session de revue.

---

## Bugs secondaires

### ✅ #5 — NameError `storage_context` dans le fallback sans ChromaDB (fait le 2026-07-08)
**Fichier** : `llm-agents/llm/longterm.py` (~ligne 184, `_init_shared_index`)

Dans la branche fallback (pas de vector store **et** pas d'index existant sur disque),
`VectorStoreIndex.from_documents([], storage_context=storage_context, ...)` référence une
variable `storage_context` jamais définie dans ce chemin → `NameError`.
Ne se déclenche que si ChromaDB n'est pas importable (fallback "simple storage").

### ✅ #6 — TypeError `include_bike` en mode SOLARI + récursion (fait le 2026-07-08)
**Fichier** : `llm-agents/trip_helper/cached_triphelper.py` (~ligne 335 vs ~ligne 212)

`CachedTripHelper.get_itineraries` appelle `self.do_get_iteraries(..., include_bike=...)`,
mais la variante `do_get_iteraries_v1` (sélectionnée quand `gtfs.recursion_search_depth > 0`)
n'accepte pas ce kwarg → `TypeError` systématique dans cette configuration.
Ajouter le paramètre à la signature v1 (ou accepter `**kwargs`).

### ✅ #7 — Move perdu sur échec de push WebSocket (fait le 2026-07-08)
**Fichier** : `llm-agents/urban_mobility_agents/simulation_controller.py` (`_push_planned_move`, ~ligne 620)

Sur échec d'envoi WebSocket :
- `next_planned_move` a déjà été mis à `None` (réservation atomique) et n'est **pas restauré**
  → le trajet calculé (LLM + OTP) est perdu et sera recalculé de zéro par le scan de fallback ;
- `start_on_activity` a déjà avancé le scheduler avant le push, et le rollback ne remet que
  `heading_to`/`cache_current_activity` → état scheduler incohérent.

Correctif attendu : restaurer `next_planned_move = move` dans le rollback et remettre l'état
scheduler cohérent.

### ✅ #8 — Cache sémantique LLM : commentaire et code contradictoires (fait le 2026-07-08)
**Fichier** : `llm-agents/llm/cache.py` (`_lookup_sync`, ~lignes 150–167)

Le commentaire explique qu'« on ne rejette plus sur le score » (le filtre déterministe
agent + activity + time_slice + state_hash identifie déjà le contexte, et la LTM évolue
entre les runs, faisant chuter la similarité), mais le code rejette toujours
`best.score < self._threshold` (0,95) → miss `below_threshold` visibles dans les stats.
Décider et aligner : probablement supprimer le rejet par seuil, conformément à l'intention
documentée. Au passage : l'annotation de retour de `_lookup_sync` est fausse
(`Optional[dict]` alors qu'elle retourne un tuple `(résultat, raison)`).

### ✅ #9 — Métrique `AGENT_SCHEDULING_LAG` fausse au passage de minuit (fait le 2026-07-08)
**Fichier** : `llm-agents/urban_mobility_agents/simulation_controller.py` (~lignes 560–562)

`_send_time24h - _target_24h` soustrait deux horaires mod 86 400 sans gérer le wrap :
un envoi à 00:05 pour une cible 23:55 donne −85 800 s au lieu de +600 s.
Normaliser le delta dans [−43 200, +43 200] : `((d + 43200) % 86400) - 43200`.

### ✅ #10 — Logs loguru au format `%s` + traces `[trace]` à retirer (fait le 2026-07-08)
**Fichiers** :
- `llm-agents/handle/application.py` (~lignes 312 et 314) : `logger.warning("... %s", exc)` —
  loguru utilise `{}`, pas `%s` ; le message s'affiche littéralement sans le contenu de
  l'exception.
- Logs marqués `[trace] à retirer` encore en place :
  `urban_mobility_agents/factory/factory.py` (`init_static_data`),
  `trip_helper/cached_triphelper.py` (`OtpCachedTripHelper.__init__` + premier appel),
  `handle/application.py` (`_init_osmnx_cache`).

---

## Optimisations

### ✅ #11 — Persistance LTM coûteuse (O(N²)) et requêtes surdimensionnées (fait le 2026-07-08)
**Fichier** : `llm-agents/llm/longterm.py`

- `_save_user_metadata` est appelé à **chaque** `aadd_memory` : double sérialisation JSON
  (une pour mesurer la taille, une pour écrire) + réécriture du fichier complet à chaque
  entrée → coût quadratique au fil de la simulation, en I/O synchrone dans l'event loop.
  Pistes : écrire en différé (flush périodique / à l'éviction LRU), sérialiser une seule fois.
- `aquery_user_memories` récupère jusqu'à `min(top_k × 100, 500)` nœuds globaux puis filtre
  par `person_id` en Python — exécuté à chaque décision de trajet de chaque agent LLM.
  ChromaDB supporte le filtrage par métadonnées côté requête (`where={"person_id": ...}`).
- Remplacer les nombreux `print()` par loguru (dont un par requête LTM :
  "Retrieved N raw nodes").

### ✅ #12 — I/O fichier synchrones dans l'event loop (fait le 2026-07-08)
**Fichiers** : `urban_mobility_agents/utils/move_logger.py` (`MoveLogger.log_move`,
`GamaArrivalsLogger.log_arrival`), `urban_mobility_agents/agents/llm_agent.py`
(`log_llm_cache_hit`, ~ligne 58), `handle/application.py` (`_AgentStateLog.record`).

Écritures fichier bloquantes (open/write) appelées dans des coroutines à chaque événement.
Sous charge (heures de pointe), chaque écriture bloque toutes les coroutines.
Passer par `asyncio.to_thread` ou un writer bufferisé avec flush périodique.

### ✅ #13 — `ClientSession` aiohttp créée par requête OSMnx HTTP (fait le 2026-07-08)
**Fichier** : `llm-agents/trip_helper/osmnx_direct.py` (`_get_direct_plan_http`, ~ligne 499)

Une `aiohttp.ClientSession` est créée puis fermée à chaque requête vers les réplicas osmnx.
Réutiliser une session partagée (avec `TCPConnector` limité), comme le fait
`OTPTripHelper.get_session()`.

### ✅ #14 — Tâches fire-and-forget sans référence conservée (fait le 2026-07-08)
**Fichiers** : `trip_helper/cached_triphelper.py` (`store_async`, `blacklist_add_async`),
`trip_helper/osmnx_direct.py` (stores du cache persistant), `urban_mobility_agents/agents/llm_agent.py`
(store du cache sémantique — partiellement traité via `add_done_callback`).

`asyncio.create_task(...)` sans référence conservée : Python peut garbage-collecter la task
avant son exécution (avertissement documenté d'asyncio). Conserver un `set` de références
avec `task.add_done_callback(refs.discard)`.

---

## Code mort (suppression sûre)

### #15 — Suppressions
Vérifié par recherche de références sur tout le repo (hors notebooks) :

| Emplacement | À supprimer |
|---|---|
| `llm-agents/api/` (package entier) | Cassé (importe `create_json_logger` qui n'existe plus, et `simulation` inexistant) et plus branché nulle part |
| `llm-agents/gama_models.py` | `PeopleNextMoveRequest`, `PeopleBatchNextMoveRequest`, `ObservationUpdateRequest`, `ObservationBatchUpdateRequest`, `DailyCronRequest` (utilisés uniquement par l'api morte) |
| `llm-agents/server.py` | Lanceur legacy qui démarre `llm_module.main:app` en h11 — le compose utilise `hypercorn handle.application:app` |
| `llm-agents/backup_helper.py` | Seul consommateur : `server.py` |
| `llm-agents/urban_mobility_agents/agents/llm_agent.py` | `parse_response_json`, `log_chat` (ère pré-structured-output) + imports `demjson3`, `traceback`, `re`, `time_to_bucket_text` ; imports en double (`loguru` ×2, `typing` ×3, `import asyncio` local) |
| `llm-agents/helper.py` | `to_24h_timestamp`, `time_window_generalize`, `lower_first_char`, `format_route_id` (remplacé par `get_transit_route_short_name`) |
| `llm-agents/world/population.py` | `PersonScheduler.next_activity` (doublon de `next_upcoming_activity`), `dump_population_state`/`load_population_state` (state_file plus écrit), `get_llm_based_people_list` |
| `llm-agents/trip_helper/otp.py` | `revert_fixed_date` (stub qui retourne 0), variables `d` inutilisées dans `_timed_otp`/`_timed_osmnx` |
| `llm-agents/llm/longterm.py` | `aexport_user_data`, `get_system_stats`, `force_cleanup_all_users`, `get_memory_usage_breakdown`, blocs commentés Qdrant/Pinecone (~40 lignes) |
| `llm-agents/utils.py` | `square_distance`, `random_name`, `random_choices` |
| `llm-agents/world/world_data.py` | Classe `WorldTime` |
| `llm-agents/errors.py` | `MoveNotFoundExeption` (typo incluse — utilisé uniquement par l'api morte) |
| `llm-agents/urban_mobility_agents/simulation_controller.py` | `trigger_long_term_reflection_for_all` (appelle `reflect_on_long_term_memory` avec une mauvaise signature → TypeError latent), branche morte `else -amount` dans `reschedule_amount`/`_v2` (le `return 0` en tête rend la condition toujours vraie), params `_t_sync`/`_t_parse` de `sync` jamais lus |
| `llm-agents/urban_mobility_agents/factory/factory.py` | `stop_filter` construit puis jeté (`filters=[]`) |
| `llm-agents/handle/websocket.py` | Import `from fastapi import WebSocket` inutilisé |
| `llm-agents/settings.py` | `force_reload_paths` (alias strict de `force_reload`), `agent.long_term_reflect_interval` (legacy, non lu) |

### #16 — Nettoyages divers
- **`@app.on_event` déprécié** (`handle/application.py`) → migrer vers le pattern `lifespan`.
- **Type hints faux** (`helper.py`) : `get_weekday_category` et `categorize_date_time_short`
  annotées `-> int` mais retournent des `str`.
- **Incohérence de fuseau horaire** : `to_timestamp_based_on_day` fait un floor de jour en
  base UTC (`ts // 86400`) alors que le reste du code utilise `datetime.fromtimestamp`
  (local) et que la météo utilise Europe/Paris. Correct uniquement si les conteneurs
  tournent en TZ=UTC — à documenter ou unifier.
- **Cache sémantique Qdrant sans éviction** (`llm/cache.py`) : `store` upsert avec un
  `uuid4` neuf à chaque écriture — deux décisions identiques créent deux points, croissance
  non bornée. Prévoir une clé déterministe (dédup) et/ou une politique d'éviction.
- **`publish_loop` en polling 1 s** (`handle/application.py`) : remplacer par un
  `asyncio.Event` signalé quand `_messages` se remplit (mineur — la boucle ne sert plus que
  le chemin bootstrap).
- **Contamination du purpose dans le cache OTP** (mineur) : les plans stockés par
  `store_async` portent le `purpose` du premier demandeur (mutation avant que la task
  d'écriture s'exécute) — sans conséquence car le contrôleur réécrit `purpose` sur chaque
  hit, mais fragile si ce comportement change.

---

## Ordre suggéré

1. **#5–#8** : correctifs courts et localisés (bugs secondaires).
2. **#9–#10** : métrique + hygiène des logs (trivial).
3. **#15** : suppression du code mort (gros diff mais sans risque, à faire dans un commit dédié).
4. **#11–#14** : optimisations (chacune mesurable, à valider sous charge).
5. **#16** : divers au fil de l'eau.
