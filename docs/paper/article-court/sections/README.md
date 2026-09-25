# Sections de l'article court

Dépôt des brouillons rédigés par l'agent `article-writer`, une section du plan par fichier.

| Fichier | Contenu |
|---|---|
| `NN_<slug>.en.md` | brouillon anglais, rédigé d'abord |
| `NN_<slug>.fr.md` | rendu français, produit après validation de l'anglais |

`NN` est le numéro de section de [`../PLAN.md`](../PLAN.md), de `01` à `07`. `08_appendices`
porte les annexes du § 9 du plan, dans l'ordre des lettres, destinées au matériel
supplémentaire (PDF séparé des 8 pages). Seule l'annexe D y est écrite au 2026-09-24. Son
`.tex` est `../overleaf/chapters/08_Appendices.tex`, compilé par `../overleaf/supplementary.tex`
et non par `main.tex` ; la règle des dates s'y applique comme aux autres. Un fichier ici
est un brouillon soumis, jamais une version validée : la validation se dit dans la
conversation, et le fichier reste tel que l'agent l'a rendu jusqu'à la passe suivante.

Les chiffres marqués `[c2]` dans le plan restent des placeholders nommés tant que le ticket
103 n'a pas rendu ses scores.

## La date fait foi pour la reprise du LaTeX

Il n'y a plus de générateur. `md_vers_tex.py` a été supprimé le 2026-09-23 : il ne savait
traiter que deux chapitres sur huit et en corrompait un troisième (voir
[`../outils/README.md`](../outils/README.md)). **Les `.tex` se reprennent à la main**, et ces
dates sont ce qui dit lesquels.


Chaque fichier anglais porte, sous son titre, la date de sa dernière écriture :

```
<!-- DERNIÈRE ÉCRITURE ANGLAISE : 2026-09-23 — … -->
```

Le `.tex` correspondant porte la même date entre parenthèses dans sa première ligne
d'en-tête, et il ne la porte que **tant qu'il est le rendu fidèle** de ce markdown.

**Les deux dates égales veulent dire : rien à reprendre. Les deux dates différentes veulent
dire : le `.tex` est en retard sur son master.** C'est la seule chose à regarder.

Conséquence, et elle est contraignante : **toute écriture dans un `.en.md` met à jour sa
date**, et toute reprise du `.tex` met la sienne à la même valeur — dans la même tâche,
jamais plus tard. Une date laissée en arrière fait passer pour à jour un fichier qui ne
l'est pas, ce qui est pire que pas de date du tout.

Les deux dates se relèvent d'un coup (commande corrigée le 2026-09-24 : l'ancienne cherchait
un en-tête « (23 September 2026) » que plus aucun `.tex` ne porte, et ne renvoyait rien) :

```bash
for f in docs/paper/article-court/sections/*.en.md; do n=$(basename "$f" .en.md); t=$(ls docs/paper/article-court/overleaf/chapters/ | grep -i "^${n%%_*}_"); printf '%-18s md %s | tex %s\n' "$n" "$(grep -m1 -oE 'ANGLAISE : [0-9-]+( [0-9:]+)?' "$f" | sed 's/ANGLAISE : //')" "$(sed -n 2p "docs/paper/article-court/overleaf/chapters/$t" | grep -oE '\([0-9-]+( [0-9:]+)?\)' | tr -d '()')"; done
```

Le numéro `NN` apparie les deux fichiers ; la casse des noms diffère d'un dossier à l'autre.

La date porte l'heure, à la seconde : deux écritures le même jour ne se distinguent pas
autrement. Une entrée peut ne porter que le jour, sans heure — c'est le cas de `00_abstract`,
dont l'heure est perdue.

**Ne jamais dater d'après le `mtime` du fichier.** Toute écriture le remet à l'heure de
l'écriture, y compris une écriture qui ne touche qu'un commentaire, y compris la pose du
marqueur lui-même. Le marqueur est la seule trace ; c'est celui qui écrit qui le met à jour,
à la main, dans la même tâche.

Convention posée le 2026-09-23 à la demande de l'auteur. Les horodatages initiaux ont été
relevés dans l'index git (`git ls-files --debug`), qui gardait les `mtime` d'avant la pose des
marqueurs. `05_results` porte l'heure de sa dernière reprise, les autres celle que l'index
donnait.
