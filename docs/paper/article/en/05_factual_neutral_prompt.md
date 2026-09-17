# 5. A protocol for calibrating mode choice

<!-- Dernière mise à jour : 2026-09-17 -->

**Document:** chapter 5 of the AAMAS 2027 paper — the **protocol** chapter: it defines the conditions being compared, and chapter 6 says what the comparison establishes. English master; French mirror in [`fr/05_factual_neutral_prompt.md`](../fr/05_factual_neutral_prompt.md); LaTeX rendering for Overleaf in [`overleaf/05_factual_neutral_prompt.tex`](../overleaf/05_factual_neutral_prompt.tex).
**Status:** `draft v0.10` (17 September 2026) — the title becomes descriptive: “Four ways of choosing, one set of facts” announced an equality of information that the contract of § 4.3 does not establish, since it equalises the 21 variables and not the information each decider holds. § 5.3.5 now publishes the full text of the reference expert prompt (`prompt_expert_05`), as § 5.1 publishes that of the minimal prompt.
**Previous status:** `draft v0.9` (17 September 2026) — first English master, translated from the French `brouillon v0.9` of 16 September 2026. The French carries the version history; it is not repeated here.
**Place in the paper:** section 5 of the plan announced in § 1.4 of [`../en/01_introduction.md`](../en/01_introduction.md). Outline: [`../plan/PLAN.md`](../plan/PLAN.md). Progress: [`../README.md`](../README.md).
**Convention:** a figure **in bold brackets** is an empty placeholder.

---

Embedding language-model agents in a multi-agent simulation of urban mobility raises a demand for micro-behavioural calibration. In the full model of chapter 3, agents interact through a dynamic environment that constrains them: road congestion under GAMA, saturation of public transport lines, and the strict temporal coupling imposed by the chain of personal vehicles. For the macroscopic dynamics that emerge from the simulation to be faithful to a territory, the local decision policy of each individual agent has to be representative of the population being modelled.

This chapter sets out the experimental protocol designed to isolate, calibrate and evaluate that local mode-choice policy before it is deployed in the interactive simulator. Isolating the agent means putting its decision mechanism in a unit choice situation: one specific trip, characterised by a sociological profile, a computed multimodal offer and weather conditions, with no dynamic history of the day already lived. The aim of this calibration phase is to adjust the decider's qualitative arbitration so that the distribution of its choices reproduces the regularities observed in the household travel survey, without degrading its transferability.

Four decision conditions are compared on equal inputs, under the evaluation contract of § 4.3:

1. Statistical floors and physical heuristics: reference rules with no behavioural information (uniform random draw, majority-mode zero-rule prediction, shortest-duration network heuristic).
2. The minimal prompt: the language model receiving the exhaustive situational facts with no arbitration instruction whatsoever (zero-shot descriptive).
3. The expert prompt: the model guided by reasoning heuristics optimised under strict qualitative constraints.
4. Supervised tabular models: four reference statistical algorithms fitted directly on the survey microdata.

§ 5.1 details the specification of the minimal prompt and publishes one complete inference case. § 5.2 sets out the multi-model benchmark that guarantees architectural invariance. § 5.3 gives the mathematical form of the discrete prompt-calibration problem and its guard-rails against overfitting. § 5.4 bounds the performance space between heuristic floors and the tabular ceiling. § 5.5 describes the ground-parity audit protocol that measures disaggregate accuracy on the real trips of the survey.

## 5.1 The minimal prompt (persona detail plus itinerary options)

The baseline condition evaluates generic foundation models, used off the shelf with no supervised retraining, against a minimal and circumstantial prompt. It measures the model's native decision capacity when facing a rich descriptive state, in the complete absence of strategic guidance.

For each decision $i$, the state submitted to the model is a quadruple $s_i = (x_i, \mathcal{O}_i, \mathcal{A}_i, \mathcal{W}_i)$:

1. The persona's sociological vector ($x_i$): age, sex, socio-professional category, household size and composition, income class, car ownership, driving licence and public transport passes.
2. The multimodal itinerary offer ($\mathcal{O}_i$): the set of options physically computed for the trip. Individual trips (walking, cycling, car) come from the shortest path on the OpenStreetMap graph; public transport trips are computed by OpenTripPlanner on the real service timetables, including the detail of each leg (access, waiting, transfers, in-vehicle time).
3. The planned agenda for the day ($\mathcal{A}_i$): the chain of remaining activities and their distances up to the final return home.
4. The weather context ($\mathcal{W}_i$): conditions at the moment of departure and the forecast for later time slots.

