# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

# Un seul fichier de configuration de run, plus de choix par variable : pour
# changer de config, éditer directement llm-agents/config/config.yaml.

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

# ── Mémoire des agents ─────────────────────────────────────────────────────────
# `make run MEM=0` : coupe la mémoire long terme ET l'auto-réflexion ;
# `make run MEM=1` : les réactive. Sans MEM, le fichier n'est pas touché.
# ⚠ Le levier est GAMA/CityTransport/config/sim_params.yaml, PAS l'injection de
# paramètres GAMA Server : Settings.gaml (load_sim_config, cycle 1) écrase les
# paramètres injectés avec le contenu de ce fichier. Le réglage est PERSISTANT
# (le fichier est réécrit à cycle 2) : il vaut aussi pour les runs GUI suivants.
MEM ?=
# `make run CACHE=0` : coupe le cache sémantique LLM — chaque décision passe par le
# modèle et se retrouve donc dans llm_exchanges.jsonl. Condition d'un rejeu (plancher
# « prompt nu », A/B de prompt) sur le périmètre COMPLET. Coûte ~4x plus d'appels.
# `make run CACHE=1` : le réactive. Sans CACHE, le fichier n'est pas touché.
CACHE ?=
SIM_PARAMS = GAMA/CityTransport/config/sim_params.yaml
APP_CONFIG = llm-agents/config/config.yaml

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

.PHONY: watch-containers
## Sonde la mémoire des conteneurs et capture celui qui tombe. Existe parce que trois runs ont
## été perdus le 2026-09-07 sur un `controller` tué (code 137) sans trace dans ses journaux et
## sans OOM signalé par Docker. Écrit memoire.csv, chute-<service>.txt et sonde.log dans
## experiments/.dashboard/conteneurs/<horodatage>/. Ne modifie aucun conteneur.
## Usage: make watch-containers [INTERVAL=10] [SEUIL=85] [SERVICES=controller,osmnx1] [DUREE=0]
watch-containers:
	$(DASHBOARD_PYTHON) scripts/debug/watch_containers.py \
	  --interval $(or $(INTERVAL),10) --seuil-pct $(or $(SEUIL),85) \
	  $(if $(SERVICES),--services $(SERVICES),) $(if $(DUREE),--duree $(DUREE),)

.PHONY: stop-services
## Arrête SEULEMENT les services nommés, sans supprimer conteneurs ni volumes : rend la RAM
## (osmnx1 porte 3,5 Gio, chaque OTP 1,2 à 1,5 Gio) et un redémarrage reste rapide.
## Usage: make stop-services SERVICES="controller api worker otp1 otp2 otp3 osmnx1 eqasim redis"
stop-services:
	@test -n "$(SERVICES)" || { echo "SERVICES= est vide : nommez les services à arrêter"; exit 2; }
	docker compose stop $(SERVICES)

.PHONY: experience-lancer-arret
## Lance une expérience PUIS arrête les services qu'elle utilisait. L'arrêt est chaîné dans la
## commande : il a lieu même si le tableau de bord est fermé entre-temps. Le code de retour de
## l'expérience est conservé, pour qu'un échec reste un échec dans le journal du job.
## Usage: make experience-lancer-arret EXP=<nom> SERVICES="controller api worker …" [REQUIS="…"]
## SERVICES = ce qu'on ARRÊTE à la fin ; REQUIS = ce qu'on garantit AVANT de lancer.
experience-lancer-arret:
	@test -n "$(SERVICES)" || { echo "SERVICES= est vide : nommez les services à arrêter"; exit 2; }
	@$(MAKE) --no-print-directory services-pretes REQUIS="$(if $(REQUIS),$(REQUIS),controller)"
	@set +e; \
	$(EXPERIENCES_PY) lancer --experience $(EXP); code=$$?; \
	if $(EXPERIENCES_PY) actives --est-vide; then \
		echo "[arret-fin] (code $$code) plus aucune expérience active — arrêt de : $(SERVICES)"; \
		docker compose stop $(SERVICES); \
	else \
		echo "[arret-fin] (code $$code) d'autres expériences tiennent une clé — services laissés up (R5) :"; \
		$(EXPERIENCES_PY) actives; \
	fi; \
	exit $$code

.PHONY: run-arret
## Idem pour un lancement avec GAMA : le service `gama` du profil offline est arrêté aussi.
## Usage: make run-arret JEU=<jeu> SERVICES="controller api worker …"
run-arret:
	@test -n "$(SERVICES)" || { echo "SERVICES= est vide : nommez les services à arrêter"; exit 2; }
	@set +e; \
	$(MAKE) run OFFLINE=1 JEU=$(JEU); code=$$?; \
	echo "[arret-fin] run terminé (code $$code) — arrêt de : $(SERVICES) gama"; \
	docker compose --profile offline stop $(SERVICES) gama; \
	exit $$code

.PHONY: up-services services-pretes
## Démarre SEULEMENT les services nommés, avec leurs dépendances du compose : une expérience
## n'a pas besoin du monitoring (Prometheus, Grafana, cAdvisor, node-exporter, Flower). Ne
## rend pas la main sur des services sains — pour cela, voir `services-pretes`.
## Usage: make up-services SERVICES="controller api worker"
up-services:
	@test -n "$(SERVICES)" || { echo "SERVICES= est vide : nommez les services à démarrer"; exit 2; }
	docker compose up -d $(SERVICES)

## Garantit que les services nommés tournent ET sont sains, puis rend la main. Idempotent :
## sur une pile déjà debout, docker compose ne recrée rien et la cible passe en une seconde.
## Chaînée en tête de `experience-lancer` et de `jeu` : plus besoin de penser à démarrer la
## pile avant de lancer une expérience, depuis le tableau de bord comme depuis un terminal.
## `--wait` attend les healthchecks : `controller` dépend d'`api`, `otp1-3`, `eqasim` et
## `osmnx1` en bonne santé, et le chargement des graphes OTP/OSMnx prend plusieurs minutes à
## froid. ATTENTE borne cette attente pour échouer bruyamment plutôt que de pendre.
## `--no-recreate` est NON NÉGOCIABLE : un `up -d` nu recrée un conteneur dont la configuration
## a bougé depuis son démarrage, ce qui TUERAIT le runner d'une expérience qui tourne dans
## `controller` (lancé par `docker compose exec`). Cette cible est chaînée à chaque lancement,
## y compris pendant qu'une autre expérience travaille : elle démarre ce qui manque et ne
## touche à rien de ce qui tourne. Pour appliquer un changement de configuration, c'est
## `make run` (qui recrée explicitement) ou `docker compose up -d --force-recreate` à la main.
## Usage: make services-pretes REQUIS="controller api worker" [ATTENTE=600]
services-pretes:
	@test -n "$(REQUIS)" || { echo "REQUIS= est vide : nommez les services à garantir"; exit 2; }
	@echo "🐳 Services requis : $(REQUIS) — démarrage de ce qui manque, sans toucher à ce qui tourne (max $(if $(ATTENTE),$(ATTENTE),600)s)"
	docker compose up -d --no-recreate --wait --wait-timeout $(if $(ATTENTE),$(ATTENTE),600) $(REQUIS)

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

.PHONY: otp-graph
## Construit le graphe OTP (data/gtfs/graph.obj) en partant des configurations VERSIONNÉES.
## `data/gtfs/` est un répertoire de travail non versionné : sans cette recopie, une
## reconstruction perd les réglages de `otp-toulouse/toulouse/*.json` sans le dire — c'est
## arrivé le 2026-09-04 (embedRouterConfig, boardingLocationTags, staticParkAndRide et
## maxStopToShapeSnapDistance perdus, donc des instances tournant sur les défauts d'OTP).
## L'ancien graphe est archivé, jamais écrasé.  Usage: make otp-graph
otp-graph:
	@test -f data/gtfs/Toulouse.osm.pbf || { echo "data/gtfs/Toulouse.osm.pbf manquant"; exit 1; }
	@cp -v otp-toulouse/toulouse/build-config.json otp-toulouse/toulouse/router-config.json \
	       otp-toulouse/toulouse/otp-config.json data/gtfs/
	@if [ -f data/gtfs/graph.obj ]; then \
	  d=data/gtfs/archives/$$(date +%Y-%m-%d_%H-%M)_pre_build ; mkdir -p $$d ; \
	  mv -v data/gtfs/graph.obj $$d/ ; fi
	java -Xmx4G -jar otp-toulouse/bin/otp-shaded-*.jar --build data/gtfs --save
	@ls -l data/gtfs/graph.obj && shasum -a 256 data/gtfs/graph.obj

