# Accidents sur les axes

Régime optionnel dans lequel des accidents surviennent au hasard sur le réseau routier pendant
la journée simulée. Piloté par un interrupteur dans l'IHM GAMA, **faux par défaut**.

> **État au 2026-09-14.** Les accidents **existent** et leur tirage est **conditionné aux
> statistiques BAAC** : heure, jour de semaine et classe d'axe. **Aucune durée d'itinéraire
> n'est modifiée** — le retard subi et le souvenir de l'agent viennent dans des tranches
> ultérieures. Une seule variable de la loi reste non établie, le facteur météo. Spécification :
> [`specs/accidents-interrupteur-gama.md`](../../specs/accidents-interrupteur-gama.md).

## L'interrupteur, de l'IHM au run archivé

Sept points, exactement le chemin que suit déjà `long_term_memory_enabled` :

| Étape | Fichier | Rôle |
|---|---|---|
| Déclaration et persistance | `services/GAMA/CityTransport/models/Settings.gaml` | `bool accidents_enabled <- false` ; écrit et relu dans `config/sim_params.yaml` |
| Exposition dans l'IHM | `services/GAMA/CityTransport/models/City.gaml` | paramètre « Accidents sur les axes », catégorie `Simulation` |
| Transmission | `services/GAMA/CityTransport/models/LLMAgent.gaml` | clé `accidents_enabled` dans la charge utile du `POST /init` |
| Validation | `services/llm-agents/gama_models.py` | `WorldInitRequest.accidents_enabled: Optional[bool]` |
| Passage | `services/llm-agents/handle/application.py` | transmis à `init_dynamic_scenario` |
| Application et archivage | `services/llm-agents/urban_mobility_agents/factory/factory.py` | surcharge `settings.accidents.enabled`, ouvre le registre, écrit `scenario_params.yaml` |
| Configuration | `services/llm-agents/settings.py` | `AccidentsConfig` : taux, durées, graine, garde-fous |

**`None` n'est pas `False`.** Un `/init` qui ne porte pas la clé vient d'un GAMA antérieur à
cette évolution : le contrôleur garde alors sa valeur de configuration. Un `False` explicite,
lui, est une décision de l'expérimentateur. Confondre les deux ferait désactiver en silence un
régime demandé par fichier de configuration.

**L'état effectif est toujours écrit** dans le `scenario_params.yaml` du run, y compris quand
il vaut `false`. Contrairement à `simulation_max_days`, dont l'absence signale un run antérieur
à son existence, un régime d'accidents non consigné ferait douter de **tous** les runs : le
lecteur d'une archive ne pourrait plus distinguer « désactivé » de « la question ne se posait
pas encore ».

## Le tirage

`services/llm-agents/trip_helper/accidents.py`. Un registre par run, ouvert par la fabrique de
scénario si l'interrupteur est à vrai. Le contrôleur appelle `tirer_journee` à chaque `sync` ;
l'appel est **idempotent par journée simulée**, ancrée sur le premier instant observé du run —
la même journée que celle des journaux `SIM_DAY`.

Pour chaque journée :

1. **Combien** — loi de Poisson au taux de base **conditionné par le jour de semaine**
   (vendredi ×1,188, dimanche ×0,833). Poisson et non « taux arrondi » : à 1,56 accident par
   jour, un arrondi donnerait deux accidents chaque jour, c'est-à-dire un monde plus régulier
   que le vrai. La variance fait partie du phénomène.
2. **À quelle heure** — sur la **distribution horaire mesurée**. C'est le conditionnement le
   plus marqué de la loi : 9,77 % des accidents à 17 h contre 1,45 % à 3 h, un rapport de 6,7.
3. **Sur quelle classe d'axe** — sur la **distribution par vitesse autorisée mesurée**.
4. **Sur quelle arête** — au prorata de sa longueur **à l'intérieur de la classe tirée**.
5. **Combien de temps** — une durée tirée entre les bornes configurées.

Le tirage est **déterministe à graine fixée** : deux exécutions du même scénario posent les
mêmes accidents. Sans cela, l'écart entre deux runs serait mis sur le compte des agents.

### La loi, et pourquoi elle est faite ainsi

Coefficients dans [`services/llm-agents/config/accidents_baac.yaml`](../../services/llm-agents/config/accidents_baac.yaml),
estimés sur **BAAC/ONISR 2019-2024**, département 31 : 3 789 accidents corporels, aucun non
géolocalisé, 3 414 dans l'emprise du graphe. Mesure rejouable :
`docs/traces/2026-09-14_20-40_loi_accidents_baac/`.

**Taux de base : 1,558 accident/jour** dans l'emprise du graphe — et non 1,73, qui valait pour
tout le département et surestimait le périmètre simulé de 11 %.

**Quelles variables réclament un dénominateur d'exposition, et lesquelles n'en réclament pas.**
C'est la décision de méthode de toute la loi, et elle sépare un modèle **génératif** d'un modèle
de **risque** :

| Variable | La simulation la… | Ce qu'il faut | Dénominateur ? |
|---|---|---|---|
| Heure | **tire** | distribution marginale | **non** |
| Jour de semaine | **tire** | facteur de moyenne 1 | **non** |
| Classe de vitesse | **tire** | distribution marginale | **non** |
| Météo | **impose** (bulletin du jour) | risque relatif | **oui** |

Pour les trois premières, ajouter un dénominateur serait une faute : diviser par le trafic
donnerait le risque par véhicule-km, qui ferait survenir autant d'accidents à 3 h du matin qu'à
17 h. La météo est le seul cas où la question se pose, parce que le bulletin est une entrée du
modèle et non un tirage.

