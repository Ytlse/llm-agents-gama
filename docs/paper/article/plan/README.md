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

### 11 septembre 2026 — le chapitre 1 rejoint la v5, et la chaîne d'activités est cyclique

Constat, en relisant la section 1.3 après la rédaction du chapitre 4 : **les deux chapitres ne
décrivaient pas le même substrat**. Le chapitre 4 mesure sur la cohorte v5 ; la section 1.3 décrivait
encore la v1, comme l'entrée ci-dessous l'avait signalé sans la traiter.

| | Avant (§ 1.3, `v0.18`) | Après — retenu |
|---|---|---|
| Cohorte scellée | v1, sceau 1 du 2026-09-02, sha256 `f67b0777…` | **v5**, scellée le 2026-09-04, sha256 `de73532e…` |
| Unité de tirage | la personne, par allocation proportionnelle couronne × motorisation | **le ménage** — 499 ménages entiers ; effectifs de cellule par programme entier sur les sous-cellules (couronne × motorisation × effectif présent × taille déclarée), puis descente par échanges de ménages |
| Vivier eqasim | 5 063 personnes | **11 329 personnes** — 10 979 éligibles, 5 652 ménages |
| Marges contrôlées | six, toutes conformes | **treize**, toutes conformes, aucune non mesurable, borne TOST ± 1 pt |
| Déplacements du jour | 2 693 (convention `activités − 1`) | **3 299** — chaîne **cyclique**, une chaîne de *k* activités porte *k* déplacements |
| Décisions scorées | 2 645, déduites du même compte | emplacement `[xx.y \| décisions scorées du run épinglé]` — se mesure sur un run, ne se déduit pas |

Recoupé sur le `population.json` de la v5 : somme(activités − 1) = 2 405, plus 894 personnes mobiles,
égale 3 299 — exactement les 3,30 déplacements par persona du manifeste. La convention `activités − 1`
sous-compte d'un déplacement par personne mobile, le retour au domicile, et ne retombe sur aucun
chiffre du dossier scellé.

Retenu aussi, hors du chapitre 1 : le **résumé** portait le même chiffre dérivé de la convention fausse
(« 2 645 trajets ») et passe à 3 299 déplacements, chapitre 0 en `v0.4`, décompte de mots inchangé ; et
[`../../methode/experience_plan/experiments.yaml`](../../methode/experience_plan/experiments.yaml)
corrige `trip_count: 2579` et son commentaire, ainsi que son `population_file`, qui désignait un dossier
`population_1000_AAMAS_vLAST` inexistant.

Conséquence sur les versions : chapitre 1 en `v0.19`, chapitre 0 en `v0.4`, dans les trois arbres ;
versions antérieures figées dans [`../../archive/`](../../archive/). L'avertissement porté par l'en-tête
du chapitre 4 — « conséquence à trancher sur le chapitre 1 » — est levé.

Reste ouvert, non traité ici : la maquette [`../../../tickets/ticket_035_maquette_plateforme_experiences.html`](../../../tickets/ticket_035_maquette_plateforme_experiences.html)
affiche encore « vLAST (894 mobiles, 2 579 trajets) ».

### 11 septembre 2026 — le chapitre 4 change de cohorte, et gagne une sous-section

Constat, en recoupant dans le dépôt les chiffres du brouillon hérité du manuscrit `v1.6` plutôt
qu'en les recopiant : **trois des chiffres publiés ne tiennent pas**.

| | Avant (brouillon `v0`, et § 1.3 du chapitre 1) | Après — retenu |
|---|---|---|
| Cohorte scellée | v1 en § 1.3 (six marges, deux non mesurables), v3 dans le brouillon | **v5** — treize marges conformes, aucune non mesurable, unité de tirage = le ménage |
| Déplacements du jour | 2 693 (convention `activités − 1`) | **3 299** — la chaîne d'activités est **cyclique**, une chaîne de *k* activités porte *k* déplacements |
| Effectif efficace | `n_eff ≈ 1,75 × N ≈ 1 750` | **1 530 à 1 720** (≈ 1,6 × N) — l'effet de plan de la note de dimensionnement était calculé puis non appliqué |

Retenu aussi, sur la trame interne : une sous-section neuve, **« ce qui n'entre pas au score »**
(les trois coupes de périmètre, et l'offre à mode unique qui est un accord parfait gratuit), et
des références tabulaires présentées comme une **famille en cours de caractérisation** — le
plafond de l'ablation n'est pas encore désigné, les tickets 043 et 044 étant ouverts le même
jour. Le critère de désignation est annoncé dans le texte, avant le chiffre.

Conséquence sur le chapitre 1, **non traitée dans cette passe** : la section 1.3 décrit encore la
cohorte v1 (six marges, vivier de 5 063 personnes, 2 693 déplacements, sha256 `f67b0777…`). Tant
qu'elle n'est pas réalignée, les chapitres 1 et 4 ne décrivent pas le même substrat. L'en-tête du
chapitre 4 le signale.

### 11 septembre 2026 — l'article n'avait pas de section système

Constat, à l'occasion d'un dépouillement des sommaires du corpus d'état de l'art : **le dispositif
évalué n'était décrit nulle part**. Le texte passait de l'introduction aux métriques, et le manuscrit
figé `v1.6` faisait de même. Or aucun article comparable du corpus n'en fait l'économie — Alves et al.
(2026) § 4 *Methodology*, Liu, Yang & Yin (2024) § 3 *System Design*, CitySim § 3 *Method*, Park et al.
(2023) *Approach*. Écart relevé par le tutorat.

Retenu : une **section 3, « Le dispositif »**, placée avant l'évaluation — on décrit l'objet, puis
comment on le juge. Les sections 3 à 8 antérieures décalent d'un cran, jusqu'à la section 9.

| | Avant (11 septembre, matin) | Après — retenu |
|---|---|---|
| § 3 | Métriques et socle d'évaluation | **Le dispositif : décider dans une ville contrainte** (neuf) |
| § 4 à § 8 | LLM nus … Conclusion | décalées en § 5 à § 9 |

Ce que la section 3 **ne porte pas** : le passage à l'échelle du dispositif (batching, répartition de
charge, disjoncteur, caches), écarté du chapitre sur décision de l'auteur. Si ce matériel doit
figurer, sa place est en annexe technique.

Conséquence sur le chapitre 1 : seule la phrase de la section 1.4 change, dans les trois arbres —
`v0.17` → `v0.18`, versions antérieures figées dans [`../../archive/`](../../archive/).

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
