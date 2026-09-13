---
name: prompt_calib_context
description: Charge le contexte de travail sur le module de calibration de prompt (`prompt_calibration`, dépôt git autonome à la racine du projet). Se positionne dans `prompt_calibration/` et lit la doc d'architecture `docs/arch/prompt_calibration.md`. À utiliser avant toute tâche touchant à la calibration du prompt système `itinary_multi_agent` : store SQLite/DAG, boucle de recuit simulé, métriques (L1/EMD/JSD), mutations, ablation, dashboard Streamlit, CLI `calibrate`, jeux gelés, ou lancement depuis l'IHM GAMA.
---

# prompt_calib_context — Contexte de la calibration de prompt

## Quand l'utiliser
- Avant d'éditer, débugger ou étendre le module `prompt_calibration/` (dépôt git
  autonome : `github.com/Ytlse/prompt_calibration`, cloné à la racine du projet).
- « on bosse sur la calibration de prompt », « je veux modifier la loss / le store /
  le dashboard », « ajoute une métrique », « pourquoi la boucle rejette une mutation »,
  « lance/reprends une campagne de calibration ».

## Procédure

1. **Se positionner dans le dossier de travail** (répertoire courant pour toute la session
   de calibration) :
   ```bash
   cd /Users/yvesb/Documents/Projects/llm-agents-gama/prompt_calibration
   ```

2. **Lire la documentation d'architecture** (source de vérité du module) :
   - `docs/arch/prompt_calibration.md` — vue d'ensemble du pipeline, méthodes de calcul
     (L1 composite, EMD/RPS/JSD, acceptation statistique), extraction des métadonnées
     persona, reprise & persistance (store SQLite / DAG content-addressed), CLI,
     dashboard, revue de littérature, lancement depuis l'IHM GAMA.

   Le lire intégralement avec l'outil Read (la doc vit dans le dépôt principal) :
   ```
   Read /Users/yvesb/Documents/Projects/llm-agents-gama/docs/arch/prompt_calibration.md
   ```

3. **Compléter si besoin** avec les références citées dans la doc :
   - `prompt_calibration/README.md` — état des phases, arborescence du package,
     commandes d'utilisation (venv `../../llm-agents-gama/llm-agents/.venv/bin/python`).
   - `docs/tickets/ticket_004_prompt_calibration_industrialisation.md` — plan détaillé.
   - `run.yaml` / `run.example.yaml` — gabarit de `RunConfig`.

## Rappels clés (issus de la doc)
- **Dépôt autonome** : `prompt_calibration/` est un dépôt git séparé
  (`github.com/Ytlse/prompt_calibration`), imbriqué à la racine du projet et ignoré
  par le dépôt principal. Les imports du paquet sont en `prompt_calibration.calibration.*`.
- **Venv du projet** : `../../llm-agents-gama/llm-agents/.venv/bin/python`, commandes
  lancées depuis `prompt_calibration/` (cf. `Makefile`, cible `make test`).
- **Tests** : `make test` (ou `$PY -m pytest -q` — `conftest.py` rend le paquet importable).
- **Store** : toute la campagne vit dans un unique `calibration.db` (DAG
  content-addressed) — reprise exacte, zéro appel LLM redondant.
- **Séparation des modèles** : un seul modèle d'éval épinglé (pas d'alias `-latest`),
  un modèle distinct pour les mutations.
- Après modification : mettre à jour `docs/arch/prompt_calibration.md` et
  `docs/changelog.md` (cf. `.claude/CLAUDE.md`).
