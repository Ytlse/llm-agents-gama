# 7. Agent Adaptation to External Shocks

<!-- Dernière mise à jour : 2026-09-22 -->

**Document:** chapter 7 of the AAMAS 2027 paper. It opens on the mechanism the two regimes share, takes the shock suffered before the article read, and closes on the measurements the two have in common.
**Status:** `draft v2.1` (22 September 2026) — mirror of the French `brouillon v2.1`. Three decisions by the author: the severity of an entry is the agent's rating alone in both regimes, the floor set by the measured fact being removed, which the code does not yet do; the choice of shock now carries its reservation in the text; and § 7.4, which announced the measurements common to both regimes, is withdrawn, its only measured column already being in § 7.2.1 and its stratification prediction having moved up to § 7.1.
**Status before:** `draft v2.0` (22 September 2026) — translated from the French `brouillon v2.0`, which replaced the earlier chapter entirely: the § 7.2 of `draft v1.0` described a longitudinal protocol over 200 agents that the device no longer runs.
**Place in the paper:** section 7 of the plan announced in § 1.4 of [`01_Introduction.md`](01_Introduction.md). Outline: [`../plan/PLAN.md`](../plan/PLAN.md). Progress: [`../README.md`](../README.md).
**Convention:** a figure **in brackets** is an empty placeholder, followed by the run that will fill it.

---

The 21 variables of the protocol describe a person, a purpose, an hour and a geometry. None carries what the person has lived through, none takes account of a particular situation, none carries an event of the day. A decider that receives only those 21 inputs cannot answer to anything else.

This chapter puts the same deciders in front of two regimes the survey cannot tabulate: an event suffered the day before, and a press article read in the morning. Lived or read, the information changes what the agent thinks of a transport mode, and with it the agent's travel habits. What is observed is a drop, then a gradual return towards the earlier habits. The point of comparison is a rule-based decider, which suffers nothing and reads nothing, and whose curve stays flat by construction. The chapter claims no realism about the size or the shape of the shift: it shows that an event is taken into account, and by which path.

## 7.1 The mechanism the two regimes share

An event enters the agent's memory after a trip, for what it has just lived through, or on waking, when a press article is put in front of it. Downstream, the chain is the same whatever the regime (§ 3.4).

In both cases the agent rates, on entry, the importance of what is happening to it and its valence, suffered or welcome: an article announcing a new service is rated welcome, an accident is rated negative. That rating, and it alone, sets the severity of the entry, whatever the regime. <!-- source: llm/gravite.py, NIVEAUX, five intensities; MemoryEntry.valence; schema of stm_reflection, fields severity, valence and mode; ticket 100, decisions D3 and D4 -->

In the evening, each member of the household tells the others about their day: their trips, what happened to them, what they read in the morning. That account enters the evening reflection of those who hear it, on the same footing as their own day, and it is their reflection that decides whether they draw a belief from it. The information makes one hop, from the one who lived or read it to those who live with them, and does not travel on. <!-- source: ticket 100, decisions D1 and D2; a provenance field tells a belief heard from a belief lived -->

An effect dies out in two ways, and they are told apart by measurement: by contradiction, when the agent makes the trip again and nothing recurs, or by wear, when the memory stops being served without any denial having come. The prediction bears on the stratum: for agents that keep using the mode concerned, the effect must stop at a dated contradiction, earlier than wear would have ended it; for those that avoid it, it must hold until that wear and no further. A simultaneous extinction in both strata would refute it.

The two regimes differ on entry, and on four points.

| | Shock suffered (§ 7.2) | Article read (§ 7.3) |
|---|---|---|
| Moment | on arrival from the trip, after the decision of the day | on waking, before the first decision of the day |
| Measured fact | a delay suffered in the simulation | none |
| Text | written for the agent, in its own words | quoted as it appeared, translated |
| What the day of the event measures | nothing, the decision precedes the shock | a choice, the agent decides knowing |

