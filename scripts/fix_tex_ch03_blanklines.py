from pathlib import Path

CHAPTERS = Path("docs/paper/article-court/appendices/chapters")

tex_ch03 = r"""\section{3. Mathematical Foundations of Distributional Metrics and Sample Size Bias}

This chapter formalizes the mathematical metrics used to evaluate aggregate behavioral alignment. We detail the composite loss function and prove the statistical necessity of equal sample sizes.

\subsection{3.1 Formal Definitions of Distributional Metrics}

Macro-level behavioral validation compares simulated modal distributions against observed survey distributions. We employ three complementary divergence metrics.

First, we compute the global $L_1$ distance across travel modes.

\[
L_1(\hat{P}, P^*) = \sum_{m \in \mathcal{M}} |\hat{P}_m - P_m^*|
\]

Here $\mathcal{M} = \{\text{car}, \text{foot}, \text{transit}, \text{bike}\}$ denotes candidate modes.

Second, we evaluate nominal demographic strata using the symmetric Jensen-Shannon Divergence in base 2.

\[
\mathrm{JSD}(P \parallel Q) = \frac{1}{2}\mathrm{KL}(P \parallel M) + \frac{1}{2}\mathrm{KL}(Q \parallel M), \quad M = \frac{1}{2}(P + Q)
\]

Here $\mathrm{KL}$ denotes the Kullback-Leibler divergence. We scale the metric by 100 to express results in percentage points.

Third, we evaluate ordinal dimensions using the Earth Mover's Distance. We compute the metric on cumulative distribution functions.

\[
\mathrm{EMD}(P, Q) = \frac{1}{K-1} \sum_{k=1}^{K-1} |F_P(k) - F_Q(k)| \times 100
\]

Here $F_P$ and $F_Q$ denote the cumulative distributions across the $K$ ordered bins.

\subsection{3.2 The Composite Loss Function}

The composite loss function $\mathcal{C}_{\text{EMD–JSD}}$ combines global distribution error and stratified divergences. We formalize this evaluation metric across dimensions.

\[
\mathcal{C}_{\text{EMD–JSD}} = \mathrm{JSD}^{\text{global}} + \sum_{d \in \mathcal{D}_{\text{nom}}} w_d \overline{\mathrm{JSD}}^d + \sum_{d \in \mathcal{D}_{\text{ord}}} w_d \overline{\mathrm{EMD}}^d
\]

The nominal dimensions $\mathcal{D}_{\text{nom}}$ comprise occupation, trip purpose, and gender. The ordinal dimensions $\mathcal{D}_{\text{ord}}$ comprise age brackets and distance bands. We assign fixed weights $w_{\text{global}} = 1.0$, $w_{\text{age}} = 0.5$, $w_{\text{occ}} = 0.5$, and $w_{\text{purpose}} = 0.5$. In addition, we assign $w_{\text{gender}} = 0.3$ and $w_{\text{distance}} = 0.3$, excluding strata with $n < 5$.

We tested ranking sensitivity under five alternative weighting schemes with perturbations up to $\pm 50\%$. The Kendall rank correlation coefficient across the fifteen decision-makers remained above 0.94, confirming ranking stability.

\subsection{3.3 Finite-Sample Divergence Bias}

\begin{figure}[h]
\centering
\includegraphics[width=0.90\columnwidth]{images/fig_emd_jsd_explanation}
\caption{Mathematical derivation of 1D Earth Mover's Distance between cumulative distributions and finite-sample divergence bias curve.}
\label{fig-emd_bias}
\end{figure}

Divergence metrics computed on empirical samples carry an inherent upward finite-sample bias. When sample size decreases, empirical distributions exhibit greater stochastic variance, inflating both JSD and EMD.

We demonstrated this bias empirically by subsampling the reference cohort at constant decision probabilities. Reducing sample size from 881 to 81 personas artificially increases the composite score by $+5.02$ points. Consequently, comparisons across decision-makers must maintain strictly identical sample sizes.

Figure~\ref{fig-emd_bias} illustrates the cumulative formulation of 1D Earth Mover's Distance and displays the empirical finite-sample bias curve.
"""
(CHAPTERS / "03_mathematical_metrics.tex").write_text(tex_ch03.strip() + "\n")
