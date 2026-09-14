# Ticket 071, lot 1 — Spécification des tests fonctionnels

> Écrite le 2026-09-14, **avant le code du lot 1**. Elle dit ce qui doit se produire, pas comment
> l'obtenir. Chaque cas porte ses entrées, son résultat attendu chiffré, et la raison pour
> laquelle il existe.
>
> ✅ **Deux défauts de la spécification cible ont été trouvés en écrivant ce document, et
> corrigés le 2026-09-14** sur accord de l'auteur (« mets les valeurs qui te semblent correctes »).
> Le détail est au § 9. La formule de départage de `memory-stm-ltm.md`, partie III, porte
> désormais la correction : départage nul quand un concept est seul dans son niveau, et gravité
> bornée sur [0, 1]. Les cas B1 et B8 ci-dessous sont conformes à la formule corrigée.

---

## 1. Principes

**Un test doit échouer sur le comportement d'avant.** Un test vert des deux côtés du changement ne
prouve rien. Chaque cas ci-dessous précise, quand ce n'est pas évident, ce qu'il donnait avant le
lot 1.

**Deux fichiers, deux rôles.**

| Fichier | Rôle |
|---|---|
| `tests/test_071_lot1_gravite.py` | les valeurs et les invariants : formules, bornes, tables de durée de vie |
| `tests/test_071_lot1_chaine.py` | le comportement de bout en bout, à travers les appels de production |

**Ce qui est doublé, et ce qui ne l'est pas.** On double ce qui coûte cher ou ce qui est hors
sujet, jamais la logique testée.

| Doublé | Pourquoi |
|---|---|
| L'index vectoriel et le modèle de plongement | plusieurs secondes de chargement par cas, et le rappel n'est pas l'objet du lot 1 |
| La passerelle LLM (`llm_client.execute`) | le test doit décider ce que le modèle répond, y compris répondre mal |
| Le magasin de mémoïsation des réflexions | ses effets de cache masqueraient l'appel qu'on veut observer |
| Le disque (métadonnées par agent) | vitesse, et aucun test ne doit dépendre d'un état laissé par un autre |
| L'horloge | **déjà doublée par construction** : tout passe par le temps simulé, jamais par l'horloge machine |

**Ce qui reste réel** : la fonction de gravité, l'écriture en mémoire courte, le groupement par
activité, la condition de déclenchement, la construction des entrées de mémoire longue, le
nettoyage, et toute l'instrumentation.

**Constantes en vigueur**, lues depuis la configuration et jamais recopiées dans les tests :
`S0 = 2,8` j, `k = 6`, `δ = 1` j, `FORCE_MAX = 30` j, `RETARD_REF = 1800` s, `I_choc = 0,7`,
`Θ = 0,7`, purge sous `0,01`.

---

## 2. Scénarios de référence

Cinq trajets, réutilisés dans tout le document. Ils viennent de ce que la simulation produit
réellement : une observation `arrival` porte un retard, une observation `tc_timeout` dit un
véhicule manqué, la chaîne des véhicules dit un mode contraint.

| Nom | Ce qui se passe | Retard | Corresp. ratée | Incident | Mode contraint | `I_det` attendu |
|---|---|---|---|---|---|---|
| `nominal` | tout se passe comme prévu | 0 | non | non | non | **0,00** |
| `petit_retard` | neuf minutes de retard | 540 s | non | non | non | **0,15** |
| `quart_heure` | quinze minutes | 900 s | non | non | non | **0,25** |
| `demi_heure` | trente minutes, le point de saturation | 1800 s | non | non | non | **0,50** |
| `panne_ligne_a` | la panne des expériences d'hystérésis | 2700 s | oui | non | oui | **0,80** |

`panne_ligne_a` doit valoir **exactement 0,80** : c'est la valeur que le ticket annonce pour
justifier `Θ = 0,7`. Si le code en produit une autre, c'est le choix de `Θ` qui devient
indéfendable, pas seulement un test qui casse.

---

## 3. Gravité déterministe

