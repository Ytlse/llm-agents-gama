# Ticket 048 — Le calendrier de consolidation, l'échelle d'oubli, et qui paie les réflexions

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ouvert le 2026-09-11 à la demande de l'auteur, **rien n'est lancé**.
>
> Ce ticket est le **préalable bloquant** de l'architecture mémoire décrite dans
> [`docs/arch/memory-stm-ltm.md`](../arch/memory-stm-ltm.md), **partie III**.
> Il ne construit aucun des quatre lots de cette architecture : il tranche les trois points
> qui touchent au **protocole de mesure**, et sans lesquels les lots suivants produiraient des
> chiffres ininterprétables.
>
> **Bloque** l'expérience d'hystérésis et tout chiffre qui s'en réclame.

## Le fait

Trois défauts de calendrier et de paramétrage, tous mesurés sur le dépôt et non supposés.

### 1. Le déclenchement de la consolidation dépend du nombre de déplacements

> ⚠ **Correction du 2026-09-11, après relecture de l'auteur.** La première version de ce ticket
> affirmait que 70,6 % des agent-jours ne franchissent pas le seuil de réflexion, sur la foi du
> run archivé `2026-07-08_08_54`. **Ce chiffre ne tient pas.** Ce run mesure 1,80 déplacement par
> agent-jour, là où la cohorte scellée en prévoit 3,30 par persona et 3,69 par persona mobile. Il
> est antérieur à la correction de chaîne cyclique du ticket 045, qui a ajouté 37 % de
> déplacements, et il sous-exécute en outre son propre plan. Le constat ci-dessous est reconstruit
> sur la source de vérité, et il est **nettement plus faible** que ce que la première version
> annonçait.

La source de vérité est le manifeste de la cohorte scellée, non un run.

| Grandeur | Cohorte v5 | Référence EMC² 2023 |
|---|---|---|
| Déplacements par persona | 3,299 | 3,53 |
| Déplacements par persona **mobile** | 3,69 | 3,95 |
| Part d'immobiles | 10,6 % | 10,6 % |

Sur le seul run portant de vraies observations GAMA, une entrée de mémoire courte sur six est un
plan de déplacement, les cinq autres étant des observations de marche, d'arrivée, de transport et
d'attente : **6,34 entrées par déplacement**. Un agent mobile produit donc de l'ordre de
**23 entrées par jour**, et franchit le seuil de dix environ **deux fois par jour**.

**Ce qui subsiste du constat, et qui reste vrai :** le moment de la consolidation n'est pas
maîtrisé, il est une **fonction du nombre de déplacements de l'agent**. Un agent à un seul
déplacement produit six entrées et ne consolide pas dans la journée ; un agent à quatre
déplacements consolide deux fois. La position d'un choc par rapport à la consolidation varie
donc d'un agent à l'autre et d'un scénario à l'autre, sans que rien ne la contrôle. Comme la
décision ne lit **que** la mémoire longue — la mémoire courte n'est jamais lue au moment de
décider —, un souvenir non consolidé n'existe pas pour la décision.

C'est une variable non contrôlée de l'expérience d'hystérésis, et non plus le défaut massif
annoncé d'abord. Le remède demandé par l'auteur, une réflexion par jour simulé au minimum, reste
justifié : il rend le calendrier **déterministe** au lieu de le laisser dépendre de la mobilité
de chaque agent, et il protège la queue basse de la distribution.

**À mesurer avant de trancher le régime.** Le taux d'entrées par agent-jour n'est mesurable
aujourd'hui sur aucun run exploitable : le seul run avec observations est antérieur à la cohorte
v5, et les runs récents sont des exécutions hors simulateur, qui ne portent aucune observation
et donc exactement une entrée par déplacement. Une mesure sur un run courant avec GAMA est un
préalable au choix du régime.

### 2. La normalisation min-max rend le paramètre d'oubli presque inopérant

Les trois composantes du classement sont normalisées min-max **à l'intérieur du lot de
candidats**. Le souvenir le plus récent vaut donc toujours exactement 1, le plus ancien
exactement 0, quel que soit l'écart réel entre eux. Comme la décroissance est monotone,
l'ordre par ancienneté est **invariant** au paramètre d'oubli : seul l'espacement bouge.

| Ancienneté du souvenir | Apport au score, λ = 0,357 | Apport au score, λ = 0,13 |
|---|---|---|
| 0 jour | 0,300 | 0,300 |
| 1 jour | 0,202 | 0,239 |
| 3 jours | 0,085 | 0,138 |
| 7 jours | 0,000 | 0,000 |

