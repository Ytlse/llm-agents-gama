# Contrôle de population — `population.json`

- **Effectif** : 1000 personas — sha256 `8d8bfa3645fa77fb0bcb8aaac8d02bff57395ae06475701f523ef3c772fbb704`
- **Date** : 2026-09-03T16:58:42+00:00
- **Borne TOST** : ± 1.0 pt · n_min 30 · n_min cellule 50
- **Verdicts** : conforme 13 · à corriger 0 · à publier 0 · non mesurable 0
- **Ménages** : 514 ; complets (taille déclarée) 485 (94.4 %) ; membres présents / déclarés 1000/1034 (96.7 %)
- **Mobilité** : 3.47 déplacements par persona (enquête 3.53) ; immobiles 10.6 % (enquête 10.6 %)
- **Scolaires (6-17 ans) avec activité d'études** : 75/139 mobiles = 54.0 % (enquête 90 à 95 %, seuil 88 %) · scolaires 158

## Marges

### `classe_age` — **conforme**

Base personne, ordinale, n = 1000. Cible : AUAT/CEREMA, Rapport final EMC² 2023 — bassin de vie toulousain (68 p., mai 2024) p. 11, via population_emc2_2023.yaml.
χ² = 2.1 (ddl 5, p = 0.837), V de Cramér 0.020, EMD (unités de classe) = 0.023, écart max 1.20 pt.

| Modalité | n | Observé | IC95 | Cible | Écart | TOST | Verdict |
|---|---:|---:|---|---:|---:|---|---|
| 5-17 ans | 172 | 17.2 % | [14.9, 19.7] | 16.0 % | 1.2 | non concluant | conforme |
| 18-24 ans | 119 | 11.9 % | [10.0, 14.1] | 13.0 % | -1.1 | non concluant | conforme |
| 25-34 ans | 144 | 14.4 % | [12.3, 16.7] | 14.0 % | 0.4 | non concluant | conforme |
| 35-49 ans | 219 | 21.9 % | [19.4, 24.6] | 22.0 % | -0.1 | non concluant | conforme |
| 50-64 ans | 185 | 18.5 % | [16.1, 21.0] | 19.0 % | -0.5 | non concluant | conforme |
| 65 ans et + | 161 | 16.1 % | [13.9, 18.5] | 16.0 % | 0.1 | non concluant | conforme |

### `occupation` — **conforme**

Base personne, nominale, n = 1000. Cible : AUAT/CEREMA, Rapport final EMC² 2023 — bassin de vie toulousain (68 p., mai 2024) p. 11, via population_emc2_2023.yaml.
χ² = 0.2 (ddl 6, p = 1), V de Cramér 0.006, JSD (base 2, [0, 1]) = 0.000, écart max 0.30 pt.

| Modalité | n | Observé | IC95 | Cible | Écart | TOST | Verdict |
|---|---:|---:|---|---:|---:|---|---|
| Scolaires | 170 | 17.0 % | [14.7, 19.5] | 17.0 % | 0.0 | non concluant | conforme |
| Étudiants | 90 | 9.0 % | [7.3, 10.9] | 9.0 % | 0.0 | non concluant | conforme |
| Actifs temps plein | 390 | 39.0 % | [36.0, 42.1] | 39.0 % | 0.0 | non concluant | conforme |
| Actifs temps partiel | 53 | 5.3 % | [4.0, 6.9] | 5.0 % | 0.3 | non concluant | conforme |
| En recherche d'emploi | 70 | 7.0 % | [5.5, 8.8] | 7.0 % | 0.0 | non concluant | conforme |
| Retraités | 177 | 17.7 % | [15.4, 20.2] | 18.0 % | -0.3 | non concluant | conforme |
| Autres | 50 | 5.0 % | [3.7, 6.5] | 5.0 % | 0.0 | non concluant | conforme |

### `motorisation_personne` — **conforme**

Base personne, ordinale, n = 1000. Cible : recalcul microdonnées EMC² 2023 (ProGEDO lil-1750), fichiers personnes × ménages, poids COEP, couronne par secteur de tirage (DTIR NOM_D2).
χ² = 0.0 (ddl 2, p = 0.998), V de Cramér 0.001, EMD (unités de classe) = 0.001, écart max 0.09 pt.

