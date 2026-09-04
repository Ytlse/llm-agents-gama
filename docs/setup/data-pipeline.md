# Pipeline de données géospatiales

Ce document couvre les trois sources de données géospatiales utilisées par la simulation : GTFS (horaires transport), OpenTripPlanner (routage transit) et OSMnx (routage direct).

---

## 1. Données GTFS — Tisséo + TER + liO

Les trois réseaux du périmètre des 453 communes. OTP lit le dossier `data/gtfs/` au complet lors
de la construction du graphe : tout sous-dossier qui contient un `trips.txt` est chargé comme un
feed, et les feeds sont fusionnés automatiquement.

| Source | Dossier en service | Lien |
|--------|---------|------|
| Tisséo (réseau urbain Toulouse) | `data/gtfs/tisseo_gtfs/` — **export en service** | https://data.toulouse-metropole.fr/explore/dataset/tisseo-gtfs/information/ |
| TER SNCF (réseau régional) | `data/gtfs/ter_gtfs/` = **feed annuel `ter_2026`** (depuis le 2026-09-04) | https://www.data.gouv.fr/fr/datasets/horaires-des-lignes-ter-sncf/ |
| **liO** (cars interurbains d'Occitanie) | `data/gtfs/lio_gtfs/` = **feed annuel `lio_2026`** (depuis le 2026-09-04) | https://transport.data.gouv.fr/datasets/reseau-lio-occitanie |

**liO** (ticket 031, T2 — téléchargé le 2026-09-04, ODbL, 23 833 236 o, sha256 `d196b763…`,
309 lignes, 7 506 arrêts, validité **2026-08-01 → 2027-08-31** lue dans `calendar.txt`) porte
57 à 65 % des déplacements en transports collectifs des 2ᵉ et 3ᵉ couronnes. L'export brut est
archivé sous `data/gtfs/archives/2026-09-04_lio_source/exports_bruts/` et sert de source au feed
annuel.

> **Attention à la validité des exports.** Un feed présent dans `data/gtfs/` n'est pas un feed qui
> sert : l'export TER en place ne couvrait que 2026-04-29 → 2026-10-26 et ne servait **aucun train
> le 16 mars 2026**, la date simulée ; l'export liO ne commence qu'au 1ᵉʳ août 2026. C'est
> exactement ce que le [feed annuel](../arch/gtfs-annee.md) répare, et c'est pourquoi les deux
> réseaux régionaux sont servis par lui — vérifier la date simulée dans `calendar_dates.txt`
> avant de conclure qu'un réseau est chargé.

> **Un feed qui remplace un autre se DÉPLACE, il ne se juxtapose pas.** OTP charge tout feed du
> premier niveau de `data/gtfs/` : y laisser l'ancien export à côté du nouveau servirait deux
> calendriers pour un même réseau. Les exports remplacés vont sous
> `data/gtfs/archives/<date>_…/` — l'export TER du 2026-04-29 est sous
> `data/gtfs/archives/2026-09-04_pre_lio/ter_gtfs_export_2026-04-29/`, et l'ancien `graph.obj`
> (Tisséo + TER export, 4 056 arrêts) au même endroit, comme retour arrière.

> **Trois réseaux dans le graphe supposent trois réseaux montés dans les conteneurs.** `api`,
> `worker` et `controller` montent `./data/gtfs:/data/gtfs` — pas le seul `tisseo_gtfs`. La
> porte de proximité d'OTP (`_has_reachable_stop`, 1 500 m) énumère les feeds de ce répertoire :
> montée sur le seul Tisséo, elle refusait l'appel à OTP pour **397 des 2 580 points** de la
> population scellée v4, ceux qui n'ont à portée qu'un arrêt liO ou une gare TER.

Le notebook `scripts/data/gtfs/gtfs_merge.ipynb` permet de vérifier la cohérence des flux,
d'analyser les routes et arrêts communs, et de produire un GTFS consolidé si besoin.

### Préparer les données GTFS pour GAMA

Deux couches et un fichier de courses, **produits par une seule recette** :

```shell
make gama-trip-info          # les couches PUIS les courses
make gama-layers             # les couches seules
make test-gama-includes      # 19 tests, feeds synthétiques, < 2 s
```

> **Pourquoi une seule recette pour les deux.** `trip_info.json` porte, pour chaque course,
> des **indices de sommets dans la géométrie de `routes.shp`** (`shape_segments`), et
> `PublicTransport.gaml` retrouve le tracé d'un véhicule par
> `route first_with (each.shape_id = shape_id)`. Produire l'un sans l'autre, c'est le défaut
> qui a duré **cinq mois** : les couches sont passées aux trois réseaux le 2026-09-04 tandis
> que `trip_info.json`, écrit à la main le 27 mai depuis le seul Tisséo, ne portait **aucune
> course en `route_type=2`** — GAMA dessinait 34 lignes de TER et 68 gares où aucun train ne
> roulerait. `COUCHES=0` saute l'étape des couches quand elles viennent d'être faites.

**Les couches de lignes et d'arrêts** (`scripts/data/gama/export_gtfs_layers.py`, ticket 031,
G2) : `routes.shp` et `stops.shp` à partir des **trois** réseaux — **962 tracés, 5 375 arrêts**
(contre 395 et 3 822 pour Tisséo seul), les couches précédentes déplacées dans
`archives_<date>`. Trois choix à connaître :

