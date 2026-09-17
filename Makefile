# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

# Un seul fichier de configuration de run, plus de choix par variable : pour
# changer de config, éditer directement services/llm-agents/config/config.yaml.

GAMA_BIN        = /Applications/GAMA.app/Contents/MacOS/GAMA
# Racine du dépôt, déduite de l'emplacement du Makefile (pas de chemin absolu en dur).
# ⚠ `firstword`, PAS `lastword` : MAKEFILE_LIST s'allonge à chaque `include` ci-dessous, et
# `lastword` désignerait alors le dernier .mk inclus — donc `make/` au lieu de la racine.
# Toute la résolution de chemins du dépôt bascule avec cette variable, en silence.
PROJECT_ROOT   := $(patsubst %/,%,$(dir $(abspath $(firstword $(MAKEFILE_LIST)))))
WORKSPACE       = $(PROJECT_ROOT)/services/GAMA/CityTransport

# ── Pile Docker (ticket 039) ──────────────────────────────────────────────────
# Le fichier compose vit dans infra/ ; `--project-directory` garde la RACINE comme
# base des chemins relatifs. Sans lui, compose réancre tout sur infra/ et échoue dès
# `.env` (vérifié : COMPOSE_FILE et COMPOSE_PROJECT_DIRECTORY ne suffisent pas).
COMPOSE_FILE_PATH = infra/docker-compose.yml
COMPOSE           = docker compose -f $(COMPOSE_FILE_PATH) --project-directory $(PROJECT_ROOT)

# Le venv du projet vit dans le service contrôleur (ticket 039 : services/llm-agents).
# ⚠ On l'invoque TOUJOURS par `$(VENV_PYTHON) -m <outil>` : les scripts de `.venv/bin/`
# portent un shebang absolu que le déplacement a périmé.
# Chemin ABSOLU : les cibles qui font `cd` dans un paquet n'ont ainsi aucun `../` à compter
# — c'est ce comptage qui cassait quand `packages/` s'est intercalé (ticket 039).
VENV_PYTHON       = $(PROJECT_ROOT)/services/llm-agents/.venv/bin/python

MODEL_PATH      = $(WORKSPACE)/models/City.gaml
EXPERIMENT_NAME = e

# ── Mode offline : GAMA headless en conteneur ─────────────────────────────────
# `make run OFFLINE=1` (ou l'alias `make run-offline`) : GAMA tourne dans le
# service compose `gama` (profil "offline", image gamaplatform/gama) au lieu de
# l'IHM locale. Le launcher scripts/gama/launch_headless.py pilote load/play
# via le protocole GAMA Server (port 6868).
# NB : `make run --offline` n'est pas une syntaxe make valide — utiliser OFFLINE=1.
OFFLINE ?=
ifneq ($(OFFLINE),)
  export COMPOSE_PROFILES = offline
  export GAMA_WS_URL = ws://gama:3001
endif

# ── Reprise à chaud ────────────────────────────────────────────────────────────
# `make run OFFLINE=1 CONT=1` : reprend le run précédent au lieu d'en créer un
# nouveau — le contrôleur réutilise le workdir pointé par experiments/current
# (journaux appendés, state.json et checkpoints retrouvés) et les données
# Grafana/Prometheus/Redis sont CONSERVÉES. La simulation GAMA repart à t0 du
# jour simulé (pas de gel d'état côté GAMA, cf. ticket 002) ; les caches rendent
# le rejeu quasi instantané. Arrêt à chaud préalable : `make stop-run`.
CONT ?=
ifneq ($(CONT),)
  export CONTINUE_RUN = 1
endif
# Ticket 091 — une reprise se NOMME : `make run … REPRISE=<nom du run>`. Sans ce nom, rien n'est
# réutilisé (ni point de mémoire, ni trace de décisions), parce que le lien experiments/current
# ne prouve pas de quelle expérience vient ce qu'on y trouve.
ifneq ($(REPRISE),)
  export REPRISE_RUN = $(REPRISE)
  export CONTINUE_RUN = 1
endif

# ── Mémoire des agents ─────────────────────────────────────────────────────────
# `make run MEM=0` : coupe la mémoire long terme ET l'auto-réflexion ;
# `make run MEM=1` : les réactive. Sans MEM, le fichier n'est pas touché.
# ⚠ Le levier est services/GAMA/CityTransport/config/sim_params.yaml, PAS l'injection de
# paramètres GAMA Server : Settings.gaml (load_sim_config, cycle 1) écrase les
# paramètres injectés avec le contenu de ce fichier. Le réglage est PERSISTANT
# (le fichier est réécrit à cycle 2) : il vaut aussi pour les runs GUI suivants.
MEM ?=
# `make run CACHE=0` : coupe le cache sémantique LLM — chaque décision passe par le
# modèle et se retrouve donc dans llm_exchanges.jsonl. Condition d'un rejeu (plancher
# « prompt nu », A/B de prompt) sur le périmètre COMPLET. Coûte ~4x plus d'appels.
# `make run CACHE=1` : le réactive. Sans CACHE, le fichier n'est pas touché.
CACHE ?=
# `make run CHOC=<nom>` : joue le choc déclaré dans services/llm-agents/config/chocs/<nom>.yaml
# un retard chiffré et une phrase vécue, posés sur des agents désignés à des jours désignés.
# `make run CHOC=0` : le retire. Sans CHOC, le fichier n'est pas touché.
# ⚠ Coupez le cache avec (`CACHE=0`) : sa clé ne porte aucune durée, une décision prise avant
# le choc peut être resservie pendant. Une [ALARME] se lève si on l'oublie.
CHOC ?=
CHOCS_DIR = services/llm-agents/config/chocs
SIM_PARAMS = services/GAMA/CityTransport/config/sim_params.yaml
APP_CONFIG = services/llm-agents/config/config.yaml

# ── Run sans modèles Google ───────────────────────────────────────────────────
# `make run NO_GOOGLE=1` : blanchit les deux clés Google dans les conteneurs ;
# les instances google* sont exclues de la rotation (« clé API manquante »)
# et la cascade continue sur mistral/groq/cerebras. Pas de repli dégradé :
# simplement moins de capacité LLM.
NO_GOOGLE ?=
ifneq ($(NO_GOOGLE),)
  export SIM_PROVIDER_KEYS__google =
  export PROVIDER_KEYS__google2 =
endif

# ──────────────────────────────────────────────────────────────────────────────
# Délégation (ticket 039, principe 3)
# ──────────────────────────────────────────────────────────────────────────────
#
# Ce fichier ne porte QUE la configuration ci-dessus. Les 120 cibles vivent dans
# make/*.mk, une section par fichier. Pour ajouter une cible, éditez le .mk de sa
# section — aucune déclaration n'est à faire ici, le joker les prend toutes.
#
# ⚠ Les variables doivent rester AU-DESSUS des `include` : un .mk qui lit une
# variable non encore définie ne la voit pas (les `:=` et les `ifneq` s'évaluent
# à la lecture, pas à l'exécution de la recette).

MAKE_MODULES := $(sort $(wildcard $(PROJECT_ROOT)/make/*.mk))
include $(MAKE_MODULES)

# Figé explicitement : sans cette ligne, la cible par défaut serait la PREMIÈRE
# cible du PREMIER .mk inclus — donc l'ordre alphabétique des fichiers déciderait
# de ce que fait un `make` nu.
.DEFAULT_GOAL := up
