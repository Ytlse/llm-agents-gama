# Réglages

!!! note "Rédigé à la main le 2026-09-07"
    Cette page recopie `config/settings.py`. Les variables d'environnement n'ont **pas de
    préfixe** pour l'instant : `REDIS_URL`, `PROVIDER_KEYS__mistral`. Le préfixe
    `LLM_GATEWAY_` viendra avec le paramétrage en couches (itération suivante du ticket 037).
    Modèle : `llm_gateway/.env.example`.

`Settings` est une `BaseSettings` pydantic-settings avec `env_nested_delimiter="__"`.
Construite explicitement par les fabriques (`create_app`, `create_celery_app`, tests), jamais
à l'import. Construire `Settings()` lit `providers.yaml` et l'environnement — aucun accès
Redis ni réseau. `get_settings()` (`lru_cache`) y ajoute le filtre des providers sans clé.
Les noms sont insensibles à la casse ; un `.env` n'est pas lu par pydantic (c'est
docker-compose, ou `set -a; source .env`, qui l'injecte).

## `Settings`

| Champ | Type | Défaut | Variable | Sens |
|---|---|---|---|---|
| `redis_url` | `str` | `redis://localhost:6379/0` | `REDIS_URL` | store des tâches, files de lot, rate-limiter, hash `wmetrics` |
| `celery_broker_url` | `str` | `redis://localhost:6379/1` | `CELERY_BROKER_URL` | broker Celery |
| `celery_result_backend` | `str` | `redis://localhost:6379/2` | `CELERY_RESULT_BACKEND` | backend de résultats Celery |
| `circuit_breaker_threshold` | `float` | `0.95` | `CIRCUIT_BREAKER_THRESHOLD` | déclaré ; **aucun usage dans le code** au 2026-09-07 |
| `max_retries` | `int` | `50` | `MAX_RETRIES` | plafond de `self.retry()` Celery pour un lot (5xx, 429, 400 apprise) ; borne aussi le nombre de bascules |
| `backoff_base_seconds` | `float` | `1.0` | `BACKOFF_BASE_SECONDS` | délai de retry `min(base × 2^tentative, 30 s)` |
| `provider_switch_cooldown_seconds` | `int` | `30` | `PROVIDER_SWITCH_COOLDOWN_SECONDS` | cooldown du provider fautif lors d'une bascule (parse, 4xx), pour que la rotation en choisisse un autre |
| `batch_max_agents` | `int` | `5` | `BATCH_MAX_AGENTS` | repli de `get_batch_max_agents` si aucun provider n'est configuré |
| `batch_delay_seconds` | `float` | `3.0` | `BATCH_DELAY_SECONDS` | fenêtre d'accumulation d'un lot sous le seuil de dispatch ; calée sur l'inter-arrivée mesurée des prompts (run 2026-07-10 : p50 = 1,4 s) |
| `batch_target_agents` | `int` | `10` | `BATCH_TARGET_AGENTS` | taille de file déclenchant un dispatch immédiat côté API, bornée par le plus gros provider ; découplée du min des providers (qui vaut 1) |
| `assumed_prompt_tokens` | `int` | `2200` | `ASSUMED_PROMPT_TOKENS` | tokens d'entrée max supposés par agent (historique + 10 %) ; dimensionne `batch_max_agents` et la réservation TPM |
| `assumed_output_tokens` | `int` | `800` | `ASSUMED_OUTPUT_TOKENS` | tokens de sortie estimés par agent ; avec le précédent, 3 000 tokens/agent (mesuré 2026-07-10 : ≈ 1 600, p90 ≈ 2 400, soit 25 % de marge) |
| `token_chars_ratio` | `float` | `3.0` | `TOKEN_CHARS_RATIO` | tokens ≈ caractères / ratio, pour estimer le prompt rendu (mesuré sur 427 échanges : p50 = 3,24, p10 = 3,05 ; 3,0 laisse 8 % de marge) |
| `max_batch_agents` | `int` | `20` | `MAX_BATCH_AGENTS` | plafond absolu du `batch_max_agents` calculé par provider |
| `min_output_tokens` | `int` | `512` | `MIN_OUTPUT_TOKENS` | budget de sortie minimal par requête ; en dessous, le provider est exclu au démarrage ou le lot rejoué ailleurs |
| `max_output_tokens` | `int` | `16384` | `MAX_OUTPUT_TOKENS` | plafond du `max_tokens` envoyé (limite de complétion de gpt-4o-mini, le plus contraint des providers configurés) |
| `provider_keys` | `dict[str, SecretStr]` | `{}` | `PROVIDER_KEYS__<nom>` | une clé par instance de `providers.yaml` ou par adapter ; résolution `provider_keys[instance] or provider_keys[adapter]` |
| `providers` | `dict[str, ProviderConfig]` | construit | — | **pas lu de l'env** : `build_providers` (validateur `after`) charge `providers.yaml`, calcule `batch_max_agents` et `tpm_estimate_per_request`, injecte la clé |

