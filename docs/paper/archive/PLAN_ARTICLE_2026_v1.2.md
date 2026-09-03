# Plan de Recherche & Manuscrit Consolidé (2026)

**Titre de travail proposé :**  
> *De la Décision Statistique au Comportement Adaptatif : Évaluation Empirique, Limites et Perspectives Hybrides des Agents LLM en Simulation de Mobilité Urbaine*  
> *(Alternative EN: Generative Agents vs. Statistical Oracles in Urban Mobility Simulation: Empirical Limits, Unit-Level Evaluation, and Hybrid Perspectives)*

**Version du document :** `v1.2` (1er septembre 2026)  
**Fichiers associés :** [`MANUSCRIT_DETAILLE_2026.md`](MANUSCRIT_DETAILLE_2026.md), [`PROTOCOLE_SCIENTIFIQUE.md`](PROTOCOLE_SCIENTIFIQUE.md)

---

## Structure Détaillée de l'Article

```
1. INTRODUCTION & POSITIONNEMENT
   1.1 De la règle rigide à l'agent génératif en transport
   1.2 Le dilemme : Réalisme qualitatif vs Calage statistique
   1.3 Positionnement à parité informationnelle et contributions du papier

2. JALON 0 : VALIDATION DÉMOGRAPHIQUE DE LA POPULATION SYNTHÉTIQUE
   2.1 Représentativité intrinsèque des agents sans pondération runtime
   2.2 Tableau de conformité et test d'adéquation Chi-deux (RP 2022 / CEREMA)
   2.3 Stabilité d'échelle (N = 1 000 -> 10 000)

3. COMPORTEMENT INDIVIDUEL, SÉMANTIQUE & ÉVÉNEMENTS RÉELS SOURCÉS (BLOC 1)
   3.1 Évaluation écologique sur presse locale (Minotaure, Pic d'Ozone, Coupure Périphérique)
   3.2 Protocole expérimental tripartite (Base vs Info vs Oracle)
   3.3 Formalisation mathématique de l'Hystérésis & Dynamique sur 5 jours (J1..J5)

4. ÉTUDE D'ABLATION INCRÉMENTALE EN 4 PALIERS (BLOC 2)
   4.1 Définition des 4 paliers (Planchers -> Modèle Nu Mistral/Qwen -> Calibré -> Baselines)
   4.2 Analyse macro-distributionnelle face à l'EMC² 2023
   4.3 Prévalence des temps terminaux physiques sur le prompt engineering

5. ÉVALUATION UNITAIRE FACE AUX BASELINES STATISTIQUES (BLOC 3)
   5.1 Protocole à parité informationnelle stricte sur 1 000 trajets scellés
   5.2 Inférence déterministe avec Qwen-2.5-32B local
   5.3 Analyse SHAP vs Justifications sémantiques

6. CONCEPT & PERSPECTIVES : ARCHITECTURE HYBRIDE EN CASCADE (BLOC 4)
   6.1 Triage à 3 étages (Règles -> LightGBM 90% -> LLM 10%)
   6.2 Cadre comparatif de performance multidimensionnel
   6.3 Modélisation des interactions ménage et chaînes spatiales

7. CONCLUSION & PERSPECTIVES
```

---

## Feuille de Route Expérimentale Mise à Jour

- [ ] **Jalon 0 (Démographie)** : Générer le tableau de Goodness-of-Fit comparant les 1 000 agents au rapport CEREMA / Insee.
- [ ] **Expérience 1 (Ablation 4 Paliers)** : Exécuter le benchmark comparatif (Hasard / Nu Mistral-Qwen / Calibré / LightGBM-MNL) sur le jeu de test scellé.
- [ ] **Expérience 2 (Événements Réels Sourcés)** : Tester les 3 scénarios d'actualité toulousaine (Minotaure, pic d'ozone, coupure rocade) et mesurer les taux de bascule.
- [ ] **Expérience 3 (Hystérésis 5 Jours)** : Mesurer la cinétique de ré-adoption post-panne métro ($J_1 \to J_5$).
- [ ] **Expérience 4 (Cascade Hybride)** : Simuler le flux mixte 90/10 et valider les gains de coût/vitesse et fidélité L1.