The system instruction is strictly limited to defining the task and the output format of the decision:

> *Select the optimal travel mode taking the persona into account.*
>
> *[Output instructions]*
>
> 1. *Analyse the profile.*
> 2. *Do not rule out any option: assign to EACH proposed option, by its index, the probability in % that this persona picks it — the higher the better it suits them, 0 if it is impossible for them. The sum must be exactly 100.*
> 3. *Return only a valid JSON object — no markdown, no extra text.*
> 4. *Justify the distribution in one concise sentence.*

<!-- source: packages/mobility_llm/src/mobility_llm/prompts/prompts.yaml, variant prompt_minimal_02 (82 words, "minimal" family, neutrality audit passed on 2026-09-14); the expected JSON schema follows the instruction and is reproduced in the appendix -->

One concrete inference case shows the structure of the signal the model receives:

```
--- agent_id=1320713 | Destination: work | Departure: 08:16 ---
**Context:** Weather: 10°C, Clear/Sunny. Today 10°C to 22°C, sunrise 06:27,
sunset 21:15. No precipitation expected.
**Weather later:** afternoon 15°C, Clear/Sunny · evening 16°C, Clear/Sunny.
Frédéric-Adrien, 28, Full-Time Worker (household of 2, very low income).
Usual trip purposes: Work. Lives in: Toulouse

**Further trips planned today:**
    · 13:32 → other (≈12.4 km)
    · 16:27 → home (≈11.5 km)
    · 20:00 → leisure (≈15.1 km)

**Trip options** (5 options, indices 0 to 4):
- [0] foot,metro,foot: Travel time: 20 minutes, including 16 minutes of walking.
      Has a public transport pass.
    · Walk to 'Marengo-SNCF': 9 minutes.
    · Metro 'A' to 'Esquirol': 4 minutes.
    · Walk to 'work': 7 minutes.
- [1] foot: Estimated duration: 26 minutes. Distance: 2.0 km.
- [2] bicycle: Estimated duration: 11 minutes. Distance: 2.2 km.
- [3] foot: Travel time: 28 minutes, including 28 minutes of walking.
    · Walk to 'work': 28 minutes.
- [4] car: Estimated duration: 11 minutes. Distance: 3.0 km.
```

The answer returned by the model:

```json
[{"agent_id": "1320713",
  "probabilities": [
    {"index": 0, "mode": "foot,metro,foot", "probability": 20.0},
    {"index": 1, "mode": "foot",            "probability":  5.0},
    {"index": 2, "mode": "bicycle",         "probability": 50.0},
    {"index": 3, "mode": "foot",            "probability":  5.0},
    {"index": 4, "mode": "car",             "probability": 20.0}],
  "reason": "Frédéric-Adrien favors the fast 11-minute bicycle ride to save time
             on a tight schedule while keeping costs low, bypassing a slow walk."}]
```

<!-- source: block received and answer — data/experiences/exp_gemini-35-fl_proexp04_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_t0_nosim/executions/2026-09-15_05_18_34/decisions.jsonl, person_id 1320713.
WARNING — CASE TO BE REDONE BEFORE PUBLICATION, in full. (1) The departure of this trip resolves to 17 March: it is one of the 866 cases that ticket 088 dated to the next day, so its itinerary offer was computed for the wrong day. (2) The answer quoted comes from the decider under the expert prompt, the Level 1 decider having no score on the v6. Both the received block AND the answer are to be taken again from a prompt_minimal_02 decider replayed on the corrected set (ticket 088 § 3.4). -->

The model receives five options for a two-kilometre trip, among them two walking paths and one option combining walking and metro. With no directive on the relative burden of walking, the value of time or the effect of weather, the model spreads its probability mass over the available options. It is this continuous distribution that is scored under the contract of § 4.3.

## 5.2 The benchmark: the same facts, several models

To separate what belongs to the decision framework itself from artefacts of one inference architecture, the protocol submits both the minimal prompt and the expert prompt to a battery of heterogeneous models. The test set, the agent contexts and the randomisation of option order stay strictly invariant from one model to the next.

