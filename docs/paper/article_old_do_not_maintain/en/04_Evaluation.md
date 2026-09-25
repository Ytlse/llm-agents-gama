# 4. Metrics and evaluation substrate

<!-- Dernière mise à jour : 2026-09-21 -->

**Document:** chapter 4 of the AAMAS 2027 paper, **first written in French**. This English version translates the French draft [`fr/04_Evaluation.md`](../fr/04_Evaluation.md) `v0.17`; from here on the two texts are held in parity, the French one remaining the source for this chapter. The LaTeX rendering for Overleaf is [`overleaf/chapters/04_Evaluation.tex`](../overleaf/chapters/04_Evaluation.tex).
**Status:** `draft v0.19` (21 September 2026) — English version of the French `v0.19`: translation only, no change of substance. § 4.1 now states **the language the device runs in**, and why. Three paragraphs close the section: the scope of the switch (cohort traits, system prompt, rendering template, justifications written by the agent), the four results that support it, and the two that cut the other way. Five references enter the corpus, all verified against their PDF. Set aside from the same passage: Ananthram et al. (2025), whose conclusion on pre-training representation bears on vision-language models in image understanding.
**Previous status:** `draft v0.18` (17 September 2026) — the vocabulary of the tabular references is aligned across the paper, at the author's request. Rule 1 no longer reads “the agent, the logit and the oracle”: § 4.4 has counted four tabular references since its `brouillon v0.15`, and the rule now names them as four. The three asymmetries are stated of the references rather than of a single oracle, which is exact, all four being fitted on the same file with the same household split. The measured-not-published note on renormalisation names gradient boosting, the model it was measured on. No figure changes and no claim moves. The LaTeX rendering carries this pass but still lags on the § 4.1 and § 4.2 additions of `v0.17`.
**Previous status:** `draft v0.17` (17 September 2026) — English version of the French `v0.17`: translation only, no change of substance. Two additions. § 4.1 now states **how the uncertainties are computed**: trips made by the same person are not independent, the intervals come from cluster resampling at the person level, and the resolution is ±1.3 composite point per arm; two caveats are carried in comment, the measurement predating the rescoring of 2026-09-16 and the sizing note reasoning on a household cluster where the measurement uses the person. § 4.2 **writes out the formula of the two composites** and their weights, until now described in prose alone, and names the two historical terms kept at zero weight. `draft v0.16` (16 September 2026) — English version of the French `v0.16`: translation only, no change of substance. The chapter follows the thread *what we measure on, what we measure with, under what conditions, and what the references give*: the substrate and its demographic control open it (4.1), the quantities follow (4.2), the evaluation contract comes next (4.3), the four tabular methods close it (4.4). The two divergences from the French flagged in `v0.16` were settled in the French text on the same day: the opening sentence of § 4.2 and the lead-in of the unit-level list. The two texts are in parity.
**Previous status:** the French history is kept in the source file and not repeated here. Four decisions bear on how this chapter reads. The reading **without the vehicle-chain constraint is not published**: it does not compare with the agents, all of which are subject to the chain. The ceiling is **plural** — the four methods are fitted on the same microdata at strict parity, so the exposure that makes them a high reference does not tell them apart; on each axis the ceiling is the best score reached by one of the four. The **scoring perimeter** was corrected (ticket 057): the cut at the first simulated day removed 866 decisions out of 3,299 for zero duplicates, 797 of them the morning departure, and twenty-five runs were rescored offline. Finally the chapter states what it does and what it measures on, and does not plead its own case.
**Place in the paper:** Section 4 of the plan announced in 1.4 of [`../en/01_Introduction.md`](../en/01_Introduction.md). Progress: [`../README.md`](../README.md).
**Figure convention:** no **[xx]** placeholder in the body of this chapter. Every figure is read off the sealed cohort v6, its runs of 14–15 September 2026, or the fit metrics of the tabular models, and its source is given in an HTML comment beside it so that it can be recomputed without searching.
**Data access:** agreement `lil-1750` — [`../../sources/ENGAGEMENT_DONNEES_EMC2.md`](../../sources/ENGAGEMENT_DONNEES_EMC2.md). It **applies** — citation following the annexed template, no microdata redistributed, nothing extracted into the supplementary material — and is not the subject of a section of this chapter: the access procedure for a third party is in Appendix G.
**Measurement sources:** [`docs/arch/score-synthesis.md`](../../../arch/score-synthesis.md), [`controle-population-jeu-de-test.md`](../../../arch/controle-population-jeu-de-test.md), [`../../methode/JUSTIFICATION_TAILLE_ECHANTILLON.md`](../../methode/JUSTIFICATION_TAILLE_ECHANTILLON.md), `data/population/population_1000_AAMAS_v6/{MANIFEST.yaml,CONTROLE.md}`, `data/experiences/exp_{lgbm,mnl,rf,klr}_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_nosim/executions/*/scores.json`.

