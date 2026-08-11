# Providers LLM

Configuration des fournisseurs LLM disponibles dans `llm_module/config/providers.yaml`.

La charge est distribuée entre les providers actifs selon leur `weight` via l'algorithme SWRR (Smooth Weighted Round Robin). Voir [docs/arch/llm-inference.md](../arch/llm-inference.md) pour le détail du mécanisme.

---

## Structure d'un provider

```yaml
providers:
  <nom_unique>:
    adapter: <openai|google|groq|cerebras|mistral>  # facultatif si = nom
    rpm_limit: 15              # requêtes par minute max
    tpm_limit: 200000          # tokens par minute (pour calcul batch_max_agents)
    rpd_limit: 500             # requêtes par jour (fenêtre UTC)
    tpd_limit: 2000000         # tokens par jour
    base_url: https://...      # endpoint de l'API
    default_model: gpt-4o-mini
    weight: 1.0                # poids de sélection SWRR = min(rpm, tpm/3000)/15
                               # 0 = HORS ROTATION : défini mais jamais tiré par le
                               # load balancer ; utilisable via `llm.provider` forcé
    concurrency_limit: 3       # batches simultanés max
    disable_timeout: 180       # timeout HTTP en secondes
```

`batch_max_agents` est calculé automatiquement au démarrage :
`max(1, min(tpm_limit / tokens_per_agent, rpm_limit, max_batch_agents))`

---

## Mise à jour automatique des quotas — `make providers`

```bash
make providers            # sonde les providers et met à jour providers.yaml
make providers DRY_RUN=1  # affiche le bilan sans écrire
```

Le script `scripts/providers/refresh.py` relève les quotas **réels** et les écrit
dans le YAML (édition chirurgicale : commentaires préservés, écriture atomique).

Il gère aussi le **cycle de vie des modèles** (`GET /models` par adapter) :

- **Nouveau modèle texte opérationnel** → bloc provider ajouté en fin de fichier
  avec ses quotas relevés (daté). RPD ≥ 100 (constante `MIN_RPD_NEW_PROVIDER`) →
  **en rotation** avec weight calculé ; RPD plus faible (ex. gemini-3.6-flash à
  20 req/jour) → ajouté **hors rotation** (`weight: 0`), utilisable seulement en
  `llm.provider` forcé. Garde-fous : un modèle déjà référencé dans le fichier, **même commenté**, n'est
  jamais ré-ajouté (bloc commenté = décision humaine ou obsolescence datée) ; un
  modèle Google de la même famille de quota qu'une instance active est ignoré
  (ex. `gemini-3.1-flash-lite` stable partage le seau du `-preview` : l'activer
  doublerait la pression locale sur les 500 req/jour) ; les modèles Mistral ne
  sont jamais ajoutés (quota partagé par compte → aucun gain de capacité).
- **`default_model` disparu de `/models`** → bloc **commenté avec la date** et la
  raison, plus une `[ALARME]` dans le bilan (la capacité totale baisse).

Sources par adapter :

