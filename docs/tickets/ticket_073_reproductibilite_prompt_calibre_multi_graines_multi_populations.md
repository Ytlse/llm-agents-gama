# Ticket 073 — Reproductibilité et robustesse stochastique du prompt calibré : variabilité inter-graines et sensibilité à l'échantillonnage de population

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.  
> Ouvert le 2026-09-14.  
>  
> **Catégorie** : Expériences & Cognition (🧠) / Modélisation Statistique (📊)  
> **Statut initial** : `à faire`  
>  
> **Touche potentiellement** : Chapitre 6 (§ 6.2 Ablation & Prompt Engineering, § 6.3 Robustesse & Sensibilité du prompt calibré), Chapitre 8 (§ 8.2 Menaces sur la validité interne), et Annexes méthodologiques (Défense de réplication pour le Rebuttal AAMAS 2027).

---

## 1. Contexte & Problématique Scientifique (AAMAS)

Les campagnes de mesure récentes conduites avec le modèle **Gemini 3.5** (`gemini-3.5-flash-lite`) associé au **prompt expert calibré** (`expert_gem_3.8_v2` dans le gabarit `itinary_multi_agent`) ont produit des scores de fidélité macro-distributionnelle exceptionnels :
- **Composite EMD-JSD** : **$5{,}3452$** (contre $8{,}94$ pour le prompt minimal neutre).
- **Composite hors choix uniques** : **$8{,}0910$**.
- En apparence, ces valeurs placent le modèle LLM devant les oracles tabulaires supervisés en chaîne (LightGBM : $10{,}4569$).

> **Rectificatif du 2026-09-15 ([ticket 080](ticket_080_idee_directrice_du_chapitre_6_et_impact_sur_le_papier.md)).**
> Les trois chiffres ci-dessus proviennent d'une exécution dont le `moves.csv` était tronqué à
> 274 lignes (arrêt forcé puis reprise à froid) : ils portent sur 198 décisions et 85 personas.
> Rescoré sur les 3 299 décisions, le bras vaut **6,17** de composite et **12,53** hors choix
> unique ; le même prompt sur la cohorte v6 (`prompt_expert_04`) vaut **5,30** et **10,39** —
> **derrière** les quatre familles tabulaires en chaîne. L'écart au LightGBM v6 est de
> +0,98 [−0,26 ; +2,39] en différence appariée. Le protocole ci-dessous garde tout son sens ;
> sa cible change : mesurer une dispersion propre au LLM face à un écart de l'ordre du point,
> non expliquer une victoire. Deux ajouts : (1) la première exécution à faire est un **rejeu à
> l'identique** de `pe04` sur v6, même graine, pour isoler le non-déterminisme pur ; (2) l'axe 2
> pèse plus que la cinquième graine, parce que l'écart-type apparié d'échantillonnage de cohorte
> (≈ 0,7 à N = 1 000) ne baisse pas avec les graines. Le jeu de référence n'est plus v5 mais v6.

Cependant, une analyse épistémologique et méthodologique rigoureuse met en évidence une vulnérabilité critique pour une soumission de premier plan à **AAMAS 2027** :
> **L'ensemble de ces mesures spectaculaires repose à ce jour sur un seul jeu de population (`population_1000_AAMAS_v5`, $N = 1\,000$ agents) et sur une seule graine aléatoire (`seed = 42`).**

Deux interrogations scientifiques majeures se posent alors :
1. **La loterie stochastique (*Lucky Seed*)** : Le résultat remarquable est-il le fruit d'un alignement probabiliste fortuit (ordre de présentation des agents dans le batch, tirage résiduel d'échantillonnage, ordonnancement des contextes) qui ne se reproduirait pas avec d'autres graines ?
2. **Le sur-apprentissage de cohorte (*Cohort Overfitting*)** : Les consignes cognitives du prompt expert capturent-elles de véritables lois comportementales universelles du territoire toulousain, ou sont-elles inconsciemment sur-adaptées aux particularités statistiques d'un échantillon unique de 1 000 individus ?
3. **La décomposition de la variance** : Quelle est la part de variabilité imputable au mécanisme intrinsèque du LLM (*seed variance*) versus celle imputable à l'échantillonnage de la population synthétique (*sample variance*) ?

