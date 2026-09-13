# Spec — « S'inspirer d'une expérience existante » recopie dès le choix

## Problème

Choisir une expérience dans la liste « S'inspirer d'une expérience existante » ne fait rien
par lui-même : le formulaire ne bouge qu'après un second clic sur « Recopier ses réglages ».
Le choix se lit pourtant comme une action — l'utilisateur attend que les champs suivent, et
tant que le bouton n'est pas cliqué le formulaire montre des réglages qui ne sont pas ceux de
l'expérience affichée dans la liste. Deux gestes pour une seule intention.

## Utilisateurs

- **Le chercheur** qui compose ses expériences sur sa machine : seul utilisateur, tous droits.
  Il part d'une expérience déjà enregistrée, change un ou deux réglages (prompt, modèle,
  décideur) et enregistre ou lance la nouvelle.

## Règles métier

- **R1** — Choisir une expérience dans la liste remplace **immédiatement tous les champs** du
  formulaire par les réglages de cette expérience, sans autre clic. L'effet est exactement celui
  qu'avait « Recopier ses réglages ».
- **R2** — Choisir « — partir de zéro — » après une expérience remet
  **tous les champs aux défauts** de la plateforme.
- **R3** — La recopie ne recopie jamais le **nom** : il se recalcule des paramètres (N1) ; la
  filiation `derive_de` cite l'expérience source. Inchangé.
- **R4** *(déduite)* — L'ouverture de la page ne recopie rien : la liste est sur
  « — partir de zéro — » et le formulaire montre le brouillon du dernier passage (R21). Seul un
  **changement de choix** par l'utilisateur déclenche la recopie.
- **R5** *(hypothèse appliquée — Q2 en attente)* — Après avoir modifié des champs, l'utilisateur peut **recopier à
  nouveau** l'expérience déjà choisie d'un clic (« ↺ Recopier à nouveau »), puisque rechoisir la
  même entrée n'est pas un changement.
- **R6** *(déduite)* — Une expérience qui a **disparu du disque** entre l'affichage de la liste et
  le choix ne casse rien : le formulaire garde ses valeurs, la page dit que l'expérience n'existe
  plus, et la liste revient sur l'expérience encore recopiée dans le formulaire — ou sur
  « — partir de zéro — » s'il n'y en a pas.
- **R7** *(déduite)* — Une expérience dont une valeur **ne désigne plus rien** ou est **hors
  bornes** ne casse pas la page — mêmes règles que la relecture du brouillon (R21b) : une valeur
  inconnue (population effacée, modèle retiré de `providers.yaml`, variante de prompt renommée)
  revient à son défaut, une valeur numérique hors bornes (parallélisme 128) est ramenée dans
  l'intervalle du champ, les autres champs sont recopiés.
- **R8** *(déduite)* — Après la recopie, la page **dit ce qu'elle a fait** : l'expérience
  recopiée, et que le nom se recalculera. Cette légende reste affichée **tant que le formulaire
  est celui qui vient d'être recopié**, et disparaît à la **première retouche** d'un champ : sur un
  formulaire retouché elle mentirait. Une relance de la page sans retouche ne l'efface pas.
- **R9** *(déduite)* — La recopie n'écrit rien sur le disque en dehors du brouillon du
  formulaire (R21), qui ne reçoit que des valeurs validées par R7. Aucune expérience, aucune
  exécution n'est touchée.
