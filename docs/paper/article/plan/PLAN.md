# Plan de l'article — trame dérivée du texte

**Titre de travail :**
> *De la Décision Statistique au Comportement Adaptatif : Évaluation Empirique, Limites et Perspectives Hybrides des Agents LLM en Simulation de Mobilité Urbaine*
> *(EN : Generative Agents vs. Statistical Oracles in Urban Mobility Simulation: Empirical Limits, Unit-Level Evaluation, and Hybrid Perspectives)*

**Version du document :** `v1.8` (10 septembre 2026) — le résumé entre dans la trame comme section 0, le matériel de soumission AAMAS rejoint le dossier de l'article. `v1.7` du même jour : réalignée sur le plan annoncé en section 1.4 du chapitre 1 (`v0.16`), qui fait foi : l'état de l'art devient la section 2, les sections suivantes décalent d'un cran, la cascade hybride cesse d'être une section pour devenir les implications hybrides de la section 7, et les références quittent la numérotation. Écarts détaillés et datés dans [`README.md`](README.md). Version antérieure figée dans [`../../archive/PLAN_ARTICLE_2026_v1.6.md`](../../archive/PLAN_ARTICLE_2026_v1.6.md).
**Ce qui fait foi :** le texte de l'article, section 1.4 de [`../en/01_introduction.md`](../en/01_introduction.md). Ce fichier en est dérivé — voir [`README.md`](README.md).
**Fichiers associés :** [`../README.md`](../README.md) (état d'avancement par chapitre), [`../../methode/PROTOCOLE_SCIENTIFIQUE.md`](../../methode/PROTOCOLE_SCIENTIFIQUE.md), [`../../sources/BIBLIOGRAPHIE.md`](../../sources/BIBLIOGRAPHIE.md), [`../../sources/references.bib`](../../sources/references.bib)

---

## Structure de l'article

```
0. RÉSUMÉ                                          rédigé — article/{en,fr}/00_abstract.md
   240 mots, borne OpenReview de 100 à 300 ; emplacements chiffrés encore à remplir

1. INTRODUCTION                                    rédigée — article/{en,fr}/01_introduction.md
   1.1 Contexte : mobilité multimodale, transport centré sur l'usager, exigence de fidélité
   1.2 Le verrou : la plausibilité linguistique n'est pas la fidélité distributionnelle
       -> substitut statistique (jugé sur la fidélité) vs système adaptatif (jugé sur la robustesse)
   1.3 Contributions et hypothèses
       -> C1 contrat d'évaluation à parité informationnelle (3 règles)
       -> C2 ablation en quatre paliers + H0, plafond distributionnel
       -> C3 deux régimes qu'aucune enquête ne tabule
   1.4 Organisation de l'article                    <-- fait foi pour toute la numérotation

2. ÉTAT DE L'ART                                   rédigé — article/{en,fr}/02_related_work.md
   2.1 De l'utilité aléatoire à la rationalité limitée
   2.2 Agents génératifs en simulation de mobilité
   2.3 Alignement distributionnel des populations de LLM

3. MÉTRIQUES ET SOCLE D'ÉVALUATION                 brouillon — article/fr/03_metrics_and_substrate.md
   3.1 Métriques macro (parts modales, erreur L1) et micro (accuracy, rappel, LogLoss)
   3.2 Les trois règles du contrat : parité informationnelle, lectures comparables, renormalisation sur l'offre
   3.3 Contrôle démographique de la cohorte scellée (N = 1 000, marges de l'EMC² 2023)
   3.4 Dimensionnement de l'échantillon et effectif efficace  -> methode/JUSTIFICATION_TAILLE_ECHANTILLON.md
   3.5 Stabilité d'échelle (N = 1 000 -> 10 000)

4. LES LLM NUS ET LEUR VARIABILITÉ                 brouillon — article/fr/04_bare_llm.md
   4.1 Prompt neutre et offre d'itinéraires
   4.2 Comparaison entre modèles, tous à température 0
   4.3 Variabilité inter-graines et intervalles de confiance
   4.4 Taux de bascule individuelle et test de McNemar sur décisions appariées

5. ABLATION EN QUATRE PALIERS ET RÉFÉRENCES TABULAIRES   brouillon — article/fr/05_ablation.md
   5.1 Les quatre paliers : planchers -> LLM nu -> prompt calibré -> références tabulaires
   5.2 Test de H0 sur la cohorte scellée
   5.3 Audit unitaire à parité informationnelle, contrat de 21 variables
   5.4 Prévalence des temps terminaux physiques
   5.5 SHAP contre justifications en langue naturelle
   5.6 L'angle mort de l'oracle sur les modes minoritaires
   5.7 Enseignement transférable : bien classer l'enquête ne suffit pas à simuler la ville

6. RÉGIMES NON TABULÉS                             brouillon — article/fr/06_untabulated_regimes.md
   6.1 Hystérésis sur cinq jours après une panne de service, trois conditions dont un agent sans mémoire
   6.2 Cinq événements de presse locale datés, cinq conditions par événement
   6.3 Prédictions directionnelles préenregistrées et critères de réfutation

7. LIMITES ET IMPLICATIONS HYBRIDES                brouillon — article/fr/07_limits_and_hybrid.md
   7.1 Limites : indépendance des alternatives non pertinentes, asymétrie d'exposition, cohorte synthétique
   7.2 La cascade hybride en perspective (règles -> modèle tabulaire -> LLM)
   7.3 Cadre comparatif de performance
   7.4 Interactions intra-ménage et conservation des chaînes de véhicules

8. CONCLUSION                                      brouillon — article/fr/08_conclusion.md
   8.1 Ce que l'évaluation établit en régime nominal
   8.2 Le domaine de pertinence des agents génératifs
   8.3 Ce que l'hybridation résout, et ce qu'elle laisse ouvert
```

**Hors numérotation des sections :**

- Références bibliographiques : [`../../sources/BIBLIOGRAPHIE.md`](../../sources/BIBLIOGRAPHIE.md) et [`../../sources/references.bib`](../../sources/references.bib).
- Annexes techniques : [`../fr/99_annexes.md`](../fr/99_annexes.md), brouillon issu du manuscrit.
