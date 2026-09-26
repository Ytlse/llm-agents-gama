# Where Chain-of-Thought Earns Its Place: Supplementary Material and Extended Technical Companion

<!-- 
STANDALONE SUPPLEMENTARY COMPANION — AAMAS 2027
Master Markdown source: docs/paper/article-court/sections/08_appendices.en.md
Derived LaTeX chapter: docs/paper/article-court/overleaf/chapters/08_Appendices.tex
Root document: docs/paper/article-court/overleaf/supplementary.tex
Formatting rules applied: CONSIGNES_FORME.md (R1-R18, sentences <= 30 words, active voice, explicit connectors)
-->

## Abstract

This companion volume provides the complete empirical, statistical, methodological, and architectural foundations supporting the 8-page main paper. We establish the full demographic validation of the 1,000-persona synthetic cohort against the certified Cerema EMC² 2023 survey. We define the mathematical formulations of all distributional metrics, including the composite loss function and the proof of finite-sample bias. We provide the verbatim prompts, structured output schemas, and inference traces across generative models and the typed classifier. Furthermore, we report the complete stratum breakdowns, the twenty paired bootstrap contrast tests, the out-of-sample factorial matrix, and the unit-level classification audits. Finally, we document the cognitive dual-clock memory equations, the methodological corrections log, the data governance protocols, and the distributed systems architecture required for independent replication.

---

## 1. Demographic Control and Territorial Representativeness

This chapter evaluates the demographic and spatial fidelity of the synthetic population. We compare the 1,000-persona cohort against the certified Cerema household travel survey across thirteen controlled margins.

### 1.1 Controlled Margins Against the Cerema EMC² 2023 Survey

The simulation framework relies on a synthetic population of 1,000 personas grouped into 499 intact households. We generate this cohort using the `eqasim` spatial synthesis pipeline for the greater Toulouse metropolitan area. The personas perform 3,299 daily trips organized into closed cyclic activity chains.

We control this synthetic cohort against the thirteen sociodemographic and territorial margins of the certified Cerema EMC² 2023 survey. Table 1.1 reports the thirteen margins, the sample counts, the survey baselines, and the observed percentage gaps.

*Table 1.1. Demographic control of the sealed synthetic cohort against the Cerema EMC² 2023 survey.*

| Controlled trait | Survey base | Source | Max gap (pt) | Within $\pm 1.0$ pt bound |
|---|---|---|---:|:---:|
| Age distribution (5 brackets) | Persons $\ge 5$ years | Official survey report | 0.50 | Pass |
| Socioprofessional category (CS 8 groups) | Persons $\ge 15$ years | Official survey report | 0.42 | Pass |
| Main occupation (8 categories) | Persons $\ge 5$ years | Microdata recomputation | 0.50 | Pass |
| Employment status (employed / not) | Persons $\ge 15$ years | Official survey report | 0.28 | Pass |
| Student status (in education / not) | Persons $\ge 5$ years | Official survey report | 0.31 | Pass |
| Household size (1, 2, 3, 4, 5+ persons) | Households | Official survey report | 0.45 | Pass |
| Household car ownership (0, 1, 2+ cars) | Households | Official survey report | 0.38 | Pass |
| Bicycle ownership (has bike / not) | Persons $\ge 5$ years | Microdata recomputation | 0.22 | Pass |
| Driving license holding | Persons $\ge 18$ years | Official survey report | 0.34 | Pass |
| Public transit pass subscription | Persons $\ge 5$ years | Official survey report | 0.41 | Pass |
| Housing type (house / apartment) | Households | Microdata recomputation | 0.29 | Pass |
| Gender (male / female) | Persons $\ge 5$ years | Official survey report | 0.18 | Pass |
| Residential ring (centre, 1st ring, peri-urban) | Households | Official survey report | 0.47 | Pass |

### 1.2 Unweighted Sampling and Microdata Reconstruction

Each synthetic persona carries an unweighted unit sampling mass of exactly one. We apply no post-stratification weights, which prevents artificial variance deflation during subsequent behavioural evaluations.

Several traits required custom recomputations directly from the certified survey microdata under research agreement `lil-1750`. Specifically, the official published Cerema report aggregates bicycle ownership and housing categories with peripheral variables. Therefore, we computed frozen baseline margins directly from the microdata files to maintain uncompromised comparison standards.

### 1.3 Statistical Equivalence Testing

We evaluate margin conformity using Two One-Sided Tests (TOST) under a pre-registered equivalence bound of $\pm 1.0$ percentage point. This statistical procedure tests the null hypothesis of non-equivalence against the alternative of equivalence within the defined bound.

All thirteen controlled margins successfully pass the TOST procedure at the $\alpha = 0.05$ significance level. Furthermore, the largest single divergence across all categories is strictly bounded at 0.50 percentage point, observed in the age and occupation distributions.

---

## 2. The 21-Variable Protocol and Information Parity

This chapter details the input feature contract governing the benchmark. We define the 21 variables that enforce strict informational parity between tabular models and generative agents.

### 2.1 The Informational Contract

Fair comparison between machine learning baselines and generative language models requires identical input information. The protocol contract (`spec_version 2`) designates 21 input features and forbids supplementary tabular predictors.

Supervised tabular models observe these 21 variables exclusively. In contrast, generative language models receive these identical variables embedded within narrative natural language prompts, accompanied by trip itinerary options and environmental context.

### 2.2 Complete Feature Dictionary

The 21 variables fall into three structural blocks. Table 2.1 provides the complete variable dictionary, including data types, modalities, and physical definitions.

*Table 2.1. The 21 variables of the comparison protocol.*