| Provider | Model | Minimal prompt | Expert prompt |
|---|---|:--:|:--:|
| Google | `gemini-3.1-flash-lite` | measured | measured |
| Google | `gemini-3.5-flash-lite` | **[xx]** | measured |
| Mistral | `mistral-large-2512` | measured | measured |

<!-- sources: data/experiences/exp_{gemini-31-fl,gemini-35-fl,mistral-l-25}_{promin02,proexp05,proexp06,proexp08}_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_t0_nosim, runs of 2026-09-15; proexp04 removed from this list on 2026-09-17, the variant having been deleted from the repository. The scores belong to chapter 6. [xx]: the gemini-3.5-flash-lite decider under the minimal prompt is queued in the campaign, and will in any case be replayed on the corrected set of ticket 088. -->

**Benchmark to be completed.** Two providers and three models document feasibility but do not constitute universal coverage. Deciders based on the Claude family are declared and running; a model of the OpenAI family is scheduled. The conclusions drawn qualify the architectures measured and do not claim to extend, without verification, to language models at large.

## 5.3 The expert prompt: discrete optimisation under cognitive constraints

Evaluating the minimal prompt brings out systematic distortions in the distribution of choices across population strata. To reduce those gaps without degrading the agent's robustness, the system prompt goes through a structured optimisation process, guided by the composite loss defined in § 4.2.

### 5.3.1 Mathematical formulation of the calibration

Let $\Pi$ be the space of admissible textual prompts. A prompt $p \in \Pi$ parameterises the local policy of an agent $\pi(\cdot \mid s_i; p)$, which maps any perceived state $s_i$ to a probability distribution over the available modes $\mathcal{M}(\mathcal{O}_i)$.

For a subpopulation $\mathcal{D}_k \subset \mathcal{D}_{\text{train}}$ defined by a sociological or spatial stratum $k \in \mathcal{K}$ (age band, purpose, socio-professional category, distance class), the macroscopic modal share estimated for mode $m$ under prompt $p$ is the mean of the verbalised probabilities:

$$\hat{P}_{k,m}(p) = \frac{1}{|\mathcal{D}_k|} \sum_{i \in \mathcal{D}_k} \pi(m \mid s_i; p)$$

Let $\mathbf{P}^*_k$ be the empirical reference vector taken from the survey for stratum $k$. Prompt calibration then takes the form of a discrete optimisation problem under constraints:

$$\min_{p \in \Pi} \mathcal{L}(p; \mathcal{D}_{\text{train}}) = \sum_{k \in \mathcal{K}} w_k \, D_k\left(\hat{\mathbf{P}}_k(p), \mathbf{P}^*_k\right) \quad \text{subject to} \quad \begin{cases} \mathcal{C}_{\text{qualitative}}(p) = 1 \\ \mathcal{C}_{\text{agnostic}}(p) = 1 \end{cases}$$

where $D_k$ is the Jensen–Shannon divergence ($\mathrm{JSD}$) for nominal variables and the optimal transport distance ($\mathrm{EMD}$) for ordered ordinal variables, weighted by $w_k$. The predicates $\mathcal{C}_{\text{qualitative}}$ and $\mathcal{C}_{\text{agnostic}}$ enforce the admissibility guard-rails set out below.

### 5.3.2 Reflective discrete optimisation

The textual space $\Pi$ being discrete and non-differentiable, the optimisation proceeds by model-assisted reflective search (*reflective discrete optimisation*), in the line of *Reflexion* (Shinn et al., 2023) and *TextGrad* (Yuksekgonul et al., 2024).

At each iteration $t$, the system computes the matrix of empirical residuals stratum by stratum:

$$\mathbf{R}^{(t)} = \left( \hat{\mathbf{P}}_k(p^{(t)}) - \mathbf{P}^*_k \right)_{k \in \mathcal{K}}$$

A meta-optimiser (an LLM given a dedicated reasoning budget) reads this matrix of gaps, states a cognitive hypothesis about the underlying reasoning bias, and proposes a targeted textual mutation $p^{(t+1)}$.

