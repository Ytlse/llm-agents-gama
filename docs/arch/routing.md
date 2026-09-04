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
déduisent pas l'une de l'autre : chacune est une liste littérale, et une liste incomplète
produit un chiffre plausible et faux. État au 2026-09-04, après l'ajout de `rail`.

| Table | Rôle | Train |
|---|---|---|
| `trip_helper/otp.py` → `transportModes` | ce qui est **demandé** à OTP | `rail` ✅ |
| `trip_helper/otp.py` → `SUPPORTED_MODES` | ce qui est **accepté** en retour (assertion dure) | `rail` ✅ |
| `settings.gtfs.gtfs_modality_name_map` | `route_type` → nom lu dans le prompt | `"2": "Train"` ✅ |
| `llm_agent._PT_LEG_MODES` | déclenche la mention d'abonnement TC | `rail`, `train` ✅ |
| `move_logger._RAIL_MODES` / `_CANONICAL_FR` | colonne « Train » de `moves.csv` | ✅ |
| `mode_choice.CANONICAL_MODES` / `_MODE_KEYWORDS` | mode canonique de la répartition | `train` ✅ |
| `task_worker._extract_primary_mode` | mode principal, priorité train > métro > tram > bus | ✅ |
| `frames.PROBA_COLUMNS` / `CHOSEN_MODE_MAP`, pont oracle | libellé → catégorie EMC² | « Train » → TC ✅ |
| Grafana 05 et 07, `scripts/dashboard/palette.py`, `scripts/analysis/mode_probabilities.py` | couleur du mode (violet, cf. la palette du dépôt) | ✅ |
| `calibration/metrics.categorize_mode` et ses copies | **loss de calibration** | ❌ `rail` classé en marche |
| `simulation_controller._primary_mode` | métrique `TRIP_MODE_BY_PURPOSE` | ⚠ `rail` fondu dans `transit` |
| `audit_perimetre.MOVE_MODE_MAP` | audit de périmètre | ❌ pas d'entrée « Train » |
| `GAMA/…/Settings.gaml` → `ROUTE_DISPLAY_WIDTH`, `VEHICLE_MAX_CAPACITY` | largeur et capacité par `route_type` | ❌ pas de clé `2` |

Les quatre dernières lignes sont **latentes, pas inoffensives**, et chacune a sa raison
d'attendre une décision : la loss de calibration est l'instrument de mesure du prompt (tout
changement s'y chiffre avant de s'appliquer, amendement A13) ; le mode principal d'un trajet
combinant car et train relève de la hiérarchie des modes du ticket 022 ; et GAMA ne voit
aujourd'hui **aucun** train, parce que `trip_info.json` est produit du seul feed Tisséo
(`settings.gtfs.gtfs_file`). Voir les questions ouvertes du ticket 031.

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