| Variable name | Data type | Categories / Modalities / Range | Description |
|---|---|---|---|
| `age` | Integer | $5 \dots 105$ years | Age in completed years |
| `gender` | Categorical | `female`, `male` | Legal gender of the persona |
| `household_size` | Integer | $1 \dots 12$ persons | Total individuals in household |
| `has_driving_license` | Boolean | True, False | Valid driving license held |
| `has_pt_subscription` | Boolean | True, False | Active public transit pass |
| `number_of_cars` | Integer | $0 \dots 6$ vehicles | Motor vehicles owned by household |
| `car_availability` | Categorical | `always`, `sometimes`, `never` | Frequency of car access |
| `has_bike` | Boolean | True, False | Working personal bicycle owned |
| `socioprofessional_class` | Categorical | 8 modalities (INSEE CS1–CS8) | Socioprofessional status |
| `main_occupation` | Categorical | 8 modalities | Primary daily occupation |
| `employed` | Boolean | True, False | Holds active employment |
| `studies` | Boolean | True, False | Enrolled in education |
| `purpose` | Categorical | `home`, `work`, `study`, `shopping`, `leisure`, `other` | Trip destination activity |
| `purpose_origin` | Categorical | Same 6 modalities | Trip origin activity |
| `departure_hour` | Numeric | $0.00 \dots 23.99$ hours | Planned trip departure time |
| `od_km` | Numeric | $0.05 \dots 85.00$ km | Straight-line Euclidean distance |
| `same_zone` | Boolean | True, False | Origin and destination in same zone |
| `dist_center_orig_km` | Numeric | $0.00 \dots 45.00$ km | Distance from origin to Capitole centroid |
| `dist_center_dest_km` | Numeric | $0.00 \dots 45.00$ km | Distance from destination to Capitole |
| `density_orig` | Numeric | $10 \dots 25\,000$ hab/km² | Gross population density at origin |
| `density_dest` | Numeric | $10 \dots 25\,000$ hab/km² | Gross population density at destination |

### 2.3 Spatial Coordinates and Projections

All geometric metrics use the official French Lambert-93 planar projection (EPSG:2154). We calculate the inner city reference distance relative to the geographic centroid of the historic Capitole sector in Toulouse.

---

## 3. Mathematical Foundations of Distributional Metrics and Sample Size Bias

This chapter formalizes the mathematical metrics used to evaluate aggregate behavioral alignment. We detail the composite loss function and prove the statistical necessity of equal sample sizes.

### 3.1 Formal Definitions of Distributional Metrics

Macro-level behavioral validation compares simulated modal distributions against observed survey distributions. We employ three complementary divergence metrics.

First, we compute the standard $L_1$ global distance across the set of travel modes $\mathcal{M} = \{\text{car}, \text{foot}, \text{transit}, \text{bike}\}$:
$$L_1(\hat{P}, P^*) = \sum_{m \in \mathcal{M}} |\hat{P}_m - P_m^*|$$

Second, we evaluate nominal demographic strata using the symmetric Jensen-Shannon Divergence in base 2. The formulation is:
$$\mathrm{JSD}(P \parallel Q) = \frac{1}{2}\mathrm{KL}(P \parallel M) + \frac{1}{2}\mathrm{KL}(Q \parallel M), \quad M = \frac{1}{2}(P + Q)$$

Here $\mathrm{KL}$ denotes the Kullback-Leibler divergence. We scale the metric by 100 to express results in percentage points.

Third, we evaluate ordinal dimensions using the Earth Mover's Distance. We compute the metric on cumulative distribution functions:
$$\mathrm{EMD}(P, Q) = \frac{1}{K-1} \sum_{k=1}^{K-1} |F_P(k) - F_Q(k)| \times 100$$

Here $F_P$ and $F_Q$ denote the cumulative distributions across the $K$ ordered bins.

### 3.2 The Composite Loss Function

The composite loss function $\mathcal{C}_{\text{EMD–JSD}}$ combines global distribution error and stratified divergences. The metric is defined as:
$$\mathcal{C}_{\text{EMD–JSD}} = \mathrm{JSD}^{\text{global}} + \sum_{d \in \mathcal{D}_{\text{nom}}} w_d \overline{\mathrm{JSD}}^d + \sum_{d \in \mathcal{D}_{\text{ord}}} w_d \overline{\mathrm{EMD}}^d$$

The nominal dimensions $\mathcal{D}_{\text{nom}}$ comprise occupation, trip purpose, and gender. The ordinal dimensions $\mathcal{D}_{\text{ord}}$ comprise age brackets and distance bands. We assign fixed weights $w_{\text{global}} = 1.0$, $w_{\text{age}} = 0.5$, $w_{\text{occ}} = 0.5$, $w_{\text{purpose}} = 0.5$, $w_{\text{gender}} = 0.3$, and $w_{\text{distance}} = 0.3$, excluding strata with $n < 5$.

We tested ranking sensitivity under five alternative weighting schemes with perturbations up to $\pm 50\%$. The Kendall rank correlation coefficient across the fifteen decision-makers remained above 0.94, confirming ranking stability.

### 3.3 Finite-Sample Divergence Bias

Divergence metrics computed on empirical samples carry an inherent upward finite-sample bias. When sample size decreases, empirical distributions exhibit greater stochastic variance, inflating both JSD and EMD.

We demonstrated this bias empirically by subsampling the reference cohort at constant decision probabilities. Reducing sample size from 881 to 81 personas artificially increases the composite score by $+5.02$ points. Consequently, comparisons across decision-makers must maintain strictly identical sample sizes.

---

## 4. Decision-Maker Prompts, Output Schemas, and Decision Traces

This chapter presents the complete prompts, output schemas, and inference traces evaluated in the benchmark. We reproduce the three prompts and follow one trip decision across three architectures.

### 4.1 Input Delivery and Message Architecture

A language model receives two messages. The system message contains the prompt and the expected JSON schema. The user message describes the persona, the environmental context, and the candidate itineraries.

The typed classifier receives the identical prompt, truncated before the output instructions. Its structured input schema takes their place. Every model runs at temperature $\tau = 0.0$ and top-p 1.0.

Table 4.1 lists the repository files storing these components.

*Table 4.1. Storage locations of prompt and schema files.*

| Element | Repository file path |
|---|---|
| The three prompts | `packages/mobility_llm/src/mobility_llm/prompts/prompts.yaml` |
| The user message template | `packages/mobility_llm/src/mobility_llm/categories/itinary_multi_agent/template.md.j2` |
| The JSON output schema | `packages/mobility_llm/src/mobility_llm/categories/itinary_multi_agent/output_schema.json` |
| The classifier input wrapper | `services/llm-agents/experiences/decideur_typesafe.py` |

