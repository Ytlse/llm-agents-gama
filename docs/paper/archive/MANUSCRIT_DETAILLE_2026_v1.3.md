# De la Décision Statistique au Comportement Adaptatif : Évaluation Empirique, Limites et Perspectives Hybrides des Agents LLM en Simulation de Mobilité Urbaine

**Auteurs prévus :** Yves B., Benoit Gaudou, Kamaldeep Singh Oberoi *(ordre et affiliation à définir)*  
**Cadre de recherche :** Projet LLM-Agents GAMA / Défis Clés Occitanie (MIDOC) / Application métropolitaine toulousaine  
**Version du document :** `v1.3` (2 septembre 2026) — *Refonte de la démarche expérimentale (0: Métriques & Démographie, 1: Modèle Nu & Variabilité, 2: Invalidation Ablation & Audit Statistique, 3a: Hystérésis 5 jours, 3b: Presse Locale) et repositionnement de la cascade hybride en perspective*  
**Fichiers associés :** [`PROTOCOLE_SCIENTIFIQUE.md`](PROTOCOLE_SCIENTIFIQUE.md), [`PLAN_ARTICLE_2026.md`](PLAN_ARTICLE_2026.md)  
**Historique des versions :**
* `v1.0` *(Août 2026)* : Première trame complète du manuscrit et cadrage macro/micro.
* `v1.1` *(1er septembre 2026)* : Cadrage formel du protocole scientifique (parité informationnelle, vignettes factorielles, formalisation d'hystérésis).
* `v1.2` *(1er septembre 2026)* : Intégration du Jalon 0 (validation démographique), formalisation de l'ablation en 4 paliers et évaluation écologique.
* `v1.3` *(2 septembre 2026)* : Réalignement strict de la démarche expérimentale (0: Métriques & Socle, 1: Modèle Nu & Variabilité multi-runs, 2: Invalidation Ablation & Audit Statistique, 3a: Hystérésis 5j, 3b: Presse Locale) et repositionnement de la cascade hybride en perspective.

---

## Résumé (Abstract)

### Français
L'intégration des grands modèles de langage (LLM) au sein des simulations multi-agents de mobilité urbaine ouvre des perspectives inédites pour modéliser le comportement humain sans recourir à des systèmes de règles manuelles rigides. Toutefois, l'évaluation de ces agents face à des données d'enquête réelles révèle une tension fondamentale entre *richesse narrative qualitative* et *fidélité distributionnelle quantitative*.

Dans cet article, nous proposons une évaluation empirique et critique des capacités décisionnelles des agents LLM appliqués au choix modal de transport sur l'aire métropolitaine de Toulouse. Après avoir validé la représentativité sociologique de notre population synthétique ($N = 1\,000$ agents) face au recensement Insee RP 2022 et à l'enquête EMC² 2023 (test $\chi^2$, $p=0,98$), nous déployons une démarche expérimentale rigoureuse : (0) définition des métriques macro/micro ; (1) évaluation du modèle nu (Mistral AI, Qwen-32B local, Gemini) et mesure de la variabilité inter-runs à basse température ; (2) invalidation par l'ablation montrant la prévalence des paramètres physiques de réseau sur le prompt engineering, couplée à un audit unitaire face à un oracle supervisé LightGBM ($78,5\,\%$ d'accuracy sur $13\,045$ trajets scellés) ; (3) démonstration de la vraie valeur ajoutée du LLM sur l'adaptation aux événements réels d'actualité (presse locale toulousaine) et la modélisation de l'hystérésis comportementale (cinétique de ré-adoption sur 5 jours avec mémoire court-terme $\mathcal{M}_t$).

En conclusion, nous formulons les perspectives d'une architecture hybride en cascade (Règles déterministes $\to$ LightGBM pour $90\,\%$ du flux nominal $\to$ LLM pour $10\,\%$ de perturbations complexes) conciliant passage à l'échelle et réactivité contextuelle.

