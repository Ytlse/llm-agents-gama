# Contrôle de population — `toulouse_population_1000_AAMAS.json`

- **Effectif** : 1000 personas — sha256 `9f05c655c3ad2cf4d8c71cc3c34238417718cec742b42ef94a21eb33f694639f`
- **Date** : 2026-09-03T16:16:44+00:00
- **Borne TOST** : ± 1.0 pt · n_min 30 · n_min cellule 50
- **Verdicts** : conforme 12 · à publier 1 · à corriger 0 · non mesurable 0
- **Ménages** : 513 ; complets (taille déclarée) 469 (91.4 %) ; membres présents / déclarés 1000/1052 (95.1 %)
- **Mobilité** : 2.44 déplacements par persona (enquête 3.53) ; immobiles 10.6 % (enquête 10.6 %)
- **Scolaires (6-17 ans) avec activité d'études** : 131/148 mobiles = 88.5 % (enquête 90 à 95 %, seuil 88 %) · scolaires 151

## Marges

### `classe_age` — **conforme**

Base personne, ordinale, n = 1000. Cible : AUAT/CEREMA, Rapport final EMC² 2023 — bassin de vie toulousain (68 p., mai 2024) p. 11, via population_emc2_2023.yaml.
χ² = 0.1 (ddl 5, p = 1), V de Cramér 0.005, EMD (unités de classe) = 0.012, écart max 0.30 pt.

| Modalité | n | Observé | IC95 | Cible | Écart | TOST | Verdict |
|---|---:|---:|---|---:|---:|---|---|
| 5-17 ans | 163 | 16.3 % | [14.1, 18.7] | 16.0 % | 0.3 | non concluant | conforme |
| 18-24 ans | 130 | 13.0 % | [11.0, 15.2] | 13.0 % | 0.0 | non concluant | conforme |
| 25-34 ans | 140 | 14.0 % | [11.9, 16.3] | 14.0 % | 0.0 | non concluant | conforme |
| 35-49 ans | 220 | 22.0 % | [19.5, 24.7] | 22.0 % | 0.0 | non concluant | conforme |
| 50-64 ans | 187 | 18.7 % | [16.3, 21.3] | 19.0 % | -0.3 | non concluant | conforme |
| 65 ans et + | 160 | 16.0 % | [13.8, 18.4] | 16.0 % | 0.0 | non concluant | conforme |

### `occupation` — **conforme**

Base personne, nominale, n = 1000. Cible : AUAT/CEREMA, Rapport final EMC² 2023 — bassin de vie toulousain (68 p., mai 2024) p. 11, via population_emc2_2023.yaml.
χ² = 1.0 (ddl 6, p = 0.985), V de Cramér 0.013, JSD (base 2, [0, 1]) = 0.000, écart max 0.70 pt.

| Modalité | n | Observé | IC95 | Cible | Écart | TOST | Verdict |
|---|---:|---:|---|---:|---:|---|---|
| Scolaires | 163 | 16.3 % | [14.1, 18.7] | 17.0 % | -0.7 | non concluant | conforme |
| Étudiants | 90 | 9.0 % | [7.3, 10.9] | 9.0 % | 0.0 | non concluant | conforme |
| Actifs temps plein | 390 | 39.0 % | [36.0, 42.1] | 39.0 % | 0.0 | non concluant | conforme |
| Actifs temps partiel | 56 | 5.6 % | [4.3, 7.2] | 5.0 % | 0.6 | non concluant | conforme |
| En recherche d'emploi | 71 | 7.1 % | [5.6, 8.9] | 7.0 % | 0.1 | non concluant | conforme |
| Retraités | 180 | 18.0 % | [15.7, 20.5] | 18.0 % | 0.0 | non concluant | conforme |
| Autres | 50 | 5.0 % | [3.7, 6.5] | 5.0 % | 0.0 | non concluant | conforme |

### `motorisation_personne` — **conforme**

