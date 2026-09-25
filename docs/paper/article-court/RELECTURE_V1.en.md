# Review v1 of the drafted sections — corrections to apply

English rendering of `RELECTURE_V1.md`, which remains the reference. Review dated 2026-09-22
of the eight files in `sections/`, done as an AAMAS reviewer with no access to the history.
**Assumption: ticket 103 returns its scenario 1**, and the four `[c2]` placeholders of § 5.1
and § 5.3 are filled with its scores. Nothing below concerns those four gaps; everything else
is to be done, in the order of § 11.

Overall grade as it stands: **13/20**, against 7/20 for the long version. The tutor's two
complaints are answered. What remains is local substance to correct, and finishing.

Each item carries: the passage, the correction, the cost in words, the test. The writer
applies it, updates the `<!-- source: -->` comment concerned, and returns the report block of
rule 20.

---

## 1. Global corrections

**G1 — Thousands separators.** 65 numbers carry the French thin space (*1 000*, *3 299*,
*39 203*) against 13 with the English comma (*11,329*). Convention: comma everywhere
(*1,000*, *3,299*, *39,203*), tables and abstract included.
*Test:* `grep -c "[0-9] [0-9]\{3\}\b" sections/*.md` returns 0.

**G2 — Missing report block.** None of the eight files carries the `=== SECTION REPORT ===`
of rule 20. The agent's flags live only in the HTML comments, one by one. Add the block at
the end of each file, as an HTML comment, filled for the current state.
*Test:* `grep -l "SECTION REPORT" sections/0*.md` returns all eight files.

**G3 — The replacement tic.** The colon is gone; the two-clause sentence coordinated by
", and" with a short tail has taken its place. *"…and no further."*, *"…and not a day
longer."*, *"…and it stops being taken."*, *"…and this paper supplies them."*, *"…and the
language model intervenes only there."* Over five pages it reads as a string of maxims.
Break one in three: a subordinate clause, two sentences, or a rewording.
*Heuristic test:* `grep -c ", and [a-z ]\{3,30\}\.$" sections/*.md` drops by a third.

**G4 — Compile and count pages.** 5,930 words of prose (+14 % on 5,200), five figures, four
tables. Nobody has compiled. Fitting in 8 pages is the constraint that decides every cut of
§ 10; measure it before polishing.
*Test:* the PDF is 8 pages at most, references excluded, with no `??`.

**G5 — The ±1.3 resolution is stale.** § 4.3: *"That estimate predates the correction of the
scoring set."* That figure is the yardstick of the whole § 5 ("1.5 to 5.5 times the cohort
resolution", "0.56 against ±1.3"). Recompute it on the corrected set with the existing
cluster resampling (script of ticket 096 lot 2, 2,000 replicates), then replace the value and
delete the reservation sentence. One hour of machine time.
*Test:* the word *predates* is gone from § 4.3; the new value appears in §§ 4.3, 5.1, 5.2.

---

## 2. § 0 — Abstract

**A1.** *"Verbalised deliberation earned its place outside that ordinary day."* The past tense
reads as an event, not a result. → *"Verbalised deliberation earns its place outside that
ordinary day."*

**A2.** Once § 5.3 is filled: *"matches them for a fiftieth of the cost"* takes its measured
out-of-sample status, without a figure if the 300-word budget does not allow one
(*"matches them on a second cohort, for a fiftieth of the cost"*).

**A3.** G1 applies: *1,000*, *3,299*, *21*.

---

## 3. § 1 — Introduction

**I1 — Platform and lineage, absent.** Neither GAMA nor the lineage of the system. Add at
the end of § 1.3, before the contributions paragraph:
*"The agents live in a GAMA simulation of the Toulouse area, with its real networks and
timetables, in the line of the GAMA–OpenTripPlanner–LLM architecture of Vu et al. (2025)."*
(+25 words.) The citation `vu2025modeling` is already in the `.bib`.

**I2 — Duplicate definition.** *"a decision-maker being anything that turns a trip description
into a probability over the options offered"* appears in § 1.3 **and** at the head of § 4,
word for word (rule 8). Keep the one in § 1.3, recast as a full clause:
*"We call decision-maker anything that turns a trip description into a probability over the
options offered."* Delete the one in § 4 (−20 words).

