# Architecture mémoire : STM et LTM

Document **unique** de la mémoire des agents. Il couvre les structures de données, les
algorithmes, la pipeline de consolidation, les paramètres, les métriques, et illustre chaque
étape avec des exemples tirés des logs réels.

| Partie | Contenu | Statut |
|---|---|---|
| I — Filiation | D'où vient chaque mécanisme, ce qu'on en prend et ce qu'on en écarte | — |
| II — Le dispositif | STM, consolidation, LTM, récupération, oubli, paramètres, métriques | **en service** |
| III — Évolutions | Gravité, consolidation des concepts, récupération structurée, mémoire noyau | **spécifié, non implémenté** |

La partie III décrit du code qui **n'existe pas**. Chacune de ses sections le rappelle. Tant
qu'une section y figure, rien de ce qu'elle décrit n'est exécuté.

---

# Partie I — Filiation

## D'où vient chaque mécanisme

Cette mémoire n'est pas une invention locale : c'est l'architecture d'agents génératifs de
**Park et al. (2023)**, adaptée au transport multimodal par **Vu, Gaudou & Oberoi (2025)**,
dont ce dépôt est la continuation. Savoir ce qui vient de qui permet de distinguer une
décision de conception d'un accident d'implémentation — et les deux existent ici.

| Mécanisme | Source | Statut chez nous |
|---|---|---|
| Flux d'expériences, réflexion, récupération pondérée | Park et al. (2023) | en service, via Vu et al. |
| Deux niveaux STM / LTM, concepts vs réflexions | Vu, Gaudou & Oberoi (2025) | en service |
| Score = sémantique + BLEU-2 + décroissance | Vu, Gaudou & Oberoi (2025) | en service |
| Réflexion **à la fin de chaque jour simulé** | Vu, Gaudou & Oberoi (2025) | restauré le 2026-09-11, ticket 048 |
| Pertinence contextuelle par lieu et heure | Vu, Gaudou & Oberoi (2025) | **spécifié chez eux, non implémenté ici** → partie III |
| Score d'importance du souvenir | Park et al. (2023) | **absent**, écarté par Vu et al. → partie III |
| Réflexion déclenchée par importance cumulée | Park et al. (2023) | **absent** → partie III |
| Oubli d'Ebbinghaus, force renforcée au rappel | MemoryBank, Zhong et al. (2024) | → partie III |
| Opérations explicites sur un souvenir existant | Mem0, Chhikara et al. (2025) ; A-MEM, Xu et al. (2025) | → partie III |
| Récupération structurée avant sémantique | HippoRAG, Gutiérrez et al. (2024) | → partie III, **avec divergence** |
| Mémoire noyau toujours en contexte | MemGPT, Packer et al. (2023) | → partie III |
| Réflexion périodique et formation d'habitudes | GATSim, Liu et al. (2025) | en service (auto-réflexion à 3 jours) |
| Ablation de mémoire comme protocole de preuve | Sensors 25(18), 5688 (2025) | protocole des expériences d'hystérésis |

## Les quatre écarts avec Park et al. (2023), et pourquoi

Trois sont hérités de Vu et al., un est une décision de ce dépôt. Tous sont vérifiés sur le
texte des articles, pas de mémoire.

**1. L'importance a disparu du score.** Park et al. classent un souvenir sur
`recency + importance + relevance`, l'importance étant obtenue en demandant au modèle une note
entière de 1 à 10 sur une échelle ancrée par deux exemples, « 1 purement banal, se brosser les
dents » et « 10 extrêmement marquant, une rupture ». Le mot *importance* n'apparaît **nulle
part** chez Vu et al., qui lui substituent un score lexical BLEU-2 sur les mots-clés, destiné à
capter la pertinence saisonnière. Notre champ `long_term_retrieval__default_reflection_importance_score`
est le vestige de cette substitution : son nom dit *importance*, son rôle est d'être la valeur
de repli du BLEU pour les entrées sans mots-clés. Conséquence en service : un retard de
quarante-cinq minutes et un trajet nominal sont conservés et rappelés du même poids.

**2. La réflexion se déclenche sur un compte, pas sur une gravité cumulée.** Park et al.
déclenchent quand *la somme des importances* des derniers événements perçus dépasse un seuil,
fixé à 150 chez eux, ce qui donne « environ deux ou trois réflexions par jour ». Faute
d'importance, notre seuil porte sur un **nombre d'entrées**. Le régime obtenu tombe par accident
dans le même ordre de grandeur, environ deux consolidations par jour pour un agent mobile, mais
il ne hiérarchise rien : dix trajets sans histoire déclenchent une réflexion, un incident isolé
n'en déclenche aucune.

**3. La décroissance part de la création, non du dernier rappel.** Park et al. font décroître
la fraîcheur « depuis le dernier rappel du souvenir », avec un facteur de 0,995 par heure de
jeu. Chez nous elle part de l'écriture. Un souvenir relu chaque matin reste frais chez eux et
s'efface chez nous. C'est le renforcement au rappel, que MemoryBank formalise et que la
partie III réintroduit. L'écart d'échelle est par ailleurs important :

| Ancienneté | Park et al. (0,995 / h) | Ici (constante 2,8 j) |
|---|---|---|
| 1 jour | 0,887 | 0,700 |
| 3 jours | 0,697 | 0,343 |
| 7 jours | 0,431 | 0,082 |
| 14 jours | 0,186 | 0,007 |

Leur demi-vie est de **5,8 jours**, la nôtre de **1,94 jour** : nos agents oublient trois fois
plus vite. Ce n'est pas un défaut en soi — un mois de vie de village n'est pas une semaine de
navette domicile-travail — mais c'est un choix, et il doit être su. Le bras de sensibilité des
expériences, qui porte la constante à 7,7 jours, encadre la valeur de Park et al.

**4. La normalisation min-max est abandonnée, et c'est notre divergence propre.** Park et al.
écrivent explicitement qu'ils ramènent les trois composantes sur [0, 1] par min-max avant de
les combiner, tous leurs poids valant 1. Nous avons retiré cette normalisation le 2026-09-11.
La raison tient à l'usage, pas à la correction : chez Park et al., la récupération n'a qu'à
**ordonner** un lot de souvenirs pour un agent donné, et une échelle relative y suffit. Ici deux
exigences supplémentaires s'y opposent. Les scores doivent être **comparables d'une décision à
l'autre**, puisque l'article confronte des distributions entre bras. Et la constante de temps
doit **déplacer la courbe**, puisqu'un critère de réfutation pré-enregistré en dépend — or sous
min-max l'ordre par ancienneté est invariant au paramètre, la décroissance étant monotone.
Nos poids valent en outre 0,4 / 0,3 / 0,3 et non 1 / 1 / 1.

## Ce qui a été lu en entier, et ce qui ne l'a pas été

Quatre des articles cités sont dans le corpus local `docs/paper/sources/etat_de_lart/` et ont
été lus : Park et al. (2023), Vu et al. (2025), CitySim, AgentMove. Les affirmations qui les
concernent dans ce document sont vérifiées sur leur texte. Les autres sont cités d'après la
bibliographie de l'état de l'art du projet, sans lecture intégrale dans le dépôt : leurs
mécanismes sont décrits au niveau où cette bibliographie les décrit, sans chiffre ni détail
qui n'en proviendrait pas. La liste complète figure en fin de document.