Base personne, ordinale, n = 1000. Cible : recalcul microdonnées EMC² 2023 (ProGEDO lil-1750), fichiers personnes × ménages, poids COEP, couronne par secteur de tirage (DTIR NOM_D2).
χ² = 0.0 (ddl 2, p = 0.998), V de Cramér 0.001, EMD (unités de classe) = 0.001, écart max 0.09 pt.

| Modalité | n | Observé | IC95 | Cible | Écart | TOST | Verdict |
|---|---:|---:|---|---:|---:|---|---|
| sans voiture | 136 | 13.6 % | [11.5, 15.9] | 13.6 % | 0.0 | non concluant | conforme |
| une voiture | 377 | 37.7 % | [34.7, 40.8] | 37.8 % | -0.1 | non concluant | conforme |
| deux voitures et + | 487 | 48.7 % | [45.6, 51.8] | 48.6 % | 0.1 | non concluant | conforme |

### `motorisation_menage` — **à publier**

Base menage, ordinale, n = 1000. Cible : AUAT/CEREMA, Rapport final EMC² 2023 — bassin de vie toulousain (68 p., mai 2024) p. 21, via population_emc2_2023.yaml.
χ² = 6.2 (ddl 2, p = 0.0454), V de Cramér 0.056, EMD (unités de classe) = 0.049, écart max 3.57 pt.

> sans voiture : 22.8 % contre 19.2 % (+3.6 pt)

| Modalité | n | Observé | IC95 | Cible | Écart | TOST | Verdict |
|---|---:|---:|---|---:|---:|---|---|
| sans voiture | 136 | 22.8 % | [19.8, 25.9] | 19.2 % | 3.6 | écart | à publier |
| une voiture | 377 | 43.2 % | [39.7, 46.9] | 45.5 % | -2.2 | non concluant | conforme |
| deux voitures et + | 487 | 34.0 % | [30.6, 37.5] | 35.4 % | -1.4 | non concluant | conforme |

### `couronne` — **conforme**

Base personne, nominale, n = 1000. Cible : AUAT/CEREMA, Rapport final EMC² 2023 — bassin de vie toulousain (68 p., mai 2024) p. 10 (habitants de 5 ans et +), via population_emc2_2023.yaml.
χ² = 0.0 (ddl 3, p = 1), V de Cramér 0.001, JSD (base 2, [0, 1]) = 0.000, écart max 0.06 pt.

| Modalité | n | Observé | IC95 | Cible | Écart | TOST | Verdict |
|---|---:|---:|---|---:|---:|---|---|
| Toulouse | 363 | 36.3 % | [33.3, 39.4] | 36.4 % | -0.1 | non concluant | conforme |
| 1ere couronne | 341 | 34.1 % | [31.2, 37.1] | 34.1 % | 0.0 | non concluant | conforme |
| 2eme couronne | 142 | 14.2 % | [12.1, 16.5] | 14.2 % | 0.0 | non concluant | conforme |
| 3eme couronne | 154 | 15.4 % | [13.2, 17.8] | 15.4 % | 0.0 | non concluant | conforme |

### `couronne_x_motorisation` — **conforme**

Base personne, nominale, n = 1000. Cible : recalcul microdonnées EMC² 2023 (ProGEDO lil-1750), fichiers personnes × ménages, poids COEP, couronne par secteur de tirage (DTIR NOM_D2).
χ² = 0.0 (ddl 11, p = 1), V de Cramér 0.002, JSD (base 2, [0, 1]) = 0.000, écart max 0.05 pt.

