# Ticket 068 — Mesure de la variabilité décisionnelle au sein d'un groupe homogène et comparaison multi-référentiels (TBD)

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-13.
>
> **Catégorie** : Expériences & Cognition (🧠)
> **Statut initial** : `à faire`
>
> **Touche potentiellement** : Chapitre 5 (§ 5.3 variabilité et dispersion) et Chapitre 7 (§ 7.2 régimes non tabulés / sensibilité).

---

## 1. Contexte & Problématique Scientifique (AAMAS)

Dans les simulations multi-agents (ABM) de mobilité urbaine basées sur des modèles de fondation (LLM), une question méthodologique centrale se pose quant à la fidélité comportementale :
> **Quelle est la variabilité des choix modaux au sein d'un groupe d'agents strictement ou quasi-homogène, et comment cette dispersion se compare-t-elle à des référentiels de référence (données terrain, modèles économétriques ou variabilité inter-groupes) ?**

Deux pathologies symétriques guettent les agents LLM :
1. **L'effondrement stéréotypé (*mode collapse* / hyper-conformisme)** : soumis à un profil donné (ex. un cadre périurbain motorisé), le LLM choisit systématiquement le même mode (100 % voiture), annulant toute la diversité comportementale inobservée et la rationalité limitée des humains réels.
2. **L'hallucination stochastique (bruit non calibré)** : à l'inverse, si le prompt ou l'échantillonnage génère une dispersion erratique et uniforme, le LLM disperse des choix absurdes sans rapport avec les contraintes d'accessibilité physique ou d'équipements de l'agent.

Ce ticket vise à instrumenter, mesurer et formaliser cette variabilité décisionnelle au sein de groupes homogènes afin d'apporter une réponse rigoureuse et quantifiable aux relecteurs d'AAMAS.

---

## 2. Définition Opérationnelle du « Groupe Homogène »

L'expérience distingue deux niveaux d'homogénéité :

### Niveau 1 : Clones stricts (Iso-contexte absolu)
- **Définition** : Même persona textuel identique, même historique, même origine-destination, mêmes horaires, même météo, mêmes alternatives de transport avec temps et coûts strictement identiques.
- **Objectif** : Mesurer la variabilité décisionnelle résiduelle due au seul processus d'inférence et d'échantillonnage du LLM face à un problème invariant.

### Niveau 2 : Strate sociodémographique et spatiale pure
- **Définition** : Groupe d'agents distincts partageant exactement la même combinaison de variables de contrôle dans la cohorte scellée v5 :
  - Même couronne de résidence (ex. Pôle urbain centre).
  - Même équipement de mobilité (permis = oui, voiture au foyer $\ge 1$, abonnement TC = oui, vélo = oui).
  - Même motif de déplacement principal (ex. Travail).
  - Tranche de distance comparable (ex. 3 à 5 km).
- **Objectif** : Mesurer l'effet des micro-variations individuelles (récit de vie, âge précis, profession) au sein d'une même classe d'équivalence sociologique.

---

## 3. Options de Comparaison pour le Référentiel (« TBD »)

Le ticket laisse ouvert l'arbitrage du comparateur de référence parmi quatre options complémentaires (à finaliser lors de l'exécution) :

| Option | Référentiel de comparaison | Question scientifique adressée | Métriques d'évaluation |
|---|---|---|---|
| **Option A : Empirique terrain (EMC2)** | Distribution des choix observés dans l'enquête ménages pour la même strate sociodémographique. | Le LLM reproduit-il la dispersion réelle des comportements humains observés sur le territoire ? | Divergence de Jensen-Shannon ($JSD$), distance $L_1$, ratio d'entropies $H_{LLM} / H_{EMC2}$. |
| **Option B : Oracles statistiques (Logit / RF)** | Distribution probabiliste prédite par le Logit multinomial ou la forêt aléatoire pour les mêmes covariables. | Le LLM génère-t-il une variabilité comparable à celle issue d'une fonction d'utilité aléatoire classique ($\epsilon \sim \text{Gumbel}$) ? | Test du $\chi^2$ de conformité multinomiale, entropie croisée, écart d'entropie résiduelle. |
| **Option C : Décomposition de variance (Intra vs Inter)** | Rapport entre la variance interne du groupe homogène et la variance globale de la population hétérogène. | Le LLM différencie-t-il significativement des groupes distincts par rapport à sa variabilité interne (absence de sur-bruit) ? | Ratio de Fisher ($F = \sigma^2_{inter} / \sigma^2_{intra}$), indice de Theil, information mutuelle $I(\text{Mode}; \text{Groupe})$. |
| **Option D : Bruit stochastique intrinsèque** | Variabilité de répétition du modèle ($\tau > 0$ vs $\tau = 0$) sur une même instance. | La variabilité intra-groupe découle-t-elle d'une sensibilité au contexte narratif ou d'un simple bruit de tirage stochastique ? | Taux de bascule individuel (*churn rate*), corrélation de rang des probabilités logit. |

---

## 4. Métriques Quantitatives de Dispersion

Pour chaque groupe homogène $g$ de $N$ décisions réparties sur $K$ modes avec fréquences $(p_1, \dots, p_K)$ :

1. **Entropie de Shannon normalisée** :
   $$H_{norm}(g) = -\frac{1}{\ln K} \sum_{k=1}^K p_k \ln p_k \quad \in [0, 1]$$
   - $H_{norm} = 0$ : consensus absolu (mono-mode / collapse).
   - $H_{norm} = 1$ : équiprobabilité parfaite (indifférence totale).

2. **Indice d'Herfindahl-Hirschman modal (HHI)** :
   $$HHI(g) = \sum_{k=1}^K p_k^2 \quad \in [1/K, 1]$$
   Mesure la concentration sur le mode dominant.

3. **Taux de bascule inter-clones (*Churn rate*)** :
   Proportion de paires d'agents d'un même groupe homogène choisissant des modes différents.

4. **Distance distributionnelle au comparateur de référence** :
   $$D_{JS}(P_{LLM} \parallel P_{ref}) \quad \text{et} \quad L_1 = \frac{1}{2} \sum_{k=1}^K |p_{k}^{LLM} - p_{k}^{ref}|$$

---

## 5. Protocole Expérimental Prévu

1. **Sélection de 3 à 5 archétypes contrastés** dans la cohorte v5 (ex. :
   - *Archétype 1* : Actif périurbain motorisé sans alternative TC performante (captif voiture attendu).
   - *Archétype 2* : Étudiant urbain multimodal avec abonnement TC et vélo (zone de fort arbitrage modal).
   - *Archétype 3* : Retraité urbain pour motif achat/loisir à courte distance (arbitrage marche/TC).
2. **Génération de $N = 30$ à 50 répliques par archétype** (clones stricts et personas homogènes).
3. **Exécution du modèle de référence** (Gemini Flash / prompt factuel neutre vs prompt expert calibré).
4. **Calcul des métriques de dispersion** et confrontation au référentiel arbitré (EMC2, Oracle Logit, ou décomposition de variance).

---

## 6. Critères d'Acceptation

- [ ] L'échantillon de groupes homogènes (clones stricts et strates pures) est formellement extrait et scellé.
- [ ] Le référentiel de comparaison (Options A, B, C ou combinaison) est formellement arbitré.
- [ ] Le script de calcul des métriques de variabilité ($H_{norm}$, $HHI$, $L_1$, $JSD$, ratio $F$) est développé et testé.
- [ ] Les résultats expérimentaux sont consignés dans un rapport de synthèse ou intégrés dans les sections pertinentes du manuscrit (§ 5.3 ou § 7.2).
