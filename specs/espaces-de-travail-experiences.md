# Espaces de travail du registre d'expériences

## Problème

Le registre « Mes expériences » du tableau de bord affiche les cinquante-sept expériences du
dépôt sans distinction. Quand un chantier n'en concerne que seize, les quarante et une autres
sont du bruit permanent : elles allongent le tableau, diluent les filtres et obligent à
relire les noms pour retrouver la ligne qui compte. Le seul découpage existant, le statut
(actif, archivé, invalidé), dit si une expérience est utilisable, pas à quel travail elle
appartient.

## Utilisateurs

L'auteur du dépôt, seul utilisateur du tableau de bord, qui le lance en local par
`make dashboard`. Aucun contrôle d'accès : qui ouvre la page a tous les droits. Le tableau de
bord tourne sur la machine de l'auteur et n'est pas exposé.

## Règles métier

**R1** — Un espace de travail porte un nom et une liste ordonnée de noms d'expériences.
Plusieurs espaces coexistent.

**R2** — Un menu déroulant, visible en tête du registre, choisit l'espace actif parmi les
espaces définis, plus une entrée « Toutes les expériences » toujours présente en première
position.

**R3** — « Toutes les expériences » est l'espace actif par défaut au premier lancement, et le
registre s'y comporte exactement comme aujourd'hui.

**R4** — Quand un espace nommé est actif, le registre n'affiche que les expériences de sa
liste. Les filtres, tris et compteurs existants opèrent sur ce sous-ensemble et sur lui seul.

**R5** — L'espace actif survit au rechargement de la page et au redémarrage du tableau de
bord.

**R6** — Un espace nommé « papier version courte » existe. Il contient les expériences des
quatre phases du ticket 103, les trois expériences optionnelles, et les expériences déjà
mesurées sur c1 sans lesquelles les nouvelles ne se lisent pas.

**R6a** — Chaque entrée d'un espace porte une étiquette de phase, libre, affichée par le
registre dans une colonne et servant de regroupement. Le nom de l'expérience, lui, reste
calculé depuis ses paramètres et ne porte aucune marque de phase.

**R6b** — Une entrée peut être marquée optionnelle. Le registre la distingue visiblement des
entrées retenues, et l'affiche par défaut.

**R7** — Changer d'espace ne modifie, ne déplace ni ne supprime aucune expérience. Un espace
est une vue, pas un rangement.

**R8** — Une expérience peut appartenir à plusieurs espaces à la fois.

**R9 (déduite)** — Un nom listé dans un espace sans dossier correspondant sur le disque
n'est pas une erreur. L'espace est écrit avant que les expériences existent, et le registre
le signale sans se casser : la ligne est annoncée comme attendue, et le compte des manquantes
est affiché.

**R10 (déduite)** — Une expérience présente sur le disque et citée par aucun espace reste
visible dans « Toutes les expériences ». Aucune expérience ne devient invisible du seul fait
qu'un espace existe.

**R11 (déduite)** — Un espace dont la liste est vide s'affiche, avec un message qui le dit.
Il ne se confond pas avec « Toutes les expériences ».

**R12 (déduite)** — Le filtrage par espace se compose avec le masquage par statut : dans un
espace, une expérience archivée ou invalidée reste hors de la vue par défaut, comme
aujourd'hui, et le panneau de statuts la compte.

**R13 (déduite)** — Si le fichier qui définit les espaces est absent, illisible ou
syntaxiquement invalide, le tableau de bord démarre avec le seul « Toutes les expériences »
et journalise l'anomalie. Un espace mal écrit ne rend jamais le registre inaccessible.

**R14 (déduite)** — Si l'espace mémorisé comme actif n'existe plus au démarrage, le registre
retombe sur « Toutes les expériences » et le dit une fois.

**R15** — Le sélecteur « s'inspirer d'une expérience existante » du formulaire de création
est filtré par l'espace actif, comme le registre.

**R16 (déduite)** — Les vues qui rendent compte de ce qui tourne — activités en cours,
reprises, file d'attente — ne sont jamais filtrées par l'espace actif. Une exécution en cours
reste visible quel que soit l'espace choisi, sans quoi un run se perdrait de vue en changeant
de menu.

## Critères d'acceptation