logs:
	docker compose logs -f

ps:
	docker compose ps

error:
	python3 scripts/errors.py $(if $(LOG),$(LOG),experiments/current/app.log)

warning:
	python3 scripts/warnings.py $(if $(LOG),$(LOG),experiments/current/app.log)

## Parité des chapitres de l'article : mêmes versions dans article/en, article/fr et article/overleaf. Usage: make paper-parite
paper-parite:
	python3 scripts/paper/verifier_parite.py

## Rapport de santé « agent-ready » du dernier run. Usage: make report [RUN=experiments/archive/<date>] [OUT=rapport.md]
report:
	python3 scripts/debug/run_report.py $(if $(RUN),$(RUN),) $(if $(OUT),--out $(OUT),)

## Analyse débit vs capacité LLM du dernier run. Usage: make capacity [RUN=… OUT=…]
capacity:
	python3 scripts/debug/llm_capacity.py $(if $(RUN),$(RUN),) $(if $(OUT),--out $(OUT),)

## Analyse de la phase d'init : timeline des étapes, réchauffage des caches (OTP/OSMnx/LLM), bugs de démarrage. Usage: make init [RUN=… OUT=…]
init:
	python3 scripts/debug/init_report.py $(if $(RUN),$(RUN),) $(if $(OUT),--out $(OUT),)

.PHONY: providers
## Met à jour config/llm_gateway/providers.yaml depuis les quotas réels (headers x-ratelimit + Cloud Quotas Google). Usage: make providers [DRY_RUN=1]
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

.PHONY: tests test-gateway test-mobility test-all lint-imports lint typecheck analysis

# Interpréteur des paquets (installés en editable dans le venv de llm-agents).
PKG_PYTHON ?= llm-agents/.venv/bin/python

## Tests du gateway LLM générique (unit + contract + integration ; e2e si LLM_GATEWAY_E2E_URL)
test-gateway:
	cd llm_gateway && ../$(PKG_PYTHON) -m pytest

## Tests du domaine mobilité (mobility_core) et des catégories LLM (mobility_llm)
test-mobility:
	cd mobility_core && ../$(PKG_PYTHON) -m pytest
	cd mobility_llm && ../$(PKG_PYTHON) -m pytest

## Les trois paquets, puis les contrats d'architecture
test-all: test-gateway test-mobility lint-imports

## Alias historique
tests: test-all

## Contrats import-linter des trois paquets (.importlinter à la racine)
lint-imports:
	$(PKG_PYTHON) -c "from importlinter.cli import lint_imports_command; lint_imports_command()"

## ruff sur les trois paquets
lint:
	$(PKG_PYTHON) -m ruff check llm_gateway mobility_core mobility_llm

## mypy : contrat public du gateway (core, ports, sdk) en strict
typecheck:
	cd llm_gateway && ../$(PKG_PYTHON) -m mypy src/llm_gateway/core src/llm_gateway/ports src/llm_gateway/sdk

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

.PHONY: help
## Liste les cibles documentées : le nom de chaque cible et le bloc `##` qui la précède.
## Utile depuis que le tableau de bord n'affiche plus le catalogue des cibles.
help:
	@awk '\
	  /^## / { if (doc == "") doc = substr($$0, 4); next } \
	  /^\.PHONY/ { next } \
	  /^[a-zA-Z0-9_.-]+:/ { if (doc != "") { split($$0, cible, ":"); printf "  %-24s %s\n", cible[1], doc }; doc = ""; next } \
	  /^[[:space:]]*$$/ { doc = "" } \
	' $(firstword $(MAKEFILE_LIST))

## Tableau de bord de pilotage : état des services, expériences en cours, tickets, métriques de run.
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

.PHONY: synthesis synthesis-open synthesis-pull-db terminal-page \
        common-set-eval heldout-eval \
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

## Build a TIMESTAMPED, archived synthesis page for the frozen-set A/B measurements
## (temps terminal). Aucun appel LLM : relit docs/traces/<nom>/results.json.
## Sortie : docs/synthesis/<AAAA-MM-JJ_HH-MM>_temps_terminal.html — chaque exécution
## crée une archive, aucune page existante n'est écrasée (contrairement à index.html,
## régénérée en place parce qu'elle suit l'état courant).
terminal-page:
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.synthesis.build_terminal_page

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

## Sélectionne les décisions du run épinglé où le LLM a retenu un transport collectif
## alors que la MARCHE était proposée, puis les rejoue sous dix prompts modifiés.
## AUCUN appel LLM ici : sélection seule, pour vérifier le périmètre.
alt-prompt-subset:
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make alt-prompt-subset SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.synthesis.alt_prompt_replay subset

## Rejoue le sous-jeu sous les dix variantes de prompt.
## CONSOMME DU QUOTA LLM (~620 appels Gemini free tier, ~25 min sur deux clés).
## Chiffrez d'abord : make alt-prompt-replay DRY_RUN=1
## Reprise gratuite : un bras dont la trace existe déjà est repris sans appel
## (FORCE=1 pour le re-payer). Usage : [VARIANTS=1,4,10] [DRY_RUN=1] [FORCE=1]
alt-prompt-replay:
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make alt-prompt-replay SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.synthesis.alt_prompt_replay replay \
	  $(if $(DRY_RUN),--dry-run,) $(if $(FORCE),--force,) \
	  $(if $(VARIANTS),--variants $(VARIANTS),)

## Écrit les dix pages docs/synthesis/detail_simulation_26_08_alternative<N>.html
## depuis les traces du rejeu. Aucun appel LLM. Usage : [VARIANTS=1,4,10]
alt-prompt-pages:
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make alt-prompt-pages SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.synthesis.alt_prompt_replay render \
	  $(if $(VARIANTS),--variants $(VARIANTS),)

## Figure PNG : les camemberts avant / après d'un ajout de prompt, lus dans la page
## de la variante. Aucun appel LLM.
## Usage : [VARIANT=1] [SCOPE=global|subset|both] — global (défaut) = population entière,
## subset = les 495 décisions rejouées seules, both = les deux étages empilés.
alt-prompt-figure:
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make alt-prompt-figure SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.synthesis.alt_prompt_figure \
	  $(if $(VARIANT),--variant $(VARIANT),) $(if $(SCOPE),--scope $(SCOPE),)

## Tests du rejeu : appariement moves.csv ↔ llm_exchanges.jsonl, point d'insertion
## du bloc de variante, substitution. Journaux fabriqués, aucun appel LLM.
test-alt-prompt:
	@$(SYNTHESIS_PYTHON) -m pytest scripts/tests/test_alt_prompt_replay.py -q

# ──────────────────────────────────────────────────────────────────────────────
# Modèle de choix modal (ticket 005)
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: zones housing-type bike-ownership terminal-time car-availability avancement policy policy-tune common-set-predict equipment-propensity
.PHONY: logit mnl-predict bi-oracle
.PHONY: communes-couronnes audit-perimetre audit-couronnes residence-zone couronne-v7

## ──────────────────────────────────────────────────────────────────────────────
## Périmètre de population (ticket 020)
## ──────────────────────────────────────────────────────────────────────────────

