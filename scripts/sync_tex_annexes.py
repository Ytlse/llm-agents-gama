#!/usr/bin/env python3
"""Synchronize LaTeX appendix chapters with markdown contents."""

from pathlib import Path

BASE = Path("docs/paper/article-court/appendices")
CHAPTERS = BASE / "chapters"

# ==============================================================================
# 11. Multi-Agent Specification
# ==============================================================================
tex_ch11 = r"""\section{11. Formal Multi-Agent Specification and Dual-Clock Memory Dynamics}

This chapter presents the formal mathematical specification of the generative mobility agent. We define choice set pruning under vehicle chaining, the dual-clock memory architecture, five-component retrieval scoring, and concept consolidation dynamics.

\subsection{11.1 Formal Agent Tuple and Physical Vehicle Chain Constraints}

We formalize each generative mobility agent as a structured mathematical tuple:
\[\text{Agent}_i = \langle P_i, M_{i,t}, C_{i,t}, \pi_\theta \rangle\]

Here $P_i$ denotes the static demographic persona vector. The variable $M_{i,t}$ denotes the dynamic cognitive memory state. The term $C_{i,t}$ represents physical vehicle availability and location. Finally, $\pi_\theta$ denotes the stochastic decision policy parameterized by model weights $\theta$.

The operational action space $\mathcal{A}(o_t, C_{i,t})$ prunes physically impossible itineraries from candidate options $o_t$. An agent cannot select a private motorized vehicle if that vehicle resides at another physical node:
\[\text{car} \in \mathcal{A}(o_t, C_{i,t}) \iff C_{i,t}^{\text{car\_at\_origin}} = \text{True}\]

Similarly, bicycle choices require local bicycle availability. When an agent drives to work, the vehicle remains at the workplace centroid until the return trip.

Furthermore, unexpected operational delays trigger behavioral rescheduling. When transit congestion generates an arrival delay exceeding 15 minutes, the simulation applies an activity shortening rule:
\[\Delta t_{\text{target}} = 0.75 \times \text{delay}\]

This adjustment compresses subsequent activity durations while preserving mandatory departure deadlines.

\subsection{11.2 Intellectual Filiation and the Four Architectural Divergences}

Our cognitive architecture builds upon the generative agent framework introduced by Park et al. (2023). It incorporates the multimodal transport extension formulated by Vu, Gaudou \& Oberoi (2025). However, metropolitan transport simulation introduces strict physical conservation laws and longitudinal comparability requirements. Consequently, our implementation establishes four principled divergences from Park et al. (2023).

\subsubsection{Divergence 1: Reinstatement of Event Gravity}
Park et al. scored memory importance using a subjective model rating from 1 to 10. Vu et al. discarded importance entirely, substituting lexical n-gram overlap. That substitution caused severe distortions. A 45-minute transit disruption and a nominal 5-minute trip received identical retrieval priorities.

We reinstated event gravity with an explicit weight of 0.20 in the retrieval formula. Furthermore, we compute event gravity deterministically from physical delays and lived disruptions. Deterministic calculation avoids subjective prompt drift.

\subsubsection{Divergence 2: Triple Additive Consolidation Triggers}
Park et al. triggered memory reflection when cumulative importance exceeded a numerical threshold of 150. That rule produced two to three reflections daily. Conversely, Vu et al. evaluated reflection strictly at the conclusion of each simulated day.

Our architecture unifies both principles through three additive triggering rules shown in Table~\ref{tab:triggers}.

\begin{table}[h]
\centering
\caption{Additive triggering mechanisms governing cognitive reflection.}
\label{tab:triggers}
\small
\begin{tabular}{lll}
\toprule
\textbf{Trigger} & \textbf{Formal condition} & \textbf{Frequency / Regime} \\
\midrule
Volumetric buffer threshold & Buffer length $\ge 10$ entries & Frequent (commute bursts) \\
Cumulative rupture threshold & Cumulative event gravity $\sum g \ge 0.70$ & Exceptional (severe shocks) \\
Daily consolidation floor & Simulated wall-clock $\ge$ 22:00 & Daily deterministic sweep \\
\bottomrule
\end{tabular}
\end{table}

The daily floor guarantees that every active agent reflects at least once per 24-hour cycle. In contrast, the cumulative rupture threshold captures unexpected traumatic shocks immediately.

\subsubsection{Divergence 3: Retrieval-Based Decay and Calibrated Half-Life}
Park et al. degraded recency using an hourly attenuation factor of 0.995, yielding a half-life of 5.78 days. Their decay counted from the moment of last retrieval. In contrast, early transport implementations degraded memories strictly from initial creation time. That early design effaced regularly consulted habits.

We align with Park et al. by measuring elapsed time from the most recent active recall. However, we calibrate the baseline half-life to transport reality:
\[\tau_{1/2} = 1.94 \text{ days} \quad (S_0 = 2.80 \text{ days})\]

Urban mobility habits evolve on weekly cycles. Commuters do not retain mundane travel sensations for six weeks. Additionally, each successful retrieval into the decision prompt reinforces the memory trace. Active retrieval lengthens trace lifespan by exactly one day.

\subsubsection{Divergence 4: Elimination of Min-Max Normalization}
Park et al. normalized component scores across candidate memories via dynamic min-max scaling before linear summation. While min-max scaling orders memories effectively within a single prompt, it destroys absolute comparability across experimental conditions.

Under min-max scaling, the newest memory always scores 1.0 and the oldest always scores 0.0, regardless of absolute elapsed time. That artifact renders parameter sensitivity sweeps mathematically undetectable. We enforce an absolute, non-normalized bounded scoring formulation on $[0, 1]$. This formulation preserves cross-condition empirical comparability.

\subsection{11.3 Five-Phase Nycthemeral Lifecycle and Multi-Agent Synchronization}

Agents navigate a synchronized five-phase daily cognitive cycle. Figure~\ref{fig:mem_lifecycle} illustrates the six operational processing stages linking physical events to prompt generation.

\begin{figure*}[t]
\centering
\includegraphics[width=0.90\textwidth]{images/fig_memory_lifecycle}
\caption{Processing stages of the multi-agent cognitive memory pipeline, from sensory perception to prompt injection.}
\label{fig:mem_lifecycle}
\end{figure*}

The nycthemeral cycle organizes these stages across distinct temporal windows summarized in Table~\ref{tab:nycthemeral}.

\begin{table}[h]
\centering
\caption{Five operational phases of the synchronized multi-agent daily cycle.}
\label{tab:nycthemeral}
\small
\begin{tabularx}{\columnwidth}{l l L}
\toprule
\textbf{Phase} & \textbf{Time window} & \textbf{Operational activities} \\
\midrule
Phase 1: Waking \& Planning & 05:00--09:00 & Morning commute evaluation, retrieval of consolidated concepts \\
Phase 2: In-Trip Execution & 09:00--18:00 & Physical stage execution, transfer logging, short-term buffer updates \\
Phase 3: Household Exchange & 18:00--22:00 & Dinner conversation, 1-hop belief sharing with family members \\
Phase 4: Evening Floor & 22:00 & Structured LLM reflection, concept updating, EDF queue dispatch \\
Phase 5: Nighttime Drainage & 22:00--05:00 & Background reflection completion during physical simulation lull \\
\bottomrule
\end{tabularx}
\end{table}

Phase 3 enforces a strict one-hop viral barrier (Rule D2). Hearsay travel experiences cannot propagate beyond the immediate household boundary.

Every three days, agents trigger an asynchronous biographical reflection. This higher-level synthesis extracts stable multi-day routines into persistent summary nodes.

\subsection{11.4 Multi-Pool Candidate Generation and Five-Component Retrieval Scoring}

To balance semantic nuance and physical relevance, our retrieval engine draws candidate memories from three complementary pools shown in Table~\ref{tab:candidate_pools}.

\begin{table}[h]
\centering
\caption{Multi-pool candidate memory generation architecture.}
\label{tab:candidate_pools}
\small
\begin{tabular}{llll}
\toprule
\textbf{Pool} & \textbf{Storage backend} & \textbf{Query logic} & \textbf{Quota} \\
\midrule
Pool A: Semantic Search & ChromaDB HNSW & Cosine distance over MiniLM embeddings & $\le 50$ candidates \\
Pool B: Object Affinity & RAM metadata index & Exact match on available modal options & $\le 8$ per mode \\
Pool C: Salient Shocks & RAM metadata index & High-gravity disruptions ($g_m \ge 0.70$) & $\le 5$ memories \\
\bottomrule
\end{tabular}
\end{table}

Combining these pools guarantees that severe disruptions influence modal choices even when trip origins differ. The retrieval algorithm ranks candidates using a linear formulation:
\[S(m, q) = 0.30 \cdot \exp(\cos(e_m, e_q) - 1) + 0.20 \cdot R(\Delta t) + 0.20 \cdot g_m + 0.20 \cdot \text{Aff}_{\text{axes}}(m, q) + 0.10 \cdot \text{Aff}_{\text{meteo}}(m, q)\]

The semantic term rescales ChromaDB cosine distance into $[e^{-2}, 1] \approx [0.135, 1.0]$. The axis affinity matches four contextual coordinates:
\[\text{Aff}_{\text{axes}} = 0.50 \cdot [\text{mode}] + 0.20 \cdot [\text{location}] + 0.15 \cdot [\text{time-slot}] + 0.15 \cdot [\text{purpose}]\]

The weather affinity contributes a binary indicator matching atmospheric conditions. Figure~\ref{fig:retrieval_radar} illustrates the resulting retrieval profiles across three representative mobility situations.

\begin{figure}[h]
\centering
\includegraphics[width=0.85\columnwidth]{images/fig_retrieval_components}
\caption{Radar chart of the five retrieval scoring components across routine, breakdown, and weather shock profiles.}
\label{fig:retrieval_radar}
\end{figure}

\subsection{11.5 Cognitive Decay Dynamics and Recall Reinforcement}

Episodic traces decay following an Ebbinghaus exponential formulation. We modulate memory retention $R(\Delta t)$ by event severity $g_m \in [0, 1]$:
\[R(\Delta t) = \exp\left(-\frac{\Delta t}{\tau(g_m)}\right)\]

The memory lifespan $\tau(g_m)$ expands proportionally with experienced trauma:
\[\tau(g_m) = \min(S_0 \cdot (1 + k \cdot g_m), \tau_{\max})\]

We set baseline stability $S_0 = 2.80$ days, sensitivity multiplier $k = 6.0$, and maximum lifespan $\tau_{\max} = 30.0$ days. Consequently, a mundane commute exhibits a half-life of 1.94 days. In contrast, a severe accident reaches a half-life of 13.6 days.

Figure~\ref{fig:decay_curve} contrasts our calibrated mobility decay against the classical Park et al. baseline and demonstrates active recall reinforcement.

\begin{figure}[h]
\centering
\includegraphics[width=0.90\columnwidth]{images/fig_ebbinghaus_decay}
\caption{Retention trajectories showing rapid decay for routine commutes, persistent retention for traumatic shocks, and recall reinforcement.}
\label{fig:decay_curve}
\end{figure}

Each time an episodic trace ranks in the final top-10 decision context, its reference timestamp refreshes. Furthermore, its lifespan $\tau$ increases by one full day.

\subsection{11.6 Concept Evolution, Laplace Confidence, and Dual Extinction Mechanics}

Reflections consolidate episodic experiences into generalized conceptual beliefs. We represent each concept as a formal 5-tuple:
\[\text{Concept} = \langle \text{content}, \text{keywords}, \text{spatial\_scope}, \text{temporal\_scope}, \text{objective} \rangle\]

During consolidation, the model inspects existing active beliefs and applies one of the four structured mutations listed in Table~\ref{tab:concept_ops}.

\begin{table}[h]
\centering
\caption{Four structured operations governing conceptual belief evolution.}
\label{tab:concept_ops}
\small
\begin{tabular}{lll}
\toprule
\textbf{Operation} & \textbf{Action on existing concept} & \textbf{Effect on confidence} \\
\midrule
\texttt{creer} & Instantiates a novel concept & Initial prior ($\text{obs}=0, \text{contre}=0, \text{Conf}=0.50$) \\
\texttt{confirmer} & Confirms current travel rule & Increments observation count ($\text{obs} \leftarrow \text{obs} + 1$) \\
\texttt{preciser} & Updates descriptive scope & Preserves empirical counters and confidence \\
\texttt{contredire} & Records counter-example & Increments counter-examples ($\text{contre} \leftarrow \text{contre} + 1$) \\
\bottomrule
\end{tabular}
\end{table}

We evaluate belief reliability using Laplace's rule of succession (1814):
\[\text{Conf}(c) = \frac{\text{obs} + 1}{\text{obs} + \text{contre} + 2}\]

When accumulated counter-examples drive confidence below 0.50, the agent deactivates the concept. The system records the exact deactivation timestamp without deleting the underlying record. This dated retirement provides an empirical marker of habit abandonment.

In accordance with Tulving's dual-memory taxonomy (1972), our architecture implements two distinct extinction pathways. Semantic knowledge is extinguished strictly through empirical contradiction, never through calendar time. Conversely, episodic traces are pruned when retention strength drops below 1\% ($R < 0.01$).

Mundane commutes vanish after 13 days of non-recall. Traumatic memories persist for over 90 days.

\subsection{11.7 Working Context Formulation and Prompt Injection}

Decisions do not feed raw unstructured memory streams to the language model. Instead, the simulation controller compiles memory states into three deterministic context blocks. Table~\ref{tab:working_context} outlines their structure and operational sources.

\begin{table}[h]
\centering
\caption{Structure of the three deterministic working context blocks.}
\label{tab:working_context}
\small
\begin{tabular}{lll}
\toprule
\textbf{Context block} & \textbf{Generation source} & \textbf{Injected content} \\
\midrule
\texttt{My habits} & Arrival trip logs & Empirical mode frequencies and delay counts \\
\texttt{What I know} & Consolidated concepts & High-confidence travel beliefs ($\text{Conf} \ge 0.50$) \\
\texttt{What changed recently} & Press and shock logs & Disruptions, de-indexed beliefs, press bulletins \\
\bottomrule
\end{tabular}
\end{table}

These three blocks form the agent working context (Packer et al., 2023). They inject directly into the Jinja2 decision template alongside the physical choice set, enabling transparent and bounded modal choices.
"""

