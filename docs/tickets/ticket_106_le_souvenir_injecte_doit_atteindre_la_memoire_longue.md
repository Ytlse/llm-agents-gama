# Ticket 106 — Le souvenir injecté doit atteindre la mémoire longue

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ouvert le 2026-09-23, en instruisant la reprise de la campagne c3 v4 : en vérifiant que
> le point `jour_017` portait bien le choc, on a découvert qu'aucun jour du run ne le portait.

---

## 1. La question, en une phrase

Une consolidation qui consomme un événement injecté doit-elle **prouver** qu'elle en a gardé
trace, ou peut-on supposer qu'elle l'a fait ?

## 2. Ce qui s'est passé, le 2026-09-23

La campagne `e_c3_attribution_861500_v4` a injecté une panne de métro dans la mémoire courte de
861500 le 27 mars à 14:02. L'agent l'a jugée **grave — 0,75, RETENU 0,75**.

| | |
|---|---|
| Entrée courte | 27 mars 14:02, importance 0,75 |
| Consolidation couvrante | 19:30 le même jour |
| Ce qu'elle a écrit | *« Today went very smoothly overall, with all my trips adhering closely to schedule »*, importance 0,10 |
| Documents de mémoire longue parlant de métro, éclairage, annonce ou rame | **0 sur 123** |

Le run a continué 2 h 22 de plus à mesurer l'effet d'un souvenir qui n'existait pas.

**Cause mécanique.** Le texte de l'événement est **joint** à l'observation d'arrivée (ticket 100,
comportement délibéré). Cette arrivée disait `On time.` — `arrive_at` 1774620168 contre
`expected_arrive_at` 1774620367, soit 199 s d'avance, parce que `retard_injecte_s` (1 680 s) ne
remonte qu'au `GamaArrivalsLogger`. La journée offerte à la consolidation avait donc pour ligne
dominante « tout s'est bien passé », et c'est ce que la synthèse a retenu.

**Non corrigé ici.** Faire porter le retard injecté à l'arrivée a été examiné et **écarté par
l'auteur le 2026-09-23**. Ce ticket ne change pas ce qui est injecté ; il rend visible ce qui en
sort.

## 3. Pourquoi aucun contrôle n'existait

Rien ne relie une entrée de mémoire courte à sa réflexion en mémoire longue : la consolidation est
une **synthèse reformulée**, pas une copie, et aucun identifiant ne voyage. Vérifier que le
souvenir est passé suppose donc de comparer des textes, ce qu'aucun code ne faisait.

## 4. Ce qui change

### 4.1 Un témoin par mots distinctifs

Après chaque consolidation qui consomme une entrée injectée, le contenu écrit en mémoire longue
est comparé aux mots du texte injecté qui ne pourraient pas venir d'une journée ordinaire.
L'ancrage est le **préfixe de l'entrée courte** (`[ INCIDENT ]`, `[ PRESSE ]`) : le texte est déjà
là, rien ne redescend du contrôleur.

En dessous de `temoin_souvenir_mots_min` mots retrouvés (2 par défaut), une ligne `[ALARME]`
nomme l'agent, l'événement, les mots cherchés et ceux retrouvés. **`make error` la montre.**

### 4.2 Le témoin alarme, il n'arrête pas

C'est le geste du ticket 105 **à un cran de moins**, et la raison est mesurée : le témoin de ce
ticket est heuristique là où celui du 105 était certain. Une paraphrase légitime — « the
underground » pour « metro » — produirait une fausse alarme, et le risque s'inverse : là où le 105
attrapait un défaut fréquent avec un test sûr, arrêter ici risquerait de tuer un bon run.

La trace `temoin_souvenir.jsonl` porte les **deux** verdicts, précisément pour que le taux de
fausses alarmes s'observe sur des runs réels. Quand il sera connu, brancher l'arrêt est une ligne
à changer.

### 4.3 Ce que la calibration a donné

Mesuré sur les 15 runs archivés portant une injection. Deux n'ont **aucune** consolidation après
l'injection (le run s'est arrêté avant) : le témoin ne les voit pas, et ne doit pas les voir.

