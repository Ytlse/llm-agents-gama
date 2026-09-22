# ──────────────────────────────────────────────────────────────────────────────
# Docker Compose
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: up down restart rebuild logs ps clean purge-cache

up:
	$(COMPOSE) up -d

# --profile offline : inclut le service gama (mode headless) s'il tourne ;
# sans effet quand il n'est pas lancé.
down:
	$(COMPOSE) --profile offline down

restart:
	$(COMPOSE) restart

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
	$(COMPOSE) stop $(SERVICES)

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
		$(COMPOSE) stop $(SERVICES); \
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
	$(COMPOSE) --profile offline stop $(SERVICES) gama; \
	exit $$code

.PHONY: up-services services-pretes
## Démarre SEULEMENT les services nommés, avec leurs dépendances du compose : une expérience
## n'a pas besoin du monitoring (Prometheus, Grafana, cAdvisor, node-exporter, Flower). Ne
## rend pas la main sur des services sains — pour cela, voir `services-pretes`.
## Usage: make up-services SERVICES="controller api worker"
up-services:
	@test -n "$(SERVICES)" || { echo "SERVICES= est vide : nommez les services à démarrer"; exit 2; }
	$(COMPOSE) up -d $(SERVICES)

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
	$(COMPOSE) up -d --no-recreate --wait --wait-timeout $(if $(ATTENTE),$(ATTENTE),600) $(REQUIS)

## Rebuild all images from scratch and restart
rebuild:
	$(COMPOSE) build --no-cache
	$(COMPOSE) up -d

## Rebuild and restart api + worker + controller only
api:
	$(COMPOSE) up --build api worker controller

## Rebuild and restart otp + worker only
otp:
	$(COMPOSE) up --build otp worker

.PHONY: otp-graph
## Construit le graphe OTP (data/gtfs/graph.obj) en partant des configurations VERSIONNÉES.
## `data/gtfs/` est un répertoire de travail non versionné : sans cette recopie, une
## reconstruction perd les réglages de `services/otp-toulouse/toulouse/*.json` sans le dire — c'est
## arrivé le 2026-09-04 (embedRouterConfig, boardingLocationTags, staticParkAndRide et
## maxStopToShapeSnapDistance perdus, donc des instances tournant sur les défauts d'OTP).
## L'ancien graphe est archivé, jamais écrasé.  Usage: make otp-graph
otp-graph:
	@test -f data/gtfs/Toulouse.osm.pbf || { echo "data/gtfs/Toulouse.osm.pbf manquant"; exit 1; }
	@cp -v services/otp-toulouse/toulouse/build-config.json services/otp-toulouse/toulouse/router-config.json \
	       services/otp-toulouse/toulouse/otp-config.json data/gtfs/
	@if [ -f data/gtfs/graph.obj ]; then \
	  d=data/gtfs/archives/$$(date +%Y-%m-%d_%H-%M)_pre_build ; mkdir -p $$d ; \
	  mv -v data/gtfs/graph.obj $$d/ ; fi
	java -Xmx4G -jar services/otp-toulouse/bin/otp-shaded-*.jar --build data/gtfs --save
	@ls -l data/gtfs/graph.obj && shasum -a 256 data/gtfs/graph.obj

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

error:
	python3 scripts/errors.py $(if $(LOG),$(LOG),experiments/current/app.log)

warning:
	python3 scripts/warnings.py $(if $(LOG),$(LOG),experiments/current/app.log)

## Marqueurs d'écriture générée dans les chapitres de l'article. Usage: make paper-style [F=docs/paper/article/fr/03_Architecture.md]
paper-style:
	python3 scripts/paper/detecter_artefacts_ia.py $(if $(F),--fichier $(F),)

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

.PHONY: personas-verifier
## Vérifie qu'une population de personas est bien celle que son MANIFEST décrit (ticket 093).
## Usage: make personas-verifier [POP=data/population/population_10_mesurables_093]
# Empreinte du fichier, effectif, et existence + empreinte de la source dont il est tiré. Ce
# n'est PAS un sceau AAMAS (pas de strates ni de marges — elles n'ont aucun sens à dix agents) :
# c'est la garantie qu'une population retouchée à la main cesse de se réclamer d'un critère mesuré.
personas-verifier:
	$(VENV_PYTHON) -m scripts.data.population.selectionner_personas_mesurables \
		--verifier "$(if $(POP),$(POP),data/population/population_10_mesurables_093)"

.PHONY: mesures
## Recalcule les CSV de mesures par jour simulé d'un run (ticket 093). Usage: make mesures RUN=experiments/archive/<date> [OUT=…]
# Les CSV vivent dans <run>/mesures/ et survivent à l'arrêt des conteneurs. Le calcul est
# idempotent sur les FLUX (tout est réécrit depuis moves.csv dédupliqué) et conserve les ÉTATS
# déjà écrits : un état ne se reconstitue pas après coup, et le rejeu d'une reprise écrase les
# points de reprise des journées déjà vécues.
mesures:
	@test -n "$(RUN)" || { echo "Usage: make mesures RUN=experiments/archive/<date>"; exit 2; }
	$(VENV_PYTHON) -m scripts.analysis.mesures "$(RUN)" $(if $(OUT),-o "$(OUT)",)

