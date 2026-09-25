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
| Score = sémantique + BLEU-2 + décroissance | Vu, Gaudou & Oberoi (2025) | remplacé le 2026-09-14 par un score à cinq composantes (ticket 071, lot 2) ; le BLEU-2 n'y figure plus |
| Réflexion **à la fin de chaque jour simulé** | Vu, Gaudou & Oberoi (2025) | restauré le 2026-09-11, ticket 048 |
| Pertinence contextuelle par lieu et heure | Vu, Gaudou & Oberoi (2025) | **spécifié chez eux, non implémenté ici** → partie III |
| Score d'importance du souvenir | Park et al. (2023) | **absent**, écarté par Vu et al. → partie III |
| Réflexion déclenchée par importance cumulée | Park et al. (2023) | **absent** → partie III |
| Oubli d'Ebbinghaus, force renforcée au rappel | MemoryBank, Zhong et al. (2024) | → partie III |
| Opérations explicites sur un souvenir existant | Mem0, Chhikara et al. (2025) ; A-MEM, Xu et al. (2025) | → partie III |
| Génération de candidats multi-viviers | technique classique de recherche d'information | → partie III |
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
est le vestige de cette substitution : son nom dit *importance*, mais il servait de valeur de
repli au BLEU pour les entrées sans mots-clés. Un retard de quarante-cinq minutes et un trajet
nominal étaient donc conservés et rappelés du même poids. **L'écart est résorbé depuis le
ticket 071** : la gravité revient au classement au lot 2, avec un poids de 0,20, et le BLEU-2 en
sort (partie II, étape 2).

**2. La réflexion se déclenche sur un compte, pas sur une gravité cumulée.** Park et al.
déclenchent quand *la somme des importances* des derniers événements perçus dépasse un seuil,
fixé à 150 chez eux, ce qui donne « environ deux ou trois réflexions par jour ». Faute
d'importance, notre seuil porte sur un **nombre d'entrées**. Le régime obtenu tombe par accident
dans le même ordre de grandeur, environ deux consolidations par jour pour un agent mobile, mais
il ne hiérarchise rien : dix trajets sans histoire déclenchent une réflexion, un incident isolé
n'en déclenche aucune.

**3. La décroissance part de la création, non du dernier rappel.** Park et al. font décroître
la fraîcheur « depuis le dernier rappel du souvenir », avec un facteur de 0,995 par heure de
jeu. Chez nous elle partait de l'écriture : un souvenir relu chaque matin restait frais chez eux
et s'effaçait chez nous. **Le lot 1 du ticket 071 résorbe cet écart.** Le Δt se compte depuis
le dernier rappel, et chaque rappel allonge la durée de vie d'un jour, selon le renforcement
que MemoryBank formalise (partie II, étape 2, composante 2). L'écart d'échelle demeure pour un
trajet banal :

| Ancienneté | Park et al. (0,995 / h) | Ici (constante 2,8 j) |
|---|---|---|
| 1 jour | 0,887 | 0,700 |
| 3 jours | 0,697 | 0,343 |
| 7 jours | 0,431 | 0,082 |
| 14 jours | 0,186 | 0,007 |

Leur demi-vie est de **5,8 jours**, la nôtre de **1,94 jour** : nos agents oublient trois fois
plus vite. Ce n'est pas un défaut en soi — un mois de vie de village n'est pas une semaine de
navette domicile-travail — mais c'est un choix, et il doit être su. Le bras de sensibilité des
expériences prend, depuis le 2026-09-14, la valeur de Park et al. elle-même comme second point,
8,3 jours, là où la première version la fixait à 7,7 jours, λ divisé par trois (partie III,
règle des constantes).

**4. La normalisation min-max est abandonnée, et c'est notre divergence propre.** Park et al.
écrivent explicitement qu'ils ramènent les trois composantes sur [0, 1] par min-max avant de
les combiner, tous leurs poids valant 1. Nous avons retiré cette normalisation le 2026-09-11.
La raison tient à l'usage, pas à la correction : chez Park et al., la récupération n'a qu'à
**ordonner** un lot de souvenirs pour un agent donné, et une échelle relative y suffit. Ici deux
exigences supplémentaires s'y opposent. Les scores doivent être **comparables d'une décision à
l'autre**, puisque l'article confronte des distributions entre bras. Et la constante de temps
doit **déplacer la courbe**, puisqu'un critère de réfutation pré-enregistré en dépend — or sous
min-max l'ordre par ancienneté est invariant au paramètre, la décroissance étant monotone.
Nos poids ne valent pas non plus 1 / 1 / 1 : 0,4 / 0,3 / 0,3 jusqu'au ticket 071, puis, depuis
le lot 2, 0,30 / 0,20 / 0,20 / 0,20 / 0,10 sur cinq composantes (partie II, étape 2).

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
│  score composite : similarité, temps, gravité, axes, météo.              │
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
    tags: Optional[str]          # mots-clés ; plus lus par le classement LTM depuis le ticket 071, lot 2
    valence: str = "neutre"      # negative | neutral | positive
    origine: Optional[str] = None  # vecu | lu | entendu  (ticket 100)