- **R10** *(déduite)* — Une expérience **supprimée du disque après avoir été choisie** est signalée
  à l'interaction suivante : le formulaire garde ses réglages, la liste revient sur
  « — partir de zéro — », et « ↺ Recopier à nouveau » est grisé. L'avertissement suit la règle de
  R8 (affiché tant que le formulaire n'est pas retouché) ; le journal, lui, ne le dit qu'une fois. Sans cela la liste retombe
  en silence sur « — partir de zéro — » et contredit le formulaire — le défaut que cette spec
  entend supprimer.
- **R11** *(déduite)* — Un clic sur « ↺ Recopier à nouveau » parti **avant** la disparition de la
  source et arrivé **après** ne remet rien aux défauts : le formulaire garde ses réglages, et
  l'avertissement R10 le dit.

## Critères d'acceptation

- **R1** — expérience `A` enregistrée avec parallélisme 16, température 0.7, variante `b_min` ;
  formulaire sur les défauts → choisir `A` dans la liste → sans autre clic, le formulaire montre
  16, 0.7, `b_min`, et le nom calculé en tête est celui de `A`.
- **R2** — après le critère R1, choisir « — partir de zéro — » → parallélisme 8, température 0.0,
  variante active : les défauts.
- **R3** — expérience source nommée `un_nom_historique` → après recopie, aucun champ « nom » n'est
  saisi, la filiation vaut `un_nom_historique`, le nom affiché est recalculé.
- **R4** — brouillon enregistré avec parallélisme 16 ; page rouverte → la liste affiche
  « — partir de zéro — » et le formulaire montre 16, pas 8.
- **R5** — `A` choisie, parallélisme passé à la main de 16 à 4 → clic « ↺ Recopier à nouveau » →
  parallélisme 16 ; le bouton est grisé quand la liste est sur « — partir de zéro — ».
- **R6** — `A` recopiée (parallélisme 16), dossier de `B` supprimé après le rendu de la liste →
  choisir `B` → aucune exception, parallélisme toujours 16, message « l'expérience « B » n'existe
  plus », liste revenue sur `A`.
- **R7** — `A` porte `parallelisme: 128` et `modele: fantome/absent` → choisir `A` → aucune
  exception, parallélisme 64 (borne haute du champ), modèle = premier modèle connu, température
  et variante recopiées.
- **R8** — choisir `A` → la page affiche « réglages de « A » recopiés — le nom se recalcule » ;
  une relance sans retouche → toujours affichée ; une retouche du parallélisme → plus affichée.
- **R9** — choisir `A` → `data/experiences/` est inchangé à l'octet ; seul le fichier de
  brouillon a changé, et il ne contient que des valeurs acceptées par la validation R21b.
- **R10** — `A` recopiée (16), dossier de `A` supprimé, puis n'importe quelle interaction → message
  « l'expérience « A », recopiée dans le formulaire, n'existe plus », parallélisme 16, liste sur
  « — partir de zéro — », « ↺ Recopier à nouveau » grisé ; une relance sans retouche → message
  toujours là ; une retouche → plus de message.
- **R11** — `A` recopiée (16), bouton « ↺ Recopier à nouveau » actif, dossier de `A` supprimé, clic
  → parallélisme 16 (pas 8), message R10 affiché.

## Non-goals

- Ne pas changer « 📋 Dupliquer » dans « Mes expériences » : même recopie, même comportement
  qu'aujourd'hui, et la liste « S'inspirer » n'est pas repositionnée sur l'expérience dupliquée
  (Q3, tranché le 2026-09-08 : hors périmètre).
- Aucun « annuler » : un choix écrase les champs, le brouillon n'a pas d'historique.
- Aucune fusion de deux expériences, aucune recopie partielle (« seulement le décideur »).
- Le calcul du nom, la grammaire du nom et la détection de doublon ne bougent pas.
- Rien ne change côté GAMA ni dans `experience.yaml`.

## Sécurité

- Un seul utilisateur local ; aucune authentification n'entre en jeu.
- Les `experience.yaml` sont **des données, pas des commandes** : toute valeur relue passe par la
  validation R21b (listes connues, bornes, date ISO) avant d'atteindre un champ. Aucun chemin lu
  dans un YAML ne sert à écrire ou à exécuter quoi que ce soit.
- La recopie n'écrit que le brouillon du formulaire, dans son fichier habituel ; jamais dans
  `data/experiences/`.
- Les noms d'expériences affichés viennent du disque local et sont rendus par Streamlit comme
  du texte, jamais interprétés.

## Questions ouvertes

Tranchées le 2026-09-08 : **Q1** (oui : « — partir de zéro — » remet les défauts, R2) et **Q3**
(hors périmètre : « Dupliquer » ne repositionne pas la liste).

- **Q2** *(en attente, hypothèse appliquée : le bouton reste)* — Concrètement : vous choisissez
  l'expérience `A`, ses réglages arrivent dans le formulaire, vous changez le parallélisme à la
  main, puis vous voulez **revenir aux réglages de `A`**. Rechoisir `A` dans la liste ne fait
  rien, puisqu'elle est déjà sélectionnée. Deux options : (a) garder un petit bouton
  « ↺ Recopier à nouveau » à côté de la liste, qui réapplique `A` d'un clic ; (b) pas de bouton,
  il faut choisir « — partir de zéro — » puis rechoisir `A`. L'hypothèse appliquée est (a) ;
  dire « retire le bouton » suffit pour passer à (b).
- **Q4** *(relevé à la relecture, préexistant, non traité)* — La filiation `derive_de` fait partie
  du brouillon (R21) : après une recopie de `A`, la page rouverte le lendemain affiche
  « — partir de zéro — » (R4) mais une expérience enregistrée depuis ce brouillon déclarera
  `derive_de: A`. Vrai avant cette spec (le bouton « Recopier ses réglages » faisait pareil).
  Faut-il effacer la filiation à la réouverture, ou l'afficher ?
- **Q5** *(relevé à la relecture, préexistant, hors périmètre par Q3)* — « 📋 Dupliquer » recopie
  sans la validation R7 : une expérience à `parallelisme: 128` casse encore la page depuis
  « Mes expériences » alors qu'elle est absorbée depuis « S'inspirer ». Aligner « Dupliquer » sur
  R7 est un mot à ajouter ; à décider.