(CHAPTERS / "11_multi_agent_specification.tex").write_text(tex_ch11.strip() + "\n")
print("✓ chapters/11_multi_agent_specification.tex")

# ==============================================================================
# 15. Systems Architecture
# ==============================================================================
tex_ch15 = r"""\section{15. Systems Architecture, Distributed Topology, and TypeSafe Engine Specifications}

This chapter specifies the software architecture, distributed orchestration, and engineering interfaces. We provide the container topology, the decision lifecycle sequence, the EDF backpressure mechanism, the SWRR gateway, and sovereign vLLM deployment parameters.

\subsection{15.1 Distributed Container Topology}

The simulation infrastructure coordinates seven containerized services managed through Docker Compose. Figure~\ref{fig:c4_topology} illustrates the container topology and communication channels.

\begin{figure*}[t]
\centering
\includegraphics[width=0.90\textwidth]{images/fig_c4_container_topology}
\caption{Distributed container topology of the multi-agent simulation framework across seven microservices.}
\label{fig:c4_topology}
\end{figure*}

The GAMA platform simulates continuous physical movement across the road and transit network. The FastAPI controller coordinates agent state transitions, triggers routing queries, and formats decision prompts. Redis acts as a high-throughput cache for candidate itineraries and pending decision requests.

\subsection{15.2 Decision Lifecycle UML Sequence}

Figure 15.2 illustrates the asynchronous message sequence governing each mobility decision.

\begin{Verbatim}
GAMA Server          Controller            Routers             ChromaDB          LLM / TypeSafe
    |                     |                   |                   |                     |
    |-- Agent IDLE ------>|                   |                   |                     |
    |   (event trigger)   |-- Route Request ->|                   |                     |
    |                     |   (OTP / OSMnx)   |                   |                     |
    |                     |<-- Candidates ----|                   |                     |
    |                     |                   |                   |                     |
    |                     |-- Filter Chains --+ (prune unavailable vehicles)            |
    |                     |-- Query Context --------------------->|                     |
    |                     |<-- Memories & Reflections ------------|                     |
    |                     |                                                             |
    |                     |-- Render Jinja2 / Choice Query ---------------------------->|
    |                     |   (sub-bullets, strict schema)                              |
    |                     |<-- Probability Vector & Justification ----------------------|
    |                     |                                                             |
    |                     |-- Multinomial Mode Draw (seed)                              |
    |<- Execute Move -----|                                                             |
    |   (WebSocket push)  |                                                             |
\end{Verbatim}

The controller initiates routing calculations as soon as an agent completes a previous activity. Vehicle chaining filters remove private modes if the vehicle remains parked elsewhere. Once the model returns a valid probability distribution, the controller executes a seeded multinomial draw.

\subsection{15.3 Asynchronous Backpressure and Simulation Synchronization}

Simulation clocks advance discrete simulation steps, whereas external language models exhibit variable network latency. Uncontrolled clock progression would cause agents to miss departure deadlines while awaiting API responses.

To maintain temporal synchronization, the controller implements a dual backpressure mechanism (\texttt{services/llm-agents/backpressure.py}).

First, a reactive backpressure function throttles GAMA \texttt{/sync} responses based on pending queue backlog. The interval formula specifies:
\[\Delta t = \text{cap} \cdot \left(\min\left(1, \frac{n}{N}\right)\right)^k\]
Parameter values are $k = 3.7$ and $\text{cap} = 30.0$ seconds. A floor threshold disables throttling when backlog remains below concurrency capacity.

Second, an Earliest Deadline First (EDF) scheduler evaluates departure feasibility. If an agent faces an imminent departure whose decision remains in flight, the controller withholds the \texttt{/sync} confirmation. This pause holds simulation time until the decision resolves, preventing missed departures.

Figure~\ref{fig:backpressure} illustrates the non-linear reactive backpressure delay curve and the emergency EDF hold boundary.

\begin{figure}[h]
\centering
\includegraphics[width=0.90\columnwidth]{images/fig_backpressure_edf}
\caption{Reactive backpressure throttle curve ($k = 3.7$) and deterministic Earliest Deadline First (EDF) freeze threshold.}
\label{fig:backpressure}
\end{figure}

\subsection{15.4 SWRR Gateway and Atomic Quota Reservation}

The inference gateway balances requests across multiple API keys using a Smooth Weighted Round-Robin (SWRR) algorithm.

To prevent HTTP 429 rate limit errors, Redis tracks token consumption using an atomic token bucket. An atomic Lua script checks both Requests-Per-Minute (RPM) and Tokens-Per-Minute (TPM) limits before granting execution tokens.

When executing scientific evaluation runs, the gateway activates the \texttt{force\_provider} flag. This setting disables automatic provider failover. If the target provider fails, the pipeline halts immediately, preventing uncontrolled cross-model contamination.

\subsection{15.5 TypeSafe Classifier Integration Engine}

The typed zero-shot classifier (\texttt{jev-1.13.0}) interfaces through \texttt{decideur\_typesafe.py}.

Unlike generative language models, the classifier accepts structured option sets as criteria rather than free text. The engine strips \texttt{[Output instructions]} from prompt templates because output types are enforced structurally:

\begin{Verbatim}
def instructions_servies(texte: str) -> str:
    coupe = texte.find("[Output instructions]")
    return (texte[:coupe] if coupe > 0 else texte).strip()
\end{Verbatim}

The classifier returns discrete option probabilities rounded to two decimal places. The engine enforces a strict sum tolerance:
\[\left|\sum_{i} p_i - 1.0\right| \le 0.02\]
The engine renormalizes weights when the probability sum falls within $[0.98, 1.02]$. If the sum deviates further, the engine marks the response as an invalid non-decision. The system logs non-decisions explicitly and excludes them from modal share calculations, rejecting silent default fallbacks.

\subsection{15.6 Sovereign vLLM Deployment and Hardware Parameters}

Researchers can execute all benchmarks locally using open-weight foundation models. Deploy the vLLM engine with the following command:

\begin{Verbatim}
vllm serve Qwen/Qwen2.5-32B-Instruct-AWQ \
  --quantization awq \
  --max-model-len 4096 \
  --gpu-memory-utilization 0.90 \
  --port 8000 \
  --seed 42
\end{Verbatim}

Serving \texttt{Qwen2.5-32B-Instruct-AWQ} requires a single GPU equipped with 24 GB of VRAM. Operating at temperature $\tau = 0.0$ and top-p 1.0 guarantees fully deterministic local replication.
"""

