---
name: suivi-tickets
description: Tient à jour l'état des tickets de `docs/tickets/` dans `scripts/dashboard/tickets_status.yaml`. À utiliser dès qu'un chantier commence, avance ou se termine, et quand on demande « mets à jour les statuts », « où en sont les tickets », « fais un passage sur les tickets ouverts ». Passe un ticket commencé à `en cours`, le passe à `terminé` quand tous ses points sont traités, débloque en cascade ceux qu'il bloquait et annonce « Ticket XXX est maintenant faisable ». Ne juge pas la priorité à la place de l'auteur.
---

# Tenue des statuts de tickets

La source de vérité est **`scripts/dashboard/tickets_status.yaml`**, jamais l'en-tête d'un
`.md` : un `**Statut**` recopié dans chaque ticket se périme en silence, et il y en a
quatre-vingts à tenir.

## Règle 1 — un ticket commencé passe `en cours`, le jour où il commence

Dès qu'une ligne de code, de spec ou de texte est écrite pour un ticket, son statut passe
`en cours` et sa note dit **ce qui est livré** et **ce qui reste**. Pas à la fin, pas au
prochain passage : une session qui livre trois lots et laisse `à faire` fait chercher à la
suivante un travail déjà fait.

La note s'écrit en **ajoutant** à la suite, jamais en réécrivant : elle porte l'historique des
décisions. Chaque ajout est daté (`AVANCE DU 2026-09-16 :`, `LIVRÉ le …`), et il cite sa preuve
— un fichier, un numéro de ligne, un compte de tests, un chiffre mesuré. Une note sans preuve
ne se vérifie pas au passage suivant.

⚠ **Une note vieillit par sa PREMIÈRE phrase.** C'est celle qu'on ne réécrit pas en ajoutant
« LIVRÉ » à la fin, et c'est celle que le triage lit. Le ticket 048 a porté pendant cinq jours
une note qui ouvrait sur « rien n'est lancé » et finissait sur « LIVRÉ, les trois points de
code » — le triage avait cru la première et ouvert un faux conflit avec un autre ticket.

## Règle 2 — tous les points traités : `terminé`, puis débloquer, puis le dire

Quand **tous** les points du ticket sont traités — critères d'acceptation cochés, lots livrés,
questions tranchées :

1. **Statut `terminé`**, et la note dit sur quoi ça s'appuie.
2. **Retirer son bloc `triage`.** Un ticket clos ne se trie pas : on ne se demande pas si un
   ticket terminé est faisable. Une épreuve du dépôt le vérifie
   (`test_R34_les_tickets_clos_ne_portent_pas_de_triage`), et un triage oublié sur un ticket
   clos à drapeau fausse en plus le compte des tickets touchant les jeux de test.
3. **Débloquer en cascade.** Chercher les tickets dont la note porte `DÉPEND DE : <ce ticket>`,
   et pour chacun : s'il n'a plus aucun bloquant ouvert, le repasser à son statut de travail
   (`à faire`, ou `en cours` s'il était commencé), et ajouter à sa note ce qui l'a libéré.
4. **L'annoncer dans la réponse**, une ligne par ticket libéré :

   > **Ticket 063 est maintenant faisable** — son bloquant 041 est terminé.

   Un déblocage silencieux ne sert à rien : personne ne relit quarante notes pour découvrir
   qu'un chantier est devenu prenable.

Si un seul point reste, le ticket **ne passe pas** `terminé`. Ce qui n'a pas été exécuté part
dans un ticket neuf plutôt que de garder ouvert un chantier fait à 90 % — c'est ce qui a été
fait du 045, dont le reliquat est devenu le 076.

## Règle 3 — `bloqué` veut dire : un autre TICKET ouvert manque

Convention du 2026-09-16, rappelée dans l'en-tête du fichier de statuts :

- un ticket qui ne peut pas être **entièrement** fait avant la fin d'un autre ticket ouvert est
  `bloqué`, et sa note nomme le bloquant sur une ligne **`DÉPEND DE : 0XX — raison`** ;
- un blocage qui **n'est pas un ticket** — accord de l'auteur, verrou de l'article, quota,
  événement attendu — ne bascule PAS le statut : il se dit dans la note sous la forme
  `DÉPEND DE : aucun ticket — <ce qui manque>`. Annoncer `bloqué` ferait chercher un déblocage
  technique qui n'existe pas ;
- `en veille` ≠ `bloqué` : rien n'empêche d'avancer, c'est une décision de ne pas le faire
  maintenant ;
- un ticket en `amélioration` ne bascule pas : rien n'est attendu de lui, et le dire bloqué
  laisserait croire qu'il partirait si on le débloquait.

Avant de poser un `bloqué`, **vérifier que le bloquant est bien ouvert** : une dépendance
éteinte est fréquente (le 036 se croyait bloqué par le 037, dont le lot attendu était livré).

## Comment vérifier un statut, et sur quoi ne pas se fier

Un statut se vérifie **contre l'état réel**, pas contre les notes :

| Où regarder | Ce que ça prouve |
|---|---|
| `docs/changelog.md`, en tête | ce qui a été livré, et quand |
| `git log --oneline` | le code qui a bougé |
| le fichier de l'article | une passe de rédaction (`ticket 0XX appliqué` dans la ligne de statut) |
| `campagnes/*/etat.json`, `ps` | une campagne qui tourne, ou qui ne tourne plus |
| les `- [ ]` du ticket | ce qui reste vraiment à cocher |

Trois pièges déjà rencontrés, tous silencieux :

- une **campagne citée par une note peut avoir été supprimée** depuis (trois l'ont été le
  16/09, leur substrat étant faux) ;
- un ticket peut avoir **un `.md` et aucune ligne de statut** : il n'apparaît alors dans aucun
  classement. Comparer la liste des fichiers et les clés du YAML ;
- **deux tickets peuvent porter le même numéro** (005, 014, 087). La clé est le nom de fichier
  complet, jamais la forme courte.

## Mécanique du fichier

- Les notes sont des scalaires pliés (`>-`) : indentation de **6 espaces** sous `note:`, de
  **8** sous `triage.motif:`. Une ligne dédentée casse le YAML.
- Un retour à la ligne automatique ne doit **jamais couper un mot sur un tiret** : le pliage
  recolle avec une espace et produit `non- monotonie`.
- Après écriture : relire le fichier avec un parseur YAML, puis lancer
  `services/llm-agents/.venv/bin/python -m pytest scripts/tests/test_dashboard_tickets_status.py -q`.
- **D'autres sessions écrivent ce fichier.** Le relire juste avant d'écrire, et ne jamais
  réécrire un bloc à partir d'une lecture vieille de plusieurs minutes.

## Ce que cette skill ne fait pas

Elle ne décide pas de la **priorité** ni de l'**intérêt AAMAS** à la place de l'auteur : les
deux échelles de triage et l'axe ⭐ se posent avec leur raison écrite, et une note ou un statut
qui demande un arbitrage se **signale** au lieu d'être tranché — « à l'auteur de dire si cela
suffit à clore le ticket ».
