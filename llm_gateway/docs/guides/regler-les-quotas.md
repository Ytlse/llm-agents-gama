# Régler les quotas

Le gateway travaille avec des fournisseurs free tier aux quotas petits et différents. Ce
guide dit quel réglage borne quoi, comment lire un `batch_max_agents` de 2, et comment
rafraîchir les chiffres. Les valeurs par défaut sont celles de `config/settings.py` et de
`config/providers.yaml` ; la liste complète est dans [Réglages](../reference/reglages.md).

## Les quatre quotas d'un provider

| Champ | Fenêtre | Comment il est appliqué |
|---|---|---|
| `rpm_limit` | 60 s glissantes | réservation atomique avant chaque appel (script Lua) ; lissage : deux appels espacés de moins de `60 / rpm` s sont refusés (à 15 RPM : 4 s) |
| `tpm_limit` | 60 s glissantes | réservation des tokens **estimés** avant l'appel, recalée sur le prompt rendu puis sur la consommation réelle ; dépassement → refus, le balancer passe au provider suivant |
| `rpd_limit` | jour UTC | compté à la réservation ; atteint → provider écarté jusqu'à minuit UTC (`quota_exhausted`), plus re-sondé |
| `tpd_limit` | jour UTC | compté **après** l'appel sur les tokens facturés ; même mise à l'écart |

Un appel échoué restitue sa réservation RPM et TPM : les erreurs ne consomment pas de quota.
Les compteurs du jour sont des clés Redis à TTL 25 h ; les fenêtres 60 s sont remises à zéro
au démarrage de l'API (lifespan), jamais par un worker.

## Combien d'agents dans un lot

Le calcul est fait une fois, à la construction de `Settings`, pour chaque provider :

```
tokens_per_agent = assumed_prompt_tokens + assumed_output_tokens     = 2 200 + 800 = 3 000
tpm_bound        = tpm_limit // tokens_per_agent    (rpm_limit si pas de tpm_limit)
req_bound        = max_tokens_per_request // tokens_per_agent    (max_batch_agents si absent)
batch_max_agents = max(1, min(tpm_bound, req_bound, rpm_limit, max_batch_agents = 20))
tpm_estimate_per_request = batch_max_agents × tokens_per_agent    (si tpm_limit)
```

Sur le fichier livré :

| Provider | `tpm_limit` | `max_tokens_per_request` | `rpm_limit` | → `batch_max_agents` | estimation TPM/requête |
|---|---|---|---|---|---|
| `mistral` | 500 000 | — | 60 | min(166, 20, 60, 20) = **20** | 60 000 |
| `openai` | 200 000 | — | 15 | min(66, 20, 15, 20) = **15** | 45 000 |
| `google_gemini31` | 250 000 | — | 15 | **15** | 45 000 |
| `google_gemma42` | 16 000 | 16 000 | 30 | min(5, 5, 30, 20) = **5** | 15 000 |
| `groq_openai_120` | 8 000 | 8 000 | 30 | min(2, 2, 30, 20) = **2** | 6 000 |
| `cerebras_gpt-oss-120b` | 30 000 | — | 5 | min(10, 20, 5, 20) = **5** | 15 000 |

Ces valeurs se lisent dans le log au démarrage (`Provider 'x' — batch_max_agents=… tpm_estimate_per_request=…`)
et dans `llm-gateway config show`.

**Exclusion au démarrage.** Un provider avec `max_tokens_per_request` est écarté si
`max_tokens_per_request < batch_max_agents × assumed_prompt_tokens + min_output_tokens` : pour
`groq_openai_120`, 2 × 2 200 + 512 = 4 912 ≤ 8 000, il reste. Le message est un WARNING
« Fournisseur 'x' exclu : capacité insuffisante (…) » avec le calcul.

**Deux seuils, deux rôles.** L'API décide *quand* dispatcher avec `get_dispatch_threshold` :
`batch_target_agents` (10) borné par le **plus gros** provider — pas le plus petit, sinon le
seuil vaudrait 1 et la fenêtre d'accumulation ne servirait jamais. Le worker décide *combien*
prendre avec le `batch_max_agents` **du provider qu'il vient de réserver**. Un lot de 10
tâches en file peut donc partir en un appel chez Mistral ou en cinq chez Groq.

## La fenêtre d'accumulation

`batch_delay_seconds` = 3 s. Une requête isolée attend ce délai avant de partir ; c'est le
`P4_4_ms` visible dans `timing_p5`. Le réglage est calé sur une mesure du run 2026-07-10
(inter-arrivée des prompts p50 = 1,4 s, p90 du débit 40 prompts/min) : à 1 s la fusion ne
captait presque rien, à 3 s le taux de batching (`llm_agents_batched_total /
llm_prompts_sent_total`) monte. L'allonger ajoute de la latence à chaque décision ; le réduire
multiplie les appels et donc la pression RPM.

## Les estimations de tokens, et comment elles ont été mesurées

Trois nombres pilotent la réservation TPM ; ils sont **mesurés**, pas choisis :

| Réglage | Valeur | Mesure (commentaires de `settings.py`) |
|---|---|---|
| `assumed_prompt_tokens` | 2 200 | historique des `tokens_in` par agent + 10 % de marge |
| `assumed_output_tokens` | 800 | run 2026-07-10 : 1 282 tokens d'entrée + 320 de sortie ≈ 1 600 par agent, p90 ≈ 2 400 ; 3 000 garde ~25 % de marge. Un 4 096 codé en dur donnait 6 296/agent et écrasait `batch_max_agents` à 1 sur les petits TPM |
| `token_chars_ratio` | 3,0 | run 2026-07-10, 427 échanges (prompts FR + JSON) : p50 = 3,24, p10 = 3,05 → 3,0 laisse ~8 % de marge |