The measured fact does not vanish for all that: a delay suffered shifts the day, constrains the trips that follow, and finds its way into what the agent recounts in the evening. It simply carries no weight in the rating the agent gives the event. <!-- ⚠ The code does not do this as of 22 September: gravite_concept applies I = max(I_llm, I_det), documented as NON-NEGOTIABLE. The author's decision of 22 September removes that floor; it is carried to ticket 100 and awaits its code batch. -->

## 7.2 The shock suffered by a single agent

### 7.2.1 The path the effect took

An agent suffers a car breakdown, turns away from the car for fifteen days, then comes back to the level it was at.

Of the four paths by which the past reaches a decision (§ 3.4), one alone carried this effect: the "what has changed recently" block, where the account of the breakdown appears in 75 of the 376 decision prompts, from the day of the breakdown to the fifteenth day that follows, its duration following from the severity of the event instead of being a number of days set by hand. Similarity recall never brought the memory back, and the belief that the evening consolidation drew from it reached no prompt: born of a single event, it has no observation to set against the six that the selection retains, ranked by confidence then by number of observations. No comparator is played against this result and none could be, since none of the twenty-one variables of the substrate moves between the day before and the day after the breakdown: their gap is null by identity, not by measurement. <!-- source: llm_exchanges.jsonl, 75 prompts out of 376, search for the text of both entries in the messages sent to the model; trace_rappel.jsonl, no occurrence among the memories served; llm/noyau.py, bloc_connaissances and duree_service_jours, 15.29 days for a severity of 0.70, a value written before the run in specs/ticket_095/tests.md; 66 of the agent's 80 concepts sit at their birth confidence -->

### 7.2.2 The device

One agent is played twice, once exposed to an incident, once not; what is observed is the gap between the two runs. The protocol provides for several shocks, of different kinds and severities; the one whose results follow is an engine breakdown that imposes a delay on a car trip, then a smaller delay the day after. Each incident produces a delay actually suffered in the simulation and an observation written in the agent's own words. The vehicle is still offered the next day, which is the condition for measuring an arbitration rather than a constraint, and is not what an engine breakdown would produce in the real world. <!-- source: ticket 079, declaration format and content guard; 30 then 20 minutes, that is 0.700 then 0.533; the second day stays below the threshold that opens the text block, so a return could not be attributed to it. The campaign reported here predates decision D4 of ticket 100: the agent does not yet rate the shock on entry, the next one will -->

### 7.2.3 Results

The car is offered as often as before, and stops being taken. On the trips where it appears among the proposed itineraries, the exposed agent retains it 34 times out of 36 before the incident, 12 out of 38 afterwards, then 35 out of 40. The unexposed agent stays at 28 out of 31, 45 out of 49 and 40 out of 46. The itinerary engine proposes the car at the same rate before and after the breakdown: what changes is the use the agent makes of an option it has all along. <!-- source: moves.csv of both runs, column "Modes proposés au LLM", model decisions only -->

![Daily propensity towards the car](../images/tmp_ch7_propension_quotidienne.png)

*Figure 7.1 (provisional) — Probability the agent grants the car, averaged over the decisions of the day. The measurement is daily and cuts the simulation into no phase.*

The propensity falls on the very day of the breakdown, from 90 % the day before to 40 %, then swings between 5 and 52 %. It returns into the band of the unexposed agent, which never leaves 65 to 90 %, on 15 April. The account of the incident, for its part, disappears from the decision prompts after the 13th. One day separates these two dates, and neither is deduced from the service duration: the first is read on the announced probabilities, the second on the text actually sent to the model. <!-- source: moves.csv, column P(Voiture Privée) %; llm_exchanges.jsonl, last occurrence of the account -->