| Adapter | Source | Champs mis à jour |
|---------|--------|-------------------|
| mistral | 1 requête sonde (`max_tokens=1`) → en-têtes `x-ratelimit-*` | `rpm_limit` (borné à 60 : cadence doc 1 req/s), `tpm_limit`, `tpd_limit` (garde-fou, voir ci-dessous) |
| groq | idem — attention `x-ratelimit-limit-requests` = requêtes/**jour** | `tpm_limit`, `rpd_limit` (RPM et TPD absents des en-têtes → manuels) |
| cerebras | idem (granularités minute/heure/jour) | `rpm_limit`, `tpm_limit`, `rpd_limit`, `tpd_limit` |
| google | API Cloud Quotas (`gcloud auth print-access-token`, projet actif) | `rpm_limit`, `tpm_limit`, `rpd_limit` |
| openai | aucune (pas de clé) | — |

Le `weight` est recalculé (convention `min(rpm, tpm/3000)/15`) dès que
`rpm_limit` ou `tpm_limit` change, et `max_tokens_per_request` suit `tpm_limit`
quand le champ existe. Une sonde en échec laisse l'instance **intacte** et lève
une ligne `[ALARME]` dans le bilan (jamais d'assouplissement silencieux).

**Garde-fou Mistral** : le free tier est plafonné à **1 milliard de tokens/mois**
(quota non exposé par l'API, et aucun quota journalier côté Mistral). Pour éviter
de consommer le mois en une journée, le script force
`tpd_limit = 3 × (1 Md / 30) = 100 M tokens/jour` (facteur et quota mensuel :
constantes `MISTRAL_PRORATA_FACTOR` / `MISTRAL_MONTHLY_TOKENS` du script).

La doc Google (`ai.google.dev/gemini-api/docs/rate-limits`) ne publie plus les
tableaux par modèle — l'API Cloud Quotas est la seule source programmatique ;
les noms de quotas y sont des familles (`gemma-4-26b`, `gemini-3.1-flash-lite`),
mappées par plus long préfixe sur les `default_model`.

---

## Providers actifs

Quotas free tier relevés par `make providers` (2026-08-03) :

| Provider | Adapter | Modèle par défaut | RPM | TPM | RPD | TPD | Poids |
|----------|---------|-------------------|-----|-----|-----|-----|-------|
| `openai` | openai | gpt-4o-mini | 15 | 200K | — | 2M | 1.0 |
| `mistral` | mistral | mistral-small-latest | 60 | 500K | — | 100M† | 4.0 |
| `google_gemini31` | google | gemini-3.1-flash-lite-preview | 15 | 250K | 500 | — | 1.0 |
| `google_gemini35` | google | gemini-3.5-flash-lite | 15 | 250K | 500 | — | 1.0 |
| `google2` | google | gemini-3.1-flash-lite-preview | 15 | 250K | 500 | — | 1.0 |
| `google2_35` | google | gemini-3.5-flash-lite | 15 | 250K | 500 | — | 1.0 |
| `google_gemma42` | google | gemma-4-26b-a4b-it | 30 | 16K | 14 400 | — | 0.36 |
| `google_gemma43` | google | gemma-4-31b-it | 30 | 16K | 14 400 | — | 0.36 |
| `groq_llama3` | groq | llama-3.3-70b-versatile | 30 | 12K | 1 000 | 100K | 0.27 |
| `groq_llama31` | groq | llama-3.1-8b-instant | 2‡ | 6K | 14 400 | 500K | 0.13 |
| `groq_openai_120` | groq | openai/gpt-oss-120b | 30 | 8K | 1 000 | 200K | 0.18 |
| `cerebras_gpt-oss-120b` | cerebras | gpt-oss-120b | 5 | 30K | 2 400 | 1M | 0.33 |
| `cerebras_zai-glm-4.7` | cerebras | zai-glm-4.7 | 5 | 30K | 2 400 | 1M | 0.33 |
| `cerebras_gemma_4_31b`* | cerebras | gemma-4-31b | 5 | 30K | 2 400 | 1M | 0.33 |
| `groq_qwen_qwen3_6_27b`* | groq | qwen/qwen3.6-27b | 30 | 8K | 1 000 | — | 0.18 |
| `google_gemini_3_flash_preview`* | google | gemini-3-flash-preview | 5 | 250K | 20 | — | **0 (hors rotation)** |
| `google_gemini_3_5_flash`* | google | gemini-3.5-flash | 5 | 250K | 20 | — | **0 (hors rotation)** |
| `google_gemini_3_6_flash`* | google | gemini-3.6-flash | 5 | 250K | 20 | — | **0 (hors rotation)** |

† garde-fou local (3× le prorata journalier du milliard de tokens/mois), pas un quota Mistral.
‡ auto-restriction locale : le TPM 6 000 ne soutient que ~2 req/min (le vrai RPM Groq est 30).
\* ajoutés automatiquement par `make providers` le 2026-08-03 (seaux de quota indépendants : le gemma-4-31b Cerebras ne consomme pas le quota Google de `google_gemma43`).

Cerebras applique aussi une limite **horaire** (150 req/h, 1 M tokens/h) non
modélisée dans le YAML. Mistral n'a pas de seau par modèle : le quota est
partagé entre tous les modèles du compte.

---

## Clés API

Les clés sont injectées via des variables d'environnement dans `.env`, **jamais** dans le YAML :

```
PROVIDER_KEYS__openai=sk-...
PROVIDER_KEYS__groq=gsk-...
PROVIDER_KEYS__google=AIza...
PROVIDER_KEYS__mistral=...
PROVIDER_KEYS__cerebras=...
```

Pour plusieurs instances d'un même fournisseur (ex. `groq_llama3`, `groq_llama31`), la clé est partagée via le champ `adapter` commun (`groq`). La résolution est `PROVIDER_KEYS__<nom_instance>` puis repli sur `PROVIDER_KEYS__<adapter>`.

---

## Sélectionner un provider dans la config d'expérience

Le fichier YAML de l'expérience peut forcer un provider spécifique :

```yaml
llm:
  provider: groq_llama3        # force ce provider pour toute la simulation
  model: llama-3.3-70b-versatile  # surcharge le modèle par défaut
```

Si `provider` est absent, le load balancer SWRR distribue entre tous les providers actifs.

---

## Ajouter un nouveau provider

1. Ajouter une entrée dans `llm_module/config/providers.yaml`
2. Renseigner la clé dans `.env` : `PROVIDER_KEYS__<adapter>=...`
3. Si l'adapter n'existe pas encore, implémenter la classe dans `llm_module/providers/`
4. Lancer `make providers DRY_RUN=1` pour vérifier quotas et existence du modèle
