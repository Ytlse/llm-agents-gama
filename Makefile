# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

CONFIG   ?= config_baseline_10000_current.yaml
# CONFIG   ?= config_baseline_1000_current.yaml
export CONFIG_FILE = $(CONFIG)

# Guard: warn immediately if the chosen config file does not exist
_CONFIG_PATH := llm-agents/config/$(CONFIG)
ifeq ($(wildcard $(_CONFIG_PATH)),)
  $(warning ⚠️  Config file '$(_CONFIG_PATH)' not found — containers will start with default settings (SOLARI mode, wrong endpoints). Set CONFIG=<existing-file>.yaml)
endif

GAMA_BIN        = /Applications/GAMA.app/Contents/MacOS/GAMA
# Racine du dépôt, déduite de l'emplacement du Makefile (pas de chemin absolu en dur)
PROJECT_ROOT   := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
WORKSPACE       = $(PROJECT_ROOT)/GAMA/CityTransport
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
# Docker Compose
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: up down restart rebuild logs ps clean purge-cache

up:
	docker compose up -d

# --profile offline : inclut le service gama (mode headless) s'il tourne ;
# sans effet quand il n'est pas lancé.
down:
	docker compose --profile offline down

restart:
	docker compose restart

## Rebuild all images from scratch and restart
rebuild:
	docker compose build --no-cache
	docker compose up -d

## Rebuild and restart api + worker + controller only
api:
	docker compose up --build api worker controller

## Rebuild and restart otp + worker only
otp:
	docker compose up --build otp worker

logs:
	docker compose logs -f

ps:
	docker compose ps

error:
	python3 scripts/errors.py $(if $(LOG),$(LOG),experiments/current/app.log)

warning:
	python3 scripts/warnings.py $(if $(LOG),$(LOG),experiments/current/app.log)

## Rapport de santé « agent-ready » du dernier run. Usage: make report [RUN=experiments/archive/<date>] [OUT=rapport.md]
report:
	python3 scripts/debug/run_report.py $(if $(RUN),$(RUN),) $(if $(OUT),--out $(OUT),)

## Analyse débit vs capacité LLM du dernier run. Usage: make capacity [RUN=… OUT=…]
capacity:
	python3 scripts/debug/llm_capacity.py $(if $(RUN),$(RUN),) $(if $(OUT),--out $(OUT),)

## Analyse de la phase d'init : timeline des étapes, réchauffage des caches (OTP/OSMnx/LLM), bugs de démarrage. Usage: make init [RUN=… OUT=…]
init:
	python3 scripts/debug/init_report.py $(if $(RUN),$(RUN),) $(if $(OUT),--out $(OUT),)

## Met à jour llm_module/config/providers.yaml depuis les quotas réels (headers x-ratelimit + Cloud Quotas Google). Usage: make providers [DRY_RUN=1]
.PHONY: providers
providers:
	python3 scripts/providers/refresh.py $(if $(DRY_RUN),--dry-run,)

## Remove containers, volumes and images
clean:
	@read -rp "Voulez-vous supprimer toutes les images Docker ? (y/N): " ans; \
	if [ "$$ans" = "y" ] || [ "$$ans" = "Y" ] || [ "$$ans" = "yes" ] || [ "$$ans" = "YES" ]; then \
		docker compose down -v --rmi all; \
		docker system prune -a --volumes -f; \
	fi

clean_all:
	@read -rp "Voulez-vous supprimer toutes les images Docker ? (y/N): " ans; \
	if [ "$$ans" = "y" ] || [ "$$ans" = "Y" ] || [ "$$ans" = "yes" ] || [ "$$ans" = "YES" ]; then \
		docker ps -aq | xargs -r docker rm -f; \
		docker system prune -a -f --volumes; \
	fi

