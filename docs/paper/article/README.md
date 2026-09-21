# Le texte de l'article

Un chapitre par section de l'article, dans trois arbres parallèles :

| Dossier | Contenu |
|---|---|
| [`en/`](en/) | **maître anglais** — c'est le texte de référence |
| [`fr/`](fr/) | miroir français, et brouillons des chapitres pas encore rédigés |
| [`overleaf/`](overleaf/) | rendu LaTeX, à inclure dans le projet Overleaf **dans l'ordre des numéros** |
| [`relecture/`](relecture/) | relecture section par section, un fichier par chapitre |
| [`plan/`](plan/) | la trame, dérivée du texte — voir [`plan/README.md`](plan/README.md) |
| [`CITATIONS.md`](CITATIONS.md) | vérification des citations, une entrée par référence |
| [`SOUMISSION_AAMAS_2027.md`](SOUMISSION_AAMAS_2027.md) | consignes de soumission : OpenReview, format, matériel additionnel, règles IA |
| [`overleaf/template/`](overleaf/template/) | gabarit officiel AAMAS 2027 (`aamas.cls`, style de références, exemple) |
| [`ameliorations.md`](ameliorations.md) | points retirés du texte, à consolider ailleurs |
| [`actions.md`](actions.md) | actions pour écrire le papier, risques relecteurs et objections |

Le numéro de fichier **est** le numéro de section annoncé en 1.4 du chapitre 1. Une
renumérotation se voit donc dans `git status`, et pas seulement dans une phrase.

Chaque fichier porte, juste après son titre, un commentaire `Dernière mise à jour : AAAA-MM-JJ`
— `<!-- … -->` en Markdown, `% …` dans l'en-tête LaTeX. Il donne la date de la dernière
modification du fichier, à mettre à jour **dans la même passe** que le texte ; les numéros de
version, eux, restent dans l'en-tête. Un commentaire qui ne bouge pas quand le texte bouge est
pire que pas de date du tout.

**Pas de formule-slogan en tête de paragraphe.** « Une famille, pas un oracle désigné »,
« X, pas Y », « ceci n'est pas cela » : ces tournures annoncent une posture au lieu d'énoncer un
fait, elles ne se vérifient pas, et elles survivent aux mesures qui les contredisent — celle-là
est restée en place alors que le § 4.4 désignait l'oracle sous critère écrit. Un paragraphe
commence par ce qu'il établit.

**Le chapitre ne plaide pas.** Une phrase qui défend un choix contre une objection que personne
n'a formulée sort du texte : « ce n'est pas un raffinement de présentation », « elle n'est pas
cosmétique », la mise en garde méthodologique préventive contre un test qu'on n'emploie pas, la
déclaration défensive d'un réglage. Le chapitre dit ce qu'il fait et sur quoi, et prend position
avec ses chiffres ; l'objection se traite au chapitre des limites, ou pas du tout. Corollaire :
un chiffre qui n'alimente aucune affirmation du chapitre sort du corps du texte, et vit en
commentaire HTML ou en annexe. Règle tirée de la relecture du chapitre 4, 16 septembre 2026.

**Ce qui n'entre pas dans le texte.** Une phrase qui décrit la fabrication plutôt que la mesure
n'a pas sa place dans un chapitre : versions antérieures archivées, dossier « immuable » ou « en
service », fichier « figé dans le dépôt », empreintes, ce qui est gelé où. Le texte dit ce qui est
mesuré, sur quoi et comment ; la traçabilité vit dans les commentaires HTML `<!-- source: … -->`
à côté du chiffre, et dans le dépôt.

Elle s'arrête là : le rendu LaTeX d'[`overleaf/`](overleaf/) ne reprend **aucun** commentaire
`source:`. Décision de l'auteur, 21 septembre 2026 — les notes alourdissaient le fichier collé dans
Overleaf sans rien y apporter, `fr/` et `en/` les portant déjà. Une traduction ne les réintroduit
pas ; l'en-tête de chaque `.tex` le rappelle.

## État d'avancement

