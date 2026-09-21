# 5. A protocol for calibrating mode choice

<!-- Dernière mise à jour : 2026-09-21 -->

**Document:** chapter 5 of the AAMAS 2027 paper — the **protocol** chapter: it defines the conditions being compared, and chapter 6 says what the comparison establishes. English master; French mirror in [`fr/05_factual_neutral_prompt.md`](../fr/05_factual_neutral_prompt.md); LaTeX rendering for Overleaf in [`overleaf/05_factual_neutral_prompt.tex`](../overleaf/05_factual_neutral_prompt.tex).
**Status:** `draft v0.11` (21 September 2026) — author's review, eight points. The § 5.2 on the multi-model benchmark is dissolved: the list of models and its table move up into the chapter head, and the following sections move up one rank. The mathematical formulation of § 5.2.1 is reduced to one sentence and one formula. § 5.2.2 states the procedure actually followed — successive mutations of a single prompt, tested on the cases meant to switch and then on a paired replay — and its illustration changes: the distance elasticity of the `ref1` champion is removed, that diagnosis holding neither for the minimal prompt (whose car share runs from 9.7 to 74.9 %) nor for the published expert prompt; the drift of retired people, measured and traced, replaces it. The guard-rails go from four to three and **stop asserting a disjoint training pool**: the gaps that drive the mutations were read on the sealed cohort, and the chapter 6 scores are stated as in-sample. § 5.2.4 adds that the expert prompt holds for the model it was tuned against. § 5.4 loses its justifying opening sentence and the detail of the reconstruction engines. No reference to a ticket remains in the body text. Third pass the same day: the headings go back under rule 1 of the README, the § 5.2.4 is merged into § 5.2.3, the opening paragraph of § 5.2.1 is rewritten by the author, and the gloss of the formula and the retired-people illustration leave the body text.
**Previous status:** `draft v0.10` (17 September 2026) — the title becomes descriptive: “Four ways of choosing, one set of facts” announced an equality of information that the contract of § 4.3 does not establish, since it equalises the 21 variables and not the information each decider holds. § 5.3.5 now publishes the full text of the reference expert prompt (`prompt_expert_05`), as § 5.1 publishes that of the minimal prompt.
**Previous status:** `draft v0.9` (17 September 2026) — first English master, translated from the French `brouillon v0.9` of 16 September 2026. The French carries the version history; it is not repeated here.
**Place in the paper:** section 5 of the plan announced in § 1.4 of [`../en/01_introduction.md`](../en/01_introduction.md). Outline: [`../plan/PLAN.md`](../plan/PLAN.md). Progress: [`../README.md`](../README.md).
**Convention:** a figure **in bold brackets** is an empty placeholder.

---

This chapter tunes the local decision policy of the agent before deploying it in the simulator. The tuning bears on an isolated choice: one precise trip, characterised by a sociological profile, a computed multimodal offer and weather conditions, with no dynamic history of the day already elapsed. The four levels of § 1.3 are compared there on equal inputs, under the comparison protocol of § 4.3.

The two language-model conditions are measured on `gemini-3.1-flash-lite`, `gemini-3.5-flash-lite` and `mistral-large-2512`, with the same test set, the same agent contexts and the same randomisation of the option order.

<!-- sources: data/experiences/exp_{gemini-31-fl,gemini-35-fl,mistral-l-25}_{promin02,proexp05,proexp06,proexp08}_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_t0_nosim, replay on the corrected set, runs of 2026-09-16 and 2026-09-17. The gemini-3.5-flash-lite decider under the minimal prompt, carried as [xx] until 2026-09-20, is measured: composite EMD–JSD 7.024, run 2026-09-16_19_05_45; chapter 6 publishes it. The deciders agy-claude-o-5, agy-claude-o-4-6 and agy-gemini-38-f are declared with no score. -->

## 5.1 The minimal prompt

The base condition evaluates generic foundation models, used off the shelf with no prompt engineering, against a minimal and circumstantial prompt.

The observation submitted to the model is the one of § 3.3: the sociological profile, the offer of viable itineraries with the detail of their legs, the agenda of the remaining activities and the weather context.

The system instruction is limited to the definition of the task and the output format of the decision:

> *Select the optimal travel mode taking the persona into account.*
>
> *[Output instructions]*
>
> 1. *Analyse the profile.*
> 2. *Do not rule out any option: assign to EACH proposed option, by its index, the probability in % that this persona picks it — the higher the better it suits them, 0 if it is impossible for them. The sum must be exactly 100.*
> 3. *Return only a valid JSON object — no markdown, no extra text.*
> 4. *Justify the distribution in one concise sentence.*

<!-- source: packages/mobility_llm/src/mobility_llm/prompts/prompts.yaml, variant prompt_minimal_02 (82 words, "minimal" family, neutrality audit passed on 2026-09-14); the expected JSON schema follows the instruction and is reproduced in the appendix -->

One inference case gives the structure of the signal the model receives:

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

Response returned by the model:

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

