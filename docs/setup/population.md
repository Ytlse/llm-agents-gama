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
| `generate_population.py` | Wrapper Docker : lit la taille depuis `APP_CONFIG_PATH` ou env, calcule le `sampling_rate`, gère le cache par taille exacte, supporte le filtrage par bbox → communes IRIS |
| `server.py` | Service HTTP minimal sur le port 8003 (`GET /health`, `POST /generate`), sérialise les requêtes concurrentes (synpp n'est pas réentrant) |
| `synthesis/population/llm_agents.py` | Stage synpp custom : export JSON pour GAMA — noms Faker, traits Big Five optionnels, intégration polygone OTP2 (snap des activités hors-graphe), fusion des activités consécutives identiques, garantie domicile en début/fin de journée |

**Modifications upstream :**

- `config_toulouse.yml` — départements réduits à `["31"]` seul, `sampling_rate` porté à `0.01`, stage `synthesis.population.llm_agents` ajouté à la liste `run`
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
| ENTD (enquête nationale déplacements) | `entd_2008/` | Comportements de mobilité (motifs, fréquences, modes) → génération des chaînes d'activités |
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
  departments: ["31"]
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

⚠ **Limite assumée de la version livrée** : `DEPARTMENTS = ['31']` sert **346 des 453
communes**. Les 107 autres (Gers, Tarn, Tarn-et-Garonne, Ariège, Aude — dont **100 en 3ᵉ
couronne**) demandent +10 Go de BD TOPO et de BAN. Conséquence chiffrée : la 3ᵉ couronne
plafonne à **10,6 %** de la population quand l'enquête en compte **15,4 %**. Voir
[`../arch/perimetre-population.md`](../arch/perimetre-population.md), limite n°6.

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

## Filtrage de la population par bounding box

La zone de simulation est automatiquement dérivée de l'emprise géographique des arrêts GTFS, augmentée d'un tampon de **~5 km** (0,05°) :

```
world_bbox = GTFS stops extent ± 0.05°
```

Au chargement, seuls les agents dont le **domicile** est situé à l'intérieur de cette bbox sont retenus. Les agents qui travaillent ou étudient hors de la bbox restent dans la simulation mais leurs déplacements sont filtrés lors de la planification.

Pour analyser la distribution spatiale et choisir une bbox adaptée :

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
| 4 – Calcul d'itinéraires | `Temp/3_pt_enriched/` | `Temp/4_routed/` | Routes OSMnx parallélisées (jusqu'à 12 workers) — durée, distance, géométrie |
| 5 – Ajustement horaires | `Temp/4_routed/` | `Temp/5_scheduled/` | Recalage des `scheduled_start_time` pour absorber les temps de trajet réels |
| 7 – Export final | `Temp/5_scheduled/` | `data/population/` | Copie vers le dossier consommé par GAMA et le serveur d'agents (monté dans les conteneurs sous `/eqasim-output`). **Refuse** d'écraser si la source n'a aucune activité planifiée ou perd la moitié des agents ; laisse un `.bak` |
| 8 – Traits EMC² | `data/population/` | `data/population/` | `fix_minor_traits`, puis `enrich_housing_type`, puis `enrich_personal_bike` — dans cet ordre. Chacun **refuse de tourner** si sa ressource d'accès restreint manque, au lieu d'imputer à l'aveugle |
| 9 – Audit | `data/population/` | (rapport) | Verdict **POPULATION COMPLÈTE / INCOMPLÈTE** : présence des neuf traits que la simulation consomme, et des horaires recalés |

Chaque étape est idempotente : si le fichier de sortie existe déjà dans `Temp/`, elle est ignorée. Pour forcer la reprise à partir d'une étape, définir `FORCE_STEP = 'raw' | 'fixed' | 'pt_enriched' | 'routed' | 'scheduled'` dans la première cellule.

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