Ce ticket a pour objet de concevoir, d'exécuter et d'analyser le protocole expérimental complet permettant de répondre de façon formelle et chiffrée à ces questions.

---

## 2. Diptyque Expérimental : Les Deux Axes de Sensibilité

Pour isoler rigoureusement les sources d'aléa sans confondre leurs effets, l'étude s'articule autour de deux axes orthogonaux :

```
                  ┌────────────────────────────────────────────────────────┐
                  │                 ESPACE DES ÉVALUATIONS                 │
                  └────────────────────────────────────────────────────────┘
                                              │
                    ┌─────────────────────────┴─────────────────────────┐
                    ▼                                                   ▼
       ┌─────────────────────────┐                         ┌─────────────────────────┐
       │         AXE 1           │                         │         AXE 2           │
       │ Variabilité Multi-Seeds │                         │ Multi-Populations       │
       │    (Iso-Population)     │                         │      (Iso-Seed)         │
       └─────────────────────────┘                         └─────────────────────────┘
                    │                                                   │
     • Cohorte v5 scellée FIXE                           • Modèle & Prompt v2 FIXES
     • 5 graines aléatoires indépendantes                 • 3 à 5 cohortes distinctes
       (42, 123, 456, 789, 2026)                           (échantillons indépendants EMC2)
     • Mesure de la dispersion résiduelle                • Mesure de la généralisation
       du LLM et du churn individuel                       territoriale hors échantillon
                    │                                                   │
                    └─────────────────────────┬─────────────────────────┘
                                              ▼
                               ┌─────────────────────────────┐
                               │        DÉCOMPOSITION        │
                               │    DE VARIANCE (ANOVA)      │
                               │   Part du hasard LLM vs     │
                               │   Part d'échantillonnage    │
                               └─────────────────────────────┘
```

---

### Axe 1 : Variabilité inter-graines à iso-population (Stochasticité intrinsèque du modèle & du pipeline)

* **Condition expérimentale** :
  - **Population** : `population_1000_AAMAS_v5` (scellée, 1 000 agents, 3 299 déplacements bruts, 3 154 décisions attendues).
  - **Décideur** : `gemini-3.5-flash-lite`, température $\tau = 0{,}0$, prompt calibré `expert_gem_3.8_v2`.
  - **Graines testées ($S = 5$)** :
    - `seed_1 = 42` (run de référence existant).
    - `seed_2 = 123`
    - `seed_3 = 456`
    - `seed_4 = 789`
    - `seed_5 = 2026`
  - Les graines gouvernent l'ensemble des sources stochastiques du framework : `graine_ordre` (ordre des sollicitations), `graine_tirage` (choix aléatoire au sein des distributions probabilistes le cas échéant), et `graine_calendrier`.

* **Indicateurs mesurés** :
  1. **Dispersion macro-statistique** :
     - Moyenne ($\mu$), écart-type ($\sigma$) et intervalle de confiance à 95 % ($IC_{95\%}$) du score composite EMD-JSD global et hors choix uniques.
     - Écart-type des parts modales pour chaque mode principal : $\sigma(\text{voiture})$, $\sigma(\text{marche})$, $\sigma(\text{TC})$, $\sigma(\text{vélo})$.
  2. **Stabilité micro-décisionnelle (Cohérence individuelle)** :
     - **Taux de bascule (*Churn rate*)** : Proportion de décisions où le mode retenu diverge pour le même individu et le même trajet entre deux graines $s_i$ et $s_j$.
     - **Matrice de concordance** : Accord inter-graines mesuré par le coefficient $\kappa$ de Fleiss ou l'alpha de Krippendorff sur les 3 154 décisions appariées.
  3. **Test de significativité face au prompt factuel neutre** :
     - Test de Student apparié ou test non paramétrique de Wilcoxon confirmant que même sous la graine la plus défavorable, le prompt calibré surpasse significativement le prompt minimal ($p < 0{,}001$).