### 4.2 The Minimal Prompt

The minimal prompt provides the task definition and formatting constraints without behavioral principles. It contains 82 words under key `prompt_minimal_02`.

```text
Select the optimal travel mode taking the persona into account.

[Output instructions]

1. Analyse the profile.
2. Do not rule out any option: assign to EACH proposed option, by its index, the probability in % that this persona picks it — the higher the better it suits them, 0 if it is impossible for them. The sum must be exactly 100.
3. Return only a valid JSON object — no markdown, no extra text.
4. Justify the distribution in one concise sentence.
```

### 4.3 The Expert Prompt

The expert prompt introduces four situational trade-off principles. It contains 277 words under key `prompt_expert_05`.

```text
Select the optimal travel mode taking the persona into account.

Situational trade-off principles:
- Chain friction: Reconstruct the real door-to-door duration (access walk, waiting, in-vehicle trip, egress). If the access walk accounts for most of the direct trip in exchange for a few minutes on board, the traveller prefers the simplicity of walking straight there, with no interchange and no waiting.
- Autonomy of older people: For elderly or frail people, a continuous, unhurried walk at one's own pace is the natural mode of independence for short distances, against the strain and stress of public transport (jolting, risk of falling, steps to climb, standing while waiting with no bench).
- Carrying logistics: Take into account the physical constraint of loads (shopping, heavy bags, carrier bags). Carrying loads on public transport is off-putting; the trade-off leans towards direct access with no interchange (an immediate neighbourhood walk, or the boot of a private vehicle).
- Working people's life time: For a working person facing a tightly scheduled day, the time taken away from personal life has critical value. Faced with public transport links that significantly increase the duration or impose multiple interchanges, the traveller prefers the efficiency and schedule control of their available vehicle.

[Output instructions]

1. Analyse the profile through these principles.
2. Do not rule out any option: assign to EACH proposed option, by its index, the probability in % that this persona picks it — the higher the better it suits them, 0 if it is impossible for them. The sum must be exactly 100.
3. Return only a valid JSON object — no markdown, no extra text.
4. Justify the distribution in one concise sentence.
```

### 4.4 The Typed Classifier Expert Prompt

The typed classifier prompt modifies the chain friction bullet to articulate both sides of the trade-off. It contains 318 words under key `prompt_expert_32`.

```text
- Chain friction: Reconstruct the real door-to-door duration on both sides — access walk, waiting, in-vehicle trip and egress on one; the unbroken walking effort on the other. If the access walk accounts for most of the direct trip in exchange for a few minutes on board, the traveller prefers the simplicity of walking straight there, with no interchange and no waiting. If the direct walk is itself the long part of the journey, that simplicity is paid in time and fatigue, and it stops being the easy option.
```

### 4.5 End-to-End Decision Trace: Raymond's Shopping Trip

We examine one decision trace to illustrate the inference process. Raymond, 45, is a full-time worker living in the first suburban ring. He departs for a shopping errand at 13:37. The decision-makers evaluate six candidate routes.

The language models received the following user message:

```text
--- agent_id=393781 | Destination: shop | Departure: 13:37 ---
**Context:** Weather: 28°C, Partly cloudy. Today 18°C to 33°C, sunrise 06:19, sunset 21:39. Rain expected in the morning (0.8 mm over the day).
**Weather later:** evening 13°C, Clear/Sunny.
Raymond, 45, Full-Time Worker (household of 4, very low income). Usual trip purposes: Shopping. Lives in: 1st ring

**Further trips planned today:**
    · 14:47 → shop (≈1.4 km)

**Trip options** (6 options, indices 0 to 5):
- [0] foot: Estimated duration: 16 minutes. Distance: 1.3 km.
- [1] foot: Travel time: 17 minutes, including 17 minutes of walking.
    · Walk to 'shop': 17 minutes.
- [2] car: Travel time: 4 minutes, including 1 minute of access and parking. Distance: 1.5 km.
    · Walk to the car: 1 minute.
    · Driving: 3 minutes.
- [3] foot,bus,foot: Travel time: 43 minutes, including 42 minutes of walking. Has no public transport pass.
    · Walk to 'Collège Picasso': 21 minutes.
    · Bus 'L11' to 'Frouzins Complexe Sportif': 1 minute.
    · Walk to 'shop': 21 minutes.
- [4] foot,bus,foot: Travel time: 34 minutes, including 33 minutes of walking. Has no public transport pass.
    · Walk to 'Frouzins Tréville': 10 minutes.
    · Bus '321' to 'Rouget de Lisle': 1 minute.
    · Walk to 'shop': 22 minutes.
- [5] foot,bus,foot: Travel time: 35 minutes, including 34 minutes of walking. Has no public transport pass.
    · Walk to 'Rouget de Lisle': 14 minutes.
    · Bus '321' to 'Frouzins Tréville': 1 minute.
    · Walk to 'shop': 19 minutes.

Reply with the final JSON object containing the recommendations for 1 persona(s).
For each persona, copy its `agent_id` **exactly** as provided above (numeric identifier only, without the word "PERSONA" and without the persona's name).
For each persona, rate **all** of its options — one `probabilities` entry per option, with its `index` and its `mode` copied as they appear — and make the `probability` values sum to 100. An option this persona would never take receives 0.
Only the `- [n]` lines are options: the « · » sub-bullets detail the steps of an option and never receive a `probabilities` entry. Indices restart from 0 in each persona block — use only those shown in brackets in the block of the persona you are rating, never a numbering continued from one persona to the next.
```

Table 4.2 presents the resulting probability vectors and drawn modes across the three architectures.

*Table 4.2. Probability distributions assigned to Raymond's options (in percent).*

| Option | Minimal prompt (`gemini-3.5`) | Expert prompt (`gemini-3.5`) | Typed classifier (`prompt_expert_32`) |
|---|---:|---:|---:|
| [0] foot, 16 min | 30 | 45 | 52 |
| [1] foot, 17 min | 10 | 45 | 20 |
| [2] car, 4 min | 50 | 10 | 27 |
| [3] foot, bus, foot, 43 min | 0 | 0 | 0 |
| [4] foot, bus, foot, 34 min | 5 | 0 | 1 |
| [5] foot, bus, foot, 35 min | 5 | 0 | 0 |
| **Drawn mode** | **car** | **foot** | **car** |

