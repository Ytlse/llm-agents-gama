# Spec — Enregistrer une expérience sans la lancer

## Problème

Écrire son expérience aujourd'hui et la lancer demain est impossible dans deux cas courants.
Tant qu'aucun jeu de déplacements n'est préparé pour la population, le bouton
« 💾 Enregistrer et valider » est grisé, alors que le schéma de la plateforme accepte sans
broncher une expérience qui nomme un jeu pas encore construit. Et l'enregistrement est soudé à
une validation qui tourne dans le conteneur `controller` : service arrêté, le fichier est bien
écrit mais l'écran affiche une erreur Docker, qui se lit comme un enregistrement raté.

## Utilisateurs

- **Le chercheur** qui prépare ses expériences sur sa machine : seul utilisateur, tous droits.
  Il compose une expérience, l'enregistre, construit le jeu (une heure), revient la lancer.

## Règles métier

- **R1** — Un bouton écrit `data/experiences/<nom>/experience.yaml` sans rien lancer. Il ne
  dépend ni du service `controller`, ni de l'existence du jeu de déplacements.
- **R2** — Quand la population n'a aucun jeu, l'expérience enregistrée **nomme le jeu qu'elle
  attend** : celui que le bouton de warm-up construirait, soit `<population>_<AAAAMMJJ>` pour le
  jour choisi. Le fichier est donc exploitable tel quel dès que ce jeu est clos.
- **R3** — La validation par la plateforme est une étape distincte, tentée seulement quand
  `controller` tourne. Service arrêté, l'enregistrement est confirmé et l'absence de validation
  est écrite ; elle n'est jamais présentée comme un échec d'enregistrement.
- **R4** — Après enregistrement, la page dit le chemin écrit, le jeu attendu, et l'état de ce
  jeu : absent, en construction, ou clos et prêt.
- **R5** — Le seul motif qui empêche encore d'enregistrer est un nom d'expérience vide ou refusé.
- **R6** *(déduite)* — Enregistrer sous un nom qui porte déjà des exécutions le dit avant
  d'écrire, et une case de confirmation garde le bouton : la définition change pour les
  exécutions futures. Les exécutions archivées ne bougent pas, chacune portant sa propre copie
  figée de la définition dans son `execution.yaml`.
- **R7** *(déduite)* — Le jeu attendu suit la date choisie : changer le jour simulé change le nom
  du jeu attendu, et la page l'écrit avant l'enregistrement.
- **R8** *(déduite)* — Enregistrer deux fois sans rien changer laisse le fichier identique et le
  dit. Aucune exécution n'est créée, aucun dossier d'exécution n'est touché, jamais.
- **R9** *(déduite)* — Une expérience enregistrée dont le jeu n'est pas encore clos apparaît dans
  « Mes expériences » avec ce fait dit, distinct d'une expérience prête à lancer.

- **R10** *(déduite)* — La validation n'est tentée que si le service `controller` est **connu en
  marche**. État inconnu, service arrêté, ou exécution en direct indisponible : l'enregistrement est
  confirmé et la ligne dit que la validation n'a pas été tentée, avec la raison. Aucune commande
  n'est lancée dans ces cas : l'enregistrement n'attend jamais Docker.
- **R11** *(déduite)* — Quand la validation est tentée, sa sortie s'affiche sous une étiquette qui
  la nomme, pour qu'un échec de validation ne puisse pas se lire comme un échec d'enregistrement.
  Son délai d'attente est de vingt secondes, la validation n'étant qu'une vérification de schéma.

## Critères d'acceptation

- **R1** — population sans aucun jeu, `controller` arrêté, nom renseigné → le bouton est actif,
  le clic écrit le fichier, aucune exécution n'apparaît.
- **R2** — population `population_1000_AAMAS`, jour 2026-03-16, aucun jeu → le fichier écrit
  porte `jeu.nom: population_1000_AAMAS_20260316`, et ce nom est celui que le bouton de warm-up
  passerait à `make jeu`.
