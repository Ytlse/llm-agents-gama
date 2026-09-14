# Ticket 071, lot 2 — Spécification des tests fonctionnels

> Écrite le 2026-09-14, **avant le code du lot 2**. Même convention qu'au lot 1 : chaque cas
> porte ses entrées, son résultat attendu, et la raison pour laquelle il existe.
>
> ✅ **Les trois points du § 8 sont tranchés le 2026-09-14.** Issue **A** : l'affinité
> catégorielle se réduit à la **météo**, les cinq composantes redeviennent disjointes et leur
> nombre ne change pas. `axe_objet` est un **mode canonique**. Un cinquième axe, `axe_meteo`,
> est ajouté à l'entrée de mémoire.
>
> ⚠ **Les tests de ce document ne sont PAS écrits.** Décision de l'auteur : le code du lot 2
> part sans eux, les tests viendront à la fin du lot suivant et couvriront les deux lots. Le
> filet en place est celui des lots 0 et 1 — 154 tests, tous verts — qui traverse le code du
> lot 2 sans l'éprouver. **Ce document reste le contrat à honorer.**

---

## 1. Ce que le lot 2 change

| | Aujourd'hui | Après le lot 2 |
|---|---|---|
| Vivier de candidats | une passe sémantique | **trois viviers** réunis et dédupliqués |
| Composantes du score | 3 (0,4 / 0,3 / 0,3) | **5** (0,30 / 0,10 / 0,20 / 0,20 / 0,20) |
| Terme lexical | recouvrement de mots sur les étiquettes | **appariement d'attributs discrets** |
| Axes du souvenir | non renseignés | **normalisés à l'écriture** |
| Modèle de plongement | codé en dur | **lu depuis le paramètre** (modèle inchangé) |

Le lot 1 a déjà posé les champs `axe_objet`, `axe_lieu`, `axe_creneau`, `axe_motif` sur
`MemoryEntry` : ils existent et valent `None`. Le lot 2 les remplit et s'en sert.

---

## 2. Normalisation des axes, à l'écriture

**À l'écriture, jamais à la lecture.** Sans cela, deux graphies de la même ligne ne se
rencontrent jamais, et normaliser au rappel coûterait le même travail à chaque décision.

| Axe | Source | Vocabulaire |
|---|---|---|
| `axe_objet` | mode principal du trajet, via `mode_hierarchy.primary_canonical` | `walking`, `cycling`, `car`, `public_transport`, `train`, `motorbike` |
| `axe_lieu` | arrêt, ligne ou portée spatiale du concept | texte normalisé (casse, espaces, préfixe `line:`) |
| `axe_creneau` | horodatage du souvenir | `nuit`, `matin`, `midi`, `soir` |
| `axe_motif` | `activity.purpose` | `work`, `education`, `shop`, `leisure`, `home` |

| # | Cas | Attendu |
|---|---|---|
| A1 | une option « foot,bus,foot » | `axe_objet = "public_transport"` — le mode PRINCIPAL, pas la première jambe |
| A2 | une option « car » | `axe_objet = "car"` |
| A3 | un mode inconnu de la hiérarchie | `axe_objet = None`, **plus un compteur** — jamais rangé d'office dans le fourre-tout |
| A4 | deux graphies d'une même ligne (`"Line: 401"`, `"line:401"`) | même `axe_lieu` |
| A5 | un souvenir à 8 h 12, un autre à 18 h 40 | `matin` et `soir` |
| A6 | un axe non résolu | `None`, traité comme **absence de correspondance** et non comme correspondance avec tout |
| A7 | les axes sont figés à l'écriture | relire l'entrée ne les recalcule pas |

⚠ **`mode_label()` ne doit pas bouger.** `parse_option_modes` relit ces étiquettes dans le
texte du prompt : l'axe se **dérive** de l'étiquette, il ne la remplace pas. Un test le
verrouille (A8).

---

## 3. Les trois viviers

| Vivier | Contenu | Coût |
|---|---|---|
| **A — sémantique** | comportement actuel, `min(max(5 × top_k, 32), 100)` candidats | un plongement de requête |
| **B — par objet** | pour chaque mode offert dans les options, les souvenirs portant cet `axe_objet`, par gravité puis récence, 8 au plus par mode | nul, lecture en RAM |
| **C — chocs** | les souvenirs de gravité ≥ seuil du choc, 5 au plus, **sans aucune condition de contexte** | nul, lecture en RAM |

