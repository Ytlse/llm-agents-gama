# Inventaire des données personnelles et identifiants dans le dépôt

Ce document recense l'intégralité des occurrences de données personnelles, nom d'auteur, adresse email, nom d'utilisateur système et identifiants de plateformes présents dans les fichiers du dépôt.

---

## 1. Adresse email (`yves.bru@gmail.com`)

| Fichier | Ligne | Contexte |
| :--- | :---: | :--- |
| [`docs/paper/article-court/main.tex`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/article-court/main.tex#L112) | 112 | `\email{yves.bru@gmail.com}` (En-tête auteur de l'article court) |
| [`docs/paper/article-court/appendices/main.tex`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/article-court/appendices/main.tex#L53) | 53 | `\email{yves.bru@gmail.com}` (En-tête auteur des annexes) |
| [`docs/paper/article-court/overleaf/supplementary.tex`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/article-court/overleaf/supplementary.tex#L52) | 52 | `\email{yves.bru@gmail.com}` (En-tête auteur matériel supplémentaire) |
| [`docs/paper/article_old_do_not_maintain/overleaf/main.tex`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/article_old_do_not_maintain/overleaf/main.tex#L111) | 111 | `\email{yves.bru@gmail.com}` (Template historique) |
| [`docs/tickets/ticket_009_calibration_genetique.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/tickets/ticket_009_calibration_genetique.md#L32) | 32 | `Auteur : Yves Bru <yves.bru@gmail.com>` |

> [!NOTE]
> Pour une soumission d'article scientifique en **double-aveugle (double-blind review)**, les lignes `\email{...}` et `\author{...}` dans les fichiers `.tex` doivent être masquées ou remplacées par `\author{Anonymous Author(s)}`.

---

## 2. Nom d'auteur (`Yves Bru`)

| Fichier | Ligne | Contexte |
| :--- | :---: | :--- |
| [`docs/paper/article-court/main.tex`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/article-court/main.tex#L109) | 109 | `\author{Yves Bru}` |
| [`docs/paper/article-court/appendices/main.tex`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/article-court/appendices/main.tex#L50) | 50 | `\author{Yves Bru}` |
| [`docs/paper/article-court/overleaf/supplementary.tex`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/article-court/overleaf/supplementary.tex#L49) | 49 | `\author{Yves Bru}` |
| [`docs/paper/article_old_do_not_maintain/overleaf/main.tex`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/article_old_do_not_maintain/overleaf/main.tex#L108) | 108 | `\author{Yves Bru}` |

---

## 3. Nom d'utilisateur Mac & Chemins locaux (`yvesb` / `/Users/yvesb`)

Ces occurrences proviennent principalement de chemins de build absolus consignés dans les métadonnées de reproductibilité de la population scellée et dans les notebooks Jupyter :

### A. Métadonnées de population scellée & Sceaux
* [`data/population/population_1000_AAMAS_v6/MANIFEST.yaml`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/data/population/population_1000_AAMAS_v6/MANIFEST.yaml) (Lignes 58, 126, 130) : Chemins absolus des fichiers sources de marges lors du scellement.
* [`data/population/population_1000_AAMAS_v6/report.json`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/data/population/population_1000_AAMAS_v6/report.json) (Lignes 14, 19)
* [`data/population/population_1000_AAMAS_v6/selection.json`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/data/population/population_1000_AAMAS_v6/selection.json) (Lignes 34, 39, 67, 107)

### B. Documentation et suivi de publication
* [`docs/paper/suivi_actions_publication.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/suivi_actions_publication.md) (41 occurrences de liens vers des artefacts locaux)
* [`docs/paper/README.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/README.md) (21 occurrences de liens locaux)
* [`docs/paper/methode/quotas_summary.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/methode/quotas_summary.md)
* [`docs/paper/archive/MANUSCRIT_DETAILLE_2026_v1.1.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/archive/MANUSCRIT_DETAILLE_2026_v1.1.md)
* [`docs/paper/archive/PLAN_ARTICLE_2026_v1.1.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/archive/PLAN_ARTICLE_2026_v1.1.md)
* [`docs/changelog.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/changelog.md)
* [`docs/tickets/ticket_008_run_24h_mesures_synthese.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/tickets/ticket_008_run_24h_mesures_synthese.md)
* [`docs/tickets/ticket_057_audit_et_reflexion_double_lecture_tabulaire.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/tickets/ticket_057_audit_et_reflexion_double_lecture_tabulaire.md)
* [`.claude/skills/prompt_calib_context/SKILL.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/.claude/skills/prompt_calib_context/SKILL.md)

### C. Scripts et Notebooks Jupyter (cellules contenant des chemins locaux)
* [`generate_fig8_exact.py`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/generate_fig8_exact.py)
* [`scripts/analysis/architecture_bande_en.py`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/scripts/analysis/architecture_bande_en.py)
* [`scripts/analysis/build_illustrations_html.py`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/scripts/analysis/build_illustrations_html.py)
* `scripts/analysis/delays.ipynb`
* `scripts/analysis/llm_traffic_analyse.ipynb`
* `scripts/analysis/pipeline.ipynb`
* `scripts/analysis/selected_mode_stats.ipynb`
* `scripts/data/population/generate_population.ipynb`
* `scripts/infra/direct_trip.ipynb`
* `scripts/infra/otp_shape.ipynb`
* `scripts/infra/test_boucle_comp.ipynb`
* `scripts/models_influence/prompt_calibration.ipynb`
* `scripts/progedo_logit/explore_mode_choice_dataset.ipynb`
* `scripts/progedo_logit/explore_progedo_bike_shapley.ipynb`
* `scripts/progedo_logit/explore_progedo_walk_shapley.ipynb`
* `scripts/progedo_logit/prepare_progedo_logit.ipynb`

---

## 4. Identifiant de compte GitHub / DagsHub (`Ytlse`)

Présent dans les URLs de dépôts distants et sous-modules :

* [`.dvc/config`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/.dvc/config) (`url = https://dagshub.com/Ytlse/llm-urban-mode-choice.dvc`)
* [`.gitmodules`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/.gitmodules) (`url = https://github.com/Ytlse/prompt_calibration.git`)
* [`README.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/README.md)
* [`docs/arch/prompt_calibration.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/arch/prompt_calibration.md)
* [`docs/setup/population.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/setup/population.md)
* [`docs/changelog.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/changelog.md)
* [`docs/paper/gama_days/GAMA_DAYS_ABSTRACT_EN_TEX.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/gama_days/GAMA_DAYS_ABSTRACT_EN_TEX.md)
* [`.claude/skills/prompt_calib_context/SKILL.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/.claude/skills/prompt_calib_context/SKILL.md)
* [`packages/llm_gateway/NOTICE`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/packages/llm_gateway/NOTICE)
* [`packages/mobility_core/NOTICE`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/packages/mobility_core/NOTICE)
* [`packages/mobility_llm/NOTICE`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/packages/mobility_llm/NOTICE)
