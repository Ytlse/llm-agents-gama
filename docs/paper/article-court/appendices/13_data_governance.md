# 13. Research Data Governance, Legal Embargo, and Third-Party Replication Protocol

This chapter defines data governance constraints and replication protocols. We detail the legal requirements governing the Cerema EMC² 2023 survey and provide independent replication instructions.

## 13.1 Legal Framework and Agreement `lil-1750`

The research uses microdata from the certified Cerema Household Travel Survey (EMC² 2023, Greater Toulouse). We obtained these data through the French national Quetelet-ProGEDO diffusion portal under research agreement `lil-1750`.

French statistical confidentiality regulations strictly forbid transferring raw microdata to third parties. Consequently, the public replication archive cannot distribute the raw survey files.

## 13.2 Open Replication Package Boundary

The open replication repository contains all artifacts permissible under law.

**Software and code.** Complete simulation and inference Python source code.

**Configurations.** Random seeds and experimental configuration manifests.

**Synthetic cohort.** The sealed synthetic cohort of 1,000 personas and validation scripts.

**Spatial layers.** Multimodal routing graphs and OpenTripPlanner configurations.

## 13.3 Third-Party Microdata Access Protocol

Independent researchers can replicate our exact baseline fits through five sequential steps.

1. Register an academic research account on the national ADISP portal (`progedo-adisp.fr`).
2. Request the certified microdata for the Greater Toulouse 2023 mobility survey.
3. Place received microdata files into repository directory `data/PROGEDO 2023/`.
4. Execute `build_mode_choice_dataset.py` with seed 0 to regenerate the exact train/test split.
5. Execute `fit_mode_choice_*.py` to reproduce the tabular benchmark metrics.

Furthermore, evaluating tabular references on drawn modes rather than continuous probability masses introduces sampling noise. Table 13.1 quantifies this noise across the four baseline models.

*Table 13.1. Tabular references evaluated on drawn modes against continuous mass.*

| Reference method | Composite EMD–JSD (drawn modes) | Gap with probability mass |
|---|---:|---:|
| Gradient boosting (LightGBM) | 3.88 | $+0.28$ pt |
| Multinomial logit | 4.54 | $+0.52$ pt |
| Kernel logistic regression | 3.52 | $-0.08$ pt |
| Random forest | 4.40 | $+0.31$ pt |
