# Dimensionnement de l'Échantillon & Justification Statistique ($N = 1\,000$)

**Projet :** LLM-Agents GAMA / Modélisation Comportementale de Mobilité Urbaine  
**Cadre :** Note méthodologique d'appui pour l'écriture de l'article (AAMAS / TRB / JASSS 2026-2027)  
**Documents associés :** [`MANUSCRIT_DETAILLE_2026.md`](MANUSCRIT_DETAILLE_2026.md), [`PROTOCOLE_SCIENTIFIQUE.md`](PROTOCOLE_SCIENTIFIQUE.md), [`PLAN_ARTICLE_2026.md`](PLAN_ARTICLE_2026.md)  
**Date :** 2 septembre 2026  

---

## 1. Le Raisonnement Fondamental avant les Chiffres

Trois principes méthodologiques fondamentaux fixent la taille d'échantillon pertinente ($N = 1\,000$ agents / personas), la taille brute de population n'étant que le troisième paramètre :

### 1.1 L'unité d'analyse est le déplacement, avec effet de grappe intra-agent ($n_{\text{eff}}$)
* Une part modale ne se calcule pas sur les agents, mais sur les **déplacements**.
* Avec une mobilité moyenne de $\approx 3{,}5$ déplacements/jour/agent, $N = 1\,000$ agents génèrent $\approx 3\,500$ déplacements quotidiens.
* Cependant, les déplacements d'un même agent ne sont **pas indépendants** : ils partagent la même motorisation au foyer, la même localisation de résidence et de travail, et la même chaîne d'activités quotidienne.
* Avec un coefficient de corrélation intra-classe réaliste ($\rho \approx 0{,}4 - 0{,}5$) et une taille moyenne de grappe $m \approx 3{,}5$, l'effet de plan (*Design Effect*) s'établit à :
  $$\text{DEFF} = 1 + (m - 1)\rho \approx 1 + (3{,}5 - 1) \times 0{,}45 \approx 2{,}125$$
  L'effectif efficace équivalent est donc :
  $$n_{\text{eff}} = \frac{n_{\text{trips}}}{\text{DEFF}} \approx \frac{3\,500}{2{,}0} \approx 1{,}75 \times N \quad (\text{soit } 1\,750 \text{ à } 2\,000 \text{ déplacements indépendants équivalents})$$
* **Règle d'inférence :** C'est cet effectif efficace qui régit les intervalles de confiance. Tout calcul d'incertitude doit impérativement reposer sur un **bootstrap par agent (cluster bootstrap)** et non sur un intervalle binomial naïf calculé sur les déplacements isolés.

---

### 1.2 La précision de l'enquête de référence (EMC² 2023) est un plancher naturel
* L'Enquête Mobilité Certifiée CEREMA (EMC² 2023) du bassin de vie toulousain porte sur près de $16\,000$ habitants ($15\,775$ personnes interrogées dans $10\,783$ ménages ; [Résultats AUAT 2023](https://www.aua-toulouse.org/les-resultats-de-lenquete-2023-sur-les-mobilites-des-habitants-du-bassin-de-vie-toulousain/)).
* Après prise en compte des coefficients de pondération ($COEP$) et de l'effet de grappe ménage, la précision propre de l'enquête terrain sur une part modale agrégée se situe autour de **$\pm 0{,}3$ à $\pm 0{,}6$ point de pourcentage**.
* Descendre en dessous de cette borne côté simulation n'apporte aucun gain d'information scientifique : on comparerait une estimation simulée ultra-résolue à une cible empirique dont l'incertitude propre est déjà de $\pm 0{,}5\text{ pt}$.

---

### 1.3 Le résultat central est un biais structurel, non une différence marginale
* L'évaluation empirique des agents LLM révèle des écarts macroscopiques majeurs : sous-estimation systématique de la marche courte et sur-attraction disproportionnée du vélo ou des TC (écarts de l'ordre de **$8$ à $15$ points de pourcentage**).
* Un tel écart est détectable et réfutable avec une puissance statistique maximale dès quelques centaines d'agents.
* **Augmenter $N$ réduit la variance d'échantillonnage, jamais le biais de spécification comportementale.** Multiplier les agents par 10 ou 20 ne ferait que mesurer avec une précision infinitésimale un biais structurel qu'un échantillon de $1\,000$ agents démontre déjà sans ambiguïté.