| # | Chapitre | EN | FR | LaTeX | Relecture |
|---|---|---|---|---|---|
| 0 | Résumé (*abstract*) | `v1.9` | `v1.9` | `v1.9` | [00](relecture/00_abstract.md) |
| 1 | Introduction | `v0.26` | `v0.26` | `v0.25` | [01](relecture/01_introduction.md) |
| 2 | État de l'art (*related work*) | `v0.19` | `v0.19` | `v0.19` | dans le fichier du ch. 1 |
| 3 | Le dispositif (*architecture*) | `brouillon v0.7` | `brouillon v0.7` | `v0.7` | — |
| 4 | Métriques et socle d'évaluation | `brouillon v0.19` | `brouillon v0.19` | `v0.18` | — |
| 5 | Quatre façons de choisir, une seule information *(protocole)* | `brouillon v0.11` | `brouillon v0.11` | `v0.10` | — |
| 6 | Résultats | `brouillon v0.4` | `brouillon v0.8` | `v0.4` | — |
| 7 | Régimes non tabulés | `brouillon v1.0` | `brouillon v1.0` | `v1.0` | — |
| 8 | Limites et implications hybrides | `brouillon v0.3` | `brouillon v0.3` | `v0.2` | — |
| 9 | Conclusion | `brouillon v0.2` | `brouillon v0.2` | `v0.2` | — |
| 99 | Annexes techniques | `brouillon v0` | `brouillon v0` | `v0` | — |

**Ce tableau est un instantané, relevé le 21 septembre 2026** depuis la ligne de statut de chaque
fichier. Neuf de ses onze lignes étaient fausses ce jour-là : elles donnaient pour absents des
textes anglais et des rendus LaTeX qui existent depuis, et elles gelaient les versions du français
à leur état du 15 septembre. Le chapitre 6 est réellement désaligné, `v0.8` en français contre
`v0.4` en anglais et en LaTeX ; le chapitre 8 a changé de version pendant la journée du 21. Une
ligne qui ne bouge pas quand un chapitre bouge trompe davantage qu'une case vide : c'est la ligne
de statut du fichier qui fait foi, jamais ce tableau.

**Restructuration du 15 septembre 2026 — chapitres 5 et 6.** Le chapitre intercalaire 4.5 **a été
absorbé** par le chapitre 5, qui devient le chapitre de **protocole** (ce que l'on compare) ; le 6
reste celui des **résultats**. Le fichier d'origine est archivé sous
[`../archive/04.5_prompt_calibration_v0.1.md`](../archive/04.5_prompt_calibration_v0.1.md). Le titre du chapitre 6 n'est plus arrêté : les scores recalculés
depuis le dépôt contredisent l'hypothèse H0 de non-atteinte qu'il devait établir. Idée directrice,
titre et répercussions sur le résumé, le § 1.3 et le chapitre 9 sont en décision au
[ticket 080](../../tickets/ticket_080_idee_directrice_du_chapitre_6_et_impact_sur_le_papier.md).
L'avancement document par document du français est tenu dans [`fr/README.md`](fr/README.md).

## L'ordre de travail : le français d'abord, les traductions à la fin

Décision de l'auteur, 11 septembre 2026 : **les chapitres se rédigent et se relisent en français**,
et les maîtres anglais comme les rendus LaTeX s'écrivent **en fin de parcours**, une fois le fond
arrêté. `en/` reste le texte de référence pour la soumission — c'est l'ordre de fabrication qui
change, pas le statut des arbres.

Conséquence sur la parité : tant qu'un chapitre est en `brouillon`, l'absence d'anglais et de LaTeX
est normale et `make paper-parite` ne la compte pas comme un écart. Les chapitres 3 (`brouillon v0.5`) et 4 (`brouillon v0.5`) sont les premiers
écrits dans cet ordre : texte neuf, et non un extrait du manuscrit.

`brouillon` = texte français extrait du manuscrit détaillé `v1.6` (3 septembre 2026), **antérieur**
à la réécriture de l'introduction : vocabulaire « Tier 1/2/3 » à reprendre, chiffres à recouper
depuis le dépôt, renvois de section à refaire. Chaque fichier le dit dans son en-tête.

## La règle de parité

Les trois fichiers d'un chapitre rédigé portent le **même numéro de version**. Comme l'arbre par
langue les éloigne, la vérification est outillée :

```bash
make paper-parite
```

Elle sort en erreur quand un maître a bougé sans son miroir, quand une langue manque à un
chapitre rédigé, ou quand une section annoncée par [`plan/PLAN.md`](plan/PLAN.md) n'a aucun
fichier. Sur un chapitre encore en brouillon, l'absence d'anglais et de LaTeX est normale et
n'est pas comptée comme un écart.

## Ce qui n'est pas ici

Ce dossier porte tout ce qui concerne l'article AAMAS 2027 : son **texte**, sa trame, sa relecture, ses citations, ses consignes de soumission et le gabarit de la conférence. Ce qui le fonde vit à côté : la méthode et les mesures dans
[`../methode/`](../methode/), la matière première (état de l'art, presse locale, bibliographie)
dans [`../sources/`](../sources/), l'unique résumé GAMA Days — la seule chose ici qui ne concerne pas l'article AAMAS — dans
[`../gama_days/`](../gama_days/), les figures dans [`../figures/`](../figures/), les instantanés
figés dans [`../archive/`](../archive/).
