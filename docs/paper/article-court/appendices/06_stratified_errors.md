# 6. Stratified Error Breakdown, Modal Profiles, and Tuning-Induced Regressions

This chapter provides comprehensive error breakdowns across all evaluated decision-makers. We examine performance across urban dimensions, present pairwise decision concordance, and identify sub-populations where prompt engineering degrades accuracy.

## 6.1 Dimension-Wise Weighted Error

We compute the mean stratum $L_1$ error weighted by the population size of covered strata. Five dimensions enter the composite score: distance band, trip purpose, age bracket, occupation category, and gender. Two additional dimensions, residential ring and housing type, enter neither the composite loss nor the calibration cycle.

Table 6.1 details the weighted $L_1$ errors across all deciders. Distance is the only dimension where an LLM agent achieves the lowest error across all benchmarked methods.

*Table 6.1. Weighted $L_1$ error (in %) across urban dimensions and decision-makers.*

| Decision-maker | Distance | Purpose | Age | Occupation | Gender | Ring | Housing |
|---|---:|---:|---:|---:|---:|---:|---:|
| `gemini-3.5`, minimal | 24.1 | 27.9 | 30.6 | 25.3 | 23.9 | 25.7 | 30.5 |
| `gemini-3.5`, expert | **14.2** | 21.4 | 22.1 | 18.5 | 13.6 | 19.6 | 23.6 |
| `gemini-3.1`, minimal | 38.0 | 37.8 | 43.9 | 39.2 | 39.4 | 40.5 | 43.1 |
| `gemini-3.1`, expert | 30.2 | 30.8 | 35.8 | 31.2 | 30.7 | 33.0 | 37.4 |
| `mistral-large`, minimal | 51.9 | 39.3 | 46.8 | 43.8 | 44.5 | 47.6 | 51.0 |
| `mistral-large`, expert | 33.7 | 27.9 | 30.4 | 28.6 | 25.3 | 29.6 | 33.0 |
| Gradient boosting (LightGBM) | 17.8 | **13.6** | 18.2 | 15.7 | 8.5 | 11.5 | 16.6 |
| Random forest | 16.8 | 18.1 | **16.8** | **12.9** | **5.3** | **9.5** | **15.9** |
| Kernel logistic regression | 18.1 | 14.2 | 18.9 | 15.1 | 8.1 | 11.8 | 17.0 |
| Multinomial logit | 19.5 | 16.4 | 21.2 | 17.8 | 10.4 | 13.2 | 19.4 |

## 6.2 Global Modal Share Distributions

Table 6.2 compares predicted modal shares against the empirical Cerema survey ground truth. Every decider underestimates car usage because vehicle chaining constraints enforce strict feasibility checks.

Language models overestimate cycling by a factor of two across all weighted strata. Conversely, supervised tabular models systematically underestimate cycling shares.

*Table 6.2. Global modal split percentages across models against the survey.*

| Model | Car (%) | Walking (%) | Transit (%) | Cycling (%) |
|---|---:|---:|---:|---:|
| Cerema EMC² 2023 survey | 56.7 | 26.8 | 12.4 | 4.1 |
| Minimal prompt, `gemini-3.5` | 47.4 | 24.0 | 20.9 | 7.6 |
| Expert prompt, `gemini-3.5` | 52.3 | 24.2 | 16.6 | 6.8 |
| Minimal prompt, `gemini-3.1` | 44.1 | 19.5 | 28.8 | 7.7 |
| Expert prompt, `gemini-3.1` | 46.2 | 21.7 | 24.8 | 7.4 |
| Minimal prompt, `mistral-large` | 36.7 | 24.4 | 30.6 | 8.2 |
| Expert prompt, `mistral-large` | 43.4 | 29.3 | 19.2 | 8.1 |
| Gradient boosting (LightGBM) | 52.8 | 29.1 | 14.8 | 3.3 |
| Random forest | 56.2 | 27.6 | 14.2 | 2.0 |
| Kernel logistic regression | 54.4 | 28.9 | 13.6 | 3.0 |
| Multinomial logit | 53.3 | 27.2 | 16.4 | 3.0 |

## 6.3 Visualizations of Multi-Dimensional Error Profiles

We provide four multi-panel visual figures examining stratified modal behavior.

Figure 6.1 displays car shares across six dimensions (`images/ch99_dimensions_voiture.png`). On the first four dimensions, the expert prompt sits substantially closer to the target than the minimal baseline. On residential ring and housing type, both LLM series remain distant from empirical targets.

