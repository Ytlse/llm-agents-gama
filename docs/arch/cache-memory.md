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

Le cache est **hybride** : il se comporte différemment selon que l'agent a déjà vécu quelque chose ou non.

```
[Évaluation d'un itinéraire]
│
├── Filtre déterministe des conditions factuelles (toujours appliqué) :
│     agent_id + activity_id + catégorie de jour + tranche 10 min + hash(options, météo)
│   Toute différence ⇒ le cache est ignoré.
│
├── LTM vide (typiquement : tout le bootstrap)
│   └── Correspondance exacte (`scroll` clé-valeur, ~0,1 ms, aucun embedding)
│       ├── Trouvé → décision resservie
│       └── Sinon  → appel LLM, puis store avec `memory_empty=True`
│
└── LTM remplie
    └── Embedding de la LTM courante, puis similarité cosinus (`query_points`)
        contre les LTM des décisions stockées aux mêmes conditions
        ├── score ≥ `cache.semantic_threshold` → décision resservie
        └── score <  seuil (ou aucun candidat)  → appel LLM avec la LTM,
                                                   puis store avec `memory_empty=False`
```

Sans souvenir, deux décisions prises dans les mêmes conditions factuelles sont nécessairement identiques : l'embedding serait du calcul pur perte. Dès que l'agent a un vécu, ce vécu pèse sur sa décision, et le cache ne la resert que si la mémoire courante est proche de celle qui l'avait produite — **c'est ce qui permet à l'agent d'apprendre** au lieu de rejouer indéfiniment sa première décision.

Les deux familles de points sont **étanches** (`memory_empty` fait partie du filtre) : une décision prise sans souvenir n'est jamais resservie à un agent qui en a, et réciproquement.

### Ce qui est mis en cache : une distribution, pas une décision

Le LLM ne renvoie plus un itinéraire choisi mais une **probabilité par option**
(cf. `docs/arch/llm-inference.md`). C'est ce vecteur qui est persisté, dans le champ
`probabilities` du point Qdrant (`[{code, mode, p}, …]`, indexé par code de plan et non
par position).

Conséquence : **un hit ne resert pas une décision figée, il rejoue un tirage**. La graine
dérive de `(agent.mode_draw_seed, agent_id, activity_id, jour simulé)` — un même agent,
replacé dans le même contexte un autre jour, peut donc changer de mode sans qu'aucun appel
LLM ait lieu. Le cache économise l'inférence, pas la variabilité des comportements.

Deux cas particuliers :

- **options disparues** — les codes de plan absents des options courantes sont écartés et
  la masse restante est renormalisée ; s'il ne reste rien de tirable, le hit devient un
  miss (`code_not_in_options`) et le LLM est rappelé ;
- **points hérités** — les points écrits avant cette bascule ne portent que
  `chosen_plan_code` : ils sont resservis tels quels, sans tirage. En pratique, changer le
  prompt système change aussi le checksum d'isolation du cache, donc ces points vivent dans
  un répertoire distinct.

- Stockage : disque local dans `data/llm_cache/<checksum_prompt>/<population_name>/`
- Activation : `cache.enabled: true` dans la config d'expérience
- Le store post-inférence est **fire-and-forget** (n'alourdit pas le chemin critique)
- **Le payload LLM — et donc la requête ChromaDB de mémoire long terme — n'est construit
  que si l'agent a des souvenirs**, ou à défaut sur un miss. Le bootstrap (LTM vide) ne paie
  donc ni requête LTM ni embedding sur le chemin nominal.
- Les points `memory_empty=True` portent un vecteur neutre : ils ne sont relus que par filtre.
- **Accès sérialisé** : le client Qdrant embarqué (`QdrantClient(path=...)`) n'est pas
  thread-safe ; toutes les opérations base (`scroll`, `query_points`, `upsert`) passent sous
  un verrou dédié (`_db_lock`). Sans ce verrou, les lookups/stores concurrents lancés via
  `asyncio.to_thread` corrompent l'index (erreurs "operands could not be broadcast",
  erreurs SQLite) et le cache ne sert plus rien.
- **Alarme corruption** : après 5 erreurs Qdrant consécutives, une ligne
  `[ALARME] Cache LLM` (niveau ERROR, visible via `make error`) signale que la base est
  probablement corrompue et qu'il faut supprimer le répertoire de cache.

### Quand le cache est-il pertinent ?

La clé de lookup encode l'**agent**, l'**activité**, la **catégorie de jour** (semaine/week-end), la **tranche de 10 minutes**, les **options de transport disponibles** et la **météo** — plus, sur la branche sémantique, la **mémoire long terme** de l'agent. Un même agent replacé dans le même contexte de décision *et* avec un vécu comparable reçoit la même **distribution** sans appel LLM supplémentaire — le mode effectif, lui, est retiré au sort.

