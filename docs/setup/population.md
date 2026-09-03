# Population synthétique — EQUASIM

Le module EQUASIM génère une population synthétique réaliste (activités, localisation, démographie) à partir des données publiques françaises (INSEE, OSM, GTFS, BAN, BDTOPO).

Le guide officiel de configuration pour Toulouse est disponible ici :
**https://github.com/eqasim-org/eqasim-france/blob/main/docs/cases/toulouse.md**

Pour savoir d'où vient chaque attribut d'un agent (algo eqasim amont, fork, export JSON,
notebook, correctifs de surface) : [../arch/population-post-traitements.md](../arch/population-post-traitements.md).

---

## Mise en place du dépôt eqasim-toulouse

Le dossier `eqasim-toulouse/` n'est **pas inclus** dans ce dépôt git. Il utilise un fork personnalisé hébergé sur `https://github.com/Ytlse/eqasim-llm-toulouse`.

```shell
git clone https://github.com/Ytlse/eqasim-llm-toulouse eqasim-toulouse
```

L'upstream est configuré pour recevoir les mises à jour de l'eqasim officiel :

```shell
cd eqasim-toulouse
git remote add upstream https://github.com/eqasim-org/eqasim-france.git
```

### Personnalisations du fork (vs upstream)

**Nouveaux fichiers :**