- les couches sont **restreintes au périmètre** — liO couvre toute l'Occitanie, ses 2 553 tracés
  déborderaient dix fois le monde GAMA — mais les tracés retenus ne sont **jamais découpés** ;
- le feed TER ne publie **aucune géométrie** (son `shapes.txt` n'a qu'un en-tête, ses
  `trips.shape_id` sont vides) : ses tracés sont reconstruits depuis la suite des arrêts,
  marqués `trace=arrets`, à raison d'**un tracé par suite d'arrêts distincte** — 266 motifs de
  desserte pour 1 137 courses. Le module partagé
  [`scripts/data/gama/gtfs_traces.py`](../../scripts/data/gama/gtfs_traces.py) est l'endroit
  **unique** où ces `shape_id` sont fabriqués, pour que la couche et les courses ne puissent
  pas diverger ;
- les `shape_id` et `stop_id` ne sont jamais préfixés (ils servent de jointure avec les itinéraires
  d'OTP) ; une collision entre réseaux lève une `[ALARME]`.

> **Un tracé par (ligne, sens) fabriquait du mouvement.** Jusqu'au 2026-09-04, le TER recevait
> un tracé par couple (ligne, sens), celui de la course la plus desservie. Or `build_trips`
> force le dernier segment d'une course **jusqu'au dernier point du tracé** : une course
> Toulouse → Tarbes posée sur le tracé Toulouse → Pau roulerait jusqu'à Pau, dans le temps de
> parcours de Tarbes. Mesuré : **168 des 1 137 courses TER (14,8 %)** n'étaient même pas une
> sous-suite du tracé de leur couple, et **6 n'avaient aucun `direction_id`** — leur `shape_id`
> valait `NaN` et elles étaient absentes de la couche, sans un mot. Avec un tracé par desserte,
> les 1 137 courses sont placées et aucun segment n'est forcé.

Couverture mesurée du monde GAMA : l'enveloppe des lignes passe de 21 % à 100 %, **156 des
217 mailles de 5 km du périmètre portent un arrêt** (52 avant) et **571 des 785 zones fines de
l'enquête** (394 avant) — inchangé par le passage à 962 tracés, qui n'ajoute aucun arrêt.

**Les courses et le calendrier** (`scripts/data/gama/export_trip_info.py`) : `trip_info.json`,
à partir des mêmes trois feeds et de la **date simulée lue dans `Settings.gaml`**
(`starting_date`, pas recopiée dans la recette). Cinq contrôles **bloquants** — le fichier n'est
pas écrit s'ils tombent, et la recette sort en code 2 :

| Contrôle | Ce qu'il empêche |
|---|---|
| la date simulée est **dans** la fenêtre et **servie** par au moins un réseau | hors calendrier, `is_trip_available_today` se contente d'un `warn` et ne planifie plus **aucune** course : la simulation tourne, le réseau est vide, rien ne le dit |
| l'**étendue** des dates servies tient dans les 64 bits du masque de GAMA | `build_calendar_binary_map` construit un bit par jour de l'intervalle, pas par date servie |
| chaque course a son tracé dans `routes.shp`, **avec le même nombre de points** | un `shape_id` absent rend `route first_with (…)` nil ; un tracé plus court fait sortir les `shape_segments` de la liste des sommets |
| aucun `route_type` de la couche n'est **sans course** | le défaut des cinq mois |
| aucun `route_type` de la couche n'est sans course **le jour simulé** | porter des courses en juin ne fait pas rouler un train en mars |

Deux points délicats, documentés dans l'en-tête du script :

- **`service_id` est préfixé par réseau, et lui seul.** Les feeds annuels TER et liO numérotent
  leurs services `SVC_0001`… : **224 identifiants collisionnent**. Fusionnés tels quels, les
  cars liO liraient le calendrier des trains. Le préfixe est sans danger parce que `service_id`
  n'est une clé de jointure avec rien (GAMA ne le lit que dans `trip_calendar_map`).
- **La source Tisséo est l'export en service, pas le feed annuel.** Le feed annuel forke les
  géométries divergentes en `<shape_id>__<export>` : **329 de ses 705 `shape_id` sont absents
  de `routes.shp`**, et OTP sert l'export en service. Les trois feeds lus sont exactement ceux
  du `FEEDS_DEFAUT` des couches.

État mesuré le 2026-09-04 (`docs/traces/2026-09-04_10-30_trip_info_trois_reseaux/`) :

| | avant (27 mai) | après |
|---|---|---|
| courses | 39 343 | **41 302** |
| `route_type=2` (TER) | **0** | **884** (356 actives le 16/03) |
| `route_type=3` (bus + cars liO) | 32 205 | 33 280 |
| réseaux | Tisséo seul | Tisséo + TER + liO |
| taille | 28 315 173 o | 30 121 074 o |
| durée de génération | — | 57 s (46 s de `build_trips`) |

⚠ `export_trip_info.py` importe `llm-agents/inputs/gtfs/{reader,gama}.py`, donc
`llm-agents/settings.py`. **Depuis le 2026-09-04, cet import ne crée plus de répertoire de run
et ne déplace plus `experiments/current`** — cela appartient à `claim_run()`, que seul le
processus propriétaire appelle. La réserve du ticket 031 (question ouverte n° 12) est donc
levée : la recette peut tourner pendant un run.

### Le monde GAMA : le périmètre des 453 communes (ticket 031, G1)

```shell
llm-agents/.venv/bin/python scripts/data/gama/export_perimetre_shapefile.py
```

écrit `GAMA/CityTransport/includes/perimetre_453.shp` (polygone dissous des quatre couronnes,
EPSG:4326 comme `routes.shp`). `Settings.gaml` en fait l'emprise du monde —
`geometry shape <- envelope(perimetre_shape_file)`, **86 × 93 km** (mesuré en Lambert-93 sur le
polygone dissous : 85,8 × 92,9 km, 5 428 km² de communes dans une enveloppe de 7 971 km² ; GAMA
annonce 87 × 94 km dans sa propre projection) — à la place de l'enveloppe des lignes Tisséo. Ce que
cette dernière laissait dehors, mesuré sur la population scellée v4 : **201 des 1 000 domiciles**
(le rapport de périmètre citait 163, mesurés sur la v3, moins riche en 3ᵉ couronne) ; sur le monde
actuel, **0 / 1 000**. Le rapport de périmètre annonçait « 106 × 93 km » :
c'est un degré de longitude compté à 111 km sans le cosinus de la latitude (à 43,5°, un degré de
longitude vaut 80,8 km) — la hauteur était juste, la largeur surestimée de 23 %. Au chargement, GAMA écrit la part
du monde couverte par les lignes TC (`[PERIMETRE] … les lignes TC n'en couvrent que N %`) et, à la
création des habitants, le nombre d'agents hors du monde (`[PERIMETRE] 1000 habitants créés, 0 hors
du monde GAMA` ; `[ALARME]` sinon). Le dossier `includes/` n'est pas versionné : ce script est la
recette, à rejouer après tout changement de `couronne_perimetre.geojson`.

**`roads.shp` / `nodes.shp` (G4)** : leur `.prj` déclare `WGS 84 / UTM zone 48N` (EPSG:32648, la
projection par défaut de GAMA) alors que Toulouse est en zone 31N — et leurs coordonnées
(x ≈ −4 025 000, y ≈ 12 208 000) ne sont celles d'aucune des deux : ce sont les coordonnées
internes de GAMA, sauvegardées telles quelles par `OSMLoadDriving.gaml` (`save road to:
"../includes/roads.shp"`). Ces fichiers ne sont lus par aucun modèle (`City.gaml` ne charge que
`perimetre_453.shp`, `routes.shp`, `stops.shp`, `trip_info.json`) ; ils ne sont pas géoréférencés et
ne se « corrigent » pas en changeant le `.prj`. À régénérer avec une projection explicite si la voirie
GAMA devait servir un jour ; laissés en place, documentés ici (2026-09-03).

---

## 2. OpenTripPlanner (OTP)

OTP est le moteur de calcul d'itinéraires multi-modal (transit + marche/vélo/voiture).

### Installation

1. Télécharger le binaire OTP depuis le [guide officiel](https://docs.opentripplanner.org/en/v2.7.0/Getting-OTP/) et le placer dans `otp-toulouse/bin/`.

2. L'extrait OSM `data/gtfs/Toulouse.osm.pbf` est, **depuis le 2026-09-03 (ticket 031, T1)**,
   l'extrait du **polygone exact des 453 communes** de l'enquête EMC² 2023 — produit sans
   téléchargement par `scripts/data/population/build_osmnx_perimeter_graph.py` (`osmium extract
   --polygon` sur les pbf régionaux du fork eqasim, millésime OSM 2022-01-01, 76 Mo, md5
   `62d45fe5…`), copié depuis `data/cache/osmnx/perimetre_453/perimetre_453.osm.pbf`. Il remplace un
   extrait bbbike de 2026 limité au rectangle de 30 km (`TOULOUSE_OSM_ROUTES_30K_BBOX`), hors duquel
   OTP ne pouvait pas rattacher les domiciles de 3ᵉ couronne ni trois gares TER (« Couldn't link ») ;
   l'ancien extrait et son `graph.obj` sont archivés dans `data/gtfs/archives/2026-09-03_pre_perimetre_453/`,
   la provenance est consignée dans `otp-toulouse/toulouse/Toulouse.osm.pbf.dvc` (écrit à la main,
   `dvc` n'étant pas installé) et `README_Toulouse.osm.pbf.md`. Limite : la voirie passe de 2026 à
   2022 ; un extrait 2026 du même polygone demande un téléchargement régional (~270 Mo), non fait sans
   accord. Un autre extrait se pose au même endroit (`Toulouse.osm.pbf`), puis le graphe se reconstruit.

3. Placer les dossiers GTFS (`tisseo_gtfs/`, `ter_gtfs/`, `lio_gtfs/` — les trois en service
   depuis le 2026-09-04) dans `data/gtfs/`. `data/gtfs/build-config.json` fixe la fenêtre de
   service `[2026-01-01, 2027-12-31]` (T5), alignée sur les feeds annuels et la date simulée.
   `router-config.json` n'est **pas** dans ce répertoire : les instances tournent sur la
   configuration de routage par défaut d'OTP, ce qui est une limite connue.

### Construction et démarrage (hors Docker)

```shell
# Construire le graphe de transport (résultat : data/gtfs/graph.obj)
make otp-graph