---

### Axe 2 : Sensibilité inter-populations à graines contrôlées (Généralisation hors échantillon)

* **Condition expérimentale** :
  - **Décideur & Prompt** : `gemini-3.5-flash-lite`, $\tau = 0{,}0$, `expert_gem_3.8_v2`.
  - **Graine fixée** : `seed = 42` (puis vérification croisée sur une seconde graine).
  - **Cohortes testées ($K = 3$ à $5$)** :
    - Cohorte 1 : `population_1000_AAMAS_v5` (cohorte de calibration historique).
    - Cohortes 2 à 4 : Nouveaux échantillons synthétiques de $N = 1\,000$ agents distincts, générés à partir des données de calage territorial (EMC2 / Cerema / Haute-Garonne) selon le générateur certifié du projet, avec les mêmes contraintes marginales (structure d'âge, couronnes communales, motorisation du ménage, détention du permis et accès vélo).

* **Indicateurs mesurés** :
  1. **Préservation du score de fidélité territoriale** :
     - Le score composite EMD-JSD reste-t-il stable dans la fourchette cible ($5{,}0$ à $6{,}5$) sur les nouvelles populations, ou observe-t-on une dégradation vers le score du prompt neutre ($8{,}94$) ?
  2. **Uniformité des erreurs par strate** :
     - Calcul des distances $L_1$ par strate (couronne de résidence, tranche de distance, motif) pour vérifier que le profil d'erreur est invariant et ne compense pas artificiellement des dérives divergentes.
  3. **Mesure de l'overfitting de prompt** :
     - Écart de généralisation : $\Delta_{\text{gen}} = |\overline{\text{Score}}_{\text{nouvelles\_pop}} - \text{Score}_{\text{v5}}|$. Un $\Delta_{\text{gen}} < 1{,}0$ point validera l'absence de sur-apprentissage de la cohorte.

---

## 3. Décomposition Statistique de la Variance (ANOVA)

Afin de répondre précisément à la demande (« *quelle est la part de hasard dans ces résultats ?* »), les résultats feront l'objet d'une **analyse de variance à deux facteurs (Two-Way ANOVA)** sur le plan factoriel croisé ou quasi-complet :

$$Y_{ijk} = \mu + \alpha_i (\text{Population}_i) + \beta_j (\text{Graine}_j) + (\alpha\beta)_{ij} + \epsilon_{ijk}$$

Où $Y$ représente la métrique d'intérêt (composite EMD-JSD ou écart à la part modale cible).

* **Décomposition de la somme des carrés** :
  $$SS_{\text{Total}} = SS_{\text{Population}} + SS_{\text{Graine}} + SS_{\text{Interaction}} + SS_{\text{Résiduelle}}$$

* **Quantification de la part de variance ($\eta^2$)** :
  - **Part imputable à l'aléa LLM/pipeline** : $\eta^2_{\text{graine}} = \frac{SS_{\text{Graine}}}{SS_{\text{Total}}}$.
  - **Part imputable à l'échantillonnage démographique** : $\eta^2_{\text{pop}} = \frac{SS_{\text{Population}}}{SS_{\text{Total}}}$.
  - **Part résiduelle / bruit inexpliqué** : $\eta^2_{\text{résiduelle}} = \frac{SS_{\text{Résiduelle}}}{SS_{\text{Total}}}$.

Cette formalisation mathématique fournit une réponse chiffrée, irréfutable et prête pour l'article AAMAS pour démontrer si les gains du prompt calibré relèvent d'un signal systématique robuste ou de fluctuations d'échantillonnage.

---

## 4. Stratégie d'Exécution & Économie de Moyens

L'exécution d'un run complet sur 1 000 agents représentant environ 3 150 sollicitations du LLM (soit ~1,5 million de tokens en entrée et ~300 000 tokens en sortie par run), le plan expérimental est échelonné en **deux phases prioritaires** pour respecter les quotas et optimiser les temps de calcul :

### Phase 1 : Variabilité stochastique multi-graines (Priorité immédiate)
- **Objectif** : Exécuter 4 nouvelles graines sur la cohorte v5 (`seeds = [123, 456, 789, 2026]`) pour compléter le run de référence 42.
- **Volume** : 4 runs $\times$ 3 154 décisions $\approx$ 12 600 requêtes.
- **Outillage** : Mode découplé sans simulateur (`_nosim`) via le pipeline de parallélisation d'Antigravity ou la gateway unifiée.
- **Résultat attendu** : Barres d'erreur $\mu \pm \sigma$ et matrice de churn sur la cohorte v5.

### Phase 2 : Validation croisée multi-populations (Second temps)
- **Objectif** : Exécuter 2 à 3 cohortes alternatives scellées avec la graine de référence (42), plus un contrôle croisé avec une seconde graine.
- **Volume** : 3 à 4 runs additionnels.
- **Résultat attendu** : Mesure de l'écart de généralisation $\Delta_{\text{gen}}$ et tableau ANOVA complet.

---

## 5. Livrables Attendus

1. **Expériences archivées dans `data/experiences/`** :
   - Traces, `scores.json`, `synthese.json` et `decisions.jsonl` horodatés pour chaque couple `(population, graine)`.
2. **Script d'analyse statistique et de synthèse** :
   - `scripts/experiments/eval_reproducibility_calibrated_prompt.py` (calcul automatique des moyennes, écarts-types, matrices de churn, ANOVA et export LaTeX/Markdown).
3. **Mise à jour du Manuscrit AAMAS** :
   - **Chapitre 6 (§ 6.3)** : Insertion d'une sous-section dédiée intitulée *« Stochastic Robustness and Population Sensitivity of Calibrated Prompting »*, accompagnée du tableau de dispersion $\mu \pm \sigma$ et de boxplots comparatifs.
   - **Rebuttal Defence Pack** : Argumentaire pré-rédigé démontrant la robustesse statistique face aux critiques de « cherry-picking » ou de « lucky seed ».

---

## 6. Liens & Articulation avec les Autres Chantiers

- [Ticket 055 — Benchmark multi-modèles et variabilité inter-graines sous prompt neutre](ticket_055_benchmark_multimodeles_et_variabilite.md) : Porte sur la variabilité sous prompt factuel neutre (Chapitre 5), tandis que le ticket 073 porte spécifiquement sur le prompt expert calibré (Chapitre 6).
- [Ticket 056 — Audit et réflexion sur les résultats du prompt expert](ticket_056_audit_et_reflexion_resultats_prompt_expert.md) : Porte sur l'intégrité de la chaîne de calcul et l'ablation v2 vs v3 ; le ticket 073 en constitue le prolongement empirique et statistique naturel.
- [Ticket 068 — Mesure de la variabilité décisionnelle au sein d'un groupe homogène](ticket_068_variabilite_decision_groupe_homogene.md) : Analyse la dispersion micro au sein de groupes d'agents identiques (clones), alors que le 073 traite de la reproductibilité macro et de l'échantillonnage de la population globale.

---

## 7. Critères d'Acceptation

- [ ] Les 4 runs de graines alternatives sur `population_1000_AAMAS_v5` sont exécutés et archivés avec succès.
- [ ] Au moins 2 populations synthétiques répliquées conformes au protocole territorial sont générées et exécutées.
- [ ] Le script d'analyse statistique de variabilité et de décomposition de variance (ANOVA / $\eta^2$) est développé et versionné.
- [ ] Les métriques de reproductibilité (moyenne, écart-type, IC 95%, taux de bascule individuel, $\kappa$) sont calculées et documentées.
- [ ] Les résultats sont intégrés dans le Chapitre 6 (§ 6.3) du manuscrit avec leurs représentations graphiques (boxplots de dispersion).
- [ ] Une conclusion claire est formulée quantifiant la part exacte du hasard dans les performances observées.