Fichier des valeurs. Fonction pure, aucun simulateur, aucun modèle.

| # | Cas | Entrée | Résultat attendu |
|---|---|---|---|
| A1 | les cinq scénarios de référence | § 2 | les cinq valeurs du tableau, à 1e-9 |
| A2 | le retard sature | 2700 s, puis 36 000 s | **0,50** dans les deux cas : au-delà de `RETARD_REF` la composante ne monte plus |
| A3 | un retard négatif n'est pas un bonus | −600 s (arrivée en avance) | **0,00**, jamais une valeur négative |
| A4 | la somme est bornée | tout à la valeur maximale | **1,00** exactement, pas 1,000000001 |
| A5 | chaque composante pèse ce qu'elle annonce | une composante à la fois | 0,50 / 0,20 / 0,20 / 0,10 |
| A6 | le détail est rendu | un cas mixte | la fonction rend la valeur **et** la contribution de chaque composante, pour que l'instrumentation puisse dire laquelle a joué |

**A7 — la composante inactive se déclare.** L'incident réseau n'a pas de source : GAMA ne joue pas
encore les événements. Le test vérifie **deux** choses :

- la fonction accepte le paramètre et le propage, donc la chaîne est prête ;
- au démarrage, une ligne de journal **nomme** les composantes actives et inactives.

*Pourquoi ce test existe.* Une composante sans observable contribue zéro, et zéro est exactement
la valeur d'un trajet parfait. Sans déclaration, la gravité serait sous-estimée sans qu'aucun
symptôme n'apparaisse. Le test échoue si le journal est muet.

**A8 — les trois autres composantes ne sont pas repondérées.** Avec l'incident inactif, un trajet
qui coche les trois composantes disponibles vaut **0,80** et non 1,00. Repondérer pour « compenser »
changerait l'échelle de gravité en silence ; le test l'interdit.

---

## 4. Niveau nommé et règle du maximum

La passerelle est doublée : le test décide ce que le modèle répond.

| # | Cas | Réponse du modèle | `I_det` du groupe | `I_concept` attendu |
|---|---|---|---|---|
| B1 | les cinq échelons | `anodin` … `marquant`, seuls | — (0,00) | 0,10 / 0,30 / 0,50 / 0,75 / 1,00 |
| B2 | **le modèle sous-estime un fait mesuré** | `notable` (0,30) | 0,80 (`panne_ligne_a`) | **0,80** — le fait l'emporte |
| B3 | le modèle est d'accord | `grave` (0,75) | 0,50 | **0,75** |
| B4 | **le modèle surestime** | `marquant` (1,00) | 0,00 (`nominal`) | **1,00** — comportement documenté, non borné |
| B5 | le maximum porte sur **tout** le groupe | `anodin` | groupe = 0,15 / 0,80 / 0,00 | **0,80** — le pire du groupe, pas le dernier |
| B6 | un niveau inconnu ne casse pas la réflexion | `"catastrophique"` | 0,50 | **0,50**, plus un WARNING nommant la valeur reçue |
| B7 | un niveau absent ne casse pas la réflexion | champ manquant | 0,25 | **0,25**, plus un WARNING |

*B2 est le test central du lot.* C'est la règle de sécurité non négociable : un modèle qui minimise
un incident de quarante-cinq minutes ne peut pas le dégrader.

*B4 dit une limite, il ne la corrige pas.* La règle du maximum ne protège que vers le bas. Le test
**fige la surestimation comme comportement attendu** pour que personne ne croie l'inverse. Le jour
où un plafond symétrique est décidé, ce test doit être réécrit sciemment.

*B6 et B7 sont des tests de robustesse, pas de tolérance.* Un modèle qui répond hors grille ne doit
pas faire perdre la réflexion entière, mais il doit laisser une trace : c'est ce qui permettra de
voir, sur un run, qu'un modèle ne respecte pas l'échelle.

**B8 — le départage ne change pas le niveau.** Trois concepts `genant`, rangés 1, 2, 3 : les
gravités attendues sont **0,55 / 0,50 / 0,45**. Aucune ne franchit vers `grave` (0,75) ni vers
`notable` (0,30). Le rang départage à l'intérieur d'un niveau, il ne déplace pas d'un niveau.

