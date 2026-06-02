# Cache et mémoire des agents

Deux mécanismes distincts coexistent : la **mémoire cognitive** des agents (qui simule leur vécu) et le **cache sémantique LLM** (qui évite les appels redondants).

---

## Mémoire cognitive — trois niveaux

```
[Événements de simulation et décisions]
└── Mémoire Court Terme (Python RAM — isolation par activity_id)
    └── Vidage périodique (toutes les 6h de temps simulé)
        └── Inférence de synthèse LLM
            └── Écriture en Mémoire Long Terme (ChromaDB — base vectorielle locale)
                └── Index partagé / partitionnement logique par person_id
```

### Court terme (STM)

- Stockée en RAM Python dans une liste ordonnée de `MemoryEntry`
- Isolation par `activity_id` : chaque activité a sa propre fenêtre contextuelle
- Purgée toutes les **6h de temps simulé**, déclenchant une synthèse vers la LTM
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

En mode `SOLARI` (mode historique, alternatif à OTP), un cache d'itinéraires pré-calculés est utilisé via `CachedTripHelper`. En mode `OTP` (mode courant), les itinéraires sont calculés dynamiquement sans cache d'itinéraires.

---

## Cache des graphes OSMnx

Les graphes topologiques OSMnx (walk, bike, drive) sont téléchargés depuis OpenStreetMap au premier démarrage et mis en cache dans `data/osmnx_cache/`. Ce cache est persistant entre les redémarrages Docker (volume monté).

---

## Résumé des caches par couche

| Cache | Technologie | Persistance | Clé |
|-------|-------------|------------|-----|
| Mémoire LT agents | ChromaDB | Disque | `person_id` + embedding |
| Cache sémantique LLM | Disque local | Disque | Vecteur (options + historique + purpose) |
| Graphes OSMnx | Fichiers pickle | Volume Docker | Zone géographique + mode |
