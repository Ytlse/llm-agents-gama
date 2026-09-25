# Projet LaTeX de l'article court — version française — AAMAS 2027

Projet compilable de la **version française du papier court**, créé le 2026-09-22. Il est le
jumeau de `../overleaf/`, le projet anglais, dont il reprend le préambule, le réglage des
flottants, le bloc de copyright, le `\graphicspath` et le bloc d'auteurs à l'identique, avec
les **mêmes noms de fichiers de chapitre** et les **mêmes `\label`**, pour que les deux
projets se lisent côte à côte.

## L'anglais fait foi

**Ce projet est un rendu, pas une source.** Décision de l'auteur du 2026-09-22, consigne
**R17** : pour l'article court, c'est **l'anglais qui fait foi** — l'inverse de l'article
long, où le français est la source de vérité. La chaîne est donc :

```
../sections/<n>_<nom>.en.md      master, ce qui fait foi
        ↓  rendu français
../sections/<n>_<nom>.fr.md      mêmes coupes de paragraphe, mêmes chiffres, mêmes figures
        ↓  génération LaTeX
chapters/<NN>_<Nom>.tex          ce dossier
```

On régénère un `.tex` après toute passe validée du `.fr.md` correspondant, lequel se
réaligne lui-même sur le `.en.md`. **Aucune amélioration de fond ne se décide côté
français** : elle se décide en anglais et redescend. Les commentaires `<!-- source: … -->`
des Markdown sont la trace de provenance et **ne sont pas repris** dans le LaTeX, comme dans
le projet anglais.

Les rendus français s'arrêtent au corps des sections. Trois éléments de ce projet n'ont donc
pas de `.fr.md` derrière eux et ont été rendus ici, à valider par l'auteur :

| Élément | Où | État |
|---|---|---|
| Le **titre** et son titre court | `main.tex` | rendu du titre anglais de `../PLAN.md` § 0 |
| Les **mots-clés** | `main.tex` | rendu des `\keywords` anglais |
| Les **`\Description{}`** des cinq figures | `chapters/` | rendu de ceux du projet anglais ; texte d'accessibilité, non imprimé |

La **note de bas de page du résumé**, qui cite l'enquête dans la forme que le diffuseur
impose, est reprise du projet anglais et traduite ; elle ne compte pas dans le budget de mots
et ne voyage pas dans le champ OpenReview.

## Ce qu'on téléverse sur Overleaf

Le projet Overleaf est le miroir exact de ce dossier. **Tout téléverser tel quel**, rien à
déplacer :

| Fichier | Rôle |
|---|---|
| `main.tex` | Fichier maître : préambule, langue, titre, auteurs, `\input` des sept chapitres |
| `chapters/00_Abstract.tex` … `07_Implications.tex` | Les sept sections, une par fichier, dans l'ordre de lecture |
| `images/` | Les cinq figures appelées par le corps, copiées du projet anglais |
| `sample.bib` | Bibliographie **réelle**, sous-ensemble de `../../sources/sample.bib` restreint aux clés citées |
| `aamas.cls`, `ACM-Reference-Format.bst` | Style imposé par la conférence ; **ne rien y modifier** |
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
renvois en `??` et les citations en `[?]`. Sur Overleaf, régler le compilateur sur pdfLaTeX.

```sh
pdflatex -interaction=nonstopmode main.tex
bibtex   main
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
```

**Aucun paquet à installer.** `babel` avec l'option `french` charge sans conflit sous
`aamas.cls` — vérifié le 2026-09-22 sur TeX Live 2026, `french.ldf` venant de `babel-french`,
présent dans toute TeX Live complète comme dans l'image Overleaf. Rien d'autre n'a été
ajouté au préambule anglais.

Il n'y a **pas de fichier d'annexes** : les annexes A à J du plan (`../PLAN.md` § 9) partent
en matériel supplémentaire, hors des 8 pages, et le corps les nomme en texte brut
(« annexe A ») faute de `\label` à viser.

## Typographie française : qui fait quoi

| Ce qu'il faut | Qui le pose |
|---|---|
| Espace fine insécable devant `;` `:` `?` `!` | **`babel` french**, tout seul. Les chapitres écrivent la ponctuation nue — **ne jamais doubler à la main.** |
| Espaces dans les guillemets `« … »` | **`babel` french**, tout seul. Les chapitres écrivent `«` et `»` nus. |
| Séparateur de milliers (`1 000`, `39 203`) | **Les chapitres**, en `\,` : `1\,000`, `39\,203`. L'espace fine U+202F du Markdown ne survivrait pas à pdfLaTeX. |
| Espace devant `%` (`95 %`) | **Les chapitres**, en `\,\%`. |
| Virgule décimale (`4,86`, `±1,3`) | Simple caractère ; `±` s'écrit `$\pm$`. |
| Coupure des mots à la française | **`babel` french** (motifs `loadhyph-fr`), plus `\emergencystretch=1.5em` dans `main.tex` — voir ci-dessous. |

