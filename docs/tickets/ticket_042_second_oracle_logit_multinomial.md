# Ticket 042 — Le second oracle : un logit multinomial, et un score qui l'utilise

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité.
>
> Spécification : [`specs/score_composite_deux_oracles.md`](../../specs/score_composite_deux_oracles.md).
> Livré le 2026-09-10, blocs A/B/C mesurés sur le run épinglé, bloc C2 en attente d'une
> paire A/B déjà payée.

## Le problème, en un paragraphe

L'article annonçait deux références tabulaires — « the multinomial logit and the supervised
oracle » (C1, parité d'information) et « Level 3: the tabular references » (C2, ablation) —
et le dépôt n'en avait qu'une. `exp_03a_multinomial_logit` désignait
`scripts/progedo_logit/mnl_model.json`, **fichier absent** : le marqueur
`\todo{xx.y | exp_03a}` n'avait aucune valeur possible, et « l'oracle est un plafond de
référence » restait une hypothèse. Le composite, lui, ne mesurait qu'une chose : l'écart des
parts modales à l'enquête.

Ce n'est pas un manque cosmétique. Notre H0 se joue sur une **L1 de parts modales**, et c'est
l'axe exact où la littérature donne l'avantage au logit : Martín-Baos et al. (2023) mesurent
XGBoost au-dessus du MNL de 2,2 à 5,6 points sur l'exactitude désagrégée, mais **moins bon
sur les parts agrégées et les indicateurs comportementaux** ; Zhao et al. (2020) qualifient
les élasticités des modèles à arbres de *behaviorally unreasonable*. Le plafond pouvait donc
être le logit, et il n'y avait aucun moyen de le savoir.

## Ce qui a été livré

**1. Le second oracle, à parité stricte (voie 1).** `make logit` estime une régression
logistique multinomiale pondérée sur les 21 variables du `feature_spec.json`, et la parité
avec le booster est vraie **par construction** : même parquet, même colonne `split` étanche
au ménage, même `sample_weight` (COEP), même `encode_features`, mêmes métriques (module
partagé `mode_choice_eval.py`). La régularisation est choisie en validation croisée à 5 plis
groupée par ménage **dans le train** — le split test n'est jamais lu pour régler.

Mesuré sur le split test scellé de 13 045 trajets :

| | CEL | GMPCA | Exactitude | L1 masse | L1 mode élu |
|---|---|---|---|---|---|
| Booster LightGBM | 0,5402 | 0,583 | **0,785** | **0,0269** | **0,0730** |
| Logit multinomial | 0,5954 | 0,551 | 0,766 | 0,0286 | 0,1003 |

**Le booster reste devant sur les deux familles d'indicateurs**, y compris les parts
agrégées. C'est un résultat, pas un détail : l'inversion annoncée par Martín-Baos ne se
produit pas ici, et « oracle = plafond de référence » cesse d'être une hypothèse. L'écart
d'exactitude est de 1,9 point, du même ordre que les 2 à 3 points que Hillel (2021) obtient
sur échantillonnage groupé, et bien loin des 20 à 35 points de la littérature ancienne.

**2. Un composite à deux oracles.** `make bi-oracle` produit trois blocs :

| Bloc | Grandeur | Valeur (run épinglé) |
|---|---|---|
| A — fidélité EMC² | composite `emd_jsd`, inchangé | **16,16** |
| B — accord désagrégé au logit | JSD(prompt, MNL) rapportée à la JSD inter-oracles | **899 %** |
| C1 — sens de variation | part des transitions de distance dont le signe contredit l'arbitre | **5,0 %** (1/20) |
| C2 — élasticités A/B | signes d'élasticité d'arc | **non mesuré** |

`s_B = 899` se lit : sur les 2 584 décisions comparables, le prompt est **neuf fois plus
loin du logit que le booster ne l'est** (0,1847 bit contre 0,0205). Le dénominateur est ce
qui rend le chiffre lisible sans arbitrer une constante — c'est la distance entre les deux
oracles, mesurée sur les mêmes décisions.

**3. Poids nuls, et c'est un choix.** `w_B = w_C = 0` (manifeste `score.bi_oracle`) : les
deux termes sont calculés, journalisés et publiés, mais ne sélectionnent aucun prompt. Un
prompt choisi sous un terme mesuré contre un modèle serait ajusté à ce modèle, pas à
l'enquête. Le composite restant linéaire, une promotion ultérieure s'applique
rétroactivement par simple addition de `w·s`, sans repayer un appel LLM.

## Les trois pièges que la mesure a révélés

**1. Le plancher de la divergence de Kullback-Leibler décidait du score.** 1 923 des 2 584
décisions déclenchent le plancher `ε`, et 1 109 distributions du prompt sont quasi
dégénérées (un mode au-dessus de 0,999). Le rapport de KL vaut alors 2 338 % — un chiffre qui
mesure `ε` autant que les décisions. La grandeur de tête est donc la **JSD** : définie sur
les zéros, bornée par 1 bit, sans constante. Le rapport de KL reste publié en second, avec
le compte des décisions où le plancher a joué, parce que c'est lui qui est comparable à la
littérature.

**2. Une offre à un seul mode est un accord parfait gratuit.** 665 décisions du run n'ont
qu'un itinéraire (méthode « Un seul itinéraire disponible ») : le prompt n'a jamais été
interrogé, et les trois décideurs sont forcés sur le même mode. Les inclure aurait fait
*baisser* le score sans qu'aucun accord n'ait été mesuré — la vacuité prise pour de la
perfection, motif récurrent de ce dépôt. Elles sont écartées et comptées, des deux côtés.

**3. La modalité « absente » d'une catégorielle n'est pas toujours identifiée.** Un logit ne
route pas les valeurs manquantes ; l'encodage leur donne une modalité `__missing__`. Mais si
le train n'en contient aucune — c'est le cas de `socioprofessional_class`, absente de 498
décisions du run parce que la population synthétique porte des modalités que le spec
d'enquête ne connaît pas — son coefficient reste nul, et la valeur absente se comporte comme
la **modalité de référence**. L'artefact publie donc `missing_category_support` : quelle
modalité `__missing__` est identifiée, et par combien de lignes.

## Ce qui n'est pas fait, et pourquoi

- **Ni valeur du temps ni disposition à payer.** Le contrat des 21 variables ne porte aucune
  variable de coût, ni de niveau de service par mode. Ce modèle est une logistique
  multinomiale sur caractéristiques individuelles, **pas** un modèle d'utilité aléatoire au
  sens de McFadden, et l'article doit le dire en une phrase. La voie 2 (utilités par
  alternative alimentées par `mode_skims.parquet`, qui existe déjà : 29 212 paires OD ×
  tranche horaire, quatre modes routés) romprait la parité d'information et fera l'objet d'un
  ticket distinct si un relecteur exige la WTP.
