# Réglages

> Page **générée** par `tools/gen_settings_doc.py` depuis les modèles pydantic ; la relancer après
> tout changement de `config/settings.py` ou `config/providers.py`.

Les réglages sont **groupés** et viennent de six sources, de la plus forte à la plus faible :
arguments du constructeur, environnement `LLM_GATEWAY_*` (`__` sépare les niveaux :
`LLM_GATEWAY_BATCHING__DELAY_SECONDS`), anciens noms non préfixés (dépréciés, une version, un
avertissement par variable trouvée), fichier YAML désigné par `LLM_GATEWAY_CONFIG`, profil désigné par
`LLM_GATEWAY_PROFILE` (`free-tier`, `paid`), défauts du code. Les clés d'API se lisent sous
`LLM_GATEWAY_PROVIDER_KEYS__<nom>` **ou** `PROVIDER_KEYS__<nom>` (nom canonique partagé avec le compose,
`make providers` et prompt_calibration, sans avertissement).

## Champs de premier niveau

| Champ | Type | Défaut | Variable | Sens |
|---|---|---|---|---|
| `providers_file` | `Path | NoneType` | `None` | `LLM_GATEWAY_PROVIDERS_FILE` | fichier des fournisseurs (configuration de déploiement). `None` = exemple livré chargé avec un avertissement. |
| `learned_limits` | `Literal[redis, file, none]` | `'redis'` | `LLM_GATEWAY_LEARNED_LIMITS` | où vivent les limites apprises (`max_output_tokens` révélé par HTTP 400) : `redis`, `file`, `none`. |
| `learned_limits_file` | `Path | NoneType` | `None` | `LLM_GATEWAY_LEARNED_LIMITS_FILE` | chemin du fichier JSON quand `learned_limits=file` ; défaut `<telemetry.workdir>/learned_limits.json`. |
| `provider_keys` | `dict[str, SecretStr]` | `vide` | `LLM_GATEWAY_PROVIDER_KEYS__<nom>` ou `PROVIDER_KEYS__<nom>` | clés d'API par instance ou par adapter ; résolution `provider_keys[instance] or provider_keys[adapter]`. |
| `providers` | `dict[str, ProviderConfig]` | `vide` | — | **construit** après validation : instances résolues (`ProviderConfig`), pas lu de l'environnement. |
| `declared_providers` | `list[str]` | `vide` | — | **construit** : noms déclarés dans le fichier, avec ou sans clé. |

## `redis`

Connexion Redis : store des tâches, files de lot, rate-limiter, compteurs, limites apprises.

| Champ | Type | Défaut | Variable | Sens |
|---|---|---|---|---|
| `url` | `str` | `'redis://localhost:6379/0'` | `LLM_GATEWAY_REDIS__URL` (ex-`REDIS_URL`) |  |

## `executor`

Exécution des lots. `celery` aujourd'hui ; un exécuteur in-process est prévu.

| Champ | Type | Défaut | Variable | Sens |
|---|---|---|---|---|
| `kind` | `Literal[celery]` | `'celery'` | `LLM_GATEWAY_EXECUTOR__KIND` |  |
| `celery_broker_url` | `str` | `'redis://localhost:6379/1'` | `LLM_GATEWAY_EXECUTOR__CELERY_BROKER_URL` (ex-`CELERY_BROKER_URL`) |  |
| `celery_result_backend` | `str` | `'redis://localhost:6379/2'` | `LLM_GATEWAY_EXECUTOR__CELERY_RESULT_BACKEND` (ex-`CELERY_RESULT_BACKEND`) |  |

## `inference`

Défauts d'inférence ; surchargés par provider (`inference:` du fichier) puis par requête.

| Champ | Type | Défaut | Variable | Sens |
|---|---|---|---|---|
| `temperature` | `float` | `0.7` | `LLM_GATEWAY_INFERENCE__TEMPERATURE` |  |
| `top_p` | `float | NoneType` | `None` | `LLM_GATEWAY_INFERENCE__TOP_P` |  |
| `max_tokens` | `int` | `4096` | `LLM_GATEWAY_INFERENCE__MAX_TOKENS` |  |

## `batching`

Micro-batching : valeurs mesurées sur les runs de juillet 2026, à recalibrer ailleurs.