---

## 5. Durée de vie, rappel et renforcement

**C1 — la table de durée de vie initiale.** `force = min(S0 × (1 + k × I), FORCE_MAX)`.

| Niveau | Gravité | `force` attendue |
|---|---|---|
| trajet nominal | 0,00 | **2,80** j |
| `anodin` | 0,10 | **4,48** j |
| `notable` | 0,30 | **7,84** j |
| `genant` | 0,50 | **11,20** j |
| `grave` | 0,75 | **15,40** j |
| `marquant` | 1,00 | **19,60** j |

**C2 — la table des poids dans le temps**, `exp(-Δt / force)`, tolérance 0,01. C'est la table
publiée dans la spécification : si le code s'en écarte, c'est la spécification qui ment.

| Niveau | 7 j | 14 j | 30 j | 60 j |
|---|---|---|---|---|
| nominal | 0,08 | 0,007 | — | — |
| `genant` | 0,54 | 0,29 | 0,07 | 0,005 |
| `grave` | 0,63 | 0,40 | 0,14 | 0,02 |
| `marquant` | 0,70 | 0,49 | 0,22 | 0,05 |

**C3 — le plafond s'applique dès l'écriture.** Au point de sensibilité publié (`S0 = 8,3` j,
Park et al.), un `marquant` donnerait 58,1 j : la `force` écrite doit valoir **30,0** j exactement.
*Avant le lot 1, aucune durée de vie n'existait : le test échoue par absence.*

**C4 — le renforcement est additif.** Un rappel : `force + 1`, `rappels + 1`. Dix rappels d'un
trajet banal : **12,80** j. Un facteur multiplicatif donnerait 11,33 j ; le test distingue les deux.

**C5 — le nombre de rappels jusqu'au plafond.** Trajet banal : **28** rappels. `marquant` :
**11** rappels. Ce sont les deux chiffres que la spécification avance pour justifier `δ = 1`.

**C6 — le plafond tient au renforcement.** Cent rappels d'un `marquant` : **30,0** j, jamais plus.

**C7 — la décroissance part du dernier rappel, pas de l'écriture.** Un souvenir écrit il y a
dix jours, rappelé il y a un jour, gravité nulle : poids attendu **exp(-1/3,8) = 0,77**, et non
`exp(-10/2,8) = 0,03`. La `force` vaut 3,8 j (2,8 + 1 rappel) et le `Δt` se compte depuis le
rappel.

*C7 est le test qui justifie le champ `dernier_rappel`.* Sans lui, l'écart entre 0,77 et 0,03 est
invisible.

**C8 — l'horodatage d'origine ne bouge JAMAIS au rappel.** Après trois rappels, le `timestamp` de
l'entrée est identique à l'écriture, à la seconde.

*Pourquoi.* Cet horodatage s'affiche dans le prompt et sert de côté gauche aux filtres par jour et
par ancienneté. Le faire glisser réécrirait l'histoire de l'agent : il croirait que sa chute à
vélo a eu lieu hier.

**C9 — seules les entrées SERVIES sont renforcées.** Un rappel qui remonte trente candidats et en
sert dix : dix compteurs à 1, vingt à 0.

---

## 6. Déclenchement par rupture

La troisième condition **s'ajoute** aux deux existantes, elle ne les remplace pas.

| # | Tampon de l'agent | `I_cumul` | Déclenche ? | Motif attendu |
|---|---|---|---|---|
| D1 | 2 × `quart_heure` | 0,50 | **non** | — |
| D2 | 3 × `quart_heure` | 0,75 | **oui** | `rupture` |
| D3 | 1 × `panne_ligne_a` | 0,80 | **oui** | `rupture`, dès la première entrée |
| D4 | 1 × `demi_heure` + 1 × `petit_retard` | 0,65 | **non** | — |
| D5 | exactement au seuil (`0,70`) | 0,70 | **oui** | le seuil est atteint, pas dépassé |
| D6 | 10 entrées `nominal` | 0,00 | **oui** | `seuil d'entrées` — l'ancienne condition vit toujours |
| D7 | 1 entrée `nominal`, 22 h passées | 0,00 | **oui** | `plancher journalier` |
| D8 | tampon vide, 22 h passées | — | **non** | rien à consolider |

