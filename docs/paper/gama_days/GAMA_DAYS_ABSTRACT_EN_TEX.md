% =====================================================================
% GAMA_DAYS_ABSTRACT_EN_TEX.md — source LaTeX soumis aux GAMA Days 2026.
% Version v1.0 (9 septembre 2026). Document complet, classe gamadays,
% copie conforme de ce qui part sur Overleaf.
%
% Textes miroirs, à tenir dans la même passe :
%   GAMA_DAYS_ABSTRACT_FR.md  (français, où se fait la rédaction, + annexe des mesures)
%   GAMA_DAYS_ABSTRACT_EN.md  (anglais, décompte de mots de référence)
%
% Longueur du corps du résumé : 488 mots, notes exclues.
%
% Chiffres mesurés et leurs sources :
%   26.5 / 15.3 / 12.6  -> data/experiences/exp_gemini-35-fl_expcham5_jtir_t0_nosim_2/executions/2026-09-08_20_28_52/scores.json
%                          (12.6 = composite.emd_jsd ; l'écart L1 du même run vaut 35.2)
%   29.9                -> data/experiences/exp_majvoiture_nosim/executions/2026-09-07_21_22_45/scores.json
%    4.9                -> data/experiences/exp_lgbm_jtir_nosim/executions/2026-09-08_05_48_45/scores.json
%   12.4 / 26.8         -> scripts/data/population/cerema_values.yaml (cibles EMC2 2023)
%   1 000 personas      -> data/population/population_1000_AAMAS/MANIFEST.yaml (sceau 1)
%
% Dépendances hors dépôt : classe gamadays.cls, image architecture_GAMA_Agents.jpg.
% =====================================================================

\documentclass{gamadays}

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

\date{yves.bru@gmail.com; benoit.gaudou@ut-capitole.fr; ksoberoi@cesi.fr}

\usepackage{graphicx}

\begin{document}

\maketitle

\begin{figure}[htbp]
    \centering
    \includegraphics[width=1.1\linewidth]{architecture_GAMA_Agents.jpg}
    \label{fig:toulouse_transport}
\end{figure}


\begin{keywords}
Large Language Models; Generative Agents; Urban Mobility; Mode Choice; GAMA Platform
\\\\
\end{keywords}

\begin{abstract}
Multi-agent simulations of urban mobility traditionally rely on tabular models, discrete choice models or supervised learners estimated from surveys, or on explicit rule systems. In both cases the space of representable behaviours is fixed a priori by the specification: a factor that has not been encoded as a variable or a rule cannot influence any decision. Generative agents based on large language models (LLMs) promise to overcome this limitation. Using a certified household travel survey, we measure the calibration gap between these agents and traditional models estimated from it, and we test whether they adapt to situations that no variable encodes.
\\\\
We built on GAMA a simulation platform of the Toulouse metropolitan area, integrating the road and rail networks and the three public transport networks. A synthetic population of 1,000 individuals is generated with eqasim, and alternative itineraries are computed on the real networks with OpenTripPlanner. The model carries the constraints that make a day realistic and that no route planner knows: the spatial chaining of vehicles, a car available only where it was left, the driver needed to move it, forced returns home, and the temporal chaining of activities. Each inhabitant becomes a generative agent: its mode choice rule is no longer written in the model, it is produced by a large language model queried in batches, which receives the agent's profile and the itineraries actually offered and spreads 100\,\% of the decision over them.
\\\\
All decision makers are compared on this same substrate against the modal shares of the 2023 EMC\textsuperscript{2} survey (CEREMA). Three references frame the comparison at identical variables: an empirical prior, always the car, as a floor; the multinomial logit as the econometric reference; and a supervised LightGBM oracle estimated on the survey as a ceiling.
\\\\
Statistical calibration fails. The simulated modal shares show major systematic biases\footnote{ Measurements of 8 September 2026 on a sealed cohort of 1,000 personas / 2,636 trips decided. Generative agent: Gemini 3.5 Flash-Lite, temperature 0.0, prompt template \texttt{expert\_chaine\_m5}.}: over-attraction to public transport, 26.5\%\ against 12.4\% observed, and underestimation of walking, 15.3\% against 26.8\%. Our composite gap\footnote{ The composite score sums the divergence on the overall modal shares and within the age, gender, occupation, purpose and distance strata, Earth mover's distance for ordinal variables and Jensen--Shannon for nominal ones.} to the observed distributions, to be minimised, is 12.6, against 29.9 for the empirical prior and 4.9 for the oracle. In exchange, we probe two regimes no memoryless tabular model can produce: adaptation to real events from the local press, and behavioural hysteresis over five days after a major metro breakdown, carried by a short-term memory register that revises the perception of risk. We report the share of modal shifts and the re-adoption rate, against a control agent without memory.
\\\\
We draw implications for hybrid architectures, in which the tabular model secures calibration in the nominal regime and the generative agent handles departures from it. GAMA is not a host here: it is what grounds the decision in the terrain. The language model produces reasoning, the simulation produces the situation that reasoning applies to, the real geography, the transport supply at departure time, and the day that constrains the next. Without that grounding, the agent would deliberate in a vacuum.
\\
\end{abstract}

\begin{additionnalMaterial}
https://github.com/Ytlse/llm-urban-mode-choice
\end{additionnalMaterial}


\end{document}
