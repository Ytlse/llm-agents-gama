# Introduction

## 1. General Context: Multimodal Complexity and the Need for User-Centric Realism

Understanding human mobility behavior in multimodal transport systems is essential for advancing traffic planning and the design of efficient transport networks. The challenge lies not only in representing travel patterns but also in building a simulation framework that supports the study of individual behavior, the testing of behavioral hypotheses, and the development of improved, sustainable, and personalized mobility strategies.

The emergence of personalized multimodal transport systems reflects a broader shift toward user-centric mobility, where public transit, walking, cycling, and shared services are integrated to provide journeys tailored to individual preferences (Smith et al., 1995; Axhausen et al., 2016). Capturing such systems in simulation, however, is particularly challenging because mobility choices are shaped by diverse socioeconomic profiles, accessibility constraints, and personal experiences (Grignard et al., 2018). As highlighted by Oberoi (2024), personalization within the Mobility-as-a-Service (MaaS) paradigm requires addressing the heterogeneity of users—including their preferences, contexts, and accessibility needs—which remains a significant challenge for developing realistic transport models. Modeling, therefore, requires both flexibility and realism to capture heterogeneous and adaptive travel decisions across populations.

Existing transport simulations often struggle with this complexity and with the availability of data needed to calibrate models. In particular, detailed trajectory and itinerary datasets, which are critical for capturing the nuances of multimodal travel behavior, are extremely scarce (Fourez et al., 2025). Such datasets exist for a limited number of major metropolitan areas, for example, Tokyo, Japan, but are largely unavailable elsewhere (Feng et al., 2024, 2025). This dependence on scarce calibration data restricts the applicability and transferability of existing models in smaller or less data-rich regions. Moreover, integrating multiple external data sources requires extensive rule engineering, producing brittle models that are difficult to scale and prone to failure in unforeseen conditions.

---

## 2. Related Work: From Econometric Utility to Behavioral Psychology and Generative Agents

### 2.1 From Calculated Utility to Empirical Cognitive Biases
To model travel choices without requiring exhaustive trajectory tracking, transportation engineering has historically relied on **Discrete Choice Models (DCM)** grounded in Random Utility Maximization (RUM) (McFadden, 1974; Ben-Akiva & Lerman, 1985; Train, 2002). In these frameworks (e.g., Multinomial Logit, Mixed Logit), mode choice is mathematically formulated as the maximization of an explicit utility function balancing travel time, monetary cost, and socioeconomic coefficients. While mathematically tractable and calibratable on aggregate travel surveys, these models operate under the assumption of unbounded economic rationality (or static taste variations). They structurally struggle to capture the **bounded rationality** and **cognitive biases** that fundamentally govern daily human mobility.

Empirical behavioral research demonstrates that human modal choice rarely stems from a cold calculation of global utility. Instead, it is steered by decision heuristics, perceptual distortions, and habit persistence. As established by Adam & Gaudou (2025), travelers systematically apply **asymmetric perceptual filters**: underestimating the true operating and ownership costs of private cars while overestimating the friction, waiting times, and discomfort of public transit. Furthermore, mobility decisions are heavily constrained by unobserved psychological constructs rooted in social psychology (e.g., the Theory of Planned Behavior): acute time sensitivity, cost aversion, and technological affinity constitute key determinants of mode choice, particularly in on-demand or multimodal settings (Sameen et al., 2025 [SAPA]; Chu & Guo, 2023). Conventional tabular econometric models remain blind to these subjective dimensions, as travel surveys seldom record psychometric attitudes.

### 2.2 The Emergence of Generative Agents (LLMs) in Transport Simulation
In response to the rigidities of manual rule engineering and the behavioral limits of pure utility functions, the multi-agent systems (MAS / ABM) community has recently turned toward Large Language Models (LLMs) to instantiate **cognitive generative agents** (Park et al., 2023; Chopra et al., 2024). By embedding foundation models as decision engines, researchers aim to endow synthetic travelers with natural language reasoning, episodic memory, and subjective deliberation capabilities without requiring explicit decision trees (Liu et al., 2024).

