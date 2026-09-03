# Cadre Méthodologique & Protocole Scientifique de Référence (2026)
## Projet LLM-Agents GAMA / Modélisation Comportementale de Mobilité Urbaine

**Auteurs :** Yves B., Benoit Gaudou, Kamaldeep Singh Oberoi  
**Contexte :** Projet LLM-Agents GAMA / Défis Clés Occitanie (MIDOC)  
**Objet :** Guide méthodologique, normes de rigueur scientifique, protocoles d'expérimentation et standards de publication pour l'article de recherche 2026.

---

## 1. Principes Épistémologiques & Standards de Rigueur

La recherche sur les agents génératifs appliqués aux sciences sociales et aux transports (GABM) doit respecter les standards les plus stricts de la méthode scientifique. L'objectif est de produire des résultats **réfutables**, **reproductibles** et **statistiquement solides**.

```
                ┌────────────────────────────────────────────────────────┐
                │ 1. Question de Recherche & Hypothèses Testables (H0)   │
                └──────────────────────────┬─────────────────────────────┘
                                           │
                                           ▼
                ┌────────────────────────────────────────────────────────┐
                │ 2. Protocole Contrôlé (Ceteris Paribus, Zéro Fuite)    │
                └──────────────────────────┬─────────────────────────────┘
                                           │
                                           ▼
                ┌────────────────────────────────────────────────────────┐
                │ 3. Baselines Loyales (Logit Multinomial & LightGBM)    │
                └──────────────────────────┬─────────────────────────────┘
                                           │
                                           ▼
                ┌────────────────────────────────────────────────────────┐
                │ 4. Validation Statistique (Seeds, IC95, Ablations)    │
                └──────────────────────────┬─────────────────────────────┘
                                           │
                                           ▼
                ┌────────────────────────────────────────────────────────┐
                │ 5. Discussion des Limites & Menaces de Validité        │
                └────────────────────────────────────────────────────────┘
```

### 1.1 Falsifiabilité et Hypothèses Claires
Chaque section expérimentale de l'article doit tester une hypothèse formelle $H_1$ contre une hypothèse nulle $H_0$ :
* **Hypothèse Macro ($H_{1,\text{macro}}$)** : Les agents LLM génèrent des biais systématiques de distribution modale dus à leurs priors linguistiques, non résolubles par du simple prompt engineering.
* **Hypothèse Micro ($H_{1,\text{micro}}$)** : Sur données tabulaires d'enquête sans contexte qualitatif, un modèle supervisé (LightGBM) surpasse significativement le LLM en précision et en coût.
* **Hypothèse Sémantique ($H_{1,\text{qual}}$)** : L'agent LLM réagit de manière cohérente et statistiquement significative aux contraintes narratives non tabulées (encombrement, sécurité, météo, tenue).
* **Hypothèse Dynamique ($H_{1,\text{hyst}}$)** : L'intégration d'une mémoire épisodique permet de modéliser l'hystérésis comportementale (inertie post-perturbation) qu'un modèle statistique statique réinitialise instantanément.

### 1.2 Principe d'Isolation des Variables (*Ceteris Paribus*)
Pour isoler l'effet d'une variable ou d'un composant architectural :
1. **Identité stricte de l'environnement** : Même réseau routier/TC, mêmes horaires GTFS, mêmes calculs d'itinéraires OTP.
2. **Étude d'ablation systématique** : Pour tout composant revendiqué (mémoire, filtre de contraintes, cascade), évaluer le système $S$ et le système dégradé $S \setminus \{\text{Composant}\}$.
3. **Contrôle de la variance stochastique** : 
   * Pour les évaluations déterministes : $\tau = 0.0$, seed fixé.
   * Pour les simulations stochastiques : $\tau > 0$, répétition sur $N \ge 5$ seeds distincts, rapport de la moyenne $\mu$ et de l'intervalle de confiance à $95\,\%$ ($\mu \pm 1.96 \frac{\sigma}{\sqrt{N}}$).

### 1.3 Étanchéité des Données (*Zero Data Leakage*)
* **Découpage par grappe de ménage (`hh_id`)** : La partition Train ($60\,\%$), Validation ($15\,\%$), Test ($25\,\%$) sur l'enquête EMC² 2023 ($52\,248$ trajets) est groupée strictement par identifiant de foyer afin d'éviter toute contamination intra-ménage.
* **Jeu de test scellé** : Les $13\,045$ trajets du jeu de test ne sont jamais utilisés pour calibrer les prompts, ajuster des seuils ou entraîner des modèles.