### English
*Integrating Large Language Models (LLMs) into agent-based mobility simulations offers new avenues for modeling human decision-making beyond rigid rule-based systems. However, benchmarking these agents against real-world travel surveys reveals a fundamental trade-off between qualitative semantic expressiveness and quantitative distributional fidelity.*

*In this paper, we present an empirical assessment of LLM agents for mode choice in the Toulouse metropolitan area. After validating the demographic alignment of our synthetic population ($N = 1,000$ agents) against the Insee Census and the 2023 EMC² household travel survey ($\chi^2$ test, $p=0.98$), we follow a systematic experimental progression: (0) formal definition of macro and micro evaluation metrics; (1) bare LLM evaluation (Mistral AI, local Qwen-32B, Gemini) measuring multi-run variability at low temperature; (2) ablation study showing that physical network parameters outweigh prompt engineering, paired with a unit-level audit against a LightGBM statistical oracle ($78.5\%$ accuracy on $13,045$ sealed test trips); (3) demonstration of the LLM's unique value in processing unstructured local news events and capturing longitudinal behavioral hysteresis (5-day recovery kinetics via memory buffer $\mathcal{M}_t$).*

*Finally, we outline the perspectives of a cascading hybrid architecture (Deterministic Rules $\to$ LightGBM for $90\%$ nominal flow $\to$ LLM for $10\%$ disruptions) balancing scalability and contextual adaptability.*

---

# 1. Introduction & Positionnement Scientifique

### 1.1 Contexte : L'émergence des agents génératifs en simulation de transport
La modélisation multi-agents des systèmes de transport (ABM) repose traditionnellement sur :
* Les **modèles de choix discrets** (Logit multinomial, Logit emboîté), calibrés sur des utilités économétriques globales mais rigides face à des contextes imprévus ;
* Les **systèmes experts à base de règles** (arbres décisionnels, automates BDI), coûteux à concevoir manuellement et incapables de généraliser hors de leur domaine nominal.

L'avènement des modèles de langage génératifs (LLM) permet d'introduire des agents autonomes capables de raisonner en langage naturel, d'évaluer des compromis complexes (durée, confort, météo, contraintes d'agenda) et de justifier explicitement leurs choix.

### 1.2 Le verrou scientifique : Réalisme qualitatif vs Calage empirique
Si les agents LLM font preuve d'une expressivité impressionnante sur des scénarios individuels scénarisés, la simulation sur l'aire métropolitaine de Toulouse se heurte à la **fidélité distributionnelle**. Les LLM n'ont pas été entraînés pour reproduire la répartition modale d'un territoire spécifique. Leurs distributions agrégées sont biaisées par des priors culturels mondiaux issus de leur pré-entraînement, conduisant à des anomalies systématiques (ex. sous-estimation de la marche à pied courte, engouement disproportionné pour les transports en commun).

### 1.3 Positionnement du travail
Ce papier se positionne au croisement de trois disciplines :
1. **Évaluation empirique duale (Macro & Micro)** : Évaluer les LLM hors des benchmarks synthétiques sur des données d'enquête réelles d'envergure (EMC² 2023, $785$ zones fines, $453$ communes de l'aire toulousaine), en analysant à la fois les statistiques agrégées (parts modales) et les décisions individuelles unijoueurs ;
2. **Audit critique face aux baselines statistiques et à l'Oracle supervisé** : Utiliser le Logit Multinomial (MNL) et un modèle de Machine Learning tabulaire de pointe (LightGBM) comme références de ce que les approches classiques produisent à **parité informationnelle stricte** (15 variables identiques) ;
3. **Qualification du domaine d'excellence des LLM et perspectives hybrides** : Identifier la vraie rupture comportementale du LLM (actualités réelles non tabulées, dynamique d'hystérésis temporelle) et poser les perspectives d'une architecture hybride en cascade.

---

# 2. Étape 0 : Définition des Métriques & Validation Démographique

### 2.1 Cadre de Mesure et Métriques d'Évaluation
Pour évaluer rigoureusement les modèles sur les deux échelles décisionnelles :

