# Plan de l'article — trame dérivée du texte

**Titre de travail :**
> *De la Décision Statistique au Comportement Adaptatif : Évaluation Empirique, Limites et Perspectives Hybrides des Agents LLM en Simulation de Mobilité Urbaine*
> *(EN : Generative Agents vs. Statistical Oracles in Urban Mobility Simulation: Empirical Limits, Unit-Level Evaluation, and Hybrid Perspectives)*

**Version du document :** `v1.14` (21 septembre 2026) — les trames des chapitres 8 et 9 sont reprises du texte, dont elles avaient divergé entièrement. Le 8 annonçait quatre sous-sections dont aucune n'existait (cadre comparatif de performance, interactions intra-ménage) ; il en porte six, les § 8.5 et § 8.6 étant écrits le 21 septembre. Le 9 annonçait trois sous-sections quand il est une liste de cinq enseignements. `v1.13` (15 septembre 2026) — le chapitre 4 perd sa section 4.3 (périmètre de mesure) ; le socle devient 4.3 et la cohorte 4.4, tous deux chiffrés sur la v6 ; une seule lecture des parts modales. `v1.12` (même jour) — **restructuration des chapitres 5 et 6** ([ticket 080](../../../tickets/ticket_080_idee_directrice_du_chapitre_6_et_impact_sur_le_papier.md)). Le chapitre intercalaire 4.5 disparaît : son contenu devient le § 5.2, et le chapitre 5 devient le chapitre de protocole (ce que l'on compare), le 6 celui des résultats (ce que la comparaison établit). Le titre du chapitre 6 n'est plus arrêté : les scores recalculés depuis le dépôt le 15 septembre 2026 contredisent l'hypothèse H0 de non-atteinte qu'il devait établir, et son idée directrice est en décision. Le protocole de variabilité passe du chapitre 5 au 6 ; le benchmark multi-modèles quitte le corps du chapitre 5. `v1.11` (11 septembre 2026) — le chapitre 4 perd sa section de dimensionnement (contrainte de pages : il en reste une phrase en 4.5) et resserre son périmètre de mesure ; il couvre désormais exactement ce que la section 1.4 lui annonce. `v1.10` (même jour) — le chapitre 4 est rédigé, et sa trame interne change : une sous-section neuve sur le périmètre de mesure (ce qui n'entre pas au score), les références tabulaires deviennent une **famille en cours de caractérisation** plutôt qu'un oracle désigné, et la cohorte scellée retenue est la **v5**. Numérotation des sections inchangée. `v1.9` (même jour) — l'article gagne une section système : le dispositif évalué est décrit en section 3, les sections 3 à 8 antérieures décalent d'un cran jusqu'à la section 9. Le trou était réel — ni `article/`, ni le manuscrit figé `v1.6` ne décrivaient l'objet évalué, là où tout article comparable du corpus porte une section méthode ou système. `v1.8` (10 septembre 2026) — le résumé entre dans la trame comme section 0, le matériel de soumission AAMAS rejoint le dossier de l'article. `v1.7` du même jour : réalignée sur le plan annoncé en section 1.4 du chapitre 1 (`v0.16`), qui fait foi : l'état de l'art devient la section 2, les sections suivantes décalent d'un cran, la cascade hybride cesse d'être une section pour devenir les implications hybrides de la section 7, et les références quittent la numérotation. Écarts détaillés et datés dans [`README.md`](README.md). Version antérieure figée dans [`../../archive/PLAN_ARTICLE_2026_v1.6.md`](../../archive/PLAN_ARTICLE_2026_v1.6.md).
**Ce qui fait foi :** le texte de l'article, section 1.4 de [`../en/01_introduction.md`](../en/01_introduction.md). Ce fichier en est dérivé — voir [`README.md`](README.md).
**Fichiers associés :** [`../README.md`](../README.md) (état d'avancement par chapitre), [`../../methode/PROTOCOLE_SCIENTIFIQUE.md`](../../methode/PROTOCOLE_SCIENTIFIQUE.md), [`../../sources/BIBLIOGRAPHIE.md`](../../sources/BIBLIOGRAPHIE.md), [`../../sources/sample.bib`](../../sources/sample.bib)

---

## Structure de l'article

```
0. RÉSUMÉ                                          rédigé — article/{en,fr}/00_abstract.md
   240 mots, borne OpenReview de 100 à 300 ; emplacements chiffrés encore à remplir

1. INTRODUCTION                                    rédigée — article/{en,fr}/01_introduction.md
   1.1 Contexte : mobilité multimodale, transport centré sur l'usager, exigence de fidélité
   1.2 Une population plausible agent par agent peut être fausse en agrégé
       -> substitut statistique (jugé sur la fidélité) vs système adaptatif (jugé sur la robustesse)
   1.3 Contributions et hypothèses
       -> C1 contrat d'évaluation à parité informationnelle (3 règles)
       -> C2 ablation en quatre paliers + H0, plafond distributionnel
       -> C3 deux régimes qu'aucune enquête ne tabule
   1.4 Organisation de l'article                    <-- fait foi pour toute la numérotation

2. ÉTAT DE L'ART                                   rédigé — article/{en,fr}/02_related_work.md
   2.1 Choix discrets et filtres de perception
   2.2 Agents génératifs en simulation de mobilité
   2.3 Alignement distributionnel des populations de LLM

3. LE DISPOSITIF : DÉCIDER DANS UNE VILLE CONTRAINTE   brouillon — article/fr/03_architecture.md
   3.1 Vue d'ensemble : GAMA porte le monde, le contrôleur le cycle de vie, le module LLM le choix
   3.2 Le terrain : deux moteurs d'itinéraires, l'horloge du réseau, le périmètre, les modes ouverts
   3.3 Le point de décision : ce que l'agent voit, ce qu'il rend (un indice, pas un trajet)
   3.4 Mémoire courte et longue : ce qui fait qu'un jour ressemble au précédent
   3.5 La journée est une chaîne : les trois règles des véhicules personnels

4. MÉTRIQUES ET SOCLE D'ÉVALUATION                 brouillon v0.9 — article/fr/04_metrics_and_substrate.md
   4.1 Deux échelles, et la lecture qui décide de tout (une seule lecture : la masse de probabilité)
   4.2 Les trois règles du contrat : parité informationnelle, lectures homogènes, renormalisation sur l'offre
   4.3 Le socle de référence : un seul jeu de test, quatre familles tabulaires chiffrées sur la v6, deux lectures (chaîne / sans chaîne)
   4.4 La cohorte scellée et son contrôle démographique (13 marges, TOST ± 1 pt, chiffré)
   -- le périmètre de mesure (ancienne 4.3) et le dimensionnement de l'échantillon quittent le chapitre
      -> methode/JUSTIFICATION_TAILLE_ECHANTILLON.md

5. QUATRE FAÇONS DE CHOISIR, UNE SEULE INFORMATION  trame — article/fr/05_factual_neutral_prompt.md
   -- le chapitre de PROTOCOLE : il définit les conditions comparées, le 6 dit ce qu'elles donnent
   5.1 Le prompt factuel neutre : tout dire de la personne et du trajet, rien de la décision
   5.2 Le prompt calibré : optimiser sans apprendre l'enquête par cœur
       -> absorbe l'ancien chapitre intercalaire 4.5 ; le numéro 4.5 DISPARAÎT de l'article
       -> optimisation réfléchie (LLM-as-Optimizer) et les quatre garde-fous anti-surapprentissage
       -> la recherche génétique tient en UN paragraphe : écartée sur son coût en tokens, pas par
          principe ; la perspective (si le coût baisse d'un ordre de grandeur) part en section 8
   5.3 Les deux bouts de l'échelle : planchers et références tabulaires
       -> les quatre paliers de l'ablation sont définis ici, une fois pour toutes
   -- SORT DU CHAPITRE : le benchmark multi-modèles (annexe ou tableau en 6.1, à trancher) ;
      le protocole de variabilité, qui devient la section 6.3

6. TITRE À ARRÊTER — ticket 080 (chapitre de résultats)   trame — article/fr/06_results.md
   -- le chapitre de RÉSULTATS. Son idée directrice n'est PAS tranchée : les scores recalculés le
      2026-09-15 contredisent l'hypothèse H0 de non-atteinte qu'il devait établir. Trois options
      sont posées au ticket 080 (équivalence / le palier 2 fait le travail / le critère a changé
      de nature), et le titre découle de celle qui sera retenue.
   6.1 Treize décideurs sur la même échelle (les trois lectures, et l'écart apparié au plafond)
   6.2 Ce que l'ingénierie de prompt déplace (prompt minimal -> prompt expert, et sur quel modèle)
   6.3 Le détail des résultats agrégés, sur Gemini 3.5 (pente de distance, résidu par mode)
   6.4 Décider pareil, décider autrement (accord décision par décision, exactitude unitaire)
   6.5 Variation de cohorte et dispersion entre graines
   -- ÉTAT AU 2026-09-17 : rédigé en `brouillon v0.4`, tous les décideurs sur le jeu corrigé du
      ticket 088. Le détail part à l'annexe H. Restent la dispersion inter-graines (ticket 073,
      deux **TBC** au § 6.5) et l'exactitude unitaire de l'agent (ticket 058, deux [xx] au § 6.4)

7. RÉGIMES NON TABULÉS                             brouillon — article/fr/07_untabulated_regimes.md
   7.1 Cinq événements de presse locale datés, cinq conditions par événement,
       sous les prédictions directionnelles préenregistrées et leurs critères de réfutation
   7.2 Cinq jours, un retard subi le deuxième : trois conditions dont un agent sans mémoire
   7.3 Ce que ce chapitre transmet

8. LIMITES ET IMPLICATIONS HYBRIDES                brouillon — article/fr/08_limits_and_hybrid.md
   8.1 L'offre d'itinéraires ne contient aucun trajet combiné
   8.2 La chaîne des véhicules, l'horizon de décision et le parc du ménage
   8.3 Ce que coûte une journée simulée
   8.4 Ce que ces limites impliquent pour une architecture en cascade
   8.5 Les deux registres de la mémoire partagent un seul magasin
   8.6 Le dispositif s'exécute en anglais

9. CONCLUSION                                      brouillon — article/fr/09_conclusion.md
   Cinq enseignements numérotés, sans sous-sections : pas de LLM pour la prédiction de masse
   statique ; la valeur du LLM dans la dépendance contextuelle et l'adaptation ; un enseignement
   de mesure transférable hors de ce cas ; l'architecture hybride en cascade, dont la part de
   flux par étage reste un emplacement ; le coût et la reproductibilité, qui tranchent là où la
   fidélité ne tranche pas
```

**Hors numérotation des sections :**

- Références bibliographiques : [`../../sources/BIBLIOGRAPHIE.md`](../../sources/BIBLIOGRAPHIE.md) et [`../../sources/sample.bib`](../../sources/sample.bib).
- Annexes techniques : [`../fr/99_annexes.md`](../fr/99_annexes.md), brouillon issu du manuscrit.
