# Plan Expérimental & Spécification Unifiée des Expériences (AAMAS 2027)

Ce dossier contient la spécification complète, standardisée et reproductible de l'ensemble des expériences à mener pour l'article de recherche :
> **« Limites et perspectives des agents LLM en simulation de mobilité urbaine »** (Cible : AAMAS 2027).

Le fichier central est **[`experiments.yaml`](experiments.yaml)**. Il sert de **source unique de vérité (*Single Source of Truth*)** pour toute la campagne de tests.

---

## 1. But et Philosophie de la Spécification Unifiée

Dans une recherche expérimentale confrontant des modèles d'IA générative (LLM), des modèles tabulaires supervisés (LightGBM, Logit) et des heuristiques physiques, le risque majeur est la dispersion méthodologique : prompts modifiés à la volée, températures variables, versions de population hétérogènes, coûts non maîtrisés.

Le fichier `experiments.yaml` formalise un contrat strict :
1. **Substrat commun scellé (*Common Set*)** : Toutes les expériences du benchmark partagent exactement le même jeu d'entrée ($1\,000$ personnes alignées à l'enquête EMC² 2023, avec leurs alternatives OTP pré-calculées).
2. **Parité informationnelle stricte** : Aucun modèle ne reçoit d'information privilégiée.
3. **Reproductibilité totale** : Chaque expérience est auto-porteuse (modèle, température, template de prompt, seed, paramètres de micro-batching).
4. **Dimensionnement des coûts avant exécution (*Dry-run*)** : Calcul prédictif du nombre de requêtes API et du volume de tokens pour éviter tout dépassement de quota ou surprise budgétaire.

---

## 2. Les 4 Exploitations du Fichier YAML

Le fichier `experiments.yaml` est conçu pour être consommé par 4 outils distincts du projet :

```
                        ┌─────────────────────────────────┐
                        │        experiments.yaml         │
                        │     (Source unique de vérité)   │
                        └────────────────┬────────────────┘
             ┌───────────────────────────┼───────────────────────────┐
             ▼                           ▼                           ▼                           ▼
    1. EXÉCUTION & RUN          2. MOTEUR DE SCORING        3. DASHBOARD HTML           4. ARTICLE AAMAS
   Pilote l'inférence           Calcule EMD, JSD, L1,       Génère / met à jour         Génère les tableaux
   (Micro-batching API,         Accuracy unitaire face      docs/synthesis/index.html   LaTeX et remplit les
   concurrence, rate-limits)    à EMC² et LightGBM          (radar d'écarts, badges)    TODO du manuscrit
```

### 1. Orchestration & Exécution
Le lanceur lit la configuration de l'expérience sélectionnée, charge la population scellée, regroupe les requêtes par `batch_size`, appelle le provider (Google, Mistral, vLLM local ou Heuristique locale) et enregistre les réponses brutes dans `experiments/archive/<id>/`.