The agent took the car again twelve times during the period, and no contradiction of a belief was recorded: the belief born of the breakdown was not being served, so there was nothing to contradict. The extinction observed is therefore that of the memory wearing out, not that of a contradiction. <!-- source: ticket 095 § 1, zero concept contradiction in the three arms of the 077 campaign; agent_memory_events.jsonl of the exposed run -->

Declared opinions follow the same movement, then return to their earlier level. Asked outside any decision about six criteria, the exposed agent falls on five of them at the milestone that follows the breakdown: the safety of the car goes from 8 to 3, convenience from 9 to 6, comfort from 8 to 5, speed from 9 to 8 and cost from 6 to 5. At the two following milestones, all five have found their starting value again. The environment, which no incident of the device targets, stays at 3 across the four surveys. On the car, the unexposed agent moves on none of the six criteria. <!-- source: affinites_declarees.csv of both runs, Likert scale 0-10, criteria from Adam & Gaudou (2025), one questionnaire per mode, milestones on days 12, 17, 31 and 40 -->

![The six criteria, across the five modes, at the four milestones](../images/tmp_ch7_affinites_tous_modes.png)

*Figure 7.2 (provisional) — Declared opinions, six criteria per mode, exposed agent as a solid line and unexposed agent dashed. The red band marks the breakdown, the vertical line the day its account leaves the context. The environment serves as a control question.*

Public transport, the bicycle, walking and the train offer no such reading. Both agents drift there from one milestone to the next, nineteen of the thirty series for the exposed agent, sixteen for the control, and the movements do not resemble each other from one arm to the other. The car is the only mode where the exposed agent moves and the control does not; that is what makes the gap attributable to the breakdown rather than to the noise of the survey. A return to the starting level on five scales describes an opinion regenerated from the persona as soon as the context stops carrying the incident.

<!-- TODO: the dynamics between the second and the third survey are not observed, and that interval is precisely the one in which the account leaves the context. Moving to a daily survey is decided for the next campaign, ticket 095 Q7. -->

## 7.3 The article read, then told at home

### 7.3.1 The five events

Five articles taken from the Toulouse local press each act through one or more channels. Gusts of the Autan wind above 80 km/h close the city's fenced parks and expose the bridges over the Garonne. A rumour of bedbugs on the fabric seats of the metro and buses leaves the technical offer intact and the credibility of the mode dented. An open-ended strike of refuse collectors makes the pavements of the inner centre impassable without changing their geometry in any way. The street parade of La Machine pedestrianises the centre in front of a dense crowd. The launch of electrically assisted VélôToulouse erases the gradient of the hillsides. <!-- source: docs/paper/sources/actualites/RAPPORT_SCENARIOS_QUALITATIFS_TOULOUSE.md, § 3; the five are retained from a matrix of thirty candidate articles, carried to the appendix -->

None of these five pieces of information has a column in a classical system, and adding one would be complex, and endless, each day bringing a new piece of news.

### 7.3.2 The device

The experiment is played on a few households, over several consecutive days, with memory on. One member per household receives the text in the morning, before their first decision. The articles appeared in French; the five texts are given translated. <!-- source: ticket 059, batch 1; both versions and their provenance live in the corpus manifest. The calendar leaves twelve days before the first publication, the time for a habit to form: it is computed on the last five observations of the same activity (ticket 093) -->

| # | Condition | What the decider receives | What the condition separates |
|---|---|---|---|
| C1 | Agent, nominal day | no article | the reference level of the day |
| C2 | Agent, raw article | the press text as it appeared | the total effect of the event |
| C3 | Agent, control text | a news text with no plausible link to mode choice, of matched length, the same for all five events | the effect of the content from the effect of adding a text |

The control text is a natural-science dispatch, matched in length to each article to within half a percent to eight percent. <!-- source: docs/paper/sources/actualites/articles_txt/MANIFEST.yaml, common control; France 24, 19 September 2026; it does not come from the corpus of thirty, assembled for its link to mobility --> A distant text and a Toulouse news item are not worth the same to someone who lives in the city, and the gap between C3 and C1 carries that reservation.