```

#### `origine` — d'où vient ce que l'entrée raconte (ticket 100, lot 1)

Trois valeurs : `vecu` (l'agent l'a fait ou subi), `lu` (canal presse, lot 2), `entendu` (un
autre membre de son foyer le lui a dit, lot 4).

Ce champ n'est pas documentaire : il porte la décision **D2 du ticket 100 — un seul saut**. Ce
qui est entendu ne repart jamais. Sans lui, une croyance née d'un ouï-dire est indiscernable
d'une croyance née d'un trajet, et il n'y a pas de raccourci : le ticket 078 § 4.1 avait
explicitement refusé cette généalogie, au motif que l'ancrage (`observations ≥ 1`) suffisait à
fermer la boucle. Il suffit à empêcher une amplification **non ancrée** ; il ne suffit pas à
borner la circulation à un saut, ce que D2 exige.

⚠ `None` n'est pas `vecu`. `None` veut dire « entrée écrite avant le ticket 100 » ; la propriété
`origine_effective` la **lit** comme vécue, faute de mieux, mais l'entrée ne le **déclare** pas.
Confondre les deux ferait passer pour une mesure ce qui n'est qu'un défaut de champ — et dans ce
dépôt, l'absence de mesure produit volontiers la valeur parfaite.

Au lot 1, le champ est écrit et journalisé, et ne filtre rien. Il ne devient une règle qu'au
lot 4, avec la circulation au sein du foyer.

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

La consolidation se déclenche à **trois** conditions, dont la première rencontrée suffit. Elles
sont additives : aucune ne remplace les autres.

```
len(stm.recent_entries) >= settings.agent.stm_reflection_min_entries   # défaut : 10
```

```
somme des gravités du tampon >= memoire__theta_gravite_cumulee   # Θ = 0,7
et tampon non vide
```

```
heure murale simulée >= stm_reflection_daily_floor_hour   # défaut : 22 h
et tampon non vide
et le plancher n'a pas déjà servi cet agent aujourd'hui
```

La deuxième est le **déclenchement par rupture** (ticket 071, lot 1, depuis le 2026-09-14).
C'est le mécanisme de Park et al. (2023, § 4.2), qui remplace un compte d'entrées par une somme
d'importances — avec une différence à dire : chez eux le seuil cumulé se franchit deux ou trois
fois par jour, c'est un régime **courant** ; ici il est **exceptionnel** par construction de Θ,
réservé aux ruptures. La consolidation de base reste celle de la nuit.

⚠ **Θ = 0,7 a été fixé sans mesure**, faute de run ayant jamais calculé la gravité
déterministe. Le critère de vérification est « moins d'un déclenchement par agent et par semaine
simulée » ; au-delà, une alarme `[ALARME]` part sur front montant et Θ doit monter. La ligne de
journal du cycle compte les trois motifs **séparément**, sans quoi cette vérification demanderait
de rejouer la simulation.

La troisième est le **plancher journalier** (ticket 048, depuis le 2026-09-11).

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

### Consolidation des concepts (ticket 071, lot 3)

Un concept ne s'empile plus, il se **corrige**. Les concepts que l'agent tient déjà sur les
modes et les motifs de sa journée lui sont montrés dans l'appel de réflexion **qui a déjà
lieu** — coût marginal nul — et il désigne celui qu'il met à jour.

| Opération | Effet |
|---|---|
| `creer` | nouveau concept |
| `confirmer` | `observations += 1`, rien de neuf n'est écrit, force renforcée |
| `preciser` | le contenu est remplacé, compteurs et historique conservés |
| `contredire` | `contre_exemples += 1` sur la cible, et le nouveau concept prend la relève |

```
confiance = (observations + 1) / (observations + contre_exemples + 2)      # Laplace (1814)
```

Sous 0,5 — le concept a été contredit plus souvent que confirmé — il **cesse d'être servi**,
et sa mise à l'écart est **datée**. Il n'est jamais supprimé : cette mise à l'écart datée EST
la trace lisible du changement d'habitude que l'expérience d'hystérésis cherche.

⚠ **Trois conséquences à connaître.**

1. La date est posée à la **cessation de service**, pas au seuil de trois contre-exemples. Un
   concept sort du panier dès qu'il n'est plus servi, donc il n'est plus montré, donc il ne peut
   plus être contredit : rattacher la date au seuil de trois la rendait inatteignable pour un
   concept peu observé, et l'observable n'aurait jamais été écrit.
2. Le nombre de contradictions qu'un concept peut recevoir est **borné** par sa sortie du
   panier. Un concept observé trois fois en reçoit quatre, puis plus aucune.
3. La règle de non-exclusion du lot 2 gagne une **troisième exception**, avec l'identité de
   l'agent et la fenêtre d'âge : le concept mis hors service.

Le panier `(mode, motif)` désigne un **ensemble** de candidats, jamais un emplacement unique :
une identité par couple condamnerait l'agent à une seule pensée par mode et par motif.

#### Compter ces opérations (ticket 093)

Les quatre opérations sont écrites dans le journal lisible `memoires/<agent>.md`, qui **n'est pas
une source de mesure** — son propre en-tête le dit. Depuis le ticket 093, une trace structurée les
consigne aussi : une ligne JSONL par opération dans `operations_concept.jsonl`, sous
`agent.trace_concepts_enabled` (éteint par défaut). Elle est **gelée pendant le rejeu** d'une
reprise : une opération rejouée n'est pas une opération, la mémoire est gelée et ne décide rien.

C'est la courbe la plus parlante du dispositif. Mesuré sur dix jours et cinq agents : **38 créés,
61 confirmés, une seule contradiction** — celle de Corinne, le jour du choc. Sans événement
injecté, la mémoire n'a jamais rien révisé.

⚠ Trace éteinte, les colonnes de `<run>/mesures/memoire_par_jour.csv` restent **vides** et non à
zéro : « aucune contradiction » et « on ne compte pas les contradictions » ne doivent pas se citer
pareil. Voir `docs/arch/mesures-personas.md`.

### Le vocabulaire des modes (ticket 077, lot A)

`mode_canonique()` accepte **deux vocabulaires**, et c'est délibéré. Les décisions d'itinéraire
portent des étiquettes de **jambes** (`foot`, `bus`, `bicycle`), que la hiérarchie AUAT/CEREMA
sait ramener à un mode. Le schéma JSON de la réflexion impose au modèle les modes **canoniques**
(`walking`, `cycling`, `public_transport`, `train`, `motorbike`, `car`, plus `any` qui signifie
« ce concept ne porte pas sur un mode »).

⚠ **Jusqu'au 2026-09-15, seul le premier vocabulaire traversait.** Sur les sept valeurs que le
schéma autorise, `car` était la seule à être aussi une étiquette de jambe ; les six autres
rendaient `None`. Le run de trente jours du ticket 075 en porte la trace complète :

| Conséquence | Mesure |
|---|---|
| Concepts sans axe d'objet | 211 sur 231 |
| Appels de réflexion sans aucune croyance montrée | 159 blocs sur 235 (68 %), et 63 sur 63 pour l'agent sans voiture |
| Opérations de correction appliquées | 0 précision, 1 contradiction |
| Concepts restés à confiance 0,50 | 225 sur 231 |
| Part du top-K venant du seul vivier sémantique | 100 % |

Le modèle n'y est pour rien : quand une croyance lui est montrée, il la confirme **74 fois sur
76**. La liste des modes canoniques acceptés est **dérivée de la ressource gelée**
(`canonical_order()`), jamais écrite dans `axes.py` : une liste recopiée divergerait le jour où
la hiérarchie bouge.

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

### Étape 0 — Trois viviers, et non plus un (ticket 071, lot 2)

Le vivier de candidats n'est plus produit par une seule passe sémantique. Trois passes
s'unissent, dédupliquées par identifiant de document.

| Vivier | Contenu | Coût |
|---|---|---|
| **A — sémantique** | les plus proches du texte de la situation, borne inchangée | un plongement de requête |
| **B — par objet** | pour chaque mode offert dans les options, les souvenirs portant ce mode, les plus graves et les plus récents d'abord, 8 au plus par mode | nul, lecture en RAM |
| **C — chocs** | les souvenirs au-dessus du seuil de gravité, 5 au plus, **sans aucune condition** de lieu, d'heure ni de motif | nul, lecture en RAM |

Les viviers B et C lisent les métadonnées de l'agent, **déjà en mémoire vive** — rechargées du
disque si l'agent avait été évincé du cache LRU. Aucun plongement, aucune requête au magasin
vectoriel.

**Le phénomène que cela permet d'observer.** Une chute à vélo à 8 h 12 boulevard de Strasbourg
doit peser sur la décision de 18 h 40 où le vélo figure parmi les options. Ni le lieu, ni le
créneau, ni le motif ne coïncident : seul l'objet les relie, et l'objet suffit. Le vivier C
garantit en plus qu'un souvenir grave n'est jamais perdu par accident de classement.

**Instrumentation.** La part du top-K issue de chaque vivier est journalisée sur une fenêtre de
200 décisions. Deux alarmes sur front montant : le vivier B vide sur plus d'un tiers des
décisions, signe d'une normalisation d'axes défaillante ; et plus de 95 % du top-K venant du
seul vivier A, signe que les viviers structurés ne servent à rien.

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
| Jour ouvré et créneau | week-day et tranche horaire de la requête | `long_term_memory_filter_by_datetime` |

Les filtres se **cumulent** depuis le 2026-09-14 (ticket 071, défaut C). Auparavant, activer le
filtre par jour et créneau provoquait une sortie immédiate, et la fenêtre d'âge n'était **jamais
appliquée** : un souvenir vieux de trois ans en temps simulé passait, pourvu qu'il tombe le même
jour de semaine que la requête. Le défaut était dormant, l'option étant à faux par défaut.

### Étape 2 — Score composite

```python
combined_score = (
    _sim   × sim_weight         +   # 0.30  similarité sémantique
    _temps × time_weight        +   # 0.20  poids temporel (confiance, pour un concept)
    _grav  × importance_weight  +   # 0.20  gravité du souvenir
    _axes  × affinite_weight    +   # 0.20  affinité d'axes : objet, lieu, créneau, motif
    _cat   × keyword_weight         # 0.10  météo seule
)                                   # somme des poids : 1.00
```

Les poids sont les `settings.agent.long_term_retrieval__{sim,time,importance,affinite,keyword}_weight`.
Le score a **cinq composantes depuis le ticket 071, lot 2** (2026-09-14). Il en avait trois
auparavant, pondérées 0,4 / 0,3 / 0,3 : la similarité, un recouvrement lexical dit « BLEU-2 »
et la décroissance temporelle, soit le triplet de Vu, Gaudou & Oberoi (2025). Le lot 2 y ajoute
la gravité, que Park et al. (2023) classaient et que Vu et al. avaient écartée, et l'affinité
d'axes, apport propre. Le terme lexical, lui, ne mesure plus que la météo (composante 5).

Les cinq entrent en **valeur absolue** et restent dans [0, 1] par construction. La similarité
ne descend jamais sous e⁻² ≈ 0,135 (composante 1).

⚠ **La normalisation min-max par composante a été supprimée le 2026-09-11** (ticket 048), ce
qui est une divergence assumée vis-à-vis de Park et al. (2023), qui l'emploient explicitement.
Le raisonnement complet est en partie I, écart n° 4. Elle
ramenait mécaniquement le meilleur candidat du lot à 1 et le pire à 0, quel que soit l'écart
réel entre eux : le souvenir le plus récent valait toujours exactement 1 et le plus ancien
exactement 0. Deux conséquences. L'ordre par ancienneté était **invariant** à la constante de
temps, la décroissance étant monotone, si bien qu'un bras de sensibilité d'expérience pouvait
ne rien mesurer pour une raison purement technique. Et deux décisions n'étaient pas comparables
entre elles, leurs scores étant relatifs à des lots différents.

#### Composante 1 — Similarité sémantique (`_sim`, poids 0,30)

`rank_nodes` ne reçoit **ni un cosinus ni une distance**. Il reçoit `exp(-d)`. La collection
ChromaDB est créée en `hnsw:space: cosine` (`create_chroma_store`, `llm/longterm.py`). ChromaDB
renvoie donc la distance cosinus `d = 1 − cos`, sur [0, 2], calculée dans l'espace à 384
dimensions de `all-MiniLM-L6-v2`. L'adaptateur `llama-index-vector-stores-chroma` 0.4.2 la
convertit en `similarity_score = math.exp(-distance)` (`llama_index/vector_stores/chroma/base.py`,
ligne 432, vérifié dans le conteneur `controller` le 2026-09-24 avec chromadb 1.5.9). Le terme
effectivement pondéré est :

```text
_sim = exp(cos − 1)        sur [e⁻², 1] ≈ [0,135 ; 1]
```

| Cosinus | `_sim` | Apport au score (× 0,30) |
|---|---|---|
| 1 | 1,000 | 0,300 |
| 0,5 | 0,607 | 0,182 |
| 0 | 0,368 | 0,110 |
| −1 | 0,135 | 0,041 |

Trois conséquences :

- **Un cosinus nul vaut 0,37, pas 0.** Un candidat du vivier A sans aucun rapport sémantique
  avec la requête garde 0,11 point de score. Entre un cosinus de 0 et un cosinus de 1, la
  composante ne varie que de 0,63, soit 0,19 point de score et non 0,30.
- **Le `np.clip(…, 0, 1)` de `rank_nodes` ne modifie rien** : `exp(-d)` reste dans ]0, 1], à
  un arrondi flottant près au voisinage de 1.
- **Les candidats qu'apportent les viviers B et C valent exactement 0** : ils sont construits
  avec `score=0.0`, sans plongement. Un souvenir déjà remonté par le vivier A garde son score,
  la déduplication conservant la première occurrence. Face à un candidat sémantique orthogonal
  à la requête, un souvenir structuré part donc avec 0,11 point de retard, que ses quatre
  autres composantes doivent combler.

#### Composante 2 — Poids temporel (`_temps`, poids 0,20)

Deux régimes, selon le type de l'entrée (ticket 071, lots 1 et 3) :

| Type | Terme | Lecture |
|---|---|---|
| Épisodique : `CONVERSATION`, `REFLECTION` | `exp(-Δt / force)` | Δt en jours simulés depuis le **dernier rappel**, à défaut depuis l'écriture |
| Sémantique : `CONCEPT`, `SUMMARY` | `(obs + 1) / (obs + contre + 2)` | confiance de Laplace, sans horloge ; 0,5 pour un concept jamais observé |

La constante `force` est propre au souvenir. Elle vaut `min(S0 × (1 + k × I), FORCE_MAX)` à
l'écriture, avec `S0 = long_term_retrieval__force_base_jours = 2,8`,
`k = memoire__force_k_importance = 6`, `FORCE_MAX = memoire__force_max_jours = 30` et `I` la
gravité : 2,8 jours pour un trajet banal, 19,6 pour un souvenir `marquant` (I = 1). Chaque
passage au top-K ajoute `memoire__force_delta_rappel_jours = 1` jour, sous le même plafond.

```python
def _time_decay_score(self, timestamp_str, query_at, entree=None) -> float:
    if query_at is None:
        return 0.0
    if entree is not None:
        if not entree.est_episodique:                 # concept, résumé
            return float(entree.confiance)
        reference = entree.horodatage_de_reference    # dernier_rappel, sinon timestamp
        force = entree.force
    else:                                             # nœud sans entrée autoritaire
        reference = datetime.fromisoformat(timestamp_str)
        force = None                                  # → S0
    # `gama_timestamp` et non `.timestamp()` : les deux côtés sont en heure MURALE
    time_diff = max(0, (query_at - gama_timestamp(reference)) / 86400)  # en jours
    return poids_temporel(time_diff, force)           # exp(-Δt / force)
```

Sans entrée autoritaire, c'est-à-dire une entrée écrite avant le lot 1 ou un test qui ne fournit
que des nœuds, le calcul retombe sur l'horodatage de l'index et sur `S0`. Sans horloge simulée,
le terme vaut 0.

Le paramètre est une **constante de temps en jours** depuis le ticket 048, et non plus une
base d'exponentielle. Le défaut de 2,8 jours reproduit exactement l'ancienne base de 0,7 par
jour, à trois décimales : un écart mesuré après ce changement est donc attribuable aux
mécanismes nouveaux et non à un oubli silencieusement accéléré. Un paramètre en jours se
discute — « un souvenir ordinaire dure trois fois plus longtemps » — là où une base
d'exponentielle ne se discute pas ; c'est lui que les bras de sensibilité des expériences
doivent viser, la conversion depuis un λ déclaré étant `force = 1 / λ`.

Le lot 1 du ticket 071 a levé les deux limites que cette composante portait jusque-là. Elle
partait de la **date d'écriture**, là où Park et al. (2023) font décroître depuis le dernier
rappel : un souvenir relu chaque matin s'effaçait comme s'il n'avait jamais servi. Et sa
constante était **uniforme**, indifférente à la gravité de ce qui est mémorisé.

⚠ Les deux termes de la soustraction doivent porter **la même convention** : `query_at` est
un horodatage GAMA (heure murale) et `timestamp` un `datetime` naïf aux champs muraux. Avant
le 2026-09-04, les deux erreurs s'annulaient par construction (le souvenir était écrit et
relu dans le fuseau du processus) ; corriger l'écriture sans corriger cette lecture aurait
ajouté une heure d'ancienneté fictive à chaque souvenir.

Pour un souvenir épisodique jamais rappelé :

| Ancienneté | Trajet banal, force 2,8 j | Ancienne base 0,7 | `marquant`, force 19,6 j |
|-----------|-----------|-----------|-----------|
| 0 jours   | 1.000     | 1.000 | 1.000 |
| 1 jour    | 0.700     | 0.700 | 0.950 |
| 3 jours   | 0.343     | 0.343 | 0.858 |
| 7 jours   | 0.082     | 0.082 | 0.700 |
| 14 jours  | 0.007     | 0.007 | 0.490 |

La demi-vie est d'environ **1,94 jour** (`ln(2) × 2,8`) pour un trajet banal, inchangée depuis
le ticket 048, et de **13,6 jours** pour un souvenir `marquant`.

#### Composante 3 — Gravité (`_grav`, poids 0,20)

`entree.importance`, sur [0, 1], lue telle quelle. C'est la composante d'importance de Park et
al. (2023), restaurée au lot 2. Son calcul, un plancher déterministe tiré de ce que la
simulation a mesuré puis le jugement du modèle à la réflexion, est décrit en partie III,
lot 1. Un nœud sans entrée autoritaire vaut 0.

#### Composante 4 — Affinité d'axes (`_axes`, poids 0,20)

`affinite_axes` (`llm/axes.py`) compare les axes du souvenir, normalisés à l'écriture, à ceux
du contexte de la décision :

```text
_axes = 0.50 × [axe_objet concorde] + 0.20 × [axe_lieu concorde]
      + 0.15 × [axe_creneau concorde] + 0.15 × [axe_motif concorde]
