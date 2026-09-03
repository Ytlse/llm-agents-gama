# Contrôle de population — `toulouse_population_1000_AAMAS.json`

- **Effectif** : 1000 personas — sha256 `f67b07772f3dced9d1058cbf1c29f5779425386cc52ced0f778d1a2c233b0a84`
- **Date** : 2026-09-02T20:39:51+00:00
- **Borne TOST** : ± 1.0 pt · n_min 30 · n_min cellule 50
- **Verdicts** : conforme 6 · non mesurable 2 · à corriger 0 · à publier 0

## Marges

### `classe_age` — **conforme**

Base personne, ordinale, n = 1000. Cible : AUAT/CEREMA, Rapport final EMC² 2023 — bassin de vie toulousain (68 p., mai 2024) p. 11, via population_emc2_2023.yaml.
χ² = 4.9 (ddl 5, p = 0.426), V de Cramér 0.031, EMD (unités de classe) = 0.038, écart max 1.40 pt.

| Modalité | n | Observé | IC95 | Cible | Écart | TOST | Verdict |
|---|---:|---:|---|---:|---:|---|---|
| 5-17 ans | 171 | 17.1 % | [14.8, 19.6] | 16.0 % | 1.1 | non concluant | conforme |
| 18-24 ans | 119 | 11.9 % | [10.0, 14.1] | 13.0 % | -1.1 | non concluant | conforme |
| 25-34 ans | 153 | 15.3 % | [13.1, 17.7] | 14.0 % | 1.3 | non concluant | conforme |
| 35-49 ans | 211 | 21.1 % | [18.6, 23.8] | 22.0 % | -0.9 | non concluant | conforme |
| 50-64 ans | 176 | 17.6 % | [15.3, 20.1] | 19.0 % | -1.4 | non concluant | conforme |
| 65 ans et + | 170 | 17.0 % | [14.7, 19.5] | 16.0 % | 1.0 | non concluant | conforme |

### `occupation` — **conforme**

Base personne, nominale, n = 1000. Cible : AUAT/CEREMA, Rapport final EMC² 2023 — bassin de vie toulousain (68 p., mai 2024) p. 11, via population_emc2_2023.yaml.
χ² = 0.0 (ddl 6, p = 1), V de Cramér 0.000, JSD (base 2, [0, 1]) = 0.000, écart max 0.00 pt.

| Modalité | n | Observé | IC95 | Cible | Écart | TOST | Verdict |
|---|---:|---:|---|---:|---:|---|---|
| Scolaires | 170 | 17.0 % | [14.7, 19.5] | 17.0 % | 0.0 | non concluant | conforme |
| Étudiants | 90 | 9.0 % | [7.3, 10.9] | 9.0 % | 0.0 | non concluant | conforme |
| Actifs temps plein | 390 | 39.0 % | [36.0, 42.1] | 39.0 % | 0.0 | non concluant | conforme |
| Actifs temps partiel | 50 | 5.0 % | [3.7, 6.5] | 5.0 % | 0.0 | non concluant | conforme |
| En recherche d'emploi | 70 | 7.0 % | [5.5, 8.8] | 7.0 % | 0.0 | non concluant | conforme |
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

### `motorisation_menage` — **conforme**

Base menage, ordinale, n = 1000. Cible : AUAT/CEREMA, Rapport final EMC² 2023 — bassin de vie toulousain (68 p., mai 2024) p. 21, via population_emc2_2023.yaml.
χ² = 2.5 (ddl 2, p = 0.286), V de Cramér 0.035, EMD (unités de classe) = 0.023, écart max 2.32 pt.

| Modalité | n | Observé | IC95 | Cible | Écart | TOST | Verdict |
|---|---:|---:|---|---:|---:|---|---|
| sans voiture | 136 | 21.2 % | [18.3, 24.3] | 19.2 % | 2.0 | non concluant | conforme |
| une voiture | 377 | 43.1 % | [39.6, 46.8] | 45.5 % | -2.3 | non concluant | conforme |
| deux voitures et + | 487 | 35.6 % | [32.2, 39.2] | 35.4 % | 0.3 | non concluant | conforme |

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

### `genre` — **non mesurable**

Base personne, nominale, n = 1000. Cible : aucune — le rapport EMC² 2023 ne publie pas la répartition par sexe.

> aucune cible publiée — candidat recalculé (P2, COEP) : Femmes 51.3 %, Hommes 48.7 %

| Modalité | n | Observé | IC95 | Cible | Écart | TOST | Verdict |
|---|---:|---:|---|---:|---:|---|---|
| Femmes | 507 | 50.7 % | — | — | — | — | non mesurable (aucune cible publiée) |
| Hommes | 493 | 49.3 % | — | — | — | — | non mesurable (aucune cible publiée) |

### `permis_adultes` — **non mesurable**

Base personne, nominale, n = 829. Cible : aucune — le mot « permis » n'apparaît qu'une fois dans le rapport, p. 4, dans la liste des questions posées.

> aucune cible publiée — candidat recalculé (P7 = 1, 18 ans et +, COEP) : Oui 85.9 %, Non 12.8 %, Conduite accompagnée 1.4 %

| Modalité | n | Observé | IC95 | Cible | Écart | TOST | Verdict |
|---|---:|---:|---|---:|---:|---|---|
| Oui | 691 | 83.4 % | — | — | — | — | non mesurable (aucune cible publiée) |
| Non | 138 | 16.6 % | — | — | — | — | non mesurable (aucune cible publiée) |

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
| genre | — | référence (aucune cible publiée) | non mesurable | non — cible absente du rapport |
| permis_adultes | — | référence (aucune cible publiée) | non mesurable | non — cible absente du rapport |
