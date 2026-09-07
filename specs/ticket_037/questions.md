# Ticket 037 — questions vivantes et hypothèses

Convention : on avance sous hypothèse, on note ici, on pose à la fin.

## Tranchées le 2026-09-06 (GO)

- Trois paquets au lieu d'un : oui.
- Authentification : différée, ticket 036.
- Versioning, distribution, dépôt séparé : second temps, guidé.

## Hypothèses prises pendant l'itération 1

| # | Hypothèse | Pourquoi | À confirmer |
|---|---|---|---|
| H1 | Noms `llm_gateway`, `mobility_core`, `mobility_llm` | proposés dans le plan, non contestés | oui |
| H2 | Trois répertoires à la racine du monorepo ; extraction du gateway plus tard | l'extraction dépend du versioning (second temps) | oui |
| H3 | Français pour code, docstrings, documentation | cohérence avec le dépôt | oui |
| H4 | Licence : aucun fichier LICENSE tant que la licence n'est pas choisie | décision de l'auteur | **question ouverte** |
| H5 | Le contrat de réponse (`AgentResponse`, `OptionProbability`) reste typé « options » dans le gateway | le contrat HTTP consommé par le SDK ne bouge pas ; généricisation de la sortie en itération 2 | oui |
| H6 | Les templates, schémas et `prompts.yaml` gardent leur disposition à plat dans `mobility_llm/prompts/` | prompt_calibration et les expériences citent `prompts.yaml` ; le rangement par catégorie viendra avec le registre complet | oui |
| H7 | Le worker Celery reste dans `llm_gateway/worker/` ; `executor/` apparaîtra avec le port d'exécution | éviter un sous-paquet nommé `celery` et un déplacement de plus | oui |
| H8 | `providers.yaml` reste une donnée du paquet `llm_gateway` pour cette itération | sa sortie du paquet est liée au paramétrage en couches | oui |
| H9 | `sim_ts` du journal des échanges = score de priorité du lot (min des départs) et non le départ du premier agent | le worker ne connaît plus `departure_timestamp` ; même lot, mêmes minutes | oui |
| H10 | `ruff format` n'est pas appliqué dans cette itération, seul `ruff check` | un reformatage massif dans le même changement que les déplacements casse la détection de renommage de git | oui |
| H11 | Le collecteur Prometheus du worker garde les familles métier (`llm_transport_mode_chosen_total`…) | les dashboards Grafana les citent ; l'exposition par le bundle viendra avec la généricité | oui |

## Questions ouvertes

1. Licence du gateway (MIT, Apache-2.0, propriétaire) ?
| H12 | La preuve d'adoption de `llm_gateway.testing` est dans `mobility_llm/tests/unit/test_bundle_end_to_end.py`, pas dans deux tests de llm-agents | aucun test de llm-agents ne simule aujourd'hui le gateway (grep `LLMGatewayClient` dans llm-agents/tests : rien) ; en créer deux artificiels n'aurait rien prouvé | oui |
| H13 | Le compteur Prometheus `alarme_total` du SDK est créé au premier `fire_alarme`, et hors registre si la famille est déjà exposée dans le processus | `import llm_gateway` dans le processus API faisait planter le démarrage (DuplicateTimeseries) | oui |
| H14 | `ruff check` avec `UP` (modernisation des annotations) a été appliqué en `--fix` sur les trois paquets | 379 corrections sûres, les fichiers étaient déjà déplacés ; le reformatage (`ruff format`) reste différé (H10) | oui |
| H15 | Relecture de la documentation (agent, 2026-09-07) : trois réglages ou mécanismes restent incomplets et sont laissés à l'itération « généricité » | `Settings.circuit_breaker_threshold` est déclaré mais jamais lu ; `_load_adapters()` énumère cinq modules codés en dur (un nouvel adapter exige d'éditer ce dictionnaire, ce que l'entry point `llm_gateway.adapters` remplacera) ; `configure_logging()` fait toujours `logger.remove()` (sans effet sur un hôte qui n'importe que le SDK, puisque seules les fabriques l'appellent) | oui |

## Questions ouvertes (mise à jour 2026-09-07)

1. Licence du gateway (MIT, Apache-2.0, propriétaire) ? Aucun fichier LICENSE tant que ce n'est pas tranché.
2. Faut-il pousser la branche pour faire tourner la CI maintenant, ou attendre la fin de `feat_cache_population` ?
