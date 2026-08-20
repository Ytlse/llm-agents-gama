# LLM Agents & GAMA platform

Modeling realistic human behavior using generative agents in a multimodal transport system: Software architecture and Application to Toulouse.

## Architecture

![architecture](docs/paper/raw_assets/architecture.png)

Vue d'ensemble technique : [ARCHITECTURE.md](ARCHITECTURE.md)

---

## Documentation

### Mise en place

| Document | Description |
|----------|-------------|
| [docs/setup/population.md](docs/setup/population.md) | Génération de la population synthétique (EQUASIM) |
| [docs/setup/data-pipeline.md](docs/setup/data-pipeline.md) | GTFS, OpenTripPlanner, OSMnx — données géospatiales |
| [docs/setup/llm-providers.md](docs/setup/llm-providers.md) | Configuration des providers LLM et clés API |
| [docs/setup/quickstart.md](docs/setup/quickstart.md) | Lancer la simulation, ports, scripts disponibles |

### Architecture par sujet

| Document | Description |
|----------|-------------|
| [docs/arch/agents-lifecycle.md](docs/arch/agents-lifecycle.md) | Cycle de planification des agents, bootstrap, WebSocket |
| [docs/arch/llm-inference.md](docs/arch/llm-inference.md) | Batching, SWRR, circuit breaker, load balancing LLM |
| [docs/arch/routing.md](docs/arch/routing.md) | OTP (transit) et OSMnx (marche/vélo/voiture) |
| [docs/arch/vehicle-chain.md](docs/arch/vehicle-chain.md) | Cohérence de chaîne vélo/voiture : le véhicule reste où l'agent l'a garé |
| [docs/arch/cache-memory.md](docs/arch/cache-memory.md) | Mémoire court/long terme, cache sémantique LLM |
| [docs/arch/llm-module-package-refactor.md](docs/arch/llm-module-package-refactor.md) | CR (implémenté) : restructuration de llm_module en package (ports, injection, pyproject) |

### Observabilité et mesure

| Document | Description |
|----------|-------------|
| [docs/arch/dashboard.md](docs/arch/dashboard.md) | Tableau de bord `make dashboard` : vue d'ensemble du projet, pilotage du run GAMA (lancement/arrêt, progression, top erreurs), providers LLM (quotas temps réel, `make providers`), cibles `make` des sous-projets, tickets et métriques (Docker, run, synthèse, calibration) |
| [docs/arch/monitoring.md](docs/arch/monitoring.md) | Métriques Prometheus, dashboards Grafana 01→08, alarmes & alertes |
| [docs/arch/score-synthesis.md](docs/arch/score-synthesis.md) | Page de synthèse `make synthesis` : simulation, calibration et modèle PROGEDO face à l'enquête EMC². `make common-set-eval` produit la mesure du volet calibration sur le jeu commun et `make heldout-eval` son score de généralisation sur le jeu de test gelé — **les deux seules cibles qui consomment du quota LLM** (chiffrer d'abord : `DRY_RUN=1`) ; `make common-set-predict` produit celle du volet modèle, hors ligne et déterministe. `make model-compare RUN=…` ventile le score d'un run **modèle par modèle** (page dédiée sous `docs/synthesis/models/<run>/`), sans appel LLM |

---

## Dépôts externes

| Module | Emplacement local | Dépôt git séparé |
|--------|------------------|-----------------|
| EQUASIM Toulouse | `eqasim-toulouse/` | repo indépendant (voir [docs/setup/population.md](docs/setup/population.md)) |

Le dossier `eqasim-toulouse/` est intentionnellement absent du suivi git de ce dépôt (`.gitignore`).

---

## Reference

```
@misc{vu2025modelingrealistichumanbehavior,
      title={Modeling realistic human behavior using generative agents in a multimodal transport system: Software architecture and Application to Toulouse}, 
      author={Trung-Dung Vu and Benoit Gaudou and Kamaldeep Singh Oberoi},
      year={2025},
      eprint={2510.19497},
      archivePrefix={arXiv},
      primaryClass={cs.MA},
      url={https://arxiv.org/abs/2510.19497}, 
}
```