- **Le bloc C2 n'est pas mesuré.** Une élasticité du prompt exige des décisions rejouées,
  donc des appels LLM. Le module n'en fait aucun : il exploite une paire A/B **déjà payée**
  quand on lui en désigne une (`--ab-variable` + les deux bras). Les A/B de
  `car_availability` conviendraient — la variable est dans le contrat — mais leur store n'est
  pas sur cette machine.
- **La parité avec l'agent n'est pas totale, et c'est à déclarer.** L'agent LLM reçoit
  jusqu'à six itinéraires **avec leurs durées** ; les deux oracles n'ont ni temps ni coût par
  mode. La parité porte sur les 21 variables de contexte, pas sur l'information de niveau de
  service — et c'est l'agent qui en a davantage. C'est la première chose qu'un relecteur
  éprouvera sur « informational parity ».

## Suites

- Ligne de statut `exp_03a` dans `docs/paper/methode/experience_plan/experiments.yaml` :
  le `model_path` désigne désormais un fichier qui existe.
- Point 4.12 de `docs/paper/article/relecture/01_introduction.md` : les six métriques
  demandées sont produites ; reste à écrire la phrase de limite (« pas un RUM ») dans le
  chapitre 2.
- Mesurer `s_B` sur deux ou trois runs de plus avant d'envisager de promouvoir `w_B` :
  un terme à 899 % pèserait, à poids 0,1, dix fois l'écart que la calibration cherche à
  mesurer.