```

C'est un bonus et jamais un veto : un axe discordant contribue zéro. Un axe absent aussi, d'un
côté comme de l'autre, car `None` ne concorde avec rien, pas même avec `None`. L'objet courant
est l'ensemble des modes offerts : un souvenir de vélo concorde dès que le vélo figure parmi
les options. Le contexte de décision (`llm_agent.py`, seul appelant qui en fournit un) porte
`axe_lieu = None` : le lieu ne concorde donc jamais au rappel, et `_axes` plafonne à 0,80.

#### Composante 5 — Météo (`_cat`, poids 0,10)

`affinite_meteo(entree.axe_meteo, contexte["axe_meteo"])` (`llm/axes.py`) vaut 1 si la météo
du souvenir concorde avec celle de la décision, 0 sinon ou si l'une des deux manque. Le poids
garde le nom `keyword_weight` pour ne pas casser les surcharges d'expérience existantes.

⚠ **Ce terme ne mesure plus aucun recouvrement lexical** depuis l'arbitrage du 2026-09-14
(issue A, `specs/ticket_071/tests_lot2.md` § 8.1). Jusqu'au lot 2, il pesait un taux de rappel
lexical entre la requête et le champ `tags` de l'entrée, appelé « BLEU-2 » d'après Vu, Gaudou &
Oberoi (2025) sans en être un : le BLEU de Papineni et al. (2002) est une moyenne géométrique de
précisions d'n-grammes assortie d'une pénalité de brièveté. Le lot 2 devait le remplacer par
une affinité catégorielle sur le mode, le créneau, le motif et la météo. Trois de ces quatre
attributs étant déjà des axes de la composante 4, ils auraient compté deux fois, avec des poids
différents : seule la météo est restée.

`_bleu_score` existe encore dans `llm/longterm.py`, mais seuls les tests l'appellent. Le
classement ne lit plus les `tags`, et `long_term_retrieval__default_reflection_importance_score`,
qui servait de repli aux entrées sans `tags`, n'est plus lu par aucun code.

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
def cleanup_user_memories(person_id, days_threshold=30, now=None):
    sim_now = now or _sim_now(person_id)      # souvenir le plus récent de l'agent
    if sim_now is None:
        return                                 # on ne nettoie RIEN plutôt que de deviner
    for entry in entries:
        if not entry.est_episodique:           # concepts, résumés
            keep                               # jamais l'horloge (lot 3 : la contradiction)
        age = sim_now - entry.horodatage_de_reference   # depuis le DERNIER RAPPEL
        keep if (
            age <= days_threshold              OR   # plancher de sécurité
            exp(-age / entry.force) >= memoire__purge_seuil_poids
        )
    _delete_from_index(supprimés)              # retrait du vector store
```

⚠ **La règle a changé le 2026-09-14** (ticket 071, lot 1). Elle reposait sur un seuil d'âge
commun plus une exemption par **type** : les réflexions et les résumés ne partaient jamais. Deux
conséquences fâcheuses, que le lot 1 corrige : un souvenir grave de trente et un jours tombait
avec les trajets ordinaires, et les réflexions s'accumulaient sans fin.

Deux registres, comme la taxonomie de Tulving (1972) le demande :

| Registre | Ici | Ce qui l'efface |
|---|---|---|
| **Sémantique** | concepts, résumés | la **contradiction**, jamais l'horloge (lot 3) |
| **Épisodique** | entrées brutes, réflexions | le **poids temporel** sous 1 %, soit ~4,6 constantes de temps |

Treize jours pour un trajet banal jamais rappelé, quatre-vingt-onze pour un souvenir
`marquant` : donc **jamais dans un run**. C'est désormais la gravité, et le nombre de rappels,
qui décident de la survie — plus le seul calendrier. `days_threshold` reste un **plancher de
sécurité** : rien de plus jeune n'est purgé, il ne peut que retarder une purge.

⚠ **Le seuil se calcule en temps SIMULÉ depuis le 2026-09-14** (ticket 071, défaut A). Il se
calculait auparavant sur `datetime.now()`, l'horloge de la **machine hôte**, alors que
`entry.timestamp` porte l'heure murale de GAMA. Dès qu'un run rejouait une date antérieure de
plus que le seuil, la condition de conservation était fausse pour **toutes** les entrées, et le
nettoyage vidait concepts et conversations en bloc. Le défaut n'a jamais pu se produire, son
seul déclencheur demandant dix mille entrées pour un agent, soit près de quatorze cents jours
simulés.

Le « maintenant » d'un agent est le souvenir le plus récent qu'il porte. **Un nettoyage qui ne
sait pas dater ne nettoie rien** : jamais de repli sur l'horloge de la machine, une suppression
ne devant pas dépendre de la date à laquelle le run a été lancé.

⚠ **Les entrées retirées sortent aussi de l'index vectoriel** depuis la même date (défaut B).
Sans cela, un souvenir absent des métadonnées continuait d'être renvoyé par ChromaDB et
réinjecté dans les prompts. Trois précisions. L'identifiant de document est désormais **monotone
et persisté** (`next_doc_index`), là où il dérivait de la longueur de la liste et entrait donc
en collision après un nettoyage. Une suppression qui échoue est journalisée et **non propagée** :
elle ne doit pas faire perdre la mise à jour des métadonnées. Et les entrées écrites avant ce
ticket n'ont pas d'identifiant, donc ne sont pas adressables : elles sortent des métadonnées et
restent dans l'index, ce qui est signalé en WARNING.

**Résiduel assumé.** Un second chemin de divergence subsiste, indépendant du nettoyage : les
entrées d'un format non relisible sont ignorées au chargement des métadonnées et restent dans
l'index. Le fermer demanderait de vérifier l'appartenance de chaque document aux métadonnées
actives à chaque rappel. Écarté comme disproportionné, consigné pour ne pas être oublié.

Les réflexions et résumés sont **toujours conservés** indépendamment de leur âge. Seules les entrées CONCEPT ou CONVERSATION antérieures au seuil sont supprimées.

⚠ **Jusqu'au ticket 071, aucune notion d'importance n'existait dans le dispositif.**
`MemoryEntry` ne portait pas de champ d'importance : la rétention ne connaissait que l'âge et le
type, et le score composite que la similarité, le recouvrement lexical et l'ancienneté. Un
retard de 45 minutes et un trajet nominal étaient conservés et rappelés du même poids. Le champ
`importance` existe depuis le lot 1 : il fixe la durée de vie du souvenir, et il pèse 0,20 au
classement depuis le lot 2 (étape 2, composante 3).

**L'origine de cette absence est documentée.** Park et al. (2023) portent une importance,
demandée au modèle sous forme d'entier de 1 à 10 sur une échelle ancrée par deux exemples, et
s'en servent à la fois au classement et au déclenchement de la réflexion. Vu, Gaudou & Oberoi
(2025) ne la reprennent pas — le mot n'apparaît pas dans leur article — et lui substituent le
score BLEU-2. Le paramètre `long_term_retrieval__default_reflection_importance_score` (0.2)
est le vestige de cette substitution : son nom dit *importance*, mais il servait de valeur de
repli au BLEU pour les entrées sans `tags`, c'est-à-dire les réflexions narratives. Aucun code
ne le lit depuis le lot 2.

La gravité réintroduite est décrite en **partie III, lot 1**.

### Éviction LRU du cache RAM

Lorsque plus de 2 000 agents sont en RAM, les plus anciennement accédés sont flushés sur disque avant d'être retirés du dict Python, puis un `gc.collect()` libère la mémoire.

---

## La mémoire noyau (ticket 071, lot 4)

Les dix souvenirs bruts servis au modèle sont remplacés par un **bloc permanent structuré**,
complété de deux ou trois entrées épisodiques rappelées pour la décision en cours. C'est le
*working context* de MemGPT (Packer et al., 2023, § 2.1).

```
Mes habitudes                                 [ produit par le JOURNAL DES TRAJETS ]
- work le matin : à vélo, 9 fois sur 11. 2 retard(s) de plus de 10 min

Ce que je sais                                        [ produit par les CONCEPTS ]
- Le bus 401 est fiable, sauf les jours de pluie.                          (12 obs.)

Ce qui a changé récemment                    [ produit par les CHOCS et les MISES À L'ÉCART ]
- Je ne crois plus que : la ligne A est fiable
```

**Les trois blocs sont CALCULÉS, aucun n'est écrit par le modèle**, et le lot ne coûte donc
aucune inférence supplémentaire. La spécification ne calculait que les habitudes et confiait les
connaissances au modèle ; depuis le lot 3, un concept porte son compteur d'observations, sa
confiance et son état de service, si bien que le bloc se calcule exactement. L'argument du
garde-fou — un texte réécrit périodiquement par un modèle dérive et invente — vaut pour les trois.

**Le bloc ne porte aucune métadonnée sur lui-même** : ni date de mise à jour, ni nombre de jours
de vécu. Une personne ne pense pas « mon résumé d'habitudes date de trois jours » ; lui donner
cette phrase l'invite à raisonner sur le mécanisme de sa mémoire au lieu de raisonner sur son
trajet. Un bloc vide est **absent**, et non présent avec un titre : un titre sans contenu dit au
modèle qu'il devrait y avoir quelque chose.

**Le journal des trajets n'existait pas** et a été créé : `MoveLogger` écrit dans `moves.csv` et
rien d'autre, `PersonState` ne garde aucun historique, et relire un CSV à chaque décision est
exclu. C'est un compteur par agent — modes retenus et retards subis, par couple motif-créneau —
**persisté avec les métadonnées de l'agent**, ce qui réutilise l'écriture différée en place. Il
est alimenté à l'ARRIVÉE, seul endroit où le mode retenu et le retard réellement subi sont connus
ensemble.

⚠ **Le mode ne se relit pas dans la mémoire courte** (ticket 077, lot C, révisé le 2026-09-15).
Une première version cherchait, à l'arrivée, l'entrée de décision du trajet dans le tampon court.
Les consolidations vident ce tampon entre le départ et l'arrivée : la décision avait le plus
souvent disparu, et le journal enregistrait **2 trajets pour 40 arrivées** — le bloc « Mes
habitudes » était alors absent de **tous** les prompts de décision. Le contrôleur note donc le
mode retenu au moment de la DÉCISION, dans une table `(agent, activité) → mode` purgée à la
lecture. Le motif et le créneau, eux, viennent de l'arrivée : ce sont les seuls qu'elle porte.

Le dernier bloc est l'endroit où l'hystérésis devient lisible dans le prompt lui-même, et non
plus seulement dans les statistiques de sortie.

### Les lignes garanties passent en tête du dernier bloc (ticket 111)

Une lecture d'article (`[ PRESSE ]`) ou un message du lecteur (`[ FOYER ]`) est **servi au rendu**
pendant ses jours de service, sans passer par le rappel ni par le seuil de gravité
(`memoire__importance_choc`). `bloc_changements(entrees, maintenant, person_id, lignes)` et
`memoire_noyau(…, lignes)` reçoivent ces lignes à part, et trois règles les régissent :

- elles viennent **en premier** dans « Ce qui a changé récemment » ;
- elles ne comptent pas dans `memoire__changements_max` : un choc récent ne les évince pas, et
  elles n'évincent pas un choc ;
- une entrée de mémoire dont le `content` est exactement une ligne servie est **sautée** — une
  lecture jugée grave ne paraît pas deux fois.

```
Ce qui a changé récemment
- [ PRESSE ] This morning I read in the paper: « (Translated from French) Gusts… »
- Je ne crois plus que : la ligne A est fiable
```

