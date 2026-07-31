# Cohérence de chaîne des véhicules personnels

Un vélo et une voiture ne sont pas des options de menu : ce sont des **objets qui
occupent un lieu**. Un agent qui part travailler à vélo n'a pas de voiture au bureau, et
son vélo n'est pas resté à la maison. Ce document décrit comment le contrôleur applique
cette contrainte, et ce qu'elle ne couvre pas.

Code : `llm-agents/urban_mobility_agents/simulation_controller.py` (helpers `_vehicle_*`,
`_park_vehicles`, `_settle_vehicles_at_home`) — état : `PersonState.planning_vehicle_at`
(`llm-agents/models.py`).

## État

```python
planning_vehicle_at: dict[str, Location]   # clés "bike" / "car"
```

**Clé absente ⇒ véhicule au domicile.** La journée commence au domicile, où l'agent gare
les véhicules qu'il possède : le dict vide est l'état initial, et un retour au domicile
purge la clé plutôt que d'y écrire `home`.

**La possession reste une condition indépendante, testée en premier.** Ce dict décrit une
position, pas un droit d'usage : il ne fait jamais apparaître un véhicule chez quelqu'un
qui n'en a pas. Un agent `personal_bike = "Pas de vélo"` ou `number_of_cars = 0` est
écarté du mode avant toute question de position — au verrou de sortie
(`_vehicle_available`), au verrou de retour (`_vehicles_parked_at`) comme au décompte des
orphelins (`_orphaned_vehicles`). Les défauts diffèrent entre les deux véhicules : champ
`personal_bike` absent ⇒ vélo (rétrocompatibilité des anciennes populations), champ
`number_of_cars` absent ou nul ⇒ pas de voiture.

Les clés sont les sorties de `_primary_mode` (`bike`, `car`, `walk`, `transit`), pour
comparer directement une position de véhicule au mode d'un itinéraire.

C'est un état de **planification**, pas d'exécution : le plan court devant la simulation
GAMA (bootstrap 24 h + horizon glissant), donc ce champ suit la chaîne *planifiée*, pas
la position réelle de l'agent dans GAMA à l'instant t.

## Les trois règles

### 1. Verrou de sortie — on ne conduit que ce qui est là

`_vehicle_available(person, mode, from_location)` : le mode véhiculé n'est proposé à OTP
que si l'agent **possède** le véhicule *et* que celui-ci est garé au point de départ.
Un post-filtre écarte en plus les itinéraires que OTP/OSMnx renvoient sans qu'on les ait
demandés.

La possession seule ne suffit plus. Avant, un agent parti travailler en bus retrouvait
son vélo pour repartir du bureau ; la voiture, elle, n'avait aucune contrainte de
position du tout et était disponible partout, tout le temps.

### 2. Stationnement — le véhicule suit celui qui l'utilise

`_park_vehicles(person, plan, from_location, destination)` : le véhicule du mode retenu
se déplace jusqu'à la destination ; **les autres restent où ils sont**.

Aucun retour implicite au domicile : c'était le dernier vestige de téléportation de la
version booléenne, où un vélo laissé au bureau était réputé retrouvé à la maison le soir.

### 3. Verrou de retour — on ramène son véhicule chez soi

Sur un trajet dont le motif est `home`, si un véhicule est garé au point de départ, les
itinéraires candidats sont **restreints à ce mode**. L'agent ramène son vélo ou sa
voiture. Si les deux sont là, le choix entre eux reste au LLM.

C'est un filtre sur l'ensemble des options, pas une décision : **aucun appel LLM
supplémentaire**. Quand aucun itinéraire n'existe dans le mode attendu (OTP muet,
distance hors portée vélo), on rend la main plutôt que de bloquer l'agent — il rentre
autrement et le véhicule devient orphelin (voir plus bas).

## Cas résiduel : les véhicules orphelins

Le verrou de retour ne couvre que les véhicules garés au **point de départ** du trajet de
retour. Une étape intermédiaire suffit à le contourner :

> domicile → travail **en voiture** · travail → sport **à pied** · sport → domicile **en bus**