<!-- source: block received and response — data/experiences/exp_gemini-35-fl_proexp04_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_t0_nosim/executions/2026-09-15_05_18_34/decisions.jsonl, person_id 1320713.
⚠ CASE TO BE REDONE BEFORE PUBLICATION, in full. (1) The departure of this trip resolves to 17 March: it is one of the 866 cases that ticket 088 dated to the following day, so its itinerary offer was computed for the wrong day. (2) The quoted response comes from the decider under the expert prompt, level 1 having no score on v6. Both the received block AND the response are to be redone from a prompt_minimal_02 decider replayed on the corrected set (ticket 088 § 3.4). -->

The model receives five options for a two-kilometre trip, among them two walking routes and one combination of walking and metro. With no directive on the effort of walking, the value of time or the effect of the weather, it spreads its probability mass over the options. It is that distribution which is scored under the protocol of § 4.3.

## 5.2 The expert prompt

The minimal prompt produces systematic gaps to the survey, and those gaps concentrate on identifiable strata. The system prompt is tuned by iterations to reduce them, under the composite loss of § 4.2.

### 5.2.1 Per-stratum loss

The prompt defines the local policy of the agent: for each perceived state, it assigns a probability distribution over the available transport modes. For a stratum (age band, trip purpose, socio-professional category, place of residence or distance class), the share of each mode generated by the prompt is the mean of the probabilities it assigns to the trips of that stratum. The survey supplies the reference value for each stratum. Calibrating means finding the text that minimises the gap between the probabilities the prompt produces and those reference values, stratum by stratum:

$$\min_p \sum_k w_k D_k(\hat{P}_k(p), P^*_k)$$

<!-- D_k: Jensen–Shannon divergence on nominal strata, optimal transport distance on ordered strata; weights w_k of § 4.2. -->

### 5.2.2 Prompt engineering

The space of texts is discrete and non-differentiable. An evolutionary optimisation of prompts (*EvoPrompt*, Guo et al., 2023) would evaluate populations of variants by crossover and selection, but fitness is not measured here on an isolated sample: it is measured on the distribution produced by a whole cohort, and ten prompts over ten generations on 800 personas require 80,000 inferences. The tuning therefore proceeds by successive mutations of a single prompt, in the line of model-assisted reflective approaches (Shinn et al., 2023; Yuksekgonul et al., 2024).

Each iteration starts from the per-stratum gaps produced by the prompt in service. A language model reads those gaps and the justifications the agent wrote with its decisions, states a hypothesis about the reasoning mechanism that produces the gap, and proposes a targeted textual mutation. The mutation is played first on some twenty trips chosen to be those the hypothesis says should switch, then on a larger stratified sample, replayed identically against a control arm carrying the unchanged prompt. It is retained if the over-represented mode recedes without another gap widening; otherwise it is rejected, and the reason for the rejection is recorded with it.

<!-- source: docs/traces/2026-09-08_16-05_prompt_expcha_derives_m5/README.md §§ 1 to 3 — run exp_gemini-35-fl_expcha_jtir_t0_nosim of 2026-09-08, 2,639 trips; paired replay of 200 stratified decisions in 25 batches of 8, six arms, user text identical to the byte (fingerprint 6a4866b8673c); retired people L1 69.9 (control) → 62.9 (M1bis+M2+M3+M4+M5); M1 and M6 rejected. Procedure: .agents/skills/optimiser-prompt-experience/SKILL.md, lines 30 to 124 (per-stratum deltas, 20 target cases per mutation, retention criterion). -->

### 5.2.3 Admissibility guard-rails and the prompt retained

Three constraints frame the tuning.

1. **No numerical threshold.** The prompt may carry no numerical value, no distance bound and no quantitative target ("favour walking under 1.5 km", "aim for 55 % car choices"). A syntactic analyser discards, before evaluation, any candidate carrying one. The text handles only qualitative arbitration notions: access friction, accumulated physical fatigue, exposure to the weather, schedule constraints.
2. **No label of the survey.** The prompt names no professional category, no age band and no target municipality. It states its heuristics as principles transposable to another territory.
3. **Measurement on verbalised distributions.** On a cohort of this size, a stochastic draw spreads each modal share by $\pm 1.7$ points for one and the same prompt. The calibration score is therefore computed on the continuous probability vectors, not on drawn modes.

The gaps that drive the mutations were read on the sealed cohort of chapter 4 itself, for most of the retained mutations. The expert-prompt scores reported in chapter 6 are therefore in-sample scores, not an out-of-sample generalisation performance.

<!-- source: docs/tickets/ticket_080_idee_directrice_du_chapitre_6_et_impact_sur_le_papier.md §§ 0.6 and 3.4 — prompt_expert_06/07/08 "edited in view of the scores of the sealed v5 cohort"; prompt_expert_05 = ablation of the anti-walking clause, measured on the v5 cohort on 2026-09-13 (5.79 against 6.16) before retention, therefore informed by the cohort. The only prompt prior to the first run on the cohort, prompt_expert_04, was deleted from the repository on 2026-09-17. The disjoint 50/20/30 pool (train 430, val 178, test 259, docs/arch/prompt_calibration.md § 3.2) belongs to the prompt_calibration module and did not serve the published variants. ±1.7 points: docs/arch/prompt_calibration.md line 75. -->