| Modalité | n | Observé | IC95 | Cible | Écart | TOST | Verdict |
|---|---:|---:|---|---:|---:|---|---|
| Toulouse × sans voiture | 107 | 10.7 % | [8.9, 12.8] | 10.7 % | 0.0 | non concluant | conforme |
| Toulouse × une voiture | 172 | 17.2 % | [14.9, 19.7] | 17.3 % | -0.1 | non concluant | conforme |
| Toulouse × deux voitures et + | 84 | 8.4 % | [6.8, 10.3] | 8.4 % | -0.0 | non concluant | conforme |
| 1ere couronne × sans voiture | 19 | 1.9 % | — | 1.9 % | -0.0 | — | non mesurable (effectif 19 < 30 : pas d'IC exploitable) |
| 1ere couronne × une voiture | 122 | 12.2 % | [10.2, 14.4] | 12.2 % | -0.0 | non concluant | conforme |
| 1ere couronne × deux voitures et + | 200 | 20.0 % | [17.6, 22.6] | 20.0 % | 0.0 | non concluant | conforme |
| 2eme couronne × sans voiture | 4 | 0.4 % | — | 0.4 % | 0.0 | — | non mesurable (effectif 4 < 30 : pas d'IC exploitable) |
| 2eme couronne × une voiture | 39 | 3.9 % | [2.8, 5.3] | 3.9 % | -0.0 | non concluant | conforme |
| 2eme couronne × deux voitures et + | 99 | 9.9 % | [8.1, 11.9] | 9.9 % | 0.0 | non concluant | conforme |
| 3eme couronne × sans voiture | 6 | 0.6 % | — | 0.6 % | -0.0 | — | non mesurable (effectif 6 < 30 : pas d'IC exploitable) |
| 3eme couronne × une voiture | 44 | 4.4 % | [3.2, 5.9] | 4.4 % | 0.0 | non concluant | conforme |
| 3eme couronne × deux voitures et + | 104 | 10.4 % | [8.6, 12.5] | 10.4 % | 0.0 | non concluant | conforme |

### `age_quinquennal` — **conforme**

Base personne, ordinale, n = 1000. Cible : recalcul microdonnées EMC² 2023 (ProGEDO lil-1750), personnes interrogées (PENQ = 1) × ménages × déplacements, poids COEP — gelé cm1, non publié à ce pas.
χ² = 0.2 (ddl 14, p = 1), V de Cramér 0.004, EMD (unités de classe) = 0.018, écart max 0.30 pt.

| Modalité | n | Observé | IC95 | Cible | Écart | TOST | Verdict |
|---|---:|---:|---|---:|---:|---|---|
| 5-9 | 63 | 6.3 % | [4.9, 8.0] | 6.3 % | 0.0 | non concluant | conforme |
| 10-14 | 69 | 6.9 % | [5.4, 8.7] | 6.8 % | 0.1 | non concluant | conforme |
| 15-19 | 73 | 7.3 % | [5.8, 9.1] | 7.3 % | 0.0 | non concluant | conforme |
| 20-24 | 88 | 8.8 % | [7.1, 10.7] | 8.8 % | -0.0 | non concluant | conforme |
| 25-29 | 68 | 6.8 % | [5.3, 8.5] | 6.9 % | -0.1 | non concluant | conforme |
| 30-34 | 72 | 7.2 % | [5.7, 9.0] | 7.5 % | -0.3 | non concluant | conforme |
| 35-39 | 79 | 7.9 % | [6.3, 9.7] | 7.9 % | -0.0 | non concluant | conforme |
| 40-44 | 71 | 7.1 % | [5.6, 8.9] | 7.0 % | 0.1 | non concluant | conforme |
| 45-49 | 70 | 7.0 % | [5.5, 8.8] | 7.0 % | 0.0 | non concluant | conforme |
| 50-54 | 71 | 7.1 % | [5.6, 8.9] | 7.0 % | 0.1 | non concluant | conforme |
| 55-59 | 59 | 5.9 % | [4.5, 7.5] | 5.8 % | 0.1 | non concluant | conforme |
| 60-64 | 57 | 5.7 % | [4.3, 7.3] | 5.7 % | 0.0 | non concluant | conforme |
| 65-69 | 45 | 4.5 % | [3.3, 6.0] | 4.5 % | 0.0 | non concluant | conforme |
| 70-74 | 43 | 4.3 % | [3.1, 5.7] | 4.3 % | 0.0 | non concluant | conforme |
| 75 et + | 72 | 7.2 % | [5.7, 9.0] | 7.1 % | 0.1 | non concluant | conforme |

### `genre` — **conforme**

Base personne, nominale, n = 1000. Cible : recalcul microdonnées EMC² 2023 (ProGEDO lil-1750), personnes interrogées (PENQ = 1) × ménages × déplacements, poids COEP — gelé cm1, non publié à ce pas.
χ² = 0.0 (ddl 1, p = 0.99), V de Cramér 0.000, JSD (base 2, [0, 1]) = 0.000, écart max 0.02 pt.

| Modalité | n | Observé | IC95 | Cible | Écart | TOST | Verdict |
|---|---:|---:|---|---:|---:|---|---|
| Femmes | 513 | 51.3 % | [48.2, 54.4] | 51.3 % | 0.0 | non concluant | conforme |
| Hommes | 487 | 48.7 % | [45.6, 51.8] | 48.7 % | -0.0 | non concluant | conforme |

### `taille_menage_personne` — **conforme**

Base personne, ordinale, n = 1000. Cible : recalcul microdonnées EMC² 2023 (ProGEDO lil-1750), personnes interrogées (PENQ = 1) × ménages × déplacements, poids COEP — gelé cm1, non publié à ce pas.
χ² = 0.7 (ddl 4, p = 0.945), V de Cramér 0.014, EMD (unités de classe) = 0.031, écart max 0.81 pt.

| Modalité | n | Observé | IC95 | Cible | Écart | TOST | Verdict |
|---|---:|---:|---|---:|---:|---|---|
| 1 | 220 | 22.0 % | [19.5, 24.7] | 21.2 % | 0.8 | non concluant | conforme |
| 2 | 295 | 29.5 % | [26.7, 32.4] | 29.5 % | 0.0 | non concluant | conforme |
| 3 | 191 | 19.1 % | [16.7, 21.7] | 19.1 % | -0.0 | non concluant | conforme |
| 4 | 200 | 20.0 % | [17.6, 22.6] | 20.2 % | -0.2 | non concluant | conforme |
| 5 et + | 94 | 9.4 % | [7.7, 11.4] | 10.1 % | -0.7 | non concluant | conforme |

### `permis_adultes` — **conforme**

Base personne, nominale, n = 837. Cible : recalcul microdonnées EMC² 2023 (ProGEDO lil-1750), personnes interrogées (PENQ = 1) × ménages × déplacements, poids COEP — gelé cm1, non publié à ce pas.
χ² = 0.0 (ddl 1, p = 0.973), V de Cramér 0.001, JSD (base 2, [0, 1]) = 0.000, écart max 0.04 pt.

| Modalité | n | Observé | IC95 | Cible | Écart | TOST | Verdict |
|---|---:|---:|---|---:|---:|---|---|
| Oui | 719 | 85.9 % | [83.4, 88.2] | 85.9 % | 0.0 | non concluant | conforme |
| Non | 118 | 14.1 % | [11.8, 16.6] | 14.1 % | -0.0 | non concluant | conforme |

### `abonnement_tc` — **conforme**

Base personne, nominale, n = 1000. Cible : recalcul microdonnées EMC² 2023 (ProGEDO lil-1750), personnes interrogées (PENQ = 1) × ménages × déplacements, poids COEP — gelé cm1, non publié à ce pas.
χ² = 0.0 (ddl 1, p = 0.972), V de Cramér 0.001, JSD (base 2, [0, 1]) = 0.000, écart max 0.05 pt.

| Modalité | n | Observé | IC95 | Cible | Écart | TOST | Verdict |
|---|---:|---:|---|---:|---:|---|---|
| Oui | 258 | 25.8 % | [23.1, 28.6] | 25.8 % | -0.0 | non concluant | conforme |
| Non | 742 | 74.2 % | [71.4, 76.9] | 74.2 % | 0.0 | non concluant | conforme |

### `logement` — **conforme**

Base personne, nominale, n = 1000. Cible : recalcul microdonnées EMC² 2023 (ProGEDO lil-1750), personnes interrogées (PENQ = 1) × ménages × déplacements, poids COEP — gelé cm1, non publié à ce pas.
χ² = 0.0 (ddl 4, p = 1), V de Cramér 0.003, JSD (base 2, [0, 1]) = 0.000, écart max 0.04 pt.

| Modalité | n | Observé | IC95 | Cible | Écart | TOST | Verdict |
|---|---:|---:|---|---:|---:|---|---|
| Individuel isolé | 417 | 41.7 % | [38.6, 44.8] | 41.7 % | -0.0 | non concluant | conforme |
| Individuel accolé | 146 | 14.6 % | [12.5, 16.9] | 14.6 % | 0.0 | non concluant | conforme |
| Petit habitat collectif | 239 | 23.9 % | [21.3, 26.7] | 23.9 % | -0.0 | non concluant | conforme |
| Grand habitat collectif | 194 | 19.4 % | [17.0, 22.0] | 19.4 % | -0.0 | non concluant | conforme |
| Autres | 4 | 0.4 % | — | 0.4 % | 0.0 | — | non mesurable (effectif 4 < 30 : pas d'IC exploitable) |

### `immobile` — **conforme**

Base personne, nominale, n = 1000. Cible : recalcul microdonnées EMC² 2023 (ProGEDO lil-1750), personnes interrogées (PENQ = 1) × ménages × déplacements, poids COEP — gelé cm1, non publié à ce pas.
χ² = 0.0 (ddl 1, p = 0.963), V de Cramér 0.001, JSD (base 2, [0, 1]) = 0.000, écart max 0.05 pt.

| Modalité | n | Observé | IC95 | Cible | Écart | TOST | Verdict |
|---|---:|---:|---|---:|---:|---|---|
| Oui | 106 | 10.6 % | [8.8, 12.7] | 10.6 % | -0.0 | non concluant | conforme |
| Non | 894 | 89.4 % | [87.3, 91.2] | 89.4 % | 0.0 | non concluant | conforme |

## Journal de recoupement (protocole §2.1)

| Ligne | Publié | Référence | Écart | Statut | Source |
|---|---:|---:|---:|---|---|
| Genre — Femmes | 51.8 % | 51.3 % | -0.5 | concordant | recalcul microdonnées (P2, COEP) — non publié |
| Genre — Hommes | 48.2 % | 48.7 % | 0.5 | concordant | recalcul microdonnées (P2, COEP) — non publié |
| Âge — Moins de 18 ans | 19.4 % | 16.0 % | -3.4 | ÉCART — à consigner (Annexe F) | rapport p. 11 (6 classes agrégées) — population de 5 ans et + |
| Âge — 18-64 ans | 62.1 % | 68.0 % | 5.9 | ÉCART — à consigner (Annexe F) | rapport p. 11 (6 classes agrégées) — population de 5 ans et + |
| Âge — 65 ans et plus | 18.5 % | 16.0 % | -2.5 | ÉCART — à consigner (Annexe F) | rapport p. 11 (6 classes agrégées) — population de 5 ans et + |
| Ménages sans voiture | 22.3 % | 19.0 % | -3.3 | ÉCART — à consigner (Annexe F) | rapport p. 21 (base ménage) |
| Ménages avec 1 voiture | 46.1 % | 45.0 % | -1.1 | ÉCART — à consigner (Annexe F) | rapport p. 21 (base ménage) |
| Ménages avec 2+ voitures | 31.6 % | 35.0 % | 3.4 | ÉCART — à consigner (Annexe F) | rapport p. 21 (base ménage) |
| Détention du permis (adultes) | 84.2 % | 85.9 % | 1.7 | ÉCART — à consigner (Annexe F) | recalcul microdonnées (P7 = 1, 18 ans et +, COEP) — non publié |

## Synthèse des écarts

| Écart | Amplitude | Nature | Verdict | Refermable au scellement |
|---|---|---|---|---|
| mobilité quotidienne | 2.44 déplacements par persona contre 3.53 dans l'enquête ; 10.6 % d'immobiles contre 10.6 % | chaînes d'activités (ENTD 2008 appariée par eqasim) | à publier | non — enquête d'appariement (levier eqasim) |
| motorisation_menage | sans voiture : 22.8 % contre 19.2 % (+3.6 pt) | base ménage (pondération 1/taille) | à publier | non — à déclarer |