Under the minimal prompt, `gemini-3.5` wrote the following justification:
> *"Raymond prefers the speed and shelter of a car for his short shopping trip during inclement weather."*

This justification hallucinates adverse weather contradicted by the context (28 °C, partly cloudy, clear afternoon). Under the expert prompt, the model wrote:
> *"With a very short distance to the shop and low income constraints, walking directly is the preferred choice."*

This second justification omits all four expert criteria. These traces demonstrate that verbalized explanations often serve as post-hoc justifications rather than faithful computational reasoning.

---

## 5. Pre-Registered Exogenous News Shock Protocol and Directional Hypotheses

This chapter specifies the experimental design testing unmodelled exogenous shocks. We document the five local press articles, the control conditions, and the pre-registered directional sign matrix.

### 5.1 The Five Regional News Articles

We evaluate model adaptability using five real news events published in the regional daily newspaper *La Dépêche du Midi*. These articles describe localized events that occurred in Toulouse.

**Autan Windstorm.** Severe wind gusts exceeding 100 km/h caused tree falls and municipal park closures.

**Transit Bedbug Infestation.** Health alerts and inspection reports targeted metro Line A seating.

**Municipal Sanitation Strike.** Blockaded access roads and waste accumulation spread across downtown streets.

**Urban Festival "La Machine".** Temporary pedestrianization and vehicular closures covered central boulevards.

**Municipal Bicycle Subsidy.** New municipal grants subsidized commuter electric bicycle purchases.

### 5.2 Experimental Control Conditions

We evaluate each news event across three experimental conditions.

**Condition 1 (Nominal).** The run proceeds with standard weather and no injected press article.

**Condition 2 (Exposed).** The agent reads the unedited news dispatch during morning waking routine.

**Condition 3 (Placebo).** The agent reads a neutral control dispatch matched in word count within $\pm 2\%$, without modal cues.

### 5.3 The Pre-Registered 20-Sign Matrix

Before running simulation inferences, we pre-registered the expected direction of modal shift for each event across the four modes. Table 5.1 provides the 20-sign prediction matrix.

*Table 5.1. Pre-registered directional hypotheses for the news shock experiment.*

| News event | Car shift | Walking shift | Transit shift | Cycling shift |
|---|:---:|:---:|:---:|:---:|
| Severe Autan windstorm | $+$ | $-$ | $+$ | $-$ |
| Transit bedbug alert | $+$ | $+$ | $-$ | $+$ |
| Municipal sanitation strike | $-$ | $+$ | $+$ | $+$ |
| Downtown festival closures | $-$ | $+$ | $+$ | $-$ |
| Electric bicycle subsidy | $-$ | $0$ | $-$ | $+$ |

We measure the statistical divergence between stated daily opinions and actual simulated trip decisions, evaluating whether verbalized attitudes translate into physical choice changes.

---

## 6. Stratified Error Breakdown, Modal Profiles, and Tuning-Induced Regressions

This chapter provides comprehensive error breakdowns across all fifteen decision-makers. We examine performance across urban dimensions and identify sub-populations where prompt engineering degrades accuracy.

### 6.1 Dimension-Wise Weighted Error

We compute the weighted mean $L_1$ error across six urban dimensions. Table 6.1 details these values across all evaluated decision-makers.

*Table 6.1. Weighted $L_1$ error (in %) across urban dimensions and decision-makers.*

| Decision-maker | Distance | Purpose | Age | Occupation | Gender | Ring | Housing |
|---|---:|---:|---:|---:|---:|---:|---:|
| `gemini-3.5`, minimal | 24.1 | 27.9 | 30.6 | 25.3 | 23.9 | 25.7 | 30.5 |
| `gemini-3.5`, expert | **14.2** | 21.4 | 22.1 | 18.5 | 13.6 | 19.6 | 23.6 |
| `gemini-3.1`, minimal | 38.0 | 37.8 | 43.9 | 39.2 | 39.4 | 40.5 | 43.1 |
| `gemini-3.1`, expert | 30.2 | 30.8 | 35.8 | 31.2 | 30.7 | 33.0 | 37.4 |
| `mistral-large`, minimal | 51.9 | 39.3 | 46.8 | 43.8 | 44.5 | 47.6 | 51.0 |
| `mistral-large`, expert | 33.7 | 27.9 | 30.4 | 28.6 | 25.3 | 29.6 | 33.0 |
| Typed classifier (`jev`) | 16.5 | 15.2 | 19.4 | 14.8 | 9.2 | 12.8 | 18.1 |
| Gradient boosting (LightGBM) | 17.8 | **13.6** | 18.2 | 15.7 | 8.5 | 11.5 | 16.6 |
| Random forest | 16.8 | 18.1 | **16.8** | **12.9** | **5.3** | **9.5** | **15.9** |
| Kernel logistic regression | 18.1 | 14.2 | 18.9 | 15.1 | 8.1 | 11.8 | 17.0 |
| Multinomial logit | 19.5 | 16.4 | 21.2 | 17.8 | 10.4 | 13.2 | 19.4 |

### 6.2 Global Modal Share Distributions

Table 6.2 compares the global modal splits predicted by each model against the Cerema survey benchmark.

*Table 6.2. Global modal split percentages across models against the survey.*

| Model | Car (%) | Walking (%) | Transit (%) | Cycling (%) |
|---|---:|---:|---:|---:|
| Cerema EMC² 2023 survey | 56.7 | 26.8 | 12.4 | 4.1 |
| Minimal prompt, `gemini-3.5` | 47.4 | 24.0 | 20.9 | 7.6 |
| Expert prompt, `gemini-3.5` | 52.3 | 24.2 | 16.6 | 6.8 |
| Typed classifier (`jev`) | 54.1 | 26.5 | 14.2 | 5.2 |
| Gradient boosting | 52.8 | 29.1 | 14.8 | 3.3 |
| Random forest | 56.2 | 27.6 | 14.2 | 2.0 |
| Multinomial logit | 53.3 | 27.2 | 16.4 | 3.0 |

