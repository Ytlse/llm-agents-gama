# Architecture du routage

Deux moteurs de calcul d'itinéraires coexistent avec des rôles strictement séparés.

---

## Vue d'ensemble

| Moteur | Modes | Technologie | Instances actives |
|--------|-------|-------------|-------------------|
| OTP | Transit (bus, tram, métro, téléphérique, **car interurbain liO**, **TER**) | GraphQL Transmodel v3 | 3 (`otp1/2/3`, ports 8080-8082) |
| OSMnx | Marche, vélo, voiture | Dijkstra sur graphe NetworkX | 1 (`osmnx1`, port 8090) |

Les deux moteurs sont interrogés **en parallèle** pour chaque agent, puis leurs résultats sont consolidés et dédupliqués avant la phase de décision LLM.

---

## OpenTripPlanner (transit)

OTP est dédié exclusivement aux transports en commun en mode horaire contraint.

### Logique `arrive_by`

Pour garantir que l'agent arrive à l'heure à son activité, le système utilise une inversion temporelle :

1. Calcul du `target_arrival_time` = heure de début de l'activité cible
2. Si `target_arrival_time` < timestamp simulation actuel → planification pour le lendemain (`+ 86400s`)
3. Requête OTP avec `arriveBy=True`

### API

- Endpoint unique : `/otp/transmodel/v3` (GraphQL)
- Données sources : extrait OSM du **polygone des 453 communes** (`data/gtfs/Toulouse.osm.pbf`,
  OSM 2022, ticket 031 T1 — avant le 2026-09-03 : rectangle de 30 km, hors duquel un domicile de
  3ᵉ couronne n'était pas rattachable, « Couldn't link ») + **trois** feeds GTFS
  (`data/gtfs/tisseo_gtfs/`, `ter_gtfs/`, `lio_gtfs/`), compilés en `data/gtfs/graph.obj`
  (84,4 Mo, 55 s de construction, 2,1 Go de pointe — [data-pipeline.md](../setup/data-pipeline.md))
- Le `graph.obj` est chargé en mémoire au démarrage (1,0 Go au chargement, 2,2 à 2,6 Go après
  2 580 requêtes ; limite 6 Go)
