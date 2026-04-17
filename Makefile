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

## Start all services then launch the GAMA experiment
## Usage: make run [CONFIG=my_config.yaml] [EXPERIMENT_NAME=e]
run: up
	@if pgrep -f "$(GAMA_BIN)" > /dev/null; then \
		echo "⚠️  GAMA est déjà en cours d'exécution. Lancement ignoré."; \
	else \
		echo "🚀 Lancement de l'expérience GAMA : $(EXPERIMENT_NAME)..."; \
		$(GAMA_BIN) -p $(WORKSPACE) -o $(MODEL_PATH) -e "$(EXPERIMENT_NAME)" & \
	fi
