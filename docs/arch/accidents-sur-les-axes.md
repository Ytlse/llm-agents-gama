# Accidents sur les axes

Régime dans lequel des accidents surviennent au hasard sur le réseau routier pendant la
journée simulée. Piloté par un interrupteur dans l'IHM GAMA, **vrai par défaut** depuis le
2026-09-15.

> ⚠ **Le régime est actif par défaut, et il RALENTIT depuis le 2026-09-15.** Tout run tire des
> accidents sans qu'on l'ait demandé, et ces accidents allongent désormais les itinéraires qui
> les traversent. Les runs d'avant et d'après ce jour ne sont donc **pas comparables**. Les
> tickets ouverts qui lancent un run portent l'avertissement correspondant ; avant
> d'interpréter un run, lire `accidents_enabled` dans son `scenario_params.yaml`.

> **État au 2026-09-15.** Les accidents existent, leur tirage est **conditionné aux
> statistiques BAAC** (heure, jour de semaine, classe d'axe), ils **allongent les itinéraires**
> qui les traversent, et l'expérimentateur peut en **poser** un à la main. Restent hors
> périmètre le **souvenir** du retard et le **contournement**. Une variable de la loi reste non
> établie, le facteur météo. Spécification :
> [`specs/accidents-interrupteur-gama.md`](../../specs/accidents-interrupteur-gama.md).

## L'interrupteur, de l'IHM au run archivé

Sept points, exactement le chemin que suit déjà `long_term_memory_enabled` :

| Étape | Fichier | Rôle |
|---|---|---|
| Déclaration et persistance | `services/GAMA/CityTransport/models/Settings.gaml` | `bool accidents_enabled <- true` ; écrit et relu dans `config/sim_params.yaml` |
| Exposition dans l'IHM | `services/GAMA/CityTransport/models/City.gaml` | paramètre « Accidents sur les axes », catégorie `Simulation` |
| Transmission | `services/GAMA/CityTransport/models/LLMAgent.gaml` | clé `accidents_enabled` dans la charge utile du `POST /init` |
| Validation | `services/llm-agents/gama_models.py` | `WorldInitRequest.accidents_enabled: Optional[bool]` |
| Passage | `services/llm-agents/handle/application.py` | transmis à `init_dynamic_scenario` |
| Application et archivage | `services/llm-agents/urban_mobility_agents/factory/factory.py` | surcharge `settings.accidents.enabled`, ouvre le registre, écrit `scenario_params.yaml` |
| Configuration | `services/llm-agents/settings.py` | `AccidentsConfig` : taux, durées, graine, garde-fous |

**`None` n'est pas `False`.** Un `/init` qui ne porte pas la clé vient d'un GAMA antérieur à
cette évolution : le contrôleur garde alors sa valeur de configuration — donc **vrai**. Un
`False` explicite, lui, est une décision de l'expérimentateur. Confondre les deux ferait
désactiver en silence un régime demandé par fichier de configuration.

De même, un `sim_params.yaml` antérieur au 2026-09-15 ne porte pas la clé : GAMA prend alors
le défaut et **active** les accidents. C'est voulu, et c'est la raison de l'avertissement porté
par les tickets qui lancent un run.

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

## Le retard, et les deux gardes qui l'accompagnent obligatoirement

Un déplacement en voiture dont l'itinéraire traverse une arête accidentée voit sa durée
allongée : le facteur d'accident se multiplie au temps de parcours de cette arête, à côté du
facteur de zone TomTom, dans
[`_congested_travel_time`](../../services/llm-agents/trip_helper/osmnx_direct.py). C'est le
seul endroit du dispositif qui connaisse les arêtes réellement empruntées — les agents GAMA se
déplacent à vol d'oiseau, mais leur vitesse est calée sur la durée calculée là
(`Inhabitant.gaml:390`), donc un itinéraire allongé fait bien arriver l'agent en retard.

**L'ampleur du ralentissement est une hypothèse déclarée, pas une mesure.** Aucune source ne la
donne : le flux DATEX des DIR, seul à porter des durées réelles, n'est pas archivé. Le facteur
vit dans `AccidentsConfig.facteur_ralentissement`. Tout effet mesuré sur les agents sera l'effet
de **ce** nombre : il se publie avec le résultat.

**L'agent ne contourne pas.** Le chemin a été choisi en temps libre, avant que le surcoût ne
s'applique. Contourner demanderait de recalculer le plus court chemin sur des poids modifiés.

### Deux caches auraient rendu ce retard dangereux

Livrer le retard sans ces deux gardes aurait faussé des runs en silence. Elles sont arrivées
dans le même geste, et un test le vérifie.

- **Le cache d'itinéraires** est adressé **sans la date** (`version | jour de semaine | créneau
  | mode | coordonnées`). Une durée contenant un accident y serait resservie à tous les mardis
  8 h, y compris aux runs qui n'ont demandé aucun accident. **Garde :** tant qu'un accident est
  actif, ni lecture ni écriture. Volontairement grossière — un accident actif n'importe où
  suffit à contourner le cache, car on ne connaît pas le chemin avant de l'avoir calculé. Coût
  assumé : une à trois heures par journée simulée où le routage voiture calcule à froid.
- **Le cache de décisions LLM** construit sa clé sur les **codes d'options** — des routes et
  des arrêts — donc **insensible aux durées** par construction (`llm/cache.py`,
  `_make_state_hash`). Un agent retardé de vingt minutes se verrait resservir la décision prise
  sans le retard. **Garde :** la signature des accidents actifs entre dans `extra_key`.
  Grossière elle aussi — elle décrit l'état du monde, pas ce que l'agent traverse : deux agents
  dont aucun itinéraire ne croise l'accident auront quand même des clés distinctes. C'est
  sur-invalider, jamais sous-invalider.

Le même piège s'était déjà produit trois fois dans le dépôt — temps terminal, traits du persona,
contexte d'anticipation — dont une au prix d'un vidage manuel de cache. Celle-ci est la
quatrième, et `extra_key` existait pour elle.

## Poser un accident à la main

C'est de là que viendront les figures : le tirage aléatoire, à fréquence réelle, ne touche que
~0,6 déplacement par journée simulée à 1 000 agents et ne peut rien montrer. Même mécanisme,
même monde, autre déclenchement.

- **Depuis l'IHM GAMA** : catégorie `Accidents`, régler latitude, longitude, heure et durée,
  puis le bouton « Poser un accident maintenant ». Défauts calés sur la rocade à Empalot, 8 h.
- **Depuis un script** : `POST /accidents` avec `{lat, lon, debut_ts, duree_minutes}`.

L'accident est accroché à l'arête du graphe la plus proche du point et entre dans le même
registre que les accidents tirés. ⚠ Une pose dans un run où le régime est décoché est
**refusée**, avec une alarme au journal : sans ce refus, l'expérimentateur croirait avoir posé
un accident dans un monde qui n'en veut pas.

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

- Il ne fait pas **contourner** : l'agent subit le retard sur le chemin qu'il avait choisi.
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
