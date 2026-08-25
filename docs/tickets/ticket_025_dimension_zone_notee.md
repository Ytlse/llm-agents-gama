# Ticket 025 — Noter la dimension « lieu de résidence », ou assumer de ne pas la noter

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source
> de vérité.
>
> **Nature du ticket** : *décision de mesure*, pas correction. Il ne corrige aucun bug : il
> demande de trancher si la dimension la plus mal ajustée du modèle doit entrer dans le
> score qui pilote la calibration.
>
> ## ⚠ AVERTISSEMENT — À LIRE AVANT DE DEMANDER L'IMPLÉMENTATION
>
> Ce ticket **n'est pas un réglage**. Le déplacement de niveau qu'il provoque est **dix à
> vingt fois plus grand** que l'effet qu'on chercherait à lire :
>
> | | aujourd'hui | zone notée à `w = 0,3` | zone notée à `w = 0,5` |
> |---|---:|---:|---:|
> | composite (`v7`/train) | **25,69** | **38,07** | **46,32** |
>
> Conséquences directes, chiffrées :
>
> - **728 évaluations stockées** dans `prompt_calibration/calibration_results/` (601 nœuds
>   de prompt distincts) portent un composite calculé sans ce terme. Elles ne sont plus
>   comparables à un composite qui l'inclut ;
> - les **quatre lignes** du registre `avancement.yaml` — dont les gains du ticket 013,
>   `−4,52` et `−2,17` — deviennent incomparables aux suivantes ;
> - la page de synthèse, le tableau de bord et toute lecture historique du score changent
>   de repère **sans que le modèle ait changé** ;
> - le **cache Shapley** et les ablations reposent sur une loss stable : la changer les
>   invalide (cf. la règle « garder le modèle d'éval stable ») ;
> - la **calibration change d'objectif**. Le L1 de la zone vaut 43 points contre 6 à 12
>   pour les dimensions notées : ce terme **dominerait** la loss, et l'optimiseur
>   sacrifierait volontiers l'âge, le motif ou la distance pour gagner sur la zone. Ce
>   n'est pas une hypothèse à écarter, c'est le comportement attendu d'un optimiseur.
>
> **Rien de tout cela ne demande d'appel LLM** — les décisions sont stockées, tout se
> recalcule — mais tout demande de **rebaseliner** ce qui a déjà été publié. Ne demandez
> l'implémentation qu'en sachant que la réponse à « le score s'est-il amélioré depuis
> juillet ? » devra être reconstruite.

## Le constat

La cible existe. `cerema_values.yaml` publie les parts modales par couronne :

| couronne | voiture | marche | TC | vélo |
|---|---:|---:|---:|---:|
| Toulouse | 31 % | 39 % | 21 % | 6 % |
| 1ʳᵉ couronne | 64 % | 21 % | 8 % | 4 % |
| 2ᵉ couronne | 74 % | 15 % | 7 % | 2 % |
| 3ᵉ couronne | 71 % | 18 % | 6 % | 2 % |

Le scoring, lui, l'écarte : `lieu_residence` et `type_logement` sont les deux seules
dimensions marquées `scored: False` dans
[`frames.py`](../../scripts/synthesis/frames.py). Elles sont **affichées, pas notées**.

**La raison est bonne** : le composite de la page doit être *exactement* la loss que le
moteur de calibration optimise — même classe `L1Composite`, mêmes poids. Or ces poids sont
`global 1,0 · âge 0,5 · occupation 0,5 · motif 0,5 · genre 0,3 · distance 0,3`. Aucun terme
de zone. Afficher un composite qui noterait une dimension que l'optimiseur ignore
donnerait un score que rien n'a jamais cherché à améliorer.

**Et c'est exactement le problème.** Sur `v7`/train :

| dimension | L1 | notée |
|---|---:|---|
| global | 6,29 | ✅ |
| genre | 6,49 | ✅ |
| motif | 7,92 | ✅ |
| âge | 8,96 | ✅ |
| occupation | 10,63 | ✅ |
| distance | 12,32 | ✅ |
| **lieu de résidence** | **43,38** | ❌ |

Le désajustement le plus grave du modèle est celui que personne ne note — donc celui que la
calibration n'a jamais eu de raison de réduire. C'est le motif « une dimension non mesurée
est une dimension qui ne peut pas échouer », en grand format.

## Le préalable qui n'est pas négociable

**Noter cette dimension avant d'avoir une population conforme au périmètre serait noter du
bruit.** Mesuré sur `v7` (930 personas) :

| couronne | personas | communes couvertes |
|---|---:|---|
| Toulouse | 376 | 1 / 1 |
| 1ʳᵉ couronne | 365 | 56 / 69 |
| 2ᵉ couronne | 135 | 34 / 108 |
| 3ᵉ couronne | **54** | **20 / 275** |

La 3ᵉ couronne pèse 15,4 % du cadrage et 5,8 % de la masse mesurée ; sa strate tient dans
18 agents sur les splits retenus. Noter une dimension dont un quart du poids repose sur
18 personas ferait piloter la calibration par le bruit d'échantillonnage.

→ **Ce ticket dépend du [ticket 026](ticket_026_population_conforme_perimetre.md)** (population
conforme au périmètre EMC²). Dans l'autre ordre, on optimiserait contre une géographie
tronquée.

## Les trois options, et celle que je recommande

| # | Option | Ce qu'elle coûte |
|---|---|---|
| A | **Ajouter le terme au composite** (`w = 0,3` ou `0,5`) | Rebaseline complet : 728 évaluations, 4 lignes de registre, cache Shapley, objectif de calibration déplacé |
| B | **Publier un second composite** à côté — `composite_etendu` — sans toucher au composite comparable | Aucun historique cassé, aucune loss modifiée. Deux chiffres à expliquer, et la calibration continue d'ignorer la zone |
| C | **Ne rien noter et l'écrire** : la dimension reste affichée, et la limite est publiée avec son amplitude | Gratuit. La zone reste hors de l'optimisation, ce qui doit alors figurer dans les limites de la publication |

**Je recommande B, puis A une fois le ticket 026 livré et mesuré.** B rend le chiffre
visible et opposable sans casser un seul historique ; il permet de *voir* ce que la
calibration laisserait sur la table avant de décider de l'y engager. A reste la bonne
réponse à terme — un score qui ignore la géographie ne mesure pas ce que le projet prétend
mesurer — mais il se paie une fois, proprement, sur une population conforme.

## Les axes à instruire

| # | Axe | Question |
|---|---|---|
| C1 | **Poids** | `0,3` (comme genre/distance) ou `0,5` (comme âge/motif/occupation) ? Le L1 de la zone étant 3 à 6 fois celui des autres, même `0,3` en fait le premier terme de la loss |
| C2 | **Renormalisation** | Ajouter un terme ou redistribuer la somme des poids à 2,6 constante ? La seconde voie garde le niveau du composite comparable mais dilue toutes les dimensions existantes |
| C3 | **Effectif minimal** | Une strate sous `STRATUM_MIN_PERSONAS` est déjà exclue par `_dim_mean_measured`. Faut-il un seuil spécifique à la zone, plus exigeant ? |
| C4 | **Hors périmètre** | Il n'a aucune cible. Reste-t-il hors des strates (ticket 021) ou devient-il une modalité à cible nulle ? |
| C5 | **Rétro-application** | Re-scorer les 728 évaluations stockées (possible sans appel LLM, mais les records des jeux gelés ne portent pas la couronne : il faut la joindre) ou repartir d'une base neuve et le dire ? |
| C6 | **`type_logement`** | Même situation (`scored: False`, ticket 019). Le traiter dans le même geste ou séparément ? |

## Ce qu'il faut savoir avant de commencer

- **Les records des jeux gelés ne portent pas la couronne.** Elle se joint par `agent_id`
  à la population, comme le fait
  [`measure_couronne_v7.py`](../../scripts/synthesis/measure_couronne_v7.py). Noter la
  dimension dans le moteur demande donc que l'évaluateur reçoive cette métadonnée — un
  changement de contrat de `build_decision_records`, pas seulement un poids en plus.
- **Aucun appel LLM n'est nécessaire**, à aucune étape : `evals.decisions` conserve les
  décisions brutes. C'est du re-scoring, pas de la ré-évaluation.
- **Le composite ne bouge pas « un peu ».** Il saute de 12 à 21 points. Toute lecture qui
  compare un avant et un après doit être refaite dans le même monde.

## Sources

- [ticket 021](ticket_021_couronne_residence_post_traitement.md) — la correction du
  classement, et la mesure `+2,11 pt` qui a rendu ce ticket-ci visible.
- [`docs/traces/2026-08-24_couronne_v7/`](../traces/2026-08-24_couronne_v7/README.md) — les
  L1 par strate, et le piège de pondération.
- [`docs/arch/score-synthesis.md`](../arch/score-synthesis.md) — la formule du composite,
  ses poids, et la règle « la loss n'est pas réimplémentée ».
- [`prompt_calibration/PROTOCOLE.md`](../../prompt_calibration/PROTOCOLE.md) — le lieu de
  résidence est un des axes de la contribution T3 de l'article.
