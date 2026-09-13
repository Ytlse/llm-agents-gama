# ADR 0002 — Le gateway découvre ses catégories par un hook enfichable

- **Date** : 2026-09-06
- **Statut** : accepté (ticket 037, itération 1, point 4 « hook de catégorie minimal »)
- **Portée** : `llm_gateway.ports.category`, `llm_gateway.prompts.registry`, l'API et le worker

## Contexte

Une fois le métier sorti du gateway ([ADR 0001](0001-trois-paquets.md)), il fallait décider
comment le gateway retrouve ce qu'il ne contient plus : le template et le schéma d'une
catégorie, le modèle qui valide un item, la règle de priorité d'un lot, les métriques métier
que le worker calculait lui-même (`llm_transport_mode_chosen_total`, désaccords de mode,
tranches de distance).

Contraintes : le gateway ne doit importer aucun paquet métier (contrat
`gateway-sans-metier`) ; le contrat HTTP consommé par le contrôleur GAMA ne doit pas bouger ;
une catégorie mal déclarée doit échouer au démarrage, pas à la première requête ; les
dashboards Grafana lisent les compteurs Redis existants.

## Décision

Un **bundle** est un objet `CategoryBundle` (nom, répertoire de templates, fichier de
schémas, `prompts.yaml` facultatif, dictionnaire de `CategorySpec`) fourni par un paquet
tiers sous l'**entry point** `llm_gateway.categories` :

```toml
[project.entry-points."llm_gateway.categories"]
mobility = "mobility_llm:bundle"
```

Un `CategorySpec` porte trois hooks, tous facultatifs : `item_model` (modèle pydantic de
l'item ; défaut `AgentItem`, un `agent_id` et des champs libres conservés), `priority`
(score d'un lot, plus bas = plus urgent ; défaut aucun), `observe` (appelé après validation
de la réponse avec un `ObserveContext` — catégorie, provider, items validés, sortie,
`MetricsSink`).

Le **registre** (`CategoryRegistry`) est construit explicitement par `build_deps` (API) et
`build_worker_runtime` (worker) à partir des entry points, ou passé à la main
(`llm_gateway.testing.build_registry`). À la construction, pour chaque catégorie : template
et schéma présents, sinon `ValueError` ; un même nom dans deux bundles → `ValueError`.

L'**API** résout la catégorie, valide les items avec `item_model` et calcule la priorité
avant de persister la tâche : catégorie inconnue ou item invalide → 422. Le **worker**
demande au handle de valider, rendre et fournir le schéma, appelle l'adapter, puis
`handle.observe(...)` ; une exception dans `observe` est journalisée et n'échoue jamais le
lot. Le worker n'importe plus le choix modal.

Hypothèses associées : le collecteur Prometheus du gateway garde les familles métier de la
mobilité codées en dur (H11), le `sim_ts` du journal des échanges devient le score de
priorité du lot (H9), le contrat de réponse reste typé « options » (H5), le bundle `echo` de
`llm_gateway.testing` sert de bundle minimal et la preuve d'adoption de l'outillage de test
est `mobility_llm/tests/unit/test_bundle_end_to_end.py` (H12).

## Conséquences

- Sans bundle installé, `llm-gateway categories` rend 1 et toute requête est refusée en 422
  avec la liste (vide) des catégories : le gateway n'a plus de comportement « par défaut »
  qui masquerait une installation incomplète.
- Ajouter une catégorie ne touche pas au gateway : un paquet, un entry point, des fichiers.
- Le registre valide au démarrage : un déploiement avec un template manquant ne démarre
  pas.
- `mobility_llm` doit être installé dans l'environnement de l'API **et** du worker (l'image
  Docker embarque les trois paquets).
- Limite connue : les compteurs écrits par `observe` ne sortent sur `/metrics` que si le
  collecteur de l'API connaît la famille ; l'exposition déclarée par le bundle viendra avec
  la généricité (itération suivante). Même chose pour la sortie : une seule forme (`agents`
  alignés sur `agent_id`).

## Alternatives écartées

- **Un registre configuré par fichier (YAML listant des chemins de templates)** : ne
  résout ni la validation des items ni les métriques métier, qui sont du code.
- **Des sous-classes de worker par catégorie** : impose Celery au métier et un worker par
  bundle.
- **Garder `AgentSpec` dans le gateway avec tous les champs optionnels** : le gateway
  continuerait de dire ce qu'est un persona ; un bundle documentaire n'aurait rien à en faire.
- **Découverte par import de module nommé dans une variable d'environnement** : moins
  standard que l'entry point, qu'`importlib.metadata` sert sans configuration et que
  `pip install` suffit à activer.