## Purge tous les caches applicatifs (OSMnx, eqasim, RAPTOR) + cache Docker builder
purge_cache:
	@echo "🗑️  Cache Docker builder..."
	docker builder prune -a -f
	@echo "🗑️  Cache OSMnx graphs (data/cache/osmnx)..."
	rm -f data/cache/osmnx/*.pkl
	@echo "🗑️  Cache OSMnx local (llm-agents/osmnx_cache)..."
	rm -f llm-agents/osmnx_cache/*.pkl
	@echo "🗑️  Cache scripts OSMnx (scripts/general/cache)..."
	rm -f scripts/general/cache/*.pkl
	@echo "🗑️  Cache pipeline eqasim (eqasim-toulouse/cache)..."
	rm -rf eqasim-toulouse/cache/*.cache
	@echo "🗑️  Cache eqasim (data/cache/eqasim) + population générée (data/population)..."
	rm -rf data/cache/eqasim/*.cache
	rm -f data/population/*.json
	@echo "🗑️  Cache RAPTOR/Solari..."
	rm -f llm-agents/raptor_cache.pickle
	@echo "✅ Tous les caches purgés."

# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: tests burst analysis

tests:
	python llm_module/tests/test_main.py

burst:
	python llm_module/tests/test_e2e.py --scenario 1 --burst 80

# Les notebooks tournent via papermill, installé dans le venv du projet : le
# python du système ne suffit pas. Surchargeable comme les autres interpréteurs.
ANALYSIS_PYTHON ?= llm-agents/.venv/bin/python

## Run all analysis notebooks. Usage: make analysis [LOG_DIR=../../experiments/my_exp/]
analysis:
	@test -x $(ANALYSIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(ANALYSIS_PYTHON)"; \
	  echo "Surchargez-le : make analysis ANALYSIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	$(ANALYSIS_PYTHON) scripts/analysis/run_analysis.py $(if $(LOG_DIR),--log-dir $(LOG_DIR),)

# ──────────────────────────────────────────────────────────────────────────────
# Pilotage
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: dashboard

DASHBOARD_PYTHON ?= llm-agents/.venv/bin/python
DASHBOARD_PORT   ?= 8503
# Thème imposé (light|dark) : les graphes choisissent leurs pas de couleur
# dessus. Le laisser vide ferait diverger l'UI et les couleurs de texte.
DASHBOARD_THEME  ?= light

## Tableau de bord de pilotage : cibles make, tickets, métriques de run.
## Usage: make dashboard [DASHBOARD_THEME=dark] [DASHBOARD_PORT=8503] [DASHBOARD_PYTHON=/chemin/python]
dashboard:
	@test -x $(DASHBOARD_PYTHON) || { \
	  echo "Interpréteur introuvable : $(DASHBOARD_PYTHON)"; \
	  echo "Surchargez-le : make dashboard DASHBOARD_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	$(DASHBOARD_PYTHON) -m streamlit run scripts/dashboard/app.py \
	  --server.port $(DASHBOARD_PORT) --server.headless false \
	  --theme.base $(DASHBOARD_THEME) --theme.primaryColor "#2a78d6"

# ──────────────────────────────────────────────────────────────────────────────
# Synthèse des scores
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: synthesis synthesis-open synthesis-pull-db common-set-eval heldout-eval \
        model-compare model-compare-open

# La synthèse importe pandas/numpy et le moteur de calibration : le python3 du
# système ne suffit pas. On vise le venv du projet, surchargeable.
SYNTHESIS_PYTHON ?= llm-agents/.venv/bin/python

# Rapatriement du store de la campagne cloud avant chaque synthèse (PULL=0 pour
# sauter, p. ex. hors-ligne). La campagne tourne sur la VM : sans ce pull, la
# colonne calibration de la page reflète un instantané local périmé.
SYNTHESIS_PULL_DB := prompt_calibration/calibration_results/calibration_cloud.db
PULL ?= 1

## Rapatrie le store cloud utilisé par la page (calibration_cloud.db). Best-effort :
## si la VM est injoignable, avertit et laisse la synthèse tourner sur l'instantané local.
synthesis-pull-db:
	@$(MAKE) -C prompt_calibration pull-db \
	  LOCAL_DB=calibration_results/calibration_cloud.db \
	|| { echo ""; \
	  echo "⚠️  [ALARME] Rapatriement du store cloud impossible (VM éteinte ? gcloud absent ?)."; \
	  echo "    La page va être générée sur l'instantané local :"; \
	  ls -l $(SYNTHESIS_PULL_DB) 2>/dev/null || echo "    (aucun instantané local : $(SYNTHESIS_PULL_DB) manquant)"; \
	  echo "    Pour ignorer ce pull explicitement : make synthesis PULL=0"; \
	  echo ""; }

## Regenerate the score synthesis page. Usage: make synthesis [RUN=experiments/archive/2026-07-29_18_34] [PULL=0]
synthesis: $(if $(filter 0,$(PULL)),,synthesis-pull-db)
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make synthesis SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.synthesis.build $(if $(RUN),--run $(RUN),)

## Regenerate then open the page in the default browser.
synthesis-open: synthesis
	open docs/synthesis/index.html

## Compare a run to its predecessors AND break its score down by LLM model.
## Usage: make model-compare RUN=experiments/archive/<run> [BASELINE="a b"] [OUT=…]
## Aucun appel LLM : tout est relu dans moves.csv, avec le lecteur et la loss de
## `make synthesis`. À utiliser quand un run a fait tourner plusieurs modèles — la
## page principale, qui agrège le run entier, ne peut pas les séparer. Sortie :
## docs/synthesis/models/<run>/index.html
model-compare:
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make model-compare SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	@test -n "$(RUN)" || { \
	  echo "RUN est obligatoire : make model-compare RUN=experiments/archive/<run>"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.synthesis.model_compare --run $(RUN) \
	  $(foreach b,$(BASELINE),--baseline $(b)) $(if $(OUT),--out $(OUT),)

## Idem, puis ouvre la page.
model-compare-open: model-compare
	open docs/synthesis/models/$(notdir $(patsubst %/,%,$(RUN)))/index.html

## Re-evaluate the pinned prompt lineage's seed and leaf on the common set (action A3).
## CONSOMME DU QUOTA LLM (~130 appels Gemini free tier). Chiffrez d'abord :
##   make common-set-eval DRY_RUN=1
## Reprise gratuite : les évals déjà payées sont servies par le cache du store.
common-set-eval:
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make common-set-eval SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.synthesis.common_set_eval \
	  $(if $(DRY_RUN),--dry-run,) $(if $(PROVIDER),--provider $(PROVIDER),) \
	  $(if $(BATCH),--batch $(BATCH),)

## Evaluate the pinned prompt lineage on a HELD-OUT frozen split (action A4).
## C'est le seul score de la calibration qui ne porte pas sur le jeu ayant servi à
## l'optimiser. CONSOMME DU QUOTA LLM (~100 appels Gemini free tier pour les 6 nœuds
## de la lignée, ~35 pour les deux extrémités). Chiffrez d'abord :
##   make heldout-eval DRY_RUN=1
##   make heldout-eval NODES=all PROVIDER=google2     # toute la lignée
## Reprise gratuite et par nœud : les évals déjà payées sont servies par le cache du
## store. Le témoin d'effectif, lui, est calculé par `make synthesis` sans appel LLM.
heldout-eval:
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make heldout-eval SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.synthesis.heldout_eval \
	  $(if $(DRY_RUN),--dry-run,) $(if $(PROVIDER),--provider $(PROVIDER),) \
	  $(if $(BATCH),--batch $(BATCH),) $(if $(NODES),--nodes $(NODES),) \
	  $(if $(DATASET),--dataset $(DATASET),)

# ──────────────────────────────────────────────────────────────────────────────
# Modèle de choix modal (ticket 005)
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: zones housing-type policy common-set-predict

## Rebuild the fine-zone resource read by llm_module.core.zone_resolver.
## Requires the restricted PROGEDO data under 'data/PROGEDO 2023/'.
zones:
	@test -d "data/PROGEDO 2023" || { \
	  echo "Données PROGEDO absentes : data/PROGEDO 2023/ (accès restreint lil-1750)"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.progedo_logit.export_zone_layer

## Rebuild the housing-type law read when enriching a synthetic population (action A2).
## Requires the restricted PROGEDO data under 'data/PROGEDO 2023/'.
## Puis, pour poser le trait sur une population (aucun appel LLM, déterministe) :
##   llm-agents/.venv/bin/python -m scripts.data.population.enrich_housing_type \
##     data/population/toulouse_population_1000.json
housing-type:
	@test -d "data/PROGEDO 2023" || { \
	  echo "Données PROGEDO absentes : data/PROGEDO 2023/ (accès restreint lil-1750)"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.progedo_logit.export_housing_type

## Retrain the PROGEDO mode-choice policy → scripts/progedo_logit/mode_choice_policy.json
## Le parquet d'entraînement est versionné : contrairement à `zones`, cette cible
## n'exige PAS les données PROGEDO brutes. Résultat déterministe (graine fixée).
policy:
	@test -f scripts/progedo_logit/progedo_mode_choice_v2.parquet || { \
	  echo "Jeu d'entraînement absent : scripts/progedo_logit/progedo_mode_choice_v2.parquet"; \
	  echo "Il est versionné ; s'il manque, régénérez-le avec build_mode_choice_dataset.py"; \
	  echo "(qui exige, lui, les données PROGEDO d'accès restreint)."; \
	  exit 1; }
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make policy SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.progedo_logit.fit_mode_choice_policy

## Apply the trained policy to the pinned common set, renormalised on the OTP offer
## (action A8) → scripts/synthesis/data/progedo_on_common_set.parquet
## Aucun appel LLM, aucun réseau, graine sans objet : le résultat est déterministe.
## Exige la couche de zones (`make zones`) pour les six variables géographiques.
##   make common-set-predict DRY_RUN=1   # périmètre et statuts, sans écrire
common-set-predict:
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make common-set-predict SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.synthesis.model_on_common_set \
	  $(if $(DRY_RUN),--dry-run,)

# ──────────────────────────────────────────────────────────────────────────────
# GAMA
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: run

## Wait until the API and controller are ready (polls /health)
wait-ready:
	@echo "⏳ Attente que l'API soit prête (max 300s)..."
	@elapsed=0; \
	while ! curl -sf http://localhost:8000/health > /dev/null 2>&1; do \
		if [ $$elapsed -ge 300 ]; then \
			echo ""; \
			echo "❌ Timeout : l'API (port 8000) n'a pas répondu en 300s."; \
			echo "   Vérifiez les logs : make logs"; \
			exit 1; \
		fi; \
		printf "\r   API  (port 8000) : %ds écoulées..." $$elapsed; \
		sleep 5; elapsed=$$((elapsed + 5)); \
	done
	@echo "\n✅ API prête"
	@echo "⏳ Attente que le Controller soit prêt (max 60s)..."
	@elapsed=0; \
	while ! curl -sf http://localhost:8002/ > /dev/null 2>&1; do \
		if [ $$elapsed -ge 60 ]; then \
			echo ""; \
			echo "⚠️  Controller (port 8002) pas encore prêt, lancement GAMA quand même."; \
			break; \
		fi; \
		printf "\r   Controller (port 8002) : %ds écoulées..." $$elapsed; \
		sleep 3; elapsed=$$((elapsed + 3)); \
	done
	@echo "⏳ Attente que Grafana soit prêt (max 60s)..."
	@elapsed=0; \
	while ! curl -sf http://localhost:3000/api/health > /dev/null 2>&1; do \
		if [ $$elapsed -ge 60 ]; then \
			echo ""; \
			echo "⚠️  Grafana (port 3000) pas encore prêt, lancement GAMA quand même."; \
			break; \
		fi; \
		printf "\r   Grafana  (port 3000) : %ds écoulées..." $$elapsed; \
		sleep 3; elapsed=$$((elapsed + 3)); \
	done
	@echo "\n✅ Services prêts — lancement GAMA autorisé"

## Start all services then launch the GAMA experiment
## Usage: make run [CONFIG=my_config.yaml] [EXPERIMENT_NAME=e] [OFFLINE=1]
## OFFLINE=1 : GAMA headless en conteneur (service `gama`, profil compose "offline"),
## piloté via GAMA Server — aucune IHM, tout démarre avec docker compose.
run:
ifeq ($(CONT),)
	echo "🗑️  Arrêt de Grafana et Prometheus..."; \
	docker compose stop grafana prometheus 2>/dev/null || true; \
	docker compose rm -f grafana prometheus 2>/dev/null || true; \
	echo "🗑️  Suppression des données Grafana et Prometheus..."; \
	rm -rf data/grafana_data data/prometheus_data; \
	echo "🗑️  Purge des compteurs Redis (wmetrics:)..."; \
	docker compose exec -T redis redis-cli --scan --pattern "wmetrics:*" | xargs -r docker compose exec -T redis redis-cli del 2>/dev/null || true; \

else
	@echo "♻️  Reprise à chaud : workdir, métriques et compteurs conservés ($(shell readlink experiments/current))"
endif
	@$(MAKE) up
	@$(MAKE) wait-ready
ifneq ($(OFFLINE),)
	@if pgrep -f "launch_headless.py" > /dev/null; then \
		echo "⚠️  Un launcher GAMA headless tourne déjà. Lancement ignoré."; \
	else \
		echo "🚀 Lancement headless de l'expérience GAMA : $(EXPERIMENT_NAME) (GAMA Server, conteneur gama)..."; \
		mkdir -p experiments/current; \
		docker compose exec -T -e GAMA_EXPERIMENT=$(EXPERIMENT_NAME) controller \
			python /app/scripts/gama/launch_headless.py \
			>> experiments/current/gama_headless.log 2>&1 & \
		echo "   Console GAMA → experiments/current/gama_headless.log"; \
	fi
else
	@if pgrep -f "$(GAMA_BIN)" > /dev/null; then \
		echo "⚠️  GAMA est déjà en cours d'exécution. Lancement ignoré."; \
	else \
		echo "🚀 Lancement de l'expérience GAMA : $(EXPERIMENT_NAME)..."; \
		$(GAMA_BIN) -p $(WORKSPACE) -o $(MODEL_PATH) -e "$(EXPERIMENT_NAME)" & \
	fi
endif

## Alias : make run-offline == make run OFFLINE=1
.PHONY: run-offline
run-offline:
	@$(MAKE) run OFFLINE=1

## Régénère la base de prompts d'itinéraire SANS simulation ni appel LLM (mode rapide).
## ⛔ ABANDONNÉ POUR LA CALIBRATION (2026-08-17) : sans appel LLM, la chaîne de véhicules
## n'est pas rejouable (savoir où est le vélo suppose de connaître le mode du trajet
## précédent), le vélo est donc proposé partout — 34 % de part vélo sous 1 km contre ~9 %
## sur un jeu issu d'une simulation. NE PAS geler un jeu de calibration depuis cette base :
## voir l'en-tête de scripts/prompt_base/build.py et le §9 du ticket 013.
## Reste utile pour : réchauffer les caches OTP/OSMnx d'un run à venir, éprouver le rendu
## d'une option, chiffrer le coût de routage d'une population.
## La pile doit être debout (make up) — le script tourne dans le conteneur controller.
##
## Usage : make prompt-base [POPULATION=...] [DAY=2026-03-17] [BASE=<nom>] [LIMIT=50]
.PHONY: prompt-base
POPULATION ?= /app/experiments/current/population_1000.json
DAY ?= 2026-03-17
BASE ?= $(DAY)
prompt-base:
	docker compose exec -T controller python /app/scripts/prompt_base/build.py \
		--population $(POPULATION) \
		--out /app/experiments/bases/$(BASE)/entries.jsonl \
		--day $(DAY) \
		$(if $(LIMIT),--limit $(LIMIT),)

## Statut du run GAMA en cours. Sortie parsable clé=valeur :
## run=actif|inactif, mode=offline|ihm, pid, current=<cible du symlink experiments/current>
.PHONY: status
status:
	@if pgrep -f "launch_headless.py" > /dev/null; then \
		echo "run=actif mode=offline pid=$$(pgrep -f launch_headless.py | head -1)"; \
	elif pgrep -f "$(GAMA_BIN)" > /dev/null; then \
		echo "run=actif mode=ihm pid=$$(pgrep -f "$(GAMA_BIN)" | head -1)"; \
	else \
		echo "run=inactif"; \
	fi
	@echo "current=$$(readlink experiments/current 2>/dev/null || echo '-')"

## Arrête le run GAMA en cours SANS toucher au reste de la pile (api, worker, redis…).
## Offline : tue le launcher dans le conteneur controller puis stoppe le service gama
## (GAMA Server tue l'expérience dont le client s'est déconnecté). IHM : SIGTERM à GAMA.
## Pour tout arrêter, y compris les services : make down.
.PHONY: stop-run
stop-run:
	@if docker compose ps --status running controller 2>/dev/null | grep -q controller; then \
		docker compose exec -T controller pkill -f launch_headless.py 2>/dev/null || true; \
	fi
	-@pkill -f "scripts/gama/launch_headless.py" 2>/dev/null || true
	-@docker compose --profile offline stop gama 2>/dev/null || true
	-@pkill -f "$(GAMA_BIN)" 2>/dev/null || true
	@echo "✅ Run arrêté. Les services restent en place (make down pour tout couper)."
