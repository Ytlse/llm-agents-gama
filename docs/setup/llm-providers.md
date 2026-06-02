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
    tpd_limit: 2000000         # tokens par jour
    base_url: https://...      # endpoint de l'API
    default_model: gpt-4o-mini
    weight: 1.0                # poids de sélection SWRR
    concurrency_limit: 3       # batches simultanés max
    disable_timeout: 180       # timeout HTTP en secondes
```

`batch_max_agents` est calculé automatiquement au démarrage :
`max(1, min(tpm_limit / tokens_per_agent, rpm_limit, max_batch_agents))`

---

## Providers actifs

| Provider | Adapter | Modèle par défaut | RPM | Poids |
|----------|---------|-------------------|-----|-------|
| `openai` | openai | gpt-4o-mini | 15 | 1.0 |
| `mistral` | mistral | mistral-small-latest | 90 | 1.0 |
| `google_gemini31` | google | gemini-3.1-flash-lite-preview | 15 | 2.0 |
| `google_gemma42` | google | gemma-4-26b-a4b-it | 15 | 2.0 |
| `google_gemma43` | google | gemma-4-31b-it | 15 | 2.0 |
| `groq_llama3` | groq | llama-3.3-70b-versatile | 30 | 1.0 |
| `groq_llama4` | groq | meta-llama/llama-4-scout-17b-16e-instruct | 30 | 1.0 |
| `groq_llama31` | groq | llama-3.1-8b-instant | 30 | 1.0 |
| `groq_qwen` | groq | qwen/qwen3-32b | 60 | 1.0 |
| `groq_openai_120` | groq | openai/gpt-oss-120b | 30 | 1.0 |
| `groq_openai_20` | groq | openai/gpt-oss-20b | 30 | 1.0 |
| `cerebras_gpt-oss-120b` | cerebras | gpt-oss-120b | 5 | 1.0 |
| `cerebras_zai-glm-4.7` | cerebras | zai-glm-4.7 | 5 | 1.0 |

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

Pour plusieurs instances d'un même fournisseur (ex. `groq_llama3`, `groq_llama4`), la clé est partagée via le champ `adapter` commun (`groq`). La clé est lue depuis `PROVIDER_KEYS__<adapter>`.

---

## Sélectionner un provider dans la config d'expérience

Le fichier YAML de l'expérience peut forcer un provider spécifique :

```yaml
llm:
  provider: groq_llama4        # force ce provider pour toute la simulation
  model: meta-llama/llama-4-scout-17b-16e-instruct  # surcharge le modèle par défaut
```

Si `provider` est absent, le load balancer SWRR distribue entre tous les providers actifs.

---

## Ajouter un nouveau provider

1. Ajouter une entrée dans `llm_module/config/providers.yaml`
2. Renseigner la clé dans `.env` : `PROVIDER_KEYS__<adapter>=...`
3. Si l'adapter n'existe pas encore, implémenter la classe dans `llm_module/providers/`
