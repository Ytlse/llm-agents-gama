# ──────────────────────────────────────────────────────────────────────────────
# Expériences Mémoire (Ticket 109)
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: experience-memoire-lancer experience-memoire-estimer experience-memoire-nuit

## Lance une expérience mémoire A/B (bras traité puis témoin consécutifs, Ticket 109).
## Usage: make experience-memoire-lancer EXP=<nom> [DRY_RUN=1] [BRANCHE=both|treated|control]
experience-memoire-lancer:
	@test -n "$(EXP)" || { echo "❌ Variable EXP manquante (ex: make experience-memoire-lancer EXP=exp_mem_...)"; exit 1; }
	$(VENV_PYTHON) scripts/experiment/orchestrateur_memoire.py --experience $(EXP) $(if $(filter 1,$(DRY_RUN)),--dry-run,) $(if $(BRANCHE),--branche $(BRANCHE),)

## Estime le coût en requêtes et en jetons d'une expérience mémoire.
## Usage: make experience-memoire-estimer EXP=<nom>
experience-memoire-estimer:
	@test -n "$(EXP)" || { echo "❌ Variable EXP manquante (ex: make experience-memoire-estimer EXP=exp_mem_...)"; exit 1; }
	$(VENV_PYTHON) scripts/experiment/orchestrateur_memoire.py --experience $(EXP) --estimer

## Enchaîne les expériences mémoire une par une, en arrière-plan, pour une nuit sans surveillance.
## Sans EXP : toutes les expériences déclarées non terminées, dans l'ordre de création.
## Suspension pour 503 : nouvel essai toutes les ATTENTE_S s, ESSAIS_MAX fois sans progrès.
## Quota épuisé : expérience suivante. Journal : experiments/enchainement_nuit_<date>.log
## Usage: make experience-memoire-nuit [EXP="exp_a exp_b"] [ATTENTE_S=1800] [ESSAIS_MAX=6]
experience-memoire-nuit:
	@env -u MAKEFLAGS -u MAKELEVEL -u MFLAGS ATTENTE_S=$(or $(ATTENTE_S),1800) ESSAIS_MAX=$(or $(ESSAIS_MAX),6) \
		nohup $(if $(shell command -v caffeinate),caffeinate -i,) bash scripts/experiment/enchainer_experiences_memoire.sh $(EXP) >/dev/null 2>&1 &
	@sleep 3; journal=$$(ls -t experiments/enchainement_nuit_*.log 2>/dev/null | head -1); \
		cat "$$journal"; echo "🌙 Suivi : tail -f $$journal"
