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

> **Ajout du 2026-09-18 : un axe 0 en amont du diptyque.** Le schéma ci-dessous reste exact pour
> les deux axes qu'il décrit, mais il leur manquait leur point zéro — la répétition à l'identique,
> qui ne change aucune entrée. Les deux axes se lisent contre lui, pas contre rien.

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

### Axe 0 : Réplicat à l'identique (non-déterminisme pur du fournisseur)

**Demande de l'auteur du 2026-09-18** : lancer **deux fois la même expérience avec exactement le
même modèle**, tout le reste égal, et comparer ce qui en sort — en premier lieu **les masses de
probabilité que le modèle attribue aux modes**, pas seulement le mode finalement retenu.

**Pourquoi cet axe passe AVANT l'axe 1.** Une graine ne change pas *rien* : elle change l'ordre des
sollicitations (`graine_ordre`), le tirage dans la distribution (`graine_tirage`) et le calendrier
(`graine_calendrier`). Une dispersion mesurée entre deux graines mélange donc le non-déterminisme du
fournisseur et l'aléa du dispositif, sans permettre de les séparer. L'axe 0 ne change **aucune**
entrée : tout ce qu'il mesure est imputable au modèle. Sans lui, l'axe 1 mesure une somme et
l'attribue à une seule de ses parts.

**Le dispositif est déjà en place, il n'y a rien à coder pour exécuter ce bras.**

- `experiences lancer` **sans** `--reprendre` crée une **nouvelle exécution** dans la même
  expérience (`cli.py:640`) : la définition n'est pas mutée, et le registre liste une ligne par
  exécution (`registre.py:135`), donc le réplicat s'affiche à côté de son aîné sans l'écraser.
- Le cache sémantique est **éteint par construction** dans ce chemin :
  `settings.cache.enabled = False` (`cli.py:583`, RG-2). Le second passage redemande donc
  réellement au modèle au lieu de resservir les réponses du premier.
- ⚠ **Avec `--reprendre`, le bras ne mesure rien** : les décisions déjà archivées sont resservies
  sans sollicitation (`runner.py:600`). C'est le mécanisme de survie au quota, pas un réplicat.
  Un réplicat se lance donc **à vide**, puis se reprend — avec `--reprendre` — sur *sa propre*
  exécution jusqu'à la couvrir entièrement.
- ⚠ **Une exécution ARRÊTÉE est close et immuable (E19), donc irreprenable.** `--reprendre` la
  refuse : « rien à reprendre […] clôturée (arretee) : immuable ». Se reprennent les exécutions
  non clôturées — en pause, épuisée, interrompue, ou en cours sans runner. Constaté le
  2026-09-21 : l'exécution `2026-09-20_18_55_16` du réplicat, arrêtée à 120/3 299, a dû être
  abandonnée. **Une pause se reprend, un arrêt se paie** : sur un bras à ≈ 2 500 sollicitations,
  la différence est de plusieurs fenêtres de quota. À décider avant d'arrêter, pas après.

**Le témoin de déterminisme du dispositif existe déjà, et il est exact.**
`exp_rf_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_nosim` porte **deux** exécutions
(`2026-09-16_13_53_48` et `2026-09-16_15_52_59`) : composite **4,09**, hors choix unique **5,81**,
L1 **38,33** — identiques au centième des deux côtés. La chaîne (jeu, offre, chaînage, scoreur)
reproduit donc à l'identique quand le décideur est déterministe. **Tout écart observé sur le
réplicat LLM appartient au modèle**, et cette égalité est la mesure de référence de l'axe.

