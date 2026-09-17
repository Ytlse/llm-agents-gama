# 6. Results

<!-- Dernière mise à jour : 2026-09-17 -->

**Document:** chapter 6 of the AAMAS 2027 paper — the **results** chapter: chapter 5 defines the conditions compared, this one says what the comparison establishes. English master; French mirror in [`fr/06_results.md`](../fr/06_results.md); LaTeX rendering for Overleaf in [`overleaf/06_results.tex`](../overleaf/06_results.tex).
**Status:** `draft v0.4` (17 September 2026) — first English master, translated from the French `brouillon v0.4` of the same day. The French carries the version history; it is not repeated here. Five sections, four figures already composed in English by `scripts/analysis/plot_chapitre6.py`; the detail tables live in appendix H.
**Place in the paper:** section 6 of the plan announced in § 1.4 of [`../en/01_introduction.md`](../en/01_introduction.md). Outline: [`../plan/PLAN.md`](../plan/PLAN.md). Progress: [`../README.md`](../README.md).
**Convention:** a figure followed by **TBC** is to be consolidated. A figure **in bold brackets** is an empty placeholder.

---

Chapter 5 described four ways of deciding a travel mode from the same state. This chapter confronts them with the survey, on the cohort of 1,000 personas and the 3,154 scored decisions of the evaluated day.