---

# Partie II — Le dispositif en service

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

**Fichier :** `services/llm-agents/llm/shortterm.py` — classe `UserShortTermMemory`

```python
class UserShortTermMemory:
    person_id: str
    recent_entries: List[MemoryEntry]   # anneau FIFO, max 100
    max_entries: int = 100
    last_activity: datetime
```

Chaque entrée est un `MemoryEntry` (`services/llm-agents/llm/memory.py`) :

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

**L'horodatage d'un souvenir est l'heure MURALE de GAMA** (`sim_clock.wall_clock`), depuis
le 2026-09-04. Ce n'est pas un détail d'affichage : ce `datetime` est **lu par le modèle**
(la ligne « `- Time 16 March 2026, 05:12: …` » des souvenirs passés à la réflexion, et le
nom du jour des souvenirs de réflexion rappelés dans le prompt), et il sert de côté gauche
aux filtres LTM par jour de semaine et par ancienneté. Relu dans le fuseau du **processus**,
il annonçait une heure de trop (deux en été) et faisait passer un souvenir de 23 h au
lendemain. Deux conventions se croisent ici et doivent s'annuler exactement : le stockage
écrit `wall_clock(ts)`, la relecture repasse par `sim_clock.gama_timestamp(entry.timestamp)`
— **jamais** `entry.timestamp.timestamp()`, qui rendrait la main au fuseau du processus.
Détail et mesures : [trace](../traces/2026-09-04_14-30_horloge_prompt_meteo/README.md).

**Exemple réel** (`agent_memory_events.csv`, agent `387324`) — la colonne `datetime` porte
désormais l'heure que GAMA affiche, soit 05:00:01 pour l'horodatage 1773637201 (elle
affichait `06:00:01` avant le 2026-09-04) :

