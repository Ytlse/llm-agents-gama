\documentclass{gamadays}

\usepackage{url}

% ------------------------------------------
% TITRE
% ------------------------------------------

\title{\textbf{Integrating LLM-Based Generative Agents into GAMA: Opportunities and Limits in Multimodal Transport Simulation}}


% ------------------------------------------
% AUTEUR(S)
% ------------------------------------------

% 1 auteur
% \author{L. Author \\
%  Employer, laboratory acronym}
% \date{email}
 
% plusieurs auteurs 
\author{Y. Bru\up{1}, B. Gaudou\up{1}, K. S. Oberoi\up{2} \\[6pt]
\up{1} Université Toulouse Capitole, IRIT, Toulouse, France\\
\up{2} CESI, CESI LINEACT, Toulouse, France\\
}

\date{bru.yves@protonmail.com; benoit.gaudou@ut-capitole.fr; ksoberoi@cesi.fr}

\usepackage{graphicx}
\usepackage{hyperref}
\usepackage{natbib}
%\usepackage{xcolor} %%%%%% to be removed when the colors are removed
%\usepackage[normalem]{ulem} %%%%%% to be removed when the strikethrough is removed

\begin{document}

\maketitle

\begin{keywords}
Large Language Models; Generative Agents; Urban Mobility; Mode Choice; GAMA Platform
\\\\
\end{keywords}

\begin{abstract}
Existing multi-agent simulations of multimodal urban mobility either rely on machine learning models on structured data estimated from household travel surveys, or on explicit rules defined by domain experts. In both these cases, the space of representable behaviours is fixed \emph{a priori}: a factor encoded as neither variable nor rule cannot influence any decision of the agent in the simulation. However, in reality, choosing a transport mode is multidimensional: objective factors like travel time, physical effort, speed and comfort intertwine with subjective factors tied to personality and experience. Integrating such decision-making complexity into a city-scale multimodal mobility simulation is a difficult task. Generative agents based on Large Language Models (LLMs) promise to overcome this limitation. Fed on massive textual corpora, they carry decision heuristics \citet{liu2024toward} that surveys do not record, and are able to adapt their decisions without requiring explicit rules.
\\\\
Published evaluations of generative mobility agents rarely confront them with an observed population: most compare them with rule-based agents, or with patterns their authors produced themselves. Against a certified household travel survey \citet{opentripplanner2025}, we measure the calibration gap between these agents and the models estimated from it, and test whether the agents adapt to situations no variable encodes. We built using GAMA a simulation of the Toulouse metropolitan area, integrating the road and rail networks and three public transport networks. A synthetic population of 1,000 individuals is generated with eqasim\citet{horl2021eqasim}, and alternative itineraries are computed on the real networks with OpenTripPlanner \citet{opentripplanner2025}. The simulation simulates a realistic day with realistic constraints unknown to the route planner: a car available only where it was left, the driver needed to move it, forced returns home, and the temporal chaining of activities. Each inhabitant becomes a generative agent: its mode choice rule is no longer written in the simulation model, a language model queried in batches produces it from the agent profile and the itineraries actually offered.
\\\\
Using a dataset of 3,299 trips, we compare the results of our generative agents with those of classical systems based on rigid rules or tabular data. In known situations (where the space of representable behaviors is defined a priori), our results show that generative agents are very close to traditional models, with a slight deviation.
Their true strength emerges in unforeseen circumstances, such as a news article mentioning bed bugs in the metro, which influences the agents' decisions. We observe an evolution in their choices over time, as well as their ability to gradually reduce the impact of this information-an adaptability that classical models cannot replicate.
\\\\
Each decision incurs an inference cost, and on an ordinary day, the representativeness of generative agents does not justify the expense: tabular models perform just as well, if not slightly better at no cost and instantly. The value of the language model lies in describing complex mode choices, especially during unforeseen circumstances. This is not possible with rule-based models and static household travel surveys. In addition, this opens the way for a hybrid architecture \citet{liu2024toward}: the tabular model would handle the nominal regime, while the language model, aligned with the inhabitants' choices, would determine when to take over and make decisions based on each individual's personality.


%The value of the language model lies elsewhere
%GAMA is what grounds the decision in reality: the actual geography, the transport supply, and the departure time.

\end{abstract}

\begin{additionnalMaterial}
GitHub repository: \url{https://github.com/Ytlse/llm-urban-mode-choice}.
\end{additionnalMaterial}

\begin{figure}[htbp]
    \centering
    \includegraphics[width=\linewidth]{architecture_GAMA_Agents.jpg}
    \label{fig:toulouse_transport}
    \caption{Architecture of the GAMA-generative agents coupling}
\end{figure}

\bibliographystyle{ACM-Reference-Format} 
\bibliography{sample}

\end{document}

