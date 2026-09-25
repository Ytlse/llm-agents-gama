# Outils de traduction et de rendu LaTeX — article court

L'anglais fait foi (consigne **R17**). Le français est un rendu, et le LaTeX un rendu du
rendu. Ces quatre outils déplacent du texte d'un maillon au suivant et vérifient qu'il n'a
rien perdu en route. **Aucun ne fait appel à un modèle de langue** : la traduction se fait
dehors, dans l'outil de votre choix, et revient par fichier.

```
sections/NN_<slug>.en.md          master, ce qui fait foi
   │  make paper-court-extraire S=NN
   ▼
traductions/<slug>.a-traduire.txt lot à traduire, blocs [[n]], 4 500 signes par partie
   │  vous, dans DeepL ou ailleurs
   ▼
traductions/<slug>.traduit.txt
   │  make paper-court-passe S=NN FR=<fichier>
   ▼
sections/NN_<slug>.fr.md
overleaf/chapters/NN_Nom.tex  et  overleaf-fr/chapters/NN_Nom.tex
```

## Les trois fichiers

| Fichier | Rôle |
|---|---|
| `modele_document.py` | découpe une section en blocs typés. C'est le contrat commun : extraction et injection voient la même numérotation, donc un texte traduit se repose là où il a été pris. |
| `extraire_blocs.py` | sort le texte traduisible. Les commentaires `<!-- source: -->`, les maths, les cellules numériques et le compte-rendu ne sortent jamais. |
| `injecter_traduction.py` | reconstruit le `.fr.md` depuis la structure de l'anglais : mêmes coupes, commentaires de source recopiés à l'octet, typographie française des nombres. |

## Le report vers le LaTeX n'est plus outillé

`md_vers_tex.py` portait la prose du Markdown dans les `.tex` en y raccrochant le balisage
éditorial — clés de citation, `\label`, renvois, italiques, flottants. **Il a été supprimé le
2026-09-23**, sur décision de l'auteur, après une mesure chapitre par chapitre :

| Chapitres | Ce que l'outil faisait |
|---|---|
| 1, 2 | traités correctement, rien à reporter |
| 0, 3, 4, 5, 6 | **refusés** : il compte les paragraphes des deux côtés, et une légende de flottant compte pour un paragraphe côté Markdown — de 1 à 8 d'écart |
| 7 | **pire qu'un refus** : il proposait un report qui cassait trois renvois, en gardant le numéro littéral *et* en ajoutant la commande (`Section~\ref{sec:mechanism} 6.2`), ou en posant la commande à côté de sa cible (`The traced path of Section 6 rests~\ref{sec:nontabulated} on one agent`) |

Deux chapitres sur huit, et un piège sur un troisième. **Les `.tex` se tiennent désormais à la
main**, et la date d'en-tête de chaque chapitre dit s'il est en phase avec son master : voir
[`../sections/README.md`](../sections/README.md).

Sont partis avec le fichier trois cibles `make` — `paper-court-tex`, `paper-court-tex-ecrire`
et `paper-court-tex-verifier`. La dernière était le seul contrôle automatique des citations et
des renvois sur les seize chapitres des deux projets, et **rien ne la remplace aujourd'hui**.

Le fichier n'a jamais été commité. Son objet reste dans le dépôt tant qu'un `git gc` n'est pas
passé : `git cat-file -p 2c1d2ad711ecb15fc07e4617e45013f09c5f0e35` le rend.

## Si le traducteur mange les balises

Le lot porte des lignes `[[12]]`. Si l'outil les supprime, l'injection se recale sur
l'**ordre des blocs** : elle marche toujours, et refuse d'écrire si les comptes ne tombent
pas juste. Une balise suivie de son texte sur la même ligne est acceptée.

## Essai à blanc

L'essai à blanc passait par `md_vers_tex.py --md … --tex …`, supprimé. Il n'y a plus de
rendu LaTeX candidat à comparer.