.PHONY: mesures-continuite
## Vérifie qu'une coupure n'a pas trahi les courbes (ticket 093, recette). Usage: make mesures-continuite AVANT=<copie des CSV> APRES=<run>/mesures
# Sortie non nulle si une clé est dédoublée, un jour ouvré manquant, ou si une valeur d'un jour
# ANTÉRIEUR à la coupure a changé. Le mode d'emploi de la recette est dans docs/arch/mesures-personas.md.
mesures-continuite:
	@test -n "$(AVANT)" -a -n "$(APRES)" || { echo "Usage: make mesures-continuite AVANT=<copie> APRES=<run>/mesures"; exit 2; }
	$(VENV_PYTHON) -m scripts.analysis.mesures.continuite "$(AVANT)" "$(APRES)"

.PHONY: personas-mesurables
## Choisit des personas dont les décisions sont observables, depuis un run déjà joué (ticket 093).
## Usage: make personas-mesurables RUN=data/experiences/<exp>/executions/<date> [SOURCE=…] [SORTIE=…] [CONSERVER=899549,616478] [N=10]
# Le critère (≥ 4 trajets, TOUJOURS plus d'un itinéraire, ≥ 2 modes choisis) se mesure AVANT le
# run à observer : la sélection est donc reproductible et opposable, et le MANIFEST nomme le run
# de référence — un même agent peut satisfaire le critère sur un run et le manquer sur un autre.
personas-mesurables:
	@test -n "$(RUN)" || { echo "Usage: make personas-mesurables RUN=<répertoire d'un run joué>"; exit 2; }
	$(VENV_PYTHON) -m scripts.data.population.selectionner_personas_mesurables \
		--run "$(RUN)" \
		--source "$(if $(SOURCE),$(SOURCE),data/population/population_1000_AAMAS_v6/population.json)" \
		--sortie "$(if $(SORTIE),$(SORTIE),data/population/population_10_mesurables_093)" \
		--conserver "$(if $(CONSERVER),$(CONSERVER),899549,616478)" \
		-n $(if $(N),$(N),10)

.PHONY: memoire-rapport
## Rapport HTML par persona sur un run de mémoire (ticket 077, lot F). Usage: make memoire-rapport RUN=experiments/archive/2026-09-14_23_58
# La sortie vit sous docs/traces/<date_heure>_rapport_memoire/, hors git : c'est une
# trace d'analyse datée, pas un livrable versionné (décision 2026-09-02).
memoire-rapport:
	@test -n "$(RUN)" || { echo "Usage: make memoire-rapport RUN=experiments/archive/<date>"; exit 2; }
	@out="docs/traces/$$(date +%Y-%m-%d_%H-%M)_rapport_memoire"; \
	mkdir -p "$$out"; \
	$(VENV_PYTHON) -m scripts.analysis.memoire.rapport "$(RUN)" -o "$$out/rapport.html"

.PHONY: providers provider
## Met à jour config/llm_gateway/providers.yaml depuis les quotas réels (headers x-ratelimit + Cloud Quotas Google). Usage: make providers [PROVIDER=groq] [DRY_RUN=1]
providers:
	$(VENV_PYTHON) scripts/providers/refresh.py $(if $(DRY_RUN),--dry-run,) $(if $(PROVIDER),--provider $(PROVIDER),)

provider: providers

## Remove containers, volumes and images
clean:
	@read -rp "Voulez-vous supprimer toutes les images Docker ? (y/N): " ans; \
	if [ "$$ans" = "y" ] || [ "$$ans" = "Y" ] || [ "$$ans" = "yes" ] || [ "$$ans" = "YES" ]; then \
		$(COMPOSE) down -v --rmi all; \
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
	@echo "🗑️  Cache OSMnx local (services/llm-agents/osmnx_cache)..."
	rm -f services/llm-agents/osmnx_cache/*.pkl
	@echo "🗑️  Cache scripts OSMnx (scripts/general/cache)..."
	rm -f scripts/general/cache/*.pkl
	@echo "🗑️  Cache pipeline eqasim (services/eqasim-toulouse/cache)..."
	rm -rf services/eqasim-toulouse/cache/*.cache
	@echo "🗑️  Cache eqasim (data/cache/eqasim) + population générée (data/population)..."
	rm -rf data/cache/eqasim/*.cache
	rm -f data/population/*.json
	@echo "🗑️  Cache RAPTOR/Solari..."
	rm -f services/llm-agents/raptor_cache.pickle
	@echo "✅ Tous les caches purgés."