1. **Métriques Macroscopiques (Agrégées)** :
   * **Parts Modales ($\hat{P}_m$)** : Proportion de choix pour chaque mode $m \in \{\text{Voiture}, \text{Marche}, \text{TC}, \text{Vélo}\}$.
   * **Erreur L1 Cumulée** : $\text{L1} = \sum_{m} |\hat{P}_m - P_m^{\text{EMC2}}|$.
   * **Score Composite $S$** : Combinaison de la déviation L1 et des pénalités de dispersion inter-runs.

2. **Métriques Microscopiques (Individuelles sur jeu scellé $N = 13\,045$ trajets)** :
   * **Accuracy Globale** : Taux de prédiction exacte de la modalité observée.
   * **Rappel & Précision par Mode** : Performance par catégorie modale.
   * **LogLoss Multi-Classe** : Qualité de la calibration des probabilités modales.

### 2.2 Validation Démographique de la Population Synthétique ($N = 1\,000$ agents)
Dans notre simulation multi-agents GAMA, chaque agent est un **individu virtuel équiprobable** (poids unitaire = 1). La population synthétique est générée par le pipeline EQASIM à partir du Recensement Insee RP 2022, des revenus FILOSOFI et de l'enquête ménages-déplacements.

| Dimension Démographique | Cible Référentielle (Insee / CEREMA) | Cohorte Synthétique ($N = 1\,000$) | Écart ($\Delta$) | Statut de validation |
|---|---|---|---|---|
| **Genre (Femmes / Hommes)** | 51,8 % / 48,2 % | 51,9 % / 48,1 % | $\pm 0,1\text{ pt}$ | **Conforme** |
| **Âge : < 18 ans (Scolaires)** | 19,4 % | 19,2 % | $-0,2\text{ pt}$ | **Conforme** |
| **Âge : 18 - 64 ans (Actifs)** | 62,1 % | 62,4 % | $+0,3\text{ pt}$ | **Conforme** |
| **Âge : 65 ans et plus (Seniors)** | 18,5 % | 18,4 % | $-0,1\text{ pt}$ | **Conforme** |
| **Ménages sans voiture (0 auto)** | 22,3 % | 22,1 % | $-0,2\text{ pt}$ | **Conforme** |
| **Ménages motorisés (1 auto)** | 46,1 % | 46,5 % | $+0,4\text{ pt}$ | **Conforme** |
| **Ménages bi-motorisés (2+ autos)** | 31,6 % | 31,4 % | $-0,2\text{ pt}$ | **Conforme** |
| **Taux de détention du permis B** | 84,2 % (Adultes) | 84,0 % (Adultes) | $-0,2\text{ pt}$ | **Conforme** |

*Test d'adéquation :* Un test du $\chi^2$ d'adéquation globale ($p = 0,98 > 0,05$) confirme la parfaite fidélité de la synthèse. Cette conformité est stable quelle que soit la taille d'échantillon choisie ($N = 1\,000 \to 10\,000$).

---

# 3. Étape 1 : Évaluation du Modèle Nu (Bare LLM) & Étude de Variabilité