---

## 2. Grille des Paliers de Taille d'Échantillon

Demi-largeur d'intervalle de confiance à $95\,\%$ ($IC_{95\%} = \pm 1{,}96 \sqrt{\frac{p(1-p)}{n_{\text{eff}}}}$), exprimée en points de pourcentage, avec $n_{\text{eff}} \approx 1{,}75 \times N$ :

| Nombre d'Agents ($N$) | Effectif efficace ($n_{\text{eff}}$) | Part $\approx 50\,\%$ (Voiture) | Part $\approx 25\,\%$ (Marche) | Part $\approx 5\,\%$ (Vélo) | Portée méthodologique & Ce que ça permet |
|---|---|---|---|---|---|
| **200 – 300** | 350 – 525 | $\pm 4{,}3\text{ pt}$ | $\pm 3{,}7\text{ pt}$ | $\pm 1{,}9\text{ pt}$ *(37 % rel.)* | **Pilote / Débogage de prompt.** Non publiable pour une validation macro. |
| **500** | 875 | $\pm 3{,}3\text{ pt}$ | $\pm 2{,}9\text{ pt}$ | $\pm 1{,}4\text{ pt}$ *(28 % rel.)* | **Strict minimum.** Suffit à établir un biais $\ge 8\text{ pt}$ sur les modes majeurs. Aucune analyse par sous-groupe. Le vélo reste imprécis en relatif, ce qui est gênant vu que c'est là que le biais se joue. |
| **1 000 – 1 500** | 1 750 – 2 600 | **$\pm 2{,}3\text{ pt}$** | **$\pm 2{,}0\text{ pt}$** | **$\pm 1{,}0\text{ pt}$** *(20 % rel.)* | **Minimum acceptable & défendable en revue.** Permet 3–4 sous-groupes larges (zone métro / 1re couronne / périphérie, motorisé / non). |
| **2 000 – 3 000** | 3 500 – 5 250 | $\pm 1{,}7\text{ pt}$ | $\pm 1{,}4\text{ pt}$ | $\pm 0{,}7\text{ pt}$ *(14 % rel.)* | **Taille correcte.** Un croisement à deux dimensions, un IC sur le vélo assez serré pour discuter la sur-attraction, marge pour 3 seeds. |
| **5 000 – 10 000** | 8 750 – 17 500 | $\pm 1{,}0$ à $\pm 0{,}7\text{ pt}$ | $\pm 0{,}9$ à $\pm 0{,}6\text{ pt}$ | $\pm 0{,}46$ à $\pm 0{,}32\text{ pt}$ | **Plus que bien.** Vous égalez la précision de l'EMC² et pouvez valider par secteur de tirage. |
| **$> 15\,000 – 20\,000$** | $> 26\,000$ | $< \pm 0{,}5\text{ pt}$ | $< \pm 0{,}4\text{ pt}$ | $< \pm 0{,}2\text{ pt}$ | **Trop grand pour une passe agrégée unique.** |

---

## 3. Pourquoi « Trop Grand » Commence Là ($> 10\,000$ agents)

Au-delà de $\approx 10\,000$ agents, trois choses se retournent contre le protocole :

