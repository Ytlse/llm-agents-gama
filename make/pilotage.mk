# ──────────────────────────────────────────────────────────────────────────────
# Pilotage
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: dashboard

DASHBOARD_PYTHON ?= $(VENV_PYTHON)
DASHBOARD_PORT   ?= 8503
# Thème imposé (light|dark) : les graphes choisissent leurs pas de couleur
# dessus. Le laisser vide ferait diverger l'UI et les couleurs de texte.
DASHBOARD_THEME  ?= light

.PHONY: help
## Liste les cibles documentées : le nom de chaque cible et le bloc `##` qui la précède.
## Utile depuis que le tableau de bord n'affiche plus le catalogue des cibles.
## Balaie TOUS les fichiers lus (racine + make/*.mk) : avec `firstword`, le découpage
## du ticket 039 aurait réduit cette liste aux seules cibles du fichier racine — zéro.
help:
	@awk '\
	  /^## / { if (doc == "") doc = substr($$0, 4); next } \
	  /^\.PHONY/ { next } \
	  /^[a-zA-Z0-9_.-]+:/ { if (doc != "") { split($$0, cible, ":"); printf "  %-24s %s\n", cible[1], doc }; doc = ""; next } \
	  /^[[:space:]]*$$/ { doc = "" } \
	' $(MAKEFILE_LIST)

## Tableau de bord de pilotage : état des services, expériences en cours, tickets, métriques de run.
## Usage: make dashboard [DASHBOARD_THEME=dark] [DASHBOARD_PORT=8503] [DASHBOARD_PYTHON=/chemin/python]
dashboard:
	@test -x $(DASHBOARD_PYTHON) || { \
	  echo "Interpréteur introuvable : $(DASHBOARD_PYTHON)"; \
	  echo "Surchargez-le : make dashboard DASHBOARD_PYTHON=/chemin/vers/python"; \
	  exit 1; }
	$(DASHBOARD_PYTHON) -m streamlit run scripts/dashboard/app.py \
	  --server.port $(DASHBOARD_PORT) --server.headless false \
	  --theme.base $(DASHBOARD_THEME) --theme.primaryColor "#2a78d6"
