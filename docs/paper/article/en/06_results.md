# 6. Results

<!-- Dernière mise à jour : 2026-09-17 -->

**Document:** chapter 6 of the AAMAS 2027 paper — the **results** chapter: chapter 5 defines the conditions compared, this one says what the comparison establishes. English master; French mirror in [`fr/06_results.md`](../fr/06_results.md); LaTeX rendering for Overleaf in [`overleaf/06_results.tex`](../overleaf/06_results.tex).
**Status:** `draft v0.4` (17 September 2026) — first English master, translated from the French `brouillon v0.4` of the same day. The French carries the version history; it is not repeated here. Five sections, six figures already composed in English: four by `scripts/analysis/plot_chapitre6.py`, the two of the unit audit by `scripts/analysis/plot_audit_unitaire.py`; the detail tables live in appendices H and I.
**Place in the paper:** section 6 of the plan announced in § 1.4 of [`../en/01_introduction.md`](../en/01_introduction.md). Outline: [`../plan/PLAN.md`](../plan/PLAN.md). Progress: [`../README.md`](../README.md).
**Convention:** a figure followed by **TBC** is to be consolidated. A figure **in bold brackets** is an empty placeholder.

---

Chapter 5 described four ways of deciding a travel mode from the same state. This chapter confronts them with the survey, on the cohort of 1,000 personas and the 3,154 scored decisions of the evaluated day.

