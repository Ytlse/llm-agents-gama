# 4. Decision-Maker Prompts, Output Schemas, and Decision Traces

This chapter presents the complete prompts, output schemas, and inference traces evaluated in the benchmark. We reproduce the three prompts and follow one trip decision across three architectures.

## 4.1 Input Delivery and Message Architecture

A language model receives two messages. The system message contains the prompt and the expected JSON schema. The user message describes the persona, the environmental context, and the candidate itineraries.

The typed classifier receives the identical prompt, truncated before the output instructions. Its structured input schema takes their place. Every model runs at temperature $\tau = 0.0$ and top-p 1.0.

Table 4.1 lists the repository files storing these components.

*Table 4.1. Storage locations of prompt and schema files.*

| Element | Repository file path |
|---|---|
| The three prompts | `packages/mobility_llm/src/mobility_llm/prompts/prompts.yaml` |
| The user message template | `packages/mobility_llm/src/mobility_llm/categories/itinary_multi_agent/template.md.j2` |
| The JSON output schema | `packages/mobility_llm/src/mobility_llm/categories/itinary_multi_agent/output_schema.json` |
| The classifier input wrapper | `services/llm-agents/experiences/decideur_typesafe.py` |

## 4.2 The Minimal Prompt

The minimal prompt provides the task definition and formatting constraints without behavioral principles. It contains 82 words under key `prompt_minimal_02`.

```text
Select the optimal travel mode taking the persona into account.

[Output instructions]

1. Analyse the profile.
2. Do not rule out any option: assign to EACH proposed option, by its index, the probability in % that this persona picks it — the higher the better it suits them, 0 if it is impossible for them. The sum must be exactly 100.
3. Return only a valid JSON object — no markdown, no extra text.
4. Justify the distribution in one concise sentence.
```

## 4.3 The Expert Prompt

The expert prompt introduces four situational trade-off principles. It contains 277 words under key `prompt_expert_05`.

```text
Select the optimal travel mode taking the persona into account.

Situational trade-off principles:
- Chain friction: Reconstruct the real door-to-door duration (access walk, waiting, in-vehicle trip, egress). If the access walk accounts for most of the direct trip in exchange for a few minutes on board, the traveller prefers the simplicity of walking straight there, with no interchange and no waiting.
- Autonomy of older people: For elderly or frail people, a continuous, unhurried walk at one's own pace is the natural mode of independence for short distances, against the strain and stress of public transport (jolting, risk of falling, steps to climb, standing while waiting with no bench).
- Carrying logistics: Take into account the physical constraint of loads (shopping, heavy bags, carrier bags). Carrying loads on public transport is off-putting; the trade-off leans towards direct access with no interchange (an immediate neighbourhood walk, or the boot of a private vehicle).
- Working people's life time: For a working person facing a tightly scheduled day, the time taken away from personal life has critical value. Faced with public transport links that significantly increase the duration or impose multiple interchanges, the traveller prefers the efficiency and schedule control of their available vehicle.

[Output instructions]

1. Analyse the profile through these principles.
2. Do not rule out any option: assign to EACH proposed option, by its index, the probability in % that this persona picks it — the higher the better it suits them, 0 if it is impossible for them. The sum must be exactly 100.
3. Return only a valid JSON object — no markdown, no extra text.
4. Justify the distribution in one concise sentence.
```

## 4.4 The Typed Classifier Expert Prompt

The typed classifier prompt modifies the chain friction bullet to articulate both sides of the trade-off. It contains 318 words under key `prompt_expert_32`.

```text
- Chain friction: Reconstruct the real door-to-door duration on both sides — access walk, waiting, in-vehicle trip and egress on one; the unbroken walking effort on the other. If the access walk accounts for most of the direct trip in exchange for a few minutes on board, the traveller prefers the simplicity of walking straight there, with no interchange and no waiting. If the direct walk is itself the long part of the journey, that simplicity is paid in time and fatigue, and it stops being the easy option.
```

## 4.5 End-to-End Decision Trace: Raymond's Shopping Trip