**Bras à exécuter** (un seul, et c'est le moins cher du ticket) :

| Paramètre | Valeur |
|---|---|
| Modèle | `gemini-3.5-flash-lite` (instances `google_gemini35_key1`, `key2`) |
| Prompt | `prompt_expert_05` |
| Jeu | `population_1000_AAMAS_v6_20260316_EN_c` (sceau `412efada…31db6`) |
| Température | 0,0 · `top_p` 1,0 |
| Graines | `graine_ordre` 42, `graine_tirage` 42, `graine_calendrier` 42 — **inchangées** |
| Exécution de référence | `2026-09-16_22_20_25` (composite 4,86 · hors choix unique 6,86 · L1 58,48) |
| Coût | ≈ 2 500 sollicitations fraîches (mesuré sur les bras sans reprise : 2 506 et 2 643), soit ≈ 2,5 jours de quota à 1 000 RPD |
| **Définition prête** | `exp_gemini-35-fl_proexp05_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_t0_nosim_2` — vérifiée le 2026-09-21 : `nommage.segments()` la recalcule au nom de son aîné, donc aucun écart d'identité. `vehicule_chaine`, `verrou_retour` et `troncature_15` y sont écrits explicitement, pour que l'égalité se lise sans exécuter de code. Aucune exécution : elle se lance **à vide**. |
| Estimation | 3 161 sollicitations · ≈ 3,2 fenêtres de quota · ≈ 6 300 s de calcul utile |

> **Fausse piste écartée le 2026-09-21.** Un réplicat avait été lancé sur
> `…_jeu-20260316_EN_t0_nosim_2`, c'est-à-dire sur l'**ancien** jeu — celui dont 797 premiers
> déplacements portent l'offre et la météo du 17 mars (ticket 088). Il a été arrêté à 120/3 299.
> Son appariement contre l'aîné correspondant est chiffrable mais **hors substrat publié** : il
> ne se pose pas à côté des composites du chapitre 6. Le bras de la phase 0 est celui du jeu
> corrigé, et lui seul.

> **Caducité corrigée.** Le rectificatif du 2026-09-15 demandait ce rejeu sur `pe04`
> (`expert_gem_3.8_v2`). Cette variante a été **supprimée le 2026-09-17** — ni servable par son nom
> canonique, ni par son ancien nom, et toute expérience qui la désigne échoue. Le réplicat porte
> donc sur `prompt_expert_05`, seule survivante de la lignée.

**Trois niveaux de comparaison, du plus fin au plus grossier.** Tous se calculent sur des fichiers
**déjà produits** : aucun code de production n'est touché.

1. **Les masses** — c'est la mesure demandée. `decisions.jsonl` porte, pour chaque décision, le
   vecteur `distribution` sur les six modes canoniques et `poids_presentes` sur les seules options
   offertes ; l'appariement se fait sur `(person_id, activity_id)`. À chiffrer : part des décisions
   dont la distribution est identique, L1 moyenne et L1 maximale entre les deux vecteurs, part des
   décisions dont l'argmax bascule, et distribution des écarts (une queue épaisse sur peu de
   décisions ne se lit pas comme un bruit diffus sur toutes).
2. **Le mode retenu** — taux de bascule individuel. À masses égales et `graine_tirage` égale, le
   mode tiré **doit** être identique : une bascule sans écart de masse est un défaut du dispositif,
   pas du modèle, et se traite comme tel.
3. **Le macro** — composite, lecture hors choix unique, L1, et parts modales *attendues* contre
   *tirées* (`scripts/analysis/mode_probabilities.py`). C'est le seul niveau que le § 6.5 publie ;
   les deux autres disent s'il est stable pour de bonnes raisons.

**Outillage — livré le 2026-09-21.** `scripts/analysis/appariement_executions.py`, CLI
`make apparier A=<exécution> B=<exécution> [JSON=…] [TOUT=1]`. Il appelle `registre.comparer`
en garde, apparie sur `(person_id, activity_id)` et rend les trois niveaux ci-dessus. Deux
points de conception qui ne sont pas des détails :

- **les masses se lisent dans `poids_presentes`, jamais dans `distribution`.** Ce dernier agrège
  sur les six modes canoniques et écrase deux options d'un même mode : sur les 120 premières
  décisions du réplicat, il annonçait 5 bascules « à masses égales » contre UNE pour
  `poids_presentes`. Les quatre autres étaient un artefact d'agrégation. Comme ce cas se lit
  comme un défaut du dispositif, le mauvais vecteur invente un bug ;
- **seules les décisions à offre identique et décideur sollicité des deux côtés sont chiffrées.**
  Les divergences héritées du déplacement précédent (`cascade_amont`) sont écartées et comptées
  à part — 11 sur 120 dans le relevé ci-dessus.