Deux libellés restent en anglais parce qu'ils viennent de la classe et non de nous :
**`Keywords`** et **`ACM Reference Format`** en première page. `babel` traduit en revanche
« References » en « Références ». Ne pas corriger en touchant `aamas.cls`.

## Trois réglages que le projet anglais n'a pas besoin de porter

Le français écrit environ 10 % plus long que l'anglais et coupe moins volontiers ses mots.
Trois réglages, et seulement trois, compensent cela. Aucun ne touche aux marges, au corps ni
à l'interligne, que le gabarit interdit de modifier.

1. **`\emergencystretch=1.5em`** dans `main.tex`. Sans lui, cinq paragraphes débordaient dans
   la gouttière, jusqu'à 18,5 pt. Avec lui, il reste **un seul débordement**, de 1,9 pt, sur
   l'équation du § 4.3 — exactement le même que dans le projet anglais, et pour la même
   raison.
2. **Tableau 1 en `\small`, `tabcolsep` à 5 pt, intitulés de colonne repliés sur deux
   lignes.** Les intitulés français sont plus longs des deux côtés (« Prompt expert,
   classifieur à sortie typée (en échantillon) » contre « Expert prompt, typed classifier
   (in sample) ») et le tableau débordait `\textwidth` de 73 pt.
3. **Tableau 3** garde le repli sur deux lignes du projet anglais, avec des abréviations
   françaises (« Exact. », « Entr. crois. »).

## Ce qu'il faut regarder sur le PDF compilé

C'est l'objet de l'item **G4** de `../RELECTURE_V1.md`, et le compte de pages décide des
coupes du § 10 du plan.

1. **Le nombre de pages.** État au 2026-09-22 : **11 pages au total, 10 hors références**,
   contre **10 et 9** pour le projet anglais. Le français prend donc **une page de plus**, et
   les deux versions dépassent les 8 pages visées. La coupe se décide sur l'anglais, qui fait
   foi, et redescend ici.
2. **Les cinq figures et les quatre tableaux** : aucun ne doit flotter à des pages de son
   texte. Si un flottant dérive, le premier réglage à toucher est `[tbp]` / `[tp]`, pas la
   mise en page.
3. **Les crochets** : `[c2, …]` aux § 5.1 et 5.3, `[replay pending]` dans le tableau 1. Ils
   sont **volontaires** et attendent le ticket 103. Ils sont posés en texte brut, pas avec
   `\todo` qui imprime en gras. Rien d'autre ne doit être entre crochets. La mention
   `[replay pending]` reste en anglais des deux côtés : c'est l'étiquette d'un état de
   ticket, pas de la prose.
4. **Si le PDF dépasse la cible**, la première coupe prévue est le tableau 4 (§ 6.4), dont la
   phrase de remplacement est déjà rédigée en français dans
   `chapters/06_Non_tabulated.tex`, en commentaire d'en-tête.

## Figures encore à régénérer

`../PLAN.md` § 9 les signale toutes les deux ; les PNG livrés ici sont les versions
actuelles, pas les versions finales. **Ce sont les mêmes fichiers que le projet anglais** :
toutes les figures de l'article se composent **en anglais**, y compris dans cette version
française. Ne pas en faire une variante française.

| Fichier | Ce qui manque |
|---|---|
| `images/ch6_echelle.png` (figure 2) | La colonne d'étendue inter-graines. Les quinze lignes y sont déjà. |
| `images/ch7_propension_quotidienne.png` (figure 5) | Titre, axes, légende et annotations encore en français (`témoin`, `exposé`, `avarie`) : à passer en anglais. |

`images/ch6_audit_modes.png` (figure 4) est posée sur une colonne, comme le plan le demande,
alors que le papier long la met sur deux. Si ses deux panneaux de barres deviennent
illisibles à 240 pt, la passer en `figure*`.

## Ce que le gabarit impose, et qui nous concerne ici

- **Anonymat** : `\documentclass[sigconf,anonymous]{aamas}` pour la soumission ; la variante
  sans `anonymous` est en commentaire dans `main.tex`, pour la version finale seulement.
- **Préambule à remplir** : `\acmSubmissionID{…}` avec le numéro OpenReview, et
  `\submissionType{…}` pour la piste visée.
- **Citations numériques** : `\bibliographystyle{ACM-Reference-Format}` imprime `[12]`.
  `\citet` donne « Auteur [12] », `\citep` donne « [12] ». Les formes auteur-année écrites
  dans le Markdown ne survivent donc pas dans le PDF : la relecture des citations se fait sur
  le PDF compilé, pas sur le Markdown.
- **Tableaux** : légende **au-dessus**, `booktabs`, `\midrule` réservé à la séparation de
  l'en-tête et des données.
- **Figures** : légende **en dessous**, et un `\Description{…}` obligatoire pour chacune —
  texte brut, 2 000 caractères au plus, non imprimé. Les cinq tiennent sous la limite.
- **Mise en page non négociable** : marges, corps, interligne. Tout recours excessif à
  `\vspace` expose au rejet.
