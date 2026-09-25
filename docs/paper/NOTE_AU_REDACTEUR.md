# Note au rédacteur — points relevés dans l'article, à corriger

Ce fichier liste ce qu'une session a trouvé de faux, de daté ou d'irreproductible dans
`docs/paper/article/`, **sans y toucher**. L'article est verrouillé : la correction passe par
la skill `article-verrou` et un accord humain explicite, point par point.

Chaque entrée dit : ce qui est écrit, ce que la source dit, et ce qu'il faudrait changer. Les
chiffres sont recoupés dans
[`article-court/experiments_results.md`](article-court/experiments_results.md), qui porte les
chemins pour les revérifier sans reconstituer la session.

Une entrée traitée ne se supprime pas : elle se date et passe en **RÉGLÉ**, avec la version de
l'article où la correction est entrée. Une liste qu'on vide ne se distingue pas d'une liste
qu'on n'a jamais tenue.

---

## 1. Le § 7.2 annonce un second incident qui n'a jamais eu lieu

**Relevé le :** 2026-09-23 · **Gravité : majeur** · **Sections :** `fr/07_Adaptation.md` § 7.2.2,
`en/07_Adaptation.md` § 7.2.2

**Ce qui est écrit.**

> « […] une avarie moteur qui impose un retard sur un trajet en voiture, **puis un retard moindre
> le lendemain**. »
> « […] an engine breakdown that imposes a delay on a car trip, **then a smaller delay the day
> after**. »

Et le commentaire de source enchaîne : « le second jour reste sous le seuil qui ouvre le bloc de
texte, un retour ne pourrait pas lui être attribué ».

**Ce que la source dit.** `experiments/archive/2026-09-18_19_27/chocs.jsonl` ne contient **que le
jour 15**. Le jour 16 est déclaré dans `c6_voiture_suspecte.yaml` et ne s'est pas appliqué.

**Ce qu'il faudrait changer.** Décrire un incident, pas deux. Si le second jour reste mentionné
parce qu'il fait partie du dispositif déclaré, dire qu'il n'a pas été joué — le commentaire de
source raisonne aujourd'hui sur un événement inexistant, ce qui est plus trompeur que son
absence.

**Fait dans l'article court, le 2026-09-23.** `article-court/sections/06_non_tabulated.en.md`
§ 6.3 et son rendu `overleaf/chapters/06_Non_tabulated.tex` ne décrivent plus qu'un incident,
« a half-hour delay on a car trip », le retard nommé d'après `retard_injecte_s: 1800`. **L'entrée
reste OUVERTE :** elle porte sur l'article long, qui est verrouillé et porte encore la phrase.

---

## 2. Le § 7.2 est exact mais irreproductible depuis le dépôt

**Relevé le :** 2026-09-23 · **Gravité : majeur** · **Sections :** `fr|en/07_Adaptation.md`
§ 7.2.1 et § 7.2.2

**Ce qui est écrit.** « 30 puis 20 minutes, soit 0,700 puis 0,533 » (commentaire de source du
§ 7.2.2) et « 15,29 jours pour une gravité de 0,70 », « du jour de la panne au quinzième jour qui
suit » (§ 7.2.1).

**Ce que la source dit.** Ces chiffres décrivent **exactement** ce qui a été injecté :
`retard_injecte_s: 1800`, gravité `0.7`. Le texte n'est pas faux.

Mais deux choses ont bougé depuis, et aucune n'est signalée :

- `c6_voiture_suspecte.yaml` déclare aujourd'hui `retard_min: **45**`, non 30 ;
- le régime de saturation du retard est passé de `palier` à `asymptote` le 2026-09-21. Sous
  `palier`, 30, 45 et 60 minutes valaient la même gravité ; sous `asymptote`, non.

Rejoué depuis le dépôt d'aujourd'hui, le cas rend **0,6427** et **14,27 jours**, non 0,700 et
15,29.

**Ce qu'il faudrait changer.** Le commentaire de source doit nommer le régime (`palier`) et le
retard réellement injecté (1800 s). Sans cela, un relecteur qui rejoue le cas obtient d'autres
chiffres et conclut à une erreur de l'auteur.

---

## 3. « Chaque incident produit un retard » — il s'en est produit quatre

**Relevé le :** 2026-09-23 · **Gravité : à vérifier** · **Sections :** `fr|en/07_Adaptation.md`
§ 7.2.2

**Ce qui est écrit.** « Chaque incident produit un retard effectivement subi dans la simulation
et une observation écrite dans les mots de l'agent. » Le singulier suppose une injection.

**Ce que la source dit.** Le choc s'est injecté **quatre fois** le 30 mars, pour deux
déplacements en voiture ce jour-là. C'est le défaut de cadence corrigé depuis par
`cadence: jour`.

**Ce qui reste à établir.** Si les quatre injections ont produit quatre retards subis ou un
seul. Je ne l'ai pas tranché. Le décompte « 75 des 376 prompts » du § 7.2.1 n'est pas concerné :
le bloc de texte est journalier.

---

## 4. L'abstract anglais décrit un choc que le chapitre 7 ne rapporte plus

**Relevé le :** 2026-09-23 · **Gravité : mineur** · **Section :** `en/00_Abstract.md`

L'abstract présente le § 7.2 comme portant la panne de métro, gravité 0,70 et trace 14,6 jours,
quand le § 7.2 rapporte une avarie voiture à 15,29 jours.

**Signalé pour mémoire, pas comme une incohérence silencieuse :** l'abstract déclare lui-même
l'écart — « The gap is open and it is for the chapter to close it ». Il se refermera quand le
chapitre 7 suivra la bascule.

---

## Vérifié et indemne au 2026-09-23

- **§ 7.2.3** — les comptes 34/36, 12/38, 35/40 et 28/31, 45/49, 40/46 sont lus dans les
  `moves.csv` des deux exécutions, colonne « Modes proposés au LLM ». Ils ne dépendent ni de la
  déclaration ni du régime de gravité.
- **§ 7.2.1** — le décompte « 75 des 376 prompts de décision » porte sur un bloc journalier,
  insensible au nombre d'injections dans la journée.
- **Le jour 13 inerte de `c3_panne_reseau`** (constaté le 2026-09-23) ne touche pas l'article :
  c3 n'est pas le choc rapporté, et n'apparaît que dans l'historique de version de l'abstract
  anglais.
- **Le correctif du frein de contre-pression** (2026-09-22) change la durée d'un run, aucun
  comportement mesuré.
