# Projet LaTeX de l'article court — AAMAS 2027

Projet compilable du **papier court** (8 pages), créé le 2026-09-22. Il est autonome et
distinct de celui du papier long (`../../article/overleaf/`), dont il reprend le préambule,
le réglage des flottants, le bloc de copyright et le bloc d'auteurs — et rien d'autre.

**Les masters sont les Markdown de `../sections/`.** Les `.tex` de `chapters/` en sont
dérivés : après toute passe validée sur une section, on régénère le `.tex` correspondant.
Les commentaires `<!-- source: … -->` du Markdown sont la trace de provenance et **ne sont
pas repris** dans le LaTeX (décision de l'auteur, 2026-09-21, reconduite ici).

## Ce qu'on téléverse sur Overleaf

Le projet Overleaf est le miroir exact de ce dossier. **Tout téléverser tel quel**, rien à
déplacer :

| Fichier | Rôle |
|---|---|
| `main.tex` | Fichier maître : préambule, titre, auteurs, `\input` des sept chapitres |
| `supplementary.tex` | Seconde racine : le matériel supplémentaire (annexes), une colonne, hors des 8 pages |
| `repository.tex` | Adresse du dépôt anonyme, lue par les deux racines ; **seul endroit où elle est écrite** |
| `chapters/00_Abstract.tex` … `07_Implications.tex` | Les sept sections, une par fichier, dans l'ordre de lecture |
| `chapters/08_Appendices.tex` | Les annexes, lues par `supplementary.tex` seulement (annexe D au 2026-09-24) |
| `images/` | Les cinq figures appelées par le corps |
| `sample.bib` | Bibliographie **réelle**, sous-ensemble de `../../sources/sample.bib` restreint aux clés citées |
| `aamas.cls`, `ACM-Reference-Format.bst` | Style imposé par la conférence, copiés du gabarit ; **ne rien y modifier** |
| `by.pdf`, `by.eps` | Logo Creative Commons du bloc de licence |

**La bibliographie n'est pas `template/sample.bib` du gabarit.** Ce fichier-là est la démo
ACM, onze clés factices, et aucune des vingt clés citées ici n'y figure : chaque `\citep`
imprimerait `[?]`. Le `sample.bib` de ce dossier est extrait de
`../../sources/sample.bib` : il n'en garde que les 29 clés citées par le LaTeX et par les
masters anglais (audit des citations du 2026-09-24). **On ne le corrige pas ici** : toute
correction se fait dans `../../sources/sample.bib`, puis on refait l'extraction, et les deux
copies `overleaf/` et `overleaf-fr/` restent identiques.

## Comment compiler

**Quatre passes : pdfLaTeX → BibTeX → pdfLaTeX → pdfLaTeX.** Une seule passe imprime les
renvois en `??` et les citations en `[?]`. Sur Overleaf, régler le compilateur sur pdfLaTeX
et lancer deux fois après la première compilation complète.

## Le matériel supplémentaire

Les annexes A à J du plan (`../PLAN.md` § 9) partent en matériel supplémentaire, hors des
8 pages : AAMAS le reçoit en **un ZIP de 25 Mo au plus**, sous les mêmes règles de double
anonymat que le papier. Elles se compilent dans **`supplementary.tex`**, seconde racine du même
projet, qui reprend la classe, le bloc de copyright et les auteurs de `main.tex`, au format
`manuscript` (une colonne) pour que les longues lignes des prompts restent lisibles. Il
`\input` `chapters/08_Appendices.tex`, rendu à la main de `../sections/08_appendices.en.md`.
Au 2026-09-24, seule l'**annexe D** y figure : les trois prompts et un trajet décidé sous
chacun. Le `\setcounter{section}{3}` en tête du chapitre la fait imprimer « D » ; il saute
quand A, B et C seront écrites.

- **Compiler :** sur Overleaf, *Menu → Main document → `supplementary.tex`*, compiler, puis
  remettre `main.tex`. Deux passes pdfLaTeX suffisent : aucune citation, donc pas de BibTeX.
- **Paquet requis :** `fvextra`, pour les blocs verbatim qui coupent leurs lignes. Il est dans
  TeX Live, donc sur Overleaf.
- **Renvois :** le corps nomme les annexes en texte brut (« Appendix D ») : les deux racines
  compilent séparément, il n'y a pas de `\label` commun à viser.

## Le dépôt anonyme

L'adresse `https://anonymous.4open.science/r/TBD` n'est écrite qu'**une fois**, dans
`repository.tex` (`\repoid`). Elle sert à la note de bas de page du § 4.1 et aux quatre liens
de l'annexe D.1. **Avant la soumission, remplacer `TBD`** par l'identifiant que donne
anonymous.4open.science : c'est la seule modification à faire (consigne R14, pas de
placeholder dans le texte livré). Les liens de l'annexe supposent que le dépôt anonymisé garde
l'arborescence de ce dépôt-ci ; le vérifier en ouvrant chacun d'eux une fois le dépôt créé.
`\url{}` ne développe pas les macros : l'adresse s'imprime avec `\texttt{\repodisplay}` et
se lie avec `\href{\repobase/...}`.

