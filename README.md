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
| [docs/arch/cache-memory.md](docs/arch/cache-memory.md) | Mémoire court/long terme, cache sémantique LLM |

### Observabilité et mesure

| Document | Description |
|----------|-------------|
| [observability.md](observability.md) | Métriques Prometheus / Grafana |
| [pipeline.md](pipeline.md) | Points de mesure du pipeline de planification |

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