Corollaire : le cache est réutilisable d'un run à l'autre pour un scénario donné, mais une réflexion LTM qui change significativement le vécu d'un agent invalide ses décisions cachées — par construction.

> ⚠️ Le filtre inclut désormais `weekday` et `memory_empty`. Les caches produits avant cette
> évolution ne portent pas ces champs et ne seront jamais retrouvés : supprimer
> `data/llm_cache/` pour repartir proprement.

> Le cache n'a **aucun mode dégradé** : la clé de lookup est toujours appliquée dans son
> intégralité. En cas de panne LLM durable, la simulation **attend** le rétablissement
> (disjoncteur client, cf. `docs/arch/llm-inference.md` § « Panne durable ») plutôt que
> de servir des décisions sous contraintes relâchées.

> Le principe vaut aussi à l'**écriture** : un repli uniforme (vecteur LLM inexploitable,
> typé `UniformFallback` par `normalize_option_probabilities`) sert le trajet en cours
> mais n'est **jamais persisté** — `[cache] store refusé` dans les logs. Sans ce refus,
> le hasard d'un run devenait la « décision » servie à tous les runs suivants (constaté
> le 2026-08-03 ; assainissement : `scripts/cache/purge_uniform_fallback.py`).

### Mémoïsation des réflexions STM/LTM (ticket 012)

Les appels de **réflexion** obéissent à un régime distinct des décisions : le prompt
contient le vécu unique de l'agent, donc tout rapprochement (sémantique, inter-agents)
est interdit — mais un prompt **byte-identique** (re-run déterministe : décisions au
cache, tirages seedés, météo rejouée) est une fonction pure déjà payée.
`ReflectionMemoStore` (`llm/reflection_store.py`) mémoïse par SHA-256 du prompt
effectif (agent, identité, vécu, consignes, horodatage, paramètres LLM) dans
`reflections.sqlite`, à côté du cache de décisions — l'isolation par checksum de
prompt système est héritée du répertoire.

| | Décisions (`llm_decisions`) | Réflexions (`reflections.sqlite`) |
|---|---|---|
| Réutilisation | Contexte partagé (agent, activité, créneau, météo…) | **Exact uniquement**, jamais inter-agents |
| Branche sémantique | Oui (seuil cosinus) | **Non — par construction** |
| Contenu servi | Distribution → nouveau tirage | La réflexion telle que payée |
| Repli persisté | Jamais (`UniformFallback`) | Jamais (réflexion vide refusée) |

Un hit (`[reflection-memo] hit` dans les logs, compteur Prometheus
`agent_reflection_memo_total`) a des effets strictement identiques à un appel réel :
STM consommée, entrées REFLECTION/CONCEPT écrites en LTM. Désactivable via
`cache.reflection_memo_enabled`. Le taux de hit attendu est ~0 % sur un scénario
inédit et ~100 % sur le re-run d'un scénario épinglé — c'est la mesure de validation
du ticket 012 (A3).

### Cache LRU des métadonnées LTM

`MultiUserLongTermMemory` garde en mémoire les métadonnées des agents (`~3 Ko`/agent), plafonnées par `agent.long_term_max_loaded_metadata` (défaut **5000**). Ce plafond **doit rester au-dessus du nombre d'agents** : en dessous, le parcours round-robin des agents provoque une éviction — donc une relecture et une réécriture disque — à chaque décision. Aucun `gc.collect()` n'est déclenché à l'éviction (`_cleanup_metadata_cache` est appelé depuis l'event loop).

---

## Cache des itinéraires (CachedTripHelper)

Le cache persistant d'itinéraires (`OtpPersistentCache`, SQLite) mémorise les itinéraires
par couple origine/destination/heure (`gtfs.otp_cache_enabled`, défaut `true`), les réutilise
à une heure de départ proche par décalage temporel, et blackliste les paires O/D sans
itinéraire ; la base est persistée par population dans `llm-agents/data/otp_cache/<population>/`.
La clé de cache inclut les modes disponibles pour l'agent (`include_car` **et** `include_bike`) :
deux agents avec des équipements différents (avec/sans vélo) ne partagent jamais une entrée,
sinon l'option vélo pourrait manquer silencieusement dans les choix proposés au LLM.

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