```
context          | timestamp  | datetime             | person_id | activity_id                          | message
shortterm_memory | 1773637201 | 2026-03-16 05:00:01  | 387324    | 63ef6b85-810e-57aa-a59d-8a18b0a06a6f | [ TRAVEL_PLAN ] Plan to head <work> served from LLM cache.
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

La consolidation se déclenche à **deux** conditions, dont la première suffit.

```
len(stm.recent_entries) >= settings.agent.stm_reflection_min_entries   # défaut : 10
```

```
heure murale simulée >= stm_reflection_daily_floor_hour   # défaut : 22 h
et tampon non vide
et le plancher n'a pas déjà servi cet agent aujourd'hui
```

La seconde est le **plancher journalier** (ticket 048, depuis le 2026-09-11).

**Ce n'est pas une invention, c'est une restauration.** Vu, Gaudou & Oberoi (2025), dont ce
dispositif est la continuation, écrivent que la mémoire courte « sert principalement d'entrée
au processus de réflexion **à la fin de chaque jour simulé** ». Le seuil volumétrique est une
dérive par rapport à cette spécification. Park et al. (2023) déclenchent de leur côté sur une
somme d'importances et rapportent « environ deux ou trois réflexions par jour » : les deux
ancêtres décrivent donc un rythme au moins quotidien, que le seuil par compte ne garantissait
pas.

Le seuil volumétrique seul rendait le moment de la consolidation dépendant du nombre de déplacements
de l'agent : un agent à un seul déplacement produit environ six entrées et ne consolidait pas
de la journée, un agent à quatre en produisait vingt-quatre et consolidait deux fois. Comme la
décision ne lit **que** la mémoire longue, un souvenir non consolidé n'existe pas pour elle,
et la position d'un choc par rapport à la consolidation devenait une variable non contrôlée de
l'expérience d'hystérésis. Le plancher rend ce calendrier déterministe : à 22 h, tout agent
dont le tampon n'est pas vide soumet une réflexion, quel que soit son remplissage, une fois
par jour simulé au plus. L'heure laisse la nuit simulée au drainage EDF.

Le journal distingue les deux voies à chaque cycle :

```
[timestamp: …] STM reflection for 312 agents (287 par le seuil de 10 entrées, 25 par le plancher journalier)
```

### Mémoïsation des appels de réflexion (ticket 012)

Avant l'appel LLM, `reflect_on_short_term_memory` (et `reflect_on_long_term_memory`)
consulte `ReflectionMemoStore` : si le **prompt effectif exact** (agent, identité,
vécu, consignes, horodatage, paramètres LLM) a déjà été payé — cas des re-runs
déterministes — la réflexion stockée est servie sans appel réseau, avec des effets
strictement identiques (STM consommée, entrées REFLECTION/CONCEPT en LTM). Aucun
rapprochement : le moindre octet de différence est un miss. Voir
`docs/arch/cache-memory.md` § « Mémoïsation des réflexions ».

### Ordonnancement : file EDF, échéance = réveil de l'agent (ticket 010)

Les réflexions ne partent plus en fire-and-forget vers le gateway : chaque agent
éligible est soumis à la **file EDF** du dispatcher (kind `reflect`) avec pour
échéance le **réveil de son agent** — la prochaine occurrence de la première
activité planifiée de la journée (`PersonScheduler.next_wakeup_ts()`) :

```
deadline_sim = prochain réveil de l'agent            # première activité du jour suivant
# fallback si l'agent n'a aucune activité horodatée :
deadline_sim = déclenchement + settings.agent.stm_reflection_deadline_sim_s   # 12 h
```

C'est la seule échéance naturelle d'une réflexion : la LTM du matin doit intégrer la
veille avant la première décision du lendemain. Les réflexions ne bénéficient d'aucun
cache **par rapprochement** : le prompt contient le vécu réel de l'agent, unique et
consommé après usage, et servir à un agent l'introspection d'un autre serait une
dégradation. La seule mémoïsation possible est donc **exacte**, au prompt byte-identique
(`ReflectionMemoStore`, ticket 012), et elle ne se déclenche qu'au rejeu déterministe
d'un run. Au premier passage, chaque réflexion est payée : à l'intérieur d'un run, la
seule variable d'ajustement reste *quand* on les exécute, jamais *si* on les exécute.

Conséquences :

- **Drainage nocturne** : les agents rentrent le soir avec leurs mémoires pleines et
  déclenchent tous leur réflexion dans la même fenêtre (run 2026-08-03 : 247 réflexions
  pour 13 décisions en 30 min simulées). Avec l'échéance au réveil, les décisions
  d'itinéraire du soir passent mécaniquement devant, et le stock se draine toute la
  nuit simulée — fenêtre presque sans décisions — dans l'ordre des réveils (lève-tôt
  d'abord). Ce backlog nocturne est le fonctionnement **nominal**, pas une saturation
  (cf. alarme backlog, `docs/arch/llm-inference.md`).
- **Garantie « avant le réveil »** : les échéances `reflect` sont incluses dans le test
  de faisabilité EDF de la contre-pression prédictive (`edf_snapshot_deadlines()`). Si
  le débit LLM ne permet plus de les tenir, le `/sync` est retenu — le temps simulé se
  fige pendant que la file se draine.
- **Échéance conservée entre retentatives** : en cas d'échec gateway (timeout, providers
  saturés), les entrées STM restent en place et le sync suivant re-soumet la réflexion
  avec sa deadline d'origine (`_stm_reflect_due`) — jamais repoussée.
- **Alarme** : si une réflexion reste pendante au-delà de son échéance (le réveil de son
  agent est passé), un `[ALARME]` est loggé en ERROR (front montant, `make error`).

### Drainage post-pause (fin d'horizon `simulation_max_days`)

À la pause GAMA de fin d'horizon, le controller reste vivant et les consommateurs EDF
continuent de servir les réflexions encore en file — elles écrivent en LTM, utile aux
runs qui reprennent cette population. Rien n'interrompt ce drainage : seul `make down`
tue le process. Le scan worker (30 s) rend l'état lisible dès que GAMA est silencieux
depuis plus de 90 s :

```
[drainage] GAMA silencieux depuis 95s (pause ou fin de run) — 42 réflexion(s) STM encore en file, …
[drainage] Réflexions STM épuisées — LTM complète, arrêt sûr (make down)
```

Attendre le message « épuisées » avant d'arrêter les services si la LTM du run doit
être réutilisée.

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
└── llm_client.execute()  # SDK typé           → prompt : categories/stm_reflection/template.md.j2
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

**Fichier :** `services/llm-agents/llm/longterm.py` — classe `MultiUserLongTermMemory`

| Composant | Technologie | Rôle |
|-----------|-------------|------|
| Index vectoriel | ChromaDB (`hnsw:space=cosine`) | Recherche par similarité |
| Modèle d'embedding | `all-MiniLM-L6-v2` (384 dim) | Vectorisation des textes |
| Métadonnées | JSON shardés sur disque (100 shards par hash MD5) | Entrées complètes, scoring |
| Cache LRU | Dict Python, max 2 000 utilisateurs | Évite les I/O disque répétitifs |

### Organisation des données

Un seul index ChromaDB est partagé entre tous les agents (une seule collection `memory_collection`). L'isolation par agent est déléguée au vector store : le retriever passe un `MetadataFilters(person_id=...)` (traduit en clause `where` Chroma), avec `similarity_top_k = min(max(top_k × 5, 32), 100)` — la marge sert uniquement au re-ranking (décroissance temporelle, mots-clés). Un re-filtrage `person_id` côté Python est conservé en défense en profondeur. Le recall par agent ne dépend donc plus du peuplement global de l'index. Le champ d'isolation dans les métadonnées du document :

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

Les métadonnées JSON par agent (liste des entrées, dates de cleanup/réflexion) sont shardées.
Les entrées sont sérialisées via `MemoryEntry.to_dict()` (timestamp ISO, `memory_type` en valeur
chaîne) et relues via `MemoryEntry.from_dict()` — le round-trip garantit que la mémoire épisodique
survit aux redémarrages du contrôleur ; les entrées d'un ancien format non relisible sont ignorées
au chargement plutôt que d'invalider tout le fichier :

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

Pour 1 000+ agents simultanés, le chargement/sauvegarde JSON de chaque agent à chaque requête serait prohibitif. Le cache LRU maintient en RAM les métadonnées des 2 000 agents les plus récemment actifs. Le plafond doit rester **au-dessus du nombre d'agents simulés** : en dessous, le parcours round-robin des agents provoque une éviction (relecture + réécriture disque) à chaque décision. À ~3 Ko de métadonnées par agent, 2 000 agents pèsent environ 6 Mo :

```python
def _cleanup_metadata_cache(self):
    if len(self.user_metadata) <= self.max_loaded_metadata:  # 2000
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
    similarity_top_k=min(max(top_k * 5, 32), 100),   # 50 candidats pour top_k = 10
    filters=MetadataFilters(filters=[MetadataFilter(key="person_id", value=person_id)]),
)
nodes = await retriever.aretrieve(query)
```

Le filtrage par `person_id` est délégué à ChromaDB (clause `where`) ; la marge ×5 au-dessus du top-K, bornée à 100, laisse de quoi re-ranker. Avec le top-K par défaut de 10, ChromaDB renvoie 50 candidats. Ils sont ensuite re-filtrés par `person_id` en défense en profondeur, puis par fenêtre temporelle :

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

Les trois composantes sont celles de Vu, Gaudou & Oberoi (2025) : un score sémantique par
cosinus sur l'embedding, un score BLEU-2 sur les mots-clés qui tient lieu de pertinence
saisonnière, et une décroissance temporelle. Elles remplacent le triplet
`recency + importance + relevance` de Park et al. (2023), dont la composante d'importance a été
écartée — voir la partie I, écart n° 1.

Les trois entrent en **valeur absolue** sur [0, 1]. Le score de similarité, qui vient du vector
store et peut sortir de l'intervalle, y est borné ; les deux autres le sont par construction.

⚠ **La normalisation min-max par composante a été supprimée le 2026-09-11** (ticket 048), ce
qui est une divergence assumée vis-à-vis de Park et al. (2023), qui l'emploient explicitement.
Le raisonnement complet est en partie I, écart n° 4. Elle
ramenait mécaniquement le meilleur candidat du lot à 1 et le pire à 0, quel que soit l'écart
réel entre eux : le souvenir le plus récent valait toujours exactement 1 et le plus ancien
exactement 0. Deux conséquences. L'ordre par ancienneté était **invariant** à la constante de
temps, la décroissance étant monotone, si bien qu'un bras de sensibilité d'expérience pouvait
ne rien mesurer pour une raison purement technique. Et deux décisions n'étaient pas comparables
entre elles, leurs scores étant relatifs à des lots différents.

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
    force = settings.agent.long_term_retrieval__force_base_jours  # 2.8 jours
    # `gama_timestamp` et non `.timestamp()` : les deux côtés sont en heure MURALE
    time_diff = (query_at - gama_timestamp(timestamp)) / 86400  # en jours
    return math.exp(-time_diff / force)
```

Le paramètre est une **constante de temps en jours** depuis le ticket 048, et non plus une
base d'exponentielle. Le défaut de 2,8 jours reproduit exactement l'ancienne base de 0,7 par
jour, à trois décimales : un écart mesuré après ce changement est donc attribuable aux
mécanismes nouveaux et non à un oubli silencieusement accéléré. Un paramètre en jours se
discute — « un souvenir ordinaire dure trois fois plus longtemps » — là où une base
d'exponentielle ne se discute pas ; c'est lui que les bras de sensibilité des expériences
doivent viser, la conversion depuis un λ déclaré étant `force = 1 / λ`.

Deux limites connues de cette composante, toutes deux traitées en partie III. Elle part de
la **date d'écriture** et non du dernier rappel, là où Park et al. (2023) font décroître depuis
le dernier rappel du souvenir : un souvenir relu chaque matin s'efface ici comme s'il n'avait
jamais servi. Et elle est **uniforme**, indifférente à la gravité de ce qui est mémorisé.

⚠ Les deux termes de la soustraction doivent porter **la même convention** : `query_at` est
un horodatage GAMA (heure murale) et `timestamp` un `datetime` naïf aux champs muraux. Avant
le 2026-09-04, les deux erreurs s'annulaient par construction (le souvenir était écrit et
relu dans le fuseau du processus) ; corriger l'écriture sans corriger cette lecture aurait
ajouté une heure d'ancienneté fictive à chaque souvenir.