**D9 — les trois motifs sont comptés séparément** dans la ligne de journal du cycle. Sans cela, la
mesure de rareté du régime de rupture (question Q5) est impossible.

**D10 — une rupture ne déclenche qu'une fois pour le même tampon.** Après consommation, le cumul
repart de zéro : un agent en rupture ne doit pas boucler sur lui-même.

---

## 7. Rétention

**E1 — la purge suit le poids, plus le type.** Seuil : poids sous 0,01.

| Entrée | Âge | Purgée ? |
|---|---|---|
| trajet banal, jamais rappelé | 13 j | **oui** |
| trajet banal | 12 j | non |
| `marquant` | 30 j | **non** — son poids vaut encore 0,22 |
| `marquant` | 90 j | **non** — poids 0,0102, encore au-dessus du seuil |
| `marquant` | 95 j | **oui** — poids 0,0079 |

*Avant le lot 1*, la rétention se jouait sur l'âge et le type seuls : un `marquant` de trente et un
jours tombait avec les autres.

**E2 — un concept n'est JAMAIS purgé par le temps.** Un concept de deux ans, jamais contredit,
reste présent. Sa mise à l'écart datée est l'observable que l'expérience cherche ; la supprimer
détruirait la mesure.

**E3 — la purge retire aussi du magasin vectoriel.** Acquis du travail du 2026-09-14 ; le test
reste comme filet de non-régression.

**E4 — une purge qui ne sait pas dater ne purge rien.** Acquis ; jamais de repli sur l'horloge
machine.

---

## 8. Instrumentation, compatibilité, chaîne complète

**F1 — les quantiles de gravité sont publiés à chaque cycle.** Vingt concepts de gravités connues :
les cinq quantiles attendus sont vérifiés dans la ligne de journal.

**F2 — alarme d'un modèle qui nivelle.** Deux jours simulés sans aucun concept `grave` ou
au-dessus, **alors que** des retards au-dessus du seuil ont été observés : une ligne `[ALARME]`,
sur **front montant**. Le troisième jour identique n'en produit pas une deuxième.

**F3 — alarme de rupture trop fréquente.** Plus d'un déclenchement par agent et par semaine :
`[ALARME]`, front montant. C'est le critère de la question Q5.

**F4 — garde-fou du modèle.** Une expérience qui déclare la mémoire active sous un modèle autre que
celui de la campagne produit une ligne de journal. Pas un refus.

**G1 — les anciennes métadonnées se relisent.** Une entrée écrite avant le lot 1, sans aucun des
champs nouveaux, se recharge sans exception : gravité 0,0, `force` non fixée, zéro rappel, et le
rappel la sert avec la constante de temps par défaut.

**G2 — le retour en arrière reste possible.** Une entrée écrite **après** le lot 1 se relit par du
code qui ignore les champs nouveaux, sans exception.

**G3 — les deux formats de concept cohabitent.** Le format tableau (ancien) et le format objet
(nouveau) se lisent tous les deux. *Sans quoi un run repris perd ses concepts.*

**G4 — l'ancien cache de réflexions est ignoré, pas servi.** La clé de mémoïsation porte une
version de schéma : une entrée écrite sous l'ancien schéma produit un **miss**, pas une réflexion
sans gravité.

**H1 — la chaîne complète, un jour d'agent.** Le test de bout en bout, toutes doublures en place :

1. l'agent reçoit quatre observations, dont `panne_ligne_a` ;
2. la gravité déterministe est calculée et portée par chaque entrée de mémoire courte ;
3. le cumul atteint le seuil, la réflexion part avec le motif `rupture` ;
4. la passerelle doublée rend une réflexion et deux concepts, dont un `notable` sur le groupe de
   la panne ;
