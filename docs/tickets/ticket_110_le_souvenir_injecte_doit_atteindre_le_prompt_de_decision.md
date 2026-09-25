# Ticket 110 — Le souvenir injecté doit atteindre le prompt de décision

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ouvert le 2026-09-24 à la demande de l'auteur, après la campagne c3 v7 à deux bras.

---

## 1. La question, en une phrase

Le ticket 106 vérifie que le souvenir injecté atteint la **mémoire longue**. Il ne dit pas s'il
atteint le **modèle au moment de décider** — et c'est cela seul qui peut produire un effet.

## 2. Trois instruments, et pourquoi deux ne suffisent pas

Mesuré le 2026-09-24 sur les dix-sept runs archivés portant une injection.

### 2.1 Le témoin du ticket 106 ne voit qu'un canal

Il compare la consolidation du soir au texte qui vient de l'alimenter. C'est le bon geste pour
ce qu'il surveille, mais la décision n'est pas nourrie que par la mémoire longue : le bloc
« ce qui a changé récemment », la mémoire courte et les concepts y arrivent aussi.

Le run `2026-09-23_09_31` en est la preuve : le témoin le déclare **PERDU** — aucune de ses 112
entrées de mémoire longue ne porte le choc — et **3 de ses 9 décisions postérieures** reçoivent
pourtant le récit du choc dans leur prompt. Un verdict « PERDU » ne signifie donc pas que
l'agent a décidé sans le souvenir.

### 2.2 Le compte des rappels ne mesure pas ce qui est servi

`rappels` et `dernier_rappel` sont écrits sur chaque entrée de mémoire longue, et la tentation
est forte de s'en servir : « combien de fois le souvenir est-il ressorti ? ». **Mesuré, et
écarté.** Le run `2026-09-19_18_09` totalise **zéro rappel** et fait chuter la voiture décidée
de 95 % à 48 % : son effet passe par le bloc « ce qui a changé récemment », qui ne consomme
aucun rappel. Un témoin bâti sur `rappels` aurait classé « dormant » le run qui porte le
résultat du § 7.2 de l'article.

### 2.3 La présence au prompt, auto-calibrée, est la mesure qui tient

C'est la mesure du § 7.2.1 de l'article : le récit du choc figure-t-il dans le texte
effectivement soumis au modèle ? Elle ne demande pas par quel canal il est arrivé, ce qui est
précisément sa force.

**L'ancrage se calibre tout seul, sans liste d'exclusion.** On retient les mots du texte
injecté qui n'apparaissent dans **aucun prompt de décision d'avant le choc**. Un mot déjà
présent avant ne peut rien ancrer, quelle qu'en soit la raison — et cela règle sans arbitrage
le défaut qui a coûté deux faux verdicts au ticket 106 : sur le run c6 du 2026-09-23,
`speed`, `hard`, `short` et `restart` sont écartés automatiquement, parce que le prompt système
les contient déjà.

**Contrôle de validité :** sur `2026-09-21_15_13`, le run dont le § 7.2.1 est tiré, ce compte
rend **75 prompts porteurs** — le chiffre publié, obtenu indépendamment.

## 3. Le piège qui invalide une mesure naïve : un prompt porte plusieurs agents

`llm_exchanges.jsonl` est écrit **côté worker** et groupe les décisions par lot — jusqu'à douze
agents dans un seul appel sur `2026-09-21_15_13`. Compter un prompt entier comme « portant le
souvenir » attribue à tous les agents du lot le souvenir d'un seul.

Ce n'est pas théorique : mesuré des deux façons, le run `2026-09-17_07_18` passe de **0** à
**8 décisions porteuses** selon qu'on segmente ou non. Le message utilisateur délimite les
agents par `--- agent_id=<id> | … ---` : la mesure ne teste que le bloc de l'agent exposé et ne
compte que ses décisions à lui. Toute implémentation qui l'oublie rendra des chiffres faux sur
les runs de cohorte, et justes sur les runs à un agent — c'est-à-dire indétectable en recette
si la recette ne porte que sur un persona.

## 4. Ce que la mesure donne sur les runs archivés

Par agent **exposé**, segmentation faite.

| run | événement | agent | décisions après | portant | part | dernier jour servi |
|---|---|---|---|---|---|---|
| `2026-09-18_19_27` | c6 | 899549 | 27 | **0** | **0 %** | — jamais servi |
| `2026-09-23_13_54` | c3 | 861500 | 36 | **0** | **0 %** | — jamais servi |
| `2026-09-20_17_44` | c6 | 899549 | 82 | 19 | 23 % | 2026-04-06 |
| `2026-09-23_09_31` | c3 | 861500 | 9 | 3 | 33 % | 2026-03-30 |
| `2026-09-23_11_10` | c3 | 861500 | 3 | 1 | 33 % | 2026-03-30 |
| `2026-09-19_18_09` | c6 | 899549 | 82 | 39 | 48 % | 2026-04-13 |
| `2026-09-18_14_31` | c6 | 899549 | 34 | 18 | 53 % | 2026-04-06 |
| `2026-09-21_15_13` | c6 | 861500 | 142 | **75** | 53 % | 2026-04-13 |
| `2026-09-24_00_15` | c3 | 861500 | 155 | 85 | 55 % | 2026-04-27 |
| `2026-09-22_14_08` | c6 | 861500 | 13 | 8 | 62 % | 2026-03-19 |
| `2026-09-23_20_35` | c6 | 861500 | 92 | 63 | 68 % | 2026-04-16 |
| `2026-09-22_16_55` | c3 | 861500 | 149 | 121 | 81 % | 2026-04-23 |
| `2026-09-22_14_54` | a13 | 6 agents | 5 à 18 | 5 à 18 | 86–100 % | 2026-03-19/20 |