- **R3** — `controller` arrêté → message « enregistré, non validé : le service `controller` ne
  tourne pas » ; `controller` actif → la sortie de la validation est affichée sous le message
  d'enregistrement.
- **R4** — après le clic, la page affiche le chemin relatif du fichier et « jeu attendu
  `population_1000_AAMAS_20260316` : à construire ».
- **R5** — nom vide → bouton grisé avec son motif ; nom `../../evade` → grisé avec son motif ;
  nom valide → actif, quel que soit l'état du jeu et du contrôleur.
- **R6** — nom d'une expérience portant deux exécutions → avertissement nommant le nombre
  d'exécutions, bouton grisé jusqu'à la case cochée ; après écriture, les deux dossiers
  d'exécution et leurs `execution.yaml` sont inchangés à l'octet.
- **R7** — jour changé de 2026-03-16 à 2026-03-17 → le jeu attendu devient
  `population_1000_AAMAS_20260317` à l'écran comme dans le fichier.
- **R8** — deux clics de suite → même contenu de fichier, message disant que rien n'a changé,
  et `data/experiences/<nom>/executions/` inchangé.
- **R9** — expérience enregistrée dont le jeu n'existe pas → sa ligne du registre dit « jeu à
  construire » ; jeu clos → la ligne ne le dit pas.

- **R10** — état des services inconnu → message « validation non tentée : l'état des services
  Docker est inconnu », et aucune commande n'a été exécutée ; contrôleur arrêté → même forme avec
  sa raison ; contrôleur en marche → la validation est bien lancée.
- **R11** — validation lancée → la sortie est précédée de « validation par la plateforme : », et
  le délai passé à l'exécution en direct est de vingt secondes.

## Non-goals

- Ne pas construire le jeu à l'enregistrement : c'est une heure de calcul, elle reste un clic
  explicite.
- Ne pas gérer plusieurs brouillons nommés dans le formulaire : le brouillon reste unique, et
  une expérience enregistrée est justement le moyen de garder plusieurs plans côte à côte.
- Ne pas vérifier à l'enregistrement que le jeu, la population ou le modèle existent : c'est le
  rôle du lancement, qui refuse déjà avec ses motifs.
- Ne pas modifier la validation de la plateforme ni le schéma de l'expérience.
- Ne pas toucher aux exécutions archivées, ni à leur copie figée de la définition.
- Ne pas permettre d'enregistrer une expérience dont le nom est vide ou hors motif.

## Sécurité

- Application locale, mono-utilisateur, sans authentification — inchangé.
- Le nom d'expérience devient un dossier : il reste validé comme aujourd'hui (lettres, chiffres,
  tiret, souligné, point, 64 au plus). C'est la seule saisie qui construit un chemin sur l'hôte.
- Le nom du jeu attendu est **calculé**, jamais saisi : population et date viennent de listes ou
  d'un sélecteur de date.
- L'écriture reste atomique et confinée à `data/experiences/<nom>/experience.yaml`. Rien n'est
  écrit sous `executions/`.

## Questions ouvertes

1. **Un bouton ou deux ?** Défaut retenu : un seul bouton « 💾 Enregistrer », qui tente la
   validation quand `controller` tourne et le dit sinon. L'autre lecture serait deux boutons,
   « Enregistrer » et « Valider », au prix d'un quatrième bouton dans une rangée déjà pleine.
2. **Jeu attendu ou jeu vide ?** Défaut retenu : l'expérience nomme le jeu qu'elle attend, ce qui
   la rend lançable sans retouche dès le warm-up terminé. L'autre lecture serait un `jeu.nom`
   vide à compléter plus tard, qui obligerait à rouvrir le formulaire.
3. **Écrasement d'un nom déjà exécuté** : confirmation obligatoire (défaut retenu) ou simple
   avertissement ?
