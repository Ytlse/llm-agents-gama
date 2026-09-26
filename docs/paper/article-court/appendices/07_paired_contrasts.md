# 7. Paired Resampling Hypothesis Tests across Twenty Contrast Pairs

This chapter establishes the statistical significance of performance contrasts between decision-makers. We present cluster bootstrap hypothesis tests across twenty distinct model pairs.

## 7.1 Individual-Level Cluster Bootstrap Protocol

We compute confidence intervals using cluster bootstrap resampling at the individual persona level. We execute $B = 2{,}000$ bootstrap replicates with a fixed random seed (2026), resampling across the 868 common mobile individuals.

This clustering scheme accounts for intra-individual trip correlation. Evaluating paired differences across identical bootstrap samples cancels common variance components.

## 7.2 The Twenty Paired Contrasts

Table 7.1 reports the paired differences across three evaluation metrics: the composite score, the non-single choice score, and the global $L_1$ modal share error.

*Table 7.1. Paired bootstrap differences (95% CI) across twenty model contrasts. Bold denotes intervals excluding zero.*

| Contrast pair | Composite difference | Non-single choice | Global $L_1$ error |
|---|---|---|---|
| `gemini-3.5` (expert $-$ minimal) | **$-2.27$** [$-3.22; -1.40$] | **$-3.59$** [$-4.83; -2.45$] | **$-10.2$** [$-12.5; -8.0$] |
| `gemini-3.1` (expert $-$ minimal) | **$-3.37$** [$-4.25; -2.45$] | **$-4.15$** [$-5.22; -3.09$] | **$-8.6$** [$-10.6; -6.8$] |
| `mistral-large` (expert $-$ minimal) | **$-7.25$** [$-8.67; -5.90$] | **$-8.63$** [$-10.28; -7.15$] | **$-18.0$** [$-22.4; -13.5$] |
| `gemini-3.5` expert $-$ Gradient boosting | **$+1.35$** [$+0.28; +2.47$] | $+1.09$ [$-0.27; +2.45$] | $+4.3$ [$-1.2; +9.7$] |
| `gemini-3.5` expert $-$ Kernel regression | **$+1.38$** [$+0.32; +2.45$] | **$+1.35$** [$+0.10; +2.69$] | **$+7.1$** [$+1.8; +12.1$] |
| `gemini-3.5` expert $-$ Random forest | $+0.94$ [$-0.06; +1.98$] | $+1.17$ [$-0.02; +2.39$] | **$+7.7$** [$+3.3; +11.7$] |
| `gemini-3.5` expert $-$ Multinomial logit | $+0.96$ [$-0.18; +2.17$] | $+0.39$ [$-1.10; +1.80$] | $+4.4$ [$-0.4; +8.5$] |
| `gemini-3.1` expert $-$ Gradient boosting | **$+5.50$** [$+4.19; +6.93$] | **$+6.65$** [$+5.21; +8.29$] | **$+21.7$** [$+16.6; +27.0$] |
| `mistral-large` expert $-$ Gradient boosting | **$+4.07$** [$+2.47; +5.75$] | **$+6.33$** [$+4.54; +8.09$] | **$+17.2$** [$+12.7; +21.6$] |
| `gemini-3.1` $-$ `gemini-3.5` (expert) | **$+4.15$** [$+2.99; +5.43$] | **$+5.56$** [$+4.12; +7.02$] | **$+17.4$** [$+14.6; +20.3$] |
| `gemini-3.1` $-$ `gemini-3.5` (minimal) | **$+5.25$** [$+4.11; +6.40$] | **$+6.13$** [$+4.75; +7.53$] | **$+15.8$** [$+13.2; +18.3$] |
| `mistral-large` $-$ `gemini-3.5` (expert) | **$+2.71$** [$+1.17; +4.25$] | **$+5.24$** [$+3.76; +6.66$] | **$+12.8$** [$+8.3; +17.4$] |
| `gemini-3.1` $-$ `mistral-large` (expert) | $+1.44$ [$-0.10; +2.98$] | $+0.32$ [$-1.14; +1.82$] | $+4.6$ [$-0.1; +9.0$] |
| `gemini-3.1` $-$ `mistral-large` (minimal) | **$-2.45$** [$-4.08; -0.85$] | **$-4.16$** [$-5.89; -2.45$] | **$-4.8$** [$-7.4; -2.2$] |
| Jev under `gemini-3.5` prompt $-$ minimal | **$-9.71$** [$-11.66; -7.80$] | **$-12.78$** [$-14.86; -10.68$] | **$-30.2$** [$-36.0; -24.6$] |
| Jev under `gemini-3.5` prompt $-$ Gradient boosting | $+0.66$ [$-0.63; +2.07$] | $+1.32$ [$-0.19; +2.86$] | $+3.1$ [$-1.4; +7.3$] |
| Jev under `gemini-3.5` prompt $-$ Kernel regression | $+0.69$ [$-0.57; +2.06$] | **$+1.58$** [$+0.22; +3.00$] | **$+5.9$** [$+1.6; +9.8$] |
| Jev under `gemini-3.5` prompt $-$ Random forest | $+0.25$ [$-1.03; +1.61$] | **$+1.40$** [$+0.08; +2.80$] | **$+6.5$** [$+1.8; +10.6$] |
| Jev under `gemini-3.5` prompt $-$ Multinomial logit | $+0.27$ [$-1.11; +1.70$] | $+0.62$ [$-0.97; +2.24$] | $+3.1$ [$-1.7; +7.8$] |
| Jev under `gemini-3.5` prompt $-$ `gemini-3.5` expert | $-0.69$ [$-2.04; +0.65$] | $+0.23$ [$-1.14; +1.56$] | $-1.2$ [$-7.0; +4.3$] |

## 7.3 Instruction-Dependent Ranking Reversals

The empirical ranking of models depends heavily on prompt instructions. Under the minimal prompt, `gemini-3.1` outperforms `mistral-large` by 2.45 points, an interval strictly excluding zero. In contrast, under the expert prompt, `mistral-large` surpasses `gemini-3.1` by 1.44 points.

Consequently, evaluating language models under a single prompt measures the model-prompt pair rather than the intrinsic capability of the architecture. Furthermore, the ablation of the justification clause improves the composite score by $+0.17$ [$-0.45; +0.79$] point.
