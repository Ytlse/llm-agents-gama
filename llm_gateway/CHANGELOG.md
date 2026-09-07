# Changelog — llm-gateway

Format : `## [version] - AAAA-MM-JJ`, entrées les plus récentes en tête. Le ton est celui de
l'usage : ce que le changement permet ou modifie pour qui s'en sert. Les fichiers touchés
sont dans git.

## [1.3.0] - 2026-09-07 (itération 2, lots B à E)

### Lot B — les paramètres d'inférence se résolvent en cascade

Température, `top_p` et budget de sortie par tâche viennent, dans l'ordre, de la requête
(`parameters`), du fournisseur (bloc `inference:` de son entrée) puis des défauts globaux
(`inference` des réglages). Le worker n'a plus de littéral `0.7` ni `4096` ; `top_p` est envoyé
aux fournisseurs quand il est défini, jamais sinon. Une valeur illisible dans la requête descend
au niveau suivant au lieu de faire échouer le lot.

### Lot D — télémétrie : rien n'est écrit sans le demander, et occupé n'est pas en panne

- **Journal des échanges désactivé par défaut** (`telemetry.exchanges_enabled`) : prompts et
  réponses complets sont des données personnelles potentielles. Activé, il passe par un
  **rédacteur** configurable (`telemetry.redactor`, chemin pointé) : masquage ou hachage de
  champs, troncature, ou le vôtre ; et il tourne par taille (`exchanges_max_bytes`). Le format
  lu par `make report` ne change pas. Le journal de dialogue du SDK est lui aussi opt-in.
- **Logging non intrusif** : `configure_logging` ne retire plus que le handler par défaut de
  loguru, les sinks de l'hôte survivent ; `reset_logging` défait ce qu'il a posé.
- **Familles Prometheus déclarées par les bundles** (`CategoryBundle.metric_families`) : le
  collecteur ne connaît plus les modes de transport, il rend ce que le bundle déclare. Les noms
  mobilité sont conservés, les dashboards Grafana ne bougent pas.
- **Le worker n'abandonne plus une file quand les fournisseurs sont seulement occupés.** Fenêtre
  RPM/TPM pleine, lissage ou concurrence ne sont pas des pannes : le lot attend la fenêtre,
  borné par `max_retries`, avec une alarme `providers_occupes` sur front montant. L'abandon reste
  pour cooldown, désactivation et quota du jour. Le budget d'attente devient réglable
  (`provider_wait_seconds`, `saturation_poll_seconds`, `saturation_retries`,
  `saturation_retry_seconds`, `abandon_when_busy`).

  **Avant :** run Prompt_Minimaliste du 2026-09-07 : une instance forcée à 15 RPM, la moitié des
  sollicitations abandonnées après 48 s, décisions perdues sans réessai.
  **Après :** le lot attend son créneau ; la perte ne vient plus du gateway.

### Lot C — un seul traducteur pour toute API compatible OpenAI

**Avant :** quatre adapters de cent lignes recopiés (OpenAI, Groq, Cerebras, Mistral), un
`ping()` défini partout et appelé nulle part, une liste fermée de modules à éditer pour ajouter
un fournisseur, et les pannes réseau qui échouaient la tâche sans réessai.
**Après :** `OpenAICompatibleAdapter` porte le dialecte `/chat/completions` ; les quatre
deviennent des réglages (`structured_output`, `schema_in_system`) que l'instance du fichier des
fournisseurs peut surcharger. Un fournisseur compatible (Ollama, vLLM, OpenRouter…) s'ajoute par
configuration seule : `adapter: openai_compatible`. Un paquet tiers apporte son adapter par
l'entry point `llm_gateway.adapters`. Délai dépassé, connexion refusée et réponse coupée sont
des `ProviderServerError` (`network_timeout`, `network_connect`, `network_protocol`) : réessayées
avec backoff et cooldown. `ping()` a disparu.

## [1.2.0] - 2026-09-07 (itération 2, lot A)

Les réglages deviennent une configuration de bibliothèque : groupés, préfixés, en couches.

- **Préfixe `LLM_GATEWAY_`** et groupes `redis`, `executor`, `inference`, `batching`, `resilience`,
  `api`, `telemetry` (`LLM_GATEWAY_BATCHING__DELAY_SECONDS`). Six sources dans un ordre fixe :
  constructeur, environnement, anciens noms (dépréciés, avertis), fichier `LLM_GATEWAY_CONFIG`,
  profil `LLM_GATEWAY_PROFILE` (`free-tier`, `paid`), défauts. `PROVIDER_KEYS__<nom>` reste le
  nom canonique des clés d'API.
- **Le fichier des fournisseurs sort du paquet** : `LLM_GATEWAY_PROVIDERS_FILE` le désigne, le
  paquet ne livre qu'un `providers.example.yaml`. Une clé inconnue fait échouer le démarrage en
  nommant le fournisseur et la clé ; `llm-gateway config schema` publie le JSON Schema.
- **Les plafonds de complétion appris** (`max_output_tokens` révélé par un HTTP 400) ne sont plus
  réécrits dans un YAML : ils vivent dans Redis (partagés entre API et workers), un fichier JSON
  ou la mémoire, et se fusionnent au démarrage sans jamais élargir un plafond déclaré.
- **`GET /config`** et **`GET /config/providers`** : la configuration effective, secrets masqués.
- Le CORS n'est plus `*` en dur : `api.cors_origins`, vide par défaut (le compose garde `["*"]`).
- Le seuil de désactivation d'un fournisseur (`30` erreurs consécutives, codé dans le worker)
  devient `resilience.disable_after_consecutive_errors` ; `circuit_breaker_threshold`, jamais lu,
  disparaît.

**Avant :** `REDIS_URL`, `APP_WORKDIR` partagés avec le contrôleur ; `providers.yaml` dans le paquet
et réécrit par le worker ; `Settings` à plat.
**Après :** `LLM_GATEWAY_REDIS__URL`, `LLM_GATEWAY_TELEMETRY__WORKDIR` ; fichier de déploiement
désigné, jamais modifié ; `settings.batching.delay_seconds`, alias à plat conservés une version.

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