| Champ | Type | Défaut | Variable | Sens |
|---|---|---|---|---|
| `max_agents` | `int` | `5` | `LLM_GATEWAY_BATCHING__MAX_AGENTS` (ex-`BATCH_MAX_AGENTS`) |  |
| `delay_seconds` | `float` | `3.0` | `LLM_GATEWAY_BATCHING__DELAY_SECONDS` (ex-`BATCH_DELAY_SECONDS`) |  |
| `target_agents` | `int` | `10` | `LLM_GATEWAY_BATCHING__TARGET_AGENTS` (ex-`BATCH_TARGET_AGENTS`) |  |
| `assumed_prompt_tokens` | `int` | `2200` | `LLM_GATEWAY_BATCHING__ASSUMED_PROMPT_TOKENS` (ex-`ASSUMED_PROMPT_TOKENS`) |  |
| `assumed_output_tokens` | `int` | `800` | `LLM_GATEWAY_BATCHING__ASSUMED_OUTPUT_TOKENS` (ex-`ASSUMED_OUTPUT_TOKENS`) |  |
| `token_chars_ratio` | `float` | `3.0` | `LLM_GATEWAY_BATCHING__TOKEN_CHARS_RATIO` (ex-`TOKEN_CHARS_RATIO`) |  |
| `max_batch_agents` | `int` | `20` | `LLM_GATEWAY_BATCHING__MAX_BATCH_AGENTS` (ex-`MAX_BATCH_AGENTS`) |  |
| `min_output_tokens` | `int` | `512` | `LLM_GATEWAY_BATCHING__MIN_OUTPUT_TOKENS` (ex-`MIN_OUTPUT_TOKENS`) |  |
| `max_output_tokens` | `int` | `16384` | `LLM_GATEWAY_BATCHING__MAX_OUTPUT_TOKENS` (ex-`MAX_OUTPUT_TOKENS`) |  |

## `resilience`

Réessais, bascule de fournisseur, désactivation après erreurs consécutives.

| Champ | Type | Défaut | Variable | Sens |
|---|---|---|---|---|
| `max_retries` | `int` | `50` | `LLM_GATEWAY_RESILIENCE__MAX_RETRIES` (ex-`MAX_RETRIES`) |  |
| `backoff_base_seconds` | `float` | `1.0` | `LLM_GATEWAY_RESILIENCE__BACKOFF_BASE_SECONDS` (ex-`BACKOFF_BASE_SECONDS`) |  |
| `provider_switch_cooldown_seconds` | `int` | `30` | `LLM_GATEWAY_RESILIENCE__PROVIDER_SWITCH_COOLDOWN_SECONDS` (ex-`PROVIDER_SWITCH_COOLDOWN_SECONDS`) |  |
| `disable_after_consecutive_errors` | `int` | `30` | `LLM_GATEWAY_RESILIENCE__DISABLE_AFTER_CONSECUTIVE_ERRORS` |  |
| `provider_wait_seconds` | `float` | `8.0` | `LLM_GATEWAY_RESILIENCE__PROVIDER_WAIT_SECONDS` |  |
| `saturation_poll_seconds` | `float` | `2.0` | `LLM_GATEWAY_RESILIENCE__SATURATION_POLL_SECONDS` |  |
| `saturation_retries` | `int` | `2` | `LLM_GATEWAY_RESILIENCE__SATURATION_RETRIES` |  |
| `saturation_retry_seconds` | `float` | `12.0` | `LLM_GATEWAY_RESILIENCE__SATURATION_RETRY_SECONDS` |  |
| `abandon_when_busy` | `bool` | `False` | `LLM_GATEWAY_RESILIENCE__ABANDON_WHEN_BUSY` |  |

## `api`

Couche HTTP : CORS, taille de requête, jetons (ticket 036, non appliqués).

| Champ | Type | Défaut | Variable | Sens |
|---|---|---|---|---|
| `cors_origins` | `list[str]` | `vide` | `LLM_GATEWAY_API__CORS_ORIGINS` |  |
| `max_request_bytes` | `int` | `2000000` | `LLM_GATEWAY_API__MAX_REQUEST_BYTES` |  |
| `auth_tokens` | `list[SecretStr]` | `vide` | `LLM_GATEWAY_API__AUTH_TOKENS` |  |

## `telemetry`

Logs, dossier du run, journal des échanges.

