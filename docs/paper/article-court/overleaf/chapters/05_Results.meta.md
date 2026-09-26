# Métadonnées et notes de rédaction — 05_Results.tex

## 1. En-tête et traçabilité

```text
chapters/05_Results.tex — LaTeX rendering of ../sections/05_results.en.md (2026-09-26 00:10:00)
Section 5 of the SHORT paper. \input from main.tex, after 04_Bench.tex.
Re-carried by hand on 26 September 2026 against the master of 2026-09-26 00:10:00.
This file DEFINES \label{sec:results}, referenced by the reading map of Section 1.4, and
  \label{sec:individual}, referenced from Section 7.1. It also defines sec:scale,
  sec:tuning and sec:deliberation (the last referenced from 5.4), and tab:scale, which
  04_Bench.tex references ("Table 1").
It references sec:quantities (Section 4.3, the cohort resolution) and sec:deliberation.
Figures: three, caption BELOW and a mandatory \Description{} (plain text, 2000 characters
  at most, not printed).
  fig:scale  (figure*, both columns) images/ch6_echelle.png     — ../PLAN.md § 9, figure 2, full width
  fig:distance (\columnwidth)        images/ch6_distance.png    — figure 3, one column
  fig:audit-modes (\columnwidth)     images/ch6_audit_modes.png — figure 4, one column
  REGENERATION PENDING on ch6_echelle.png: it must gain the inter-seed range column
  (../PLAN.md § 9). The PNG shipped here already carries the fifteen rows.
  ch6_audit_modes.png is set across both columns in the long paper. The plan puts it in one
  column here; two panels of grouped bars at 240 pt may not hold. If the compiled PDF is
  unreadable, promote it to figure* — it costs no page, the paper being float-bound.
Tables: three, caption ABOVE, booktabs.
  tab:scale (table*, both columns) — Table 1, moved from 4.4 to 5.1 on 25 September 2026
    by the master (editorial review, author's agreement). Rows grouped, then sorted by
    composite, with a Group column. Fifteen rows and five columns do not fit \columnwidth.
    04_Bench.tex, re-carried the same day, no longer carries the table: this file is the
    only one to define the label.
  tab:gains (table*, both columns) — ../PLAN.md § 9, Table 2 is full width; the confidence
    intervals in the cells do not fit \columnwidth.
  tab:unit (\columnwidth, tabularx with the L column of main.tex) — Table 3, one column,
    seven rows since the all-car row was added. Column heads are abbreviated over two
    lines, as in the long paper: the Markdown heads ("Cross-entropy", "Bike recall")
    overrun 240 pt.
PLACEHOLDERS, DELIBERATE, waiting on ticket 103: five "[pending]" cells in the last column
  of Table 1, plain bracketed text, NOT \todo. The one the master sets in bold (minimal
  prompt, gemini-3.5) is in \textbf{} here. Section 5.3 no longer carries any "[c2, ...]"
  item: the master now gives the measured second-cohort scores.
Appendix F is named in plain text: it lives in the supplementary material.
Claims pass of 2026-09-25 (evening), in the .tex at the author's request, master not yet
  realigned: the cohort resolution stays a scale (the figure prints it) but no longer
  serves as an equivalence test; 5.3 no longer concludes on the causal role of the text;
  the all-car baseline is named by its rule.
No citation in this section.
Derived file: regenerate after every validated pass of ../sections/05_results.en.md.
```

## 2. Notes éditoriales et décisions de rédaction (corps)

### 📌 **Note** — `Flottant \begin{table*}` (L134-L135)

```text
Écart au tableau 1 vérifié le 2026-09-25 : composite 2,27 / 3,37 / 7,25 contre 2,16 / 3,40 /
  7,12 par soustraction ; L1 10,2 / 8,6 / 18,0 identiques. Effet de l'appariement.
```

### ⚠️ **À TRANCHER** — `A classifier that writes no text reaches the reference range (sec:deliberation)` (L178-L181)

```text
A TRANCHER : statut de la seconde cohorte. Le ticket 103 la dit hors échantillon pour tous
  les prompts ; la décision du 2026-09-24 en fait la cohorte de calibration. Tant que
  prompt_expert_32 n'est pas re-réglé sur c2, c'est le score c1 (3,65) qui est en
  échantillon et le score c2 (4,64) qui est hors échantillon. Le dire ici en une phrase.
```

### 📊 **Source / Données** — `A classifier that writes no text reaches the reference range (sec:deliberation)` (L189-L191)

```text
source : experiments_results.md, ticket 103 phase 4 (jev x prompt_expert_05, c1, graine 42 :
  4,1399 ; gemini-3.5 : 4,8571) et phases 1-2 sur c2 (jev x prompt_expert_32 : 4,6394 ;
  gemini-3.5 x prompt_expert_05 : 4,7627). Relecture de l'auteur du 2026-09-25.
```

### ⚠️ **À TRANCHER** — `A classifier that writes no text reaches the reference range (sec:deliberation)` (L195-L196)

```text
A TRANCHER (relecture externe) : dire d'où viennent les 23 026 décisions (graines ?
  cohortes ?), la date du tarif et ce que couvre la facturation (cache, jetons).
```

