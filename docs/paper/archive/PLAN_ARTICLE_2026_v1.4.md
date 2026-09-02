# Plan de Recherche & Manuscrit Consolidé (2026)

**Titre de travail proposé :**  
> *De la Décision Statistique au Comportement Adaptatif : Évaluation Empirique, Limites et Perspectives Hybrides des Agents LLM en Simulation de Mobilité Urbaine*  
> *(Alternative EN: Generative Agents vs. Statistical Oracles in Urban Mobility Simulation: Empirical Limits, Unit-Level Evaluation, and Hybrid Perspectives)*

**Version du document :** `v1.4` (2 septembre 2026)  
**Fichiers associés :** [`MANUSCRIT_DETAILLE_2026.md`](MANUSCRIT_DETAILLE_2026.md), [`PROTOCOLE_SCIENTIFIQUE.md`](PROTOCOLE_SCIENTIFIQUE.md), [`MANUSCRIT_DETAILLE_2026_SLIDES.html`](MANUSCRIT_DETAILLE_2026_SLIDES.html), [`SLIDES_SEMINAIRE_2026_v1.0.html`](SLIDES_SEMINAIRE_2026_v1.0.html)

---

## Structure Détaillée de l'Article (Démarche 0 ➔ 1 ➔ 2 ➔ 3a ➔ 3b ➔ Perspectives)

```
1. INTRODUCTION & POSITIONNEMENT SCIENTIFIQUE
   1.1 De la règle rigide à l'agent génératif en transport
   1.2 Le verrou scientifique : Réalisme qualitatif vs Calage statistique sur Toulouse
   1.3 Positionnement à parité informationnelle (Macro/Micro) et axes de l'article

2. ÉTAPE 0 : DÉFINITION DES MÉTRIQUES & VALIDATION DÉMOGRAPHIQUE
   2.1 Cadre de mesure : Métriques macro (Parts modales, Erreur L1) & micro (Accuracy, Rappel, LogLoss)
   2.2 Trois règles de comparabilité : argmax contre argmax, renormalisation sur l'offre (IIA), effectif obligatoire
   2.3 Cohérence démographique de la population synthétique N=1 000 (RP 2022 / EMC² 2023, écart max 0,4 pt)
       -> requalifiée en contrôle de cohérence ; test d'équivalence (TOST) et croisements à produire
   2.4 Dimensionnement de l'échantillon N=1 000 & justification statistique
       -> effectif efficace n_eff ≈ 1 750 (cluster bootstrap), plancher EMC² ±0,5 pt, arbitrage variance vs biais
   2.5 Stabilité d'échelle (N = 1 000 -> 10 000)

3. ÉTAPE 1 : ÉVALUATION DU MODÈLE NU (BARE LLM) & ÉTUDE DE VARIABILITÉ
   3.1 Modèle nu : prompt minimaliste neutre ("Choisis l'itinéraire le plus approprié") + options OTP
   3.2 Benchmark multi-modèles (Mistral-Small, Qwen-2.5-32B local, Gemini)
   3.3 Étude de la variabilité inter-runs à basse température (dispersion sur 5 seeds, IC 95%)
   3.4 Taux de bascule individuelle inter-graines & test de McNemar sur décisions appariées

4. ÉTAPE 2 : INVALIDATION PAR L'ABLATION & AUDIT FACE AUX BASELINES STATISTIQUES
   4.1 Étude d'ablation en 4 paliers (+ palier 2 bis few-shot) : Planchers -> Nu -> Calibré -> Baselines
   4.2 Invalidation du prompt engineering : prévalence des temps terminaux physiques (voiture 7,93 -> 0,55 min = -4,52 pt)
   4.3 Audit unitaire à parité informationnelle stricte, contrat de 21 variables
       -> oracle et MNL sur 13 045 trajets scellés ; LLM sur un sous-échantillon de 1 000
       -> dissymétrie d'exposition déclarée : 31 279 trajets vus contre zéro
   4.4 Analyse SHAP (géométrie od_km 28.5%, densité 12.6%) vs Justifications sémantiques LLM
   4.5 L'angle mort de l'oracle : rappel vélo 13,8 % pour 4,0 % de support
   4.6 Enseignement transférable : 93,4 % d'accuracy sur l'enquête = pire score en simulation (fuite par la durée)

5. ÉTAPE 3 : LA VALEUR AJOUTÉE DU LLM (ÉVÉNEMENTS RÉELS & DYNAMIQUE TEMPORELLE)
   5.1 Étape 3a : Hystérésis temporelle sur 5 jours (J1..J5), trois bras dont un agent SANS mémoire
       -> statut épistémique : pas de vérité terrain ; on teste l'ordre des bras, la monotonie, la sensibilité a gamma/lambda
   5.2 Étape 3b : Évaluation écologique sur presse locale sourcée (30 articles, 5 scénarios majeurs)
       -> cinq conditions : Base / Brut / Paraphrase sans indice modal / Placebo / Oracle informé
       -> prédictions pré-enregistrées : 120 signes issus de la grille d'expertise, gelée avant tout appel
   5.3 Critères de réfutation de H3, et cohérence physique texte <-> graphe

6. CONCEPT & PERSPECTIVES : ARCHITECTURE HYBRIDE EN CASCADE
   6.1 Formulation de la cascade comme prospective (Règles -> LightGBM 90% -> LLM 10%)
   6.2 Cadre comparatif de performance multidimensionnel (Gain 10x vitesse, -90% tokens)
   6.3 Interactions intra-ménage et conservation des chaînes spatiales de véhicules

7. CONCLUSION & ENSEIGNEMENTS
```
