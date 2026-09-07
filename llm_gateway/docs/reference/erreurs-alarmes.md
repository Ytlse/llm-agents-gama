# Erreurs et alarmes

## Hiérarchie des exceptions

Déclarées dans `adapters/base.py`, sauf `ProviderCapacityError` (`worker/task_worker.py`).

```
Exception
├── ProviderError(provider, status_code, message, error_type="unknown", ratelimit_reset=None)
│   ├── ProviderServerError      # HTTP 5xx — et 503 synthétisé sur une sortie tronquée (finish_reason=length / MAX_TOKENS)
│   └── ProviderClientError      # HTTP 4xx — 429, 400 max_tokens, 401, 402, 413…
├── ProviderParseError(provider, raw, detail)   # JSON illisible, clé `agents` absente, item hors AgentResponse, boucle de répétition
└── ProviderCapacityError(provider, prompt_tokens_est, max_tokens_per_request)   # levée AVANT l'appel HTTP
```

`error_type` est la clé de la famille `llm_provider_errors_by_type_total` : les dix premiers
mots du message du fournisseur (`extract_error_type`), `max_tokens_truncation` pour une
troncature, `parse error …` pour un parse. `ratelimit_reset` vient de `retry-after`,
`x-ratelimit-reset-tokens`, `x-ratelimit-reset-requests`, `x-ratelimit-reset`, ou du corps
JSON d'un 429 (Gemini : `error.details[].retryDelay` ou « Please retry in 11.1s »).

## Ce que le worker fait de chaque erreur

`process_batch_task` (`worker/task_worker.py`), dans l'ordre des `except` :

| Erreur | Réaction | Puis |
|---|---|---|
| **Aucun provider disponible** (`RuntimeError` de `select_provider`) | attente locale jusqu'à 8 s, un essai toutes les 2 s ; 2 `retry` Celery (countdown 12 s) | `[ALARME] Tous les providers LLM saturés ou indisponibles`, compteur `alarme:providers_satures`, **échec** de jusqu'à 100 tâches de la file |
| `ProviderCapacityError` | slot RPM/TPM restitué, `capacity_reroute_total:<p>` | **bascule** |
| `ProviderServerError` (5xx, troncature) | cooldown du provider **60 s**, `retry` Celery après `min(backoff_base_seconds × 2^tentative, 30 s)` tant que `retries < max_retries` (50) | sinon échec « Max retries dépassé suite à une erreur 5xx » |
| `ProviderClientError` **429** | cooldown = délai annoncé par le provider (`_parse_ratelimit_reset_seconds`, +2 s de marge, borné à [10, 3600] s, défaut 60), même backoff et `retry` | sinon échec « Max retries dépassé … Rate Limits » |
| `ProviderClientError` **400 max_tokens** | si le message donne une limite N (formats Groq, OpenAI, Google) **et** qu'elle est plus stricte que la connue : `learn_provider_max_output_tokens` (config mémoire + `providers.yaml`), `retry` après 1 s | si la limite était déjà connue : **bascule** (pour ne pas boucler sur la même 400) |
| `ProviderClientError` autre 4xx | — | **bascule** |
| `ProviderParseError` | log WARNING avec les 300 premiers caractères du brut | **bascule** ; en dernier recours, échec avec `error = "<détail>\nRaw LLM response:\n<brut>"` |
| `RuntimeError` inattendue | `logger.exception` | échec |
| toute autre `Exception` | `logger.exception` | échec |

**Bascule** (`_switch_provider_or_fail`) : le provider fautif reçoit un cooldown de
`provider_switch_cooldown_seconds` (30 s), le lot est remis en file et rejoué **sans**
`force_provider` pour que la rotation choisisse un autre modèle. Nombre de bascules borné à
`min(max_retries, max(1, len(providers) − 1))` : une requête réellement invalide finit par
échouer sur tous les providers.

En plus, indépendamment du type : chaque appel échoué incrémente le compteur d'erreurs
consécutives du provider ; à **30**, le provider est désactivé `disable_timeout` secondes
(180 par défaut) et le compteur remis à zéro. Un succès remet le compteur à zéro.

Une tâche échouée est persistée en `failed` avec son `error`, publiée sur Pub/Sub (le
long-poll rend la main aussitôt) et journalisée en ERROR : `Tâche échouée | task_id=…
error=…`.

## Convention `[ALARME]`

Une anomalie **confirmée** — seuil franchi, erreur répétée — se journalise en ERROR avec le
préfixe `[ALARME]`, sur **front montant** (une fois par épisode, pas à chaque occurrence), et
compte dans la famille Prometheus `alarme_total{source}` :

- dans un processus qui expose `/metrics` (contrôleur GAMA, SDK) : `fire_alarme(source)`
  (`telemetry/alarms.py`), à côté du `logger.error("[ALARME] …")`. Le compteur est **créé au
  premier appel**, jamais à l'import ; si la famille existe déjà dans le registre (processus
  API), il passe hors registre pour éviter `DuplicateTimeseries` ;
- dans le worker Celery (pas de `/metrics`) : `metrics.incr("alarme:<source>")` dans Redis,
  relu par le collecteur de l'API sous le même nom de famille.

`source` est un slug court et stable (faible cardinalité). `make error` depuis la racine du
dépôt liste les `[ALARME]` des journaux du run.

## Sources d'alarme dans le code (2026-09-07)

| Où | Source / compteur | Déclenchement | Réarmement |
|---|---|---|---|
| `worker/task_worker.py` | `alarme:providers_satures` | tous les providers saturés ou indisponibles après 8 s et 2 retries ; les tâches de la file échouent | à chaque épisode (pas de front montant explicite : l'événement est déjà rare) |
| `sdk/client.py` | `gateway_llm` | 10 tâches échouées d'affilée côté client ; arme la backpressure | premier succès |
| `sdk/client.py` | `gateway_llm_circuit` | disjoncteur ouvert (10 échecs consécutifs) ; soumissions suspendues | sonde réussie |
| `mobility_llm/categories/itinary_multi_agent.py` | `alarme:mode_label_mismatch` | plus de 5 % des étiquettes de mode en désaccord sur ≥ 200 options vérifiées | jamais (le compteur Redis persiste : une seule alarme par vie du hash) |
| `config/settings.py` | log seul | provider introuvable dans `providers.yaml`, ou fichier non inscriptible, lors de la persistance d'un `max_output_tokens` appris | — |
| `adapters/google_adapter.py` | log seul | 3 troncatures `MAX_TOKENS` consécutives sur une instance | première complétion propre |
| `mobility_llm/mode_choice.py` | log seul | vecteur de probabilités absent ou de somme nulle → repli uniforme, la décision du modèle est perdue | — |
| `mobility_core/zone_resolver.py` | log seul | plus de 15 % des points hors couche de zones fines sur ≥ 200 points (attendu ~5 %) | sous 8 % |

Les alarmes « log seul » ne comptent pas dans `alarme_total` : elles sont visibles dans les
journaux et par `make error`, pas dans Grafana.

## Journaux d'erreur

- `APP_WORKDIR/llm_errors.jsonl` : une ligne par appel LLM échoué (`time`, `task_id`,
  `provider`, `error_type`, `error_message`, `http_status`, `ratelimit_reset`).
- Ring buffer Redis `llm:recent_errors` (50 dernières), servi par `GET /errors/recent`.
- `llm_call_completed | … status=failed` en ERROR à chaque appel échoué, `status=success`
  en INFO à chaque appel réussi : un worker muet n'est pas un worker qui va bien.