---

## 4.1 The evaluation substrate

The measurements in this paper rest, for the most part, on one **test set**: a sealed cohort of 1,000 people, their trips on the evaluated day, and the itineraries the routers returned for each of them. It is on this set that most of the experiments of chapters 5 and 6 run, agents and tabular references alike. The few measurements carried out on a smaller set say so where they are cited. <!-- source: data/jeux/population_1000_AAMAS_v6_20260316_EN/MANIFEST.yaml -->

The 1,000 people fall into 499 whole households, the household being the sampling unit, drawn from a pool of 11,329 people produced by the eqasim synthesis chain (Hörl & Balać, 2021) from the census, tax income records and the household travel survey. The perimeter is the survey's: the 453 municipalities of the Toulouse living area. <!-- source: data/population/population_1000_AAMAS_v6/MANIFEST.yaml, selection.menages_retenus.n = 499, selection.vivier.n = 11329 ; perimeter delimited by the municipal polygon, not by a radius -->

Each person carries a weight of one. The mobility of the cohort is that of its activity chains, which are cyclic: the day closes on the return home, so that a chain of *k* activities carries *k* trips. It produces 3,299 trips on the evaluated day, that is 3.30 per person and 3.69 per mobile person, with 10.6 % immobile; the survey gives 3.53, 3.95 and 10.6 %. <!-- source: MANIFEST.yaml, controle.menages_et_mobilite and reference_enquete ; 3,161 carry a modal decision, the other 138 have origin and destination at the same place -->

Thirteen margins are controlled, each with its source: a page of the published report, or a recomputation on the survey microdata (Appendix G) where the report does not publish the margin.

| Margin | Base | Source | Max gap (pt) | Verdict |
|---|---|---|---:|---|
| Age class (6 classes) | person | published report | 0.50 | conforming |
| Occupation | person | published report | 0.50 | conforming |
| Five-year age (15 classes) | person | microdata | 0.29 | conforming |
| Car ownership | person | microdata | 0.09 | conforming |
| Car ownership | household | published report | 0.06 | conforming |
| Residential ring | person | published report | 0.06 | conforming |
| Ring × car ownership | person | microdata | 0.05 | conforming |
| Household size | person | microdata | 0.06 | conforming |
| Driving licence (18 and over) | person | microdata | 0.01 | conforming |
| Public transport season ticket | person | microdata | 0.05 | conforming |
| Dwelling type | person | microdata | 0.04 | conforming |
| Gender | person | microdata | 0.02 | conforming |
| People with no trip on the previous day | person | microdata | 0.05 | conforming |

<!-- source: data/population/population_1000_AAMAS_v6/CONTROLE.md, sealed on 2026-09-14 ; 13 conforming, 0 to publish, 0 not measurable ; recomputations cited under agreement lil-1750 -->

The test is an equivalence test margin by margin, with an indifference margin of 1 point announced before the measurement, completed by the maximum absolute gap and a Cramér's $V$ as effect size.