Le critère de réfutation de l'hypothèse — « l'effet mémoire tombe si diviser λ par trois ne
déplace pas la courbe » — peut donc se déclencher pour une raison **purement technique**.

### 3. Le paramètre d'oubli déclaré dans les expériences n'est branché sur rien

`memory_decay_lambda` et `memory_horizon_days`, déclarés dans
`docs/paper/methode/experience_plan/experiments.yaml`, ne sont lus par **aucun code**. Le
bras de sensibilité à λ divisé par trois n'est aujourd'hui pas exécutable.

## Décisions de l'auteur, 2026-09-11

- **Point 1 — consolidation.** Une réflexion **par jour simulé au minimum**, indépendamment du
  remplissage du tampon. L'idéal visé est **une réflexion par déplacement**, sous réserve du
  coût.
- **Point 2 — normalisation.** La normalisation min-max par composante est **abandonnée**. Les
  composantes entrent en valeur absolue sur [0, 1].
- **Point 3 — paramètre d'oubli.** Proposition retenue pour arbitrage, ci-dessous.

## Ce qui est proposé pour le paramètre d'oubli

Le paramètre disparaît au profit d'une **constante de temps exprimée en jours**,
`long_term_retrieval__force_base_jours`, celle du lot 1 de la partie III de
[`memory-stm-ltm.md`](../arch/memory-stm-ltm.md).

- **Conversion immédiate** depuis les valeurs déjà déclarées, `S = 1 / λ` : le bras principal
  passe à 2,5 jours, le bras de sensibilité à 7,7 jours.
- **Défaut à 2,8 jours**, qui reproduit *exactement* la décroissance en service, une base de
  0,7 par jour étant une constante de temps de 2,80 jours et une demi-vie de 1,94 jour. Un
  défaut plus court accélérerait l'oubli en silence et rendrait inattribuable tout écart
  mesuré ensuite.
- **Un paramètre en jours se lit et se discute.** Le bras de sensibilité s'énonce alors « un
  souvenir ordinaire dure trois fois plus longtemps », qui est une hypothèse défendable devant
  un relecteur, là où « la base de l'exponentielle passe de 0,7 à 0,88 » n'en est pas une.

## Le coût d'une réflexion par déplacement, et qui peut la payer

Volume pour mille agents sur cinq jours simulés, à 3 299 déplacements par jour, 894 agents
mobiles et 6,34 entrées de mémoire par déplacement. Le tableau compte **tous** les appels de
mémoire : les réflexions courtes, et l'auto-réflexion longue durée, qui part tous les trois
jours et représente 894 appels sur cet horizon, identiques dans tous les régimes.

| Régime | Réflexions courtes | Appels mémoire | **Appels mémoire par déplacement** | Total avec les décisions | Écart |
|---|---|---|---|---|---|
| Actuel, seuil volumétrique de 10 | ≈ 10 460 | ≈ 11 350 | **0,69** | ≈ 27 850 | référence |
| **Plancher journalier — régime retenu** | 10 460 à 14 930 | 11 350 à 15 820 | **0,69 à 0,96** | 27 850 à 32 320 | **0 à +16 %** |
| Une par jour simulé, seule | 4 470 | 5 360 | **0,33** | 21 860 | −22 % |
| Une par déplacement | 16 495 | 17 390 | **1,05** | 33 880 | +22 % |

La colonne à retenir est celle des **appels mémoire par déplacement**, parce qu'elle est la
seule qui ne dépende ni de la taille de la population ni de la durée de l'horizon. Elle se lit
directement : aujourd'hui la mémoire coûte environ **deux tiers d'appel par déplacement**, et
le régime le plus ambitieux la porte à **un appel par déplacement**, soit un doublement de la
part mémoire et un cinquième de plus sur l'ensemble de la campagne.

Trois lectures, dont deux inattendues.

**Le régime par jour, pris seul, coûte moins cher qu'aujourd'hui.** Le seuil volumétrique
déclenche déjà environ deux consolidations quotidiennes pour un agent mobile, donc imposer
exactement une réflexion par jour serait un *ralentissement*. Ce n'est pas ce que demande
l'auteur.

**Le plancher journalier, qui est le régime retenu, est presque gratuit.** Le seuil reste, et
une réflexion part en fin de journée simulée seulement si le tampon n'est pas vide et n'a pas
déjà déclenché. Le surcoût ne concerne donc que les agents à faible mobilité, et la fourchette
ci-dessus est large faute de connaître leur part exacte : la borne haute suppose que *tous* les
agents ont besoin du plancher chaque jour, ce qui est certainement faux. La valeur réelle est
proche de la borne basse, et c'est l'objet de l'action 2.

