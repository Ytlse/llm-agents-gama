# Plan de Recherche & Manuscrit Consolidé (2026)

**Titre de travail proposé :**  
> *De la Décision Statistique au Comportement Adaptatif : Évaluation Empirique, Limites et Perspectives Hybrides des Agents LLM en Simulation de Mobilité Urbaine*  
> *(Alternative EN: Generative Agents vs. Statistical Oracles in Urban Mobility Simulation: Empirical Limits, Unit-Level Evaluation, and Hybrid Perspectives)*

**Version du document :** `v1.3` (2 septembre 2026)  
**Fichiers associés :** [`MANUSCRIT_DETAILLE_2026.md`](MANUSCRIT_DETAILLE_2026.md), [`PROTOCOLE_SCIENTIFIQUE.md`](PROTOCOLE_SCIENTIFIQUE.md), [`MANUSCRIT_DETAILLE_2026_SLIDES.html`](MANUSCRIT_DETAILLE_2026_SLIDES.html)

---

## Structure Détaillée de l'Article (Démarche 0 ➔ 1 ➔ 2 ➔ 3a ➔ 3b ➔ Perspectives)

```
1. INTRODUCTION & POSITIONNEMENT SCIENTIFIQUE
   1.1 De la règle rigide à l'agent génératif en transport
   1.2 Le verrou scientifique : Réalisme qualitatif vs Calage statistique sur Toulouse
   1.3 Positionnement à parité informationnelle (Macro/Micro) et axes de l'article

2. ÉTAPE 0 : DÉFINITION DES MÉTRIQUES & VALIDATION DÉMOGRAPHIQUE
   2.1 Cadre de mesure : Métriques macro (Parts modales, Erreur L1) & micro (Accuracy, Rappel, LogLoss)
   2.2 Validation démographique de la population synthétique N=1 000 (RP 2022 / EMC² 2023, Chi2 p=0.98)
   2.3 Stabilité d'échelle (N = 1 000 -> 10 000)

3. ÉTAPE 1 : ÉVALUATION DU MODÈLE NU (BARE LLM) & ÉTUDE DE VARIABILITÉ
   3.1 Modèle nu : prompt minimaliste neutre ("Choisis l'itinéraire le plus approprié") + options OTP
   3.2 Benchmark multi-modèles (Mistral-Small, Qwen-2.5-32B local, Gemini)
   3.3 Étude de la variabilité inter-runs à basse température (dispersion sur 5 seeds, IC 95%)

4. ÉTAPE 2 : INVALIDATION PAR L'ABLATION & AUDIT FACE AUX BASELINES STATISTIQUES
   4.1 Étude d'ablation en 4 paliers (Planchers -> Modèle Nu -> Calibré -> Baselines)
   4.2 Invalidation du prompt engineering : prévalence des temps terminaux physiques sur le prompt
   4.3 Audit unitaire à parité informationnelle stricte sur 13 045 trajets scellés (15 variables)
   4.4 Analyse SHAP (géométrie od_km 28.5%, densité 12.6%) vs Justifications sémantiques LLM

5. ÉTAPE 3 : LA VALEUR AJOUTÉE DU LLM (ÉVÉNEMENTS RÉELS & DYNAMIQUE TEMPORELLE)
   5.1 Étape 3a : Adaptation aux situations exceptionnelles & Hystérésis temporelle sur 5 jours (J1..J5)
   5.2 Étape 3b : Évaluation écologique sur événements réels sourcés dans la presse locale (Minotaure, Ozone, Rocade)

6. CONCEPT & PERSPECTIVES : ARCHITECTURE HYBRIDE EN CASCADE
   6.1 Formulation de la cascade comme prospective (Règles -> LightGBM 90% -> LLM 10%)
   6.2 Cadre comparatif de performance multidimensionnel (Gain 10x vitesse, -90% tokens)
   6.3 Interactions intra-ménage et conservation des chaînes spatiales de véhicules

7. CONCLUSION & ENSEIGNEMENTS
```