Sans ligne à servir — pas d'événement, choc vécu, service terminé — le bloc est **identique à
l'octet près** à celui d'avant. Si le noyau échoue à se construire, le bloc de repli garde les
lignes : une décision ne perd pas sa lecture parce qu'un autre bloc a cassé. Détail et
calendrier du service dans [`evenements.md`](evenements.md#ce-que-lagent-a-lu-est-devant-lui-quand-il-décide-ticket-111).

L'entrée longue de l'article (et, chez un membre informé, celle du message, `origine: entendu`)
reste écrite à l'injection : c'est elle qui concourt au rappel **après** le service. Son
écriture est désormais **attendue**, comme le jugement.

### La durée d'un choc se DÉRIVE de sa gravité (ticket 095, lot A)

Un souvenir de gravité de choc est servi dans « Ce qui a changé récemment » **tant que son poids
de décroissance dépasse un seuil**. La durée n'est plus un entier posé : elle se calcule, souvenir
par souvenir, à partir de la gravité de l'événement.

```
poids(t) = exp(-t / force)        force = min(S0 × (1 + k × gravité), 30)   S0 = 2,8   k = 6
durée    = force × ln(1 / SEUIL)                                           SEUIL = 0,35
servi    = max(PLANCHER, min(PLAFOND, durée))                 PLANCHER = 2 j  PLAFOND = 30 j
```

C'est la MÊME courbe que celle du rappel (MemoryBank, Zhong et al. 2024) : la durée d'un effet
cesse d'être un paramètre posé à côté du modèle d'oubli pour en devenir une conséquence.

| Gravité | force | durée servie | Exemple |
|---:|---:|---:|---|
| 0,10 | 4,48 j | **4,70 j** | contrariété |
| 0,30 | 7,84 j | **8,23 j** | incident mineur |
| 0,62 | 13,22 j | **13,88 j** | bouchon C1 au jour 2 — sous le seuil d'entrée du bloc |
| 0,70 | 14,56 j | **15,29 j** | C6, moteur suspect — la gravité mesurée au ticket 077 |
| 0,90 | 17,92 j | **18,81 j** | C3, panne réseau |
| 1,00 | 19,60 j | **20,58 j** | maximum atteignable par la gravité |

**L'âge se compte depuis l'ÉVÉNEMENT**, pas depuis le dernier rappel : ce bloc annonce
l'ancienneté d'un changement, pas celle de sa dernière lecture. Le renforcement au rappel
continue de jouer, mais par la `force`, donc sur la durée — il ne rajeunit pas l'événement.

**Aucune des deux bornes ne mord, et il ne faut citer ni « 2 » ni « 50 » comme durées
observées.** `borne_0_1` plafonne la gravité à 1,0 : la durée maximale issue de la gravité vaut
20,58 j et la durée minimale 2,94 j à gravité nulle — donc au-dessus du plancher de 2 j.

Ce qui borne réellement par le haut est `memoire__force_max_jours = 30`, via le renforcement au
rappel : `force_apres_rappel` ajoute un jour par rappel jusqu'à 30, et à force = 30 la durée vaut
**31,49 j**. C'est LE plafond du dispositif, et c'est lui qui empêche un souvenir souvent rappelé
de repousser indéfiniment son échéance dans un bloc de taille fixe (`changements_max = 3`) — la
fenêtre cesserait d'être une fenêtre pour devenir une archive.

`memoire__plafond_changement_jours` vaut **50 j depuis le 2026-09-22** (auparavant 30). Comme
31,49 < 50, il ne peut plus mordre. Il est conservé comme **témoin** : `DureeService.borne` le
journalise s'il mord, et une telle ligne signalerait que la loi de décroissance ou le plafond de
force a bougé sans qu'on le remarque. Le garde-fou sur le coût d'un run est passé au protocole —
horizon de 50 jours, l'arrêt normal restant l'extinction du souvenir suivie de sept jours vécus.

⚠ Le commentaire précédent de ce paragraphe affirmait que sans le plafond de durée « un souvenir
souvent rappelé repousserait indéfiniment son échéance ». C'était faux : le renforcement sature
au plafond de force, et la protection vient de là.

### Le mode `fixe`, et pourquoi il reste

`memoire__mode_fenetre_changements` vaut `derivee` par défaut depuis le 2026-09-21. À `fixe`, le
comportement d'avant le ticket 095 revient : un souvenir de gravité de choc est servi tant qu'il a
moins de `memoire__fenetre_changements_jours` jours — **14 par défaut** — puis **plus du tout**.
Coupure franche, et non décroissance : la force du souvenir n'entre pas dans cette décision.

C'est le mode des **bras de contrôle méthodologique**, ceux qui doivent reproduire les campagnes
des 19 et 20 septembre 2026. ⚠ **Un run archivé ne se compare à un run neuf qu'en déclarant
`fixe`.**

⚠ **Ce paramètre gouverne la durée observable d'un effet de choc, et il était écrit en dur.**
Sur `experiments/archive/2026-09-19_07_31`, le choc tombe le 30 mars ; le récit quitte le bloc
le 13 avril, quatorze jours plus tard jour pour jour.

| | P(voiture) annoncée par le modèle |
|---|---|
| tant que le récit est dans le prompt | **6,9 %** (n = 18) |
| une fois sorti | **55,2 %** (n = 33) |

La bascule se produit **d'un prompt à l'autre** : 5 % au dernier qui le porte, 60 % au premier
qui ne le porte plus. Le rapport du run attribuait ce retour à la décroissance exponentielle du
souvenir, dont la durée de vie calculée valait ~14,6 jours. Les deux explications prédisent la
même date, et rien dans le dispositif ne permettait de les départager — c'est pour cela que le
paramètre est devenu un réglage : à 7 et à 21 jours, elles ne prédisent plus la même chose.

**La valeur 0 est l'ablation déclarée** : aucun souvenir de choc n'entre dans le bloc. Une valeur
négative est ramenée à 0 et journalisée — elle ne doit pas se lire comme un réglage accepté.

**Deux fenêtres, volontairement.** Seule celle des souvenirs de choc est réglable. Celle des
croyances mises à l'écart reste la constante historique de 14 jours : les faire varier ensemble
confondrait deux changements dans une seule mesure.

**La sortie de fenêtre se journalise**, une fois par souvenir et par agent, au front montant :

```
[noyau] 899549 : le souvenir de choc du 2026-03-30 est sorti du bloc « ce qui a changé
        récemment » (durée 15.29 j dérivée d'une gravité de 0.70 (force 14.56 j, durée
        calculée 15.29 j)) — plus aucun souvenir de choc ne pèse sur ses décisions.
```

Elle porte **ce qui a produit la durée**, et non la seule date : gravité, force, durée calculée,
et le nom de la borne quand une borne a mordu. Une durée servie sans sa cause ne se vérifie pas
après coup — c'est exactement ce qui a rendu indiscernables, deux jours durant, la décroissance
du souvenir et la coupure de fenêtre. En mode `fixe`, la ligne nomme la fenêtre en jours et ne
prétend à aucune durée dérivée.

Sans cette ligne, l'événement n'était lisible qu'en relisant le texte des prompts après le run.

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

### Observation (ticket 077)

| Paramètre | Défaut | Effet |
|-----------|--------|-------|
| `trace_rappel_enabled` | false | Écrit une ligne JSONL par rappel dans `trace_rappel.jsonl` : le top-K servi, avec pour chaque souvenir son identifiant, son type, son **vivier d'origine**, son score composite et son rang. Éteint, rien n'est écrit — mais la **mesure de concentration** tourne toujours, elle ne coûte qu'un compteur borné en RAM. |
| `trace_rappel_file` | `trace_rappel.jsonl` | Destination de la trace, résolue dans le répertoire de run. |

### Récupération

| Paramètre | Défaut | Effet |
|-----------|--------|-------|
| `long_term_max_entries_query` | 10 | Top-K renvoyé au LLM |
| `long_term_max_days_query` | 60 | Fenêtre de look-back en jours. Portée de 30 à 60 au ticket 071, lot 0. Vaut l'**horizon de l'expérience**, plafonné par `memoire__fenetre_age_max_jours` : `experiences/cli.py` l'applique depuis `horizon_jours` au lancement. À 30 jours en dur, un run de soixante perdait son second mois sans qu'aucune ligne ne le dise. |
| `long_term_retrieval__sim_weight` | 0.30 | Poids de la similarité sémantique, qui vaut `exp(cos − 1)` et non le cosinus (étape 2, composante 1). 0,4 avant le lot 2. |
| `long_term_retrieval__keyword_weight` | 0.10 | Poids de l'appariement de **météo**, et de lui seul (arbitrage du 2026-09-14). Nom conservé pour les surcharges d'expérience : il pesait le score dit BLEU, à 0,3, avant le lot 2. |
| `long_term_retrieval__time_weight` | 0.20 | Poids du terme temporel : `exp(-Δt / force)` pour un souvenir épisodique, confiance de Laplace pour un concept ou un résumé. 0,3 avant le lot 2. |
| `long_term_retrieval__importance_weight` | 0.20 | Poids de la gravité du souvenir. Déclaré au lot 0, lu depuis le lot 2. |
| `long_term_retrieval__affinite_weight` | 0.20 | Poids de l'affinité d'axes (objet, lieu, créneau, motif). Déclaré au lot 0, lu depuis le lot 2. Les cinq poids somment à 1,00. |
| `long_term_retrieval__force_base_jours` | 2.8 | Constante de temps de l'oubli, en jours |
| `long_term_retrieval__default_reflection_importance_score` | 0.2 | ⚠ **Lu par aucun code** depuis le lot 2. Nom trompeur : c'était la valeur de repli du score BLEU pour les entrées sans `tags`, pas une importance. |
| `long_term_memory_filter_by_datetime` | false | Active deux filtres supplémentaires sur le vivier : même classe de jour (ouvré/week-end) et même tranche horaire que la requête. Se **cumule** avec la fenêtre d'âge depuis le ticket 071 ; il l'annulait auparavant. Coupe le vivier, à manier avec la règle de non-exclusion du lot 2 en tête. |

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

### Les alarmes du ticket 077

| Alarme | Seuil | Ce qu'elle dit |
|---|---|---|
| `aucune croyance montrée au modèle dans N %` | 50 % sur 50 réflexions | Le panier `(mode, motif)` ne désigne aucun candidat. Le modèle ne peut ni confirmer ni préciser : il ne lui reste qu'à créer, et les concepts s'empilent en reformulations. **C'est la garde du lot A** : vérifier d'abord que les axes d'objet ne sont pas vides. |
| `concentration des rappels à N %` | 80 % sur 200 rappels, réarmée sous 65 % | Les dix souvenirs les plus servis occupent la quasi-totalité du top-K. Le rappel s'auto-renforce : ce que l'agent a appris tôt évince ce qu'il apprend ensuite. ⚠ Un rappel qui sert **tout** ce que l'agent possède n'entre pas dans la mesure : sans cette garde, l'alarme se levait au cinquième jour simulé et ne mesurait que la taille de la mémoire, pas une sélection. |

Les deux se déclenchent sur **front montant** et se réarment sous un seuil bas. Sans hystérésis,
une valeur qui oscille autour d'un seuil unique inonderait le journal.

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
- [ticket 048](../tickets/ticket_048_calendrier_de_consolidation_et_echelle_d_oubli.md) — le calendrier de consolidation, l'échelle d'oubli et le coût des réflexions (**clos le 2026-09-21** ; son reliquat est le lot F du ticket 095)
- [ticket 095](../tickets/ticket_095_duree_d_un_souvenir_et_enquete_du_soir.md) — la durée d'un souvenir dérivée de sa gravité, l'enquête du soir, et le reliquat du 048
- [ticket 071](../tickets/ticket_071_evolution_memoire_du_code_actuel_a_l_etat_vise.md) — les quatre défauts du rappel et du nettoyage, issus d'une expertise externe

---

# Partie III — Évolutions spécifiées, non implémentées

> **Rien de ce qui suit n'existe dans le code.** Cette partie est une spécification, pas une
> description. Elle est ordonnée en quatre lots, du moins au plus dépendant. Aucun ne coûte
> d'appel supplémentaire au modèle : tout ce que le modèle y produit est demandé à l'intérieur
> des réflexions qui ont déjà lieu.
>
> Préalable livré : le [ticket 048](../tickets/ticket_048_calendrier_de_consolidation_et_echelle_d_oubli.md),
> **clos le 2026-09-21**. Ce qu'il n'avait pas exécuté — la mesure du taux d'entrées par agent-jour,
> la garantie « avant le réveil », le rejeu des mesures min-max et la conversion d'`experiments.yaml`
> — est le **lot F** du [ticket 095](../tickets/ticket_095_duree_d_un_souvenir_et_enquete_du_soir.md).

## Trois règles

1. **Un souvenir est qualifié, pas seulement daté.** Il porte une gravité, et cette gravité
   décide de sa durée de vie et de son poids au rappel. C'est le retour de la composante
   d'importance de **Park et al. (2023)**, écartée par Vu et al. (partie I, écart n° 1).
2. **Un concept se corrige au lieu de s'empiler.** Une connaissance est un objet unique qui se
   confirme, se précise ou se voit contredire, avec un compteur derrière. C'est le principe
   d'extraction-puis-mise-à-jour de **Mem0, Chhikara et al. (2025)** et de l'évolution des
   notes d'**A-MEM, Xu et al. (2025)**.
3. **Au rappel, rien ne filtre, tout pondère.** Hors identité de l'agent et fenêtre d'âge,
   aucun critère n'exclut un souvenir. La justification est au lot 2.

---

## Lot 1 — La gravité d'un souvenir

> ✅ **LIVRÉ le 2026-09-14.** Ce lot n'est plus une spécification, c'est le dispositif en
> service : la gravité déterministe (`llm/gravite.py`), les huit champs de `MemoryEntry` plus
> `dernier_rappel`, la durée de vie couplée à la gravité, le renforcement additif au rappel, la
> décroissance depuis le dernier rappel, le déclenchement par rupture et la rétention par le
> poids. Voir la **partie II** pour la description de ce qui tourne ; ce qui suit garde le
> raisonnement et les sources, qui se transportent à l'article.
>
> **Deux écarts avec le texte ci-dessous, décidés en cours de route :**
> 1. la formule de départage est corrigée (départage nul pour un concept seul, gravité bornée
>    sur [0, 1]) — voir plus bas ;
> 2. un champ `dernier_rappel` s'ajoute aux huit, distinct de `timestamp` qui reste l'heure de
>    l'ÉVÉNEMENT : celui-ci s'affiche dans le prompt et le faire glisser au rappel réécrirait
>    l'histoire de l'agent.
>
> **Ce qui n'est PAS alimenté** : la composante « incident réseau » de la gravité déterministe.
> GAMA ne joue pas encore les événements. La chaîne est posée de bout en bout et la composante
> est **déclarée inactive** au démarrage — une composante sans source contribue zéro, et zéro
> est exactement la valeur d'un trajet parfait. Les trois autres ne sont pas repondérées.
>
> Tests : `test_071_lot1_gravite.py` (57) et `test_071_lot1_chaine.py` (27).


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
ecart(n, rang) = 0                              si n = 1      # rien à départager
               = 2 × (n - rang) / (n - 1) - 1   sinon         # +1 au premier, -1 au dernier

I_llm = borne_0_1( valeur(niveau) + 0.05 × ecart(n_niveau, rang_dans_niveau) )
```

> ⚠ **Corrigée le 2026-09-14, deux défauts trouvés en rédigeant les tests du lot 1**
> (`specs/ticket_071/tests_lot1.md`, § 9). La formule précédente était
> `valeur + 0,05 × (2 × (n - rang) / max(n - 1, 1) - 1)`.
>
> **Un concept seul dans son niveau était pénalisé de 0,05.** Avec `n = 1`, le terme valait
> `2 × 0 / 1 - 1 = -1` : un `marquant` seul tombait à 0,95, un `genant` seul à 0,45. Or « seul
> dans son niveau » est le cas le plus courant, une réflexion rendant zéro à cinq concepts. Le
> départage vaut désormais **zéro** quand il n'y a qu'un candidat.
>
> **La gravité pouvait dépasser 1.** Un `marquant` premier de trois valait 1,05, et la durée de
> vie qui en découle passait de 19,60 à 20,44 jours. La borne existait pour `I_det`, elle
> manquait pour `I_llm` : elle est ajoutée.
>
> Aucun code n'est concerné, rien n'était implémenté. Les valeurs de la table ci-dessus sont
> inchangées : seuls les cas limites bougeaient.

**Règle de sécurité, non négociable.** La gravité retenue pour un concept est le **maximum**
entre le jugement du modèle et la plus forte gravité déterministe du groupe d'entrées dont il
est issu. Un modèle qui sous-estime un incident de quarante-cinq minutes ne peut donc pas le
dégrader : le fait mesuré l'emporte toujours sur le jugement.

```
I_concept = max(I_llm, max(I_det des entrées consommées))
```

### Déclenchement par gravité cumulée

Le seuil de réflexion passe d'un **compte d'entrées** à une **somme de gravités**, ce qui est le
mécanisme de Park et al. (2023), seuil fixé à 150 chez eux sur une échelle de 1 à 10.

> ✅ **Arbitrage rendu et confirmé par l'auteur le 2026-09-14** (ticket 071, § 2.6, arbitrage 2).
> **Le plancher journalier de 22 h, livré au ticket 048, est le régime de consolidation.** Le
> déclenchement par gravité cumulée n'intervient en cours de journée que sur **rupture**,
> `I_cumul ≥ Θ`, avec `Θ = 0,7`, le seuil du choc. La réflexion par déplacement, un temps envisagée, est
> **abandonnée**. Trois raisons : la consolidation mnésique humaine est favorisée par le sommeil
> et les périodes hors ligne (Diekelmann & Born, 2010), et l'extraction des régularités relève
> d'un rejeu différé dans l'architecture à deux systèmes (McClelland, McNaughton & O'Reilly,
> 1995) ; Vu et al. (2025, § 3.6) spécifient la réflexion à la fin de chaque jour simulé ; et le
> coût mesuré au ticket 048 rend le régime par déplacement inutile, +22 % sur la campagne pour
> une réactivité que rien ne réclame. Différence avec Park et al. à dire : chez eux le seuil se
> franchit deux ou trois fois par jour, c'est un régime courant ; ici il est exceptionnel par
> construction de `Θ`. **La mesure de `I_det` par agent-jour** sert à vérifier que ce seuil reste
> exceptionnel, moins d'un déclenchement par agent et par semaine, et à le relever sinon. Cette
> mesure était portée par le ticket 048 ; depuis la clôture de celui-ci le 2026-09-21 elle est au
> **lot F1 du [ticket 095](../tickets/ticket_095_duree_d_un_souvenir_et_enquete_du_soir.md)**, qui
> la relèvera sur les campagnes E2/E3 — les premiers runs GAMA courants sur cohorte v5.

### Oubli : une courbe, et un plancher

Chaque souvenir porte une constante de temps, fixée à l'écriture selon sa gravité. Le mécanisme
est celui de **MemoryBank, Zhong, Guo, Gao, Ye & Wang (2024)**, qui applique la courbe d'oubli
d'Ebbinghaus et fait croître la force d'un souvenir à chaque rappel.

```
force_initiale = min(S0 × (1 + k × importance), FORCE_MAX)   # S0 = 2.8 jours, k = 6, FORCE_MAX = 30 jours
```

`S0` vaut 2,8 jours **pour reproduire exactement la décroissance en service** : un `S0` plus
court accélérerait l'oubli en silence, et tout écart mesuré ensuite deviendrait inattribuable.
Sa règle de conception, écrite le 2026-09-14 : un trajet banal pèse moins de 10 % après une
semaine, `exp(-7/2,8) = 0,08`. Son origine est à dire honnêtement dans l'article : la base de
0,7 par jour est héritée de l'implémentation de Vu et al., **leur article donne la formule mais
pas la valeur**.

`k` vaut 6, et non 3 comme dans la première version de cette partie. La règle vient de l'ancre
textuelle du niveau `marquant`, « je m'en souviendrai dans un mois » : un tel souvenir garde la
moitié de son poids à deux semaines et un cinquième à trente jours. À `k = 3` il tombait à 7 %
en un mois, ce qui contredisait la phrase qui le définit.

| Niveau | Gravité | Durée de vie initiale | Poids à 7 j | à 14 j | à 30 j | à 60 j |
|---|---|---|---|---|---|---|
| trajet nominal | 0 | 2,8 j | 0,08 | 0,007 | — | — |
| `genant` | 0,50 | 11,2 j | 0,54 | 0,29 | 0,07 | 0,005 |
| `grave` | 0,75 | 15,4 j | 0,63 | 0,40 | 0,14 | 0,02 |
| `marquant` | 1,00 | 19,6 j | 0,70 | 0,49 | 0,22 | 0,05 |

Le plafond `FORCE_MAX` s'applique dès l'écriture : aucune durée de vie ne le dépasse, y compris
dans le bras de sensibilité où `S0` triple.

```
score_temps = exp(-Δt / force)
```

> ⚠ **Révision du 2026-09-14, après expertise externe.** Une version antérieure ajoutait un
> **plancher** sous cette courbe, `max(exp(-Δt/force), φ × importance)`, pour qu'un choc ne
> s'efface jamais. Ce plancher est **supprimé**, pour deux raisons.
>
> **Le triple compte.** La gravité entrait alors trois fois dans le score : par la constante de
> temps, par le plancher, et comme composante propre. Or l'expérience d'hystérésis a pour
> critère de réfutation pré-enregistré qu'un allongement de la constante de temps déplace la
> courbe de reprise. Avec trois canaux confondus, l'effet de l'oubli devient inséparable de
> l'effet de la gravité, et le critère ne mesure plus ce qu'il prétend mesurer.
>
> **Le contresens psychologique.** Un plancher fige la composante d'**ancienneté**, ce qui
> revient à poser que le temps cesse de s'écouler pour un souvenir grave. Ce n'est pas ce que
> décrit la psychologie du souvenir marquant : la personne sait parfaitement que l'événement est
> ancien. Ce qui reste élevé n'est pas sa récence, c'est son **accessibilité** et son **poids
> décisionnel**.

La persistance d'un choc est donc portée par les deux mécanismes qui la portent honnêtement :
une **constante de temps allongée** par la gravité, qui donne près de vingt jours à un souvenir
`marquant` contre moins de trois à un trajet banal, et le **vivier des chocs** du lot 2, qui
injecte ces souvenirs dans les candidats sans condition de contexte. Aucun des deux ne falsifie
la décroissance temporelle.

**Découplage : tranché le 2026-09-14, il n'y en a pas.** Même sans plancher, la gravité entre
encore deux fois, par la constante de temps et par sa composante propre. Un découplage complet
rendrait `force` indépendante de la gravité, la persistance reposant alors sur le seul vivier
des chocs et sur la composante de gravité : plus propre pour l'ablation, plus pauvre
cognitivement.

> ✅ **Arbitrage rendu par l'auteur le 2026-09-14** (ticket 071, § 2.6, arbitrage 1, issue C).
> **Le couplage `force = S0 × (1 + k × I)` est gardé tel quel, sans interrupteur.** Une relecture
> extérieure proposait de le garder derrière un paramètre d'ablation `α ∈ {0, 1}`,
> `force = S0 × (1 + α × k × I)`, avec `α = 0` réservé à un bras de sensibilité du chapitre 7.
> Ce paramètre n'avait de raison d'être que si le critère de réfutation (ii) du chapitre 7 —
> « diviser la vitesse d'oubli par trois ne déplace pas la courbe » — restait un critère de
> réfutation. **Il a été supprimé**, avec le bras `exp_04d` qui l'exécutait : l'article ne
> prétend pas isoler l'effet causal de l'oubli, la mémoire est un élément du dispositif et non
> son sujet. Sans ce critère, `α` n'a plus d'objet et n'est pas implémenté. Ce qui reste à dire
> devant un relecteur — la sensibilité au paramètre d'oubli choisi — l'est par la règle de
> conception de `S0` et par son second point de sensibilité publié (§ « Paramètres de la
> partie III »), non par un run.

### Ce qui s'oublie au temps, et ce qui ne s'oublie pas

> ⚠ **Ajout du 2026-09-14, après expertise externe.** La décroissance ci-dessus s'appliquait
> indistinctement à **toutes** les entrées, y compris aux concepts. C'est un contresens cognitif.

La taxonomie classique de la mémoire déclarative, d'Endel Tulving à la relecture qu'en donne le
cadre CoALA de Sumers et al. pour les agents de langue, sépare deux régimes qui n'ont pas la
même dynamique d'effacement.

| Registre | Contenu ici | Ce qui l'efface |
|---|---|---|
| **Épisodique** | entrées brutes, réflexions narratives | le **temps**, courbe d'Ebbinghaus, renforcée au rappel |
| **Sémantique** | concepts, résumés | la **contradiction**, jamais l'horloge seule |

Qu'une ligne de bus sature les jours de pluie entre 8 h et 8 h 30 ne devient pas faux parce que
dix jours ont passé. Sous le régime uniforme, ce concept tombait pourtant à moins de 3 % de son
poids initial en dix jours et sortait du top-K, sans qu'aucune observation ne l'ait infirmé.

**Règle retenue.** Pour une entrée de type `concept` ou `summary`, la composante temporelle n'est
plus une décroissance d'horloge mais la **confiance** du lot 3, calculée sur les observations et
les contre-exemples. Un concept jamais contredit garde son poids ; un concept contredit le perd,
quelle que soit son ancienneté. La date de dernière observation reste utilisée, mais comme
départage entre concepts de confiance égale, non comme facteur d'effacement.

```
score_temps(entrée) = exp(-Δt / force)      si épisodique
score_temps(concept) = confiance            = (obs + 1) / (obs + contre_ex + 2)
```

Un concept dont la confiance passe sous **0,5** cesse d'être servi au modèle, sans être
supprimé : sa mise à l'écart datée est la trace du changement d'habitude que l'expérience
cherche à observer. Avec le lissage de Laplace, ce seuil a une lecture exacte : le concept a été
contredit plus souvent que confirmé, `contre_exemples > observations`.

**Le rappel renforce**, pour le registre épisodique, comme chez MemoryBank, et comme chez Park et
al. dont la fraîcheur décroît depuis le **dernier rappel** et non depuis la création (partie I,
écart n° 3).

```
force ← min(force + δ, FORCE_MAX)                  # δ = 1 jour, FORCE_MAX = 30 jours
rappels ← rappels + 1
```

> ⚠ **Révision du 2026-09-14.** La première version renforçait par un facteur, `force × 1,15`.
> Sur un horizon de soixante jours, dix-sept rappels suffisaient à porter un trajet banal au
> plafond, et tout ce qui est rappelé souvent aurait saturé. Le renforcement devient **additif** :
> chaque rappel ajoute un jour de durée de vie. Un trajet banal rappelé vingt fois voit sa
> constante de temps passer de 2,8 à 22,8 jours ; il atteint le plafond en vingt-huit rappels, un
> souvenir `marquant` en onze. C'est aussi plus proche de l'apprentissage de base d'ACT-R, où
> l'effet de la fréquence a des rendements décroissants (Anderson & Lebiere, 1998). Le plafond de
> 30 jours a sa règle : aucun souvenir ne devient éternel, deux mois sans rappel ramènent un
> souvenir au plafond à un huitième de son poids, `exp(-60/30) = 0,14`.

**Conséquence de conception à assumer.** Si le choc ne s'oublie pas, le retour au mode abandonné
ne peut plus s'expliquer par l'oubli. Il doit se gagner : chaque trajet réussi incrémente les
`observations` du concept concerné et relève sa confiance (lot 3). Deux forces opposées
gouvernent la reprise, et c'est cette opposition qui produit une courbe d'hystérésis
interprétable plutôt qu'une décroissance paramétrée. Le protocole d'épreuve est l'**ablation de
mémoire**, comme dans l'étude de grève de taxis publiée dans *Sensors* 25(18), 5688 (2025), et
comme l'exige le degré « robuste » du benchmark SILICA, qui demande qu'un résultat survive à une
remise à zéro de la mémoire.

### Régime Système 1 / Système 2 : évalué, non retenu

> ⚠ **Arbitrage de l'auteur, 2026-09-11, confirmé le 2026-09-14.** Il ne vivait que dans le
> ticket 071 § 2.9 et nulle part dans cette doc — une session qui lit la doc seule reproposait
> le raccourci de routine sans savoir qu'il avait été tranché. Consigné ici le 2026-09-21 au
> titre du ticket 051 § C.

L'expertise du ticket 051 pose la distinction de la psychologie de l'habitude : un déplacement
nominal relève d'un automatisme machinal (Système 1) et n'a pas à mobiliser une délibération
(Système 2). Portée au dispositif, elle donne un court-circuit — dérouler la routine sans
appeler le modèle, et ne le réveiller que sur rupture : retard important, incident réseau,
alerte météo. Le gain serait réel, une journée de 1 000 personas coûtant quelque 3 millions de
tokens (§ 8.3 de l'article).

**Ce n'est pas retenu, et la raison n'est pas le coût.** Coder l'habitude interdirait de montrer
qu'elle émerge. Le reproche que l'expertise adresse par ailleurs au dispositif — un modèle de
fréquences habillé d'une couche de langage — s'appliquerait alors à sa propre proposition : la
répétition observée serait celle que la règle impose.

**Ce qui en tient lieu : la mesure.** Aucune ligne n'impose à un agent de reprendre le mode de
la veille ; la répétition, quand elle apparaît, vient du rappel de ses propres trajets.
L'observable est la décroissance de l'entropie des choix d'un même agent au fil des jours
simulés, sur la fenêtre longitudinale du § 7.2 de l'article. `make mesures RUN=…` porte déjà la
part décidée et l'habitude ou la rupture par activité, par jour simulé (ticket 093) ; l'entropie
par agent n'est pas encore calculée. Un court-circuit de routine devient une optimisation
défendable le jour où cette mesure existe — et il fournirait alors le critère d'aiguillage que
la cascade du § 8.4 de l'article laisse vide.

### Instrumentation du lot 1

Compteurs par cycle de réflexion : gravités attribuées en cinq quantiles, pour repérer un modèle
qui écrase ses jugements ; part des souvenirs au-dessus du seuil de choc. Alarme sur front
montant si aucun concept n'atteint `grave` sur plus de deux jours simulés alors que des retards
dépassant le seuil ont été observés — signe d'un modèle qui nivelle.

---

## Lot 2 — Récupération structurée, sans exclusion

> ✅ **LIVRÉ le 2026-09-14.** Les trois viviers, les cinq composantes du score, les axes
> normalisés à l'écriture et le paramètre de plongement branché sont en service. Voir la
> **partie II** pour ce qui tourne.
>
> **Trois écarts avec le texte ci-dessous, décidés en cours de route** — le détail et le
> raisonnement sont dans `specs/ticket_071/tests_lot2.md` :
>
> 1. **L'affinité catégorielle se réduit à la MÉTÉO.** Le texte ci-dessous lui fait apparier
>    « mode, créneau, motif, météo » — or trois de ces quatre attributs SONT déjà les axes de
>    l'affinité d'axes. Ils auraient été comptés deux fois, avec des poids différents, sans que
>    rien ne le dise : un score dont deux termes mesurent la même chose n'est plus
>    interprétable, et la calibration des cinq poids aurait porté sur des composantes corrélées
>    par construction. Un cinquième axe `axe_meteo` est ajouté à l'entrée de mémoire, la météo
>    n'étant stockée nulle part.
> 2. **`axe_objet` est un MODE canonique**, pas une ligne de réseau. Les exemples du texte
>    (`metro_A`, `bus_401`) rendraient le vivier B toujours vide, puisqu'il apparie les modes
>    offerts dans les options. La ligne et l'arrêt vont dans `axe_lieu`.
> 3. **Le concept déclare son mode**, champ `mode` du schéma de réflexion. La mémoire longue ne
>    contient que des réflexions et des concepts : sans ce champ, le vivier B n'aurait rien à
>    apparier.
>
> ⚠ **Le lot 2 est livré SANS tests propres**, sur décision de l'auteur : ils viendront à la
> fin du lot suivant. Le contrat à honorer est écrit dans `specs/ticket_071/tests_lot2.md`.


### Les trois viviers

Le vivier de candidats n'est plus produit par une seule requête sémantique. Trois passes
s'unissent, dédupliquées par identifiant de document.

| Vivier | Contenu | Coût |
|---|---|---|
| **A — sémantique** | Les plus proches du texte de la situation, borne actuelle conservée : `min(max(5 × top_k, 32), 100)`. | Un embedding de requête. |
| **B — par objet** | Pour **chaque mode présent dans les options offertes**, les souvenirs portant cet `axe_objet`, triés par gravité puis par récence, huit au plus par mode. | Une clause de métadonnées par mode. Aucun embedding. |
| **C — chocs** | Les souvenirs dont la gravité dépasse `I_choc`, cinq au plus, sans aucune condition de lieu, d'heure ni de motif. | Une clause de métadonnées. |

### Pourquoi rien ne filtre

> ⚠ **Correction du 2026-09-14, après expertise externe.** Une version antérieure présentait ces
> trois viviers comme une « inversion d'HippoRAG », en affirmant que chez Gutiérrez et al. (2024)
> « la structure restreint la recherche ». **C'est un contresens.** HippoRAG procède par
> diffusion d'activation sur un graphe d'entités et a précisément été conçu pour l'associativité
> à sauts multiples entre contextes dissemblables : il ne restreint rien. L'article figurait dans
> la liste de ceux qui n'ont **pas** été lus dans le corpus local, et la filiation a été écrite
> sans l'avoir vérifiée. Elle est retirée.
>
> Ce que décrit ce lot est une **génération de candidats multi-viviers**, technique classique de
> recherche d'information combinant recherche dense, présélection par facettes et vivier
> d'exception. La nommer ainsi coûte moins cher qu'une filiation contestable. À noter que la
> diffusion d'activation d'HippoRAG traiterait l'exemple ci-dessous au moins aussi bien : c'est
> une piste, pas un repoussoir.

La règle de non-exclusion, elle, reste entière et ne dépend d'aucune filiation. Le phénomène que
le dispositif doit observer est le **report d'un contexte sur un autre**.

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
| Affinité d'axes | 0,20 | apport propre, en bonus et jamais en veto |

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

> ⚠ **Révision du 2026-09-14, arbitrage de l'auteur.** Le dispositif bascule à **100 % anglais**
> (ticket 074) : prompts, population, souvenirs. Le remplacement par un modèle **francophone**
> perd donc son objet et **`Solon-embeddings-large-0.1` est abandonné comme cible**. Le modèle
> anglophone hérité de Vu et al. redevient cohérent avec le corpus. Ce qui reste vrai et reste à
> faire : **brancher le paramètre**, pour pouvoir comparer deux modèles sans toucher au code. Le
> paragraphe ci-dessous est conservé pour mémoire du raisonnement, sa conclusion ne vaut plus.


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

> ✅ **LIVRÉ le 2026-09-14.** Voir la **partie II** pour ce qui tourne. Deux écarts avec le texte
> ci-dessous, décidés en cours de route (`specs/ticket_071/tests_lot3.md`) :
>
> 1. **`confirmer` ne rafraîchit PAS l'horodatage**, contrairement à ce qui est écrit plus bas :
>    le lot 1 a posé que `timestamp` est l'heure de l'événement et s'affiche dans le prompt. Un
>    champ `derniere_observation` distinct porte la date de la dernière confirmation.
> 2. **La mise à l'écart est datée à la cessation de service**, pas au seuil de trois
>    contre-exemples — sans quoi elle était inatteignable pour un concept peu observé.


Aujourd'hui chaque réflexion émet jusqu'à cinq concepts, chacun écrit comme une entrée neuve.
Rien ne les relie. Au bout d'un mois un agent porte des centaines de concepts, dont beaucoup
répètent la même chose et certains se contredisent — et c'est le prompt de décision qui arbitre,
à chaque décision, à ses frais.

Le mécanisme vient de **Mem0, Chhikara et al. (2025)**, qui extrait puis applique des opérations
explicites sur la mémoire existante plutôt que d'empiler, et d'**A-MEM, Xu et al. (2025)**, dont
les notes se lient et évoluent à l'arrivée d'un souvenir nouveau.

### Le panier de candidats, et non une identité

> ⚠ **Révision du 2026-09-14, après expertise externe.** Ce lot spécifiait
> `identite = hash(axe_objet, axe_motif)`, une **faute de conception**. Tous les concepts d'un
> agent portant le même couple mode-motif auraient partagé la même identité, donc le même
> emplacement. Un agent pendulaire à vélo produisant successivement « la piste du canal est
> protégée », « l'abri à vélos du campus sature à 8 h 30 » et « les pavés du centre sont
> glissants par temps de pluie » aurait vu chaque concept **détruire le précédent**. Par
> construction, un agent n'aurait pu tenir qu'**une seule pensée par couple mode-motif**.

Le couple mode-motif devient un **panier de candidats**, pas une identité.

```
panier = (axe_objet, axe_motif)        # correspondance exacte sur une métadonnée indexée
```

Il ne désigne plus *le* concept à mettre à jour, mais le petit ensemble de concepts qu'il
*pourrait* s'agir de mettre à jour. La discrimination se fait ensuite **à l'intérieur du
panier**, qui compte quelques unités et non l'index entier.

Deux voies, la seconde étant retenue.

- **Par similarité**, comme A-MEM, Xu et al. (2025) : le concept nouveau est comparé aux
  concepts du panier, et au-delà d'un seuil de proximité il met à jour le plus proche. Rejetée
  comme voie principale : un seuil fixe sur un plongement francophone est arbitraire et
  demanderait une calibration que rien ne fonde.
- **Par désignation du modèle**, retenue : les quelques concepts du panier sont montrés au
  modèle dans l'appel de réflexion qui a déjà lieu, et il désigne celui qu'il met à jour, ou
  déclare qu'il n'en met à jour aucun. Coût marginal nul, aucun seuil à calibrer, et le modèle
  dispose du contexte que le panier seul n'a pas.

La propriété essentielle de la version initiale est conservée : **aucun balayage de l'index
n'est nécessaire**, la présélection restant une correspondance exacte sur une métadonnée.

### Opérations

Quatre opérations, choisies par le modèle via un champ `operation` ajouté au schéma de sortie de
la réflexion existante, accompagné de l'identifiant du concept visé lorsqu'il y en a un.

| Opération | Effet |
|---|---|
| `creer` | Aucune identité correspondante. Nouveau concept, `observations = 1`. |
| `confirmer` | Même affirmation. Rien n'est écrit de neuf : `observations += 1`, horodatage rafraîchi, force renforcée. |
| `preciser` | Affirmation compatible mais plus fine. Le contenu est remplacé ; compteurs et historique conservés. |
| `contredire` | Affirmation incompatible. `contre_exemples += 1`. L'ancien concept est marqué **dépassé** et le nouveau prend la relève quand il a été contredit **au moins trois fois et plus souvent que confirmé** : trois contradictions ne suffisent pas contre vingt confirmations, une majorité de contradictions ne suffit pas sur deux observations. |

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

> ✅ **LIVRÉ le 2026-09-14.** Voir la **partie II**. Trois écarts avec le texte ci-dessous,
> décidés en cours de route (`specs/ticket_071/tests_lot4.md`) :
>
> 1. **Les TROIS blocs sont calculés**, y compris celui des connaissances que le texte confie au
>    modèle : le lot 3 a rendu les concepts assez structurés pour qu'il se calcule exactement, et
>    le garde-fou vaut pour les trois.
> 2. **Le journal des trajets a dû être créé** : il n'existait sous aucune forme interrogeable.
> 3. **Un paramètre distinct** commande le nombre d'entrées épisodiques servies à côté du bloc,
>    plutôt que de réutiliser le top-K du rappel.


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

> ✅ **Lot 4 livré le 2026-09-14.** `memoire__episodiques_avec_noyau` s'ajoute aux douze
> constantes. **Les quatre lots du volet CODE sont livrés.**

> ✅ **Lot 3 livré le 2026-09-14.** `memoire__confiance_seuil_service` et
> `memoire__contre_exemples_seuil` ont désormais un lecteur. Les douze constantes du § 2.10 sont
> toutes en service.

> ✅ **Lot 2 livré le 2026-09-14.** `memoire__vivier_b_par_mode` et `memoire__vivier_c_taille`
> ont désormais un lecteur, et les **cinq** poids du rappel sont lus par le classement : ils ont
> basculé ensemble à 0,30 / 0,10 / 0,20 / 0,20 / 0,20. Restent sans lecteur :
> `confiance_seuil_service` et `contre_exemples_seuil`, qui attendent le lot 3.

> ✅ **Lot 1 livré le 2026-09-14.** Les constantes suivantes ont désormais un LECTEUR :
> `memoire__force_k_importance`, `force_delta_rappel_jours`, `force_max_jours`,
> `purge_seuil_poids`, `retard_ref_s`, `importance_choc`, `theta_gravite_cumulee`. Restent sans
> lecteur jusqu'aux lots suivants : `confiance_seuil_service`, `contre_exemples_seuil`,
> `vivier_b_par_mode`, `vivier_c_taille`.

> ✅ **Lot 0 livré le 2026-09-14.** Les constantes de ce tableau sont désormais **déclarées
> dans `services/llm-agents/settings.py`**, préfixées `memoire__`, chacune avec sa règle de
> conception en commentaire. Elles n'ont pas encore de lecteur : le code qui les lit arrive
> lot par lot. La fenêtre d'âge, elle, est **câblée** : elle vaut l'horizon de l'expérience,
> plafonné à 60 jours, appliqué par `experiences/cli.py`.
>
> ⚠ **Les cinq poids du rappel ne sont pas encore basculés.** `rank_nodes` n'en lit que trois,
> qui gardent leurs valeurs en service (0,4 / 0,3 / 0,3). Les porter à 0,30 / 0,10 / 0,20 avant
> que le classement ne lise les cinq ferait tomber la somme des poids lus à 0,60 ; comme les
> composantes entrent en valeur **absolue** depuis le ticket 048 — la normalisation min-max a
> justement été supprimée pour rendre deux décisions comparables — l'ordre des candidats
> changerait sous un régime que personne n'a spécifié. Les cinq basculent ensemble, au lot 2.
> Un test le verrouille : `tests/test_071_lot0_constantes.py`.

> **Règle des constantes, fixée le 2026-09-14.** Chaque constante porte une règle de conception
> en une phrase, rattachée au phénomène et non à l'horizon : **le même jeu vaut pour cinq jours
> comme pour soixante**, seul l'horizon change entre expériences. Les valeurs sont fixées avant
> tout run `exp_04*`, aucun n'ayant tourné à cette date. Ce qui rend une valeur défendable n'est
> pas une citation mais trois choses : la règle, la date, et un point de sensibilité. Le point de
> sensibilité est `S0 = 8,3` jours, la valeur publiée de Park et al. (2023), 0,995 par heure de
> jeu, tout le reste étant fixe.

| Paramètre | Valeur | Règle de conception |
|---|---|---|
| `long_term_retrieval__force_base_jours` (`S0`, existe déjà) | 2,8 | Un trajet banal pèse moins de 10 % après une semaine. Héritée de l'implémentation de Vu et al., non publiée dans leur article ; conservée parce qu'elle reproduit la décroissance en service. |
| `memoire__force_k_importance` (`k`) | 6 | Un souvenir `marquant`, « je m'en souviendrai dans un mois », garde la moitié de son poids à deux semaines et un cinquième à trente jours. |
| `memoire__force_delta_rappel_jours` (`δ`) | 1 | Chaque rappel ajoute un jour de durée de vie : un trajet banal atteint le plafond en vingt-huit rappels, un souvenir `marquant` en onze. Remplace le facteur multiplicatif `κ = 0,15`. |
| `memoire__force_max_jours` (`FORCE_MAX`) | 30 | Aucun souvenir ne devient éternel : au plafond, deux mois sans rappel le ramènent à un huitième. S'applique aussi à la durée de vie initiale. |
| `memoire__purge_seuil_poids` | 0,01 | Une entrée épisodique est purgée quand son poids temporel passe sous 1 %, soit 4,6 constantes de temps : 13 jours pour un trajet banal jamais rappelé, 90 pour un souvenir `marquant`, donc jamais dans un run. Les concepts ne sont jamais purgés, seulement marqués dépassés. Remplace les seuils par type du nettoyage en service. |
| `long_term_max_days_query` (fenêtre d'âge, existe déjà) et `memory_horizon_days` du fichier d'expériences | = horizon de l'expérience, 60 au plus | Rien ne filtre par l'âge à l'intérieur d'un run, la décroissance suffit. Le défaut de 30 jours aurait coupé le second mois d'un run de soixante jours. |
| `memoire__retard_ref_s` | 1800 | Retard qui sature la composante déterministe de gravité. **Règle à écrire** : à rattacher à la distribution des durées de déplacement de la cohorte, mesurable sans run. |
| `memoire__importance_choc` | 0,7 | Seuil du choc, soit le niveau `grave` et au-dessus. Ouvre le vivier des chocs du lot 2. |
| `memoire__theta_gravite_cumulee` (`Θ`) | 0,7, égal au seuil du choc | Un seul souvenir grave déclenche la réflexion en journée, ou une journée dont les retards cumulés en valent un. La panne de la ligne A des expériences d'hystérésis vaut 0,8 en gravité déterministe : à `Θ = 1,0`, le choc étudié n'aurait pas déclenché avant le soir. **À vérifier sur mesure** : moins d'un déclenchement par agent et par semaine, sinon `Θ` monte. |
| `memoire__confiance_seuil_service` | 0,5 | Un concept cesse d'être servi quand il a été contredit plus souvent que confirmé, `contre_exemples > observations` sous Laplace. |
| `memoire__contre_exemples_seuil` | 3, **et** confiance < 0,5 | Un concept est dépassé quand il a été contredit au moins trois fois et plus souvent que confirmé. |
| `memoire__vivier_b_par_mode` | 8 | Souvenirs tirés par mode envisagé. Indépendant de l'horizon. |
| `memoire__vivier_c_taille` | 5 | Souvenirs graves tirés sans condition. Indépendant de l'horizon. |
| `long_term_retrieval__*_weight` | 0,30 / 0,10 / 0,20 / 0,20 / 0,20 | Les cinq poids du lot 2, à calibrer sur jeux gelés. Indépendants de l'horizon. |
| `long_term_self_reflect_interval_days` (existe déjà) | 3 | Vingt passages sur soixante jours. Indépendant de l'horizon. |

⚠ **Aucune de ces valeurs ne se redéfinit dans `config/config.yaml`** (règle posée le
2026-09-19, vérifiée par `test_077_lotJ_reglages_experience.py`). Une expérience qui veut en
faire varier une passe par l'**environnement** (`AGENT__MEMOIRE__…`) : le réglage appartient
alors au run, il se retrouve dans son identité, et il disparaît avec lui.

Posé dans `config.yaml`, il devient la norme du dépôt sans que personne ne l'ait décidé. C'est
arrivé le 18 septembre : `memoire__importance_choc` y est passé de 0,70 à 0,50 pour un choc qui
franchissait déjà le seuil — la gravité valait exactement 0,70 et la comparaison est `>=`. Effet
recherché : nul. Effet obtenu : six souvenirs de plus dans le vivier C, et une trentaine de tests
rouges énonçant la règle que la configuration venait de contredire.

Restent tels quels, indépendants de l'horizon : la grille des cinq niveaux de gravité, les poids
de la gravité déterministe, le top-K à 10, le plancher journalier à 22 h.

---

## Observer la mémoire : le journal par agent (ticket 075)

Les mécanismes ci-dessus sont validés par 249 tests unitaires. Aucun ne dit ce que la mémoire
d'un agent **devient** quand elle vit soixante jours simulés. Le journal de mémoire répond à
cette question-là, et à aucune autre.

`llm/journal_memoire.py` écrit **un Markdown par agent** dans `<workdir>/memoires/<person_id>.md`,
en continu pendant le run :

| Événement | Ce qui est écrit |
|---|---|
| Consolidation STM → LTM | section datée, **motif** (`seuil` / `plancher journalier` / `rupture`), ce qui l'a déclenchée, les entrées consommées, la réflexion, puis l'**état complet** de la mémoire après |
| Auto-réflexion LTM | sa propre section : elle ne consomme aucune entrée courte, elle relit la mémoire longue |
| Opération de concept | `créé` / `confirmé` / `précisé` / `contredit`, contenu et compteurs **avant → après**, mise à l'écart datée le cas échéant |
| Écriture épisodique | une ligne : type, contenu, gravité, force |
| Rappel | une ligne : combien de souvenirs servis, force et compteur après renforcement |
| Purge | une ligne par entrée oubliée, âge depuis le dernier rappel et force |

Le **motif** vient du contrôleur, capturé au moment de l'éligibilité et transmis par
`Context.data` : quand la réflexion s'exécute (file EDF, la nuit simulée), le tampon a changé et
le motif ne serait plus retrouvable.

**Réglages.** `agent.journal_memoire_enabled` (défaut **false**) et `agent.journal_memoire_dir`
(défaut `memoires`, résolu dans le workdir). Éteint, le journal ne coûte ni fichier ni appel
disque — à mille agents, l'état complet écrit à chaque consolidation ferait des centaines de
mégaoctets que personne n'ouvrirait.

⚠ **Ce n'est pas une source de mesure.** Les chiffres se prennent dans les métadonnées de la
mémoire et dans `moves.csv`. Ce fichier est fait pour être **lu**.

## Relire un run : le rapport par persona (ticket 077, lot F)

Le journal ci-dessus se lit agent par agent, jour par jour. Il ne répond pas à la question qui
vient ensuite : *cet agent a-t-il changé de comportement, et sur quoi s'appuyait-il pour
décider ?* Le rapport la pose sur un run entier, en un fichier.

    python -m scripts.analysis.memoire.rapport <dossier_run> -o <sortie.html>
    make memoire-rapport RUN=experiments/archive/2026-09-14_23_58

Sortie : **un seul HTML autonome** sous `docs/traces/<date_heure>_rapport_memoire/`, hors git.
Bibliothèque standard uniquement, SVG en ligne (`scripts/analysis/memoire/`, quatre modules :
`sources`, `mesures`, `graphiques`, `rapport`). Deux exécutions sur le même run rendent le
**même octet** : aucun horodatage de génération n'entre dans le corps.

Ce que le rapport montre, par persona :

| Pièce | Ce qu'elle dit |
|---|---|
| Frise des modes | une ligne par motif, une colonne par jour, la couleur du mode retenu (palette du dépôt) — l'habitude s'y voit s'installer |
| **Tableau des itinéraires** | une ligne par itinéraire distinct **proposé**, une colonne par jour : bleu clair proposé, bleu foncé retenu, gris quand l'appariement a échoué |
| Décisivité et entropie | par semaine, sur la répartition de `moves.csv` ; une semaine sans décision probabilisée coupe le tracé au lieu de valoir zéro |
| Concepts | groupés par thème, avec observations, contre-exemples, confiance (Laplace) et force ; les reformulations d'un même thème sont groupées |
| Habitudes et auto-réflexion | le `journal` des métadonnées LTM et la dernière synthèse long terme |

Puis une section transversale : contamination des observations (marches fantômes, voiture
journalisée en transport collectif), taux de `known_beliefs` vide, concentration des rappels.

**Trois pièges du format, traités une fois pour toutes** dans `sources.py` :

1. `llm_exchanges.jsonl` **n'est pas du JSONL** malgré l'extension — objets JSON indentés
   concaténés, lus par `raw_decode` en boucle ;
2. `moves.csv` porte les **trajets rejoués** après redémarrage. La clé de décision est
   `(ID Personne, ID Activité, Temps simulé)` — l'identifiant d'activité seul se répète d'un jour
   sur l'autre. On garde la première ligne par heure de calcul ; le rapport **déclare** le nombre
   d'exclus (84 sur le run du 2026-09-14) ;
3. les **options proposées n'existent que dans le texte des prompts**. L'appariement se fait par
   `(agent, jour, motif)` et heure de départ la plus proche ; un trajet non retrouvé donne une
   colonne **grise déclarée**, jamais une case vide muette. Le lot E.3 rendra cet appariement
   inutile au run suivant.

⚠ **Une section vide se déclare comme vide.** Un agent sans concept produit tout de même sa
section, avec la mention explicite qu'il s'agit d'une absence de mesure et non d'un résultat
propre. Dans ce dépôt, l'absence de mesure produit volontiers le score parfait.

Contrat de test : `specs/ticket_077/tests.md` § F, vérifié par
`services/llm-agents/tests/test_077_lotF_rapport.py` (fixtures minimales, plus un test de bout en
bout sur le run de référence quand il est présent).

## Reprise à chaud d'un run long (ticket 075)

`make run OFFLINE=1 CONT=1` réutilise le répertoire du run — donc **retrouve la mémoire
pleine** — pendant que GAMA repart à son t0 et rejoue les jours déjà vécus. Sans précaution, ces
jours rejoués réécrivent des souvenirs déjà écrits : épisodes en double, compteurs
d'observations et de contre-exemples incrémentés deux fois.

Deux pièces, dans `urban_mobility_agents/utils/reprise.py` :

1. **Un point de reprise par jour simulé**, écrit à **3 h** — après le drainage nocturne des
   réflexions et après le plancher de 22 h, donc sur des tampons de mémoire courte vides. Il
   contient la mémoire longue, les `.md` du journal, l'ancre du run et les compteurs. Écriture
   atomique (répertoire temporaire puis renommage) : un point interrompu n'est jamais valide.
2. **Le rejeu à mémoire gelée** : au redémarrage, l'état est restauré au dernier point, puis
   toute écriture de mémoire est suspendue jusqu'à ce que l'horloge simulée dépasse ce point.
   Le point d'étranglement est `add_short_term_memory` : sans entrée courte, aucun agent ne
   devient éligible à la consolidation. Les décisions et les déplacements, eux, ont lieu.
3. **La trace de rejeu** (`utils/rejeu_decisions.py`, ticket 090) : chaque décision vivante est
   consignée sous `(personne, activité, instant)` dans `<workdir>/decisions_rejeu.jsonl`, et
   resservie pendant le gel **sans appel au modèle**.

⚠ **La phrase « le cache les sert sans appel au modèle » était vraie en général et fausse sur les
runs de mesure**, où le cache sémantique est coupé — c'est la condition d'un run journalisé sur
son périmètre complet. Le rejeu y repayait donc chaque décision : mesuré le 2026-09-16, huit jours
rejoués, une centaine d'appels, trois quarts d'heure d'attente réseau pour retrouver un état déjà
connu. D'où la troisième pièce.

**La trace n'est pas le cache.** Sa source est le workdir de CE run et non un répertoire partagé ;
sa clé n'est pas une empreinte d'état non indexée par modèle ; sa portée s'arrête avec
`gel_actif()` — sans cette condition elle deviendrait un cache permanent ; et une clé manquée est
comptée puis **alarmée** au-delà de 20 %, là où le cache recalculerait en silence. Une manquée ne
fait pas échouer le run — on appelle le modèle — mais un rejeu qui ne retrouve pas ses propres
choix ne reconstruit pas l'état qu'on croit reprendre.

L'**ancre du run** (`utils/ancre_run.py`) est restaurée depuis le point et n'est jamais
réancrée sur le premier timestamp du rejeu : sinon la progression de la date météo rembobinerait
pour tous les agents.

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
- **Gutiérrez, B. J. et al. (2024)** — *HippoRAG*, NeurIPS, [arXiv:2405.14831](https://arxiv.org/abs/2405.14831). Diffusion d'activation sur un graphe d'entités, pour l'associativité à sauts multiples entre contextes dissemblables. **Aucun mécanisme de ce document n'en dérive** : une filiation écrite sans lecture de l'article a été retirée le 2026-09-14. Reste une piste ouverte pour le lot 2.
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

Ajoutées le 2026-09-14 à la relecture du ticket 071, notices recoupées sur l'éditeur ou arXiv, non lues intégralement dans le dépôt :

- **Diekelmann, S. & Born, J. (2010)** — *The memory function of sleep*, Nature Reviews Neuroscience 11(2), 114–126. La consolidation se fait au repos : fonde le plancher journalier.
- **McClelland, J. L., McNaughton, B. L. & O'Reilly, R. C. (1995)** — *Why there are complementary learning systems in the hippocampus and neocortex*, Psychological Review 102(3), 419–457. Deux systèmes, épisodique rapide et sémantique lent : fonde la séparation des régimes d'oubli et le rejeu différé.
- **Verplanken, B. & Aarts, H. (1999)** — *Habit, attitude, and planned behaviour: is habit an empty construct or an interesting case of goal-directed automaticity?*, European Review of Social Psychology 10(1), 101–134. L'habitude comme automatisme dirigé par le but : c'est la source du régime Système 1 / Système 2 évalué puis écarté ci-dessus. ⚠ Notice reprise du ticket 051, **non recoupée** sur l'éditeur — à vérifier avant toute citation dans l'article, où la porte de `CITATIONS.md` exige en outre le PDF dans `docs/paper/sources/etat_de_lart/`.

---

## Le témoin du souvenir injecté (ticket 106)

Une consolidation est une **synthèse reformulée**, pas une copie : aucun identifiant ne relie une
entrée de mémoire courte à la réflexion qui la consomme. Rien ne garantissait donc qu'un événement
injecté atteigne la mémoire longue — et le 2026-09-23, un choc jugé **grave (0,75)** a disparu
sans laisser de trace.

| Run `2026-09-23_13_54` | |
|---|---|
| Entrée courte | 27 mars 14:02, importance 0,75 |
| Consolidation couvrante (19:30) | *« Today went very smoothly overall »*, importance 0,10 |
| Documents de mémoire longue parlant de métro, éclairage, annonce ou rame | **0 sur 123** |

Cause mécanique : le texte est **joint** à l'observation d'arrivée, et cette arrivée disait
`On time.` — l'agent était 199 s en avance, `retard_injecte_s` ne remontant qu'au
`GamaArrivalsLogger`. La journée offerte à la synthèse avait pour ligne dominante « tout s'est
bien passé ».

### Comment il marche

Après chaque écriture en mémoire longue, `llm.evenements.temoin.controler` cherche dans
`all_messages` une entrée portant un préfixe d'injection (`[ INCIDENT ]`, `[ PRESSE ]`). S'il n'y
en a pas — le cas de l'immense majorité des consolidations — il ne fait rien. S'il y en a une, il
extrait du texte injecté les mots qui ne pourraient pas venir d'une journée ordinaire et les
cherche dans ce qui vient d'être écrit.

En dessous de `temoin_souvenir_mots_min` mots retrouvés, une ligne `[ALARME] [temoin]` nomme
l'agent, les mots cherchés et ceux retrouvés. Le succès est journalisé lui aussi.

### Il alarme, il n'arrête pas

C'est le geste du ticket 105 **à un cran de moins**, délibérément. Le témoin du 105 est certain —
un repli est un fait ; celui-ci est heuristique — une paraphrase légitime (« the underground »
pour « metro ») produit une fausse alarme. Arrêter un run là-dessus risquerait de tuer un bon run.

`temoin_souvenir.jsonl` porte les **deux** verdicts, pour que le taux de fausses alarmes s'observe
sur des runs réels avant qu'on envisage l'arrêt. Chaque ligne nomme l'événement du run : la
consolidation du soir ne connaît pas l'événement joint à une arrivée du matin, l'identifiant est
donc lu dans le registre — exact tant qu'un run ne déclare qu'un événement, et ce que le site
d'appel passe explicitement l'emporte.

⚠ Le témoin ne contrôle que ce qui est **injecté**. Une injection déclarée qui ne se produit pas
ne le réveille jamais et ne laisse aucune trace chez lui : c'est l'objet du ticket 108.

⚠ Et il ne contrôle qu'**un canal**. La décision est nourrie par la mémoire longue, mais aussi
par le bloc « ce qui a changé récemment », la mémoire courte et les concepts. Un verdict
`PERDU` ne veut donc pas dire que l'agent a décidé sans le souvenir : le run
`2026-09-23_09_31`, déclaré PERDU, sert pourtant le récit du choc dans 3 de ses 9 décisions
postérieures. Mesurer ce qui atteint le prompt de décision est l'objet du ticket 110.

### La liste d'exclusion

Un mot banal du domaine — « trip », « minutes », « late », « station » — ne prouve rien. Deux
pièges rencontrés en calibrant, tous deux silencieux :

- `incident` correspondait à *« without any unexpected incidents »*, qui dit le contraire de ce
  que le témoin cherche ;
- `between` était le seul mot que le run perdu retrouvait, dans *« a short walk between
  errands »* — il suffisait à le faire passer pour sain.

Règle d'admission : *ce mot apparaîtrait-il dans la réflexion d'un jour ordinaire ?* Si oui,
il sort. La liste vit dans `llm/evenements/temoin.py`.

### Ce que la calibration a donné

Sur les 15 runs archivés portant une injection, deux n'ont aucune consolidation après l'injection
(le run s'est arrêté avant) et sortent du champ du témoin.

| | |
|---|---|
| Runs observables | 13 |
| Souvenir retrouvé | 11 |
| Souvenir perdu | 2 (`09_31`, `13_54`, tous deux c3 sur 861500) |
| Mots retrouvés, runs sains | 3 à 81 |
| Mots retrouvés, runs perdus | 0 et 1 |

Aucun run ne se situe au voisinage du seuil : la séparation est franche, et le seuil de 2 n'est
pas un arbitrage fin. Taux de perte mesuré : **2/13 = 15 %**, et **2/4 = 50 % sur le seul c3**.

### Où le lire

- `make error` — les alarmes.
- `make report` — la section « Témoin du souvenir injecté », les deux verdicts et une alarme 🔴
  par perte.
- `temoin_souvenir.jsonl` dans le répertoire du run — une ligne par consolidation contrôlée.
