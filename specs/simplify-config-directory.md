# Simplification de `llm-agents/config/` : une seule configuration de run

## Problème

`llm-agents/config/` contient aujourd'hui ~30 fichiers `config_*.yaml` d'expériences passées
(baselines, variantes de modèle), sélectionnables au lancement via `make run CONFIG=...`. Ce
choix multiplie les configurations à maintenir et floute laquelle est "la" configuration
actuelle. L'utilisateur veut n'en garder qu'une seule, basée sur `config_test_meteo_agent.yaml`,
modifiable directement dans le fichier plutôt que choisie en ligne de commande.

## Utilisateurs

Chercheur unique (l'utilisateur), qui lance les runs via `make run` en local ou en mode
offline (`make run OFFLINE=1`). Aucune notion de droits différenciés.

## Règles métier

- R1 : `make run` ne prend plus de variable `CONFIG` — la sélection d'un fichier de config
  parmi plusieurs n'existe plus dans le Makefile.
- R2 : Le contenu de `llm-agents/config/config_test_meteo_agent.yaml` devient LA configuration
  de run, sous un nouveau nom `config.yaml`.
- R3 : Tous les autres fichiers `config_*.yaml` d'expérience (baselines, variantes de modèle)
  sont supprimés du répertoire — ils restent récupérables via l'historique git.
- R4 : Chaque run continue d'écrire, dans le dossier `experiments/archive/<run>/`, la
  configuration effectivement utilisée (comportement actuel de `save_static_config`,
  inchangé).
- R5 (déduite) : `osmnx.yaml` et `terminal_time.yaml`, chargés par des chemins codés en dur
  dans `trip_helper/osmnx_direct.py` et `trip_helper/terminal_time.py`, ne font pas partie de
  la sélection "config de run" — ils sont conservés tels quels.
- R6 (déduite) : la documentation (`README.md`, `docs/`) et le changelog reflètent la
  disparition du choix `CONFIG=` et la nouvelle façon de changer de configuration (éditer
  `config.yaml`).

## Critères d'acceptation

- R1 : `grep CONFIG Makefile` ne renvoie plus de variable `CONFIG` pilotant un choix de
  fichier ; `make run` sans argument utilise toujours la même configuration.
- R2 : `llm-agents/config/config.yaml` existe et contient (au minimum) les clés actuellement
  présentes dans `config_test_meteo_agent.yaml` ; un run affiche bien `weather_per_agent_dates:
  true` dans `static_config.yaml` généré.
- R3 : `ls llm-agents/config/` ne liste plus aucun `config_baseline*`, `config_gpt-oss*`,
  `config_llama*`, `config_mistral*`, `config_qwen*`, `config_deepseek*`.
- R4 : après un run, `experiments/archive/<run>/static_config.yaml` existe et reflète la
  config utilisée — inchangé par rapport à avant.
- R5 : les tests existants qui chargent `osmnx.yaml` / `terminal_time.yaml`
  (`test_terminal_time.py`, `osmnx_direct.py`) passent sans modification de chemin.
- R6 : `docs/changelog.md` a une nouvelle entrée en tête décrivant le changement, et toute
  doc mentionnant `make run CONFIG=...` est corrigée.

## Non-goals

- Ne touche pas au contenu métier de `config_test_meteo_agent.yaml` (les valeurs elles-mêmes
  ne changent pas, seul le nom de fichier change).
- Ne modifie pas `osmnx.yaml` ni `terminal_time.yaml`.
- Ne change pas le format ou l'emplacement de `static_config.yaml` dans `experiments/`.
- Ne touche pas à `GAMA/CityTransport/config/sim_params.yaml` (autre système de config, celui
  du levier mémoire `MEM=`).

## Sécurité

Aucune donnée sensible dans ces fichiers YAML (paramètres de simulation, pas de secrets).
Pas de surface d'entrée hostile — fichiers locaux, modifiés uniquement par l'utilisateur.

## Questions ouvertes — résolues

1. **Archivage** : `settings.py` ne dépend plus d'`APP_CONFIG_PATH` — `config.yaml` est
   chargé directement et le workdir d'expérience (`experiments/archive/<run>/`) est créé et
   archivé **inconditionnellement**, dès le premier accès à `settings` (y compris hors
   `make run` : tests, scripts). Validé explicitement par l'utilisateur malgré l'effet de
   bord signalé (chaque run de tests crée désormais un workdir).
2. Les commentaires de l'ancien `config.yaml` (base, cache LLM désactivé par défaut) ont été
   laissés disparaître — seul le contenu de `config_test_meteo_agent.yaml` est repris.
3. `docker-compose.yml` garde la variable `CONFIG_FILE` (inerte côté `settings.py`, mais lue
   directement par `eqasim-toulouse/generate_population.py`), avec un nouveau défaut :
   `${CONFIG_FILE:-config.yaml}`.
