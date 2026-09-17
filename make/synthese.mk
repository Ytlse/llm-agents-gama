# ──────────────────────────────────────────────────────────────────────────────
# Synthèse des scores
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: synthesis synthesis-open synthesis-pull-db terminal-page \
        common-set-eval heldout-eval \
        model-compare model-compare-open

# La synthèse importe pandas/numpy et le moteur de calibration : le python3 du
# système ne suffit pas. On vise le venv du projet, surchargeable.
SYNTHESIS_PYTHON ?= $(VENV_PYTHON)

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
