% =====================================================================
% GAMA_DAYS_ABSTRACT_EN_TEX.md — source LaTeX pour les GAMA Days 2026.
% Version v2.3 (21 septembre 2026). Document complet, classe gamadays.
%
% Textes miroirs, à tenir dans la même passe :
%   GAMA_DAYS_ABSTRACT_FR.md  (français, + annexe des mesures)
%   GAMA_DAYS_ABSTRACT_EN.md  (anglais, texte courant seul)
%
% Longueur du corps du résumé : 497 mots, notes exclues (488 à la v1.0 soumise,
%   493 à la v2.2). Ce fichier porte le texte et le décompte qui font foi :
%   python3 scripts/paper/compter_mots_latex.py docs/paper/gama_days/GAMA_DAYS_ABSTRACT_EN_TEX.md
%   Les deux notes portent la source de l'enquête et la référence Liu, Yang & Yin ;
%   elles ne comptent pas dans la longueur, seule l'accroche dans le corps se paie.
%
% Chiffres du texte et leurs sources — tous sur le jeu corrigé du ticket 088 :
%   3 299 déplacements  -> data/population/population_1000_AAMAS/MANIFEST.yaml (sceau 1)
%   1 000 personas      -> idem
%   Ce sont les deux seuls chiffres du corps. Ce que le résumé ne chiffre plus vit
%   aux chapitres : écart apparié au gradient boosté 1,35 [+0,28 ; +2,47], qui
%   n'exclut pas zéro face à la forêt aléatoire ni au logit multinomial, d'où
%   « très proches, à un léger écart près » et non « au niveau des quatre »
%   (docs/paper/article/fr/06_results.md § 6.1) ; coût d'inférence, § 8.3.
%   Trace des recalculs -> docs/traces/2026-09-17_09-40_ch6_jeu_corrige_complet/
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

\author{Y. Bru\up{1}, B. Gaudou\up{1}, K. S. Oberoi\up{2} \\[6pt]
\up{1} Université Toulouse Capitole, IRIT, Toulouse, France\\
\up{2} CESI, CESI LINEACT, Toulouse, France\\
}

\date{yves.bru@gmail.com; benoit.gaudou@ut-capitole.fr; ksoberoi@cesi.fr}

\usepackage{graphicx}
\usepackage{url}

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
Existing multi-agent simulations of multimodal urban mobility either rely on tabular models estimated from household travel surveys, or on explicit rules defined by domain experts. In both these cases, the space of representable behaviours is fixed \emph{a priori}: a factor encoded as neither variable nor rule cannot influence any decision of the agent in the simulation. However, in reality, choosing a transport mode is multidimensional: objective factors like travel time, physical effort, speed and comfort intertwine with subjective factors tied to personality and experience. Integrating such decision-making complexity into a city-scale multimodal mobility simulation is a difficult task. Generative agents based on large language models (LLMs) promise to overcome this limitation. Fed on massive textual corpora, they carry decision heuristics that surveys do not record, and are able to adapt their decisions without requiring explicit rules.
\\\\
Against a certified household travel survey\footnote{Enquête Ménages Déplacements (EMD), Toulouse / Grande agglomération toulousaine (EMD, Toulouse / Grande agglomération toulousaine) --- 2023, CEREMA, Syndicat mixte des transports en commun de l'agglomération toulousaine (producteurs), PROGEDO-ADISP (diffuseur). Final report: \url{https://www.aua-toulouse.org/wp-content/uploads/2024/05/Rapport-final-68-pages-Enquete-mobilite-2023-Bassin-de-vie-toulousain.pdf}}, we measure the calibration gap between these agents and the models estimated from it, and test whether the agents adapt to situations no variable encodes. We built using GAMA a simulation of the Toulouse metropolitan area, integrating the road and rail networks and three public transport networks. A synthetic population of 1,000 individuals is generated with eqasim, and alternative itineraries are computed on the real networks with OpenTripPlanner. The simulation simulates a realistic day with realistic constraints unknown to the route planner: a car available only where it was left, the driver needed to move it, forced returns home, and the temporal chaining of activities. Each inhabitant becomes a generative agent: its mode choice rule is no longer written in the simulation model, a language model queried in batches produces it from the agent profile and the itineraries actually offered, spreading 100\,\% of the decision over them.
\\\\
Using a dataset of 3,299 trips, we compare the results of our generative agents with those of classical systems based on rigid rules or tabular data. In known situations (where the space of representable behaviors is defined a priori), generative agents produce results very close to traditional models, with a slight deviation.
Their true strength emerges in unforeseen circumstances, such as a news article mentioning bed bugs in the metro, which influences the agents' decisions. We observe an evolution in their choices over time, as well as their ability to gradually reduce the impact of this information-an adaptability that classical models cannot replicate.
\\\\
Each decision incurs an inference cost, and on an ordinary day, the representativeness of generative agents does not justify the expense: tabular models perform just as well, if not slightly better at no cost and instantly. The value of the language model lies in describing complex mode choices, especially during unforeseen circumstances. This is not possible with rule-based models and static household travel surveys. In addition, this opens the way for a hybrid architecture\footnote{Toward LLM-agent-based modeling of transportation systems: a conceptual framework, Liu, Yang \& Yin, arXiv:2412.06681, where hybrid modelling is proposed as a near-term integration strategy.}: the tabular model would handle the nominal regime, while the language model, aligned with the inhabitants' choices, would determine when to take over and make decisions based on each individual's personality.
\end{abstract}

\begin{additionnalMaterial}
https://github.com/Ytlse/llm-urban-mode-choice
\end{additionnalMaterial}


\end{document}