- Contrôle de rattachement d'une population : `scripts/data/gtfs/otp_link_check.py` — sur la v4
  (1 000 domiciles + 1 580 lieux d'activité distincts, lundi 16 mars 2026 8 h) :
  **0 `LOCATION_NOT_FOUND`**, 314 points sans itinéraire TC dont 91 `noStopsInRange` et 124
  `walkingBetterThanTransit` (des points sans TC ou mieux servis à pied, pas un défaut de
  graphe). Le script ventile ses résultats **par couronne de résidence** — c'est là que se lit le
  manque de desserte, invisible dans un total — et compte les itinéraires qui **proposent un
  train** ; `--num-trip-patterns 6` reproduit ce que le runtime demande réellement

### Les trois réseaux, en service depuis le 2026-09-04

| Réseau | Feed servi | Ce qu'il porte |
|---|---|---|
| Tisséo | `tisseo_gtfs` (export en service) | 124 lignes urbaines — bus, tram, métro, Téléo |
| liO | `lio_gtfs` = **feed annuel `lio_2026`** | 302 lignes d'autocar interurbain (`route_type=3`), dont 56 touchent les 453 communes |
| TER Occitanie | `ter_gtfs` = **feed annuel `ter_2026`** | 17 lignes ferroviaires (`route_type=2`), 234 arrêts |

Les deux feeds régionaux passent par le **feed annuel** (`gtfs-annee.md`) pour une raison
mesurée : l'export liO ne couvre rien avant le 1ᵉʳ août 2026, et l'export TER en service
(2026-04-29 → 2026-10-26) ne faisait rouler **aucun train le 16 mars 2026**, la journée simulée.

**Les modes demandés à OTP sont `bus`, `metro`, `tram`, `cableway` et `rail`**
(`trip_helper/otp.py`), et `gtfs_modality_name_map` nomme les `route_type` 0, 1, **2**, 3 et 6.
Un réseau présent dans le graphe dont le mode n'est pas demandé est **introuvable, sans aucun
signal** : le TER est resté dans ce cas du 2026-09-03 au 2026-09-04, ses arrêts comptant dans
l'enveloppe de desserte sans qu'aucun agent puisse s'en voir proposer un. Les cars liO, eux,
sont en `route_type=3` et passent par `bus`.

**La porte de proximité doit voir tous les réseaux.** `OTPTripHelper._has_reachable_stop`
(1 500 m) saute l'appel à OTP quand ni l'origine ni la destination n'a d'arrêt à portée. Bâtie
sur le seul feed primaire, elle **écartait 397 des 2 580 points de la v4** — 245 des 374 de
3ᵉ couronne, 150 des 339 de 2ᵉ — qui n'ont à portée qu'un arrêt liO ou une gare TER. Elle
énumère désormais les feeds comme OTP le fait (un répertoire ou un zip portant `stops.txt` au
premier niveau du répertoire de build) : 17 955 arrêts au lieu de 5 661. Un seul feed trouvé
lève un avertissement au démarrage, et un balayage plus pauvre que le feed primaire une
`[ALARME]` avec repli sur celui-ci — la porte ne rétrécit jamais en silence.

> **Ce que la journée simulée voit** (v4, lundi 16 mars 2026 8 h, destination le Capitole).
> Points sans itinéraire TC : **670 → 314** entre l'état Tisséo+TER-export et l'état en service ;
> par couronne, 3ᵉ **369 → 148**, 2ᵉ **160 → 26**, 1ʳᵉ 9 → 8, Toulouse inchangé à 132 (tous
> `walkingBetterThanTransit`). Sur les six itinéraires que le runtime demande par trajet,
> **1 883 des 11 288 rendus proposent un train** (16,7 %), et **833 points** en ont au moins un —
> dont 169 des 374 de 3ᵉ couronne, où 58 % des itinéraires passent par le rail. Toutes les jambes
> ferroviaires portent l'autorité SNCF VOYAGEURS.
>
> Les cars TER de substitution, eux, ont été cherchés dans le GTFS SNCF national (ticket 031, T6) :
> **trois courses, toutes le 2026-09-03**, une substitution de travaux. Décision : ne pas charger
> ce feed.

Le feed Tisséo consommé par la simulation est une **fenêtre** du feed annuel :
GAMA encode le calendrier des services en masque binaire 64 bits et ne peut pas
en absorber davantage. Voir [`gtfs-annee.md`](gtfs-annee.md).

### Load balancing

Les trois instances OTP (`otp1`, `otp2`, `otp3`) reçoivent les requêtes via la variable :

```
OTP_ENDPOINTS=http://otp1:8080/otp/transmodel/v3,http://otp2:8080/otp/transmodel/v3,http://otp3:8080/otp/transmodel/v3
```

La concurrence OTP est bornée côté controller : `otp_max_concurrent: 30`.

---

## Cluster OSMnx (modes directs)

Chaque instance OSMnx charge trois graphes topologiques en RAM au démarrage — un worker par mode,
1,0 à 1,4 Go de RSS chacun une fois son graphe isolé (pointe 2,8 à 3,0 Go au chargement du pickle),
d'où la limite de 8 Go du service.

### Le graphe : le polygone des 453 communes (ticket 031, partie 2)

Depuis le 2026-09-03, le graphe servi est celui du **polygone des 453 communes** de l'enquête
(`geography.PERIMETER_CACHE_KEY` = `444ca7e6a515`, label `perimetre_453_communes:cc1:osm-220101`,
pickle de 225 Mo : marche 176 340 nœuds / 472 544 arêtes, vélo 151 833 / 360 801, voiture
65 150 / 148 959), construit hors ligne par `make osmnx-perimeter-graph` depuis les pbf OSM régionaux
— le même graphe que le notebook de population (étapes 4+5). La clé se configure
(`gtfs.osmnx_graph_key`) ; `osmnx_server` et `_GraphStore` refusent de démarrer si son pickle manque
(`[ALARME]`, `GraphMissingError`) au lieu de télécharger un disque de 30 km à sa place. Le disque
historique (`ecb40f20a303`, `TOULOUSE_CENTER_DIST_M`) ne sert plus qu'à l'audit : sur lui, un trajet
de 3ᵉ couronne sur six n'était pas un itinéraire mais un repli à 70 km/h (ticket 031 § 1.4).

Les vitesses de `config/osmnx.yaml` sont posées sur le pickle à sa construction ; après une
modification, `build_osmnx_perimeter_graph.py --respeed` les repose (26 s). Le 2026-09-03, le mode
vélo a reçu ses vitesses pour `service`, `track`, `trunk`, `*_link`, `pedestrian`, `footway`, `road`,
`bridleway`, `busway` (source GraphHopper, profil `bike`, et code de la route pour les sections
poussées) : 32,0 % des arêtes vélo étaient en repli à 14 km/h, il en reste 2 (0,0 %) ; la voiture
gagne `living_street` (20 km/h, zone de rencontre) et `motorway_link` (70). Toute modification de
ces vitesses change la durée réseau : `routing_version` est passée à `r2`.

### Modes et coupures

| Mode | Vitesse | Coupure spatiale | Modèle de congestion |
|------|---------|-----------------|----------------------|
| Marche (`walk`) | Fixe (config) | 15 km | Non |
| Vélo (`bike`) | Paramétrable | 30 km | Non |
| Voiture (`drive`) | Dynamique | Aucune | Profils horaires TomTom Toulouse, **par zone d'arête** |

Les requêtes au-delà des coupures spatiales sont rejetées sans calcul Dijkstra.

### Congestion par zone d'arête (ticket 031, décision 4)

Chaque nœud du graphe porte une **zone** (`trip_helper/congestion_zones.py`) : `city` — la commune
de Toulouse (frontière géocodée du graphe) ; `agglo` — l'agglomération hors Toulouse, union des
couronnes Toulouse + 1ʳᵉ + 2ᵉ de l'enquête (`llm_module/data/couronne_perimetre.geojson`) ;
`outside` — le reste (la 3ᵉ couronne et au-delà). La durée congestionnée d'un trajet voiture est la
**somme des temps libres de ses arêtes, chacun multiplié par le facteur TomTom de la zone de son
nœud d'origine à l'heure de départ** : profil « ville » (`city_raw`) en ville, « agglomération »
(`metro_raw`) en agglomération, **1,0 dehors**. Un trajet 3ᵉ couronne → Toulouse n'est donc
congestionné que sur sa part agglomérée ; un village → village de 3ᵉ couronne ne l'est pas.

Avant le 2026-09-03, un seul facteur s'appliquait à tout le trajet : « ville » si un bout touchait
Toulouse, « agglomération » sinon — soit 1,84 un lundi à 8 h sur un trajet rural que rien ne
congestionne. Les zones sont posées une fois : à la construction du graphe du polygone des 453
communes (`make osmnx-perimeter-graph`, option `--zones-only` pour un pickle existant) et, pour le
graphe historique de 30 km, paresseusement au premier chargement (`_GraphStore`, `route_worker`,
réplicas), puis mises en cache dans le pickle. Un nœud sans zone est une erreur explicite (pas de
facteur deviné) ; la géométrie des couronnes doit être visible du service (montage
`llm_module/data/couronne_perimetre.geojson` dans les réplicas `osmnx`). Le repli « même nœud »
(deux bouts rabattus sur le même nœud) rend une durée à la vitesse de repli du mode sur la
distance à vol d'oiseau × 1,3, minimum 1 s — plus 70 km/h pour tous les modes.

### Calcul `arrive_by` (modes directs)

Les itinéraires OSMnx ne supportent pas nativement `arriveBy`. Le système calcule le trajet à vitesse nominale, puis décale le résultat en arrière dans le temps pour aligner l'heure de fin sur `target_arrival_time`.

### Temps terminal : accès et diffusion (ticket 013)

Ce que renvoie le moteur OSMnx est du **temps de parcours réseau pur**. La part non
conduite d'un trajet véhiculé — rejoindre le véhicule, chercher où le garer, marcher
jusqu'à la destination — n'est plus fondue dans cette durée (`park_base` de
`config/osmnx.yaml` est retiré, conservé commenté) : elle est portée par des **jambes
nommées** que `_make_travel_plan` ajoute de part et d'autre du tronçon routé, et que le
gabarit de rendu décompose ligne par ligne. Un plan voiture ou vélo compte donc **trois
jambes**, pas une.

| | Accès | Diffusion |
|---|---|---|
| Tarifé sur | couronne d'**origine** (où le véhicule est garé) | couronne de **destination** (où trouver une place) |
| Voiture | 1 à 3 min | 1 à 7 min (stationnement + recherche) |
| Vélo | 1 min (non spatialisé, non sourcé) | 1 min |
| Marche | — (porte-à-porte) | — |
| Transports collectifs | — (jambes de marche **déjà** routées par OTP) | — |

Trois propriétés structurent le dispositif :

- **Paramètre exogène**, valeurs et provenance dans `llm-agents/config/terminal_time.yaml`
  (NCHRP 716, COMPASS, Shoup, Millard-Ball, Cerema) — jamais ajusté pour améliorer un score.
- Les couronnes sont celles de l'enquête — appartenance aux couronnes par liste de
  communes (`llm_module.core.residence_zone.CommunalZones`, ticket 028), **la même
  définition** que le trait `residence_zone` du persona et que la colonne « Lieu de
  résidence » du move-log : deux classements divergents factureraient un stationnement de
  centre-ville à un agent que le journal dit en 1ʳᵉ couronne. Les lois de
  `terminal_time_emc2.json` sont stratifiées sur cette même table (`tt4`). Un point hors
  des 453 communes reçoit `hors périmètre`, donc la loi `default` — compté
  (`terminal_time_out_of_perimeter_total`) et alarmé une fois, jamais rangé en silence
  dans la couronne la plus externe.
- Les jambes terminales portent `is_transfer=True` et un marqueur `__TERMINAL_*`, ce qui les
  exclut de `TravelPlan.get_code()` et de `mode_label()` : **décomposer l'affichage d'une
  option ne doit pas la faire passer pour une autre option** (le code est la clé du cache de
  décisions, l'étiquette de mode alimente la loss de calibration).

Deux versions distinctes en découlent, et la distinction n'est pas cosmétique :
`version` (temps terminal) indexe les caches qui mémorisent des **plans** — itinéraires OTP,
décisions LLM ; `routing_version` indexe le cache de routage OSMnx, qui ne mémorise que du
temps réseau. Les confondre ferait recalculer des milliers de routes (~2 h pour 930
personas) à chaque ajustement du stationnement. Détail dans
[cache-memory.md](cache-memory.md).

Une **grille de sensibilité** (`sensitivity:` du même fichier, `terminal_time.apply_variant`)
met les valeurs à l'échelle par un facteur uniforme — 0,5 / 1 / 1,5 — pour savoir si une
conclusion dépend du réglage. Le nom de la variante entre dans `data_version()`, donc les
trois jeux ne partagent aucune clé de cache. ⚠ Cette grille n'a **pas encore de script qui
la parcourt** : elle est appelable et testée, la mesure T6 reste à produire.

### Gestion du multi-processing

Le GIL Python bloque l'exécution parallèle des algorithmes Dijkstra dans le même processus. L'architecture s'adapte selon l'environnement :

| Contexte | Executor | Raison |
|----------|----------|--------|
| Conteneur Docker standard | `ProcessPoolExecutor` (1 worker/mode) | Isolation CPU complète |
| Processus démonisé (Uvicorn/Hypercorn) | `ThreadPoolExecutor` | Interdit de forker depuis un démon Python |

### Déploiement

En production, une seule instance (`osmnx1`) est active par défaut. Des replicas supplémentaires peuvent être décommentés dans `docker-compose.yml` :

```yaml
# osmnx2:
#   <<: *osmnx-service
#   ports:
#     - "8091:8090"
```

Le controller les répartit en round-robin via `OSMNX_ENDPOINTS`.

---

## Consolidation des résultats

Après les appels OTP et OSMnx (parallèles), le controller :
1. Unifie les timestamps en millisecondes
2. Déduplique les itinéraires identiques
3. Mélange aléatoirement l'ordre de présentation au LLM (anti-biais de position)
4. Transmet la liste au module de décision LLM

### Le plafond de candidats, et où il pince

`settings.gtfs.max_trip_candidates` (**6**) sert deux fois, et ce n'est pas la même chose :

| Où | Ce que le 6 fait |
|---|---|
| `trip_helper/otp.py` → `numTripPatterns` | **combien OTP en cherche.** Il rend ses 6 meilleurs motifs au coût généralisé ; avec trois réseaux dans le graphe, ils peuvent tous être des bus, et l'option ferroviaire n'existe alors *pas* avant même la sélection |
| `simulation_controller._select_candidates` | **combien l'agent en voit.** Le plus rapide par groupe de mode d'abord (groupe = `_primary_mode`), puis remplissage jusqu'à 6 — options directes marche/vélo/voiture incluses, qui occupent donc des créneaux |

Mesuré le 2026-09-04 sur les 2 580 points de la population scellée v4 vers le Capitole,
lundi 16 mars 2026 8 h (7 740 requêtes,
[trace](../traces/2026-09-04_10-17_hierarchie_modes_enquete/README.md)) :

| `numTripPatterns` | motifs rendus | points avec ≥ 1 train | plafond OTP atteint | ms/requête |
|---:|---:|---:|---:|---:|
| **6** (production) | 11 281 | **833 (32,3 %)** | 59,7 % | 236,6 |
| 10 | 16 246 | 867 (33,6 %) | 42,2 % | 252,1 |
| 20 | 24 204 | 878 (34,0 %) | 24,5 % | 207,6 |

Côté sélection, sur le run archivé `2026-09-04_01_09` (4 768 décisions) : le plafond de 6
est **atteint dans 44,7 %** des décisions, et l'agent voit 1 seul mode distinct dans 22,6 %
des cas, 2 dans 28,6 %, 3 dans 35,1 %, 4 dans 13,7 %.

⚠ Monter ce réglage change le prompt, donc les décisions et le cache de décisions : c'est
une décision de l'auteur, pas un ajustement.

---

## Modes disponibles par agent

Tous les modes ne sont pas interrogés pour tous les agents : le jeu d'options est
restreint **avant** les appels de routage, dans `_compute_move_for_activity`
(`urban_mobility_agents/simulation_controller.py`).

| Mode | Condition | Source |
|------|-----------|--------|
| Voiture | `number_of_cars > 0` **et** la voiture est au point de départ | trait du ménage + état de chaîne |
| Vélo | possède un vélo **et** le vélo est au point de départ | trait individuel + état de chaîne |
| Marche, transports collectifs | toujours | — |

`include_car` / `include_bike` conditionnent la requête OSMnx *et* un post-filtre sur les
plans revenus (un motif OTP peut contenir un tronçon vélo). Ils alimentent aussi la clé du
cache de routage persistant : un trajet calculé sans vélo ne pollue pas celui calculé avec.

### Option synthétique : le car scolaire (ticket 030)

Le transport scolaire est le premier mode collectif des 2ᵉ et 3ᵉ couronnes mais n'existe dans
aucun GTFS. Une **option synthétique** le supplée, produite par
[`trip_helper/school_bus.py`](../../llm-agents/trip_helper/school_bus.py) — une fonction, pas un
moteur : aucun appel OTP ni OSMnx. Elle est injectée dans `_compute_move_for_activity` après le
post-filtre et **avant** le verrou de retour (un élève venu en voiture reprend la voiture ; venu en
car scolaire, il le retrouve au retour).

| Aspect | Règle |
|--------|-------|
| Éligibilité | persona **5-17 ans** + domicile **hors ressort Tisséo** (`home.public_transport is False`) + trajet lié à l'activité `education`. Ni sectorisation, ni seuil de distance. |
| Horaire | calé sur l'activité scolaire, **± 30 min** (aller : arrive 30 min avant le début ; retour : part 30 min après la fin). |
| Durée | `accès + distance_vol_d'oiseau × détour / vitesse + ramassage`, paramètres figés de [`config/school_bus.yaml`](../../llm-agents/config/school_bus.yaml), calés sur la médiane EMC² (≈ 30 min). |
| Coût | nul (gratuité régionale) — porté par le libellé de rendu, aucun champ tarif dans le modèle. |
| Mode / métriques | `mode="school_bus"` → compté en **transport collectif** (`move_logger._BUS_MODES`, `mode_choice.canonical_mode`, `categorize_mode`, pont oracle). **Exception** : `_pt_subscription_note` l'exclut (gratuit, pas d'abonnement). |
| Rendu GAMA | `transit_route="__DIRECT_CAR__"` → GAMA l'interpole point-à-point comme une voiture, **sans édition GAMA** ; l'agent s'affiche en rouge (lot GAMA hors périmètre). Arrêts nommés non vides pour que `get_code()` diffère d'une vraie voiture (anti-collision de déduplication). |

L'enquête EMC² reste la source de la **durée** (réalisme physique) ; l'**éligibilité** vient du
règlement liО, pas de l'enquête. Détail et décisions : `docs/tickets/ticket_030_car_scolaire_synthetique.md`.

### Les listes de modes, et où en est le train

Un mode traverse une dizaine de tables avant d'arriver dans une part modale. Elles ne se
déduisaient pas l'une de l'autre : chacune était une liste littérale, et une liste
incomplète produit un chiffre plausible et faux. **Depuis le 2026-09-04 (ticket 022),
l'ORDRE de priorité n'est plus qu'à un seul endroit** — voir
[« La hiérarchie des modes »](#la-hiérarchie-des-modes-une-seule-source) plus bas. Les
listes d'appartenance, elles, restent plurielles ; le tableau ci-dessous dit où elles en
sont.

| Table | Rôle | Train |
|---|---|---|
| `trip_helper/otp.py` → `transportModes` | ce qui est **demandé** à OTP | `rail` ✅ |
| `trip_helper/otp.py` → `SUPPORTED_MODES` | ce qui est **accepté** en retour (assertion dure) | `rail` ✅ |
| `settings.gtfs.gtfs_modality_name_map` | `route_type` → nom lu dans le prompt | `"2": "Train"` ✅ |
| `llm_agent._PT_LEG_MODES` | déclenche la mention d'abonnement TC | `rail`, `train` ✅ |
| **`llm_module/data/mode_hierarchy_emc2.json`** | **l'ordre de priorité, gelé depuis le rapport p. 53** | rang **5** ✅ *(2026-09-04)* |
| `move_logger._RAIL_MODES` / `_CANONICAL_FR` | colonne « Train » de `moves.csv` | vues de la hiérarchie ✅ *(2026-09-04)* |
| `mode_choice.CANONICAL_MODES` / `_MODE_KEYWORDS` | mode canonique de la répartition | `train`, ordre contrôlé à l'import ✅ *(2026-09-04)* |
| `task_worker._extract_primary_mode` | compteurs de diagnostic ; suit la hiérarchie | ✅ *(2026-09-04)* |
| `frames.PROBA_COLUMNS` / `CHOSEN_MODE_MAP`, pont oracle | libellé → catégorie EMC² | « Train » → TC ✅ |
| Grafana 05 et 07, `scripts/dashboard/palette.py`, `scripts/analysis/mode_probabilities.py` | couleur du mode (violet, cf. la palette du dépôt) | ✅ |
| `calibration/metrics.categorize_mode` et sa copie `prompt_calibration_lib` | **loss de calibration** | `rail`, `train`, `ter` ✅ *(2026-09-04)* |
| `GAMA/…/Settings.gaml` → `ROUTE_DISPLAY_WIDTH`, `VEHICLE_MAX_CAPACITY`, `TYPE_RAIL` | largeur, capacité et filtres par `route_type` | clé `2` ✅ *(2026-09-04)* |
| `simulation_controller._primary_mode` | métrique `TRIP_MODE_BY_PURPOSE`, et **regroupement de `_select_candidates`** | `rail` fondu dans `transit` — **correct** : ce sont les 4 catégories agrégées de l'enquête, où le train EST dans les TC (rangs 1 à 13, p. 53) ✅ *(2026-09-04)* |
| `move_logger._plan_transport_mode` — **ordre** de la cascade | colonne « Mode de transport Choisi » | lit la hiérarchie ; `_BUS_MODES` avant `_RAIL_MODES` est **conforme à l'enquête** ✅ *(2026-09-04)* |
| `simulation_controller._vehicle_mode` | chaîne des véhicules (ticket 008) : verrous, stationnement, passager | hors hiérarchie **par construction** — c'est « où est la voiture », pas « quel est le mode principal » |
| `mode_labels.AGGREGATION` (audit de périmètre A7 et A2, carnet `selected_mode_stats`) | libellé fin → catégorie EMC², **et l'alarme sur tout libellé hors table** | « Train » → TC ✅ *(2026-09-04)* |

**Deux corrections livrées le 2026-09-04, mesurées avant application.**

* **La loss de calibration** (`categorize_mode`) n'avait de mot-clé ni pour `rail`, ni pour
  `train`, ni pour `ter` : « foot,rail,foot » tombait sur le mot « foot » et le TER était
  compté en **marche** — le défaut du Téléo du 2026-08-26, sur un mode dix fois plus offert.
  La cascade cherche désormais ses mots-clés **par mot** et non par sous-chaîne, parce que
  « car » désigne un autocar en français et que liO n'est composé que d'autocars : le
  libellé « autocar » était rangé dans **voiture**. Effet chiffré sur les mesures déjà
  publiées : **zéro** — aucun des 111 libellés des jeux gelés (385 888 options) ni des 86
  libellés des décisions en cache (444 055 décisions) ne contient `rail`, `train` ni `ter`
  (vocabulaire réel : `foot`, `bus`, `metro`, `tram`, `cableway`, `car`, `bicycle`).
  Le test de parité **lit les listes de production dans leur source** au lieu d'en recopier
  un littéral : un littéral ne tombe que si l'instrument change, jamais si la production
  change, et c'est cette asymétrie qui avait laissé passer les deux défauts.
* **Les tables `route_type` de GAMA** n'avaient pas de clé `2`, alors que les couches
  régénérées portent **34 tracés** et **68 arrêts** en `route_type=2`. Une clé absente rend
  `nil` : tracé sans épaisseur et capacité de zéro place. Les clés sont posées (largeur 25,
  capacité 300 — ordre de grandeur sourcé sur le matériel roulant d'Occitanie, cf.
  `Settings.gaml`), et surtout un **garde-fou** recense au chargement les `route_type`
  présents dans les trois sources qui indexent ces tables (`routes.shp`, `stops.shp`,
  `trip_info.json`) et alarme sur tout type qu'elles ignorent.

**Ce que le garde-fou a immédiatement trouvé** : `trip_info.json` (28 Mo, produit du seul
feed Tisséo) ne porte **aucune** course `route_type=2`, alors que `routes.shp` en trace 34.
GAMA dessine donc 34 lignes de TER et 68 gares où **aucun train ne roulera** — une ligne
visible et morte se lit comme une ligne sans passage, pas comme une donnée manquante. Le
journal le dit maintenant :

```
[PERIMETRE] route_type=2 (Train) : 34 lignes, 68 arrêts, 0 courses — largeur 25.0, capacité 300 places.
[ALARME] route_type tracé(s) dans routes.shp mais ABSENT(s) de trip_info.json : [2.0] — aucun véhicule de ce type ne roulera.
```

### La hiérarchie des modes : une seule source

**Arbitrage du ticket 022, rendu le 2026-09-04 : la hiérarchie du dépôt est celle de
l'enquête.** L'ordre n'est plus écrit dans le code : il est gelé dans
[`llm_module/data/mode_hierarchy_emc2.json`](../../llm_module/data/mode_hierarchy_emc2.json)
et servi par [`llm_module/core/mode_hierarchy.py`](../../llm_module/core/mode_hierarchy.py).

    métro > tram > téléphérique > bus (car liO, car scolaire, TAD) > train
          > voiture > deux-roues motorisé > vélo > marche

**Il n'y avait rien à postuler : l'ordre est publié.** Le rapport AUAT/CEREMA donne en
annexe, **page 53** (« Hiérarchie des modes »), les 36 modes enquêtés dans l'ordre — celui
qui, dit le même rapport p. 12, « découle d'une hiérarchisation des modes définie au niveau
national ». Il est **contrôlé sur les microdonnées** par
[`export_mode_hierarchy.py`](../../scripts/progedo_logit/export_mode_hierarchy.py) : 53
paires de codes tranchées par 2 607 observations, **53 conformes sur 53**, une seule
observation à contre-courant et elle est conforme à l'annexe (un Flixbus, rang 12, perd
contre un TER, rang 8).

**Le cran qui surprend : le bus passe AVANT le train** (rangs 4 et 8 ; mesuré, 34
déplacements mixtes sur 35 codés bus). Un itinéraire « autocar liO + TER » est donc un
déplacement en **transports collectifs**, pas en train. Le constat déposé la veille dans le
ticket 022 — « la colonne Train de `moves.csv` sous-compte le rail de 62,5 % » —
**s'inverse** : les 1 177 itinéraires concernés sont correctement étiquetés
`Transports_collectifs`. `_BUS_MODES` avant `_RAIL_MODES` était conforme ; c'étaient
`mode_choice` et `task_worker`, qui testaient le train **en tête**, qui divergeaient.

**Le cran qui mordait : la voiture après tout le collectif** (rang 19, contre 1 à 13).
`_plan_transport_mode` et `_primary_mode` la testaient **en premier**, alors que l'enquête
code 760 de ses 770 déplacements mixtes voiture + TC en « transports collectifs » (axe A7,
rejoué à l'unité). Latent jusqu'ici : OTP est interrogé mode par mode.

**Ce que le mode principal N'EST PAS.** La chaîne de véhicules du ticket 008 demande « où
est la voiture », pas « quel est le mode principal » : sur un rabattement, l'enquête classe
le déplacement en TC *et* la voiture doit être garée à destination. Les deux lectures sont
donc séparées — `_primary_mode` (hiérarchie, métrique, regroupement) et `_vehicle_mode`
(verrous de sortie et de retour, stationnement, passager). Les confondre faisait perdre la
voiture au verrou de retour.

**Effet mesuré avant application** (`docs/traces/2026-09-04_10-17_hierarchie_modes_enquete/`,
versions « avant » extraites par `git show`, jamais recopiées) : **zéro bascule** pour
`_plan_transport_mode` et `canonical_mode` sur les 385 888 options des jeux gelés, les
444 055 décisions en cache et les 17 258 options du run archivé. Aucun résultat publié ne
bouge, et le critère de non-régression du ticket est vérifié par la mesure. Les seules
bascules sont des corrections des compteurs de diagnostic du worker : le Téléo et le car
scolaire sortent de `other`, où ils atterrissaient **avec un ERROR à chaque décision**.

**Ce que la métrique à quatre catégories n'a pas de fautif.** Le ticket annonçait que
Grafana 07 « compare une base à quatre modes à une base à cinq ». Vérification :
`grafana/dashboards/07_metier_mobilite.json` mappe `public_transport|train → tc` d'un côté
et `transit → tc` de l'autre. **Les deux séries sont ramenées aux mêmes quatre catégories
EMC²** — celles que l'annexe p. 53 nomme, où les rangs 1 à 13 forment « transports en
commun », train compris. Fondre `rail` dans `transit` est correct pour cette métrique.

⚠ Reste une limite du regroupement, chiffrée et **non corrigée** : `_select_candidates`
groupe par `_primary_mode`, donc un train pur et un bus + train partagent l'unique créneau
`transit`. Sur les 440 points où une option de train pur existe, **122 (27,7 %)** sont
écartés au profit d'un bus + train plus rapide, et le train ne s'offre jamais comme choix
distinct. Corriger cela change le prompt : décision de l'auteur (ticket 022).

**Le bout aval de la chaîne, corrigé le 2026-09-04.** `audit_perimetre.MOVE_MODE_MAP`
écartait (`continue`) tout libellé hors de ses quatre entrées : un déplacement « Train »
sortait de l'audit des parts modales sans être compté ni signalé. Le carnet
`scripts/analysis/selected_mode_stats.ipynb` faisait le même geste par un `replace()`
incomplet suivi d'un `reindex(mode_order)`. Les deux lisent désormais **une seule** table,
[`scripts/analysis/mode_labels.py`](../../scripts/analysis/mode_labels.py), qui publie le
**détail par libellé** et la **table d'agrégation** vers les catégories de l'enquête, et
dont la couverture est confrontée à
[`mode_hierarchy`](../../llm_module/core/mode_hierarchy.py) à chaque comptage. Un libellé
hors table est compté sous `libelle_inconnu`, nommé, et alarmé en ERROR dans l'`app.log`
du run — donc lu par `make error`. Détail : [`perimetre-population.md`](perimetre-population.md),
axe A7.

**Le train est un groupe d'options à part depuis le 2026-09-04.** `_select_candidates` plafonne
les itinéraires offerts à l'agent à `settings.gtfs.max_trip_candidates` (**6**, tenu à 6 par
décision du même jour) en gardant d'abord le plus rapide de chaque **groupe**. Le groupe était la
catégorie agrégée de l'enquête : un train direct et un bus + train y tombaient ensemble, et le
plus lent des deux ne passait pas. Mesuré sur les 2 580 points de la population scellée v4 : sur
les **440 points où un itinéraire ferroviaire direct existe, 122 (27,7 %)** le perdaient au
profit d'un bus + train plus rapide — l'agent ne voyait donc jamais le train comme un choix.
`_selection_group` scinde désormais le collectif en deux, ferroviaire et reste.

**Seul le train est scindé, et c'est mesuré.** Avec une clé par famille (métro, tram,
téléphérique, bus, train), huit groupes se disputeraient six créneaux, et la passe de priorité —
qui prend le plus rapide de chaque groupe inédit par durée croissante — pourrait remplir les six
de variantes collectives en **écartant la voiture**, le vélo ou la marche. Avec cinq groupes, les
cinq tiennent et il reste un créneau de remplissage ; un test le vérifie. Cette clé ne sert qu'à
l'affichage : `trip_mode_by_purpose` et les parts modales restent sur les **quatre catégories** de
l'enquête, où le train est un transport collectif.

