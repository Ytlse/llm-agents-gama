# Population synthétique — EQUASIM

Le module EQUASIM génère une population synthétique réaliste (activités, localisation, démographie) à partir des données publiques françaises (INSEE, OSM, GTFS, BAN, BDTOPO).

Le guide officiel de configuration pour Toulouse est disponible ici :
**https://github.com/eqasim-org/eqasim-france/blob/main/docs/cases/toulouse.md**

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
| Export final | `Temp/5_scheduled/` | `data/eqasim_output/` | Copie vers le dossier consommé par GAMA et le serveur d'agents |

Chaque étape est idempotente : si le fichier de sortie existe déjà dans `Temp/`, elle est ignorée. Pour forcer la reprise à partir d'une étape, définir `FORCE_STEP = 'raw' | 'fixed' | 'pt_enriched' | 'routed' | 'scheduled'` dans la première cellule.

**Prérequis** : le service eqasim doit être démarré avant d'exécuter le notebook.

```shell
docker compose up eqasim
# puis ouvrir scripts/data/population/generate_population.ipynb
```