Trips are not independent: those made by the same person share their activity chain, their equipment and their home. Confidence intervals are therefore obtained by cluster resampling at the person level. The resolution reached is ±1.3 composite point per arm, and most of that noise comes from the least populated strata: the distance class beyond 50 km carries only 17 decisions. <!-- source: docs/traces/2026-09-15_09-20_ticket080_idee_directrice_chapitre6/rapport.md § 2.1, 867 people drawn with replacement, 100 replicates, official scorer ; paired differences at 200 replicates (§ 2.2). Measured before the rescoring of 2026-09-16 : the composites there run from 4.40 to 8.95 where the table of § 4.4 carries 3.60 to 4.09. The sizing note computes on its side a design effect at household level (DEFF ≈ 2.1) ; the cluster used at measurement is the person. -->

The device runs in English: the cohort's traits, the system prompt, the template that formats the observation, and the justifications the agent writes. Municipality, stop and line names stay in French, as they would under any language of execution. <!-- source: config/prompts.yaml and categories/itinary_multi_agent/template.md.j2 ; data/population/population_1000_AAMAS_v6/MANIFEST.yaml -->

Four results support that choice. Forcing a reasoning model to produce its thinking trace outside English costs accuracy (Qi et al., 2025), and the prompts of chapter 5 impose exactly such a multi-step reasoning procedure. In agentic recommendation, local-language bias is prevalent and explicit reasoning worsens it outside English (Liu et al., 2025). Across 180 diagnostic vignettes blind-rated by two physicians, four models out of five scored higher in English, by 0.37 to 0.91 point out of 18 (Bazoge et al., 2026). Explicit cultural framing finally weighs more than the prompt's language on alignment with a population's values, and it works as well when stated in English (Bulté & Rigouts Terryn, 2026): the territorial anchor the prompt carries is not lost in translation.

Two results cut the other way. A model answers a question of local culture better when it is asked in the matching language (Ying et al., 2025), a benefit English execution gives up; and prompting in English induces a Western-centric bias (Soegeng et al., 2026), which the device counters by no reinforcement of its territorial framing, a point § 8.6 carries as a limit. The four results above moreover bear on neighbouring tasks and not on ours: no measurement conducted here establishes that running in French degraded the scores of chapter 6.

## 4.2 What is measured

The population of agents chooses among the itineraries offered for each trip. Those choices are evaluated at two scales:

- **at the aggregate scale**, the question is fidelity: is the modal split produced that of the territory?
- **at the unit scale**, the question is agreement decision by decision: did this particular trip receive the mode the person declared?

### The modal split

Four modes are scored: car, public transport, walking, cycling. The reference is that of the EMC² 2023 survey. It is recomputed for each stratum — age class, occupation, gender, trip purpose, distance class — and those readings are then aggregated into a composite score. <!-- source: docs/arch/score-synthesis.md § 2 ; prompt_calibration/calibration/metrics.py -->

- **The L1 error**, the sum of absolute share gaps, is expressed in percentage points and reads without conversion:

$$L_1 = \sum_{m} \left| \hat{P}_m - P_m^{\text{EMC}^2} \right|$$

- **The Jensen-Shannon divergence**, on the nominal axes (gender, occupation, purpose):

$$\mathrm{JSD}(P \parallel Q) = \tfrac{1}{2}\,\mathrm{KL}(P \parallel M) + \tfrac{1}{2}\,\mathrm{KL}(Q \parallel M), \qquad M = \tfrac{1}{2}(P + Q)$$