**Le catalogue des lignes réunit les trois réseaux depuis le 2026-09-04.** `GTFSData` ne
charge qu'un feed (`settings.gtfs.gtfs_file`, Tisséo) alors que le graphe OTP en porte trois.
Un identifiant de ligne liO ou TER ne se trouvait donc dans aucune table, et le prompt de
l'agent lisait « Trajet en **Unknown 392** » pour les **319 lignes** des deux réseaux
régionaux — le mode *et* le numéro perdus, alors que la table des modalités connaît le train
(`route_type` 2) depuis le même jour. `init_route_lookup_maps` joint désormais le **catalogue
des lignes** des autres feeds en service (`trip_helper.otp.feeds_en_service`, la même
énumération que la porte de proximité), et rien d'autre : ni horaires, ni arrêts, les tables
lourdes du feed primaire restant intactes. Mesuré : **443 lignes** au catalogue dont 319
venues de liO (302) et du TER (17), **0 de mode inconnu**. La jointure se fait par
`route_id` — sans collision entre les trois feeds ; les **noms courts**, eux, collisionnent
(37 mesurés, une ligne « 1 » existant partout) et restent au feed primaire, la ligne
régionale demeurant joignable par son identifiant. Une collision d'`route_id` serait une
ambiguïté réelle : elle s'alarme.