(CHAPTERS / "15_systems_architecture.tex").write_text(tex_ch15.strip() + "\n")
print("✓ chapters/15_systems_architecture.tex")

# ==============================================================================
# 03. Mathematical Metrics
# ==============================================================================
tex_ch03 = r"""\section{3. Mathematical Foundations of Distributional Metrics and Sample Size Bias}

This chapter formalizes the mathematical metrics used to evaluate aggregate behavioral alignment. We detail the composite loss function and prove the statistical necessity of equal sample sizes.

\subsection{3.1 Formal Definitions of Distributional Metrics}

Macro-level behavioral validation compares simulated modal distributions against observed survey distributions. We employ three complementary divergence metrics.

First, we compute the standard $L_1$ global distance across the set of travel modes $\mathcal{M} = \{\text{car}, \text{foot}, \text{transit}, \text{bike}\}$:
\[L_1(\hat{P}, P^*) = \sum_{m \in \mathcal{M}} |\hat{P}_m - P_m^*|\]

Second, we evaluate nominal demographic strata using the symmetric Jensen-Shannon Divergence in base 2. The formulation is:
\[\mathrm{JSD}(P \parallel Q) = \frac{1}{2}\mathrm{KL}(P \parallel M) + \frac{1}{2}\mathrm{KL}(Q \parallel M), \quad M = \frac{1}{2}(P + Q)\]

Here $\mathrm{KL}$ denotes the Kullback-Leibler divergence. We scale the metric by 100 to express results in percentage points.

Third, we evaluate ordinal dimensions using the Earth Mover's Distance. We compute the metric on cumulative distribution functions:
\[\mathrm{EMD}(P, Q) = \frac{1}{K-1} \sum_{k=1}^{K-1} |F_P(k) - F_Q(k)| \times 100\]

Here $F_P$ and $F_Q$ denote the cumulative distributions across the $K$ ordered bins.

\subsection{3.2 The Composite Loss Function}

The composite loss function $\mathcal{C}_{\text{EMD–JSD}}$ combines global distribution error and stratified divergences. The metric is defined as:
\[\mathcal{C}_{\text{EMD–JSD}} = \mathrm{JSD}^{\text{global}} + \sum_{d \in \mathcal{D}_{\text{nom}}} w_d \overline{\mathrm{JSD}}^d + \sum_{d \in \mathcal{D}_{\text{ord}}} w_d \overline{\mathrm{EMD}}^d\]

The nominal dimensions $\mathcal{D}_{\text{nom}}$ comprise occupation, trip purpose, and gender. The ordinal dimensions $\mathcal{D}_{\text{ord}}$ comprise age brackets and distance bands. We assign fixed weights $w_{\text{global}} = 1.0$, $w_{\text{age}} = 0.5$, $w_{\text{occ}} = 0.5$, $w_{\text{purpose}} = 0.5$, $w_{\text{gender}} = 0.3$, and $w_{\text{distance}} = 0.3$, excluding strata with $n < 5$.

We tested ranking sensitivity under five alternative weighting schemes with perturbations up to $\pm 50\%$. The Kendall rank correlation coefficient across the fifteen decision-makers remained above 0.94, confirming ranking stability.

\subsection{3.3 Finite-Sample Divergence Bias}

Divergence metrics computed on empirical samples carry an inherent upward finite-sample bias. When sample size decreases, empirical distributions exhibit greater stochastic variance, inflating both JSD and EMD.

We demonstrated this bias empirically by subsampling the reference cohort at constant decision probabilities. Reducing sample size from 881 to 81 personas artificially increases the composite score by $+5.02$ points. Consequently, comparisons across decision-makers must maintain strictly identical sample sizes.

Figure~\ref{fig:emd_bias} illustrates the cumulative formulation of 1D Earth Mover's Distance and displays the empirical finite-sample bias curve.

\begin{figure}[h]
\centering
\includegraphics[width=0.90\columnwidth]{images/fig_emd_jsd_explanation}
\caption{Mathematical derivation of 1D Earth Mover's Distance between cumulative distributions and finite-sample divergence bias curve.}
\label{fig:emd_bias}
\end{figure}
"""

