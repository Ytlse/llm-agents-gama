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
| H4 | Licence : Apache-2.0 pour le gateway (décision du 2026-09-07) | décision de l'auteur | fait |
| H5 | Le contrat de réponse (`AgentResponse`, `OptionProbability`) reste typé « options » dans le gateway | le contrat HTTP consommé par le SDK ne bouge pas ; généricisation de la sortie en itération 2 | oui |
| H6 | ~~Disposition à plat~~ Rangement par catégorie livré au lot E (H24) ; `prompts.yaml` seul reste à plat | prompt_calibration et les expériences citent `prompts.yaml` ; le rangement par catégorie viendra avec le registre complet | oui |
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
| H17 | Pas de sous-modèle `providers` : trois champs de premier niveau (`providers_file`, `learned_limits`, `learned_limits_file`) | `settings.providers` reste le dictionnaire des instances résolues, cité à vingt-deux endroits (worker, balancer, API, prompt_calibration) | oui |
| H18 | Le contrôleur lit le fichier des fournisseurs monté (`LLM_GATEWAY_PROVIDERS_FILE`), pas `GET /config/providers` | l'API n'est pas prête quand le contrôleur charge ses réglages ; l'endpoint existe pour les outils | oui |
| H19 | `PROVIDER_KEYS__<nom>` reste le nom canonique des clés d'API, sans avertissement | partagé avec le `.env` de l'auteur, la logique des seconds seaux Google du compose, `make providers` et prompt_calibration | oui |
| H20 | Le journal des échanges garde son emplacement par défaut (`<workdir>/llm_exchanges.jsonl`) au lot A | sa désactivation par défaut est le lot D, avec le rédacteur | oui |
| H21 | Le journal des échanges est désactivé par défaut ; le compose de la simulation l'active (`LLM_GATEWAY_TELEMETRY__EXCHANGES_ENABLED=true`) | données personnelles potentielles ; `make report` et le tableau de bord en dépendent, d'où l'activation explicite côté déploiement | oui |
| H22 | Le worker n'abandonne plus une file quand les fournisseurs éligibles sont seulement occupés ; il attend jusqu'à `max_retries` | run Prompt_Minimaliste : 120 sollicitations sur 240 perdues sur une instance forcée à 15 RPM, alors qu'elle n'était ni en cooldown ni au quota ; `abandon_when_busy` rétablit l'ancien comportement | oui |
| H23 | Les familles Prometheus métier sont déclarées par le bundle et rendues génériquement ; leurs noms ne changent pas | dashboards Grafana 04 et 07 | oui |
| H24 | Rangement par catégorie dans `mobility_llm/categories/<nom>/` (template, schéma, `observe.py`) ; `prompts.yaml` reste dans `prompts/` | prompt_calibration et les expériences citent `prompts/prompts.yaml` ; le module d'observation devient `categories/itinary_multi_agent/observe.py` réexporté par le sous-paquet, imports inchangés | oui |
| H25 | L'itération 2 a été menée dans un worktree git sur la branche `ticket-037-iteration-2`, pas dans l'arbre principal | une expérience tournait sur les conteneurs, qui montent l'arbre principal et rechargent le code de l'API à chaque sauvegarde ; la fusion, le compose (journal des échanges activé) et la recréation des conteneurs attendent la fin du run | oui |

## Questions ouvertes (mise à jour 2026-09-07)

1. ~~Licence du gateway ?~~ Tranchée le 2026-09-07 : **Apache-2.0** (LICENSE + NOTICE dans `llm_gateway/`, métadonnées pyproject). Titulaire du copyright écrit « les auteurs du dépôt » dans NOTICE : à préciser si une entité doit y figurer. La licence des ressources EMC² de `mobility_core` fait l'objet du ticket 038.
2. ~~Pousser la branche pour la CI ?~~ Fait le 2026-09-07 : trois commits poussés, CI verte au troisième run.
| H16 | ~~Cliquet à 70 %~~ Remonté à 80 % au lot C (81 % mesurés) | 74 % mesurés ; adapters OpenAI-compatibles et worker peu couverts hors intégration, leurs tests arrivent avec l'adapter générique (itération 2) ; le seuil ne redescend jamais | oui |
