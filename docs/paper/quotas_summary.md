# Synthèse des Quotas des Fournisseurs LLM

> **Fichier source de configuration :** [`llm_module/config/providers.yaml`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/llm_module/config/providers.yaml)  
> **Script de mise à jour des quotas :** [`scripts/providers/refresh.py`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/scripts/providers/refresh.py) (`make providers` ou `make providers DRY_RUN=1`)  
> **Page HTML interactive :** [`docs/quotas_summary.html`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/quotas_summary.html)

---

## 1. Vue d'ensemble des capacités

| Indicateur | Valeur | Description |
| :--- | :---: | :--- |
| **Fournisseurs actifs en rotation** | **11** | Instances réparties sur Mistral, Google, Groq et Cerebras |
| **Capacité instantanée totale (RPM)** | **206 req/min** | Somme des quotas de requêtes par minute en rotation |
| **Quota journalier cumulé (RPD)** | **37 700+ req/jour** | Plafond journalier combiné sur les quotas gratuits |
| **Fournisseurs hors rotation / inactifs** | **5** | 4 modèles Google à quota faible (RPD < 100) + OpenAI (sans clé) |
| **Modèles archivés / obsolètes** | **7** | Retirés des API ou pour cause d'incompatibilité technique |

---

## 2. Fournisseurs actifs dans la rotation (SWRR)

Ces instances reçoivent le trafic distribué selon leur poids (SWRR - *Smooth Weighted Round Robin*) et disposent d'une clé API valide dans `.env` :

| Instance | Adapter | Modèle par défaut | RPM | TPM | RPD | TPD | Poids (`weight`) | Conc. | Rôle / Statut |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`mistral`** | `mistral` | `mistral-small-latest` | **60** | 500 000 | — | 100 M\* | **4.0** (40.5%) | 3 | Pilier de simulation. Garde-fou 100M tokens/j |
| **`google_gemini31`** | `google` | `gemini-3.1-flash-lite-preview` | **15** | 250 000 | **500** | — | **1.0** (10.1%) | 2 | **Juge de référence** (calibration des prompts) |
| **`google_gemini35`** | `google` | `gemini-3.5-flash-lite` | **15** | 250 000 | **500** | — | **1.0** (10.1%) | 2 | **Mutateur & Générateur** (+ thinking 1024) |
| **`google2`** | `google` | `gemini-3.1-flash-lite-preview` | **15** | 250 000 | **500** | — | **1.0** (10.1%) | 2 | Seconde clé Google (mesures hors campagne) |
| **`google2_35`** | `google` | `gemini-3.5-flash-lite` | **15** | 250 000 | **500** | — | **1.0** (10.1%) | 2 | 2e seau sur seconde clé Google |
| **`google_gemma42`** | `google` | `gemma-4-26b-a4b-it` | **30** | 16 000 | **14 400** | — | **0.36** (3.6%) | 1 | TPM limitant (max_tokens_per_request: 16k) |
| **`google_gemma43`** | `google` | `gemma-4-31b-it` | **30** | 16 000 | **14 400** | — | **0.36** (3.6%) | 1 | TPM limitant (max_tokens_per_request: 16k) |
| **`cerebras_gpt-oss-120b`**| `cerebras` | `gpt-oss-120b` | **5** | 30 000 | **2 400** | 1 M | **0.33** (3.3%) | 4 | Relevé en-têtes (limite 150 req/h non modélisée) |
| **`cerebras_gemma_4_31b`** | `cerebras` | `gemma-4-31b` | **5** | 30 000 | **2 400** | 1 M | **0.33** (3.3%) | 1 | Seau Cerebras distinct de google_gemma43 |
| **`groq_openai_120`** | `groq` | `openai/gpt-oss-120b` | **30** | 8 000 | **1 000** | 200 K | **0.18** (1.8%) | 3 | TPM limitant (max_tokens_per_request: 8k) |
| **`groq_qwen_qwen3_6_27b`**| `groq` | `qwen/qwen3.6-27b` | **30** | 8 000 | **1 000** | — | **0.18** (1.8%) | 3 | Ajouté via `make providers` |

