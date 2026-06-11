# Architecture mémoire : STM et LTM

Ce document décrit en détail le système de mémoire à deux niveaux des agents : la mémoire court terme (STM) et la mémoire long terme (LTM). Il couvre les structures de données, les algorithmes, la pipeline de consolidation, et illustre chaque étape avec des exemples tirés des logs réels.

---

## Vue d'ensemble

Chaque agent dispose d'une mémoire organisée en trois niveaux fonctionnels :

```text
┌──────────────────────────────────────────────────────────────────────────┐
│  STM — RAM Python (UserShortTermMemory)                                  │
│  Buffer FIFO circulaire, max 100 entrées par agent, partitionné par      │
│  activity_id. Alimenté à chaque décision de planification et             │
│  observation GAMA (transfer, wait, transit, arrival).                    │
└────────────────────────────┬─────────────────────────────────────────────┘
                             │  ≥ stm_reflection_min_entries (défaut : 10)
                             │  Appel LLM → réflexion + extraction concepts
                             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  LTM — ChromaDB (MultiUserLongTermMemory)                                │
│  Index vectoriel partagé (cosine HNSW), métadonnées JSON shardées        │
│  sur disque. Contient réflexions, concepts, résumés. Requêté via         │
│  score composite (similarité + BLEU + décroissance temporelle).          │
└────────────────────────────┬─────────────────────────────────────────────┘
                             │  tous les long_term_self_reflect_interval_days
                             │  Appel LLM → consolidation de patterns
                             ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  LTM Self-reflection — Synthèses multi-jours                             │
│  Résumés de haut niveau (habitudes durables, tendances). Stockés         │
│  comme entrées SUMMARY dans la même collection ChromaDB.                 │
└──────────────────────────────────────────────────────────────────────────┘
```