> **Pourquoi une recette et pas la commande nue.** `data/gtfs/` est un répertoire de **travail**,
> non versionné ; les configurations d'OTP, elles, sont versionnées dans
> `otp-toulouse/toulouse/` (`build-config.json`, `router-config.json`, `otp-config.json`).
> `make otp-graph` les y recopie avant de construire, puis archive l'ancien graphe. Le
> 2026-09-04, une reconstruction faite à la main avec un `build-config.json` minimal écrit
> directement dans `data/gtfs/` a **perdu en silence** quatre réglages — `embedRouterConfig`,
> `boardingLocationTags`, `staticParkAndRide`, `maxStopToShapeSnapDistance` — et les trois
> instances ont tourné une nuit sur les valeurs par défaut d'OTP, sans une ligne de journal
> pour le dire. Le graphe reconstruit avec les réglages retrouvés compte **9 716
> correspondances contraintes** là où le précédent n'en avait aucune.
>
> ⚠ Le contrôle de desserte (`scripts/data/gtfs/otp_link_check.py`) ne voit **pas** cette
> différence : il mesure si un itinéraire existe, pas lequel est choisi. Mesuré avant et après
> la correction : 314 points sans itinéraire des deux côtés, sur 2 580. Les correspondances
> contraintes et le temps de battement changent l'itinéraire retenu, non son existence.