We examine one decision trace to illustrate the inference process. Raymond, 45, is a full-time worker living in the first suburban ring. He departs for a shopping errand at 13:37. The decision-makers evaluate six candidate routes.

The language models received the following user message:

```text
--- agent_id=393781 | Destination: shop | Departure: 13:37 ---
**Context:** Weather: 28°C, Partly cloudy. Today 18°C to 33°C, sunrise 06:19, sunset 21:39. Rain expected in the morning (0.8 mm over the day).
**Weather later:** evening 13°C, Clear/Sunny.
Raymond, 45, Full-Time Worker (household of 4, very low income). Usual trip purposes: Shopping. Lives in: 1st ring

**Further trips planned today:**
    · 14:47 → shop (≈1.4 km)

**Trip options** (6 options, indices 0 to 5):
- [0] foot: Estimated duration: 16 minutes. Distance: 1.3 km.
- [1] foot: Travel time: 17 minutes, including 17 minutes of walking.
    · Walk to 'shop': 17 minutes.
- [2] car: Travel time: 4 minutes, including 1 minute of access and parking. Distance: 1.5 km.
    · Walk to the car: 1 minute.
    · Driving: 3 minutes.
- [3] foot,bus,foot: Travel time: 43 minutes, including 42 minutes of walking. Has no public transport pass.
    · Walk to 'Collège Picasso': 21 minutes.
    · Bus 'L11' to 'Frouzins Complexe Sportif': 1 minute.
    · Walk to 'shop': 21 minutes.
- [4] foot,bus,foot: Travel time: 34 minutes, including 33 minutes of walking. Has no public transport pass.
    · Walk to 'Frouzins Tréville': 10 minutes.
    · Bus '321' to 'Rouget de Lisle': 1 minute.
    · Walk to 'shop': 22 minutes.
- [5] foot,bus,foot: Travel time: 35 minutes, including 34 minutes of walking. Has no public transport pass.
    · Walk to 'Rouget de Lisle': 14 minutes.
    · Bus '321' to 'Frouzins Tréville': 1 minute.
    · Walk to 'shop': 19 minutes.

Reply with the final JSON object containing the recommendations for 1 persona(s).
For each persona, copy its `agent_id` **exactly** as provided above (numeric identifier only, without the word "PERSONA" and without the persona's name).
For each persona, rate **all** of its options — one `probabilities` entry per option, with its `index` and its `mode` copied as they appear — and make the `probability` values sum to 100. An option this persona would never take receives 0.
Only the `- [n]` lines are options: the « · » sub-bullets detail the steps of an option and never receive a `probabilities` entry. Indices restart from 0 in each persona block — use only those shown in brackets in the block of the persona you are rating, never a numbering continued from one persona to the next.
```

Table 4.2 presents the resulting probability vectors and drawn modes across the three architectures.

*Table 4.2. Probability distributions assigned to Raymond's options (in percent).*

| Option | Minimal prompt (`gemini-3.5`) | Expert prompt (`gemini-3.5`) | Typed classifier (`prompt_expert_32`) |
|---|---:|---:|---:|
| [0] foot, 16 min | 30 | 45 | 52 |
| [1] foot, 17 min | 10 | 45 | 20 |
| [2] car, 4 min | 50 | 10 | 27 |
| [3] foot, bus, foot, 43 min | 0 | 0 | 0 |
| [4] foot, bus, foot, 34 min | 5 | 0 | 1 |
| [5] foot, bus, foot, 35 min | 5 | 0 | 0 |
| **Drawn mode** | **car** | **foot** | **car** |

Under the minimal prompt, `gemini-3.5` wrote the following justification:
> *"Raymond prefers the speed and shelter of a car for his short shopping trip during inclement weather."*

This justification hallucinates adverse weather contradicted by the context (28 °C, partly cloudy, clear afternoon). Under the expert prompt, the model wrote:
> *"With a very short distance to the shop and low income constraints, walking directly is the preferred choice."*

This second justification omits all four expert criteria. These traces demonstrate that verbalized explanations often serve as post-hoc justifications rather than faithful computational reasoning.

---
