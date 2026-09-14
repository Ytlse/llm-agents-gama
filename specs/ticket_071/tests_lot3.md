# Ticket 071, lot 3 — Spécification des tests fonctionnels

> Écrite le 2026-09-14, **avant le code du lot 3**. Même convention qu'aux lots 1 et 2.
>
> ⚠ **Quatre points sont apparus en rédigeant ce document** (§ 7). L'un est un **conflit direct
> avec une règle du lot 1**, un autre **ajoute une exception** à la règle de non-exclusion du
> lot 2. Mes résolutions sont proposées et appliquées ; elles sont écrites pour être contestées.
>
> ✅ **Écrit et vérifié le 2026-09-14.** `test_071_lot3_concepts.py` (32 cas) et
> `test_071_lot2_rappel.py` (44 cas) honorent ce document et `tests_lot2.md`, livré sans les
> siens. Validation par l'échec vérifiée : rebrancher la décroissance d'horloge sur les
> concepts casse D1, D2 et D3.
>
> ⚠ **Un cinquième défaut est apparu en écrivant les tests** — § 7.5. Il rendait la trace
> datée que l'expérience d'hystérésis cherche **jamais écrite** pour un concept peu observé.

---

## 1. Ce que le lot 3 change

Aujourd'hui, chaque réflexion émet jusqu'à cinq concepts, chacun écrit comme une entrée neuve.
Rien ne les relie. Au bout d'un mois un agent porte des centaines de concepts, dont beaucoup
répètent la même chose et certains se contredisent — et c'est le prompt de décision qui arbitre,
à chaque décision, à ses frais.

| | Aujourd'hui | Après le lot 3 |
|---|---|---|
| Concepts | empilés, jamais corrigés | **panier**, quatre opérations, compteurs |
| Oubli d'un concept | l'horloge, comme une entrée brute | la **contradiction**, jamais l'horloge |
| Concept contredit | reste servi indéfiniment | **cesse d'être servi**, sans être supprimé |
| Concept dépassé | n'existe pas | **marqué et daté**, jamais supprimé |

---

## 2. Le panier

```
panier = (axe_objet, axe_motif)        # correspondance exacte sur une métadonnée indexée
```

Le couple mode-motif désigne un **petit ensemble de candidats**, pas un emplacement unique. Une
identité unique par couple condamnerait l'agent à une seule pensée par mode et par motif, chaque
concept nouveau détruisant le précédent.

| # | Cas | Attendu |
|---|---|---|
| A1 | trois concepts `cycling` / `work` | même panier, tous trois conservés |
| A2 | un concept `cycling` / `work` et un `car` / `work` | paniers distincts |
| A3 | un concept sans mode (`any`) | panier `(None, motif)` — il existe, il n'est pas perdu |
| A4 | la présélection ne balaie pas l'index | aucune requête vectorielle, correspondance exacte en RAM |
| A5 | le panier est stable d'un run repris à l'autre | il se calcule sur les axes ÉCRITS, jamais recalculés |

---

## 3. Les quatre opérations

Le modèle voit les concepts du panier dans l'appel de réflexion **qui a déjà lieu**, et désigne
celui qu'il met à jour — ou déclare n'en mettre aucun. Coût marginal nul, aucun seuil arbitraire
à calibrer. C'est le principe de Mem0 : le modèle choisit l'opération.

| Opération | Effet attendu |
|---|---|
| `creer` | nouveau concept, `observations = 1`, aucun compteur touché ailleurs |
| `confirmer` | `observations += 1` sur la cible, **rien de neuf n'est écrit**, force renforcée |
| `preciser` | le contenu de la cible est remplacé, **compteurs et historique conservés** |
| `contredire` | `contre_exemples += 1` sur la cible, **et** le nouveau concept est écrit |

| # | Cas | Attendu |
|---|---|---|
| B1 | `creer` | une entrée de plus, `observations = 1`, `contre_exemples = 0` |
| B2 | `confirmer` sur une cible | **aucune entrée de plus**, `observations` passe de 1 à 2 |
| B3 | `preciser` | aucune entrée de plus, contenu remplacé, `observations` inchangé |
| B4 | `contredire` | une entrée de plus **et** `contre_exemples` de la cible passe à 1 |
| B5 | opération inconnue | repli sur `creer`, plus un WARNING nommant la valeur reçue |
| B6 | cible inconnue ou absente | repli sur `creer`, plus un WARNING — jamais une exception |
| B7 | cible appartenant à un autre agent | refusée, repli sur `creer` — un agent ne touche pas la mémoire d'un autre |
| B8 | **aucune suppression, jamais** | après cent contradictions, le concept est toujours là |