The treatment of distance elasticity illustrates the mechanism. In the reference campaign, the share given to the private car stayed flat across every distance class (42.7 %, 46.6 %, 40.4 %, 42.6 %, 49.1 %), where the survey records a rise from 18 % to 77 %. In parallel, the walking share was underestimated by 44.7 points on trips under 1 km, and overestimated by 8.5 points beyond 10 km. The meta-optimiser injects no direct instruction about distance; it introduces a behavioural rule built on the cost of engaging a vehicle: getting a motorised vehicle under way (unlocking, leaving the parking space, access manoeuvres) imposes an irreducible temporal and cognitive friction, which lowers its relevance for short trips while preserving its advantage over long distances.

<!-- source: docs/arch/prompt_calibration.md § 2.9, axis "echelle" and lever cout_fixe_vehicule -->

### 5.3.3 Complexity, and the trade-off against evolutionary algorithms

Classical evolutionary optimisation of prompts (*EvoPrompt*, Guo et al., 2023) generates populations of variants evaluated by crossover and stochastic selection. Effective as this approach has proved on single-item text classification, applying it to multi-agent simulation runs into a computational scaling barrier.

In a multi-agent model, fitness is not evaluated on an isolated sample but on the emergence of a macroscopic distribution across a whole cohort of agents. For a population of 10 prompts evaluated over 10 generations on 800 personas, the protocol requires $10 \times 10 \times 800 = 80\,000$ agent inferences. That computational cost makes blind evolutionary exploration disproportionate to the marginal gains expected. Choosing a reflective search guided by the residual matrix lifts the constraint by concentrating exploration on causally justified mutations.

### 5.3.4 The four admissibility guard-rails

Four methodological constraints ensure that calibration does not degenerate into artificial memorisation of the survey statistics:

1. Rule 1: numerical thresholds are forbidden ($\mathcal{C}_{\text{qualitative}}$). The meta-optimiser may not insert numerical values, distance bounds or quantitative targets ("prefer walking under 1.5 km", "aim for 55 % car choice"). An automatic syntactic analyser removes, before evaluation, any candidate that breaks this rule. The prompt handles only qualitative arbitration notions: access friction, cumulative physical fatigue, exposure to bad weather, strict schedule constraints.
2. Rule 2: strict separation of populations. The personas used to drive the calibration come from a training pool entirely disjoint from the sealed cohort of chapter 4 ($\mathcal{D}_{\text{train}} \cap \mathcal{D}_{\text{sealed}} = \emptyset$). The search rests on a fast screening partition (about 20 % of the training data) and a validation partition for early stopping. The evaluation reported in chapter 6 therefore measures out-of-sample generalisation.
3. Rule 3: measurement on continuous verbalised distributions. On a cohort of 800 people, a discrete stochastic draw induces a sampling variance of $\pm 1.7$ points on the modal shares for one and the same prompt. To remove that noise, the calibration score is computed directly on the continuous probability vectors verbalised by the model. This ensures that a mutation is accepted only on a demonstrated structural gain.
4. Rule 4: Tabu memory, credit assignment and compaction. A Tabu memory records the semantics of mutations already rejected, so that redundant exploration is avoided. A modular decomposition into independent reasoning blocks, evaluated by leave-one-out ablation ($N-1$) or Shapley values, quantifies the marginal impact of each directive. A final compaction pass removes the blocks whose contribution does not reach the statistical non-inferiority threshold, which bounds the length of the final prompt.

The meta-optimiser is further bound by the predicate $\mathcal{C}_{\text{agnostic}}$: it may not name the sociological labels of the survey (professional categories, age bands or target municipalities). The prompt must state its heuristics as universal principles, transposable to other territories.

### 5.3.5 Status of the variants, and the sealing of the evaluation

One variant out of this process is the reference expert prompt: the one whose optimisation was carried out without ever exposing the meta-optimiser to the sealed cohort, and whose justification instruction carries no modal *a priori*. Exploratory variants tuned directly on the residuals of the sealed cohort are isolated methodologically and published under the status of an in-sample fitting upper bound, which makes the cost of out-of-sample generalisation visible.

<!-- source: ticket 080 § 3.4, revised 2026-09-17 — prompt_expert_05 = Level 2, promoted that day; prompt_expert_04, which held that status, was deleted from the repository at the author's request and can no longer be served; prompt_expert_06/07/08 = tuned in sight of the cohort, published separately -->