**Le régime par déplacement coûte un cinquième de plus sur la campagne**, et non la moitié
comme la première version de ce ticket l'annonçait. Sous ce régime il y a exactement une
réflexion courte par décision, donc la mémoire pèse la moitié du volume total — et c'est ce qui
rend la question du modèle légitime.

### La piste des modèles locaux, sous condition de mesure

Huit modèles LM Studio sont déjà déclarés dans `config/llm_gateway/providers.yaml`, hors
rotation depuis le 2026-09-08. Deux raisons de fond rendent la réflexion **candidate**, là où
la décision ne l'est pas.

1. **La nature de la tâche.** Une réflexion est un résumé et une extraction sous schéma
   contraint. C'est le registre où un petit modèle local est le plus compétitif. Une décision
   est une répartition de préférence entre itinéraires : c'est *la grandeur que l'article
   mesure*, et elle ne se délègue pas.
2. **Le volume.** Sous le régime par déplacement, déplacer les réflexions vers le local divise
   par deux la consommation distante, sans toucher à ce qui est mesuré.

**Mais la réflexion produit la mémoire, qui nourrit la décision.** Une réflexion dégradée
dégrade la décision indirectement. Le principe de non-dégradation scientifique du dépôt
interdit donc d'admettre un modèle local sur une intuition. L'admission doit être **mesurée**,
et elle est mesurable sans le moindre run de simulation.

**Protocole d'admission, sur jeux gelés.** Rejouer *N* prompts de réflexion réels extraits d'un
run archivé, à travers le modèle de référence et le candidat local, puis comparer :

- taux de sorties conformes au schéma, et taux de relances ;
- nombre de concepts extraits, et accord sur le **niveau nommé** attribué ;
- accord sur la normalisation des quatre axes ;
- **et surtout l'effet en aval** : injecter les deux mémoires produites dans le *même* prompt de
  décision, et comparer les distributions de probabilité modale.

Le candidat est admis si et seulement si l'écart en aval tient dans la marge d'équivalence.
Sinon il est écarté, et la réflexion reste distante. Aucune admission « parce que c'est moins
cher ».

Contraintes connues, issues de la mise en service du 2026-09-08 : LM Studio refuse
`json_object` et exige `json_schema` ; un seul modèle local est chargé à la fois, donc la
cascade ne provoque pas de chargement à la volée ; le contexte par défaut est de 4 096 jetons,
à porter à 16 384 via `make lmstudio-charger`.

## Ce qu'il faut faire

1. **Déclencher une réflexion par jour simulé au minimum.** Le seuil volumétrique devient une
   borne haute et non une condition : une réflexion part de toute façon en fin de journée
   simulée, tampon non vide, quel que soit son remplissage. L'échéance EDF reste le réveil de
   l'agent. Vérifier que la garantie « avant le réveil » tient encore sous ce volume, et que
   la contre-pression prédictive reste faisable.
2. **Mesurer le taux réel d'entrées par agent-jour** sur un run courant avec GAMA et cohorte v5,
   aucun run exploitable ne le permettant aujourd'hui, puis trancher entre plancher journalier et
   régime par déplacement au vu du coût mesuré et non estimé.
3. **Supprimer la normalisation min-max** des composantes du classement, et rejouer les mesures
   déjà publiées qui en dépendent.
4. **Remplacer le paramètre d'oubli** par une constante de temps en jours, la brancher
   réellement, convertir les déclarations d'expériences existantes, et faire de même pour
   l'horizon de mémoire.
5. **Instruire la piste locale** selon le protocole d'admission ci-dessus, sur jeux gelés, et
   publier le tableau d'écart. Conclusion possible : aucun candidat admis.

## Hors périmètre

Les quatre lots de la partie III de [`memory-stm-ltm.md`](../arch/memory-stm-ltm.md) — gravité,
récupération structurée et embedding francophone, consolidation des concepts, mémoire noyau. Ils
dépendent de ce ticket, ils n'en font pas partie.

## Ce que ce ticket bloque

L'expérience d'hystérésis et tout chiffre qui s'en réclame. Tant que le point 1 n'est pas
livré, la position du choc dans le calendrier de consolidation est une variable non contrôlée
de l'expérience ; tant que le point 2 ne l'est pas, le bras de sensibilité ne mesure pas ce
qu'il prétend mesurer.
