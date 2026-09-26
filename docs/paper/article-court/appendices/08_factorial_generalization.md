# 8. Factorial Out-of-Sample Generalization and Between-Seed Robustness

This chapter evaluates out-of-sample prompt generalization and between-seed stochastic dispersion. We specify the factorial experimental design crossing models and instructions on independent cohorts, define pre-registered acceptance scenarios, and document Monte Carlo stability.

## 8.1 The $2 \times 3$ Factorial Architecture Matrix

To verify that expert prompt performance avoids in-sample overfitting, we evaluate a $2 \times 3$ factorial design. The design crosses two distinct architectures with three instruction levels.

The two architectures comprise the generative multi-token model (`gemini-3.5-flash-lite`) and the typed constrained classifier (`jev-1.13.0`). The three prompt levels include the unengineered baseline (`prompt_minimal_02`), the cognitive ablation prompt (`prompt_expert_05`), and the classifier prompt (`prompt_expert_32`).

We maintain strict cohort separation between calibration and evaluation. The calibration cohort $c_2$ (`population_1000_AAMAS_v6_c2`) serves exclusively for prompt development. The evaluation cohort $c_1$ (`population_1000_AAMAS_v6`) remains sealed, containing zero overlapping personas with $c_2$.

Table 8.1 documents composite metric scores measured out of sample.

*Table 8.1. Factorial out-of-sample composite scores ($c_2 \rightarrow c_1$).*

| Architecture | Minimal prompt (`02`) | Expert LLM (`05`) | Expert classifier (`32`) |
|---|---:|---:|---:|
| Generative LLM (`gemini-3.5`) | 7.02 | 4.86 | 5.33 |
| Typed classifier (`jev-1.13.0`) | 13.75 | 4.12 | **3.65** |

Under `prompt_expert_32`, the typed classifier attains an out-of-sample composite score of 3.65 on sealed cohort $c_1$. The resulting score of 3.65 places the model inside the reference tabular band ($[3.60, 4.09]$).

## 8.2 Pre-Registered Acceptance Scenarios for Ticket 103

Before measuring calibration transfers, we pre-registered three formal acceptance scenarios governing empirical outcomes.

**Scenario 1 (Full Parity).** The out-of-sample score of `jev-1.13.0` falls within the tabular benchmark band. Furthermore, cluster bootstrap intervals include zero against at least two tabular baselines. Under this outcome, the typed classifier achieves empirical parity with supervised machine learning.

**Scenario 2 (Upper Bound).** The out-of-sample score lands within 1.3 points above the tabular envelope. The classifier establishes a rigorous non-deliberative upper bound, verifying that discursive reasoning does not enhance predictive fit.

**Scenario 3 (Sample Rejection).** The out-of-sample score exceeds the tabular envelope by more than 1.3 points. This outcome refutes generalization, identifying earlier in-sample fits as sample-specific artefacts.

Evaluating both models under identical prompts reveals whether performance gains stem from the prompt text or from architectural constraints.

## 8.3 Between-Seed Stochastic Robustness

We evaluate stochastic stability across three independent random seeds: 42, 123, and 789. Each seed controls itinerary alternative ordering, weather realizations, and multinomial choice sampling simultaneously.

Across the three seeds on cohort $c_1$, the composite score of `gemini-3.5` under `prompt_expert_05` ranges across 4.86, 4.65, and 4.30. This yields an empirical range of 0.56 points.

Because this variation remains well below the cohort resolution limit of $\pm 1.3$ points, seed dispersion does not alter model rankings. The typed classifier demonstrates strict deterministic replication when configured with zero temperature.

## 8.4 Pending Empirical Replays and Execution Status

The full factorial grid requires completing all execution phases across both cohorts.

**Pending Campaign Execution (Ticket 103 Lots A and B).** Complete replication of Lot A on calibration cohort $c_2$ and Lot B multi-seed replays on $c_1$ are scheduled for final execution. Table 8.1 will incorporate the finalized bootstrap confidence intervals upon campaign completion.

---
