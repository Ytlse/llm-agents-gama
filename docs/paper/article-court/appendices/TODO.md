# Master TODO List — AAMAS 2027 Supplementary Appendices Volume

This document tracks all missing empirical datasets, pending simulation campaigns, visual assets, and reviewer checklist items required to finalize the AAMAS 2027 supplementary material volume (`docs/paper/article-court/appendices/`).

---

## 1. Pending Empirical Simulations and Machine Execution

### 1.1 Ticket 103: Factorial Square and Out-of-Sample Validation
- [ ] **Lot A Execution on Calibration Cohort $c_2$ (`population_1000_AAMAS_v6_c2`):**
  - Run deterministic baselines (A7–A13: MNL, LightGBM, KLR, Random Forest, Uniform Random, All-Car, Shortest Duration) to establish the empirical performance envelope of cohort $c_2$.
  - Run LLM generative agents (A1: `gemini-3.5-flash-lite` $\times$ `prompt_minimal_02`, A2: `gemini-3.5-flash-lite` $\times$ `prompt_expert_05`, A3: `gemini-3.5-flash-lite` $\times$ `prompt_expert_32`).
  - Run typed classifier agents (A4: `jev-1.13.0` $\times$ `prompt_minimal_02`, A5: `jev-1.13.0` $\times$ `prompt_expert_05`, A6: `jev-1.13.0` $\times$ `prompt_expert_32`).
  - Compute cluster bootstrap paired differences ($B = 2{,}000$ replicates, person-level resampling) across all 14 pairs on $c_2$.
  - Confirm whether outcome satisfies **Scenario 1** (full parity within $[3.60, 4.09]$ band) or **Scenario 2** (upper bound within $+1.3$ pt).
- [ ] **Lot B Execution on Sealed Cohort $c_1$ (`population_1000_AAMAS_v6`):**
  - Execute multi-seed replays on seeds 123 and 789 for key deciders:
    - B1–B2: `jev-1.13.0` $\times$ `prompt_expert_32` (seeds 123, 789).
    - B3–B4: `jev-1.13.0` $\times$ `prompt_expert_05` (seeds 123, 789).
    - B5–B6: `gemini-3.5-flash-lite` $\times$ `prompt_minimal_02` (seeds 123, 789).
  - Verify deterministic zero-variance property of `jev` under temperature $\tau = 0.0$.
  - Quantify between-seed Monte Carlo range against the $\pm 1.3$ pt cohort resolution threshold.

### 1.2 News Shock Exogenous Adaptation (`exp_05a-e` / Tickets 059, 064, 095)
- [ ] **Empirical Campaign Runs across 5 Local Events:**
  - Execute 3 experimental conditions (C1: Nominal, C2: Exposed raw text, C3: Matched natural-science placebo) for all 5 dispatches:
    - Event A09 (Severe Autan windstorm)
    - Event A13 (Transit bedbug infestation alert)
    - Event A07 (Municipal sanitation workers strike)
    - Event A18 (Downtown street parade "La Machine")
    - Event A25 (Electric shared bicycle expansion)
  - Fill the empirical 20-cell outcome table with measured modal share deltas ($\Delta \text{Car}$, $\Delta \text{Bicycle}$, $\Delta \text{Walking}$, $\Delta \text{Transit}$) and 95% bootstrap confidence intervals.
  - Calculate empirical sign agreement rate against pre-registered hypotheses in `grille_signes.yaml` (frozen 2026-09-21).
  - Measure gap between announced severity / mode affinity ratings and actual trip choices.
- [ ] **Longitudinal Memory Decay Tracking:**
  - Run multi-day simulation tracking daily propensity towards impacted modes.
  - Quantify the exact date of memory extinction: distinguish between dated trip contradiction vs temporal memory wear ($t > \tau(g)$).
  - Collect daily multi-criteria Likert ratings (safety, convenience, comfort, speed, cost, environment) across the 40-day simulation window.

---

## 2. Visual Assets and Plot Regeneration

### 2.1 Figure Upgrades and Vectorization
- [x] **Chapter 11 Cognitive Memory Suite:**
  - High-resolution `fig_memory_lifecycle.png` (300 DPI, full multi-agent pipeline).
  - High-resolution `fig_ebbinghaus_decay.png` (300 DPI, calibrated $\tau_{1/2}=1.94$ d vs Park et al. $\tau_{1/2}=5.78$ d + active recall).
  - High-resolution `fig_retrieval_components.png` (300 DPI, radar chart across routine, breakdown, and news shock profiles).
- [x] **Chapter 15 Systems Architecture Figures:**
  - Professional C4 container topology `fig_c4_container_topology.png` (300 DPI, Docker Compose 7 microservices).
  - Non-linear reactive backpressure delay curve `fig_backpressure_edf.png` (300 DPI, $k=3.7$, $\Delta t_{\max}=30$ s, and EDF freeze threshold).
- [x] **Chapter 3 Mathematical Metrics:**
  - Geometric 1D Earth Mover's Distance and finite-sample bias curve `fig_emd_jsd_explanation.png` (300 DPI).
- [x] **Chapter 9 Computational Economics:**
  - Metropolitan cost waterfall and 1:50 cost ratio bar chart `fig_metropolitan_cost_waterfall.png` (300 DPI).
