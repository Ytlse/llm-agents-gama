# Plan de l'article — trame dérivée du texte

**Titre de travail :**
> *De la Décision Statistique au Comportement Adaptatif : Évaluation Empirique, Limites et Perspectives Hybrides des Agents LLM en Simulation de Mobilité Urbaine*
> *(EN : Generative Agents vs. Statistical Oracles in Urban Mobility Simulation: Empirical Limits, Unit-Level Evaluation, and Hybrid Perspectives)*

**Version du document :** `v1.11` (11 septembre 2026) — le chapitre 4 perd sa section de dimensionnement (contrainte de pages : il en reste une phrase en 4.5) et resserre son périmètre de mesure ; il couvre désormais exactement ce que la section 1.4 lui annonce. `v1.10` (même jour) — le chapitre 4 est rédigé, et sa trame interne change : une sous-section neuve sur le périmètre de mesure (ce qui n'entre pas au score), les références tabulaires deviennent une **famille en cours de caractérisation** plutôt qu'un oracle désigné, et la cohorte scellée retenue est la **v5**. Numérotation des sections inchangée. `v1.9` (même jour) — l'article gagne une section système : le dispositif évalué est décrit en section 3, les sections 3 à 8 antérieures décalent d'un cran jusqu'à la section 9. Le trou était réel — ni `article/`, ni le manuscrit figé `v1.6` ne décrivaient l'objet évalué, là où tout article comparable du corpus porte une section méthode ou système. `v1.8` (10 septembre 2026) — le résumé entre dans la trame comme section 0, le matériel de soumission AAMAS rejoint le dossier de l'article. `v1.7` du même jour : réalignée sur le plan annoncé en section 1.4 du chapitre 1 (`v0.16`), qui fait foi : l'état de l'art devient la section 2, les sections suivantes décalent d'un cran, la cascade hybride cesse d'être une section pour devenir les implications hybrides de la section 7, et les références quittent la numérotation. Écarts détaillés et datés dans [`README.md`](README.md). Version antérieure figée dans [`../../archive/PLAN_ARTICLE_2026_v1.6.md`](../../archive/PLAN_ARTICLE_2026_v1.6.md).
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

3. LE DISPOSITIF : DÉCIDER DANS UNE VILLE CONTRAINTE   brouillon — article/fr/03_architecture.md
   3.1 Vue d'ensemble : GAMA porte le monde, le contrôleur le cycle de vie, le module LLM le choix
   3.2 Le terrain : deux moteurs d'itinéraires, l'horloge du réseau, le périmètre, les modes ouverts
   3.3 Le point de décision : ce que l'agent voit, ce qu'il rend (un indice, pas un trajet)
   3.4 Mémoire courte et longue : ce qui fait qu'un jour ressemble au précédent
   3.5 La journée est une chaîne : les trois règles des véhicules personnels

4. MÉTRIQUES ET SOCLE D'ÉVALUATION                 brouillon v0.8 — article/fr/04_metrics_and_substrate.md
   4.1 Deux échelles, et la lecture qui décide de tout (masse de probabilité vs mode le plus probable)
   4.2 Les trois règles du contrat : parité informationnelle, lectures homogènes, renormalisation sur l'offre
   4.3 Le périmètre de mesure (trois phrases : ce qui porte une décision modale)
   4.4 Le socle de référence : une cohorte en service, quatre familles tabulaires
   4.5 La cohorte scellée et son contrôle démographique (13 marges, TOST ± 1 pt)
   -- le dimensionnement de l'échantillon quitte le chapitre (place), il en reste une phrase en 4.5
      -> methode/JUSTIFICATION_TAILLE_ECHANTILLON.md

4.5 CALIBRATION DU PROMPT (OPTIMISATION RÉFLÉCHIE) brouillon v0.1 — article/fr/04.5_prompt_calibration.md
    4.5.1 La vulnérabilité du prompt « calibré » et l'impératif de réfutabilité
    4.5.2 Le goulet computationnel : échec d'échelle du génétique en MAS (O(G·P·N) tokens)
    4.5.3 Le paradigme retenu : optimisation réfléchie (LLM-as-Optimizer / gradient textuel)
    4.5.4 Les quatre garde-fous structurels anti-surapprentissage (Zéro seuil, populations cloisonnées, comptages pondérés, compaction)
    4.5.5 Statut du Palier 2 dans l'architecture de la preuve (plafond Tier 3 de SILICA)

5. ÉVALUATION SOUS PROMPT FACTUEL NEUTRE ET CIRCONSTANCIÉ ET VARIABILITÉ  brouillon — article/fr/05_factual_neutral_prompt.md
   5.1 Définition du prompt factuel neutre et circonstancié
   5.2 Benchmark multi-modèles et diversité des voies d'inférence (Pilotage)
   5.3 Protocole de variabilité et dispersion inter-runs à température 0

6. ABLATION EN QUATRE PALIERS ET RÉFÉRENCES TABULAIRES   brouillon — article/fr/06_ablation.md
   6.1 Les quatre paliers : planchers -> prompt factuel neutre et circonstancié -> prompt calibré -> références tabulaires
   6.2 Test de H0 sur la cohorte scellée
   6.3 Audit unitaire à parité informationnelle, contrat de 21 variables
   6.4 Prévalence des temps terminaux physiques
   6.5 SHAP contre justifications en langue naturelle
   6.6 L'angle mort de l'oracle sur les modes minoritaires
   6.7 Enseignement transférable : bien classer l'enquête ne suffit pas à simuler la ville

7. RÉGIMES NON TABULÉS                             brouillon — article/fr/07_untabulated_regimes.md
   7.1 Hystérésis sur cinq jours après une panne de service, trois conditions dont un agent sans mémoire
   7.2 Cinq événements de presse locale datés, cinq conditions par événement
   7.3 Prédictions directionnelles préenregistrées et critères de réfutation

8. LIMITES ET IMPLICATIONS HYBRIDES                brouillon — article/fr/08_limits_and_hybrid.md
   8.1 Limites : indépendance des alternatives non pertinentes, asymétrie d'exposition, cohorte synthétique
   8.2 La cascade hybride en perspective (règles -> modèle tabulaire -> LLM)
   8.3 Cadre comparatif de performance
   8.4 Interactions intra-ménage et conservation des chaînes de véhicules

9. CONCLUSION                                      brouillon — article/fr/09_conclusion.md
   9.1 Ce que l'évaluation établit en régime nominal
   9.2 Le domaine de pertinence des agents génératifs
   9.3 Ce que l'hybridation résout, et ce qu'elle laisse ouvert
```

**Hors numérotation des sections :**

- Références bibliographiques : [`../../sources/BIBLIOGRAPHIE.md`](../../sources/BIBLIOGRAPHIE.md) et [`../../sources/references.bib`](../../sources/references.bib).
- Annexes techniques : [`../fr/99_annexes.md`](../fr/99_annexes.md), brouillon issu du manuscrit.
