# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: tests test-gateway test-mobility test-all lint-imports lint typecheck analysis

# Interpréteur des paquets (installés en editable dans le venv de llm-agents).
PKG_PYTHON ?= $(VENV_PYTHON)

## Tests du gateway LLM générique (unit + contract + integration ; e2e si LLM_GATEWAY_E2E_URL)
test-gateway:
	cd packages/llm_gateway && $(PKG_PYTHON) -m pytest

## Tests du domaine mobilité (mobility_core) et des catégories LLM (mobility_llm)
test-mobility:
	cd packages/mobility_core && $(PKG_PYTHON) -m pytest
	cd packages/mobility_llm && $(PKG_PYTHON) -m pytest

## Les trois paquets, puis les contrats d'architecture
test-all: test-gateway test-mobility lint-imports

## Alias historique
tests: test-all

## Contrats import-linter des trois paquets (.importlinter à la racine)
lint-imports:
	$(PKG_PYTHON) -c "from importlinter.cli import lint_imports_command; lint_imports_command()"

## ruff sur les trois paquets
lint:
	$(PKG_PYTHON) -m ruff check packages/llm_gateway packages/mobility_core packages/mobility_llm

## mypy : contrat public du gateway (core, ports, sdk) en strict
typecheck:
	cd packages/llm_gateway && $(PKG_PYTHON) -m mypy src/llm_gateway/core src/llm_gateway/ports src/llm_gateway/sdk

# Les notebooks tournent via papermill, installé dans le venv du projet : le
# python du système ne suffit pas. Surchargeable comme les autres interpréteurs.
ANALYSIS_PYTHON ?= $(VENV_PYTHON)

## Run all analysis notebooks. Usage: make analysis [LOG_DIR=../../experiments/my_exp/]
analysis:
	@test -x $(ANALYSIS_PYTHON) || { \
	  echo "Interpréteur introuvable : $(ANALYSIS_PYTHON)"; \
	  echo "Surchargez-le : make analysis ANALYSIS_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	$(ANALYSIS_PYTHON) scripts/analysis/run_analysis.py $(if $(LOG_DIR),--log-dir $(LOG_DIR),)