---

## 4. § 2 — Related work

**R1 — One behavioural reference, and it is a self-citation.** § 2.1 rests "departures that no
survey records" on Adam & Gaudou 2025 alone, a co-author of the paper. Add two references on
habit and inertia in mode choice — candidates to verify: Gärling & Axhausen 2003
(*Transportation*, special issue on habit), Verplanken et al. 1997 (habit and mode choice).
One sentence, +25 words, two `.bib` entries to create.

**R2 — CitySim and MATSim have vanished.** CitySim is the only other city-scale LLM system;
it is exactly the gap this paper fills. Restore in § 2.2, after Liu et al.: *"CitySim (Bougie
& Watanabe, 2025) scales such agents to a city and validates them on time use, but no
experiment confronts a simulated modal split with an observed one. Earlier simulators such
as MATSim (Horni et al., 2016) reach equilibrium by scoring plans, and the agent does not
deliberate."* (+50 words.) Both keys exist in the `.bib`.

**R3 — The debate on written reasoning is not cited.** § 2.3, last paragraph: *"The gains
reported for written reasoning come from tasks that have one verifiable answer."* This is the
sentence that shields § 5.3 from "known", and it has no source. Cite Wei et al. 2022
(chain-of-thought prompting) and one work on the conditions under which written reasoning
helps (Sprague et al. 2024, *To CoT or not to CoT*). Two `.bib` entries to create, +10 words.

**R4 — Name GAMA in Alves.** *"They couple a multi-agent platform to a language-model
module"* → *"They couple the GAMA platform to…"*. Anonymity is no reason: a platform does not
de-anonymise.

---

## 5. § 3 — The agent

**T1 — The platform, named and described (+110 words).** § 3.1 says *"A multi-agent platform
carries the world"* and *"the routing engines"*. Without the names and what they bring, a MAS
reviewer asks where the multi-agent system is, and § 6 loses its ground: the breakdown is a
fact of the simulation, not an injected text. Rewrite the first paragraph:

> *Three components carry the simulation. A GAMA multi-agent simulation carries the world:
> the real geography of the 453 communes, the transport networks, the clock, and the physical
> execution of every trip. OpenTripPlanner produces the public transport itineraries on the
> real timetables; a shortest-path computation on the OpenStreetMap graph produces the direct
> trips by foot, bicycle and car. A controller carries the agent lifecycle, builds the options
> available at the departure hour, and holds the clock so that no agent leaves before it has
> decided. A decision module produces the choice, and the language model intervenes only
> there.*

The colon after "the world" is the only one in the paragraph (R2). The next paragraph
(*"The loop closes…"*) stays.

**T2 — The household hop, one sentence in § 3.3.** The mechanism is described in § 6.2 and
then declared not exercised. Its design home is here: *"In the evening each household member
tells the others their day, and that account enters the hearers' reflection."* (+20 words.)
Then N1 shortens § 6.2 by as much.

---

## 6. § 4 — The bench

**Q1 — Delete the duplicate definition** (see I2). −20 words.

**Q2 — The cohort release claim is not settled.** *"We release the protocol, the code, the
seeds and the synthetic cohort itself. The status of the other resources derived from the
survey is not settled."* The cohort comes from eqasim, which reads the survey; its status is
that of the "other derived resources" (`SOUMISSION_AAMAS_2027.md` l. 81). Nobody has made
that commitment. → *"We release the protocol, the code and the seeds. Whether the synthetic
cohort, derived from the survey through the synthesis chain, can be released is not settled."*
*Test:* the words *cohort itself* are gone.

**Q3 — After G5**, replace the resolution value and remove *"That estimate predates the
correction of the scoring set."*

**Q4 — Table 1, once lot B of ticket 103 has returned:** replace the two *[replay pending]*
with the measured ranges; the *not replayed* entries stay. The *(in sample)* label on the Jev
expert row stays, since it is a c1 score; add under the table: *"The out-of-sample
measurement of that row is in Section 5.3."*

