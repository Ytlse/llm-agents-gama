# 7. Responding to what no variable encodes

<!-- Dernière mise à jour : 2026-09-17 -->

**Document:** chapter 7 of the AAMAS 2027 paper — the chapter of the regimes no survey variable carries: chapter 6 measures the agent on the 21 inputs of the contract, this one measures it on a newspaper article of the day and on yesterday's delay. English master; French mirror in [`fr/07_untabulated_regimes.md`](../fr/07_untabulated_regimes.md); LaTeX rendering for Overleaf in [`overleaf/07_untabulated_regimes.tex`](../overleaf/07_untabulated_regimes.tex).
**Status:** `draft v1.0` (17 September 2026) — first English master, translated from the French `brouillon v1.0` of the same day. The French carries the version history; it is not repeated here. **No result is published: neither campaign has been run**, and every expected quantity carries the name of the run that will produce it.
**Place in the paper:** section 7 of the plan announced in § 1.4 of [`../en/01_introduction.md`](../en/01_introduction.md). Outline: [`../plan/PLAN.md`](../plan/PLAN.md). Progress: [`../README.md`](../README.md).
**Convention:** a figure **in brackets** is an empty placeholder, followed by the run that will fill it.

---

Chapter 6 compares the deciders on the 21 variables of the contract, and the four tabular references come ahead of the best expert prompt there, 3.60 to 4.09 of composite against 4.49. Those 21 variables describe a person, a purpose, an hour and a geometry; none carries the weather, none carries a travel duration, none carries an event of the day. <!-- source: scripts/progedo_logit/feature_spec.json, 21 inputs: 12 persona, 2 purpose, 1 departure hour, 6 geometry -->

This chapter measures the same deciders on two regimes the survey does not tabulate: a press article published in the morning, and a delay suffered the day before. No survey follows the same travellers through a dated Toulouse event, so no value measured here has a target. What is tested is the sign of a displacement, the ordering of the conditions, and the monotonicity of a return, all three written before the first call to the model.

The two regimes add one ingredient at a time to the device of chapter 6. § 7.1 adds a text to the context, memory off as in chapters 5 and 6. § 7.2 switches memory on and inflicts a delay. The chapter does not seek to isolate the effect of a forgetting parameter: the variants of forgetting speed are reported in the appendix, under robustness.

## 7.1 Five local press events, five conditions

### 7.1.1 The events

Five real and dated articles from the Toulouse local press each act through a channel that none of the 21 variables represents. Gusts of the Autan wind above 80 km/h close the city's fenced parks and expose the bridges over the Garonne. A rumour of bedbugs on the fabric seats of the metro and buses leaves the technical offer intact and the credibility of the mode dented. An open-ended strike of refuse collectors makes the pavements of the inner centre impassable without changing their geometry in any way. The street parade of La Machine pedestrianises the centre in front of a dense crowd. The launch of electrically assisted VélôToulouse erases the gradient of the hillsides.

These five events are retained from a matrix of thirty candidate articles, each cell of which carries a modal impact rated from zero to three, a spatial scale and a verified source. <!-- source: docs/paper/sources/actualites/RAPPORT_SCENARIOS_QUALITATIFS_TOULOUSE.md, § 2 the matrix, § 3 the five retained; the full matrix goes to the appendix --> The whole matrix appears in the appendix; the chapter evaluates only the five.

### 7.1.2 The five conditions

Each event is played under five conditions on the same 3,299 trips of the sealed cohort, with memory off, the order of the proposed itineraries being drawn at random on every request. <!-- source: population_1000_AAMAS_v6; option_order_seed, a control made necessary by the order sensitivity that SILICA measures (Bin Tareaf, 2026) -->

| # | Condition | What the decider receives | What the condition separates |
|---|---|---|---|
| C1 | Agent, nominal day | no article | the reference level of the day |
| C2 | Agent, raw article | the press text as it appeared | the total effect of the event |
| C3 | Agent, neutral paraphrase | the same fact, rewritten with no mention of any mode or road | the execution of a lexical instruction from the inference on the situation |
| C4 | Agent, control text | a real local article of comparable length, with no plausible link to mode choice | the effect of the content from the effect of adding a text |
| C5 | Tabular reference, encoded event | the event translated into the offer: links cut, frequencies degraded | what a tabular reference makes of the event when it reaches it |