---

## 2. Protocoles Expérimentaux Détaillés

---

### Protocole 1 : Évaluation Unitaire à Parité Informationnelle Stricte (Bloc 3)

**Objectif :** Comparer la précision décisionnelle micro du LLM face aux baselines statistiques sur le jeu de test réel.

1. **Jeu de données :** Échantillon stratifié de $N = 1\,000$ trajets extrait du jeu de test scellé `mode_choice_test.csv`.
2. **Parité Informationnelle Stricte :** 
   * Le LLM et les modèles statistiques reçoivent **exactement le même vecteur de 15 variables socio-démographiques et spatiales** :
     $$\vec{x} = (\text{age}, \text{gender}, \text{hh\_size}, \text{license}, N_{\text{cars}}, \text{car\_avail}, \text{bike}, \text{pt\_sub}, \text{occupation}, \text{purpose}, \text{dep\_hour}, od\_km, \text{same\_zone}, \text{dens\_orig}, \text{dens\_dest})$$
   * Aucune information d'itinéraire externe (OTP) n'est fournie dans cette expérience afin de garantir une équité parfaite.
3. **Modèles comparés :**
   * **Baseline 1** : Multinomial Logit (MNL) de référence en économie des transports.
   * **Baseline 2** : LightGBM supervisé optimisé.
   * **LLM Local (Open-Weights)** : Qwen-2.5-32B-Instruct ($\tau = 0.0$, inférence locale déterministe).
   * **LLMs Distants (APIs)** : Mistral-Small, Gemini-1.5/2.0-Flash.
4. **Métriques d'évaluation :**
   * Accuracy globale pondérée.
   * Précision, Rappel et F1-Score par modalité (Voiture, Marche, TC, Vélo).
   * Matrice de confusion croisée $4 \times 4$ (LLM vs Réel, LLM vs LightGBM).
   * Coût computationnel (temps par décision, tokens consommés).

---

### Protocole 2 : Étude Factorielle par Vignettes Sémantiques Contrôlées (Bloc 1)

**Objectif :** Démontrer scientifiquement la capacité du LLM à traiter des contextes qualitatifs non tabulables sans biais de sélection (*cherry-picking*).

1. **Génération du jeu de vignettes ($N = 50$ profils de base) :**
   * Échantillonnage de 50 trajets d'enquête représentatifs couvrant différentes distances ($0.5\text{ km} \le od\_km \le 15\text{ km}$) et différentes classes socio-professionnelles.
2. **Matrice Factorielle des Perturbations ($50 \times 5 = 250$ tests) :**
   * **Condition $C_0$ (Contrôle / Nominal)** : Profil socio-démographique pur.
   * **Condition $C_1$ (Logistique / Encombrement)** : Ajout d'un bagage lourd ou objet fragile (ex. colis volumineux, gâteau d'anniversaire).
   * **Condition $C_2$ (Sécurité Situationnelle)** : Déplacement nocturne (23h30) en zone isolée ou mal éclairée.
   * **Condition $C_3$ (Météo Dégradée)** : Averse continue et rafales de vent.
   * **Condition $C_4$ (Contrainte Vestimentaire / Événement)** : Entretien formel ou cérémonie en tenue habillée.