Le cache sémantique LLM (`LlmSemanticCache`) est un système **orthogonal** : il met en cache les **décisions** (index d'itinéraire choisi), pas les souvenirs. Il est décrit dans [cache-memory.md](cache-memory.md).

---

## Mémoire court terme (STM)

### Structure

**Fichier :** `llm-agents/llm/shortterm.py` — classe `UserShortTermMemory`

```python
class UserShortTermMemory:
    person_id: str
    recent_entries: List[MemoryEntry]   # anneau FIFO, max 100
    max_entries: int = 100
    last_activity: datetime
```

Chaque entrée est un `MemoryEntry` (`llm-agents/llm/memory.py`) :

```python
@dataclass
class MemoryEntry:
    content: str           # texte libre
    timestamp: datetime
    memory_type: MemoryType   # CONVERSATION | REFLECTION | CONCEPT | SUMMARY
    person_id: str
    activity_id: Optional[str]   # UUID de l'activité GAMA (clé de partition)
    tags: Optional[str]          # mots-clés pour le scoring BLEU en LTM
```

### Alimentation du buffer

Deux sources écrivent dans la STM :

| Source | Méthode | Contenu |
|--------|---------|---------|
| Décision de planification | `add_message()` | `[ TRAVEL_PLAN ] Plan to head <work> …` |
| Observation GAMA enrichie météo | `add_message()` | `[ transfer ] 08:32, Arrêt Capitole, 18°C, Pluie 2mm …` |

La météo est injectée avant stockage selon la tranche horaire de la simulation (4 tranches : nuit / matin / midi / soir). Les précipitations ne sont incluses que si `precip_mm > 0`.

**Exemple réel** (`agent_memory_events.csv`, 2026-03-16 06:00:01, agent `387324`) :

```
context          | timestamp  | datetime             | person_id | activity_id                          | message
shortterm_memory | 1773637201 | 2026-03-16 06:00:01  | 387324    | 63ef6b85-810e-57aa-a59d-8a18b0a06a6f | [ TRAVEL_PLAN ] Plan to head <work> served from LLM cache.
                                                                                                         Durée estimée : 24 minutes. Distance : 19.7 km.
                                                                                                         Reasoning: Décision récupérée depuis le cache sémantique LLM.
```

### Gestion du buffer FIFO

```python
def add_message(self, msg, timestamp, activity_id):
    entry = MemoryEntry(content=msg, ...)
    self.recent_entries.append(entry)
    if len(self.recent_entries) > self.max_entries:
        self.recent_entries = self.recent_entries[-self.max_entries:]
```

Les 100 entrées les plus récentes sont conservées. Dès que le seuil de réflexion est atteint, le batch consolidé est supprimé du buffer (`remove_batch()`), ce qui libère de la place sans jamais tronquer arbitrairement un contexte d'activité en cours.

### Groupement par `activity_id`

Avant d'envoyer les entrées au LLM de réflexion, la méthode `get_all_message_and_group()` partitionne le buffer en **groupes cohérents par activité** :

```python
def get_all_message_and_group(self):
    results = []
    buffer = []
    for entry in self.recent_entries:
        if buffer and entry.activity_id != buffer[-1].activity_id:
            results.append(buffer)
            buffer = []
        if entry.activity_id:
            buffer.append(entry)
        else:
            results.append([entry])   # entrée sans contexte d'activité
    if buffer:
        results.append(buffer)
    return results, all_entries
```

Un groupe = toutes les observations et décisions d'un même déplacement (de la maison au travail, par exemple). Le LLM de réflexion reçoit chaque groupe comme contexte structuré.

---

## Consolidation STM → LTM

### Déclenchement

La consolidation est **volumétrique**, pas temporelle. Elle se déclenche dans `simulation_controller.py::trigger_short_term_reflection_for_all_people()` quand :

```
len(stm.recent_entries) >= settings.agent.stm_reflection_min_entries   # défaut : 10
```

### Pipeline de réflexion

```text
[STM buffer ≥ 10 entrées]
└── get_all_message_and_group()          → liste de groupes par activity_id
└── Formatage payload JSON
    └── {
          "category": "stm_reflection",
          "agents": [{
            "agent_id": person_id,
            "perception": <profil narratif de l'agent>,
            "context": <JSON des groupes d'expériences>,
            "departure_timestamp": <timestamp>
          }]
        }
└── llm_client.execute_async()           → prompt : stm_reflection.md.j2
    ← {
        "reflection": "Aujourd'hui j'ai alterné...",
        "concepts": [
          ["contenu", "mots-clés", "scope spatial", "scope temporel", "objectif"],
          ...
        ]
      }
└── aadd_memory(MemoryEntry(type=REFLECTION, content=reflection))
└── Pour chaque concept → aadd_memory(MemoryEntry(type=CONCEPT, content=concept_json))
└── stm.remove_batch(entries_traitées)
```

### Format des concepts (5-tuple)

Chaque concept extrait est un tableau JSON de 5 éléments :

```json
["contenu de la connaissance", "mots-clés", "portée spatiale", "portée temporelle", "objectif"]
```

**Exemples réels** (agent `544611`, 2026-03-16 06:15:00) :

```
["Le bus 401 arrive généralement à l'heure", "bus 401, ponctualité", "Bus 401", "quotidien", "prévoir moins de marge pour les trajets courts"]
["Les segments de marche sont toujours de 5 minutes entre Banayre et le point d'arrêt", "marche, durée constante", "Banayre ↔ arrêt", "quotidien", "intégrer marche dans le calcul total"]
["Les trajets vers des lieux éloignés nécessitent un buffer supplémentaire", "trajet long, marge", "8 mai 1945", "occasionnel", "ajouter 5‑10 minutes de sécurité"]
["Les estimations de temps du cache sont très proches de la réalité", "estimation, précision", "travels plan cache", "quotidien", "continuer à se fier aux prévisions LLM"]
["Planifier les retours après l'école en tenant compte du bus 401 qui peut varier d'une minute", "retour, variation bus", "Lycée Fonsorbes", "quotidien", "prévoir une minute supplémentaire"]
```

Et la réflexion narrative correspondante :

```
Aujourd'hui j'ai fait plusieurs allers‑retours entre la maison, le lycée Fonsorbes et mon petit boulot.
Le matin, à 07h45, j'ai pris le bus 401 pour aller au travail. Le trajet prévu était de 12 minutes
(5 min de marche + 5 min de bus + 2 min de marche) et je suis arrivée à l'heure, le bus était ponctuel.
[…] En résumé, le bus 401 est généralement fiable, les temps de marche sont constants, mais les trajets
plus longs demandent un buffer de 5‑10 minutes.
```

---

## Mémoire long terme (LTM)

### Infrastructure

**Fichier :** `llm-agents/llm/longterm.py` — classe `MultiUserLongTermMemory`

| Composant | Technologie | Rôle |
|-----------|-------------|------|
| Index vectoriel | ChromaDB (`hnsw:space=cosine`) | Recherche par similarité |
| Modèle d'embedding | `all-MiniLM-L6-v2` (384 dim) | Vectorisation des textes |
| Métadonnées | JSON shardés sur disque (100 shards par hash MD5) | Entrées complètes, scoring |
| Cache LRU | Dict Python, max 200 utilisateurs | Évite les I/O disque répétitifs |

### Organisation des données

Un seul index ChromaDB est partagé entre tous les agents (une seule collection `memory_collection`). ChromaDB ne supporte pas de filtre pré-retrieval sur les métadonnées dans cette configuration, donc l'isolation est purement **post-retrieval** : le retriever demande `min(top_k × 100, 500)` candidats globaux, puis on filtre manuellement par `person_id`. Conséquence : plus la LTM est peuplée d'agents, plus les 500 candidats bruts sont dilués — la qualité du recall par agent diminue si le nombre d'entrées total est très élevé. L'isolation se fait via le champ `person_id` dans les métadonnées du document :

```python
Document(
    text=str(entry.content),
    metadata={
        "person_id": person_id,
        "timestamp": entry.timestamp.isoformat(),
        "memory_type": entry.memory_type,   # "reflection" | "concept" | "summary"
        "namespace": f"user_{person_id}",
        "doc_id": f"{person_id}_{index}",
        "tags": entry.tags,                 # chaîne CSV de mots-clés
    }
)
```

Les métadonnées JSON par agent (liste des entrées, dates de cleanup/réflexion) sont shardées :

```
long_term_memory/
├── chroma_db/          ← index vectoriel ChromaDB
└── user_metadata/
    ├── shard_00/
    │   └── 387324.json
    ├── shard_01/
    │   └── 1170603.json
    └── ...             ← 100 shards (hash MD5 % 100)
```

### Cache LRU des métadonnées

Pour 1 000+ agents simultanés, le chargement/sauvegarde JSON de chaque agent à chaque requête serait prohibitif. Le cache LRU maintient en RAM les métadonnées des 200 agents les plus récemment actifs :

```python
def _cleanup_metadata_cache(self):
    if len(self.user_metadata) <= self.max_loaded_metadata:  # 200
        return
    sorted_users = sorted(self.metadata_access_times.items(), key=lambda x: x[1])
    for person_id, _ in sorted_users[:users_to_remove]:
        self._save_user_metadata(person_id)   # flush sur disque
        del self.user_metadata[person_id]
    gc.collect()
```

---

## Algorithme de récupération (retrieval)

### Étape 1 — Pré-filtrage ChromaDB

```python
retriever = self.shared_index.as_retriever(
    similarity_top_k=min(top_k * 100, 500)   # récupère 500 candidats max
)
nodes = await retriever.aretrieve(query)
```

ChromaDB retourne jusqu'à 500 voisins (HNSW cosine). Ils sont ensuite filtrés par `person_id` pour l'isolation agent, puis par fenêtre temporelle :

| Filtre | Condition | Activé par |
|--------|-----------|------------|
| Isolation agent | `node.metadata["person_id"] == person_id` | Toujours |
| Fenêtre passée | `delta_days <= max_past_days` (défaut : 30) | `long_term_max_days_query` |
| Jour ouvré | week-day query ↔ week-day entrée | `long_term_filter_by_datetime` |

### Étape 2 — Score composite

```python
combined_score = (
    _sim_score       × sim_score_weight    +   # 0.4
    _imp_score       × keyword_weight      +   # 0.3
    _time_decay_score × time_decay_weight      # 0.3
)
```

Chaque composante est normalisée min-max avant la combinaison :

```python
def _normalize_score(a):
    if a.max() == a.min(): return np.zeros_like(a)
    return (a - a.min()) / (a.max() - a.min())
```

#### Composante 1 — Similarité cosine (`sim_score`, poids 0.4)

Score brut fourni par ChromaDB (distance cosine dans l'espace 384-dim de `all-MiniLM-L6-v2`).

#### Composante 2 — Score BLEU sur mots-clés (`imp_score`, poids 0.3)

Mesure le chevauchement lexical entre la requête et le champ `tags` de l'entrée mémoire. Utilise des unigrammes (poids 0.7) et des bigrammes (poids 0.3) :

```python
def _bleu_score(self, query: str, keyword: str) -> float:
    kw_tokens  = keyword.lower().split()
    q_tokens   = query.lower().split()

    unigram_score = |kw_unigrams ∩ q_unigrams| / |kw_unigrams|
    bigram_score  = |kw_bigrams  ∩ q_bigrams | / |kw_bigrams |

    return 0.7 * unigram_score + 0.3 * bigram_score
```

**Exemple :** requête `"bus 401 ponctualité matin"`, tags `"bus 401, ponctualité"` → unigramme overlap = 3/3 = 1.0, bigramme overlap = `{(bus,401)} ∩ {(bus,401),(401,ponctualité)} = 1` → score = 0.7 × 1.0 + 0.3 × 0.5 = **0.85**.

Les entrées sans `tags` (ex. réflexions narratives) reçoivent le score par défaut `long_term_retrieval__default_reflection_importance_score = 0.2`.

#### Composante 3 — Décroissance temporelle (`time_decay`, poids 0.3)

```python
def _time_decay_score(self, timestamp_str, query_at) -> float:
    decay = settings.agent.long_term_retrieval__time_decay  # 0.7
    time_diff = (query_at - int(timestamp.timestamp())) / 86400  # en jours
    return decay ** time_diff
```

| Ancienneté | Score brut |
|-----------|-----------|
| 0 jours   | 1.000     |
| 1 jour    | 0.700     |
| 3 jours   | 0.343     |
| 7 jours   | 0.082     |
| 14 jours  | 0.007     |

La demi-vie effective est d'environ **1,94 jours** (`log(0.5) / log(0.7)`).

### Étape 3 — Top-K final

```python
top_k_indices = np.argsort(combined_score)[-top_k:][::-1]
result = [user_results[i] for i in top_k_indices]
```

`top_k = long_term_max_entries_query` (défaut : 10). Ces 10 entrées sont sérialisées comme `history` dans le payload LLM.

---

## Auto-réflexion LTM

Tous les `long_term_self_reflect_interval_days` (défaut : 3 jours), un second appel LLM consolide la LTM elle-même :

```text
[Intervalle écoulé depuis last_reflection]
└── get_last_user_memories(from_date=now - self_reflect_window_days)
    └── Toutes les entrées LTM des 5 derniers jours
└── llm_client → prompt : ltm_self_reflection.md.j2
    ← Résumé de patterns, habitudes durables, tendances détectées
└── aadd_memory(MemoryEntry(type=SUMMARY, content=résumé))
└── user_metadata["last_reflection"] = now
```

L'entrée SUMMARY est stockée dans le même index ChromaDB et participe aux requêtes futures avec sa propre décroissance temporelle.

**Exemple réel** (agent `1396214`) :

```
Ma journée s'est déroulée sans accroc, en suivant mes habitudes de transport. J'ai effectué mon trajet
habituel [08:30 → work] en utilisant le métro B (~25 min). Le retour [18:00 → home] s'est également
bien passé en 22 minutes. Le métro B reste mon option la plus fiable pour éviter les aléas de la
circulation, surtout avec mon budget serré. Je continuerai à privilégier le métro pour la régularité,
tout en gardant ma voiture comme solution de secours si jamais il y a une grève ou un problème
technique sur la ligne.

→ Concepts stockés :
["Le métro B est le moyen le plus fiable pour mes trajets domicile-travail",
 "métro B, fiabilité, travail", "Ligne B", "quotidien", "optimisation trajet"]
["Les trajets en métro prennent environ 25 minutes en incluant la marche",
 "temps de trajet, marche, métro", "Faculté de Pharmacie, Canal du Midi", "quotidien", "gestion du temps"]
```

---

## Nettoyage et oubli

### Déclenchement automatique

Un agent qui dépasse 10 000 entrées LTM déclenche immédiatement un nettoyage avec seuil de 7 jours :

```python
if len(self.user_metadata[person_id]["entries"]) > 10000:
    self.cleanup_user_memories(person_id, days_threshold=7)
```

### Politique de rétention

```python
def cleanup_user_memories(person_id, days_threshold=30):
    cutoff_date = now - timedelta(days=days_threshold)
    for entry in entries:
        keep if (
            entry.timestamp > cutoff_date          OR
            entry.importance_score > 0.7           OR
            entry.memory_type in ["reflection", "summary"]
        )
```

Les réflexions et résumés sont **toujours conservés** indépendamment de leur âge. Seules les entrées CONCEPT ou CONVERSATION anciennes et sans importance élevée sont supprimées.

### Éviction LRU du cache RAM

Lorsque plus de 200 agents sont en RAM, les plus anciennement accédés sont flushés sur disque avant d'être retirés du dict Python, puis un `gc.collect()` libère la mémoire.

---

## Intégration dans la pipeline de décision

```text
evaluate_and_choose_travel_plan()
│
├─ 1. aquery_user_memories(person_id, query, top_k=10, max_past_days=30)
│      ↳ ChromaDB pré-filtre 500 candidats
│      ↳ Filtrage person_id + fenêtre temporelle
│      ↳ Score composite → top 10
│      ↳ Sérialisés en liste de strings → payload["history"]
│
├─ 2. Lookup cache sémantique (LlmSemanticCache)
│      ├─ HIT  → retourne l'index mémorisé, écrit en STM, fin
│      └─ MISS ↓
│
├─ 3. Appel LLM (gateway)
│      payload = {
│        "category": "itinary_multi_agent",
│        "agents": [{
│          "agent_id": person_id,
│          "perception": <profil narratif>,
│          "history": [...10 souvenirs LTM...],
│          "trajectories": [...options d'itinéraires...],
│          "departure_time": "08:30"
│        }]
│      }
│      ← {"chosen_index": 2, "reason": "..."}
│
├─ 4. asyncio.create_task(cache.store(...))   ← fire-and-forget
│
└─ 5. stm.add_message(plan_choisi, activity_id=...)  ← stockage STM
```

La LTM est **lue** avant la décision (contexte historique pour le LLM) mais **écrite** de manière asynchrone après la réflexion (pas sur le chemin critique). Le chemin critique de planification n'est bloqué que par le lookup ChromaDB (instrumenté via `ltm_query_duration_seconds`).

---

## Résumé des paramètres clés

| Paramètre | Défaut | Effet |
|-----------|--------|-------|
| `stm_reflection_min_entries` | 10 | Seuil de déclenchement de la réflexion |
| `long_term_max_entries_query` | 10 | Top-K renvoyé au LLM |
| `long_term_max_days_query` | 30 | Fenêtre de look-back en jours |
| `long_term_retrieval__sim_weight` | 0.4 | Poids similarité cosine |
| `long_term_retrieval__keyword_weight` | 0.3 | Poids score BLEU |
| `long_term_retrieval__time_weight` | 0.3 | Poids décroissance temporelle |
| `long_term_retrieval__time_decay` | 0.7 | Base de la décroissance (par jour) |
| `long_term_self_reflect_enabled` | true | Active l'auto-réflexion LTM |
| `long_term_self_reflect_interval_days` | 3 | Fréquence de l'auto-réflexion |
| `long_term_self_reflect_window_days` | 5 | Fenêtre de look-back pour l'auto-réflexion |

---

## Métriques associées

| Métrique | Description |
|----------|-------------|
| `ltm_query_duration_seconds` | Latence totale des appels `aquery_user_memories` (ChromaDB + re-ranking) |

Voir [agents-lifecycle.md](agents-lifecycle.md) pour le contexte d'appel dans le cycle de planification et [cache-memory.md](cache-memory.md) pour le cache sémantique LLM.