Le worker recale la réservation en deux temps : au rendu, `prompt_chars / 3,0 + n_agents ×
800` remplace le forfait (une réflexion STM à ~4 500 tokens d'entrée par agent réserve son
vrai coût, un petit lot rend du headroom) ; après la réponse, la consommation facturée
remplace l'estimation. Deux WARNING signalent une dérive : `tokens_in dépasse
assumed_prompt_tokens` (par agent) et `Estimation TPM sous-évaluée de N tokens` (réel >
réservé × 1,25). Les voir souvent = remesurer sur `llm_exchanges.jsonl` et ajuster.

## Le budget de sortie

```
max_tokens = min(parameters.max_tokens (défaut 4096) × n_agents,
                 settings.max_output_tokens (16 384),
                 provider.max_output_tokens)
max_tokens = min(max_tokens, max_tokens_per_request − prompt_estimé)     # si le provider a une capacité par requête
```

Si `max_tokens_per_request − prompt_estimé < min_output_tokens` (512), le lot ne part pas :
`ProviderCapacityError`, slot restitué, bascule vers un autre provider,
`llm_capacity_reroute_total` incrémenté. C'est le garde-fou 413 : sur le run 2026-07-11, 38
requêtes partaient condamnées vers les petits quotas parce que l'estimation statique
sous-évaluait les prompts de réflexion d'un facteur 2.

`max_output_tokens` par provider borne aussi la sélection : une requête avec
`parameters.max_tokens = 8000` n'ira pas chez un provider qui plafonne à 4 096.

### `max_output_tokens` s'apprend

Quand un provider répond HTTP 400 avec sa limite (« `max_tokens` must be less than or equal
to 8192 » chez Groq, « supports at most 16384 completion tokens » chez OpenAI, « …limited to
8192 » chez Google), `learn_provider_max_output_tokens` :

1. met à jour la config du processus courant (le prochain lot est plafonné) ;
2. range la valeur dans le **store des limites apprises** (port `LearnedLimits`) : hash Redis
   `llm_gateway:learned:max_output_tokens` partagé entre l'API et les workers
   (`LLM_GATEWAY_LEARNED_LIMITS=redis`, défaut), fichier JSON sans Redis (`file`,
   `LLM_GATEWAY_LEARNED_LIMITS_FILE`), ou rien (`none`) ;
3. rend `True` si la limite est nouvelle et plus stricte : le lot est rejoué après 1 s.
   Sinon `False` : le worker bascule vers un autre provider au lieu de reboucler sur la même
   400.

Au démarrage, chaque processus fusionne les limites apprises par-dessus le fichier des
fournisseurs (`apply_learned_limits`) : une limite apprise ne peut que **resserrer** un plafond
déclaré, jamais l'élargir. Le fichier des fournisseurs n'est plus jamais réécrit par le
gateway ; pour rendre une limite apprise définitive, recopiez-la dans `max_output_tokens`.

!!! note "Si le store est injoignable"
    L'apprentissage ajuste la config mémoire, rejoue le lot, et journalise
    `[ALARME] Impossible de mémoriser la limite apprise` : les autres processus la réapprendront
    à leur première 400. Rien n'est perdu, seulement réappris.

## Rafraîchir les quotas : `make providers`

Depuis la racine du dépôt, `scripts/providers/refresh.py` relève les quotas **réels** et
réécrit `config/llm_gateway/providers.yaml` (édition chirurgicale, commentaires préservés) :

```bash
make providers DRY_RUN=1      # bilan sans écrire
make providers                # écrit
```

| Adapter | Source | Champs mis à jour |
|---|---|---|
| mistral, groq, cerebras | une requête sonde (`max_tokens=1`) → en-têtes `x-ratelimit-*` | mistral : `rpm_limit` (borné à 60, cadence documentée 1 req/s), `tpm_limit`, `tpd_limit` forcé à 3 × (1 Md / 30) = 100 M tokens/jour (garde-fou : le free tier est mensuel, non exposé) ; groq : `rpd_limit`, `tpm_limit` (RPM et TPD absents des en-têtes) ; cerebras : les quatre |
| google | API Cloud Quotas (`gcloud auth print-access-token`) | `rpm_limit`, `tpm_limit`, `rpd_limit` par famille de modèle |
| openai, ou toute instance sans clé | — | ignorée avec avertissement |

Le script recalcule `weight = min(rpm, tpm/3000)/15` dès que `rpm_limit` ou `tpm_limit`
change, aligne `max_tokens_per_request` sur `tpm_limit` quand le champ existe, ajoute en fin
de fichier tout nouveau modèle texte trouvé par `GET /models` (en rotation si RPD ≥ 100, sinon
`weight: 0`), commente avec la date un `default_model` disparu, et ne supprime ni n'assouplit
jamais rien en silence : une sonde en échec laisse l'instance intacte avec une `[ALARME]`
dans le bilan. Un bloc déjà présent, même commenté, n'est jamais ré-ajouté.

## Lire l'état courant

- `GET /health` : `current_rpm`, `daily_requests`, `daily_tokens`, `cooldown`,
  `quota_exhausted`, `available` par provider.
- `GET /metrics` : `llm_provider_state`, `llm_provider_daily_usage_ratio`,
  `llm_provider_quota_exhausted`, `celery_worker_utilization_ratio`,
  `llm_task_queue_depth_by_category`.
- Journal du worker : `Quota journalier RPD épuisé — provider écarté jusqu'à minuit UTC |
  provider=… used=… limit=… reset_in=…s`.
