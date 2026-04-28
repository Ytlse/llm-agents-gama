# LLM Agents & GAMA platform
Modeling realistic human behavior using generative agents in a multimodal transport system: Software architecture and Application to Toulouse.

<!-- ![intro](docs/paper/raw_assets/toulouse_transport_system.png) -->

## Dépôts externes

Ce projet dépend de modules dont les sources ne sont pas hébergées dans ce dépôt.

| Module | Emplacement local | Dépôt git séparé |
|--------|------------------|-----------------|
| EQUASIM Toulouse | `eqasim-toulouse/` | géré dans un repo indépendant |

Le dossier `eqasim-toulouse/` est intentionnellement absent du suivi git de ce dépôt (`.gitignore`). Il doit être cloné/configuré manuellement après avoir cloné ce projet (voir la section [Population synthétique — EQUASIM](#population-synthétique--equasim) ci-dessous).

## Source references

- GTFS references: https://gtfs.org/resources/gtfs/
- GTFS data: https://data.toulouse-metropole.fr/explore/dataset/tisseo-gtfs/information/
- Other map & population data: https://github.com/eqasim-org/ile-de-france/blob/develop/docs/cases/toulouse.md
- OpenTripPlanner: https://www.opentripplanner.org/

## Architecture

![architecture](docs/paper/raw_assets/architecture.png)

## User guide

### 0. Population synthétique — EQUASIM

Le module EQUASIM Toulouse génère une population synthétique réaliste (activités, localisation, démographie) à partir des données publiques françaises (INSEE, OSM, GTFS, BAN, BDTOPO).

#### Mise en place du dépôt eqasim-toulouse

Le dossier `eqasim-toulouse/` n'est **pas inclus** dans ce dépôt git. Il faut le configurer manuellement :

```shell
# Cloner le fork EQUASIM dans le bon dossier
git clone <url-du-fork-eqasim> eqasim-toulouse
```

Pour gérer tes modifications (fichiers custom : `synthesis/population/llm_agents.py`, `config_toulouse.yml`, `generate_population.py`) de manière indépendante :

```shell
cd eqasim-toulouse
git remote add upstream https://github.com/eqasim-org/ile-de-france.git
# Tes commits vont dans ton fork ; les mises à jour upstream via git pull upstream
```

#### Données d'entrée requises

Télécharger et placer les données dans `data/eqasim/data/` (voir le [guide officiel](https://github.com/eqasim-org/ile-de-france/blob/develop/docs/cases/toulouse.md)) :

| Données | Sous-dossier dans `data/eqasim/data/` |
|---------|--------------------------------------|
| FILOSOFI (revenus INSEE) | `filosofi_2019/` |
| Recensement INSEE | `rp_2019/` |
| ENTD (enquête nationale déplacements) | `entd_2008/` |
| BD TOPO | `bdtopo_toulouse/` |
| OSM Toulouse | `osm_toulouse/` |
| GTFS Tisséo | `gtfs_toulouse/` |
| BAN (adresses) | `ban_toulouse/` |

#### Générer la population manuellement (hors Docker)

```shell
cd eqasim-toulouse
poetry run python generate_population.py
# Résultat : data/eqasim/output/toulouse_population_N.json
```

Variables d'environnement utilisées par `generate_population.py` :

| Variable | Défaut | Description |
|----------|--------|-------------|
| `EQASIM_POPULATION_SIZE` | lu depuis `APP_CONFIG_PATH` ou `1000` | Nombre d'agents cibles |
| `EQASIM_GENERATE_PERSONALITY` | `false` | Générer les scores Big Five (OCEAN) |
| `EQASIM_RANDOM_SEED` | `1234` | Graine de reproductibilité |

#### Activer le mode EQUASIM dans le controller

Dans le fichier de config YAML du controller (ex. `llm-agents/config/config_baseline_1000_current.yaml`) :

```yaml
data:
  population_source: eqasim      # "csv" = ancien mode CSV/GPKG (défaut)
  generate_personality_traits: false
```

En mode Docker, le service `eqasim-init` génère automatiquement la population avant le démarrage du controller (voir section [Run the simulation](#5-run-the-simulation)).

### 1. Population synthetic data

La population est générée par le module EQUASIM Toulouse (voir section 0 ci-dessus). Le fichier `data/po_toulouse.big/` (ancienne population CSV/GPKG) n'est plus utilisé et peut être supprimé.

### 2. Setup OpenTripPlanner

- Download OTP binary from this [guide](https://docs.opentripplanner.org/en/v2.7.0/Getting-OTP/), then put the jar file into the `otp-toulouse/bin/` folder.

- Download the GTFS data from this [link](https://data.toulouse-metropole.fr/explore/dataset/tisseo-gtfs/information/), and extract the GTFS file into the `otp-toulouse/toulouse/gtfs` folder.

- Download the `Toulouse.osm.pbf` file from this [link](https://download.bbbike.org/osm/bbbike/Toulouse/) (find it from the Protocolbuffer (PBF) link on the left side), then put it in the `otp-toulouse/toulouse` folder.

- Run the following commands:

```shell
cd otp-toulouse/

# build the graph.obj file
java -Xmx4G -jar ./bin/otp-shaded-2.8.1.jar --build ./toulouse --save

# run the server
java -Xmx4G -jar ./bin/otp-shaded-2.8.1.jar --load ./toulouse
```

### 3. Prepare the GTFS data for the LLM agent and GAMA model

- Download the GTFS data and extract it into the `data/gtfs` folder.

- Run the following commands. This script builds the GTFS data file - `trip_info.json` - that the models in the GAMA platform can read, and moves this file into the model folder (GAMA/CityTransport/includes/).

```shell
cd scripts/
bash update_gtfs_data.sh
```

### 4. Prepare the config file and workdir

- Create a new config file in the llm-agents/config folder (see the examples in this folder, and find more details in the llm-agents/settings file).

- Copy the sample `population.json` file into the `workdir` folder (which is a setting in the `config.toml` file). Make sure the file name is in the format `population_<number of people>_<number of agents>.json`.

- Depending on which LLM provider you use, populate the api key in the `llm-agents/.envrc` file. The template for this file can be found in `llm-agents/.envrc.example`. In this source code, we support [OpenAI](https://platform.openai.com/), [Groq](https://groq.com/), and self-hosted [vLLM](https://docs.vllm.ai/). If you use vLLM, please populate your `HF_TOKEN` to allow vLLM to download the model from the Hugging Face repository. The `.envrc` file should be loaded as environment variables; you can use direnv for this.

- If you want to experiment with other models, please add a new section in the MODELS list in the `settings.py` file

    ```json
    {
        "code": "openai/gpt-oss-120b",
        "model": "openai/gpt-oss-120b",
        "llm_provider": "vllm",
        "api_key": os.getenv("GROQ_API_KEY"),
        "api_url": "https://api.groq.com/openai/v1",
    },
    ```


### 5. Run the simulation

- Start all Docker services first (LLM agents, Redis, OTP, monitoring, et génération de la population EQUASIM) :

```shell
docker compose up
```

Le service `eqasim-init` se lance automatiquement en premier. S'il trouve un fichier de population JSON existant avec suffisamment d'habitants dans le volume `eqasim_output`, il saute synpp et démarre instantanément. Sinon il génère la population puis le controller démarre.

Pour forcer la regénération (nouvelle seed, nouveau sampling_rate) sans perdre les fichiers existants :

```shell
EQASIM_FORCE_REGENERATE=true docker compose up
```

Pour vider uniquement le cache intermédiaire synpp (utile si les données INSEE/OSM ont changé) sans supprimer les populations déjà générées :

```shell
docker volume rm $(docker compose ps -q | head -1 | xargs docker inspect --format '{{ .Name }}' 2>/dev/null || echo "llm-agents-gama")_eqasim_cache
# ou plus simplement :
docker compose down && docker volume rm <project>_eqasim_cache && docker compose up
```

Pour surcharger la taille de population sans modifier les configs :

```shell
EQASIM_POPULATION_SIZE=5000 docker compose up
```

- Open the GAMA model. The entry model is `GAMA/CityTransport/City.gaml`.

- Hit the play button to start the simulation. The controller will connect to GAMA automatically via WebSocket.

## Reference

```
@misc{vu2025modelingrealistichumanbehavior,
      title={Modeling realistic human behavior using generative agents in a multimodal transport system: Software architecture and Application to Toulouse}, 
      author={Trung-Dung Vu and Benoit Gaudou and Kamaldeep Singh Oberoi},
      year={2025},
      eprint={2510.19497},
      archivePrefix={arXiv},
      primaryClass={cs.MA},
      url={https://arxiv.org/abs/2510.19497}, 
}
```
