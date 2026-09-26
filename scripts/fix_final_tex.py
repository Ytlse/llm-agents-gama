from pathlib import Path
import re

CHAPTERS = Path("docs/paper/article-court/appendices/chapters")

# 1. Fix 01_demographic_control.tex: convert markdown table to tabular
c1 = (CHAPTERS / "01_demographic_control.tex").read_text()
# find table markdown
tab1_raw = """| Controlled trait | Survey base | Source | Max gap (pt) | Within $\\pm 1.0$ pt bound |
|---|---|---|---:|:---:|
| Age class (6 classes) | Persons $\\ge 5$ years | Official survey report | 0.50 | Pass |
| Occupation (8 modalities) | Persons $\\ge 5$ years | Official survey report | 0.50 | Pass |
| Five-year age (15 classes) | Persons $\\ge 5$ years | Survey microdata (recomputed) | 0.29 | Pass |
| Car ownership (individual) | Persons $\\ge 18$ years | Survey microdata (recomputed) | 0.09 | Pass |
| Car ownership (household) | Households | Official survey report | 0.06 | Pass |
| Residential ring (3 rings) | Persons $\\ge 5$ years | Official survey report | 0.06 | Pass |
| Ring $\\times$ car ownership | Persons $\\ge 5$ years | Survey microdata (recomputed) | 0.05 | Pass |
| Household size (1 to 5+ persons) | Households | Survey microdata (recomputed) | 0.06 | Pass |
| Driving licence (18 and over) | Persons $\\ge 18$ years | Survey microdata (recomputed) | 0.01 | Pass |
| Public transit pass subscription | Persons $\\ge 5$ years | Survey microdata (recomputed) | 0.05 | Pass |
| Dwelling type (house / apartment) | Households | Survey microdata (recomputed) | 0.04 | Pass |
| Gender (female / male) | Persons $\\ge 5$ years | Survey microdata (recomputed) | 0.02 | Pass |
| People with no trip on previous day | Persons $\\ge 5$ years | Survey microdata (recomputed) | 0.05 | Pass |"""

tab1_tex = r"""\begin{table*}[t]
\centering
\caption{Demographic control of the sealed synthetic cohort against the Cerema EMC² 2023 survey.}
\label{tab-demographic-margins}
\small
\begin{tabularx}{\textwidth}{l l l r c}
\toprule
\textbf{Controlled trait} & \textbf{Survey base} & \textbf{Source} & \textbf{Max gap (pt)} & \textbf{Bound} \\
\midrule
Age class (6 classes) & Persons $\ge 5$ years & Official survey report & 0.50 & Pass \\
Occupation (8 modalities) & Persons $\ge 5$ years & Official survey report & 0.50 & Pass \\
Five-year age (15 classes) & Persons $\ge 5$ years & Survey microdata & 0.29 & Pass \\
Car ownership (individual) & Persons $\ge 18$ years & Survey microdata & 0.09 & Pass \\
Car ownership (household) & Households & Official survey report & 0.06 & Pass \\
Residential ring (3 rings) & Persons $\ge 5$ years & Official survey report & 0.06 & Pass \\
Ring $\times$ car ownership & Persons $\ge 5$ years & Survey microdata & 0.05 & Pass \\
Household size (1 to 5+ persons) & Households & Survey microdata & 0.06 & Pass \\
Driving licence (18 and over) & Persons $\ge 18$ years & Survey microdata & 0.01 & Pass \\
Transit pass subscription & Persons $\ge 5$ years & Survey microdata & 0.05 & Pass \\
Dwelling type (house / apt) & Households & Official survey report & 0.04 & Pass \\
Gender (female / male) & Persons $\ge 5$ years & Survey microdata & 0.02 & Pass \\
No trip on previous day & Persons $\ge 5$ years & Survey microdata & 0.05 & Pass \\
\bottomrule
\end{tabularx}
\end{table*}"""

c1 = c1.replace(r"\emph{Table 1.1. Demographic control of the sealed synthetic cohort against the Cerema EMC² 2023 survey.}", "")
c1 = c1.replace(tab1_raw, tab1_tex)
# Move table float before line mentioning Table 1.1
c1 = c1.replace("Table 1.1", r"Table~\ref{tab-demographic-margins}")
ref_pos = c1.find(r"Table~\ref{tab-demographic-margins}")
tbl_pos = c1.find(r"\begin{table*}")
tbl_end = c1.find(r"\end{table*}") + len(r"\end{table*}")
if ref_pos != -1 and tbl_pos != -1 and ref_pos < tbl_pos:
    tbl_block = c1[tbl_pos:tbl_end]
    c1 = c1[:tbl_pos] + c1[tbl_end:]
    # insert before the paragraph of ref_pos
    p_start = c1.rfind("\n\n", 0, ref_pos)
    p_start = 0 if p_start == -1 else p_start + 2
    c1 = c1[:p_start] + tbl_block + "\n\n" + c1[p_start:]

(CHAPTERS / "01_demographic_control.tex").write_text(c1)
print("✓ Fixed 01_demographic_control.tex")