| # | Cas | Attendu |
|---|---|---|
| B1 | trois viviers rendent le même souvenir | il apparaît **une fois** — déduplication par identifiant de document |
| B2 | un mode offert sans aucun souvenir | vivier B vide pour ce mode, sans exception |
| B3 | douze souvenirs `cycling`, plafond 8 | les 8 plus graves d'abord, la récence départageant à gravité égale |
| B4 | un souvenir grave hors contexte | présent par le vivier C, **aucune condition de lieu, d'heure ni de motif** |
| B5 | l'index sémantique ne rend rien | les viviers B et C fonctionnent quand même |
| B6 | l'agent n'est plus dans le cache mémoire | les viviers B et C le rechargent depuis le disque, ils ne rendent pas vide |
| B7 | comptage par vivier | la part du top-K issue de chaque vivier est journalisée |

**B8 — le cas qui justifie tout le lot.** Une chute à vélo à 8 h 12 boulevard de Strasbourg
doit peser sur la décision de 18 h 40 où le vélo figure parmi les options. Ni le lieu, ni le
créneau, ni le motif ne coïncident. **Le test vérifie que ce souvenir est servi**, et qu'il ne
l'était pas avant le lot 2.

---

## 4. Le score à cinq composantes

```
score = 0,30 × similarité + 0,10 × affinité catégorielle + 0,20 × poids temporel
      + 0,20 × gravité + 0,20 × affinité d'axes
```

```
affinité d'axes = 0,50 × [objet concorde] + 0,20 × [lieu] + 0,15 × [créneau] + 0,15 × [motif]
```

| # | Cas | Attendu |
|---|---|---|
| C1 | les cinq poids sont lus | leur somme vaut 1,00 — le test du lot 0 doit maintenant passer avec cinq |
| C2 | toutes composantes au maximum | score 1,00 |
| C3 | un souvenir dont **aucun** axe ne concorde | reste **classable**, affinité 0, jamais exclu |
| C4 | un axe discordant | contribue **zéro**, il ne retranche rien |
| C5 | deux souvenirs identiques sauf la gravité | le plus grave passe devant |
| C6 | un axe `None` face à un axe renseigné | ne concorde pas — l'absence ne s'apparie avec rien |
| C7 | un axe `None` des deux côtés | ne concorde pas non plus — deux inconnues ne font pas une correspondance |
| C8 | le poids temporel des concepts | **inchangé au lot 2** : la confiance arrive au lot 3 |

**C9 — rien ne filtre, hors identité et fenêtre d'âge.** Aucune combinaison d'axes discordants
ne fait disparaître un candidat du classement. C'est la règle de non-exclusion, et c'est elle
qui permet le cas B8.

---

## 5. Le plongement

| # | Cas | Attendu |
|---|---|---|
| D1 | le paramètre est lu | le modèle chargé est celui de `settings.agent.embedding_model` |
| D2 | le paramètre est vide | repli sur le modèle actuel, **en le journalisant** |
| D3 | le modèle ne change pas | valeur par défaut = le modèle en service, aucun index à reconstruire |

**Le passage à un modèle francophone est abandonné** (bascule anglaise, ticket 074). Ce qui
reste est de brancher le paramètre : un paramètre qui ne commande rien empêche de comparer deux
modèles sans toucher au code.

---

## 6. Instrumentation

| # | Cas | Attendu |
|---|---|---|
| E1 | part du top-K par vivier | journalisée à chaque cycle |
| E2 | vivier B vide sur plus d'un tiers des décisions | `[ALARME]` sur front montant — signale une normalisation d'axes défaillante |
| E3 | part du top-K issue du seul vivier A au-dessus de 95 % | `[ALARME]` sur front montant — les viviers structurés ne servent à rien |
| E4 | retour sous le seuil | l'alarme se referme, avec hystérésis |

---

## 7. Non-régression

- Les 17 tests de `test_071_rappel_et_nettoyage.py`, les 30 du lot 0 et les 84 du lot 1 passent.
- Le test `test_les_poids_lus_par_le_classement_somment_a_un` du lot 0 devient vrai **avec cinq
  poids** au lieu de trois : c'est le signe que la bascule est complète.
- Les tests du ticket 048 sur le classement absolu passent toujours : aucune renormalisation par
  lot ne revient.

---

## 8. Ce qui demandait un arbitrage — rendu le 2026-09-14

### 8.1 ⚠ Double comptage entre l'affinité catégorielle et l'affinité d'axes

Le ticket définit deux composantes distinctes :

