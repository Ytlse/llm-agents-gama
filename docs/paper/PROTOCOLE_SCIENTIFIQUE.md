# Cadre Méthodologique & Protocole Scientifique de Référence (2026)
## Projet LLM-Agents GAMA / Modélisation Comportementale de Mobilité Urbaine

**Auteurs :** Yves B., Benoit Gaudou, Kamaldeep Singh Oberoi  
**Cadre de recherche :** Projet LLM-Agents GAMA / Défis Clés Occitanie (MIDOC)  
**Version :** `v1.4` (2 septembre 2026) — *Intégration du cadre de stress-test SILICA (Bin Tareaf et al., 2026) et de la dichotomie de Baronchelli (2025, 2026) : formalisation des trois niveaux de validation (Tier 1/2/3), règles de comparabilité (argmax, renormalisation sur l'offre, effectif), randomisation des options contre les biais de primauté, et critères de réfutation explicites*  
**Fichiers associés :** [`MANUSCRIT_DETAILLE_2026.md`](MANUSCRIT_DETAILLE_2026.md), [`PLAN_ARTICLE_2026.md`](PLAN_ARTICLE_2026.md), [`BIBLIOGRAPHIE.md`](BIBLIOGRAPHIE.md), [`references.bib`](references.bib), [`SLIDES_SEMINAIRE_2026_v1.0.html`](SLIDES_SEMINAIRE_2026_v1.0.html)  

---

## 1. Principes Épistémologiques & Standards de Rigueur

La recherche sur les agents génératifs appliqués aux sciences sociales et aux transports (GABM) doit respecter les standards les plus stricts de la méthode scientifique. L'objectif est de produire des résultats **réfutables**, **reproductibles** et **statistiquement solides**.

### 1.1 La Grille de Validation en 3 Paliers (SILICA / Bin Tareaf et al., 2026)
Pour clarifier le statut épistémique des simulations à base de LLM, nous adoptons la taxonomie issue du benchmark **SILICA** (*Bin Tareaf et al., 2026* ; *Baronchelli, 2026*) :
* **Tier 1 (Émergence en configuration standard)** : Le comportement ou phénomène apparaît sous le protocole expérimental initial.
* **Tier 2 (Robustesse & Stabilité qualitative)** : Le comportement résiste aux perturbations (variations de prompts, mémoires, tailles d'échantillons, randomisation de l'ordre des options, incitations) et reste qualitativement stable entre architectures de LLM.
* **Tier 3 (Fidélité distributionnelle humaine quantitative)** : Le modèle reproduit fidèlement et quantitativement les distributions statistiques et mécanismes d'interaction empiriques observés chez l'humain.

Ce protocole prouve que si les agents LLM atteignent le **Tier 2** sur les régimes non tabulés (adaptation textuelle, hystérésis), ils butent sur un **plafond de Tier 3** face aux distributions modales empiriques de l'enquête ménages-déplacements (EMC² 2023), justifiant l'arbitrage vers une architecture hybride en cascade.

```
                ┌────────────────────────────────────────────────────────┐
                │ 0. Jalon 0 : Cohérence de la Population Synthétique    │
                │    (Équivalence par marge vs Recensement/CEREMA)       │
                └──────────────────────────┬─────────────────────────────┘
                                           │
                                           ▼
                ┌────────────────────────────────────────────────────────┐
                │ 1. Question de Recherche & Hypothèses Testables (H0/H1)│
                └──────────────────────────┬─────────────────────────────┘
                                           │
                                           ▼
                ┌────────────────────────────────────────────────────────┐
                │ 2. Ablation Incrémentale en 4 Paliers (+ few-shot)     │
                │    (Planchers -> Nu -> Calibré -> Baselines ML/Logit)  │
                └──────────────────────────┬─────────────────────────────┘
                                           │
                                           ▼
                ┌────────────────────────────────────────────────────────┐
                │ 3. Évaluation Écologique — 5 conditions, pré-enregistrée│
                │    (Brut / Paraphrase / Placebo / Oracle informé)      │
                └──────────────────────────┬─────────────────────────────┘
                                           │
                                           ▼
                ┌────────────────────────────────────────────────────────┐
                │ 4. Validation Statistique (Seeds, IC95, McNemar, L1)   │
                └────────────────────────────────────────────────────────┘
```

---

## 2. Jalon 0 : Validation Démographique de la Population Synthétique

Dans la simulation multi-agents GAMA, chaque agent est un **individu virtuel unique et équiprobable** (poids unitaire = 1). Aucun coefficient d'extrapolation $COEP$ n'est requis au runtime de la simulation, car le moteur de synthèse amont (EQASIM / Recensement Insee RP 2022 + FILOSOFI + ENTD) calibre directement la fréquence des profils pour reproduire la structure sociologique de la métropole.

### 2.1 Tableau de Conformité Démographique (Goodness-of-Fit)
Pour prouver que la cohorte synthétique ($N = 1\,000$ ou $N = 10\,000$ agents) reproduit fidèlement la population de référence publiée dans le rapport officiel CEREMA / Insee :

| Variable Démographique | Cible Référentielle (Rapport / Insee) | Population Synthétique ($N = 1\,000$) | Écart ($\Delta$) | Statut de validation |
|---|---|---|---|---|
| **Genre (Femmes / Hommes)** | 51,8 % / 48,2 % | 51,9 % / 48,1 % | $\pm 0,1\text{ pt}$ | Conforme |
| **Âge : Moins de 18 ans** | 19,4 % | 19,2 % | $-0,2\text{ pt}$ | Conforme |
| **Âge : 18 - 64 ans (Actifs)** | 62,1 % | 62,4 % | $+0,3\text{ pt}$ | Conforme |
| **Âge : 65 ans et plus** | 18,5 % | 18,4 % | $-0,1\text{ pt}$ | Conforme |
| **Ménages sans voiture** | 22,3 % | 22,1 % | $-0,2\text{ pt}$ | Conforme |
| **Ménages avec 1 voiture** | 46,1 % | 46,5 % | $+0,4\text{ pt}$ | Conforme |
| **Ménages avec 2+ voitures** | 31,6 % | 31,4 % | $-0,2\text{ pt}$ | Conforme |
| **Taux de détention du permis** | 84,2 % (Adultes) | 84,0 % (Adultes) | $-0,2\text{ pt}$ | Conforme |

### 2.2 Statut du Jalon 0, Test d'Équivalence & Stabilité d'Échelle
* **Ce que le tableau établit.** Les huit marges sont reproduites à $0,4$ pt près. Comme le moteur de synthèse amont cale directement ces distributions, les retrouver est un **contrôle de cohérence de la chaîne de génération** — pas une preuve de fidélité sociologique.
* **Test retenu pour la publication : l'équivalence, pas la non-significativité.** Un $\chi^2$ non significatif échoue à détecter un écart, ce qui ne prouve pas son absence — et « seuil de non-rejet $p > 0,95$ » n'est pas un critère statistique. Le protocole retient donc un **test d'équivalence (TOST)** marge par marge avec une borne d'indifférence annoncée d'avance ($\pm 1$ pt), accompagné de l'écart absolu maximal et d'un $V$ de Cramér.
* **Ce qui reste à tester.** Les **croisements** (âge × motorisation × zone fine) : c'est là qu'une synthèse par marges échoue sans qu'aucune marge ne bouge.
* Grâce aux propriétés du tirage stratifié d'EQASIM, cette représentativité est invariante par changement d'échelle ($N = 1\,000 \to N = 10\,000$).

### 2.3 Dimensionnement de l'Échantillon ($N = 1\,000$) & Inférence par Cluster Bootstrap
*(Voir note complète : [`JUSTIFICATION_TAILLE_ECHANTILLON.md`](JUSTIFICATION_TAILLE_ECHANTILLON.md))*

1. **Unité d'analyse = déplacement ($n_{\text{eff}}$ & Cluster Bootstrap) :**  
   Une part modale se calcule sur les déplacements ($\approx 3{,}5$ dépl./jour/agent, soit $\approx 3\,500$ déplacements pour $1\,000$ agents). En raison de la forte corrélation intra-agent (même foyer, localisation, motorisation ; $\rho \approx 0{,}4 - 0{,}5$), l'effectif efficace est de $n_{\text{eff}} = \frac{n_{\text{trips}}}{1 + (m-1)\rho} \approx 1{,}75 \times N \approx 1\,750\text{ à } 2\,000$. Les intervalles de confiance doivent impérativement être calculés par **cluster bootstrap par agent** (et non par un IC binomial naïf sur les déplacements).
2. **Plancher de précision de l'enquête référence (EMC² 2023) :**  
   Portant sur près de $16\,000$ habitants, l'enquête EMC² toulousaine (AUAT/CEREMA) a une précision propre de $\pm 0{,}3$ à $\pm 0{,}6\text{ pt}$ sur les parts modales agrégées. Descendre en dessous côté simulation n'apporte aucun gain d'information.
3. **Détection de biais vs variance :**  
   Les déviations majeures observées (sous-estimation de la marche, sur-attraction du vélo : écarts de $8$ à $15\text{ pt}$) sont structurelles. $N = 1\,000$ agents ($IC_{95\%} = \pm 2{,}0\text{ pt}$ sur la marche, $\pm 1{,}0\text{ pt}$ sur le vélo) offre une puissance statistique maximale pour prouver ces biais tout en permettant des analyses sur 3–4 sous-groupes larges.
4. **Plans appariés pour régimes non tabulés (Actualités / Hystérésis) :**  
   Les mêmes $500$ à $1\,000$ agents sont suivis à travers toutes les conditions et graines. Le test apparié (McNemar) élimine la variance inter-individuelle et permet de détecter des variations modales de $3$ à $5\text{ pt}$ avec une efficacité 3 à 10 fois supérieure à des groupes indépendants.

---

## 3. Formalisation Mathématique des Métriques d'Écart & Poids

Pour éviter tout arbitraire méthodologique, l'écart entre la réalité terrain et les prédictions est mesuré à deux échelles complémentaires :

### 3.1 Échelle Micro-Décisionnelle (Unitaire)
* **Accuracy pondérée ($COEP$)** sur données d'enquête brutes scellées ($13\,045$ trajets) :
  $$\text{Accuracy} = \frac{\sum_{i=1}^N w_i \cdot \mathbb{I}(\hat{y}_i = y_i)}{\sum_{i=1}^N w_i}$$
* **Macro-F1 Score & LogLoss Multi-Classe** pour pénaliser les erreurs sur les classes minoritaires (Vélo à 4,1 %).

### 3.2 Trois Règles de Comparabilité, Appliquées Sans Exception

1. **Règle argmax.** Un modèle probabiliste possède deux erreurs L1 : sur la masse de probabilité et sur l'argmax. En simulation, un agent retient **un** mode. Toute comparaison à un agent se fait donc **argmax contre argmax** — pour l'oracle de référence, $7,30\text{ pt}$ et non $2,69\text{ pt}$.
2. **Renormalisation sur l'offre.** La politique tabulaire prédit sur quatre classes en aveugle ; l'agent ne choisit que parmi les itinéraires proposés par le calculateur. Chaque prédiction est restreinte aux modes offerts, puis renormalisée à $100\,\%$ (hypothèse IIA, déclarée comme limite).
3. **Effectif obligatoire.** Les divergences distributionnelles sont biaisées vers le haut sur les petites strates : à décisions rigoureusement inchangées, passer de 881 à 81 personnes dégrade le composite de **$+5,02$ pt**. Aucun score n'est publié sans son effectif, et un témoin d'effectif sans appel au modèle accompagne toute comparaison de substrats.

### 3.3 Échelle Macroscopique (Distributionnelle)
* **Erreur L1 / Total Variation Distance (TVD)** :
  $$\text{TVD}(P, Q) = \frac{1}{2} \sum_{m \in \text{Modes}} \left\vert P(m) - Q(m) \right\vert$$
* **Score Composite Multi-Strates ($\mathcal{L}_{\text{composite}}$)** :
  Pour s'assurer que le modèle ne compense pas des erreurs inverses entre sous-populations, la loss composite agrège la TVD globale et les TVD par strates démographiques :
  $$\mathcal{L}_{\text{composite}} = w_{\text{global}} \cdot \text{TVD}_{\text{global}} + \sum_{s \in \text{Strates}} w_s \cdot \text{TVD}_s \quad \text{avec} \quad \sum w = 1$$
  *Poids réellement servis par le moteur* (manifeste `scripts/synthesis/sources.yaml`) : $w_{\text{global}} = 1{,}0$, $w_{\text{pénalité d'absence}} = 1{,}0$, $w_{\text{âge}} = 0{,}5$, $w_{\text{occupation}} = 0{,}5$, $w_{\text{motif}} = 0{,}5$, $w_{\text{genre}} = 0{,}3$, $w_{\text{distance}} = 0{,}3$. La somme vaut $4{,}1$ : le composite est une **somme pondérée non renormalisée**, et se lit en points de pourcentage à ce facteur d'échelle près — la contrainte $\sum w = 1$ des versions précédentes de ce document ne décrivait pas le moteur. La dimension `length_penalty`, qui pénalise les prompts longs, est neutralisée dans les comparaisons où aucun prompt n'intervient (simulation, modèle tabulaire).

---

## 4. Protocole d'Ablation Incrémentale en 4 Paliers

L'évaluation compare systématiquement les modèles à travers 4 paliers d'information croissante :

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PALIER 0 : PLANCHERS STATISTIQUES & HEURISTIQUES PHYSIQUES                  │
│ 0.1 Hasard Uniforme : Tirage aléatoire pur (25 % par mode) ──► 0 info.      │
│ 0.2 Prior Empirique (Zero-Rule) : Prédit toujours Voiture ──► 56,7 % acc.   │
│ 0.3 Heuristique du Plus Rapide : Min(Durée OTP) ──► Physique réseau pure.   │
├─────────────────────────────────────────────────────────────────────────────┤
│ PALIER 1 : MODÈLE NU / BARE LLM (Zero Prompt Engineering)                   │
│ • Profil complet personne + Itinéraires réels OpenTripPlanner (OTP).        │
│ • Prompt neutre : « Choisis l'itinéraire le plus approprié ».               │
│ • Modèles évalués :                                                         │
│   - Modèles Français / Européens : Mistral (Mistral-Small, Mistral-Nemo)    │
│   - Modèle Ouvert Local : Qwen-2.5-32B-Instruct (Déterministe tau=0.0)      │
│   - Modèle Propriétaire : Google Gemini-Flash                               │
├─────────────────────────────────────────────────────────────────────────────┤
│ PALIER 2 : MODÈLE CALIBRÉ (Prompt Engineering & Optimisation)               │
│ • Injection de consignes comportementales et personas enrichis.             │
│ • Mesure du gain net : Delta = Score(Calibré) - Score(Nu).                  │
│ • Le gain n'est retenu que s'il excède la dispersion inter-graines (± 1,2).  │
├─────────────────────────────────────────────────────────────────────────────┤
│ PALIER 2 bis : MODÈLE FEW-SHOT (k exemples d'enquête dans le prompt)        │
│ • Sépare « le LLM ne peut pas » de « le LLM n'a pas été informé ».          │
├─────────────────────────────────────────────────────────────────────────────┤
│ PALIER 3 : BASELINES STATISTIQUES DE RÉFÉRENCE (Plafond Tabulaire)          │
│ • Modèle Économétrique de référence : Logit Multinomial (MNL de McFadden).  │
│ • Oracle Machine Learning Supervisé : LightGBM (78,5 % acc, LogLoss 0,540). │
│ • Contrat de 21 variables (spec v2) ; découpage du test PAR MÉNAGE.         │
│ • Plafond de référence, non concurrent : 31 279 trajets vus contre zéro.    │
└─────────────────────────────────────────────────────────────────────────────┘

**Angle mort à publier avec le plafond.** L'oracle atteint $78,5\,\%$ d'accuracy en abandonnant la classe minoritaire : rappel vélo $13,8\,\%$ pour $4,0\,\%$ de support, contre $87,5\,\%$ sur la voiture. Une comparaison limitée à l'accuracy globale masque exactement ce compromis, et c'est dans cet angle mort que le domaine d'excellence de l'agent est à chercher.
```

---

## 5. Protocole d'Évaluation Écologique : Événements Réels Sourcés

Pour dépasser les contextes synthétiques arbitraires, les agents LLM sont évalués face à des **articles de presse locale et communiqués officiels réels et datés de la métropole toulousaine**.

### 5.1 Matrice des 4 Événements d'Actualité Sourcés

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. ÉVÉNEMENT CULTUREL / FESTIF (Attracteur piéton/TC & Blocage routier)     │
│ • Fait réel sourcé : Le passage du Minotaure dans les rues de Toulouse      │
│   (Compagnie La Machine - La Dépêche du Midi / Métropole).                  │
│ • Article brut injecté : « Hyper-centre piétonnisé, circulation fermée sur  │
│   les boulevards, métros renforcés, affluence piétonne exceptionnelle ».    │
│ • Hypothèse : Chute de l'usage voiture vers Métro et Marche.                │
├─────────────────────────────────────────────────────────────────────────────┤
│ 2. ÉVÉNEMENT ENVIRONNEMENTAL / RÉGULATOIRE (Incentive TC)                   │
│ • Fait réel sourcé : Pic de pollution à l'ozone et Alerte Canicule          │
│   (Arrêté préfectoral Haute-Garonne / Ticket Planète Tisséo à 3 €).         │
│ • Article brut injecté : « Transports collectifs à tarif réduit/gratuits,   │
│   circulation différenciée Crit'Air et recommandation d'éviter le vélo ».   │
│ • Hypothèse : Bascule vers TC climatisés et évitement du vélo à 14h.        │
├─────────────────────────────────────────────────────────────────────────────┤
│ 3. INCIDENT D'INFRASTRUCTURE MAJEUR (Répulseur Voiture)                     │
│ • Fait réel sourcé : Accident grave et coupure du Périphérique Ouest        │
│   au niveau du pont d'Empalot (Flash Radio Vinci / La Dépêche).             │
│ • Article brut injecté : « Rocade coupée, +1h de bouchon estimé ».          │
│ • Hypothèse : Report modal d'urgence vers TER / Métro.                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ 4. PANNE MAJEURE RÉSEAU (Répulseur TC & Test Longitudinal d'Hystérésis)     │
│ • Fait réel sourcé : Panne informatique générale du Métro Ligne A Tisséo.   │
│ • Article brut injecté : « Métro à l'arrêt complet toute la soirée de 17h ».│
│ • Hypothèse : Bascule d'urgence à J, et persistance du churn à J+1..J+5.    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Protocole Expérimental à Cinq Conditions & Cinétique Temporelle

Comparer « agent avec article » à « oracle sans article » ne démontre rien : l'oracle n'est pas *aveugle*, il n'est pas *informé*. Pour chaque événement, **cinq** conditions sont comparées sur une cohorte de $1\,000$ déplacements :

1. **Base** : agent sans article de presse (régime nominal).
2. **Info** : agent avec l'article brut injecté dans le prompt.
3. **Paraphrase sans indice modal** : le même fait réécrit en retirant toute mention de mode — sans ce bras, on mesure du suivi de consigne et non du raisonnement, car l'article contient souvent la réponse (« métros renforcés »).
4. **Placebo** : un article réel classé « éliminer » par la grille, sans effet modal attendu — contrôle de spécificité, gratuit puisque le matériel est déjà archivé.
5. **Oracle informé** : le même événement traduit en variables (liens coupés dans le graphe, fréquences dégradées, météo). Cette condition rend la comparaison honnête **et** rétablit la cohérence physique du bras textuel : le contexte doit être **le même événement déclaré deux fois**, une fois en langue et une fois en graphe.

*Mesure :*
* Taux de bascule modal net : $\Delta \text{Mode} = \text{Choix}(\text{Info}) - \text{Choix}(\text{Base})$, et l'écart Info − Paraphrase, qui isole la part de suivi de consigne.
* Cinétique de dissipation de l'impact sur 5 jours consécutifs ($J+1$ à $J+5$) grâce au registre de mémoire $\mathcal{M}_t$, avec un bras **agent sans mémoire** comme témoin — sans lui, l'inertie observée n'est pas imputable au registre.

### 5.3 Prédictions Pré-Enregistrées & Critères de Réfutation

**Pré-enregistration.** La grille d'expertise des 30 articles (impacts modaux de 0 à 3 étoiles, échelle spatiale, crédibilité, verdict) a été écrite **avant tout appel au modèle**. Gelée par empreinte git et datée, elle fournit $4 \times 30 = 120$ prédictions directionnelles signées. L'évaluation rapporte le **taux de signe correct** et un **$\kappa$ pondéré** (intensité ordinale), et publie la grille intégrale en annexe.

**Absence de vérité terrain, déclarée.** Aucune enquête ne suit les mêmes individus jour après jour autour d'un incident : la *valeur* du taux de reprise à $J+1$ n'est comparable à rien. Ce qui est testable est l'**ordre des bras**, la **monotonie** de la remontée, la **sensibilité** à $\gamma$ et $\lambda$, et la comparaison de la demi-vie mesurée aux élasticités publiées après grèves et pannes.

**H3 est réfutée si :** (i) l'agent sans registre montre la même inertie à $J+1$ ; (ii) diviser $\lambda$ par trois ne déplace pas la courbe ; (iii) un article placebo produit le même report modal que l'article pertinent.
