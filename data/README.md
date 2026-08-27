# data/

Données de la simulation. Certains dossiers sont versionnés via DVC (`.dvc`), les caches sont régénérables et exclus du dépôt git.

## Structure

```
data/
├── cache/                   # Caches régénérables (exclus du dépôt git)
│   ├── eqasim/              # Cache intermédiaire du pipeline eqasim
│   ├── llm/                 # Cache sémantique des réponses LLM 
│   └── osmnx/               # Graphes routiers OSMnx sérialisés 
│
├── gtfs/                    # Données de transport en commun (DVC : gtfs.dvc)
│   ├── tisseo_gtfs/         # Feed GTFS Tisséo (réseau urbain Toulouse)
│   ├── ter_gtfs/            # Feed GTFS TER (réseau régional SNCF)
│   ├── Toulouse.osm.pbf     # Carte OSM utilisée par OTP pour la construction du graphe
│   ├── graph.obj            # Graphe multimodal compilé par OTP
│   └── archives/            # Anciennes versions des feeds GTFS
│       └── 2026-08-26_pre_year_feed/   # Jeu en service avant le feed annuel + 7 exports bruts
│
├── gtfs_year/               # Feeds annuels reconstruits (non versionné, `make gtfs-year`)
│   ├── tisseo_<année>/      # 365 jours : offre réelle quand elle existe, copiée sinon
│   └── ter_<année>/         # idem pour le TER — voir docs/arch/gtfs-annee.md
│
├── population/              # Population synthétique générée par eqasim (DVC : eqasim_output.dvc)
│   └── toulouse_population_<N>.json   # N = taille de la population (100, 200, …, 10000)
│
├── po_toulouse.small/       # Données spatiales POI Toulouse (DVC : po_toulouse.small.dvc)
│
├── weather/                 # Météo historique Toulouse 2025 (CSV mensuels)
│
├── exports/                 # Exports géospatiaux générés par les scripts d'analyse
│   └── gtfs/                # Routes et arrêts au format GeoJSON / Shapefile
│
└── prometheus_data/         # Base de données Prometheus (créé par Docker, non versionné)
```

## DVC

Les dossiers volumineux sont gérés par [DVC](https://dvc.org/) et ne sont pas stockés dans git.
Pour les récupérer :

```bash
dvc pull
```

Fichiers DVC présents : `gtfs.dvc`, `eqasim_output.dvc`, `po_toulouse.small.dvc`, `population_samples.dvc`.

## Caches

Les trois dossiers sous `cache/` sont entièrement régénérables :

| Dossier | Régénéré par | Commande |
|---|---|---|
| `cache/eqasim/` | Pipeline eqasim | `make purge_cache` puis relancer eqasim |
| `cache/llm/` | Premier appel LLM par population | `make purge_cache` |
| `cache/osmnx/` | Démarrage du service OSMnx | `make purge_cache` |

## Données GTFS / OTP

Le dossier `gtfs/` sert à la fois de répertoire d'entrée pour OTP et de stockage des feeds GTFS, car OTP exige que la carte OSM (`.pbf`) et les feeds soient dans le même répertoire lors de la construction du graphe (`make build-graph` dans `otp-toulouse/`).