# Démarrer le serveur OTP
java -Xmx4G -jar otp-toulouse/bin/otp-shaded-2.8.1.jar --load data/gtfs
```

Mesuré le 2026-09-03 sur l'extrait du polygone (JDK 25, `-Xmx4G`) : **46 s de construction, 2,0 Go
de RSS de pointe, `graph.obj` de 66 Mo** (contre 77 Mo pour le rectangle de 2026 : la voirie 2022
est moins détaillée), 4 056 arrêts dont 3 757 rattachés à la voirie — les 167 « isolés » sont les
arrêts TER hors du polygone (234 arrêts TER, 68 dedans). Puis `docker compose restart otp1 otp2 otp3`
(≈ 20 s jusqu'au healthcheck, 1,2 à 1,4 Go par instance chargée). Contrôle de rattachement d'une
population : `scripts/data/gtfs/otp_link_check.py --population <fichier>` compte les
`routingErrors` OTP (`LOCATION_NOT_FOUND` = « Couldn't link ») pour chaque domicile et lieu
d'activité, **ventilés par couronne de résidence** (`--sans-couronnes` pour ne pas ventiler).

**Le graphe en service depuis le 2026-09-04 porte les trois réseaux**, mesuré dans les mêmes
conditions (JDK 25, `-Xmx4G`) : **55,3 s de construction, 2,09 Go de RSS de pointe, `graph.obj`
de 84 438 867 o** (sha256 `f2820c59…`), 268 076 sommets, 666 759 arêtes, **11 507 arrêts,
3 146 patterns et 9 716 correspondances contraintes** (contre 4 056 arrêts et 588 patterns avec
Tisséo + TER seuls). Une instance qui le sert tient dans 1,0 Go au chargement et 2,2 à 2,6 Go
après 2 580 requêtes : `mem_limit: 6g` et `-Xmx4G` gardent de la marge, et les trois
*healthchecks* passent en une vingtaine de secondes.

Sur la population scellée v4 (2 580 points, lundi 16 mars 2026 8 h, destination le Capitole),
les points sans itinéraire TC passent de **670 à 314** — 3ᵉ couronne **369 → 148**, 2ᵉ couronne
**160 → 26**, 1ʳᵉ 9 → 8, Toulouse inchangé à 132 (tous `walkingBetterThanTransit`, la marche bat
le TC) — avec toujours **zéro échec de rattachement**. Sur les six itinéraires que le runtime
demande par trajet, **1 883 des 11 288 rendus proposent un train** :
`otp_link_check.py --num-trip-patterns 6` reproduit cette condition, et son champ
`itineraires_avec_train` la chiffre.

Ce passage de 339 à 314 vient de la **coupe de la queue tronquée de liO** : l'export cessait de
décrire treize lignes `.liO 31` au changement de service du 13/12/2026, dont dix rabattements sur
gare du périmètre. Voir [`gtfs-annee.md`](../arch/gtfs-annee.md) et
`docs/traces/2026-09-04_07-17_ticket031_lio_queue_rail/`.

### Configuration dans le controller

```yaml
# llm-agents/config/config.yaml
gtfs:
  mode: OTP
  otp_endpoint: http://localhost:8080/otp/transmodel/v3
  otp_max_concurrent: 30
