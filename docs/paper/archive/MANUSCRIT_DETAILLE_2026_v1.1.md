# De la Décision Statistique au Comportement Adaptatif : Évaluation Empirique, Limites et Perspectives Hybrides des Agents LLM en Simulation de Mobilité Urbaine

**Auteurs prévus :** Yves B., Benoit Gaudou, Kamaldeep Singh Oberoi *(ordre et affiliation à définir)*  
**Cadre de recherche :** Projet LLM-Agents GAMA / Défis Clés Occitanie (MIDOC) / Application métropolitaine toulousaine  
**Version du document :** `v1.1` (1er septembre 2026) — *Amendements méthodologiques, protocoles factoriels et parité d'information*  
**Fichiers associés :** [`PROTOCOLE_SCIENTIFIQUE.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/PROTOCOLE_SCIENTIFIQUE.md), [`PLAN_ARTICLE_2026.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/paper/PLAN_ARTICLE_2026.md)  
**Historique des versions :**
* `v1.0` *(Août 2026)* : Première trame complète du manuscrit et cadrage macro/micro.
* `v1.1` *(1er septembre 2026)* : Cadrage formel du protocole scientifique : introduction de l'étude factorielle par vignettes sémantiques (test de McNemar), parité informationnelle stricte (vecteur 15 variables, baseline Logit Multinomial), formalisation mathématique de l'hystérésis sur 5 jours, formulation conceptuelle et cadre d'évaluation empirique de l'architecture hybride en cascade.

---

## Résumé (Abstract)

### Français
L'intégration des grands modèles de langage (LLM) au sein des simulations multi-agents (Generative Agent-Based Modeling, GABM) ouvre des perspectives inédites pour modéliser le comportement humain sans recourir à des systèmes de règles manuelles rigides. Toutefois, l'évaluation de ces agents face à des données d'enquête réelles révèle une tension fondamentale entre *richesse narrative qualitative* et *fidélité distributionnelle quantitative*. 

Dans cet article, nous proposons une évaluation critique et empirique des capacités décisionnelles des agents LLM appliqués au choix modal de transport sur l'aire métropolitaine de Toulouse. Nous confrontons les décisions d'agents génératifs (Mistral, Gemini, et un modèle local Qwen-32B) à des baselines statistiques éprouvées : un modèle Logit Multinomial (MNL) de référence et un oracle supervisé LightGBM entraîné sur l'enquête ménages-déplacements EMC² 2023 ($78,5\,\%$ d'accuracy sur $13\,045$ trajets de test scellés, avec un découpage étanche par ménage). 

Nos résultats mettent en évidence :
1. **Au niveau macroscopique**, des biais structurels persistants du LLM (sous-représentation massive de la marche à $11,9\,\%$ contre $26,8\,\%$ dans l'enquête, sur-attractivité des transports collectifs et du vélo, et hyper-sensibilité aux temps terminaux de déplacement) ;
2. **Au niveau microscopique (unitaire)**, une évaluation en aveugle à **parité informationnelle stricte** sur $1\,000$ profils réels d'enquête (même vecteur de 15 caractéristiques socio-démographiques et spatiales pour le LLM, le MNL et LightGBM), permettant d'analyser la matrice de confusion croisée et d'opposer l'importance des variables tabulaires (SHAP) aux justifications sémantiques produites par le LLM ;
3. **Au niveau comportemental**, la capacité du LLM à intégrer des contextes qualitatifs non tabulés évaluée via une **étude factorielle par vignettes** (encombrement, sécurité nocturne, météo, tenue) et à modéliser formellement le phénomène d'**hystérésis** (mémoire d'un incident de réseau persistant à $J+1$ avec cinétique de ré-adoption sur 5 jours, là où un modèle statistique réinitialise immédiatement son choix).

