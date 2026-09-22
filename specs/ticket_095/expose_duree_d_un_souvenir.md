# La durée d'un souvenir : de quoi il s'agit, et ce qui reste à décider

Écrit le 2026-09-22 parce que les échanges précédents renvoyaient à des codes — E3, E4, C2, C3,
C6 — sans jamais dire ce qu'ils désignent. Ce texte se lit seul. Les codes y sont nommés une
fois, puis remplacés par ce qu'ils veulent dire.

| Code | Ce que c'est |
|---|---|
| **C2** | l'incident *crevaison* : 35 minutes de retard à vélo, réparation sur le trottoir |
| **C3** | l'incident *panne du réseau* : métro arrêté en tunnel, 45 minutes, correspondance ratée |
| **C6** | l'incident *panne moteur* : voiture en rade sur la voie rapide, 30 minutes de dépannage |
| **E3** | l'expérience « la durée d'un souvenir suit sa gravité » |
| **E4** | l'expérience « le plafond de 30 jours mord » |

---

## 1. Ce qu'est la durée d'un souvenir, en une page

Quand un agent vit un incident ou lit un article, une entrée est écrite dans sa mémoire. Cette
entrée porte une **gravité** entre 0 et 1. De la gravité découle tout le reste, par deux
formules et rien d'autre.

**La force de l'oubli.** `force = 2,8 × (1 + 6 × gravité)`, en jours, plafonnée à 30. C'est la
constante de temps d'une décroissance exponentielle : le poids du souvenir vaut
`exp(−Δt / force)`. La forme vient de MemoryBank (Zhong et al., 2024), qui reprend la courbe
d'oubli d'Ebbinghaus ; la modulation par la gravité vient de la mémoire émotionnelle
(McGaugh, 2004).

**La durée servie.** Le souvenir est présenté à l'agent tant que son poids dépasse un seuil de
service fixé à 0,35 — soit pendant `force × ln(1 / 0,35)`, c'est-à-dire `force × 1,0498` jours.
Cette durée est ensuite bornée entre 2 et 30 jours.

Ce que cela donne aux cinq échelons de l'échelle :

| Échelon | Gravité | Force | **Durée servie** |
|---|---|---|---|
| anodin | 0,10 | 4,48 j | **4,70 j** |
| notable | 0,30 | 7,84 j | **8,23 j** |
| génant | 0,50 | 11,20 j | **11,76 j** |
| grave | 0,75 | 15,40 j | **16,17 j** |
| marquant | 1,00 | 19,60 j | **20,58 j** |

⚠ **Ne pas confondre force et durée.** La force est la constante de temps, la durée est ce qu'on
observe. Elles diffèrent d'un facteur 1,0498 — assez peu pour qu'on les confonde, assez pour
qu'un chiffre cité soit faux. (Je les ai moi-même confondues dans le bilan d'hier ; c'est
corrigé partout.)

---

## 2. D'où vient la gravité — et ce qui a changé ce matin

Elle peut venir de deux endroits.

**La gravité mesurée.** La simulation sait ce qu'elle a fait subir : un retard, une
correspondance ratée, un incident réseau, un mode contraint. Chacun pèse, et la somme donne une
gravité. C'est objectif, gratuit, reproductible.

**La gravité jugée.** On montre le texte à l'agent et on lui demande ce que cela vaut pour lui,
sur les cinq échelons ci-dessus. C'est le seul moyen de qualifier un **article de presse**, qui
ne fait subir aucun retard et vaudrait donc zéro — c'est-à-dire exactement la valeur d'un trajet
parfait. Son silence passerait pour une absence d'effet alors qu'il ne mesurerait que la durée
de vie qu'on lui a donnée.

