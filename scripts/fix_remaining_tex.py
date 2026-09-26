from pathlib import Path
import re

CHAPTERS = Path("docs/paper/article-court/appendices/chapters")

# 1. Fix 04_prompts_and_traces.tex
c4 = (CHAPTERS / "04_prompts_and_traces.tex").read_text()
# Replace table 4.1
old_tab41 = """| Element | Repository file path |
|---|---|
| The three prompts | \\texttt{packages/mobility_llm/src/mobility_llm/prompts/prompts.yaml} |
| The user message template | \\texttt{packages/mobility_llm/src/mobility_llm/categories/itinary_multi_agent/template.md.j2} |
| The JSON output schema | \\texttt{packages/mobility_llm/src/mobility_llm/categories/itinary_multi_agent/output_schema.json} |
| The classifier input wrapper | \\texttt{services/llm-agents/experiences/decideur_typesafe.py} |"""

new_tab41 = r"""\begin{table}[h]
\centering
\caption{Storage locations of prompt and schema files.}
\label{tab-prompts-files}
\small
\begin{tabularx}{\columnwidth}{lX}
\toprule
\textbf{Element} & \textbf{Repository file path} \\
\midrule
The three prompts & \texttt{packages/mobility_llm/.../prompts.yaml} \\
User message template & \texttt{packages/mobility_llm/.../template.md.j2} \\
JSON output schema & \texttt{packages/mobility_llm/.../output_schema.json} \\
Classifier wrapper & \texttt{services/llm-agents/.../decideur_typesafe.py} \\
\bottomrule
\end{tabularx}
\end{table}"""

c4 = c4.replace(old_tab41, new_tab41).replace(r"\emph{Table 4.1. Storage locations of prompt and schema files.}", "")

# Replace table 4.2
old_tab42 = """| Option | Minimal prompt (\\texttt{gemini-3.5}) | Expert prompt (\\texttt{gemini-3.5}) | Typed classifier (\\texttt{prompt_expert_32}) |
|---|---:|---:|---:|
| [0] foot, 16 min | 30 | 45 | 52 |
| [1] foot, 17 min | 10 | 45 | 20 |
| [2] car, 4 min | 50 | 10 | 27 |
| [3] foot, bus, foot, 43 min | 0 | 0 | 0 |
| [4] foot, bus, foot, 34 min | 5 | 0 | 1 |
| [5] foot, bus, foot, 35 min | 5 | 0 | 0 |
| \\textbf{Drawn mode} | \\textbf{car} | \\textbf{foot} | \\textbf{car} |"""

new_tab42 = r"""\begin{table}[h]
\centering
\caption{Probability distributions assigned to Raymond's options (in percent).}
\label{tab-raymond-options}
\small
\begin{tabular}{lrrr}
\toprule
\textbf{Option} & \textbf{Minimal} & \textbf{Expert} & \textbf{Typed} \\
\midrule
[0] foot, 16 min & 30 & 45 & 52 \\
[1] foot, 17 min & 10 & 45 & 20 \\
[2] car, 4 min & 50 & 10 & 27 \\
[3] foot, bus, foot, 43 min & 0 & 0 & 0 \\
[4] foot, bus, foot, 34 min & 5 & 0 & 1 \\
[5] foot, bus, foot, 35 min & 5 & 0 & 0 \\
\midrule
\textbf{Drawn mode} & \textbf{car} & \textbf{foot} & \textbf{car} \\
\bottomrule
\end{tabular}
\end{table}"""

c4 = c4.replace(old_tab42, new_tab42).replace(r"\emph{Table 4.2. Probability distributions assigned to Raymond's options (in percent).}", "")
c4 = c4.replace("Table 4.1", r"Table~\ref{tab-prompts-files}")
c4 = c4.replace("Table 4.2", r"Table~\ref{tab-raymond-options}")

# Reorder so tables precede refs
# Table 4.1 before line "Table~\ref{tab-prompts-files} lists the repository files storing these components."
p1 = "The typed classifier receives the identical prompt, truncated before the output instructions. Its structured input schema takes their place. Every model runs at temperature $\\tau = 0.0$ and top-p 1.0.\n\n"
c4 = c4.replace(p1 + new_tab41 + "\n\n" + r"Table~\ref{tab-prompts-files} lists the repository files storing these components.",
                p1 + new_tab41 + "\n\n" + r"Table~\ref{tab-prompts-files} lists the repository files storing these components.")

# If table is after the sentence, move it before:
c4 = re.sub(r"(Table~\\ref\{tab-prompts-files\} lists the repository files storing these components\.\n\n)(" + re.escape(new_tab41) + ")", r"\2\n\n\1", c4)
c4 = re.sub(r"(Table~\\ref\{tab-raymond-options\} presents the resulting probability vectors and drawn modes across the three architectures\.\n\n)(" + re.escape(new_tab42) + ")", r"\2\n\n\1", c4)

(CHAPTERS / "04_prompts_and_traces.tex").write_text(c4)
print("✓ Fixed 04_prompts_and_traces.tex")