The system instruction is the only thing that separates this condition from the minimal prompt. The block of facts submitted to the model (persona, computed itinerary offer, agenda for the day, weather context) is produced by the same chain and laid out in the same form as in § 5.1, and the expected answer follows the same JSON schema. The text of the reference variant, the sole element that changes, reads:

> *Select the optimal travel mode taking the persona into account.*
>
> *Situational trade-off principles:*
>
> - *Chain friction: Reconstruct the real door-to-door duration (access walk, waiting, in-vehicle trip, egress). If the access walk accounts for most of the direct trip in exchange for a few minutes on board, the traveller prefers the simplicity of walking straight there, with no interchange and no waiting.*
> - *Autonomy of older people: For elderly or frail people, a continuous, unhurried walk at one's own pace is the natural mode of independence for short distances, against the strain and stress of public transport (jolting, risk of falling, steps to climb, standing while waiting with no bench).*
> - *Carrying logistics: Take into account the physical constraint of loads (shopping, heavy bags, carrier bags). Carrying loads on public transport is off-putting; the trade-off leans towards direct access with no interchange (an immediate neighbourhood walk, or the boot of a private vehicle).*
> - *Working people's life time: For a working person facing a tightly scheduled day, the time taken away from personal life has critical value. Faced with public transport links that significantly increase the duration or impose multiple interchanges, the traveller prefers the efficiency and schedule control of their available vehicle.*
>
> *[Output instructions]*
>
> 1. *Analyse the profile through these principles.*
> 2. *Do not rule out any option: assign to EACH proposed option, by its index, the probability in % that this persona picks it — the higher the better it suits them, 0 if it is impossible for them. The sum must be exactly 100.*
> 3. *Return only a valid JSON object — no markdown, no extra text.*
> 4. *Justify the distribution in one concise sentence.*

<!-- source: packages/mobility_llm/src/mobility_llm/prompts/prompts.yaml, variant prompt_expert_05 (277 words, "expert" family, neutrality audit passed on 2026-09-14, text sha256 5f55688f9cb3ba3e1e6c6f96549a339858ac72b110d9bdc7d14651c216b53ef4); the expected JSON schema follows the instruction and is reproduced in the appendix -->

Four arbitration principles are added to the output instructions of § 5.1, which the variant repeats verbatim apart from the reference to those principles in the first one. None carries a numerical value, a distance bound or a modal-share target (rule 1), and none names a professional category, an age band or a municipality of the survey (the agnosticism predicate): chain friction, the continuous unhurried walk of an older person, the burden of carried loads and the value of personal time for a tightly scheduled working person are stated as transposable mechanisms. The gap with the minimal prompt rests on these four directives alone; the task and the answer format are unchanged.

## 5.4 The two ends of the scale: floors and tabular references

Reading a distributional gap requires the model to be placed between two methodological bounds: the level reached with no behavioural knowledge, and the level reached by models trained on the real answers.

The floor characterises the performance of deciders that hold no behavioural or sociological information:

- Uniform random draw: probability spread equally over all the options computed for the trip ($1 / |\mathcal{O}_i|$).
- Empirical prior (zero-rule): all the probability given systematically to the globally majority mode of the territory (the private car).
- Shortest-duration physical heuristic: deterministic selection of the itinerary with the lowest travel time on the transport graphs.

