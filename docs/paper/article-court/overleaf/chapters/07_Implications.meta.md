# Métadonnées et notes de rédaction — 07_Implications.tex

## 1. En-tête et traçabilité

```text
chapters/07_Implications.tex — LaTeX rendering of ../sections/07_implications.en.md (2026-09-26 00:10:00)
Section 7 of the SHORT paper, the last one. \input from main.tex, after 06_Non_tabulated.tex.
This file DEFINES \label{sec:implications}, \label{sec:cost-of-deciding} (7.1),
  \label{sec:limitations} (7.2) and \label{sec:conclusion} (7.3); no other chapter
  references them.
It REFERENCES sec:mechanism (Section 6.2, from 7.1) and sec:nontabulated (Section 6, from
  7.2). sec:individual (Section 5.4) is no longer referenced from here.
Figures: none, and none is wanted. ../PLAN.md § 7.1 forbids a cascade figure with empty
  flow shares, and forbids \todo.
Tables: none.
Citation: chopra2024limits (AAMAS 2025), the one published answer to the inference cost. It
  resolves in sample.bib.
Section 7.2 carries five run-in limitations whose titles are bold in the master; they are
  set with \textbf{} at the head of each paragraph.
CUT CANDIDATE, from the master's comments, if the page budget requires it: the last sentence
  of the cost paragraph of 7.3, "Billions of tokens per simulated day cannot be justified
  just to reproduce what the survey already tabulates."
ONE STATEMENT DEPENDS ON TICKET 103 although no placeholder is written here: the sentence
  of the conclusion on the typed classifier reaching the same range (written under scenario
  1; it leaves the conclusion under scenario 3).
Re-carried by hand on 26 September 2026 against the master of 2026-09-26 00:10:00: 7.1
  retitled ("What it costs to let generative agents decide", label renamed from
  sec:architecture-implication, which nothing referenced); the three-stage division of
  labour and the nominal-stage paragraph are withdrawn, replaced by two paragraphs (calling
  generative agents only when an event occurs; which parts of the memory need a language
  model, moved from 6.2); 7.2 rewritten as five titled limitations; 7.3 rewritten in five
  paragraphs. Earlier states of this chapter live in git history.
Maintained by hand (no generator since 2026-09-23): carry every validated pass of
  ../sections/07_implications.en.md and set the date of line 2 to its marker.
Claims pass of 2026-09-25 (evening): master Markdown realigned. Open questions left as
  "A TRANCHER" comments in the body.
```

## 2. Notes éditoriales et décisions de rédaction (corps)

_Aucune note éditoriale ou commentaire interne dans le corps de ce chapitre._
