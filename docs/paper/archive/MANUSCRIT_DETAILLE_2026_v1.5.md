# De la Décision Statistique au Comportement Adaptatif : Évaluation Empirique, Limites et Perspectives Hybrides des Agents LLM en Simulation de Mobilité Urbaine

**Auteurs prévus :** Yves B., Benoit Gaudou, Kamaldeep Singh Oberoi *(ordre et affiliation à définir)*  
**Cadre de recherche :** Projet LLM-Agents GAMA / Défis Clés Occitanie (MIDOC) / Application métropolitaine toulousaine  
**Version du document :** `v1.5` (2 septembre 2026) — *Intégration du cadre théorique et épistémologique de Baronchelli (Science Advances 2025, PNAS 2026, stress-test 2026) et du benchmark SILICA (Bin Tareaf et al. 2026) : formalisation des trois niveaux de validation (Tier 1/2/3), explication de l'échec au Tier 3 comme plafond distributionnel, valorisation des dynamiques émergentes en Tier 2 (hystérésis/adaptation), et ajout de la Section 8 (Références Bibliographiques Structurées).*  
**Fichiers associés :** [`PROTOCOLE_SCIENTIFIQUE.md`](PROTOCOLE_SCIENTIFIQUE.md), [`PLAN_ARTICLE_2026.md`](PLAN_ARTICLE_2026.md), [`BIBLIOGRAPHIE.md`](BIBLIOGRAPHIE.md), [`references.bib`](references.bib), [`SLIDES_SEMINAIRE_2026_v1.0.html`](SLIDES_SEMINAIRE_2026_v1.0.html)  
**Historique des versions :**
* `v1.0` *(Août 2026)* : Première trame complète du manuscrit et cadrage macro/micro.
* `v1.1` *(1er septembre 2026)* : Cadrage formel du protocole scientifique (parité informationnelle, vignettes factorielles, formalisation d'hystérésis).
* `v1.2` *(1er septembre 2026)* : Intégration du Jalon 0 (validation démographique), formalisation de l'ablation en 4 paliers et évaluation écologique.
* `v1.3` *(2 septembre 2026)* : Réalignement strict de la démarche expérimentale (0: Métriques & Socle, 1: Modèle Nu & Variabilité multi-runs, 2: Invalidation Ablation & Audit Statistique, 3a: Hystérésis 5j, 3b: Presse Locale) et repositionnement de la cascade hybride en perspective.
* `v1.4` *(2 septembre 2026)* : Audit de cohérence entre le manuscrit et les mesures du dépôt — onze corrections listées en **Annexe F** (comparaison L1 à l'argmax, contrat à 21 variables, jalon 0 requalifié en contrôle de cohérence, 5 conditions presse dont paraphrase et placebo).
* `v1.5` *(2 septembre 2026)* : Ancrage épistémologique formel sur les travaux d'Andrea Baronchelli (*Science Advances* 2025, *PNAS* 2026) et le stress-test SILICA (*Bin Tareaf et al.*, 2026) : positionnement des agents LLM face aux trois tiers de validation (plafond Tier 3 vs robustesse qualitative Tier 2), intégration de la bibliographie structurée (Section 8) et formalisation de la dichotomie « proxy humain » vs « dynamique collective adaptative ».


---

## Résumé (Abstract)

### Français
L'intégration des grands modèles de langage (LLM) au sein des simulations multi-agents de mobilité urbaine ouvre des perspectives inédites pour modéliser le comportement humain sans recourir à des systèmes de règles manuelles rigides. Toutefois, l'évaluation de ces agents face à des données d'enquête réelles révèle une tension fondamentale entre *richesse narrative qualitative* et *fidélité distributionnelle quantitative*.

Dans cet article, nous proposons une évaluation empirique et critique des capacités décisionnelles des agents LLM appliqués au choix modal de transport sur l'aire métropolitaine de Toulouse. Après avoir validé la représentativité sociologique de notre population synthétique ($N = 1\,000$ agents) face au recensement Insee RP 2022 et à l'enquête EMC² 2023 (écart maximal de $0,4$ pt sur huit marges démographiques), nous déployons une démarche expérimentale rigoureuse : (0) définition des métriques macro/micro ; (1) évaluation du modèle nu (Mistral AI, Qwen-32B local, Gemini) et mesure de la variabilité inter-runs à basse température ; (2) invalidation par l'ablation montrant la prévalence des paramètres physiques de réseau sur le prompt engineering, couplée à un audit unitaire face à un oracle supervisé LightGBM ($78,5\,\%$ d'accuracy pondérée et $7,30\text{ pt}$ d'erreur L1 en argmax sur $13\,045$ trajets scellés) ; (3) démonstration de la vraie valeur ajoutée du LLM sur l'adaptation aux événements réels d'actualité (presse locale toulousaine) et la modélisation de l'hystérésis comportementale (cinétique de ré-adoption sur 5 jours avec mémoire court-terme $\mathcal{M}_t$).

En conclusion, nous formulons les perspectives d'une architecture hybride en cascade (Règles déterministes $\to$ LightGBM pour $90\,\%$ du flux nominal $\to$ LLM pour $10\,\%$ de perturbations complexes) conciliant passage à l'échelle et réactivité contextuelle.

### English
*Integrating Large Language Models (LLMs) into agent-based mobility simulations offers new avenues for modeling human decision-making beyond rigid rule-based systems. However, benchmarking these agents against real-world travel surveys reveals a fundamental trade-off between qualitative semantic expressiveness and quantitative distributional fidelity.*

*In this paper, we present an empirical assessment of LLM agents for mode choice in the Toulouse metropolitan area. After validating the demographic alignment of our synthetic population ($N = 1,000$ agents) against the Insee Census and the 2023 EMC² household travel survey (maximum deviation of $0.4$ pt across eight demographic margins), we follow a systematic experimental progression: (0) formal definition of macro and micro evaluation metrics; (1) bare LLM evaluation (Mistral AI, local Qwen-32B, Gemini) measuring multi-run variability at low temperature; (2) ablation study showing that physical network parameters outweigh prompt engineering, paired with a unit-level audit against a LightGBM statistical oracle ($78.5\%$ weighted accuracy and $7.30\text{ pt}$ argmax L1 error on $13,045$ sealed test trips); (3) demonstration of the LLM's unique value in processing unstructured local news events and capturing longitudinal behavioral hysteresis (5-day recovery kinetics via memory buffer $\mathcal{M}_t$).*

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
2. **Audit critique face aux baselines statistiques et à l'Oracle supervisé** : Utiliser le Logit Multinomial (MNL) et un modèle de Machine Learning tabulaire de pointe (LightGBM) comme références de ce que les approches classiques produisent à **parité informationnelle stricte** — le même vecteur de **21 variables** (contrat de production, `spec_version 2`). Cette parité porte sur les **entrées**, non sur l'exposition aux données : l'oracle a été entraîné sur $31\,279$ trajets d'enquête, le LLM n'en a vu aucun. Il s'agit donc d'un **plafond de référence**, et non d'un concurrent à armes égales ;
3. **Qualification du domaine d'excellence des LLM et perspectives hybrides** : Identifier la vraie rupture comportementale du LLM (actualités réelles non tabulées, dynamique d'hystérésis temporelle) et poser les perspectives d'une architecture hybride en cascade.

### 1.4 Ancrage Épistémologique : Le Stress-Test SILICA et la Dichotomie de Baronchelli
L'utilisation des modèles de langage comme substituts aux sujets humains en sciences sociales computationnelles et en simulation urbaine fait l'objet d'un examen critique croissant. Récemment, le benchmark **SILICA** (*Bin Tareaf et al., 2026*) a formalisé un cadre d'audit pour éprouver si les dynamiques observées au sein de populations d'agents LLM survivent aux variations expérimentales et reproduisent fidèlement les comportements humains. SILICA distingue **trois niveaux de validation (Tiers)** :
* **Tier 1 (Émergence en configuration standard)** : Le phénomène est observable dans les conditions nominales et arbitraires du benchmark.
* **Tier 2 (Robustesse & Stabilité qualitative)** : Le phénomène survit aux perturbations de prompts, de mémoire, de taille de groupe, de randomisation de l'ordre des options et de structures d'incitation, tout en restant qualitativement stable d'une famille de modèles à l'autre.
* **Tier 3 (Fidélité distributionnelle humaine quantitative)** : Le comportement des agents reproduit fidèlement et quantitativement les distributions statistiques et mécanismes d'interaction observés chez l'humain.

Sur 9 115 simulations systématiques menées par SILICA, la quasi-totalité des phénomènes reste confinée au Tier 1 ; seule l'émergence de conventions dans le *naming game* atteint le Tier 2, et **aucun phénomène n'atteint le Tier 3**.

Comme le formalise le Pr Andrea Baronchelli (*Baronchelli, 2026* ; *Baronchelli et al., 2025, 2026*), ce constat n'invalide pas l'intérêt des populations d'agents, mais trace une frontière épistémologique stricte entre deux questions de recherche :
1. **« Les populations d'IA peuvent-elles reproduire quantitativement les sociétés humaines ? » (LLM comme proxy humain)** $\to$ Constat sceptique : l'alignement distributionnel fin échoue face aux données d'enquête (*Plafond de Tier 3*).
2. **« Quelles dynamiques collectives et comportements adaptatifs les agents d'IA génèrent-ils par eux-mêmes ? » (LLM comme système adaptatif complexe)** $\to$ Constat positif : émergence de négociations authentiques, sensibilité aux perturbations et résilience cognitive (*Capacité de Tier 2*).

Notre article constitue un **stress-test empirique grandeur nature** de cette dichotomie sur la mobilité urbaine toulousaine : nous démontrons empiriquement le plafond de Tier 3 sur les distributions de choix modal nominal (Étape 2), tout en établissant la valeur ajoutée de Tier 2 des agents LLM sur les régimes non tabulés et l'hystérésis temporelle (Étape 3).

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

**Ce que ce tableau établit, et ce qu'il n'établit pas.** Les huit marges sont reproduites à $0,4$ pt près. Deux précautions accompagnent cette lecture :

1. **Ces marges sont calées par construction.** Le moteur de synthèse amont ajuste directement la fréquence des profils sur ces distributions ; les retrouver est un **contrôle de cohérence de la chaîne de génération**, non une preuve de fidélité sociologique. Ce qui reste à tester est ailleurs : dans les **croisements** (âge × motorisation × zone fine), là où une synthèse par marges peut échouer sans qu'aucune marge ne bouge.
2. **Un test du $\chi^2$ non significatif ne prouve pas la conformité** : il échoue à détecter un écart, ce qui n'est pas la même chose. À $N = 1\,000$ sa puissance est faible, et un « seuil de non-rejet $p > 0,95$ » n'est pas un critère statistique. La formulation retenue pour la publication est donc un **test d'équivalence** (TOST) marge par marge, avec une borne d'indifférence annoncée d'avance ($\pm 1$ pt), complété par l'écart absolu maximal et un $V$ de Cramér comme tailles d'effet.

### 2.3 Dimensionnement de l'Échantillon ($N = 1\,000$) et Justification Statistique
Le choix de fixer l'évaluation principale sur une cohorte de $N = 1\,000$ agents synthétiques (stratifiés selon secteur $\times$ classe d'âge $\times$ motorisation) répond à une justification statistique rigoureuse (*ex ante*, détaillée dans [`JUSTIFICATION_TAILLE_ECHANTILLON.md`](JUSTIFICATION_TAILLE_ECHANTILLON.md)) :

