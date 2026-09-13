# Plan de Recherche & Manuscrit Consolidé (2026)

**Titre de travail proposé :**  
> *De la Décision Statistique au Comportement Adaptatif : Évaluation Empirique, Limites et Perspectives Hybrides des Agents LLM en Simulation de Mobilité Urbaine*  
> *(Alternative EN: Generative Agents vs. Statistical Oracles in Urban Mobility Simulation: Empirical Limits, Unit-Level Evaluation, and Hybrid Perspectives)*

**Version du document :** `v1.1` (1er septembre 2026)  
**Fichiers associés :** [`MANUSCRIT_DETAILLE_2026.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/MANUSCRIT_DETAILLE_2026.md), [`PROTOCOLE_SCIENTIFIQUE.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/PROTOCOLE_SCIENTIFIQUE.md)

---

## Résumé du Projet d'Article (Abstract Draft)

Les grands modèles de langage (LLM) suscitent un intérêt croissant pour modéliser le comportement d'agents en simulation urbaine (GABM). Si leur expressivité sémantique promet des comportements plus riches que les règles rigides, leur fidélité empirique face aux enquêtes de déplacement réelles reste à quantifier rigoureusement. 

Dans ce travail, nous confrontons le comportement d'agents génératifs (Mistral, Gemini, Qwen-32B local) à des baselines statistiques éprouvées : un modèle Logit Multinomial (MNL) et un oracle supervisé LightGBM entraîné sur l'enquête ménages-déplacements EMC² 2023 de Toulouse (78,5 % d'accuracy sur $13\,045$ trajets scellés, split étanche par foyer) :
1. **Au niveau macro/agrégé**, nous analysons les biais structurels du LLM (sous-représentation massive de la marche, sur-pondération des transports collectifs et du vélo, forte sensibilité aux temps terminaux).
2. **Au niveau micro/unitaire**, nous établissons un protocole d'évaluation directe du LLM sur données d'enquête réelles masquées sous **parité informationnelle stricte** (même vecteur de 15 variables socio-spatiales), comparant matrices de confusion, F1-scores et SHAP vs motifs textuels.
3. **Sur le plan comportemental**, nous validons la valeur ajoutée du LLM via une **étude factorielle par vignettes sémantiques contrôlées** ($N = 50 \times 5 = 250$ tests, test de McNemar) et formalisons mathématiquement l'**hystérésis post-incident** (cinétique de ré-adoption sur 5 jours avec registre de mémoire court-terme $\mathcal{M}_t$).
4. Enfin, nous formulons le **concept et la perspective d'évaluation d'une architecture hybride en cascade** (Règles $\to$ LightGBM pour les 90 % de flux nominaux $\to$ LLM pour les 10 % d'exceptions et perturbations) intégrée aux contraintes du foyer (accompagnement intra-ménage, cohérence de chaîne de véhicule).

---

## Table des Matières et Structure Détaillée

```
1. INTRODUCTION & POSITIONNEMENT
   1.1 De la règle rigide à l'agent génératif en transport
   1.2 Le dilemme : Réalisme qualitatif vs Calage statistique
   1.3 Positionnement à parité informationnelle et contributions du papier

2. COMPORTEMENT INDIVIDUEL, CONTEXTE SÉMANTIQUE & ADAPTATION DYNAMIQUE (BLOC 1)
   2.1 Protocole expérimental nominal & Contrôle budgétaire
   2.2 Personas augmentés & Étude factorielle par vignettes sémantiques (C0..C4)
   2.3 Analyse automatique des justifications (Text Mining)
   2.4 Chocs ponctuels & Formalisation mathématique de l'Hystérésis (J1..J5)

3. UTILITÉ ET LIMITES EN SIMULATION DE MOBILITÉ (BLOC 2)
   3.1 Macro-distribution vs Réalité empirique (EMC² 2023)
   3.2 Sensibilité aux paramètres exogènes (Temps terminaux)
   3.3 Analyse des biais culturels et modèles LLM (Gemini, Mistral, Qwen)

4. ÉVALUATION UNITAIRE FACE AUX BASELINES STATISTIQUES (BLOC 3)
   4.1 Baselines de référence : Logit Multinomial (MNL) & Oracle LightGBM
   4.2 Protocole d'inférence directe à parité informationnelle stricte (Zero-Routing vs OTP)
   4.3 Inférence locale avec Qwen-32B (Zéro-coût, haute reproductibilité)
   4.4 Analyse SHAP vs Raisonnement sémantique

5. CONCEPT & PERSPECTIVES : ARCHITECTURE HYBRIDE & ÉCHELLE DU FOYER (BLOC 4)
   5.1 Architecture hybride en cascade (Triage Déterministe / ML / LLM)
   5.2 Cadre comparatif de performance (LightGBM vs LLM vs Cascade)
   5.3 Modélisation à l'échelle du ménage (Compétition véhicule, accompagnement, chaîne spatiale)

6. CONCLUSION & PERSPECTIVES
```

---

## Détail des Sections & Contenus

---

## Section 1 — Comportement individuel, Contexte sémantique & Adaptation (BLOC 1)

### 1.1 Protocole de référence & Contrôle des quotas
* **Règle préalable de dimensionnement** : Calcul strict du volume d'appels ($\text{Appels} = N_{\text{agents}} \times N_{\text{trajets}} \times N_{\text{jours}} \times N_{\text{seeds}} \times N_{\text{modèles}}$).
* **Gestion de la température et variance** : Documentation de la variance résiduelle observée même à basse température ($\tau \approx 0.2$), rapport systématique des intervalles de dispersion (IC95).

### 1.2 Étude factorielle par vignettes sémantiques contrôlées
* Échantillon de $N=50$ profils réels d'enquête croisés avec 5 conditions ($C_0$ contrôle nominal, $C_1$ logistique/encombrement, $C_2$ sécurité nocturne, $C_3$ météo dégradée, $C_4$ tenue formelle).
* Mesure du taux de bascule modal $\Delta \text{Bascule}(C_k)$ et validation statistique par test de McNemar ($p < 0.01$).

### 1.3 Text Mining des Justifications LLM
* Isolation des cas où $\text{Choix}_{\text{LLM}} \neq \text{Choix}_{\text{LightGBM}}$.
* Analyse NLP / clustering thématique sur le texte de justification produit par le LLM pour catégoriser objectivement les facteurs de bifurcation.

### 1.4 Formalisation mathématique de l'Hystérésis (J1 à J5)
* Registre de mémoire court-terme $\mathcal{M}_t$ avec dépréciation exponentielle de la confiance modale $w_m(t)$.
* Expérimentation longitudinale sur 5 jours avec panne à $J_2$ (17h), mesure du churn modal à $J_3$ et retour progressif à l'équilibre à $J_4 \to J_5$.

---

## Section 2 — Utilité & Limites observées en simulation (BLOC 2)

### 2.1 Analyse des distorsions distributionnelles
* Confrontation des résultats de simulation (Run de référence `2026-08-24_17_34`, 2 911 décisions) à l'enquête EMC² :
  * Voitures : 57,6 % (simu) vs 56,7 % (cible) $\to$ excellent calage global.
  * Marche : 11,9 % (simu) vs 26,8 % (cible) $\to$ sous-représentation critique.
  * Transports collectifs : 17,2 % (simu) vs 12,4 % (cible) $\to$ sur-attractivité.
  * Vélo : 13,3 % (simu) vs 4,1 % (cible) $\to$ sur-représentation des alternatives douces.

### 2.2 Sensibilité aux paramètres exogènes
* Analyse de l'impact des temps terminaux (accès/stationnement) : l'alignement sur les histogrammes réels d'enquête fait chuter le composite de $-4,52\text{ pt}$ (prouvant que la physique du réseau prime sur le prompt).
* Diagnostic du biais de report Marche $\to$ TC (495 décisions analysées où le LLM prend le bus pour des distances marchables).

---

## Section 3 — Évaluation unitaire face aux Baselines Statistiques (BLOC 3)

### 3.1 Statut des Baselines (Logit Multinomial & Oracle LightGBM)
* MNL économétrique et LightGBM entraînés sur $31\,279$ trajets réels, validés sur $13\,045$ trajets (split par foyer `hh_id` sans fuite de données).
* Performances LightGBM : **Accuracy 78,54 %**, LogLoss $0,54$, erreur L1 de distribution de $2,68\text{ pt}$.

### 3.2 Protocole du Banc d'Évaluation Unitaire à Parité Stricte (`eval_llm_on_survey.py`)
* Échantillon stratifié gelé de $N = 1\,000$ trajets réels issus de `mode_choice_test.csv`.
* Même vecteur de 15 caractéristiques socio-spatiales $\vec{x}$ injecté pour le LLM et les modèles statistiques.
* Inférence en aveugle (choix réel masqué) $\to$ calcul de la matrice de confusion 4x4, Précision, Rappel, F1 par mode.

### 3.3 Utilisation du modèle local Qwen-32B
* Exécution locale zéro-coût, déterministe et reproductible pour absorber des volumes de tests significatifs.
* Comparatif croisé avec les modèles distants (Mistral, Gemini) pour mesurer les biais culturels intrinsèques.

### 3.4 Confrontation SHAP vs Justifications
* LightGBM s'appuie à 60% sur la distance OD ($28,5\%$), l'abonnement TC ($9,5\%$), la zone fine ($7,4\%$) et la densité ($12,6\%$).
* Le LLM privilégie la vitesse apparente et le confort relatif.

---

## Section 4 — Concept & Perspectives : Architecture Hybride & Foyer (BLOC 4)

### 4.1 Architecture Hybride en Cascade (Proposition Conceptuelle & Évaluation)
* **Niveau 1 (Règles physiques)** : Filtre d'éligibilité strict (possession de permis, disponibilité véhicule).
* **Niveau 2 (Oracle statistique - 90% du trafic)** : Inférence LightGBM instantanée pour les trajets de routine nominaux.
* **Niveau 3 (Agent LLM - 10% d'exceptions)** : Déclenchement conditionnel lors d'incidents météo, pannes réseau, contextes familiaux ou incertitude ML ($\max P < 0.50$).

### 4.2 L'Échelle de la Cellule Familiale
* Arbitrage de l'équipement unique (compétition pour la voiture du ménage).
* Accompagnement intra-ménage (dépose d'enfants contraignant le mode pour le travail).
* Cohérence de chaîne spatiale (le véhicule reste là où il a été garé).

---

## Figures & Tables Prévues pour l'Article

1. **Figure 1** : Architecture logicielle du système hybride (Cascade Règles $\to$ LightGBM $\to$ LLM).
2. **Figure 2** : Matrice de confusion comparée (Logit vs LightGBM vs Qwen-32B sur le jeu de test EMC² 1 000 trajets).
3. **Figure 3** : Courbe longitudinale d'hystérésis post-incident ($J_1$ normal $\to$ $J_2$ incident $\to$ $J_3$ churn $\to$ $J_4-J_5$ rétablissement).
4. **Table 1** : Tableau comparatif multidimensionnel (Accuracy unitaire, L1 macro, Latence, Coût, Adaptabilité, Explicabilité).
5. **Table 2** : Feature Importance SHAP de LightGBM vs Thèmes extraits des justifications LLM.

---

## Feuille de Route Expérimentale (TODO Prochaines Semaines)

- [ ] **Expérience 1 (Unitaire)** : Développer et exécuter `scripts/progedo_logit/eval_llm_on_survey.py` avec Qwen-32B local sur $1\,000$ lignes de test à parité d'information stricte.
- [ ] **Expérience 2 (Vignettes Sémantiques)** : Évaluer les 50 profils sur les 5 conditions ($C_0 \dots C_4$) et tester la significativité statistique (McNemar).
- [ ] **Expérience 3 (Hystérésis)** : Créer le micro-scénario longitudinal de 5 jours avec incident à $J_2$ (17h) et mesurer la cinétique de ré-adoption ($J_3 \dots J_5$).
- [ ] **Expérience 4 (Text Mining)** : Extraire les motifs de divergence LLM $\neq$ LightGBM sur les justifications produites.
(LLM vs LightGBM).
- [ ] **Expérience 3 (Text Mining)** : Extraire les motifs de divergence LLM $\neq$ LightGBM sur les justifications produites.
- [ ] **Expérience 4 (Multi-LLM)** : Comparer la matrice de confusion sur un sous-échantillon avec Gemini / Mistral / Grok.
