# Spec 03 — Exécution sans simulateur (ticket 035, `S`)

## Problème

Une part des expériences ne demande que « quelles options a-t-on proposées, qu'a répondu le
décideur ». Elles paient pourtant aujourd'hui le démarrage de GAMA, le routage en vol et une
journée simulée de plus d'une heure et demie. Il faut dérouler la journée d'une cohorte sur un jeu
enregistré, avec la décision unique, sans simulateur — et que le résultat soit indiscernable de ce
que la simulation aurait décidé.

## Utilisateurs

- **Le chercheur** : lance une expérience en mode sans simulateur depuis la plateforme, suit
  l'avancement, met en pause, arrête.
- **Le registre** (spec 06) : reçoit un résultat archivé de même forme que celui du mode simulateur.

## Règles métier

- **S1** — Une exécution sans simulateur prend une expérience (spec 06) dont le mode est « sans
  simulateur » et déroule, pour chaque personne, ses déplacements de la journée **dans l'ordre
  horaire**, en appelant la décision unique (spec 02) avec les propositions du jeu enregistré (spec 01).
- **S2** — Aucun moteur de routage n'est sollicité. Un déplacement absent du jeu est tracé
  « non couvert » et **n'est pas décidé** ; il compte dans la couverture (spec 06), jamais dans les
  parts modales. Un déplacement couvert par le jeu mais **sans aucune proposition** des moteurs
  est tracé « inexploitable » : **exclu des attendus** (aucun décideur ne peut le trancher),
  affiché à côté de la couverture et remonté en WARNING (décision de l'auteur, 2026-09-06).
- **S3** — Ce mode **refuse** avant lancement toute expérience qui active la mémoire, porte un
  événement vécu (incident de réseau), ou demande un horizon supérieur à une journée, avec le
  message : « ces questions relèvent du mode simulateur » (EF-33).
- **S4** — **Regroupement libre, résultat indiscernable.** Le système peut regrouper les décisions de
  plusieurs personnes dans une même sollicitation et les paralléliser, sous deux conditions : le
  résultat est identique, décision par décision, à une exécution séquentielle ; et **la dépendance D4
  est respectée** — deux déplacements d'une même personne ne sont jamais décidés dans le même lot ni
  en parallèle.
- **S5** — Le **régime de regroupement effectivement appliqué** (taille de lot demandée, tailles
  réellement servies, parallélisme) est enregistré dans le résultat, sollicitation par sollicitation.
- **S6** — **Avancement visible** pendant l'exécution : déplacements décidés / attendus, personnes
  terminées, temps écoulé, temps restant estimé à partir du débit observé, sollicitations du
  décideur, erreurs par type. Rafraîchi au moins toutes les 5 secondes.
- **S7** — L'exécution se termine par un résultat archivé (spec 06) **dans la même forme** que celui
  du mode simulateur : mêmes traces de décision, mêmes empreintes, même couverture.
- **S8** *(déduite)* — Une exécution **journalise** début, fin, durée, compteurs (décidés, non
  couverts, sans solution, choix unique, replis, erreurs) et **annonce le succès** explicitement.
- **S9** *(déduite)* — Une exécution est **reprenable** au déplacement près (spec 05) : un déplacement
  déjà décidé et archivé n'est jamais redemandé au décideur.
- **S10** *(déduite)* — Le décideur d'une expérience peut être **local et déterministe** (heuristique,
  modèle supervisé) : l'exécution ne suppose jamais un service réseau, et un décideur local ne
  consomme aucun quota (les compteurs de S6 l'affichent à 0).
- **S11** *(déduite)* — La date de chaque personne suit la **politique de calendrier** de l'expérience
  (spec 06) ; météo et jour de semaine du texte présenté au décideur en découlent, jamais de l'horloge
  du processus.

## Critères d'acceptation

- **S1** — Personne à 3 déplacements → 3 appels de la décision unique dans l'ordre horaire, l'état des
  véhicules du 2ᵉ appel étant celui laissé par le 1ᵉʳ.
- **S2** — Jeu couvrant 2 539 / 2 579 → 40 déplacements « non couverts », 0 appel moteur, parts modales
  calculées sur 2 539 et couverture affichée 98,4 %.
- **S3** — Expérience mémoire activée + mode sans simulateur → refus avant lancement avec le message
  attendu ; idem horizon = 5 jours ; idem incident à J2.
- **S4** — Même expérience exécutée avec lot = 1 puis lot = 10 → traces de décision identiques
  (décideur de rejeu) ; aucun lot ne contient deux déplacements d'une même personne.
- **S5** — Résultat d'une exécution en lot = 10 : chaque sollicitation porte sa taille réelle ; la
  distribution des tailles est affichée dans la synthèse.
- **S6** — À 71 % d'avancement, l'affichage donne décidés / attendus, temps écoulé, estimation du
  restant, nombre de sollicitations, erreurs ; deux lectures à 5 s d'intervalle diffèrent.
- **S7** — Un résultat sans simulateur et un résultat simulateur se chargent avec le **même** lecteur
  et passent la même validation d'archive.
- **S8** — Journal d'une exécution terminée : une ligne de succès avec durée et six compteurs.
- **S9** — Interrompre à 1 300 décisions, reprendre → exactement 1 279 sollicitations
  supplémentaires (sur 2 579), et le résultat final est identique à celui d'une exécution
  ininterrompue (décideur de rejeu).
- **S10** — Décideur « durée minimale » → 2 579 décisions, 0 requête réseau, quota affiché 0 / N.
- **S11** — Politique « date propre à chaque personne » : deux personnes de dates différentes lisent
  des météos et des jours de semaine différents ; sous `TZ=UTC` et `TZ=Europe/Paris`, textes identiques.

## Non-goals

- Pas de déplacement physique, pas de congestion vécue, pas de mémoire, pas d'incident : c'est le
  mode simulateur (spec 04).
- Pas de calcul de score dans l'exécution : elle produit des décisions, la restitution (spec 06) note.
- Pas d'optimisation du coût par réutilisation d'un cache sémantique : chaque décision non archivée
  est demandée au décideur (RG-2).

## Sécurité

- Les réponses du décideur distant sont hostiles par défaut (voir spec 02).
- L'exécution n'écrit **aucun secret** dans le résultat : les fournisseurs y sont désignés par nom
  d'instance, jamais par clé.
- Une exécution ne lit que la population, le jeu et l'expérience désignés : aucun accès à
  `experiments/current` ni à un autre résultat, sauf le décideur de rejeu qui cite l'archive lue.

## Questions ouvertes

1. **Unité de sollicitation** (ticket §7.1) : une question par déplacement (comportement actuel,
   « unité d'évaluation = déplacement » dans le protocole) ou une question par personne couvrant sa
   journée ? La seconde rend S4 caduque (plus de lot inter-personnes possible sur la chaîne) et change
   l'estimation de coût de la spec 06.
2. **Regroupement figé** (ticket §7.6) : quand deux décideurs comparés n'acceptent pas la même taille
   de lot, faut-il imposer une taille commune pour que la comparaison reste propre ? Si oui, la règle
   de comparabilité de la spec 06 inclut le régime S5.
3. **Horizon > 1 jour sans simulateur** : S3 le refuse. Alternative : D journées **indépendantes**
   (état des véhicules réinitialisé chaque matin, aucune mémoire) — utile pour une politique « date
   propre à chaque personne » sur plusieurs jours d'enquête ? À trancher.