- **affinité catégorielle**, 0,10, qui remplace le terme lexical : « un appariement d'attributs
  discrets, mode, créneau, motif, météo » (§ 2.2, d'après le ticket 051 § D) ;
- **affinité d'axes**, 0,20 : objet, lieu, créneau, motif.

**Trois des quatre attributs sont les mêmes.** Le mode, le créneau et le motif seraient comptés
**deux fois**, avec des poids différents et sans que rien ne le dise. Seules la météo d'un côté
et le lieu de l'autre sont propres à une composante. Un score dont deux termes mesurent la même
chose n'est plus interprétable, et la calibration annoncée des cinq poids porterait sur des
composantes corrélées par construction.

✅ **Retenue : issue A.**

Trois issues :

- **A. L'affinité catégorielle se réduit à la MÉTÉO**, 0,10. ✅ **Retenue.** C'est le seul attribut qu'elle
  apporte, et il a du sens : un souvenir de pluie éclaire une décision sous la pluie. Les cinq
  composantes redeviennent disjointes. *Recommandée.*
- **B. Fusionner les deux** en une seule affinité à 0,30, météo comprise comme cinquième axe.
  Quatre composantes au lieu de cinq ; il faut alors le dire dans l'article, qui en annonce cinq.
- **C. Garder les deux telles quelles** et assumer le double comptage, en l'écrivant. Le moins
  cher à coder, le plus difficile à défendre devant un relecteur.

### 8.2 `axe_objet` : un mode, ou un objet de réseau ?

La spécification donne pour exemples `velo`, `metro_A`, `bus_401` — un **mode** et deux **lignes**.
Or le vivier B apparie « pour chaque mode présent dans les options offertes » : un axe au niveau
de la ligne n'apparierait jamais un mode, et le vivier B reviendrait toujours vide.

✅ **Retenu le 2026-09-14.** `axe_objet` = **mode canonique** (`walking`, `cycling`, `car`,
`public_transport`, `train`, `motorbike`), lu depuis la hiérarchie des modes qui fait déjà
autorité dans le dépôt ; la ligne et l'arrêt vont dans `axe_lieu`. Les tests A1 à A3 sont écrits
ainsi.

### 8.3 La météo d'un souvenir n'est stockée nulle part

Si l'issue A ou B est retenue en 8.1, il faut comparer la météo du souvenir à celle de la
décision. Or aucun champ ne la porte : elle est calculée à la volée au moment du prompt.

✅ **Retenu le 2026-09-14.** Un cinquième axe `axe_meteo` sur `MemoryEntry`, renseigné à l'écriture comme les
quatre autres, avec un vocabulaire réduit — `sec`, `pluie`, `neige`, `canicule`, `froid`. Cela
ajoute un champ au lot 1 déjà livré ; la relecture tolérante le permet sans casse.

---

## 9. Critères d'acceptation du lot 2

- [ ] Les trois points du § 8 sont tranchés, et `memory-stm-ltm.md` corrigé en conséquence.
- [ ] Tous les cas des § 2 à 6 passent.
- [ ] Le test B8 échoue si l'on retire le vivier B. Vérifié en le retirant.
- [ ] Les cinq poids lus somment à 1,00.
- [ ] Non-régression complète (§ 7).
- [ ] `docs/arch/memory-stm-ltm.md` : le lot 2 est replié dans la partie II.
- [ ] `docs/changelog.md` : une entrée, avec bloc Avant / Après.


---

## 10. Ce que le code livré fait, et qui n'était pas dans ce document

Trois points sont apparus à l'implémentation et méritent d'être dits, faute de quoi les tests
à écrire viseraient à côté.

**Le concept déclare son mode.** La mémoire longue ne contient que des réflexions et des
concepts : les entrées brutes sont consommées par la réflexion et n'y arrivent jamais. Sans un
mode porté par le concept, le vivier par objet n'aurait donc rien à apparier. Le schéma de
sortie gagne un champ `mode`, avec `any` pour un concept qui ne parle d'aucun mode — et `any`
devient un axe **vide**, parce qu'un axe absent ne s'apparie avec rien, ce qui est exact : ce
concept n'a pas à remonter au titre d'un mode. La version du schéma passe à 2.

**Les axes d'une réflexion viennent de l'épisode le plus grave de la journée**, et non du
dernier ni du plus fréquent : c'est lui qui la caractérise. À gravité égale, le plus récent
l'emporte.

**L'affinité d'objet apparie un ENSEMBLE.** Une décision offre plusieurs modes ; exiger
l'égalité avec un seul « mode courant » n'aurait pas de sens, il n'y en a pas un. Un souvenir
de vélo concorde dès que le vélo figure parmi les options.