Early implementations in urban mobility have demonstrated promising qualitative expressiveness: generative travelers can evaluate complex trade-offs, interpret environmental cues, and adapt their daily schedules or rerouting decisions in response to road disruptions (Bougie & Watanabe, 2025 [CitySim]; Vu, Gaudou & Oberoi, 2025; Alves et al., 2026). By synthesizing personas and latent behavioral attitudes from coarse demographic data (Sameen et al., 2025; Argyle et al., 2022), LLMs offer the seductive prospect of "zero-shot" behavioral realism, ostensibly bypassing both brittle rule engineering and the scarcity of fine-grained trajectory data.

---

## 3. The Scientific Gap: Narrative Plausibility vs. Distributional Fidelity

However, this qualitative expressiveness conceals a fundamental epistemological pitfall: **linguistic plausibility does not equate to psychological validity or statistical fidelity**.

While an LLM agent can articulate fluent and seemingly rational justifications for its travel choices, recent audit benchmarks reveal a persistent *knowledge-to-simulation gap* (Meister et al., 2024). When prompted with sociodemographic personas, generative agents frequently yield stereotyped, caricatured responses that reflect global internet pre-training priors rather than the localized behavioral realities of a specific metropolitan population (Meister et al., 2024; Choi et al., 2026; Łajewska et al., 2026). In mobility simulation, this manifests as acute structural distortions—such as an exaggerated environmentalist affinity for cycling paired with a severe under-representation of routine short-distance walking.

This scientific lock has been formally conceptualized by the **SILICA** benchmark (Bin Tareaf et al., 2026), which defines three hierarchical tiers of validation for LLM agent populations:
1. **Tier 1 (Nominal Emergence):** Behaviors observed under standard, arbitrary benchmark prompts.
2. **Tier 2 (Qualitative Robustness & Adaptation):** Behaviors that remain qualitatively stable under structural perturbations (prompt reframing, option shuffling, memory resets, and incentive variations).
3. **Tier 3 (Quantitative Distributional Fidelity):** The exact quantitative replication of empirical human behavioral distributions.

Across more than 9,000 systematic multi-agent simulations, SILICA established that **no LLM society achieves Tier 3 fidelity**. As synthesized by Andrea Baronchelli (2025, 2026), this draws an unyielding epistemological boundary between two distinct paradigms:
* **LLMs as "Statistical Human Proxies":** Deploying uncalibrated LLM agents to predict the nominal modal split of an urban area inevitably hits an insurmountable **"Tier 3 Ceiling"** unless heavily constrained by supervised models.
* **LLMs as "Complex Adaptive Systems":** Generative agents possess authentic **Tier 2** value when adapting to unforeseen, non-tabulated contexts (unstructured news articles) and simulating longitudinal inertia (behavioral hysteresis).

In urban transportation, this tension is exacerbated by the primacy of physical network constraints. While recent literature focuses heavily on automated prompt engineering (e.g., APE, ProTeGi, OPRO, MIPRO; Zhou et al., 2022; Pryzant et al., 2023; Yang et al., 2023; Opsahl-Ong et al., 2024), nominal mode choice remains fundamentally constrained by spatial topology, schedules, and access times. Determining whether prompt enrichment can overcome these distortions or whether it hits a structural ceiling constitutes a critical methodological question. Deploying LLM agents indiscriminately across an entire metropolitan population risks severe distributional skew, while incurring prohibitive computational latency and inference costs (Chopra et al., 2024; Alves et al., 2026).

---

## 4. Objectives and Contributions of the Paper

This paper delivers a full-scale **empirical stress-test** of generative agents applied to mode choice, benchmarked against real-world travel survey data in the metropolitan area of Toulouse, France (the certified Cerema EMC² 2023 household travel survey, covering 16,000 respondents across 785 fine zones). By confronting LLM agents with econometric baselines and a supervised tabular oracle under **strict informational parity**, we delineate precisely where LLMs fail as statistical proxies and where they provide authentic behavioral value.

Our core contributions are organized around four major axes:

1. **A Strict Informational Parity Benchmark at Dual Scales (Macro & Micro):**  
   We establish an uncompromised 21-variable contract (`spec_version 2`) evaluated on a demographically representative synthetic cohort ($N = 1,000$ agents across 514 complete households, validated via TOST equivalence testing within $\pm 1\text{ pt}$ on 13 census and mobility margins) and on a sealed ground-truth test set of $13,045$ survey trips. We benchmark three LLM families (Mistral AI, local deterministic Qwen-2.5-32B, Google Gemini) against the econometric baseline (Multinomial Logit) and a state-of-the-art supervised oracle (LightGBM; Ke et al., 2017), strictly enforcing argmax-to-argmax comparability and choice-set renormalization (IIA).

2. **Evaluation of Semantic Enrichment and Empirical Proof of the Tier 3 Ceiling:**  
   Through a systematic 4-tier ablation study (Tier 0: travel-time heuristics and statistical floors; Tier 1: bare model without behavioral instructions; Tier 2: enriched prompt integrating detailed personas, a 4-step decision grid, qualitative mode guidelines, and daily trip chaining; Tier 3: tabular statistical baselines), we quantify the real impact of prompt engineering. We demonstrate that even an enriched, highly directive prompt yields only a marginal gain ($\Delta S < 1.5\text{ pt}$) and remains powerless against structural distribution biases (walking remains severely under-estimated at $11.9\%$ vs. $26.8\%$ observed, while cycling is over-represented at $13.3\%$ vs. $4.1\%$). In contrast, physical impedance calculated by OpenTripPlanner—specifically terminal walking and parking access times—fundamentally dictates modal choice (a 7-minute physical adjustment brings a $-4.52\text{ pt}$ gain, three times the effect of prompt enrichment). This experimentally materializes the Tier 3 Ceiling documented by SILICA in nominal regimes.

3. **Demonstration of Tier 2 Value-Add in Non-Tabulated Regimes:**  
   We demonstrate where generative agents provide authentic behavioral breakthroughs that tabular models cannot capture:
   * *5-Day Longitudinal Behavioral Hysteresis:* Leveraging an episodic short-term memory buffer $\mathcal{M}_t$ (Park et al., 2023), LLM agents simulate realistic avoidance, churn, and progressive recovery kinetics over 5 days following an acute transit breakdown (e.g., subway line failure), overcoming the memoryless nature of tabular baselines.
   * *Ecological Adaptation to Local News Media:* Exposing agents to 30 real, localized news articles (strikes, heatwaves, major infrastructure works) within a pre-registered 5-condition protocol (raw text, mode-neutral paraphrase, placebo, informed oracle), benchmarked against 120 pre-registered expert directional predictions.

4. **Formalization of a Cascading Hybrid Architecture:**  
   To resolve the dichotomy between statistical fidelity and semantic adaptability, we propose an operational cascading architecture: delegating $90\%$ of the nominal, routine commuter flow to the high-throughput tabular oracle (Tier 3), while routing the $10\%$ of travelers experiencing complex disruptions or semantic news shocks to cognitive LLM agents (Tier 2), slashing inference costs and token consumption by a factor of ten.

---

## 5. Paper Organization

The remainder of this paper is structured as follows:
* **Section 2** formalizes our macro- and microscopic evaluation metrics and details the demographic validation of our synthetic cohort (Milestone 0).
* **Section 3** evaluates bare LLM performance across multiple models and quantifies stochastic multi-seed variability across 5 fixed random seeds.
* **Section 4** details the ablation study confronting the bare model with the prompt enriched with a behavioral decision grid and qualitative guidelines, complemented by microscopic (trip-level) evaluation against the supervised LightGBM oracle, materializing the Tier 3 Ceiling.
* **Section 5** demonstrates the Tier 2 value-add of generative agents through 5-day behavioral hysteresis kinetics and ecological adaptation to 30 local news events.
* **Section 6** develops the prospective cascading hybrid architecture and discusses metropolitan scalability.
* Finally, **Section 7** concludes with key takeaways and perspectives for urban mobility modeling.