<!-- source: data/experiences/exp_*_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_*/executions/*/scores.json; cohort population_1000_AAMAS_v6, set population_1000_AAMAS_v6_20260316_EN_c, formula v1_reference (0aeee565…), EMC² 2023 reference frame (9ac34597…). 3,154 decisions out of 3,299 expected, 868 mobile people; 138 unusable trips are excluded by the scorer. Every decider is measured on this set: the replay campaign of ticket 088 finished on 2026-09-17 at 09:25, and no figure in the chapter is read off the earlier substrate any more. -->

Every result in this chapter bears on a couple: a language model and an arbitration instruction, carried by its system prompt and subject to the prohibitions of § 5.3.4, among them any numerical threshold. Engineering that prompt brings `gemini-3.5-flash-lite` 2.3 composite points closer to the survey distribution and `mistral-large-2512` 7.3 points closer, where cohort variation is of the order of 1.3 points. The carrier weighs as much as the instruction: submitted as it stands to a second model from the same provider, the variant tuned against `gemini-3.5-flash-lite` leaves 4.2 points between the two, more than it brings to the weaker of them. Of the three couples measured, one comes within a point and a half of the tabular ceiling, separable from two of the four reference methods and not separable from the other two, and that proximity of the margins covers a decision-by-decision disagreement that the tabular methods, among themselves, do not have.

## 6.1 Thirteen deciders on the same scale

The three readings defined in § 4.2 are published for every decider.

![The thirteen deciders on the composite EMD–JSD axis, by group](../images/ch6_echelle.png)

*Figure 6.1 — The thirteen deciders on the composite EMD–JSD axis. The scale spans a factor of fourteen between the random floor and the best composite, and four groups separate clearly on it. The floors occupy the upper half, from 27 to 50. The minimal prompt places the language models between 7.0 and 14.8, against 27.0 for the shortest-duration heuristic: the facts alone, with no arbitration instruction, already carry behavioural information, distinct from what the survey records. The expert prompt brings the same models back to between 4.9 and 9.0. The four tabular methods hold within a half-point interval, from 3.60 to 4.09. The grey band gives cohort variation, of the order of 1.3 points.*

| Decider | Composite EMD–JSD | Excluding single choice | L1 on global shares |
|---|---:|---:|---:|
| Uniform random draw | 50.16 | 57.90 | 86.80 |
| All-car | 30.73 | 28.41 | 58.00 |
| Shortest duration | 26.97 | 23.93 | 53.62 |
| Minimal prompt, `mistral-large-2512` | 14.75 | 20.72 | 44.71 |
| Minimal prompt, `gemini-3.1-flash-lite` | 12.38 | 16.65 | 39.88 |
| Minimal prompt, `gemini-3.5-flash-lite` | 7.02 | 10.39 | 24.08 |
| Expert prompt, `gemini-3.1-flash-lite` | 8.98 | 12.39 | 31.25 |
| Expert prompt, `mistral-large-2512` | 7.63 | 12.27 | 26.64 |
| Expert prompt, `gemini-3.5-flash-lite` | 4.86 | 6.86 | 13.85 |
| Multinomial logit | 4.02 | 6.63 | 8.99 |
| Random forest | 4.09 | 5.81 | **5.28** |
| Kernel logistic regression | 3.61 | **5.61** | 6.69 |
| Gradient boosting (LightGBM) | **3.60** | 5.84 | 9.49 |

<!-- sources: scores.json, composite.emd_jsd, composite.emd_jsd_hors_choix_unique, global.l1. Minimal prompt = prompt_minimal_02; expert prompt = prompt_expert_05, promoted on 2026-09-17 (prompt_expert_04 deleted from the repository the same day, at the author's request). In this campaign, prompt_expert_05 was tuned against gemini-3.5-flash-lite then submitted as it stands to the other two models; nothing in the protocol requires a single instruction, and a per-model tuning remains open. In bold, the best score in each column. -->

The composite bears on every decision of the day, constrained trips included; the reading excluding single choice removes those where only one option existed; the L1 on global shares looks only at the four aggregate modal shares, with no stratification.

Two scores a point apart are not told apart by this table, cohort variation being of the same order (§ 6.5). Playing two deciders on the same personas removes that term, since it then acts on both sides: paired this way, `gemini-3.5` under the expert prompt is behind gradient boosting by **1.35 points [+0.28; +2.47]** and behind kernel regression by **1.38 [+0.32; +2.45]**, while not separable from the random forest, +0.94 [−0.06; +1.98], nor from the multinomial logit, +0.96 [−0.18; +2.17]. The other two models stay **4.07 [+2.47; +5.75]** and **5.50 [+4.19; +6.93]** behind gradient boosting. One of the three couples therefore comes within reach of the tabular ceiling, and its gap excludes zero against two of the four reference methods. Prompt engineering was carried out on `gemini-3.5`: the distance of the other two measures what an instruction transports, not what a tuning conducted on them would produce.

No equivalence test is reported: the margin was not written before the measurement, and a margin chosen now would be chosen after seeing the figures. Hypothesis H0 of § 1.3 is therefore presented as a paired estimate, with a sign, an amplitude and an interval.

<!-- source: docs/traces/2026-09-17_09-40_ch6_jeu_corrige_complet/ — fourteen paired differences recomputed after the replay campaign ended, every decider on the corrected set, 2,000 replicates, seed 2026, cluster resampling at the person level over 868 common people. The fourteen differences and their three readings are in appendix H. -->

## 6.2 What prompt engineering moves

![Prompt engineering trajectory for three models](../images/ch6_ingenierie.png)

*Figure 6.2 — What prompt engineering makes each model travel. The hollow circle is the minimal prompt, the filled circle the expert prompt evaluated out of sample, the squares two variants tuned in sight of the evaluated cohort. The green band gives the interval of the four tabular methods. The three models start from different places, advance by different amounts, and one alone comes into contact with the band.*

| Paired gain, expert prompt − minimal prompt | Composite | Excluding single choice | L1 on global shares |
|---|---|---|---|
| `gemini-3.5-flash-lite` | **+2.27 [+1.40; +3.22]** | **+3.59 [+2.45; +4.83]** | **+10.2 [+8.0; +12.5]** |
| `gemini-3.1-flash-lite` | **+3.37 [+2.45; +4.25]** | **+4.15 [+3.09; +5.22]** | **+8.6 [+6.8; +10.6]** |
| `mistral-large-2512` | **+7.25 [+5.90; +8.67]** | **+8.63 [+7.15; +10.28]** | **+18.0 [+13.5; +22.4]** |

A dozen engineering iterations on `gemini-3.5-flash-lite` and two or three on each of the other two models produce these displacements, measured at identical personas, itinerary offer, seed and foundation model, the instruction alone changing. The three intervals exclude zero on the three readings, and the gain runs from one and a half to five and a half times cohort variation. The variant measured here was tuned against `gemini-3.5`, then submitted as it stands to the other two models: submitted that way to `gemini-3.1`, it leaves the latter behind `gemini-3.5` by **4.15 points [+2.99; +5.43]**, more than the 3.37 points it brings it, so that a benchmark run under a single instruction measures the model–instruction couple and not the model. The gain itself does not go to the model the instruction was tuned against: `gemini-3.1` takes 3.37 points from it and `gemini-3.5` 2.27, while the second stays 4.15 points ahead of the first after tuning. What prompt engineering moves and the level it reaches are two distinct quantities.

<!-- source: docs/traces/2026-09-17_09-40_ch6_jeu_corrige_complet/; 2,000 replicates, seed 2026, 868 common people, every decider on the corrected set. A positive gain is a lower error. The number of iterations is the order of magnitude declared by the author; § 5.3 describes the procedure, appendix H carries the variants and their scores. The gaps between carriers under each instruction, the reversal of ranking between gemini-3.1 and mistral-large, and the ablation of the justification clause are in appendix H. -->

## 6.3 The detail of the aggregate results, on Gemini 3.5

What follows is measured on `gemini-3.5-flash-lite`, the model against which prompt engineering was conducted; the amplitudes of § 6.2 show that each model responds in its own way.

![Car share by distance band](../images/ch6_distance.png)

*Figure 6.3 — The car share by distance band: the survey target, `gemini-3.5` under the minimal prompt then under the expert prompt, and the tabular method closest to the target on this dimension. § 5.3 describes the lever introduced against a car share flat from one band to the next: engaging a vehicle costs a fixed amount paid in full whatever the length of the trip, and therefore weighs the more heavily the shorter the trip.*

The lever produces what it aimed at, and it creates a slope rather than shifting a level: the car share stays under one kilometre where it was, eight points below the target, and rises by eight to fourteen points at long distances. `gemini-3.5` under the expert prompt passes there ahead of the four methods fitted on the survey, 14.2 points of weighted error against 16.8 for the random forest and 17.8 for gradient boosting: it is the only dimension where an agent manages this, and the one the lever was written against.

![Public transport and cycling by age and by occupation](../images/ch6_residu.png)

*Figure 6.4 — The two modes that carry the residual, read by age and by occupation. The public transport peak of the 15–19 year olds, 47.4 % in the survey, is reproduced by no decider: the agent places 20.8 % there after tuning and the random forest 26.4 %. Cycling follows the opposite path on the same stratum, 19.7 % for the agent against 4.1 % observed, and tuning does not move it.*

What tuning does not correct concentrates on these two modes and on the school-age strata. The 15–19 year olds, school pupils and students are the three strata where the agent places the most cycling, up to five times the observed share, and where it misses the most public transport. The levers of the prompt are written for the arbitrations of a motorised adult — the cost of engaging a vehicle, the value of time under a schedule constraint, the burden of bad weather — and they do not bear on a population for which the survey places nearly half the trips in public transport.

The two minority modes carry an error the instruction does not correct. The three language models place cycling between 6.8 and 8.1 % where the survey counts 4.1 %, and prompt engineering moves that share by only one tenth to eight tenths of a point, where it makes public transport fall back by four to eleven points: two errors coexist in the same decider, and only one answers the instruction. Finally, the two dimensions absent from the calibration cycle as from the composite, the residential ring and the housing type, are those where the agent falls furthest behind, by eight and by seven points against gradient boosting.

**The detailed results are in [appendix H](99_annexes.md)**: the error by dimension and by decider, the modal shares of each, the strata that tuning degrades on the three models, and four plates — the car share on six dimensions, and the four modes read by distance, by occupation and by purpose.

<!-- source: scores.json, detail.<dimension>.strates and global.actual/target; every decider on the corrected set …_20260316_EN_c. The figure compares prompt_minimal_02 and prompt_expert_05, regenerated on 2026-09-17 by scripts/analysis/plot_chapitre6.py. Weighted L1 error on the distance dimension, mean of the covered strata weighted by their size: 14.19 for gemini-3.5 under the expert prompt, 16.79 for the random forest, 17.79 for gradient boosting, 18.09 for kernel regression, 20.73 for the multinomial logit. The 15-19 year olds and trips over 50 km resist every decider, tabular methods included: 34 to 59 and 42 to 72 points of error. Appendix H. -->

## 6.4 Deciding alike, deciding otherwise

Two deciders can produce the same aggregate shares without ever deciding the same thing. On an equal offer, over the trips where both actually chose, agreement is measured on the most likely mode and on the mode actually drawn.

| Pair | Agreement, most likely mode | Agreement, drawn mode |
|---|---:|---:|
| Gradient boosting / kernel regression | 91.6 % | 90.5 % |
| Expert prompt `gemini-3.5` / gradient boosting | 69.7 % | 61.4 % |
| Expert prompt `gemini-3.5` / expert prompt `gemini-3.1` | 79.6 % | 72.8 % |

The four tabular methods form a block, at nine agreements out of ten. No agent enters it, and the agents do not form a second one: the two language models compared here agree as little with each other as with a tabular method. One trip in three receives two different answers from two deciders that the aggregate shares give as neighbours.

Which of the two is right on a given trip cannot be read off the synthetic cohort, which carries no individual truth. The unit accuracy announced in § 4.2 is measured on the survey test partition, 13,045 trips split by household and weighted: the "always the car" prior reaches 57.1 % there, the multinomial logit 76.6 %, the random forest 77.6 %, kernel logistic regression 78.4 % and gradient boosting 78.5 %. The agent is being measured on the same partition, by the protocol of § 5.5: **[xx]** for the minimal prompt, **[xx]** for the expert prompt. A decider can restore the split of a territory while getting half the individuals wrong, and the converse holds too: the composite of § 6.1 therefore does not tell apart two deciders that decide one trip in three differently.

<!-- sources: moves.csv of the corrected-set runs, trips carrying at least two options offered to both deciders, 2,374 to 2,479 depending on the pair; the six pairs and the median gap between distributions are in appendix H. Accuracies: scripts/progedo_logit/{mode_choice_policy,klr_model,rf_mode_choice,mnl_model}_metrics.json, test.accuracy_weighted over 13,045 trips (split by household, seed 0, calibration weights); the prior's accuracy equals the observed car share. These values are not commensurable with the composites: different set, different support. For the agent, the experiment exp_gemini-35-fl_promin02_jtir_pop-enquete_058_test_… was launched on 2026-09-17 at 07:02 and interrupted at 822 trips; the expert prompt has no run yet. Joining the decision log to the declared modes of the survey has still to be tooled: ticket 058. -->

## 6.5 Cohort variation and between-seed dispersion

A cohort of 1,000 personas measures a composite only to within ±1.3 points: that is the 95 % confidence interval obtained by resampling people with replacement, and it bounds what the table of § 6.1 allows to be told apart. The paired standard deviation of that term is about 0.7, so that no equivalence margin below 1.4 points will be concluded from one run on this cohort; only further cohorts lower it, and three are planned in [ticket 073](../../../tickets/ticket_073_reproductibilite_prompt_calibre_multi_graines_multi_populations.md), axis 2. This is why every comparison in this chapter is paired: playing the two deciders on the same personas makes that term act on both sides, where it cancels.

Between-seed dispersion, for its part, leaves the gaps of this chapter where they are **TBC**. Replayed on the same cohort with other seeds, a language-model decider stays within cohort variation, and none of the paired differences of §§ 6.1 and 6.2 changes sign **TBC**. The protocol that establishes this is the one of the same ticket, axis 1.

Two measurements already give the order of magnitude. The same prompt, on the same model and with the same seed, replayed on the corrected substrate of [ticket 088](../../../tickets/ticket_088_jeu_corrige_et_rejeu_complet.md), moves its composite by 0.24 to 1.17 points depending on the decider, where deterministic deciders move by less than 0.12; and two runs of the same prompt on two successive cohorts agree on 86.1 % of the most likely modes. Both confound the non-determinism of the model with the change of substrate, and it is identical replay that separates them.

Two asymmetries of the device remain declared rather than corrected. The tabular methods were fitted on real days, themselves chained, and playing them under the chain constraint applies that constraint a second time (§ 4.4). The agent sees the agenda of its day where the tabular methods decide each trip in isolation (§ 4.3, taken up again in chapter 8).

<!-- REVIEW WARNING: the two **TBC** of the second paragraph anticipate a result that is not yet measured. Author's decision of 2026-09-17: write the chapter taking between-seed dispersion as given and similar, and lift the TBC when ticket 073 axis 1 has delivered its identical replay. No figure is advanced while the measurement does not exist. The rest is measured: ±1.3 points and paired standard deviation of 0.7 from ticket 080 § 0.3, substrate gaps read in the scores.json of the two sets, agreement of 86.1 % from two runs of the same prompt on two successive cohorts. -->

---

### Tickets attached to this chapter

- [Ticket 080](../../../tickets/ticket_080_idee_directrice_du_chapitre_6_et_impact_sur_le_papier.md) — guiding idea, author's decisions, impact on the rest of the paper
- [Ticket 088](../../../tickets/ticket_088_jeu_corrige_et_rejeu_complet.md) — corrected set and replay of the language-model deciders
- [Ticket 073](../../../tickets/ticket_073_reproductibilite_prompt_calibre_multi_graines_multi_populations.md) — identical replay, between-seed dispersion, further cohorts
- [Ticket 074](../../../tickets/ticket_074_bascule_anglaise_archivage_et_reprise_de_campagne.md) — v6 campaign, substrate of the published figures
- [Ticket 055](../../../tickets/ticket_055_benchmark_multimodeles_et_variabilite.md) — multi-model benchmark
- [Ticket 057](../../../tickets/ticket_057_audit_et_reflexion_double_lecture_tabulaire.md) — vehicle-chain constraint and scoring perimeter
- [Ticket 058](../../../tickets/ticket_058_perimetre_et_methode_audit_unitaire.md) — unit audit, agreement with observed choices, Shapley attributions
- [Ticket 046](../../../tickets/ticket_046_asymetrie_informationnelle_du_contrat_d_evaluation.md) — information asymmetry between the agent and the tabular methods
