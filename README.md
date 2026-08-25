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
| [docs/arch/population-post-traitements.md](docs/arch/population-post-traitements.md) | Population synthétique : les quatre étages de post-traitement entre eqasim et le `traits_json` de l'agent |
| [docs/arch/llm-inference.md](docs/arch/llm-inference.md) | Batching, SWRR, circuit breaker, load balancing LLM |
| [docs/arch/routing.md](docs/arch/routing.md) | OTP (transit) et OSMnx (marche/vélo/voiture) |
| [docs/synthesis/](docs/synthesis/) — pages `<AAAA-MM-JJ_HH-MM>_*.html` | Pages de mesure **horodatées et archivées** (`make terminal-page`) : une mesure sur jeux gelés garde la sienne, aucune n'écrase la précédente — contrairement à `index.html`, régénérée en place parce qu'elle suit l'état courant |
| [docs/traces/](docs/traces/) | Traces archivées des expériences citées ailleurs — `index.html` lisible au navigateur, `README.md` dans le dépôt, `results.json` pour un script. Le store de calibration étant régénérable et hors dépôt, c'est ici que les mesures survivent |
| [docs/arch/protocole-parametre-exogene.md](docs/arch/protocole-parametre-exogene.md) | Méthode pour corriger un paramètre exogène (temps terminal, attente…) **sans rejouer de simulation** : mesurer dans l'enquête, réécrire un jeu gelé, valider par le moteur de calibration, archiver, puis porte de décision |
| [docs/arch/velo-equipement.md](docs/arch/velo-equipement.md) | Équipement vélo du persona : les trois étages appris sur EMC² (stock du ménage, attribution nominative, VAE), et les cibles réellement opposables à une population synthétique |
| [docs/arch/vehicle-chain.md](docs/arch/vehicle-chain.md) | Cohérence de chaîne vélo/voiture : le véhicule reste où l'agent l'a garé |
| [docs/arch/cache-memory.md](docs/arch/cache-memory.md) | Mémoire court/long terme, cache sémantique LLM |
| [docs/arch/llm-module-package-refactor.md](docs/arch/llm-module-package-refactor.md) | CR (implémenté) : restructuration de llm_module en package (ports, injection, pyproject) |

### Observabilité et mesure

| Document | Description |
|----------|-------------|
| [docs/arch/dashboard.md](docs/arch/dashboard.md) | Tableau de bord `make dashboard` : vue d'ensemble du projet, pilotage du run GAMA (lancement/arrêt, progression, top erreurs), providers LLM (quotas temps réel, `make providers`), cibles `make` des sous-projets, tickets et métriques (Docker, run, synthèse, calibration) |
| [docs/arch/monitoring.md](docs/arch/monitoring.md) | Métriques Prometheus, dashboards Grafana 01→08, alarmes & alertes |
| [docs/arch/score-synthesis.md](docs/arch/score-synthesis.md) | Page de synthèse `make synthesis` : simulation, calibration et modèle PROGEDO face à l'enquête EMC². `make common-set-eval` produit la mesure du volet calibration sur le jeu commun et `make heldout-eval` son score de généralisation sur le jeu de test gelé — **les deux seules cibles qui consomment du quota LLM** (chiffrer d'abord : `DRY_RUN=1`) ; `make common-set-predict` produit celle du volet modèle, hors ligne et déterministe. `make model-compare RUN=…` ventile le score d'un run **modèle par modèle** (page dédiée sous `docs/synthesis/models/<run>/`), sans appel LLM |
| [docs/arch/perimetre-population.md](docs/arch/perimetre-population.md) | Périmètre de population : les neuf écarts de base entre la population interrogée par l'enquête EMC² et la population simulée, chacun chiffré et tranché. `make audit-perimetre` rejoue les mesures (code de sortie **3** = axe non mesurable), `make communes-couronnes` produit la correspondance commune → couronne des 453 communes, `make audit-couronnes` mesure les deux équivalences sur lesquelles repose la correction du ticket 021 |

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