> ⚠️ **Limitation connue — `fixed_day` et date absolue** : la clé du cache OTP inclut la
> **date simulée réelle** (`YYYY-MM-DD`), calculée avant le remapping `gtfs.fixed_day`
> effectué dans `OTPTripHelper`. Avec `fixed_day` actif, deux dates simulées différentes
> envoient pourtant la même requête à OTP (mêmes horaires GTFS) mais génèrent des clés
> distinctes : un cache réchauffé pour le jour J est donc **intégralement raté** pour une
> simulation au jour J+1. TODO (voir `OtpPersistentCache.make_key`) : baser la partie date
> de la clé sur la date fixe (ou le jour de semaine) quand `fixed_day` est actif, à l'image
> de la clé weekday d'`OsmnxPersistentCache`.

Le routage direct OSMnx (marche/vélo/voiture) dispose, lui, de son propre cache persistant
**toujours actif** (`OsmnxPersistentCache`, `llm-agents/data/osmnx_cache/`). La clé voiture
inclut le **jour de la semaine + tranche horaire** (granularité du facteur de congestion) mais
**pas la date absolue** : deux runs à des dates calendaires différentes mais même weekday
réutilisent les mêmes trajets. Marche/vélo sont indépendants du temps (coords + mode).
Combiné à la seed déterministe d'échantillonnage des agents
(`data.population_sample_seed`, défaut 42), rejouer une simulation retire exactement les mêmes
agents → mêmes trajets → hits de cache au lieu de recalculs.