1. **Le budget d'erreur cesse d'être dominé par l'échantillonnage :**  
   À partir de $\approx 2\,000$ agents, votre incertitude est de $\pm 1{,}5\text{ pt}$, alors que les écarts de spécification par rapport à l'EMC² dépassent facilement $3$ à $5\text{ pts}$ :
   * Hiérarchie du mode principal ;
   * Déplacements très courts déclarés ou non ;
   * Traitement de l'accompagnement ;
   * Périmètre interne ;
   * Âge minimum ($5\text{ ans}$ et plus dans l'EMC² 2023) ;
   * Jour moyen de semaine hors vacances.  
   *Payer de l'inférence pour resserrer un IC déjà petit devant un biais de définition non résolu est un mauvais arbitrage.*

2. **Les tests perdent leur sens :**  
   Un $\chi^2$ sur les parts modales rejette à n'importe quel $N$ ; à $20\,000$ agents il rejettera un écart de $0{,}4\text{ pt}$. Il faut passer aux **tailles d'effet avec IC** (MAE sur les parts, distance de variation totale / TVD, JSD) plutôt qu'aux p-values, ce qui rend l'inflation de $N$ inutile.

3. **Le budget est mieux dépensé ailleurs :**  
   Avec 5 conditions d'actualité, un placebo et 5 jours d'hystérésis, chaque agent coûte $\approx 25$ à $35$ jours-agents simulés. Un même budget d'inférence donne soit $10\,000$ agents en une passe, soit $2\,000$ agents $\times 5$ seeds, soit $2\,000$ agents $\times$ la matrice complète de scénarios. Ce que demandent les relecteurs sur un papier LLM-as-agent, c'est la **variance inter-seed et la sensibilité au prompt**, pas un $N$ spectaculaire.

---

## 4. Recommandation Opérationnelle

### 4.1 Pour le tableau de calage agrégé
* **$2\,000$ agents, 3 seeds.**  
* Incertitude à $\pm 1{,}5\text{ pt}$, séparation propre de l'erreur d'échantillonnage et de la stochasticité du LLM, et coût raisonnable.

### 4.2 Pour la partie régimes non tabulés (Actualités & Hystérésis)
* **Appariez.**  
* Les mêmes $500$ à $1\,000$ agents dans toutes les conditions, avec les mêmes seeds.
* Un contraste intra-agent (**McNemar / différence appariée**) élimine l'hétérogénéité individuelle et détecte un basculement de $3$ à $5\text{ pts}$ avec **3 à 10 fois moins d'agents** qu'un plan indépendant. C'est le levier le plus rentable de tout le design expérimental.

### 4.3 Deux points de méthode qui valent plus que du volume

1. **Échantillonnage stratifié dans la population eqasim :**  
   Échantillonnez de façon stratifiée dans la population eqasim, sur les strates mêmes qui serviront à la validation (**secteur géographique $\times$ classe d'âge $\times$ motorisation**), avec allocation proportionnelle. $1\,000$ agents stratifiés valent $\approx 2\,000$ tirés au hasard, et vous garantissez les effectifs par cellule. Visez $50$ déplacements minimum par cellule validée, $100$ pour discuter le vélo.
2. **Justification explicite de $N$ dans le papier par un calcul de précision ex ante :**  
   Justifiez $N$ explicitement dans le papier, par un calcul de précision *ex ante* plutôt que par la disponibilité budgétaire. Une phrase du type :  
   > *« $N = 1\,000$ (soit $n_{\text{eff}} \approx 1\,750$ déplacements efficaces après correction de grappe) donne une demi-largeur d'IC de $2{,}0\text{ pt}$ sur la part de la marche et $1{,}0\text{ pt}$ sur le vélo, à comparer aux biais de spécification observés ($> 8\text{ pts}$) »*  
   désarme la critique de taille d'échantillon bien mieux qu'un $N$ trois fois plus grand sans justification.

---

## 5. Références Utiles

* **AUAT (2023) :** *Les résultats de l'enquête 2023 sur les mobilités des habitants du bassin de vie toulousain (EMC²)*. [Lien AUAT](https://www.aua-toulouse.org/les-resultats-de-lenquete-2023-sur-les-mobilites-des-habitants-du-bassin-de-vie-toulousain/)
* **CEREMA :** *Fiche technique « Dimensionnement de l'échantillon et zonage »*. Elle donne les minima par secteur de tirage retenus pour l'enquête. Aligner la stratification sur leurs secteurs rend la comparaison désagrégée directement lisible.
