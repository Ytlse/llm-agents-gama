# Les plans de l'article

Ce dossier porte la trame de l'article. Un seul fichier courant, [`PLAN.md`](PLAN.md).

## 1. Ce qui fait foi

**Le texte de l'article fait foi.** La numérotation et le découpage des sections sont ceux
annoncés dans la section 1.4 du chapitre 1, [`../en/01_introduction.md`](../en/01_introduction.md).
`PLAN.md` en est **dérivé** — jamais l'inverse.

Quand les deux divergent, c'est le plan qui a tort et qui se corrige. Cette règle existe parce
que la divergence est déjà arrivée : la trame et le texte ont vécu neuf jours sans se parler
(voir le journal ci-dessous).

## 2. Comment le plan se met à jour

Une renumérotation touche trois choses **dans le même commit** :

1. les numéros de fichier des chapitres (`article/en/NN_slug.md`, `article/fr/`, `article/overleaf/`) ;
2. la phrase de la section 1.4 du chapitre 1, dans les trois fichiers du chapitre (EN, FR, `.tex`) ;
3. `PLAN.md`, et l'entrée correspondante dans le journal ci-dessous.

`make paper-parite` relit les trois arbres et signale ce qui ne concorde plus : un chapitre dont
les versions diffèrent d'une langue à l'autre, une langue manquante, un numéro de section du plan
sans dossier correspondant.

## 3. Journal des écarts

Un écart constaté se consigne ici, daté, avec ce qui a été retenu. Jamais corrigé en silence.

### 10 septembre 2026 — la trame v1.6 et le texte v0.16 ne disaient pas la même chose

Le texte a été retenu, sur arbitrage de l'auteur. Trois écarts :

| | `PLAN.md` v1.6 (3 septembre) | Texte de l'article v0.16 (10 septembre) — retenu |
|---|---|---|
| § 2 | Étape 0 : métriques et validation démographique | **État de l'art** (nouveau), les étapes décalent d'un cran |
| § 6 | Concept & perspectives : l'architecture hybride en cascade | Régimes non tabulés : hystérésis et presse locale |
| § 7 | Conclusion & enseignements | Limites, dont l'IIA de la renormalisation et l'asymétrie d'exposition, et implications hybrides |
| § 8 | Références bibliographiques | Conclusion |

Deux conséquences de fond, et pas seulement de numérotation :

- **La cascade hybride n'est plus une section.** Elle devient les implications hybrides de la
  section 7, à la suite des limites — c'est-à-dire une perspective tirée des limites mesurées,
  et non une contribution annoncée.
- **Les références quittent la numérotation des sections.** Elles vivent dans
  [`../../sources/BIBLIOGRAPHIE.md`](../../sources/BIBLIOGRAPHIE.md) et
  [`../../sources/references.bib`](../../sources/references.bib), comme toute matière première.

## 4. Versions antérieures

Dans [`../../archive/`](../../archive/) : `PLAN_ARTICLE_2026_v1.1.md` à `_v1.5.md`, et
`_v1.6.md`, la dernière version d'avant réalignement.