<!-- source: data/experiences/exp_*_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_*/executions/*/scores.json; cohort population_1000_AAMAS_v6, set population_1000_AAMAS_v6_20260316_EN_c, formula v1_reference (0aeee565…), EMC² 2023 reference frame (9ac34597…). 3,154 decisions out of 3,299 expected, 868 mobile people; 138 unusable trips are excluded by the scorer. Every decider is measured on this set: the replay campaign of ticket 088 finished on 2026-09-17 at 09:25, and no figure in the chapter is read off the earlier substrate any more. -->

Every result in this chapter bears on a couple: a language model and an arbitration instruction, carried by its system prompt and subject to the prohibitions of § 5.2.3, among them any numerical threshold. Engineering that prompt brings `gemini-3.5-flash-lite` 2.3 composite points closer to the survey distribution and `mistral-large-2512` 7.3 points closer, where cohort variation is of the order of 1.3 points. The carrier weighs as much as the instruction: submitted as it stands to a second model from the same provider, the variant tuned against `gemini-3.5-flash-lite` leaves 4.2 points between the two, more than it brings to the weaker of them. Of the three couples measured, one comes within a point and a half of the tabular ceiling, separable from two of the four reference methods and not separable from the other two, and that proximity of the margins covers a decision-by-decision disagreement that the tabular methods, among themselves, do not have.

## 6.1 Thirteen deciders on the same scale

The three readings defined in § 4.2 are published for every decider.

![The thirteen deciders on the composite EMD–JSD axis, by group](../images/ch6_echelle.png)

*Figure 6.1 — The thirteen deciders on the composite EMD–JSD axis, a factor of fourteen between the random floor and the best composite. Four groups separate on it: the floors from 27 to 50, the minimal prompt from 7.0 to 14.8, the expert prompt from 4.9 to 9.0, the four tabular methods from 3.60 to 4.09. The minimal prompt thus passes below the shortest-duration heuristic, at 27.0: the facts alone, with no arbitration instruction, already carry behavioural information. The grey band gives cohort variation, of the order of 1.3 points.*

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

<!-- source: docs/traces/2026-09-17_09-40_ch6_jeu_corrige_complet/ — fourteen paired differences recomputed after the replay campaign ended, every decider on the corrected set, 2,000 replicates, seed 2026, cluster resampling at the person level over 868 common people. The fourteen differences and their three readings are in appendix H. -->

## 6.2 What prompt engineering moves

![Prompt engineering trajectory for three models](../images/ch6_ingenierie.png)

*Figure 6.2 — What prompt engineering makes each model travel. The hollow circle is the minimal prompt, the filled circle the reference expert prompt, the squares two variants rewritten on the residuals of the cohort. The green band gives the interval of the four tabular methods. The three models start from different places, advance by different amounts, and one alone comes into contact with the band.*

| Paired gain, expert prompt − minimal prompt | Composite | Excluding single choice | L1 on global shares |
|---|---|---|---|
| `gemini-3.5-flash-lite` | **+2.27 [+1.40; +3.22]** | **+3.59 [+2.45; +4.83]** | **+10.2 [+8.0; +12.5]** |
| `gemini-3.1-flash-lite` | **+3.37 [+2.45; +4.25]** | **+4.15 [+3.09; +5.22]** | **+8.6 [+6.8; +10.6]** |
| `mistral-large-2512` | **+7.25 [+5.90; +8.67]** | **+8.63 [+7.15; +10.28]** | **+18.0 [+13.5; +22.4]** |

These displacements are measured at identical personas, itinerary offer, seed and foundation model, the instruction alone changing. The three intervals exclude zero on the three readings, and the gain runs from one and a half to five and a half times cohort variation.

<!-- source: docs/traces/2026-09-17_09-40_ch6_jeu_corrige_complet/; 2,000 replicates, seed 2026, 868 common people, every decider on the corrected set. A positive gain is a lower error. The number of iterations is the order of magnitude declared by the author; § 5.2 describes the procedure, appendix H carries the variants and their scores. The gaps between carriers under each instruction, the reversal of ranking between gemini-3.1 and mistral-large, and the ablation of the justification clause are in appendix H. -->

## 6.3 The detail of the aggregate results, on Gemini 3.5

![Car share by distance band](../images/ch6_distance.png)

*Figure 6.3 — The car share by distance band: the survey target, `gemini-3.5` under the minimal prompt then under the expert prompt, and the tabular method closest to the target on this dimension.*

<!-- source: scores.json of the two corrected-set runs, detail.distance.strates, car share prompt_minimal_02 → prompt_expert_05: 9.7 → 10.1 (0-1 km); 37.7 → 43.4; 51.1 → 58.4; 60.0 → 65.9; 67.5 → 74.1; 74.9 → 80.8; 63.8 → 61.8 (over 50 km, n = 17). The fixed-cost lever of the vehicle ("Fixed frictions of the car") belongs to prompt_expert_08, not to prompt_expert_05 which the figure plots: the slope is measured, its attribution to that lever is not. -->

![Public transport and cycling by age and by occupation](../images/ch6_residu.png)

*Figure 6.4 — The two modes that carry the residual, read by age and by occupation. The public transport peak of the 15–19 year olds, 47.4 % in the survey, is reproduced by no decider: the agent places 20.8 % there after tuning and the random forest 26.4 %. Cycling follows the opposite path on the same stratum, 19.7 % for the agent against 4.1 % observed, and tuning does not move it.*

The two minority modes carry an error the instruction does not correct. The three language models place cycling between 6.8 and 8.1 % where the survey counts 4.1 %, and prompt engineering moves that share by only one tenth to eight tenths of a point, where it makes public transport fall back by four to eleven points: two errors coexist in the same decider, and only one answers the instruction.

The detailed results are in [appendix H](99_annexes.md): the error by dimension and by decider, the modal shares of each, the strata that tuning degrades on the three models, and four plates, the car share on six dimensions and the four modes read by distance, by occupation and by purpose.

<!-- source: scores.json, detail.<dimension>.strates and global.actual/target; every decider on the corrected set …_20260316_EN_c. The figure compares prompt_minimal_02 and prompt_expert_05, regenerated on 2026-09-17 by scripts/analysis/plot_chapitre6.py. Weighted L1 error on the distance dimension, mean of the covered strata weighted by their size: 14.19 for gemini-3.5 under the expert prompt, 16.79 for the random forest, 17.79 for gradient boosting, 18.09 for kernel regression, 20.73 for the multinomial logit. The 15-19 year olds and trips over 50 km resist every decider, tabular methods included: 34 to 59 and 42 to 72 points of error. Appendix H. -->

## 6.4 Agreement between deciders, trip by trip

On an equal offer, over the trips where both deciders actually chose, agreement is measured on the most likely mode and on the mode actually drawn.

| Pair | Agreement, most likely mode | Agreement, drawn mode |
|---|---:|---:|
| Gradient boosting / kernel regression | 91.6 % | 90.5 % |
| Expert prompt `gemini-3.5` / gradient boosting | 69.7 % | 61.4 % |
| Expert prompt `gemini-3.5` / expert prompt `gemini-3.1` | 79.6 % | 72.8 % |

The four tabular methods form a block, at nine agreements out of ten. No agent enters it, and the agents do not form a second one: the two language models compared here agree as little with each other as with a tabular method. One trip in three receives two different answers from two deciders that the aggregate shares give as neighbours.

<!-- source: moves.csv of the corrected-set runs, trips carrying at least two options offered to both deciders, 2,374 to 2,479 depending on the pair; the six pairs and the median gap between distributions are in appendix H. -->

## 6.5 Individual decision

The unit accuracy announced in § 4.2 is measured on the days the respondents actually described, by the protocol of § 5.4: 9,621 trips made by 2,930 people, each carrying the mode they declared.

| Decider | Accuracy | Cross-entropy | Bike recall | Walking recall |
|---|---:|---:|---:|---:|
| Gradient boosting | 71.5 | **0.299** | 20.4 | 63.4 |
| Multinomial logit | 68.6 | 0.358 | 18.3 | 60.0 |
| Shortest duration | 68.1 | — | 25.8 | 19.2 |
| Expert prompt, `gemini-3.5` | 67.6 | 0.342 | 22.5 | 47.2 |
| Minimal prompt, `gemini-3.5` | 64.8 | 0.383 | 24.1 | 44.2 |

*Five deciders out of nine, in per cent except for cross-entropy, measured over the 5,451 decisions every decider compared scores. The other four and the precision columns are in appendix I.*

The expert prompt names the declared mode slightly less often than the tabular methods. On cross-entropy, which weighs the probability a decider gave to the mode finally declared, it comes ahead of one of them alone, the multinomial logit. The ranking therefore depends on the quantity read without bringing the agent ahead, and neither of these two readings can be read off the composite of § 6.1, which compares aggregate shares alone.

![Recall and precision per mode](../images/ch6_audit_modes.png)

*Figure 6.5 — Recall and precision per mode, for the tabular ceiling and the two levels. Both levels recall bikes better than any fitted method, 22.5 and 24.1 % against 20.4, and pay for it in precision, 15.0 against 27.3: they announce bikes three times too often. On walking the relation reverses, recall 47.2 against 63.4 and precision 62.9 against 53.2, the best of the table.*

![Unit agreement by trip distance](../images/ch6_audit_distance.png)

*Figure 6.6 — Unit agreement by distance band. Below 1 km, a third of the sample together with the next band, the deciders spread from 36.9 to 62.4 %; beyond 10 km they all hold within two points and the all-car baseline matches the tabular ceiling. The comparison between deciders plays out on short trips.*

The per-mode detail of the nine deciders, the confusion matrix and the ceiling of the audit are in appendix I.

<!-- sources: cross-entropy recomputed on 2026-09-21 over the common support, the 5,451 arbitrated decisions scored by the six distribution-bearing deciders compared here; the earlier reading scored each decider on its own subset, 5,923 to 6,588 decisions depending on how hard it decided, and put the expert prompt first — trace docs/traces/2026-09-21_11-45_ticket058_entropie_support_commun/. Unit accuracies: scripts/progedo_logit/audit_unitaire_058.py over the runs of set enquete_058_test_20260316, nine deciders, 9,613 to 9,618 trips scored depending on the decider; figures 6.5 and 6.6 regenerated by scripts/analysis/plot_audit_unitaire.py (9,621 declared, less those without an offer and the broken chainings). The two LLM arms are exp_gemini-35-fl_{promin02,proexp05}_jtir_pop-enquete_058_test_… completed on 2026-09-18 and 2026-09-19, 12,562 decisions each, no error. These values are commensurable neither with the composites (different set, different support) nor with the test-partition landmarks quoted in § 5.3: the latter hold outside the vehicle chain and without the option cap, and give 76.6 to 78.5 % to the same tabular methods that reach 68.6 to 71.5 % here. -->

## 6.6 Cohort variation and between-seed dispersion

A cohort of 1,000 personas measures a composite only to within ±1.3 points: that is the 95 % confidence interval obtained by resampling people with replacement, and it bounds what the table of § 6.1 allows to be told apart. The paired standard deviation of that term is about 0.7, so that no equivalence margin below 1.4 points will be concluded from one run on this cohort; only further cohorts lower it. This is why every comparison in this chapter is paired: playing the two deciders on the same personas makes that term act on both sides, where it cancels.

Between-seed dispersion, for its part, leaves the gaps of this chapter where they are **TBC**. Replayed on the same cohort with other seeds, a language-model decider stays within cohort variation, and none of the paired differences of § 6.2 and appendix H changes sign **TBC**.

<!-- The two claims of the paragraph above anticipate a result that is NOT yet measured, hence the **TBC**. Author's decision of 2026-09-17: write the chapter taking between-seed dispersion as given and similar, and lift the TBC when the identical replay of ticket 073 axis 1 has delivered it. No figure is advanced while the measurement does not exist. Do not publish this paragraph without that replay. -->

Two measurements already give the order of magnitude. The same prompt, on the same model and with the same seed, replayed on a corrected substrate, moves its composite by 0.24 to 1.17 points depending on the decider, where deterministic deciders move by less than 0.12; and two runs of the same prompt on two successive cohorts agree on 86.1 % of the most likely modes. Both confound the non-determinism of the model with the change of substrate, and it is identical replay that separates them.

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