Alarme sur une couverture `communes / max(|A|, |B|)` sous 80 %, pour ne pas rééditer le
`moves.csv` tronqué du 2026-09-15.

**Garde de publication.** Deux exécutions du même bras coexistant dans le registre, le chapitre doit
continuer à **nommer l'exécution** qu'il publie : sans cela, un réplicat peut devenir en silence « la »
mesure du bras au prochain passage d'un script qui prend la plus récente.

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

### Phase 0 : Réplicat à l'identique (à faire en premier, un seul bras)
- **Objectif** : isoler le non-déterminisme propre au fournisseur, en ne changeant rien du tout — même modèle, même prompt, même jeu, mêmes trois graines.
- **Volume** : 1 run, ≈ 2 500 sollicitations fraîches, ≈ 2,5 jours de quota à 1 000 RPD.
- **Commande** : `experiences lancer --experience exp_gemini-35-fl_proexp05_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_t0_nosim` **sans** `--reprendre` (une reprise resservirait les décisions archivées et ne mesurerait rien), puis reprises successives de cette seconde exécution jusqu'à couverture complète.
- **Résultat attendu** : part des décisions à masses identiques, L1 entre distributions appariées, taux de bascule du mode retenu, et écart macro contre l'exécution `2026-09-16_22_20_25`.
- **Ce qu'il conditionne** : si le réplicat pur diverge déjà de l'ordre du point de composite, la dispersion inter-graines de la phase 1 ne mesure plus ce qu'elle prétend mesurer, et l'ordre de grandeur publié au § 6.5 doit le dire.

### Phase 1 : Variabilité stochastique multi-graines (Priorité immédiate)
- **Objectif** : Exécuter 4 nouvelles graines (`seeds = [123, 456, 789, 2026]`) pour compléter le run de référence 42. **Sur la cohorte v6 et le jeu corrigé** (`population_1000_AAMAS_v6_20260316_EN_c`) : la v5 est en archive froide depuis le 2026-09-14 et inaccessible au code, et le substrat de mesure a changé de date (ticket 088).
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
- [Ticket 068 — Variabilité au sein d'un groupe homogène](ticket_068_variabilite_decision_groupe_homogene.md), **option D** : son « bruit stochastique intrinsèque » ($\tau > 0$ contre $\tau = 0$ sur une même instance) est le même phénomène que l'axe 0, mesuré à l'échelle d'un clone et à température variable. L'axe 0 le mesure à $\tau = 0$ sur la cohorte entière : il faut que l'un cite le chiffre de l'autre plutôt que de le remesurer.

---

## 7. Critères d'Acceptation

- [ ] **Le réplicat à l'identique (axe 0) est exécuté** et archivé comme SECONDE exécution de l'expérience de référence `exp_gemini-35-fl_proexp05_…_EN_c_t0_nosim`, sans `--reprendre` au lancement.
- [ ] **Le pairage exécution-contre-exécution est écrit et versionné**, et rend les trois niveaux : masses (`distribution`, `poids_presentes` appariés sur `(person_id, activity_id)`), mode retenu, macro.
- [ ] **Les masses sont chiffrées** : part des décisions à distribution identique, L1 moyenne et maximale entre distributions appariées, part des argmax qui basculent.
- [ ] Toute bascule de mode retenu SANS écart de masse est instruite comme un défaut du dispositif (à `graine_tirage` égale, le tirage doit être reproductible) et non portée au compte du modèle.
- [ ] Les 4 runs de graines alternatives sur `population_1000_AAMAS_v6_20260316_EN_c` sont exécutés et archivés avec succès (la v5 est en archive froide).
- [ ] Au moins 2 populations synthétiques répliquées conformes au protocole territorial sont générées et exécutées.
- [ ] Le script d'analyse statistique de variabilité et de décomposition de variance (ANOVA / $\eta^2$) est développé et versionné.
- [ ] Les métriques de reproductibilité (moyenne, écart-type, IC 95%, taux de bascule individuel, $\kappa$) sont calculées et documentées.
- [ ] Les résultats sont intégrés dans le Chapitre 6 (§ 6.3) du manuscrit avec leurs représentations graphiques (boxplots de dispersion).
- [ ] Une conclusion claire est formulée quantifiant la part exacte du hasard dans les performances observées.