Condition C5 exists only when the event modifies the offer. The 21 variables carrying neither weather nor duration, the only channel by which an event reaches a tabular reference is rule 3 of the contract: a mode removed from the offer leaves the prediction, which renormalises over the remaining modes. The La Machine parade thus translates into cuts in the graph and modes removed; the bedbug rumour does not translate, and C5 is identical to C1 there. The reach is measured and published rather than assumed: on a ring-road closure, 18.2 % of the car trips between 7 and 9 a.m. use the affected axis. <!-- source: trace 2026-09-14_11-20_exposition_rocade_lot0bis; the measurement bears on an event since set aside, it gives the order of magnitude, not the value for the five -->

### 7.1.3 Predictions and measurement

For each event and each mode, the expected direction of the displacement is written before the first call, that is twenty signed predictions. The quantity measured is the modal share gap between C2 and C1, paired on the same trips, with an interval obtained by cluster resampling at the person level (§ 4.1).

Over twenty predictions, the bar of the binomial test against chance stands at fifteen concordant signs ($p = 0.021$); fourteen do not suffice ($p = 0.058$). The chapter publishes that rate, **[xx/20 | exp_05a-e]**, and the weighted $\kappa$ on the expected intensity without testing it, twenty items not allowing it.

Two controls bound the reading. The control text gives the amplitude of a modal displacement with no relevant content, **[x.x | C4 − C1]** point, to be compared with the identical replay of the nominal day, which gives the decider's own noise. <!-- source: ticket 080 § 3.1 bis, identical replay ready without code; between-seed dispersion is not measured (§ 6.5), it cannot serve as a noise reference --> The paraphrase gives the share of the displacement that survives the removal of all mobility vocabulary, **[xx]** % of the amplitude of C2.

The predictions fall if the sign rate does not reach fifteen out of twenty, if the control text displaces as much as the article, or if the paraphrase loses the sign of the article on the majority of cells.

![Modal response under the five conditions, five events by four modes](../images/ch7_presse.png)

*Figure 7.1 — Modal share gap with respect to the nominal day, for the five events and the four modes. Each cell carries three markers, raw article, paraphrase and control text, with their interval; the expected sign is watermarked. Condition C5 appears only on the cells where the event reaches the offer.*

## 7.2 Five days, a delay suffered on the second

### 7.2.1 The device

A subsample of the sealed cohort is played three times over five working days in GAMA, in offline mode, with the same calendar, the same weather, the same offer and the same seeds. The draw is by whole households, so that the household's vehicle chain stays coherent, at 200 agents including at least 60 public transport subscribers or captives. <!-- source: docs/paper/methode/experience_plan/ETAPE_3A_PLAN_LONGITUDINAL.md § 4.3 and § 4.6; the size is calibrated on the power of the paired contrast, not on the budget -->

On the second day at 5 p.m., a network failure imposes 45 minutes of delay on the metro users concerned. The incident is declared once and produces two things: a delay actually suffered in the simulation, and an observation written in the agent's own words, never in the form of an instruction. <!-- source: ticket 079, declaration format and content guard in batch 1; an imperative text is refused at load time --> The network is nominal from the third day onwards.

Three conditions share these draws: the agent with memory, the same agent with its memory switched off, and the tabular reference, stateless by construction. The unit of analysis is the exposed agent, the one that lived through the delay; its count is published with the result.

### 7.2.2 What the device predicts

Three mechanisms already in service decide what can be observed, and their constants bound the predictions.

The severity of the incident is computed from what the simulation measures. A delay that saturates the 30-minute cap is worth 0.50 and the network incident 0.20, that is 0.70, the threshold beyond which a memory is served with no context condition. The lifetime of the trace then goes from 2.8 to 14.6 days: three days after the shock, it still weighs 81 % of its initial weight. <!-- source: llm/gravite.py, force = min(S0 × (1 + 6·I), 30) with S0 = 2.8 d; llm/chocs.py § 1; settings.agent.memoire__importance_choc = 0.7 --> The trace therefore does not fade within the window of the experiment, and clock-driven forgetting explains no return.

Evening consolidation can draw a concept from it, which is born with no observation to its credit and is therefore worth 0.50 under Laplace's rule of succession, the threshold below which a concept stops being served. <!-- source: llm/concepts.py, confidence = (obs + 1) / (obs + counter + 2), memoire__confiance_seuil_service = 0.5; measured in ticket 077: 225 concepts out of 231 left at 0.50 --> A single contradiction brings it down to 0.33 and takes it out of service.

Contradicting that belief requires a metro trip without delay. The return therefore happens agent by agent, at the pace of the retries, and not by a common decay.

The predictions follow. On the second day after 5 p.m., the three conditions avoid the disrupted mode, the offer being degraded for all of them. On the third day, the offer having returned to nominal, the share of the disrupted mode among the exposed places the agent with memory below the other two, which stay within the interval of their pre-shock regime: **[xx.x | exp_04a]** against **[xx.x | exp_04b]** and **[xx.x | exp_04c]**. From the third to the fifth day, the return of the agent with memory is monotonic; it is fitted by $\delta_t = A e^{-t/\tau} + c$, whose constant **[x.x]** day and permanent share **[x.x]** point are published with their bootstrap interval over the agents. The permanent share losses recorded after a transport strike, from 0.3 to 2.5 %, serve as an order of magnitude and not as a target.

These predictions fall if the agent without memory shows the same inertia on the third day, if the return is not monotonic, or if the count of exposed agents falls below the declared threshold, in which case the result is reported as inconclusive.

![Share of the disrupted mode among exposed agents, from the first to the fifth day](../images/ch7_hysteresis.png)

*Figure 7.2 — Share of the disrupted mode among exposed agents, three conditions, with intervals. The shock strikes on the second day at 5 p.m.; the offer is nominal from the third onwards.*

### 7.2.3 What memory shows during these five days

The device logs, per exposed agent and per day, whether the memory of the shock was served at the decision, and the operations consolidation applies to the concepts: creation, confirmation, contradiction. <!-- source: memoire_par_jour.csv, choc_par_jour.csv, habitudes_par_activite.csv; docs/arch/mesures-personas.md § 3 --> The prediction is that the return curve follows the cumulative curve of contradictions, and not the age of the trace.

A ten-day pilot on five agents gives the measure of what this prediction demands: 38 creations, 61 confirmations and a single contradiction, that of the agent exposed to the shock on the day itself. <!-- source: run of 2026-09-16, ticket 093 --> If the exposed agents do not retry the disrupted mode, the belief stays in service and the return has no engine; that is a measurable result of the device, on the same footing as the return.

## 7.3 What this chapter carries

The two regimes give a reading of what the 21 variables of the contract do not carry: the reaction to a text published in the morning, and the persistence of a delay suffered the day before. Their reach is bounded by what the device encodes: a single shock, a single model, a tabular condition informed only where the event reaches the offer, and a count of exposed agents that decides what is measurable.

Chapter 8 discusses the limits of the contract and the implications for hybrid designs; the execution cost of the language-model conditions is in chapter 9.

<!-- CROSS-REFERENCE TO CHECK: the French says "chapitre 9", but the cost of a simulated day is § 8.3 of chapter 8, and chapter 9 carries no cost figure since the speed ratio was withdrawn for want of a source. Translated faithfully; the arbitration belongs to the author. -->

---

### Tickets attached to this chapter

- [Ticket 041](../../../tickets/ticket_041_etape_3a_hysteresis_longitudinale.md) — longitudinal protocol, arms, sample size, calendar and pre-registered predictions
- [Ticket 048](../../../tickets/ticket_048_calendrier_de_consolidation_et_echelle_d_oubli.md) — consolidation floor at 10 p.m. and forgetting constant in days
- [Ticket 059](../../../tickets/ticket_059_etape_3b_presse_locale_et_predictions_preenregistrees.md) — five-condition protocol, press corpus and concordance metrics
- [Ticket 063](../../../tickets/ticket_063_campagne_experimentale_hysteresis_longitudinale.md) — longitudinal hysteresis campaign
- [Ticket 064](../../../tickets/ticket_064_campagne_experimentale_presse_locale_et_scoring.md) — local press campaign and scoring
- [Ticket 071](../../../tickets/ticket_071_evolution_memoire_du_code_actuel_a_l_etat_vise.md) — deterministic severity, recall pools and memory lifetime
- [Ticket 077](../../../tickets/ticket_077_la_memoire_apprend_sur_des_observations_fausses.md) — integrity of the observations memory learns from