---

## 4. Confiance, service et dépassement

```
confiance = (observations + 1) / (observations + contre_exemples + 2)      # Laplace (1814)
```

| # | Cas | `obs` / `contre` | Confiance | Servi ? | Dépassé ? |
|---|---|---|---|---|---|
| C1 | jamais observé | 0 / 0 | 0,50 | **oui** (le seuil est strict) | non |
| C2 | confirmé une fois | 1 / 0 | 0,67 | oui | non |
| C3 | contredit une fois | 1 / 1 | 0,50 | oui | non |
| C4 | contredit deux fois | 1 / 2 | 0,40 | **non** | non — il faut trois contre-exemples |
| C5 | contredit trois fois | 1 / 3 | 0,33 | non | **oui** |
| C6 | trois contradictions, vingt confirmations | 20 / 3 | 0,84 | oui | **non** |
| C7 | une majorité sur deux observations | 0 / 1 | 0,33 | non | non |

C6 et C7 sont les deux cas que la double condition existe pour écarter : ni trois contradictions
contre vingt confirmations, ni une majorité sur deux observations.

| # | Cas | Attendu |
|---|---|---|
| C8 | un concept dépassé | marqué **et daté**, présent dans les métadonnées, absent du rappel |
| C9 | la date de dépassement | en temps **simulé**, jamais l'horloge machine |
| C10 | un concept dépassé redevient majoritaire | il n'est **pas** ressuscité automatiquement — le marquage est daté et reste |

---

## 5. Ce qui s'oublie au temps, et ce qui ne s'oublie pas

```
score_temps(entrée)  = exp(-Δt / force)   si épisodique
score_temps(concept) = confiance          si sémantique
```

| # | Cas | Attendu |
|---|---|---|
| D1 | un concept de dix jours jamais contredit | poids **inchangé** — sous le régime uniforme il tombait à 0,028 |
| D2 | un concept de deux ans jamais contredit | poids inchangé |
| D3 | un concept contredit | perd son poids **quelle que soit** son ancienneté |
| D4 | une entrée épisodique | garde la décroissance exponentielle du lot 1 |
| D5 | deux concepts de confiance égale | la date de dernière observation les départage, **sans** effacer |

**D1 est le test qui justifie tout le lot.** Qu'une ligne sature les jours de pluie ne devient
pas faux parce que dix jours ont passé.

---

## 6. Instrumentation

| # | Cas | Attendu |
|---|---|---|
| E1 | compteur d'opérations par type | journalisé à chaque cycle de réflexion |
| E2 | aucun `contredire` sur plus de deux jours simulés **alors que** des contre-exemples existent | `[ALARME]` sur front montant — signe d'un modèle qui confirme tout |
| E3 | retour à la normale | l'alarme se referme |
| E4 | part des concepts hors service | journalisée — c'est l'observable de l'hystérésis |

---

## 7. Ce qui est apparu en rédigeant ce document

### 7.1 ⚠ `confirmer` voudrait rafraîchir l'horodatage — le lot 1 l'interdit

La spécification écrit, pour `confirmer` : « `observations += 1`, **horodatage rafraîchi**, force
renforcée ». Or le lot 1 a posé une règle explicite et testée : `timestamp` est l'heure de
l'**événement**, il s'affiche dans le prompt, et le faire glisser réécrirait l'histoire de
l'agent — il croirait que sa chute à vélo a eu lieu hier.

*Résolution appliquée* : un champ **`derniere_observation`** distinct, en temps simulé. Il sert
au départage de D5 et ne touche ni au texte du prompt, ni aux filtres d'âge. Le `timestamp` ne
bouge pas, et le test C8 du lot 1 continue de le vérifier.

### 7.2 ⚠ Le panier ne peut pas être calculé après coup

