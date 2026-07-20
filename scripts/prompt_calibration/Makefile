# Makefile — prompt_calibration (ticket 004)
# Raccourcis autour de la CLI `calibration.cli` et du dashboard Streamlit.
#
# Notion d'« essai » : chaque essai est une branche isolée dans le store SQLite,
# avec une config optionnelle. On peut donc lancer/relancer plusieurs campagnes
# en parallèle sans qu'elles se marchent dessus (reprise au point d'arrêt).
#
#   make run essai3      lance (ou relance/reprend) l'essai 3
#   make ui              ouvre l'interface (dashboard Streamlit)
#   make status essai3   état de l'essai 3
#   make help            liste toutes les cibles
#
# Résolution config/branche pour « essaiN » :
#   • branche  = <essai>            (ex. essai3 → isolation + reprise)
#   • config   = runN.yaml si présent, sinon run.yaml (gabarit par défaut)
# On peut aussi forcer : `make run ESSAI=essai3 CONFIG=run.yaml ITER=20`.

PY  := ../../llm-agents/.venv/bin/python
CLI := $(PY) -m calibration.cli

# ── Résolution de l'essai ────────────────────────────────────────────────────
# Cibles « verbe » connues ; tout autre mot de la ligne est traité comme l'essai.
COMMANDS := help run resume ui dashboard status export finalize backtest \
            datasets test clean
ESSAI    ?= $(strip $(filter-out $(COMMANDS),$(MAKECMDGOALS)))
ESSAI    := $(if $(ESSAI),$(ESSAI),essai1)
ESSAI_NUM := $(patsubst essai%,%,$(ESSAI))
CONFIG   ?= $(firstword $(wildcard run$(ESSAI_NUM).yaml) run.yaml)

# ── Options facultatives ─────────────────────────────────────────────────────
ITER    ?=                       # nombre d'itérations (0/absent → max_iterations de la config)
ISLANDS ?=                       # nombre d'îlots parallèles (>1 → multi-branches)
PORT    ?=                       # port du dashboard Streamlit
OUT     ?= calibration_results/export
VERSION ?= v1                    # version de jeux gelés pour `make datasets`

RUN_FLAGS := $(if $(ITER),--iterations $(ITER),) $(if $(ISLANDS),--islands $(ISLANDS),)
UI_FLAGS  := $(if $(PORT),--port $(PORT),)

.DEFAULT_GOAL := help

# ── Cibles principales ───────────────────────────────────────────────────────

.PHONY: help
help:
	@echo "prompt_calibration — cibles disponibles :"
	@echo ""
	@echo "  make run <essai>        lance ou relance/reprend une campagne (ex: make run essai3)"
	@echo "  make resume <essai>     alias explicite de run (reprise depuis le store)"
	@echo "  make ui [<essai>]       ouvre le dashboard Streamlit (lecteur du store)"
	@echo "  make status <essai>     état de la branche (meilleur nœud, itération, #évals)"
	@echo "  make export <essai>     export lisible du store (CSV + timeline Markdown)"
	@echo "  make finalize <essai>   éval test + bilan avant/après (dry-run ; WRITE=1 publie)"
	@echo "  make backtest <essai>   recalcule des losses sur l'historique (zéro appel LLM)"
	@echo "  make datasets           (re)génère les jeux gelés depuis experiments/current"
	@echo "  make test               pytest -q"
	@echo "  make clean              supprime les exports générés (garde le store)"
	@echo ""
	@echo "Options : ESSAI=essai3 CONFIG=run.yaml ITER=20 ISLANDS=4 PORT=8502 WRITE=1"
	@echo "Essai courant : ESSAI=$(ESSAI)  CONFIG=$(CONFIG)  branche=$(ESSAI)"

.PHONY: run
run:
	@echo "▶ Essai $(ESSAI) — config $(CONFIG) — branche $(ESSAI)"
	$(CLI) run --config $(CONFIG) --branch $(ESSAI) $(RUN_FLAGS)

.PHONY: resume
resume:
	@echo "▶ Reprise essai $(ESSAI) — config $(CONFIG)"
	$(CLI) resume --config $(CONFIG) --branch $(ESSAI) $(RUN_FLAGS)

.PHONY: ui dashboard
ui dashboard:
	@echo "▶ Dashboard — config $(CONFIG)"
	$(CLI) dashboard --config $(CONFIG) $(UI_FLAGS)

.PHONY: status
status:
	$(CLI) status --config $(CONFIG) --branch $(ESSAI)

.PHONY: export
export:
	$(CLI) export --config $(CONFIG) --branch $(ESSAI) --out $(OUT)

.PHONY: finalize
finalize:
	$(CLI) finalize --config $(CONFIG) --branch $(ESSAI) \
		$(if $(WRITE),--write,) $(if $(ACTIVATE),--activate,)

.PHONY: backtest
backtest:
	$(CLI) backtest --config $(CONFIG) --branch $(ESSAI) \
		$(if $(METRICS),--metrics $(METRICS),) $(if $(DATASET),--dataset $(DATASET),)

# ── Utilitaires ──────────────────────────────────────────────────────────────

.PHONY: datasets
datasets:
	$(PY) -m calibration.datasets ../../experiments/current calibration_datasets $(VERSION)

.PHONY: test
test:
	$(PY) -m pytest -q

.PHONY: clean
clean:
	rm -rf calibration_results/export calibration_results/backtest.csv

# ── Absorbe l'argument « essaiN » (et assimilés) pour qu'il ne soit pas ───────
# ── interprété comme une cible à construire. ─────────────────────────────────
%:
	@:
