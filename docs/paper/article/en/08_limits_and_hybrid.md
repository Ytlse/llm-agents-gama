# 8. Limitations

<!-- Dernière mise à jour : 2026-09-21 -->

**Document:** chapter 8 of the AAMAS 2027 paper. English master; French mirror in [`fr/08_limits_and_hybrid.md`](../fr/08_limits_and_hybrid.md); LaTeX rendering for Overleaf in [`overleaf/08_limits_and_hybrid.tex`](../overleaf/08_limits_and_hybrid.tex).
**Status:** `draft v0.3` (21 September 2026) — § 8.6 is added under ticket 074: the device runs in English, which § 4.1 justifies, and the Western-centric bias English induces has received no counter-measure, the reinforcement of the territorial framing having been set aside so as to change a single variable. The limit is declared and the share of the gap it accounts for is not quantified. One reference enters the chapter, Soegeng et al. (2026).
**Previous status:** `draft v0.2` (21 September 2026) — § 8.5 is added under ticket 051: both memory registers share a single index, the decider under evaluation maintains the semantic register itself, and the routing criterion Figure 8.1 leaves empty is referred to the measurement of habit. No bibliographic reference is added: the anchoring of the automatism versus deliberation distinction lives in `docs/arch/memory-stm-ltm.md`, its notice not having been cross-checked.
**Previous status:** `draft v0.1` (17 September 2026) — first English master, translated from the French `brouillon v0.1` of the same day. The limits published here come from tickets 049 and 057, the inference cost from a measurement of 17 September 2026. Figure 8.1 carries the cascade; its two flow shares are **[xx]** placeholders, to be filled once a routing criterion has been defined and measured.
**Place in the paper:** section of the same number in the plan announced in § 1.4 of [`../en/01_introduction.md`](../en/01_introduction.md). Progress: [`../README.md`](../README.md).

---

## 8.1 The itinerary offer contains no combined trip

OpenTripPlanner is queried mode by mode, and the set of options submitted to the agent therefore contains no mixed itinerary: no car to a park-and-ride then metro, no bicycle to a station then regional train. The survey does count such trips, and the national hierarchy of modes files almost all of them under public transport: 760 of the 770 trips that mix car and public transport, and the 58 trips that mix bicycle and public transport. Part of the target is thus out of reach by construction.
<!-- source: docs/tickets/ticket_049_itineraire_mixte_limite_a_publier.md, § The fact; EMC² 2023 microdata, COEP weighting, trips internal to the perimeter -->

The amplitude of that share reads stratum by stratum, not globally. Over the whole living area, feeder trips weigh 1.41 points of modal share. Related to the public transport target of each ring, the unreachable fraction is 3 % in Toulouse, 22 % in the first ring, 31 % in the second and 28 % in the third. By distance band, it reaches 39 % between 10 and 20 km, 59 % between 20 and 50 km and 64 % beyond. The trips concerned have a median of 11.1 km against 1.9 km for the whole, are return-home trips for 42 % and fixed-workplace trips for 14 %, and 3.1 % of mobile people declare at least one.
<!-- source: idem, § The amplitude, by stratum -->

The direction in which this limit acts was measured over seventeen archived runs, about 50,000 trips. The simulation over-produces public transport exactly where the target is least reachable: between 20 and 50 km, the three language models place 27 to 36 % of the probability mass in public transport for a target of 13 %, and beyond 50 km, 42 to 47 % for a target of 12 %. Neutralising the feeder bound in the score brings nothing to the three language models, at 0.000 point, where it brings 2.17 to 2.19 points to the shortest-duration and all-car floors, and 0.00 to 0.17 point to the four tabular methods.
<!-- source: docs/traces/2026-09-12_10-10_sens_limite_rabattement/; shares by band: gemini-38-f 36 % and 47 %, gemini-31-fl 33 % and 42 %, gemini-35-fl 27 % and 43 % -->

## 8.2 The vehicle chain, the decision horizon and the household fleet

Tracking the position of personal vehicles raises two locks of different natures. The return lock requires coming home with the vehicle taken out in the morning, and it reproduces a regularity of the field: in the survey, 98.5 % of the returns home of a car chain begun in the morning are made by car, and 93.8 % for the bicycle. These constrained returns weigh 18.2 % of the trips in the survey and 18.0 % in the simulated day, with no tuning having aimed at that value.
<!-- source: docs/tickets/ticket_057_audit_et_reflexion_double_lecture_tabulaire.md, § 2.3 -->

The exit lock removes the option of driving from a trip that starts where the vehicle is not parked, and it acts four times more often than in reality. The situation affects 4.2 % of driver trips in the survey. On one and the same cohort, it affects 13.8 to 15.4 % under the expert prompt, 17.7 to 18.0 % for the four tabular methods, 18.7 to 18.9 % under the minimal prompt and 30.9 % at the random floor. The rate orders itself by the decider alone, which a defect of the rule or of the synthetic population would not produce: it measures the cost of deciding a trip without looking at the rest of the day, and the calibrated instruction pays it less than the models fitted on the survey. No decider reaches the level of the field.
<!-- source: idem, § 2.3, table by decider -->

Availability of the household car fleet is approximated by a rule that gives a vehicle to every motorised adult holding a licence, without counting the cars the household declares. Of the 499 households of the sealed cohort, 90 have more drivers than vehicles, which makes 268 personas eligible for concurrent circulation. Replacing their decisions with those taken under the full offer moves the car share from 52.0 to 53.2 % for a target of 55.9 %, degrades the stratification, and costs 0.073 point of composite. That value sits eighteen times below the resolution of the instrument, which is 1.3 points per decider.
<!-- source: idem, §§ 6 and 7; resolution: § 4.1 -->

The four tabular methods have read 39,203 real trips of the local survey, and the agent has read none. The comparison protocol declares this imbalance rather than claiming parity of information: parity bears on the description of the current trip, and the agent additionally receives its agenda and the weather of the coming time slots. What the device establishes is that an agent does something a trip-by-trip classifier cannot do, not that it does better on equal information.
<!-- source: docs/tickets/ticket_046_asymetrie_informationnelle_du_contrat_d_evaluation.md, arbitration of 2026-09-17; § 4.3, rule 1 -->

Renormalising the tabular distribution over the viable itineraries alone finally rests on the assumption of independence of irrelevant alternatives. Removing a physically unavailable mode and recomputing the mass over the remaining modes assumes that the ratio of probabilities between two retained modes does not depend on the removed mode, which the multinomial logit satisfies by construction and which the other three methods do not guarantee.

## 8.3 What a simulated day costs

A weekday on 1,000 personas produces 3,299 trips, of which 3,161 are usable and 3,154 decided. The 702 trips that offer only one itinerary give rise to no model solicitation, and the reference day requires 2,108 of them, a run with no reuse of an earlier day requiring of the order of 2,500. The gateway groups eight of them per request, and the day fits in some 270 requests. A decision carries 620 to 840 input tokens depending on the model and the instruction variant: the person, the weather, the chain constraints and the detail of at most six itineraries, the shared preamble being amortised over the whole batch. Output runs from 190 to 790 tokens, the spread coming from the reasoning trace, billed outside the completion cap for the models that produce one. The reference day thus consumes 3 million tokens.
<!-- source: docs/traces/2026-09-21_13-10_cout_jev_vs_gemini/ — erratum to the trace of 2026-09-17 11:26, which aggregated per HTTP request and not per decision; compteurs.json of exp_gemini-35-fl_proexp05_…_t0 run 2026-09-15_07_02_03 for the 2,108 solicitations; tokens per decision aggregated over the llm_exchanges.jsonl logs since 2026-09-14, the agent count being read in each response: gemini-3.5-flash-lite expert 646 in and 790 out, gemini-3.1-flash-lite 839 and 204, mistral-large-3 695 and 191; mean batch of 7.9 agents per request for gemini-3.5, 4.0 for gemini-3.1, 5.9 for mistral-large-3. Direct measurement on a complete arm, with no product: 2,442 decisions, 309 requests, 3.40 M tokens -->

The ablation experiments run with memory disabled, so this budget covers no consolidation. A short consolidation requires 1,292 input tokens and 388 output, a multi-day self-reflection 2,313 and 335. On the runs that switch memory on, an agent triggers 1.25 and 0.27 of them per simulated day. Related to the 894 mobile personas of the cohort, a day with memory active would add about 2.5 million tokens.
<!-- source: idem, tokens per consolidation and not per request, the batches averaging 3.28 and 1.37; frequencies measured on experiments/archive/2026-09-16_15_58, 5 personas and 11 simulated days; 894 mobile: MANIFEST.yaml, 106 immobile out of 1,000. A consolidation fires for every agent that lived through the day, hence the 894 mobile and not the 868 people that chapter 6 and the appendix count: those 868 carry at least one retained decision, the other 26 having only trips whose origin and destination coincide. Checked on decisions.jsonl of run 2026-09-15_07_02_03: 894 people present, 868 with a retained decision. -->

Moving to the survey perimeter changes the order of magnitude. The 453 municipalities hold 1,320,000 inhabitants aged 5 and over, that is 4.36 million daily trips at the rate of 3.30 trips per person measured on the cohort. At the ratio of one solicitation per 1.5 decisions observed here, a simulated day would require 2.9 million solicitations, that is some 370,000 requests, and 2.6 to 4.2 billion tokens depending on whether the decider produces a reasoning trace. The per-minute and per-day quotas of commercial gateways already dictate the run time on 1,000 personas, as chapter 9 reports.
<!-- source: 1,320,000 inhabitants: docs/arch/perimetre-population.md; 3.30 trips: MANIFEST.yaml; the detail of the computation is in the trace of 2026-09-17 11:26 -->

This cost commands that language deliberation be reserved for the situations where it brings something measured. Chapter 5 sets aside, for the same reason, the combinatorial optimisation of the instruction, which would have required 80,000 inferences for a marginal gain, and chapter 7 delimits the two regimes where deliberation produces a behaviour that no tabulated variable carries.

## 8.4 What these limits imply for a cascade architecture

The measurements of chapter 6 and the cost of § 8.3 lead to a division of labour rather than to the substitution of one paradigm for the other. A first deterministic stage prunes the alternatives that are physically or legally impossible: no licence, vehicle parked elsewhere, no offer. A second tabular stage handles routine trips in the nominal regime, at zero token cost and with the alignment § 4.4 measures. A third stage calls the language model only on rupture: an unlisted incident, local textual information, a delay that puts the next activity in question.

```
                         [ Trip to be decided ]
                                     │
                                     ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │ Stage 1 — Deterministic filter                                       │
 │ Licence, vehicle parked elsewhere, no offer on the mode              │
 │ ──► removal of the impossible alternatives                           │
 └───────────────────────────────────┬──────────────────────────────────┘
                                     │ eligible options
                                     ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │ Stage 2 — Tabular engine                       flow share: [xx] %    │
 │ Routine trip, nominal network, no text to interpret                  │
 │ ──► immediate decision, no token consumed                            │
 └───────────────────────────────────┬──────────────────────────────────┘
                                     │ rupture detected
                                     ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │ Stage 3 — Generative decider                   flow share: [xx] %    │
 │ Unlisted incident, local textual information, delay putting          │
 │ the next activity in question                                        │
 │ ──► deliberation in language, memory update                          │
 └──────────────────────────────────────────────────────────────────────┘
```

*Figure 8.1 — The three stages of the cascade. The two flow shares are to be built with the results: they presuppose an explicit routing criterion between routine and rupture, and its measurement on the sealed cohort.*

The share of the flow that the second stage would absorb is not measured to date. No counter of the device separates routine decisions from rupture decisions, and the reuse rate of archived decisions does not answer the question, since it describes a resumption of execution. Quantifying the reduction in calls therefore presupposes the routing criterion of Figure 8.1, then its application to the 3,154 decisions of the reference day.

Planning at the scale of the day answers the exit lock of § 8.2. The agent already receives its agenda, and what it lacks is to commit, from the first departure of the morning, to the whole loop, so that the morning choice carries the condition of the return. The measured blocking rate, 13.8 to 15.4 % under the expert prompt against 4.2 % in the field, gives the magnitude that such planning should reduce.

The household is the only social group of the simulation that carries a stable identifier. Of the 499 households of the cohort, 287 have several members present and 788 personas live with at least one other simulated agent. Their members differ by trip purpose in 223 households, by driving licence in 133, by public transport pass in 122. Arbitrating the shared vehicle, the school drop-off and the joint shopping trip belongs to a negotiation between personas of the same household, where the current device allocates independently.
<!-- source: docs/tickets/ticket_078_partage_de_concepts_au_sein_du_foyer.md, § 0, measured on data/population/toulouse_population_1000_AAMAS_v6.json -->

Feedback from modal choices onto the physical network remains outside the evaluated device, which handles an exogenous itinerary offer. Connecting it would allow the study of how incident memory and itinerary reports compose into congestion and public transport occupancy. Distilling the reasoning traces towards compact models executable locally would finally lift the dependence on remote gateways that § 8.3 quantifies, and would make individual mobility simulation compatible with the statistical confidentiality attached to its data.

## 8.5 The two memory registers share a single store

Long-term memory separates lived traces from concepts by their forgetting regime and not by their store. Both registers live in the same per-agent vector index, with the same embedding and the same retrieval path; what sets them apart is an attribute of the entry, which governs the temporal component of the retrieval score: a decay since the last recall for a trace, a confidence built from the counts of confirmations and counter-examples for a concept. A semantic store of its own, indexed for itself and maintained by inference over observations rather than by a clock, is a different architecture, and the device evaluated here does not put it to the test.
<!-- source: services/llm-agents/llm/longterm.py, est_episodique branch of the temporal score ; llm/concepts.py, confiance() ; single ChromaDB collection "memory_collection" -->

The semantic register is moreover maintained by the decider under evaluation. At each consolidation the model is shown the concepts neighbouring the mode-purpose pair at hand, and it designates the one it creates, confirms, refines or contradicts; that designation replaces a fixed similarity threshold, for which no value is measured on the embedding in use, but it makes the upkeep of the memory depend on the same policy as the decision. A decider that handles these four operations poorly degrades its own memory, and nothing in the protocol of chapter 5 separates the two effects.
<!-- source: docs/arch/memory-stm-ltm.md, batch 3 ; docs/tickets/ticket_071_evolution_memoire_du_code_actuel_a_l_etat_vise.md, § 2.3 -->

The routing criterion that Figure 8.1 leaves empty is that of habit. No rule requires an agent to take yesterday's mode again: repetition, where it appears, comes from the recall of its own trips. Its onset is therefore an observable quantity, the decay of the entropy of a single agent's choices across simulated days, and the five days of § 7.2 provide the window. Encoding the automatism before measuring it would produce the routine instead of observing it, and would deprive the second stage of the cascade of the criterion that triggers it.
<!-- source: docs/tickets/ticket_051_reflexion_architecture_cognitive_memoire.md, § C ; ticket 071 § 2.9, author's arbitration of 2026-09-11 and 2026-09-14 -->

## 8.6 The device runs in English with no reinforcement of its territorial framing

The system prompt, the rendering template and the cohort's traits are in English, and the prompt anchors the territory only by naming the city. Prompting in English gives the best overall performance but induces a Western-centric bias: cultural knowledge is present in local-language representations and poorly retrieved from English (Soegeng et al., 2026). Enriching the prompt's framing, with the urban structure, the transport operator and local orders of magnitude, was the available lever against that bias; it was set aside so that the move to English would change a single variable and stay attributable. The share of the territorial gap of chapter 6 that this bias accounts for is therefore not quantified: no run in French bears on the set that underpins those measurements.
<!-- source: docs/tickets/ticket_074_bascule_anglaise_archivage_et_reprise_de_campagne.md, § 3.3 and arbitration Q3 of 2026-09-14 ; the justification of English is in § 4.1 -->

---

### Tickets attached to this chapter

- [Ticket 046](../../../tickets/ticket_046_asymetrie_informationnelle_du_contrat_d_evaluation.md) — The agent sees its day, the tabular model does not: what the protocol declares
- [Ticket 049](../../../tickets/ticket_049_itineraire_mixte_limite_a_publier.md) — The mixed itinerary does not exist: publish the limit, and say which way it leans
- [Ticket 051](../../../tickets/ticket_051_reflexion_architecture_cognitive_memoire.md) — Reflection and epistemological audit of the memory architecture: § 8.5 carries its prospect, and habit is measured there instead of being encoded
- [Ticket 057](../../../tickets/ticket_057_audit_et_reflexion_double_lecture_tabulaire.md) — Audit of the chain constraint, return lock and exit lock
- [Ticket 060](../../../tickets/ticket_060_formalisation_architecture_hybride_et_perspectives.md) — Formalisation of the hybrid cascade architecture and perspectives
- [Ticket 074](../../../tickets/ticket_074_bascule_anglaise_archivage_et_reprise_de_campagne.md) — Switch of the device to English: § 8.6 carries the bias it induces and the absence of a counter-measure
- [Ticket 078](../../../tickets/ticket_078_partage_de_concepts_au_sein_du_foyer.md) — The household as a channel: what one member learns