| Champ | Type | Défaut | Variable | Sens |
|---|---|---|---|---|
| `log_level` | `str` | `'INFO'` | `LLM_GATEWAY_TELEMETRY__LOG_LEVEL` (ex-`LOG_LEVEL`) |  |
| `log_format` | `Literal[text, json]` | `'text'` | `LLM_GATEWAY_TELEMETRY__LOG_FORMAT` |  |
| `service_name` | `str | NoneType` | `None` | `LLM_GATEWAY_TELEMETRY__SERVICE_NAME` (ex-`SERVICE_NAME`) |  |
| `workdir` | `Path` | `PosixPath('.')` | `LLM_GATEWAY_TELEMETRY__WORKDIR` (ex-`APP_WORKDIR`) |  |
| `exchanges_enabled` | `bool` | `False` | `LLM_GATEWAY_TELEMETRY__EXCHANGES_ENABLED` |  |
| `exchanges_file` | `Path | NoneType` | `None` | `LLM_GATEWAY_TELEMETRY__EXCHANGES_FILE` (ex-`LLM_EXCHANGES_FILE`) |  |
| `exchanges_max_bytes` | `int` | `200000000` | `LLM_GATEWAY_TELEMETRY__EXCHANGES_MAX_BYTES` |  |
| `redactor` | `str | NoneType` | `None` | `LLM_GATEWAY_TELEMETRY__REDACTOR` |  |

## Fichier des fournisseurs

Un objet `providers:` dont chaque entrée suit `ProviderEntry`. Toute clé inconnue fait échouer le
chargement en nommant le fournisseur et la clé. Schéma JSON : `llm-gateway config schema providers`.

| Champ | Type | Défaut | Sens |
|---|---|---|---|
| `rpm_limit` | `int` | **obligatoire** | requêtes/minute, fenêtre glissante 60 s, lissage `60 / rpm` entre deux requêtes |
| `base_url` | `str` | **obligatoire** | racine de l'API du fournisseur |
| `default_model` | `str` | **obligatoire** | modèle envoyé si la requête n'en impose pas |
| `tpm_limit` | `int | NoneType` | `None` | tokens/minute réservés dans la même fenêtre ; borne `batch_max_agents` |
| `rpd_limit` | `int | NoneType` | `None` | requêtes/jour (fuseau du provider) ; atteint → écarté jusqu'à son reset |
| `quota_reset_tz` | `str` | `UTC` | fuseau où le provider situe minuit (`America/Los_Angeles` pour Google) |
| `tpd_limit` | `int | NoneType` | `None` | tokens/jour (UTC), comptés a posteriori ; même mise à l'écart |
| `max_tokens_per_request` | `int | NoneType` | `None` | capacité d'une requête unique (HTTP 413 au-delà) ; borne le lot et le budget de sortie |
| `max_output_tokens` | `int | NoneType` | `None` | plafond de complétion ; appris sur HTTP 400 et retenu par le store de limites apprises |
| `weight` | `float` | `1.0` | poids SWRR : `min(rpm_limit, tpm_limit / 3000) / 15` |
| `concurrency_limit` | `int` | `2` | workers simultanés autorisés sur l'instance |
| `disable_timeout` | `int` | `180` | durée (s) de mise à l'écart après `disable_after_consecutive_errors` erreurs |
| `adapter` | `str` | `''` | nom de l'adapter (openai_compatible, openai, mistral, google, groq, cerebras, ou un entry point `llm_gateway.adapters`) ; défaut = nom de l'entrée |
| `structured_output` | `Union[Literal[json_schema, json_object, none], NoneType]` | `None` | sortie structurée du traducteur OpenAI-compatible : `json_schema`, `json_object`, `none` ; None = défaut de l'adapter |
| `schema_in_system` | `bool | NoneType` | `None` | recopier le schéma JSON dans le message system ; None = défaut de l'adapter |
| `inference` | `InferenceOverrides | NoneType` | `None` | surcharges `temperature`, `top_p`, `max_tokens` pour cette instance |
| `batch_max_agents` | `int | NoneType` | `None` | toléré pour les anciens fichiers, **ignoré** avec un avertissement : le gateway le calcule |

### `inference` (surcharges par fournisseur)

| Champ | Type | Défaut |
|---|---|---|
| `temperature` | `float | NoneType` | `None` |
| `top_p` | `float | NoneType` | `None` |
| `max_tokens` | `int | NoneType` | `None` |