\* *Garde-fou local du gateway : 3× le prorata journalier du milliard de tokens/mois Mistral (non exposé par l'API).*

---

## 3. Fournisseurs hors rotation (`weight: 0.0`) et non configurés

Ces instances sont présentes dans `providers.yaml` mais **ne reçoivent aucun trafic automatique** du load balancer :

| Instance | Adapter | Modèle par défaut | RPM | TPM | RPD | Poids | Raison |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **`google_gemini_3_flash_preview`** | `google` | `gemini-3-flash-preview` | 5 | 250 000 | **20** | **0.0** | RPD free tier 20/j < 100 (forcé via `llm.provider` uniquement) |
| **`google_gemini_3_5_flash`** | `google` | `gemini-3.5-flash` | 5 | 250 000 | **20** | **0.0** | RPD free tier 20/j < 100 (forcé via `llm.provider` uniquement) |
| **`google_gemini_3_6_flash`** | `google` | `gemini-3.6-flash` | 5 | 250 000 | **20** | **0.0** | RPD free tier 20/j < 100 (forcé via `llm.provider` uniquement) |
| **`google_gemini_3_7_flash`** | `google` | `gemini-3.7-flash` | 5 | 250 000 | **20** | **0.0** | RPD free tier 20/j < 100 (relevé le 2026-08-18) |
| **`openai`** | `openai` | `gpt-4o-mini` | 15 | 200 000 | — | **1.0** | Exclu au démarrage : aucune clé `PROVIDER_KEYS__openai` dans `.env` |

---

## 4. Modèles archivés ou désactivés

| Instance | Modèle | Date / Contexte | Raison de la désactivation |
| :--- | :--- | :--- | :--- |
| `groq_llama3` | `llama-3.3-70b-versatile` | 2026-08-18 | Disparu de `GET /models` Groq &rarr; commenté automatiquement |
| `groq_llama31` | `llama-3.1-8b-instant` | 2026-08-18 | Disparu de `GET /models` Groq &rarr; commenté automatiquement |
| `cerebras_zai-glm-4.7` | `zai-glm-4.7` | 2026-08-03 | 100% de troncatures (modèle raisonneur consommant son quota de sortie en pensée sans générer de JSON) |
| `groq_meta1` & `groq_meta2` | `llama-prompt-guard-2-*` | Historique | `max_tokens` bridé à 512, insuffisant pour les lots de personas |
| `groq_allam` | `allam-2-7b` | Historique | Erreur de conformité du format JSON en sortie |
| `groq_openai_20` | `openai/gpt-oss-20b` | Historique | Instabilité et erreurs 5xx fréquentes |
| `google_gemma3n` | `gemma-3n-e2b-it` | Historique | Remplacé par Gemma 4.2 et 4.3 |

---

## 5. Comment fonctionne le script de mise à jour des quotas ?

Le script [`scripts/providers/refresh.py`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/scripts/providers/refresh.py) s'exécute via Make :

```bash
make providers            # Sonde les API et met à jour providers.yaml
make providers DRY_RUN=1  # Prévisualisation sans écriture
```

### Méthode de collecte par Adapter :
1. **Mistral, Groq, Cerebras** : Exécute une micro-requête (`max_tokens=1`) et extrait les en-têtes de réponse `x-ratelimit-*`.
2. **Google (Gemini & Gemma)** : Interroge l'API officielle Google Cloud Quotas (`cloudquotas.googleapis.com`) à l'aide d'un jeton `gcloud auth print-access-token` sur le projet actif.
3. **OpenAI** : Ignoré si aucune clé n'est présente dans `.env`.

### Détection automatique du cycle de vie des modèles :
- **Nouveaux modèles opérationnels** : Détectés via `GET /models`. Si le quota journalier $\text{RPD} \ge 100$, le modèle est ajouté en fin de fichier et activé dans la rotation. Si $\text{RPD} < 100$, il est ajouté avec `weight: 0.0` (hors rotation).
- **Modèles décommissionnés par l'hébergeur** : Si un modèle n'apparaît plus dans `GET /models`, son bloc YAML est commenté et daté, et une alerte `[ALARME]` est levée dans le bilan.
- **Préservation chirurgicale** : L'écriture ne modifie que les champs numériques mis à jour et conserve l'intégralité des commentaires existants.

---

## 6. Rôles clés dans le module de calibration génétique

Dans [`prompt_calibration`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/prompt_calibration/docs/quotas-et-modeles.md), deux seaux Google Gemini indépendants sont exploités :

1. **Le Juge d'Évaluation (`google_gemini31`)** :
   - Modèle : `gemini-3.1-flash-lite-preview`
   - Quota : 500 requêtes/jour.
   - Propriété : **Aucune réflexion** (`thinking: 0`), épinglé dans la clé de cache `eval_params_key`.
2. **Le Mutateur de Prompts (`google_gemini35`)** :
   - Modèle : `gemini-3.5-flash-lite`
   - Quota : 500 requêtes/jour (seau distinct).
   - Propriété : Reçoit un budget de pensée (`mutation_thinking_budget: 1024` tokens) pour produire de meilleures variantes de prompt sans dériver les scores du juge.