**Le tirage en deux temps de la classe puis de l'arête n'est pas un détail.** C'est le
résultat le plus parlant de la mesure :

| Classe | Part des accidents | Part du réseau simulé |
|---|---:|---:|
| ≤ 30 km/h | 7,95 % | **58,12 %** |
| 31-50 | **57,47 %** | 33,89 % |
| 71-90 | **27,25 %** | 4,42 % |

Tirer l'arête au seul prorata de sa longueur, comme le faisait la première tranche, plaçait
58 % des accidents en zone apaisée — qui n'en porte que 8 % dans la réalité — et n'en mettait
presque aucun sur la classe 71-90, qui en porte 27 % pour 4,4 % des kilomètres.

### ⚠ Le facteur météo a été calculé, puis rejeté

Il vaut **1**, et ce n'est pas un oubli. Rapporter la part d'accidents par condition à la
fréquence de cette condition dans les relevés de Toulouse donne : pluie légère ×0,47,
temps couvert ×0,17, brouillard ×33,7. Soit « la pluie légère est deux fois plus sûre que la
moyenne » et « le brouillard multiplie le risque par 34 ». Ni l'un ni l'autre n'est croyable.

La cause est une **incommensurabilité des nomenclatures** : `atm` est ce que l'agent
verbalisateur a coché — 84 % des constats portent « normale », y compris sous un ciel couvert —
quand la source météo locale classe 20 % des créneaux en « pluie légère », catégorie qui
absorbe le code « pluie possible », une prévision et non une observation. Les deux vocabulaires
ne découpent pas le même monde.

Ajuster la correspondance jusqu'à obtenir des nombres plausibles reviendrait à choisir le
résultat. Les deux voies propres : une source d'exposition découpée comme `atm`, ou un risque
relatif déclaré exogène ([protocole](protocole-parametre-exogene.md)).

## Pourquoi aucune durée n'est modifiée dans cette tranche

Ce n'est pas un découpage de commodité. Deux caches rendraient un retard dangereux, et les deux
sont neutralisés par construction tant qu'aucune durée ne bouge :

- **Le cache d'itinéraires** est adressé **sans la date** (`version | jour de semaine | créneau
  | mode | coordonnées`). Une durée contenant un accident y serait resservie à tous les mardis
  8 h, y compris aux runs qui n'ont demandé aucun accident.
- **Le cache de décisions LLM** construit sa clé sur les **codes d'options** — des routes et
  des arrêts — donc **insensible aux durées** par construction
  (`llm/cache.py`, `_make_state_hash`). Un agent retardé de 25 minutes se verrait resservir la
  décision qu'il avait prise sans le retard, sans qu'aucun journal ne le signale.

Le même piège s'est déjà produit trois fois dans le dépôt — temps terminal, traits du persona,
contexte d'anticipation — dont une fois au prix d'un vidage manuel de cache. Le champ
`extra_key` existe pour ça et sera le véhicule de l'accident le jour venu.

Un test garde cette frontière : `test_aucune_duree_d_itineraire_n_est_modifiee_par_cette_tranche`
échoue dès que `osmnx_direct` lit le registre, en rappelant que les deux gardes doivent être
livrées dans la même tranche que le retard.

## Journalisation

Chaque journée simulée produit une ligne, **y compris quand tout vaut zéro** :

```
[accidents] Jour 3 — accidents tirés=2, refusés=0, actifs au total=5
[accidents]   posé : arête 1234→5678 à 2026-03-18 17:42 pour 45 min
```

À 1,73 accident par jour, beaucoup de journées n'en verront aucun : c'est le comportement
correct. Sans ce compteur, « aucun accident ce jour-là » et « le tirage ne tourne plus » se
ressemblent trop — c'est le motif récurrent du dépôt, où l'absence de mesure produit le score
parfait.

Alarmes `[ALARME]` sur : taux hors bornes, tirage aberrant au-delà du plafond, arête inconnue,
durée non positive, réseau non indexé.

**Le tirage est fail-open.** Une erreur lève une alarme et laisse la simulation continuer : un
régime d'accidents est un décor, pas une dépendance. Le faire tomber au milieu d'un run de
plusieurs heures coûterait infiniment plus cher que l'absence d'accidents ce jour-là.

## Ce que ce régime ne fait pas

- Il ne **ralentit personne** (cette tranche).
- Il ne rend aucun agent **victime** d'un accident : 0,0025 agent impliqué par journée simulée
  à 1 000 agents, hors d'atteinte des cohortes.
- Il ne fait pas **rouler les agents sur le graphe** : ils se déplacent à vol d'oiseau
  (`Inhabitant.gaml:54`). Ce n'est pas un obstacle au retard futur — la durée vient du graphe
  et gouverne la vitesse (`Inhabitant.gaml:390`) — mais le rattachement se fera par
  l'itinéraire calculé, jamais par la position.
- Il ne porte **aucune figure publiable**. L'exposition mesurée est de 38,5 déplacements
  touchés par journée simulée à 1 000 agents : la mesure viendra d'un accident **posé** à la
  main, pas du tirage.

## Voir aussi

- [`specs/accidents-interrupteur-gama.md`](../../specs/accidents-interrupteur-gama.md) — règles et critères d'acceptation
- [`docs/tickets/ticket_070_accidents_aleatoires_sur_les_axes.md`](../tickets/ticket_070_accidents_aleatoires_sur_les_axes.md) — le dossier complet
- [`docs/arch/routing.md`](routing.md) — calcul d'itinéraires et caches
- [`docs/arch/protocole-parametre-exogene.md`](protocole-parametre-exogene.md) — pour l'ampleur du retard, quand il viendra
