# Changelog

!!! note "Copie"
    Cette page est une copie ; la source est `CHANGELOG.md` à la racine du paquet
    `llm_gateway`. En cas d'écart, c'est le fichier racine qui fait foi.

Format : `## [version] - AAAA-MM-JJ`, entrées les plus récentes en tête. Le ton est celui de
l'usage : ce que le changement permet ou modifie pour qui s'en sert. Les fichiers touchés
sont dans git.

## [1.1.0] - 2026-09-07

Le gateway devient une bibliothèque générique : il ne connaît plus la mobilité toulousaine.
Les prompts, le modèle de persona, le choix modal et les métriques métier vivent dans
`mobility_llm`, le domaine de l'enquête dans `mobility_core` (ticket 037, itération 1).

**Avant :** un seul paquet `llm_module` mêlant gateway et métier. Les templates, schémas et
variantes de prompt étaient livrés dans le paquet ; `AgentSpec` (perception, trajectoires,
ressenti…) était imposé à toute catégorie ; le worker importait le choix modal et comptait
les désaccords de mode ; l'API refusait un item sans `perception` même pour une catégorie
qui ne s'en sert pas.
**Après :** le gateway ne connaît qu'`AgentItem` (un `agent_id`, le reste libre). Chaque
catégorie est déclarée par un *bundle* (`CategoryBundle` / `CategorySpec`) découvert par
l'entry point `llm_gateway.categories` : c'est le bundle qui valide les items, fixe la
priorité d'un lot et observe la réponse pour ses métriques. Sans bundle installé, toute
requête est refusée en 422 avec la liste des catégories connues (vide).

### Ce qui change pour un consommateur

- **Import :** `from llm_gateway import LLMGatewayClient, LLMRequest` remplace
  `llm_module.sdk`. La façade est paresseuse : importer `llm_gateway` ne charge ni httpx, ni
  prometheus_client, ni FastAPI ; chaque nom est résolu au premier accès.
- **Coquille dépréciée :** `llm_module` reste importable, chaque module réexporte son
  successeur et émet un `DeprecationWarning` ; retrait prévu en 2.0.
- **Version lisible :** `llm_gateway.__version__` (et `pip show llm-gateway`).
- **CLI :** `llm-gateway serve | worker | config validate | config show | categories`.
  `config show` masque les secrets ; `categories` rend 1 quand aucun bundle n'est enregistré.
- **Catégorie validée au démarrage :** template ou schéma absent → `ValueError` à la
  construction du registre, plus à la première requête.

### Ce qui change à l'exploitation

- **Réparation JSON :** `json-repair` remplace `demjson3` pour les sorties LLM mal formées
  (virgules finales, guillemets simples, accolades manquantes, texte parasite).
- **Compteur d'alarmes :** la famille Prometheus `alarme_total{source}` du SDK est créée au
  premier `fire_alarme`, jamais à l'import ; dans le processus API, où le collecteur Redis
  expose déjà cette famille, le compteur passe hors registre. Le démarrage de l'API ne plante
  plus sur `DuplicateTimeseries`.
- **Image Docker :** contexte de build à la racine du dépôt, les trois paquets installés,
  utilisateur non privilégié `gateway`.
- **`.env.example`** livré avec toutes les variables lues (clés `PROVIDER_KEYS__<nom>`,
  Redis, journaux).

### Tests et qualité

- Quatre étages (`unit`, `contract`, `integration`, `e2e`), marqueur posé par le dossier,
  `--strict-markers`. Les contrats des ports tournent sur mémoire, fakeredis (scripts Lua) et
  un Redis réel quand `LLM_GATEWAY_TEST_REDIS_URL` est défini.
- Sous-paquet `llm_gateway.testing` : bundle `echo`, `build_registry`, `FakeAdapter`, ports
  mémoire — un consommateur teste son bundle sans Redis ni réseau.
- Propriétés hypothesis (séquence SWRR, clé de lot), corpus de sorties LLM contre le parseur.
- Couverture exigée : 80 % (`fail_under`). CI GitHub Actions : lint, mypy strict sur
  `core`/`ports`/`sdk`, 5 contrats import-linter, tests avec Redis de service, wheels,
  `mkdocs build --strict`.

### Reporté

Préfixe `LLM_GATEWAY_` des variables d'environnement et sortie de `providers.yaml` du
paquet ; adapter OpenAI-compatible générique ; exécuteur sans Celery ; authentification
(ticket 036) ; licence.

## [1.0.0] - 2026-07-07

Restructuration de `llm_module` en package ports & adapters : composition explicite
(`create_app`, `build_deps`), fin des effets de bord à l'import (le reset des fenêtres RPM
devient un geste du lifespan de l'API), compteurs du worker dans un hash Redis unique,
client httpx partagé par adapter, SDK typé (`TaskResult`). Compte rendu :
`docs/arch/llm-module-package-refactor.md` du dépôt.