Trois runs de plus rendent 0 % — `16_15_58`, `17_07_18`, `22_09_39` — mais avec 9, 2 et 5
décisions postérieures seulement. Sous cette taille, « jamais servi » et « presque aucune
décision » ne se distinguent pas : ils sortent du champ, comme le ticket 106 avait écarté les
runs sans consolidation après l'injection.

**Restent deux runs qui ont une vraie fenêtre de mesure et n'ont servi le souvenir à aucune
décision :** `2026-09-18_19_27` (27 décisions) et `2026-09-23_13_54` (36). Rien ne le disait.
Un seul des deux — `13_54` — est attrapé par le témoin du ticket 106.

**Contrôle de validité :** `2026-09-21_15_13` rend **75** décisions porteuses. C'est le chiffre
du § 7.2.1 de l'article, obtenu indépendamment.

## 5. Ce que la mesure ne dit pas, et qu'il faut écrire à côté

Servir le souvenir ne produit pas l'effet. Le run c3 du 2026-09-24 le sert dans **55 % de ses
décisions et jusqu'au dernier jour simulé**, et sa part de transports collectifs décidée ne
bouge pas de plus de six points par rapport à son bras témoin. Le souvenir était devant le
modèle une décision sur deux ; le modèle a continué de prendre le métro.

C'est un résultat **comportemental**, et ce ticket ne le traite pas. Il fournit l'instrument
qui permet de le distinguer d'une panne de plomberie — distinction qu'aucun run ne permettait
de faire avant aujourd'hui.

## 6. Ce qu'il faut livrer

### 6.1 La mesure, en fin de run

Par agent exposé : nombre de décisions postérieures au choc, nombre portant le souvenir, part,
premier et dernier jour servi, et les mots d'ancrage retenus. L'ancrage se calcule sur les
prompts du run lui-même, jamais sur une liste écrite d'avance.

### 6.2 L'alarme

`[ALARME]` quand un souvenir injecté n'atteint **aucune** décision. C'est le cas de deux runs
qui ont une vraie fenêtre de mesure, et c'est le défaut que ce ticket existe pour rendre
visible. Une part faible mais
non nulle n'est pas une alarme : c'est une donnée.

⚠ **Une seconde alarme est à discuter, pas à livrer d'office :** le souvenir servi au-delà de
la durée de vie déclarée. `2026-09-19_07_31` et `2026-09-24_00_15` le servent jusqu'au dernier
jour simulé, ce qui peut être conforme (plafond à 50 jours) ou trahir un souvenir qui ne sort
jamais du contexte. Trancher demande de comparer à la durée dérivée de la gravité, ce que ce
ticket ne fait pas encore.

### 6.3 La section de rapport

`make report` rend la mesure **dans les deux sens** : la part servie quand tout va bien, pas
seulement l'absence. Un rapport muet quand tout va bien ne se distingue pas d'un rapport mort.

### 6.4 Le coût, à vérifier avant de brancher

`llm_exchanges.jsonl` pèse 5,2 Mo pour 201 décisions et n'est pas du JSONL — ce sont des objets
JSON indentés concaténés, qu'un `json.loads` par ligne ne lit pas. Relire tout le fichier en
fin de run est acceptable à cette taille ; à l'échelle d'une cohorte de mille agents, il faudra
compter au fil de l'eau plutôt que relire. À mesurer avant de choisir.

## 7. Ce qui ne change pas

- **Aucun run n'est arrêté par ce chemin.** Même geste que les tickets 106 et 108.
- Le témoin du ticket 106 reste en place : il surveille un canal précis, et il le surveille
  bien. Celui-ci ne le remplace pas.
- Rien pendant un rejeu.

## 8. Critères d'acceptation

- [ ] Un run dit, par agent exposé, dans quelle part de ses décisions postérieures le souvenir
      injecté était présent, et jusqu'à quel jour.
- [ ] Les mots d'ancrage sont calibrés sur les prompts d'avant le choc du run lui-même, et
      journalisés.
- [ ] Un souvenir qui n'atteint aucune décision lève une `[ALARME]`.
- [ ] `make report` rend la mesure dans les deux sens.
- [ ] La segmentation par `--- agent_id=` est faite : la recette comporte AU MOINS un run de
      cohorte, sans quoi le défaut reste invisible.
- [ ] Les deux runs à zéro avec fenêtre (`18_19_27`, 27 décisions ; `13_54`, 36) sont signalés,
      et `21_15_13` rend 75 décisions porteuses — le chiffre du § 7.2.1.
- [ ] Les runs de moins de dix décisions postérieures sortent du champ, et le disent.
- [ ] Le coût de la mesure est chiffré sur un run de cohorte.
- [ ] Aucun run n'est arrêté par ce chemin.
- [ ] Suite complète au vert.

## 9. Voir aussi

- Ticket 106 — le souvenir atteint-il la mémoire longue (un canal, en amont de celui-ci).
- Ticket 108 — l'injection déclarée a-t-elle eu lieu (encore en amont).
- `docs/paper/article/fr/07_Adaptation.md` § 7.2.1 — la mesure dont celle-ci généralise l'idée.