Le panier se calcule sur `(axe_objet, axe_motif)` du concept **nouveau**. Mais les concepts
candidats doivent être montrés au modèle **avant** qu'il n'écrive le sien. On ne peut pas
attendre sa réponse pour choisir quoi lui montrer, et un second appel est exclu par la contrainte
transverse du ticket : aucun lot ne coûte d'appel supplémentaire.

*Résolution appliquée* : les paniers montrés sont ceux des **entrées consommées du jour** —
les modes et les motifs que l'agent a réellement empruntés. C'est exactement la bonne portée :
il réfléchit sur sa journée, les concepts qu'il pourrait corriger sont ceux qui parlent de cette
journée.

### 7.3 ⚠ Le panier « sans mode » peut devenir le fourre-tout

Un concept qui ne parle d'aucun mode porte `axe_objet = None` (réponse `any` du modèle). Le
panier `(None, motif)` rassemblerait alors tous les concepts généraux d'un même motif, et le
montrer entier gonflerait le prompt.

*Résolution appliquée* : **au plus cinq concepts montrés par panier**, les plus confiants
d'abord, la dernière observation départageant. Les concepts hors service n'y figurent pas — il
n'y a pas lieu de proposer au modèle de corriger ce qu'on ne lui sert plus.

### 7.4 ⚠ La règle de non-exclusion du lot 2 gagne une exception

Le lot 2 a posé : « hors identité de l'agent et fenêtre d'âge, **rien ne filtre**, tout pondère ».
Le lot 3 écarte du rappel les concepts de confiance inférieure à 0,5. C'est bien un **filtre**, et
c'est la spécification qui le demande : « un concept dont la confiance passe sous 0,5 cesse d'être
servi au modèle, sans être supprimé ».

*Ce qui est appliqué* : l'exception, telle que la spécification la décrit. Elle est **écrite
comme une exception** et non fondue dans la règle, parce que la formulation « rien ne filtre » se
transporte à l'article et qu'elle y deviendrait fausse sans mention. Les exceptions sont donc
trois : l'identité de l'agent, la fenêtre d'âge, et le concept mis hors service.

### 7.5 ⚠ La date de mise à l'écart était inatteignable

**Trouvé en exécutant les tests, pas en les lisant.** Deux règles se contredisaient :

- un concept **sort du panier** dès qu'il cesse d'être servi, confiance sous 0,5 — il n'est
  donc plus montré au modèle, donc plus contredit ;
- il n'est marqué **dépassé** qu'à partir de **trois** contre-exemples.

Pour un concept peu observé, le premier seuil arrive avant le second. Un concept d'une seule
observation cesse d'être servi à la deuxième contradiction et n'atteint jamais la troisième :
il restait hors service **sans jamais être daté**. Or c'est cette mise à l'écart datée qui est
l'observable de l'hystérésis — elle n'aurait jamais été écrite pour ces concepts-là.

*Résolution appliquée* : la date est posée quand le concept **cesse d'être servi**, et non au
seuil de trois contre-exemples. C'est d'ailleurs ce que la spécification rattache à la trace :
« sous un seuil, le concept cesse d'être servi sans être supprimé : sa mise à l'écart datée est
la trace du changement d'habitude ». Le prédicat « dépassé » à trois contre-exemples subsiste et
qualifie un état plus fort, atteint quand le concept était assez observé pour y arriver.

*Effet de bord mesuré* : le nombre de contradictions qu'un concept peut recevoir est **borné**
par sa sortie du panier. Un concept observé trois fois en reçoit quatre, puis plus aucune. Ce
n'est pas un défaut, c'est la conséquence de ne plus proposer au modèle ce qu'on ne lui sert
plus — et le test B8 le verrouille.

---

## 8. Critères d'acceptation du lot 3

- [ ] Tous les cas des § 2 à 6 passent.
- [ ] Les tests du contrat du **lot 2** (`tests_lot2.md`) sont écrits et passent.
- [ ] Le test D1 échoue si l'on rebranche la décroissance d'horloge sur les concepts.
- [ ] Le test B8 échoue si l'on ajoute une suppression.
- [ ] Non-régression : les 154 tests des lots 0 et 1 passent.
- [ ] `docs/arch/memory-stm-ltm.md` : le lot 3 est replié dans la partie II.
- [ ] `docs/changelog.md` : une entrée, avec bloc Avant / Après.