An expert prompt holds for the model it was tuned against. The per-stratum gaps differ from one model to the next, and a mutation retained on one is not retained by right on another.

<!-- source: ticket 080 § 3.4, revised 2026-09-17 — prompt_expert_05 = level 2, promoted that day; prompt_expert_04, which held that status, was deleted from the repository at the author's request and is no longer servable; prompt_expert_06/07/08 = tuned in sight of the cohort, published separately. Model tuned against: prompts.yaml, _provenance of prompt_expert_05, drifts measured on exp_gemini-35-fl_expgem38v2_…_v5. -->

Only the system instruction distinguishes this condition from the minimal prompt. The block of facts, the chain that produces it and the expected JSON schema are those of § 5.1. The text of the expert prompt is the following:

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

<!-- source: packages/mobility_llm/src/mobility_llm/prompts/prompts.yaml, variant prompt_expert_05 (277 words, "expert" family, neutrality audit passed on 2026-09-14, sha256 of the text 5f55688f9cb3ba3e1e6c6f96549a339858ac72b110d9bdc7d14651c216b53ef4); the expected JSON schema follows the instruction and is reproduced in the appendix -->

The four principles are added to the output instructions of § 5.1, which the variant repeats identically apart from the reference to the principles in the first. None carries a numerical value or a modal-share target, and none names a category of the survey.

## 5.3 Floors and tabular references

A distribution gap is read between two bounds: the level reached with no behavioural knowledge, and the one reached by models trained on the real answers.

The floor characterises deciders that hold no behavioural information: the uniform random draw, which gives equal probability to all the options computed for the trip ($1 / |\mathcal{O}_i|$); the empirical prior, which puts all the probability on the majority mode of the territory, the private car; and the shortest-duration heuristic, which keeps the fastest itinerary on the transport graphs. The ceiling is the performance of the four tabular references of § 4.4, read axis by axis for want of a method that dominates all three.

The scores of the floors and the ceiling are consolidated in the comparative table of chapter 6. The gap between them spans an order of magnitude, the floors showing divergences seven to fourteen times higher than the supervised models.

<!-- accuracy landmarks on the survey test partition (13,045 trips, split by household, calibration weights): "always the car" prior 57.1 %, multinomial logit 76.6 %, random forest 77.6 %, kernel logistic regression 78.4 %, gradient boosting 78.5 %. Sources: scripts/progedo_logit/{mode_choice_policy,klr_model,rf_mode_choice,mnl_model}_metrics.json, test.accuracy_weighted; the prior's accuracy equals the observed car share. These figures do NOT come from the scores.json of the v6 campaign, which carry no accuracy. They are not commensurable with the composites: different sets, different supports. -->

## 5.4 The unit audit at ground parity

The audit confronts the decider, trip by trip, with the days the respondents actually described: 2,930 people and 9,621 trips, each carrying the declared mode. The itinerary offer is rebuilt by the same engines as the simulation, from the centroids of the zones and the declared departure time, with the weather bulletin of the day described.

Each decider receives that offer under the chain constraint of § 3.5: the agent under the minimal prompt, the agent under the expert prompt, the four supervised tabular models (renormalised over the offer under rule 3 of the protocol) and the empirical prior. The chain makes the offer path-dependent, since a decider who left the car at home is no longer offered it later on; the number of trips whose declared mode thereby falls out of the presented options is specific to each decider. This unit confrontation yields the disaggregate classification metrics announced in § 4.2: weighted overall accuracy, cross-entropy (LogLoss), multi-class confusion matrices, precision and recall per transport mode.

<!-- source: unit audit of 2026-09-19, nine deciders on the enquete_058_test_20260316 set — out-of-options counts from 947 (majvoiture) to 1,428 (minimal prompt), 1,295 for the expert prompt; shared ceiling of 86 trips for which the set itself carries no option with the declared mode; trips internal to a single fine-grained zone set aside, a quarter of the total, their distance not being measurable between two coincident centroids; the effective agenda of the day as lived is known only through the declared trips. Detail and thresholds: docs/tickets/ticket_058_perimetre_et_methode_audit_unitaire.md -->

This audit evaluates the models on the very data substrate that served to train the supervised references.

---

### Tickets attached to this chapter
- [Ticket 080](../../../tickets/ticket_080_idee_directrice_du_chapitre_6_et_impact_sur_le_papier.md) — Restructuring of chapters 5 and 6, absorption of 4.5
- [Ticket 055](../../../tickets/ticket_055_benchmark_multimodeles_et_variabilite.md) — Multi-model benchmark and between-seed variability
- [Ticket 004](../../../tickets/ticket_004_prompt_calibration_industrialisation.md) — Industrialisation of prompt calibration
- [Ticket 054](../../../tickets/ticket_054_sobriete_computationnelle_prompt_calibration.md) — Computational sobriety of the calibration
- [Ticket 058](../../../tickets/ticket_058_perimetre_et_methode_audit_unitaire.md) — Perimeter and method of the unit audit (§ 5.4)