1. **Unité d'analyse = déplacement et effet de grappe ($n_{\text{eff}}$) :**  
   Une part modale se calcule sur les flux de trajets ($\approx 3{,}5$ déplacements/jour/agent, soit $\approx 3\,500$ déplacements pour $1\,000$ agents). Compte tenu de la corrélation intra-agent (même équipement automobile, même domicile/travail, $\rho \approx 0{,}4 - 0{,}5$), l'effectif efficace équivalent est de $n_{\text{eff}} \approx 1{,}75 \times N \approx 1\,750$ déplacements indépendants. Tout intervalle de confiance est estimé par **cluster bootstrap par agent**.
2. **Plancher de l'enquête terrain (EMC² 2023) :**  
   L'enquête de référence toulousaine porte sur $\approx 16\,000$ habitants et présente, après redressement et grappes ménages, une incertitude propre de $\pm 0{,}3$ à $\pm 0{,}6\text{ pt}$ sur les parts modales. Réduire l'incertitude simulée en deçà n'apporte aucun pouvoir de décision statistique face à une cible dont la précision est finie.
3. **Détection de biais structurels ($> 8\text{ pt}$) :**  
   À $N = 1\,000$ ($n_{\text{eff}} \approx 1\,750$), la demi-largeur de l'IC à $95\,\%$ est de $\pm 2{,}0\text{ pt}$ sur la marche et $\pm 1{,}0\text{ pt}$ sur le vélo. Cette précision suffit amplement à caractériser les biais systématiques observés (sous-estimation de la marche, engouement disproportionné pour le vélo) et à autoriser l'analyse sur 3–4 macro-strates spatiales et socio-démographiques.
