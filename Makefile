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

# ── Mémoire des agents ─────────────────────────────────────────────────────────
# `make run MEM=0` : coupe la mémoire long terme ET l'auto-réflexion ;
# `make run MEM=1` : les réactive. Sans MEM, le fichier n'est pas touché.
# ⚠ Le levier est GAMA/CityTransport/config/sim_params.yaml, PAS l'injection de
# paramètres GAMA Server : Settings.gaml (load_sim_config, cycle 1) écrase les
# paramètres injectés avec le contenu de ce fichier. Le réglage est PERSISTANT
# (le fichier est réécrit à cycle 2) : il vaut aussi pour les runs GUI suivants.
MEM ?=
SIM_PARAMS = GAMA/CityTransport/config/sim_params.yaml

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

# ──────────────────────────────────────────────────────────────────────────────
# Modèle de choix modal (ticket 005)
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: zones housing-type bike-ownership terminal-time car-availability avancement policy common-set-predict
.PHONY: communes-couronnes audit-perimetre audit-couronnes residence-zone couronne-v7

## ──────────────────────────────────────────────────────────────────────────────
## Périmètre de population (ticket 020)
## ──────────────────────────────────────────────────────────────────────────────

## Rebuild the commune → couronne table and the couronne geometry (ticket 020, lot 3).
## Requires the restricted PROGEDO data under 'data/PROGEDO 2023/'.
## C'est la DONNÉE MANQUANTE du ticket : l'enquête découpe ses couronnes par LISTE DE
## COMMUNES (1 / 69 / 108 / 275), là où `geo_reference.residence_zone` classe par
## distance à l'hypercentre. Produit llm_module/data/commune_couronne.json et
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

## Rebuild the fine-zone resource read by llm_module.core.zone_resolver.
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

## Détail par sous-catégorie d'un A/B de jeux gelés — un mini-graphe par mode, une
## courbe par bras, plus les tableaux L1. Reconstruit depuis les décisions DÉJÀ dans le
## store : aucun appel LLM. Usage: make ab-detail [DATASET=val|screen]
.PHONY: ab-detail
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
ifneq ($(MEM),)
	@perl -pi -e 's/^long_term_memory_enabled:.*/long_term_memory_enabled: $(if $(filter 0,$(MEM)),false,true)/; s/^long_term_self_reflect_enabled:.*/long_term_self_reflect_enabled: $(if $(filter 0,$(MEM)),false,true)/' $(SIM_PARAMS)
	@echo "🧠 Mémoire des agents (LTM + auto-réflexion) : $(if $(filter 0,$(MEM)),DÉSACTIVÉE,activée) — écrit dans $(SIM_PARAMS)"
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

## ── Jeton d'exclusion du protocole exogène (ticket 023) ─────────────────────
## Aucune procédure du protocole (A/B, réécriture de jeu, archivage) ne doit tourner
## pendant qu'un run consomme le même quota LLM : si la cascade de fournisseurs bascule
## entre deux bras, ils n'ont pas été évalués par le même modèle, et l'écart mesuré est
## confondu avec le traitement.
## ⚠ Ce verrou est LOCAL : il n'atteint pas la campagne génétique de la VM cloud. D'où
## CLOUD_PAUSED=1, qui est une liste de contrôle humaine et non une garantie.
.PHONY: protocol-lock protocol-unlock protocol-status

## État du jeton et des sondes qui empêcheraient une prise. Usage: make protocol-status [JSON=1]
protocol-status:
	@python3 scripts/protocol_lock.py status $(if $(JSON),--json,)

## Prend le jeton. Usage: make protocol-lock SUBJECT="ticket 023 — A/B météo" CLOUD_PAUSED=1 [MINUTES=90] [STEAL=1]
protocol-lock:
	@test -n "$(SUBJECT)" || { echo "[REFUS] SUBJECT est obligatoire — un jeton anonyme ne se débloque pas sans risque."; exit 2; }
	@python3 scripts/protocol_lock.py acquire --subject "$(SUBJECT)" \
	  $(if $(MINUTES),--expected-minutes $(MINUTES),) \
	  $(if $(CLOUD_PAUSED),--cloud-paused,) $(if $(STEAL),--steal-orphan,)

## Relâche le jeton et enregistre le second instantané de quota. Usage: make protocol-unlock [FORCE=1]
protocol-unlock:
	@python3 scripts/protocol_lock.py release $(if $(FORCE),--force,)

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
