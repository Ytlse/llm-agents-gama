# Gabarit officiel AAMAS 2027

Gabarit fourni par la conférence, déposé tel quel le 10 septembre 2026 (fichiers du 22 juillet 2026).
**Ne rien modifier ici** : `aamas.cls` et `ACM-Reference-Format.bst` sont les fichiers de style de la
conférence, et le gabarit interdit explicitement de les altérer. Les fichiers de travail de l'article
vivent dans `docs/paper/`, pas dans ce dossier.

| Fichier | Rôle |
|---|---|
| `AAMAS_2027_sample.pdf` | Consignes de mise en forme, compilées (2 pages) — le document à relire avant la première soumission |
| `AAMAS_2027_sample.tex` | Source du même document : sert de gabarit de départ |
| `aamas.cls` | Classe de document, identique à `acmart` sauf l'attribution de copyright à l'IFAAMAS |
| `ACM-Reference-Format.bst` | Style bibliographique imposé (citations **numériques**) |
| `sample.bib` | Bibliographie d'exemple : montre le format attendu pour chaque type d'entrée |
| `by.pdf`, `by.eps` | Logo Creative Commons du bloc de licence |
| `aamas27-logo-small.jpg` | Logo de la conférence utilisé par l'exemple de figure |

## Ce que le gabarit impose, et qui nous concerne

**Anonymat.** `\documentclass[sigconf,anonymous]{aamas}` pour la soumission : l'option remplace les
noms d'auteurs par le numéro de soumission. `\documentclass[sigconf]{aamas}` seulement pour la
version finale. C'est le mécanisme du double insu confirmé par l'appel à communications.

**Préambule à remplir.** `\acmSubmissionID{...}` avec le numéro attribué par OpenReview lors de
l'enregistrement du résumé, et `\submissionType{...}` pour la piste visée (met à jour l'en-tête et
le sous-titre — il ne faut plus écrire la piste dans le sous-titre).

**Mise en page non négociable.** Marges, corps de police, interligne, définitions de paragraphes et
de listes : toute modification, et tout recours excessif à `\vspace`, expose au rejet. La police
Libertine est obligatoire. Corollaire pratique : les 8 pages ne peuvent pas être gagnées par la mise
en page, seulement par le texte.

**Citations numériques.** `\bibliographystyle{ACM-Reference-Format}` et `\cite` produisent des
renvois numérotés du type « [4, 11] ». Notre rendu LaTeX écrit `\citep` / `\citet` (natbib, chargé
par la classe) : `\citet` continue de fonctionner et donne « Auteur [12] », mais la relecture doit se
faire sur le PDF compilé, pas sur le markdown.

**Noms d'auteurs complets dans la bibliographie.** « Donald E. Knuth », pas « D. E. Knuth ». Vérifié
le 10 septembre 2026 sur `docs/paper/sources/references.bib` : aucune entrée en initiales seules.

**Tableaux.** `table` + `tabular` avec `booktabs`, légende **au-dessus**, `\midrule` réservé à la
séparation de l'en-tête et des données — c'est ce qui permet aux technologies d'assistance de
reconnaître les en-têtes.

**Figures.** Légende **en dessous**, et une commande `\Description{...}` obligatoire pour chaque
figure non décorative : texte brut, 2 000 caractères au plus, non imprimé. Couleur autorisée à
condition de rester lisible en niveaux de gris et pour un lecteur daltonien.

**Version finale seulement.** Paquet `balance` et commande `\balance` pour équilibrer les colonnes
de la dernière page.

## Ce que le gabarit ne dit pas

Le gabarit renvoie explicitement à l'appel à communications pour **la limite de pages et les
exigences d'anonymat** : « Please consult the Call for Papers for information on matters such as the
page limit or anonymity requirements », sur <https://warwick.ac.uk/fac/sci/dcs/aamas2027/>.
Notre `docs/paper/article/SOUMISSION_AAMAS_2027.md` retient 8 pages de texte, figures et tableaux
comprises, plus des pages illimitées pour les seules références : à recouper sur cette page avant la
soumission, le gabarit ne l'atteste pas.