## `ProviderConfig` (instance résolue)

Ce que le gateway manipule : l'entrée du fichier, la clé injectée et deux valeurs calculées.
`batch_max_agents = max(1, min(tpm_limit / (assumed_prompt_tokens + assumed_output_tokens),
max_tokens_per_request / idem, rpm_limit, batching.max_batch_agents))` ;
`tpm_estimate_per_request = batch_max_agents × (assumed_prompt_tokens + assumed_output_tokens)` si `tpm_limit`.

| Champ | Type | Défaut |
|---|---|---|
| `api_key` | `SecretStr` | `''` |
| `rpm_limit` | `int` | **obligatoire** |
| `tpm_limit` | `int | NoneType` | `None` |
| `rpd_limit` | `int | NoneType` | `None` |
| `tpd_limit` | `int | NoneType` | `None` |
| `max_tokens_per_request` | `int | NoneType` | `None` |
| `max_output_tokens` | `int | NoneType` | `None` |
| `base_url` | `str` | **obligatoire** |
| `default_model` | `str` | **obligatoire** |
| `weight` | `float` | `1.0` |
| `batch_max_agents` | `int` | `1` |
| `tpm_estimate_per_request` | `int | NoneType` | `None` |
| `concurrency_limit` | `int` | `2` |
| `disable_timeout` | `int` | `180` |
| `adapter` | `str` | `''` |
| `structured_output` | `Union[Literal[json_schema, json_object, none], NoneType]` | `None` |
| `schema_in_system` | `bool | NoneType` | `None` |
| `inference` | `InferenceOverrides | NoneType` | `None` |

## Anciens noms encore lus (dépréciés)

| Ancien nom | Nouveau nom |
|---|---|
| `REDIS_URL` | `LLM_GATEWAY_REDIS__URL` |
| `CELERY_BROKER_URL` | `LLM_GATEWAY_EXECUTOR__CELERY_BROKER_URL` |
| `CELERY_RESULT_BACKEND` | `LLM_GATEWAY_EXECUTOR__CELERY_RESULT_BACKEND` |
| `LOG_LEVEL` | `LLM_GATEWAY_TELEMETRY__LOG_LEVEL` |
| `SERVICE_NAME` | `LLM_GATEWAY_TELEMETRY__SERVICE_NAME` |
| `APP_WORKDIR` | `LLM_GATEWAY_TELEMETRY__WORKDIR` |
| `LLM_EXCHANGES_FILE` | `LLM_GATEWAY_TELEMETRY__EXCHANGES_FILE` |
| `MAX_RETRIES` | `LLM_GATEWAY_RESILIENCE__MAX_RETRIES` |
| `BACKOFF_BASE_SECONDS` | `LLM_GATEWAY_RESILIENCE__BACKOFF_BASE_SECONDS` |
| `PROVIDER_SWITCH_COOLDOWN_SECONDS` | `LLM_GATEWAY_RESILIENCE__PROVIDER_SWITCH_COOLDOWN_SECONDS` |
| `BATCH_MAX_AGENTS` | `LLM_GATEWAY_BATCHING__MAX_AGENTS` |
| `BATCH_DELAY_SECONDS` | `LLM_GATEWAY_BATCHING__DELAY_SECONDS` |
| `BATCH_TARGET_AGENTS` | `LLM_GATEWAY_BATCHING__TARGET_AGENTS` |
| `ASSUMED_PROMPT_TOKENS` | `LLM_GATEWAY_BATCHING__ASSUMED_PROMPT_TOKENS` |
| `ASSUMED_OUTPUT_TOKENS` | `LLM_GATEWAY_BATCHING__ASSUMED_OUTPUT_TOKENS` |
| `TOKEN_CHARS_RATIO` | `LLM_GATEWAY_BATCHING__TOKEN_CHARS_RATIO` |
| `MAX_BATCH_AGENTS` | `LLM_GATEWAY_BATCHING__MAX_BATCH_AGENTS` |
| `MIN_OUTPUT_TOKENS` | `LLM_GATEWAY_BATCHING__MIN_OUTPUT_TOKENS` |
| `MAX_OUTPUT_TOKENS` | `LLM_GATEWAY_BATCHING__MAX_OUTPUT_TOKENS` |

`PROVIDER_KEYS__<nom>` n'est pas déprécié : c'est le nom canonique des clés d'API.
