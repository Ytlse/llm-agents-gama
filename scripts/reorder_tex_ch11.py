from pathlib import Path

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

\begin{table}[h]
\centering
\caption{Additive triggering mechanisms governing cognitive reflection.}
\label{tab-triggers}
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

Our architecture unifies both principles through three additive triggering rules shown in Table~\ref{tab-triggers}.

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

\begin{figure*}[t]
\centering
\includegraphics[width=0.90\textwidth]{images/fig_memory_lifecycle}
\caption{Processing stages of the multi-agent cognitive memory pipeline, from sensory perception to prompt injection.}
\label{fig-mem_lifecycle}
\end{figure*}

\begin{table}[h]
\centering
\caption{Five operational phases of the synchronized multi-agent daily cycle.}
\label{tab-nycthemeral}
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

Agents navigate a synchronized five-phase daily cognitive cycle. Figure~\ref{fig-mem_lifecycle} illustrates the six operational processing stages linking physical events to prompt generation.

The nycthemeral cycle organizes these stages across distinct temporal windows summarized in Table~\ref{tab-nycthemeral}.

Phase 3 enforces a strict one-hop viral barrier (Rule D2). Hearsay travel experiences cannot propagate beyond the immediate household boundary.

Every three days, agents trigger an asynchronous biographical reflection. This higher-level synthesis extracts stable multi-day routines into persistent summary nodes.

\subsection{11.4 Multi-Pool Candidate Generation and Five-Component Retrieval Scoring}

\begin{table}[h]
\centering
\caption{Multi-pool candidate memory generation architecture.}
\label{tab-candidate_pools}
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

\begin{figure}[h]
\centering
\includegraphics[width=0.85\columnwidth]{images/fig_retrieval_components}
\caption{Radar chart of the five retrieval scoring components across routine, breakdown, and weather shock profiles.}
\label{fig-retrieval_radar}
\end{figure}

To balance semantic nuance and physical relevance, our retrieval engine draws candidate memories from three complementary pools shown in Table~\ref{tab-candidate_pools}.

Combining these pools guarantees that severe disruptions influence modal choices even when trip origins differ. The retrieval algorithm ranks candidates using a linear formulation.

\[S(m, q) = 0.30 \cdot \exp(\cos(e_m, e_q) - 1) + 0.20 \cdot R(\Delta t) + 0.20 \cdot g_m + 0.20 \cdot \text{Aff}_{\text{axes}}(m, q) + 0.10 \cdot \text{Aff}_{\text{meteo}}(m, q)\]

The semantic term rescales ChromaDB cosine distance into $[e^{-2}, 1] \approx [0.135, 1.0]$. The axis affinity matches four contextual coordinates.

\[\text{Aff}_{\text{axes}} = 0.50 \cdot [\text{mode}] + 0.20 \cdot [\text{location}] + 0.15 \cdot [\text{time-slot}] + 0.15 \cdot [\text{purpose}]\]

The weather affinity contributes a binary indicator matching atmospheric conditions. Figure~\ref{fig-retrieval_radar} illustrates the resulting retrieval profiles across three representative mobility situations.

\subsection{11.5 Cognitive Decay Dynamics and Recall Reinforcement}

\begin{figure}[h]
\centering
\includegraphics[width=0.90\columnwidth]{images/fig_ebbinghaus_decay}
\caption{Retention trajectories showing rapid decay for routine commutes, persistent retention for traumatic shocks, and recall reinforcement.}
\label{fig-decay_curve}
\end{figure}

Episodic traces decay following an Ebbinghaus exponential formulation. We modulate memory retention $R(\Delta t)$ by event severity $g_m \in [0, 1]$:
\[R(\Delta t) = \exp\left(-\frac{\Delta t}{\tau(g_m)}\right)\]

The memory lifespan $\tau(g_m)$ expands proportionally with experienced trauma:
\[\tau(g_m) = \min(S_0 \cdot (1 + k \cdot g_m), \tau_{\max})\]

We set baseline stability $S_0 = 2.80$ days, sensitivity multiplier $k = 6.0$, and maximum lifespan $\tau_{\max} = 30.0$ days. Consequently, a mundane commute exhibits a half-life of 1.94 days. In contrast, a severe accident reaches a half-life of 13.6 days.

Figure~\ref{fig-decay_curve} contrasts our calibrated mobility decay against the classical Park et al. baseline and demonstrates active recall reinforcement.

Each time an episodic trace ranks in the final top-10 decision context, its reference timestamp refreshes. Furthermore, its lifespan $\tau$ increases by one full day.

\subsection{11.6 Concept Evolution, Laplace Confidence, and Dual Extinction Mechanics}

Reflections consolidate episodic experiences into generalized conceptual beliefs. We represent each concept as a formal 5-tuple:
\[\text{Concept} = \langle \text{content}, \text{keywords}, \text{spatial\_scope}, \text{temporal\_scope}, \text{objective} \rangle\]

\begin{table}[h]
\centering
\caption{Four structured operations governing conceptual belief evolution.}
\label{tab-concept_ops}
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

During consolidation, the model inspects existing active beliefs and applies one of the four structured mutations listed in Table~\ref{tab-concept_ops}.

We evaluate belief reliability using Laplace's rule of succession (1814):
\[\text{Conf}(c) = \frac{\text{obs} + 1}{\text{obs} + \text{contre} + 2}\]

When accumulated counter-examples drive confidence below 0.50, the agent deactivates the concept. The system records the exact deactivation timestamp without deleting the underlying record. This dated retirement provides an empirical marker of habit abandonment.

In accordance with Tulving's dual-memory taxonomy (1972), our architecture implements two distinct extinction pathways. Semantic knowledge is extinguished strictly through empirical contradiction, never through calendar time. Conversely, episodic traces are pruned when retention strength drops below 1\% ($R < 0.01$).

Mundane commutes vanish after 13 days of non-recall. Traumatic memories persist for over 90 days.

\subsection{11.7 Working Context Formulation and Prompt Injection}

\begin{table}[h]
\centering
\caption{Structure of the three deterministic working context blocks.}
\label{tab-working_context}
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

Decisions do not feed raw unstructured memory streams to the language model. Instead, the simulation controller compiles memory states into three deterministic context blocks. Table~\ref{tab-working_context} outlines their structure and operational sources.

These three blocks form the agent working context (Packer et al., 2023). They inject directly into the Jinja2 decision template alongside the physical choice set, enabling transparent and bounded modal choices.
"""

Path("docs/paper/article-court/appendices/chapters/11_multi_agent_specification.tex").write_text(tex_ch11.strip() + "\n")
print("Reordered Chapter 11 floats.")
