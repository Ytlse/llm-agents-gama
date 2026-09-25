# Ticket 111 — Décisions, hypothèses, points à vérifier

## Décisions de l'auteur (2026-09-25)

**D1 — La lecture est servie systématiquement au lecteur.** Quelle que soit la gravité jugée,
dans « Ce qui a changé récemment ».

**D2 — Le mécanisme agit au rendu du prompt.** Deux autres voies ont été écartées :

- *Invalider puis recalculer* les décisions pré-calculées : une décision laisse des traces dès
  son calcul — ligne de `moves.csv`, véhicules garés (`_park_vehicles`, `_settle_vehicles_at_home`),
  souvenirs renforcés par le rappel, trace de rejeu, compteurs du jeu. En oublier une, c'est une
  ligne en double ou une voiture garée au bout d'une chaîne annulée.
- *Retenir le pré-calcul* jusqu'à la lecture : faisable, le jour de lecture étant connu d'avance,
  mais il faut garder cinq sites de dispatch, trois branches du scan et les vagues du bootstrap,
  reconstruire la profondeur de file en rafale à 00:00, et le lecteur déciderait avec une mémoire
  plus fraîche de dix-sept heures que dans le bras témoin.

**D3 — Durée : 5 jours de déplacement.** Jours ouvrés quand `no_weekend_departures` est actif, le
jour de lecture comptant comme jour 1. Motif : le jour de lecture est tiré entre les jours 9 et 13,
et cinq jours calendaires ne donneraient que trois jours de décisions à certains foyers. Au-delà,
règles ordinaires.

**D4 — Le lecteur transmet à sa famille, un message par destinataire** (idée 2). Un appel LLM de
plus par foyer ; le lecteur peut ne rien dire à certains. Écartés :

- le récit identique pour tout le foyer (idée 1) : ce n'est pas une transmission d'une personne à
  une autre ;
- le journal laissé sur la table (idée 3) : aucune transmission ;
- la conversation du dîner (idée 4) : trop complexe ;
- le bouche-à-oreille tiré selon la personnalité (idée 5) : possible, non retenu.

**D5 — Pour un mineur, le message est la décision des parents** (E1). Motif, dans les mots de
l'auteur : une version simplifiée pour un enfant ne le fera pas changer de trajet, alors que
dans la réalité ce sont les parents qui décident. Écartés :

- E2, le parent qui décide le trajet de l'enfant : fidèle, mais ne vaudrait que s'il s'appliquait
  à tous les enfants de tous les runs — un autre ticket, si l'auteur le souhaite un jour ;
- E3, l'enfant qui voit le bloc de ses parents : mécanisme général qui change les autres
  expériences.

**D6 — L'enquête d'affinité voit la même ligne** que la décision pendant les jours de service.

**D7 — Chez le destinataire** : écriture en mémoire courte et longue, `origine: entendu` (jamais
retransmis, garde G3), jugement par le destinataire lui-même, enfants compris.

**D8 — Le contrôle après run est branché sur `make report`** dans ce ticket.

**D9 — Pas de run de validation** pour l'instant.

**D10 — Travail sur une branche**, fusionnée sur `main` à la fin.

## Hypothèses prises sans question

- **H1** — Les deux clés `service` et `relais` sont posées dans les cinq articles (`a07`, `a09`,
  `a13`, `a18`, `a25`), le défaut touchant tout le canal `lu`. À retirer d'un article si l'auteur
  le souhaite.
- **H2** — Âge absent : le membre est traité en adulte, avec un WARNING, comme pour le tirage des
  lecteurs.
- **H3** — Clés absentes d'une déclaration : comportement d'avant ce ticket, journalisé au
  chargement.
- **H4** — Un message long n'est pas tronqué ; sa longueur est tracée.

## À vérifier au moment d'implémenter

- **V1** — `foyer.autres_membres` ou la population donnent-ils bien le prénom, l'âge,
  l'occupation, les modes habituels et les trajets du jour de chaque membre ? Sinon, construire la
  fiche depuis `Person.identity`.
- **V2** — L'ordre des opérations dans `llm_agent.py` : les lignes doivent être connues avant
  `llm_cache.lookup` (~l. 1202), et le bloc de mémoire se construit plus bas (~l. 922, dans une
  méthode à relire).
- **V3** — `temoin.texte_injecte` reconnaît-il les préfixes par une liste ? Y ajouter
  `[ FOYER ]`.
- **V4** — Relire les numéros de ligne cités par le plan, écrit sur `50115a2`.

## Hors périmètre, noté en passant

- Le concept tiré de l'article par la réflexion du lecteur porte `origine: vecu`
  (`286920_26` dans `2026-09-24_17_50`), alors qu'il vient d'une entrée `lu`. À instruire à part :
  la provenance compte pour le tableau des quatre voies.
- La mesure de présence au prompt tous canaux confondus reste l'objet du ticket 110.