Le cache est initialisé dans `_prepare_population` (`handle.application`) **avant** toute
opération de routage, si bien que le Pass 2 de génération de population (calcul des temps de
trajet pour l'ajustement des plannings) en bénéficie aussi : une régénération du fichier
population réutilise les routes déjà calculées au lieu de tout recalculer via OSMnx.

---

## Cache des graphes OSMnx

Les graphes topologiques OSMnx (walk, bike, drive) vivent dans `data/cache/osmnx/` (monté dans les
réplicas `osmnx` et le controller sous `/app/osmnx_cache`), sous la forme `graphs_<clé>.pkl` +
`boundary_<clé>.pkl`. **Depuis le 2026-09-03 (ticket 031, partie 2), le graphe servi au runtime est
celui du polygone des 453 communes** — clé `444ca7e6a515`, label
`perimetre_453_communes:cc1:osm-220101` (`geography.PERIMETER_CACHE_KEY`), 225 Mo, construit hors
ligne et sans téléchargement par `make osmnx-perimeter-graph` depuis les pbf OSM régionaux. La clé
se configure (`gtfs.osmnx_graph_key`, vide = polygone) ; un graphe absent est une **erreur explicite**
(`[ALARME]`, `GraphMissingError`), plus un téléchargement Overpass à sa place. Seul le graphe
historique du disque de 30 km (clé `ecb40f20a303`, `PRODUCTION_CACHE_KEY_30KM`) garde sa recette de
téléchargement, pour l'audit. Un changement des vitesses de `config/osmnx.yaml` se repose sur le
pickle avec `build_osmnx_perimeter_graph.py --respeed` (26 s, 2,6 Go de pointe) : le pickle porte
les vitesses de sa construction, la config seule ne suffit pas.

**Les caches d'itinéraires sont par population**, pas par graphe : le cache SQLite OSMnx
(`osmnx_persistent_cache_dir/<population>/`) et le cache OTP (`otp_persistent_cache_dir/<population>/`)
d'une population nouvelle partent vierges — la v4 n'a rien à purger. Mais la clé SQLite OSMnx ne
porte pas le graphe : une population déjà servie sur le disque de 30 km garderait ses durées (dont
les replis à 70 km/h des trajets de 3ᵉ couronne). C'est pourquoi **`routing_version` passe de `r1` à
`r2`** au changement de graphe et de vitesses vélo (`config/terminal_time.yaml`) : les anciennes
lignes restent lisibles pour audit, aucune n'est resservie.

---

## Résumé des caches par couche

| Cache | Technologie | Persistance | Clé |
|-------|-------------|------------|-----|
| Mémoire LT agents | ChromaDB | Disque | `person_id` + embedding |
| Cache sémantique LLM | Disque local (Qdrant) | Disque | Vecteur (options + historique + purpose) |
| Itinéraires OTP | SQLite (`OtpPersistentCache`) | Disque | **version des données** + date + bucket 10 min + coords + mode |
| Routage direct OSMnx | SQLite (`OsmnxPersistentCache`) | Disque, par population | **`routing_version`** (`r2`) + coords + mode (+ jour-de-semaine/heure pour la voiture) |
| Graphes OSMnx | Fichiers pickle | Volume Docker | Clé de graphe (`444ca7e6a515` = polygone des 453 communes) + mode |

### Version des données d'itinéraire dans les clés (ticket 013)

**Trois** caches survivent aux runs et étaient **aveugles** à un changement de définition
des durées d'itinéraire. Ils portent désormais tous les trois
`trip_helper.terminal_time.data_version()`, lu du champ `version:` de
`llm-agents/config/terminal_time.yaml` : **bumper cette version les invalide proprement**,
sans rien détruire — les anciennes lignes restent lisibles pour audit.

- **Routage OSMnx** — adressé par (mode, coordonnées, créneau). Le jour où le temps de
  stationnement est sorti de `duration_s`, il aurait continué à servir des durées calculées
  sous l'ancienne définition, indéfiniment.
- **Itinéraires OTP** — le plus lourd des trois, parce qu'il ne mémorise pas des durées mais
  les **`TravelPlan` sérialisés**, options voiture et vélo comprises (le cache s'intercale à
  la frontière appelant → helper, donc après l'assemblage transit + direct). Un cache chaud
  aurait resservi des plans à **une seule jambe**, portant l'ancien stationnement fondu dans
  la durée : le défaut du ticket 013 en entier, ressuscité après sa correction.
- **Décisions LLM** — le plus discret. `state_hash` est fait des `TravelPlan.get_code()`
  triés, c'est-à-dire de routes et d'arrêts : **insensible aux durées par construction**.
  Sans version, un run rejouerait tranquillement des décisions prises sur des options où la
  voiture était plus rapide qu'elle ne l'est — et **rien ne l'aurait signalé dans les logs**,
  puisque de son point de vue le contexte de décision est identique.

> Même famille de piège, fermée au ticket 014 : le **contexte d'anticipation** injecté dans
> le prompt (météo du jour, agenda glissant, position des véhicules) n'apparaît ni dans les
> codes d'options ni dans la météo du moment. Sa signature déterministe entre donc dans le
> `state_hash` via `extra_key` — deux agendas ou deux états de véhicules différents ne
> peuvent pas se servir mutuellement une décision. `extra_key` vide (anticipation
> désactivée) laisse le hash strictement identique à l'existant : le cache d'avant reste
> lisible à flag éteint.

### Couper le cache pour rendre un run rejouable — `make run CACHE=0`

Une décision servie par le cache **n'est jamais journalisée** : elle n'apparaît pas dans
`llm_exchanges.jsonl`, donc son prompt n'existe nulle part. Conséquence directe pour toute
mesure qui rejoue des décisions — A/B de prompt, plancher « prompt nu », ablation : elle ne
peut porter que sur les décisions ayant **raté** le cache.

Chiffré sur le run du 2026-08-27 : 6 735 décisions par la voie LLM, **76,4 % servies par le
cache**, et le journal ne portait que **377 des 3 249** décisions du périmètre scoré. Les
377 ne sont pas un échantillon : ce sont les plus atypiques du run, celles qu'aucune
décision voisine n'avait déjà couvertes.

`make run CACHE=0` bascule `cache.enabled` dans `llm-agents/config/config.yaml`, sur le
patron de `MEM=0`. `enabled: false` court-circuite entièrement le cache
(`self.llm_cache = None`) : il n'est ni lu ni écrit, et **il est donc inutile de le
supprimer** — les décisions déjà payées restent valides pour un run ultérieur.

Le coût est l'inverse exact du taux de service : **×4,24** sur ce run. En requêtes et en
tokens, 228 → ~967 et 1,2 M → ~5,2 M. Deux conséquences pratiques : sur des paliers
gratuits à 500 requêtes/jour, un run de 1 000 agents **force la bascule entre modèles**
— qui veut un plancher sur modèle unique doit réduire le périmètre ; et `make run CACHE=1`
doit suivre, sinon tous les runs ultérieurs paient le plein tarif sans que rien ne le
rappelle.

> **Troisième occurrence de la même famille, fermée le 2026-08-27 — et celle qui a coûté un
> vidage manuel.** Les **traits du persona** n'apparaissent ni dans les codes d'options, ni
> dans la météo, ni dans la signature d'anticipation. Or tous ne conditionnent pas l'offre :
> `has_pt_subscription` ne change que le **texte du prompt** (`_pt_subscription_note` accole
> « Abonné aux transports en commun. » à l'option TC). Corriger l'abonnement de 352 agents
> laissait donc leurs décisions déjà en cache être resservies **sous l'ancien prompt**, sans
> aucun signal. Une signature des traits entre désormais dans le `state_hash` via
> `traits_key` (`_traits_signature` dans `llm_agent.py`).
>
> Deux précisions qui font la différence entre un correctif et une gêne :
>
> - **`has_driving_license` s'auto-invalidait déjà.** Il passe par `_can_drive`, qui
>   conditionne les modes offerts, donc les codes d'options, donc le `state_hash`. Seuls les
>   traits « narratifs » avaient besoin de la signature.
> - **`name` est exclu de la signature, et c'est vérifié plutôt que supposé.** Il vient de
>   Faker non graine à la génération : l'inclure viderait tout le cache à chaque
>   régénération de population. Contrôle du 2026-08-27 : le `name` est **identique** entre la
>   population source et celle du run (930/930), il n'est donc pas re-tiré au chargement,
>   contrairement à ce qu'affirmait la documentation de la chaîne de population. Tout le
>   reste de `traits_json` entre, y compris ce qui ne sert qu'au narratif — trier par « ce
>   qui atteint le prompt » est exactement l'arbitrage qui a produit le défaut.
>
> `traits_key` vide laisse le hash strictement identique à l'existant, comme `extra_key` :
> un cache d'avant le correctif reste lisible, au prix de n'être pas gardé sur cet axe.

> La **liste noire** d'`OtpPersistentCache` (`make_blacklist_key`) reste délibérément **non
> versionnée** : « OTP ne relie pas ces deux points » est un fait de topologie du réseau, qui
> ne dépend d'aucun temps terminal. La versionner ferait re-interroger OTP pour rien sur
> toutes les paires connues comme non reliées.

> ⚠️ Toute modification des valeurs de `terminal_time.yaml` **doit** bumper `version:`. Le
> chargeur refuse une configuration sans version, mais il ne peut pas devenir qu'une valeur
> a changé sans que la version suive.

Le store de calibration, lui, était déjà correct : `RunConfig.eval_params_key()` contient
`ds=<dataset_version>`, donc une éval sur `v4` ne peut pas lire le cache d'une éval sur `v3`.

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

- **Log par décision** : chaque hit du cache sémantique LLM est aussi tracé ligne par ligne
  dans `workdir/llm_cache_hits.jsonl` (`agent_id`, `activity_id`, `sim_ts`, `sim_day`, `mode`,
  `category`), via `log_llm_cache_hit()` (`agents/llm_agent.py`). Un hit ne déclenchant aucun
  appel LLM, il n'apparaît pas dans `llm_exchanges.jsonl` ; ce fichier permet donc de compter
  les appels économisés et de ventiler l'économie de tokens par jour de simulation. La valeur
  en tokens économisés est estimée côté analyse au coût moyen par agent des appels réels.

> Les échanges LLM (`llm_exchanges.jsonl`) portent désormais `sim_ts`/`sim_day` (timestamp
> simulé issu de `AgentSpec.departure_timestamp`), ce qui permet de bucketiser la
> consommation de tokens par jour *simulé* et non par horloge murale.

### Couverture du cache LLM et diagnostic des miss

Un hit rate bas à l'init **n'est pas un problème de taille** (Qdrant embarqué n'a pas de
plafond) mais de **couverture** : le chemin exact utilisé par le bootstrap
(`memory_empty=True`) ne sert une décision que si le contexte (`agent_id`, `activity_id`,
`weekday`, `time_slice`, `state_hash`) a déjà été **stocké lors d'un run précédent**. Or
le `store` n'a lieu que si l'appel LLM réussit (`llm_result.ok`) : si la gateway sature
pendant le run de peuplement, les décisions échouées ne sont jamais mises en cache et
manquent au run suivant — un déficit **auto-entretenu** tant qu'un run n'a pas réussi
à 100 %.

Deux traces, ajoutées pour objectiver la couverture sans rejouer un run :

- **Au démarrage** (`LlmSemanticCache.log_coverage()`), une ligne
  `[cache] couverture LLM au démarrage : N points (E exact/bootstrap, A agents couverts,
  S obsolètes weekday=None)` + les gauges `llm_cache_points_total`,
  `llm_cache_points_exact`, `llm_cache_agents_covered`, `llm_cache_points_stale` — affichées
  dans les dashboards Grafana `02_init_bootstrap` (instantané + % de couverture population)
  et `06_cache_llm` (tendance inter-runs). Les points
  `weekday=None` proviennent d'un **schéma antérieur** (avant l'ajout du champ `weekday`) et
  ne matcheront jamais le filtre courant : au-delà de 30 % un `[ALARME]` invite à repurger.
- **Sur miss** `no_candidates` du chemin exact (borné aux ~30 premiers), une ligne classe la
  cause : *agent ABSENT du cache* (trou de couverture) vs *clé différente*
  (météo/créneau/state_hash) — l'ensemble `_exact_agents` renseigné au démarrage évite toute
  requête DB supplémentaire.