Figure 6.2 breaks down the four transport modes by distance band (`images/ch99_modes_distance.png`). Car and walking predictions closely track ground truth beyond one kilometer. Public transit displays persistent overestimation between two and twenty kilometers.

Figure 6.3 examines modal distributions across eight occupation categories (`images/ch99_modes_occupation.png`). School-age categories (pupils and students) exhibit the highest cycling shares: 8.2% and 13.3% under the expert prompt versus 4.2% and 4.0% in the survey.

Figure 6.4 plots the four modes across six trip purposes (`images/ch99_modes_motif.png`). Educational trips produce the largest divergence following prompt engineering, shifting heavily toward private vehicles.

## 6.4 Strata Degraded by Expert Prompt Tuning

Prompt engineering does not improve performance across all demographic segments. Table 6.3 identifies sub-populations where the expert prompt degraded accuracy relative to the uncalibrated baseline.

*Table 6.3. Stratum $L_1$ errors (%) degraded after expert prompt engineering.*

| Stratum and evaluated model | Minimal prompt error (%) | Expert prompt error (%) | Net degradation |
|---|---:|---:|---:|
| Education purpose, `gemini-3.5` ($n = 218$) | 28.0 | 33.5 | $+5.5$ pt |
| Education purpose, `gemini-3.1` ($n = 218$) | 20.0 | 21.2 | $+1.2$ pt |
| Education purpose, `mistral-large` ($n = 218$) | 8.7 | 22.3 | $+13.6$ pt |
| Adolescents aged 15–19, `gemini-3.5` ($n = 61$) | 53.4 | 58.3 | $+4.9$ pt |
| Adolescents aged 15–19, `gemini-3.1` ($n = 61$) | 49.2 | 47.9 | $-1.3$ pt |
| Adolescents aged 15–19, `mistral-large` ($n = 61$) | 34.1 | 44.9 | $+10.8$ pt |
| Trips $> 50$ km, `gemini-3.5` ($n = 19$) | 42.1 | 51.4 | $+9.3$ pt |

The degradation on educational trips appears across all three language models. The prompt emphasizes travel speed and vehicle utility, inadvertently prompting students who lack private vehicles to select cars. Trips exceeding 50 kilometers similarly resist calibration across all deciders.

## 6.5 Decision-by-Decision Concordance Between Deciders

We evaluate agreement across 2,374 to 2,479 trips where at least two alternatives were available. Table 6.4 summarizes concordance between model pairs.

Tabular models display high mutual agreement, exceeding 88% on drawn choices. Conversely, LLMs diverge sharply from tabular references, exhibiting median $L_1$ distances near 40 percentage points.

*Table 6.4. Pairwise concordance across common trips with multiple available alternatives.*

| Model comparison pair | Concordance on most likely mode (%) | Concordance on drawn mode (%) | Median $L_1$ distance between distributions |
|---|---:|---:|---:|
| Gradient boosting / Kernel regression | 91.6 | 90.5 | 8.3 |
| Gradient boosting / Random forest | 89.0 | 88.3 | 11.3 |
| Expert `gemini-3.5` / Gradient boosting | 69.7 | 61.4 | 39.0 |
| Expert `gemini-3.5` / Random forest | 71.4 | 60.4 | 42.6 |
| Expert `gemini-3.5` / Expert `gemini-3.1` | 79.6 | 72.8 | 40.0 |
| Expert `gemini-3.1` / Expert `mistral-large` | 72.6 | 70.6 | 40.0 |

## 6.6 Non-Convex Optimization and Prompt Engineering Trajectory

We tracked iterative prompt modifications evaluated on `gemini-3.5-flash-lite`. Table 6.5 documents the resulting composite scores.

Variants tailored directly to sample residuals (`prompt_expert_06` and `08`) degraded aggregate performance. In contrast, `prompt_expert_05` retained general cognitive principles, achieving superior generalization. This pattern highlights the non-convex optimization surface characteristic of natural language prompts.

*Table 6.5. Evaluation metrics across prompt engineering iterations on `gemini-3.5-flash-lite`.*

| Prompt variant | Engineering status | Composite score | Excl. special conditions | Macro $L_1$ error (%) |
|---|---|---:|---:|---:|
| `prompt_minimal_02` | Baseline without engineering | 7.02 | 10.39 | 24.08 |
| `prompt_expert_05` | General cognitive ablation | 4.86 | 6.86 | 13.85 |
| `prompt_expert_06` | Tuned on cohort residuals | 5.33 | 7.24 | 15.39 |
| `prompt_expert_08` | Heavily tuned on residuals | 6.58 | 10.32 | 21.74 |

---