---

## 7. § 5 — Results

**F1 — § 5.1, after lot B:** fill *[c2, inter-seed range per key decision-maker]*; rewrite
the two sentences *"The minimal-prompt condition has not been replayed… The effect of the seed
on the sign of the paired differences reported here is therefore not measured"* according to
Q3 of the ticket: either "no published difference changes sign across seeds", or the list of
those that do, which then leave the text.

**F2 — § 5.2, the 15–19 stratum to Appendix F (−40 words).** Three sentences that feed none of
the four claims of § 5. Keep: *"One stratum resists every decision-maker, the 15–19 year olds
(Appendix F)."*

**F3 — § 5.3, after lot A:** fill the three placeholders. **The closing sentence of the second
paragraph is chosen after reading Q2**: if `prompt_expert_32` improves gemini as much as it
improves Jev, write that the effect is in the text; if it improves Jev alone, write that the
effect is in the pair. Do not write the sentence before the scores.

**F4 — § 5.4, Table 3: two Jevs under one label.** The *Typed classifier* row at 64.3 % is the
**transferred-instruction** arm (`prompt_expert_05`, Appendix I.1 bis "Jev, consigne
gemini-3.5"). § 5.3 speaks of the classifier under **its own tuned instruction**, which scores
64.7 % in the same appendix. The reader believes they are reading one decision-maker. Put both
rows, labelled *Typed classifier, transferred instruction* (64.3) and *Typed classifier, own
instruction* (64.7; cross-entropy 0.464; bike and walk recall to take from Appendix I.2). Both
sit under the floor, and the claim comes out stronger. The text that follows (*"It reaches
64.3 % where the floor reaches 66.7 %"*) then names the arm. +15 words.

**F5 — § 5.4, the 93.4 % declared as not recomputed.** *"a figure carried from the earlier
manuscript and never recomputed independently"*: honest, and not publishable. Find the
`metrics.json` of the variant (the one whose distance was reconstructed from the declared
duration) and recompute `accuracy_weighted`. If the source is not found within two hours, the
whole paragraph goes (−90 words) and the measurement lesson moves to § 7.2 as one sentence
without a figure.

**F6 — § 5.4, check the 8.3.** *"The median distance between two agent distributions is four
times the distance between two tabular ones, 39.0 points against 8.3."* The 39.0 is in
Appendix H.5 (row expert gemini-3.5 / gradient boosting). The 8.3 must be in the same table,
on a named tabular pair; otherwise the sentence goes.

---

## 8. § 6 — The non-tabulated regime

**N1 — The household hop, shortened (−40 words).** § 6.2 describes it in four sentences and
then says *"The single-agent case below does not exercise this step."* After T2, two sentences
suffice: the mechanism exists, it is not exercised here.

**N2 — Number the frequency table**: *"Table 4 — Car taken when the car is offered…"*, for
consistency with the other three. It is a fourth table: if G4 returns more than 8 pages, it
becomes a sentence again (*"94 %, 32 % then 88 % of the trips where the car was offered,
against 90, 92 and 87 % for the control"*).

**N3 — § 6.1, a repetition.** *"No comparator can be run against this result, and none could
be."* repeats the previous sentence. Delete (−12 words).

---

## 9. § 7 — Implications

**P1 — Who rates the severity.** § 6.2 says that in the traced case *"that severity came
declared with the incident"*; § 7.1 writes *"The language model receives what no variable
carries, rates it, and writes it into memory."* § 7.1 credits the model with a step that § 6
says was not exercised. → *"The language model receives what no variable carries and writes
it into memory; rating its severity is its task in the current design, and the traced case did
not exercise it (Section 6.2)."*

**P2 — § 7.2, after lot B:** *"one agent, one event and one seed"* stays true for § 6; add one
sentence on what the three seeds of § 5 cover and do not cover.

---

## 9 bis. What the text tells about itself, and nobody wants to read

Two families of sentences got through the previous review, and rule 14 of the agent did not
name them. **The paper's own history**: what was found, corrected, recomputed, what was done
in what order. **Implementation justification**: why the system is built the way it is, when
the answer changes nothing in what the reader must understand. The `article-verrou` charter
forbids both (substance rule 3: fabrication instead of measurement). A reviewer reads either
a confession or a development log.

The sorting below keeps what answers a real objection (the reader *will* ask why the car is
still offered after a breakdown) and removes what answers only the author.

### The paper's own history — to remove

| § | Passage | Correction | Words |
|---|---|---|---:|
| 4.3 | *That estimate predates the correction of the scoring set.* | Already G5/Q3: recompute, then remove the sentence. | −10 |
| 4.4 | *The typed classifier's instruction was tuned differently, and it required a second cohort. Its mutations read the classifier's gaps on the cohort that scores it, so its score there is in sample. We therefore measure every published crossing…* | Four sentences of minutes. → *The classifier's instruction was tuned on the first cohort; every crossing of models and instructions is therefore measured on a second cohort, which shares no persona with the first.* The "in sample" reservation stays in the row label of Table 1. | −35 |
| 4.4, Table 1 caption | *The typed classifier's expert prompt was tuned on the cohort that scores it.* | Repeats the *(in sample)* row label. Remove. | −12 |
| 5.2 | *The expert text was tuned against gemini-3.5 on a calibration population drawn apart from the scored cohort. Its score here is therefore out of sample for that model.* | Already said in § 4.4 (*tuned against one language model on a separate calibration population*). Keep in § 4.4, remove here. | −25 |
| 5.4 | *One earlier variant shows what a decision-maker scored in the wrong place looks like. Scored on the survey it reached 93.4 % accuracy, a figure carried from the earlier manuscript and never recomputed independently. In simulation it produced the worst composite of that campaign, 9.28 against 7.40 for the published condition, on the reading that keeps every decision. Excluding single-option trips the two values become 11.31 and 10.07, so the ordering holds and the margin falls from 1.88 to 1.24 points.* | The whole paragraph is the debugging log: "earlier variant", "that campaign", "the published condition", "carried from", and a robustness check on two readings. The lesson is a result, not a confession. → *A variant whose distance input had been reconstructed from the declared travel time reached 93.4 % accuracy on the survey and the worst composite in simulation, 9.28 against 7.40: the reconstructed distance carried the mode. We therefore score a decision-maker where it is used, not where scoring is convenient.* Conditional on F5 (the 93.4 recomputed). | −60 |
| 6.2 | *…and rating it is the language model's task in the current design.* | "in the current design" is system, not result. → *In the run below, the severity was declared with the incident rather than rated by the model.* | −5 |
| 6.3 | *Both runs keep memory enabled, where every measurement of the bench ran with memory disabled.* | § 3.3 already says the bench runs with memory off. → *Both runs keep memory enabled.* | −10 |
| 5.1 | *The minimal-prompt condition has not been replayed under those seeds. The effect of the seed on the sign of the paired differences reported here is therefore not measured.* | Progress status, not result. Disappears with F1; if a seed is still missing at submission, one sentence in § 7.2 and nothing in § 5. | (F1) |

### Implementation justification — to remove or reduce

| § | Passage | Correction | Words |
|---|---|---|---:|
| 5.3 | *The cheaper decision-maker sends the larger input. The typed classifier sends 1 050 input tokens per decision against 629 for the language model, its instruction being resent whole at every call. The gap comes from the tariff rather than from the volume, at 0.042 dollar per million input tokens with the output not billed.* | Why the cheaper one sends more tokens, the cache, the tariff: nobody reads a paper for that. → *At an equal load of 23,026 decisions the classifier costs 1.06 dollar against 49.28, a factor of about fifty.* The token/tariff detail goes to Appendix I. | −45 |
| 4.4 | *We estimate the four at strict parity, on one file with one split.* | "one file" means nothing to the reader. → *estimated on the same survey partition.* | −5 |
| 4.4 → 5.3 → 0 → 7.3 | *under a fixed output type, writing nothing* / *under a fixed output type, and it produces no sentence* / *reads the same context under a fixed output type, and writes no text* / *reads the same context and writes nothing* | The typed classifier is defined four times. One definition in § 4.4; then *the typed classifier*. The abstract keeps its own, being a standalone text. | −25 |
| 5.1 + 5.3 | *We report this as an observation on two versions of one model family, not as a property of language models in general.* / *We state that as a result on this bench, not as a property of language models.* | The same defence twice. Keep the one in § 5.3, where it matters; in § 5.1, *on two versions of one model family* as an aside and nothing more. | −15 |
| 2.3 | *…and we claim no agreement with its results on games.* | A defence against an objection nobody raised (§ 2.3 already says SILICA measures games). Remove the clause. | −10 |
| 6.3 | *The car remains offered the next morning, the condition for measuring an arbitration rather than a constraint. A real engine failure would immobilise the vehicle; this one does not.* | The first sentence answers a real objection: keep, compressed. The second is the limitation: once, in § 7.2. → *The car remains offered the next morning, so that what we measure is an arbitration and not a constraint.* | −15 |
| 7.1 | *We give no share of trips per stage either, since no counter of ours separates an ordinary decision from a disrupted one.* | "no counter of ours" is a tooling excuse. → *We do not estimate the share of trips each stage would take.* | −10 |

### What stays, and why

- § 3.2 *The options are listed in a random order, so that rank does not become preference*:
  a control against a published bias (SILICA), one clause. Stays.
- § 4.2 *Ranking alone would send every persona of one profile into the same mode*: the reason
  for rule 2, which the reader must have. Stays.
- § 4.3 *Trips of one person are not independent, so every interval comes from resampling
  clusters at the person level*: method, not justification. Stays.
- § 4.4 the sentence on the mutations of the expert prompt: that is reproducibility, one
  sentence. Stays.

**Total for this section: −282 words.** It pays for the +255 of the platform (§ 10).

---

## 10. Budget and order of cuts

| Additions | | Cuts | |
|---|---:|---|---:|
| T1 platform | +110 | Q1 duplicate definition | −20 |
| R2 CitySim, MATSim | +50 | F2 15–19 stratum | −40 |
| I1 lineage | +25 | N1 household hop in § 6.2 | −40 |
| R1 habit references | +25 | N3 repetition § 6.1 | −12 |
| T2 household hop in § 3.3 | +20 | Q2 release | −10 |
| F4 Jev row | +15 | | |
| R3 CoT | +10 | § 9 bis, the paper's history | −157 |
| | | § 9 bis, implementation justification | −125 |
| **Total** | **+255** | | **−404** |

Balance **−149 words → about 5,780 words of prose, +11 % on budget**, inside the 15 % margin.
G4 still decides. If the PDF exceeds 8 pages, cut in this order, stopping as soon as it fits:

1. § 5.2: the seven car-share values per band become "rises by six to seven points in every
   band between one and fifty kilometres" (−35).
2. § 6.4: Table 4 becomes a sentence again (N2) (−30 and one float).
3. § 4.3: the paragraph on the two accompanying readings becomes one sentence (−40).
4. § 5.1: the paragraph "The backbone model weighs as much as the instruction" loses its
   second sentence (−20).
5. § 5.4: F5, if the 93.4 is not recomputed (−90).

---

## 11. Execution order

1. **G1** — mechanical, five minutes, first so as not to reread twice.
2. **Q2, F4, F5, P1, N3** — the local substance corrections. One hour.
2 bis. **§ 9 bis** — remove the paper's history and the implementation justifications. Before
   the platform: these cuts are what pays for it.
3. **T1, T2, I1, R2, R4** — the platform. The only additions that change how a MAS reviewer
   reads the paper.
4. **Q1, F2, N1** — the cuts that pay.
5. **G5** then **Q3** — the recomputed resolution.
6. **R1, R3** — two `.bib` files to create, four entries.
7. **G3** — the tic, in a whole-text rereading.
8. **When ticket 103 returns: F1, F3, Q4, A2, P2.**
9. **G2** — the report blocks, on the final state of each section.
10. **G4** — compile, count, apply the cuts of § 10 if needed.
11. Only then, the French pass.
