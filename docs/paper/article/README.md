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

Le numéro de fichier **est** le numéro de section annoncé en 1.4 du chapitre 1. Une
renumérotation se voit donc dans `git status`, et pas seulement dans une phrase.

Chaque fichier porte, juste après son titre, un commentaire `Dernière mise à jour : AAAA-MM-JJ`
— `<!-- … -->` en Markdown, `% …` dans l'en-tête LaTeX. Il donne la date de la dernière
modification du fichier, à mettre à jour **dans la même passe** que le texte ; les numéros de
version, eux, restent dans l'en-tête. Un commentaire qui ne bouge pas quand le texte bouge est
pire que pas de date du tout.

## État d'avancement

| # | Chapitre | EN | FR | LaTeX | Relecture |
|---|---|---|---|---|---|
| 0 | Résumé (*abstract*) | `v0.3` | `v0.3` | `v0.3` | [00](relecture/00_abstract.md) |
| 1 | Introduction | `v0.17` | `v0.17` | `v0.17` | [01](relecture/01_introduction.md) |
| 2 | État de l'art (*related work*) | `v0.17` | `v0.17` | `v0.17` | dans le fichier du ch. 1 |
| 3 | Métriques et socle d'évaluation | — | brouillon | — | — |
| 4 | Les LLM nus et leur variabilité | — | brouillon | — | — |
| 5 | Ablation en quatre paliers et références tabulaires | — | brouillon | — | — |
| 6 | Régimes non tabulés | — | brouillon | — | — |
| 7 | Limites et implications hybrides | — | brouillon | — | — |
| 8 | Conclusion | — | brouillon | — | — |
| 99 | Annexes techniques | — | brouillon | — | — |

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