| | |
|---|---|
| Runs observables | **13** |
| Souvenir retrouvé | **11** |
| Souvenir perdu | **2** — `2026-09-23_09_31` et `2026-09-23_13_54`, tous deux c3 sur 861500 |
| Mots retrouvés, runs sains | 3 à 81 |
| Mots retrouvés, runs perdus | **0 et 1** |

La séparation est **franche** : aucun run ne se situe au voisinage du seuil. Le seuil de 2 n'est
donc pas un arbitrage fin.

⚠ **Deux chiffres annoncés la veille étaient faux**, et la calibration les corrige :

- le run `2026-09-23_09_31` avait été compté comme **gardant** le choc sur la foi de deux mots
  (« lighting », « missed ») ; avec la liste d'exclusion calibrée il en retrouve **zéro**, et la
  lecture de ses six réflexions le confirme — *« Today went entirely according to schedule with no
  complications »* ;
- le taux de perte annoncé — 1 sur 15, soit 7 % — est en réalité **2 sur 13, soit 15 %**, et
  **2 sur 4 (50 %) sur le seul événement c3**.

Le défaut est donc plus fréquent qu'annoncé, et le témoin plus net. Les deux poussent dans le sens
d'un arrêt ; la décision reste à l'auteur.

### 4.4 La liste d'exclusion, et pourquoi elle existe

Un mot banal dans ce domaine ne prouve rien : tous les agents écrivent « trip », « minutes »,
« late ». Deux pièges rencontrés en calibrant, tous deux silencieux :

- **`incident`** correspondait à la phrase *« without any unexpected incidents »*, qui dit
  exactement le contraire de ce que le témoin cherche ;
- **`between`** était le seul mot que le run v4 retrouvait, dans *« a short walk between
  errands »* — il suffisait à le faire passer pour un run sain.

La règle d'admission dans la liste : *ce mot apparaîtrait-il dans la réflexion d'un jour
ordinaire ?* Si oui, il sort.

### 4.5 `make report` rend les deux verdicts

Une section « Témoin du souvenir injecté », une ligne par consolidation contrôlée, et une alarme
🔴 par souvenir perdu. Les succès y figurent aussi : un témoin dont on ne voit que les échecs ne
permet pas de distinguer « il ne se déclenche jamais » de « il ne tourne plus ».

## 5. Ce qui ne change pas

- Le texte de l'événement reste **joint** à l'observation, jamais substitué (ticket 100).
- L'arrivée ne porte **pas** le retard injecté — tranché par l'auteur le 2026-09-23.
- Aucun run n'est arrêté par ce témoin.
- Rien pendant un rejeu : la mémoire est gelée, la consolidation traversée a déjà été contrôlée
  au premier passage, et la recontrôler fausserait le taux qu'on cherche à mesurer.
- Le contrôle ne lève jamais vers l'appelant : un témoin qui ferait tomber une consolidation
  coûterait plus cher que le défaut qu'il surveille.

## 6. Critères d'acceptation

- [x] Une consolidation qui consomme une entrée injectée est contrôlée ; une consolidation
      ordinaire ne l'est pas.
- [x] Un souvenir perdu produit une ligne `[ALARME]` nommant l'agent et les mots cherchés.
- [x] Un souvenir retrouvé est journalisé lui aussi.
- [x] `make report` rend les deux verdicts et lève une alarme par perte.
- [x] Le témoin sépare correctement les 13 runs archivés observables.
- [x] Aucun run n'est arrêté par ce chemin.
- [x] Suite complète au vert.

## 7. La question laissée à l'auteur

Le témoin sépare les 13 runs sans cas limite, et le défaut touche 1 run sur 7 — 1 sur 2 pour c3.
**Faut-il armer l'arrêt maintenant, ou attendre d'avoir observé son taux de fausses alarmes ?**

Ce ticket livre l'attente. Basculer se fait dans `reflect_on_short_term_memory`, au même endroit
que l'appel actuel, et suppose de faire remonter la décision au contrôleur — seul détenteur de
`_declencher_hibernation_propre`, que le ticket 105 vient d'outiller avec un `motif`.