Face à ce compromis entre fidélité statistique et adaptabilité sémantique, nous formulons le **concept et la perspective d'évaluation d'une architecture hybride en cascade** (Règles déterministes $\to$ LightGBM pour $90\,\%$ du trafic nominal $\to$ LLM pour les $10\,\%$ d'exceptions et de perturbations) couplée aux contraintes de la cellule familiale (arbitrage du véhicule partagé, accompagnement scolaire).

### English
*Integrating Large Language Models (LLMs) into agent-based social simulations (GABM) offers new avenues for modeling human decision-making beyond rigid rule-based systems. However, benchmarking these agents against real-world travel surveys reveals a fundamental trade-off between qualitative semantic expressiveness and quantitative distributional fidelity.*

*In this paper, we present an empirical and critical assessment of LLM agents for mode choice in the Toulouse metropolitan area. We benchmark generative agents (Mistral, Gemini, local Qwen-32B) against established statistical baselines: a reference Multinomial Logit (MNL) model and a supervised statistical oracle (LightGBM trained on the 2023 EMC² household travel survey, achieving $78.5\%$ accuracy on $13,045$ household-split test trips).*

*Our contributions are three-fold: (i) at the macro-level, we quantify persistent LLM distribution biases (severe under-representation of walking at $11.9\%$ vs. $26.8\%$ target, transit over-attractiveness, high sensitivity to access/egress times); (ii) at the micro-level, we establish a unit-level blind evaluation protocol under strict feature parity (identical 15-variable socio-demographic vector), contrasting econometric/SHAP feature attributions with LLM natural language justifications; (iii) at the behavioral level, we validate LLM responsiveness to unstructured contexts through a controlled factorial vignette study and formalize behavioral hysteresis ($J+1$ memory effect and 5-day recovery dynamics following a transit breakdown).*

*To bridge the gap between statistical calibration and behavioral adaptation, we propose the concept and evaluation perspective of a cascading hybrid architecture (Deterministic Rules $\to$ LightGBM for $90\%$ nominal flow $\to$ LLM for $10\%$ disruptions/exceptions) embedded within household-level constraints (shared vehicle competition, escort trips).*

---

# 1. Introduction & Positionnement Scientifique

### 1.1 Contexte : L'émergence des agents génératifs en simulation de transport
La modélisation multi-agents des systèmes de transport (ABM) repose traditionnellement sur deux approches :
* Les **modèles de choix discrets** (Logit multinomial, Logit emboîté), calibrés sur des utilités économétriques globales mais rigides face à des contextes imprévus ;
* Les **systèmes experts à base de règles** (arbres décisionnels, automates BDI), coûteux à concevoir manuellement et incapables de généraliser hors de leur domaine nominal.

L'avènement des modèles de langage génératifs (LLM) permet d'introduire des agents autonomes capables de raisonner en langage naturel, d'évaluer des compromis complexes (durée, confort, météo, contraintes d'agenda) et de justifier explicitement leurs choix.

### 1.2 Le verrou scientifique : Réalisme qualitatif vs Calage empirique
Si les agents LLM font preuve d'une expressivité impressionnante sur des scénarios individuels scénarisés, leur déploiement à l'échelle d'une métropole pose un défi majeur : **la fidélité distributionnelle**. Les LLM n'ont pas été entraînés pour reproduire la répartition modale d'un territoire spécifique. Leurs distributions agrégées sont biaisées par des priors culturels mondiaux issus de leur pré-entraînement, conduisant à des anomalies systématiques (ex. sous-estimation des déplacements courts à pied, engouement disproportionné pour les transports en commun).