Jusqu'à hier, le code prenait **le maximum des deux** : l'agent pouvait aggraver, jamais
minorer. La décision de ce matin (« la gravité est celle de l'agent, seule ») a retiré ce
plancher. À la place, l'écart entre l'estimation et le fait mesuré est **journalisé**, et une
alarme se lève quand l'agent sous-estime de plus d'un échelon. On veut savoir, pas rattraper :
corriger en silence rétablirait le plancher sous un autre nom, et la campagne mesurerait de
nouveau la garde au lieu de mesurer l'agent.

---

## 3. La première expérience : « la durée suit la gravité »

**Ce qu'elle veut montrer.** Que la date à laquelle l'effet d'un incident s'éteint se déplace
avec sa gravité, et dans l'ordre prédit — pas qu'un souvenir s'efface, ce qui est trivial, mais
que la date de son extinction soit une **conséquence calculée** du modèle d'oubli plutôt qu'un
entier posé à côté.

**Comment elle s'y prend.** Trois campagnes identiques à un détail près : l'incident joué. La
crevaison, la panne moteur, la panne du réseau. Prédiction écrite **avant** le run : les trois
extinctions tombent dans l'ordre, autour de 8, 15 et 19 jours.

**Ce qui la falsifierait.** Des extinctions au même jour malgré des gravités différentes (le
calcul n'est pas branché), ou dans le désordre (la gravité ne mesure pas ce qu'on croit).

### Le problème que la décision de ce matin lui pose

Le protocole repose sur une prémisse : que la gravité se **déclare**, et que trois incidents de
sévérités déclarées distinctes produisent trois durées distinctes. Ce n'est plus vrai. Si
l'agent juge les trois « génant », les trois vivent le même temps, et le run ne falsifie rien —
il mesure le jugement.

### Le problème que ces trois incidents avaient déjà, avant toute décision

En recalculant leurs gravités mesurées telles qu'ils sont déclarés aujourd'hui :

| Incident | Gravité mesurée | Durée servie |
|---|---|---|
| crevaison (35 min) | 0,768 | 16,49 j |
| panne moteur (30 min) | 0,700 | 15,29 j |
| panne réseau (45 min + correspondance ratée) | 1,000 | 20,58 j |

La crevaison était censée être *le cas de gravité faible*. Elle arrive à un jour de la panne
moteur. La raison : la part du retard est **fortement concave** — 30 minutes valent 0,50, mais
45 n'en valent que 0,64 et 60 que 0,68. Passé une demi-heure, allonger le retard ne sépare
presque plus rien.

**Donc : les trois bras tels qu'ils sont écrits ne produiraient pas 8 / 15 / 19 jours, mais
16 / 15 / 21.** Deux courbes sur trois seraient indiscernables. Ce défaut est antérieur à la
décision de ce matin et indépendant d'elle.

---

## 4. La seconde expérience : « le plafond mord » — et pourquoi elle ne peut pas être jouée

Le code borne la durée servie à **30 jours**. Une borne qu'aucun run n'exerce est du code non
testé : on ne sait pas si elle s'applique, ni si elle est journalisée quand elle s'applique.
L'expérience devait donc produire un souvenir assez fort pour buter dessus.

**Le ticket demande « un bras avec un incident de gravité ≥ 1,30 ». C'est impossible.** La
gravité est bornée à 1,0 par construction. Un souvenir `marquant`, le maximum absolu, a une
force de 19,6 jours et une durée servie de **20,58 jours** — soit **dix jours sous le plafond**.
Aucune gravité, si grande soit-elle, ne peut faire mordre cette borne à l'écriture.

**Il n'y a qu'un chemin qui y mène : le rappel.** Chaque fois qu'un souvenir est servi à
l'agent, sa force gagne un jour, jusqu'à 30. Un souvenir souvent rappelé finit donc par atteindre
force 30, d'où une durée calculée de 31,5 jours, ramenée à 30 par le plafond. C'est exactement
le premier argument du ticket en faveur du plafond : *« un souvenir servi est un souvenir
rappelé »*.

Autrement dit : le plafond n'est pas une borne sur la **gravité**, c'est une borne sur
l'**entretien**. Il protège contre un souvenir qui se ravive indéfiniment parce qu'il est
consulté tous les jours, pas contre un souvenir initialement très grave.

---

## 5. Ce qui est décidé, et ce qui ne l'est pas

### Décidé le 2026-09-22 par l'auteur — la gravité est celle de l'agent

> « Je souhaite que ce soit l'agent qui décide de la gravité. Par contre, il faudrait s'assurer
> que quand l'agent décide, on soit au niveau de ce qu'on avait imaginé lors de l'analyse de
> l'article. Si l'agent a un jugement inapproprié, ça ne va pas passer. Donc ça, c'est quelque
> chose qu'il faudrait tester en amont, peut-être dans un test fonctionnel. En pratique, on
> laisse l'agent décider. Peut-être que selon le profil de la personne, la réponse ne sera pas
> systématiquement la même. »

Ce que cela tranche : la première expérience se rejoue **sur la gravité jugée**, pas sous
ablation du jugement. La prédiction ne porte plus sur une gravité déclarée avant le run mais sur
l'intensité que l'agent rend, lue dans la trace.

Ce que cela demande en plus, et qui n'existe pas encore : **un garde-fou en amont**, qui vérifie
avant toute campagne que le jugement de l'agent tombe dans la plage attendue à la lecture du
texte. Sans lui, un modèle qui répondrait « anodin » partout ferait tourner quarante jours de
campagne pour ne rien mesurer — ce qui a failli arriver ce matin, pour une autre raison.

⚠ **Ce garde-fou n'est pas encore spécifié.** Proposition à valider avant toute écriture de code
(cf. § 6).

### Non décidé — la seconde expérience

La question posée jusqu'ici (« faut-il jouer, réécrire ou retirer ? ») supposait qu'on avait
compris de quoi elle parle. Elle est reformulée au § 7.

---

## 6. Le garde-fou proposé — à valider

**Principe.** Une grille d'attendus, écrite par l'auteur **avant** de voir les réponses, qui
donne pour chaque texte la plage d'échelons acceptable. Non pas une valeur — une plage : deux
personnes raisonnables ne jugent pas identiquement un article sur des punaises.

**Forme envisagée** — un fichier de déclaration, à côté des textes :

```yaml
a13_punaises_metro:
  attendu: [anodin, notable]      # ce qu'on trouverait normal à la lecture
  modes_attendus: [public_transport]
  motif: "inquiétude sans conséquence pratique ; porte sur le métro et rien d'autre"
```

**Ce que le test fait.** Il interroge chaque texte avec plusieurs profils, et rend trois choses :

1. **Le taux hors plage.** Un jugement hors de l'attendu déclaré n'est pas une erreur en soi —
   c'est un signal. Au-delà d'un seuil, la campagne ne part pas.
2. **L'étalement entre textes.** Si tous les textes reçoivent le même échelon, la première
   expérience ne mesurera rien, quelle que soit la justesse de chaque jugement pris isolément.
3. **La part du profil.** Le même texte soumis à plusieurs personas : l'écart entre profils est
   **attendu** et doit être mesuré, pas éliminé. C'est même un résultat en soi — si un
   automobiliste et un usager du métro jugent différemment un article sur le métro, le
   dispositif fait ce qu'on lui demande.

**Coût.** Cinq textes × six profils = trente appels, quelques minutes. À rejouer à chaque
changement de modèle ou de gabarit, jamais pendant une campagne.

**Ce qu'il ne peut pas faire.** Dire si l'agent a *raison*. Il dit seulement si le dispositif
produit encore l'étalement sur lequel l'analyse des textes s'appuyait.

---

## 7. La question qui reste — reformulée

Le plafond de 30 jours existe dans le code. Aucune campagne ne l'a jamais atteint, et aucune ne
peut l'atteindre par la gravité seule : le maximum absolu plafonne à 20,6 jours.

Il ne peut être atteint que si un souvenir est **rappelé assez souvent** pour que son entretien
le pousse jusqu'à 30 jours de force.

**La question, en une phrase :** garde-t-on ce plafond, et si oui, veut-on une campagne qui
l'exerce — c'est-à-dire un run assez long pour qu'un souvenir très rappelé y bute — ou accepte-
t-on qu'il reste une borne de sûreté, exercée en test unitaire seulement et jamais observée dans
une campagne ?

Les trois réponses possibles, et ce que chacune coûte :

| Réponse | Ce qu'il faut faire | Ce que ça coûte |
|---|---|---|
| **L'exercer pour de vrai** | un run d'au moins 35 jours où un souvenir est rappelé presque tous les jours ; l'incident le plus grave, sur un agent dont les trajets le ramènent constamment au même endroit | une campagne longue, dont le seul objet est d'exercer une borne |
| **Le garder sans l'exercer** | rien, sinon dire dans l'article que c'est une borne de sûreté et non une durée observée | zéro — mais le plafond reste une affirmation, pas une mesure |
| **Le retirer** | supprimer la borne haute ; la durée maximale devient **31,5 jours**, fixée par le plafond de FORCE qui, lui, reste | rien — voir ci-dessous |

### Ce que le plafond de durée fait réellement : presque rien

Il y a **deux** plafonds de 30 dans le code, et ils ne bornent pas la même chose.

- `memoire__force_max_jours = 30` borne la **force**, donc l'entretien par le rappel. C'est un
  énoncé de modèle : consulter un souvenir ne peut pas le renforcer sans fin.
- `memoire__plafond_changement_jours = 30` borne la **durée servie**, qui est déjà dérivée de la
  force.

Or `durée = force × 1,0498`. Le plafond de force borne donc déjà la durée à **31,49 jours**. Le
plafond de durée ne peut mordre que dans la bande `force ∈ ]28,58 ; 30]`, et il y rabote **au
plus 1,49 jour**. Pour y entrer, il faut avoir été rappelé 9 fois (souvenir `marquant`), 14 fois
(`grave`) ou 25 fois (`anodin`).

**Conséquence : la crainte d'un souvenir qui durerait des années est déjà couverte, et pas par ce
plafond-là.** Aucun souvenir ne peut être servi plus de 31,5 jours, quoi qu'il arrive, parce que
sa force sature à 30. Le plafond de durée est un second verrou posé derrière le premier, qui
retire un jour et demi dans un cas rare — et qui coûte à l'article une phrase fausse : « entre 2
et 30 jours » donne pour bornes observées deux valeurs que rien n'a jamais atteintes.

### DÉCIDÉ LE 2026-09-22 — le plafond de durée passe à 50 jours et devient un témoin

`memoire__plafond_changement_jours : 30 → 50`. Comme la durée atteignable plafonne à 31,49 j
(conséquence du plafond de force), **cette borne ne peut plus mordre**. Elle est gardée plutôt
que supprimée pour une raison : elle se journalise quand elle mord (`DureeService.borne`). Le
jour où une ligne de journal la nommerait, c'est que la loi de décroissance ou le plafond de
force aurait bougé sans qu'on le remarque. C'est un témoin, pas un clamp.

Le mécanisme reste exercé en test : `test_A6` et `test_B8` abaissent le plafond pour vérifier
qu'il mord et qu'il se nomme.

**Le garde-fou passe du modèle au protocole : 50 jours d'horizon de run.** L'arrêt normal reste
l'extinction — `arret_sur_extinction.py` observe 7 jours VÉCUS après la sortie du dernier
souvenir de choc, puis rend la main ou arrête le run. Les 50 jours sont la butée, pas la durée
prévue.

⚠ **Cet arrêt n'est pas automatique aujourd'hui.** C'est un script de surveillance à lancer à
côté du run (`--arreter` pour qu'il coupe, `--souvenir-du AAAA-MM-JJ` très recommandé : sans
cette date, il attend que PLUS AUCUN souvenir de choc ne pèse, ce qui n'arrive qu'en toute fin
de run puisque l'agent en fabrique lui-même). Le câbler dans le lanceur de campagne est un
travail à part.

### Séparer le modèle de la fenêtre d'observation

Le plafond de durée mélange deux choses qui n'ont pas la même nature :

| | Nature | Où cela se décide |
|---|---|---|
| la loi de décroissance et son plafond de force | **modèle** — ce qu'on affirme sur la mémoire | dans le code, et défendable dans l'article |
| l'horizon du run | **protocole** — combien de jours on peut payer | dans la déclaration de l'expérience |

Un plafond sur la durée servie est un plafond de modèle qui se comporte comme un plafond
d'observation : quand il mord, la date d'extinction observée **est la borne**, pas la loi. On
mesure alors son propre garde-fou. C'est le motif que ce dépôt a déjà payé ailleurs — une
absence de mesure qui rend le score parfait.

Un horizon d'observation déclaré fait le contraire : un souvenir encore servi au dernier jour
est enregistré comme **censuré à droite** — « toujours vivant au jour H » — et non comme éteint.
C'est le traitement standard en analyse de survie, il se publie tel quel, et il rend les bras
comparables puisqu'ils partagent le même horizon.

Et il ouvre une mesure meilleure que la date d'extinction : sur trente jours, on ne compare plus
un point de croisement mais **les trajectoires de décroissance** entières. C'est plus robuste —
un croisement dépend d'un seuil, une pente non — et c'est exactement ce que « l'observer sur un
mois et voir que ça décroît » veut dire.

⚠ Quelle que soit la réponse, **le plancher de 2 jours est dans le même cas** : à gravité nulle
la durée vaut déjà 2,94 jours, donc le plancher ne peut jamais mordre non plus. Si l'article
cite « entre 2 et 30 jours », les deux bornes sont des bornes de sûreté et aucune n'a jamais été
observée. C'est à dire, ou à corriger.
