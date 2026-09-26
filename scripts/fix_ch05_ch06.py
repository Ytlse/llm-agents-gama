from pathlib import Path
import re

CHAPTERS = Path("docs/paper/article-court/appendices/chapters")

# Fix 05_news_shocks.tex
c5 = (CHAPTERS / "05_news_shocks.tex").read_text()
sec55 = r"""\subsection{Longitudinal Extinction and Household Transmission}

\begin{figure}[tp]
  \centering
  \includegraphics[width=0.95\columnwidth]{images/ch7_propension_quotidienne.png}
  \caption{Daily modal propensity towards private car following an unexpected incident.}
  \label{fig-propension}
\end{figure}

\begin{figure}[tp]
  \centering
  \includegraphics[width=0.95\columnwidth]{images/ch7_affinites_tous_modes.png}
  \caption{Declared multi-criteria affinities across modes, exposed vs control agent.}
  \label{fig-affinites}
\end{figure}

We track how shock perceptions propagate and extinguish over longitudinal multi-day runs. Figure~\ref{fig-propension} demonstrates the temporal trajectory of modal propensity following a disruption. Figure~\ref{fig-affinites} plots stated multi-criteria affinity ratings across four milestones.
"""

# Find \subsection{Longitudinal Extinction...}
idx_start = c5.find(r"\subsection{Longitudinal Extinction and Household Transmission}")
idx_end = c5.find(r"\subsection{Pending Campaign Execution and Status}")
if idx_start != -1 and idx_end != -1:
    c5 = c5[:idx_start] + sec55 + "\n\n" + c5[idx_end:]
    (CHAPTERS / "05_news_shocks.tex").write_text(c5)
    print("✓ Fixed 05_news_shocks.tex")

# Fix 06_stratified_errors.tex
c6 = (CHAPTERS / "06_stratified_errors.tex").read_text()

sec63 = r"""\subsection{Visualizations of Multi-Dimensional Error Profiles}

\begin{figure*}[tp]
  \centering
  \includegraphics[width=\textwidth]{images/ch99_dimensions_voiture.png}
  \caption{Car share by stratum across six dimensions, minimal vs expert prompt against survey and tabular reference.}
  \label{fig-dim-voiture}
\end{figure*}

\begin{figure*}[tp]
  \centering
  \includegraphics[width=\textwidth]{images/ch99_modes_distance.png}
  \caption{Four transport modes broken down by distance band.}
  \label{fig-modes-dist}
\end{figure*}

\begin{figure*}[tp]
  \centering
  \includegraphics[width=\textwidth]{images/ch99_modes_occupation.png}
  \caption{Four transport modes across eight occupation categories.}
  \label{fig-modes-occ}
\end{figure*}

\begin{figure*}[tp]
  \centering
  \includegraphics[width=\textwidth]{images/ch99_modes_motif.png}
  \caption{Four transport modes across six trip purposes.}
  \label{fig-modes-motif}
\end{figure*}

We provide four multi-panel visual figures examining stratified modal behavior.

Figure~\ref{fig-dim-voiture} displays car shares across six dimensions. On the first four dimensions, the expert prompt sits substantially closer to the target than the minimal baseline. On residential ring and housing type, both LLM series remain distant from empirical targets.

Figure~\ref{fig-modes-dist} breaks down the four transport modes by distance band. Car and walking predictions closely track ground truth beyond one kilometer. Public transit displays persistent overestimation between two and twenty kilometers.

Figure~\ref{fig-modes-occ} examines modal distributions across eight occupation categories. School-age categories exhibit the highest cycling shares, reaching 8.2\% and 13.3\% under the expert prompt versus 4.2\% and 4.0\% in the survey.

Figure~\ref{fig-modes-motif} plots the four modes across six trip purposes. Educational trips produce the largest divergence following prompt engineering, shifting heavily toward private vehicles.
"""

idx6_start = c6.find(r"\subsection{Visualizations of Multi-Dimensional Error Profiles}")
idx6_end = c6.find(r"\subsection{Strata Degraded by Expert Prompt Tuning}")
if idx6_start != -1 and idx6_end != -1:
    c6 = c6[:idx6_start] + sec63 + "\n\n" + c6[idx6_end:]
    (CHAPTERS / "06_stratified_errors.tex").write_text(c6)
    print("✓ Fixed 06_stratified_errors.tex")

