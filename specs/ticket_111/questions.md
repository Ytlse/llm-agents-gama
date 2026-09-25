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

### Ajoutées à l'implémentation (2026-09-25)

- **H1 bis** — Les clés sont aussi posées dans les trois variantes `lu` dérivées :
  `a09_vent_autan__population_20_foyers_059`, `a09_vent_autan__population_4_foyer_133048` et
  `a13_punaises_metro__banc`. Huit déclarations en tout. Sans elles, les expériences qui jouent
  ces variantes garderaient le défaut.
- **H5** — `relais` exige `service`, le canal `lu` et une règle `foyers`. `service` est refusé
  sur un événement qui n'est pas `moment: reveil`. Un choc vécu s'applique après la décision, et
  une garantie au rendu n'y aurait pas de sens.
- **H6** — Une décision qui doit porter une ligne ne lit pas le cache de décisions et n'y est
  pas stockée. La clé du cache ne porte pas la ligne : une lecture la priverait de sa ligne, et
  une écriture la resservirait à un non-lecteur. Chaque contournement est compté.
- **H7** — Un lecteur déclaré non avenu emporte ses informés : sans lecture, il n'y a rien à
  transmettre. Une seule `[ALARME]` donne le nombre de décisions déjà servies avec la ligne.
- **H8** — Les clés du schéma de sortie sont en anglais (`recipients`, `speaks`, `message`),
  comme le gabarit. `valider()` accepte aussi les formes françaises `destinataires` et `parle`.
- **H9** — `directif` est vrai quand le message porte une famille directive, ou quand il
  s'adresse à un mineur : une décision parentale dit ce que l'enfant fera. La trace le dit, sans
  rien refuser.

### Ajoutées après la revue de conformité (spec-critic, 2026-09-25)

- **H10** — À la reprise, `_ont_lu` et `_entendus` se relisent dans `evenements.jsonl`, qui ne
  porte que des injections abouties. Passé le jour de lecture, un lecteur absent du journal ne
  sert plus de ligne, pas plus que ses informés, et une seule `[ALARME]` le dit. Le jour même,
  on sert.
- **H11** — Un lecteur sans autre membre mobile produit un relais **vide** : pas d'appel, pas
  d'alarme, et un compteur à part (`relais_sans_membre`). Ce n'est pas un refus.
- **H12** — Sous `lecteurs_par_foyer > 1`, seul le premier lecteur relaie, et un membre déjà
  informé n'est jamais réécrit.
- **H13** — Les décideurs du banc (`decideur_typesafe`, `decideur_antigravity`) portent la ligne
  comme les bras LLM.
- **H14** — Les lignes `origine: entendu` ne comptent pas comme des expositions : contrôle 108,
  table des chocs de `mesures/calcul.py`, compte de `figure_rupture_retour.py`. Le tableau des
  quatre voies range les co-résidents sous leurs sous-rôles.

### Tranché par l'auteur

- **Q1 — tranchée le 2026-09-25 : « 2 retry max ».** Un refus d'origine technique n'est pas
  gravé : une reprise retente, deux fois au plus (trois tentatives), puis le refus devient
  définitif. Un refus sur le contenu reste définitif dès la première fois. La question telle
  qu'elle était posée : une panne du fournisseur pendant le relais (réponse vide après la file d'attente du
  client, ou exception) est traitée comme un **refus définitif**, écrit dans
  `relais_foyer.jsonl`, et la reprise ne réessaie pas. C'est le même régime que le jugement :
  une réponse vide y déclare l'exposition non avenue. Le choix est fait pour la cohérence
  interne du run, puisque les membres ne voient rien de tout le run plutôt qu'une partie. La
  contrepartie : un foyer frappé par une panne sort de la mesure « informé », et l'`[ALARME]`
  est le seul signal. Autre possibilité : ne pas graver les refus d'origine technique, pour
  qu'une reprise retente, au prix de membres informés en cours de service sans entrée en
  mémoire du jour de lecture.

### Constaté en passant, antérieur au ticket

- Les compteurs journaliers basculent de jour sur l'horodatage de la dernière décision. Or
  `noter_decision` reçoit tantôt le jour du trajet, tantôt celui du `/sync`, si bien qu'une
  décision pré-calculée la veille peut remettre les compteurs à zéro en cours de journée. Le
  ticket 111 appelle `noter_decision` **avant** `noter_contournement_cache` pour que ce dernier
  compteur survive. Le va-et-vient lui-même n'est pas corrigé.

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
