# data/

Données de la simulation. Le substrat scellé et les définitions d'expériences se versionnent ;
les caches, les feeds volumineux et les exécutions sont régénérables et restent hors du dépôt.

## Structure

```
data/
├── population/                        # Substrat de référence
│   ├── population_1000_AAMAS_v5/      # Cohorte SCELLÉE (1 000 personas) — la seule en service
│   │   ├── population.json            #   le fichier que lit le chargeur
│   │   ├── MANIFEST.yaml              #   empreinte de scellement (population.sha256)
│   │   ├── CONTROLE.md                #   les treize marges de contrôle
│   │   ├── report.json / selection.json
│   ├── toulouse_population_1000_AAMAS.json   # source déclarée, même empreinte (provenance)
│   ├── sauvegardes/                   # .tar.gz des cohortes v1 → v5
│   └── archive.zip                    # cohortes v1/v3/v4 et populations pré-AAMAS
│
├── jeux/                              # Jeux de propositions (MANIFEST + propositions.jsonl)
│   ├── population_1000_AAMAS_v5_<date>/
│   └── archive.zip                    # jeu scellé contre la v1
│
├── experiences/                       # Définitions d'expériences (experience.yaml, versionnées)
│   ├── archive_v1_2026-09-11/         # définitions de la campagne v1 — sans les exécutions
│   └── archive_v1_2026-09-11.zip      # la campagne complète, exécutions comprises
│
├── cache/                             # Caches régénérables (hors dépôt)
│   ├── eqasim/                        # cache du pipeline de synthèse de population
│   ├── llm/                           # cache sémantique des réponses LLM
│   ├── osmnx/                         # graphes routiers sérialisés + périmètre
│   │   ├── graphs_444ca7e6a515.pkl    #   graphe EN SERVICE (+ .meta.json et boundary_…)
│   │   └── perimetre_453/             #   extraits OSM du polygone des 453 communes
│   └── otp/                           # itinéraires mémorisés (otp_cache.db)
│
├── gtfs/                              # Entrée d'OTP — monté en lecture seule sur /var/otp/toulouse
│   ├── Toulouse.osm.pbf               # fond de carte
│   ├── graph.obj                      # graphe multimodal EN SERVICE (fait foi)
│   ├── tisseo_gtfs/                   # réseau urbain
│   ├── lio_gtfs/                      # cars régionaux
│   ├── ter_gtfs/                      # trains régionaux
│   ├── build-config.json              # recopiés depuis services/otp-toulouse/toulouse/ par `make otp-graph`
│   ├── otp-config.json / router-config.json
│   └── archives/                      # graphes et feeds antérieurs, chacun avec son README
│
├── gtfs_year/                         # Feeds annuels reconstruits (`make gtfs-year`)
│   ├── tisseo_<année>/  ter_<année>/  lio_<année>/
│
├── PROGEDO 2023/                      # Micro-données EMC² — ACCÈS RESTREINT, hors dépôt
│   ├── lil-1750-Donnees_CSV/fichiers_standards/   # seul format lu par le code
│   ├── lil-1750-Documentation/        # dont SIG/ (zones fines)
│   └── lil-1750-Donnees_{SAS,SPSS,STATA}/         # livraison originale, non lue
│
├── insee/                             # AAV2020 + grille de densité (génération de population)
├── weather/                           # Météo historique Toulouse (CSV mensuels)
└── prometheus_data/                   # Base Prometheus (créée par Docker, non versionnée)
```

## Montages dans les conteneurs

| Hôte | Conteneur |
|---|---|
| `data/population` | `/data/eqasim-output` (controller), `/eqasim-output` (eqasim) |
| `data/gtfs` | `/var/otp/toulouse` (otp1/2/3, lecture seule), `/data/gtfs` |
| `data/cache/osmnx` | `/app/osmnx_cache` et `/app/data/cache/osmnx` |
| `data/cache/otp` | `/app/data/cache/otp` |
| `data/cache/llm` | `/app/data/llm_cache` |
| `data/cache/eqasim` | `/eqasim-cache` |
| `data/jeux`, `data/experiences` | `/app/data/…` |
| `data/weather` | `/app/data/weather` et `/data/weather` |
| `data/prometheus_data` | `/prometheus` |

## Quel graphe fait foi

`data/gtfs/graph.obj` — celui que chargent les trois instances OTP, qui montent `data/gtfs`
en entier. Le réglage `settings.gtfs.gtfs_file` pointe sur `data/gtfs/tisseo_gtfs/`, mais
`sim_clock.py` n'y lit que `agency.txt` et les calendriers : jamais un graphe.

Reconstruction : `make otp-graph` (~55 s). L'ancien graphe est déplacé dans
`archives/<date>_pre_build/`, jamais écrasé.

## DVC

`gtfs.dvc`, `eqasim_output.dvc`, `po_toulouse.small.dvc`, `population_samples.dvc`.
`dvc pull` récupère les dossiers correspondants — `po_toulouse.small/` et `population_samples/`
ne sont plus sur le disque : ils n'ont aucun lecteur dans le code.

## Caches

| Dossier | Régénéré par |
|---|---|
| `cache/eqasim/` | pipeline eqasim (2,4 Go — ne pas vider sans raison, la resynthèse est longue) |
| `cache/llm/` | premier appel LLM de chaque expérience |
| `cache/osmnx/` | démarrage du service OSMnx ; `perimetre_453/` par `build_osmnx_perimeter_graph.py` |
| `cache/otp/` | premiers itinéraires calculés |

Vider un cache pendant qu'un conteneur tourne laisse le service écrire dans un fichier délié :
arrêter la pile (ou au moins `controller` et `osmnx1`) avant, ou les redémarrer après.
