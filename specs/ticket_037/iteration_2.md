# Ticket 037 — Itération 2 : paramétrage en couches et généricité

> Plan d'architecture soumis à validation le 2026-09-07. Aucun code avant le GO.
> Estimation : 4 jours en cinq lots livrables séparément, chacun avec ses tests, sa CI verte et son
> entrée de changelog. Ordre imposé par les dépendances : A → B → C → D → E.

## Lot A — Réglages en couches (1,5 j)

**Fichiers.** `llm_gateway/src/llm_gateway/config/settings.py` (refonte), `config/sources.py` (nouveau :
sources pydantic-settings), `config/providers.py` (nouveau : modèle du fichier des providers),
`config/profiles/free-tier.yaml` et `paid.yaml` (nouveaux), `config/providers.example.yaml` (remplace le
fichier livré), `ports/learned_limits.py` + `infra/{redis,memory}/learned_limits.py` (nouveaux),
`api/routes.py` (`GET /config`, `GET /config/providers`), `cli.py` (`config schema`),
`tools/gen_settings_doc.py` (nouveau : génère `docs/reference/reglages.md`).

**Structures.** `GatewaySettings(BaseSettings)` avec `env_prefix="LLM_GATEWAY_"`, `env_nested_delimiter="__"`,
composé de sous-modèles :

| Sous-modèle | Champs | Remplace |
|---|---|---|
| `redis` | `url` | `REDIS_URL` |
| `executor` | `kind` (celery, réservé : inprocess), `celery_broker_url`, `celery_result_backend` | `CELERY_*` |
| `providers` | `file: Path \| None`, `learned_state: redis \| file \| none`, `learned_state_file` | `config/providers.yaml` dans le paquet |
| `inference` | `temperature=0.7`, `top_p=None`, `max_tokens=4096` | littéraux du worker |
| `batching` | les six réglages actuels, docstring = méthode de mesure | champs à plat |
| `resilience` | `max_retries`, `backoff_base_seconds`, `provider_switch_cooldown_seconds`, `disable_after_consecutive_errors=30` | `circuit_breaker_threshold` supprimé, le `30` codé du worker |
| `api` | `cors_origins: list[str] = []`, `max_request_bytes`, `auth_tokens` (vide, ticket 036) | `allow_origins=["*"]` |
| `telemetry` | `log_level`, `log_format` (text, json), `service_name`, `workdir`, `exchanges_file=None`, `exchanges_max_bytes`, `redactor: str \| None` | `LOG_LEVEL`, `SERVICE_NAME`, `APP_WORKDIR`, `LLM_EXCHANGES_FILE` |
| `provider_keys` | `dict[str, SecretStr]` | `PROVIDER_KEYS__x` (inchangé, préfixé) |

**Logique des sources**, de la plus forte à la plus faible : arguments du constructeur, environnement
préfixé, `.env`, fichier YAML désigné par `LLM_GATEWAY_CONFIG`, profil désigné par `LLM_GATEWAY_PROFILE`,
défauts. Une source `LegacyEnvSource` lit encore les anciens noms non préfixés pendant une version et
journalise un avertissement de dépréciation par variable trouvée : le `.env` de l'auteur continue de
fonctionner sans modification.

`ProvidersFile(BaseModel, extra="forbid")` : `providers: dict[str, ProviderEntry]`, `ProviderEntry` = l'actuel
`ProviderConfig` moins les champs calculés, plus `inference: InferenceOverrides | None`. Erreur de validation
nommant le provider et la clé. Le fichier de déploiement quitte le paquet : `config/llm_gateway/providers.yaml`
à la racine du dépôt, monté dans `api`/`worker` sous `/app/config/providers.yaml`,
`LLM_GATEWAY_PROVIDERS__FILE` dans le compose. `make providers` (`scripts/providers/refresh.py`) écrit au
nouveau chemin. Les consommateurs qui lisaient le fichier (`llm-agents/settings.py`,
`llm-agents/experiences/ressources.py`, `scripts/dashboard/metrics.py`) interrogent `GET /config/providers`
(sans secrets), avec repli sur le fichier quand l'API est injoignable.

`LearnedLimits` (port) : `get(provider) -> int | None`, `set(provider, limit)`. Implémentations Redis (hash
`llm_gateway:learned:max_output_tokens`) et fichier JSON (mode sans Redis). `learn_provider_max_output_tokens`
n'écrit plus dans un YAML ; au démarrage, les limites apprises se fusionnent par-dessus la configuration, avec
une ligne de log par provider. La configuration effective est journalisée une fois au démarrage, secrets
masqués (`config show` existe déjà).