(CHAPTERS / "03_mathematical_metrics.tex").write_text(tex_ch03.strip() + "\n")
print("✓ chapters/03_mathematical_metrics.tex")

# ==============================================================================
# 09. Computational Economics
# ==============================================================================
tex_ch09 = r"""\section{9. Computational Economics, Token Accounting, and Metropolitan Scaling Laws}

This chapter evaluates the computational and economic demands of large-scale agent simulation. We account for token consumption, explain pricing tariffs, quantify memory overheads, and formalize scaling equations for metropolitan deployments.

\subsection{9.1 Granular Token Accounting and Tariff Breakdown}

We profile the token demands of every decision architecture across 23,026 simulated trip choices. Table~\ref{tab:token_breakdown} details prompt tokens, thinking tokens, completion tokens, and dollar costs.

The typed classifier transmits more input tokens per call (1,050 tokens) than the generative language model (629 tokens). This difference arises because the classifier resends full option schema definitions with every prompt. However, the classifier generates zero output tokens and requires no reasoning compute.

Furthermore, cloud provider pricing structures bill the classifier at 0.042 dollars per million input tokens, with output unbilled. Consequently, the typed classifier costs 1.06 dollars for 23,026 decisions, whereas the generative agent costs 49.28 dollars. This difference establishes a 1:50 cost ratio favoring typed classification.

\begin{table*}[t]
\centering
\caption{Token breakdown and monetary cost across 23,026 simulated decisions.}
\label{tab:token_breakdown}
\small
\begin{tabular}{lrrrrr}
\toprule
\textbf{Architecture} & \textbf{Input tokens} & \textbf{Reasoning tokens} & \textbf{Output tokens} & \textbf{Total cost (\$)} & \textbf{Cost / 1k trips (\$)} \\
\midrule
Minimal prompt (\texttt{gemini-3.5}) & 485 & 820 & 42 & 28.40 & 1.23 \\
Expert prompt (\texttt{gemini-3.5}) & 629 & 1,215 & 48 & 49.28 & 2.14 \\
Expert prompt (\texttt{mistral-large}) & 632 & 950 & 51 & 84.50 & 3.67 \\
Typed classifier (\texttt{jev-1.13.0}) & 1,050 & 0 & 0 & \textbf{1.06} & \textbf{0.046} \\
Gradient boosting (LightGBM) & 0 & 0 & 0 & $<$ 0.001 & $<$ 0.0001 \\
\bottomrule
\end{tabular}
\end{table*}

\subsection{9.2 Memory Computational Overhead}

Maintaining longitudinal agent memory introduces significant secondary token consumption beyond trip decisions.

Simulating one weekday for 1,000 synthetic personas requires 2,108 trip-level model calls, consuming 3.0 million tokens with memory disabled. Enabling active episodic memory adds 2.5 million additional tokens per simulated day across 894 mobile personas.

This memory overhead comprises two scheduled processes. Daily evening consolidation requires 1.25 short consolidation calls per agent. Weekly biographical reflection requires 0.27 self-reflection calls per agent.

\subsection{9.3 Metropolitan Scaling Equations and Cascade Architecture}

We evaluate computational feasibility across the entire Toulouse metropolitan survey perimeter. The territory encompasses 1.32 million residents aged five and older, generating 4.36 million daily trips (3.30 trips per person).

Pruning unarbitrated trips with single viable options leaves 2.9 million decisions requiring deliberation. Simulating one metropolitan day using unconstrained generative LLMs demands 2.6 to 4.2 billion tokens, incurring approximately 140,000 dollars daily.

A multi-tier cascade architecture resolves this scaling bottleneck through three stages.

Stage 1 evaluates deterministic feasibility and rule-based heuristics. This stage absorbs 65\% to 75\% of routine trips at negligible computational cost.

Stage 2 directs standard multi-option arbitrations to the typed classifier. Operating at 0.046 dollars per 1,000 trips, this stage handles 20\% to 30\% of daily choices for less than 150 dollars.

Stage 3 invokes generative language models exclusively when an agent encounters unexpected exogenous shocks. Because shocks affect under 2\% of daily trips, daily simulation expenses remain below 400 dollars.

Figure~\ref{fig:cost_waterfall} illustrates the monetary cost comparison across decision architectures and traces the progressive collapse of metropolitan simulation expenses through cascade filtering.

\begin{figure}[h]
\centering
\includegraphics[width=0.90\columnwidth]{images/fig_metropolitan_cost_waterfall}
\caption{Architectural cost comparison across 23,026 decisions and metropolitan cost collapse from 140,000 dollars to under 400 dollars per simulated day.}
\label{fig:cost_waterfall}
\end{figure}
"""

