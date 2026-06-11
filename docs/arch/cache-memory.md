# Cache et mémoire des agents

Deux mécanismes distincts coexistent : la **mémoire cognitive** des agents (qui simule leur vécu) et le **cache sémantique LLM** (qui évite les appels redondants).

---

## Mémoire cognitive — trois niveaux

```
[Événements de simulation et décisions]
└── Mémoire Court Terme (Python RAM — isolation par activity_id)
    └── Seuil atteint (stm_reflection_min_entries entrées dans le buffer)
        └── Appel gateway llm_module (catégorie stm_reflection)
            └── Réflexion narrative + concepts extraits
                └── Écriture en Mémoire Long Terme (ChromaDB — base vectorielle locale)
                    └── Index partagé / partitionnement logique par person_id
                        └── Self-reflection multi-jours (intervalle temps : long_term_self_reflect_interval_days)
                            └── Appel gateway llm_module (catégorie ltm_self_reflection)
```

### Court terme (STM)

- Stockée en RAM Python dans une liste ordonnée de `MemoryEntry`
- Isolation par `activity_id` : chaque activité a sa propre fenêtre contextuelle
- Purgée quand le buffer atteint **`stm_reflection_min_entries`** entrées (seuil configurable) — déclenchement par volume, pas par intervalle de temps
- Implémentation : `llm-agents/llm/shortterm.py`

### Long terme (LTM — ChromaDB)

- Base vectorielle locale ChromaDB, partitionnée logiquement par `person_id`
- Alimentée par la synthèse LLM des souvenirs court terme
- Activée via `long_term_memory_enabled: true` dans la config

#### Algorithme de récupération mémorielle

Lors de l'évaluation d'un itinéraire, les souvenirs sont extraits via un score composite normalisé :

$$\text{Score} = (\text{Similarité Cosinus} \times 0.4) + (\text{Score BLEU des mots-clés} \times 0.3) + (\text{Décroissance Temporelle} \times 0.3)$$

Les souvenirs récents et pertinents remontent dans le contexte LLM de l'agent.

- Implémentation : `llm-agents/llm/longterm.py`

---

## Cache sémantique LLM (LlmSemanticCache)

Le cache sémantique est **orthogonal à la mémoire cognitive** : il évite d'appeler le LLM quand une situation de mobilité similaire a déjà été évaluée, sans chercher à reproduire un raisonnement narratif.

```
[Évaluation d'un itinéraire]
└── Lookup : similarité cosinus sur le vecteur (options + historique + purpose)
    ├── Score ≥ semantic_threshold → retourne l'index de décision sans appel LLM
    │                                 (mode = "cache:<modes>")
    └── Score < threshold → appel LLM puis store asynchrone dans le cache
```

- Stockage : disque local dans `data/llm_cache/<population_name>/`
- Activation : `cache.enabled: true` dans la config d'expérience
- Le store post-inférence est **fire-and-forget** (n'alourdit pas le chemin critique)

### Quand le cache est-il pertinent ?

Le vecteur de lookup encode les **options de transport disponibles**, l'**historique récent** et le **but du déplacement**. Deux agents avec les mêmes options de transport, le même profil d'historique et le même but de déplacement reçoivent la même décision sans appel LLM supplémentaire.

---

## Cache des itinéraires (CachedTripHelper)

Le cache persistant d'itinéraires (`OtpPersistentCache`, SQLite) mémorise les itinéraires
par couple origine/destination/heure (`gtfs.otp_cache_enabled`, défaut `true`), les réutilise
à une heure de départ proche par décalage temporel, et blackliste les paires O/D sans
itinéraire ; la base est persistée par population dans `llm-agents/data/otp_cache/<population>/`.

Selon le mode de routage, deux câblages partagent le même `OtpPersistentCache` :

- **Mode `OTP` (principal)** : la factory enrobe `OTPTripHelper` dans **`OtpCachedTripHelper`**,
  un décorateur **fin** qui **ne change pas** la stratégie de recherche — sur un miss il
  délègue l'appel verbatim à OTP, puis stocke. Le cache s'intercale à la frontière
  appelant → helper (`_compute_move_for_activity`), où les requêtes utilisent toujours les
  paramètres par défaut. Le cache est initialisé par population dans `handle.application`
  (`init_otp_persistent_cache`).
- **Mode `SOLARI` (historique)** : `CachedTripHelper` enrobe `SolariTripHelper` et applique
  en plus une stratégie de recherche élargie sur un miss (`do_get_iteraries_v2` : expansion
  multi-mode accès/sortie + dédup).

> ⚠️ **Approximation temporelle** : la clé bucketise l'heure de départ par tranches de
> 10 min et un itinéraire stocké est réutilisé à une heure proche par décalage des
> timestamps. Pour les segments TC, cela décale les horaires planifiés de ≤ 10 min (les
> mêmes que ceux du cache SOLARI historique). Si une reprise strictement exacte est requise,
> passer la clé sur l'heure exacte (sans décalage).

Le routage direct OSMnx (marche/vélo/voiture) dispose, lui, de son propre cache persistant
**toujours actif** (`OsmnxPersistentCache`, `llm-agents/data/osmnx_cache/`).

---

## Cache des graphes OSMnx

Les graphes topologiques OSMnx (walk, bike, drive) sont téléchargés depuis OpenStreetMap au premier démarrage et mis en cache dans `data/osmnx_cache/`. Ce cache est persistant entre les redémarrages Docker (volume monté).

---

## Résumé des caches par couche

| Cache | Technologie | Persistance | Clé |
|-------|-------------|------------|-----|
| Mémoire LT agents | ChromaDB | Disque | `person_id` + embedding |
| Cache sémantique LLM | Disque local (Qdrant) | Disque | Vecteur (options + historique + purpose) |
| Itinéraires OTP | SQLite (`OtpPersistentCache`) | Disque | date + bucket 10 min + coords + mode |
| Routage direct OSMnx | SQLite (`OsmnxPersistentCache`) | Disque | coords + mode (+ date/heure pour la voiture) |
| Graphes OSMnx | Fichiers pickle | Volume Docker | Zone géographique + mode |

---

## Observabilité du taux de cache

Les trois caches de décision/routage exposent un **taux de hit** sous deux formes :

- **Logs** : une ligne `[cache] OTP X% (h/n) · OSMnx Y% (h/n) · LLM Z% (h/n)` est émise à la
  fin du warm-up (`bootstrap_all_agents`) et à chaque `[sync] START`. Une source affiche
  `off` quand elle n'a reçu aucune requête (cache désactivé ou non sollicité). Format
  construit par `_format_cache_hit_rates()` (`simulation_controller.py`), à partir des
  accesseurs `get_otp_cache_stats()`, `get_osmnx_cache_stats()`, `get_llm_cache_stats()`.
- **Prometheus** : gauges `trip_cache_hit_ratio` (OTP), `osmnx_cache_hit_ratio` (OSMnx)
  et compteurs `llm_cache_hits_total` / `llm_cache_misses_total` (LLM).

Les compteurs hits/lookups sont **process-wide** et cumulés depuis le démarrage : les
pourcentages convergent donc vers le taux global de la session.