Méthodes : `get_batch_max_agents(force_provider)` — limite du provider forcé, sinon le
**minimum** des providers (conservateur, utilisé par le worker au pop) ;
`get_dispatch_threshold(force_provider)` — capacité du provider forcé, sinon
`min(batch_target_agents, max des batch_max_agents)` (utilisé par l'API).

## `ProviderConfig`

Une entrée de `providers.yaml` (`src/llm_gateway/config/providers.yaml`), après calcul.

| Champ | Type | Défaut | Sens |
|---|---|---|---|
| `api_key` | `SecretStr` | `""` | injectée depuis `provider_keys` ; vide → instance exclue de la rotation par `filter_providers_without_api_key` |
| `rpm_limit` | `int` | obligatoire | requêtes/minute, fenêtre glissante 60 s, lissage `min_interval = 60 / rpm` |
| `tpm_limit` | `int | None` | `None` | tokens/minute estimés réservés dans la même fenêtre ; borne `batch_max_agents` |
| `rpd_limit` | `int | None` | `None` | requêtes/jour (UTC) ; atteint → écarté jusqu'à minuit UTC |
| `tpd_limit` | `int | None` | `None` | tokens/jour (UTC), comptés a posteriori sur les tokens réels ; même mise à l'écart |
| `max_tokens_per_request` | `int | None` | `None` | capacité d'une requête unique ; exclu au démarrage si `< batch_max_agents × assumed_prompt_tokens + min_output_tokens` ; garde-fou 413 au rendu |
| `max_output_tokens` | `int | None` | `None` | plafond de complétion du modèle ; `None` = repli sur `settings.max_output_tokens` ; **appris sur HTTP 400 et persisté** dans le fichier |
| `base_url` | `str` | obligatoire | racine de l'API du fournisseur |
| `default_model` | `str` | obligatoire | modèle si la requête n'en impose pas |
| `weight` | `float` | `1.0` | poids SWRR ; `0` = hors rotation |
| `batch_max_agents` | `int` | `1` (calculé) | `max(1, min(tpm_limit // 3000 ou rpm, max_tokens_per_request // 3000 ou max_batch_agents, rpm_limit, max_batch_agents))` — ne pas écrire dans le fichier |
| `tpm_estimate_per_request` | `int | None` | calculé | `batch_max_agents × 3000` si `tpm_limit`, sinon `None` ; réservation TPM initiale |
| `concurrency_limit` | `int` | `2` | workers Celery simultanés sur ce provider |
| `disable_timeout` | `int` | `180` | secondes de désactivation après 30 erreurs consécutives |
| `adapter` | `str` | `""` (= nom de l'instance) | classe d'adapter (`openai`, `mistral`, `google`, `groq`, `cerebras`) et clé héritée |

`repr(ProviderConfig)` n'affiche que la longueur de la clé. `llm-gateway config show`
imprime la configuration effective avec les secrets masqués.

!!! warning "Clés inconnues"
    `ProviderConfig` ne fixe pas `extra` : une clé YAML mal orthographiée est **ignorée sans
    erreur**. Le refus des clés inconnues annoncé dans le ticket 037 n'est pas dans le code au
    2026-09-07.

## Variables lues ailleurs que dans `Settings`

| Variable | Lue par | Sens |
|---|---|---|
| `LOG_LEVEL` | `telemetry/logger.configure_logging` | niveau du handler loguru posé par les fabriques (défaut `INFO`) |
| `SERVICE_NAME` | idem | si défini, sink fichier `APP_WORKDIR/<SERVICE_NAME>.log` (rotation 10 MB, rétention 7 jours, `enqueue=True`) ; docker-compose : `api`, `worker` |
| `APP_WORKDIR` | `telemetry/logger` | dossier de `llm_exchanges.jsonl`, `llm_errors.jsonl` et du sink service (défaut `.`) ; docker-compose : `/app/experiments/current` |
| `LLM_EXCHANGES_FILE` | `log_llm_exchange` | chemin complet du journal des échanges, prime sur `APP_WORKDIR/llm_exchanges.jsonl` |
| `LLM_GATEWAY_TEST_REDIS_URL` | `tests/contract/conftest.py` | ajoute le backend Redis réel aux tests de contrat |
| `LLM_GATEWAY_E2E_URL` | tests `e2e` | gateway en marche ; absent → sautés |

## Ce qui n'est pas un réglage

Les délais d'attente d'un provider saturé (8 s, un essai toutes les 2 s, 2 retries de 12 s),
le seuil de désactivation (30 erreurs consécutives), le cooldown 5xx (60 s), le plafond de
backoff (30 s), le timeout HTTP d'un adapter (`request_timeout` de classe : 120 s, 240 s pour
Google) et le seuil d'alarme du SDK (10 échecs) sont des constantes du code.