### 2. Moteur de Scoring et d'Évaluation
À la fin du run, le moteur de calcul réutilise les clés `scoring:` pour produire :
* **Parts modales globales** : Comparées aux cibles Cerema EMC² 2023 (Voiture, TC, Marche, Vélo).
* **Écarts macroscopiques par strate** : EMD (Earth Mover's Distance) pour variables ordinales (âge, distance) et JSD (Jensen-Shannon) pour variables nominales (motif, genre, couronne).
* **Métriques unitaires** : Exactitude (Accuracy) et Log-Loss face au choix réel observé et à l'oracle LightGBM.

### 3. Restitution Visuelle & Tableau de Bord
La page web de synthèse (`docs/synthesis/index.html`) est régénérée automatiquement :
* Ajout d'une colonne dédiée à l'expérience.
* Affichage des badges (Modèle, Température, Date, Batching).
* Visualisation graphique des sur/sous-estimations modales (sur-attractivité du vélo, sous-estimation de la marche).
* Encadré de suivi opérationnel (requêtes réussies, tokens consommés, coût réel).

### 4. Injection Directe dans le Manuscrit AAMAS
Un script d'export extrait les métriques pour remplir automatiquement les tableaux comparatifs du papier LaTeX/Markdown (Section 4 et 5), remplaçant les marqueurs `⟨xx⟩ %` sans aucune saisie manuelle propice aux erreurs.

---

## 3. Anatomie du Fichier `experiments.yaml`

Le fichier se divise en deux sections principales :

### Section `defaults:` (Socle Commun)
Définit tout ce qui est partagé par l'ensemble des expériences pour éviter toute duplication inutile :
* `inputs` : Chemins de la population scellée (`population.json`), cibles Cerema (`cerema_values.yaml`), politiques LightGBM et cache OTP.
* `scoring` : Liste des métriques (EMD, JSD, L1, Accuracy) et des strates sociologiques d'évaluation.
* `outputs` : Dossier racine d'archivage des résultats et chemin du dashboard de synthèse.

### Section `experiments:` (Matrice des Tests)
Chaque expérience est une entrée de liste avec les champs suivants :

| Champ | Type | Description |
|---|---|---|
| `id` | String | Identifiant technique unique (ex: `exp_02_bare_gemini_flash_lite`) |
| `title` | String | Titre lisible affiché dans le dashboard et le papier |
| `phase` | String | Section méthodologique (`ablation_baseline`, `calibrated`, `hysteresis_5d`, `news_events`) |
| `description` | String | Contexte et hypothèse scientifique testée |
| `engine` | Object | Moteur décisionnel : `type` (`heuristic`, `llm`, `tabular_ml`), `model`, `provider`, `temperature`, `seed`, `prompt_template` |
| `execution` | Object | Paramètres d'exécution : `batch_size` (micro-batching), `max_parallel_requests` |
| `estimation` | Object | Hypothèses de tokens par trajet et tarification pour le calcul prédictif de coût |

---

## 4. Dimensionnement Opérationnel & Respect des Quotas API

L'évaluation ne repose pas sur une facturation théorique au dollar, mais sur le respect des **quotas réels de débit et de plafonds journaliers du pool SWRR** configuré dans [`llm_module/config/providers.yaml`](llm_module/config/providers.yaml) et synthétisé dans [`docs/paper/quotas_summary.html`](docs/paper/quotas_summary.html).

### 4.1 Quotas des fournisseurs clés en rotation (Source : `quotas_summary.html`)

| Instance | Modèle réel | RPM | TPM | RPD (Req/jour) | TPD (Tokens/jour) | Rôle dans le projet |
|---|---|:---:|:---:|:---:|:---:|---|
| **`google_gemini31`** | `gemini-3.1-flash-lite-preview` | **15** | 250 000 | **500** | — | **Juge de référence** (`thinking: 0`, cache strict) |
| **`google_gemini35`** | `gemini-3.5-flash-lite` | **15** | 250 000 | **500** | — | Mutateur / Variantes (+ thinking 1024) |
| **`google2`** | `gemini-3.1-flash-lite-preview` | **15** | 250 000 | **500** | — | Seconde clé Google (mesures hors campagne) |
| **`mistral`** | `mistral-small-latest` | **60** | 500 000 | — | 100 M (garde-fou) | Pilier de simulation (1 req/s) |
| **`vllm_local`** | `Qwen/Qwen2.5-32B-Instruct-AWQ` | $\infty$ | $\infty$ | $\infty$ | $\infty$ | Inférence GPU locale déterministe |

---

### 4.2 Les ratios de dimensionnement de la passerelle

1. **Forfait par tâche (`tokens_per_agent`)** :
   $$\text{tokens\_per\_agent} = 3\,000\text{ tokens (2 200 in + 800 out)}$$
   Calé sur les ~1 600 tokens/agent mesurés en simulation + marge de sécurité pour garantir l'absence de troncature HTTP 413.
2. **Dimensionnement du batch (`batch_target_agents`)** :
   * Cible de regroupement passerelle : **$B = 10\text{ agents par batch}$** (défaut `Settings.batch_target_agents`).
   * Moyenne observée en simulation : **~7 à 10 agents par lot**.
3. **Seuil critique RPD (Pourquoi le batching est obligatoire)** :
   * **Sans batching** ($1\,000$ requêtes pour $1\,000$ trajets) : le run sature immédiatement le quota de 500 RPD de `google_gemini31` à 50 % du jeu de données et échoue.
   * **Avec micro-batching ($B = 10$)** : $1\,000$ trajets $\to$ **$\approx 100\text{ requêtes}$**, soit seulement **20 % du quota journalier (100 / 500 RPD)**.

---

### 4.3 Matrice d'impact opérationnel (Cohorte scellée de 1 000 personnes ≈ 2 579 trajets, Batch nominal B = 10)

> **Unité d'évaluation = le déplacement.** La cohorte scellée est de **1 000 personnes** (894 mobiles) ;
> leurs chaînes d'activités produisent **≈ 2 579 trajets** (2,58/pers), unité sur laquelle sont
> calculées parts modales et métriques unitaires. Les estimations de requêtes ci-dessous supposent
> un micro-batch B=10 sur cet effectif de trajets.

| Expérience | Modèle passerelle | Req. sans batch | Req. micro-batch ($B=10$) | Conso Quota Journalier (RPD) | Risque Rate-Limit (RPM/TPM) |
|---|---|:---:|:---:|:---:|---|
| **`exp_00b` A priori Voiture** | Heuristique locale | 0 | 0 | **0 %** (0 req) | Nul (local) |
| **`exp_01a` Gemini Flash-Lite** | `gemini-3.1-flash-lite-preview` | 1 000 | **100** | **20 %** (100 / 500 RPD) | Nul (15 RPM géré par SWRR) |
| **`exp_01b` Mistral Small** | `mistral-small-latest` | 1 000 | **100** | **< 1 %** (sur 100M TPD) | Nul (60 RPM large) |
| **`exp_01c` Qwen-32B Local** | `Qwen2.5-32B-Instruct` | 1 000 | **100** | **0 %** (local GPU) | Nul (GPU local) |
| **`exp_02a` Gemini Calibré** | `gemini-3.1-flash-lite-preview` | 1 000 | **100** | **20 %** (100 / 500 RPD) | Nul (cache optimisé) |
| **`exp_02b` Gemini Few-Shot** | `gemini-3.1-flash-lite-preview` | 1 000 | **100** | **20 %** (100 / 500 RPD) | Nul |
| **`exp_03b` Oracle LightGBM** | Tabulaire supervisé | 0 | 0 | **0 %** (0 req) | Nul (local) |
| **`exp_04a` Hystérésis (5 jours)**| `gemini-3.1-flash-lite-preview` | 5 000 | **500** | **100 %** (500 / 500 RPD) | Nécessite 2 clés Google (`google_gemini31` + `google2`) |
| **`exp_04d` Hystérésis λ÷3 (5 j)** | `gemini-3.1-flash-lite-preview` | 5 000 | **500** | **100 %** (500 / 500 RPD) | Jour de campagne dédié (bras de sensibilité λ) |
| **`exp_05a..c` Presse Locale** | `gemini-3.1-flash-lite-preview` | 1 000 | **100** | **20 %** (100 / 500 RPD) | Nul (par condition ; 4 conditions LLM/événement) |

---

## 5. Synthèse des Expériences Définies

Le fichier `experiments.yaml` couvre la totalité du plan de recherche AAMAS 2027 :

1. **Phase 0 : Planchers Heuristiques & Physiques**
   * `exp_00a_random_otp` : Hasard uniforme parmi les options d'itinéraires OTP.
   * `exp_00b_majority_car` : A priori empirique (mode majoritaire : Voiture 100 %).
   * `exp_00c_shortest_time` : Heuristique du trajet le plus rapide (min durée OTP).
2. **Phase 1 : Modèles Nus / Bare LLM (Zero Prompt Engineering, $T=0.0$)**
   * `exp_01a_bare_gemini_flash_lite` : Google Gemini 3.1 Flash-Lite (référence distante économique).
   * `exp_01b_bare_mistral_small` : Mistral Small (modèle souverain européen).
   * `exp_01c_bare_qwen_32b_local` : Qwen-2.5-32B Instruct (modèle open-weight déterministe local vLLM).
3. **Phase 2 : Optimisation Sémantique & Prompt Calibré**
   * `exp_02a_calibrated_prompt` : LLM avec prompt optimisé issu de la calibration génétique.
   * `exp_02b_few_shot_emc2` : LLM avec injection de $k$ exemples réels de l'enquête EMC².
4. **Phase 3 : Plafond Tabulaire Supervisé (Baselines de référence)**
   * `exp_03a_multinomial_logit` : Logit Multinomial (MNL McFadden).
   * `exp_03b_oracle_lightgbm` : Oracle supervisé LightGBM scellé sur ProGEDO / EMC² 2023.
5. **Phase 4 : Valeur Ajoutée LLM — Hystérésis Post-Incident (Cinétique 5 Jours)**
   * `exp_04a_hysteresis_memory_5d` : Panne métro J2 + rétablissement J3-J5 avec mémoire court-terme $\mathcal{M}_t$ ($\lambda = 0{,}4$).
   * `exp_04b_hysteresis_amnesic_5d` : Condition contrôle : sans registre de mémoire.
   * `exp_04c_hysteresis_oracle_lightgbm` : Comportement de l'oracle tabulaire (amnésie structurelle).
   * `exp_04d_hysteresis_memory_5d_lambda_low` : Bras de sensibilité $\lambda \div 3 = 0{,}13$ — exécute le critère de réfutation (ii) du protocole (« diviser $\lambda$ par trois doit déplacer la courbe »).
6. **Phase 5 : Valeur Ajoutée LLM — Évaluation Écologique sur Presse Locale**
   * Événement 1 : Festival La Machine / Minotaure (Centre piétonnisé) — **5 conditions** (Nominal, Brut, Paraphrase sans indice modal, Placebo, Oracle encodé).
   * Événement 2 : Canicule & Pic d'Ozone (Crit'Air / TC réduits) — **5 conditions** (« pire cas » de suivi de consigne : l'article brut nomme la réponse modale).
   * Événement 3 : Coupure d'infrastructure Rocade Empalot (+1h de bouchon) — **5 conditions**.

> **Note.** La quantification d'incertitude n'est plus optionnelle : chaque métrique est publiée avec un
> IC95 par **cluster bootstrap par agent** ; les contrastes appariés des Phases 4 et 5 utilisent **McNemar** ;
> le calage macro vs EMC² utilise un **test d'équivalence (TOST, ±1 pt)**. Voir `defaults.scoring.uncertainty`.