**Un troisième défaut du même genre, trouvé et corrigé en chemin** :
`mode_choice.canonical_mode("foot,cableway,foot")` renvoyait **`walking`**. Le Téléo ne
figurait dans aucune des six listes de `_MODE_KEYWORDS` ; la cascade descendait jusqu'à
« walking », que le mot `foot` satisfait. La masse de probabilité d'une option de
téléphérique **pur** était donc comptée en marche dans `mode_distribution`, donc dans les
colonnes `P(...) %` de `moves.csv` et dans `llm_mode_probability_pct_total`. Sans exception
et sans WARNING : la chaîne composée ne tombait même pas dans `other`. `cableway`,
`gondola` et `funicular` sont ajoutés ; effet chiffré avant application : **120** des
385 888 options des jeux gelés (0,031 %) et **5** des 17 258 du dernier run archivé — un
seul libellé concerné.

**Le libellé de ligne, lui, est un défaut actif** : `GTFSData.DEFAULT()` ne lit que
`data/gtfs/tisseo_gtfs`, donc `route_id_map` ne connaît que les 124 lignes Tisséo et
`get_route_type_string_by_id` renvoie « Unknown » pour les **319 lignes liO et TER** — le prompt
de l'agent lit « Trajet en Unknown 392 vers "MURET SNCF" ». Les `route_id` des trois feeds ne se
collisionnent pas (0 collision mesurée), donc une union par `route_id` est sûre ; les
`route_short_name`, eux, collisionnent (au moins 20 entre Tisséo et liO), donc
`route_name_id_map` ne peut pas être unioné tel quel. Corriger change le texte du prompt, donc
les résultats et le cache de décisions : question ouverte du ticket 031.