The ceiling is the performance of the four supervised tabular models presented in § 4.4 (multinomial logit, gradient boosting, random forest, kernel logistic regression). These models hold the 21 variables of the contract and were trained on 39,203 real survey trips, of which the agent has read no record. Since no tabular method dominates on all three metrics at once (global shares, composite L1, composite EMD–JSD), the ceiling is defined by the Pareto frontier of the best scores these models reach on each axis.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ LEVEL 0: STATISTICAL FLOORS & PHYSICAL HEURISTICS                           │
│ • Uniform random draw ──► zero information.                                 │
│ • Empirical prior (zero-rule) ──► always predicts the car.                  │
│ • Shortest-duration heuristic ──► min(OTP duration).                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ LEVEL 1: MINIMAL AND CIRCUMSTANTIAL PROMPT (no prompt engineering)          │
│ • Full persona + OTP/OSM itinerary options + neutral instruction.           │
├─────────────────────────────────────────────────────────────────────────────┤
│ LEVEL 2: EXPERT PROMPT (reflective optimisation under guard-rails)          │
│ • Contextual arbitration instructions, with no numerical threshold.         │
├─────────────────────────────────────────────────────────────────────────────┤
│ LEVEL 3: TABULAR REFERENCES FITTED ON THE SURVEY                            │
│ • Multinomial logit, LightGBM, random forest, kernel logistic               │
│   regression: all under the chain constraint, like the agents.              │
└─────────────────────────────────────────────────────────────────────────────┘
```

In keeping with the separation between protocol and results, the numerical scores of the floors and the ceiling are not presented in this chapter: they are consolidated in the comparative table of chapter 6. Two methodological landmarks nonetheless frame the exercise: the gap between the floors and the ceiling spans an order of magnitude (the floors showing divergences seven to fourteen times higher than the supervised models), and another cohort of 1,000 personas built the same way would move a decider's composite by $\pm 1.3$ points (95 % CI, cluster resampling at the person level).

The two scales of evaluation are dual. The composite scores summarise aggregate distributions computed on a representative synthetic cohort. That cohort has no declared individual ground truth, however, so measuring disaggregate accuracy requires a protocol of its own, developed in § 5.5.

<!-- accuracy landmarks on the survey test partition (13,045 trips, split by household, calibration weights): "always the car" prior 57.1 %, multinomial logit 76.6 %, random forest 77.6 %, kernel logistic regression 78.4 %, gradient boosting 78.5 %. Sources: scripts/progedo_logit/{mode_choice_policy,klr_model,rf_mode_choice,mnl_model}_metrics.json, test.accuracy_weighted; the prior's accuracy equals the observed car share. These figures do NOT come from the scores.json of the v6 campaign, which carry no accuracy. They are not commensurable with the composites: different sets, different supports. -->

## 5.5 The ground-parity audit: tuning the agent where the truth exists

Evaluating the local mode-choice policy cannot stop at macro-distributional fidelity on a synthetic population: it has to be completed by a decision-by-decision audit against verifiable real choices.

This ground-parity audit protocol uses the sealed test partition of the household travel survey (13,045 real trips), on which the tabular models are formally validated. For each observed trip, the multimodal itinerary offer is rebuilt by the same engines as the simulation (road shortest path and OpenTripPlanner on the reference timetables), from the centroids of the origin and destination zones and the documented departure time.

Every decider is then submitted to that same offer: the agent under the minimal prompt, the agent under the expert prompt, the four supervised tabular models (renormalised over the offer under rule 3 of the contract) and the empirical prior. This unit confrontation yields the disaggregate classification metrics announced in § 4.2: weighted overall accuracy, cross-entropy (LogLoss), multi-class confusion matrices, precision and recall per transport mode.

Two limits inherent to historical reconstruction must be stated:

1. Origin and destination are centroids of fine-grained zones rather than exact geolocated addresses; the computed offer therefore reflects the representative trip of the zone.
2. The effective agenda of the day as lived by the respondent is only partly available, so the environmental conditions are drawn within the survey's observation window.

This audit evaluates the models on the very data substrate that served to train the supervised references. Reading the disagreement matrices by purpose or by distance class isolates the reasoning failures of the unit agent and guides the qualitative adjustments of the prompt, which completes the macroscopic analysis with a check of individual coherence. The methodological detail and the thresholds of this audit are documented in [ticket 058](../../../tickets/ticket_058_perimetre_et_methode_audit_unitaire.md).

---

### Tickets attached to this chapter
- [Ticket 080](../../../tickets/ticket_080_idee_directrice_du_chapitre_6_et_impact_sur_le_papier.md) — Restructuring of chapters 5 and 6, absorption of 4.5
- [Ticket 055](../../../tickets/ticket_055_benchmark_multimodeles_et_variabilite.md) — Multi-model benchmark and between-seed variability
- [Ticket 004](../../../tickets/ticket_004_prompt_calibration_industrialisation.md) — Industrialisation of prompt calibration
- [Ticket 054](../../../tickets/ticket_054_sobriete_computationnelle_prompt_calibration.md) — Computational sobriety of the calibration
- [Ticket 058](../../../tickets/ticket_058_perimetre_et_methode_audit_unitaire.md) — Perimeter and method of the unit audit (§ 5.5)