**Tests.** Précédence des six sources ; source héritée avec avertissement ; clé inconnue dans le YAML ;
fichier des providers absent → erreur explicite ; contrat `LearnedLimits` (mémoire, fakeredis, Redis CI) ;
`GET /config` masque les secrets ; profil `free-tier` charge.

## Lot B — Cascade des paramètres d'inférence (0,5 j)

`core/inference.py` (pur) : `InferenceParams(temperature, top_p, max_tokens)` et
`resolve_inference(request_parameters, provider_overrides, defaults) -> InferenceParams`, requête puis
provider puis défaut global. `InternalRequest` gagne `top_p: float | None`. Le worker appelle `resolve_inference`
et perd ses littéraux `0.7` et `4096`. Les adapters envoient `top_p` quand il est défini. Tests unitaires
de la cascade et du payload de chaque adapter.

## Lot C — Adapters (1 j)

`adapters/openai_compatible.py` : `OpenAICompatibleAdapter(BaseAdapter)` paramétré par `structured_output`
(`json_schema`, `json_object`, `none`) et le nom de l'en-tête d'authentification. `openai`, `groq`, `cerebras`,
`mistral` deviennent des sous-classes de trois lignes ; un fournisseur compatible s'ajoute désormais par
configuration seule (`adapter: openai_compatible`, `structured_output: json_object`). `ping()` disparaît
partout (jamais appelé). `BaseAdapter._post()` centralise l'appel HTTP et convertit
`httpx.TimeoutException`, `ConnectError`, `RemoteProtocolError` en `ProviderServerError` (`error_type`
`network_timeout`, `network_connect`) : le worker les réessaie comme un 5xx. Découverte par entry point
`llm_gateway.adapters` (nom → classe) en plus des cinq modules intégrés. Tests sur transport httpx simulé
pour l'adapter générique et les erreurs réseau ; la couverture du gateway remonte à 80 % et le cliquet
`fail_under` avec elle.

## Lot D — Télémétrie et journal des échanges (0,5 j)

`telemetry/exchanges.py` : `ExchangeRecord`, `Redactor = Callable[[ExchangeRecord], ExchangeRecord]`,
rédacteurs livrés `identity`, `FieldRedactor(fields, mode=hash|mask)`, `TruncateRedactor(max_chars)`,
choisi par chemin pointé dans `telemetry.redactor` ; rotation par taille. Journal **désactivé par défaut**
(`exchanges_file=None`) ; le compose de la simulation l'active explicitement. Le journal de dialogue du
SDK (`dialogue_log_file`) passe à `None` par défaut ; le contrôleur le demande explicitement s'il le veut.
`configure_logging()` ne retire plus que le handler qu'il a lui-même posé (identifiant conservé) ; le
remplacement du handler par défaut de loguru devient une option des points d'entrée `serve` et `worker`.
Métriques : `CategoryBundle` déclare ses familles Prometheus (`MetricFamilySpec(name, help, labels,
redis_prefix)`) et `WorkerMetricsCollector` les rend génériquement ; le bundle mobilité déclare les familles
existantes sous leurs noms actuels, les dashboards Grafana 04 et 07 ne bougent pas. Les familles génériques
gardent aussi leurs noms (renommage en `llm_gateway_*` différé, il casserait les dashboards).

## Lot E — Rangement des catégories et restes (0,5 j)

`CategorySpec` gagne `template_path` et `schema_path` optionnels ; `mobility_llm/categories/<nom>/`
regroupe `template.md.j2` et `output_schema.json` ; `prompts.yaml` (variantes) reste où il est, chemin
cité par prompt_calibration et les expériences. `PromptManager` accepte plusieurs répertoires de templates
et des schémas par catégorie. Suppression de `circuit_breaker_threshold`. ADR 0003 « couches de
configuration », `reglages.md` régénéré par `tools/gen_settings_doc.py`, CHANGELOG 1.2.0 du gateway,
quickstart et compose sur les nouveaux noms de variables, ticket 037 mis à jour.

## Ce que l'itération ne fait pas

Exécuteur in-process (itération 4), authentification (ticket 036), renommage des familles Prometheus,
versioning et publication (itération 3), reformatage `ruff format`.

## Risques et garde-fous

- Renommage des variables d'environnement : `LegacyEnvSource` + avertissement, aucune modification du
  `.env` de l'auteur, compose basculé dans le même commit que le code.
- Sortie de `providers.yaml` du paquet : `make providers`, le dashboard et le contrôleur suivent dans le
  même lot ; prompt_calibration (dépôt autonome) lit `llm_module.config.get_settings()` via la coquille,
  qui continue de fonctionner puisque le chemin du fichier vient des réglages.
- Chaque lot se termine par : trois suites vertes, suite llm-agents verte, import-linter, CI verte.