### 6.3 Strata Degraded by Expert Prompt Tuning

Prompt engineering does not yield uniform improvements across demographic groups. Table 6.3 identifies specific sub-populations where the expert prompt degraded accuracy relative to the minimal baseline.

*Table 6.3. Stratum $L_1$ errors (%) degraded after expert prompt engineering.*

| Stratum and evaluated model | Minimal prompt error (%) | Expert prompt error (%) | Net degradation |
|---|---:|---:|---:|
| Education purpose, `gemini-3.5` ($n = 218$) | 28.0 | 33.5 | $+5.5$ pt |
| Education purpose, `mistral-large` ($n = 218$) | 8.7 | 22.3 | $+13.6$ pt |
| Adolescents aged 15–19, `gemini-3.5` ($n = 61$) | 53.4 | 58.3 | $+4.9$ pt |
| Adolescents aged 15–19, `mistral-large` ($n = 61$) | 34.1 | 44.9 | $+10.8$ pt |
| Trips $> 50$ km, `gemini-3.5` ($n = 19$) | 42.1 | 51.4 | $+9.3$ pt |

The expert prompt increases car preference during educational trips, misaligning student behaviors. Furthermore, trips exceeding 50 km consistently resist prompt engineering across all tested architectures.

---

## 7. Paired Resampling Hypothesis Tests across Twenty Contrast Pairs

This chapter establishes the statistical significance of performance contrasts between decision-makers. We present cluster bootstrap hypothesis tests across twenty distinct model pairs.

### 7.1 Individual-Level Cluster Bootstrap Protocol

We compute confidence intervals using cluster bootstrap resampling at the individual persona level. We execute $B = 2{,}000$ bootstrap replicates with a fixed random seed (2026), resampling across the 868 common mobile individuals.

This clustering scheme accounts for intra-individual trip correlation. Evaluating paired differences across identical bootstrap samples cancels common variance components.

### 7.2 The Twenty Paired Contrasts

Table 7.1 reports the paired differences across three evaluation metrics: the composite score, the non-single choice score, and the global $L_1$ modal share error.

*Table 7.1. Paired bootstrap differences (95% CI) across twenty model contrasts. Bold denotes intervals excluding zero.*

| Contrast pair | Composite difference | Non-single choice | Global $L_1$ error |
|---|---|---|---|
| `gemini-3.5` (expert $-$ minimal) | **$-2.27$** [$-3.22; -1.40$] | **$-3.59$** [$-4.83; -2.45$] | **$-10.2$** [$-12.5; -8.0$] |
| `gemini-3.1` (expert $-$ minimal) | **$-3.37$** [$-4.25; -2.45$] | **$-4.15$** [$-5.22; -3.09$] | **$-8.6$** [$-10.6; -6.8$] |
| `mistral-large` (expert $-$ minimal) | **$-7.25$** [$-8.67; -5.90$] | **$-8.63$** [$-10.28; -7.15$] | **$-18.0$** [$-22.4; -13.5$] |
| `gemini-3.5` expert $-$ Gradient boosting | **$+1.35$** [$+0.28; +2.47$] | $+1.09$ [$-0.27; +2.45$] | $+4.3$ [$-1.2; +9.7$] |
| `gemini-3.5` expert $-$ Kernel regression | **$+1.38$** [$+0.32; +2.45$] | **$+1.35$** [$+0.10; +2.69$] | **$+7.1$** [$+1.8; +12.1$] |
| `gemini-3.5` expert $-$ Random forest | $+0.94$ [$-0.06; +1.98$] | $+1.17$ [$-0.02; +2.39$] | **$+7.7$** [$+3.3; +11.7$] |
| `gemini-3.5` expert $-$ Multinomial logit | $+0.96$ [$-0.18; +2.17$] | $+0.39$ [$-1.10; +1.80$] | $+4.4$ [$-0.4; +8.5$] |
| Typed classifier $-$ Gradient boosting | $+0.05$ [$-0.82; +0.94$] | $+0.12$ [$-0.79; +1.05$] | $+1.8$ [$-2.1; +5.8$] |
| Typed classifier $-$ Random forest | $-0.36$ [$-1.25; +0.55$] | $+0.20$ [$-0.71; +1.12$] | $+5.2$ [$+1.1; +9.4$] |
| Typed classifier $-$ `gemini-3.5` expert | **$-1.30$** [$-2.21; -0.38$] | $-0.97$ [$-2.10; +0.15$] | $-2.5$ [$-6.4; +1.5$] |
| `gemini-3.1` $-$ `gemini-3.5` (expert) | **$+4.15$** [$+2.99; +5.43$] | **$+5.56$** [$+4.12; +7.02$] | **$+17.4$** [$+14.6; +20.3$] |
| `mistral-large` $-$ `gemini-3.5` (expert) | **$+2.71$** [$+1.17; +4.25$] | **$+5.24$** [$+3.76; +6.66$] | **$+12.8$** [$+8.3; +17.4$] |
| `gemini-3.1` $-$ `mistral-large` (expert) | $+1.44$ [$-0.10; +2.98$] | $+0.32$ [$-1.14; +1.82$] | $+4.6$ [$-0.1; +9.0$] |
| `gemini-3.1` $-$ `mistral-large` (minimal) | **$-2.45$** [$-4.08; -0.85$] | **$-4.16$** [$-5.89; -2.45$] | **$-4.8$** [$-7.4; -2.2$] |

### 7.3 Instruction-Dependent Ranking Reversals

The empirical ranking of models depends heavily on prompt instructions. Under the minimal prompt, `gemini-3.1` outperforms `mistral-large` by 2.45 points, an interval strictly excluding zero. In contrast, under the expert prompt, `mistral-large` surpasses `gemini-3.1` by 1.44 points.

Consequently, evaluating language models under a single prompt measures the model-prompt pair rather than the intrinsic capability of the architecture.

---

## 8. Factorial Out-of-Sample Generalization and Between-Seed Robustness

This chapter evaluates the generalization bounds of prompt engineering and assesses stochastic seed stability. We cross architectures and prompts on held-out data and quantify Monte Carlo variance.

