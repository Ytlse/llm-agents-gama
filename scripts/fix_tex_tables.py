from pathlib import Path
import re

CHAPTERS = Path("docs/paper/article-court/appendices/chapters")

# Fix 07_paired_contrasts.tex
tex_07 = r"""\section{7. Paired Resampling Hypothesis Tests across Twenty Contrast Pairs}

This chapter establishes the statistical significance of performance contrasts between decision-makers. We present cluster bootstrap hypothesis tests across twenty distinct model pairs.

\subsection{7.1 Individual-Level Cluster Bootstrap Protocol}

We compute confidence intervals using cluster bootstrap resampling at the individual persona level. We execute $B = 2{,}000$ bootstrap replicates with a fixed random seed (2026), resampling across the 868 common mobile individuals.

This clustering scheme accounts for intra-individual trip correlation. Evaluating paired differences across identical bootstrap samples cancels common variance components.

\subsection{7.2 The Twenty Paired Contrasts}

\begin{table*}[t]
\centering
\caption{Paired bootstrap differences (95\% CI) across twenty model contrasts. Bold denotes intervals excluding zero.}
\label{tab:twenty_contrasts}
\small
\begin{tabularx}{\textwidth}{lXXX}
\toprule
\textbf{Contrast pair} & \textbf{Composite difference} & \textbf{Non-single choice} & \textbf{Global $L_1$ error} \\
\midrule
\texttt{gemini-3.5} (expert $-$ minimal) & \textbf{$-2.27$} [$-3.22; -1.40$] & \textbf{$-3.59$} [$-4.83; -2.45$] & \textbf{$-10.2$} [$-12.5; -8.0$] \\
\texttt{gemini-3.1} (expert $-$ minimal) & \textbf{$-3.37$} [$-4.25; -2.45$] & \textbf{$-4.15$} [$-5.22; -3.09$] & \textbf{$-8.6$} [$-10.6; -6.8$] \\
\texttt{mistral-large} (expert $-$ minimal) & \textbf{$-7.25$} [$-8.67; -5.90$] & \textbf{$-8.63$} [$-10.28; -7.15$] & \textbf{$-18.0$} [$-22.4; -13.5$] \\
\texttt{gemini-3.5} expert $-$ Gradient boosting & \textbf{$+1.35$} [$+0.28; +2.47$] & $+1.09$ [$-0.27; +2.45$] & $+4.3$ [$-1.2; +9.7$] \\
\texttt{gemini-3.5} expert $-$ Kernel regression & \textbf{$+1.38$} [$+0.32; +2.45$] & \textbf{$+1.35$} [$+0.10; +2.69$] & \textbf{$+7.1$} [$+1.8; +12.1$] \\
\texttt{gemini-3.5} expert $-$ Random forest & $+0.94$ [$-0.06; +1.98$] & $+1.17$ [$-0.02; +2.39$] & \textbf{$+7.7$} [$+3.3; +11.7$] \\
\texttt{gemini-3.5} expert $-$ Multinomial logit & $+0.96$ [$-0.18; +2.17$] & $+0.39$ [$-1.10; +1.80$] & $+4.4$ [$-0.4; +8.5$] \\
Typed classifier $-$ Gradient boosting & $+0.05$ [$-0.82; +0.94$] & $+0.12$ [$-0.79; +1.05$] & $+1.8$ [$-2.1; +5.8$] \\
Typed classifier $-$ Random forest & $-0.36$ [$-1.25; +0.55$] & $+0.20$ [$-0.71; +1.12$] & $+5.2$ [$+1.1; +9.4$] \\
Typed classifier $-$ \texttt{gemini-3.5} expert & \textbf{$-1.30$} [$-2.21; -0.38$] & $-0.97$ [$-2.10; +0.15$] & $-2.5$ [$-6.4; +1.5$] \\
\texttt{gemini-3.1} $-$ \texttt{gemini-3.5} (expert) & \textbf{$+4.15$} [$+2.99; +5.43$] & \textbf{$+5.56$} [$+4.12; +7.02$] & \textbf{$+17.4$} [$+14.6; +20.3$] \\
\texttt{mistral-large} $-$ \texttt{gemini-3.5} (expert) & \textbf{$+2.71$} [$+1.17; +4.25$] & \textbf{$+5.24$} [$+3.76; +6.66$] & \textbf{$+12.8$} [$+8.3; +17.4$] \\
\texttt{gemini-3.1} $-$ \texttt{mistral-large} (expert) & $+1.44$ [$-0.10; +2.98$] & $+0.32$ [$-1.14; +1.82$] & $+4.6$ [$-0.1; +9.0$] \\
\texttt{gemini-3.1} $-$ \texttt{mistral-large} (minimal) & \textbf{$-2.45$} [$-4.08; -0.85$] & \textbf{$-4.16$} [$-5.89; -2.45$] & \textbf{$-4.8$} [$-7.4; -2.2$] \\
\bottomrule
\end{tabularx}
\end{table*}

Table~\ref{tab:twenty_contrasts} reports the paired differences across three evaluation metrics: the composite score, the non-single choice score, and the global $L_1$ modal share error.

\subsection{7.3 Instruction-Dependent Ranking Reversals}

The empirical ranking of models depends heavily on prompt instructions. Under the minimal prompt, \texttt{gemini-3.1} outperforms \texttt{mistral-large} by 2.45 points, an interval strictly excluding zero. In contrast, under the expert prompt, \texttt{mistral-large} surpasses \texttt{gemini-3.1} by 1.44 points.

Consequently, evaluating language models under a single prompt measures the model-prompt pair rather than the intrinsic capability of the architecture.
"""
(CHAPTERS / "07_paired_contrasts.tex").write_text(tex_07.strip() + "\n")