- **The optimal transport distance** (*Earth Mover's Distance*, or Wasserstein-1 on a line), on the ordinal axes (age class, distance class). For $K$ ordered classes and $F$, $\hat{F}$ the cumulative distribution functions:

$$\mathrm{EMD}(\hat{P}, P) = \sum_{k=1}^{K-1} \left| \hat{F}_k - F_k \right|$$

These readings aggregate into two composites. Each adds to the global reading the mean of each stratum, weighted 0.5 for age, occupation and purpose, 0.3 for gender and distance:

$$\mathcal{C}_{L_1} = L_1^{\text{global}} + \sum_{d} w_d\,\overline{L_1}^{\,d}, \qquad \mathcal{C}_{\text{EMD–JSD}} = \mathrm{JSD}^{\text{global}} + \sum_{d\ \text{nominal}} w_d\,\overline{\mathrm{JSD}}^{\,d} + \sum_{d\ \text{ordinal}} w_d\,\overline{\mathrm{EMD}}^{\,d}$$

where the bar is the unweighted mean over the categories of the stratum, categories of fewer than five personas being left out. <!-- source: prompt_calibration/calibration/metrics.py, WEIGHTS (global 1.0, age 0.5, occupation 0.5, motif 0.5, genre 0.3, distance 0.3) and STRATUM_MIN_PERSONAS = 5. Two historical terms, absent_penalty and length_penalty, are still computed and stored at zero weight ; the composite being linear, that removal re-applies exactly (rescale_composite). Check on exp_lgbm_…_c_nosim of 2026-09-16 : 9.491 + 0.5 (17.938 + 18.772 + 13.521) + 0.3 (8.483 + 20.975) = 43.444. -->

### Unit-level accuracy

Four quantities are published at this scale: accuracy, cross-entropy measured on the decisions every decider compared scores, then recall and precision per mode.

### The scored quantity

A distribution over the four modes summarises in two ways, and both give a modal share: summing the probability assigned to each mode, or counting only the most probable mode. We keep the first, the **mass**. We ask the model to verbalise its distribution rather than to sample it by repetition (Meister et al. (2024) show that verbalised distributions align better than sampled ones), and the decision actually played in the simulation is a draw from that distribution. Keeping the most probable mode would flatten individual variability: every persona of the same profile would set off in the same mode, and the population would lose exactly what it is asked to reproduce. The mass is therefore the scored quantity, for every decision-maker compared, and it is what compares with the mass of a tabular model; the most probable mode is published as a secondary reading, against the tabular argmax. <!-- source: the scorer also computes a variant on the drawn modes (composite.emd_jsd_tire) ; the one published is the mass (composite.emd_jsd). Readings attendu / elu / brut: scripts/synthesis/build.py -->

The quantities above are published together and read axis by axis.

## 4.3 The three rules of the comparison protocol

The first contribution announced in 1.3, under the name **comparison protocol**, comes down to three rules. Each closes one way in which a comparison between a generative agent and a tabular model can be biased.

**Rule 1 — a common set of inputs.** The agent and the four tabular references receive the same 21 variables describing the person and the trip to be decided: twelve for the person and their household, three for the trip itself (purpose at origin, purpose at destination, departure hour), six for the geometry (distance between origin and destination, whether or not they lie in the same zone, distance to the centre from the origin and then from the destination, population density at each). The complete list is in the appendix. <!-- source: scripts/progedo_logit/feature_spec.json ; list reproduced in the appendix -->

The agent additionally receives three things no tabular model can receive: the schedule of the trips it has left before returning home, the weather of the coming time slots, and the itineraries themselves, step by step, where the tabular model knows only the geometry of the trip and sees the offer only through the renormalisation of rule 3. <!-- source: mobility_llm/src/mobility_llm/persona.py, fields agenda, day_outlook and trajectories ; rendered in categories/itinary_multi_agent/template.md.j2 ("Trip options") --> What is equalised is the 21 variables, not the information: the agent receives more.

The third asymmetry does not pull the same way as the first two: on exposure, the tabular references have read 39,203 survey trips and the agent has read none <!-- source: scripts/progedo_logit/mode_choice_policy_metrics.json, training.n_fit 31,279 + training.n_valid 7,924 ; the sum is the right count for an exposure claim, early stopping (early_stopping_rounds 50, best_iteration 1500) letting the validation set choose the number of iterations and so shape the model. The 13,045 test trips are out of this count --> : that is what makes them high references rather than competitors.

**Rule 2 — the probability mass is the scored quantity.** The agent spreads a probability mass over the options presented to it, six at most <!-- source: experience.yaml of the played experiments, max_candidats: 6 -->, and that mass compares with the mass of the tabular model (Section 4.2).

**Rule 3 — renormalisation on the offer.** The tabular model predicts over four classes without knowing what was offered; the agent chooses only among the itineraries the routers actually returned. Every tabular prediction is therefore restricted to the modes offered for that trip, then renormalised to 100 %. The probabilities are written before and after correction. <!-- effect measured, not published : renormalisation removes 1.5 point from gradient boosting's car share without the chain constraint (58.8 % → 57.3 %, n = 3,111) and 9.0 points under it (52.7 % → 43.7 %, n = 2,502) ; decisions.jsonl of exp_lgbm_…_nochn_noret_nosim and …_nosim, mean of p_raw_voiture and p_voiture -->

## 4.4 The four tabular reference models

Four classical mode choice methods serve as references: the multinomial logit, gradient boosting (LightGBM, Ke et al., 2017), kernel logistic regression and the random forest. Each is fitted on the survey microdata[^emc2], then played on the test set of Section 4.1, trip by trip, exactly as the agents are. <!-- source: the fit is validated separately, on a quarter of the survey split by household (scripts/progedo_logit/*_metrics.json, split.by = hh_id) ; that validation only checks that the models hold and does not enter the paper -->

They are estimated at strict parity: same data file, same household split, same raising weights, same encoding, same metrics from a shared module.

They are subject to the vehicle-chain constraint of chapter 3, the very one the agents are subject to: a car that left in the morning is not available in the evening.

| Reference method | L1 global shares (pts) | Composite L1 (cumulated pts) | Composite EMD–JSD |
|---|---:|---:|---:|
| Gradient boosting (LightGBM) | 9.5 | 43.4 | 3.60 |
| Multinomial logit | 9.0 | 44.9 | 4.02 |
| Kernel logistic regression | 6.7 | 41.1 | 3.61 |
| Random forest | **5.3** | **38.3** | 4.09 |

<!-- sources: data/experiences/exp_{lgbm,mnl,rf,klr}_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_nosim, runs of 2026-09-16, scores.json : global.l1, composite.l1, composite.emd_jsd, composite.emd_jsd_tire. The reading without the chain constraint (…_nochn_noret_nosim) is not published : it does not compare with the agents, all of which are subject to the chain. Target : 56.7 / 12.4 / 26.8 / 4.1 % (car / public transport / walking / cycling), cerema_values.yaml renormalised over four modes. -->

No method leads on all three axes. The random forest has the lowest error on global shares, 5.3 points, and the best composite L1. On the composite EMD–JSD, gradient boosting and kernel logistic regression stand at 3.604 and 3.605: two thousandths separate them, for a resolution of ±1.3 point per arm, and the axis therefore designates neither. Gradient boosting ends last on global shares, at 9.5 points.

Kernel logistic regression follows the random forest on the other two axes. <!-- source: klr_model_metrics.json ; RBF kernel, Nyström approximation -->

Together the four methods form the high reference, and the ceiling reads axis by axis: on each, the best score in the table. It is against that ceiling that an agent compares.

[^emc2]: doi:10.13144/lil-0933
    Enquête Ménages Déplacements (EMD), Toulouse / Grande agglomération toulousaine
    (EMD, Toulouse / Grande agglomération toulousaine) - 2023, CEREMA, Syndicat mixte
    des transports en commun de l'agglomération toulousaine (producers), PROGEDO-ADISP
    (distributor)

---

### Tickets attached to this chapter
- [Ticket 043](../../../tickets/ticket_043_troisieme_famille_regression_logistique_noyau.md) — Third reference family: kernel logistic regression
- [Ticket 045](../../../tickets/ticket_045_substrat_unique_v5_et_reconstruction_des_experiences.md) — Single substrate v5 and rebuilding of the experiments
- [Ticket 046](../../../tickets/ticket_046_asymetrie_informationnelle_du_contrat_d_evaluation.md) — The agent sees its day, the tabular model does not: what does the protocol say?
- [Ticket 047](../../../tickets/ticket_047_offre_a_mode_unique_ce_qui_compte_comme_decision.md) — Single-mode offer: what counts as a decision
- [Ticket 057](../../../tickets/ticket_057_audit_et_reflexion_double_lecture_tabulaire.md) — Audit of the vehicle-chain constraint and of the scoring perimeter
- [Ticket 052](../../../tickets/ticket_052_documentation_cohorte_scellee_v5.md) — Documentation and demographic sealing of cohort v5
- [Ticket 053](../../../tickets/ticket_053_acces_donnees_recherche_et_reproductibilite.md) — Survey data access for research and reproducibility protocol