(CHAPTERS / "09_computational_economics.tex").write_text(tex_ch09.strip() + "\n")
print("✓ chapters/09_computational_economics.tex")

# ==============================================================================
# 10. Execution Language
# ==============================================================================
tex_ch10 = r"""\section{10. The Execution Language Dilemma: Cross-Lingual Spatial Reasoning}

This chapter examines the methodological rationale for running model prompts in English within a French urban environment. We analyze literature findings and present paired bilingual experimental results.

\subsection{10.1 English Prompts in French Mobility Contexts}

The survey microdata and spatial infrastructure originate in Toulouse, France. Nevertheless, the production framework delivers prompts in English, retaining French proper nouns for transit stops and districts.

Executing in English leverages superior reasoning benchmarks documented in frontier foundational models. Foundational models exhibit lower perplexity and fewer tokenization splits on English syntax, improving logical rule following.

Four published studies support this choice. Forcing a reasoning model outside English costs accuracy. In agentic recommendation, local-language bias is prevalent, and explicit reasoning worsens it outside English. Across 180 clinical vignettes, four models out of five scored higher in English. Finally, explicit cultural framing weighs more than language on alignment.

Two studies argue conversely. A model captures local cultural nuances better in the native language. Furthermore, prompting in English can induce Western-centric bias. However, no measurement conducted here establishes that French prompts improved behavioral scores.

\subsection{10.2 Empirical Bilingual Comparison}

We evaluated a paired sample of 200 decisions executed under identical French and English prompt templates. Table~\ref{tab:bilingual} reports accuracy, compliance, and token consumption across both languages.

\begin{table}[h]
\centering
\caption{Paired performance comparison between English and French prompt executions.}
\label{tab:bilingual}
\small
\begin{tabular}{lrrr}
\toprule
\textbf{Metric} & \textbf{English prompt} & \textbf{French prompt} & \textbf{Difference} \\
\midrule
JSON schema compliance rate & 100.0\% & 98.5\% & $-1.5$ pt \\
Mode agreement with survey & 67.5\% & 66.0\% & $-1.5$ pt \\
Average input tokens per trip & 629 & 794 & $+26.2\%$ \\
Reasoning tokens per trip & 1,215 & 1,480 & $+21.8\%$ \\
\bottomrule
\end{tabular}
\end{table}

French prompt execution inflates token consumption by over 20\% due to sub-word tokenization fragmentation. Furthermore, schema compliance degrades slightly. Consequently, English execution provides superior operational reliability.

Figure~\ref{fig:bpe_token} illustrates Byte-Pair Encoding sub-word fragmentation on French mobility terms and contrasts input and reasoning token overheads across both languages.

\begin{figure}[h]
\centering
\includegraphics[width=0.90\columnwidth]{images/fig_french_english_tokenization}
\caption{Byte-Pair Encoding (BPE) byte fragmentation on French transport vocabulary and observed 26.2\% token inflation.}
\label{fig:bpe_token}
\end{figure}
"""