## Ce qu'il faut regarder sur le premier PDF

C'est l'objet de l'item **G4** de `../RELECTURE_V1.en.md` : personne n'avait encore compilé,
et les 8 pages décident des coupes du § 10 du plan.

1. **Le nombre de pages**, 8 au plus, références non comprises.
2. **Les cinq figures et les quatre tableaux** : aucun ne doit flotter à des pages de son
   texte. Si un flottant dérive, le premier réglage à toucher est `[tbp]` / `[tp]`, pas la
   mise en page (le gabarit interdit de la modifier, et les 8 pages ne se gagnent que par
   le texte).
3. **Les crochets** : `[c2, …]` aux § 5.1 et 5.3, `[replay pending]` dans le tableau 1. Ils
   sont **volontaires** et attendent le ticket 103. Ils sont posés en texte brut, pas avec
   `\todo` qui imprime en gras : lisibles, pas criards. Rien d'autre ne doit être entre
   crochets.
4. **Si le PDF dépasse 8 pages**, la première coupe prévue est le tableau 4 (§ 6.4), dont la
   phrase de remplacement est déjà rédigée dans `chapters/06_Non_tabulated.tex`, en
   commentaire d'en-tête.

## Figures encore à régénérer

`../PLAN.md` § 9 les signale toutes les deux ; les PNG livrés ici sont les versions
actuelles, pas les versions finales.

| Fichier | Ce qui manque |
|---|---|
| `images/ch6_echelle.png` (figure 2) | La colonne d'étendue inter-graines. Les quinze lignes, elles, y sont déjà. |
| `images/ch7_propension_quotidienne.png` (figure 5) | Titre, axes, légende et annotations encore en français (`témoin`, `exposé`, `avarie`). Toutes les figures de l'article se composent en anglais. |

`images/ch6_audit_modes.png` (figure 4) est posée sur une colonne, comme le plan le demande,
alors que le papier long la met sur deux. Si ses deux panneaux de barres deviennent
illisibles à 240 pt, la passer en `figure*` : cela ne coûte pas de page, l'article étant
contraint par ses flottants et non par sa hauteur de texte.

## Ce que le gabarit impose, et qui nous concerne ici

- **Anonymat** : `\documentclass[sigconf,anonymous]{aamas}` pour la soumission ; la variante
  sans `anonymous` est en commentaire dans `main.tex`, pour la version finale seulement.
- **Préambule à remplir** : `\acmSubmissionID{…}` avec le numéro OpenReview, et
  `\submissionType{…}` pour la piste visée.
- **Citations numériques** : `\bibliographystyle{ACM-Reference-Format}` imprime `[12]`.
  `\citet` donne « Auteur [12] », `\citep` donne « [12] ». Les formes auteur-année écrites
  dans le Markdown ne survivent donc pas dans le PDF : la relecture des citations se fait
  sur le PDF compilé, pas sur le Markdown.
- **Tableaux** : légende **au-dessus**, `booktabs`, `\midrule` réservé à la séparation de
  l'en-tête et des données (c'est ce qui permet aux technologies d'assistance de reconnaître
  les en-têtes).
- **Figures** : légende **en dessous**, et un `\Description{…}` obligatoire pour chacune —
  texte brut, 2 000 caractères au plus, non imprimé.
- **Mise en page non négociable** : marges, corps, interligne. Tout recours excessif à
  `\vspace` expose au rejet.