### Cohérence de chaîne des véhicules

La possession seule ne suffit pas : un agent parti travailler en bus a laissé son vélo au
domicile et ne peut pas repartir avec — et la même contrainte vaut pour la voiture.
`PersonState.planning_vehicle_at` suit la **position** de chaque véhicule le long de la
chaîne planifiée (clé absente ⇒ au domicile) :

- **verrou de sortie** : le mode n'est proposé que si le véhicule est au point de départ ;
- **stationnement** : le véhicule utilisé suit l'agent, les autres restent où ils sont ;
- **verrou de retour** : un trajet vers le domicile partant d'un lieu où un véhicule est
  garé est restreint à ce mode — l'agent le ramène, sans appel LLM supplémentaire ;
- **« pas de déplacement »** (même localisation) : inchangé, l'agent n'a pas bougé.

C'est un état de **planification** : le plan court devant l'exécution GAMA, le champ suit
la chaîne planifiée et non la position réelle de l'agent. La séquentialité par agent est
garantie — le pré-calcul par vagues fait avancer chaque agent d'une activité par vague,
avec barrière avant la suivante (cf. `docs/arch/agents-lifecycle.md`).

Détail complet, cas résiduels (véhicules orphelins), réglages et métriques :
[vehicle-chain.md](vehicle-chain.md).

**Effet mesuré (étape vélo).** Rejouée sur le run `2026-07-29_18_34`, la règle invalide
352 des 1086 trajets à vélo, soit **5,9 points de part modale** (18,2 % → 12,3 % en borne
haute, si tout se reporte hors vélo). Cible EMC² 2023 : 4 %. L'extension à la voiture n'a
pas encore de mesure rejouée : `vehicle_chain_enabled=false` permet le run témoin.