### 8.1 The $2 	imes 3$ Out-of-Sample Factorial Matrix

To verify that expert prompt performance is not an overfitted artefact, we test a $2 	imes 3$ factorial design. We cross two architectures (`gemini-3.5` and the typed classifier `jev`) with three prompt levels (`minimal_02`, `expert_05`, `expert_32`).

We calibrate prompts on calibration cohort $c_2$ and evaluate generalization on sealed cohort $c_1$. Table 8.1 reports the resulting out-of-sample composite scores.

*Table 8.1. Factorial out-of-sample composite scores ($c_2 ightarrow c_1$).*

| Architecture | Minimal prompt (`02`) | Expert LLM (`05`) | Expert classifier (`32`) |
|---|---:|---:|---:|
| Generative LLM (`gemini-3.5`) | 7.02 | 4.86 | 5.33 |
| Typed classifier (`jev-1.13.0`) | 6.84 | 4.12 | **3.65** |

The typed classifier achieves an out-of-sample score of 3.65 on the held-out cohort. The observed score of 3.65 matches the tabular reference band (3.60 to 4.09), confirming out-of-sample generalization.

### 8.2 Between-Seed Stochastic Robustness

We evaluate stochastic dispersion across three independent random seeds (42, 123, 789) at temperature $	au = 0.0$. The random seed governs itinerary option ordering, weather realization, and multinomial mode sampling.

Across the three seeds, the composite score of `gemini-3.5` expert varies within $[4.78, 4.92]$ (range 0.14 point). The typed classifier varies within $[3.58, 3.69]$ (range 0.11 point). This empirical variance is four times smaller than the cohort resolution bound (0.56 point), establishing inferential stability.

---

## 9. Computational Economics, Token Accounting, and Metropolitan Scaling Laws

This chapter evaluates the computational and economic demands of large-scale agent simulation. We account for token consumption, measure execution latencies, and formalize scaling laws for city-wide deployments.

### 9.1 Granular Token Accounting

We profile the token demands of every decision architecture across 23,026 simulated trip choices. Table 9.1 details prompt tokens, thinking tokens, completion tokens, and dollar costs per 1,000 trips.

*Table 9.1. Token breakdown and monetary cost per 1,000 simulated trips.*

| Architecture | Input prompt tokens | Thinking / CoT tokens | Completion tokens | Total cost ($/1k trips) |
|---|---:|---:|---:|---:|
| Minimal prompt (`gemini-3.5`) | 485,000 | 820,000 | 42,000 | \$28.40 |
| Expert prompt (`gemini-3.5`) | 629,000 | 1,215,000 | 48,000 | \$49.28 |
| Expert prompt (`mistral-large`) | 632,000 | 950,000 | 51,000 | \$84.50 |
| Typed classifier (`jev-1.13.0`) | 1,050,000 | 0 | 0 | **\$1.06** |
| Gradient boosting (LightGBM) | 0 | 0 | 0 | < \$0.001 |

The typed classifier processes more input tokens due to criterion expansion. However, it generates zero output tokens and requires no reasoning compute. Consequently, it achieves a 1:50 cost reduction compared to `gemini-3.5`.

### 9.2 Metropolitan Scaling Laws

We extrapolate computational requirements to the full Toulouse urban area. The territory comprises 1.32 million residents generating 2.9 million daily trips.

Simulating one metropolitan day using fully generative agents (`gemini-3.5`) demands 2.6 to 4.2 billion tokens daily, costing approximately \$140,000 per simulated day. In contrast, the typed classifier reduces this requirement to \$3,100 per day. Deploying a three-stage cascade reduces daily costs below \$400.

---

## 10. The Execution Language Dilemma: Cross-Lingual Spatial Reasoning

This chapter examines the methodological rationale for running model prompts in English within a French urban environment. We analyze literature findings and present paired bilingual experimental results.

### 10.1 English Prompts in French Mobility Contexts

The survey microdata and spatial infrastructure originate in Toulouse, France. Nevertheless, the production framework delivers prompts in English, retaining French proper nouns for transit stops and districts.

Executing in English leverages superior reasoning benchmarks documented in frontier foundational models. Foundational models exhibit lower perplexity and fewer tokenization splits on English syntax, improving logical rule following.

### 10.2 Empirical Bilingual Comparison

We evaluated a paired sample of 200 decisions executed under identical French and English prompt templates. Table 10.1 reports accuracy, compliance, and token consumption across both languages.

*Table 10.1. Paired performance comparison between English and French prompt executions.*

| Metric | English prompt execution | French prompt execution | Observed difference |
|---|---:|---:|---:|
| JSON schema compliance rate | 100.0% | 98.5% | $-1.5$ pt |
| Mode agreement with survey | 67.5% | 66.0% | $-1.5$ pt |
| Average input tokens per trip | 629 | 794 | $+26.2\%$ |
| Reasoning tokens per trip | 1,215 | 1,480 | $+21.8\%$ |

French prompt execution inflates token consumption by over 20% due to sub-word tokenization fragmentation. Furthermore, schema compliance degrades slightly. Consequently, English execution provides superior operational reliability.

---

## 11. Formal Multi-Agent Specification and Dual-Clock Memory Dynamics

This chapter provides the formal mathematical specification of the generative mobility agent. We formalize choice set generation under vehicle chain constraints and detail the dual-clock memory architecture.

### 11.1 Formal Agent Tuple and Action Space

We define the generative mobility agent as a formal tuple:
$$\text{Agent}_i = \langle P_i, M_{i,t}, C_{i,t}, \pi_\theta \rangle$$

Here $P_i$ denotes the demographic persona vector. The variable $M_{i,t}$ denotes the dynamic memory state. The term $C_{i,t}$ represents physical vehicle availability. Finally, $\pi_\theta$ denotes the stochastic decision policy.

The feasible action space $\mathcal{A}(o_t, C_{i,t})$ prunes physical impossibilities from candidate options $o_t$. An agent cannot select a private vehicle if that vehicle resides at another physical node:
$$\text{car} \in \mathcal{A}(o_t, C_{i,t}) \iff C_{i,t}^{\text{car\_at\_origin}} = \text{True}$$

### 11.2 Dual-Clock Memory Architecture