5. les entrées de mémoire longue sont écrites.

**Résultats attendus, tous vérifiés dans le même test :** le concept issu de la panne porte une
gravité de **0,80** et non 0,30, sa `force` vaut **16,24** j, le motif de déclenchement est
`rupture`, et **aucun appel supplémentaire** n'a été fait à la passerelle — un seul appel, celui
de la réflexion qui avait déjà lieu.

*Le dernier point est la contrainte transverse du ticket.* Un lot qui coûterait un appel de plus
par agent et par jour changerait le coût de la campagne ; le test compte les appels.

**H2 — un jour sans rien.** Quatre observations `nominal` : aucune rupture, consolidation au
plancher de 22 h, gravités toutes nulles, et le journal le dit. Un dispositif muet quand tout va
bien ne permet pas de distinguer « ça marche » de « ça ne tourne plus ».

---

## 9. Deux défauts de la spécification, trouvés en écrivant ces tests

Les deux portent sur la formule de départage du § 2.1 du ticket :

```
I_llm = valeur(niveau) + 0,05 × (2 × (n_niveau − rang) / max(n_niveau − 1, 1) − 1)
```

**Défaut 1 — un concept seul dans son niveau est pénalisé de 0,05.** Avec `n_niveau = 1` et
`rang = 1`, le terme vaut `2 × 0 / 1 − 1 = −1`, donc **−0,05**. Un `marquant` seul vaut 0,95 au
lieu de 1,00, un `genant` seul 0,45. Or « seul dans son niveau » est le cas le plus courant : une
réflexion rend zéro à cinq concepts, rarement deux du même échelon. Il n'y a rien à départager
quand il n'y a qu'un candidat.

*Correction proposée* : le terme de départage vaut **0** quand `n_niveau = 1`.

**Défaut 2 — la gravité peut dépasser 1.** Un `marquant` premier de trois vaut
`1,00 + 0,05 = 1,05`. La gravité est spécifiée sur [0, 1], et la durée de vie qui en découle
passerait de 19,60 j à 20,44 j. La borne existe pour `I_det`, elle manque pour `I_llm`.

*Correction proposée* : borner `I_llm` sur [0, 1] après départage.

✅ **Arbitrage rendu le 2026-09-14 : les deux corrections sont appliquées** à
`memory-stm-ltm.md`, partie III, et signalées au § 2.1 du ticket. Aucun code n'était concerné,
rien n'était implémenté. Les cas B1 et B8 ci-dessus sont conformes à la formule corrigée.

**Ce que les corrections changent, en valeurs.** Les six durées de vie de la table C1 sont
inchangées : seuls les cas limites bougeaient.

| Cas | Formule littérale | Formule corrigée |
|---|---|---|
| `marquant` seul dans son niveau | 0,95 → force 18,76 j | **1,00** → force **19,60** j |
| `genant` seul dans son niveau | 0,45 → force 10,36 j | **0,50** → force **11,20** j |
| `marquant` premier de trois | 1,05 → force 20,44 j | **1,00** → force **19,60** j |
| `genant` premier de trois | 0,55 → force 12,04 j | 0,55 → force 12,04 j, inchangé |

---

## 10. Critères d'acceptation du lot 1

- [ ] Les deux défauts du § 9 sont tranchés, et la spécification `memory-stm-ltm.md` corrigée.
- [ ] Tous les cas des § 3 à 8 passent.
- [ ] Les tests du lot 0 et les dix-sept de `test_071_rappel_et_nettoyage.py` passent toujours.
- [ ] Le test B2 échoue si l'on retire la règle du maximum. Vérifié en la retirant.
- [ ] Le test H1 compte **un** appel à la passerelle, pas deux.
- [ ] Le journal de démarrage nomme les composantes de `I_det` actives et inactives.
- [ ] `docs/arch/memory-stm-ltm.md` : la partie III du lot 1 est repliée dans la partie II.
- [ ] `docs/changelog.md` : une entrée, avec bloc Avant / Après.