La voiture dort au travail. `_settle_vehicles_at_home` détecte la situation à chaque
retour au domicile planifié, la compte, et — par défaut — **ramène le véhicule au
domicile**. Sans ce rattrapage, l'agent perdrait sa voiture pour tous les jours suivants
de la simulation : un biais bien pire que la téléportation qu'on corrige.

Le rattrapage est donc une approximation assumée, mais **mesurée** :
`agent_vehicle_chain_total{event="orphaned"}` et une alarme `[ALARME]` à front montant
au-delà de 5 % des retours au domicile (source `vehicule_orphelin`).

## Effet sur le cache de routage

`include_car` et `include_bike` font partie de la clé du cache OTP persistant
(`OtpPersistentCache.make_key`), donc aucun risque de pollution croisée. En revanche
`include_car` **varie maintenant d'un trajet à l'autre** pour un même agent, là où il
était constant : mécaniquement, un même couple origine-destination peut désormais exister
en deux variantes de clé, et le taux de hit du cache OTP baisse légèrement.

## Limites connues

- **La voiture est traitée comme un bien individuel.** `number_of_cars` vient du ménage,
  mais la position est suivie par personne : deux conjoints peuvent « partir chacun avec
  la voiture ». Modéliser le partage demanderait une position par ménage (les
  coordonnées du domicile feraient une clé utilisable, faute de `household_id`).
- **Pas de multimodalité véhiculée intra-boucle.** Un park-and-ride (voiture jusqu'au
  relais, TC ensuite, reprise de la voiture au retour) n'est pas représentable : le mode
  d'un itinéraire est son mode principal. C'est ce que débloquerait une planification par
  boucle (décision au niveau de la tournée domicile→domicile plutôt que du trajet).
- **Replanification d'une même activité.** Si un trajet déjà planifié est recalculé et
  qu'un autre mode est retenu, la position du véhicule reflète la dernière décision, pas
  l'historique. Sans conséquence en pratique (les chemins de planification se gardent
  d'un double calcul), mais c'est une conséquence du choix d'un état de planification.
- **Populations sans domicile connu** (`identity.home` absent) : la contrainte est
  désactivée pour cet agent — comportement historique, compté sous `event="no_home"`. Le
  loader eqasim écarte ces agents dès qu'une bbox est posée, ce qui est le cas nominal.

## Réglages (`llm-agents/settings.py`, section `agent`)

| Réglage | Défaut | Effet |
|---------|--------|-------|
| `vehicle_chain_enabled` | `true` | Contrainte complète. `false` = comportement historique (possession = disponibilité partout), utile pour mesurer l'effet à population égale |
| `vehicle_return_home_lock` | `true` | Verrou de retour (règle 3) |
| `vehicle_orphan_reset_at_home` | `true` | Rattrapage des véhicules orphelins au domicile |
| `vehicle_orphan_alarm_ratio` | `0.05` | Seuil d'alarme sur la part des retours laissant un orphelin |
| `vehicle_orphan_alarm_min_returns` | `200` | Retours observés avant que l'alarme puisse se déclencher |

## Métriques

`agent_vehicle_chain_total{mode, event}` — `mode` ∈ `bike`/`car`, `event` ∈ :

| `event` | Signification |
|---------|---------------|
| `unavailable` | Mode écarté des options : véhicule possédé mais garé ailleurs |
| `forced_return` | Trajet de retour restreint à ce mode (l'agent ramène son véhicule) |
| `return_failed` | Verrou de retour inapplicable (aucun itinéraire dans ce mode) |
| `orphaned` | Retour au domicile avec le véhicule resté ailleurs |
| `reset_home` | Orphelin ramené au domicile par le rattrapage |
| `no_home` | Agent sans domicile connu : contrainte désactivée |

Effet attendu sur les parts modales : `trip_mode_by_purpose_total{mode}` (voir
[monitoring.md](monitoring.md)).

## Tests

`llm-agents/tests/test_vehicle_chain.py` — 52 tests sur les fonctions réelles du
contrôleur (possession, position initiale, les trois règles, orphelins, chaînes de
journée complètes, rattrapage au domicile).

```bash
cd llm-agents && .venv/bin/python -m pytest tests/test_vehicle_chain.py -q
```