# 2. Fix 02_protocol_variables.tex
c2 = (CHAPTERS / "02_protocol_variables.tex").read_text()
# Find table 2.1 markdown
m_tab2 = re.search(r"\| Variable name \| Data type \|.*?\n(?=\\subsection|\Z)", c2, re.DOTALL)
if m_tab2:
    tab2_raw = m_tab2.group(0).strip()
    tab2_tex = r"""\begin{table*}[t]
\centering
\caption{Complete 21-variable feature dictionary of the information contract.}
\label{tab-feature-dict}
\small
\begin{tabularx}{\textwidth}{l l l X}
\toprule
\textbf{Variable name} & \textbf{Data type} & \textbf{Modalities / Range} & \textbf{Description} \\
\midrule
\texttt{age} & Integer & 5--100 & Persona chronological age \\
\texttt{sexe} & Categorical & male, female & Persona administrative sex \\
\texttt{csp} & Categorical & 8 modalities & Occupation category \\
\texttt{revenu\_fiscal} & Float & Positive & Household tax revenue \\
\texttt{nb\_pers} & Integer & 1--8 & Household total size \\
\texttt{nb\_enf} & Integer & 0--6 & Number of children under 18 \\
\texttt{nb\_voitures} & Integer & 0--4 & Total vehicles in household \\
\texttt{nb\_velos} & Integer & 0--6 & Total bicycles in household \\
\texttt{permis\_conduire} & Boolean & True, False & Driving license possession \\
\texttt{abonnement\_tc} & Boolean & True, False & Transit pass ownership \\
\texttt{commune\_resid} & Integer & INSEE code & Residential municipality code \\
\texttt{couronne} & Categorical & center, ring1, ring2 & Urban perimeter ring \\
\texttt{type\_logement} & Categorical & house, apartment & Residential dwelling typology \\
\texttt{motif} & Categorical & 9 modalities & Primary trip purpose \\
\texttt{heure\_dep} & Float & 0.0--24.0 & Scheduled departure hour \\
\texttt{heure\_arr} & Float & 0.0--24.0 & Expected arrival hour \\
\texttt{distance\_vol} & Float & Positive (km) & Euclidean origin-destination distance \\
\texttt{options\_modes} & List & Subset of 4 modes & Feasible candidate mode options \\
\texttt{options\_durees} & List & Positive (minutes) & Routing durations per candidate mode \\
\texttt{options\_couts} & List & Positive (euros) & Monetary trip expenses per mode \\
\texttt{meteo\_courante} & Categorical & 4 states & Weather during departure interval \\
\bottomrule
\end{tabularx}
\end{table*}"""
    c2 = c2.replace(r"\emph{Table 2.1. Complete 21-variable feature dictionary of the information contract.}", "")
    c2 = c2.replace(tab2_raw, tab2_tex)
    c2 = c2.replace("Table 2.1", r"Table~\ref{tab-feature-dict}")
    ref_pos2 = c2.find(r"Table~\ref{tab-feature-dict}")
    tbl_pos2 = c2.find(r"\begin{table*}")
    tbl_end2 = c2.find(r"\end{table*}") + len(r"\end{table*}")
    if ref_pos2 != -1 and tbl_pos2 != -1 and ref_pos2 < tbl_pos2:
        tbl_block2 = c2[tbl_pos2:tbl_end2]
        c2 = c2[:tbl_pos2] + c2[tbl_end2:]
        p_start2 = c2.rfind("\n\n", 0, ref_pos2)
        p_start2 = 0 if p_start2 == -1 else p_start2 + 2
        c2 = c2[:p_start2] + tbl_block2 + "\n\n" + c2[p_start2:]
    (CHAPTERS / "02_protocol_variables.tex").write_text(c2)
    print("✓ Fixed 02_protocol_variables.tex")

# 3. Fix 05_news_shocks.tex: R9 on fig-propension
c5 = (CHAPTERS / "05_news_shocks.tex").read_text()
# Figure fig-propension
fig_prop_pattern = re.compile(r"\\begin\{figure\}.*?\\label\{fig-propension\}.*?\\end\{figure\}", re.DOTALL)
m_fig_prop = fig_prop_pattern.search(c5)
if m_fig_prop:
    fig_str = m_fig_prop.group(0)
    ref_idx = c5.find(r"\ref{fig-propension}")
    if ref_idx != -1 and ref_idx < m_fig_prop.start():
        c5 = c5[:m_fig_prop.start()] + c5[m_fig_prop.end():]
        p_s = c5.rfind("\n\n", 0, ref_idx)
        p_s = 0 if p_s == -1 else p_s + 2
        c5 = c5[:p_s] + fig_str + "\n\n" + c5[p_s:]
    (CHAPTERS / "05_news_shocks.tex").write_text(c5)
    print("✓ Fixed 05_news_shocks.tex")

# 4. Fix 06_stratified_errors.tex: R9 on fig-dim-voiture and fig-modes-occ
c6 = (CHAPTERS / "06_stratified_errors.tex").read_text()
for fig_lbl in ["fig-dim-voiture", "fig-modes-occ"]:
    pat = re.compile(r"\\begin\{figure\*?\}.*?\\label\{" + fig_lbl + r"\}.*?\\end\{figure\*?\}", re.DOTALL)
    m = pat.search(c6)
    if m:
        fig_str = m.group(0)
        ref_idx = c6.find(r"\ref{" + fig_lbl + "}")
        if ref_idx != -1 and ref_idx < m.start():
            c6 = c6[:m.start()] + c6[m.end():]
            p_s = c6.rfind("\n\n", 0, ref_idx)
            p_s = 0 if p_s == -1 else p_s + 2
            c6 = c6[:p_s] + fig_str + "\n\n" + c6[p_s:]
(CHAPTERS / "06_stratified_errors.tex").write_text(c6)
print("✓ Fixed 06_stratified_errors.tex")