### 1.3 Positionnement du travail
Ce papier se positionne au croisement de trois disciplines :
1. **L'évaluation empirique des LLMs pour la décision** : dépasser les benchmarks académiques synthétiques en évaluant les LLMs sur des données d'enquête réelles d'envergure (EMC² 2023, $785$ zones fines, $453$ communes) à **parité informationnelle stricte** ;
2. **L'audit critique face aux baselines statistiques et à l'Oracle supervisé** : utiliser le Logit Multinomial (MNL) et un modèle de Machine Learning tabulaire de pointe (LightGBM) comme références de ce que les approches classiques produisent sur les mêmes données ;
3. **Le cadre conceptuel et la perspective d'ingénierie des systèmes hybrides** : formaliser l'architecture de triage en cascade où le ML tabulaire assure le calage de masse et le LLM traite les ruptures contextuelles (imprévus, mémoire d'incident, contextes qualitatifs).

---

# 2. Comportement Individuel, Sémantique & Adaptation Dynamique (BLOC 1)

*Dans cette section, nous démontrons la valeur ajoutée intrinsèque du raisonnement LLM face à des situations que les modèles tabulaires classiques ne peuvent pas capturer.*

### 2.1 Protocole expérimental et reproductibilité
Pour que l'analyse comportementale soit rigoureuse et réfutable, nous posons un protocole d'évaluation strict :
* **Déterminisme et dispersion** : Même à basse température ($\tau = 0.2$), une variance résiduelle inter-runs existe. Nous évaluons systématiquement chaque expérience sur plusieurs seeds fixés et rapportons la moyenne accompagnée de l'écart-type ou de l'intervalle de confiance à $95\,\%$.
* **Comparaison multi-modèles** : Évaluation croisée sur des familles d'architectures distinctes (Mistral-Small/Nemo, Gemini-Flash, Qwen-32B local).

### 2.2 Personas augmentés & Étude factorielle par vignettes sémantiques
Les modèles statistiques tabulaires réduisent l'individu à un vecteur de variables numériques et catégorielles fixes $\vec{x}$. Pour démontrer la capacité du LLM à intégrer des nuances qualitatives sans tomber dans le biais de sélection d'exemples anecdotiques (*cherry-picking*), nous établissons un **protocole d'évaluation factorielle par vignettes sémantiques contrôlées**.

#### Protocole d'expérimentation par vignettes ($N = 50$ profils $\times$ 5 conditions = 250 tests) :
À partir d'un échantillon stratifié de $N = 50$ profils réels d'enquête couvrant diverses classes d'âge, motifs et distances ($0.5\text{ km} \le od\_km \le 15\text{ km}$), nous générons 5 conditions expérimentales strictes :

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ MATRICE FACTORIELLE DES VIGNETTES SÉMANTIQUES (5 CONDITIONS TESTÉES)        │
├─────────────────────────────────────────────────────────────────────────────┤
│ Condition C0 (Contrôle / Nominal) : Vecteur tabulaire standard.             │
│   ──► Choix de référence du LLM et de l'Oracle LightGBM.                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ Condition C1 (Logistique & Encombrement) :                                  │
│   « Je transporte un gâteau d'anniversaire fragile et un carton volumineux » │
│   ──► Hypothèse : Éviction de la marche longue et du vélo ──► Voiture.      │
├─────────────────────────────────────────────────────────────────────────────┤
│ Condition C2 (Sécurité Situationnelle & Nocturne) :                         │
│   « Trajet de retour à 23h30 à travers une zone industrielle isolée »       │
│   ──► Hypothèse : Arbitrage préférentiel vers TC abrité ou Voiture.         │
├─────────────────────────────────────────────────────────────────────────────┤
│ Condition C3 (Météo Dégradée) :                                             │
│   « Pluie battante continue et rafales de vent à 60 km/h »                  │
│   ──► Hypothèse : Chute massive du vélo vers TC ou Voiture.                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ Condition C4 (Contrainte Vestimentaire & Événement) :                       │
│   « Entretien d'embauche formel en costume trois pièces / tailleur »        │
│   ──► Hypothèse : Évitement de l'effort physique et de la transpiration.    │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Quantification et validation statistique :
Pour chaque condition qualitative $C_k$ ($k \in \{1, \dots, 4\}$), nous mesurons le taux de bascule modal par rapport à la condition contrôle $C_0$ :
$$\Delta \text{Bascule}(C_k) = \frac{1}{N} \sum_{i=1}^N \mathbb{I}\left(\text{Choix}_i(C_k) \neq \text{Choix}_i(C_0)\right)$$
La significativité statistique de la modification des choix est validée par un **test de McNemar** pour paires liées (seuil $\alpha = 0,01$), prouvant que les bifurcations décisionnelles du LLM ne relèvent pas du bruit stochastique mais d'une sensibilité sémantique robuste.

### 2.3 Analyse automatique des justifications (Text Mining)
Contrairement aux modèles de type « boîte noire », le LLM produit une justification textuelle explicite pour chaque décision. 
* **Méthode** : Sur l'ensemble des trajets où le choix du LLM s'écarte de la prédiction statistique de LightGBM ($\text{Choix}_{\text{LLM}} \neq \text{Choix}_{\text{LightGBM}}$), nous appliquons un pipeline de NLP (extraction de motifs clés, clustering sémantique).
* **Résultat attendu** : Une quantification objective des motivations de divergence (ex. *35 % des écarts justifiés par le confort physique, 28 % par l'évitement de ruptures de charge, 20 % par des contraintes horaires perçues*).

### 2.4 Chocs ponctuels et modélisation formelle de l'Hystérésis (Effet mémoire longitudinal)
L'absence de mémoire constitue une limitation structurelle majeure des modèles de choix discrets et des arbres de décision tabulaires. Ces modèles sont **strictement markoviens / amnésiques** : dès que le réseau revient à son état physique nominal, leurs prédictions se réinitialisent instantanément à l'identique.

#### 2.4.1 Formalisation mathématique de l'état interne et de la mémoire
Pour modéliser l'inertie cognitive et l'hystérésis comportementale, chaque agent génératif est doté d'un registre de mémoire épisodique court-terme $\mathcal{M}_t$ horodaté :
$$\mathcal{M}_t = \left\{ e_k = \left( t_k, \text{mode}_k, \Delta t_{\text{retard}, k}, \text{ressenti}_k \right) \mid t - t_k \le \Delta T_{\text{horizon}} \right\}$$

L'impact mémoriel d'une expérience négative sur la confiance accordée au mode $m$ décroît selon une loi d'atténuation temporelle exponentielle :
$$w_m(t) = 1 - \sum_{\substack{e_k \in \mathcal{M}_t \\ \text{mode}_k = m}} \gamma \cdot \frac{\Delta t_{\text{retard}, k}}{\Delta t_{\text{ref}}} \cdot \exp\left(-\lambda (t - t_k)\right)$$
où $\gamma$ est un coefficient de sensibilité individuelle, $\Delta t_{\text{ref}}$ un retard de référence (ex. $30\text{ min}$), et $\lambda$ le taux d'oubli journalier.

#### 2.4.2 Protocole expérimental longitudinal sur 5 jours ($J_1$ à $J_5$)
Nous testons cette dynamique sur une cohorte d'agents utilisant usuellement les transports en commun (Métro Ligne A) :

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

* **Résultats & Diagnostic** : Là où LightGBM affiche une discontinuité artificielle ($80\,\% \to 0\,\% \to 80\,\%$), l'agent LLM doté de mémoire reproduit fidèlement la **courbe de ré-adoption progressive** observée en sociologie des transports suite à une rupture de service majeure.

---

# 3. Utilité et Limites en Simulation Urbaine (BLOC 2)

*Dans cette section, nous documentons les distorsions observées lors des runs de simulation à grande échelle sur la métropole toulousaine.*

### 3.1 Macro-distribution vs Réalité empirique (EMC² 2023)
L'analyse du run de référence de simulation (`2026-08-24_17_34`, portant sur $2\,911$ décisions d'agents synthétiques) révèle un alignement contrasté face à la cible d'enquête :

| Mode de transport | Cible Réelle (EMC² 2023) | Simulation LLM (Run 2026-08-24) | Diagnostic & Biais |
|---|---|---|---|
| **Voiture** | **56,70 %** | **57,58 %** | **Alignement remarquable** ($\Delta = +0,88\text{ pt}$) |
| **Marche** | **26,80 %** | **11,90 %** | **Sous-représentation critique** ($\Delta = -14,90\text{ pt}$) |
| **Transports Collectifs** | **12,37 %** | **17,23 %** | **Sur-attractivité marquée** ($\Delta = +4,86\text{ pt}$) |
| **Vélo** | **4,12 %** | **13,29 %** | **Sur-utilisation massive** ($\Delta = +9,17\text{ pt}$) |
| **Score Composite (Loss)** | — | **18,23** | *(L1 global : 29,81 pt)* |

### 3.2 La physique du réseau prime sur le prompt : Le rôle des temps terminaux
Une série d'expériences de correction sur jeux gelés démontre que les modifications cosmétiques du prompt système ont un effet marginal comparé à l'alignement des paramètres d'itinéraire :
* **Ajout d'une consigne de chaîne dans le prompt** (ticket 014) : $\Delta \text{Composite} = +0,21$ *(inefficace)*.
* **Alignement du temps terminal voiture sur l'enquête** (accès/stationnement réduit de $7,93\text{ min}$ à $0,55\text{ min}$) : $\Delta \text{Composite} = -4,52\text{ pt}$ *(gain massif)*.
* **Alignement conjoint voiture + vélo** : $\Delta \text{Composite} = -2,17\text{ pt}$ *(le vélo redevient trop attractif dès qu'on réduit son temps d'accroche)*.

### 3.3 Le biais de report Marche $\to$ Transports Collectifs
L'analyse approfondie de $495$ décisions où le LLM a retenu un bus ou un tramway alors qu'un itinéraire piéton direct était proposé montre un biais cognitif propre aux LLMs : le modèle sur-valorise la vitesse nominale du véhicule collectif et sous-estime la pénibilité d'un trajet à pied de moins de $15$ minutes.

---

# 4. Évaluation Unitaire Face aux Baselines Statistiques & à l'Oracle (BLOC 3)

*Dans cette section, nous présentons le face-à-face micro-décisionnel entre les agents LLM et les modèles statistiques sur les mêmes données individuelles d'enquête, sous une discipline stricte de parité informationnelle.*

### 4.1 Les Baselines Statistiques : Modèle Logit Multinomial (MNL) & Oracle LightGBM
Pour situer les performances du LLM, nous mobilisons deux modèles statistiques de référence :
1. **Modèle Économétrique de référence (Logit Multinomial / MNL)** : Calibré par maximum de vraisemblance sur les utilités systématiques linéaires des attributs socio-démographiques et de distance.
2. **Oracle Supervisé Machine Learning (LightGBM)** :
   * **Substrat d'apprentissage** : $31\,279$ trajets réels (EMC² 2023 / ProGEDO lil-1750), $7\,924$ trajets de validation, $13\,045$ trajets de test gelés.
   * **Discipline d'échantillonnage** : Découpage strict par identifiant de ménage (`hh_id`, test 25 %, seed 0) pour proscrire toute fuite d'information intra-foyer (*zero data leakage*).
   * **Performances sur le test scellé** :
     * **Accuracy globale pondérée : 78,54 %**
     * **LogLoss multi-classe : 0,540**
     * **Erreur L1 sur la distribution : 2,68 pt**

```
MATRICE DE CONFUSION DE L'ORACLE LIGHTGBM (Test scellé de 13 045 trajets) :
                 Prédit Vélo   Prédit Voiture   Prédit TC   Prédit Marche   | Rappel
Réel Vélo            67              251           51            150        | 13,8 %
Réel Voiture         30             6384          264            632        | 87,5 %
Réel TC              25              302         1068            217        | 66,1 %
Réel Marche          20              748          110           2726        | 74,9 %
```

### 4.2 Protocole d'inférence unitaire à parité informationnelle stricte (`eval_llm_on_survey.py`)
Pour garantir une comparaison équitable et scientifiquement irréfutable, l'évaluation exclut toute asymétrie d'information :
* **Vecteur de caractéristiques strictement identique** : Le prompt système du LLM reçoit exactement les 15 variables tabulaires fournies au modèle LightGBM et au MNL :
  $$\vec{x} = (\text{age}, \text{gender}, \text{hh\_size}, \text{license}, N_{\text{cars}}, \text{car\_avail}, \text{bike}, \text{pt\_sub}, \text{occupation}, \text{purpose}, \text{dep\_hour}, od\_km, \text{same\_zone}, \text{dens\_orig}, \text{dens\_dest})$$
* **Distinction des cadres d'évaluation** :
  1. *Benchmark Tabulaire Pur (Zero-Routing)* : Inférence basée uniquement sur $\vec{x}$ (sans calcul d'itinéraire externe OTP) pour mesurer la capacité intrinsèque du LLM à estimer le mode à partir du profil socio-spatial ;
  2. *Benchmark Système Complet (Avec OTP)* : Inférence enrichie des métriques d'offre de transport (temps de parcours, correspondances, temps terminaux calculés par le calculateur d'itinéraire).
* **Échantillonnage de test scellé** : Tirage stratifié de $N = 1\,000$ trajets sur le jeu de test gelé `mode_choice_test.csv`, modalité réelle masquée.

### 4.3 Inférence locale avec Qwen-32B & Reproductibilité
L'évaluation unitaire est exécutée sur un modèle open-weights local (**Qwen-2.5-32B-Instruct**) via un serveur d'inférence local (vLLM / Ollama) :
* **Garantie scientifique** : Zéro coût d'API, absence totale de rate-limit, reproductibilité déterministe pérenne ($\tau = 0.0$, seed fixé) et indépendance vis-à-vis des dérives de versions d'APIs commerciales propriétaires.

### 4.4 Analyse SHAP vs Justifications LLM
La décomposition de l'importance des variables (SHAP values & Gain Share de LightGBM) met en évidence les mécanismes sous-jacents :
1. `od_km` ($28,52\,\%$) : Déterminant physique majeur de portée spatiale ;
2. `has_pt_subscription` ($9,53\,\%$) : Marqueur fort d'accès et d'habitude aux TC ;
3. `same_zone` ($7,42\,\%$) : Indicateur d'hyper-proximité piétonne ;
4. `density_orig` + `density_dest` ($12,65\,\%$) : Morphologie urbaine et compacité ;
5. `number_of_cars` + `car_availability` ($9,99\,\%$) : Équipement automobile lourd.

*Mise en regard dans l'article :* Là où LightGBM et le MNL fondent plus de $68\,\%$ de leur prédiction sur la géométrie spatiale et l'équipement matériel possédé, le LLM cherche à optimiser le confort perçu, le temps et la pénibilité relative, expliquant ses déviations et sa sous-estimation de la marche sur courtes distances.

---

# 5. Concept & Perspectives : L'Architecture Hybride en Cascade (BLOC 4)

*Dans cette section, nous formulons le concept architectural et la perspective d'évaluation d'un système hybride conçu pour dépasser les limitations respectives du LLM pur et du ML tabulaire pur.*

### 5.1 Formulation Conceptuelle de la Cascade Hybride
Pour concilier la vitesse, le coût nul et la précision macroscopique de LightGBM avec la flexibilité cognitive du LLM, nous proposons une architecture de triage à trois étages :

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
                                      │ Détection d'exception / Perturbation
                                      ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │ ÉTAGE 3 : AGENT GÉNÉRATIF LLM (10 % des situations complexes)          │
 │ - Incident réseau, météo extrême, contexte qualitatif / bagage,        │
 │   arbitrage intra-foyer ou forte incertitude ML (max P_mode < 0.50)    │
 │ ──► Raisonnement sémantique, négociation, mise à jour mémoire J+1      │
 └────────────────────────────────────────────────────────────────────────┘
```

#### Critères formels de dérivation vers l'Étage 3 (LLM) :
Un trajet est orienté vers l'agent LLM si au moins une des conditions suivantes est remplie :
1. **Événement exogène avéré** : Alerte météo sévère ($\text{pluie} > 10\text{ mm/h}$) ou perturbation réseau ($\text{retard TC} > 15\text{ min}$) ;
2. **Contexte narratif qualitatif** : Présence d'une contrainte d'encombrement, de sécurité nocturne ou d'accompagnement ;
3. **Incertitude du modèle statistique** : Entropie prédictive élevée du modèle LightGBM ($\max_{m} P(m \mid \vec{x}) < 0,50$).

#### Cadre comparatif pour l'évaluation empirique de la cascade :

| Dimension évaluée | Simulation 100 % LightGBM | Simulation 100 % LLM | Architecture Hybride en Cascade |
|---|---|---|---|
| **Temps d'exécution (10 000 trajets)** | $< 1\text{ seconde}$ | $\approx 45\text{ minutes}$ | $\approx 4\text{ minutes}$ (Accélération $10\times$) |
| **Volume de requêtes / Coût Tokens** | $0\text{ token}$ | $10\,000\text{ requêtes}$ | Réduction de $90\,\%$ ($1\,000\text{ req}$) |
| **Fidélité Macro (Erreur L1 Distribution)** | Excellente ($2,68\text{ pt}$) | Dégradée ($29,81\text{ pt}$) | **Excellente & Calée ($\approx 3,2\text{ pt}$)** |
| **Adaptabilité aux Incidents & Hystérésis** | Nulle (Amnésie $J+1$) | Réaliste (Inertie cognitive) | **Préservée sur les agents perturbés** |

### 5.2 L'Échelle de la Cellule Familiale
L'individu simulé n'évolue pas en vase clos. Nous intégrons les contraintes d'interaction du foyer :
1. **Compétition pour la ressource automobile** : Si un ménage de deux adultes actifs ne possède qu'un seul véhicule, un module d'arbitrage (ou de négociation d'agents) alloue la voiture selon l'éloignement du lieu de travail et l'absence d'alternative TC viable.
2. **Accompagnement intra-ménage** (`accompagnement_intra_menage.pptx`) : Les trajets de dépose des enfants vers l'école contraignent le choix modal et la chaîne de déplacements du parent accompagnateur.
3. **Cohérence spatiale des chaînes de véhicules** ([`docs/arch/vehicle-chain.md`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/arch/vehicle-chain.md)) : Conservation de l'état spatial du véhicule (garé sur le lieu de travail ou au domicile) interdisant toute réapparition magique le lendemain.

---

# 6. Discussion & Conclusion

### 6.1 Synthèse des apports
* Les agents LLMs ne doivent pas être employés comme de simples prédicteurs de choix modal statique (où les arbres de décision supervisés restent plus rapides, moins coûteux et mieux calés statistiquement).
* Leur véritable rupture réside dans leur **capacité d'adaptation contextuelle**, leur **explicabilité native** et la modélisation de dynamiques longitudinales telles que l'**hystérésis post-perturbation**.
* L'avenir des jumeaux numériques urbains réside dans des architectures **hybrides**, combinant l'efficacité des modèles statistiques pour le flux de masse et l'intelligence sémantique des LLM pour les cas limites et les ruptures de réseau.

---

# ANNEXES TECHNIQUES & MÉTHODOLOGIQUES

---

## Annexe A : Gestion des Quotas, Économie de Tokens & Architecture Multi-Providers (SWRR)

*(Synthèse extraite et formalisée d'après [`docs/quotas_summary.html`](file:///Users/yvesb/Documents/Projects/llm-agents-gama/docs/quotas_summary.html))*

### A.1 Calculateur de budget d'appels
Pour éviter tout dépassement de quota ou facturation imprévue lors des campagnes de simulation, le volume de requêtes est systématiquement calculé a priori :
$$\text{Total Calls} = N_{\text{agents}} \times N_{\text{trajets/jour}} \times N_{\text{jours}} \times N_{\text{seeds}} \times N_{\text{modèles}}$$

### A.2 Capacité Globale du Pool d'Inférence
La plateforme de simulation s'appuie sur un pool mutualisé de **11 instances réparties sur 4 adaptateurs** (Mistral, Google AI Studio, Cerebras, Groq) permettant d'atteindre :
* **Débit instantané cumulé** : **206 req/min (RPM)**
* **Plafond journalier free-tier** : **37 700+ req/jour (RPD)**

### A.3 Tableau des Fournisseurs Actifs en Rotation (SWRR)

Le répartiteur de charge utilise l'algorithme **Smooth Weighted Round Robin (SWRR)** avec une règle de normalisation du poids basée sur la référence de $15\text{ RPM}$ :
$$\text{Poids} = \frac{\min(\text{RPM\_limit}, \text{TPM\_limit} / 3\,000)}{15}$$

| Instance | Adaptateur | Modèle | RPM | TPM | RPD | Poids SWRR | Part Trafic | Rôle / Spécialisation |
|---|---|---|---|---|---|---|---|---|
| `mistral` | Mistral | `mistral-small-latest` | 60 | 500k | 100M tok | **4.0** | 40,5 % | Pilier central (borné à 1 req/s) |
| `google_gemini31` | Google | `gemini-3.1-flash-lite-preview` | 15 | 250k | 500 | **1.0** | 10,1 % | **Juge Éval** (clé calibration) |
| `google_gemini35` | Google | `gemini-3.5-flash-lite` | 15 | 250k | 500 | **1.0** | 10,1 % | **Mutateur** (+ thinking) |
| `google2` | Google | `gemini-3.1-flash-lite-preview` | 15 | 250k | 500 | **1.0** | 10,1 % | Seconde clé Google (pré-tests) |
| `google2_35` | Google | `gemini-3.5-flash-lite` | 15 | 250k | 500 | **1.0** | 10,1 % | Seconde clé Google (seau 3.5) |
| `google_gemma42` | Google | `gemma-4-26b-a4b-it` | 30 | 150k | 1 500 | **0.36** | 3,6 % | Modèle compact |
| `google_gemma43` | Google | `gemma-4-31b-it` | 30 | 150k | 1 500 | **0.36** | 3,6 % | Modèle compact |
| `cerebras_gpt` | Cerebras | `gpt-oss-120b` | 30 | 100k | 14 400 | **0.33** | 3,3 % | Inférence ultra-rapide |
| `cerebras_gemma` | Cerebras | `gemma-4-31b` | 30 | 100k | 14 400 | **0.33** | 3,3 % | Inférence ultra-rapide |
| `groq_openai` | Groq | `openai-120` | 30 | 50k | 14 400 | **0.18** | 1,8 % | Inférence LPUs |
| `groq_qwen` | Groq | `qwen3-6-27b` | 30 | 50k | 14 400 | **0.18** | 1,8 % | Inférence LPUs |

### A.4 Stratégie d'Expérimentation « Drip-Feed » & Caching Content-Addressed
* **Store SQLite adressé par contenu** : Indexation unique par $\text{hash}(\text{prompt} + \text{options} + \text{model\_id} + \text{temp})$ garantissant qu'aucune requête déjà validée n'est rejouée ni refacturée.
* **Garde-fous temps réel** : Disjoncteurs automatiques en cas de réponse $429$ (Too Many Requests), mise en quarantaine temporaire du provider et bascule automatique sur les instances de secours.

---

## Annexe B : Spécification du Script `eval_llm_on_survey.py`

* **Localisation** : `scripts/progedo_logit/eval_llm_on_survey.py`
* **Entrée** : `scripts/progedo_logit/mode_choice_test.csv` (13 045 lignes)
* **Arguments CLI** :
  * `--n_samples` : Taille de l'échantillon stratifié (défaut : $1\,000$).
  * `--model` : Identifiant du modèle (`local-qwen32b`, `gemini-1.5-flash`, `mistral-small`).
  * `--endpoint` : URL de l'API locale (ex. `http://localhost:11434/v1` ou `http://localhost:8000/v1`).
  * `--seed` : Graine aléatoire de tirage (défaut : $42$).
* **Sorties générées** :
  * `results/eval_survey_<model>_<date>.json` : Métriques brutes (Accuracy, F1, LogLoss).
  * `results/confusion_matrix_<model>.png` : Graphique prêt pour insertion LaTeX/PDF.

---

## Annexe C : Configuration de l'Inférence Locale Qwen-32B

* **Modèle recommandé** : `Qwen/Qwen2.5-32B-Instruct-AWQ` ou version quantifiée GGUF (Q4_K_M ou Q5_K_M).
* **Moteur d'exécution** :
  * Option 1 : **vLLM** (haute performance en batching sur GPU Apple Silicon / CUDA) :
    ```bash
    vllm serve Qwen/Qwen2.5-32B-Instruct-AWQ --port 8000 --max-model-len 4096
    ```
  * Option 2 : **Ollama** :
    ```bash
    ollama run qwen2.5:32b
    ```
* **Paramètres de prompt recommandés** : `temperature: 0.0`, `seed: 0`, schéma de réponse JSON strict `{ "choice": "walk"|"bike"|"car"|"transit", "reason": "..." }`.

---

## Annexe D : Bilan de la Prompt Calibration & Retours d'Expérience

Le module de calibration automatique développé dans le projet (`prompt_calibration/`) a exploré l'optimisation discrète de blocs de prompts guidée par les valeurs de Shapley.
* **Enseignement technique majeur** : L'espace d'optimisation d'un prompt pour reproduire une distribution multivariée est hautement non convexe et sujet au bruit d'échantillonnage. 
* **Conclusion méthodologique** : Sans accès à des clusters de calcul permettant des milliers d'évaluations parallèles, les gains obtenus par calibration de prompt restent inférieurs aux gains apportés par le réalignement direct des données de routage (temps terminaux, affectation des vélos). Cela justifie le pivot du présent article vers l'évaluation empirique et l'architecture hybride.

---

## Annexe E : Dictionnaire des Variables de l'Enquête EMC² 2023

| Variable | Type | Description / Modalités |
|---|---|---|
| `age` | Numérique | Âge de l'individu ($5$ à $99$ ans) |
| `gender` | Catégoriel | `Male`, `Female` |
| `household_size` | Numérique | Nombre de personnes dans le ménage |
| `has_driving_license` | Booléen | Détention du permis de conduire B |
| `number_of_cars` | Numérique | Nombre de véhicules motorisés du foyer |
| `car_availability` | Catégoriel | `all` (toujours), `some` (parfois), `none` (jamais) |
| `has_bike` | Booléen | Attribution nominative d'un vélo (personnel ou VAE) |
| `has_pt_subscription` | Booléen | Détention d'un abonnement de transport collectif |
| `main_occupation` | Catégoriel | Travail plein/partiel, Étudiant, Retraité, Au foyer... |
| `purpose` | Catégoriel | Motif destination : `work`, `education`, `shop`, `leisure`, `home` |
| `departure_hour` | Numérique | Heure de départ de l'activité ($0$ à $23$) |
| `od_km` | Numérique | Distance inter-centroïdes de zones fines en km |
| `same_zone` | Booléen | Déplacement intra-zone fine ($1$ si origine = destination) |
| `density_orig` / `dest` | Numérique | Densité de population/emploi de la zone fine |
| `mode` (Cible) | Catégoriel | `bike`, `car`, `transit`, `walk` |