| Modalité | n | Observé | IC95 | Cible | Écart | TOST | Verdict |
|---|---:|---:|---|---:|---:|---|---|
| sans voiture | 136 | 13.6 % | [11.5, 15.9] | 13.6 % | 0.0 | non concluant | conforme |
| une voiture | 377 | 37.7 % | [34.7, 40.8] | 37.8 % | -0.1 | non concluant | conforme |
| deux voitures et + | 487 | 48.7 % | [45.6, 51.8] | 48.6 % | 0.1 | non concluant | conforme |

### `motorisation_menage` — **conforme**

Base menage, ordinale, n = 1000. Cible : AUAT/CEREMA, Rapport final EMC² 2023 — bassin de vie toulousain (68 p., mai 2024) p. 21, via population_emc2_2023.yaml.
χ² = 2.4 (ddl 2, p = 0.306), V de Cramér 0.034, EMD (unités de classe) = 0.032, écart max 2.21 pt.

| Modalité | n | Observé | IC95 | Cible | Écart | TOST | Verdict |
|---|---:|---:|---|---:|---:|---|---|
| sans voiture | 136 | 21.4 % | [18.5, 24.5] | 19.2 % | 2.2 | non concluant | conforme |
| une voiture | 377 | 44.2 % | [40.6, 47.8] | 45.5 % | -1.2 | non concluant | conforme |
| deux voitures et + | 487 | 34.4 % | [31.0, 37.9] | 35.4 % | -1.0 | non concluant | conforme |

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
χ² = 0.0 (ddl 14, p = 1), V de Cramér 0.002, EMD (unités de classe) = 0.016, écart max 0.10 pt.

| Modalité | n | Observé | IC95 | Cible | Écart | TOST | Verdict |
|---|---:|---:|---|---:|---:|---|---|
| 5-9 | 63 | 6.3 % | [4.9, 8.0] | 6.3 % | 0.0 | non concluant | conforme |
| 10-14 | 68 | 6.8 % | [5.3, 8.5] | 6.8 % | -0.0 | non concluant | conforme |
| 15-19 | 72 | 7.2 % | [5.7, 9.0] | 7.3 % | -0.1 | non concluant | conforme |
| 20-24 | 88 | 8.8 % | [7.1, 10.7] | 8.8 % | -0.0 | non concluant | conforme |
| 25-29 | 69 | 6.9 % | [5.4, 8.7] | 6.9 % | 0.0 | non concluant | conforme |
| 30-34 | 75 | 7.5 % | [5.9, 9.3] | 7.5 % | -0.0 | non concluant | conforme |
| 35-39 | 79 | 7.9 % | [6.3, 9.7] | 7.9 % | -0.0 | non concluant | conforme |
| 40-44 | 70 | 7.0 % | [5.5, 8.8] | 7.0 % | -0.0 | non concluant | conforme |
| 45-49 | 70 | 7.0 % | [5.5, 8.8] | 7.0 % | 0.0 | non concluant | conforme |
| 50-54 | 70 | 7.0 % | [5.5, 8.8] | 7.0 % | -0.0 | non concluant | conforme |
| 55-59 | 58 | 5.8 % | [4.4, 7.4] | 5.8 % | -0.0 | non concluant | conforme |
| 60-64 | 57 | 5.7 % | [4.3, 7.3] | 5.7 % | 0.0 | non concluant | conforme |
| 65-69 | 45 | 4.5 % | [3.3, 6.0] | 4.5 % | 0.0 | non concluant | conforme |
| 70-74 | 44 | 4.4 % | [3.2, 5.9] | 4.3 % | 0.1 | non concluant | conforme |
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
χ² = 4.1 (ddl 4, p = 0.395), V de Cramér 0.032, EMD (unités de classe) = 0.052, écart max 2.16 pt.