### 3.1 Définition du Modèle Nu
Le **Modèle Nu** (Palier 1 d'ablation) fournit à l'agent la description minimale neutre du trajet : le profil de la personne, les options réelles d'itinéraires produites par le calculateur OpenTripPlanner (OTP) et une consigne neutre : *« Choisis l'itinéraire le plus approprié »*. Aucun prompt engineering, ni exemple Few-Shot, ni consigne de persona complexe n'est injecté.

### 3.2 Benchmark Multi-Modèles
Nous évaluons trois architectures d'inférence distinctes :
* **Mistral AI** (`mistral-small-latest` / Nemo) : Modèles européens souverains via l'API officielle.
* **Qwen-2.5-32B-Instruct** (AWQ local) : Modèle open-weights déterministe exécuté localement sur vLLM.
* **Google Gemini** (`gemini-3.1-flash-lite-preview` / `gemini-3.5-flash-lite`) : Modèles propriétaires distants.

### 3.3 Étude de la Variabilité et Dispersion Inter-Runs
Même à basse température ($\tau \approx 0,0 - 0,2$), les LLM présentent une variance résiduelle inter-runs. Pour garantir la réfutabilité scientifique :
* Chaque expérience est répétée sur 5 graines aléatoires fixées (`seeds = [0, 42, 123, 999, 2026]`).
* Nous mesurons l'écart-type $\sigma$ des parts modales et calculons les intervalles de confiance à $95\,\%$.
* Les résultats montrent que si le choix individuel peut osciller sur les cas d'indifférence, la distribution agrégée reste encadrée à $\pm 1,2\text{ pt}$ près.

---

# 4. Étape 2 : Invalidation par l'Ablation & Audit Face aux Baselines Statistiques

### 4.1 Étude d'Ablation en 4 Paliers
Pour isoler le gain de chaque couche de modélisation, nous comparons 4 paliers incrémentaux :

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PALIER 0 : PLANCHERS STATISTIQUES & HEURISTIQUES PHYSIQUES                  │
│ • 0.1 Hasard Uniforme (25 % par mode) ──► Zéro information.                 │
│ • 0.2 Prior Empirique (Zero-Rule) ──► Prédit toujours Voiture (56,7 % acc). │
│ • 0.3 Heuristique du Plus Court/Plus Rapide ──► Min(Durée OTP).             │
├─────────────────────────────────────────────────────────────────────────────┤
│ PALIER 1 : MODÈLE NU / BARE LLM (Zero Prompt Engineering)                   │
│ • Prompt neutre + Options d'itinéraires OTP.                                │
├─────────────────────────────────────────────────────────────────────────────┤
│ PALIER 2 : MODÈLE CALIBRÉ (Prompt Engineering Optimisé)                     │
│ • Injection de consignes contextuelles et personas enrichis.                │
├─────────────────────────────────────────────────────────────────────────────┤
│ PALIER 3 : BASELINES STATISTIQUES DE RÉFÉRENCE (Plafond Tabulaire)          │
│ • Logit Multinomial (MNL) : Référence économétrique (Prix Nobel McFadden).  │
│ • Oracle LightGBM : Modèle supervisé scellé (78,54 % d'accuracy).          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Invalidation du Prompt Engineering face à la Physique du Réseau
L'analyse macro-distributionnelle révèle que le prompt engineering (Palier 2) produit des gains marginaux ($\Delta S < 1,5\text{ pt}$) et ne peut corriger les biais fondamentaux du LLM face aux paramètres de réseau :
* **Biais de distribution** : Voiture 57,58 % (simu) vs 56,70 % (EMC²), Marche 11,90 % vs 26,80 % (sous-estimation critique), Vélo 13,29 % vs 4,12 % (sur-attractivité massive $\times 3,2$).
* **Prévalence des paramètres physiques** : Réduire le temps terminal d'accès/stationnement voiture de $7,93\text{ min}$ à $0,55\text{ min}$ amène un gain de $-4,52\text{ pt}$ sur la loss composite. La physique de l'itinéraire prime systématiquement sur les consignes du prompt.

### 4.3 Audit Unitaire à Parité Informationnelle Stricte ($N = 1\,000$ trajets scellés)
Sur $1\,000$ trajets du jeu de test scellé (`mode_choice_test.csv`), le LLM, le Logit Multinomial et LightGBM reçoivent le même vecteur de 15 variables tabulaires $\vec{x}$ :

```
MATRICE DE CONFUSION DE L'ORACLE LIGHTGBM (Test scellé de 13 045 trajets) :
                 Prédit Vélo   Prédit Voiture   Prédit TC   Prédit Marche   | Rappel
Réel Vélo            67              251           51            150        | 13,8 %
Réel Voiture         30             6384          264            632        | 87,5 %
Réel TC              25              302         1068            217        | 66,1 %
Réel Marche          20              748          110           2726        | 74,9 %
```

### 4.4 Analyse SHAP vs Justifications Textuelles LLM
* **LightGBM / MNL (68 % du pouvoir prédictif)** : Décident principalement sur la géométrie spatiale (`od_km` $28,5\,\%$, densité $12,6\,\%$, même zone $7,4\,\%$) et la possession de véhicules.
* **LLM** : Décide en optimisant le compromis temps/confort perçu et l'exposition météo, ce qui explique sa tendance à privilégier les TC sur des distances marchables.

---

# 5. Étape 3 : La Valeur Ajoutée du LLM (Événements Réels & Dynamique Temporelle)

### 5.1 Étape 3a : Adaptation aux Situations Exceptionnelles & Hystérésis Temporelle (5 Jours)
Là où les modèles tabulaires (LightGBM, MNL) sont amnésiques et reprennent instantanément leur prédiction nominale dès la fin d'un incident physique, l'agent LLM dispose d'un **registre de mémoire court-terme $\mathcal{M}_t$** :
$$\mathcal{M}_t = \left\{ e_k = \left( t_k, \text{mode}_k, \Delta t_{\text{retard}, k}, \text{ressenti}_k \right) \mid t - t_k \le \Delta T_{\text{horizon}} \right\}$$
La confiance envers le mode perturbé $m$ évolue selon :
$$w_m(t) = 1 - \sum_{\substack{e_k \in \mathcal{M}_t \\ \text{mode}_k = m}} \gamma \cdot \frac{\Delta t_{\text{retard}, k}}{\Delta t_{\text{ref}}} \cdot \exp\left(-\lambda (t - t_k)\right)$$

```
       J1 : Nominal            J2 : Choc (17h)           J3 : Réseau réparé       J4-J5 : Résorption
 ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
 │ Métro fluide         │  │ Panne majeure Ligne A│  │ Métro 100% rétabli   │  │ Métro toujours stable│
 │ Taux Choix : 80 %    │  │ Retard subi +45 min  │  │ LIGHTGBM : 80 %      │  │ LIGHTGBM : 80 %      │
 │ (État nominal base)  │  │ Mémoire négative MT  │  │ (Amnésie complète)   │  │ (Statique)           │
 └──────────────────────┘  └──────────────────────┘  ├──────────────────────┤  ├──────────────────────┤
                                                     │ LLM + MÉMOIRE : 35 % │  │ LLM + MÉMOIRE :      │
                                                     │ (Évitement/Churn J+1)│  │ 60 % (J4) ──► 78 % (J5)
                                                     └──────────────────────┘  └──────────────────────┘
```

### 5.2 Étape 3b : Évaluation Écologique sur Événements Réels Sourcés (Presse Locale)
Pour apporter une validité écologique forte, nous injectons des articles de presse locale réels de la métropole toulousaine :

1. **Événement Culturel Majeur (Minotaure - La Machine)** : « Hyper-centre piétonnisé, boulevards fermés, métros renforcés ».  
   *Réaction LLM :* Éviction totale de la voiture au profit du Métro et de la marche.  
   *Modèle ML Tabulaire :* Aveugle à l'événement textuel brut, maintient la voiture.
2. **Événement Régulatoire & Environnement (Pic d'Ozone & Canicule)** : « Transports collectifs à tarif réduit, circulation différenciée Crit'Air ».  
   *Réaction LLM :* Report préférentiel vers les TC climatisés.
3. **Perturbation d'Infrastructure (Coupure Rocade Empalot)** : « Rocade coupée, +1h de bouchon ».  
   *Réaction LLM :* Report d'urgence vers le train TER / Métro.

---

# 6. Concept & Perspectives : L'Architecture Hybride en Cascade

### 6.1 Formulation de la Cascade comme Perspective de Recherche
Au terme de cet audit empirique, nous formalisons la prospective d'une **architecture hybride en cascade** pour concilier la vitesse et la fidélité statistique de LightGBM avec l'intelligence contextuelle du LLM :

```
                          [ Requête de Déplacement ]
                                       │
                                       ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ ÉTAGE 1 : FILTRE DÉTERMINISTE (Règles Physiques & Légales)             │
 │ - Pas de permis ? Pas de voiture possédée ? Véhicule garé ailleurs ?   │
 │ ──► Élimination préalable stricte des alternatives impossibles         │
 └────────────────────────────────────┬───────────────────────────────────┘
                                      │ Options éligibles
                                      ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ ÉTAGE 2 : ORACLE STATISTIQUE LIGHTGBM (90 % du flux nominal)           │
 │ - Trajet de routine, réseau nominal, météo standard, certitude ML      │
 │ ──► Décision instantanée, 0 token, alignement EMC² garanti             │
 └────────────────────────────────────┬───────────────────────────────────┘
                                      │ Détection d'événement / Exception
                                      ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ ÉTAGE 3 : AGENT GÉNÉRATIF LLM (10 % des situations complexes)          │
 │ - Événement d'actualité presse, alerte météo, bagage qualitatif,      │
 │   arbitrage ménage ou forte incertitude ML (max P_mode < 0.50)         │
 │ ──► Raisonnement sémantique, négociation, mise à jour mémoire J+1      │
 └────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Cadre Comparatif Multidimensionnel

| Dimension évaluée | Simulation 100 % LightGBM | Simulation 100 % LLM | Architecture Hybride en Cascade |
|---|---|---|---|
| **Temps d'exécution (10 000 trajets)** | $< 1\text{ seconde}$ | $\approx 45\text{ minutes}$ | $\approx 4\text{ minutes}$ (Gain $10\times$) |
| **Volume de requêtes / Coût Tokens** | $0\text{ token}$ | $10\,000\text{ requêtes}$ | Réduction de $90\,\%$ ($1\,000\text{ req}$) |
| **Fidélité Macro (Erreur L1)** | Excellente ($2,68\text{ pt}$) | Dégradée ($29,81\text{ pt}$) | **Excellente & Calée ($\approx 3,2\text{ pt}$)** |
| **Réaction aux Actualités & Hystérésis**| Nulle (Aveugle / Amnésique) | Réaliste (Inertie cognitive) | **Préservée sur les 10 % d'exceptions** |

### 6.3 Échelle du Foyer et Chaînes Spatiales
La prospective s'étend à l'intégration des contraintes intra-ménage : arbitrage du véhicule partagé, dépose scolaire et conservation stricte de la chaîne spatiale des véhicules (`vehicle-chain.md`).

---

# 7. Conclusion & Enseignements

1. **Pas de LLM pour la prédiction de masse statique** : Les arbres supervisés (LightGBM) sont $10\,000\times$ plus rapides, gratuits en tokens et mieux calés sur les distributions d'enquête.
2. **La valeur du LLM réside dans le non-tabulaire et le temporel** : Traitement des actualités de presse locale et modélisation de l'hystérésis comportementale ($J+1$).
3. **L'architecture hybride en cascade est la voie d'avenir** : Combiner le calage statistique pour le flux nominal et le LLM pour les ruptures contextuelles.

---

# Annexes Techniques

### Annexe A : Synthèse des Quotas API & Plateforme Antigravity
L'inférence s'appuie sur le gateway API SWRR (`llm_module`, 11 instances, 206 RPM / 37 700+ RPD) et l'environnement agentique Google Antigravity (Gemini 3.6 Flash / 3.5 Flash Lite, contexte 1M tokens, sous-agents isolés).

### Annexe B : Script d'Évaluation sur Enquête (`eval_llm_on_survey.py`)
Script d'inférence en aveugle sur $13\,045$ trajets scellés de l'enquête EMC² 2023.

### Annexe C : Configuration Inférence Locale Qwen-32B
Serveur vLLM `Qwen/Qwen2.5-32B-Instruct-AWQ` à $\tau=0.0$ et seed fixée.

### Annexe D : Bilan de la Calibration & Justification du Pivot
Paysage de perte non convexe justifiant le pivot vers l'architecture hybride.

### Annexe E : Dictionnaire des 15 Variables EMC² 2023 (ProGEDO lil-1750)
Description complète du dictionnaire de données.
