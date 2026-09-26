# 1. Demographic Control and Territorial Representativeness

This chapter evaluates the demographic and spatial fidelity of the synthetic population. We compare the 1,000-persona cohort against the certified Cerema household travel survey across thirteen controlled margins.

## 1.1 Controlled Margins Against the Cerema EMC² 2023 Survey

The simulation framework relies on a synthetic population of 1,000 personas grouped into 499 intact households. We generate this cohort using the `eqasim` spatial synthesis pipeline for the greater Toulouse metropolitan area. The personas perform 3,299 daily trips organized into closed cyclic activity chains.

We control this synthetic cohort against the thirteen sociodemographic and territorial margins of the certified Cerema EMC² 2023 survey. Table 1.1 reports the thirteen margins, the sample counts, the survey baselines, and the observed percentage gaps.

*Table 1.1. Demographic control of the sealed synthetic cohort against the Cerema EMC² 2023 survey.*

| Controlled trait | Survey base | Source | Max gap (pt) | Within $\pm 1.0$ pt bound |
|---|---|---|---:|:---:|
| Age class (6 classes) | Persons $\ge 5$ years | Official survey report | 0.50 | Pass |
| Occupation (8 modalities) | Persons $\ge 5$ years | Official survey report | 0.50 | Pass |
| Five-year age (15 classes) | Persons $\ge 5$ years | Survey microdata (recomputed) | 0.29 | Pass |
| Car ownership (individual) | Persons $\ge 18$ years | Survey microdata (recomputed) | 0.09 | Pass |
| Car ownership (household) | Households | Official survey report | 0.06 | Pass |
| Residential ring (3 rings) | Persons $\ge 5$ years | Official survey report | 0.06 | Pass |
| Ring $\times$ car ownership | Persons $\ge 5$ years | Survey microdata (recomputed) | 0.05 | Pass |
| Household size (1 to 5+ persons) | Households | Survey microdata (recomputed) | 0.06 | Pass |
| Driving licence (18 and over) | Persons $\ge 18$ years | Survey microdata (recomputed) | 0.01 | Pass |
| Public transit pass subscription | Persons $\ge 5$ years | Survey microdata (recomputed) | 0.05 | Pass |
| Dwelling type (house / apartment) | Households | Survey microdata (recomputed) | 0.04 | Pass |
| Gender (female / male) | Persons $\ge 5$ years | Survey microdata (recomputed) | 0.02 | Pass |
| People with no trip on previous day | Persons $\ge 5$ years | Survey microdata (recomputed) | 0.05 | Pass |

## 1.2 Unweighted Sampling and Microdata Reconstruction

Each synthetic persona carries an unweighted unit sampling mass of exactly one. We apply no post-stratification weights, which prevents artificial variance deflation during subsequent behavioural evaluations.

Several traits required custom recomputations directly from the certified survey microdata under research agreement `lil-1750`. Specifically, the official published Cerema report aggregates bicycle ownership and housing categories with peripheral variables. Therefore, we computed frozen baseline margins directly from the microdata files to maintain uncompromised comparison standards.

## 1.3 Statistical Equivalence Testing

We evaluate margin conformity using Two One-Sided Tests (TOST) under a pre-registered equivalence bound of $\pm 1.0$ percentage point. This statistical procedure tests the null hypothesis of non-equivalence against the alternative of equivalence within the defined bound.

All thirteen controlled margins successfully pass the TOST procedure at the $\alpha = 0.05$ significance level. Furthermore, the largest single divergence across all categories is strictly bounded at 0.50 percentage point, observed in the age and occupation distributions.