| Ancienneté | Score brut | Ancienne base 0,7 |
|-----------|-----------|-----------|
| 0 jours   | 1.000     | 1.000 |
| 1 jour    | 0.700     | 0.700 |
| 3 jours   | 0.343     | 0.343 |
| 7 jours   | 0.082     | 0.082 |
| 14 jours  | 0.007     | 0.007 |

La demi-vie effective est d'environ **1,94 jours** (`ln(2) × 2,8`), inchangée.

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
└── llm_client → prompt : categories/ltm_self_reflection/template.md.j2
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
            entry.memory_type in ["reflection", "summary"]
        )
```

Les réflexions et résumés sont **toujours conservés** indépendamment de leur âge. Seules les entrées CONCEPT ou CONVERSATION antérieures au seuil sont supprimées.

⚠ **Aucune notion d'importance n'existe dans le dispositif.** `MemoryEntry` ne porte pas de
champ `importance_score` : la rétention ne connaît que l'âge et le type, et le score composite
ne connaît que la similarité, le recouvrement lexical et l'ancienneté. Un retard de 45 minutes
et un trajet nominal sont donc conservés et rappelés avec exactement le même poids.

**L'origine de cette absence est documentée.** Park et al. (2023) portent une importance,
demandée au modèle sous forme d'entier de 1 à 10 sur une échelle ancrée par deux exemples, et
s'en servent à la fois au classement et au déclenchement de la réflexion. Vu, Gaudou & Oberoi
(2025) ne la reprennent pas — le mot n'apparaît pas dans leur article — et lui substituent le
score BLEU-2. Le paramètre `long_term_retrieval__default_reflection_importance_score` (0.2)
est le vestige de cette substitution : son nom dit *importance*, son rôle est d'être la valeur
de repli du BLEU pour les entrées sans `tags`, c'est-à-dire les réflexions narratives.

La réintroduction d'une gravité est spécifiée en **partie III, section 1**.

### Éviction LRU du cache RAM

Lorsque plus de 2 000 agents sont en RAM, les plus anciennement accédés sont flushés sur disque avant d'être retirés du dict Python, puis un `gc.collect()` libère la mémoire.

---

## Intégration dans la pipeline de décision

```text
evaluate_and_choose_travel_plan()
│
├─ 1. SI l'agent a des souvenirs (has_memories) :
│      aquery_user_memories(person_id, query, top_k=10, max_past_days=30)
│      ↳ ChromaDB pré-filtre 50 candidats (person_id en clause `where`)
│      ↳ Filtrage person_id + fenêtre temporelle
│      ↳ Score composite → top 10
│      ↳ Sérialisés en liste de strings → payload["history"]
│      SINON rien n'est lu ici : le payload (et donc la requête LTM) n'est
│      construit qu'après un miss, en 3. Le bootstrap ne paie ni requête ni embedding.
│
├─ 2. Lookup cache sémantique (LlmSemanticCache)
│      ├─ HIT  → retire un index dans les probabilités mémorisées, écrit en STM, fin
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
│      ← {"agents": [{"agent_id": ..., "reason": "...",
│                      "probabilities": [{index, mode, probability}, ...]}]}
│         (schéma imposé : mobility_llm/…/categories/itinary_multi_agent/output_schema.json)
│         puis tirage du mode dans cette distribution (mode_choice.draw_index)
│
├─ 4. asyncio.create_task(cache.store(...))   ← fire-and-forget
│
└─ 5. stm.add_message(plan_choisi, activity_id=...)  ← stockage STM
```

La LTM est **lue** avant la décision (contexte historique pour le LLM) mais **écrite** de manière asynchrone après la réflexion (pas sur le chemin critique). Le chemin critique de planification n'est bloqué que par le lookup ChromaDB (instrumenté via `ltm_query_duration_seconds`) — et seulement pour un agent qui a déjà un vécu : tant que sa LTM est vide, la décision ne dépend que des conditions factuelles, le cache répond par correspondance exacte et aucun embedding n'est calculé.

---

## Résumé des paramètres clés

Tous les paramètres mémoire de `AgentConfig` (`services/llm-agents/settings.py`) figurent ici. Le
tableau est vérifié contre le code : un paramètre ajouté sans ligne ici est un défaut de
documentation.

### Activation et stockage

| Paramètre | Défaut | Effet |
|-----------|--------|-------|
| `long_term_memory_enabled` | true | Coupe toute la mémoire longue : ni lecture avant décision, ni consolidation. **Surchargé par la valeur GAMA** — c'est le drapeau des bras « sans mémoire » des expériences d'ablation. |
| `long_term_memory_storage_dir` | `long_term_memory` | Index ChromaDB et métadonnées shardées, résolu dans le répertoire de run. |
| `long_term_max_loaded_metadata` | 2 000 | Plafond du cache LRU des métadonnées. Doit rester **au-dessus du nombre d'agents simulés** : en dessous, le parcours round-robin provoque une éviction à chaque décision. |
| `embedding_model` | `null` | ⚠ **Déclaré mais branché sur rien.** Le modèle est codé en dur (`all-MiniLM-L6-v2`) dans `services/llm-agents/llm/longterm.py`. Le brancher est un préalable du lot 2 de la partie III. |

### Consolidation STM → LTM

| Paramètre | Défaut | Effet |
|-----------|--------|-------|
| `stm_reflection_min_entries` | 10 | Seuil **volumétrique** de réflexion — l'une des deux conditions, l'autre étant le plancher journalier |
| `stm_reflection_deadline_sim_s` | 12 h | Échéance EDF **fallback** (agent sans activité horodatée) — l'échéance normale est le réveil de l'agent |
| `stm_reflection_daily_floor_enabled` | true | Plancher journalier de consolidation |
| `stm_reflection_daily_floor_hour` | 22 | Heure murale simulée du plancher. 22 h laisse la nuit simulée au drainage EDF. |
| `stm_reflection_min_tpm` | 30 000 | Débit minimal en jetons par minute exigé d'un fournisseur pour recevoir une réflexion. Écarte les instances trop lentes d'une tâche à contexte long. |
| `long_term_reflect_interval` | 24 h | **Hérité, non utilisé** tant que `stm_reflection_min_entries > 0`. Ancien déclenchement temporel de la réflexion, antérieur au seuil volumétrique. |

### Récupération

| Paramètre | Défaut | Effet |
|-----------|--------|-------|
| `long_term_max_entries_query` | 10 | Top-K renvoyé au LLM |
| `long_term_max_days_query` | 30 | Fenêtre de look-back en jours |
| `long_term_retrieval__sim_weight` | 0.4 | Poids similarité cosine |
| `long_term_retrieval__keyword_weight` | 0.3 | Poids score BLEU |
| `long_term_retrieval__time_weight` | 0.3 | Poids décroissance temporelle |
| `long_term_retrieval__force_base_jours` | 2.8 | Constante de temps de l'oubli, en jours |
| `long_term_retrieval__default_reflection_importance_score` | 0.2 | ⚠ Nom trompeur : valeur de repli du score **BLEU** pour les entrées sans `tags`, pas une importance. |
| `long_term_memory_filter_by_datetime` | false | Active deux filtres supplémentaires sur le vivier : même classe de jour (ouvré/week-end) et même tranche horaire que la requête. Coupe le vivier, à manier avec la règle de non-exclusion du lot 2 en tête. |

### Auto-réflexion LTM

| Paramètre | Défaut | Effet |
|-----------|--------|-------|
| `long_term_self_reflect_enabled` | true | Active l'auto-réflexion LTM. **Surchargé par la valeur GAMA.** |
| `long_term_self_reflect_interval_days` | 3 | Fréquence de l'auto-réflexion |
| `long_term_self_reflect_window_days` | 5 | Fenêtre de look-back pour l'auto-réflexion |

---

## Métriques, journaux et alarmes

### Métriques Prometheus

| Métrique | Type | Étiquettes | Ce qu'elle dit |
|---|---|---|---|
| `ltm_query_duration_seconds` | Histogram | — | Latence des appels `aquery_user_memories`, pré-filtrage ChromaDB et re-ranking compris. Bornes : 0,01 à 10 s. C'est la seule part de la mémoire qui soit sur le chemin critique d'une décision. |
| `controller_pending_reflections` | Gauge | — | Réflexions STM en file EDF ou en cours. Monte mécaniquement le soir : le drainage nocturne est le régime **nominal**, pas une saturation. |
| `agent_reflection_memo_total` | Counter | `category`, `event` | Mémoïsation des réflexions au prompt exact. `event` ∈ `hit`, `miss`, `store`, `store_refused`. Des `hit` en nombre signalent un rejeu déterministe ; zéro `hit` au premier passage est normal. |

### Lignes de journal à connaître

| Ligne | Quand | Ce qu'elle permet de lire |
|---|---|---|
| `STM reflection for N agents (a par le seuil…, b par le plancher journalier)` | à chaque cycle de soumission | La répartition entre les deux voies de déclenchement. Un `b` nul sur une journée entière signifie que le seuil suffit à tous les agents ; un `b` élevé signale une population peu mobile. |
| `[drainage] GAMA silencieux depuis Ns … N réflexion(s) STM encore en file` | GAMA muet depuis plus de 90 s | La LTM n'est pas complète, ne pas couper les services. |
| `[drainage] Réflexions STM épuisées — LTM complète, arrêt sûr (make down)` | file vidée | Arrêt sans perte. |

### Alarmes

| Alarme | Déclenchement | Ce qu'elle signifie |
|---|---|---|
| `[ALARME] N réflexion(s) STM au-delà de leur échéance (réveil de l'agent)` | front montant, au sync | La garantie « la LTM du matin intègre la veille » n'est plus tenue : file EDF surchargée ou fournisseurs saturés. Diagnostic par `make capacity`. Se réarme quand le compte revient à zéro. |

Les alarmes se relisent d'un coup avec `make error`.

### Ce qui n'est pas instrumenté

À signaler parce que l'absence de mesure est elle-même une information. Aucune métrique ne
compte les **écritures** en LTM, ni ne mesure la distribution des scores de rappel, ni ne dit
quelle part des souvenirs servis au modèle vient de quel type d'entrée. Ces trois grandeurs
deviennent nécessaires dès la partie III, dont chaque section porte sa propre instrumentation.

---

## Voir aussi

- [agents-lifecycle.md](agents-lifecycle.md) — le contexte d'appel dans le cycle de planification
- [cache-memory.md](cache-memory.md) — le cache sémantique des décisions, orthogonal à la mémoire, et la mémoïsation des réflexions
- [llm-inference.md](llm-inference.md) — la file EDF, la contre-pression et l'alarme de backlog
- [ticket 048](../tickets/ticket_048_calendrier_de_consolidation_et_echelle_d_oubli.md) — le calendrier de consolidation, l'échelle d'oubli et le coût des réflexions

---

# Partie III — Évolutions spécifiées, non implémentées

> **Rien de ce qui suit n'existe dans le code.** Cette partie est une spécification, pas une
> description. Elle est ordonnée en quatre lots, du moins au plus dépendant. Aucun ne coûte
> d'appel supplémentaire au modèle : tout ce que le modèle y produit est demandé à l'intérieur
> des réflexions qui ont déjà lieu.
>
> Préalable livré : le [ticket 048](../tickets/ticket_048_calendrier_de_consolidation_et_echelle_d_oubli.md).

## Trois règles

1. **Un souvenir est qualifié, pas seulement daté.** Il porte une gravité, et cette gravité
   décide de sa durée de vie et de son poids au rappel. C'est le retour de la composante
   d'importance de **Park et al. (2023)**, écartée par Vu et al. (partie I, écart n° 1).
2. **Un concept se corrige au lieu de s'empiler.** Une connaissance est un objet unique qui se
   confirme, se précise ou se voit contredire, avec un compteur derrière. C'est le principe
   d'extraction-puis-mise-à-jour de **Mem0, Chhikara et al. (2025)** et de l'évolution des
   notes d'**A-MEM, Xu et al. (2025)**.
3. **Au rappel, rien ne filtre, tout pondère.** Hors identité de l'agent et fenêtre d'âge,
   aucun critère n'exclut un souvenir. Cette règle est une **divergence délibérée** avec
   HippoRAG, expliquée au lot 2.

---

## Lot 1 — La gravité d'un souvenir

### Structure

`MemoryEntry` (`services/llm-agents/llm/memory.py`) gagne sept champs. Les six premiers sont écrits une
fois, `force` et `rappels` évoluent.

| Champ | Type | Rôle |
|---|---|---|
| `importance` | flottant sur [0, 1] | Gravité. Décide de la durée de vie et du poids au rappel. |
| `valence` | `negative` / `neutre` / `positive` | Sépare un souvenir marquant heureux d'un souvenir marquant subi. |
| `axe_objet` | chaîne normalisée | Le mode ou l'objet de réseau : `velo`, `metro_A`, `bus_401`. |
| `axe_lieu` | chaîne normalisée | Arrêt, ligne ou quartier, résolu vers un identifiant réseau quand c'est possible. |
| `axe_creneau` | énuméré | `nuit`, `matin`, `midi`, `soir`, aligné sur les tranches déjà utilisées pour la météo. |
| `axe_motif` | chaîne | `travail`, `ecole`, `loisir`. |
| `force` | flottant, en jours | Constante de temps de l'oubli. Croît au rappel. |
| `rappels` | entier | Nombre de fois où le souvenir a été servi au modèle. |

Les concepts portent en plus `identite`, `observations`, `contre_exemples` (lot 3).

La normalisation des axes se fait **à l'écriture**, jamais à la lecture : sans elle, deux
graphies de la même ligne de bus ne se rencontrent jamais. Un axe non résolu vaut `null`, traité
comme une absence de correspondance et non comme une correspondance avec tout.

### D'où vient la gravité

Deux sources, à deux endroits différents, jamais concurrentes.

**Les entrées brutes de mémoire courte** reçoivent une gravité **déterministe**, calculée depuis
les observations que la simulation renvoie. Elle ne coûte rien et elle est objective. C'est un
apport propre au dispositif : ni Park et al. ni Vu et al. ne disposent d'un simulateur physique
qui mesure le retard subi, et Park et al. notent explicitement qu'« il existe beaucoup
d'implémentations possibles d'un score d'importance ».

```
I_det = borne_0_1(
      0.50 × min(retard_subi / RETARD_REF, 1)      # RETARD_REF = 30 min
    + 0.20 × correspondance_ratee
    + 0.20 × incident_reseau
    + 0.10 × changement_de_mode_contraint
)
```

**Les concepts et les réflexions** reçoivent une gravité **jugée par le modèle**, demandée dans
l'appel de réflexion courte qui a déjà lieu. Le schéma de sortie de la catégorie
`stm_reflection` gagne deux champs par concept, une valence et un **niveau nommé**.

| Niveau | Valeur | Ancrage rédigé dans le prompt |
|---|---|---|
| `anodin` | 0,10 | Tout s'est passé comme je l'avais prévu. |
| `notable` | 0,30 | Un écart perceptible, sans conséquence sur la suite de ma journée. |
| `genant` | 0,50 | Cela m'a coûté du temps ou m'a obligé à décaler un horaire. |
| `grave` | 0,75 | Cela m'a fait rater quelque chose, ou m'a mis en difficulté. |
| `marquant` | 1,00 | Je m'en souviendrai dans un mois ; cela change ma façon de me déplacer. |

**Pourquoi un niveau nommé et non l'entier de Park et al.** Leur prompt demande une note de 1 à
10 en ancrant **les deux extrémités** par un exemple. Nous ancrons **chaque échelon**, et par
une conséquence observable plutôt que par une intensité ressentie : c'est un raffinement de leur
méthode, pas une contradiction. L'argument de fond est la comparabilité. Une échelle à ancres
donne une valeur absolue, comparable d'un agent à l'autre et d'un jour à l'autre — ce dont le
dispositif a besoin, puisqu'il faut peser un choc du jour 2 contre un trajet ordinaire du jour 5.
Le biais d'ancrage et de statu quo des modèles de langue, documenté par la bibliographie du
projet (arXiv 2511.05766 ; EMNLP Findings 2024), pousse dans le même sens : moins la réponse
attendue est un nombre nu, moins elle dérive.

**Le rang ne sert que de départage.** Demander au modèle de classer ses concepts entre eux
produit un ordre fiable, mais **relatif au lot** : sur une journée entièrement banale, le moins
banal décrocherait la note maximale. L'ordre à l'intérieur d'un même niveau n'écarte donc les
concepts que de ±0,05.

```
I_llm = valeur(niveau) + 0.05 × (2 × (n_niveau - rang_dans_niveau) / max(n_niveau - 1, 1) - 1)
```

**Règle de sécurité, non négociable.** La gravité retenue pour un concept est le **maximum**
entre le jugement du modèle et la plus forte gravité déterministe du groupe d'entrées dont il
est issu. Un modèle qui sous-estime un incident de quarante-cinq minutes ne peut donc pas le
dégrader : le fait mesuré l'emporte toujours sur le jugement.

```
I_concept = max(I_llm, max(I_det des entrées consommées))
```

### Déclenchement par gravité cumulée

Le seuil de réflexion passe d'un **compte d'entrées** à une **somme de gravités**, ce qui est le
mécanisme de Park et al. (2023), seuil fixé à 150 chez eux sur une échelle de 1 à 10. Le
plancher journalier du ticket 048 reste en place comme garantie basse.

### Oubli : une courbe, et un plancher

Chaque souvenir porte une constante de temps, fixée à l'écriture selon sa gravité. Le mécanisme
est celui de **MemoryBank, Zhong, Guo, Gao, Ye & Wang (2024)**, qui applique la courbe d'oubli
d'Ebbinghaus et fait croître la force d'un souvenir à chaque rappel.

```
force_initiale = S0 × (1 + k × importance)         # S0 = 2.8 jours, k = 3
```

`S0` vaut 2,8 jours **pour reproduire exactement la décroissance en service** : un `S0` plus
court accélérerait l'oubli en silence, et tout écart mesuré ensuite deviendrait inattribuable.
Un trajet banal part donc à près de trois jours, un souvenir `grave` à neuf jours, un souvenir
`marquant` à onze.

```
score_temps = max( exp(-Δt / force),  plancher )

plancher = φ × importance   si importance ≥ I_choc     # φ = 0.5, I_choc = 0.7
plancher = 0                sinon
```

**Le plancher est une divergence avec MemoryBank, et elle est délibérée.** Une courbe d'oubli
uniforme efface le choc. Or un événement à forte charge se consolide au lieu de se lisser, et
surtout : l'expérience d'hystérésis n'a de sens que si le souvenir de la panne survit assez
longtemps pour peser sur les décisions des jours suivants. Le plancher borne la décroissance par
le bas au-delà d'un seuil de gravité — un souvenir grave s'affaiblit mais ne sort jamais de
l'index.

**Le rappel renforce**, comme chez MemoryBank, et comme chez Park et al. dont la fraîcheur
décroît depuis le **dernier rappel** et non depuis la création (partie I, écart n° 3).

```
force ← min(force × (1 + κ), FORCE_MAX)            # κ = 0.15, FORCE_MAX = 30 jours
rappels ← rappels + 1
```

**Conséquence de conception à assumer.** Si le choc ne s'oublie pas, le retour au mode abandonné
ne peut plus s'expliquer par l'oubli. Il doit se gagner : chaque trajet réussi incrémente les
`observations` du concept concerné et relève sa confiance (lot 3). Deux forces opposées
gouvernent la reprise, et c'est cette opposition qui produit une courbe d'hystérésis
interprétable plutôt qu'une décroissance paramétrée. Le protocole d'épreuve est l'**ablation de
mémoire**, comme dans l'étude de grève de taxis publiée dans *Sensors* 25(18), 5688 (2025), et
comme l'exige le degré « robuste » du benchmark SILICA, qui demande qu'un résultat survive à une
remise à zéro de la mémoire.

### Instrumentation du lot 1

Compteurs par cycle de réflexion : gravités attribuées en cinq quantiles, pour repérer un modèle
qui écrase ses jugements ; part des souvenirs au-dessus du seuil de choc. Alarme sur front
montant si aucun concept n'atteint `grave` sur plus de deux jours simulés alors que des retards
dépassant le seuil ont été observés — signe d'un modèle qui nivelle.

---

## Lot 2 — Récupération structurée, sans exclusion

### Les trois viviers

Le vivier de candidats n'est plus produit par une seule requête sémantique. Trois passes
s'unissent, dédupliquées par identifiant de document.

| Vivier | Contenu | Coût |
|---|---|---|
| **A — sémantique** | Les plus proches du texte de la situation, borne actuelle conservée : `min(max(5 × top_k, 32), 100)`. | Un embedding de requête. |
| **B — par objet** | Pour **chaque mode présent dans les options offertes**, les souvenirs portant cet `axe_objet`, triés par gravité puis par récence, huit au plus par mode. | Une clause de métadonnées par mode. Aucun embedding. |
| **C — chocs** | Les souvenirs dont la gravité dépasse `I_choc`, cinq au plus, sans aucune condition de lieu, d'heure ni de motif. | Une clause de métadonnées. |

### La divergence avec HippoRAG, et pourquoi elle est nécessaire

**HippoRAG, Gutiérrez et al. (2024)** indexe la mémoire par une structure de graphe pour
retrouver ce qu'une recherche sémantique plate manque. Nous en reprenons le principe — une
structure explicite avant le sémantique — et nous en **inversons l'usage**. Chez eux, la
structure **restreint** la recherche. Ici elle ne peut pas : le phénomène que le dispositif doit
observer est précisément le **report d'un contexte sur un autre**.

> Une chute à vélo à 8 h 12 boulevard de Strasbourg doit peser sur la décision de 18 h 40 où le
> vélo figure parmi les options. Ni le lieu, ni le créneau, ni le motif ne coïncident. Un filtre
> sur le créneau horaire aurait écarté la chute. C'est l'objet qui les relie, et l'objet suffit.

D'où la règle : **hors identité de l'agent et fenêtre d'âge, plus rien ne filtre, tout pondère.**
Le vivier B est ce qui fait remonter la chute ; le vivier C garantit qu'un souvenir grave n'est
jamais perdu par accident de classement.

C'est aussi la mise en œuvre de la **pertinence contextuelle** que Vu, Gaudou & Oberoi (2025)
spécifient — « les souvenirs liés au contexte courant, par exemple le lieu et l'heure de la
journée, sont prioritaires » — mais qui, faute de champs typés, ne passe aujourd'hui que par la
similarité de texte libre et le BLEU-2 sur mots-clés.

### Classement

Cinq composantes, sur le vivier réuni, toutes en valeur absolue sur [0, 1].

| Composante | Poids proposé | Origine |
|---|---|---|
| Similarité sémantique | 0,30 | Vu et al. (2025), embedding francophone (voir ci-dessous) |
| Recouvrement lexical | 0,10 | Vu et al. (2025), BLEU-2 |
| Force temporelle | 0,20 | MemoryBank (2024), plancher compris |
| Gravité | 0,20 | Park et al. (2023), restaurée |
| Affinité d'axes | 0,20 | HippoRAG (2024), en bonus et non en veto |

Ces poids sont un point de départ à calibrer, pas un résultat.

```
affinite = ( 0.50 × [axe_objet   concorde]
           + 0.20 × [axe_lieu    concorde]
           + 0.15 × [axe_creneau concorde]
           + 0.15 × [axe_motif   concorde] )
```

**L'affinité est un bonus, jamais un veto.** Un axe discordant contribue zéro. Un souvenir dont
aucun axe ne concorde reste classable sur ses quatre autres composantes.

### Le modèle d'embedding

`all-MiniLM-L6-v2`, hérité de Vu et al. (2025), est entraîné sur l'anglais alors que tous les
souvenirs sont en français : la composante la plus pondérée du score tourne sur des vecteurs
dégradés. Remplacement retenu : **Solon-embeddings-large-0.1**, 1024 dimensions, en tête des
classements francophones. Deux préalables. Le paramètre `embedding_model` existe dans la
configuration mais **n'est branché sur rien**, le modèle étant codé en dur dans
`services/llm-agents/llm/longterm.py` : le brancher permet de comparer deux modèles sans toucher au code.
Et le passage impose une **reconstruction complète de l'index**, les vecteurs n'étant pas
comparables d'un modèle à l'autre. Mesurable sur jeux gelés, sans run de simulation.

### Instrumentation du lot 2

**Part du top-K finale issue de chaque vivier** : c'est la mesure directe de l'utilité des
viviers B et C. Deux alarmes sur front montant. Le vivier B revient vide pour plus d'un tiers
des décisions sur une fenêtre, ce qui signale une normalisation d'axes défaillante. La part du
top-K issue du seul vivier A dépasse 95 % sur une fenêtre, ce qui signale que les viviers
structurés ne servent à rien et que la conception est à revoir.

---

## Lot 3 — Un concept se corrige au lieu de s'empiler

Aujourd'hui chaque réflexion émet jusqu'à cinq concepts, chacun écrit comme une entrée neuve.
Rien ne les relie. Au bout d'un mois un agent porte des centaines de concepts, dont beaucoup
répètent la même chose et certains se contredisent — et c'est le prompt de décision qui arbitre,
à chaque décision, à ses frais.

Le mécanisme vient de **Mem0, Chhikara et al. (2025)**, qui extrait puis applique des opérations
explicites sur la mémoire existante plutôt que d'empiler, et d'**A-MEM, Xu et al. (2025)**, dont
les notes se lient et évoluent à l'arrivée d'un souvenir nouveau.

### Identité et opérations

```
identite = hash(axe_objet, axe_motif)
```

Correspondance exacte sur une métadonnée indexée : aucun embedding, aucun appel réseau. Quatre
opérations, choisies par le modèle via un champ `operation` ajouté au schéma de sortie de la
réflexion existante.

| Opération | Effet |
|---|---|
| `creer` | Aucune identité correspondante. Nouveau concept, `observations = 1`. |
| `confirmer` | Même affirmation. Rien n'est écrit de neuf : `observations += 1`, horodatage rafraîchi, force renforcée. |
| `preciser` | Affirmation compatible mais plus fine. Le contenu est remplacé ; compteurs et historique conservés. |
| `contredire` | Affirmation incompatible. `contre_exemples += 1`. Au-delà d'un seuil, l'ancien concept est marqué **dépassé** et le nouveau prend la relève. |

**Divergence avec Mem0 : il n'y a pas de suppression.** Leur jeu d'opérations comporte un
`DELETE` ; un concept dépassé n'est ici jamais supprimé, seulement marqué et daté. La raison est
scientifique et non technique : la mise à l'écart datée d'un concept **est** la trace lisible
d'un changement d'habitude, et c'est l'observable que l'expérience d'hystérésis cherche.

```
confiance = (observations + 1) / (observations + contre_exemples + 2)
```

Lissage de Laplace, pour qu'une observation unique ne vaille pas certitude.

**Les entrées épisodiques ne fusionnent jamais.** Seuls les concepts se consolident — c'est ce
qui empêche un agent de se réduire à un stéréotype sans vécu. La distinction est exactement
celle de Vu, Gaudou & Oberoi (2025) entre *concepts*, faits indépendants de l'identité, et
*réflexions*, qui incorporent les traits de l'agent.

### Instrumentation du lot 3

Compteur d'opérations par type à chaque cycle. Alarme sur front montant si aucun `contredire`
n'apparaît sur plus de deux jours simulés alors que des contre-exemples existent : signe d'un
modèle qui confirme tout.

---

## Lot 4 — La mémoire noyau

Les dix souvenirs bruts servis au modèle sont remplacés par un bloc permanent, court et
structuré, complété de deux ou trois entrées épisodiques rappelées pour la décision en cours.
Le principe est celui de **MemGPT, Packer et al. (2023)** : une mémoire noyau toujours présente
dans le contexte, le reste étant paginé à la demande.

```
Mes habitudes                                 [ produit par le journal des trajets ]
- Domicile → travail, jours ouvrés vers 07h45 : bus 401 puis 5 min de marche,
  24 min porte à porte. Tenu 9 fois sur 11.
- Retour vers 18h00, même trajet. Deux retards de plus de 10 min ce mois-ci.

Ce que je sais                                          [ produit par la réflexion ]
- Le bus 401 est fiable, sauf les jours de pluie où il perd 5 à 8 minutes.  (12 obs.)
- La marche jusqu'à l'arrêt fait toujours 5 minutes.                        (18 obs.)

Ce qui a changé récemment                               [ produit par la réflexion ]
- 14 mars, panne ligne A, 45 minutes perdues. Je n'ai pas repris la ligne A depuis.
```

**Le bloc ne porte aucune métadonnée sur lui-même** : ni date de dernière mise à jour, ni nombre
de jours de vécu. Ces informations ne changent aucune décision, elles coûtent des jetons, et
surtout elles rompent la fiction que les gabarits maintiennent. Une personne ne pense pas « mon
résumé d'habitudes date de trois jours » ; lui donner cette phrase l'invite à raisonner sur le
mécanisme de sa mémoire au lieu de raisonner sur son trajet. L'ancienneté utile est déjà portée,
énoncé par énoncé, par les compteurs d'observations.

**Garde-fou** : le bloc des habitudes est produit par le **journal des trajets**, pas par le
modèle. Un texte réécrit périodiquement par un modèle dérive et invente. Seul le bloc de
connaissances lui est confié, et chaque énoncé y porte son compteur.

L'entretien ne coûte rien de neuf : l'auto-réflexion longue durée tourne déjà tous les trois
jours, seule la forme de sa sortie change. Le rythme de trois jours est comparable à la
réflexion hebdomadaire de **GATSim, Liu et al. (2025)**, qui fait émerger des habitudes dans une
simulation de transport.

Le dernier bloc est l'endroit où l'hystérésis devient lisible dans le prompt lui-même, et non
plus seulement dans les statistiques de sortie.

---

## Paramètres de la partie III

| Paramètre | Défaut proposé | Effet |
|---|---|---|
| `memoire__retard_ref_s` | 1800 | Retard, en secondes, qui sature la composante de gravité. |
| `memoire__force_k_importance` | 3,0 | Facteur d'allongement de la durée de vie par la gravité. |
| `memoire__force_max_jours` | 30 | Plafond de renforcement au rappel. |
| `memoire__force_kappa_rappel` | 0,15 | Renforcement à chaque rappel. |
| `memoire__importance_choc` | 0,7 | Seuil du choc, soit le niveau `grave` et au-dessus. Ouvre le vivier C et le plancher de rappel. |
| `memoire__plancher_phi` | 0,5 | Hauteur du plancher, proportionnelle à la gravité. |
| `memoire__contre_exemples_seuil` | 3 | Contre-exemples avant qu'un concept soit marqué dépassé. |
| `memoire__vivier_b_par_mode` | 8 | Souvenirs tirés par mode envisagé. |
| `memoire__vivier_c_taille` | 5 | Souvenirs graves tirés sans condition. |
| `long_term_retrieval__*_weight` | 0,30 / 0,10 / 0,20 / 0,20 / 0,20 | Les cinq poids du lot 2. |

`long_term_retrieval__force_base_jours` existe déjà et vaut 2,8 : c'est le `S0` du lot 1.

---

# Sources

Lues en entier, présentes dans `docs/paper/sources/etat_de_lart/` :

- **Park, J. S. et al. (2023)** — *Generative Agents: Interactive Simulacra of Human Behavior*, UIST '23, [arXiv:2304.03442](https://arxiv.org/abs/2304.03442). Flux d'expériences, réflexion, récupération `recency + importance + relevance` normalisée min-max, importance demandée au modèle en entier de 1 à 10, réflexion déclenchée sur une somme d'importances de seuil 150, décroissance 0,995 par heure de jeu depuis le dernier rappel.
- **Vu, T.-D., Gaudou, B. & Oberoi, K. S. (2025)** — *Modeling realistic human behavior using generative agents in a multimodal transport system*, [arXiv:2510.19497](https://arxiv.org/abs/2510.19497). Architecture dont ce dépôt est la continuation : deux niveaux STM/LTM, distinction concepts/réflexions, score sémantique + BLEU-2 + décroissance, ChromaDB et `all-MiniLM-L6-v2`, réflexion à la fin de chaque jour simulé, pertinence contextuelle par lieu et heure.
- **Bougie, N. & Watanabe, N. (2025)** — *CitySim*, EMNLP Industry, [arXiv:2506.21805](https://arxiv.org/abs/2506.21805).
- **Feng, J., Du, Y., Zhao, T. & Li, Y. (2025)** — *AgentMove*, NAACL, [arXiv:2408.13986](https://arxiv.org/abs/2408.13986).

Cités d'après la bibliographie de l'état de l'art du projet, non lus intégralement dans ce dépôt :

- **Zhong, W., Guo, L., Gao, Q., Ye, H. & Wang, Y. (2024)** — *MemoryBank*, AAAI-24, [arXiv:2305.10250](https://arxiv.org/abs/2305.10250). Courbe d'oubli d'Ebbinghaus, force renforcée au rappel.
- **Chhikara, P. et al. (2025)** — *Mem0*, [arXiv:2504.19413](https://arxiv.org/abs/2504.19413). Extraction puis opérations explicites sur la mémoire existante.
- **Xu, W. et al. (2025)** — *A-MEM: Agentic Memory*, NeurIPS, [arXiv:2502.12110](https://arxiv.org/abs/2502.12110). Notes qui se lient et évoluent.
- **Gutiérrez, B. J. et al. (2024)** — *HippoRAG*, NeurIPS, [arXiv:2405.14831](https://arxiv.org/abs/2405.14831). Indexation structurée avant recherche sémantique.
- **Packer, C. et al. (2023)** — *MemGPT*, [arXiv:2310.08560](https://arxiv.org/abs/2310.08560). Mémoire noyau toujours en contexte.
- **Shinn, N. et al. (2023)** — *Reflexion*, NeurIPS, [arXiv:2303.11366](https://arxiv.org/abs/2303.11366). Réflexion verbale comme apprentissage.
- **Liu, X. et al. (2025)** — *GATSim*, [arXiv:2506.23306](https://arxiv.org/abs/2506.23306). Réflexion hebdomadaire et formation d'habitudes en simulation de transport.
- **Park, J. S. et al. (2024)** — *Generative Agent Simulations of 1,000 People*, [arXiv:2411.10109](https://arxiv.org/abs/2411.10109). 1 052 personnes simulées, 85 % de la fidélité test-retest.
- **Piao, J., Yan, Z. et al. (2025)** — *AgentSociety*, [arXiv:2502.08691](https://arxiv.org/abs/2502.08691).
- **Wang, J. et al. (2024)** — *LLMob*, NeurIPS, [arXiv:2402.14744](https://arxiv.org/abs/2402.14744).
- **Shao, C. et al. (2024)** — *CoPB*, [arXiv:2402.09836](https://arxiv.org/abs/2402.09836).
- **Li, Y. et al. (2024)** — *MobAgent*.
- ***Sensors* 25(18), 5688 (2025)** — grève de taxis à 80 % aux jours 11 à 15 d'un run de 20 jours, sous ablation des mémoires.
- **Liu et al. (2025b)**, cité dans [arXiv:2412.06681](https://arxiv.org/abs/2412.06681) — inertie et théorie de l'esprit, équilibre d'heure de départ.
- **Biais de statu quo et d'ancrage des modèles de langue** — [arXiv:2511.05766](https://arxiv.org/abs/2511.05766) ; EMNLP Findings 2024.