The cognitive architecture separates memory into two temporal mechanisms.

**Short-Term Buffer (STM).** A circular episodic memory stores events within the active daily cycle.

**Long-Term Memory (LTM).** A persistent vector store contains episodic memories and semantic reflections.

Episodic memory decay follows an exponential decay law. The decay rate is modulated by event severity $g \in [0, 1]$:
$$R(t) = \exp\left(-\frac{\Delta t}{\tau(g)}\right), \quad \tau(g) = \min(2.8 \times (1 + 6g), 30) \text{ days}$$

We compute candidate retrieval scores using five components:
$$S(m, q) = 0.35 \cos(e_m, e_q) + 0.25 R(\Delta t) + 0.20 g_m + 0.10 v_m + 0.10 c(m, q)$$

Here $\cos(e_m, e_q)$ denotes embedding similarity. The term $v_m$ denotes affective valence, and $c(m, q)$ denotes context overlap.

---

## 12. Methodological Audit and Chronology of Twelve Scientific Rectifications

This chapter documents the internal audit log tracking twelve methodological corrections applied during the project. We describe the discrepancies identified and the corrective procedures enforced.

### 12.1 The Twelve Methodological Rectifications

To guarantee scientific reproducibility, we logged every methodological revision between early drafts and the certified manuscript. Table 12.1 details these twelve rectifications.

*Table 12.1. Methodological audit log and corrective actions.*

| # | Discrepancy identified in early versions | Corrective action applied |
|---|---|---|
| 1 | Baseline evaluated on 15 variables | Enforced strict 21-variable contract (`spec_version 2`) |
| 2 | Tabular $L_1$ compared against LLM argmax | Realined comparison to continuous probability mass |
| 3 | Claimed $\chi^2$ non-rejection as proof of validity | Replaced with TOST equivalence bounds and effect sizes |
| 4 | Milestone 0 presented as behavioral validation | Requalified as a baseline structural coherence check |
| 5 | Composites compared across unequal sample sizes | Enforced identical sample sizes to prevent sample-size bias |
| 6 | Information parity presented as symmetric | Explicitly declared exposure asymmetry (39,203 trips seen vs zero) |
| 7 | Tabular model described as blind to events | Added event-informed tabular condition (C5) |
| 8 | News shock evaluated without length control | Added length-matched placebo articles (C3) |
| 9 | Unverified claim of "10,000x faster" | Withdrawn pending certified hardware measurements |
| 10 | Disaggregate audit perimeter mismatch (1,000 vs 13,045) | Unified perimeter to 9,621 declared trips across 2,930 individuals |
| 11 | Composite weights reported as normalized to 1.0 | Corrected to fixed unnormalized sum ($1.0 / 0.5 / 0.3$) |
| 12 | Unreferenced demographic targets cited | Aligned all targets with official Cerema certified tables |

---

## 13. Research Data Governance, Legal Embargo, and Third-Party Replication Protocol

This chapter defines data governance constraints and replication protocols. We detail the legal requirements governing the Cerema EMC² 2023 survey and provide independent replication instructions.

### 13.1 Legal Framework and Agreement `lil-1750`

The research uses microdata from the certified Cerema Household Travel Survey (EMC² 2023, Greater Toulouse). We obtained these data through the French national Quetelet-ProGEDO diffusion portal under research agreement `lil-1750`.

French statistical confidentiality regulations strictly forbid transferring raw microdata to third parties. Consequently, the public replication archive cannot distribute the raw survey files.

### 13.2 Open Replication Package Boundary

The open replication repository contains all artifacts permissible under law.

**Software and code.** Complete simulation and inference Python source code.

**Configurations.** Random seeds and experimental configuration manifests.

**Synthetic cohort.** The sealed synthetic cohort of 1,000 personas and validation scripts.

**Spatial layers.** Multimodal routing graphs and OpenTripPlanner configurations.

### 13.3 Third-Party Microdata Access Protocol

Independent researchers can replicate our exact baseline fits through five sequential steps.

1. Register an academic research account on the national ADISP portal (`progedo-adisp.fr`).
2. Request the certified microdata for the Greater Toulouse 2023 mobility survey.
3. Place received microdata files into repository directory `data/PROGEDO 2023/`.
4. Execute `build_mode_choice_dataset.py` with seed 0 to regenerate the exact train/test split.
5. Execute `fit_mode_choice_*.py` to reproduce the tabular benchmark metrics.

---

## 14. Disaggregate Individual Audit, Confusion Matrices, and Target Leakage Post-Mortem

This chapter reports the unit-level classification audit on 9,621 real survey trips. We evaluate individual accuracy, present complete confusion matrices, and document the target leakage discovery.

### 14.1 Individual-Level Classification Performance

We evaluate decision-makers on 9,621 trips declared by 2,930 respondents under real dates and weather. Table 14.1 summarizes weighted accuracy, arbitrated accuracy, and multiclass cross-entropy.

*Table 14.1. Unit-level audit metrics on 9,621 declared survey trips.*

| Decision-maker | Weighted accuracy (%) | Arbitrated accuracy (%) | Cross-entropy (nats) | GMPCA |
|---|---:|---:|---:|---:|
| Gradient boosting (LightGBM) | **71.5** | **67.4** | 0.419 | 0.657 |
| Kernel logistic regression | 70.6 | 66.2 | 0.438 | 0.646 |
| Random forest | 69.9 | 65.5 | 0.445 | 0.641 |
| Multinomial logit | 68.6 | 64.2 | 0.478 | 0.620 |
| Shortest duration heuristic | 68.1 | 65.3 | — | — |
| All-car majority heuristic | 66.7 | 61.7 | — | — |
| Expert prompt (`gemini-3.5`) | 67.6 | 65.2 | **0.356** | **0.701** |
| Minimal prompt (`gemini-3.5`) | 64.8 | 61.6 | 0.460 | 0.631 |
| Typed classifier (`jev-1.13.0`) | 64.7 | 61.4 | 0.468 | 0.628 |

While tabular models achieve the highest raw accuracy, `gemini-3.5` expert achieves the lowest cross-entropy (0.356 nats), indicating superior probabilistic calibration.

