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
WORKSPACE       = /Users/yvesb/Documents/llm-agents-gama/GAMA/CityTransport
MODEL_PATH      = $(WORKSPACE)/models/City.gaml
EXPERIMENT_NAME = e

# ──────────────────────────────────────────────────────────────────────────────
# Docker Compose
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: up down restart rebuild logs ps clean

up:
	docker compose up -d

down:
	docker compose down

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

## Remove containers, volumes and images
clean:
	docker compose down -v --rmi all
	docker system prune -a --volumes -f

clean_all:
	docker ps -aq | xargs -r docker rm -f
	docker system prune -a -f --volumes

# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: tests burst

tests:
	python llm_module/tests/test_main.py

burst:
	python llm_module/tests/test_e2e.py --scenario 1 --burst 80

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
## Usage: make run [CONFIG=my_config.yaml] [EXPERIMENT_NAME=e]
run:
	@read -p "Voulez-vous supprimer l'historique Prometheus/Grafana ? (y/N) : " ans; \
	if [ "$$ans" = "y" ] || [ "$$ans" = "Y" ] || [ "$$ans" = "yes" ] || [ "$$ans" = "YES" ]; then \
		echo "🗑️  Arrêt de Grafana et Prometheus..."; \
		docker compose stop grafana prometheus 2>/dev/null || true; \
		docker compose rm -f grafana prometheus 2>/dev/null || true; \
		echo "🗑️  Suppression des données Grafana et Prometheus..."; \
		rm -rf data/grafana_data data/prometheus_data; \
		echo "🗑️  Purge des compteurs Redis (wmetrics:)..."; \
		docker compose exec -T redis redis-cli --scan --pattern "wmetrics:*" | xargs -r docker compose exec -T redis redis-cli del 2>/dev/null || true; \
	else \
		echo "⏩ Conservation des données existantes."; \
	fi
	@$(MAKE) up
	@$(MAKE) wait-ready
	@if pgrep -f "$(GAMA_BIN)" > /dev/null; then \
		echo "⚠️  GAMA est déjà en cours d'exécution. Lancement ignoré."; \
	else \
		echo "🚀 Lancement de l'expérience GAMA : $(EXPERIMENT_NAME)..."; \
		$(GAMA_BIN) -p $(WORKSPACE) -o $(MODEL_PATH) -e "$(EXPERIMENT_NAME)" & \
	fi