| Règle | Entrée | Sortie attendue |
|---|---|---|
| R1 | Deux espaces définis, l'un de trois noms, l'autre de un | Les deux sont lus, avec leurs listes dans l'ordre écrit |
| R2 | Registre affiché | Un menu déroulant liste « Toutes les expériences » en premier, puis les espaces définis |
| R3 | Aucun espace jamais choisi | L'espace actif est « Toutes les expériences » et le tableau contient les mêmes lignes qu'avant la fonctionnalité |
| R4 | Espace de trois expériences actif, cinquante-sept sur le disque | Le tableau contient au plus trois lignes, et le compteur annonce trois |
| R5 | Choisir un espace, recharger la page | L'espace choisi est toujours actif |
| R6 | Espace « papier version courte » actif | Les seize expériences des phases 1 à 4 du ticket 103 sont listées, et aucune autre |
| R7 | Choisir un espace, puis « Toutes les expériences » | Les cinquante-sept expériences sont de nouveau listées, aucun fichier du dépôt n'a changé |
| R8 | Une expérience citée par deux espaces | Elle apparaît dans les deux |
| R9 | Espace citant un nom sans dossier | Le registre s'affiche, la ligne est marquée attendue, le nombre de manquantes est annoncé |
| R10 | Une expérience citée par aucun espace | Elle apparaît dans « Toutes les expériences » |
| R11 | Espace à liste vide actif | Le tableau est vide et un message nomme l'espace |
| R12 | Espace contenant une expérience archivée | Elle est hors du tableau par défaut et comptée dans le panneau de statuts |
| R13 | Fichier de définition tronqué en plein milieu | Le registre s'ouvre sur « Toutes les expériences », un avertissement est journalisé |
| R14 | Espace actif mémorisé, puis retiré du fichier | Le registre s'ouvre sur « Toutes les expériences » et l'annonce une fois |
| R6a | Espace actif avec trois phases | Une colonne de phase est affichée, les lignes sont regroupées par phase |
| R6b | Espace contenant une entrée optionnelle | Elle est visible et distinguée des entrées retenues |
| R15 | Espace de trois expériences actif | Le sélecteur « s'inspirer de » propose ces trois-là, plus « partir de zéro » |
| R16 | Espace actif ne citant pas l'expérience en cours d'exécution | Le panneau « activités en cours » l'affiche quand même |

## Non-goals

- **Pas de création ni d'édition d'espace depuis l'interface.** Les espaces se déclarent dans
  un fichier du dépôt, versionné, relu en diff. Un bouton « nouvel espace » viendra si le
  besoin se confirme.
- **Pas d'affectation automatique.** Aucune expérience n'entre dans un espace parce que son
  nom, son ticket ou sa population y ressemble.
- **Pas de filtrage des campagnes, des jeux ni des populations.** L'espace ne porte que sur
  le registre d'expériences.
- **Pas de droits, pas de partage, pas d'espace privé.** Un seul utilisateur.
- **Pas de suppression.** Retirer une expérience d'un espace ne la retire pas du disque, et
  aucun chemin de l'interface ne doit le laisser croire.

## Sécurité

Le tableau de bord est local et sans authentification ; la fonctionnalité n'ajoute ni
compte, ni droit, ni secret. La seule entrée nouvelle est le fichier de définition des
espaces, qui vit dans le dépôt et n'est écrit que par l'auteur. Il est traité comme une
donnée, pas comme du code : aucune valeur qu'il contient n'est évaluée, et un nom
d'expérience qu'il cite ne sert qu'à filtrer un tableau, jamais à construire un chemin de
fichier ni une commande. Un nom contenant un séparateur de chemin ou des caractères de
contrôle ne doit ouvrir aucun fichier hors de `data/experiences/`. Le fichier étant
faillible par accident plus que par malveillance, R13 exige qu'il échoue ouvert : le
registre reste utilisable quoi qu'il contienne.

## Décisions

Tranchées par l'auteur le 2026-09-22, en réponse aux questions posées avant l'écriture.

1. **Le fichier vit auprès du tableau de bord**, avec les statuts de tickets. Versionné,
   relu en diff.

2. **Toutes les expériences des phases sont déclarées maintenant**, y compris celles qui
   n'ont jamais tourné, et celles qui existent déjà sont reprises dans l'espace plutôt que
   recréées.

3. **Les trois expériences différées figurent dans l'espace, marquées optionnelles** (R6b).
   La décision de les couper reste ainsi visible au lieu de disparaître.

4. **Le sélecteur filtre aussi « s'inspirer de »** (R15).

## Réserve sur le nommage

L'auteur a demandé des noms qui rattachent chaque expérience à sa phase. C'est impossible
sans rompre la spec `nommage-canonique-experiences` : le nom d'une expérience est dérivé de
ses paramètres, il est son identité de dossier et sa clé de dédoublonnage, et un segment
décoratif y produirait deux noms pour un même jeu de paramètres. Le rattachement passe donc
par l'étiquette de phase de l'espace (R6a), qui est une annotation de vue et ne touche ni le
dossier ni l'identité.