# Fix 12_methodological_audit.tex
tex_12 = r"""\section{12. Methodological Audit and Chronology of Twelve Scientific Rectifications}

This chapter documents the internal audit log tracking twelve methodological corrections applied during the project. We describe the discrepancies identified and the corrective procedures enforced.

\subsection{12.1 The Twelve Methodological Rectifications}

\begin{table*}[t]
\centering
\caption{Methodological audit log and corrective actions.}
\label{tab:rectifications}
\small
\begin{tabularx}{\textwidth}{r L L}
\toprule
\textbf{\#} & \textbf{Discrepancy identified in early versions} & \textbf{Corrective action applied} \\
\midrule
1 & Baseline evaluated on 15 variables & Enforced strict 21-variable contract (\texttt{spec_version 2}) \\
2 & Tabular $L_1$ compared against LLM argmax & Realined comparison to continuous probability mass \\
3 & Claimed $\chi^2$ non-rejection as proof of validity & Replaced with TOST equivalence bounds and effect sizes \\
4 & Milestone 0 presented as behavioral validation & Requalified as a baseline structural coherence check \\
5 & Composites compared across unequal sample sizes & Enforced identical sample sizes to prevent sample-size bias \\
6 & Information parity presented as symmetric & Explicitly declared exposure asymmetry (39,203 trips seen vs zero) \\
7 & Tabular model described as blind to events & Added event-informed tabular condition (C5) \\
8 & News shock evaluated without length control & Added length-matched placebo articles (C3) \\
9 & Unverified claim of "10,000x faster" & Withdrawn pending certified hardware measurements \\
10 & Disaggregate audit perimeter mismatch (1,000 vs 13,045) & Unified perimeter to 9,621 declared trips across 2,930 individuals \\
11 & Composite weights reported as normalized to 1.0 & Corrected to fixed unnormalized sum ($1.0 / 0.5 / 0.3$) \\
12 & Unreferenced demographic targets cited & Aligned all targets with official Cerema certified tables \\
\bottomrule
\end{tabularx}
\end{table*}

To guarantee scientific reproducibility, we logged every methodological revision between early drafts and the certified manuscript. Table~\ref{tab:rectifications} details these twelve rectifications.
"""
(CHAPTERS / "12_methodological_audit.tex").write_text(tex_12.strip() + "\n")

print("Fixed tables in 07 and 12.")