| Modalité | n | Observé | IC95 | Cible | Écart | TOST | Verdict |
|---|---:|---:|---|---:|---:|---|---|
| 1 | 228 | 22.8 % | [20.2, 25.5] | 21.2 % | 1.6 | non concluant | conforme |
| 2 | 293 | 29.3 % | [26.5, 32.2] | 29.5 % | -0.2 | non concluant | conforme |
| 3 | 191 | 19.1 % | [16.7, 21.7] | 19.1 % | -0.0 | non concluant | conforme |
| 4 | 180 | 18.0 % | [15.7, 20.5] | 20.2 % | -2.2 | non concluant | conforme |
| 5 et + | 108 | 10.8 % | [8.9, 12.9] | 10.1 % | 0.7 | non concluant | conforme |

### `permis_adultes` — **conforme**

Base personne, nominale, n = 828. Cible : recalcul microdonnées EMC² 2023 (ProGEDO lil-1750), personnes interrogées (PENQ = 1) × ménages × déplacements, poids COEP — gelé cm1, non publié à ce pas.
χ² = 0.0 (ddl 1, p = 0.995), V de Cramér 0.000, JSD (base 2, [0, 1]) = 0.000, écart max 0.01 pt.

| Modalité | n | Observé | IC95 | Cible | Écart | TOST | Verdict |
|---|---:|---:|---|---:|---:|---|---|
| Oui | 711 | 85.9 % | [83.3, 88.2] | 85.9 % | 0.0 | non concluant | conforme |
| Non | 117 | 14.1 % | [11.8, 16.7] | 14.1 % | -0.0 | non concluant | conforme |

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
| Genre — Femmes | 51.3 % | 51.3 % | -0.0 | concordant | recalcul microdonnées (P2, COEP) — non publié (cm1) |
| Genre — Hommes | 48.7 % | 48.7 % | 0.0 | concordant | recalcul microdonnées (P2, COEP) — non publié (cm1) |
| Âge — 5-17 ans | 16.0 % | 16.0 % | 0.0 | concordant | rapport p. 11 (6 classes publiées) — population de 5 ans et + |
| Âge — 18-24 ans | 13.0 % | 13.0 % | 0.0 | concordant | rapport p. 11 (6 classes publiées) — population de 5 ans et + |
| Âge — 25-34 ans | 14.0 % | 14.0 % | 0.0 | concordant | rapport p. 11 (6 classes publiées) — population de 5 ans et + |
| Âge — 35-49 ans | 22.0 % | 22.0 % | 0.0 | concordant | rapport p. 11 (6 classes publiées) — population de 5 ans et + |
| Âge — 50-64 ans | 19.0 % | 19.0 % | 0.0 | concordant | rapport p. 11 (6 classes publiées) — population de 5 ans et + |
| Âge — 65 ans et plus | 16.0 % | 16.0 % | 0.0 | concordant | rapport p. 11 (6 classes publiées) — population de 5 ans et + |
| Ménages sans voiture | 19.0 % | 19.0 % | 0.0 | concordant | rapport p. 21 (base ménage) |
| Ménages avec 1 voiture | 45.0 % | 45.0 % | 0.0 | concordant | rapport p. 21 (base ménage) |
| Ménages avec 2 voitures et + | 35.0 % | 35.0 % | 0.0 | concordant | rapport p. 21 (base ménage) |
| Détention du permis (18 ans et +) | 85.9 % | 85.9 % | -0.0 | concordant | recalcul microdonnées (P7 = 1, 18 ans et +, COEP) — non publié (cm1) |
| Personnes sans déplacement la veille | 10.6 % | 10.6 % | 0.0 | concordant | recalcul microdonnées (aucun déplacement la veille, COEP) — non publié (cm1) |

## Synthèse des écarts

| Écart | Amplitude | Nature | Verdict | Refermable au scellement |
|---|---|---|---|---|
| scolaires sans activité d'études | 75/139 scolaires (6-17 ans) mobiles avec une activité d'études = 54.0 % contre 90 à 95 % dans l'enquête (seuil 88 %) | journées donneuses ENTD 2008 et appariement eqasim (jours de classe, ticket 031 § 1.2) | à publier | non — appariement HTS (levier eqasim) |
