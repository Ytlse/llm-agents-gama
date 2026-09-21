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
# ⚠ Le `mkdir -p` qui suit le `rm -rf` n'est pas cosmétique : Prometheus refuse de démarrer
# si son point de montage n'existe pas, et la métrologie manquait alors tout le run.
run:
	@# Ticket 089 — le run precedent est arrete AVANT tout le reste, et pour TOUS les
	@# lancements, reprise a chaud comprise. Sans cela le conteneur GAMA reste debout et
	@# chaque lancement charge le modele dans le processus deja en place : le
	@# 2026-09-16, deux City.gaml residents dans la meme JVM plafonnee a 12 Go ont fait
	@# tuer le conteneur par sa propre limite au jour 1. Ce qui pese est le territoire
	@# (453 communes, reseau complet), pas le nombre d'agents.
	@echo "🛑 Arret du run precedent avant lancement (GAMA garderait sinon son experiment en memoire)..."
	@$(MAKE) stop-run
ifeq ($(CONT),)
	echo "🗑️  Arrêt de Grafana et Prometheus..."; \
	$(COMPOSE) stop grafana prometheus 2>/dev/null || true; \
	$(COMPOSE) rm -f grafana prometheus 2>/dev/null || true; \
	echo "🗑️  Suppression des données Grafana et Prometheus..."; \
	rm -rf data/grafana_data data/prometheus_data; \
	mkdir -p data/grafana_data data/prometheus_data; \
	echo "🗑️  Purge des compteurs Redis (wmetrics:)..."; \
	$(COMPOSE) exec -T redis redis-cli --scan --pattern "wmetrics:*" | xargs -r $(COMPOSE) exec -T redis redis-cli del 2>/dev/null || true; \
	echo "♻️  Arrêt du contrôleur pour un démarrage à neuf..."; \
	$(COMPOSE) stop controller 2>/dev/null || true; \
	$(COMPOSE) rm -f controller 2>/dev/null || true;

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
ifneq ($(CHOC),)
	@# Ticket 079 : le choc vit dans son propre fichier, comme la loi BAAC des accidents.
	@# `CHOC=0` retire la déclaration ; tout autre nom la pose après avoir vérifié qu'elle existe.
ifeq ($(CHOC),0)
	@perl -0pi -e 's/^chocs:\n(?:[ \t]+.*\n)*//m' $(APP_CONFIG)
	@echo "⚡ Choc : AUCUN — retiré de $(APP_CONFIG)"
else
	@test -f $(CHOCS_DIR)/$(CHOC).yaml || { echo "❌ Choc introuvable : $(CHOCS_DIR)/$(CHOC).yaml (les cas livrés : $$(ls $(CHOCS_DIR)/*.yaml | xargs -n1 basename | sed 's/.yaml//' | tr '\n' ' '))"; exit 1; }
	@perl -0pi -e 's/^chocs:\n(?:[ \t]+.*\n)*//m' $(APP_CONFIG)
	@printf 'chocs:\n  enabled: true\n  fichier: /app/config/chocs/%s.yaml\n' "$(CHOC)" >> $(APP_CONFIG)
	@echo "⚡ Choc : $(CHOC) — écrit dans $(APP_CONFIG)$(if $(filter 0,$(CACHE)),, ⚠ pensez à CACHE=0)"
endif
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
		$(COMPOSE) up -d --force-recreate --no-deps controller && cp $(APP_CONFIG) .config.yaml.applique; \
	else \
		cp $(APP_CONFIG) .config.yaml.applique 2>/dev/null || true; \
	fi
	@$(MAKE) wait-ready
ifneq ($(OFFLINE),)
	@if pgrep -f "launch_headless.py" > /dev/null; then \
		echo "⚠️  Un launcher GAMA headless tourne déjà. Lancement ignoré."; \
	else \
		echo "🚀 Lancement headless de l'expérience GAMA : $(EXPERIMENT_NAME) (GAMA Server, conteneur gama)..."; \
		mkdir -p experiments/current; \
		$(COMPOSE) exec -T -e GAMA_EXPERIMENT=$(EXPERIMENT_NAME) controller \
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