4. **Arbitrage du budget d'inférence :**  
   Au-delà de $N \approx 2\,000$, l'incertitude d'échantillonnage ($\pm 1{,}5\text{ pt}$) devient négligeable devant les biais inhérents de spécification méthodologique (règle du mode principal, seuils de micro-déplacements : $3$ à $5\text{ pts}$). Le budget de calcul est ainsi réalloué à la **mesure de la variabilité stochastique (5 graines)** et aux **plans appariés intra-agents (McNemar)** sur les scénarios d'actualité et d'hystérésis ($500$ à $1\,000$ agents ré-interrogés dans 5 conditions).

La stabilité par changement d'échelle ($N = 1\,000 \to 10\,000$) découle du tirage stratifié et se vérifie par la même procédure.

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
* Nous publions en outre le **taux de bascule individuelle** inter-graines — part des décisions dont le mode change d'une graine à l'autre. Une part modale stable ne garantit pas une affectation individuelle stable : deux graines peuvent produire la même distribution en permutant les individus, et pour un modèle de charge de réseau c'est ce second niveau qui compte.
* Toute comparaison de deux prompts est conduite par **test de McNemar sur les décisions appariées** (même persona, même jeu d'options) et non par différence d'accuracy globale : deux modèles à $60\,\%$ peuvent se tromper sur des individus disjoints.

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
  *Précaution de lecture :* deux valeurs de référence circulent et ne doivent pas être mélangées — la **cible métropolitaine EMC²** (voiture 56,70 %) et la **part observée dans le jeu de test scellé** (voiture 57,07 %, vélo 4,01 %, TC 12,64 %, marche 26,28 %). Les métriques micro se lisent contre la seconde, les parts modales de simulation contre la première ; chaque tableau précise laquelle il utilise.
* **Prévalence des paramètres physiques & Plafond de Tier 3 (SILICA)** : Réduire le temps terminal d'accès/stationnement voiture de $7,93\text{ min}$ à $0,55\text{ min}$ amène un gain de $-4,52\text{ pt}$ sur la loss composite. La physique de l'itinéraire prime systématiquement sur les consignes du prompt. Ce résultat illustre concrètement le **plafond de Tier 3** mis en évidence par SILICA (*Bin Tareaf et al., 2026*) : le prompt engineering ne peut compenser les priors pré-entraînés pour atteindre la fidélité quantitative humaine sans modèle supervisé.

### 4.3 Audit Unitaire à Parité Informationnelle Stricte ($N = 1\,000$ trajets scellés)
L'oracle et le Logit Multinomial sont évalués sur l'**intégralité** du jeu de test scellé (`mode_choice_test.csv`, $13\,045$ trajets, découpage **par ménage** et non par trajet, graine 0). Le LLM, dont chaque décision coûte une requête d'inférence, est évalué sur un **sous-échantillon de $1\,000$ trajets tiré dans ce même jeu** ; toute comparaison des trois modèles est faite sur ce sous-échantillon, les chiffres sur $13\,045$ trajets servant à caractériser le plafond tabulaire. Les trois reçoivent le même vecteur de **21 variables** $\vec{x}$ (12 personne, 3 contexte, 6 géographie).

**Deux règles de comparabilité, appliquées sans exception.**
* **Règle argmax.** Un modèle probabiliste possède deux erreurs L1 : sur la masse de probabilité ($2,69\text{ pt}$) et sur l'argmax ($7,30\text{ pt}$). En simulation un agent retient **un** mode : seule la seconde est comparable aux $29,81\text{ pt}$ du LLM. L'écart réel est donc d'un facteur $4$, et non $11$.
* **Renormalisation sur l'offre.** La politique tabulaire prédit sur quatre classes en aveugle ; l'agent ne choisit que parmi les itinéraires réellement proposés par OTP. Chaque prédiction est restreinte aux modes offerts puis renormalisée à $100\,\%$ (hypothèse IIA, déclarée comme limite). Sans cette correction, on crédite le modèle d'options inexistantes et on pénalise l'agent pour des modes jamais proposés — deux biais qui vont dans le même sens.

**Bras complémentaire — LLM few-shot.** Pour séparer « le LLM ne peut pas » de « le LLM n'a pas été informé », un quatrième bras reçoit $k$ exemples de l'enquête dans le prompt. Sans lui, la comparaison à un modèle supervisé reste attaquable.


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

### 5.3 Plan Expérimental à Cinq Conditions et Prédictions Pré-Enregistrées

Comparer « agent avec article » à « oracle sans article » ne prouve rien : l'oracle n'est pas *aveugle*, il n'est pas *informé*. Le plan est donc porté à **cinq conditions** par événement, sur une cohorte de $1\,000$ déplacements :

| # | Condition | Ce que le modèle reçoit | L'objection qu'elle ferme |
|---|---|---|---|
| 1 | Agent, régime nominal | Aucun article | Référence interne du bras |
| 2 | Agent + article brut | Le texte de presse tel quel | — (mesure de l'effet total) |
| 3 | **Agent + paraphrase sans indice modal** | Le même fait, réécrit sans aucune mention de mode (« métros renforcés » retiré) | *« Le modèle ne raisonne pas, il obéit »* : l'article contient souvent la réponse |
| 4 | **Agent + article placebo** | Un article réel classé « éliminer », sans effet modal attendu | *« Le modèle réagit à n'importe quel texte »* — contrôle de spécificité |
| 5 | **Oracle + événement encodé** | L'événement traduit en variables : liens coupés dans OTP, fréquences dégradées, météo | *« Votre oracle est muet parce que vous ne lui avez rien donné »* |

La condition 5 sert deux fois : elle rend la comparaison honnête, **et** elle rétablit la cohérence physique du bras textuel — si l'article ferme des rues que le calculateur d'itinéraires ignore, l'agent raisonne contre les durées qu'on lui montre, et le résultat devient ininterprétable dans les deux sens. Le contexte textuel et le contexte physique doivent être **le même événement déclaré deux fois**, une fois en langue et une fois en graphe.

**Prédictions pré-enregistrées.** La grille d'expertise comportementale des 30 articles (impacts modaux notés de 0 à 3, échelle spatiale, classe de crédibilité) a été établie **avant tout appel au modèle**. Gelée par empreinte git et datée, elle constitue un jeu de $4 \times 30 = 120$ **prédictions directionnelles signées**. L'évaluation rapporte le taux de signe correct et un $\kappa$ pondéré (l'intensité prédite étant ordinale), et publie la grille intégrale en annexe.

**Précautions méthodologiques d'ordonnancement (Baronchelli, 2026).** Pour neutraliser tout biais d'amorçage ou de saillance positionnelle (*shared cues* / biais de primauté), l'ordre de présentation des options d'itinéraires et des modes est systématiquement randomisé de manière indépendante pour chaque requête d'agent.

**Critères de réfutation de H3.** L'hypothèse tombe si : (i) l'agent sans registre montre la même inertie à J+1 ; (ii) diviser la vitesse d'oubli $\lambda$ par trois ne déplace pas la courbe ; (iii) un article placebo produit le même report modal que l'article pertinent.

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
| **Fidélité Macro (Erreur L1, argmax)** | $7,30\text{ pt}$ — $2,69\text{ pt}$ en masse de probabilité, non comparable | Dégradée ($29,81\text{ pt}$) | À mesurer |
| **Rappel sur classe minoritaire (vélo)** | $13,8\,\%$ — angle mort assumé | À mesurer | À mesurer |
| **Réaction aux Actualités & Hystérésis**| Nulle (Aveugle / Amnésique) | Réaliste (Inertie cognitive) | **Préservée sur les 10 % d'exceptions** |

### 6.3 Échelle du Foyer et Chaînes Spatiales
La prospective s'étend à l'intégration des contraintes intra-ménage : arbitrage du véhicule partagé, dépose scolaire et conservation stricte de la chaîne spatiale des véhicules (`vehicle-chain.md`).

---

# 7. Conclusion & Enseignements

1. **Pas de LLM pour la prédiction de masse statique (Plafond de Tier 3)** : En accord direct avec les résultats du benchmark SILICA (*Bin Tareaf et al., 2026*), les agents LLM échouent à reproduire fidèlement la distribution empirique de mobilité humaine sans calage statistique lourd. Les arbres supervisés (LightGBM) sont $\approx 2\,700\times$ plus rapides (moins d'une seconde contre $\approx 45$ minutes pour $10\,000$ trajets), gratuits en tokens et quatre fois plus fidèles en argmax ($7,30\text{ pt}$ vs $29,81\text{ pt}$ d'erreur L1).
2. **La valeur du LLM réside dans la dépendance contextuelle et l'adaptation (Validité de Tier 2)** : Conformément à la thèse de Baronchelli (*Baronchelli, 2026*), l'intérêt des LLMs ne réside pas dans leur statut de « proxy humain statistique », mais dans leur comportement adaptatif émergent : dépendance non tabulée (presse locale, dégoût, densité de foule, agrément) et non indépendante (hystérésis $J+1$ avec mémoire court-terme $\mathcal{M}_t$, arbitrage intra-ménage, chaîne spatiale des véhicules). Partout ailleurs, un modèle tabulaire fait mieux et moins cher.
3. **Un enseignement de mesure, transférable hors de ce cas** : Une variante à $93,4\,\%$ d'accuracy sur l'enquête a produit le **pire** score en simulation ($9,28$ contre $7,40$ de composite), la distance reconstruite depuis la durée déclarée contenant le mode retenu. Toute évaluation d'agent génératif doit être notée **là où le modèle sert**, pas là où il est facile de le noter.
4. **L'architecture hybride en cascade répond à la dichotomie fondamentale** : Réconcilier les deux questions de Baronchelli par une division du travail — confier $90\,\%$ du flux nominal au calage statistique supervisé (Tier 3), et réserver le raisonnement génératif LLM aux $10\,\%$ de situations complexes, perturbations et ruptures contextuelles (Tier 2).

---

# 8. Références Bibliographiques

Une bibliographie détaillée, commentée et reliée aux hypothèses est disponible dans [`BIBLIOGRAPHIE.md`](BIBLIOGRAPHIE.md), et les entrées BibTeX complètes dans [`references.bib`](references.bib).

### 8.1 Épistémologie des Agents LLM, Stress-Tests & Dynamiques Collectives
* **Bin Tareaf, R. et al. (2026)**. *Benchmarking large language model agent societies against human behavioural distributions (SILICA)*. arXiv / Open-Source Benchmark (`raadbintareaf/silica-benchmark`).
* **Baronchelli, A. (2026)**. *A useful stress test for the emerging science of LLM populations*. Research Commentary, City St George's, University of London / Alan Turing Institute.
* **Baronchelli, A. et al. (2025)**. *Emergent social conventions and collective bias in LLM populations*. *Science Advances*, 11(8), eadp3456.
* **Baronchelli, A. et al. (2026)**. *Group size effects and collective misalignment in LLM multi-agent systems*. *Proceedings of the National Academy of Sciences (PNAS)*, 123(12), e2519876123.
* **Park, J. S., O'Brien, J. C., Cai, C. J., Morris, M. R., Liang, P., & Bernstein, M. S. (2023)**. *Generative agents: Interactive simulacra of human behavior*. *Proceedings of the 36th Annual ACM Symposium on User Interface Software and Technology (UIST '23)*, pp. 1–22.

### 8.2 Économétrie du Choix Discret & Modélisation des Déplacements
* **McFadden, D. (1974)**. *Conditional logit analysis of qualitative choice behavior*. In *Frontiers in Econometrics*, Academic Press, pp. 105–142.
* **Ben-Akiva, M., & Lerman, S. R. (1985)**. *Discrete Choice Analysis: Theory and Application to Travel Demand*. MIT Press.
* **Train, K. E. (2009)**. *Discrete Choice Methods with Simulation* (2nd ed.). Cambridge University Press.
* **Horni, A., Nagel, K., & Axhausen, K. W. (Eds.). (2016)**. *The Multi-Agent Transport Simulation MATSim*. Ubiquity Press.
* **Hörl, S., & Balać, M. (2021)**. *Synthetic population and travel demand generation for France from open data: eqasim pipeline*. *Transportation Research Record*, 2675(11), pp. 329–341.
* **Taillandier, P., Gaudou, B., Grignard, A., et al. (2019)**. *Building, composing and experimenting complex spatial agent-based models with the GAMA platform*. *GeoInformatica*, 23(2), pp. 299–322.

### 8.3 Machine Learning Tabulaire, Explicabilité & Données d'Enquête
* **Ke, G., Meng, Q., Finley, T., et al. (2017)**. *LightGBM: A highly efficient gradient boosting decision tree*. *Advances in Neural Information Processing Systems (NeurIPS 30)*, pp. 3146–3154.
* **Lundberg, S. M., & Lee, S.-I. (2017)**. *A unified approach to interpreting model predictions*. *Advances in Neural Information Processing Systems (NeurIPS 30)*, pp. 4765–4774.
* **Tisséo Collectivités & AUAT (2023)**. *Enquête Mobilité Certifiée Cerema (EMC² 2023) de la Grande Agglomération Toulousaine*. Micro-données ProGEDO lil-1750.
* **Insee (2022)**. *Recensement de la Population (RP 2022) & Fichier Localisé Social et Fiscal (FILOSOFI 2021)*. Institut National de la Statistique et des Études Économiques.

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

### Annexe E : Dictionnaire des 21 Variables EMC² 2023 (ProGEDO lil-1750)
Description complète du dictionnaire de données : 12 variables de personne, 3 de contexte de déplacement, 6 de géographie. Une variante à 19 variables (sans les deux distances à l'hypercentre) a été mesurée à $0,7843$ d'accuracy pour $7,43$ de composite, et deux variantes de distance ont été écartées ; le contrat servi est celui à 21 variables (`spec_version 2`).

---

### Annexe F : Journal des Corrections Méthodologiques (v1.4)

Chaque chiffre du manuscrit a été recoupé avec les mesures produites par le dépôt. Onze écarts ont été corrigés dans cette version :

| # | Écart relevé en `v1.3` | Correction appliquée en `v1.4` |
|---|---|---|
| 1 | « 15 variables » à parité informationnelle | Contrat de production à **21 variables** (`spec_version 2`) |
| 2 | L1 de l'oracle ($2,68$) opposée à celle du LLM ($29,81$) | Masse de probabilité vs argmax : comparaison ramenée à **$7,30$ contre $29,81$** |
| 3 | « $\chi^2$, $p = 0,98$ confirme la parfaite fidélité » | Non-rejet ≠ preuve ; remplacé par un **test d'équivalence** et des tailles d'effet |
| 4 | Jalon 0 présenté comme une validation | Requalifié en **contrôle de cohérence** ; croisements à tester |
| 5 | Composites comparés sans effectif | Effectif désormais obligatoire : **$+5,02$ pt** mesurés à décisions constantes en passant de 881 à 81 personnes |
| 6 | Parité présentée comme symétrique | **Dissymétrie d'exposition déclarée** ($31\,279$ trajets vus contre zéro) et bras few-shot ajouté |
| 7 | « Modèle tabulaire aveugle à l'événement » | Il n'est pas aveugle, il n'est pas informé → **condition 5** (oracle recevant l'événement encodé) |
| 8 | Effet presse mesuré contre une condition sans article | Ajout des bras **paraphrase sans indice modal** et **article placebo** |
| 9 | « $10\,000\times$ plus rapide » | **$\approx 2\,700\times$**, d'après le tableau comparatif du manuscrit lui-même |
| 10 | Périmètre de l'audit unitaire ($1\,000$ vs $13\,045$ trajets) | Périmètres explicités : oracle sur $13\,045$, LLM sur un sous-échantillon de $1\,000$ tiré du même jeu |
| 11 | Poids du composite annoncés à $0,40 / 0,20 / 0,20 / 0,20$ avec $\sum w = 1$ | Poids réellement servis : global $1,0$ · absence $1,0$ · âge $0,5$ · occupation $0,5$ · motif $0,5$ · genre $0,3$ · distance $0,3$ — **somme pondérée non renormalisée** |

*Sources de recoupement :* `scripts/progedo_logit/mode_choice_policy_metrics.json` (accuracy, LogLoss, matrice de confusion, importances de gain), `scripts/progedo_logit/feature_spec.json` (contrat de variables), `docs/arch/score-synthesis.md` (renormalisation sur l'offre, témoin d'effectif, gardes de substrat), `docs/changelog.md` (temps terminaux par mode, variantes de distance mesurées).
