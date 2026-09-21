## ── Plateforme d'expériences (ticket 035) ──────────────────────────────────────────────
## Tout passe par `python -m experiences` dans le conteneur controller (services requis pour
## préparer un jeu — OTP/OSMnx — et pour un décideur passerelle ; un décideur local n'a besoin
## de rien). Design : docs/arch/plateforme-experiences.md.
## État du dépôt mesuré sur l'HÔTE et transmis au conteneur (ticket 045, A4) : `git` n'est pas
## installé dans l'image `controller`, si bien que chaque exécution s'archivait avec
## `depot = {commit: null, arbre_propre: null}` — aucune mesure ne pouvait être rattachée à un
## état du code. `:=` et non `=` : mesuré une fois au chargement du Makefile, pas à chaque appel.
EXP_DEPOT_COMMIT := $(shell git rev-parse HEAD 2>/dev/null)
EXP_DEPOT_ARBRE_PROPRE := $(shell test -z "$$(git status --porcelain --untracked-files=no 2>/dev/null)" && echo 1 || echo 0)

# Un chemin de l'hôte vu du conteneur : la racine du dépôt y est montée sur /app.
chemin_app = $(if $(patsubst /app/%,,$(1)),/app/$(patsubst ./%,%,$(1)),$(1))

EXPERIENCES_PY = $(COMPOSE) exec -T -e EXPERIENCES_DIR=/app/data/experiences -e JEUX_DIR=/app/data/jeux -e REFERENTIEL_ENQUETE=/app/scripts/data/population/cerema_values.yaml -e EXP_DEPOT_COMMIT=$(EXP_DEPOT_COMMIT) -e EXP_DEPOT_ARBRE_PROPRE=$(EXP_DEPOT_ARBRE_PROPRE) controller python -m experiences
APPARIER_PY = $(COMPOSE) exec -T -e EXPERIENCES_DIR=/app/data/experiences -e JEUX_DIR=/app/data/jeux -e REFERENTIEL_ENQUETE=/app/scripts/data/population/cerema_values.yaml -e EXP_DEPOT_COMMIT=$(EXP_DEPOT_COMMIT) -e EXP_DEPOT_ARBRE_PROPRE=$(EXP_DEPOT_ARBRE_PROPRE) controller python /app/scripts/analysis/appariement_executions.py

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

## Recharge la passerelle LLM (api + worker) — nécessaire après un ajout dans packages/mobility_llm/src/mobility_llm/prompts/prompts.yaml
passerelle-recharger:
	$(COMPOSE) restart api worker

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

## Campagne (ticket 074, lot D) : un lot nommé d'expériences menées jusqu'au bout, à travers
## les renouvellements de quota. Tourne sur l'HÔTE, comme l'ordonnanceur, et l'appelle elle-même
## — inutile de lancer `experience-ordonnancer` à côté.
##   make campagne-lancer NOM=bascule_anglaise_v6 [ESTIMER=1] [RECOMMENCER=1] [INTERVALLE=30]
##   make campagne-etat   NOM=bascule_anglaise_v6 [JSON=1]
##   make campagne-arreter NOM=bascule_anglaise_v6
## ESTIMER=1 dit le budget et sort, sans rien enfiler. RECOMMENCER=1 ignore l'état existant.
campagne-lancer:
	@test -n "$(NOM)" || { echo "Usage : make campagne-lancer NOM=<campagne>"; exit 1; }
	@$(MAKE) --no-print-directory services-pretes REQUIS="$(if $(REQUIS),$(REQUIS),controller)"
	cd services/llm-agents && .venv/bin/python -m experiences campagne-lancer --nom $(NOM) \
	  $(if $(ESTIMER),--estimer,) $(if $(RECOMMENCER),--recommencer,) \
	  $(if $(INTERVALLE),--intervalle $(INTERVALLE),)

campagne-etat:
	@test -n "$(NOM)" || { echo "Usage : make campagne-etat NOM=<campagne>"; exit 1; }
	cd services/llm-agents && .venv/bin/python -m experiences campagne-etat --nom $(NOM) $(if $(JSON),--json,)

campagne-arreter:
	@test -n "$(NOM)" || { echo "Usage : make campagne-arreter NOM=<campagne>"; exit 1; }
	cd services/llm-agents && .venv/bin/python -m experiences campagne-arreter --nom $(NOM)

## Ordonnanceur (HÔTE) : réconcilie les fantômes et démarre les expériences en file dès qu'une
## clé se libère. À laisser tourner (le tableau de bord le supervise aussi). Ctrl-C pour arrêter.
experience-ordonnancer:
	cd services/llm-agents && .venv/bin/python -m experiences ordonnancer $(if $(INTERVALLE),--intervalle $(INTERVALLE),)

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

## Apparie DEUX exécutions décision par décision — le chiffrage de l'axe 0 (ticket 073) :
##   make apparier A=<dossier exécution> B=<dossier exécution> [JSON=<fichier>] [TOUT=1] [SEUIL=0.8]
## A et B se donnent relativement à la racine du dépôt (data/experiences/<exp>/executions/<horodatage>).
## Tourne dans le conteneur `controller`, seul endroit où la garde de comparabilité du registre
## est disponible. LECTURE SEULE : rien n'est écrit dans les exécutions.
## `comparer` répond « ces deux mesures sont-elles comparables ? » ; `apparier` répond
## « de combien le modèle a-t-il bougé, décision par décision ? ».
apparier:
	@test -n "$(A)" -a -n "$(B)" || { echo "Usage : make apparier A=<dossier> B=<dossier> [JSON=<fichier>] [TOUT=1]"; exit 1; }
	$(APPARIER_PY) $(call chemin_app,$(A)) $(call chemin_app,$(B)) \
	  $(if $(JSON),--json $(call chemin_app,$(JSON)),) $(if $(TOUT),--tout,) $(if $(SEUIL),--seuil $(SEUIL),)

.PHONY: apparier

.PHONY: campagne-lancer campagne-etat campagne-arreter

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
	$(COMPOSE) exec -T controller python /app/scripts/prompt_base/build.py \
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
	@if $(COMPOSE) ps --status running controller 2>/dev/null | grep -q controller; then \
		$(COMPOSE) exec -T controller python3 -c "import os, psutil, signal; [p.send_signal(signal.SIGTERM) for p in psutil.process_iter(['name', 'cmdline']) if p.pid != os.getpid() and p.info['cmdline'] and any('launch_headless.py' in arg for arg in p.info['cmdline'])]" 2>/dev/null || true; \
	fi
	-@pkill -f "scripts/gama/launch_headless.py" 2>/dev/null || true
	-@$(COMPOSE) --profile offline stop gama 2>/dev/null || true
	-@pkill -f "$(GAMA_BIN)" 2>/dev/null || true
	@echo "✅ Run arrêté. Les services restent en place (make down pour tout couper)."
