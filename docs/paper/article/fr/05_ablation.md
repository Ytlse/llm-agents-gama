# 5. Ablation en quatre paliers et références tabulaires (brouillon)

<!-- Dernière mise à jour : 2026-09-10 -->

**Document :** brouillon français du chapitre, extrait de `MANUSCRIT_DETAILLE_2026.md` `v1.6` (3 septembre 2026), § 4, Étape 2 — « Étape 2 : Invalidation par l'Ablation & Audit Face aux Baselines Statistiques ». Le manuscrit entier est figé dans [`../../archive/MANUSCRIT_DETAILLE_2026_v1.6.md`](../../archive/MANUSCRIT_DETAILLE_2026_v1.6.md).
**Statut :** `brouillon v0` — texte **antérieur** à la réécriture de l'introduction (dont la v0.1 date du 8 septembre 2026). Trois choses à reprendre avant d'en faire un chapitre : le vocabulaire « Tier 1 / 2 / 3 », que les chapitres rédigés remplacent par *exploratory / robust / transferable* (étapes de certification de SILICA) ; les chiffres, à recouper depuis leur source dans le dépôt et non recopiés d'ici ; les renvois de section, qui suivent l'ancienne numérotation du manuscrit. Ni maître anglais ni rendu LaTeX à ce stade.
**Place dans l'article :** section du même numéro dans le plan annoncé en 1.4 de [`../en/01_introduction.md`](../en/01_introduction.md). État d'avancement : [`../README.md`](../README.md).

---

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
