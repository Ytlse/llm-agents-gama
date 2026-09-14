# Ticket 071, lot 4 — Spécification des tests fonctionnels

> Écrite le 2026-09-14, **avant le code du lot 4**. Même convention qu'aux lots précédents.
>
> ✅ **Livré et testé le 2026-09-14**, 27 cas dans `test_071_lot4_noyau.py`. Les trois points du
> § 6 sont résolus et appliqués. Validation par l'échec vérifiée : laisser le bloc des habitudes
> recevoir un texte du modèle casse A7.

---

## 1. Ce que le lot 4 change

Les dix souvenirs bruts servis au modèle sont remplacés par un **bloc permanent structuré**,
complété de deux ou trois entrées épisodiques rappelées pour la décision en cours. Le principe
est le *working context* de MemGPT (Packer et al., 2023, § 2.1) : un bloc toujours présent dans
le contexte principal, le reste étant paginé à la demande.

```
Mes habitudes                                 [ produit par le JOURNAL DES TRAJETS ]
- Domicile → travail, matin : vélo, 9 fois sur 11. Deux retards de plus de 10 min.

Ce que je sais                                        [ produit par les CONCEPTS ]
- Le bus 401 est fiable, sauf les jours de pluie.                          (12 obs.)
- La marche jusqu'à l'arrêt fait toujours 5 minutes.                       (18 obs.)

Ce qui a changé récemment                    [ produit par les CHOCS et les MISES À L'ÉCART ]
- Panne ligne A, 45 minutes perdues. Je ne crois plus que la ligne A soit fiable.
```

**Le bloc ne porte aucune métadonnée sur lui-même** : ni date de mise à jour, ni nombre de jours
de vécu. Cela ne change aucune décision, coûte des jetons, et rompt la fiction que les gabarits
maintiennent — une personne ne pense pas « mon résumé d'habitudes date de trois jours ».

---

## 2. Le bloc « Mes habitudes »

| # | Cas | Attendu |
|---|---|---|
| A1 | neuf trajets vélo et deux en voiture, même motif et créneau | « vélo, 9 fois sur 11 » |
| A2 | un seul trajet observé | **rien** — une occurrence n'est pas une habitude |
| A3 | deux motifs distincts | deux lignes |
| A4 | des retards | comptés et dits, sans être inventés |
| A5 | aucun trajet | le bloc est **absent**, pas vide avec un titre |
| A6 | le journal survit à un redémarrage | il est persisté avec les métadonnées de l'agent |
| A7 | **le modèle n'écrit jamais ce bloc** | il est calculé, et vérifiable contre sa source |

**A7 est le garde-fou du lot.** Un texte réécrit périodiquement par un modèle dérive et invente.
Un bloc calculé depuis le journal reste vérifiable contre lui.

---

## 3. Le bloc « Ce que je sais »

| # | Cas | Attendu |
|---|---|---|
| B1 | trois concepts servis | trois énoncés, chacun avec son compteur d'observations |
| B2 | un concept mis hors service | **absent** — on ne sert pas ce qu'on ne croit plus |
| B3 | un concept jamais confirmé | présent, compteur à zéro |
| B4 | plus de concepts que la place | les plus confiants d'abord, plafonné |
| B5 | aucun concept | le bloc est absent |

---

## 4. Le bloc « Ce qui a changé récemment »

| # | Cas | Attendu |
|---|---|---|
| C1 | un choc récent | présent, avec ce qu'il a coûté |
| C2 | un concept mis à l'écart récemment | présent — c'est l'observable de l'hystérésis |
| C3 | un choc ancien | absent au-delà de la fenêtre |
| C4 | rien n'a changé | le bloc est absent |

---

## 5. Le bloc dans le prompt

| # | Cas | Attendu |
|---|---|---|
| D1 | aucune métadonnée sur le bloc | ni date, ni « il y a N jours », ni compte de jours vécus |
| D2 | entrées épisodiques | deux ou trois, pas dix |
| D3 | un agent sans mémoire | aucun bloc, comportement d'avant |
| D4 | aucun appel supplémentaire au modèle | le lot 4 ne coûte aucune inférence de plus |

---

## 6. Ce qui demande un arbitrage

### 6.1 ⚠ Le journal des trajets n'existe pas

Le bloc des habitudes doit venir du **journal des trajets**, pas du modèle. Or `MoveLogger`
écrit dans `moves.csv` et rien d'autre : il n'y a aucune structure interrogeable en mémoire, et
`PersonState` ne garde aucun historique. Relire un CSV à chaque décision est exclu — c'est le
chemin critique.

*Résolution proposée et appliquée* : un **compteur par agent**, tenu en mémoire et **persisté
avec les métadonnées de l'agent**, qui réutilise le mécanisme d'écriture différée déjà en place.
Il compte, par couple motif-créneau, les modes retenus et les retards subis. Sans persistance, un
run repris repartirait sans habitudes, et le bloc mentirait par omission le premier jour.

### 6.2 ⚠ Les trois blocs peuvent être CALCULÉS, y compris celui des connaissances

La spécification confie le bloc « Ce que je sais » au modèle et ne calcule que les habitudes.
Mais depuis le lot 3, un concept porte son compteur d'observations, sa confiance et son état de
service : le bloc se **calcule** exactement, sans rien demander à personne.

*Résolution proposée et appliquée* : **les trois blocs sont calculés.** L'argument du garde-fou
— « un texte réécrit périodiquement par un modèle dérive et invente » — vaut pour les trois, et
un bloc calculé est vérifiable contre sa source. Cela rend aussi le lot 4 strictement gratuit :
il ne touche pas au schéma de l'auto-réflexion longue durée.

### 6.3 ⚠ Le nombre d'entrées épisodiques servies passe de dix à deux ou trois

`long_term_max_entries_query` vaut 10 et commande le top-K du rappel. Le lot 4 veut deux ou trois
entrées épisodiques **en plus du bloc**.

*Résolution proposée et appliquée* : un paramètre distinct, `memoire__episodiques_avec_noyau`, à
3. `long_term_max_entries_query` reste ce qu'il est — le top-K du rappel — et c'est le rendu qui
en retient trois. Réutiliser le même paramètre pour deux choses différentes rendrait toute
mesure de sensibilité ambiguë.

---

## 7. Critères d'acceptation

- [ ] Tous les cas des § 2 à 5 passent.
- [ ] Le test A7 échoue si l'on fait écrire le bloc des habitudes par le modèle.
- [ ] Le test D4 compte **zéro** appel de plus.
- [ ] Non-régression : les 230 tests des lots 0 à 3 passent.
- [ ] `docs/arch/memory-stm-ltm.md` : le lot 4 est replié dans la partie II.
- [ ] `docs/changelog.md` : une entrée, avec bloc Avant / Après.