(CHAPTERS / "10_execution_language.tex").write_text(tex_ch10.strip() + "\n")
print("✓ chapters/10_execution_language.tex")

# ==============================================================================
# 14. Individual Audit
# ==============================================================================
tex_ch14 = r"""\section{14. Disaggregate Individual Audit, Confusion Matrices, and Target Leakage Post-Mortem}

This chapter reports the unit-level classification audit on 9,621 real survey trips. We evaluate individual accuracy, present complete confusion matrices, and document the target leakage discovery.

\subsection{14.1 Individual-Level Classification Performance}

We evaluate decision-makers on 9,621 trips declared by 2,930 respondents under real dates and weather. Table~\ref{tab:audit_metrics} summarizes weighted accuracy, arbitrated accuracy, and multiclass cross-entropy.

\begin{table*}[t]
\centering
\caption{Unit-level audit metrics on 9,621 declared survey trips.}
\label{tab:audit_metrics}
\small
\begin{tabular}{lrrrr}
\toprule
\textbf{Decision-maker} & \textbf{Weighted acc. (\%)} & \textbf{Arbitrated acc. (\%)} & \textbf{Cross-entropy (nats)} & \textbf{GMPCA} \\
\midrule
Gradient boosting (LightGBM) & \textbf{71.5} & \textbf{67.4} & 0.419 & 0.657 \\
Kernel logistic regression & 70.6 & 66.2 & 0.438 & 0.646 \\
Random forest & 69.9 & 65.5 & 0.445 & 0.641 \\
Multinomial logit & 68.6 & 64.2 & 0.478 & 0.620 \\
Shortest duration heuristic & 68.1 & 65.3 & --- & --- \\
All-car majority heuristic & 66.7 & 61.7 & --- & --- \\
Expert prompt (\texttt{gemini-3.5}) & 67.6 & 65.2 & \textbf{0.356} & \textbf{0.701} \\
Minimal prompt (\texttt{gemini-3.5}) & 64.8 & 61.6 & 0.460 & 0.631 \\
Typed classifier (\texttt{jev-1.13.0}) & 64.7 & 61.4 & 0.468 & 0.628 \\
\bottomrule
\end{tabular}
\end{table*}

While tabular models achieve the highest raw accuracy, \texttt{gemini-3.5} expert achieves the lowest cross-entropy (0.356 nats), indicating superior probabilistic calibration.

\subsection{14.2 Confusion Matrices and Precision-Recall Profiles}

Table~\ref{tab:prec_rec} presents the mode-by-mode precision and recall metrics across models.

\begin{table}[h]
\centering
\caption{Precision and recall percentages by transport mode.}
\label{tab:prec_rec}
\small
\begin{tabular}{lllll}
\toprule
\textbf{Decision-maker} & \textbf{Car (P/R)} & \textbf{Walking (P/R)} & \textbf{Transit (P/R)} & \textbf{Cycling (P/R)} \\
\midrule
Gradient boosting & 85.3 / 79.0 & 53.2 / 63.4 & 53.8 / 61.7 & 27.3 / 20.4 \\
Random forest & 84.5 / 77.2 & 50.8 / 64.0 & 51.2 / 60.6 & 25.5 / 13.9 \\
Expert prompt (\texttt{gemini-3.5}) & 80.1 / 80.4 & 62.9 / 47.2 & 49.7 / 55.2 & 15.0 / 22.5 \\
Typed classifier (\texttt{jev}) & 78.4 / 79.1 & 61.5 / 45.8 & 48.2 / 54.1 & 14.2 / 21.0 \\
\bottomrule
\end{tabular}
\end{table}

Table~\ref{tab:confusion_gemini} details the full confusion matrix for the expert prompt on declared trips.

\begin{table}[h]
\centering
\caption{Confusion matrix of the expert prompt on declared trips (trip counts).}
\label{tab:confusion_gemini}
\small
\begin{tabular}{lrrrr}
\toprule
\textbf{Declared mode} & \textbf{Pred. bike} & \textbf{Pred. car} & \textbf{Pred. transit} & \textbf{Pred. walking} \\
\midrule
Bicycle ($n = 431$) & 97 & 227 & 62 & 45 \\
Car ($n = 5{,}971$) & 345 & 4,799 & 540 & 283 \\
Public transit ($n = 1{,}562$) & 88 & 481 & 862 & 132 \\
Walking ($n = 1{,}652$) & 116 & 488 & 269 & 779 \\
\bottomrule
\end{tabular}
\end{table}

Furthermore, 1,295 trips (13.5\%) had their declared mode excluded from candidate itineraries due to vehicle chaining or option filtering.

Figure~\ref{fig:confusion_matrix} displays normalized $4 \times 4$ confusion heatmaps comparing the generative language model against the typed zero-shot classifier across all declared choices.

\begin{figure}[h]
\centering
\includegraphics[width=0.90\columnwidth]{images/fig_confusion_matrix_audit}
\caption{Comparative normalized confusion matrices on 9,621 declared trips for Gemini 3.5 expert prompt and Jev-1.13.0 typed classifier.}
\label{fig:confusion_matrix}
\end{figure}

\subsection{14.3 Target Leakage Post-Mortem}

During model development, an experimental gradient boosting variant achieved an extraordinary accuracy of 93.4\%. However, when deployed inside the dynamic multi-agent simulation, its composite divergence collapsed to 9.28 points, far worse than standard models.

An internal audit revealed severe target leakage. The feature engineering pipeline had computed trip distance by multiplying declared trip duration by mode-specific speeds. Consequently, duration implicitly encoded the true transport mode. When deployed dynamically with predicted durations, the model failed completely.
"""

(CHAPTERS / "14_individual_audit.tex").write_text(tex_ch14.strip() + "\n")
print("✓ chapters/14_individual_audit.tex")

print("\n🎉 All 6 LaTeX chapters synchronized successfully!")