| Fichier | Rôle |
|---------|------|
| `generate_population.py` | Wrapper Docker : lit la taille depuis `APP_CONFIG_PATH` ou env, calcule le `sampling_rate`, gère le cache par taille exacte (une régénération forcée **remplace** le fichier cible : avant le 2026-09-03 il restait en place et l'ancien vivier était rendu), part de `config_toulouse.yml` pour les réglages scientifiques, **vérifie avant synpp** que chaque département demandé a sa BD TOPO et sa BAN (code 3 avec la liste de ce qui manque, aucun département « sauté »), cadre de tirage = liste des communes du périmètre |
| `synthesis/population/llm_agents.py` (suite) | `household.commune_id` / `iris_id` renseignés pour **tous** les ménages depuis le tirage de zone du domicile (`spatial.home.zones`) — la colonne du recensement vaut « undefined » pour 36 % des personnes (IRIS anonymisés) ; « undefined » compte comme valeur manquante |
| `server.py` | Service HTTP minimal sur le port 8003 (`GET /health`, `POST /generate`), sérialise les requêtes concurrentes (synpp n'est pas réentrant) |
| `synthesis/population/llm_agents.py` | Stage synpp custom : export JSON pour GAMA — noms Faker, traits Big Five optionnels, intégration polygone OTP2 (snap des activités hors-graphe), fusion des activités consécutives identiques, garantie domicile en début/fin de journée |

**Modifications upstream :**

- `config_toulouse.yml` — **source unique des réglages scientifiques** : six départements du périmètre (`["31", "32", "81", "82", "09", "11"]`) et liste des 453 communes (`communes_file`, ticket 031), appariement HTS national (`filter_hts: false`, `matching_attributes` avec `age_class` en tête, `matching_minimum_observations: 5`, ticket 008), journées donneuses = jours de classe (`hts_school_days_only`, `hts_exclude_wednesday_under_age`), `sampling_rate` 0,01, stage `synthesis.population.llm_agents` dans `run`. Depuis le 2026-09-03 le service Docker **part de ce fichier** (monté dans le conteneur) et ne remplace que les chemins et paramètres d'exécution : avant, il construisait sa propre config sans ces clés et synpp retombait sur ses défauts — `filter_hts: True`, soit **308 donneurs ENTD** résidents de Haute-Garonne pour 12 000 personnes, et une dégradation qui abandonnait la classe d'âge. Toutes les populations générées par le service jusqu'à la v3 incluse portent des chaînes issues de ce vivier réduit
- `data/spatial/codes.py` — cadre de tirage par **liste de communes** (`communes` ou `communes_file`), journalisé par département (346 / 38 / 27 / 22 / 10 / 10 attendus) ; une commune demandée absente du référentiel IRIS fait échouer le stage au lieu de sortir du cadre en silence
- `data/hts/entd/cleaned.py` — journées donneuses = jours de classe ; un donneur dont la journée de référence est écartée **sort du vivier** (il ne devient pas un immobile : mesuré le 2026-09-03, la première version du filtre portait les immobiles à 40,6 % de la population contre 10,6 % dans l'enquête)
- `synthesis/population/enriched.py` — colonnes `socioprofessional_class_detail` et `employment_sector` ajoutées au jeu de sortie
- `synthesis/output.py` — colonnes supplémentaires (`household_size`, `consumption_units`, `age_range`) ; filtre sur les géométries valides dans la sortie spatiale pour éviter les `LineString` nulles
- `Dockerfile` — les données sont montées via volume `/eqasim-data` au runtime (non copiées dans l'image) ; suppression du répertoire `documentation/`

**Données supplémentaires requises** (non présentes dans l'upstream) :

| Données | Sous-dossier | Utilisation |
|---------|--------------|-------------|
| IRIS 2024 (contours communes) | `iris_2024/` | Filtrage bbox → communes via intersection spatiale Lambert-93 |
| Recensement INSEE 2022 | `rp_2022/` | Population effective par commune pour le calcul du `sampling_rate` bbox |

---

## Données d'entrée requises

Télécharger et placer les données dans `eqasim-toulouse/data/` (voir le [guide officiel](https://github.com/eqasim-org/eqasim-france/blob/main/docs/cases/toulouse.md)) :

| Données | Sous-dossier | Utilisation |
|---------|--------------|-------------|
| FILOSOFI (revenus INSEE) | `filosofi_2019/` | Distribution des revenus par ménage → profil socio-économique des agents |
| Recensement INSEE | `rp_2019/` | Structure démographique (âge, CSP, composition du ménage) → tirage des agents |
| ENTD (enquête nationale déplacements) | `entd_2008/` | Comportements de mobilité (motifs, fréquences, modes) → génération des chaînes d'activités. **Journées donneuses = jours de classe** depuis le 2026-09-03 : hors vacances scolaires (`V2_VAC_SCOL`) et hors mercredi pour les moins de 11 ans (`V2_JOUR_DEP`), réglages `hts_school_days_only` / `hts_exclude_wednesday_under_age` du fork ; sans ce filtre, 50 à 54 % des 6-17 ans générés avaient une activité d'études un jour de semaine (EMC² : 90 à 95 %) ; le stage imprime la part des scolaires mobiles avec trajet vers l'école (72,0 % → 90,8 % sur les donneurs) et alarme sous 85 % |
| BD TOPO | `bdtopo_toulouse/` | Localisation précise des bâtiments et adresses → affectation domicile/travail |
| OSM Toulouse | `osm_toulouse/` | Réseau routier et piéton, POI → calcul des itinéraires OSMnx |
| GTFS Tisséo | `gtfs_toulouse/` | Réseau TC (arrêts, lignes, horaires) → enrichissement du flag `public_transport` et calcul d'accessibilité TC |
| BAN (adresses) | `ban_toulouse/` | Géocodage des adresses → coordonnées WGS84 des activités |
| Recensement INSEE 2022 | `rp_2022/` | Population effective par commune (pour le calcul du `sampling_rate` en mode bbox) |
| IRIS 2024 (contours communes) | `iris_2024/` | Filtrage bbox → communes via intersection spatiale Lambert-93 |

---

## Service Docker

En mode Docker, `eqasim` démarre comme un **service HTTP persistant** sur le port `8003`. Il expose un endpoint `/health` et un endpoint de récupération de la population. Le controller attend sa disponibilité via `service_healthy` avant de s'initialiser.

```
EQASIM_SERVICE_URL: http://eqasim:8003
```

Variables d'environnement disponibles :

| Variable | Défaut | Description |
|----------|--------|-------------|
| `EQASIM_POPULATION_SIZE` | lu depuis `APP_CONFIG_PATH` | Nombre d'agents cibles |
| `EQASIM_GENERATE_PERSONALITY` | `false` | Générer les scores Big Five (OCEAN) |
| `EQASIM_RANDOM_SEED` | `1234` | Graine de reproductibilité |
| `EQASIM_PROCESSES` | `2` | Nombre de processus parallèles de génération |

```shell
# Surcharger la taille de population au lancement Docker
EQASIM_POPULATION_SIZE=5000 docker compose up

# Forcer la regénération
EQASIM_FORCE_REGENERATE=true docker compose up
```

---

## Configuration eqasim (`config_toulouse.yml`)

```yaml
config:
  departments: ["31", "32", "81", "82", "09", "11"]   # les six départements du périmètre EMC² (ticket 031)
  communes_file: <dépôt>/llm_module/data/commune_couronne.json   # les 453 communes ; croisé avec departments
  filter_hts: false                     # appariement sur l'ENTD nationale (ticket 008)
  matching_attributes: [age_class, sex, any_cars, socioprofessional_class, departement_id]
  matching_minimum_observations: 5
  hts_school_days_only: true            # journées donneuses = jours de classe (ticket 031 § 1.2)
  hts_exclude_wednesday_under_age: 11
  sampling_rate: 0.01          # 1 % ≈ 5 000 agents
  random_seed: 1234
  data_path: /path/to/data
  output_path: /path/to/output
  output_prefix: toulouse_

  gtfs_path: gtfs_toulouse
  osm_path: osm_toulouse
  ban_path: ban_toulouse
  bdtopo_path: bdtopo_toulouse
```

Le service Docker lit ce fichier (monté en `/eqasim/config_toulouse.yml`) et ne remplace que
`sampling_rate`, `random_seed`, les chemins, `processes`, `departments`/`communes` (la liste est
passée en clair) et `generate_personality_traits`. Il **refuse** de générer si le fichier manque
ou ne fixe pas les réglages d'appariement (code 5), et si un département demandé n'a pas ses
données (code 3). Le journal de chaque génération imprime les réglages scientifiques retenus.

---

## Cadre de tirage : le périmètre d'enquête, pas un rectangle (ticket 026)

Depuis le ticket 026, eqasim tire dans une **liste de communes** — celles du périmètre EMC²
2023 — et non dans un rectangle ni dans un département entier. Le `sampling_rate` est
recalculé sur la population RP 2022 de ces communes.

| Réglage | Où | Défaut |
|---|---|---|
| `EQASIM_PERIMETER` | `docker-compose.yml` (service eqasim) | `true` |
| `EQASIM_DEPARTMENTS` | idem | `31` |
| `PERIMETER`, `DEPARTMENTS` | cellule « Paramètres » du notebook | `True`, `['31']` |
| `perimeter`, `departments` | corps JSON de `POST /generate` | — |

`perimeter` **prime sur `bbox`** : un rectangle ne peut pas exprimer « le périmètre, ni plus
ni moins ». Et le cadre **échoue** s'il est vide ou ne recoupe pas les départements servis —
sans ce garde-fou, une faute de frappe ferait peupler tout le département en silence.

**Le périmètre d'étude est celui des 453 communes sur six départements** (ticket 031, option A,
rapport `docs/paper/population/RAPPORT_PERIMETRE_453_COMMUNES.html`). Depuis le 2026-09-03 les
données des six départements sont dans `eqasim-toulouse/data/` — BD TOPO 3-4 TOUSTHEMES SHP LAMB93
**édition 2025-03-15** pour les six (la 2024-09-15 n'est plus servie par l'IGN ; la Haute-Garonne a
été reprise dans la même édition, l'ancienne livraison est rangée dans `data/bdtopo_archive_2024-09-15/`,
hors du chemin lu par eqasim), BAN `adresses-<dep>.csv.gz` du 2026-09-03 — et le service part
des six départements par défaut (`EQASIM_DEPARTMENTS=31,32,81,82,09,11`, `DEPARTMENTS = None` ou
la liste explicite dans le notebook). Il journalise le cadre par département (346 / 38 / 27 / 22 /
10 / 10) et refuse de générer si un département demandé n'a pas ses données.

**Les communes sans IRIS sont pondérées.** Le recensement ne nomme pas la commune des personnes qui
vivent dans une commune sans IRIS (il ne donne que le département) ; eqasim les garde et leur tire
ensuite une commune sans IRIS **du cadre**. Avec une liste de communes, cela versait la population
rurale de tout le département dans quelques villages — mesuré le 2026-09-03 : 17 986 personnes
pour 10 000 demandées, 42,5 % en 3ᵉ couronne, 1 682 personas pour les dix villages audois du cadre.
Le fork multiplie désormais leur poids RP par la part de la population sans IRIS du département qui
vit dans le cadre (31 : 86,7 %, 32 : 9,4 %, 81 : 9,0 %, 82 : 20,1 %, 09 : 4,0 %, 11 : 1,0 %), et le
journal de génération l'imprime (`Commune frame: … reweighted …`). Réglage `census_undefined_reweighting`
de `config_toulouse.yml` (défaut `true`) : il entre dans l'empreinte synpp du stage — un changement
de code seul ne devalide pas un cache synpp, une valeur de configuration si.

`DEPARTMENTS = ['31']` reste possible : c'est la **répétition** sur les 346 communes
haut-garonnaises, où la 3ᵉ couronne plafonne à **10,6 %** de la population quand l'enquête en
compte **15,4 %** (100 de ses 275 communes sont hors du 31). Une population tirée sur ce cadre ne
se scelle pas en v4. Voir [`../arch/perimetre-population.md`](../arch/perimetre-population.md),
limite n°6.

**Trois réglages du fork décidés le 2026-09-03** (ticket 031) : les journées donneuses ENTD sont
des jours de classe (`hts_school_days_only`, mercredi exclu pour les moins de 11 ans) et un donneur
dont la journée est écartée sort du vivier ; la classe d'âge de l'appariement a une **borne à
17 ans** (`matching_age_boundaries: [14, 17, 29, 44, 59, 74, 1000]`) pour que les lycéens n'héritent
plus des chaînes des 18-29 ans ; une **activité hors du polygone des 453 communes est supprimée**
de la chaîne à l'étape 2 du notebook (jamais le domicile), comptée, alarmée si > 0 et déclarée
dans le MANIFEST du sceau.

### Régénérer une population avec ce cadre

1. **Les services** — `docker compose up -d eqasim otp1` (le notebook vérifie la santé
   d'eqasim en cellule 8).
2. **Le notebook** — `scripts/data/population/generate_population.ipynb`, cellule
   « Paramètres » : `PERIMETER = True`, `DEPARTMENTS = ['31']`, et **`FORCE_REGENERATE =
   True`** — sans quoi eqasim rendra le fichier en cache, qui a l'ancien cadre. Puis exécuter
   tout le notebook : étape 1 (génération), étapes 2 à 5 (journée, TC, routage, recalage),
   étape 8 (traits imputés, dont `residence_zone`) et étape 9 (verdict de complétude).
3. **Le contrôle** — `make residence-zone CHECK=1` doit passer du code `4` au code `0`.
   ⚠ Un `0` ne vaut pas conformité : l'écart de la 3ᵉ couronne y vaut 4,8 points pour une
   tolérance de 5,0. Lire aussi `make audit-perimetre` (axe A9).
4. **Le run** — les services LLM lisent `data/population/` directement ; il n'y a rien à
   rebâtir. Le filtre d'admission au chargement porte désormais sur le **périmètre** (trait
   `residence_zone`) et non plus sur le rectangle des arrêts : une population enrichie garde
   ses agents de 3ᵉ couronne. Une population **non** enrichie déclenche une alarme
   `[ALARME] … sans trait residence_zone` et retombe sur l'ancien filtre.

## Filtrage de la population par périmètre (453 communes)

Depuis le 2026-09-03 (ticket 031, partie 2), le chargement (`handle/application.py` →
`inputs/population/perimeter.py`) filtre par **commune du domicile** : `household.commune_id` doit
être l'une des 453 communes de l'enquête EMC² 2023 (`llm_module/data/commune_couronne.json`). Sans
commune, le trait `residence_zone` décide ; sans l'un ni l'autre, la géométrie du polygone des
couronnes (`couronne_perimetre.geojson`) tranche et une `[ALARME]` dit que la commune n'a pas été
vérifiée. Ce que cela change :

- **une activité hors du polygone n'écarte pas l'agent** (école ou travail hors périmètre) : elle est
  comptée dans le journal et une `[ALARME]` se lève au-delà de 1 % des activités localisées ;
- **un fichier scellé se charge entier ou se refuse** : si l'effectif après filtre n'est pas
  `population_size`, `[ALARME]` et rien n'est chargé — un sceau ne se rogne pas ;
- le **monde** (`WorldGrid`) couvre l'enveloppe du polygone unie à celle des arrêts GTFS ± 0,05°.

Avant : un rectangle de 30 km (`TOULOUSE_OSM_ROUTES_30K_BBOX`) écartait tout agent dont le domicile
**ou une seule activité** sortait — 77 des 1 000 agents de la v4 (60 domiciles, dont 55 de 3ᵉ
couronne ; 105 activités), donc un sceau refusé. Mesuré au premier chargement de la v4 : **1 000 /
1 000 admis par commune, 0 écarté, 0 activité hors polygone** (trace
`docs/traces/2026-09-03_22-46_ticket031_partie2_portage_chaine/`). La constante reste dans
`geography.py` pour l'audit.

Pour analyser la distribution spatiale d'une population :

```shell
python scripts/data/gtfs/analyze_mobility_bbox.py \
  --population data/eqasim_output/toulouse_population_5194.json \
  --percentile 95 \
  --output scripts/bbox_analysis.png
```

---

## Générer la population (notebook)

Le pipeline complet de génération est orchestré par le notebook [`scripts/data/population/generate_population.ipynb`](../../scripts/data/population/generate_population.ipynb).

Il enchaîne 5 étapes avec checkpoints intermédiaires dans `scripts/data/population/Temp/` :

| Étape | Entrée | Sortie | Description |
|-------|--------|--------|-------------|
| 1 – Génération eqasim | API eqasim (port 8003) | `Temp/1_raw/` | Appel HTTP POST `/generate` — synthèse des agents à partir des données INSEE/ENTD |
| 2 – Validation activités | `Temp/1_raw/` | `Temp/2_fixed/` | Correction des chevauchements temporels, fusion des activités redondantes |
| 3 – Enrichissement TC | `Temp/2_fixed/` | `Temp/3_pt_enriched/` | Calcul du flag `public_transport` (arrêt Tisséo dans un rayon de 1 500 m) |
| 3bis – Enrichissement zone | `Temp/3_pt_enriched/` | `Temp/4_zone_enriched/` | Libellé de zone de chaque localisation (grille de densité INSEE + aire d'attraction), géocodage inverse BAN mis en cache |
| 3ter – Sélection stratifiée (AAMAS) | `Temp/4_zone_enriched/` | `Temp/4_zone_enriched/toulouse_population_<N>_AAMAS.json` | **Optionnelle** (`SELECT_N`). D'abord **3ter-a** : les post-traitements de l'étape 8 tournent sur le vivier (logement, vélo, permis, abonnement), pour que ces traits soient des marges de sélection. Puis `scripts/AAMAS/seal_population.py select` (règle `aamas_seal_v4`, ticket 031) retient `SELECT_N` personas pile **par ménages entiers** : allocation aux 12 cellules couronne × motorisation de l'enquête, puis descente par échanges de ménages de même taille et même cellule qui rapproche les six classes d'âge du rapport, l'âge quinquennal, le genre, l'occupation, la taille de ménage, le permis, l'abonnement TC, le logement et la part d'immobiles de leurs cibles ; exclut les domiciles hors des 453 communes et journalise les départements de résidence des retenus. Placée **avant** le routage : les étapes 4 à 9 ne tournent que sur les retenus. Vivier conseillé : `POPULATION_SIZES = [5000]` (99,2 % de chances de remplir les 12 cellules ; 2 700 → 63 %). Détail : [docs/arch/controle-population-jeu-de-test.md](../arch/controle-population-jeu-de-test.md) |
| 4 – Calcul d'itinéraires | `Temp/4_zone_enriched/` | `Temp/5_scheduled/` | Routes OSMnx parallélisées (`MAX_WORKERS`, 6 par défaut) sur les **graphes du polygone des 453 communes** (`make osmnx-perimeter-graph`, clé `PERIMETER_CACHE_KEY` — le notebook refuse de tourner sans eux), et non sur le disque de 30 km de la production : un domicile de 3ᵉ couronne a ses propres nœuds de graphe (ticket 031 § 1.4) |
| 5 – Ajustement horaires | `Temp/4_routed/` | `Temp/5_scheduled/` | Recalage des `scheduled_start_time` pour absorber les temps de trajet réels |
| 6 – Réchauffage OSMnx (**optionnel**) | `Temp/5_scheduled/` | `data/cache/osmnx/<population>/osmnx_cache.db` | Pré-calcule le cache d'itinéraires du runtime (marche + vélo + voiture × 24 h : ≈ 78 000 routes pour 1 000 personas). Ne touche pas à la population. `SKIP_WARMUP = True` la saute — le runtime calcule les itinéraires manquants à la demande. `MAX_WORKERS` (défaut 12) : chaque worker charge sa copie des graphes ; à 12 la machine de développement swappe (23 Go mesurés), à 6 elle tient en RAM. Se relance seule avec `SKIP_WARMUP = False`, les autres étapes étant sautées |
| 7 – Export final | `Temp/5_scheduled/` | `data/population/` | Copie vers le dossier consommé par GAMA et le serveur d'agents (monté dans les conteneurs sous `/eqasim-output`). **Refuse** d'écraser si la source n'a aucune activité planifiée ou perd la moitié des agents ; laisse un `.bak` |
| 8 – Traits EMC² | `data/population/` | `data/population/` | `fix_minor_traits`, puis `enrich_housing_type`, puis `enrich_personal_bike` — dans cet ordre. Chacun **refuse de tourner** si sa ressource d'accès restreint manque, au lieu d'imputer à l'aveugle. La pente de l'équipement vélo par taille de ménage se juge sur le **vivier** (≥ 100 foyers par taille) ; sur une cohorte de 1 000 elle s'affiche « non concluant » sans peser sur le verdict. `--rapport-json <fichier>` écrit le même rapport en JSON (contrôles, pente, verdicts, code de sortie) : c'est ce que lit la synthèse de représentativité (`--velo`, `--velo-vivier`) |
| 9 – Audit | `data/population/` | (rapport) | Verdict **POPULATION COMPLÈTE / INCOMPLÈTE** : présence des neuf traits que la simulation consomme, et des horaires recalés |

Chaque étape est idempotente : si le fichier de sortie existe déjà dans `Temp/`, elle est ignorée. Pour forcer la reprise à partir d'une étape, définir `FORCE_STEP = 'raw' | 'fixed' | 'pt_enriched' | 'routed' | 'scheduled'` dans la première cellule.

### Le graphe de routage du polygone des 453 communes

Les étapes 4+5 recalent les horaires avec des temps de trajet OSMnx. Le graphe de la production
est un disque de 30 km autour de Toulouse (`ox.graph_from_address`, clé `ecb40f20a303`) : 98 des
154 agents de 3ᵉ couronne de la v3 habitent dehors, leurs trajets tombent sur un même nœud et
reçoivent une vitesse de repli. Le notebook route désormais sur les graphes du **polygone des
453 communes** (5 428 km²), construits sans téléchargement depuis les pbf OSM régionaux du fork
eqasim :

```shell
make osmnx-perimeter-graph TRACE=docs/traces/$(date +%Y-%m-%d_%H-%M)_graphe_osmnx_perimetre_453
```

`scripts/data/population/build_osmnx_perimeter_graph.py` : `osmium extract --polygon` sur les
deux pbf, fusion, voies `highway` en XML, puis un graphe par mode avec **les filtres réseau
d'OSMnx lui-même** (lus dans la version installée) et **les vitesses de la production**
(`config/osmnx.yaml`). Cache `data/cache/osmnx/graphs_444ca7e6a515.pkl` (label
`perimetre_453_communes:cc1:osm-220101` ; 223 Mo ; marche 176 k nœuds / 473 k arêtes, vélo
152 k / 361 k, voiture 65 k / 149 k ; 10 min de construction, 2,7 Go de pointe), frontière
`_in_city` = commune de Toulouse copiée du cache de production. Les mesures O2/O4 du rapport de
périmètre (paires « même nœud » par couronne, ms par route, RAM d'un worker) se rejouent avec
`scripts/data/population/measure_osmnx_perimeter_graph.py`. **Depuis le 2026-09-03 au soir, le
runtime (`osmnx_server.py`, `osmnx_direct.py`) sert ce même graphe** — clé `geography.PERIMETER_CACHE_KEY`,
configurable par `gtfs.osmnx_graph_key` ; le disque de 30 km ne sert plus qu'à l'audit
(`PRODUCTION_CACHE_KEY_30KM`). Les vitesses vélo manquantes (`track`, `service`, `trunk`, `*_link`… :
32 % des arêtes en repli 14 km/h) sont posées dans `config/osmnx.yaml` avec leur source et
reposées sur le pickle (`build_osmnx_perimeter_graph.py --respeed` : 24 627 arêtes vélo modifiées,
2 en repli) ; `routing_version` passe à `r2`.

### Population scellée pour l'article (AAMAS)

Pour un jeu de test à effectif rond et représentatif, la chaîne se joue en trois temps
(détail : [docs/arch/controle-population-jeu-de-test.md](../arch/controle-population-jeu-de-test.md)) :

1. **Notebook** avec `POPULATION_SIZES = [10000]` et `SELECT_N = 1000` : les étapes 1 à 3bis
   tournent sur le vivier (≈ 11 900 personnes, immobiles compris, 4 à 10 min d'eqasim), l'étape 3ter
   pré-impute le vivier puis retient 1 000 personas **par ménages entiers** (règle v4 : allocation
   couronne × motorisation, descente sur neuf marges dont les six classes d'âge, journal du
   périmètre), les étapes 4 à 9 ne tournent que sur eux
   et exportent `data/population/toulouse_population_1000_AAMAS.json` — le fichier
   `toulouse_population_1000.json` n'est pas touché.
2. **Contrôle puis scellement** :
   ```shell
   make control-population POP=data/population/toulouse_population_1000_AAMAS.json TRACE=docs/traces/<date>_population_1000_AAMAS
   make seal-population POP=data/population/toulouse_population_1000_AAMAS.json \
        SELECTION=scripts/data/population/Temp/4_zone_enriched/toulouse_population_1000_AAMAS_selection.json
   ```
   Le scellement **refuse** s'il reste une marge « à corriger » ; sinon il produit
   `data/population/population_1000_AAMAS_v4/` (`population.json`, `MANIFEST.yaml`, `CONTROLE.md`).
   Le contrôle porte aussi la ligne « scolaires (6-17 ans) avec activité d'études » (EMC² : 90 à
   95 %, seuil 88 %) : sous le seuil, l'écart est à publier — il se règle dans l'appariement
   eqasim, pas dans la sélection.
3. **Runs** sur le fichier scellé, pris entier — plus aucun ré-échantillonnage :
   ```yaml
   # llm-agents/config/config.yaml
   data:
     population_file: /data/eqasim-output/population_1000_AAMAS_v3/population.json
   ```

⚠ L'export eqasim élargi (`household`, `provenance`, `validation.commute_mode` à la racine des
enregistrements) demande de **reconstruire l'image** avant de générer : `docker compose build eqasim`.

**Prérequis** : le service eqasim doit être démarré avant d'exécuter le notebook.

```shell
docker compose up eqasim
```

Puis ouvrir `scripts/data/population/generate_population.ipynb` et l'exécuter.

### Les post-traitements sont dans le notebook (étapes 8 et 9)

Depuis le 2026-08-21, le notebook va **jusqu'au bout** : il exporte vers
`data/population/` (étape 7), applique les traits imputés depuis EMC² (étape 8) et rend un
verdict de complétude (étape 9). Il n'y a plus rien à lancer à la main après lui.

Deux manques qu'il avait, et qui étaient silencieux :

- **aucun export final.** Les cinq premières étapes travaillaient dans `Temp/`, et rien ne
  recopiait le résultat vers `data/population/` — seul dossier que lisent GAMA et le
  serveur d'agents. Le fichier qui y traînait était donc la sortie **brute** d'eqasim
  déposée par l'étape 1 : `toulouse_population_1000.json` portait **0 activité planifiée**
  là où `Temp/5_scheduled/` en comptait 3 944 ;
- **aucun trait imputé.** `housing_type` et `personal_bike` n'étaient posés que si
  quelqu'un pensait à lancer les scripts.

**Ré-imputer après un `make housing-type`.** La ressource `zf_housing_type.json` est
**versionnée** : depuis le ticket 019 elle est en v2 (leviers de taille de ménage) et le
module **refuse** une v1 plutôt que d'imputer sans levier. Une population enrichie avant le
ticket porte donc des types de logement tirés par la zone seule : il faut relancer
`enrich_housing_type` pour qu'elle passe à la loi conditionnée. Le sel de tirage a changé
(`housing_type_v2`), la ré-imputation rebat donc **toutes** les valeurs, y compris celles
qui n'auraient pas changé de loi — c'est délibéré et daté au changelog.

Les commandes ci-dessous restent utiles pour rejouer un seul trait sur une population
existante, sans repasser par la génération. Elles sont idempotentes.

```bash
llm-agents/.venv/bin/python -m scripts.data.population.fix_minor_traits data/population/toulouse_population_1000.json
```

```bash
llm-agents/.venv/bin/python -m scripts.data.population.enrich_housing_type data/population/toulouse_population_1000.json --check
```

```bash
llm-agents/.venv/bin/python -m scripts.data.population.enrich_personal_bike data/population/toulouse_population_1000.json --check
```

```bash
make residence-zone CHECK=1
```

**L'ordre compte** : `enrich_personal_bike` lit `housing_type` pour son rapport de
validation (croisement équipement × type d'habitat), il passe donc **après**
`enrich_housing_type`. Et `enrich_housing_type` lit `household_size` : il passe donc après
tout ce qui touche à la composition du foyer — depuis le **ticket 019**, la loi du logement
est conditionnée à la taille nominale du ménage, et un persona sans `household_size` ne
reçoit **aucun** type de logement (pas de repli sur la loi de zone seule). Les deux exigent les ressources d'accès restreint (`make zones`,
`make housing-type`, `make bike-ownership`) et refusent de tourner sans elles plutôt que
d'imputer à l'aveugle.

**`residence_zone` est à part** : c'est le seul trait **observé** de l'étape 8 — un domicile
est dans une commune ou il n'y est pas. Ni tirage, ni loi, ni sel, donc rien à ré-imputer
après un changement de ressource : il suffit de rejouer. Il ne dépend d'aucun autre trait et
passe en tête. Il exige `make communes-couronnes` (table `zf_couronne.json`) et `make zones`.

⚠ **Ne l'appliquez jamais EN PLACE à une population épinglée par un manifeste de jeu gelé.**
`prompt_calibration/calibration_datasets/v5` à `v8` épinglent le sha256 de
`experiments/archive/2026-08-19_14_36/population_1000.json` : la réécrire casse quatre jeux
d'un coup. Passez par `make residence-zone POP=… OUT=…`, qui écrit ailleurs.

Codes de sortie de `--check`, à distinguer : `0` tout est dans la tolérance, `1` ressource
absente (rien n'a été fait), `2` une cible servie est **démentie**, `3` population
**enrichie mais non validée** — trop peu de foyers pour trancher, ce qui est le cas normal
des populations de 10 ou 100 agents et **n'est pas un échec**. `4` (propre à
`residence_zone`) : les portes du trait passent, mais la population est spatialement plus
concentrée que le cadrage — l'axe A9 du ticket 020, qui se corrige dans le **tirage** et
non ici. Le notebook applique cette distinction, et `make residence-zone` traduit le `4` en
succès en le disant.

Détail de chaque étage : [../arch/population-post-traitements.md](../arch/population-post-traitements.md)
et, pour le vélo, [../arch/velo-equipement.md](../arch/velo-equipement.md).