3. **Mesure et Test Statistique :**
   * Pour chaque condition $C_k$, mesure du taux de bascule modal par rapport au nominal $C_0$ :
     $$\Delta \text{Bascule}(C_k) = \frac{1}{N} \sum_{i=1}^N \mathbb{I}(\text{Choix}_i(C_k) \neq \text{Choix}_i(C_0))$$
   * Test de significativité statistique de la modification des choix (Test de McNemar pour les paires liées ou test du $\chi^2$ d'indépendance, seuil $\alpha = 0.01$).

---

### Protocole 3 : Modélisation et Dynamique Longitudinale de l'Hystérésis (Bloc 1)

**Objectif :** Démontrer l'effet de mémoire comportementale à la suite d'un choc sur le réseau et mesurer la cinétique de ré-adoption du mode.

1. **Formalisation de l'état interne de l'agent :**
   * Chaque agent génératif dispose d'un registre de mémoire court-terme $\mathcal{M}_t$ horodaté :
     $$\mathcal{M}_t = \left\{ e_k = \left( t_k, \text{mode}_k, \Delta t_{\text{retard}, k}, \text{ressenti}_k \right) \mid t - t_k \le \Delta T_{\text{horizon}} \right\}$$
   * Le prompt injecte l'historique des trajets récents issus de $\mathcal{M}_t$.
2. **Scénario d'expérience longitudinale sur 5 jours consécutifs ($J_1$ à $J_5$) :**
   * **Jour $J_1$ (Régime nominal)** : Réseau fluide, aucune perturbation. Enregistrement du taux de choix initial (ex: Métro = $p_1$).
   * **Jour $J_2$ (Choc / Incident à 17h)** : Panne majeure sur la ligne de métro lors du trajet de retour. Retard subi $\Delta t = +45\text{ min}$, ressenti négatif consigné dans $\mathcal{M}_t$.
   * **Jour $J_3$ (Nominal rétabli - Test d'Hystérésis)** : Le réseau fonctionne à nouveau à $100\,\%$. Mesure du taux d'évitement résiduel $p_3 < p_1$ (churn modal temporaire).
   * **Jours $J_4$ et $J_5$ (Résorption et retour à l'équilibre)** : Mesure de la cinétique de ré-adoption progressive ($p_3 \to p_4 \to p_5 \approx p_1$).
3. **Comparaison face aux baselines :**
   * **LightGBM / Logit** : Amnésiques, $p_3 = p_1$ dès $J_3$ (reprise instantanée car les variables d'entrée physiques sont identiques).
   * **LLM avec Mémoire** : Courbe de rémission logarithmique démontrant l'inertie cognitive.

---

### Protocole 4 : Macro-Simulation & Évaluation de l'Architecture Hybride en Cascade (Bloc 2 & 4)

**Objectif :** Évaluer empiriquement le compromis de performance entre simulation 100 % LightGBM, 100 % LLM, et Architecture Hybride en Cascade.

1. **Architecture de Triage à 3 Étages :**
   * **Étage 1 (Filtre Déterministe)** : Élimination stricte des modes impossibles (pas de permis $\to$ pas de voiture, pas de vélo possédé $\to$ pas de vélo).
   * **Étage 2 (Oracle Supervisé - 90 % du flux)** : Si trajet nominal de routine (pas d'incident réseau, météo standard, pas de conflit de ressource), décision par LightGBM.
   * **Étage 3 (Agent LLM - 10 % d'exceptions)** : Si incident réseau, alerte météo, bagage/contexte qualitatif, ou arbitrage de voiture partagée au sein du ménage, activation du raisonnement LLM.
2. **Cadre d'évaluation comparative sur $10\,000$ décisions de déplacement :**

| Métrique d'Évaluation | Définition Mathématique | Enjeu Scientifique |
|---|---|---|
| **Erreur de Distribution (L1 Loss)** | $\sum_{m \in \text{Modes}} \vert P_{\text{sim}}(m) - P_{\text{EMC}^2}(m) \vert$ | Fidélité macroscopique aux parts modales réelles |
| **Coût Computationnel** | Temps total d'exécution CPU/GPU | Faisabilité pour des jumeaux numériques urbains |
| **Volume de Tokens / Coût API** | Nombre total de tokens d'entrée/sortie | Scalabilité économique |
| **Indice d'Adaptabilité Contextuelle** | Taux de réponse appropriée aux incidents $J_2 / J_3$ | Réalisme comportemental en crise |

---

## 3. Checklist de Rigueur pour le Manuscrit

Avant toute soumission ou partage académique :

- [ ] **Pas d'affirmation sans quantification** : Remplacer tout adjectif subjectif (*« très performant »*, *« bien meilleur »*) par un chiffre précis et un test statistique.
- [ ] **Reproductibilité logicielle** : Spécifier la version exacte des bibliothèques (`lightgbm==4.3.0`, `vllm==0.6.0`), les commits git, et les hyperparamètres.
- [ ] **Poids ouverts comme garantie pérenne** : Inclure au moins une évaluation complète sur un modèle open-weights local (ex: Qwen-2.5-32B).
- [ ] **Transparence sur les résultats négatifs** : Consigner explicitement les échecs de la calibration de prompt par Shapley (Annexe D) pour guider utilement la communauté.
- [ ] **Déclaration sur les menaces à la validité** : Rédiger un paragraphe dédié dans la section Discussion détaillant les limites de l'étude (ex: couverture géographique limitée à Toulouse, hypothèse de non-interaction directe entre piétons).