## Rebuild the commune → couronne table and the couronne geometry (ticket 020, lot 3).
## Requires the restricted PROGEDO data under 'data/PROGEDO 2023/'.
## C'est la DONNÉE MANQUANTE du ticket : l'enquête découpe ses couronnes par LISTE DE
## COMMUNES (1 / 69 / 108 / 275), là où `geo_reference.residence_zone` classe par
## distance à l'hypercentre. Produit mobility_core/src/mobility_core/data/commune_couronne.json et
## couronne_perimetre.geojson, tous deux versionnés.
communes-couronnes:
	@test -d "data/PROGEDO 2023" || { \
	  echo "Données PROGEDO absentes : data/PROGEDO 2023/ (accès restreint lil-1750)"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.progedo_logit.export_commune_couronne

## Audit des neuf écarts de base entre population enquêtée et population simulée
## (ticket 020, lot 2). N'exige PAS les données PROGEDO : il lit le cadrage
## `population_emc2_2023.yaml` et les ressources versionnées de `make communes-couronnes`.
##   make audit-perimetre                                  # population et run par défaut
##   make audit-perimetre POP=data/population/x.json RUN=experiments/archive/y
##   make audit-perimetre TRACE=docs/traces/2026-08-24_perimetre_population
## Codes de sortie : 0 tout conforme, 2 au moins un axe à corriger, 3 au moins un axe
## NON MESURABLE — un axe non mesuré est un axe qui passe, et le script refuse de le taire.
## Les deux équivalences du ticket 021, lot 0 : le classement d'un domicile par PRÉFIXE de
## code de zone fine contre son classement par APPARTENANCE géométrique, et « hors couche de
## zones fines » contre « hors périmètre ». Sept portes, dont un recoupement INDÉPENDANT
## contre la trace du ticket 020. Ne modifie rien.
##   make audit-couronnes
##   make audit-couronnes POP=data/population/x.json TRACE=docs/traces/y
## Codes de sortie : 0 les portes passent, 2 une porte ÉCHOUE (le ticket est à reconcevoir),
## 3 une porte est NON MESURABLE — données SIG d'accès restreint absentes, et une porte non
## mesurée est une porte qui passe. Après le lot 1, la table versionnée remplace le SIG.
## Pose la couronne de résidence et la commune sur une population déjà générée
## (ticket 021, lot 2 — étage D). Déterministe, aucun tirage, aucun appel LLM : le trait est
## OBSERVÉ. La ressource, elle, se (re)produit par `make communes-couronnes`.
##   make residence-zone                                    # population par défaut
##   make residence-zone POP=data/population/x.json CHECK=1
##   make residence-zone POP=experiments/archive/y/population_1000.json OUT=/tmp/z.json
## ⚠ NE JAMAIS enrichir EN PLACE une population épinglée par un manifeste de jeu gelé
## (calibration_datasets/v5..v8 épinglent le sha256 de l'archive 2026-08-19_14_36) : passez
## par OUT=. Codes de sortie de CHECK : 0 portes passées, 1 ressource absente, 2 une porte
## démentie, 4 portes passées mais écart au cadrage (axe A9 — le tirage, pas ce trait).
## La cible TRADUIT le 4 en succès, en le disant : make ne sait pas distinguer un code de
## sortie informatif d'une erreur, et un « Error 4 » apprendrait à ignorer les erreurs.
residence-zone:
	@$(SYNTHESIS_PYTHON) -m scripts.data.population.enrich_residence_zone \
	  $(if $(POP),$(POP),data/population/toulouse_population_1000.json) \
	  $(if $(OUT),--out $(OUT),) $(if $(CHECK),--check,) $(if $(DRY),--dry-run,) ; \
	code=$$? ; \
	if [ $$code -eq 4 ]; then \
	  echo "→ code 4 : écart au cadrage (axe A9, le tirage) — PAS un échec de ce trait." ; \
	  exit 0 ; \
	fi ; \
	exit $$code

## Chiffre l'effet du reclassement des couronnes sur le jeu gelé `v7` (ticket 021, lot 4).
## AUCUN appel LLM : les décisions sont déjà dans le store de calibration, et la couronne
## n'entre ni dans le prompt ni dans la clé de cache — « à décisions constantes » est donc
## structurel. Splits `train` + `val` (569 agents) ; `rank` est trop petit pour un découpage
## par couronne, `test` n'a pas d'éval stockée et reste la réserve de publication.
##   make couronne-v7 TRACE=docs/traces/2026-08-24_couronne_v7
couronne-v7:
	$(SYNTHESIS_PYTHON) -m scripts.synthesis.measure_couronne_v7 \
	  $(if $(TRACE),--trace $(TRACE),)

audit-couronnes:
	$(SYNTHESIS_PYTHON) -m scripts.data.population.audit_couronne_equivalences \
	  $(if $(POP),--population $(POP),) $(if $(TRACE),--trace $(TRACE),)

audit-perimetre:
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make audit-perimetre SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.data.population.audit_perimetre \
	  $(if $(POP),--population $(POP),) $(if $(RUN),--run $(RUN),) \
	  $(if $(TRACE),--trace $(TRACE),)

.PHONY: osmnx-perimeter-graph

## Graphes OSMnx (marche, vélo, voiture) du polygone des 453 communes du périmètre d'enquête
## (ticket 031 § 1.4) : extrait des pbf OSM régionaux du fork eqasim par `osmium extract`, filtres
## réseau et vitesses de la production, cache data/cache/osmnx/graphs_<clé>.pkl sous une clé
## distincte du disque de 30 km. Aucun téléchargement. Le notebook generate_population exige ce
## graphe pour les étapes 4+5. FORCE=1 reconstruit ; TRACE=<dossier> archive les mesures.
##   make osmnx-perimeter-graph TRACE=docs/traces/$$(date +%Y-%m-%d_%H-%M)_graphe_osmnx_perimetre_453
osmnx-perimeter-graph:
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; exit 1; }
	@command -v osmium >/dev/null || test -x /opt/homebrew/bin/osmium || { \
	  echo "osmium introuvable : brew install osmium-tool"; exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.data.population.build_osmnx_perimeter_graph \
	  $(if $(FORCE),--force,) $(if $(TRACE),--trace $(TRACE),)

.PHONY: synthese-representativite

## Synthèse HTML de représentativité d'une population scellée (identité visuelle de la synthèse v2,
## chiffres lus dans report.json / selection.json / MANIFEST du sceau, le contrôle du vivier et l'audit).
##   make synthese-representativite SCEAU=data/population/population_1000_AAMAS_v4 \
##        PRECEDENT=data/population/population_1000_AAMAS_v3 VIVIER=docs/traces/<d>_controle_vivier/report.json \
##        AUDIT=docs/traces/<d>_audit/audit_perimetre.json OUT=docs/traces/<d>/synthese_representativite_v3.html \
##        VELO=docs/traces/<d>/velo_cohorte.json VELO_VIVIER=docs/traces/<d>/velo_vivier.json \
##        COPIE=docs/paper/methode/population/synthese_representativite_v3_population_v4_<date>.html
## Les deux rapports vélo viennent de `enrich_personal_bike <population> --dry-run --check --rapport-json <fichier>`
## sur la cohorte scellée et sur le vivier pré-imputé (Temp/4_zone_enriched) : la pente se juge sur le vivier.
synthese-representativite:
	@test -n "$(SCEAU)" || { echo "SCEAU=<dossier scellé> obligatoire"; exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.AAMAS.synthese_representativite --sceau $(SCEAU) \
	  $(if $(PRECEDENT),--precedent $(PRECEDENT),) $(if $(VIVIER),--vivier $(VIVIER),) \
	  $(if $(AUDIT),--audit $(AUDIT),) $(if $(VELO),--velo $(VELO),) $(if $(VELO_VIVIER),--velo-vivier $(VELO_VIVIER),) \
	  --out $(if $(OUT),$(OUT),$(SCEAU)/synthese_representativite.html) \
	  $(if $(COPIE),--copie $(COPIE),)

.PHONY: synthese-generation-population

## Page « Comment la population du jeu de test est fabriquée » (eqasim, notebook, sélection, routage,
## traits, contrôle, sceau — et les résultats de chaque étage), chiffres lus dans les mêmes fichiers que la
## synthèse de représentativité plus la méta du graphe OSMnx et les mesures du graphe.
##   make synthese-generation-population SCEAU=data/population/population_1000_AAMAS_v4 \
##        VIVIER=… AUDIT=… VELO=… VELO_VIVIER=… MESURES_GRAPHE=docs/traces/<d>_mesures_graphe_perimetre_v4/mesures.json \
##        OUT=docs/traces/<d>/fabrication_population.html COPIE=docs/paper/methode/population/fabrication_population_v4_<date>.html
synthese-generation-population:
	@test -n "$(SCEAU)" || { echo "SCEAU=<dossier scellé> obligatoire"; exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.AAMAS.synthese_generation_population --sceau $(SCEAU) \
	  $(if $(VIVIER),--vivier $(VIVIER),) $(if $(AUDIT),--audit $(AUDIT),) \
	  $(if $(VELO),--velo $(VELO),) $(if $(VELO_VIVIER),--velo-vivier $(VELO_VIVIER),) \
	  $(if $(MESURES_GRAPHE),--mesures-graphe $(MESURES_GRAPHE),) \
	  --out $(if $(OUT),$(OUT),$(SCEAU)/fabrication_population.html) $(if $(COPIE),--copie $(COPIE),)

.PHONY: reference-marges control-population select-population seal-population

## Contrôle de la population du jeu de test (article AAMAS, jalon 0 du protocole).
## Compare une population synthétique aux marges de l'EMC² 2023 — classes d'âge, occupation,
## motorisation (base personne et base ménage), couronne, croisement couronne × motorisation —
## avec IC95, TOST à ± BORNE pt, χ² + V de Cramér, EMD/JSD, journal de recoupement du
## protocole et synthèse des écarts. Code 1 s'il reste un « à corriger ».
##   make control-population                                   # population par défaut
##   make control-population POP=data/population/x.json BORNE=1.0 TRACE=docs/traces/y
control-population:
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make control-population SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.AAMAS.control_population \
	  $(if $(POP),$(POP),data/population/toulouse_population_1000.json) \
	  $(if $(BORNE),--borne $(BORNE),) $(if $(TRACE),--trace $(TRACE),--trace-auto) $(if $(JSON),--json $(JSON),)

## Les marges de référence, avec leur source (page du rapport ou recalcul gelé).
## RECOMPUTE=1 regèle la cible jointe couronne × motorisation depuis les microdonnées ProGEDO.
reference-marges:
	$(SYNTHESIS_PYTHON) -m scripts.AAMAS.reference_marges $(if $(RECOMPUTE),--recompute,)

## Sélection stratifiée de N personas dans un vivier (avant le routage — l'étape 3ter du
## notebook l'appelle). POOL obligatoire ; OUT défaut : <dossier du vivier>/toulouse_population_<N>_AAMAS.json
##   make select-population POOL=scripts/data/population/Temp/4_zone_enriched/toulouse_population_5000.json N=1000
select-population:
	@test -n "$(POOL)" || { echo "POOL=<vivier.json> obligatoire"; exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.AAMAS.seal_population select --pool $(POOL) \
	  --n $(if $(N),$(N),1000) \
	  --out $(if $(OUT),$(OUT),$(dir $(POOL))toulouse_population_$(if $(N),$(N),1000)_AAMAS.json)

## Scellement : contrôle puis copie dans un dossier immuable avec MANIFEST.yaml et CONTROLE.md.
## REFUSE si une marge est « à corriger ». POP obligatoire ; OUT_DIR défaut : data/population/population_1000_AAMAS_v4
## (règle de sélection v4 : ménages entiers + six classes d'âge + périmètre des 453 communes,
## ticket 031 ; les dossiers v2 et v3 restent intacts)
##   make seal-population POP=data/population/toulouse_population_1000_AAMAS.json \
##        SELECTION=scripts/data/population/Temp/4_zone_enriched/toulouse_population_1000_AAMAS_selection.json
seal-population:
	@test -n "$(POP)" || { echo "POP=<population.json> obligatoire"; exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.AAMAS.seal_population seal --population $(POP) \
	  $(if $(OUT_DIR),--out-dir $(OUT_DIR),) $(if $(N),--n $(N),) \
	  $(if $(SELECTION),--selection-json $(SELECTION),) $(if $(BORNE),--borne $(BORNE),) \
	  $(if $(NOTE),--note "$(NOTE)",)

.PHONY: gtfs-year gtfs-year-dry gtfs-year-holdout gtfs-window test-gtfs-year

## Reconstruit un feed GTFS couvrant l'année entière à partir des exports partiels
## de l'opérateur. Chaque journée porte soit l'offre réelle publiée, soit la copie
## verbatim d'une journée réelle de même signature (jour de semaine × période
## scolaire zone C) ; aucun horaire n'est synthétisé, et la provenance de chaque
## jour est tracée sous docs/traces/<date>_gtfs_annee/.
##   make gtfs-year                              # Tisséo + TER, 2026 et 2027
##   make gtfs-year RESEAU=tisseo ANNEES="2026"
## Codes de sortie : 0 tout tenu, 1 ressource absente, 2 invariant démenti
## (le feed ne doit PAS être publié), 4 construit mais confiance dégradée.
## La cible TRADUIT le 4 en succès, en le disant : un feed annuel bâti sur six
## mois d'exports comporte forcément des journées extrapolées de loin, et un
## « Error 4 » apprendrait à ignorer les erreurs.
gtfs-year:
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make gtfs-year SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	@$(SYNTHESIS_PYTHON) -m scripts.data.gtfs_year.build_year_feed \
	  $(foreach r,$(RESEAU),--reseau $(r)) \
	  $(foreach a,$(ANNEES),--annee $(a)) \
	  $(if $(SORTIE),--sortie $(SORTIE),) $(if $(TRACE),--trace $(TRACE),) \
	  $(if $(DRY),--dry-run,) $(if $(HOLDOUT),--holdout $(HOLDOUT),) \
	  $(if $(REFRESH),--rafraichir-calendrier,) ; \
	code=$$? ; \
	if [ $$code -eq 4 ]; then \
	  echo "→ code 4 : feed construit, mais des journées sont extrapolées sans donneur de même nature." ; \
	  echo "  Lisez docs/traces/*_gtfs_annee/provenance_*.csv avant de publier." ; \
	  exit 0 ; \
	fi ; \
	exit $$code

## Planifie sans rien écrire : quelles journées sont réelles, lesquelles seraient
## copiées et depuis quand. À lancer avant tout build après réception d'exports.
gtfs-year-dry:
	@$(MAKE) gtfs-year DRY=1

## Masque un mois réel et mesure l'écart entre l'offre extrapolée et l'offre
## réellement publiée ce mois-là. C'est la seule preuve que le modèle
## d'extrapolation vaut quelque chose. Mesure de référence sur mai 2026 : écart
## maximal 5,3 %, médiane sous 1 %.
##   make gtfs-year-holdout HOLDOUT=202605
gtfs-year-holdout:
	@$(MAKE) gtfs-year RESEAU=tisseo ANNEES=2026 HOLDOUT=$(if $(HOLDOUT),$(HOLDOUT),202605) \
	  SORTIE=/tmp/gtfs_year_holdout

## Extrait du feed annuel la fenêtre que consomment GAMA et le runtime. OTP lit
## l'année entière, GAMA non : son calendrier est un masque binaire 64 bits
## (llm-agents/inputs/gtfs/gama.py, PublicTransport.gaml). La fenêtre DOIT
## contenir la date de simulation, sinon plus aucune course n'est planifiée.
##   make gtfs-window START=2026-03-16 DAYS=64
gtfs-window:
	@$(SYNTHESIS_PYTHON) -m scripts.data.gtfs_year.window_feed \
	  --source $(if $(SOURCE),$(SOURCE),data/gtfs_year/tisseo_2026) \
	  --debut $(if $(START),$(START),2026-03-16) \
	  --jours $(if $(DAYS),$(DAYS),64) \
	  --sortie $(if $(OUT),$(OUT),data/gtfs_year/fenetre_gama) --zip

## Tests unitaires du pipeline de feed annuel. Feeds synthétiques, aucun accès
## réseau, moins d'une seconde. Chaque test porte sur une décision qui, prise à
## l'envers, produit un feed plausible mais faux.
test-gtfs-year:
	@$(SYNTHESIS_PYTHON) -m pytest scripts/tests/test_gtfs_year.py -q

.PHONY: gama-layers gama-trip-info test-gama-includes

## Reconstruit les COUCHES que GAMA dessine — GAMA/CityTransport/includes/routes.shp
## et stops.shp — à partir des trois réseaux du périmètre (Tisséo, TER, liO). Les
## couches précédentes sont déplacées dans un dossier archives_<date>, jamais
## supprimées. `includes/` n'est pas versionné : cette recette est la seule trace.
##   make gama-layers
##   make gama-layers FEEDS="tisseo=data/gtfs/tisseo_gtfs ter=data/gtfs/ter_gtfs"
gama-layers:
	@$(SYNTHESIS_PYTHON) scripts/data/gama/export_gtfs_layers.py \
	  $(foreach f,$(FEEDS),--feed $(f)) \
	  $(if $(OUT),--sortie $(OUT),) $(if $(TOUT),--tout,) $(if $(JSON),--json $(JSON),)

## Reconstruit les COURSES que GAMA fait rouler — GAMA/CityTransport/includes/trip_info.json —
## à partir des trois réseaux et de la date simulée (lue dans Settings.gaml), PUIS la table
## des tracés que lit le runtime (includes/shape_lookup.json).
##
## La table publie la correspondance route_id -> shape_id -> ordre des arrêts que la recette
## a RÉELLEMENT utilisée : c'est elle qui permet à un agent de monter dans un véhicule
## (get_shape_id_from_route_info, puis `shape_id_list contains each.shape_id` côté GAMA).
## Le runtime ne la recalcule pas — le TER ne publie aucune géométrie, ses shape_id sont
## fabriqués ici, et la recette écarte des courses qu'il faudrait sinon réécarter à
## l'identique. Elle note l'empreinte de routes.shp/.dbf et de trip_info.json : refaire
## les couches SEULES la dépareille, et le runtime l'alarme au chargement.
##
## Les couches sont refaites D'ABORD, dans la même recette : `trip_info.json` porte des
## indices de sommets dans la géométrie de `routes.shp`, et produire l'un sans l'autre est
## exactement le défaut qui a duré cinq mois — couches à trois réseaux, courses à un seul,
## 34 lignes de TER dessinées où aucun train ne roulait. `COUCHES=0` saute cette étape
## quand les couches viennent d'être faites.
##
## Contrôles bloquants (le fichier n'est pas écrit s'ils tombent) : la date simulée est
## dans la fenêtre ET servie ; l'étendue des dates tient dans le masque binaire 64 bits de
## GAMA ; chaque course a son tracé dans routes.shp avec le même nombre de points ; aucun
## route_type de la couche n'est sans course le jour simulé.
##   make gama-trip-info
##   make gama-trip-info DATE=2026-03-16 DAYS=64 COUCHES=0
##   make gama-trip-info TABLE=/tmp/shape_lookup.json     # table ailleurs qu'à côté des courses
## Codes de sortie : 0 écrit, 1 ressource absente, 2 invariant démenti.
gama-trip-info:
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make gama-trip-info SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	@if [ "$(COUCHES)" != "0" ]; then $(MAKE) --no-print-directory gama-layers ; fi
	@$(SYNTHESIS_PYTHON) scripts/data/gama/export_trip_info.py \
	  $(foreach f,$(FEEDS),--feed $(f)) \
	  $(if $(DATE),--date-simulee $(DATE),) $(if $(START),--debut $(START),) \
	  $(if $(DAYS),--jours $(DAYS),) $(if $(ROUTES),--routes $(ROUTES),) \
	  $(if $(OUT),--sortie $(OUT),) $(if $(TABLE),--table-traces $(TABLE),) \
	  $(if $(JSON),--json $(JSON),)

## Tests unitaires des deux recettes ci-dessus, dont le contrôle de cohérence
## couches/courses et la table des tracés publiée : feeds synthétiques minimaux, aucun
## gros fichier, aucun accès réseau.
test-gama-includes:
	@$(SYNTHESIS_PYTHON) -m pytest scripts/tests/test_gama_includes.py -q

## Rebuild the fine-zone resource read by mobility_core.zone_resolver.
## Requires the restricted PROGEDO data under 'data/PROGEDO 2023/'.
zones:
	@test -d "data/PROGEDO 2023" || { \
	  echo "Données PROGEDO absentes : data/PROGEDO 2023/ (accès restreint lil-1750)"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.progedo_logit.export_zone_layer

## Rebuild the housing-type law read when enriching a synthetic population (action A2).
## Requires the restricted PROGEDO data under 'data/PROGEDO 2023/'.
## Ticket 019 : la loi est conditionnée à la ZONE FINE et à la TAILLE DU MÉNAGE, et la
## ressource produite est en v2 — le module refuse une v1. L'export publie le test interne
## EMC² et ÉCHOUE si l'erreur du mécanisme dépasse 1 point sur les 20 cellules.
## Puis, pour poser le trait sur une population (aucun appel LLM, déterministe) :
##   llm-agents/.venv/bin/python -m scripts.data.population.enrich_housing_type \
##     data/population/toulouse_population_1000.json --check
## Codes de sortie de --check : 0 tout est dans la tolérance, 1 ressource absente,
## 2 une cible servie est démentie, 3 population enrichie mais trop petite pour trancher.
housing-type:
	@test -d "data/PROGEDO 2023" || { \
	  echo "Données PROGEDO absentes : data/PROGEDO 2023/ (accès restreint lil-1750)"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.progedo_logit.export_housing_type

## Rebuild the bike-ownership model read when enriching a synthetic population
## (ticket 015 : les trois étages k / attribution / VAE appris sur EMC²).
## Requires the restricted PROGEDO data under 'data/PROGEDO 2023/'.
## Il lit aussi la table du type de logement (make housing-type) pour publier la cible
## d'équipement par habitat DILUÉE — la seule opposable à une population synthétique.
## Puis, pour poser le trait sur une population (aucun appel LLM, déterministe) :
##   llm-agents/.venv/bin/python -m scripts.data.population.enrich_personal_bike \
##     data/population/toulouse_population_1000.json --check
bike-ownership:
	@test -d "data/PROGEDO 2023" || { \
	  echo "Données PROGEDO absentes : data/PROGEDO 2023/ (accès restreint lil-1750)"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.progedo_logit.export_bike_ownership

## Rebuild the two equipment-propensity laws read when enriching a population:
## `has_pt_subscription` (ticket 016) and `has_driving_license` (ticket 017).
## Lot 1 commun aux deux tickets : un seul chargeur, deux cibles apprises sur le
## fichier standard `pers` d'EMC² (PENQ = 1, pondération COEP), validation croisée
## GROUPÉE PAR MÉNAGE. Les paliers tarifaires (moins de 26 ans, ouverture senior)
## sont ajustés puis ARBITRÉS sur l'AUC hors-échantillon, pas décrétés.
## Requires the restricted PROGEDO data under 'data/PROGEDO 2023/'.
##   make equipment-propensity DRY_RUN=1   # ajuste et affiche la recette, sans écrire
equipment-propensity:
	@test -d "data/PROGEDO 2023" || { \
	  echo "Données PROGEDO absentes : data/PROGEDO 2023/ (accès restreint lil-1750)"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.progedo_logit.export_equipment_propensity \
	  $(if $(DRY_RUN),--dry-run,)

## Rebuild the EMC²-measured car terminal time (access + parking search) law.
## Requires the restricted PROGEDO data under 'data/PROGEDO 2023/'.
## Ce que ça mesure : T2 (marche au départ), T6 (marche à l'arrivée) et T11 (durée de
## recherche du stationnement) du fichier trajets, par couronne. À comparer aux valeurs
## de llm-agents/config/terminal_time.yaml, mesurées 8x à 24x plus grandes.
terminal-time:
	@test -d "data/PROGEDO 2023" || { \
	  echo "Données PROGEDO absentes : data/PROGEDO 2023/ (accès restreint lil-1750)"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.progedo_logit.export_terminal_time

## Rebuild the "Avancement et résultats" page from the measurement registry.
## Une ligne par mesure FAITE : base de référence → base modifiée → modification → résultat
## → score, chacune retraçable jusqu'à une archive de docs/traces/.
## Le rendu REFUSE (et n'écrit rien) si une trace citée n'existe pas sur le disque, si un
## champ manque ou si un verdict sort du vocabulaire : une page de résultats qui se dégrade
## en silence est pire qu'une page absente. `make avancement CHECK=1` valide sans écrire.
avancement:
	$(SYNTHESIS_PYTHON) -m scripts.synthesis.render_avancement $(if $(CHECK),--check,)

.PHONY: ab-detail
## Détail par sous-catégorie d'un A/B de jeux gelés — un mini-graphe par mode, une
## courbe par bras, plus les tableaux L1. Reconstruit depuis les décisions DÉJÀ dans le
## store : aucun appel LLM. Usage: make ab-detail [DATASET=val|screen]
ab-detail:
	$(SYNTHESIS_PYTHON) -m scripts.synthesis.build_ab_detail --dataset $(if $(DATASET),$(DATASET),val)
	$(if $(DATASET),,$(SYNTHESIS_PYTHON) -m scripts.synthesis.build_ab_detail --dataset screen)

## Rebuild the EMC²-measured household car availability reference (ticket 018).
## Requires the restricted PROGEDO data under 'data/PROGEDO 2023/'.
## Ce que ça mesure : `car_availability` (all / some / none) recalculée avec LA RÈGLE
## D'EQASIM — all si voitures >= permis des majeurs, some si <, none si voitures == 0 —
## depuis M6 (voitures) et P7 (permis). Deux pondérations : ménages (COE0) et personnes
## (COE1), cette dernière étant celle opposable à une population d'agents.
## L'export ÉCHOUE si son contrôle positif ne reproduit pas la motorisation publiée
## (1,25 VP/ménage ; 19 / 45 / 35 %) : une lecture qui rate le parc ne peut pas prétendre
## mesurer sa disponibilité.
car-availability:
	@test -d "data/PROGEDO 2023" || { \
	  echo "Données PROGEDO absentes : data/PROGEDO 2023/ (accès restreint lil-1750)"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.progedo_logit.export_car_availability

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

## Tune the mode-choice booster's hyperparameters → scripts/progedo_logit/mode_choice_tuning.json
## Validation croisée groupée PAR MÉNAGE, entièrement À L'INTÉRIEUR du train : le split
## test n'est jamais lu. N'écrit aucun modèle — le gagnant se reporte à la main dans
## PARAMS de fit_mode_choice_policy.py, puis `make policy`.
##   make policy-tune TUNE_ARGS="--refine --trials 40"   # espace resserré (2e passe)
policy-tune:
	@test -f scripts/progedo_logit/progedo_mode_choice_v2.parquet || { \
	  echo "Jeu d'entraînement absent : scripts/progedo_logit/progedo_mode_choice_v2.parquet"; \
	  exit 1; }
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make policy-tune SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.progedo_logit.tune_mode_choice_policy $(TUNE_ARGS)

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
	  $(if $(DRY_RUN),--dry-run,) $(if $(POLICY),--policy $(POLICY),) $(if $(OUT),--out $(OUT),)

## Estimate the SECOND oracle: multinomial logit at strict parity (21 variables)
## → scripts/progedo_logit/mnl_model.json + mnl_model_metrics.json
## Même jeu, même split par ménage, même sample_weight et mêmes métriques que
## `make policy` : la comparaison des deux oracles ne mesure que les deux modèles.
## La régularisation est choisie en validation croisée groupée DANS le train.
##   make logit C=1.0        # impose C au lieu de le choisir (diagnostic)
logit:
	@test -f scripts/progedo_logit/progedo_mode_choice_v2.parquet || { \
	  echo "Jeu d'entraînement absent : scripts/progedo_logit/progedo_mode_choice_v2.parquet"; \
	  echo "Il est versionné ; s'il manque, régénérez-le avec build_mode_choice_dataset.py"; \
	  exit 1; }
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make logit SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.progedo_logit.fit_mode_choice_logit $(if $(C),--C $(C),)

## Apply the SECOND oracle to the pinned common set (same code path as the booster)
## → scripts/synthesis/data/mnl_on_common_set.parquet
mnl-predict:
	@$(MAKE) --no-print-directory common-set-predict \
	  POLICY=scripts/progedo_logit/mnl_model.json \
	  OUT=scripts/synthesis/data/mnl_on_common_set.parquet

## Two-oracle composite score → scripts/synthesis/data/bi_oracle.json
## Bloc A fidélité EMC² (inchangé), bloc B accord désagrégé au logit rapporté à la
## distance inter-oracles, bloc C sens de variation. Poids B et C à 0 : les termes sont
## publiés, ils ne sélectionnent aucun prompt. Aucun appel LLM, aucun réseau.
## Prérequis : make logit && make common-set-predict && make mnl-predict
bi-oracle:
	@test -x $(SYNTHESIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(SYNTHESIS_PYTHON)"; \
	  echo "Surchargez-le : make bi-oracle SYNTHESIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	$(SYNTHESIS_PYTHON) -m scripts.synthesis.bi_oracle

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
## Usage: make run [EXPERIMENT_NAME=e] [OFFLINE=1]
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
ifneq ($(MEM),)
	@perl -pi -e 's/^long_term_memory_enabled:.*/long_term_memory_enabled: $(if $(filter 0,$(MEM)),false,true)/; s/^long_term_self_reflect_enabled:.*/long_term_self_reflect_enabled: $(if $(filter 0,$(MEM)),false,true)/' $(SIM_PARAMS)
	@echo "🧠 Mémoire des agents (LTM + auto-réflexion) : $(if $(filter 0,$(MEM)),DÉSACTIVÉE,activée) — écrit dans $(SIM_PARAMS)"
endif
ifneq ($(CACHE),)
	@perl -0pi -e 's/^(cache:\n(?:.*\n)*?\s*enabled:).*/$$1 $(if $(filter 0,$(CACHE)),false,true)/m' $(APP_CONFIG)
	@echo "💾 Cache sémantique LLM : $(if $(filter 0,$(CACHE)),DÉSACTIVÉ — chaque décision sera journalisée (~4x plus d'appels),activé) — écrit dans $(APP_CONFIG)"
endif
ifneq ($(JEU),)
	@# Ticket 035 (spec 04, G2) : la simulation consomme le jeu enregistré data/jeux/$(JEU) —
	@# régime nominal sans appel moteur. Écrit `data.jeu_enregistre` dans $(APP_CONFIG) ; les
	@# tolérances horaires doivent y être déclarées (bloc commenté).
	@test -f data/jeux/$(JEU)/MANIFEST.yaml || { echo "❌ Jeu introuvable : data/jeux/$(JEU)/MANIFEST.yaml (préparez-le : make jeu POP=… NOM=$(JEU))"; exit 1; }
	@grep -q '^  jeu_tolerances_horaires:' $(APP_CONFIG) || { echo "❌ data.jeu_tolerances_horaires n'est pas déclaré dans $(APP_CONFIG) — décommentez et validez le bloc (spec 04, G5)"; exit 1; }
	@perl -0pi -e 's/^  #? ?jeu_enregistre:.*\n//m; s/^(data:\n)/$$1  jeu_enregistre: \/app\/data\/jeux\/$(JEU)\n/m' $(APP_CONFIG)
	@echo "📼 Jeu enregistré : data/jeux/$(JEU) — écrit dans $(APP_CONFIG)"
else
	@if grep -q '^  jeu_enregistre:' $(APP_CONFIG); then \
		perl -0pi -e 's/^  jeu_enregistre:.*\n//m' $(APP_CONFIG); \
		echo "📼 Aucun jeu désigné : calcul en vol (data.jeu_enregistre retiré de $(APP_CONFIG))"; \
	fi
endif
	@$(MAKE) up
	@# Les réglages de $(APP_CONFIG) sont lus au DÉMARRAGE du contrôleur, jamais à chaud : tant que
	@# le fichier diffère de la copie appliquée au dernier lancement (.config.yaml.applique), le
	@# contrôleur est recréé — CACHE=, JEU= et toute édition manuelle prennent ainsi effet
	@# (décision de l'auteur du 2026-09-06, question 17 du ticket 035).
	@if ! cmp -s $(APP_CONFIG) .config.yaml.applique; then \
		echo "♻️  $(APP_CONFIG) a changé depuis le dernier lancement : recréation du contrôleur"; \
		docker compose up -d --force-recreate --no-deps controller && cp $(APP_CONFIG) .config.yaml.applique; \
	fi
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

.PHONY: run-offline
## Alias : make run-offline == make run OFFLINE=1
run-offline:
	@$(MAKE) run OFFLINE=1

## ── Plateforme d'expériences (ticket 035) ──────────────────────────────────────────────
## Tout passe par `python -m experiences` dans le conteneur controller (services requis pour
## préparer un jeu — OTP/OSMnx — et pour un décideur passerelle ; un décideur local n'a besoin
## de rien). Design : docs/arch/plateforme-experiences.md.
EXPERIENCES_PY = docker compose exec -T -e EXPERIENCES_DIR=/app/data/experiences -e JEUX_DIR=/app/data/jeux -e REFERENTIEL_ENQUETE=/app/scripts/data/population/cerema_values.yaml controller python -m experiences

## Prépare un jeu de déplacements enregistré. Usage : make jeu POP=data/population/population_1000_AAMAS_v5 NOM=v5_j1 [JOUR=2026-03-16] [CONCURRENCE=8] [REQUIS="…"]
## Les moteurs de routage (défaut : controller otp1 otp2 otp3 osmnx1) sont démarrés et attendus sains d'abord.
jeu:
	@test -n "$(POP)" -a -n "$(NOM)" || { echo "Usage : make jeu POP=<dossier ou fichier population> NOM=<nom du jeu> [JOUR=AAAA-MM-JJ]"; exit 1; }
	@mkdir -p data/jeux
	@$(MAKE) --no-print-directory services-pretes REQUIS="$(if $(REQUIS),$(REQUIS),controller otp1 otp2 otp3 osmnx1)"
	$(EXPERIENCES_PY) preparer-jeu --population $(POP:data/population/%=/data/eqasim-output/%) --nom $(NOM) $(if $(JOUR),--jour $(JOUR),) $(if $(CONCURRENCE),--concurrence $(CONCURRENCE),)

## Consulte un jeu : make jeu-consulter NOM=v5_j1 [PERSONNE=418]
jeu-consulter:
	$(EXPERIENCES_PY) consulter-jeu --nom $(NOM) $(if $(PERSONNE),--personne $(PERSONNE),)

## Vérifie la péremption d'un jeu : make jeu-verifier NOM=v5_j1
jeu-verifier:
	$(EXPERIENCES_PY) verifier-jeu --nom $(NOM)

## L'offre TC d'un autre jour est-elle celle du jeu ? METHODE=gtfs (défaut : les courses proposées
## existent-elles ce jour dans les feeds, validité par déplacement, aucun service requis) ou
## METHODE=moteurs (OTP sur un échantillon). DECLARER=1 écrit EQUIVALENCES.yaml à côté du jeu.
## make jeu-verifier-jours NOM=v5_j1 JOUR=2026-03-17 [METHODE=gtfs|moteurs] [ECHANTILLON=100] [DECLARER=1]
jeu-verifier-jours:
	$(EXPERIENCES_PY) verifier-jours --nom $(NOM) --jour $(JOUR) $(if $(METHODE),--methode $(METHODE),) $(if $(ECHANTILLON),--echantillon $(ECHANTILLON),) $(if $(DECLARER),--declarer,)

## Recharge la passerelle LLM (api + worker) — nécessaire après un ajout dans mobility_llm/src/mobility_llm/prompts/prompts.yaml
passerelle-recharger:
	docker compose restart api worker

## LM Studio (modèles locaux, hôte) — charge un modèle avec un contexte suffisant pour la passerelle.
## LM Studio charge à 4 096 jetons par défaut : trop court pour un lot de 2 agents (~4 400 de prompt + réponse).
## L'identifiant est celui de `lms ls` (ex. mistralai/mistral-small-3.2) = default_model dans providers.yaml.
## IDENTIFIANT=<alias> charge le modèle sous un autre nom d'API : requis quand le même identifiant existe chez
## un fournisseur distant (qwen/qwen3.8-27b est aussi servi par Groq) — l'alias est alors le default_model local.
## RECHARGER=1 décharge d'abord ce qui est en mémoire sous ce nom (contexte trop court, mauvais identifiant).
## Usage : make lmstudio-charger MODELE=mistralai/mistral-small-3.2 [CTX=16384] [RECHARGER=1]
##         make lmstudio-charger MODELE=qwen/qwen3.8-27b IDENTIFIANT=qwen3.8-27b-local
LMS ?= $(shell command -v lms 2>/dev/null || echo $(HOME)/.lmstudio/bin/lms)
CTX ?= 16384
lmstudio-charger:
	@test -n "$(MODELE)" || { echo "❌ MODELE= requis (identifiant tel que 'lms ls' le donne, ex. mistralai/mistral-small-3.2)"; exit 1; }
	@command -v $(LMS) >/dev/null || { echo "❌ CLI '$(LMS)' introuvable — installez-la depuis LM Studio (Developer → lms) ou passez LMS=/chemin/vers/lms"; exit 1; }
	@if [ -n "$(RECHARGER)" ]; then \
	  for id in "$(or $(IDENTIFIANT),$(MODELE))" $(if $(IDENTIFIANT),"$(MODELE)",); do \
	    if $(LMS) ps 2>/dev/null | awk '{print $$1}' | grep -q -x -F "$$id"; then echo "⏏️  Déchargement de $$id…"; $(LMS) unload "$$id"; fi; \
	  done; \
	fi
	@if $(LMS) ps 2>/dev/null | awk '{print $$1}' | grep -q -x -F "$(or $(IDENTIFIANT),$(MODELE))"; then \
	  echo "ℹ️  $(or $(IDENTIFIANT),$(MODELE)) est déjà chargé — pour changer son contexte : relancer avec RECHARGER=1"; \
	else \
	  echo "⏳ Chargement de $(MODELE) sous l'identifiant $(or $(IDENTIFIANT),$(MODELE)) (contexte $(CTX) jetons)…"; \
	  $(LMS) load "$(MODELE)" -c $(CTX) -y $(if $(IDENTIFIANT),--identifier "$(IDENTIFIANT)",); \
	fi
	@$(LMS) ps

## Décharge un modèle de LM Studio (rend la mémoire) : make lmstudio-decharger MODELE=<identifiant chargé, colonne IDENTIFIER de `lms ps`>
lmstudio-decharger:
	@test -n "$(MODELE)" || { echo "❌ MODELE= requis (identifiant chargé, colonne IDENTIFIER de 'lms ps')"; exit 1; }
	@command -v $(LMS) >/dev/null || { echo "❌ CLI '$(LMS)' introuvable — installez-la depuis LM Studio (Developer → lms) ou passez LMS=/chemin/vers/lms"; exit 1; }
	$(LMS) unload "$(MODELE)"
	@$(LMS) ps

## État LM Studio : modèles chargés (identifiant, contexte) et instances lmstudio_* vues par la passerelle
lmstudio-etat:
	@command -v $(LMS) >/dev/null && $(LMS) ps || echo "CLI lms introuvable"
	@echo "— Passerelle (/health), instances lmstudio_* :"
	@curl -sf localhost:8000/health | python3 -c "import sys,json; p=json.load(sys.stdin).get('providers',{}); [print(f'  {k:36s} available={v.get(\"available\")}  rpm={v.get(\"current_rpm\")}') for k,v in sorted(p.items()) if k.startswith('lmstudio_')] or print('  aucune instance lmstudio_* (PROVIDER_KEYS__lmstudio absent de .env ? make passerelle-recharger ?)')" || echo "  passerelle injoignable (make up ?)"

## Valide et range une expérience : make experience-definir FICHIER=chemin/experience.yaml
experience-definir:
	$(EXPERIENCES_PY) definir $(FICHIER)

## Estime le coût avant lancement : make experience-estimer EXP=<nom>
experience-estimer:
	$(EXPERIENCES_PY) estimer --experience $(EXP)

## Lance (ou reprend avec REPRENDRE=1) une expérience sans simulateur : make experience-lancer EXP=<nom> [REPRENDRE=1] [REQUIS="controller api worker"] [ACCEPTER_PERIME=1] [ATTENDRE_FENETRE=1]
## Les services de REQUIS (défaut : `controller`) sont démarrés et attendus sains avant le lancement.
## ATTENDRE_FENETRE=1 : à l'épuisement du quota, dort en process jusqu'à minuit UTC puis repart seul (R4).
experience-lancer:
	@mkdir -p data/experiences
	@$(MAKE) --no-print-directory services-pretes REQUIS="$(if $(REQUIS),$(REQUIS),controller)"
	$(EXPERIENCES_PY) lancer --experience $(EXP) $(if $(REPRENDRE),--reprendre,) $(if $(ACCEPTER_PERIME),--accepter-perime,) $(if $(ATTENDRE_FENETRE),--attendre-fenetre,)

experience-reprendre:
	@$(MAKE) experience-lancer EXP=$(EXP) REPRENDRE=1 REQUIS="$(REQUIS)"

## File d'attente par clé (spec parallelisation_experiences) :
## experience-file            expériences en attente d'une clé (FIFO)
## experience-actives         expériences qui tiennent une clé (parallèle en cours)
## experience-defiler EXP=<n> retire une expérience de la file avant sa promotion
experience-file:
	$(EXPERIENCES_PY) file
experience-actives:
	$(EXPERIENCES_PY) actives
experience-defiler:
	$(EXPERIENCES_PY) defiler --experience $(EXP)

## Ordonnanceur (HÔTE) : réconcilie les fantômes et démarre les expériences en file dès qu'une
## clé se libère. À laisser tourner (le tableau de bord le supervise aussi). Ctrl-C pour arrêter.
experience-ordonnancer:
	cd llm-agents && .venv/bin/python -m experiences ordonnancer $(if $(INTERVALLE),--intervalle $(INTERVALLE),)

## Pause / arrêt propre de l'exécution en cours : make experience-pause EXP=<nom> · make experience-arreter EXP=<nom>
experience-pause:
	$(EXPERIENCES_PY) pause --experience $(EXP)
experience-arreter:
	$(EXPERIENCES_PY) arreter --experience $(EXP)

## Rapproche decisions.jsonl du jeu (aucun déplacement sauté ?) : make experience-erreurs EXP=<nom> [EXEC=<dossier>]
experience-erreurs:
	$(EXPERIENCES_PY) erreurs $(if $(EXEC),$(EXEC),--experience $(EXP))

## Aligne les noms d'expériences sur leurs paramètres (spec nommage-canonique-experiences) :
##   make experiences-renommer                            vérifie et dit ce qui bougerait
##   make experiences-renommer APPLIQUER=1 FUSIONNER=1     renomme, et réunit les définitions identiques
experiences-renommer:
	$(PKG_PYTHON) scripts/migrations/renommer_experiences.py $(if $(APPLIQUER),--appliquer,) $(if $(FUSIONNER),--fusionner,)

## Registre des expériences et exécutions : make registre [TRIER=couverture] [FILTRER=decideur=gemini] [TOUT=1]
## TOUT=1 réaffiche les expériences archivées ou invalidées (masquées par défaut).
registre:
	$(EXPERIENCES_PY) registre $(if $(TRIER),--trier $(TRIER),) $(if $(FILTRER),--filtrer $(FILTRER),) $(if $(TOUT),--inclure-masquees,)

## Statut de toutes les expériences (masquées comprises) : make experience-statuts
experience-statuts:
	$(EXPERIENCES_PY) statuts

## Pose le statut d'une expérience SANS RIEN SUPPRIMER ni déplacer :
##   make experience-statuer EXP=<nom> STATUT=archivee|invalide|actif MOTIF="..." [REF=specs/x.md]
## Les exécutions, traces, scores et empreintes restent sur le disque ; seule la visibilité change.
experience-statuer:
	@test -n "$(EXP)" || (echo "ERREUR : EXP=<nom d'expérience> manquant" >&2; exit 2)
	@test -n "$(STATUT)" || (echo "ERREUR : STATUT=archivee|invalide|actif manquant" >&2; exit 2)
	$(EXPERIENCES_PY) statuer $(EXP) $(STATUT) $(if $(MOTIF),--motif "$(MOTIF)",) $(if $(REF),--reference $(REF),)

## Compare deux exécutions (refuse si non comparables) : make comparer A=<dossier> B=<dossier> [TOUT=1]
## Refuse aussi d'apparier une expérience invalidée ou archivée ; TOUT=1 force en rappelant le motif.
comparer:
	$(EXPERIENCES_PY) comparer $(A) $(B) $(if $(TOUT),--inclure-invalides,)

.PHONY: services-pretes passerelle-recharger jeu jeu-consulter lmstudio-charger lmstudio-decharger lmstudio-etat jeu-verifier jeu-verifier-jours experience-definir experience-estimer experience-lancer experience-reprendre experience-pause experience-arreter experience-erreurs experience-file experience-actives experience-defiler experience-ordonnancer experiences-renommer registre comparer experience-statuts experience-statuer

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

.PHONY: status
## Statut du run GAMA en cours. Sortie parsable clé=valeur :
## run=actif|inactif, mode=offline|ihm, pid, current=<cible du symlink experiments/current>
status:
	@if pgrep -f "launch_headless.py" > /dev/null; then \
		echo "run=actif mode=offline pid=$$(pgrep -f launch_headless.py | head -1)"; \
	elif pgrep -f "$(GAMA_BIN)" > /dev/null; then \
		echo "run=actif mode=ihm pid=$$(pgrep -f "$(GAMA_BIN)" | head -1)"; \
	else \
		echo "run=inactif"; \
	fi
	@echo "current=$$(readlink experiments/current 2>/dev/null || echo '-')"

.PHONY: stop-run
## Arrête le run GAMA en cours SANS toucher au reste de la pile (api, worker, redis…).
## Offline : tue le launcher dans le conteneur controller puis stoppe le service gama
## (GAMA Server tue l'expérience dont le client s'est déconnecté). IHM : SIGTERM à GAMA.
## Pour tout arrêter, y compris les services : make down.
stop-run:
	@if docker compose ps --status running controller 2>/dev/null | grep -q controller; then \
		docker compose exec -T controller pkill -f launch_headless.py 2>/dev/null || true; \
	fi
	-@pkill -f "scripts/gama/launch_headless.py" 2>/dev/null || true
	-@docker compose --profile offline stop gama 2>/dev/null || true
	-@pkill -f "$(GAMA_BIN)" 2>/dev/null || true
	@echo "✅ Run arrêté. Les services restent en place (make down pour tout couper)."