### 7.3.3 Predictions and how they are measured

For each of the five events and each of the four modes, the modal share must rise, fall, or not move. Those twenty signs are written before the first call to the model.

![Grid of expected signs, five articles by four modes](../images/ch7_grille_signes.png)

*Figure 7.3 — The twenty expected signs, written before the first call to the model. Each cell carries the expected direction of the modal share shift under the raw article with respect to the nominal day, and its intensity as a number of dots. The three cells at zero are predictions of no net shift, which the measurement can refute as it would refute a reversed sign.*

The rating the agent gives the article, on the scale of § 7.1, is set against this grid before it moves at all: it names the modes it judges affected and the direction of the effect. The gap between what it announces and what it does is a measurement in its own right, an agent that announces the right direction without moving having read the text without drawing any consequence from it. <!-- source: llm/gravite.py, five intensities anchored by an observable consequence and one valence; ticket 059 § 5.2 and decision D3 of ticket 100 on the single scale -->

The control text bounds the reading. It gives the amplitude of a modal shift with no relevant content, **[x.x | C3 − C1]** point, to be compared with the identical replay of the nominal day, which gives the decider's own noise. <!-- source: ticket 080 § 3.1 bis, identical replay ready without code; between-seed dispersion is not measured (§ 6.1), it cannot serve as a noise reference -->

<!-- The results figure, the same grid filled with the gaps measured under C2 and C3 with their
intervals, comes with campaign exp_05a-e. It is not called here as long as it does not exist.
The drop-and-return curve is drawn with the same campaign, from the same script as figure 7.1. -->

---

### Tickets attached to this chapter

- [Ticket 041](../../../tickets/ticket_041_etape_3a_hysteresis_longitudinale.md) — longitudinal protocol, arms, sample size, calendar and pre-registered predictions
- [Ticket 048](../../../tickets/ticket_048_calendrier_de_consolidation_et_echelle_d_oubli.md) — consolidation floor at 10 p.m. and forgetting constant in days; closed on 21 September 2026, its remainder is batch F of ticket 095
- [Ticket 059](../../../tickets/ticket_059_etape_3b_presse_locale_et_predictions_preenregistrees.md) — press corpus, sign grid, household population, measurement and figures specific to the press
- [Ticket 063](../../../tickets/ticket_063_campagne_experimentale_hysteresis_longitudinale.md) — longitudinal hysteresis campaign
- [Ticket 064](../../../tickets/ticket_064_campagne_experimentale_presse_locale_et_scoring.md) — local press campaign and scoring
- [Ticket 071](../../../tickets/ticket_071_evolution_memoire_du_code_actuel_a_l_etat_vise.md) — deterministic severity, recall pools and memory lifetime
- [Ticket 077](../../../tickets/ticket_077_la_memoire_apprend_sur_des_observations_fausses.md) — integrity of the observations memory learns from
- [Ticket 078](../../../tickets/ticket_078_partage_de_concepts_au_sein_du_foyer.md) — the six rules of the household channel for beliefs; closed on 21 September 2026, absorbed by ticket 100
- [Ticket 079](../../../tickets/ticket_079_chocs_declares_vecus_par_les_agents.md) — declaration of a shock suffered and of the memory it leaves
- [Ticket 093](../../../tickets/ticket_093_personas_mesurables_et_suivi_des_habitudes.md) — per-simulated-day measurements, habits and concept operations
- [Ticket 095](../../../tickets/ticket_095_duree_d_un_souvenir_et_enquete_du_soir.md) — memory lifetime derived from severity, evening survey, and the consolidation calendar carried over from 048
- [Ticket 100](../../../tickets/ticket_100_un_seul_canal_d_evenement_pour_le_vecu_et_le_lu.md) — a single event channel for the lived and the read: two intakes, one downstream, the evening account in one hop, the rating on entry in both regimes