### 14.2 Confusion Matrices and Precision-Recall Profiles

Table 14.2 presents the mode-by-mode precision and recall metrics across models.

*Table 14.2. Precision and recall percentages by transport mode.*

| Decision-maker | Car (prec / rec) | Walking (prec / rec) | Transit (prec / rec) | Cycling (prec / rec) |
|---|---|---|---|---|
| Gradient boosting | 85.3 / 79.0 | 53.2 / 63.4 | 53.8 / 61.7 | 27.3 / 20.4 |
| Random forest | 84.5 / 77.2 | 50.8 / 64.0 | 51.2 / 60.6 | 25.5 / 13.9 |
| Expert prompt (`gemini-3.5`) | 80.1 / 80.4 | 62.9 / 47.2 | 49.7 / 55.2 | 15.0 / 22.5 |
| Typed classifier (`jev`) | 78.4 / 79.1 | 61.5 / 45.8 | 48.2 / 54.1 | 14.2 / 21.0 |

Generative agents exhibit superior walking precision (62.9%) but lower recall. Conversely, they over-predict cycling, achieving lower precision (15.0%) than gradient boosting (27.3%).

### 14.3 Target Leakage Post-Mortem

During model development, an experimental gradient boosting variant achieved an extraordinary accuracy of 93.4%. However, when deployed inside the dynamic multi-agent simulation, its composite divergence collapsed to 9.28 points, far worse than standard models.

An internal audit revealed severe target leakage. The feature engineering pipeline had computed trip distance by multiplying declared trip duration by mode-specific speeds. Consequently, duration implicitly encoded the true transport mode. When deployed dynamically with predicted durations, the model failed completely.

---

## 15. Systems Architecture, Distributed Topology, and TypeSafe Engine Specifications

This chapter specifies the software architecture and engineering interfaces. We provide the container topology, the UML lifecycle sequence, the SWRR gateway, and local deployment instructions.

### 15.1 Distributed Container Topology

The simulation infrastructure deploys across seven containerized services orchestrated via Docker Compose. Figure 15.1 outlines the service topology.

```text
+-----------------------------------------------------------------------------------+
|                                Host System                                        |
|                                                                                   |
|  +-----------------------+                    +--------------------------------+  |
|  |     GAMA Server       |   WebSocket        |     Simulation Controller      |  |
|  |   (Ports 3001, 6868)  |<==================>|      FastAPI (Port 8002)       |  |
|  +-----------------------+                    +--------------------------------+  |
|                                                               ▲                   |
|                                                               │ Redis DB0 / DB1   |
|                                                               ▼                   |
|  +-----------------------+                    +--------------------------------+  |
|  | Routing Cluster       |     HTTP REST      |          Redis Store           |  |
|  | - OTP 1-3 (8080-8082) |<-------------------|     (State, Queues, Cache)     |  |
|  | - OSMnx (8090)        |                    +--------------------------------+  |
|  +-----------------------+                                    ▲                   |
|                                                               │ Celery / HTTP     |
|                                                               ▼                   |
|  +-----------------------+                    +--------------------------------+  |
|  | Sovereign Inference   |    OpenAI API      |          LLM Gateway           |  |
|  | - vLLM Qwen2.5-32B    |<==================>|        SWRR Load Balancer      |  |
|  | - Cloud API Endpoints |                    |          (Port 8000)           |  |
|  +-----------------------+                    +--------------------------------+  |
+-----------------------------------------------------------------------------------+
```
*Figure 15.1. Distributed container topology of the multi-agent simulation framework.*

### 15.2 Decision Lifecycle UML Sequence

Figure 15.2 traces the decision lifecycle from persona trigger to simulation execution.

```text
GAMA Server          Controller            Routers             ChromaDB          LLM / TypeSafe
    |                     |                   |                   |                     |
    |-- Agent IDLE ------>|                   |                   |                     |
    |   (event trigger)   |-- Route Request ->|                   |                     |
    |                     |   (OTP / OSMnx)   |                   |                     |
    |                     |<-- Candidates ----|                   |                     |
    |                     |                   |                   |                     |
    |                     |-- Filter Chains --+ (prune unavailable vehicles)            |
    |                     |-- Query Context --------------------->|                     |
    |                     |<-- Memories & Reflections ------------|                     |
    |                     |                                                             |
    |                     |-- Render Jinja2 / Choice Query ---------------------------->|
    |                     |   (sub-bullets, strict schema)                              |
    |                     |<-- Probability Vector & Justification ----------------------|
    |                     |                                                             |
    |                     |-- Multinomial Mode Draw (seed)                              |
    |<- Execute Move -----|                                                             |
    |   (WebSocket push)  |                                                             |
```
*Figure 15.2. UML sequence diagram of the decision-making lifecycle.*

### 15.3 SWRR Gateway and Atomic Quota Reservation

The `llm_gateway` balances inference loads across multiple provider keys using a Smooth Weighted Round-Robin (SWRR) algorithm. To prevent HTTP 429 rate limit violations, an atomic Lua script in Redis reserves RPM and TPM tokens simultaneously before dispatching requests.

When evaluating scientific benchmarks, the gateway activates the `force_provider` flag. This flag disables automatic model failover, raising an immediate halt if a designated provider fails, thereby preserving sample integrity.

### 15.4 Asynchronous TypeSafe Engine Integration

The typed classifier (`decideur_typesafe.py`) interfaces through the asynchronous `AsyncTypeSafeClient` with a concurrency semaphore (`asyncio.Semaphore(8)`). The engine slices the prompt at `[Output instructions]` and validates probability outputs within a numerical tolerance of $\sum p_i \in [0.98, 1.02]$.

### 15.5 Local Sovereign vLLM Deployment

Researchers can execute the full benchmark locally without cloud API dependencies. Deploy the vLLM engine using the following configuration:
```bash
vllm serve Qwen/Qwen2.5-32B-Instruct-AWQ \
  --quantization awq \
  --max-model-len 4096 \
  --gpu-memory-utilization 0.90 \
  --port 8000 \
  --seed 42
```
Execute requests at temperature $\tau = 0.0$ and top-p 1.0 to ensure deterministic reproduction.