- [x] **Chapter 10 Execution Language:**
  - Byte-Pair Encoding (BPE) byte fragmentation and token overhead `fig_french_english_tokenization.png` (300 DPI).
- [x] **Chapter 14 Individual Unit Audit:**
  - Dual normalized $4 \times 4$ confusion matrices `fig_confusion_matrix_audit.png` (300 DPI).
- [ ] **Figure 5.1 (News Shock Sign Grid):**
  - Overlay empirical results onto `images/ch7_grille_signes.png` once campaign `exp_05a-e` completes, highlighting confirmed vs refuted cells.
- [ ] **Figure 5.2 & 5.3 (Daily Propensity and Multi-Criteria Affinities):**
  - Re-generate `images/ch7_propension_quotidienne.png` and `images/ch7_affinites_tous_modes.png` directly from finalized simulation databases (replacing temporary `tmp_` artifacts).
- [ ] **Figures 6.1–6.4 (Stratified Error Profiles):**
  - Verify high-resolution rendering of `images/ch99_dimensions_voiture.png`, `images/ch99_modes_distance.png`, `images/ch99_modes_occupation.png`, and `images/ch99_modes_motif.png`.

---

## 3. Reviewer Checklist by Evaluator Persona

### 3.1 Profile 1: Archivist & Legacy Paper Harvester
- [x] Integrate 13 demographic margins table with Cerema EMC² 2023 survey baselines (Chapter 1).
- [x] Formalize the 21-variable contract and Lambert-93 coordinate projection rules (Chapter 2).
- [x] Provide exact mathematical formulations for EMD, JSD, and composite loss (Chapter 3).
- [x] Include verbatim prompts and full Raymond decision trace (Chapter 4).
- [x] Incorporate verbatim text for the 5 news dispatches and matched placebo (Chapter 5).
- [x] Include all stratified error tables across 6 urban dimensions and 15 deciders (Chapter 6).
- [x] Formalize multi-agent tuple, dual-clock memory, and vehicle chain pruning (Chapter 11).
- [x] Document the 12-item methodological audit log across drafts v1.3–v1.6 (Chapter 12).
- [x] Detail legal data governance agreement `lil-1750` and ADISP 5-step ordering protocol (Chapter 13).

### 3.2 Profile 2: Scientific Reviewer & Empirical Auditor
- [x] Document two one-sided equivalence testing (TOST) parameter boundaries ($\pm 2.0$ pt, $\alpha = 0.05$) across all margins (Chapter 1).
- [x] Formalize empirical proof of the $+5.02$ pt finite-sample bias on $N = 3{,}154$ (Chapter 3).
- [x] Document composite loss sensitivity analysis showing rank correlations $> 0.94$ under alternative weighting schemes (Chapter 3).
- [x] Provide complete 20 paired contrasts table with 95% cluster bootstrap intervals (Chapter 7).
- [x] Report instruction-dependent ranking reversals (`gemini-3.1` vs `mistral-large`) demonstrating model-instruction coupling (Chapter 7).
- [x] Detail prompt ablation of the post-hoc justification clause ($+0.17$ pt improvement) (Chapter 7).
- [x] Document empirical token inflation in French (+26.2%) and cross-lingual performance gaps (Chapter 10).
- [x] Provide individual-level unit audit on 9,621 declared trips: accuracy, cross-entropy, precision/recall, and target leakage autopsy (Chapter 14).
- [ ] *Pending:* Insert finalized confidence intervals for Ticket 103 factorial matrix once machine runs terminate (Chapter 8).
- [ ] *Pending:* Insert empirical values for the 20 news shock cells once `exp_05a-e` completes (Chapter 5).

### 3.3 Profile 3: Systems Architect & Replication Practitioner
- [x] Document distributed container topology across 7 microservices (Chapter 15).
- [x] Provide complete UML decision lifecycle sequence diagram (Chapter 15).
- [x] Specify reactive backpressure formula ($k=3.7, \text{cap}=30\text{ s}$) and EDF synchronization hold (Chapter 15).
- [x] Document SWRR load balancing, atomic Redis token bucket reservation, and `force_provider` integrity flag (Chapter 15).
- [x] Specify TypeSafe classifier interface, `[Output instructions]` stripping, and sum tolerance $\sum p_i \in [0.98, 1.02]$ (Chapter 15).
- [x] Provide exact vLLM local deployment commands for `Qwen2.5-32B-Instruct-AWQ` and hardware requirements (Chapter 15).
- [ ] *Recommended addition:* Append raw Redis Lua token reservation script into repository replication scripts.
- [ ] *Recommended addition:* Include example `docker-compose.yml` snippet in the online code release.

---

## 4. Compilation and Format Synchronization

- [x] All 16 Markdown chapter files created and verified via `verifier_forme.py` (**0 errors, Exit code 0**).
- [x] Root LaTeX wrapper `main.tex` configured in `\documentclass[manuscript,anonymous]{aamas}` with author blocks, ACM copyright, and chapter inclusions.
- [x] Synchronize all 16 LaTeX chapter files (`chapters/00_abstract.tex` through `chapters/15_systems_architecture.tex`) with finalized Markdown content and verified via `verifier_forme.py` (**0 errors, Exit code 0**).

- [ ] Run test compilation (`pdflatex main.tex && bibtex main && pdflatex main.tex`) to verify zero LaTeX compilation warnings or broken references.
