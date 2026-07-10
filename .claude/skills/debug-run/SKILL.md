---
name: debug-run
description: Analyse le dernier run de simulation (experiments/current) et produit un rapport de santé « agent-ready » — erreurs, warnings, saturation LLM, backlog pipeline, agents inactifs, timeouts, ainsi que la phase d'init (timeline, réchauffage des caches OTP/OSMnx/LLM, bugs de démarrage). À utiliser quand l'utilisateur demande d'analyser/debugger un run, de chercher les bugs/erreurs/warnings/exceptions, pourquoi des agents restent inactifs / la planif est en retard, pourquoi l'initialisation est longue, ou si les caches sont bien utilisés/réchauffés.
---

# debug-run — Rapport de santé du dernier run

## Quand l'utiliser
- « analyse le dernier run », « qu'est-ce qui a foiré », « pourquoi des agents sont inactifs »,
  « les LLM sont-ils saturés », « cherche les bugs/erreurs/warnings/timeouts ».

## Procédure

1. Générer le rapport (par défaut sur `experiments/current`) :
   ```bash
   python3 scripts/debug/run_report.py
   ```
   Options : `python3 scripts/debug/run_report.py <RUN_DIR> --top 20 --out rapport.md`.
   Un run précis se trouve dans `experiments/archive/<date>/`.

   Pour un diagnostic ciblé **débit vs capacité LLM** (saturation providers, backlog,
   temps simulé restant sur la tâche critique) :
   ```bash
   python3 scripts/debug/llm_capacity.py   # ou : make capacity
   ```

   Pour un diagnostic ciblé de la **phase d'initialisation** (timeline des 5 étapes
   d'init, réchauffage des caches OTP/OSMnx/LLM, bugs de démarrage : stalls event-loop
   → coupures WS 1006, thrashing cache LTM, OD injoignables au bootstrap) :
   ```bash
   python3 scripts/debug/init_report.py   # ou : make init
   ```
   À privilégier quand la question porte sur le **démarrage** : « pourquoi l'init est
   longue », « le cache est-il utilisé / réchauffé », « bugs au bootstrap », coupures
   WebSocket 1006 en début de run.

2. Lire la sortie markdown. **Commencer par la section `🚨 ALARMES`** en tête : elle
   liste les anomalies ayant franchi les seuils (saturation LLM 429, backlog pipeline,
   agents inactifs, timeouts, ratio de choix d'itinéraire par défaut sur erreur
   définitive LLM — cf. section `🧭 Décisions de mobilité`, ratio « des décisions LLM »).

3. Pour chaque alarme, corréler avec les sections détaillées du rapport :
   - **Saturation LLM** → section `🤖 Santé LLM` (providers en 429, quotas). Piste :
     réduire le débit de soumission, activer plus de providers, ou augmenter le cache.
   - **Backlog pipeline** → section `⏱️ Latence pipeline` (p95/max). La demande de
     planif dépasse le débit LLM courant.
   - **Agents inactifs / timeouts** → sections `👥 Activité` et `🚦 Arrivées`.
   - **Init lente / caches froids / coupures WS 1006 au démarrage** → `init_report.py`
     (`🚀 Rapport d'initialisation`) : étape dominante, taux de réchauffage des caches,
     stalls event-loop, thrashing cache LTM.

4. Synthétiser pour l'utilisateur : les 2-3 causes racines probables + l'action la plus
   utile. Ne pas recopier tout le rapport ; pointer les signaux qui expliquent le problème.

## Notes
- Les scripts sont autonomes (stdlib only), tolérants aux fichiers manquants.
- Logs centralisés par service dans le dossier du run : `app.log` (controller),
  `worker.log` (Celery), `api.log` (gateway) — `run_report` les agrège et tague chaque
  ligne `[service]`. Restent uniquement sur `docker compose logs` : `otp*`, `osmnx*`,
  `redis` (services non-Python) — compléter avec `docker compose logs <service> --since 1h`
  si le problème vient manifestement de là.
- Seuils d'alarme ajustables en tête de `scripts/debug/run_report.py` et
  `scripts/debug/llm_capacity.py`.
