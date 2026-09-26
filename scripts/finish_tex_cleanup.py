from pathlib import Path
import re

CHAPTERS = Path("docs/paper/article-court/appendices/chapters")

# 1. Fix 01_demographic_control.tex
c1 = (CHAPTERS / "01_demographic_control.tex").read_text()
m_tab1 = re.search(r"\| Controlled trait \|.*?\n(?=\\subsection|\Z)", c1, re.DOTALL)
if m_tab1:
    tab1_raw = m_tab1.group(0).strip()
    tab1_tex = r"""\begin{table*}[t]
\centering
\caption{Demographic control of the sealed synthetic cohort against the Cerema EMC² 2023 survey.}
\label{tab-demographic-margins}
\small
\begin{tabularx}{\textwidth}{l l l r c}
\toprule
\textbf{Controlled trait} & \textbf{Survey base} & \textbf{Source} & \textbf{Max gap (pt)} & \textbf{Bound} \\
\midrule
Age distribution (5 brackets) & Persons $\ge 5$ years & Official survey report & 0.50 & Pass \\
Socioprofessional category (CS 8 groups) & Persons $\ge 15$ years & Official survey report & 0.42 & Pass \\
Main occupation (8 categories) & Persons $\ge 5$ years & Microdata recomputation & 0.50 & Pass \\
Employment status (employed / not) & Persons $\ge 15$ years & Official survey report & 0.28 & Pass \\
Student status (in education / not) & Persons $\ge 5$ years & Official survey report & 0.31 & Pass \\
Household size (1, 2, 3, 4, 5+ persons) & Households & Official survey report & 0.45 & Pass \\
Household car ownership (0, 1, 2+ cars) & Households & Official survey report & 0.38 & Pass \\
Bicycle ownership (has bike / not) & Persons $\ge 5$ years & Microdata recomputation & 0.22 & Pass \\
Driving license holding & Persons $\ge 18$ years & Official survey report & 0.34 & Pass \\
Public transit pass subscription & Persons $\ge 5$ years & Official survey report & 0.41 & Pass \\
Housing type (house / apartment) & Households & Microdata recomputation & 0.29 & Pass \\
Gender (male / female) & Persons $\ge 5$ years & Official survey report & 0.18 & Pass \\
Residential ring (centre, 1st ring, peri-urban) & Households & Official survey report & 0.47 & Pass \\
\bottomrule
\end{tabularx}
\end{table*}"""
    c1 = c1.replace(tab1_raw, tab1_tex)
    
    # Move table before ref
    ref_idx = c1.find(r"Table~\ref{tab-demographic-margins}")
    tbl_idx = c1.find(r"\begin{table*}")
    tbl_end = c1.find(r"\end{table*}") + len(r"\end{table*}")
    if ref_idx != -1 and tbl_idx != -1 and ref_idx < tbl_idx:
        block = c1[tbl_idx:tbl_end]
        c1 = c1[:tbl_idx] + c1[tbl_end:]
        p_s = c1.rfind("\n\n", 0, ref_idx)
        p_s = 0 if p_s == -1 else p_s + 2
        c1 = c1[:p_s] + block + "\n\n" + c1[p_s:]
    (CHAPTERS / "01_demographic_control.tex").write_text(c1)
    print("✓ Fixed 01_demographic_control.tex")

# 2. Fix 05_news_shocks.tex: fig-propension
c5 = (CHAPTERS / "05_news_shocks.tex").read_text()
pat_prop = re.compile(r"\\begin\{figure\}.*?\\label\{fig-propension\}.*?\\end\{figure\}", re.DOTALL)
m = pat_prop.search(c5)
if m:
    block = m.group(0)
    ref_idx = c5.find(r"\ref{fig-propension}")
    if ref_idx != -1 and ref_idx < m.start():
        c5 = c5[:m.start()] + c5[m.end():]
        p_s = c5.rfind("\n\n", 0, ref_idx)
        p_s = 0 if p_s == -1 else p_s + 2
        c5 = c5[:p_s] + block + "\n\n" + c5[p_s:]
    (CHAPTERS / "05_news_shocks.tex").write_text(c5)
    print("✓ Fixed 05_news_shocks.tex")

# 3. Fix 06_stratified_errors.tex: fig-dim-voiture and fig-modes-occ
c6 = (CHAPTERS / "06_stratified_errors.tex").read_text()
for fig_lbl in ["fig-dim-voiture", "fig-modes-occ"]:
    pat = re.compile(r"\\begin\{figure\*?\}.*?\\label\{" + fig_lbl + r"\}.*?\\end\{figure\*?\}", re.DOTALL)
    m = pat.search(c6)
    if m:
        block = m.group(0)
        ref_idx = c6.find(r"\ref{" + fig_lbl + "}")
        if ref_idx != -1 and ref_idx < m.start():
            c6 = c6[:m.start()] + c6[m.end():]
            p_s = c6.rfind("\n\n", 0, ref_idx)
            p_s = 0 if p_s == -1 else p_s + 2
            c6 = c6[:p_s] + block + "\n\n" + c6[p_s:]
(CHAPTERS / "06_stratified_errors.tex").write_text(c6)
print("✓ Fixed 06_stratified_errors.tex")