```

### Déploiement Docker

En Docker, **trois instances OTP** (`otp1`, `otp2`, `otp3`) tournent en parallèle sur les ports `8080`, `8081` et `8082`. Le controller les consomme via :

```
OTP_ENDPOINTS=http://otp1:8080/otp/transmodel/v3,http://otp2:8080/otp/transmodel/v3,http://otp3:8080/otp/transmodel/v3
```

Chaque instance charge le même `graph.obj` (volume partagé en lecture seule) et absorbe une partie du trafic de requêtes.

---

## 3. OSMnx — routage pédestre / vélo / voiture

OSMnx calcule les itinéraires directs (sans transport en commun) : marche, vélo, voiture.

### Fonctionnement

Les graphes OSMnx sont téléchargés depuis OpenStreetMap au premier démarrage puis mis en cache dans `data/cache/osmnx/` (persistant entre les redémarrages ; le cache de *routes*, distinct, vit dans `data/cache/osmnx/<population>/osmnx_cache.db`). Le calcul Dijkstra est délégué à des workers de processus dédiés par mode pour contourner le GIL Python.

### Déploiement Docker

En Docker, OSMnx tourne dans un microservice dédié (`osmnx1`, port `8090`). Des replicas supplémentaires (`osmnx2`, `osmnx3`) peuvent être activés dans `docker-compose.yml` si la charge le nécessite.

Le controller les contacte via :

```
OSMNX_ENDPOINTS=http://osmnx1:8090/route
# Plusieurs replicas séparés par des virgules, distribués en round-robin
```

### Configuration dans le controller

```yaml
gtfs:
  osmnx_cache_dir: /app/osmnx_cache
```

### Références

- GTFS : https://gtfs.org/resources/gtfs/
- GTFS Tisséo : https://data.toulouse-metropole.fr/explore/dataset/tisseo-gtfs/information/
- GTFS TER SNCF : https://www.data.gouv.fr/fr/datasets/horaires-des-lignes-ter-sncf/
- OpenTripPlanner : https://www.opentripplanner.org/
